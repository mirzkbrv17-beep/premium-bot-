from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import back_home
from services.bonus_service import AlreadyClaimed, claim_daily
from services.progress_service import award_xp, check_achievements
from utils.helpers import say, today_tashkent
from services.user_service import get_or_create_user

router = Router()


@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    try:
        streak, reward = await claim_daily(session, user.id)
    except AlreadyClaimed:
        await call.message.edit_text("🎁 Bugungi bonusni olib bo'lgansiz. Ertaga qaytib keling!",
                                     reply_markup=back_home())
    else:
        await call.message.edit_text(f"🎁 <b>Kunlik bonus</b>\n+{reward} ABU F\n🔥 Ketma-ket kun: <b>{streak}</b>",
                                     reply_markup=back_home())
        extra = await award_xp(session, user.id, "daily", f"{user.id}:{today_tashkent().isoformat()}")
        extra += await check_achievements(session, user.id)
        await say(call.bot, call.from_user.id, extra)
    await call.answer()
