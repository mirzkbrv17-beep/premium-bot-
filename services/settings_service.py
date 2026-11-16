from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import AppSetting


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.get(AppSetting, key)
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    await session.flush()


async def seed_defaults(session: AsyncSession) -> None:
    defaults = {
        "abu_f_rate_uzs": "10",
        "abu_f_min": "5",
        "card_number": settings.CARD_NUMBER,
        "card_holder": settings.CARD_HOLDER,
    }
    for key, value in defaults.items():
        if await session.get(AppSetting, key) is None:
            session.add(AppSetting(key=key, value=value))
    await session.flush()
