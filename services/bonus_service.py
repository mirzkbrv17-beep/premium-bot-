from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Streak
from services.balance_service import change_balance
from utils.helpers import today_tashkent

BASE_REWARD = 5
MILESTONES = {3: 10, 7: 25, 14: 50, 30: 100}  # streak kuni -> qo'shimcha ABU F


class AlreadyClaimed(Exception):
    pass


async def claim_daily(session: AsyncSession, user_id: int, today: date | None = None) -> tuple[int, int]:
    """(streak, reward). Kuni Asia/Tashkent bo'yicha; bir kunda faqat bir marta."""
    today = today or today_tashkent()
    st = (await session.execute(select(Streak).where(Streak.user_id == user_id).with_for_update())).scalar_one_or_none()
    if st is None:
        st = Streak(user_id=user_id, current=0, last_claim=None)
        session.add(st)
        await session.flush()
    if st.last_claim == today:
        raise AlreadyClaimed()
    st.current = st.current + 1 if st.last_claim == today - timedelta(days=1) else 1
    st.last_claim = today
    reward = BASE_REWARD + MILESTONES.get(st.current, 0)
    # ref har kun uchun unikal -> takroriy to'lovdan ikkinchi himoya
    await change_balance(session, user_id, "ABU_F", reward, "daily_bonus", f"daily:{user_id}:{today.isoformat()}")
    return st.current, reward
