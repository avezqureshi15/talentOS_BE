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
    build_review_link,
    build_slot_link,
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
                        form.user.id, notification_type=form.type
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

        content = self._build_notification_content(
            form,
            candidate_name=candidate_name,
            job_title=job_title,
            round_name=round_name,
        )

        self.notification_service.notify(
            employee_id=user_id,
            notification_type=alert_type,
            title=content["title"],
            body=content["body"],
            action_url=content["action_url"],
            action_label=content["action_label"],
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
                    "employee_id": form.user.id,
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
            employee_id=form.user.id, notification_type=alert_type,
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

    def _build_notification_content(
        self,
        form: Form,
        candidate_name: str | None = None,
        job_title: str | None = None,
        round_name: str | None = None,
    ) -> dict:
        is_review = form.type == FormType.REVIEW.value
        reviewer = form.employee.name or form.employee.emp_id or str(form.employee_id)
        sent_at = form.last_sent_at.strftime("%d %b %Y, %H:%M") if form.last_sent_at else "—"
        action_url = f"/rate-candidate/{form.id}" if is_review else f"/book-slot/{form.id}"
        form_link = build_review_link(form.id) if is_review else build_slot_link(form.id)

        parts = [f"Assigned to: {reviewer}", f"Sent: {sent_at}"]
        if round_name:
            parts.append(f"Interview: {round_name}")
        if job_title:
            parts.append(f"Job: {job_title}")
        if candidate_name:
            parts.append(f"Candidate: {candidate_name}")
        parts.append(f"Form: {form_link}")
        body = " · ".join(parts)

        return {
            "title": "Review pending" if is_review else "Slot availability request",
            "body": body,
            "action_url": action_url,
            "action_label": "Send reminder",
        }

    def remind_by_form(self, form_id: UUID) -> tuple[Form, str]:
        form = self.repository.get_by_id(form_id)
        if not form:
            raise ValueError(f"Form not found: form_id={form_id}")
        return self.notify_form(user_id=form.user.id, form_type=form.type, is_reminder=True)

    def _resolve_job_id_for_candidate(self, candidate_id: int):
        from app.modules.evaluations.evaluation_model import Candidate
        from app.modules.hiring_requests.hiring_request_model import HiringRequest

        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate or not candidate.external_job_id:
            return None
        try:
            external = UUID(str(candidate.external_job_id))
        except ValueError:
            return None
        hiring_request = (
            self.db.query(HiringRequest)
            .filter(
                (HiringRequest.id == external) | (HiringRequest.external_job_id == external)
            )
            .first()
        )
        return hiring_request.id if hiring_request else None

    def _send_form_mail(self, form: Form, is_reminder: bool = False) -> None:
        if form.type == FormType.REVIEW.value:
            send_review_mail_task(form.user.id, form.id, None, None, None, is_reminder=is_reminder)
        else:
            send_slot_mail_task(form.user.id, form.id, is_reminder=is_reminder)

    def run_reminder_job(self) -> int:
        if not is_smtp_configured():
            logger.warning(
                "Reminder run skipped: SMTP not configured — deferring to next run and keeping reminded_at untouched"
            )
            return 0
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
                        "employee_id": form.user.id,
                    },
                ))
            sent += 1
        if sent:
            self.db.commit()
        return sent

    def run_escalation_job(self) -> int:
        from app.modules.hiring_requests.hiring_request_model import HiringRequest

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
            if not jd_id and form.type == FormType.REVIEW.value and form.candidate_id:
                jd_id = self._resolve_job_id_for_candidate(form.candidate_id)
            hiring_request = None
            if jd_id:
                hiring_request = (
                    self.db.query(HiringRequest).filter(HiringRequest.id == jd_id).first()
                )
            tenant_id = (
                form.employee.tenant_id
                if form.employee and form.employee.tenant_id is not None
                else (hiring_request.tenant_id if hiring_request else None)
            )
            candidate_name = None
            if form.candidate_id:
                from app.modules.evaluations.evaluation_model import Candidate

                candidate = (
                    self.db.query(Candidate).filter(Candidate.id == form.candidate_id).first()
                )
                candidate_name = candidate.candidate_name if candidate else None
            content = self._build_notification_content(
                form,
                candidate_name=candidate_name,
                job_title=hiring_request.title if hiring_request else None,
                round_name=round_obj.name if round_obj else None,
            )
            payload = dict(
                notification_type=alert_type,
                title=content["title"],
                body=content["body"],
                action_url=content["action_url"],
                action_label=content["action_label"],
                form_id=form.id,
                job_id=jd_id,
                dedupe_key=f"{form.type}-{form.id}",
            )
            created_notification = self.notification_service.notify(
                employee_id=form.user.id, **payload,
            )
            if alert_type == NotificationType.REVIEW.value:
                if jd_id:
                    self.notification_service.notify_job_team(jd_id, **payload)
                if tenant_id is not None:
                    self.notification_service.notify_tenant_admins(tenant_id, **payload)
            else:
                if tenant_id is not None:
                    self.notification_service.notify_tenant_users(tenant_id, **payload)
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
                            "employee_id": form.user.id,
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
                    form.user.id, notification_type=alert_type,
                )
                updated += 1
            except sa_exc.SQLAlchemyError:
                self.db.rollback()
                raise
        if updated:
            self.db.commit()
        return updated
