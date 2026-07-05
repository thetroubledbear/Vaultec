"""Admin routes: user management, household management, statistics, vault monitoring."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crypto
from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import User, Document, Category, Household
from app.security import hash_password

logger = logging.getLogger("vaultec")
router = APIRouter()


class UserListItem(BaseModel):
    """User list response item."""
    id: str
    username: str
    role: str
    is_active: bool
    household_id: Optional[str] = None
    created_at: str


class CreateUserRequest(BaseModel):
    """Request to create a user."""
    username: str
    password: str = Field(..., min_length=8)
    role: str
    household_id: Optional[str] = None


class UpdateUserRequest(BaseModel):
    """Request to update a user."""
    username: str | None = None
    role: str | None = None
    is_active: bool | None = None
    household_id: str | None = None


class HouseholdItem(BaseModel):
    """Household response item."""
    id: str
    name: str
    member_count: int
    created_at: str


class CreateHouseholdRequest(BaseModel):
    """Request to create a household."""
    name: str


class StatsResponse(BaseModel):
    """Admin statistics response."""
    user_count: int
    active_user_count: int
    document_count: int
    category_count: int
    household_count: int
    vault_unlocked: bool


@router.get("/households", response_model=List[HouseholdItem])
def list_households(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> List[HouseholdItem]:
    """
    List all households.

    Requires admin role.

    Returns:
        List of household metadata {id, name, member_count, created_at}
    """
    households = db.query(Household).all()
    result = []
    for h in households:
        member_count = db.query(User).filter(User.household_id == h.id).count()
        result.append(
            HouseholdItem(
                id=str(h.id),
                name=h.name,
                member_count=member_count,
                created_at=h.created_at.isoformat(),
            )
        )
    return result


@router.post("/households", response_model=HouseholdItem, status_code=status.HTTP_201_CREATED)
def create_household(
    request: CreateHouseholdRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> HouseholdItem:
    """
    Create a new household.

    Requires admin role.

    Args:
        request: {name}

    Returns:
        Created household metadata

    Raises:
        HTTPException 409: if household name already exists
    """
    # Check for existing household with same name
    existing = db.query(Household).filter(Household.name == request.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Household with that name already exists",
        )

    household = Household(name=request.name)
    db.add(household)
    db.commit()

    return HouseholdItem(
        id=str(household.id),
        name=household.name,
        member_count=0,
        created_at=household.created_at.isoformat(),
    )


@router.get("/users", response_model=List[UserListItem])
def list_users(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> List[UserListItem]:
    """
    List all users in the vault.

    Requires admin role.

    Returns:
        List of user metadata {id, username, role, is_active, household_id, created_at}
    """
    users = db.query(User).all()
    return [
        UserListItem(
            id=str(u.id),
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            household_id=str(u.household_id) if u.household_id else None,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.post("/users", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserListItem:
    """
    Create a new user.

    Requires admin role.
    Role must be one of: admin, member, viewer.
    If household_id is not provided, defaults to the creating admin's household.

    Args:
        request: {username, password, role, household_id?}

    Returns:
        Created user metadata

    Raises:
        HTTPException 400: if role invalid or password too short or household not found
        HTTPException 409: if username already exists
    """
    # Validate role
    if request.role not in ("admin", "member", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be one of: admin, member, viewer",
        )

    # Check for existing username
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Determine household_id
    household_id = request.household_id or current_user.household_id

    # Validate household exists if explicitly provided
    if household_id:
        household = db.query(Household).filter(Household.id == household_id).first()
        if not household:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Household not found",
            )

    # Create user
    user = User(
        username=request.username,
        email=f"{request.username}@vaultec.local",
        password_hash=hash_password(request.password),
        role=request.role,
        is_active=True,
        household_id=household_id,
    )
    db.add(user)
    db.commit()

    return UserListItem(
        id=str(user.id),
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        household_id=str(household_id) if household_id else None,
        created_at=user.created_at.isoformat(),
    )


@router.patch("/users/{user_id}", response_model=UserListItem)
def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserListItem:
    """
    Update a user's role, active status, and/or household.

    Requires admin role.
    Guards: an admin cannot demote/deactivate themselves, and the last active admin cannot be removed.

    Args:
        user_id: user UUID
        request: {role?, is_active?, household_id?}

    Returns:
        Updated user metadata

    Raises:
        HTTPException 404: if user not found
        HTTPException 400: if household not found
        HTTPException 409: if violating guards (self-demotion, last admin removal)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Guard: admin cannot demote/deactivate themselves
    if user.id == current_user.id:
        if request.role and request.role != current_user.role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote yourself",
            )
        if request.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot deactivate yourself",
            )

    # Guard: cannot remove the LAST active admin
    if request.role == "admin" and user.role == "admin" and request.role != user.role:
        # Attempting to change role away from admin
        active_admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active admin",
            )

    if request.is_active is False and user.role == "admin" and user.is_active == True:
        # Attempting to deactivate an active admin
        active_admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active admin",
            )

    # Username change: validate + enforce uniqueness (username and derived email).
    if request.username is not None:
        new_username = request.username.strip()
        if not new_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username cannot be empty",
            )
        if new_username != user.username:
            clash = db.query(User).filter(
                User.username == new_username,
                User.id != user.id,
            ).first()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )
            user.username = new_username
            user.email = f"{new_username}@vaultec.local"

    # Household change: validate household exists if provided
    if request.household_id is not None:
        household = db.query(Household).filter(Household.id == request.household_id).first()
        if not household:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Household not found",
            )
        user.household_id = request.household_id

    # Apply updates
    if request.role is not None:
        if request.role not in ("admin", "member", "viewer"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be one of: admin, member, viewer",
            )
        user.role = request.role
    if request.is_active is not None:
        user.is_active = request.is_active

    db.commit()

    return UserListItem(
        id=str(user.id),
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        household_id=str(user.household_id) if user.household_id else None,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> None:
    """
    Soft-delete a user (set is_active=False).

    Requires admin role.
    Guards: same as update (cannot deactivate yourself, cannot remove last active admin).

    Args:
        user_id: user UUID

    Raises:
        HTTPException 404: if user not found
        HTTPException 409: if violating guards
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Guard: cannot deactivate yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot deactivate yourself",
        )

    # Guard: cannot remove the LAST active admin
    if user.role == "admin" and user.is_active == True:
        active_admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active admin",
            )

    user.is_active = False
    db.commit()


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> StatsResponse:
    """
    Get admin statistics and vault status.

    Requires admin role.

    Returns:
        StatsResponse with user/document/category/household counts and vault unlock status
    """
    user_count = db.query(User).count()
    active_user_count = db.query(User).filter(User.is_active == True).count()
    document_count = db.query(Document).count()
    category_count = db.query(Category).count()
    household_count = db.query(Household).count()
    vault_unlocked = crypto.is_unlocked()

    return StatsResponse(
        user_count=user_count,
        active_user_count=active_user_count,
        document_count=document_count,
        category_count=category_count,
        household_count=household_count,
        vault_unlocked=vault_unlocked,
    )
