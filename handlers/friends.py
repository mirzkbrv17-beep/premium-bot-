from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M, Message
from sqlalchemy.ext.asyncio import AsyncSession

from services import friends_service as fs
from services.friends_service import FriendError
from services.prefs_service import notify_user
from services.user_service import get_or_create_user
from utils.helpers import e

router = Router()


class FindState(StatesGroup):
    abu_id = State()


async def _me(session, ev):
    u = ev.from_user
    return await get_or_create_user(session, u.id, u.username, u.full_name)


@router.callback_query(F.data == "friends")
async def friends_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = M(inline_keyboard=[[B(text="🔎 ABU ID bo'yicha topish", callback_data="fr:find")],
                            [B(text="📬 So'rovlar", callback_data="fr:req"), B(text="👫 Do'stlarim", callback_data="fr:list")],
                            [B(text="🔒 Maxfiylik", callback_data="settings")],
                            [B(text="⬅️ Orqaga", callback_data="home")]])
    await call.message.edit_text("👫 <b>ABU Friends</b>", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "fr:find")
async def find_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(FindState.abu_id)
    await call.message.edit_text("Do'stingizning ABU ID sini yuboring (masalan <code>ABU-000125</code>):")
    await call.answer()


@router.message(FindState.abu_id, F.text)
async def find_result(message: Message, session: AsyncSession, state: FSMContext):
    me = await _me(session, message)
    target = await fs.find_user(session, message.text)
    await state.clear()
    if not target or target.is_banned:
        await message.answer("Bunday ABU ID topilmadi.")
        return
    c = await fs.profile_card(session, me.id, target)
    text = f"👤 <code>{c['abu_id']}</code>\n"
    if c["visible"]:
        text += (f"⭐ Level: <b>{c['level']}</b>\n👑 VIP: {e(c['vip'] or '—')}\n🏅 Yutuqlar: {c['achievements']}\n"
                 f"📅 Ro'yxatdan o'tgan: {c['joined']}")
    else:
        text += "🔒 Profil yopiq."
    rows = []
    if target.id != me.id:
        rows.append([B(text="❌ Do'stlikni bekor qilish", callback_data=f"fr:del:{target.id}")] if c["friend"]
                    else [B(text="➕ Do'stlik so'rovi", callback_data=f"fr:add:{target.abu_id}")])
    rows.append([B(text="⬅️ Orqaga", callback_data="friends")])
    await message.answer(text, reply_markup=M(inline_keyboard=rows))


@router.callback_query(F.data.regexp(r"^fr:add:ABU-\d+$"))
async def add(call: CallbackQuery, session: AsyncSession):
    me = await _me(session, call)
    try:
        status, target = await fs.send_request(session, me.id, call.data.split(":", 2)[2])
    except FriendError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("So'rov yuborildi ✅" if status == "sent" else "Endi do'stsiz 🎉", show_alert=True)
    if status == "sent":
        kb = M(inline_keyboard=[[B(text="📬 So'rovlarni ko'rish", callback_data="fr:req")]])
        try:
            if await __import__("services.prefs_service", fromlist=["x"]).should_notify(session, target.id, "orders"):
                await call.bot.send_message(target.tg_id, f"📬 <code>{me.abu_id}</code> sizga do'stlik so'rovi yubordi.", reply_markup=kb)
        except Exception:
            pass
    else:
        await notify_user(session, call.bot, target, "orders", f"🎉 <code>{me.abu_id}</code> bilan endi do'stsiz!")


@router.callback_query(F.data == "fr:req")
async def requests_list(call: CallbackQuery, session: AsyncSession):
    me = await _me(session, call)
    items = await fs.incoming(session, me.id)
    rows = []
    for f, u in items:
        rows.append([B(text=f"✅ {u.abu_id}", callback_data=f"fr:ok:{f.id}"), B(text="❌", callback_data=f"fr:no:{f.id}")])
    rows.append([B(text="⬅️ Orqaga", callback_data="friends")])
    await call.message.edit_text("📬 <b>Kelgan so'rovlar</b>" + ("" if items else "\nYo'q."), reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^fr:(ok|no):\d+$"))
async def respond(call: CallbackQuery, session: AsyncSession):
    me = await _me(session, call)
    _, action, fid = call.data.split(":")
    try:
        other = await fs.respond(session, me.id, int(fid), action == "ok")
    except FriendError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Qabul qilindi ✅" if action == "ok" else "Rad etildi")
    if action == "ok":
        await notify_user(session, call.bot, other, "orders", f"🎉 <code>{me.abu_id}</code> so'rovingizni qabul qildi!")
    await requests_list(call, session)


@router.callback_query(F.data == "fr:list")
async def friends_list(call: CallbackQuery, session: AsyncSession):
    me = await _me(session, call)
    items = await fs.friends(session, me.id)
    rows = [[B(text=f"{u.abu_id}", callback_data=f"fr:del:{u.id}")] for u in items]
    rows.append([B(text="⬅️ Orqaga", callback_data="friends")])
    await call.message.edit_text("👫 <b>Do'stlarim</b>" + (f" ({len(items)})\nBekor qilish uchun ID ni bosing." if items else "\nHali yo'q."),
                                 reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^fr:del:\d+$"))
async def delete_friend(call: CallbackQuery, session: AsyncSession):
    me = await _me(session, call)
    try:
        await fs.remove(session, me.id, int(call.data.split(":")[2]))
    except FriendError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Do'stlik bekor qilindi")
    await friends_list(call, session)
