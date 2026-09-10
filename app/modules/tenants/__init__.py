# Intentionally empty: importing this package must not load tenant_router.
# tenant_router imports require_permission → get_current_user; auth_dependencies
# imports tenant_access/tenant_model. A re-export here caused a circular import
# that broke `alembic upgrade`.
