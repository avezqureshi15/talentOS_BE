from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.evaluations.evaluation_model import EvaluationStatus, ResumeEvaluation


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_application_id(self, application_id: str) -> ResumeEvaluation | None:
        return (
            self.db.query(ResumeEvaluation)
            .filter(ResumeEvaluation.application_id == application_id)
            .first()
        )

    def create_queued(
        self,
        application_id: str,
        job_id: str,
        candidate_name: str | None,
        candidate_email: str | None,
        candidate_phone: str | None = None,
        cover_letter: str | None = None,
        resume_url: str | None = None,
    ) -> ResumeEvaluation:
        evaluation = ResumeEvaluation(
            application_id=application_id,
            job_id=job_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            cover_letter=cover_letter,
            resume_url=resume_url,
            status=EvaluationStatus.QUEUED.value,
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def mark_processing(self, evaluation: ResumeEvaluation) -> ResumeEvaluation:
        evaluation.status = EvaluationStatus.PROCESSING.value
        evaluation.attempts += 1
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def mark_result(
        self,
        evaluation: ResumeEvaluation,
        status: EvaluationStatus,
        fit_score: int | None = None,
        summary_md: str | None = None,
        ats_threshold_used: int | None = None,
        error_reason: str | None = None,
    ) -> ResumeEvaluation:
        evaluation.status = status.value
        evaluation.fit_score = fit_score
        evaluation.summary_md = summary_md
        evaluation.ats_threshold_used = ats_threshold_used
        evaluation.error_reason = error_reason
        evaluation.evaluated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def get_by_job(self, job_id: str, status: str | None = None) -> list[ResumeEvaluation]:
        query = self.db.query(ResumeEvaluation).filter(ResumeEvaluation.job_id == job_id)
        if status:
            query = query.filter(ResumeEvaluation.status == status)
        return query.order_by(ResumeEvaluation.fit_score.desc().nullslast()).all()
