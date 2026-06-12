"""Run all seed scripts to populate the database with initial data.

Usage:
    python -m seed.run_seed
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.modules.todo.todo_model import Todo  # noqa: E402, F401
from app.modules.users.user_model import User  # noqa: E402, F401
from seed.todo_seed import TODO_SEEDS  # noqa: E402
from seed.user_seed import USER_SEEDS  # noqa: E402

logger = get_logger(__name__)


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
