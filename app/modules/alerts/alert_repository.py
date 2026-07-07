from sqlalchemy.orm import Session

from app.modules.alerts.alert_model import Alert


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_paginated(
        self,
        page: int,
        per_page: int,
        emp_id: str | None = None,
        alert_type: str | None = None,
        is_read: bool | None = None,
    ) -> tuple[list[Alert], int]:
        query = self.db.query(Alert)
        if emp_id:
            query = query.filter(Alert.emp_id == emp_id)
        if alert_type:
            query = query.filter(Alert.type == alert_type)
        if is_read is not None:
            query = query.filter(Alert.is_read == is_read)
        total = query.count()
        alerts = (
            query.order_by(Alert.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return alerts, total

    def get_by_id(self, alert_id) -> Alert | None:
        return self.db.query(Alert).filter(Alert.id == alert_id).first()

    def get_unread_by_emp_and_type(self, emp_id: str, alert_type: str) -> Alert | None:
        return (
            self.db.query(Alert)
            .filter(Alert.emp_id == emp_id, Alert.type == alert_type, Alert.is_read.is_(False))
            .order_by(Alert.created_at.desc())
            .first()
        )

    def create(self, emp_id: str, alert_type: str) -> Alert:
        alert = Alert(emp_id=emp_id, type=alert_type, is_read=False)
        self.db.add(alert)
        self.db.flush()
        return alert

    def mark_read(self, alert: Alert) -> Alert:
        alert.is_read = True
        self.db.flush()
        return alert

    def mark_all_read(self, emp_id: str, alert_type: str) -> int:
        return (
            self.db.query(Alert)
            .filter(Alert.emp_id == emp_id, Alert.type == alert_type, Alert.is_read.is_(False))
            .update({Alert.is_read: True})
        )
