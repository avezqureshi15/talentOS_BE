from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.modules.forms.form_model import Form
from app.modules.users.user_model import User


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_form_status(
        self,
        form_type: str,
        status: str,
        emp_ids: list[str],
        page: int,
        per_page: int,
    ) -> tuple[list[tuple], int]:
        latest_subq = (
            self.db.query(
                User.emp_id.label("emp_id"),
                Form.id.label("form_id"),
            )
            .join(User, User.employee_id == Form.employee_id)
            .filter(Form.type == form_type)
            .distinct(User.emp_id)
            .order_by(User.emp_id, Form.last_sent_at.desc())
            .subquery()
        )

        query = (
            self.db.query(
                User.emp_id,
                User.name,
                User.email,
                Form.type,
                Form.status,
                Form.last_sent_at,
                Form.updated_at,
            )
            .join(latest_subq, latest_subq.c.emp_id == User.emp_id)
            .join(Form, Form.id == latest_subq.c.form_id)
            .filter(Form.status == status)
        )
        if emp_ids:
            query = query.filter(User.emp_id.in_(emp_ids))

        total = query.count()
        rows = (
            query.order_by(Form.updated_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return rows, total
