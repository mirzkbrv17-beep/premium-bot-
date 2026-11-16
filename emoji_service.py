"""Premium (custom) emoji: kesh, E() yordamchisi va xavfsiz zaxira (fallback)."""
import re
import time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSetting
from utils.emoji_config import FALLBACK

PREFIX = "emoji:"
CACHE: dict[str, str] = {}
STATE = {"enabled": True, "disabled_until": 0.0}
TAG_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.S)


def active() -> bool:
    return STATE["enabled"] and bool(CACHE) and time.monotonic() >= STATE["disabled_until"]


def disable_for(seconds: float) -> None:
    """Telegram custom emoji'ni rad etsa (masalan bot egasida Premium yo'q), vaqtincha oddiy emojiga o'tamiz."""
    STATE["disabled_until"] = time.monotonic() + seconds


def E(key: str) -> str:
    """Xabar matni uchun emoji: custom ID bo'lsa <tg-emoji>, bo'lmasa oddiy emoji."""
    base = FALLBACK.get(key, "")
    cid = CACHE.get(key)
    if cid and active():
        return f'<tg-emoji emoji-id="{cid}">{base}</tg-emoji>'
    return base


def strip_tags(text: str | None) -> str | None:
    return TAG_RE.sub(r"\1", text) if text else text


async def load(session: AsyncSession) -> None:
    CACHE.clear()
    rows = (await session.execute(select(AppSetting).where(AppSetting.key.like(f"{PREFIX}%")))).scalars().all()
    for r in rows:
        if r.value.isdigit():
            CACHE[r.key[len(PREFIX):]] = r.value
    flag = await session.get(AppSetting, "emoji_enabled")
    STATE["enabled"] = flag.value != "0" if flag else True


async def set_emoji(session: AsyncSession, key: str, emoji_id: str) -> None:
    if key not in FALLBACK or not emoji_id.isdigit():
        raise ValueError("Noto'g'ri kalit yoki ID")
    row = await session.get(AppSetting, PREFIX + key)
    if row:
        row.value = emoji_id
    else:
        session.add(AppSetting(key=PREFIX + key, value=emoji_id))
    await session.flush()
    CACHE[key] = emoji_id


async def clear_emoji(session: AsyncSession, key: str) -> None:
    await session.execute(delete(AppSetting).where(AppSetting.key == PREFIX + key))
    CACHE.pop(key, None)


async def set_enabled(session: AsyncSession, on: bool) -> None:
    row = await session.get(AppSetting, "emoji_enabled")
    if row:
        row.value = "1" if on else "0"
    else:
        session.add(AppSetting(key="emoji_enabled", value="1" if on else "0"))
    await session.flush()
    STATE["enabled"] = on
    STATE["disabled_until"] = 0.0
