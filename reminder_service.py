from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Streak, User, UserPrefs
from services.settings_service import get_setting, set_setting
from utils.helpers import TASHKENT

REMINDER_HOUR = 10


async def run_reminder_once(session: AsyncSession, bot, now: datetime | None = None) -> int:
    """Kuniga bir marta (Toshkent 10:00 dan keyin): eslatmani yoqqan va bugun bonus olmaganlarga xabar."""
    now = now or datetime.now(TASHKENT)
    today = now.date()
    if now.hour < REMINDER_HOUR or await get_setting(session, "reminder_last") == today.isoformat():
        return 0
    await set_setting(session, "reminder_last", today.isoformat())
    await session.commit()  # qayta yuborilib ketmasligi uchun avval belgilanadi
    rows = (await session.execute(select(User.tg_id, Streak.last_claim).join(UserPrefs, UserPrefs.user_id == User.id)
                                  .outerjoin(Streak, Streak.user_id == User.id)
                                  .where(UserPrefs.notify_daily.is_(True), User.is_banned.is_(False)))).all()
    sent = 0
    for tg_id, last in rows:
        if last == today:
            continue
        try:
            await bot.send_message(tg_id, "🎁 Bugungi kunlik bonusni olishni unutmang! /start → Kunlik bonus")
            sent += 1
        except Exception:
            pass
    return sent
