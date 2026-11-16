from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import back_home
from models import Achievement, User, UserAchievement, UserXP, VipLevel
from services import progress_service as pg
from services.user_service import get_or_create_user
from utils.helpers import fmt

router = Router()


@router.callback_query(F.data == "rating")
async def rating(call: CallbackQuery, session: AsyncSession):
    rows = (await session.execute(select(User.abu_id, UserXP.xp, UserXP.level).join(UserXP, UserXP.user_id == User.id)
                                  .order_by(UserXP.xp.desc()).limit(10))).all()
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    lines = [f"{medals[i]} <code>{r[0]}</code> — level {r[2]} · {fmt(r[1])} XP" for i, r in enumerate(rows)]
    await call.message.edit_text("🏆 <b>Reyting (TOP 10)</b>\n\n" + ("\n".join(lines) or "Hali ma'lumot yo'q."),
                                 reply_markup=back_home())
    await call.answer()


@router.callback_query(F.data == "vip")
async def vip(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    mine = await pg.vip_for(session, user.id)
    xp = await pg.get_xp(session, user.id)
    levels = (await session.execute(select(VipLevel).order_by(VipLevel.rank))).scalars().all()
    lines = [f"{'✅' if mine and mine.rank == v.rank else '▫️'} <b>{v.name}</b> — level {v.min_level}+ · chegirma {v.discount_percent}%"
             for v in levels]
    await call.message.edit_text(f"👑 <b>VIP darajalar</b>\nSizning levelingiz: <b>{xp.level}</b>\n\n" + "\n".join(lines) +
                                 "\n\nVIP chegirma ABU SHOP xaridlarida avtomatik qo'llanadi.", reply_markup=back_home())
    await call.answer()


@router.callback_query(F.data == "ach")
async def ach(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)
    have = {r[0] for r in await session.execute(select(UserAchievement.code).where(UserAchievement.user_id == user.id))}
    items = (await session.execute(select(Achievement))).scalars().all()
    lines = [f"{'✅' if a.code in have else '🔒'} {a.icon} <b>{a.name}</b> — {a.description} (+{a.reward_f} ABU F)" for a in items]
    await call.message.edit_text(f"🏅 <b>Yutuqlar</b> ({len(have)}/{len(items)})\n\n" + "\n".join(lines),
                                 reply_markup=back_home())
    await call.answer()
