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
from seed.todo_seed import TODO_SEEDS  # noqa: E402

logger = get_logger(__name__)


def seed_todos() -> int:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(Todo).count()
        if existing > 0:
            logger.info("Todos table already has %d records, skipping seed", existing)
            return 0

        for item in TODO_SEEDS:
            todo = Todo(**item)
            db.add(todo)

        db.commit()
        logger.info("Seeded %d todos", len(TODO_SEEDS))
        return len(TODO_SEEDS)
    except Exception as e:
        db.rollback()
        logger.error("Failed to seed todos: %s", str(e))
        raise
    finally:
        db.close()


def main() -> None:
    logger.info("Starting seed — env=%s | db=%s", settings.APP_ENV, settings.DATABASE_URL)
    total = seed_todos()
    logger.info("Seed complete — %d records inserted", total)


if __name__ == "__main__":
    main()
