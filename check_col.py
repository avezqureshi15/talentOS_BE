from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
with engine.connect() as conn:
    cols = conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position")
    ).fetchall()
    for c in cols:
        print(c[0])
