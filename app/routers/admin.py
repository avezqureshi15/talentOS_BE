from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_hr_admin
from app.models.user import AllowedUser
from app.schemas.auth import UserOut
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])


class AddUserIn(BaseModel):
    email: EmailStr
    role: str = "hr_user"  # hr_admin | hr_user


class UpdateRoleIn(BaseModel):
    role: str


@router.get("/users", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(require_hr_admin),
):
    result = await db.execute(select(AllowedUser).order_by(AllowedUser.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def add_user(
    body: AddUserIn,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(require_hr_admin),
):
    existing = await db.execute(
        select(AllowedUser).where(AllowedUser.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")

    user = AllowedUser(
        email=body.email,
        role=body.role,
        added_by=current_user.email,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await AuditService.log(
        db=db,
        entity_type="user",
        entity_id=user.id,
        event_type="USER_ADDED",
        actor_email=current_user.email,
        payload={"email": body.email, "role": body.role},
    )

    return user


@router.put("/users/{email}", response_model=UserOut)
async def update_user_role(
    email: str,
    body: UpdateRoleIn,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(require_hr_admin),
):
    result = await db.execute(select(AllowedUser).where(AllowedUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    user.role = body.role

    await AuditService.log(
        db=db,
        entity_type="user",
        entity_id=user.id,
        event_type="USER_ROLE_CHANGED",
        actor_email=current_user.email,
        payload={"email": email, "old_role": old_role, "new_role": body.role},
    )

    return user


@router.delete("/users/{email}")
async def remove_user(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(require_hr_admin),
):
    result = await db.execute(select(AllowedUser).where(AllowedUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False

    await AuditService.log(
        db=db,
        entity_type="user",
        entity_id=user.id,
        event_type="USER_REMOVED",
        actor_email=current_user.email,
        payload={"email": email},
    )

    return {"message": f"{email} access revoked"}
