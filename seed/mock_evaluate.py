"""Insert mock AI evaluation data for a candidate when the AI service is down.

Usage:
    python -m seed.mock_evaluate <application_id>
    python -m seed.mock_evaluate <application_id> --rejected
"""
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.constants import EvaluationStatus  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.applications.application_repository import ApplicationRepository  # noqa: E402
from app.modules.evaluations.evaluation_model import Candidate  # noqa: E402
from app.modules.reviews.review_model import Review  # noqa: E402
from app.modules.rounds.round_model import Round  # noqa: E402
from app.modules.rounds.round_repository import RoundRepository  # noqa: E402

logger = get_logger(__name__)

MOCK_SHORTLISTED_REVIEWS = {
    "fitscore": 82,
    "summary_md": "### Candidate Summary\n\nStrong candidate with relevant experience in full-stack development. Proven track record of delivering scalable applications.\n\n**Key strengths:**\n- 5+ years of experience in React and Node.js\n- Led a team of 3 developers\n- Strong problem-solving skills",
    "strong_matches": ["React expertise", "Team leadership", "Full-stack experience"],
    "gaps_and_concerns": ["Limited cloud experience"],
}

MOCK_REJECTED_REVIEWS = {
    "fitscore": 35,
    "summary_md": "### Candidate Summary\n\nCandidate does not meet the minimum requirements for this position.\n\n**Areas of concern:**\n- Insufficient years of experience\n- Location mismatch\n- Notice period too long",
    "strong_matches": [],
    "gaps_and_concerns": ["Insufficient experience", "Location mismatch", "Notice period too long"],
    "rejected_status": ["YOE", "LOCATION", "NOTICE_PERIOD"],
    "rejected_reason": "Candidate has less than required years of experience, is located outside the preferred region, and has a long notice period.",
}


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python -m seed.mock_evaluate <application_id> [--rejected]")
        sys.exit(1)

    application_id = args[0]
    is_rejected = "--rejected" in args
    mock = MOCK_REJECTED_REVIEWS if is_rejected else MOCK_SHORTLISTED_REVIEWS
    verdict = "rejected" if is_rejected else "shortlisted"
    status = EvaluationStatus.REJECTED if is_rejected else EvaluationStatus.SHORTLISTED

    db = SessionLocal()
    try:
        repo = ApplicationRepository(db)
        candidate = repo.get_candidate_by_application_id(application_id)
        if not candidate:
            logger.error("Candidate not found: application_id=%s", application_id)
            sys.exit(1)

        candidate.status = status.value
        candidate.fit_score = mock["fitscore"]
        candidate.summary_md = mock["summary_md"]
        candidate.ats_threshold_used = 70
        candidate.evaluated_at = datetime.now(timezone.utc)
        db.flush()

        round_obj = Round(
            id=uuid.uuid4(),
            name="Resume Shortlisting",
            candidate_id=candidate.id,
        )
        db.add(round_obj)
        db.flush()
        db.refresh(round_obj)

        candidate.current_round_id = round_obj.id
        db.flush()

        review = Review(
            id=uuid.uuid4(),
            round_id=round_obj.id,
            entity_type="AI",
            reviews=mock,
            verdict=verdict,
        )
        db.add(review)
        db.commit()
        db.refresh(candidate)

        logger.info(
            "Mock evaluation complete: application_id=%s | status=%s | round_id=%s | review verdict=%s",
            application_id, status.value, round_obj.id, verdict,
        )
        print(f"Candidate {application_id} → {status.value}")
        print(f"  Round:     {round_obj.id}")
        print(f"  Review:    {review.id}")
        print(f"  Fit score: {mock['fitscore']}")
        print(f"  Verdict:   {verdict}")

    except Exception as e:
        db.rollback()
        logger.error("Mock evaluation failed: %s", str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
