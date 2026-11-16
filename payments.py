from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Package, Payment
from services import click_service
from services.package_service import list_packages
from services.settings_service import get_setting
from services.user_service import get_or_create_user
from utils.helpers import fmt

router = Router()


class BuyStates(StatesGroup):
    amount = State()


def _pay_kb(payment: Payment) -> M:
    url = click_service.pay_url(settings.CLICK_SERVICE_ID, settings.CLICK_MERCHANT_ID, payment)
    return M(inline_keyboard=[[B(text="💳 Click orqali to'lash", url=url)], [B(text="⬅️ Orqaga", callback_data="buy")]])


@router.callback_query(F.data == "buy")
async def buy_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = M(inline_keyboard=[[B(text="🪙 ABU F", callback_data="buy:f"), B(text="💎 ABU TON", callback_data="buy:ton")],
                            [B(text="⬅️ Orqaga", callback_data="cabinet")]])
    text = "💎 <b>Valyuta sotib olish</b>\nTo'lov Click orqali. Balans to'lov tasdiqlangandan keyin avtomatik qo'shiladi."
    if not settings.click_configured:
        text += "\n\n⚠️ Click hozircha sozlanmagan (not_configured)."
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "buy:f")
async def buy_f(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not settings.click_configured:
        await call.answer("Click hozircha sozlanmagan.", show_alert=True)
        return
    mn = await get_setting(session, "abu_f_min", "5")
    rate = await get_setting(session, "abu_f_rate_uzs", "10")
    await state.set_state(BuyStates.amount)
    await call.message.edit_text(f"Necha ABU F? (minimal {mn}). Kurs: 1 ABU F = {rate} so'm.")
    await call.answer()


@router.message(BuyStates.amount, F.text)
async def buy_f_amount(message: Message, session: AsyncSession, state: FSMContext):
    raw = message.text.replace(" ", "")
    mn = int(await get_setting(session, "abu_f_min", "5"))
    rate = int(await get_setting(session, "abu_f_rate_uzs", "10"))
    if not raw.isdigit() or len(raw) > 9 or int(raw) < mn:
        await message.answer(f"Butun son yuboring (minimal {mn}).")
        return
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    pay = Payment(user_id=user.id, currency="ABU_F", grant_amount=int(raw), amount_uzs=int(raw) * rate)
    session.add(pay)
    await session.flush()
    await state.clear()
    await message.answer(f"Buyurtma #{pay.id}: <b>{fmt(pay.grant_amount)} ABU F</b> = <b>{fmt(pay.amount_uzs)} so'm</b>",
                         reply_markup=_pay_kb(pay))


@router.callback_query(F.data == "buy:ton")
async def buy_ton(call: CallbackQuery, session: AsyncSession):
    if not settings.click_configured:
        await call.answer("Click hozircha sozlanmagan.", show_alert=True)
        return
    packs = await list_packages(session, "ABU_TON")
    rows = [[B(text=f"💎 {fmt(p.amount)} ABU TON — {fmt(p.price_uzs)} so'm", callback_data=f"buy:pk:{p.id}")] for p in packs]
    rows.append([B(text="⬅️ Orqaga", callback_data="buy")])
    await call.message.edit_text("💎 <b>ABU TON paketlari</b>", reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^buy:pk:\d+$"))
async def buy_pack(call: CallbackQuery, session: AsyncSession):
    pack = await session.get(Package, int(call.data.split(":")[2]))
    if not pack or not pack.is_active:
        await call.answer("Paket topilmadi", show_alert=True)
        return
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    pay = Payment(user_id=user.id, currency=pack.currency, grant_amount=pack.amount, amount_uzs=pack.price_uzs)
    session.add(pay)
    await session.flush()
    await call.message.edit_text(f"Buyurtma #{pay.id}: <b>{fmt(pack.amount)} ABU TON</b> = <b>{fmt(pack.price_uzs)} so'm</b>",
                                 reply_markup=_pay_kb(pay))
    await call.answer()
