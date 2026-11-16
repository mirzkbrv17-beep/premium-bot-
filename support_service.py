from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SupportMessage, SupportTicket, User


class SupportError(Exception):
    pass


def tid(ticket_id: int) -> str:
    return f"T-{ticket_id:05d}"


async def create_ticket(session: AsyncSession, user_id: int, text: str) -> SupportTicket:
    text = text.strip()
    if not text:
        raise SupportError("Matn bo'sh")
    t = SupportTicket(user_id=user_id, subject=text[:60])
    session.add(t)
    await session.flush()
    session.add(SupportMessage(ticket_id=t.id, sender="user", text=text[:3000]))
    await session.flush()
    return t


async def user_message(session: AsyncSession, ticket_id: int, user_id: int, text: str) -> SupportTicket:
    t = await session.get(SupportTicket, ticket_id)
    if not t or t.user_id != user_id:
        raise SupportError("Murojaat topilmadi")
    if t.status == "closed":
        raise SupportError("Murojaat yopilgan. Yangisini oching.")
    session.add(SupportMessage(ticket_id=t.id, sender="user", text=text.strip()[:3000]))
    t.status = "open"
    await session.flush()
    return t


async def admin_reply(session: AsyncSession, ticket_id: int, text: str) -> tuple[SupportTicket, User]:
    t = await session.get(SupportTicket, ticket_id)
    if not t:
        raise SupportError("Murojaat topilmadi")
    session.add(SupportMessage(ticket_id=t.id, sender="admin", text=text.strip()[:3000]))
    if t.status != "closed":
        t.status = "answered"
    await session.flush()
    return t, await session.get(User, t.user_id)


async def close_ticket(session: AsyncSession, ticket_id: int) -> tuple[SupportTicket, User]:
    t = await session.get(SupportTicket, ticket_id)
    if not t:
        raise SupportError("Murojaat topilmadi")
    t.status = "closed"
    await session.flush()
    return t, await session.get(User, t.user_id)


async def user_tickets(session: AsyncSession, user_id: int) -> list[SupportTicket]:
    return list((await session.execute(select(SupportTicket).where(SupportTicket.user_id == user_id)
                                       .order_by(SupportTicket.id.desc()).limit(10))).scalars())


async def messages(session: AsyncSession, ticket_id: int, limit: int = 8) -> list[SupportMessage]:
    rows = (await session.execute(select(SupportMessage).where(SupportMessage.ticket_id == ticket_id)
                                  .order_by(SupportMessage.id.desc()).limit(limit))).scalars().all()
    return list(reversed(rows))
