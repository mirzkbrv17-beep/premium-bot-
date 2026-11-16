from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserPrefs

KINDS = {"referral": "Referral mukofoti", "orders": "Buyurtma va savdo holati", "news": "Admin e'lonlari (yangiliklar)",
         "daily": "Kunlik bonus eslatmasi"}
VISIBILITY = ["all", "friends", "nobody"]
VIS_LABEL = {"all": "Hamma ko'ra oladi", "friends": "Faqat do'stlar", "nobody": "Hech kim"}


async def get_prefs(session: AsyncSession, user_id: int) -> UserPrefs:
    p = await session.get(UserPrefs, user_id)
    if p is None:
        p = UserPrefs(user_id=user_id)
        session.add(p)
        await session.flush()
    return p


async def toggle(session: AsyncSession, user_id: int, kind: str) -> bool:
    if kind not in KINDS:
        raise ValueError("kind")
    p = await get_prefs(session, user_id)
    attr = f"notify_{kind}"
    setattr(p, attr, not getattr(p, attr))
    await session.flush()
    return getattr(p, attr)


async def cycle_visibility(session: AsyncSession, user_id: int) -> str:
    p = await get_prefs(session, user_id)
    p.profile_visibility = VISIBILITY[(VISIBILITY.index(p.profile_visibility) + 1) % 3]
    await session.flush()
    return p.profile_visibility


async def toggle_requests(session: AsyncSession, user_id: int) -> bool:
    p = await get_prefs(session, user_id)
    p.allow_requests = not p.allow_requests
    await session.flush()
    return p.allow_requests


async def should_notify(session: AsyncSession, user_id: int, kind: str) -> bool:
    p = await session.get(UserPrefs, user_id)
    if p is None:  # sozlama yo'q bo'lsa standart qiymatlar
        return kind != "daily"
    return bool(getattr(p, f"notify_{kind}"))


async def notify_user(session: AsyncSession, bot, user, kind: str, text: str) -> bool:
    """Foydalanuvchi shu turdagi bildirishnomani o'chirgan bo'lsa, yuborilmaydi."""
    if not await should_notify(session, user.id, kind):
        return False
    try:
        await bot.send_message(user.tg_id, text)
        return True
    except Exception:
        return False
