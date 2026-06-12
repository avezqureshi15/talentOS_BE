# Project Structure

This document defines the **canonical project structure** that MUST be followed for all modules in this application.
Every developer MUST adhere to this layout to keep the codebase consistent, scalable, and maintainable.

```
├── app/                             # Application source code
│   ├── main.py                      # FastAPI app entry point
│   ├── core/                        # Global cross-cutting configs (zero business logic)
│   │   ├── config.py                # Pydantic BaseSettings – loads .env
│   │   ├── constants.py             # Enums, error codes, magic numbers
│   │   ├── logger.py                # Centralized logging setup
│   │   └── security.py              # Request ID generation, crypto helpers
│   ├── common/                      # Shared primitives (reused by many modules)
│   │   ├── exceptions/
│   │   │   ├── base_exception.py    # BaseAppException
│   │   │   └── <module>_exception.py
│   │   └── handlers/
│   │       └── global_exception_handler.py
│   ├── db/                          # SQLAlchemy engine + session
│   │   ├── base.py                  # DeclarativeBase
│   │   └── session.py               # Engine, SessionLocal, get_db dependency
│   ├── modules/                     # Domain modules (one folder per domain)
│   │   └── <module_name>/
│   │       ├── __init__.py          # Re-exports router
│   │       ├── <module>_model.py    # SQLAlchemy model
│   │       ├── <module>_schema.py   # Pydantic request/response DTOs
│   │       ├── <module>_repository.py  # ORM queries only
│   │       ├── <module>_service.py  # Business logic only
│   │       └── <module>_router.py   # FastAPI router
│   └── middleware/
│       └── request_logging_middleware.py
├── alembic/                         # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_todos_table.py
├── seed/                            # Seed data scripts
│   ├── run_seed.py                  # Seed runner
│   └── todo_seed.py                 # Todo seed definitions
├── rules/                           # Documentation
│   ├── folder-structure.md
│   └── code.md
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Layer Rules (STRICT)

| Layer        | Responsibility                        | Allowed to import from             |
|--------------|---------------------------------------|------------------------------------|
| Router       | Parse request, delegate to service    | Service, Schema, Depends(get_db)   |
| Service      | Business logic, logging               | Repository, Schema, Exceptions     |
| Repository   | SQLAlchemy ORM queries (no logic)     | Model, DB session                  |
| Model        | SQLAlchemy table definition           | Base, SQLAlchemy types             |
| Schema       | Pydantic models for I/O               | Pydantic (no app imports)          |

## Naming Conventions

- File names: `snake_case` with module prefix: `todo_model.py`, `user_router.py`
- Classes: `PascalCase` — `TodoService`, `UserRepository`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Router prefix: plural — `/todos`, `/users`

## Adding a New Module

1. Create `app/modules/<name>/` folder
2. Add `__init__.py` that re-exports the router
3. Create `_model.py`, `_schema.py`, `_repository.py`, `_service.py`, `_router.py`
4. Import the new model in `alembic/env.py` for autogenerate detection
5. Run `docker compose exec app alembic revision --autogenerate -m "create <table>"`
6. Register the router in `app/main.py` via `app.include_router()`
7. Add exceptions in `app/common/exceptions/` if needed
8. Add seed data in `seed/` if needed
