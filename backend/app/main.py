"""FastAPI application factory."""

import asyncio
import logging

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app import crypto, vault, ingest, pipeline
from app.models import User, Household
from app.security import hash_password

logger = logging.getLogger("vaultec")

app = FastAPI(
    title="Vaultec",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

# NOTE: Vault boots LOCKED and must be unlocked after every restart.
# CORS is disabled by default.


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status: str
    initialized: bool
    unlocked: bool


class SetupRequest(BaseModel):
    """Request body for /setup endpoint (first-run initialization)."""
    passphrase: str
    admin_name: str
    admin_password: str


class UnlockRequest(BaseModel):
    """Request body for /unlock endpoint."""
    passphrase: str


@app.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.
    Returns vault initialization and unlock status.
    """
    return HealthResponse(
        status="ok",
        initialized=vault.is_initialized(db),
        unlocked=crypto.is_unlocked(),
    )


@app.post("/setup", status_code=status.HTTP_201_CREATED)
def setup_vault(request: SetupRequest, db: Session = Depends(get_db)) -> dict:
    """
    First-run vault initialization: create vault_config and first admin user.

    Only works if vault is not yet initialized.
    Derives KEK from passphrase and stores encrypted sentinel.
    Creates admin user with argon2-hashed password.

    Args:
        request: contains passphrase, admin_name, admin_password

    Returns:
        dict with message

    Raises:
        HTTPException 409: if vault is already initialized
    """
    if vault.is_initialized(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault is already initialized",
        )

    try:
        # Initialize vault (generates salt, derives KEK, encrypts sentinel)
        vault.initialize(db, request.passphrase)

        # Reuse an existing household if migrations already created one (avoids a
        # duplicate 'Home' on a fresh install where the migration seeds it too),
        # otherwise create the default household.
        default_household = db.query(Household).first()
        if default_household is None:
            default_household = Household(name="Home")
            db.add(default_household)
            db.flush()

        # Create first admin user and assign to default household
        admin_user = User(
            username=request.admin_name,
            email=request.admin_name + "@vaultec.local",
            password_hash=hash_password(request.admin_password),
            role="admin",
            is_active=True,
            household_id=default_household.id,
        )
        db.add(admin_user)
        db.commit()

        return {"message": "Vault initialized and admin user created"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        db.rollback()
        # Log the real cause (no secrets are in scope here) so failures aren't silent.
        logger.exception("Vault setup failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Setup failed",
        )


@app.post("/unlock")
def unlock_vault_endpoint(request: UnlockRequest, db: Session = Depends(get_db)) -> dict:
    """
    Unlock the vault with the master passphrase.

    Derives KEK from passphrase using stored salt and Argon2id.
    Verifies KEK by decrypting stored sentinel.

    Args:
        request: contains passphrase

    Returns:
        dict with message

    Raises:
        HTTPException 401: if passphrase is incorrect
    """
    if crypto.is_unlocked():
        return {"message": "Vault already unlocked"}

    if not vault.is_initialized(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vault is not initialized",
        )

    if vault.unlock(db, request.passphrase):
        return {"message": "Vault unlocked"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect passphrase",
        )


# Wire in routers
from app.routers import auth, documents, admin, validation, ai

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])


@app.on_event("startup")
def startup_event() -> None:
    """Start background tasks on FastAPI startup."""
    # Start scanner folder watcher as background task
    asyncio.create_task(ingest.watch_incoming())
    # Start the AI processing worker (OCR -> chunk -> embed). Runs inside the
    # api process because it needs the in-memory KEK to decrypt blobs.
    asyncio.create_task(pipeline.processing_worker())
