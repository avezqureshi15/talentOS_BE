from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.db.base import Base


class PermissionModel(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    group = Column(String(50), nullable=False, default="general")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(100), nullable=False, index=True)
    permission_code = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("role_name", "permission_code", name="uq_role_permission"),
    )
