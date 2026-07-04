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
│   │   ├── todo/                    # DB-backed module (model + repository)
│   │   │   ├── __init__.py          # Re-exports router
│   │   │   ├── todo_model.py        # SQLAlchemy model
│   │   │   ├── todo_schema.py       # Pydantic request/response DTOs
│   │   │   ├── todo_repository.py   # ORM queries only
│   │   │   ├── todo_service.py      # Business logic only
│   │   │   └── todo_router.py       # FastAPI router
│   │   ├── jobs/                    # Proxy module (calls Supabase Edge Function)
│   │   │   ├── __init__.py          # Re-exports router
│   │   │   ├── job_schema.py        # Pydantic request DTOs
│   │   │   ├── job_service.py       # httpx calls to Supabase
│   │   │   └── job_router.py        # FastAPI router
│   │   └── applications/            # Proxy module (calls Supabase Edge Functions)
│   │       ├── __init__.py          # Re-exports router
│   │       ├── application_schema.py  # Pydantic request DTOs
│   │       ├── application_service.py # httpx calls to Supabase
│   │       └── application_router.py  # FastAPI router
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

### DB-Backed Modules (e.g. `todo`)

| Layer        | Responsibility                        | Allowed to import from             |
|--------------|---------------------------------------|------------------------------------|
| Router       | Parse request, delegate to service    | Service, Schema, Depends(get_db)   |
| Service      | Business logic, logging               | Repository, Schema, Exceptions     |
| Repository   | SQLAlchemy ORM queries (no logic)     | Model, DB session                  |
| Model        | SQLAlchemy table definition           | Base, SQLAlchemy types             |
| Schema       | Pydantic models for I/O               | Pydantic (no app imports)          |

### Proxy Modules (e.g. `jobs`, `applications`)

| Layer        | Responsibility                        | Allowed to import from             |
|--------------|---------------------------------------|------------------------------------|
| Router       | Parse request, delegate to service    | Service, Schema                    |
| Service      | Make httpx calls, log, handle errors  | Schema, Exceptions, core/config    |
| Schema       | Pydantic request validation           | Pydantic (no app imports)          |

Proxy modules have **no model or repository** — they call external HTTP APIs (Supabase Edge Functions).

## Naming Conventions

- File names: `snake_case` with module prefix: `todo_model.py`, `user_router.py`
- Classes: `PascalCase` — `TodoService`, `UserRepository`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Router prefix: versioned — `/api/v1/<plural>`, e.g. `/api/v1/jobs`, `/api/v1/applications`
- Legacy modules (e.g. `todo`) may still use unversioned `/todos` until migrated
- App version via `API_V1_PREFIX` in `Settings`: all v1 routers use `f"{settings.API_V1_PREFIX}/<plural>"`

## API Versioning

All new modules MUST be versioned under `/api/v1/`:

```python
# app/modules/jobs/job_router.py
router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["jobs"])
```

The prefix is configured in `app/core/config.py` as `API_V1_PREFIX`.

List endpoints return a **response envelope**:
```json
{
  "data": [...],
  "count": 5
}
```

Single-resource endpoints return:
```json
{
  "data": { ... }
}
```

Delete endpoints return:
```json
{
  "message": "Resource deleted successfully"
}
```

## Adding a New Module

### DB-Backed Module (stores data in our PostgreSQL)

1. Create `app/modules/<name>/` folder
2. Add `__init__.py` that re-exports the router
3. Create `_model.py`, `_schema.py`, `_repository.py`, `_service.py`, `_router.py`
4. Import the new model in `alembic/env.py` for autogenerate detection
5. Run `docker compose exec app alembic revision --autogenerate -m "create <table>"`
6. Register the router in `app/main.py` via `app.include_router()`
7. Add exceptions in `app/common/exceptions/` if needed
8. Add seed data in `seed/` if needed
9. Set the router prefix to `f"{settings.API_V1_PREFIX}/<plural>"` for versioned endpoints

### Proxy Module (calls an external API, no local storage)

1. Create `app/modules/<name>/` folder
2. Add `__init__.py` that re-exports the router
3. Create `_schema.py`, `_service.py`, `_router.py` (no model or repository)
4. Register the router in `app/main.py` via `app.include_router()`
5. Set the router prefix to `f"{settings.API_V1_PREFIX}/<plural>"`
6. The service layer makes httpx calls to the external API
