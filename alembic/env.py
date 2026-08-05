import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

config = context.config

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dev.db")
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.db.base import Base  # noqa: E402
from app.modules.notifications.notification_model import Notification  # noqa: E402, F401
from app.modules.api_keys.api_key_model import ApiKey, ApiKeyPermission  # noqa: E402, F401
from app.modules.auth.auth_model import RefreshToken  # noqa: E402, F401
from app.modules.auth.invite_model import TenantInvite  # noqa: E402, F401
from app.modules.designation.designation_model import Band, Designation, KpiDefinition  # noqa: E402, F401
from app.modules.employees.employee_model import Employee  # noqa: E402, F401
from app.modules.events.event_model import Event  # noqa: E402, F401
from app.modules.evaluations.evaluation_model import Candidate  # noqa: E402, F401
from app.modules.forms.form_model import Form  # noqa: E402, F401
from app.modules.hiring_requests.hiring_request_model import HiringRequest  # noqa: E402, F401
from app.modules.interviews.models import Interview, RoundInterviewer  # noqa: E402, F401
from app.modules.reviews.review_model import Review  # noqa: E402, F401
from app.modules.rounds.round_model import Round  # noqa: E402, F401
from app.modules.settings.settings_model import TenantSetting  # noqa: E402, F401
from app.modules.slots.slot_model import Slot  # noqa: E402, F401
from app.modules.tenants.tenant_model import Tenant  # noqa: E402, F401
from app.modules.todo.todo_model import Todo  # noqa: E402, F401
from app.modules.users.user_model import User  # noqa: E402, F401
from app.modules.users.permission_model import PermissionModel, RolePermission  # noqa: E402, F401
from app.cron.cron_model import FailedCronJob  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
