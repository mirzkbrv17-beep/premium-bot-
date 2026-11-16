from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Achievement, Friendship, User, UserAchievement
from services import progress_service
from services.prefs_service import get_prefs


class FriendError(Exception):
    pass


async def _pair(session: AsyncSession, a: int, b: int) -> Friendship | None:
    return (await session.execute(select(Friendship).where(
        or_((Friendship.requester_id == a) & (Friendship.addressee_id == b),
            (Friendship.requester_id == b) & (Friendship.addressee_id == a))))).scalar_one_or_none()


async def are_friends(session: AsyncSession, a: int, b: int) -> bool:
    f = await _pair(session, a, b)
    return bool(f and f.status == "accepted")


async def find_user(session: AsyncSession, abu_id: str) -> User | None:
    return (await session.execute(select(User).where(User.abu_id == abu_id.strip().upper()))).scalar_one_or_none()


async def send_request(session: AsyncSession, me: int, target_abu_id: str) -> tuple[str, User]:
    """('sent' | 'accepted', target). 'accepted' — qarshi tomon allaqachon so'rov yuborgan bo'lsa."""
    target = await find_user(session, target_abu_id)
    if not target or target.is_banned:
        raise FriendError("Bunday ABU ID topilmadi")
    if target.id == me:
        raise FriendError("O'zingizga so'rov yubora olmaysiz")
    existing = await _pair(session, me, target.id)
    if existing:
        if existing.status == "accepted":
            raise FriendError("Siz allaqachon do'stsiz")
        if existing.requester_id == me:
            raise FriendError("So'rov allaqachon yuborilgan")
        existing.status = "accepted"  # ikkalasi ham xohlagan
        await session.flush()
        return "accepted", target
    if not (await get_prefs(session, target.id)).allow_requests:
        raise FriendError("Bu foydalanuvchi do'stlik so'rovlarini qabul qilmaydi")
    session.add(Friendship(requester_id=me, addressee_id=target.id, status="pending"))
    await session.flush()
    return "sent", target


async def respond(session: AsyncSession, me: int, friendship_id: int, accept: bool) -> User:
    f = await session.get(Friendship, friendship_id)
    if not f or f.addressee_id != me or f.status != "pending":
        raise FriendError("So'rov topilmadi")
    requester = await session.get(User, f.requester_id)
    if accept:
        f.status = "accepted"
    else:
        await session.delete(f)
    await session.flush()
    return requester


async def remove(session: AsyncSession, me: int, other: int) -> None:
    f = await _pair(session, me, other)
    if not f or f.status != "accepted":
        raise FriendError("Siz do'st emassiz")
    await session.delete(f)
    await session.flush()


async def friends(session: AsyncSession, me: int) -> list[User]:
    rows = (await session.execute(select(Friendship).where(
        Friendship.status == "accepted", or_(Friendship.requester_id == me, Friendship.addressee_id == me)).limit(50))).scalars()
    ids = [f.addressee_id if f.requester_id == me else f.requester_id for f in rows]
    return list((await session.execute(select(User).where(User.id.in_(ids)))).scalars()) if ids else []


async def incoming(session: AsyncSession, me: int) -> list[tuple[Friendship, User]]:
    rows = (await session.execute(select(Friendship, User).join(User, User.id == Friendship.requester_id).where(
        Friendship.addressee_id == me, Friendship.status == "pending").order_by(Friendship.id).limit(20))).all()
    return [(f, u) for f, u in rows]


async def profile_card(session: AsyncSession, viewer: int, target: User) -> dict:
    """Maxfiylik sozlamasiga ko'ra profil. Telegram username/ism oshkor qilinmaydi — faqat ABU ID va o'yin ko'rsatkichlari."""
    mode = (await get_prefs(session, target.id)).profile_visibility
    friend = await are_friends(session, viewer, target.id)
    visible = viewer == target.id or mode == "all" or (mode == "friends" and friend)
    card = {"abu_id": target.abu_id, "visible": visible, "friend": friend}
    if visible:
        xp = await progress_service.get_xp(session, target.id)
        vip = await progress_service.vip_for(session, target.id)
        n = len((await session.execute(select(UserAchievement.id).where(UserAchievement.user_id == target.id))).all())
        card.update(level=xp.level, vip=vip.name if vip else None, achievements=n,
                    joined=target.created_at.date().isoformat())
    return card
