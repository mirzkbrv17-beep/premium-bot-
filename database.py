import asyncio
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

BASE_DIR = Path(__file__).resolve().parent
BASELINE = "0001"  # 1-5 qismlardagi jadvallar (create_all bilan yaratilgan eski bazalar uchun)


class Base(DeclarativeBase):
    pass


def _migrate(stamp_baseline: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    if stamp_baseline:
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Bazani Alembic migratsiyalari bilan yangilaydi.
    Eski (create_all bilan yaratilgan) baza bo'lsa, avval baseline belgilanadi, so'ng yangi jadvallar qo'shiladi."""
    import models  # noqa: F401

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    stamp = "users" in tables and "alembic_version" not in tables
    await asyncio.to_thread(_migrate, stamp)
