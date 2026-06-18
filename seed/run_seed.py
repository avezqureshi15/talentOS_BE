"""Run all seed scripts to populate the database with initial data.

Usage:
    python -m seed.run_seed
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.modules.designation.designation_model import Band, Designation, KpiDefinition  # noqa: E402, F401
from app.modules.hiring_requests.hiring_request_model import HiringRequest  # noqa: E402, F401
from app.modules.todo.todo_model import Todo  # noqa: E402, F401
from app.modules.users.user_model import User  # noqa: E402, F401
from seed.bands_seed import BANDS_SEEDS  # noqa: E402
from seed.designation_seed import DESIGNATION_SEEDS  # noqa: E402
from seed.kpi_definitions_seed import KPI_DEFINITIONS_SEEDS  # noqa: E402
from seed.todo_seed import TODO_SEEDS  # noqa: E402
from seed.user_seed import USER_SEEDS  # noqa: E402

logger = get_logger(__name__)


def _prepare_record(record: dict) -> dict:
    prepared = dict(record)
    for key in ("created_at", "updated_at"):
        if key in prepared and isinstance(prepared[key], str):
            prepared[key] = datetime.fromisoformat(prepared[key].replace("Z", "+00:00"))
    if "weightage" in prepared and isinstance(prepared["weightage"], str):
        prepared["weightage"] = int(float(prepared["weightage"]))
    return prepared


def _seed_table(db, model, seeds: list[dict], label: str) -> int:
    existing = db.query(model).count()
    if existing > 0:
        logger.info("%s table already has %d records, skipping seed", label, existing)
        return 0

    for item in seeds:
        record = model(**item)
        db.add(record)

    db.commit()
    logger.info("Seeded %d %s", len(seeds), label)
    return len(seeds)


def run_seeds() -> int:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    total = 0
    try:
        total += _seed_table(db, Todo, TODO_SEEDS, "todos")
        total += _seed_table(db, User, USER_SEEDS, "users")
        total += _seed_table(db, Band, BANDS_SEEDS, "bands")
        total += _seed_table(
            db,
            Designation,
            [_prepare_record(d) for d in DESIGNATION_SEEDS],
            "designations",
        )
        total += _seed_table(
            db,
            KpiDefinition,
            [_prepare_record(d) for d in KPI_DEFINITIONS_SEEDS],
            "kpi_definitions",
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to seed: %s", str(e))
        raise
    finally:
        db.close()

    return total


def main() -> None:
    logger.info("Starting seed — env=%s | db=%s", settings.APP_ENV, settings.DATABASE_URL)
    total = run_seeds()
    logger.info("Seed complete — %d records inserted", total)


if __name__ == "__main__":
    main()
