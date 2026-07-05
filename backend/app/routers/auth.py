"""Authentication routes: login, logout, session management."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User, Session as SessionModel
from app.security import verify_password, create_session_token, hash_token, hash_password

logger = logging.getLogger("vaultec")
router = APIRouter()


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response body."""
    user: dict  # {id, username, role}


class MeResponse(BaseModel):
    """Current user response."""
    id: str
    username: str
    role: str


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    current_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user with username and password.

    On success, creates a session token, stores Session row, and sets httpOnly cookie.
    On failure, returns generic 401 without revealing which field was wrong.

    Args:
        request: {username, password}
        db: database session
        response: FastAPI Response object for setting cookies

    Returns:
        LoginResponse with user metadata

    Raises:
        HTTPException 401: if user not found or password mismatch
    """
    settings = get_settings()

    # Query user by username
    user = db.query(User).filter(User.username == request.username).first()

    # Verify password (or fail generically if user not found)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create session token
    token = create_session_token()
    token_hash = hash_token(token)

    # Create session row (expires in 7 days)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    session = SessionModel(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    # Secure cookies require HTTPS; disable only in dev so http://localhost works.
    secure_cookie = settings.app_env != "dev"

    # Set httpOnly cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return LoginResponse(
        user={
            "id": str(user.id),
            "username": user.username,
            "role": user.role,
        }
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Logout user: delete session row and clear cookie.

    Requires authentication.

    Args:
        current_user: authenticated user
        db: database session
        response: FastAPI Response for clearing cookies
    """
    settings = get_settings()

    # Delete all sessions for this user (or just the current one if tracked)
    # For simplicity, delete the current session by querying the cookie
    db.query(SessionModel).filter(SessionModel.user_id == current_user.id).delete()
    db.commit()

    # Clear cookie
    response.delete_cookie(
        key=settings.session_cookie_name,
        secure=settings.app_env != "dev",
        samesite="lax",
    )


@router.get("/me", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user)) -> MeResponse:
    """
    Get current authenticated user.

    Returns:
        Current user metadata {id, username, role}
    """
    return MeResponse(
        id=str(current_user.id),
        username=current_user.username,
        role=current_user.role,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Change the current user's password.

    Requires authentication.
    Validates current password and enforces minimum length (8 chars) for new password.

    Args:
        request: {current_password, new_password}
        current_user: authenticated user
        db: database session

    Raises:
        HTTPException 400: if new_password is shorter than 8 characters
        HTTPException 401: if current_password is incorrect
    """
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
