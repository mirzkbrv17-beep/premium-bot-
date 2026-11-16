import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Order, Product
from services.balance_service import change_balance, get_balance
from services.progress_service import vip_for
from services.settings_service import get_setting


class ShopError(Exception):
    pass


def final_price_uzs(p: Product) -> int:
    return math.ceil(p.price_uzs * (100 - p.discount_percent) / 100)  # kasr -> keyingi butun so'm


async def price_in_abu_f(session: AsyncSession, price_uzs: int) -> int:
    rate = int(await get_setting(session, "abu_f_rate_uzs", "10"))
    return math.ceil(price_uzs / rate)


async def quote(session: AsyncSession, user_id: int, p: Product) -> tuple[int, int]:
    """(narx so'mda, narx ABU F da) — mahsulot chegirmasi va foydalanuvchi VIP chegirmasi bilan."""
    price = final_price_uzs(p)
    vip = await vip_for(session, user_id)
    if vip and vip.discount_percent:
        price = math.ceil(price * (100 - vip.discount_percent) / 100)
    return price, await price_in_abu_f(session, price)


async def buy(session: AsyncSession, user_id: int, product_id: int) -> Order:
    p = (await session.execute(select(Product).where(Product.id == product_id).with_for_update())).scalar_one_or_none()
    if not p or not p.is_active:
        raise ShopError("Mahsulot mavjud emas")
    if p.stock is not None and p.stock <= 0:
        raise ShopError("Omborda qolmagan")
    price, cost = await quote(session, user_id, p)
    bal = await get_balance(session, user_id, "ABU_F", lock=True)
    if bal.amount < cost:
        raise ShopError(f"ABU F yetarli emas. Kerak: {cost}")
    if p.stock is not None:
        p.stock -= 1
    order = Order(user_id=user_id, product_id=p.id, price_uzs=price, price_abu_f=cost, status="paid")
    session.add(order)
    await session.flush()
    await change_balance(session, user_id, "ABU_F", -cost, "shop", f"order:{order.id}")
    return order
