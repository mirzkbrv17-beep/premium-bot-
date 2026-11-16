import logging
from datetime import datetime, timedelta, timezone

from aiogram.exceptions import TelegramAPIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import MandatoryChannel, Referral, User
from services.balance_service import change_balance
from services.prefs_service import should_notify
from services.progress_service import award_xp, check_achievements

log = logging.getLogger("abu.referral")

REWARD_F = 50
REWARD_TON = 2
DELAY = timedelta(hours=2)
OK_STATUSES = {"member", "administrator", "creator"}


def norm_channel(name: str) -> str:
    name = name.strip().replace("https://t.me/", "").lstrip("@")
    return "@" + name


async def ensure_default_channel(session: AsyncSession) -> None:
    count = (await session.execute(select(func.count(MandatoryChannel.id)))).scalar_one()
    if count == 0:
        session.add(MandatoryChannel(username="@o11abu"))
        await session.flush()


async def list_channels(session: AsyncSession) -> list[str]:
    rows = await session.execute(select(MandatoryChannel.username).order_by(MandatoryChannel.id))
    return [r[0] for r in rows]


async def register_referral(session: AsyncSession, invitee: User, payload: str | None) -> Referral | None:
    """Faqat YANGI foydalanuvchi uchun chaqiriladi. Payload: ref_<inviter users.id>."""
    if not payload or not payload.startswith("ref_") or not payload[4:].isdigit():
        return None
    inviter_id = int(payload[4:])
    if inviter_id == invitee.id or await session.get(User, inviter_id) is None:
        return None
    exists = (await session.execute(select(Referral).where(Referral.invitee_id == invitee.id))).scalar_one_or_none()
    if exists:
        return None
    ref = Referral(inviter_id=inviter_id, invitee_id=invitee.id)
    session.add(ref)
    await session.flush()
    return ref


async def check_subscribed(bot, tg_id: int, channels: list[str]) -> bool | None:
    """True/False; Telegram xatosi bo'lsa None (aniq javob yo'q)."""
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, tg_id)
        except TelegramAPIError as ex:
            log.warning("get_chat_member xato (%s): %s", ch, ex)
            return None
        if member.status not in OK_STATUSES:
            return False
    return True


async def mark_subscribed(session: AsyncSession, user: User, bot) -> str:
    """'ok' | 'not_subscribed' | 'error'. Obuna tasdiqlansa 2 soatlik taymer boshlanadi."""
    channels = await list_channels(session)
    res = await check_subscribed(bot, user.tg_id, channels)
    if res is None:
        return "error"
    if not res:
        return "not_subscribed"
    ref = (await session.execute(
        select(Referral).where(Referral.invitee_id == user.id).with_for_update())).scalar_one_or_none()
    if ref and ref.status == "pending" and ref.subscribed_at is None:
        now = datetime.now(timezone.utc)  # server vaqti
        ref.subscribed_at = now
        ref.check_at = now + DELAY
    return "ok"


async def process_due(session: AsyncSession, bot) -> list[tuple[int, str]]:
    """Muddati kelgan referrallarni qayta tekshiradi. [(inviter_tg_id, xabar)] qaytaradi."""
    now = datetime.now(timezone.utc)
    refs = (await session.execute(
        select(Referral).where(Referral.status == "pending", Referral.check_at.is_not(None),
                               Referral.check_at <= now).with_for_update(skip_locked=True)
    )).scalars().all()
    events: list[tuple[int, str]] = []
    channels = await list_channels(session)
    for ref in refs:
        invitee = await session.get(User, ref.invitee_id)
        res = await check_subscribed(bot, invitee.tg_id, channels)
        if res is None:
            continue  # keyingi aylanishda qayta uriniladi
        if res:
            await change_balance(session, ref.inviter_id, "ABU_F", REWARD_F, "referral", f"ref:{ref.id}:F")
            await change_balance(session, ref.inviter_id, "ABU_TON", REWARD_TON, "referral", f"ref:{ref.id}:TON")
            ref.status, ref.rewarded_at = "rewarded", now
            inviter = await session.get(User, ref.inviter_id)
            extra = await award_xp(session, ref.inviter_id, "referral", f"ref:{ref.id}")
            extra += await check_achievements(session, ref.inviter_id)
            if await should_notify(session, ref.inviter_id, "referral"):  # mukofot beriladi, xabar esa sozlamaga ko'ra
              events.append((inviter.tg_id, f"🎉 Taklifingiz uchun <b>{REWARD_F} ABU F</b> va "
                                          f"<b>{REWARD_TON} ABU TON</b> berildi!" + "".join("\n" + m for m in extra)))
        else:
            ref.status = "cancelled"
    await session.flush()
    return events


async def stats(session: AsyncSession, user_id: int) -> dict[str, int]:
    rows = await session.execute(
        select(Referral.status, func.count(Referral.id)).where(Referral.inviter_id == user_id)
        .group_by(Referral.status))
    d = {"pending": 0, "rewarded": 0, "cancelled": 0}
    d.update({k: v for k, v in rows})
    return d
