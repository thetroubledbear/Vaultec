"""Processing pipeline: OCR → chunk → embed worker."""

import asyncio
import base64
import logging

from app import ai, crypto, storage
from app.config import get_settings
from app.db import SessionLocal
from app.models import Document, DocumentVersion, Extraction, Embedding

logger = logging.getLogger("vaultec")


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks of approximately size characters.

    Uses sliding window with step = max(1, size - overlap). Strips
    whitespace-only chunks.

    Args:
        text: text to chunk
        size: target chunk size in characters
        overlap: overlap between consecutive chunks in characters

    Returns:
        list of non-empty text chunks
    """
    if size <= 0:
        return []

    step = max(1, size - overlap)
    chunks = []

    for i in range(0, len(text), step):
        chunk = text[i : i + size]
        chunk = chunk.strip()
        if chunk:  # Skip empty chunks
            chunks.append(chunk)
        # Avoid infinite loop on very small step
        if step == 1 and i + size >= len(text):
            break

    return chunks


async def process_document(doc_id) -> None:
    """
    Process a document: decrypt, extract text, chunk, and embed.

    Opens its own SessionLocal (caller should not pass a session).
    Requires crypto.is_unlocked(). All OCR/extraction stays local.

    Steps:
    1. Load Document; if not found or no versions/blobs, return early.
    2. Delete existing Extraction rows (cascade deletes embeddings).
    3. Decrypt latest version blob.
    4. Extract text via ai.extract_text.
    5. If text is empty, create an Extraction row anyway (mark done).
    6. If text exists, create Extraction, chunk, embed, and insert Embedding rows.
    7. Commit or rollback on exception.

    Args:
        doc_id: UUID of document to process

    Raises:
        Exception on processing failure (logged, re-raised)
    """
    db = SessionLocal()
    try:
        # Load document
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.warning(f"Document {doc_id} not found")
            return

        # Delete existing extractions (cascade deletes embeddings)
        db.query(Extraction).filter(Extraction.document_id == doc_id).delete()
        db.flush()

        # Get latest version
        latest = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc_id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )

        if not latest or not latest.blob:
            logger.info(f"Document {doc_id} has no versions or blobs")
            return

        # Decrypt blob
        blob = latest.blob
        try:
            ciphertext_bytes = storage.read_blob(blob.storage_path)
            plaintext = crypto.decrypt_blob(
                wrapped_dek=blob.wrapped_dek,
                dek_nonce=blob.dek_nonce,
                blob_nonce=blob.blob_nonce,
                ciphertext=base64.b64encode(ciphertext_bytes).decode("ascii"),
                plaintext_sha256=blob.plaintext_sha256,
            )
        except Exception as e:
            logger.error(f"Failed to decrypt document {doc_id}: {e}")
            raise

        # Extract text
        try:
            text, extractor_type, lang = ai.extract_text(
                plaintext, blob.mimetype, blob.filename
            )
        except Exception as e:
            logger.error(f"Failed to extract text from {doc_id}: {e}")
            raise

        # If no text, create an empty extraction anyway (mark as done)
        if not text or not text.strip():
            extraction = Extraction(
                document_id=doc_id,
                extractor_type=extractor_type,
                extracted_text="",
                lang=lang,
                char_count=0,
            )
            db.add(extraction)
            db.commit()
            logger.info(f"Document {doc_id}: no text extracted (extractor={extractor_type})")
            return

        # Create extraction row and COMMIT it before embedding. The extraction
        # is what gates re-selection by the worker, so persisting it first means
        # a provider outage during embedding does not discard the OCR result and
        # cannot cause the worker to re-OCR this doc on every cycle. Embeddings
        # can be backfilled later via POST /api/ai/reprocess/{doc_id}.
        extraction = Extraction(
            document_id=doc_id,
            extractor_type=extractor_type,
            extracted_text=text,
            lang=lang,
            char_count=len(text),
        )
        db.add(extraction)
        db.commit()
        extraction_id = extraction.id

        # Chunk and embed (best-effort — keyword search works from the committed
        # extraction even if the embedding provider is unavailable).
        settings = get_settings()
        chunks = chunk_text(text, settings.chunk_chars, settings.chunk_overlap)
        if not chunks:
            logger.info(f"Document {doc_id} processed: extraction only (no chunks)")
            return

        try:
            vectors = await ai.embed_texts(chunks)
        except Exception as e:
            logger.error(
                f"Embedding provider unavailable for {doc_id}; extraction saved, "
                f"embeddings skipped: {e}"
            )
            return

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            if len(vector) != settings.embed_dim:
                logger.warning(
                    f"Vector dim mismatch for chunk {i} of {doc_id}: "
                    f"got {len(vector)}, expected {settings.embed_dim}"
                )
            db.add(Embedding(
                extraction_id=extraction_id,
                document_id=doc_id,
                chunk_no=i,
                chunk_text=chunk,
                model=ai.embedding_model_id(),
                dim=len(vector),
                vector=vector,
            ))

        db.commit()
        logger.info(
            f"Document {doc_id} processed: {len(chunks)} chunks, "
            f"extractor={extractor_type}"
        )

    except Exception as e:
        db.rollback()
        logger.exception(f"Error processing document {doc_id}")
        raise
    finally:
        db.close()


async def processing_worker() -> None:
    """
    Infinite worker loop: process documents with status=='active' and no extraction.

    Cycles every iteration with 5s sleep. Gracefully handles asyncio.CancelledError.
    Catches all other exceptions and logs them without crashing the loop.

    Respects single-document-per-cycle (sequential) to be friendly to low-RAM
    CPU-only boxes.

    Only runs when:
    - settings.ai_enabled is True
    - crypto.is_unlocked() is True

    Raises:
        asyncio.CancelledError on cancellation (breaks the loop)
    """
    logger.info("Processing worker started")

    try:
        while True:
            try:
                await asyncio.sleep(5)

                settings = get_settings()
                if not settings.ai_enabled:
                    continue

                if not crypto.is_unlocked():
                    continue

                # Find one document with status=='active' and no extraction
                db = SessionLocal()
                try:
                    # Query: active docs with no extraction (outerjoin + filter)
                    from sqlalchemy import and_
                    from sqlalchemy.orm import outerjoin

                    doc = (
                        db.query(Document)
                        .outerjoin(Extraction)
                        .filter(
                            and_(
                                Document.status == "active",
                                Extraction.id == None,
                            )
                        )
                        .order_by(Document.created_at)
                        .first()
                    )

                    if doc:
                        doc_id = doc.id
                    else:
                        doc_id = None
                finally:
                    db.close()

                # Process the document if found
                if doc_id:
                    try:
                        await process_document(doc_id)
                    except Exception as e:
                        logger.exception(f"Failed to process document {doc_id}")
                        # Continue the loop; don't crash

            except asyncio.CancelledError:
                logger.info("Processing worker cancelled")
                break
            except Exception as e:
                logger.exception("Processing worker cycle error (continuing)")

    except asyncio.CancelledError:
        logger.info("Processing worker cancelled")
