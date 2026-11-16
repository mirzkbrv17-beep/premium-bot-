import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin_service import allowed, targets
from models import AuditLog, MandatoryChannel, Referral, User
from sqlalchemy import delete, func
from services import promo_service, referral_service
from services.balance_service import CURRENCIES, change_balance
from services.promo_service import PromoError
from services import topup_service
from services.settings_service import set_setting
from services.topup_service import TopupError
from utils.helpers import fmt, mask_card

router = Router()



@router.message(Command("setcard"))
async def set_card(message: Message, command: CommandObject, session: AsyncSession):
    """/setcard 8600123412341234 Ism Familiya  (karta raqami loglarga yozilmaydi)"""
    if not await allowed(session, message.from_user.id, "payments"):
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) != 2 or not re.fullmatch(r"\d{16}", parts[0]):
        await message.answer("Format: /setcard 16_xonali_karta_raqami Karta_egasi")
        return
    await set_setting(session, "card_number", parts[0])
    await set_setting(session, "card_holder", parts[1].strip()[:64])
    session.add(AuditLog(actor_tg_id=message.from_user.id, action="card_changed", details=mask_card(parts[0])))
    try:
        await message.delete()  # karta raqami chatda qolmasin
    except Exception:
        pass
    await message.answer(f"✅ Karta yangilandi: {mask_card(parts[0])}")


@router.callback_query(F.data.regexp(r"^adm:(ok|no):\d+$"))
async def review(call: CallbackQuery, session: AsyncSession):
    if not await allowed(session, call.from_user.id, "payments"):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    _, action, rid = call.data.split(":")
    try:
        if action == "ok":
            req = await topup_service.approve(session, int(rid), call.from_user.id)
        else:
            req = await topup_service.reject(session, int(rid), call.from_user.id)
    except TopupError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    user = (await session.execute(select(User).where(User.id == req.user_id))).scalar_one()
    done = "✅ Tasdiqlandi" if action == "ok" else "❌ Rad etildi"
    await call.message.edit_caption(caption=f"{done} — #{req.id}, {fmt(req.abu_f_amount)} ABU F")
    if action == "ok":
        user_text = f"✅ To'lov tasdiqlandi! Balansingizga <b>{fmt(req.abu_f_amount)} ABU F</b> qo'shildi."
    else:
        user_text = f"❌ #{req.id} to'lov tasdiqlanmadi. Savol bo'lsa, yordam bo'limiga murojaat qiling."
    try:
        await call.bot.send_message(user.tg_id, user_text)
    except Exception:
        pass
    for admin_id in (await targets(session, "payments")) - {call.from_user.id}:
        try:
            await call.bot.send_message(admin_id, f"{done}: #{req.id} ({fmt(req.abu_f_amount)} ABU F)")
        except Exception:
            pass
    await call.answer("Bajarildi")


async def _audit(session, admin_id, action, details=""):
    session.add(AuditLog(actor_tg_id=admin_id, action=action, details=details[:500]))


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "stats"):
        return
    users = (await session.execute(select(func.count(User.id)))).scalar_one()
    refs = (await session.execute(select(func.count(Referral.id)).where(Referral.status == "rewarded"))).scalar_one()
    await message.answer(f"📊 Foydalanuvchilar: {fmt(users)}\nMukofotlangan referrallar: {fmt(refs)}")


@router.message(Command("channels"))
async def channels(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "channels"):
        return
    chs = await referral_service.list_channels(session)
    await message.answer("Majburiy kanallar:\n" + ("\n".join(chs) if chs else "yo'q") +
                         "\n\n/channel_add @kanal\n/channel_del @kanal\n(Bot kanalda admin bo'lishi shart)")


@router.message(Command("channel_add"))
async def channel_add(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "channels") or not command.args:
        return
    name = referral_service.norm_channel(command.args)
    if name in await referral_service.list_channels(session):
        await message.answer("Bu kanal allaqachon bor.")
        return
    session.add(MandatoryChannel(username=name))
    await _audit(session, message.from_user.id, "channel_add", name)
    await message.answer(f"✅ Qo'shildi: {name}")


@router.message(Command("channel_del"))
async def channel_del(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "channels") or not command.args:
        return
    name = referral_service.norm_channel(command.args)
    await session.execute(delete(MandatoryChannel).where(MandatoryChannel.username == name))
    await _audit(session, message.from_user.id, "channel_del", name)
    await message.answer(f"🗑 O'chirildi: {name}")


@router.message(Command("give"))
async def give(message: Message, command: CommandObject, session: AsyncSession):
    """/give ABU-000001 ABU_F 100"""
    if not await allowed(session, message.from_user.id, "balance"):
        return
    a = (command.args or "").split()
    if len(a) != 3 or a[1] not in CURRENCIES or not a[2].isdigit() or int(a[2]) <= 0:
        await message.answer("Format: /give ABU-000001 ABU_F|ABU_TON miqdor")
        return
    user = (await session.execute(select(User).where(User.abu_id == a[0].upper()))).scalar_one_or_none()
    if not user:
        await message.answer("Foydalanuvchi topilmadi.")
        return
    await change_balance(session, user.id, a[1], int(a[2]), "admin_grant", f"grant:{message.message_id}:{message.chat.id}")
    await _audit(session, message.from_user.id, "give", f"{a[0]} {a[1]} {a[2]}")
    await message.answer(f"✅ {a[0]} ga {fmt(int(a[2]))} {a[1]} berildi.")
    try:
        await message.bot.send_message(user.tg_id, f"🎁 Sizga {fmt(int(a[2]))} {a[1]} berildi.")
    except Exception:
        pass


@router.message(Command("promo_add"))
async def promo_add(message: Message, command: CommandObject, session: AsyncSession):
    """/promo_add KOD ABU_F 100 limit 50 | time 7 | unlimited"""
    if not await allowed(session, message.from_user.id, "promo"):
        return
    a = (command.args or "").split()
    try:
        if len(a) < 4 or not a[2].isdigit():
            raise PromoError("Format: /promo_add KOD ABU_F|ABU_TON miqdor limit N | time KUN | unlimited")
        value = int(a[4]) if len(a) > 4 and a[4].isdigit() else None
        p = await promo_service.create_promo(session, a[0], a[1], int(a[2]), a[3], value)
    except PromoError as ex:
        await message.answer(str(ex))
        return
    await _audit(session, message.from_user.id, "promo_add", p.code)
    await message.answer(f"✅ Promo kod yaratildi: {p.code} ({p.mode})")


@router.message(Command("promo_stop"))
async def promo_stop(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "promo") or not command.args:
        return
    try:
        p = await promo_service.set_active(session, command.args, False)
    except PromoError as ex:
        await message.answer(str(ex))
        return
    await _audit(session, message.from_user.id, "promo_stop", p.code)
    await message.answer(f"⏸ To'xtatildi: {p.code} (ishlatilgan: {p.used_count})")
