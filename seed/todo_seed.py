"""Seed data for the todos table."""

TODO_SEEDS = [
    {
        "title": "Set up project architecture",
        "description": "Create the modular FastAPI project structure with core, common, and modules layers.",
        "is_completed": True,
    },
    {
        "title": "Implement Alembic migrations",
        "description": "Set up database version control with Alembic for schema migrations.",
        "is_completed": True,
    },
    {
        "title": "Add authentication module",
        "description": "Implement JWT-based auth module with login, register, and token refresh.",
        "is_completed": False,
    },
    {
        "title": "Write unit tests",
        "description": "Achieve at least 80% test coverage across all service and repository layers.",
        "is_completed": False,
    },
    {
        "title": "Set up CI/CD pipeline",
        "description": "Configure GitHub Actions for linting, testing, and automated deployment.",
        "is_completed": False,
    },
    {
        "title": "Add API documentation",
        "description": "Ensure all endpoints are documented with request/response examples.",
        "is_completed": False,
    },
]
