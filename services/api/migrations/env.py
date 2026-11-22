"""Alembic environment. The app passes an open connection in config.attributes."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import database_url_from_env

config = context.config


def run() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    # CLI usage (alembic revision / upgrade) against DATABASE_URL or DB_* variables.
    url = database_url_from_env()
    engine = engine_from_config(
        {"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()


run()
