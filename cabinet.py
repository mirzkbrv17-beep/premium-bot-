from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from keyboards.admin_menu import review_kb
from keyboards.cabinet_menu import card_details_kb, topup_methods
from keyboards.main_menu import cabinet_menu
from services.admin_service import targets
from services import progress_service, topup_service
from services.balance_service import get_balance
from services.emoji_service import E
from services.settings_service import get_setting
from services.topup_service import TopupError
from services.user_service import get_or_create_user
from utils.helpers import card_pretty, e, fmt

router = Router()


class TopupStates(StatesGroup):
    amount = State()
    receipt = State()


@router.callback_query(F.data == "cabinet")
async def cabinet(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    f = await get_balance(session, user.id, "ABU_F")
    t = await get_balance(session, user.id, "ABU_TON")
    xp = await progress_service.get_xp(session, user.id)
    vip = await progress_service.vip_for(session, user.id)
    await call.message.edit_text(
        f"👤 <b>Kabinet</b>\nID: <code>{user.abu_id}</code>\n"
        f"⭐ Level: <b>{xp.level}</b> · XP: {fmt(xp.xp)}\n👑 VIP: <b>{vip.name if vip else '—'}</b>\n\n"
        f"{E('abu_f')} ABU F: <b>{fmt(f.amount)}</b>\n{E('abu_ton')} ABU TON: <b>{fmt(t.amount)}</b>",
        reply_markup=cabinet_menu())
    await call.answer()


@router.callback_query(F.data == "topup")
async def topup(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("💳 <b>Balansni to'ldirish</b>\nTo'lov usulini tanlang:", reply_markup=topup_methods())
    await call.answer()


@router.callback_query(F.data == "topup:card")
async def topup_card(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    min_amount = await get_setting(session, "abu_f_min", "5")
    rate = await get_setting(session, "abu_f_rate_uzs", "10")
    await state.set_state(TopupStates.amount)
    await call.message.edit_text(
        f"Necha ABU F sotib olmoqchisiz? Raqam yuboring (minimal: {min_amount}).\n"
        f"Kurs: 1 ABU F = {rate} so'm.")
    await call.answer()


@router.message(TopupStates.amount, F.text)
async def topup_amount(message: Message, session: AsyncSession, state: FSMContext):
    raw = message.text.replace(" ", "")
    if not raw.isdigit() or len(raw) > 9:
        await message.answer("Iltimos, faqat butun son yuboring.")
        return
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username,
                                    message.from_user.full_name)
    try:
        req = await topup_service.create_request(session, user.id, int(raw))
    except TopupError as ex:
        await message.answer(str(ex))
        return
    number = await get_setting(session, "card_number")
    holder = await get_setting(session, "card_holder")
    await state.clear()
    if not number:
        await message.answer("Karta rekvizitlari hozircha sozlanmagan. Admin bilan bog'laning.")
        return
    await message.answer(
        f"💳 <b>Karta orqali to'lov</b>\nBuyurtma: <b>#{req.id}</b>\n"
        f"To'lanadigan summa: <b>{fmt(req.amount_uzs)} so'm</b>\n\n"
        f"Karta raqami: <code>{card_pretty(number)}</code>\n"
        f"Karta egasi: <b>{e(holder)}</b>\n\n"
        "To'lovni qilgach «To'lov qildim» tugmasini bosib, chekni yuboring. "
        "Balans admin tasdig'idan keyingina to'ldiriladi.",
        reply_markup=card_details_kb(number, req.id))


@router.callback_query(F.data.startswith("topup:paid:"))
async def topup_paid(call: CallbackQuery, state: FSMContext):
    request_id = int(call.data.split(":")[2])
    await state.set_state(TopupStates.receipt)
    await state.update_data(request_id=request_id)
    await call.message.answer("🧾 To'lov chekining skrinshotini (rasm) yuboring.")
    await call.answer()


@router.message(TopupStates.receipt, F.photo)
async def topup_receipt(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username,
                                    message.from_user.full_name)
    try:
        req = await topup_service.attach_receipt(session, data["request_id"], user.id, message.photo[-1].file_id)
    except TopupError as ex:
        await message.answer(str(ex))
        await state.clear()
        return
    await state.clear()
    await message.answer("⏳ Chek qabul qilindi. Admin tekshirgach, sizga xabar keladi.")
    caption = (f"🧾 <b>Yangi to'lov so'rovi #{req.id}</b>\n"
               f"Foydalanuvchi: {e(user.full_name)} (<code>{user.abu_id}</code>)\n"
               f"Miqdor: {fmt(req.abu_f_amount)} ABU F = {fmt(req.amount_uzs)} so'm\n"
               "Chekni bank ilovangizdagi tushumga solishtirib, keyin tasdiqlang.")
    for admin_id in await targets(session, "payments"):
        try:
            await message.bot.send_photo(admin_id, req.receipt_file_id, caption=caption,
                                         reply_markup=review_kb(req.id))
        except Exception:
            pass


@router.message(TopupStates.receipt)
async def topup_receipt_wrong(message: Message):
    await message.answer("Iltimos, chekni rasm ko'rinishida yuboring.")
