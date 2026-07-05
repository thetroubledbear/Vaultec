"""FastAPI dependencies for authentication, authorization, and vault state."""

from datetime import datetime, timezone
from typing import Callable

from fastapi import Cookie, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app import crypto
from app.models import User, Session as SessionModel
from app.security import hash_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and verify session token from httpOnly cookie.

    Reads cookie by settings.session_cookie_name, hashes it, looks up Session,
    checks expiry, and returns the associated User.

    Raises:
        HTTPException 401: if cookie missing, session not found, or expired
    """
    settings = get_settings()
    session_token = request.cookies.get(settings.session_cookie_name)

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token_hash = hash_token(session_token)

    session = db.query(SessionModel).filter(
        SessionModel.token_hash == token_hash
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Check expiry
    now = datetime.now(timezone.utc)
    if session.expires_at < now:
        # Optionally delete expired session
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    return session.user


def require_unlocked() -> bool:
    """
    Dependency that raises 423 (Locked) if vault is locked.

    Raises:
        HTTPException 423: if vault is not unlocked
    """
    if not crypto.is_unlocked():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Vault is locked",
        )
    return True


def require_role(*roles: str) -> Callable:
    """
    Factory returning a dependency that checks if user's role is in the allowed set.

    Args:
        roles: allowable role strings (e.g. "admin", "member")

    Returns:
        dependency function

    Raises:
        HTTPException 403: if user role not in roles
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return check_role
