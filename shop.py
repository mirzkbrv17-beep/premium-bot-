from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Product
from services.admin_service import targets
from services import progress_service, shop_service
from services.shop_service import ShopError, final_price_uzs, price_in_abu_f
from services.user_service import get_or_create_user
from utils.helpers import e, fmt

router = Router()


@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery, session: AsyncSession):
    prods = (await session.execute(select(Product).where(Product.is_active.is_(True))
                                   .order_by(Product.category, Product.id).limit(40))).scalars().all()
    rows = [[B(text=f"{p.category} · {p.name} — {fmt(final_price_uzs(p))} so'm", callback_data=f"shop:p:{p.id}")]
            for p in prods]
    rows.append([B(text="⬅️ Orqaga", callback_data="home")])
    text = "🛍 <b>ABU SHOP</b>\n" + ("Mahsulotni tanlang:" if prods else "Hozircha mahsulotlar yo'q.")
    await call.message.edit_text(text, reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^shop:p:\d+$"))
async def product(call: CallbackQuery, session: AsyncSession):
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p or not p.is_active:
        await call.answer("Mahsulot topilmadi", show_alert=True)
        return
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    price, cost = await shop_service.quote(session, user.id, p)
    stock = "cheksiz" if p.stock is None else str(p.stock)
    disc = f" (−{p.discount_percent}%)" if p.discount_percent else ""
    kb = M(inline_keyboard=[[B(text=f"🪙 {fmt(cost)} ABU F bilan olish", callback_data=f"shop:buy:{p.id}")],
                            [B(text="⬅️ Orqaga", callback_data="shop")]])
    await call.message.edit_text(f"<b>{e(p.name)}</b>\n{e(p.description)}\n\n"
                                 f"Narx: <b>{fmt(price)} so'm</b>{disc}\nOmborda: {stock}", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^shop:buy:\d+$"))
async def confirm(call: CallbackQuery):
    pid = call.data.split(":")[2]
    kb = M(inline_keyboard=[[B(text="✅ Ha, xarid qilaman", callback_data=f"shop:ok:{pid}"),
                             B(text="❌ Yo'q", callback_data="shop")]])
    await call.message.edit_text("Xaridni tasdiqlaysizmi? ABU F balansingizdan yechiladi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^shop:ok:\d+$"))
async def execute(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    try:
        order = await shop_service.buy(session, user.id, int(call.data.split(":")[2]))
    except ShopError as ex:
        await call.message.edit_text(f"❌ {ex}", reply_markup=M(inline_keyboard=[[B(text="⬅️ Do'kon", callback_data="shop")]]))
        await call.answer()
        return
    await call.message.edit_text(f"✅ Buyurtma #{order.id} qabul qilindi. Admin tez orada topshiradi.",
                                 reply_markup=M(inline_keyboard=[[B(text="⬅️ Do'kon", callback_data="shop")]]))
    from utils.helpers import say
    await say(call.bot, call.from_user.id, await progress_service.check_achievements(session, user.id))
    for admin_id in await targets(session, "shop"):
        try:
            await call.bot.send_message(admin_id, f"🛒 Yangi buyurtma #{order.id} ({user.abu_id}), "
                                                  f"{fmt(order.price_uzs)} so'm. /deliver {order.id}")
        except Exception:
            pass
    await call.answer()
