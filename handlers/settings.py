from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from sqlalchemy.ext.asyncio import AsyncSession

from services import prefs_service as ps
from services.user_service import get_or_create_user

router = Router()


async def _render(call: CallbackQuery, session: AsyncSession):
    u = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    p = await ps.get_prefs(session, u.id)
    mark = lambda v: "✅" if v else "▫️"
    rows = [[B(text=f"{mark(getattr(p, 'notify_' + k))} {label}", callback_data=f"set:n:{k}")] for k, label in ps.KINDS.items()]
    rows.append([B(text=f"🔒 Profil: {ps.VIS_LABEL[p.profile_visibility]}", callback_data="set:vis")])
    rows.append([B(text=f"{mark(p.allow_requests)} Do'stlik so'rovlarini qabul qilish", callback_data="set:req")])
    rows.append([B(text="⬅️ Orqaga", callback_data="home")])
    await call.message.edit_text("⚙️ <b>Sozlamalar</b>\nBildirishnomalar va maxfiylik.\n"
                                 "<i>To'lov holati haqidagi muhim xabarlar doim yuboriladi.</i>\n"
                                 "Til: O'zbekcha (boshqa tillar keyin qo'shiladi)", reply_markup=M(inline_keyboard=rows))


@router.callback_query(F.data == "settings")
async def settings_page(call: CallbackQuery, session: AsyncSession):
    await _render(call, session)
    await call.answer()


@router.callback_query(F.data.regexp(r"^set:n:(referral|orders|news|daily)$"))
async def toggle_notify(call: CallbackQuery, session: AsyncSession):
    u = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    await ps.toggle(session, u.id, call.data.split(":")[2])
    await _render(call, session)
    await call.answer()


@router.callback_query(F.data == "set:vis")
async def toggle_vis(call: CallbackQuery, session: AsyncSession):
    u = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    await ps.cycle_visibility(session, u.id)
    await _render(call, session)
    await call.answer()


@router.callback_query(F.data == "set:req")
async def toggle_req(call: CallbackQuery, session: AsyncSession):
    u = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    await ps.toggle_requests(session, u.id)
    await _render(call, session)
    await call.answer()
