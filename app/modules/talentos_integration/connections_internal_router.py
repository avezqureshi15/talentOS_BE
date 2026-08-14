"""One-click connect endpoints (POC → talentOS), talentOS side.

Auth split (see connect_architecture.md §2):

- ``POST /v1`` (provision), ``GET /v1/{flow_id}`` (status) and
  ``POST /v1/disconnect`` are called BY the POC platform using the shared service
  API key (``verify_service_api_key``).
- ``GET /ping`` is called BY the POC **tenant** using the per-tenant ``tal_`` key
  (Bearer) plus ``X-Flow-Id``. It is the mutual-ping "ping_b" side and verifies
  the credential (never the shared secret).

Credentials are returned ONLY by the provisioning response (and its replay path);
all other endpoints return state/proof, never keys.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.service_auth import verify_service_api_key
from app.db.session import get_db
from app.modules.talentos_integration.connections_service import ConnectionsService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/internal/talentos/connections",
    tags=["talentos-connections"],
)

# Routers that the POC platform calls with the shared service key.
_SERVICE_KEY_DEP = Depends(verify_service_api_key)


class ConnectRequest(BaseModel):
    flow_id: UUID
    tenant_name: str | None = Field(default=None, description="Name for the newly provisioned talentOS tenant")
    external_tenant_id: str = Field(..., description="POC tenant UUID (text)")
    rh_api_key: str = Field(..., description="rhub_ key issued by the POC (plaintext, one-time)")


class DisconnectRequest(BaseModel):
    flow_id: UUID
    external_tenant_id: str


@router.post("/v1", status_code=200)
def provision(
    body: ConnectRequest,
    db: Session = Depends(get_db),
    _= _SERVICE_KEY_DEP,
):
    """Provision a talentOS tenant + link, store the peer key, mint tal_."""
    try:
        result = ConnectionsService(db).provision(
            flow_id=body.flow_id,
            tenant_name=body.tenant_name or "",
            external_tenant_id=body.external_tenant_id,
            rh_api_key=body.rh_api_key,
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("connect provision failed | flow_id=%s", body.flow_id)
        raise HTTPException(status_code=500, detail="Provisioning failed")


@router.get("/v1/{flow_id}", status_code=200)
def status(
    flow_id: UUID,
    db: Session = Depends(get_db),
    _= _SERVICE_KEY_DEP,
):
    """Status poll — NEVER returns credentials."""
    try:
        result = ConnectionsService(db).get_status(flow_id)
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("connect status failed | flow_id=%s", flow_id)
        raise HTTPException(status_code=500, detail="Status lookup failed")


@router.post("/v1/disconnect", status_code=200)
def disconnect(
    body: DisconnectRequest,
    db: Session = Depends(get_db),
    _= _SERVICE_KEY_DEP,
):
    """Idempotent disconnect (revokes tal_, clears enc, resets link state)."""
    try:
        result = ConnectionsService(db).disconnect(
            flow_id=body.flow_id,
            external_tenant_id=body.external_tenant_id,
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("connect disconnect failed | flow_id=%s", body.flow_id)
        raise HTTPException(status_code=500, detail="Disconnect failed")


@router.get("/ping", status_code=200)
def ping(
    flow_id: UUID = Header(alias="X-Flow-Id"),
    authorization: str | None = Header(default=None, alias="Authorization", include_in_schema=False),
    db: Session = Depends(get_db),
):
    """Mutual ping (ping_b): POC → talentOS with Bearer tal_ + X-Flow-Id.

    Derives the tenant from the presented key and returns the server's OWN
    binding proof — caller-supplied tenant ids are never trusted.
    """
    raw_key = None
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.split(" ", 1)[1].strip()
    try:
        result = ConnectionsService(db).verify_ping(flow_id=flow_id, raw_key=raw_key)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("connect ping failed | flow_id=%s", flow_id)
        raise HTTPException(status_code=500, detail="Ping failed")