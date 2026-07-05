"""Validation queue routes: review and approve/reject scanned documents."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Document, Blob, DocumentVersion, Category, ValidationQueue

logger = logging.getLogger("vaultec")
router = APIRouter()


class ValidationItem(BaseModel):
    """Pending validation queue item."""
    queue_id: str
    document_id: str
    title: str
    filename: str
    mimetype: Optional[str]
    size_bytes: Optional[int]
    created_at: str


class ValidationListResponse(BaseModel):
    """List of pending validation items."""
    items: List[ValidationItem]


class ApproveDocumentRequest(BaseModel):
    """Request to approve a scanned document."""
    title: Optional[str] = None
    category: Optional[str] = None
    owner_id: Optional[str] = None


class ValidationCountResponse(BaseModel):
    """Count of pending validations."""
    pending: int


@router.get("/", response_model=ValidationListResponse)
def list_pending_validations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationListResponse:
    """
    List pending validation items.

    Returns all ValidationQueue rows with status='pending' joined with their Document
    and latest Blob. Only includes documents with status='pending'.

    Requires authentication (any household member).

    Args:
        current_user: authenticated user
        db: database session

    Returns:
        List of ValidationItem with queue_id, document_id, title, filename, mimetype, size_bytes
    """
    queue_rows = db.query(ValidationQueue).filter(
        ValidationQueue.status == "pending"
    ).all()

    items = []
    for queue_row in queue_rows:
        doc = db.query(Document).filter(Document.id == queue_row.document_id).first()
        if not doc or doc.status != "pending":
            # Skip if document doesn't exist or is no longer pending
            continue

        # Get latest blob
        latest_version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc.id
        ).order_by(DocumentVersion.version_number.desc()).first()

        if not latest_version:
            continue

        blob = latest_version.blob

        items.append(
            ValidationItem(
                queue_id=str(queue_row.id),
                document_id=str(doc.id),
                title=doc.title,
                filename=blob.filename if blob else "",
                mimetype=blob.mimetype if blob else None,
                size_bytes=blob.size_bytes if blob else None,
                created_at=queue_row.created_at.isoformat(),
            )
        )

    return ValidationListResponse(items=items)


@router.post("/{document_id}/approve", status_code=status.HTTP_200_OK)
def approve_document(
    document_id: str,
    request: ApproveDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Approve a pending scanned document.

    Sets document.status='active', applies optional title/category/visibility/owner_id changes,
    and marks related ValidationQueue rows as done.

    Requires authentication (any household member).

    Args:
        document_id: UUID of the document
        request: optional updates (title, category, visibility, owner_id)
        current_user: authenticated user
        db: database session

    Returns:
        Updated document metadata

    Raises:
        HTTPException 404: if no pending document/queue found
        HTTPException 400: if validation fails (e.g. invalid owner_id)
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc or doc.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending document not found",
        )

    queue_rows = db.query(ValidationQueue).filter(
        ValidationQueue.document_id == document_id,
        ValidationQueue.status == "pending",
    ).all()

    if not queue_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending validation found for this document",
        )

    try:
        # Apply updates if provided
        if request.title:
            doc.title = request.title

        if request.category is not None:
            if request.category == "":
                # Clear category
                doc.category_id = None
            else:
                # Resolve or create category
                cat = db.query(Category).filter(Category.name == request.category).first()
                if not cat:
                    cat = Category(name=request.category)
                    db.add(cat)
                    db.flush()
                doc.category_id = cat.id

        if request.owner_id:
            # Validate owner_id is an active user
            owner = db.query(User).filter(
                User.id == request.owner_id,
                User.is_active == True,
            ).first()
            if not owner:
                raise ValueError("owner_id is not a valid active user")
            doc.owner_id = owner.id
            # Also update household_id to the new owner's household
            doc.household_id = owner.household_id

        # Set status to active
        doc.status = "active"

        # Mark validation queue rows as done
        for queue_row in queue_rows:
            queue_row.status = "done"

        db.commit()

        # Return updated document metadata
        from app.routers.documents import _to_metadata

        return _to_metadata(db, doc, current_user).__dict__

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        db.rollback()
        logger.exception("Approve document failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Approval failed",
        )


@router.post("/{document_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Reject a pending scanned document.

    Deletes the Document, DocumentVersion rows, and ValidationQueue rows.
    The Blob is left in place (content-addressed; may be reused).

    Requires authentication (any household member).

    Args:
        document_id: UUID of the document
        current_user: authenticated user
        db: database session

    Raises:
        HTTPException 404: if no pending document found
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc or doc.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending document not found",
        )

    try:
        # Delete DocumentVersion rows (cascade will handle dependent extractions)
        db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id
        ).delete()

        # Delete ValidationQueue rows
        db.query(ValidationQueue).filter(
            ValidationQueue.document_id == document_id
        ).delete()

        # Delete Document
        db.delete(doc)
        db.commit()

        logger.info(f"Rejected document {document_id}")

    except Exception:
        db.rollback()
        logger.exception("Reject document failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Rejection failed",
        )


@router.get("/count", response_model=ValidationCountResponse)
def get_validation_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationCountResponse:
    """
    Get count of pending validations (for nav badge).

    Returns:
        {pending: N}
    """
    count = db.query(ValidationQueue).filter(
        ValidationQueue.status == "pending"
    ).count()

    return ValidationCountResponse(pending=count)
