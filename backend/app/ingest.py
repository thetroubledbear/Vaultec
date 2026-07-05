"""Folder watcher for scanner file ingest into validation queue."""

import asyncio
import logging
import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path

from app import crypto, storage
from app.config import get_settings
from app.db import SessionLocal
from app.models import Document, DocumentVersion, Blob, ValidationQueue, User

logger = logging.getLogger("vaultec")


async def watch_incoming() -> None:
    """
    Continuously watch vault_incoming_dir for scanned files.

    Runs forever with 5-second polling. Each cycle:
    1. Skip if vault is locked (KEK not in memory)
    2. List regular files directly under vault_incoming_dir (ignore dotfiles and subdirs)
    3. For each stable file (mtime > 5s old), ingest it
    4. On exception, move file to failed/ subdir; otherwise to processed/

    Never crashes the loop; all errors are caught and logged.
    """
    settings = get_settings()

    # Ensure incoming dir + subdirs exist
    os.makedirs(settings.vault_incoming_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.vault_incoming_dir, "processed"), exist_ok=True)
    os.makedirs(os.path.join(settings.vault_incoming_dir, "failed"), exist_ok=True)

    logger.info(f"Scanner watcher started, monitoring {settings.vault_incoming_dir}")

    while True:
        try:
            await asyncio.sleep(5)

            # Skip if vault is locked
            if not crypto.is_unlocked():
                continue

            # List regular files directly under vault_incoming_dir
            try:
                entries = os.listdir(settings.vault_incoming_dir)
            except (OSError, FileNotFoundError):
                logger.warning(f"Could not list {settings.vault_incoming_dir}")
                continue

            now = time.time()
            for entry in entries:
                # Skip dotfiles, subdirectories, special folders
                if entry.startswith(".") or entry in ("processed", "failed"):
                    continue

                full_path = os.path.join(settings.vault_incoming_dir, entry)
                if not os.path.isfile(full_path):
                    continue

                # Check if file is stable (mtime older than 5 seconds)
                try:
                    mtime = os.path.getmtime(full_path)
                    if now - mtime < 5:
                        # Still being written; skip
                        continue
                except OSError:
                    # File was deleted or access error; skip
                    continue

                # Ingest the file
                try:
                    ingest_file(full_path)
                    # Move to processed/ on success
                    try:
                        dest = os.path.join(settings.vault_incoming_dir, "processed", entry)
                        os.rename(full_path, dest)
                    except OSError as e:
                        logger.error(f"Failed to move {entry} to processed/: {e}")
                except Exception as e:
                    # Move to failed/ on exception
                    logger.error(f"Ingest failed for {entry}: {e}")
                    try:
                        dest = os.path.join(settings.vault_incoming_dir, "failed", entry)
                        os.rename(full_path, dest)
                    except OSError as e2:
                        logger.error(f"Also failed to move {entry} to failed/: {e2}")

        except asyncio.CancelledError:
            logger.info("Scanner watcher cancelled")
            break
        except Exception as e:
            logger.exception("Scanner watcher error (continuing)")


def ingest_file(file_path: str) -> None:
    """
    Ingest a single file from the watcher.

    1. Read file bytes
    2. Encrypt blob (requires vault unlocked)
    3. Dedup Blob by plaintext_sha256
    4. Pick owner: first ACTIVE admin, else any ACTIVE user; skip if none
    5. Create Document(status='pending'), DocumentVersion v1, ValidationQueue
    6. Commit

    On exception, rollback (file stays in incoming/ for manual review).

    Args:
        file_path: absolute path to file

    Raises:
        Any exception is caught by caller and file is moved to failed/
    """
    filename = os.path.basename(file_path)

    try:
        # Read file bytes
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to read file {filename}: {e}") from e

    # Encrypt blob
    try:
        encrypted = crypto.encrypt_blob(file_bytes)
    except Exception as e:
        raise RuntimeError(f"Failed to encrypt {filename}: {e}") from e

    # Open database session
    db = SessionLocal()

    try:
        # Check if blob with same plaintext_sha256 already exists (dedup)
        existing_blob = db.query(Blob).filter(
            Blob.plaintext_sha256 == encrypted["plaintext_sha256"]
        ).first()

        if existing_blob:
            blob = existing_blob
        else:
            # Store encrypted blob and create Blob row
            storage_path = storage.store_blob(encrypted)

            # Guess MIME from the extension so scans (PDF/image) preview inline in the Inbox.
            guessed_mime = mimetypes.guess_type(filename)[0]
            blob = Blob(
                filename=filename,
                mimetype=guessed_mime,
                size_bytes=len(file_bytes),
                wrapped_dek=encrypted["wrapped_dek"],
                dek_nonce=encrypted["dek_nonce"],
                blob_nonce=encrypted["blob_nonce"],
                plaintext_sha256=encrypted["plaintext_sha256"],
                storage_path=storage_path,
            )
            db.add(blob)
            db.flush()

        # Pick owner: first ACTIVE admin, else any ACTIVE user
        admin = db.query(User).filter(
            User.is_active == True,
            User.role == "admin",
        ).first()

        owner = admin or db.query(User).filter(User.is_active == True).first()

        if not owner:
            raise RuntimeError(f"No active user found to assign {filename}")

        # Create Document with status='pending'
        # Title = filename without extension
        title = os.path.splitext(filename)[0]
        doc = Document(
            owner_id=owner.id,
            title=title,
            household_id=owner.household_id,
            status="pending",
        )
        db.add(doc)
        db.flush()

        # Create DocumentVersion v1
        version = DocumentVersion(
            document_id=doc.id,
            blob_id=blob.id,
            version_number=1,
        )
        db.add(version)
        db.flush()

        # Create ValidationQueue entry
        queue = ValidationQueue(
            document_id=doc.id,
            task_type="scan_review",
            status="pending",
        )
        db.add(queue)

        db.commit()
        logger.info(f"Ingested {filename} as document {doc.id}")

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Ingest failed for {filename}: {e}") from e
    finally:
        db.close()
