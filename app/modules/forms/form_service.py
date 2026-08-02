from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.utils.list_utils import unique_preserve_order
from app.core.logger import get_logger
from app.modules.notifications.notification_model import NotificationType
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.forms.form_mail import (
    DETAIL_NEW_LINK,
    DETAIL_RESENT,
    MSG_EMP_NOT_FOUND,
    MSG_INVALID_EMAIL,
    MSG_REVIEW_MAIL_SENT,
    MSG_SMTP_NOT_CONFIGURED,
    build_ask_summary_message,
    detail_to_message,
    is_form_expired,
    is_smtp_configured,
    is_valid_email,
    send_review_mail_task,
    send_slot_mail_task,
)
from app.modules.forms.form_model import Form, FormStatus, FormType
from app.modules.forms.form_repository import FormRepository
from app.modules.forms.form_schema import (
    AskFormResponse,
    AskFormResultItem,
    FormSubmitResponse,
    FormValidateResponse,
    PendingMailTask,
)
from app.modules.users.user_repository import UserRepository

logger = get_logger(__name__)

_NOTIFY_COOLDOWN = timedelta(minutes=1)
_last_notified: dict[tuple[int, str, str | None], datetime] = {}


class FormService:
    def __init__(self, db: Session):
        from app.modules.notifications.notification_service import NotificationService

        self.db = db
        self.repository = FormRepository(db)
        self.user_repository = UserRepository(db)
        self.notification_service = NotificationService(db)

    def _resolve_ask_action(self, emp_id: str, form_type: str) -> tuple[Form, str]:
        user = self.user_repository.get_by_emp_id(emp_id)
        if not user:
            raise ValueError(f"User not found for emp_id={emp_id}")

        now = datetime.now(timezone.utc)
        active = self.repository.get_active_sent(emp_id, form_type)
        if active:
            self.repository.touch_last_sent_at(active, last_sent_at=now)
            return active, DETAIL_RESENT

        latest = self.repository.get_latest(emp_id, form_type)
        if latest and latest.status == FormStatus.SENT.value and is_form_expired(latest):
            self.repository.mark_expired(latest)

        form = self.repository.create(employee_id=user.id, form_type=form_type, last_sent_at=now)
        return form, DETAIL_NEW_LINK

    def generate_review_form(
        self,
        emp_id: str,
        round_id: UUID,
        candidate_id: int,
        candidate_name: str,
        round_name: str,
        interviewer_name: str,
        interviewer_email: str,
    ) -> Form:
        user = self.user_repository.get_by_emp_id(emp_id)
        if not user:
            raise ValueError(f"User not found for emp_id={emp_id}")

        now = datetime.now(timezone.utc)
        active = self.repository.get_active_sent_by_emp_and_round(emp_id, round_id)
        if active:
            self.repository.touch_last_sent_at(active, last_sent_at=now)
            self.db.commit()
            send_review_mail_task(user.id, active.id, candidate_name, round_name, interviewer_name)
            return active

        latest = self.repository.get_latest(emp_id, FormType.REVIEW.value)
        if latest and latest.status == FormStatus.SENT.value and is_form_expired(latest):
            self.repository.mark_expired(latest)

        form = self.repository.create(
            employee_id=user.id,
            form_type=FormType.REVIEW.value,
            last_sent_at=now,
            round_id=round_id,
            candidate_id=candidate_id,
        )
        self.db.commit()
        send_review_mail_task(user.id, form.id, candidate_name, round_name, interviewer_name)
        return form

    def ask_form_batch(self, emp_ids: list[str], form_type: str) -> tuple[AskFormResponse, list[PendingMailTask]]:
        results: list[AskFormResultItem] = []
        mail_tasks: list[PendingMailTask] = []
        smtp_ready = is_smtp_configured()

        for emp_id in unique_preserve_order(emp_ids):
            if not smtp_ready:
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_SMTP_NOT_CONFIGURED,
                    )
                )
                continue

            user = self.user_repository.get_by_emp_id(emp_id)
            if not user:
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_EMP_NOT_FOUND,
                    )
                )
                continue

            if not is_valid_email(user.email):
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="FAILED",
                        message=MSG_INVALID_EMAIL,
                    )
                )
                continue

            try:
                form, detail = self._resolve_ask_action(emp_id, form_type)
                self.db.flush()
                results.append(
                    AskFormResultItem(
                        emp_id=emp_id,
                        status="SUCCESS",
                        message=detail_to_message(detail),
                    )
                )
                mail_tasks.append(PendingMailTask(user_id=user.id, form_id=form.id))
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise

        try:
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise

        success_ids = [r.emp_id for r in results if r.status == "SUCCESS"]
        return (
            AskFormResponse(
                message=build_ask_summary_message(success_ids),
                results=results,
            ),
            mail_tasks,
        )

    def validate_form(self, form_id: UUID) -> FormValidateResponse:
        form = self.repository.get_by_id(form_id)
        if not form:
            return FormValidateResponse(valid=False, reason="NOT_FOUND")

        review_questions = None
        if form.type == FormType.REVIEW.value and form.round_id:
            from app.modules.interviews.review_questions_service import ReviewQuestionsService

            review_questions = ReviewQuestionsService(self.db).get_questions_for_round(form.round_id)

        if form.status == FormStatus.SUBMITTED.value:
            return FormValidateResponse(
                valid=False, reason="ALREADY_SUBMITTED", emp_id=form.employee.emp_id, type=form.type,
                round_id=form.round_id, candidate_id=form.candidate_id,
                review_questions=review_questions,
            )
        if form.status == FormStatus.EXPIRED.value:
            return FormValidateResponse(
                valid=False, reason="EXPIRED", emp_id=form.employee.emp_id, type=form.type,
                round_id=form.round_id, candidate_id=form.candidate_id,
                review_questions=review_questions,
            )
        if is_form_expired(form):
            if form.status == FormStatus.SENT.value:
                try:
                    self.repository.mark_expired(form)
                    self.db.commit()
                    self.notification_service.mark_all_read(
                        form.employee.id, notification_type=form.type
                    )
                except sa_exc.SQLAlchemyError:
                    self.db.rollback()
                    raise
            return FormValidateResponse(
                valid=False, reason="EXPIRED", emp_id=form.employee.emp_id, type=form.type,
                round_id=form.round_id, candidate_id=form.candidate_id,
                review_questions=review_questions,
            )
        return FormValidateResponse(
            valid=True, reason="VALID", emp_id=form.employee.emp_id, type=form.type,
            round_id=form.round_id, candidate_id=form.candidate_id,
            review_questions=review_questions,
        )

    def notify_form(self, user_id: int, form_type: str, is_reminder: bool = True) -> tuple[Form, str]:
        now = datetime.now(timezone.utc)

        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: user_id={user_id}")

        latest = self.repository.get_latest_by_user(user_id, form_type)
        round_id = str(latest.round_id) if (latest and latest.round_id and form_type == FormType.REVIEW.value) else None
        key = (user_id, form_type, round_id)
        last = _last_notified.get(key)
        if last and (now - last) < _NOTIFY_COOLDOWN:
            remaining = int((_NOTIFY_COOLDOWN - (now - last)).total_seconds())
            raise ValueError(f"Rate limit: Please wait {remaining} second(s) before sending another notification.")

        if form_type == FormType.REVIEW.value:
            active = self.repository.get_active_sent_by_user(user_id, form_type)
            if active:
                self.repository.touch_last_sent_at(active, last_sent_at=now)
                detail = DETAIL_RESENT
                form = active
            else:
                if latest and latest.status == FormStatus.SENT.value and is_form_expired(latest):
                    self.repository.mark_expired(latest)
                if latest and latest.status in (FormStatus.EXPIRED.value, FormStatus.SENT.value):
                    form = self.repository.create(
                        employee_id=user_id,
                        form_type=form_type,
                        last_sent_at=now,
                        round_id=latest.round_id,
                        candidate_id=latest.candidate_id,
                    )
                else:
                    raise ValueError("No existing review form found for this user.")
                detail = DETAIL_NEW_LINK
        else:
            active = self.repository.get_active_sent_by_user(user_id, form_type)
            if active:
                self.repository.touch_last_sent_at(active, last_sent_at=now)
                detail = DETAIL_RESENT
                form = active
            else:
                if latest and latest.status == FormStatus.SENT.value and is_form_expired(latest):
                    self.repository.mark_expired(latest)
                form = self.repository.create(
                    employee_id=user_id,
                    form_type=form_type,
                    last_sent_at=now,
                )
                detail = DETAIL_NEW_LINK

        _last_notified[key] = now

        alert_type = self._get_alert_type(form.type)
        action_url = (
            f"/rate-candidate/{form.id}"
            if form.type == FormType.REVIEW.value
            else f"/book-slot/{form.id}"
        )

        candidate_name = None
        job_title = None
        round_name = None
        hr = None
        if form.candidate_id or form.round_id:
            from app.modules.evaluations.evaluation_model import Candidate
            from app.modules.hiring_requests.hiring_request_model import HiringRequest
            from app.modules.rounds.round_model import Round

            if form.candidate_id:
                candidate = self.db.query(Candidate).filter(Candidate.id == form.candidate_id).first()
                candidate_name = candidate.candidate_name if candidate else None
            if form.round_id:
                round_obj = self.db.query(Round).filter(Round.id == form.round_id).first()
                if round_obj:
                    round_name = round_obj.name
                    if round_obj.jd_id:
                        hr = self.db.query(HiringRequest).filter(HiringRequest.id == round_obj.jd_id).first()
                        job_title = hr.title if hr else None

        if form.type == FormType.REVIEW.value:
            context_title = f"Review required for {candidate_name}" if candidate_name else "Review pending"
            context_parts = [part for part in (job_title, f"Round: {round_name}" if round_name else None) if part]
            context_body = " · ".join(context_parts) or "A form is waiting for your action."
        else:
            context_title = "Slot availability request"
            context_body = f"Your availability is needed to schedule interviews for {job_title}." if job_title else "A form is waiting for your action."

        self.notification_service.notify(
            employee_id=user_id,
            notification_type=alert_type,
            title=context_title,
            body=context_body,
            action_url=action_url,
            action_label="Book slots" if alert_type == NotificationType.SLOTS.value else "Submit review",
            form_id=form.id,
            candidate_id=form.candidate_id,
            job_id=hr.id if hr else None,
            dedupe_key=f"{form.type}-{form.id}",
        )

        if form.type == FormType.REVIEW.value and form.candidate_id:
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(form.candidate_id),
                candidate_id=form.candidate_id,
                event_name="Review Overdue Notification to Interviewer",
                state_code="REVIEW_NOTIFICATION_TO_INTERVIEWER",
                actor_type="HR",
                event_metadata={
                    "form_id": str(form.id),
                    "employee_id": form.employee.id,
                    "detail": detail,
                },
            ))

        return form, detail

    def mark_slots_form_submitted(self, emp_id: str) -> None:
        form = self.repository.get_active_sent(emp_id, FormType.SLOTS.value)
        if not form:
            form = self.repository.get_latest(emp_id, FormType.SLOTS.value)
        if not form or form.status != FormStatus.SENT.value:
            return
        try:
            self.repository.mark_submitted(form)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
        user = self.user_repository.get_by_emp_id(emp_id)
        if user:
            self.notification_service.mark_all_read(employee_id=user.id, notification_type=NotificationType.SLOTS.value)

    def submit_form(self, form_id: UUID) -> FormSubmitResponse:
        form = self.repository.get_by_id(form_id)
        if not form:
            raise ValueError(f"Form not found: form_id={form_id}")
        if form.status != FormStatus.SENT.value:
            return FormSubmitResponse(message="Form already finalised")
        try:
            self.repository.mark_submitted(form)
            self.db.commit()
        except sa_exc.SQLAlchemyError:
            self.db.rollback()
            raise
        alert_type = NotificationType.REVIEW.value if form.type == FormType.REVIEW.value else NotificationType.SLOTS.value
        self.notification_service.mark_all_read(
            employee_id=form.employee.id, notification_type=alert_type,
        )
        if form.type == FormType.REVIEW.value and form.candidate_id:
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(form.candidate_id),
                candidate_id=form.candidate_id,
                event_name="Review Form Submitted",
                state_code="REVIEW_FORM_SUBMITTED",
                actor_type="INTERVIEWER",
                actor_id=form.employee.emp_id,
                event_metadata={
                    "round_id": str(form.round_id) if form.round_id else None,
                    "form_id": str(form.id),
                },
            ))
        return FormSubmitResponse(message="Form submitted successfully")

    def _get_alert_type(self, form_type: str) -> str:
        return NotificationType.REVIEW.value if form_type == FormType.REVIEW.value else NotificationType.SLOTS.value

    def _send_form_mail(self, form: Form, is_reminder: bool = False) -> None:
        if form.type == FormType.REVIEW.value:
            send_review_mail_task(form.employee_id, form.id, None, None, None, is_reminder=is_reminder)
        else:
            send_slot_mail_task(form.employee_id, form.id, is_reminder=is_reminder)

    def run_reminder_job(self) -> int:
        forms = self.repository.list_due_for_reminder()
        now = datetime.now(timezone.utc)
        sent = 0
        for form in forms:
            self._send_form_mail(form, is_reminder=True)
            form.reminded_at = now
            self.db.flush()
            if form.type == FormType.REVIEW.value and form.candidate_id:
                EventService(self.db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(form.candidate_id),
                    candidate_id=form.candidate_id,
                    event_name="Review Overdue Reminder to Interviewer",
                    state_code="REVIEW_REMINDER_TO_INTERVIEWER",
                    actor_type="SYSTEM",
                    event_metadata={
                        "form_id": str(form.id),
                        "employee_id": form.employee.id,
                    },
                ))
            sent += 1
        if sent:
            self.db.commit()
        return sent

    def run_escalation_job(self) -> int:
        forms = self.repository.list_due_for_escalation()
        created = 0
        for form in forms:
            alert_type = self._get_alert_type(form.type)
            from app.modules.rounds.round_model import Round

            round_obj = (
                self.db.query(Round).filter(Round.id == form.round_id).first()
                if form.round_id
                else None
            )
            jd_id = round_obj.jd_id if round_obj else None
            action_url = (
                f"/rate-candidate/{form.id}"
                if alert_type == NotificationType.REVIEW.value
                else f"/book-slot/{form.id}"
            )
            title = (
                "Review pending"
                if alert_type == NotificationType.REVIEW.value
                else "Slot availability request"
            )
            payload = dict(
                notification_type=alert_type,
                title=title,
                body="A form is waiting for your action.",
                action_url=action_url,
                action_label="Submit review" if alert_type == NotificationType.REVIEW.value else "Book slots",
                form_id=form.id,
                job_id=jd_id,
                dedupe_key=f"{form.type}-{form.id}",
            )
            created_notification = self.notification_service.notify(
                employee_id=form.employee.id, **payload,
            )
            if jd_id:
                self.notification_service.notify_job_team(jd_id, **payload)
            if created_notification:
                created += 1
                if form.type == FormType.REVIEW.value and form.candidate_id:
                    EventService(self.db).create_event(EventCreate(
                        entity_type="CANDIDATE",
                        entity_id=str(form.candidate_id),
                        candidate_id=form.candidate_id,
                        event_name="Review Pending Escalated to HR",
                        state_code="REVIEW_ESCALATED_TO_HR",
                        actor_type="SYSTEM",
                        event_metadata={
                            "form_id": str(form.id),
                            "employee_id": form.employee.id,
                            "alert_type": alert_type,
                        },
                    ))
        return created

    def run_expiry_reconciliation_job(self) -> int:
        forms = self.repository.list_expired()
        updated = 0
        for form in forms:
            try:
                self.repository.mark_expired(form)
                alert_type = self._get_alert_type(form.type)
                self.notification_service.mark_all_read(
                    form.employee.id, notification_type=alert_type,
                )
                updated += 1
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise
        if updated:
            self.db.commit()
        return updated
