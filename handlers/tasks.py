from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from sqlalchemy.ext.asyncio import AsyncSession

from models import Task
from services import task_service
from services.task_service import TaskError
from services.user_service import get_or_create_user
from utils.helpers import e, say

router = Router()


@router.callback_query(F.data == "tasks")
async def tasks(call: CallbackQuery, session: AsyncSession):
    items = await task_service.active_tasks(session)
    rows = [[B(text=f"📋 {t.title}", callback_data=f"task:{t.id}")] for t in items]
    rows.append([B(text="⬅️ Orqaga", callback_data="home")])
    await call.message.edit_text("📋 <b>Topshiriqlar</b>\n" + ("Birini tanlang:" if items else "Hozircha topshiriq yo'q."),
                                 reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^task:\d+$"))
async def task_view(call: CallbackQuery, session: AsyncSession):
    t = await session.get(Task, int(call.data.split(":")[1]))
    if not t:
        await call.answer("Topshiriq topilmadi", show_alert=True)
        return
    reward = " + ".join(x for x in (f"{t.reward_f} ABU F" if t.reward_f else "", f"{t.reward_ton} ABU TON" if t.reward_ton else "") if x)
    rows = []
    if t.kind == "channel" and t.channel:
        rows.append([B(text="📢 Kanalga o'tish", url=f"https://t.me/{t.channel.lstrip('@')}")])
    rows += [[B(text="✅ Tekshirish", callback_data=f"task:chk:{t.id}")], [B(text="⬅️ Orqaga", callback_data="tasks")]]
    await call.message.edit_text(f"📋 <b>{e(t.title)}</b>\n{e(t.description)}\n\nMukofot: <b>{reward or '—'}</b>\n"
                                 f"Takrorlanishi: {'har kuni' if t.repeat == 'daily' else 'bir marta'}",
                                 reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^task:chk:\d+$"))
async def task_check(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    try:
        extra = await task_service.complete_task(session, call.bot, user, int(call.data.split(":")[2]))
    except TaskError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("✅ Bajarildi! Mukofot berildi.", show_alert=True)
    await say(call.bot, call.from_user.id, extra)
