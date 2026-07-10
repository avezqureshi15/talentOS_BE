# Coding Standards

This document defines the **mandatory coding conventions** for the entire codebase.
Every PR MUST comply with these rules. Violations are grounds for rejection.

---

## 1. Constants

### 1.1 Global Constants — `app/core/constants.py`

Place every constant that is **shared across two or more modules** here.
This includes error codes, pagination defaults, configurable limits, etc.

```python
# app/core/constants.py
from enum import Enum


class ErrorCode(str, Enum):
    TODO_NOT_FOUND = "TODO_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"


DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
```

**Rules:**
- Always add a new `ErrorCode` member when creating a new exception class
- Expose plain constants at module level (not nested in classes) for simple values
- Use `str` enums for error codes so `.value` returns a serialisable string
- Every constant MUST have a type annotation

### 1.2 Module-Level Constants — inside the module file

If a constant is **only used within a single module**, define it at the top of the
relevant file, prefixed with underscore to indicate private scope.

```python
# app/modules/todo/todo_service.py
_MAX_TITLE_LENGTH: int = 255
```

**Never** put single-module constants in `app/core/constants.py`.

### 1.3 Magic Numbers — ZERO TOLERANCE

Hard-coded numbers or strings in the middle of functions are forbidden.
Extract them to a named constant at the top of the file or in `core/constants.py`.

```python
# BAD
if len(title) > 255:
    raise ValueError("Too long")

# GOOD
_MAX_TITLE_LEN: int = 255
if len(title) > _MAX_TITLE_LEN:
    raise ValueError("Too long")
```

---

## 2. Error Handling

### 2.1 Exception Hierarchy

All application exceptions **must** inherit from `BaseAppException`.

```
BaseAppException (app/common/exceptions/base_exception.py)
├── TodoNotFoundException   (app/common/exceptions/todo_exception.py)
├── UserNotFoundException   (app/common/exceptions/user_exception.py)   # example
└── ...                     (create one file per module in exceptions/)
```

### 2.2 Creating a New Exception

Open `app/common/exceptions/<module>_exception.py` and subclass `BaseAppException`:

```python
from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode


class TodoNotFoundException(BaseAppException):
    def __init__(self, todo_id: int):
        super().__init__(
            message=f"Todo with id {todo_id} not found",
            code=ErrorCode.TODO_NOT_FOUND,
            status_code=404,
        )
```

**Rules:**
- One exception class per file, one file per module
- Always define a unique `ErrorCode` in `core/constants.py` for the exception
- Pass a human-readable `message`, the `ErrorCode` member, and an HTTP `status_code`
- The global handler in `app/common/handlers/global_exception_handler.py` will catch
  every `BaseAppException` subclass automatically — no manual registration needed

### 2.3 Raising Exceptions

Only raise from the **Service layer**. Never from routers or repositories.

```python
# Service layer — CORRECT
def get_todo_by_id(self, todo_id: int) -> TodoResponse:
    todo = self.repository.get_by_id(todo_id)
    if not todo:
        raise TodoNotFoundException(todo_id)
    return TodoResponse.model_validate(todo)
```

### 2.4 Adding a New ErrorCode

1. Add the new code to `ErrorCode` enum in `app/core/constants.py`
2. Create the exception class in `app/common/exceptions/`
3. Export it from `app/common/exceptions/__init__.py`

```python
# app/core/constants.py
class ErrorCode(str, Enum):
    TODO_NOT_FOUND = "TODO_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"   # new
    ...
```

```python
# app/common/exceptions/__init__.py
from .base_exception import BaseAppException
from .todo_exception import TodoNotFoundException
from .user_exception import UserNotFoundException   # new

__all__ = ["BaseAppException", "TodoNotFoundException", "UserNotFoundException"]
```

---

## 3. Logging

### 3.1 Logger Initialisation

Every file that needs logging **must** create a module-level logger with `get_logger(__name__)`:

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
```

**Never** use `logging.getLogger(...)` directly. Always go through `app.core.logger.get_logger`.

### 3.2 Log Levels — When to Use What

| Level | When |
|-------|------|
| `logger.debug(...)` | Detailed diagnostic info (DB queries, param values, loop state) |
| `logger.info(...)` | Normal application events (entity created, request started) |
| `logger.warning(...)` | Recoverable issues (retry attempts, deprecated usage) |
| `logger.error(...)` | Business errors that are handled (entity not found, validation fail) |
| `logger.critical(...)` | Unrecoverable system failures (DB connection lost) |

### 3.3 Structured Logging Pattern

Always use **printf-style formatting** (not f-strings) and include **key-value pairs**
for searchability:

```python
# BAD — f-string, hard to grep
logger.info(f"Creating todo: {data.title}")

# GOOD — printf-style, structured
logger.info("Creating todo: title=%s", data.title)

# GOOD — multiple context fields
logger.info("Todo created: id=%d | title=%s", todo.id, todo.title)

# BAD — no context
logger.info("Todo not found")

# GOOD — includes searchable context
logger.error("Todo not found: id=%d", todo_id)
```

### 3.4 What to Log Per Layer

| Layer | What to log |
|-------|-------------|
| Router | Nothing (middleware handles request/response logging) |
| Service | Entry/exit of key operations, errors before raising exceptions |
| Repository | `INFO` on mutations (create, update status, mark result, delete); `DEBUG` on queries (list, get, count) |
| Middleware | Every request IN/OUT with method, path, status, duration, request ID |

### 3.5 Request ID in Logs

The middleware injects a `request_id` into `request.state.request_id`. If you need to
include it in service-level logs, access it via the `request` object. However, the
default middleware logging is sufficient for tracing — only add request IDs to
service logs when debugging a specific flow.

---

## 4. Imports

### 4.1 Order

```python
# 1. Standard library
import time
from collections.abc import Generator

# 2. Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 3. Application
from app.core.config import settings
from app.modules.todo.todo_schema import TodoResponse
from app.modules.todo.todo_service import TodoService
```

One blank line between each group. Within each group, sort alphabetically.

### 4.2 Import Style

```python
# PREFERRED — import specific names
from app.core.logger import get_logger

# ACCEPTABLE — module-level import (only for large stdlib modules)
import logging

# FORBIDDEN — wildcard imports
from app.modules.todo import *       # NEVER
```

### 4.3 `__init__.py` Exports

Every `__init__.py` that re-exports MUST include an explicit `__all__` list:

```python
from .todo_router import router

__all__ = ["router"]
```

---

## 5. Type Hints

Write annotations everywhere. The project uses Python 3.10+ syntax.

```python
# Parameters and return types — ALWAYS
def create(title: str, description: str | None) -> Todo:
    ...

# Variables
MAX_PAGE_SIZE: int = 100

# Optional — use `X | None` not `Optional[X]`
def get_by_id(self, todo_id: int) -> Todo | None:
    ...

# Collections — use `list[X]` not `List[X]`
def get_all(self) -> list[Todo]:
    ...
```

**Forbidden:**
- `Optional[str]` → use `str | None`
- `List[Todo]` → use `list[Todo]`
- `Dict[str, int]` → use `dict[str, int]`
- `Tuple` → use `tuple`
- Unannotated function parameters or return values

---

## 6. Layer Rules (with Code Examples)

### 6.1 Router — Request/Response Only

```python
# app/modules/todo/todo_router.py
@router.get("/{todo_id}", response_model=TodoResponse)
def get_todo_by_id(todo_id: int, db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.get_todo_by_id(todo_id)
```

**Allowed:**
- Parse path/query params from the request
- Instantiate a Service with the DB session
- Return the service result (FastAPI serialises it)

**Forbidden:**
- Any business logic (`if`, `for`, calculations, validation beyond Pydantic)
- Direct repository or model access
- Logging

### 6.2 Service — Business Logic Only

```python
# app/modules/todo/todo_service.py
class TodoService:
    def __init__(self, db: Session):
        self.repository = TodoRepository(db)

    def get_todo_by_id(self, todo_id: int) -> TodoResponse:
        logger.info("Fetching todo: id=%d", todo_id)
        todo = self.repository.get_by_id(todo_id)
        if not todo:
            raise TodoNotFoundException(todo_id)
        return TodoResponse.model_validate(todo)
```

**Allowed:**
- Business logic, validation, conditional flows
- Raising custom exceptions
- Logging at INFO/ERROR level
- Calling the repository
- Mapping ORM model instances to response DTOs (`model_validate`)

**Forbidden:**
- Direct DB access (queries, sessions, commits)
- HTTP concerns (status codes, headers, request objects)
- Importing routers or schemas from other modules (use common/ for cross-cutting)

### 6.3 Repository — ORM Queries Only

```python
# app/modules/todo/todo_repository.py
class TodoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, todo_id: int) -> Todo | None:
        return self.db.query(Todo).filter(Todo.id == todo_id).first()
```

**Allowed:**
- SQLAlchemy ORM queries (`query`, `filter`, `order_by`, `all`, `first`)
- `add`, `delete`, `flush` (intermediate persistence — see §6.5)
- `commit`, `refresh` (only if the repository owns the full unit of work — preferred)
- Accepting/returning model instances only
- Logging (`INFO` on mutations, `DEBUG` on queries — see §3.4)
- Accepting/returning model instances only
- Logging (`INFO` on mutations, `DEBUG` on queries — see §3.4)

**Forbidden:**
- Business logic (`if`, `for` that contains domain logic)
- Raising exceptions (return `None` for not-found instead)
- Pydantic schema imports
- Accessing `request` or HTTP context

### 6.5 Transaction Ownership

The transaction boundary lives in the **service layer**, not the repository.

```python
# Repository — uses flush() for intermediate persistence
class TodoRepository:
    def mark_completed(self, todo: Todo) -> Todo:
        todo.status = "completed"
        self.db.flush()
        return todo

# Service — owns the commit/rollback
class TodoService:
    def complete_todo(self, todo_id: int) -> TodoResponse:
        todo = self.repository.get_by_id(todo_id)
        if not todo:
            raise TodoNotFoundException(todo_id)
        self.repository.mark_completed(todo)
        self.db.commit()          # ← service commits
        return TodoResponse.model_validate(todo)
```

**Rules:**
- Repositories use `flush()` for partial persistence (same transaction, not committed yet)
- The service calls `commit()` after all repository operations in a unit of work succeed
- The service calls `rollback()` in `except` blocks to abort on failure
- This pattern allows a single service method to coordinate multiple repository calls atomically
- The alternative (full `commit()` inside the repository) is acceptable only for simple, single-repository operations

### 6.6 Schema — Pydantic DTOs

```python
# app/modules/todo/todo_schema.py
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)


class TodoResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Rules:**
- Request DTOs: `*Create`, `*Update` — fields match what the client sends
- Response DTOs: `*Response` — fields match what the API returns, include `from_attributes=True`
  (`model_validate()` works with ORM model instances and dicts)
- Use `Field(...)` for required fields, `Field(None)` for optional
- `*Update` schemas should have all fields optional (partial updates)

---

## 7. Database Access — SQLAlchemy ORM

Only modules that own data in our PostgreSQL use SQLAlchemy (e.g., `todo`).
Modules that proxy to external services (e.g., `jobs`, `applications`) use
httpx and store no data locally.

### 7.1 Session Dependency

Each request gets a fresh SQLAlchemy `Session` via a generator dependency.
The session is automatically closed when the request finishes.

```python
from app.db.session import get_db

@router.get("/todos")
def list_todos(db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.get_all_todos()
```

### 7.2 Engine Configuration

The engine is configured in `app/db/session.py` with connection pooling:

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### 7.3 Model Definition

Each table maps to a SQLAlchemy model class inheriting from `Base`:

```python
from app.db.base import Base

class Todo(Base):
    __tablename__ = "todos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
```

### 7.4 Repository Query Patterns

```python
# SELECT all
self.db.query(Todo).order_by(Todo.created_at.desc()).all()

# SELECT by id
self.db.query(Todo).filter(Todo.id == todo_id).first()

# INSERT
todo = Todo(title=title, description=description)
self.db.add(todo)
self.db.commit()
self.db.refresh(todo)

# UPDATE (modify then flush)
todo.title = new_title
self.db.commit()
self.db.refresh(todo)

# DELETE
self.db.delete(todo)
self.db.commit()
```

### 7.5 JSON Column Types

For array or flexible data, use `JSON` column type with proper typing:

```python
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

class JobListing(Base):
    __tablename__ = "job_listings"

    requirements: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    benefits: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
```

Pydantic schemas map these as `list[str] | None = Field(None)`.

### 7.6 Foreign Key Relationships

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Application(Base):
    __tablename__ = "applications"

    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False)
    job_listing: Mapped["JobListing"] = relationship(backref="applications")
```

- Use `ondelete="CASCADE"` so deleting a parent removes children
- The `relationship()` allows eager/lazy loading of related entities
- Back-populate from the parent side via `backref="applications"`
- `model_validate` on the child model automatically includes the relationship response

---

## 8. API Versioning

### 8.1 Prefix Convention

All new modules MUST be versioned under `/api/v1/`:

```python
from app.core.config import settings

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["jobs"])
```

The prefix is defined in `app/core/config.py`:
```python
API_V1_PREFIX: str = "/api/v1"
```

### 8.2 Response Envelope

List endpoints wrap results in a `data` + `count` envelope:

```python
@router.get("/")
def list_all(db: Session = Depends(get_db)):
    service = JobService(db)
    items = service.get_all()
    return {"data": items, "count": len(items)}
```

Single-resource endpoints wrap in `data`:
```python
return {"data": item}
```

Delete endpoints return a confirmation message:
```python
return {"message": "Resource deleted successfully"}
```

---

## 9. Dependency Injection

- All DB sessions are injected via `Depends(get_db)` in routers
- Service and Repository classes receive the session through their `__init__`
- Never use global singletons for DB sessions — always use the dependency

```python
# Router — injects SQLAlchemy session
@router.get("/")
def list_todos(db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.get_all_todos()


# Service — receives session, creates repository
class TodoService:
    def __init__(self, db: Session):
        self.repository = TodoRepository(db)
```

---

## 10. Cross-Module Boundaries — ZERO Sideways Imports

### 10.1 The Golden Rule

A module **MUST NEVER** import from another sibling module. The only valid dependency direction is downward into `app/common/`:

```
app/modules/evaluations/                 app/modules/applications/
        │                                       │
        │  FORBIDDEN ←──────────────────────────│
        ▼                                       ▼
    app/common/exceptions/               app/common/clients/
```

### 10.2 What Counts as a Sideways Import

```python
# FORBIDDEN — importing repository from another module
from app.modules.evaluations.evaluation_repository import EvaluationRepository

# FORBIDDEN — importing service from another module
from app.modules.jobs.job_service import JobService

# FORBIDDEN — importing model from another module
from app.modules.evaluations.evaluation_model import Candidate

# FORBIDDEN — importing schema from another module
from app.modules.evaluations.evaluation_schema import AIEvaluationRequest
```

### 10.3 Allowed Dependency Graph

```
app/
├── common/           ← EVERY module may import from here
│   ├── exceptions/     shared exception classes
│   ├── schemas/        shared Pydantic models (if needed)
│   ├── clients/        adapters for external APIs
│   └── utils/          pure utility functions
├── core/             ← EVERY module may import from here
│   ├── config.py       settings
│   ├── constants.py    ErrorCode, pagination defaults
│   └── logger.py       log setup
├── db/               ← EVERY module may import from here
│   └── session.py      engine, get_db
├── middleware/        ← no module imports from here
├── modules/          ← NO module imports from another module
│   ├── evaluations/
│   ├── applications/
│   ├── hiring_requests/
│   ├── jobs/
│   └── ...
└── workers/          ← MAY import from modules (orchestration layer)
```

### 10.4 Sharing Types Between Modules

**Enums** shared across modules belong in `app/core/constants.py`:

```python
# app/core/constants.py
class EvaluationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SHORTLISTED = "SHORTLISTED"
    ...

# Import in any module:
from app.core.constants import EvaluationStatus
```

Never define a shared enum inside a `_model.py` file — that forces other modules to import from a sibling module, which is forbidden.

**DTOs / Schemas** shared across modules belong in `app/common/schemas/`:

```python
# app/common/schemas/evaluation.py
class EvaluationResult(BaseModel):
    application_id: str
    fit_score: int
    status: str

# app/common/clients/ai_client.py
class AIClient:
    def evaluate_resume(self, ...) -> EvaluationResult: ...
```

**ORM Models** that genuinely need to be queried by another module (rare — prefer orchestration) are a known exception. The import is tolerated but should be flagged in code review and ideally resolved by pushing the query down through the owning module's repository.

### 10.5 Cross-Module Orchestration

When one module's flow depends on another (e.g., `applications` needs to evaluate candidates), the orchestration lives in `app/workers/` or the router layer injects both services — but neither module imports the other.

```python
# ACCEPTABLE — worker imports multiple modules
# app/workers/evaluation_worker.py
from app.modules.evaluations.evaluation_service import EvaluationService
from app.modules.applications.application_service import ApplicationService

# ACCEPTABLE — router-level composition (only in the consuming router)
# app/modules/evaluations/evaluation_router.py
# (import ApplicationService only inside the endpoint function)
```

**Exception**: Workers and routers are the ONLY places where cross-module imports are tolerated, and only when strictly necessary.

---

## 11. External API Integration — Adapter Pattern (httpx)

### 11.1 One Adapter Per External Service

Every external API **MUST** have a dedicated adapter class in `app/common/clients/`. No raw `httpx` calls in business logic.

```python
# app/common/clients/supabase_client.py
class SupabaseClient:
    """Single adapter for all Supabase Edge Function calls."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/manage-job-listings", params={"id": job_id})

    def create_job(self, data: dict) -> dict:
        return self._request("POST", "/manage-job-listings", json=data)

    def get_applications(self) -> dict:
        return self._request("GET", "/get-applications")

    def send_email(self, payload: dict) -> dict:
        return self._request("POST", "/send-application-email", json=payload)
```

### 11.2 Why This Exists

- If Supabase changes its base URL, auth headers, or response format — one file changes, not 7
- The adapter is the **only** place that imports `httpx` for external calls
- Services receive the adapter via constructor injection, making them testable with a mock
- Every call has a typed method instead of raw URLs scattered across the codebase

### 11.3 Enforcing the Rule

```python
# BAD — httpx call in service
class JobService:
    def create_job(self, data: JobCreate) -> dict:
        with httpx.Client(timeout=30) as client:
            response = client.post("https://supabase/manage-job-listings", ...)

# GOOD — adapter injected
class JobService:
    def __init__(self, supabase: SupabaseClient):
        self.supabase = supabase

    def create_job(self, data: JobCreate) -> dict:
        return self.supabase.create_job(data.model_dump())
```

---

All outbound HTTP calls MUST use the `httpx` library:

```python
import httpx

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
except httpx.HTTPStatusError as exc:
    logger.error("API error: status=%d | body=%s", exc.response.status_code, exc.response.text)
    raise
except httpx.RequestError as exc:
    logger.error("Connection error: %s", str(exc))
    raise
```

**Rules:**
- Always set an explicit `timeout` — never use the default (no timeout)
- Always call `raise_for_status()` to surface HTTP errors
- Log the error details before raising
- Wrap specific errors into `BaseAppException` subclasses for the global handler

---

## 12. Module Interfaces — Protocols for Testability

### 12.1 Why Protocols

Every repository and external client **MUST** define a Protocol (or ABC). This makes services unit-testable without touching the database or network.

```python
# app/modules/todo/todo_repository.py
from typing import Protocol


class TodoRepositoryProtocol(Protocol):
    def get_by_id(self, todo_id: int) -> Todo | None: ...
    def get_all(self) -> list[Todo]: ...
    def create(self, data: dict) -> Todo: ...
    def update(self, todo: Todo, data: dict) -> Todo: ...
    def delete(self, todo: Todo) -> None: ...


class TodoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, todo_id: int) -> Todo | None:
        ...
```

### 12.2 Service Injection

Services accept protocols, not concrete classes:

```python
class TodoService:
    def __init__(self, repo: TodoRepositoryProtocol):
        self.repository = repo
```

### 12.3 Testing

```python
# tests/test_todo_service.py
class FakeTodoRepo:
    def get_by_id(self, todo_id: int) -> Todo | None:
        return fake_todo if todo_id == 1 else None

def test_get_todo_by_id():
    service = TodoService(repo=FakeTodoRepo())
    result = service.get_todo_by_id(1)
    assert result.id == 1
```

### 12.4 External Clients

Every external API adapter must also have a protocol:

```python
# app/common/clients/supabase_client.py

class SupabaseClientProtocol(Protocol):
    def get_job(self, job_id: str) -> dict: ...
    def create_job(self, data: dict) -> dict: ...
```

---

## 13. Module `__init__.py` Pattern

Each module's `__init__.py` re-exports exactly one thing: the router.

```python
# app/modules/todo/__init__.py
from .todo_router import router

__all__ = ["router"]
```

Registration in `main.py`:

```python
# app/main.py
from app.modules.todo import router as todo_router

app.include_router(todo_router)
```

---

## 14. Adding a New Module — Step-by-Step

### Standard Module Skeleton (Every module MUST use one of these two shapes)

**DB-Backed Module (stores data in PostgreSQL):**

```
app/modules/<name>/
├── __init__.py              # re-exports router
├── <name>_model.py          # SQLAlchemy model
├── <name>_schema.py         # Pydantic request/response DTOs
├── <name>_repository.py     # ORM queries + Protocol
├── <name>_service.py        # business logic (max 150 lines)
└── <name>_router.py         # endpoints (max 80 lines)
```

**Proxy Module (external API only, no local DB):**

```
app/modules/<name>/
├── __init__.py              # re-exports router
├── <name>_schema.py         # Pydantic request/response DTOs
├── <name>_service.py        # business logic (max 150 lines)
└── <name>_router.py         # endpoints (max 80 lines)
```

**Rules:**
- Every module MUST have ALL files listed above — no missing layers
- No module is allowed to skip the repository layer (even if queries are trivial)
- If a module needs types from another domain → the type goes in `app/common/schemas/`
- File size limits: router ≤ 80 lines, service ≤ 150 lines, repository ≤ 100 lines

### Step-by-Step

#### DB-Backed Module

1. Create `app/modules/<name>/` directory
2. Create files in order:
   - `<name>_model.py` — SQLAlchemy model
   - `<name>_schema.py` — Pydantic DTOs
   - `<name>_repository.py` — ORM queries + Protocol
   - `<name>_service.py` — business logic + logging
   - `<name>_router.py` — endpoints
3. Create `__init__.py` that re-exports the router
4. Import the new model in `alembic/env.py` for autogenerate detection
5. Set the router prefix to `f"{settings.API_V1_PREFIX}/<plural>"`
6. Run `docker compose exec app alembic revision --autogenerate -m "create <table>"`
7. Register the router in `app/main.py`
8. Add module-specific exceptions to `app/common/exceptions/`
9. Add new `ErrorCode` values to `app/core/constants.py` if needed
10. Add seed data in `seed/` if needed

#### Proxy Module

1. Create `app/modules/<name>/` directory
2. Create files:
   - `<name>_schema.py` — Pydantic request DTOs
   - `<name>_service.py` — business logic + external API calls via adapter
   - `<name>_router.py` — endpoints
3. Create `__init__.py` that re-exports the router
4. Register the router in `app/main.py`
5. Set the router prefix to `f"{settings.API_V1_PREFIX}/<plural>"`
6. No model, repository, migration, or seed needed

---

## 15. Response Format — Always Use Pydantic Models, Never Raw Dicts

### 15.1 No `_to_candidate_dict` Patterns

Returning raw dictionaries from services bypasses FastAPI's serialization, validation, and OpenAPI generation. Every response **MUST** use a Pydantic schema.

```python
# BAD — manually constructed dict
def _to_candidate_dict(self, evaluation) -> dict:
    return {
        "id": evaluation.application_id,
        "name": evaluation.candidate_name,
        "status": evaluation.status,
    }

# GOOD — Pydantic model
class CandidateResponse(BaseModel):
    id: str
    name: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)

def to_response(self, evaluation: Candidate) -> CandidateResponse:
    return CandidateResponse.model_validate(evaluation)
```

### 15.2 Benefits

- FastAPI validates the response shape automatically
- OpenAPI/Swagger docs reflect the real response schema
- Breaking changes are caught at compile time (type errors) instead of at runtime
- No manual field mapping — `model_validate()` handles ORM -> Pydantic automatically

### 15.3 Envelope Pattern

List endpoints MUST use the envelope pattern with a Pydantic wrapper:

```python
class PaginatedResponse(BaseModel):
    data: list[CandidateResponse]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
```

No endpoint returns a raw `list[...]` or a hand-crafted `{"data": ..., "count": ...}` dict.

---

## 16. Authentication — MUST Be Implemented Before Any Production Deployment

### 16.1 Current Status

The `auth/` module exists but is empty. JWT secrets, Google OAuth client ID/secret, and allowed email domain are already configured in `.env` but not wired into the application.

### 16.2 Requirements

Before going to production:

- [ ] `app/modules/auth/` must contain: `auth_router.py`, `auth_service.py`, `auth_schema.py`
- [ ] Google OAuth callback endpoint (`GET /api/v1/auth/google/callback`)
- [ ] JWT access token (15 min) + refresh token (7 day) issuance
- [ ] `Depends(get_current_user)` dependency that verifies the Bearer token
- [ ] Email domain restriction (only `ALLOWED_EMAIL_DOMAIN`)
- [ ] All protected endpoints require `get_current_user` dependency

### 16.3 Router Protection Pattern

Once auth is implemented:

```python
# Protected endpoint
@router.get("/hiring-requests")
def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ← required
):
    ...
```

---

## 17. Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | `snake_case` with module prefix | `todo_model.py`, `user_service.py` |
| Classes | `PascalCase` | `TodoService`, `UserRepository` |
| Functions | `snake_case` | `get_todo_by_id`, `create_user` |
| Variables | `snake_case` | `todo_id`, `db_session` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE`, `ErrorCode.TODO_NOT_FOUND` |
| Private | Prefix with `_` | `_MAX_TITLE_LEN` |
| Router prefix | plural lowercase | `/todos`, `/users`, `/auth` |
| Tags | plural lowercase | `tags=["todos"]` |
| DB tables | plural snake_case | `todos`, `user_roles` |

---

## 18. Code Style

- Line length: 120 characters maximum
- Indentation: 4 spaces (no tabs)
- Type annotations on every function (parameters + return type)
- No commented-out code — delete it
- No `print()` — use `logger`
- No bare `except:` — catch specific exceptions
- No wildcard imports (`from x import *`)
- F-strings are allowed only in **exception messages** (where printf-style is not possible)
- Logging MUST use printf-style formatting (`"message: var=%s", var`) — never f-strings in `logger.*` calls
- **File size limits** (strictly enforced):
  - Router files: **≤ 80 lines**
  - Service files: **≤ 150 lines**
  - Repository files: **≤ 100 lines**
  - Model files: **≤ 60 lines**
  - Schema files: **≤ 100 lines**
  - If a file exceeds its limit, split it into multiple files or extract logic into a helper module

---

## 19. Alembic Migrations

Alembic is the **only** way to manage schema changes. Never use `Base.metadata.create_all()`
in production (it's used in `main.py` only as a fallback for local dev).

### 19.1 Creating a Migration

```bash
# After adding a new model, generate a migration:
docker compose exec app alembic revision --autogenerate -m "create users table"

# Review the generated file in alembic/versions/
# Then apply it:
docker compose exec app alembic upgrade head
```

### 19.2 Migration Standards

- Each migration file must have a descriptive message
- Always provide both `upgrade()` and `downgrade()` functions
- Test `downgrade()` before committing
- Never edit an existing migration that has been committed — create a new one
- Use `--autogenerate` only as a starting point; always review the output

### 19.3 Wiring New Models

When you create a new SQLAlchemy model, import it in `alembic/env.py` so Alembic
can detect it for autogenerate:

```python
# alembic/env.py
from app.modules.todo.todo_model import Todo
from app.modules.user.user_model import User  # new — add here

target_metadata = Base.metadata
```

---

## 20. Seeding

### 20.1 Seed Files

Place seed data in `seed/<module>_seed.py`:

```python
# seed/user_seed.py
USER_SEEDS = [
    {"email": "admin@example.com", "name": "Admin"},
    ...
]
```

### 20.2 Running Seeds

```bash
# Via Docker:
docker compose exec app python3 -m seed.run_seed

# Or locally:
python -m seed.run_seed
```

### 20.3 Seed Runner Pattern

The runner checks for existing data and skips if records already exist (idempotent):

```python
# seed/run_seed.py
existing = db.query(Todo).count()
if existing > 0:
    logger.info("Already has %d records, skipping", existing)
    return
# ... insert seeds using SQLAlchemy ORM
```

---

## 21. Docker — The Only Setup Path

### 21.1 Single Command

```bash
cp .env.example .env        # edit DATABASE_URL if needed
docker compose up -d        # everything else is automatic
```

That single command does all of the following:
1. Starts PostgreSQL 16 container with health check
2. Builds the Python image (installs all deps from `requirements.txt`)
3. Waits for PostgreSQL to be ready
4. Runs `alembic upgrade head` to apply migrations
5. Runs `python3 -m seed.run_seed` to seed initial data (idempotent)
6. Starts the uvicorn server on port 8000

### 21.2 Other Useful Commands

```bash
docker compose logs -f                                   # tail logs
docker compose down                                      # stop everything
docker compose down -v                                   # stop + delete database
docker compose exec app alembic upgrade head              # run migrations
docker compose exec app alembic revision --autogenerate -m "desc"  # new migration
docker compose exec app python3 -m seed.run_seed          # re-seed
docker compose exec app python3 -c "from app.db.session import engine; engine.connect()"  # test DB
```

### 21.3 Required Environment Variables

```
DATABASE_URL=postgresql://postgres:postgres@db:5432/talentos
APP_ENV=development
LOG_LEVEL=INFO
RESEND_API_KEY=re_xxx                    # optional — email sending
```

In Docker Compose, `DATABASE_URL` points to the `db` service (`host=db`).
For local development, use `host=localhost`.

`RESEND_API_KEY` is optional — the email service logs a warning and skips
sending if the key is not set.

---

## 22. Testing Conventions (not yet implemented)

When tests are added:

- One test file per module: `tests/modules/todo/test_todo_service.py`
- Use `pytest` as the test runner
- Mock the repository layer when testing services
- Use factory fixtures for model instances
- For CI, use a separate test database or SQLite (override `DATABASE_URL`)

---

## 23. Summary — Checklist Before Committing

- [ ] Constants defined at the right level (global vs module)
- [ ] Exceptions inherit `BaseAppException`, registered in `__init__.py`
- [ ] Logging uses `get_logger(__name__)` and printf-style formatting
- [ ] Layer rules respected (no business logic in routers/repos)
- [ ] Type annotations on every function
- [ ] No magic numbers or hard-coded strings
- [ ] Imports follow the required order
- [ ] Router uses versioned prefix: `f"{settings.API_V1_PREFIX}/<plural>"`
- [ ] List endpoints use `{"data": items, "count": len(items)}` envelope
- [ ] Router exports from module `__init__.py`
- [ ] `__all__` defined in every public `__init__.py`
- [ ] `ErrorCode` added to `core/constants.py` for new exceptions
- [ ] Migration created for new/modified models
- [ ] New model imported in `alembic/env.py`
- [ ] New config vars added to `.env.example` and `Settings` class
- [ ] Seed data added for new modules (if applicable)
- [ ] httpx timeouts set for all external API calls
- [ ] **Cross-module check**: zero imports from sibling modules
- [ ] **Adapter check**: all external API calls go through `app/common/clients/`
- [ ] **Protocol check**: repository and client protocols defined
- [ ] **File size check**: router ≤ 80 lines, service ≤ 150 lines, repository ≤ 100 lines
- [ ] **Response check**: no raw dicts — all responses use Pydantic models
- [ ] **Module skeleton check**: all required files exist (model, schema, repo, service, router)
- [ ] **Auth check**: protected endpoints include `Depends(get_current_user)` (when auth is live)
- [ ] **No duplication check**: no repeated business logic across modules (extract to `common/`)
