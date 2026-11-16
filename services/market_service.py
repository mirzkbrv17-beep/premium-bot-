from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Listing, MarketMessage, MarketOrder, Review
from services.balance_service import change_balance, get_balance
from services.settings_service import get_setting


class MarketError(Exception):
    pass


async def create_listing(session: AsyncSession, seller_id: int, title: str, price: int, description: str) -> Listing:
    title = title.strip()[:100]
    if not title or price < 1 or price > 1_000_000_000:
        raise MarketError("Nom yoki narx noto'g'ri")
    li = Listing(seller_id=seller_id, title=title, price_abu_f=price, description=description.strip()[:500],
                 status="pending")  # har bir e'lon moderatsiyadan o'tadi
    session.add(li)
    await session.flush()
    return li


async def moderate(session: AsyncSession, listing_id: int, status: str) -> Listing:
    li = await session.get(Listing, listing_id)
    if not li or status not in ("approved", "rejected", "hidden"):
        raise MarketError("E'lon topilmadi")
    li.status = status
    await session.flush()
    return li


async def edit_price(session: AsyncSession, listing_id: int, seller_id: int, price: int) -> Listing:
    li = await session.get(Listing, listing_id)
    if not li or li.seller_id != seller_id or price < 1:
        raise MarketError("E'lon topilmadi yoki narx noto'g'ri")
    li.price_abu_f, li.status = price, "pending"  # tahrirdan keyin qayta moderatsiya
    await session.flush()
    return li


async def hide_own(session: AsyncSession, listing_id: int, seller_id: int) -> Listing:
    li = await session.get(Listing, listing_id)
    if not li or li.seller_id != seller_id:
        raise MarketError("E'lon topilmadi")
    li.status = "hidden"
    await session.flush()
    return li


async def search(session: AsyncSession, query: str | None = None, sort: str = "new",
                 page: int = 0, per_page: int = 8) -> list[Listing]:
    stmt = select(Listing).where(Listing.status == "approved")
    if query:
        stmt = stmt.where(func.lower(Listing.title).contains(query.lower().strip()))
    stmt = stmt.order_by(Listing.price_abu_f if sort == "cheap" else Listing.id.desc()).offset(page * per_page).limit(per_page)
    return list((await session.execute(stmt)).scalars())


async def seller_rating(session: AsyncSession, seller_id: int) -> tuple[float, int]:
    avg, n = (await session.execute(select(func.avg(Review.rating), func.count(Review.id))
                                    .where(Review.seller_id == seller_id))).one()
    return (round(float(avg), 1) if avg else 0.0), n


async def buy(session: AsyncSession, buyer_id: int, listing_id: int) -> MarketOrder:
    li = (await session.execute(select(Listing).where(Listing.id == listing_id).with_for_update())).scalar_one_or_none()
    if not li or li.status != "approved":
        raise MarketError("E'lon mavjud emas")
    if li.seller_id == buyer_id:
        raise MarketError("O'z e'loningizni sotib ololmaysiz")
    bal = await get_balance(session, buyer_id, "ABU_F", lock=True)
    if bal.amount < li.price_abu_f:
        raise MarketError(f"ABU F yetarli emas. Kerak: {li.price_abu_f}")
    fee_pct = int(await get_setting(session, "market_fee_percent", "5"))
    order = MarketOrder(listing_id=li.id, buyer_id=buyer_id, seller_id=li.seller_id, price_abu_f=li.price_abu_f,
                        fee_abu_f=li.price_abu_f * fee_pct // 100, status="paid")
    session.add(order)
    await session.flush()
    await change_balance(session, buyer_id, "ABU_F", -order.price_abu_f, "market_buy", f"mkt:{order.id}:buy")  # escrow
    return order


async def _order(session: AsyncSession, order_id: int) -> MarketOrder:
    o = (await session.execute(select(MarketOrder).where(MarketOrder.id == order_id).with_for_update())).scalar_one_or_none()
    if not o:
        raise MarketError("Buyurtma topilmadi")
    return o


async def mark_delivered(session: AsyncSession, order_id: int, seller_id: int) -> MarketOrder:
    o = await _order(session, order_id)
    if o.seller_id != seller_id or o.status != "paid":
        raise MarketError("Amal mumkin emas")
    o.status = "delivered"
    await session.flush()
    return o


async def _release(session: AsyncSession, o: MarketOrder) -> None:
    o.status = "completed"
    await change_balance(session, o.seller_id, "ABU_F", o.price_abu_f - o.fee_abu_f, "market_sale", f"mkt:{o.id}:sale")


async def confirm(session: AsyncSession, order_id: int, buyer_id: int) -> MarketOrder:
    o = await _order(session, order_id)
    if o.buyer_id != buyer_id or o.status != "delivered":
        raise MarketError("Amal mumkin emas")
    await _release(session, o)
    return o


async def dispute(session: AsyncSession, order_id: int, buyer_id: int) -> MarketOrder:
    o = await _order(session, order_id)
    if o.buyer_id != buyer_id or o.status not in ("paid", "delivered"):
        raise MarketError("Amal mumkin emas")
    o.status = "disputed"
    await session.flush()
    return o


async def admin_release(session: AsyncSession, order_id: int) -> MarketOrder:
    o = await _order(session, order_id)
    if o.status not in ("paid", "delivered", "disputed"):
        raise MarketError("Buyurtma allaqachon yopilgan")
    await _release(session, o)
    return o


async def admin_refund(session: AsyncSession, order_id: int) -> MarketOrder:
    o = await _order(session, order_id)
    if o.status not in ("paid", "delivered", "disputed"):
        raise MarketError("Buyurtma allaqachon yopilgan")
    o.status = "refunded"
    await change_balance(session, o.buyer_id, "ABU_F", o.price_abu_f, "market_refund", f"mkt:{o.id}:refund")
    return o


async def add_message(session: AsyncSession, order_id: int, sender_id: int, text: str) -> int:
    """Xabarni saqlaydi va qarshi tomon user.id sini qaytaradi (shaxsiy ma'lumot oshkor qilinmaydi)."""
    o = await session.get(MarketOrder, order_id)
    if not o or sender_id not in (o.buyer_id, o.seller_id):
        raise MarketError("Buyurtma topilmadi")
    session.add(MarketMessage(order_id=o.id, sender_id=sender_id, text=text.strip()[:1000]))
    await session.flush()
    return o.seller_id if sender_id == o.buyer_id else o.buyer_id


async def review(session: AsyncSession, order_id: int, buyer_id: int, rating: int) -> Review:
    o = await session.get(MarketOrder, order_id)
    if not o or o.buyer_id != buyer_id or o.status != "completed" or not 1 <= rating <= 5:
        raise MarketError("Baholab bo'lmaydi")
    if (await session.execute(select(Review.id).where(Review.order_id == o.id))).first():
        raise MarketError("Siz allaqachon baho bergansiz")
    r = Review(order_id=o.id, seller_id=o.seller_id, rating=rating)
    session.add(r)
    await session.flush()
    return r
