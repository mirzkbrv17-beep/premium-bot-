from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import SupportTicket
from services.admin_service import targets
from services import support_service as sp
from services.support_service import SupportError
from services.user_service import get_or_create_user
from utils.helpers import e

router = Router()
ST = {"open": "🟡 Ochiq", "answered": "🟢 Javob berilgan", "closed": "⚪️ Yopilgan"}


class SupStates(StatesGroup):
    new = State()
    add = State()


@router.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = M(inline_keyboard=[[B(text="✍️ Yangi murojaat", callback_data="sup:new")],
                            [B(text="📂 Murojaatlarim", callback_data="sup:list")],
                            [B(text="⬅️ Orqaga", callback_data="home")]])
    await call.message.edit_text("💬 <b>Yordam markazi</b>\nSavol yoki muammoingizni yozing — admin javob beradi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "sup:new")
async def sup_new(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupStates.new)
    await call.message.edit_text("Murojaat matnini yuboring:")
    await call.answer()


@router.message(SupStates.new, F.text)
async def sup_new_text(message: Message, session: AsyncSession, state: FSMContext):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    try:
        t = await sp.create_ticket(session, user.id, message.text)
    except SupportError as ex:
        await message.answer(str(ex))
        return
    await state.clear()
    await message.answer(f"✅ Murojaat qabul qilindi: <b>{sp.tid(t.id)}</b>")
    for admin_id in await targets(session, "support"):
        try:
            await message.bot.send_message(admin_id, f"🆘 Yangi murojaat <b>{sp.tid(t.id)}</b> ({user.abu_id}):\n{e(message.text[:500])}\n\n"
                                                     f"/reply {t.id} matn")
        except Exception:
            pass


@router.callback_query(F.data == "sup:list")
async def sup_list(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    items = await sp.user_tickets(session, user.id)
    rows = [[B(text=f"{sp.tid(t.id)} · {ST[t.status]}", callback_data=f"sup:t:{t.id}")] for t in items]
    rows.append([B(text="⬅️ Orqaga", callback_data="support")])
    await call.message.edit_text("📂 <b>Murojaatlarim</b>" + ("" if items else "\nHali yo'q."), reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^sup:t:\d+$"))
async def sup_view(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    t = await session.get(SupportTicket, int(call.data.split(":")[2]))
    if not t or t.user_id != user.id:
        await call.answer("Topilmadi", show_alert=True)
        return
    msgs = await sp.messages(session, t.id)
    body = "\n\n".join(f"{'👤' if m.sender == 'user' else '🛠 Admin'}: {e(m.text)}" for m in msgs)
    rows = [] if t.status == "closed" else [[B(text="✍️ Xabar qo'shish", callback_data=f"sup:add:{t.id}")]]
    rows.append([B(text="⬅️ Orqaga", callback_data="sup:list")])
    await call.message.edit_text(f"<b>{sp.tid(t.id)}</b> · {ST[t.status]}\n\n{body}", reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^sup:add:\d+$"))
async def sup_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupStates.add)
    await state.update_data(ticket_id=int(call.data.split(":")[2]))
    await call.message.answer("Xabaringizni yuboring:")
    await call.answer()


@router.message(SupStates.add, F.text)
async def sup_add_text(message: Message, session: AsyncSession, state: FSMContext):
    d = await state.get_data()
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    try:
        t = await sp.user_message(session, d["ticket_id"], user.id, message.text)
    except SupportError as ex:
        await message.answer(str(ex))
        await state.clear()
        return
    await state.clear()
    await message.answer("✅ Yuborildi.")
    for admin_id in await targets(session, "support"):
        try:
            await message.bot.send_message(admin_id, f"💬 {sp.tid(t.id)} ({user.abu_id}): {e(message.text[:500])}\n/reply {t.id} matn")
        except Exception:
            pass
