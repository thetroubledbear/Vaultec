"""Document management routes: upload, list, download, metadata."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crypto, storage
from app.db import get_db
from app.deps import get_current_user, require_unlocked
from app.models import User, Document, Blob, DocumentVersion, Category

logger = logging.getLogger("vaultec")
router = APIRouter()


class BlobMetadata(BaseModel):
    """Metadata for a blob (file)."""
    filename: str
    mimetype: Optional[str]
    size_bytes: Optional[int]


class DocumentMetadata(BaseModel):
    """Document metadata response."""
    id: str
    title: str
    created_at: str
    category: Optional[str] = None  # category name or null
    owner_id: str
    owner_username: Optional[str] = None
    is_owner: bool = False
    household_id: Optional[str] = None
    blob: Optional[BlobMetadata]


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: List[DocumentMetadata]


class UpdateDocumentRequest(BaseModel):
    """Request to update document metadata."""
    title: Optional[str] = None
    category: Optional[str] = None  # null to clear


class CategoryItem(BaseModel):
    """Category response item."""
    id: str
    name: str
    document_count: int


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_unlocked),
    db: Session = Depends(get_db),
) -> DocumentMetadata:
    """
    Upload and encrypt a document.

    Reads file bytes, encrypts with envelope encryption, deduplicates by plaintext SHA256,
    stores encrypted blob, and creates Document + DocumentVersion rows.
    Document is assigned to the current user's household.

    Requires authentication and vault unlocked.

    Args:
        file: multipart file upload
        title: document title
        category: optional category name (created if doesn't exist)
        current_user: authenticated user
        db: database session

    Returns:
        DocumentMetadata with id, title, created_at, and blob info

    Raises:
        HTTPException 400: if file read/encryption fails
        HTTPException 423: if vault locked
    """
    try:
        # Read file bytes
        file_bytes = await file.read()

        # Encrypt blob
        encrypted = crypto.encrypt_blob(file_bytes)

        # Check if blob with same plaintext_sha256 already exists (dedup)
        existing_blob = db.query(Blob).filter(
            Blob.plaintext_sha256 == encrypted["plaintext_sha256"]
        ).first()

        if existing_blob:
            # Reuse existing blob
            blob = existing_blob
        else:
            # Store encrypted blob and create Blob row
            storage_path = storage.store_blob(encrypted)

            blob = Blob(
                filename=file.filename,
                mimetype=file.content_type,
                size_bytes=len(file_bytes),
                wrapped_dek=encrypted["wrapped_dek"],
                dek_nonce=encrypted["dek_nonce"],
                blob_nonce=encrypted["blob_nonce"],
                plaintext_sha256=encrypted["plaintext_sha256"],
                storage_path=storage_path,
            )
            db.add(blob)
            db.flush()  # Get blob.id

        # Resolve or create category
        category_id = None
        if category:
            cat = db.query(Category).filter(Category.name == category).first()
            if not cat:
                cat = Category(name=category)
                db.add(cat)
                db.flush()
            category_id = cat.id

        # Create Document with household_id from current user's household
        doc = Document(
            owner_id=current_user.id,
            title=title,
            category_id=category_id,
            household_id=current_user.household_id,
        )
        db.add(doc)
        db.flush()

        # Create DocumentVersion (version 1)
        version = DocumentVersion(
            document_id=doc.id,
            blob_id=blob.id,
            version_number=1,
        )
        db.add(version)
        db.commit()

        return _to_metadata(db, doc, current_user)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Document upload failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload failed",
        )


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    List documents visible to the current user. Admins see all active documents.
    Non-admins see documents in their household. Optionally filtered by title search.
    Excludes pending (unvalidated) scanned docs.

    Args:
        q: optional search query (case-insensitive ILIKE %q%)
        current_user: authenticated user
        db: database session

    Returns:
        List of DocumentMetadata (each flags is_owner + owner_username)
    """
    query = db.query(Document)

    # Filter to active documents only (exclude pending scans)
    query = query.filter(Document.status == "active")

    if current_user.role != "admin":
        # Non-admins see documents in their household
        query = query.filter(Document.household_id == current_user.household_id)

    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))

    documents = query.order_by(Document.created_at.desc()).all()

    return DocumentListResponse(
        documents=[_to_metadata(db, doc, current_user) for doc in documents]
    )


def _require_view(doc: Document, current_user: User) -> None:
    """
    Ensure current user may VIEW the document: owner, admin, or in the same household.
    Raises 404 if missing, 403 if not permitted.
    """
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    is_owner = doc.owner_id == current_user.id
    is_admin = current_user.role == "admin"
    is_in_household = doc.household_id is not None and doc.household_id == current_user.household_id
    if not (is_owner or is_admin or is_in_household):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _require_edit(doc: Document, current_user: User) -> None:
    """
    Ensure current user may MODIFY the document: owner or admin only.
    (Sharing lets others view, not edit/delete/re-share.)
    Raises 404 if missing, 403 if not permitted.
    """
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _latest_blob(db: Session, doc: Document) -> Optional[Blob]:
    """Return the Blob of the document's latest version, or None."""
    latest = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id
    ).order_by(DocumentVersion.version_number.desc()).first()
    return latest.blob if latest else None


def _to_metadata(db: Session, doc: Document, current_user: User) -> DocumentMetadata:
    """Build a DocumentMetadata response, including owner + household info."""
    blob = _latest_blob(db, doc)
    blob_meta = None
    if blob:
        blob_meta = BlobMetadata(
            filename=blob.filename,
            mimetype=blob.mimetype,
            size_bytes=blob.size_bytes,
        )
    return DocumentMetadata(
        id=str(doc.id),
        title=doc.title,
        created_at=doc.created_at.isoformat(),
        category=doc.category.name if doc.category else None,
        owner_id=str(doc.owner_id),
        owner_username=doc.owner.username if doc.owner else None,
        is_owner=(doc.owner_id == current_user.id),
        household_id=str(doc.household_id) if doc.household_id else None,
        blob=blob_meta,
    )


@router.get("/categories", response_model=List[CategoryItem])
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[CategoryItem]:
    """
    Get categories for the current user's documents with document counts.
    Excludes pending (unvalidated) scanned docs.

    Declared BEFORE /{doc_id} so the literal path is not shadowed by the
    dynamic doc_id route (FastAPI matches routes in declaration order).
    """
    # Scope by household (admins: all)
    if current_user.role == "admin":
        household_filter = None
    else:
        household_filter = Document.household_id == current_user.household_id

    cat_query = db.query(Category).join(Document, Document.category_id == Category.id).filter(
        Document.status == "active"
    )
    if household_filter is not None:
        cat_query = cat_query.filter(household_filter)
    categories = cat_query.distinct().all()

    result = []
    for cat in categories:
        count_query = db.query(Document).filter(
            Document.category_id == cat.id,
            Document.status == "active",
        )
        if household_filter is not None:
            count_query = count_query.filter(household_filter)
        doc_count = count_query.count()
        result.append(CategoryItem(
            id=str(cat.id),
            name=cat.name,
            document_count=doc_count,
        ))

    return result


@router.get("/{doc_id}", response_model=DocumentMetadata)
def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentMetadata:
    """
    Get single document metadata.

    Enforces ownership (user can only access their own documents; admins can access any).

    Args:
        doc_id: document UUID
        current_user: authenticated user
        db: database session

    Returns:
        DocumentMetadata

    Raises:
        HTTPException 403: if not owner or admin
        HTTPException 404: if document not found
    """
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _require_view(doc, current_user)
    return _to_metadata(db, doc, current_user)


@router.get("/{doc_id}/download")
def download_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_unlocked),
    db: Session = Depends(get_db),
):
    """
    Download and decrypt document (attachment mode).

    Loads latest DocumentVersion → Blob, reads encrypted ciphertext from storage,
    decrypts with crypto.decrypt_blob, and returns as StreamingResponse with
    Content-Disposition: attachment.

    Requires authentication and vault unlocked.

    Args:
        doc_id: document UUID
        current_user: authenticated user
        db: database session

    Returns:
        StreamingResponse with decrypted file content

    Raises:
        HTTPException 403: if not owner or admin
        HTTPException 404: if document not found
        HTTPException 423: if vault locked
    """
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _require_view(doc, current_user)

    # Get latest version
    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id
    ).order_by(DocumentVersion.version_number.desc()).first()

    if not latest_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No versions found")

    blob = latest_version.blob

    try:
        # Read encrypted ciphertext from storage
        ciphertext_bytes = storage.read_blob(blob.storage_path)

        # Decrypt blob (need to pass ciphertext as base64)
        import base64
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        plaintext = crypto.decrypt_blob(
            wrapped_dek=blob.wrapped_dek,
            dek_nonce=blob.dek_nonce,
            blob_nonce=blob.blob_nonce,
            ciphertext=ciphertext_b64,
            plaintext_sha256=blob.plaintext_sha256,
        )

        # Return as streaming response with correct media type and attachment header
        return StreamingResponse(
            iter([plaintext]),
            media_type=blob.mimetype or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={blob.filename}",
                "Content-Length": str(len(plaintext)),
            },
        )

    except Exception as e:
        logger.exception("Document download failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Download failed",
        )


@router.get("/{doc_id}/content")
def get_document_content(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_unlocked),
    db: Session = Depends(get_db),
):
    """
    Get decrypted document content for inline viewing (not attachment).

    Loads latest DocumentVersion → Blob, reads encrypted ciphertext from storage,
    decrypts with crypto.decrypt_blob, and returns as StreamingResponse with
    Content-Disposition: inline (for browser preview).

    Requires authentication and vault unlocked.

    Args:
        doc_id: document UUID
        current_user: authenticated user
        db: database session

    Returns:
        StreamingResponse with decrypted file content (inline)

    Raises:
        HTTPException 403: if not owner or admin
        HTTPException 404: if document not found
        HTTPException 423: if vault locked
    """
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _require_view(doc, current_user)

    # Get latest version
    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id
    ).order_by(DocumentVersion.version_number.desc()).first()

    if not latest_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No versions found")

    blob = latest_version.blob

    try:
        # Read encrypted ciphertext from storage
        ciphertext_bytes = storage.read_blob(blob.storage_path)

        # Decrypt blob
        import base64
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        plaintext = crypto.decrypt_blob(
            wrapped_dek=blob.wrapped_dek,
            dek_nonce=blob.dek_nonce,
            blob_nonce=blob.blob_nonce,
            ciphertext=ciphertext_b64,
            plaintext_sha256=blob.plaintext_sha256,
        )

        # Return as streaming response with inline disposition
        return StreamingResponse(
            iter([plaintext]),
            media_type=blob.mimetype or "application/octet-stream",
            headers={
                "Content-Disposition": f"inline; filename={blob.filename}",
                "Content-Length": str(len(plaintext)),
            },
        )

    except Exception as e:
        logger.exception("Document content fetch failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content fetch failed",
        )


@router.patch("/{doc_id}", response_model=DocumentMetadata)
def update_document(
    doc_id: str,
    request: UpdateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentMetadata:
    """
    Update document metadata (title and/or category).

    Requires ownership or admin role.

    Args:
        doc_id: document UUID
        request: {title?, category?}
        current_user: authenticated user
        db: database session

    Returns:
        Updated DocumentMetadata

    Raises:
        HTTPException 403: if not owner or admin
        HTTPException 404: if document not found
    """
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _require_edit(doc, current_user)

    # Update title if provided
    if request.title is not None:
        doc.title = request.title

    # Update category if provided
    if request.category is not None:
        if request.category == "":
            # Empty string clears category
            doc.category_id = None
        else:
            # Resolve or create category by name
            cat = db.query(Category).filter(Category.name == request.category).first()
            if not cat:
                cat = Category(name=request.category)
                db.add(cat)
                db.flush()
            doc.category_id = cat.id

    db.commit()

    return _to_metadata(db, doc, current_user)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a document and its DocumentVersion rows.

    Does NOT delete Blob rows (blobs are content-addressed and may be shared).

    Requires ownership or admin role.

    Args:
        doc_id: document UUID
        current_user: authenticated user
        db: database session

    Raises:
        HTTPException 403: if not owner or admin
        HTTPException 404: if document not found
    """
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _require_edit(doc, current_user)

    # Delete DocumentVersion rows (cascade will handle this via relationship)
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id
    ).delete()

    # Delete Document row
    db.delete(doc)
    db.commit()
