"""Debug why HTTP API returns slots_count=0 but direct call returns 8."""
import sys
sys.path.insert(0, ".")

from app.db.session import SessionLocal, get_db
from app.modules.users.user_service import UserService
from app.modules.users.user_repository import UserRepository
from app.modules.users.user_model import User
from app.modules.slots.slot_model import Slot
from sqlalchemy import func, or_

db = SessionLocal()

# 1. Exact query from repository
base_query = db.query(User)
filter_condition = or_(
    User.name.ilike(f"%avez%"),
    User.email.ilike(f"%avez%"),
    User.emp_id.ilike(f"%avez%"),
    User.designation.ilike(f"%avez%"),
    User.department.ilike(f"%avez%"),
)
base_query = base_query.filter(filter_condition)
total = base_query.count()
print(f"Total matching: {total}")

results = (
    base_query.outerjoin(Slot, Slot.employee_id == User.id)
    .add_columns(func.count(Slot.id).label("slots_count"))
    .group_by(User.id)
    .order_by(func.count(Slot.id).desc(), User.name.asc())
    .offset(0)
    .limit(20)
    .all()
)
print(f"Query results: {len(results)}")
for u, count in results:
    print(f"  User {u.id} ({u.name}): slots_count={count}")

# 2. Check what UserResponse has after model_validate
from app.modules.users.user_schema import UserResponse, PaginatedUserResponse
for u, count in results:
    user_data = UserResponse.model_validate(u)
    print(f"\nBefore set: slots_count={user_data.slots_count}")
    user_data.slots_count = count
    user_data.has_slots = count > 0
    print(f"After set:  slots_count={user_data.slots_count}, has_slots={user_data.has_slots}")

# 3. Full service call
result = UserService(db).search_users(query="avez", page=1, per_page=20, slots_info=True)
print(f"\nFull service call:")
for u in result.data:
    print(f"  User {u.id} ({u.name}): slots_count={u.slots_count}, has_slots={u.has_slots}")

# 4. Verify the import used by the server
import app.modules.users.user_router as router_mod
routes = router_mod.router.routes
print(f"\nRegistered GET routes:")
for route in routes:
    if "GET" in route.methods:
        print(f"  {route.path} -> {route.endpoint.__name__}")

db.close()
