from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import back_home, channels_kb
from services import referral_service as rs
from services.user_service import get_or_create_user

router = Router()


@router.callback_query(F.data == "referral")
async def referral(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    me = await call.bot.me()
    s = await rs.stats(session, user.id)
    await call.message.edit_text(
        "👥 <b>Referral</b>\nHar bir haqiqiy taklif uchun: "
        f"<b>{rs.REWARD_F} ABU F</b> + <b>{rs.REWARD_TON} ABU TON</b>.\n"
        "Mukofot do'stingiz majburiy kanallarga obuna bo'lib, 2 soatdan keyin ham obunada qolsa beriladi.\n\n"
        f"Havolangiz:\n<code>https://t.me/{me.username}?start=ref_{user.id}</code>\n\n"
        f"⏳ Kutilmoqda: {s['pending']}\n✅ Mukofot berilgan: {s['rewarded']}\n❌ Bekor: {s['cancelled']}",
        reply_markup=back_home())
    await call.answer()


@router.callback_query(F.data == "ref:check")
async def check(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    res = await rs.mark_subscribed(session, user, call.bot)
    if res == "ok":
        await call.message.edit_text("✅ Obuna tasdiqlandi! Rahmat.", reply_markup=back_home())
        await call.answer()
    elif res == "not_subscribed":
        await call.answer("Hali barcha kanallarga obuna bo'lmagansiz.", show_alert=True)
    else:
        await call.answer("Tekshirib bo'lmadi, birozdan keyin urinib ko'ring.", show_alert=True)
