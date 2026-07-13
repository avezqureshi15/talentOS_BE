from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.modules.alerts.alert_model import Alert

logger = get_logger(__name__)

_FORM_VALIDITY_HOURS = settings.FORM_EXPIRY_HOURS


class AlertRepositoryProtocol(Protocol):
    def list_paginated(self, page: int, per_page: int, employee_id: int | None = None, alert_type: str | None = None, is_read: bool | None = None) -> tuple[list[Alert], int]: ...
    def get_by_id(self, alert_id) -> Alert | None: ...
    def get_by_form_and_type(self, form_id: UUID, alert_type: str) -> Alert | None: ...
    def get_by_emp_and_type(self, employee_id: int, alert_type: str) -> Alert | None: ...
    def get_unread_by_emp_and_type(self, employee_id: int, alert_type: str) -> Alert | None: ...
    def create(self, employee_id: int, alert_type: str, form_id: UUID | None = None) -> Alert: ...
    def mark_read(self, alert: Alert) -> Alert: ...
    def mark_all_read(self, employee_id: int, alert_type: str) -> int: ...
    def list_enriched(self, page: int, per_page: int, alert_type: str | None = None, is_read: bool | None = None) -> tuple[list[dict], int]: ...


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_paginated(self, page: int, per_page: int, employee_id: int | None = None, alert_type: str | None = None, is_read: bool | None = None) -> tuple[list[Alert], int]:
        query = self.db.query(Alert)
        if employee_id:
            query = query.filter(Alert.employee_id == employee_id)
        if alert_type:
            query = query.filter(Alert.type == alert_type)
        if is_read is not None:
            query = query.filter(Alert.is_read == is_read)
        total = query.count()
        alerts = query.order_by(Alert.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return alerts, total

    def get_by_id(self, alert_id) -> Alert | None:
        return self.db.query(Alert).filter(Alert.id == alert_id).first()

    def get_by_form_and_type(self, form_id: UUID, alert_type: str) -> Alert | None:
        return self.db.query(Alert).filter(Alert.form_id == form_id, Alert.type == alert_type).first()

    def get_by_emp_and_type(self, employee_id: int, alert_type: str) -> Alert | None:
        return self.db.query(Alert).filter(Alert.employee_id == employee_id, Alert.type == alert_type).order_by(Alert.created_at.desc()).first()

    def get_unread_by_emp_and_type(self, employee_id: int, alert_type: str) -> Alert | None:
        return self.db.query(Alert).filter(Alert.employee_id == employee_id, Alert.type == alert_type, Alert.is_read.is_(False)).order_by(Alert.created_at.desc()).first()

    def create(self, employee_id: int, alert_type: str, form_id: UUID | None = None) -> Alert:
        alert = Alert(employee_id=employee_id, type=alert_type, form_id=form_id, is_read=False)
        self.db.add(alert)
        self.db.flush()
        return alert

    def mark_read(self, alert: Alert) -> Alert:
        alert.is_read = True
        self.db.flush()
        return alert

    def mark_all_read(self, employee_id: int, alert_type: str) -> int:
        return self.db.query(Alert).filter(Alert.employee_id == employee_id, Alert.type == alert_type, Alert.is_read.is_(False)).update({Alert.is_read: True})

    def list_enriched(self, page: int, per_page: int, alert_type: str | None = None, is_read: bool | None = None) -> tuple[list[dict], int]:
        from app.modules.evaluations.evaluation_model import Candidate
        from app.modules.forms.form_model import Form, FormStatus
        from app.modules.hiring_requests.hiring_request_model import HiringRequest
        from app.modules.rounds.round_model import Round
        from app.modules.users.user_model import User

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=_FORM_VALIDITY_HOURS)
        base = settings.FRONTEND_BASE_URL.rstrip("/")

        q = self.db.query(Alert, User).join(User, User.id == Alert.employee_id)
        if alert_type:
            q = q.filter(Alert.type == alert_type)
        if is_read is not None:
            q = q.filter(Alert.is_read == is_read)
        total = q.count()
        rows = q.order_by(Alert.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        emp_ids = list({u.emp_id for _, u in rows})
        forms: dict = {}
        if emp_ids:
            fq = self.db.query(Form, User).join(User, User.id == Form.employee_id).filter(User.emp_id.in_(emp_ids), Form.status == FormStatus.SENT.value, Form.last_sent_at > cutoff)
            if alert_type:
                fq = fq.filter(Form.type == alert_type)
            forms = {u.emp_id: {"id": f.id, "rid": f.round_id} for f, u in fq.all()}

        rids = [f["rid"] for f in forms.values() if f.get("rid")]
        iv = {}
        if rids:
            iv_q = self.db.query(Round, Candidate, HiringRequest).outerjoin(Candidate, Candidate.id == Round.candidate_id).outerjoin(HiringRequest, HiringRequest.id == Round.jd_id).filter(Round.id.in_(rids))
            for r, c, h in iv_q.all():
                iv[str(r.id)] = (c.candidate_name if c else "", h.title if h else "")

        items = []
        for alert, user in rows:
            f = forms.get(user.emp_id, {})
            fid = f.get("id")
            item = {"id": str(alert.id), "type": alert.type.lower(), "created_at": alert.created_at.isoformat() if alert.created_at else None, "employee": {"id": user.emp_id, "name": user.name or "", "email": user.email or "", "phone": user.phone_number or ""}}
            if alert.type == "SLOTS":
                item["slot_link"] = f"{base}/book-slot/{fid}" if fid else None
            elif alert.type == "REVIEW":
                item["review_link"] = f"{base}/rate-candidate/{fid}" if fid else None
                rid = f.get("rid")
                if rid:
                    cn, pt = iv.get(str(rid), ("", ""))
                    item["interview"] = {"id": str(rid), "candidate_name": cn, "position": pt}
            items.append(item)
        return items, total

    @staticmethod
    def build_pagination(page: int, per_page: int, total: int) -> dict:
        return {"current_page": page, "per_page": per_page, "total_records": total, "has_more": (page * per_page) < total}
