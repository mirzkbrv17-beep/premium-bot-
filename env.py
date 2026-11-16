import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import models  # noqa: F401  (jadvallarni ro'yxatga olish)
from config import settings
from database import Base

config = context.config
target_metadata = Base.metadata


def _configure(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      render_as_batch=connection.dialect.name == "sqlite")


def run_migrations_offline() -> None:
    context.configure(url=settings.async_database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.async_database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
