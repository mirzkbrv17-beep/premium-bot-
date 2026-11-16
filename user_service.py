from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


async def get_or_create_user_ex(session: AsyncSession, tg_id: int, username: str | None,
                                full_name: str) -> tuple[User, bool]:
    user = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if user:
        user.username, user.full_name = username, full_name
        return user, False
    user = User(tg_id=tg_id, username=username, full_name=full_name)
    session.add(user)
    await session.flush()
    user.abu_id = f"ABU-{user.id:06d}"
    await session.flush()
    return user, True


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str) -> User:
    return (await get_or_create_user_ex(session, tg_id, username, full_name))[0]
