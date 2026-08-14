"""Service layer for the POC ↔ talentOS one-click connect handshake (talentOS side).

Implements the deterministic, failure-safe lifecycle:

- **Concurrency** — link rows are claimed with ``FOR UPDATE``; flows keyed on
  ``flow_id``; unique constraints are the correctness source (Redis is UX only).
- **Replay** — a flow that already exists is idempotently re-returned with the
  same credential (decrypted from ``tal_key_enc``) instead of minting a new one.
- **Transient keys** — ``*_key_enc`` hold Fernet plaintext only while the flow is
  TRANSIENT; on ``linked`` the peer key is written to the runtime store
  (``tenant_settings.RH_API_KEY``) and cleared, so a manual key rotation can never
  resurrect a revoked old key via replay.
- **Failure = enforced revoke** — a failed flow revokes both keys (auth paths do
  not check link state, so revocation is the real enforcement) and clears enc.
- **Ping = proof of binding** — the tenant is always derived FROM the presented
  key (never from the caller's payload), then cross-checked against the link's
  flow + external_tenant_id + current_flow_id.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai_recruitment_client import (
    AiRecruitmentClient,
    AiRecruitmentError,
)
from app.core.logger import get_logger
from app.core.secrets import decrypt_secret, encrypt_secret
from app.modules.api_keys.api_key_model import ApiKey
from app.modules.api_keys.api_key_service import ApiKeyService, API_KEY_ROLES
from app.modules.settings.settings_model import TenantSetting
from app.modules.talentos_integration.integration_link_model import (
    IntegrationLink,
    IntegrationLinkEvent,
    IntegrationLinkFlow,
    OPERATION_CONNECT,
    OPERATION_DISCONNECT,
    PROVIDER_POC,
    PROVIDER_TALENTOS,
    REPLAYABLE_STATES,
    STATE_DISCONNECTED,
    STATE_DISCONNECTING,
    STATE_FAILED,
    STATE_KEYS_EXCHANGED,
    STATE_LINKED,
    STATE_NONE,
    STATE_PROVISIONING,
    STATE_VERIFYING,
    TRANSIENT_STATES,
    utcnow,
)
from app.modules.tenants.tenant_model import Tenant

logger = get_logger(__name__)

# Least privilege for the auto-provisioned tal_ key (talentOS-side credential).
INTEGRATION_KEY_ROLE = "reviewer"
if INTEGRATION_KEY_ROLE not in API_KEY_ROLES:
    raise RuntimeError(f"INTEGRATION_KEY_ROLE must be one of {sorted(API_KEY_ROLES)}")

# Reconciler retry budget / backoff (documented in connect_architecture.md §7.2).
MAX_ATTEMPTS = 8
BACKOFF_BASE_SECONDS = 30
BACKOFF_CAP_SECONDS = 30 * 60
BACKOFF_JITTER_SECONDS = 15

# How long a flow waits for the OTHER direction's ping before the reconciler
# re-checks whether both mutual-ping proofs are in.
AWAIT_POLL = timedelta(seconds=15)


def backoff_delay(attempts: int) -> timedelta:
    exp = min(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)), BACKOFF_CAP_SECONDS)
    jitter = random.uniform(0, BACKOFF_JITTER_SECONDS)
    return timedelta(seconds=exp + jitter)


class ConnectionsService:
    def __init__(self, db: Session):
        self.db = db

    # ── provisioning ──────────────────────────────────────────────────────────

    def provision(
        self,
        flow_id: UUID,
        tenant_name: str,
        external_tenant_id: str,
        rh_api_key: str,
    ) -> dict:
        """Handle ``POST /internal/talentos/connections/v1``.

        Idempotent by ``flow_id``. First call mints tal_, stores the peer rhub_
        key (encrypted), and wires the talentOS tenant; any later replay with the
        same flow_id re-returns the SAME tal_ (no new key minted).
        """
        existing = (
            self.db.execute(
                select(IntegrationLinkFlow).where(
                    IntegrationLinkFlow.flow_id == flow_id
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return self._replay(existing)

        # talentOS tenant for this POC tenant (get-or-create, then row-lock).
        tenant = self._get_or_create_tenant(tenant_name, external_tenant_id)

        # Link row claimed with FOR UPDATE → deterministic winner semantics.
        link = self._lock_link(tenant.id, external_tenant_id)
        if link.state == STATE_LINKED:
            raise HTTPException(status_code=409, detail="Already connected")
        if link.state in TRANSIENT_STATES and link.current_flow_id is not None:
            # Another flow is already in flight → join it (return existing flow_id).
            return {
                "flow_id": str(link.current_flow_id),
                "state": link.state,
                "tenant_id": tenant.id,
                "already_in_progress": True,
            }

        # Fresh flow under this link (idempotency key).
        flow = IntegrationLinkFlow(
            flow_id=flow_id,
            link_id=link.id,
            operation=OPERATION_CONNECT,
            state=STATE_PROVISIONING,
            attempts=0,
            next_retry_at=utcnow(),
        )
        self.db.add(flow)
        self.db.flush()

        # Store the peer credential (Fernet-encrypted plaintext) for replay.
        link.rhub_key_enc = encrypt_secret(rh_api_key)
        link.current_flow_id = flow_id
        link.state = STATE_KEYS_EXCHANGED
        flow.state = STATE_KEYS_EXCHANGED

        # Mint tal_ with least privilege (role-limited, never superadmin).
        created = ApiKeyService(self.db).create_app(
            name=f"poc-{external_tenant_id[:12]}",
            description=f"Auto-provisioned POC integration key (flow {flow_id})",
            created_by_user_id=None,
            tenant_id=tenant.id,
            role=INTEGRATION_KEY_ROLE,
            expires_at=None,
        )
        link.tal_key_id = created.id
        link.tal_key_enc = encrypt_secret(created.full_key)

        self.db.flush()
        self._record_event(
            link_id=link.id,
            flow_id=flow_id,
            action="connect_keys_exchanged",
            actor="system",
            source="api",
            result="ok",
        )
        logger.info(
            "Provisioned POC link | flow_id=%s talentos_tenant_id=%d",
            flow_id, tenant.id,
        )
        return {
            "flow_id": str(flow_id),
            "tenant_id": tenant.id,
            "tal_api_key": created.full_key,
            "tal_key_id": created.id,
            "state": STATE_KEYS_EXCHANGED,
        }

    def _replay(self, flow: IntegrationLinkFlow) -> dict:
        link = self.db.get(IntegrationLink, flow.link_id)
        if link is None or flow.operation != OPERATION_CONNECT:
            raise HTTPException(status_code=409, detail="Flow not found or not a connect flow")

        if flow.state == STATE_LINKED:
            raise HTTPException(status_code=409, detail="Already connected")
        if flow.state not in REPLAYABLE_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"Flow {flow.flow_id} is terminal ({flow.state}); start a new connect",
            )

        # Re-return the same credential the provisioning response would have carried.
        if not link.tal_key_enc:
            raise HTTPException(status_code=409, detail="Credential no longer replayable")
        return {
            "flow_id": str(flow.flow_id),
            "tenant_id": link.tenant_id,
            "tal_api_key": decrypt_secret(link.tal_key_enc),
            "tal_key_id": link.tal_key_id,
            "state": flow.state,
            "replayed": True,
        }

    def get_status(self, flow_id: UUID) -> dict:
        """Status polling — NEVER returns credentials."""
        flow = (
            self.db.execute(
                select(IntegrationLinkFlow).where(
                    IntegrationLinkFlow.flow_id == flow_id
                )
            )
            .scalars()
            .first()
        )
        if flow is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        link = self.db.get(IntegrationLink, flow.link_id)
        return {
            "flow_id": str(flow.flow_id),
            "state": flow.state,
            "operation": flow.operation,
            "external_tenant_id": link.external_tenant_id if link else None,
            "provider": link.provider if link else None,
            "attempts": flow.attempts,
        }

    # ── ping = proof of binding ───────────────────────────────────────────────

    def verify_ping(self, flow_id: UUID, raw_key: str | None) -> dict:
        """``GET /internal/talentos/connections/ping`` (POC → talentOS, Bearer tal_).

        Derives the tenant from the presented key, cross-checks it against the
        flow/link, and advances state. Returns the server's OWN link values —
        never trusts caller-supplied ``external_tenant_id``.
        """
        # 1. Credential is valid AND resolves to a tenant.
        if not raw_key:
            raise HTTPException(status_code=401, detail="Missing credential")
        api_key = ApiKeyService.validate_api_key(raw_key, self.db)
        if api_key is None or api_key.tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked credential")

        # 2. Flow exists and belongs to that tenant's link.
        flow = (
            self.db.execute(
                select(IntegrationLinkFlow).where(
                    IntegrationLinkFlow.flow_id == flow_id
                )
            )
            .scalars()
            .first()
        )
        if flow is None or flow.operation != OPERATION_CONNECT:
            raise HTTPException(status_code=404, detail="Flow not found")

        link = self.db.get(IntegrationLink, flow.link_id)
        if link is None or link.tenant_id != api_key.tenant_id:
            raise HTTPException(status_code=403, detail="Credential does not match this link")

        # 3. Flow must be the CURRENT flow of the link (old creds can't pass).
        if link.current_flow_id != flow_id:
            raise HTTPException(status_code=409, detail="Stale flow")

        if flow.state in (STATE_LINKED, STATE_FAILED):
            # Idempotent: a linked/terminal link still returns proof (no state change).
            return self._ping_proof(link, flow)

        if flow.state not in (STATE_KEYS_EXCHANGED, STATE_VERIFYING, STATE_PROVISIONING):
            raise HTTPException(status_code=409, detail=f"Flow in state {flow.state}")

        # 4. Credential belongs to this flow's binding → record ping_b proof.
        #    Reaching "linked" requires BOTH mutual pings; if ping_a (talentOS →
        #    POC, rhub_) is already proven locally we link now, otherwise stay
        #    transient and wake the reconciler to prove ping_a.
        flow.ping_b_verified = True
        if flow.ping_a_verified:
            self._mark_linked(link, flow)
        else:
            flow.state = STATE_VERIFYING
            flow.next_retry_at = utcnow() + AWAIT_POLL
        self._record_event(
            link_id=link.id,
            flow_id=flow_id,
            action="ping_rhub_verified",
            actor="system",
            source="api",
            result="ok",
        )
        return self._ping_proof(link, flow)

    @staticmethod
    def _ping_proof(link: IntegrationLink, flow: IntegrationLinkFlow) -> dict:
        return {
            "flow_id": str(flow.flow_id),
            "external_tenant_id": link.external_tenant_id,
            "provider": link.provider,
        }

    # ── disconnect (idempotent, even when already disconnected) ───────────────

    def disconnect(self, flow_id: UUID, external_tenant_id: str) -> dict:
        """``POST /internal/talentos/connections/v1/disconnect``.

        Every re-submission is safe: revoke tal_ (no-op if already revoked),
        clear enc, mark the disconnect flow terminal. Absent link → 200 no-op.
        """
        link = (
            self.db.execute(
                select(IntegrationLink)
                .where(
                    IntegrationLink.provider == PROVIDER_POC,
                    IntegrationLink.external_tenant_id == external_tenant_id,
                )
                .with_for_update()
            )
            .scalars()
            .first()
        )
        if link is None:
            return {"flow_id": str(flow_id), "state": STATE_NONE, "result": "ok"}

        self._revoke_tal(link)
        link.rhub_key_enc = None
        link.state = STATE_NONE
        link.current_flow_id = None
        link.connected_at = None

        flow = (
            self.db.execute(
                select(IntegrationLinkFlow).where(
                    IntegrationLinkFlow.flow_id == flow_id
                )
            )
            .scalars()
            .first()
        )
        if flow is None:
            flow = IntegrationLinkFlow(
                flow_id=flow_id,
                link_id=link.id,
                operation=OPERATION_DISCONNECT,
                state=STATE_DISCONNECTED,
                attempts=0,
                next_retry_at=None,
            )
            self.db.add(flow)
        else:
            flow.operation = OPERATION_DISCONNECT
            flow.state = STATE_DISCONNECTED
            flow.next_retry_at = None
            flow.attempts = 0

        self._record_event(
            link_id=link.id,
            flow_id=flow_id,
            action="disconnect_completed",
            actor="system",
            source="api",
            result="ok",
        )
        return {"flow_id": str(flow_id), "state": STATE_NONE, "result": "ok"}

    # ── reconciler entry points ───────────────────────────────────────────────

    async def reconcile_flow(self, flow: IntegrationLinkFlow) -> str:
        """One reconciliation action for a TRANSIENT flow (worker already SKIP
        LOCKED this row). Returns a short outcome for logging."""
        link = self.db.get(IntegrationLink, flow.link_id)
        if link is None:
            return "orphan"

        if flow.operation == OPERATION_DISCONNECT:
            if flow.state == STATE_DISCONNECTING:
                self._revoke_tal(link)
                link.state = STATE_NONE
                link.current_flow_id = None
                link.connected_at = None
                flow.state = STATE_DISCONNECTED
                flow.next_retry_at = None
                self._record_event(
                    link_id=link.id, flow_id=flow.flow_id,
                    action="disconnect_completed", actor="system",
                    source="reconciler", result="ok",
                )
                return "disconnected"
            return "wait"

        if flow.operation == OPERATION_CONNECT:
            return await self._reconcile_connect(link, flow)

        return "unknown"

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_or_create_tenant(self, tenant_name: str, external_tenant_id: str) -> Tenant:
        tenant = (
            self.db.execute(
                select(Tenant).where(
                    Tenant.external_platform == PROVIDER_POC,
                    Tenant.external_tenant_id == external_tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if tenant is not None:
            return tenant

        slug = self._unique_slug(tenant_name or external_tenant_id)
        tenant = Tenant(
            name=tenant_name or external_tenant_id,
            slug=slug,
            is_active=True,
            verification_status="approved",
            external_platform=PROVIDER_POC,
            external_tenant_id=external_tenant_id,
        )
        self.db.add(tenant)
        self.db.flush()
        logger.info("Provisined talentOS tenant for POC: slug=%s", slug)
        # Re-lock row we just created so concurrent provisions serialize on it.
        return (
            self.db.execute(
                select(Tenant).where(Tenant.id == tenant.id).with_for_update()
            )
            .scalars()
            .one()
        )

    def _unique_slug(self, name: str) -> str:
        base = (name.lower().replace(" ", "-").replace("--", "-") or "poc")[:60]
        slug, counter = base, 1
        while (
            self.db.execute(select(Tenant.id).where(Tenant.slug == slug)).scalars().first()
            is not None
        ):
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def _lock_link(self, tenant_id: int, external_tenant_id: str) -> IntegrationLink:
        link = (
            self.db.execute(
                select(IntegrationLink)
                .where(
                    IntegrationLink.provider == PROVIDER_POC,
                    IntegrationLink.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            .scalars()
            .first()
        )
        if link is not None:
            return link
        link = IntegrationLink(
            provider=PROVIDER_POC,
            tenant_id=tenant_id,
            external_tenant_id=external_tenant_id,
            state=STATE_KEYS_EXCHANGED,
            current_flow_id=None,
        )
        self.db.add(link)
        self.db.flush()
        return link

    def _revoke_tal(self, link: IntegrationLink) -> None:
        if link.tal_key_id is None:
            link.tal_key_enc = None
            return
        key = self.db.get(ApiKey, link.tal_key_id)
        if key is not None and key.is_active:
            key.is_active = False
            key.updated_at = datetime.now(timezone.utc)
            logger.info("Revoked tal_ for link_id=%d key_id=%d", link.id, key.id)
        # Clear the transient plaintext copy — a revoked key must not be replayable.
        link.tal_key_enc = None

    async def _reconcile_connect(self, link: IntegrationLink, flow: IntegrationLinkFlow) -> str:
        """Advance a transient connect flow one step.

        talentOS drives ping_a (tal_ tenant's rhub_ credential → POC). Once the
        POC's proof cross-checks, we record ping_a_verified; if ping_b (the POC's
        ping we already verified) is also in, the link becomes ``linked``. Any
        failure/pending step schedules backoff and eventually fails (revokes).
        """
        if flow.state not in REPLAYABLE_STATES:
            return "wait"

        # Outbound direction already proven — only waiting on the POC's ping_b.
        if flow.ping_a_verified:
            return self._retry_or_wait(link, flow, event="await_inbound_ping", retry=True)

        if not link.rhub_key_enc:
            self._fail_connect(link, flow, "RHUB_KEY_MISSING", "peer rhub_ key not stored")
            return "failed"
        rhub_raw = decrypt_secret(link.rhub_key_enc)
        if not rhub_raw:
            self._fail_connect(link, flow, "RHUB_KEY_MISSING", "peer rhub_ key not stored")
            return "failed"

        proof = await self._ping_peer(link, flow, rhub_raw)
        if not proof:
            self._retry_or_wait(link, flow, event="ping_a_failed", retry=True)
            return "retry"

        # Cross-check the POC's proof echoes OUR binding. The POC stores the
        # talentOS tenant id as ITS external_tenant_id, so the echoed value must
        # equal our local tenant id, and provider must be talentOS's view.
        if (
            str(proof.get("flow_id", "")) == str(flow.flow_id)
            and str(proof.get("external_tenant_id", "")) == str(link.tenant_id)
            and str(proof.get("provider", "")) == PROVIDER_TALENTOS
        ):
            flow.ping_a_verified = True
            self._record_event(
                link_id=link.id, flow_id=flow.flow_id,
                action="ping_tal_verified", actor="system",
                source="reconciler", result="ok",
            )
            if flow.ping_b_verified:
                self._mark_linked(link, flow)
                return "linked"
            flow.next_retry_at = utcnow() + AWAIT_POLL
            return "await_inbound_ping"

        # Proof mismatch — don't fail yet (POC reconciler may not have settled);
        # keep retrying within budget.
        self._retry_or_wait(link, flow, event="ping_a_mismatch", retry=AWAIT_POLL)
        return "retry"

    def _retry_or_wait(self, link: IntegrationLink, flow: IntegrationLinkFlow, *, event: str, retry) -> str:
        """Account for a reconciled-but-unfinished sweep: schedule backoff and fail
        when the budget is exhausted. ``retry`` is a bool | timedelta override."""
        flow.attempts += 1
        flow.last_error_code = event
        flow.last_error = self._sanitize(event)
        if flow.attempts >= MAX_ATTEMPTS:
            self._fail_connect(link, flow, "RECONCILE_TIMEOUT", event)
            return "failed"
        if isinstance(retry, timedelta):
            flow.next_retry_at = utcnow() + retry
        else:
            flow.next_retry_at = utcnow() + backoff_delay(flow.attempts)
        return event

    async def _ping_peer(self, link: IntegrationLink, flow: IntegrationLinkFlow, rhub_raw: str) -> dict | None:
        """Send the outbound ping (talentOS → POC) using the peer rhub_ key.

        ``tenant_id` resolves the POC base URL (RH_SERVICE_URL) from the tenant's
        runtime store / platform fallback.
        """
        client = AiRecruitmentClient(tenant_id=link.tenant_id)
        try:
            return await client.ping_connection(rhub_raw, str(flow.flow_id))
        except AiRecruitmentError:
            return None

    def _mark_linked(self, link: IntegrationLink, flow: IntegrationLinkFlow) -> None:
        """Persist the peer key into the runtime store, clear transient plaintext,
        and mark both the link and flow ``linked`` (mutual pings proven)."""
        if link.rhub_key_enc:
            try:
                rhub = decrypt_secret(link.rhub_key_enc)
            except Exception:
                rhub = None
            if rhub:
                self._upsert_runtime_setting(link.tenant_id, "RH_API_KEY", rhub)
        self._clear_transient(link)
        link.state = STATE_LINKED
        link.connected_at = utcnow()
        flow.state = STATE_LINKED
        flow.next_retry_at = None
        flow.last_error_code = None
        flow.last_error = None
        self._record_event(
            link_id=link.id, flow_id=flow.flow_id,
            action="linked", actor="system", source="reconciler", result="ok",
        )
        logger.info(
            "POC integration linked | link_id=%d tenant_id=%d flow_id=%s",
            link.id, link.tenant_id, flow.flow_id,
        )

    def _upsert_runtime_setting(self, tenant_id: int, key: str, plaintext_value: str) -> None:
        row = (
            self.db.execute(
                select(TenantSetting).where(
                    TenantSetting.tenant_id == tenant_id,
                    TenantSetting.key == key,
                )
            )
            .scalars()
            .first()
        )
        encrypted = encrypt_secret(plaintext_value)
        if row:
            row.value = encrypted
        else:
            self.db.add(TenantSetting(tenant_id=tenant_id, key=key, value=encrypted))

    def _clear_transient(self, link: IntegrationLink) -> None:
        link.rhub_key_enc = None
        link.tal_key_enc = None

    def cleanup_expired(self) -> int:
        """Fail TRANSIENT flows that exhausted their retry budget.

        The per-flow sweep refuses to pick flows with ``attempts >= MAX_ATTEMPTS``
        (otherwise the final backoff would immediately re-trigger), so anything the
        worker missed (crash between commit and next sweep) is failed here —
        enforced revoke + cleared enc.
        """
        flows = (
            self.db.execute(
                select(IntegrationLinkFlow)
                .where(
                    IntegrationLinkFlow.state.in_(TRANSIENT_STATES),
                    IntegrationLinkFlow.attempts >= MAX_ATTEMPTS,
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for flow in flows:
            link = self.db.get(IntegrationLink, flow.link_id)
            if link is not None:
                self._fail_connect(link, flow, "RECONCILE_BUDGET", "Retry budget exhausted")
            else:
                flow.state = STATE_FAILED
                flow.next_retry_at = None
                flow.last_error_code = "LINK_MISSING"
                flow.last_error = "link row missing"
            count += 1
        if count:
            logger.warning("Failed %d expired integration flows", count)
        return count

    def _fail_connect(
        self, link: IntegrationLink, flow: IntegrationLinkFlow,
        code: str, error: str,
    ) -> None:
        # Failure = enforced revoke (auth paths don't check link state).
        if link.rhub_key_enc:
            # We can't revoke the POC-issued rhub_ locally; POC revokes its own.
            pass
        self._revoke_tal(link)
        link.rhub_key_enc = None
        link.state = STATE_FAILED
        flow.state = STATE_FAILED
        flow.next_retry_at = None
        flow.last_error_code = code
        flow.last_error = self._sanitize(error)
        self._record_event(
            link_id=link.id, flow_id=flow.flow_id,
            action="failed", actor="system", source="reconciler",
            result="error", detail=f"{code}: {self._sanitize(error)}",
        )
        logger.warning("Connect flow failed | link_id=%d flow_id=%s code=%s", link.id, flow.flow_id, code)

    def _record_event(
        self,
        link_id: int,
        flow_id: UUID | None,
        action: str,
        actor: str,
        source: str,
        result: str,
        detail: str | None = None,
    ) -> None:
        self.db.add(
            IntegrationLinkEvent(
                link_id=link_id,
                flow_id=flow_id,
                action=action,
                actor=actor,
                source=source,
                result=result,
                detail=self._sanitize(detail) if detail else None,
            )
        )

    @staticmethod
    def _sanitize(message: str) -> str:
        """Strip anything that could resemble credential material or raw bodies."""
        cleaned = (message or "").strip()[:500]
        for marker in ("rhub_", "tal_", "Bearer ", "Authorization"):
            cleaned = cleaned.replace(marker, f"{marker}***")
        return cleaned