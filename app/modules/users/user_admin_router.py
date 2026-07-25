import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.logger import get_logger
from app.core.security import hash_password
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.auth.auth_schema import UserInfo
from app.modules.auth.invite_model import TenantInvite
from app.modules.auth.invite_schema import CreateInviteRequest, InviteResponse, PaginatedInviteResponse, ResendInviteRequest
from app.modules.users.user_model import User
from app.modules.users.user_schema import (
    AdminUserResponse,
    CreateUserRequest,
    PaginatedAdminUserResponse,
    UpdateUserRequest,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)


def _resolve_tenant(current_user: UserInfo, tenant_id_override: int | None = None) -> int | None:
    if current_user.role == "superadmin":
        if tenant_id_override is None:
            raise HTTPException(status_code=400, detail="Superadmin must provide a tenant_id")
        return tenant_id_override
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Admin user has no tenant")
    return current_user.tenant_id


def _user_to_admin_response(u: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=u.id,
        email=u.email,
        name=u.name,
        role=u.role,
        is_active=u.is_active,
        auth_provider=u.auth_provider,
        tenant_id=u.tenant_id,
        created_at=u.created_at,
    )


@router.get("", response_model=PaginatedAdminUserResponse)
def list_users(
    q: str | None = Query(None, description="Search by name or email"),
    tenant_id: int | None = Query(None, description="Required for superadmin — filters by tenant"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    query = db.query(User).filter(User.tenant_id == tid)
    if q:
        query = query.filter(
            User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        )
    total = query.count()
    users = query.order_by(User.name).offset((page - 1) * per_page).limit(per_page).all()
    data = [_user_to_admin_response(u) for u in users]
    has_more = (page * per_page) < total
    return PaginatedAdminUserResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)


@router.post("", response_model=AdminUserResponse)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    now = datetime.now(timezone.utc)
    user = User(
        emp_id=f"u{secrets.token_hex(8)}",
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        auth_provider="email",
        tenant_id=tid,
        role=body.role,
        is_active=True,
        status="active",
        user_type="employee",
        designation="Unassigned",
        department="Unassigned",
        work_mode="remote",
        delivery_status="active",
        work_location_type="remote",
        doj=now.date(),
        date_of_birth=now.date(),
        band="L1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Admin created user: email=%s id=%d tenant_id=%d", body.email, user.id, tid)
    return _user_to_admin_response(user)


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)

    db.commit()
    db.refresh(user)
    logger.info("Admin updated user: id=%d", user_id)
    return _user_to_admin_response(user)


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    tenant_id: int | None = Query(None, description="Required for superadmin — scopes to tenant"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    logger.info("Admin deactivated user: id=%d", user_id)
    return {"message": "User deactivated successfully"}


# ── Invites ──────────────────────────────────────────────────────────


@router.post("/invites", response_model=InviteResponse)
def create_invite(
    body: CreateInviteRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)

    existing_invite = db.query(TenantInvite).filter(
        TenantInvite.tenant_id == tid,
        TenantInvite.email == body.email,
        TenantInvite.accepted_at.is_(None),
        TenantInvite.expires_at > datetime.now(timezone.utc),
    ).first()
    if existing_invite:
        raise HTTPException(status_code=409, detail="An active invite already exists for this email")

    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invite = TenantInvite(
        tenant_id=tid,
        email=body.email,
        role=body.role,
        token=token,
        invited_by_user_id=current_user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    logger.info("Admin created invite: email=%s tenant_id=%d", body.email, tid)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        token=invite.token,
        expires_at=invite.expires_at.isoformat(),
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
        created_at=invite.created_at.isoformat(),
    )


@router.get("/invites", response_model=PaginatedInviteResponse)
def list_invites(
    tenant_id: int | None = Query(None, description="Required for superadmin — filters by tenant"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    query = db.query(TenantInvite).filter(TenantInvite.tenant_id == tid)
    total = query.count()
    invites = query.order_by(TenantInvite.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    has_more = (page * per_page) < total
    data = [
        InviteResponse(
            id=i.id,
            email=i.email,
            role=i.role,
            token=i.token,
            expires_at=i.expires_at.isoformat(),
            accepted_at=i.accepted_at.isoformat() if i.accepted_at else None,
            created_at=i.created_at.isoformat(),
        )
        for i in invites
    ]
    return PaginatedInviteResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)


@router.post("/invites/resend", response_model=InviteResponse)
def resend_invite(
    body: ResendInviteRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, body.tenant_id)

    invite = db.query(TenantInvite).filter(
        TenantInvite.tenant_id == tid,
        TenantInvite.email == body.email,
        TenantInvite.accepted_at.is_(None),
    ).order_by(TenantInvite.created_at.desc()).first()

    if not invite:
        raise HTTPException(status_code=404, detail="No pending invite found for this email")

    invite.token = secrets.token_urlsafe(48)
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    db.commit()
    db.refresh(invite)
    logger.info("Admin resent invite: email=%s tenant_id=%d", body.email, tid)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        token=invite.token,
        expires_at=invite.expires_at.isoformat(),
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
        created_at=invite.created_at.isoformat(),
    )


@router.delete("/invites/{invite_id}")
def revoke_invite(
    invite_id: int,
    tenant_id: int | None = Query(None, description="Required for superadmin — scopes to tenant"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    tid = _resolve_tenant(current_user, tenant_id)
    invite = db.query(TenantInvite).filter(
        TenantInvite.id == invite_id,
        TenantInvite.tenant_id == tid,
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    db.delete(invite)
    db.commit()
    logger.info("Admin revoked invite: id=%d", invite_id)
    return {"message": "Invite revoked successfully"}
