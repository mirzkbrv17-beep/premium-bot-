from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M, Message
from sqlalchemy.ext.asyncio import AsyncSession

from services import progress_service
from services.transfer_service import TransferError, transfer
from services.user_service import get_or_create_user
from utils.helpers import e, fmt

router = Router()
CUR = {"ABU_F": "🪙 ABU F", "ABU_TON": "💎 ABU TON"}


class TrStates(StatesGroup):
    receiver = State()
    amount = State()


@router.callback_query(F.data == "transfer")
async def tr_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = M(inline_keyboard=[[B(text=CUR["ABU_F"], callback_data="tr:cur:ABU_F"),
                             B(text=CUR["ABU_TON"], callback_data="tr:cur:ABU_TON")],
                            [B(text="⬅️ Orqaga", callback_data="cabinet")]])
    await call.message.edit_text("🔁 <b>Transfer</b>\nQaysi valyutani yubormoqchisiz?", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^tr:cur:(ABU_F|ABU_TON)$"))
async def tr_cur(call: CallbackQuery, state: FSMContext):
    await state.update_data(currency=call.data.split(":")[2])
    await state.set_state(TrStates.receiver)
    await call.message.edit_text("Qabul qiluvchining ABU ID sini yuboring (masalan <code>ABU-000125</code>):")
    await call.answer()


@router.message(TrStates.receiver, F.text)
async def tr_receiver(message: Message, state: FSMContext):
    await state.update_data(receiver=message.text.strip().upper())
    await state.set_state(TrStates.amount)
    await message.answer("Miqdorni yuboring (butun son):")


@router.message(TrStates.amount, F.text)
async def tr_amount(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0 or len(raw) > 12:
        await message.answer("Iltimos, musbat butun son yuboring.")
        return
    await state.update_data(amount=int(raw))
    d = await state.get_data()
    kb = M(inline_keyboard=[[B(text="✅ Tasdiqlash", callback_data="tr:ok"), B(text="❌ Bekor", callback_data="cabinet")]])
    await message.answer(f"Tasdiqlang:\nKimga: <code>{e(d['receiver'])}</code>\n"
                         f"Miqdor: <b>{fmt(d['amount'])}</b> {CUR[d['currency']]}", reply_markup=kb)


@router.callback_query(F.data == "tr:ok")
async def tr_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    if not d.get("amount"):
        await call.answer("Sessiya tugagan, qaytadan boshlang.", show_alert=True)
        return
    sender = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    try:
        tr, receiver = await transfer(session, sender.id, d["receiver"], d["currency"], d["amount"])
    except TransferError as ex:
        await call.message.edit_text(f"❌ {ex}")
        await call.answer()
        return
    from utils.helpers import say
    await say(call.bot, call.from_user.id, await progress_service.check_achievements(session, sender.id))
    await call.message.edit_text(f"✅ Yuborildi: {fmt(tr.amount)} {CUR[tr.currency]} → <code>{receiver.abu_id}</code>")
    try:
        await call.bot.send_message(receiver.tg_id, f"📥 Sizga <b>{fmt(tr.amount)}</b> {CUR[tr.currency]} keldi "
                                                    f"(kimdan: <code>{sender.abu_id}</code>).")
    except Exception:
        pass
    await call.answer()
