import random

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import back_home
from models import Question, QuizAnswer
from services.progress_service import award_xp
from services.user_service import get_or_create_user
from utils.helpers import e, say, today_tashkent

router = Router()

WHEEL = ["🍀 Bugun omadingiz kelsin!", "🌟 Katta g'alaba yaqin!", "🔥 Streakni uzmang!", "💎 Olmosdek porlang!",
         "🚀 Yangi imkoniyatlar kutmoqda!", "🎯 Maqsadga aniq tegasiz!"]


@router.callback_query(F.data == "games")
async def games(call: CallbackQuery):
    kb = M(inline_keyboard=[[B(text="❓ Kun savoli", callback_data="quiz")],
                            [B(text="🎡 Omad g'ildiragi", callback_data="wheel")],
                            [B(text="⬅️ Orqaga", callback_data="home")]])
    await call.message.edit_text("🎮 <b>O'yinlar</b>\nChekers va duellar Mini App bilan birga keladi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "wheel")
async def wheel(call: CallbackQuery):
    """Bepul ko'ngilochar: pul yoki balans sovrini yo'q."""
    kb = M(inline_keyboard=[[B(text="🎡 Yana aylantirish", callback_data="wheel")], [B(text="⬅️ Orqaga", callback_data="games")]])
    await call.message.edit_text(f"🎡 <b>Omad g'ildiragi</b> (bepul, sovrinsiz)\n\n{random.choice(WHEEL)}", reply_markup=kb)
    await call.answer()


async def _today_question(session: AsyncSession) -> Question | None:
    qs = (await session.execute(select(Question).where(Question.is_active.is_(True)).order_by(Question.id))).scalars().all()
    return qs[today_tashkent().toordinal() % len(qs)] if qs else None  # hamma uchun bir xil kun savoli


@router.callback_query(F.data == "quiz")
async def quiz(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    q = await _today_question(session)
    day = today_tashkent().isoformat()
    if not q:
        await call.message.edit_text("Hozircha savol yo'q.", reply_markup=back_home())
    elif (await session.execute(select(QuizAnswer.id).where(QuizAnswer.user_id == user.id, QuizAnswer.day == day))).first():
        await call.message.edit_text("Bugungi savolga javob bergansiz. Ertaga qaytib keling!", reply_markup=back_home())
    else:
        opts = q.options.split("||")
        rows = [[B(text=o, callback_data=f"quiz:a:{q.id}:{i}")] for i, o in enumerate(opts)]
        await call.message.edit_text(f"❓ <b>Kun savoli</b>\n\n{e(q.text)}", reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^quiz:a:\d+:\d$"))
async def quiz_answer(call: CallbackQuery, session: AsyncSession):
    _, _, qid, idx = call.data.split(":")
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    q = await _today_question(session)
    day = today_tashkent().isoformat()
    if not q or q.id != int(qid):
        await call.answer("Savol eskirgan", show_alert=True)
        return
    if (await session.execute(select(QuizAnswer.id).where(QuizAnswer.user_id == user.id, QuizAnswer.day == day))).first():
        await call.answer("Allaqachon javob bergansiz", show_alert=True)
        return
    ok = q.correct == int(idx)  # to'g'ri javob serverda tekshiriladi
    session.add(QuizAnswer(user_id=user.id, day=day, question_id=q.id, is_correct=ok))
    await session.flush()
    extra = await award_xp(session, user.id, "quiz", f"{user.id}:{day}") if ok else []
    await call.message.edit_text("✅ To'g'ri javob! +XP" if ok else "❌ Noto'g'ri. Ertaga yana urinib ko'ring!", reply_markup=back_home())
    await say(call.bot, call.from_user.id, extra)
    await call.answer()
