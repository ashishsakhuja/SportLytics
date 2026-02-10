from app.db import SessionLocal
import sqlalchemy as sa

s = SessionLocal()
print("DB:", s.execute(sa.text("select current_database(), current_user, current_schema()")).all())
print("Tables:", s.execute(sa.text("select tablename from pg_tables where schemaname=current_schema() order by tablename")).all())
s.close()
