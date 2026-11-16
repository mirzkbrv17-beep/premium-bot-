"""XP, level, VIP va achievementlar."""
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (Achievement, MarketOrder, Order, Payment, Referral, Streak, TaskCompletion, Transfer,
                    UserAchievement, UserXP, VipLevel, XPEvent)
from services.balance_service import change_balance
from services.settings_service import get_setting

DEFAULT_XP = {"daily": 5, "task": 10, "referral": 20, "quiz": 5, "market": 10, "achievement": 15}

DEFAULT_VIP = [(1, "Bronze", 3, 0, "Yangi a'zo"), (2, "Silver", 5, 2, "Faol a'zo"), (3, "Gold", 10, 5, "Oltin a'zo"),
               (4, "Diamond", 20, 8, "Olmos a'zo"), (5, "Abu Elite", 30, 10, "ABU Elite")]

DEFAULT_ACH = [
    ("ref10", "10 ta referral", "10 ta do'st taklif qiling", "👥", "referrals", 10, 20),
    ("ref50", "50 ta referral", "50 ta do'st taklif qiling", "👥", "referrals", 50, 100),
    ("ref100", "100 ta referral", "100 ta do'st taklif qiling", "👑", "referrals", 100, 250),
    ("streak7", "7 kunlik streak", "7 kun ketma-ket bonus oling", "🔥", "streak", 7, 15),
    ("streak30", "30 kunlik streak", "30 kun ketma-ket bonus oling", "🔥", "streak", 30, 100),
    ("tasks100", "100 ta topshiriq", "100 ta topshiriq bajaring", "📋", "tasks", 100, 100),
    ("tasks500", "500 ta topshiriq", "500 ta topshiriq bajaring", "📋", "tasks", 500, 500),
    ("first_buy", "Birinchi xarid", "Birinchi xaridingizni qiling", "🛍", "purchases", 1, 5),
    ("first_transfer", "Birinchi transfer", "Birinchi transferingizni qiling", "🔁", "transfers", 1, 5),
    ("seller", "Market sotuvchisi", "Marketda birinchi savdoni yakunlang", "💼", "sales", 1, 10),
]


def level_for(xp: int) -> int:
    return int(math.sqrt(max(xp, 0) / 100)) + 1  # 0-99 XP: 1-level, 100: 2, 400: 3, 900: 4 ...


async def ensure_defaults(session: AsyncSession) -> None:
    if (await session.execute(select(func.count(VipLevel.id)))).scalar_one() == 0:
        for rank, name, lvl, disc, title in DEFAULT_VIP:
            session.add(VipLevel(rank=rank, name=name, min_level=lvl, discount_percent=disc, title=title))
    if (await session.execute(select(func.count(Achievement.code)))).scalar_one() == 0:
        for code, name, desc, icon, kind, thr, rew in DEFAULT_ACH:
            session.add(Achievement(code=code, name=name, description=desc, icon=icon, kind=kind,
                                    threshold=thr, reward_f=rew))
    await session.flush()


async def get_xp(session: AsyncSession, user_id: int, lock: bool = False) -> UserXP:
    stmt = select(UserXP).where(UserXP.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = UserXP(user_id=user_id, xp=0, level=1)
        session.add(row)
        await session.flush()
    return row


async def award_xp(session: AsyncSession, user_id: int, kind: str, ref: str, amount: int | None = None) -> list[str]:
    """Bir (kind, ref) uchun faqat bir marta XP beradi. Level oshsa ABU F mukofoti va xabar qaytaradi."""
    if amount is None:
        amount = int(await get_setting(session, f"xp_{kind}", str(DEFAULT_XP.get(kind, 0))))
    if amount <= 0:
        return []
    dup = (await session.execute(select(XPEvent.id).where(XPEvent.kind == kind, XPEvent.ref == ref))).first()
    if dup:
        return []
    row = await get_xp(session, user_id, lock=True)
    session.add(XPEvent(user_id=user_id, kind=kind, ref=ref, amount=amount))
    old = row.level
    row.xp += amount
    row.level = level_for(row.xp)
    msgs: list[str] = []
    if row.level > old:
        reward = int(await get_setting(session, "levelup_reward_f", "10"))
        for lvl in range(old + 1, row.level + 1):
            if reward > 0:
                await change_balance(session, user_id, "ABU_F", reward, "level_up", f"lvl:{user_id}:{lvl}")
            msgs.append(f"🎉 Tabriklaymiz! Yangi level: <b>{lvl}</b>" + (f" (+{reward} ABU F)" if reward > 0 else ""))
    await session.flush()
    return msgs


async def vip_for(session: AsyncSession, user_id: int) -> VipLevel | None:
    row = await get_xp(session, user_id)
    return (await session.execute(select(VipLevel).where(VipLevel.min_level <= row.level)
                                  .order_by(VipLevel.rank.desc()).limit(1))).scalar_one_or_none()


async def _counters(session: AsyncSession, uid: int) -> dict[str, int]:
    async def count(stmt):
        return (await session.execute(stmt)).scalar_one() or 0
    streak = await count(select(func.max(Streak.current)).where(Streak.user_id == uid))
    return {
        "referrals": await count(select(func.count(Referral.id)).where(Referral.inviter_id == uid, Referral.status == "rewarded")),
        "streak": streak,
        "tasks": await count(select(func.count(TaskCompletion.id)).where(TaskCompletion.user_id == uid)),
        "purchases": await count(select(func.count(Order.id)).where(Order.user_id == uid)) +
                     await count(select(func.count(Payment.id)).where(Payment.user_id == uid, Payment.status == "paid")),
        "transfers": await count(select(func.count(Transfer.id)).where(Transfer.sender_id == uid)),
        "sales": await count(select(func.count(MarketOrder.id)).where(MarketOrder.seller_id == uid,
                                                                      MarketOrder.status == "completed")),
    }


async def check_achievements(session: AsyncSession, uid: int) -> list[str]:
    have = {r[0] for r in await session.execute(select(UserAchievement.code).where(UserAchievement.user_id == uid))}
    counters = await _counters(session, uid)
    msgs: list[str] = []
    for a in (await session.execute(select(Achievement))).scalars():
        if a.code in have or counters.get(a.kind, 0) < a.threshold:
            continue
        session.add(UserAchievement(user_id=uid, code=a.code))
        if a.reward_f > 0:
            await change_balance(session, uid, "ABU_F", a.reward_f, "achievement", f"ach:{a.code}:{uid}")
        msgs.append(f"{a.icon} Yangi yutuq: <b>{a.name}</b>" + (f" (+{a.reward_f} ABU F)" if a.reward_f else ""))
        msgs += await award_xp(session, uid, "achievement", f"{a.code}:{uid}")
    await session.flush()
    return msgs
