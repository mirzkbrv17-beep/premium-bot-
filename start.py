from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import channels_kb, main_menu
from services import referral_service
from services.user_service import get_or_create_user_ex
from services.emoji_service import E
from utils.helpers import e

router = Router()


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext):
    await state.clear()
    user, created = await get_or_create_user_ex(session, message.from_user.id, message.from_user.username,
                                                message.from_user.full_name)
    ref = await referral_service.register_referral(session, user, command.args) if created else None
    await message.answer(f"{E('home')} <b>ABU BOT</b> ga xush kelibsiz, {e(user.full_name)}!\n"
                         f"Sizning ID: <code>{user.abu_id}</code>", reply_markup=main_menu())
    if ref:
        channels = await referral_service.list_channels(session)
        if channels:
            await message.answer("Do'stingizning taklifi hisobga olinishi uchun quyidagi kanallarga obuna bo'ling "
                                 "va «Tekshirish» tugmasini bosing:", reply_markup=channels_kb(channels))


@router.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("✨ <b>ABU BOT</b> — asosiy menyu", reply_markup=main_menu())
    await call.answer()
