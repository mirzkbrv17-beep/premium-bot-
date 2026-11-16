from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Referral, Streak, Task, TaskCompletion, User
from services import referral_service
from services.balance_service import change_balance
from services.progress_service import award_xp, check_achievements
from utils.helpers import today_tashkent


class TaskError(Exception):
    pass


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def active_tasks(session: AsyncSession) -> list[Task]:
    now = datetime.now(timezone.utc)
    rows = (await session.execute(select(Task).where(Task.is_active.is_(True)).order_by(Task.id))).scalars().all()
    return [t for t in rows if (not t.starts_at or _aware(t.starts_at) <= now) and (not t.ends_at or _aware(t.ends_at) > now)]


async def complete_task(session: AsyncSession, bot, user: User, task_id: int, today=None) -> list[str]:
    today = today or today_tashkent()
    task = await session.get(Task, task_id)
    if not task or task not in await active_tasks(session):
        raise TaskError("Topshiriq mavjud emas yoki muddati tugagan")
    period = "once" if task.repeat == "once" else today.isoformat()
    done = (await session.execute(select(TaskCompletion.id).where(
        TaskCompletion.task_id == task.id, TaskCompletion.user_id == user.id, TaskCompletion.period_key == period))).first()
    if done:
        raise TaskError("Bu topshiriq allaqachon bajarilgan")
    # Tekshirish mexanizmi: soxta bajarilganga mukofot berilmaydi
    if task.kind == "channel":
        res = await referral_service.check_subscribed(bot, user.tg_id, [task.channel or ""])
        if res is None:
            raise TaskError("Tekshirib bo'lmadi, keyinroq urinib ko'ring")
        if not res:
            raise TaskError("Siz hali kanalga obuna bo'lmagansiz")
    elif task.kind == "bonus":
        st = (await session.execute(select(Streak).where(Streak.user_id == user.id))).scalar_one_or_none()
        if not st or st.last_claim != today:
            raise TaskError("Avval bugungi kunlik bonusni oling")
    elif task.kind == "invite":
        n = (await session.execute(select(func.count(Referral.id)).where(
            Referral.inviter_id == user.id, Referral.status == "rewarded"))).scalar_one()
        if n < 1:
            raise TaskError("Hali mukofotlangan taklifingiz yo'q")
    else:
        raise TaskError("Noma'lum topshiriq turi")
    from models import TaskCompletion as TC
    session.add(TC(task_id=task.id, user_id=user.id, period_key=period))
    await session.flush()
    msgs = []
    if task.reward_f:
        await change_balance(session, user.id, "ABU_F", task.reward_f, "task", f"task:{task.id}:{user.id}:{period}:F")
    if task.reward_ton:
        await change_balance(session, user.id, "ABU_TON", task.reward_ton, "task", f"task:{task.id}:{user.id}:{period}:T")
    msgs += await award_xp(session, user.id, "task", f"{task.id}:{user.id}:{period}")
    msgs += await check_achievements(session, user.id)
    return msgs
