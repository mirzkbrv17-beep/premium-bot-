from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin_service import allowed
from models import AuditLog, Listing, MarketOrder, Question, SupportTicket, Task, User, VipLevel
from services import market_service as mk, support_service as sp
from services.market_service import MarketError
from services.settings_service import set_setting
from services.support_service import SupportError
from utils.helpers import e, fmt, say

router = Router()


def _audit(session, admin_id, action, details=""):
    session.add(AuditLog(actor_tg_id=admin_id, action=action, details=details[:500]))


def _id(command: CommandObject) -> int | None:
    a = (command.args or "").split()
    return int(a[0]) if a and a[0].isdigit() else None


# ---------- topshiriqlar ----------
@router.message(Command("task_add"))
async def task_add(message: Message, command: CommandObject, session: AsyncSession):
    """/task_add kind | Nomi | Tavsif | ABU_F | ABU_TON | once/daily | @kanal | kunlar
    kind: channel (kanalga obuna) | bonus (kunlik bonus olish) | invite (do'st taklif qilish)"""
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    p = [x.strip() for x in (command.args or "").split("|")]
    if (len(p) < 6 or p[0] not in ("channel", "bonus", "invite") or not p[3].isdigit() or not p[4].isdigit()
            or p[5] not in ("once", "daily") or (p[0] == "channel" and (len(p) < 7 or not p[6].startswith("@")))):
        await message.answer("Format: /task_add kind | Nomi | Tavsif | ABU_F | ABU_TON | once/daily | @kanal | kunlar\n"
                             "kind: channel | bonus | invite (kanal faqat channel uchun, kunlar ixtiyoriy)")
        return
    t = Task(kind=p[0], title=p[1][:128], description=p[2], reward_f=int(p[3]), reward_ton=int(p[4]), repeat=p[5],
             channel=p[6] if p[0] == "channel" else None)
    days = p[7] if len(p) > 7 else (p[6] if p[0] != "channel" and len(p) > 6 else "")
    if days.isdigit():
        t.ends_at = datetime.now(timezone.utc) + timedelta(days=int(days))
    session.add(t)
    await session.flush()
    _audit(session, message.from_user.id, "task_add", f"id={t.id}")
    await message.answer(f"✅ Topshiriq #{t.id} qo'shildi.")


@router.message(Command("task_list"))
async def task_list(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    rows = (await session.execute(select(Task).order_by(Task.id).limit(50))).scalars().all()
    await message.answer("\n".join(f"#{t.id} {'🟢' if t.is_active else '⚪️'} {t.kind} · {e(t.title)} · {t.reward_f}F/{t.reward_ton}T"
                                   for t in rows) or "Topshiriq yo'q.\n/task_off id")


@router.message(Command("task_off"))
async def task_off(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    t = await session.get(Task, _id(command)) if _id(command) else None
    if not t:
        await message.answer("Topshiriq topilmadi.")
        return
    t.is_active = False
    _audit(session, message.from_user.id, "task_off", f"id={t.id}")
    await message.answer("⏸ O'chirildi.")


# ---------- XP / VIP / viktorina ----------
@router.message(Command("setxp"))
async def setxp(message: Message, command: CommandObject, session: AsyncSession):
    """/setxp daily|task|referral|quiz|market|achievement miqdor   yoki   /setxp levelup_reward_f miqdor"""
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    a = (command.args or "").split()
    keys = {"daily", "task", "referral", "quiz", "market", "achievement"}
    if len(a) != 2 or not a[1].isdigit() or (a[0] not in keys and a[0] != "levelup_reward_f"):
        await message.answer("Format: /setxp daily|task|referral|quiz|market|achievement miqdor\n/setxp levelup_reward_f miqdor")
        return
    await set_setting(session, a[0] if a[0] == "levelup_reward_f" else f"xp_{a[0]}", a[1])
    _audit(session, message.from_user.id, "setxp", f"{a[0]}={a[1]}")
    await message.answer("✅ Saqlandi.")


@router.message(Command("vip_set"))
async def vip_set(message: Message, command: CommandObject, session: AsyncSession):
    """/vip_set rank min_level chegirma_foiz"""
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    a = (command.args or "").split()
    v = None
    if len(a) == 3 and all(x.isdigit() for x in a):
        v = (await session.execute(select(VipLevel).where(VipLevel.rank == int(a[0])))).scalar_one_or_none()
    if not v or int(a[2]) > 50:
        await message.answer("Format: /vip_set rank(1-5) min_level chegirma_foiz(0-50)")
        return
    v.min_level, v.discount_percent = int(a[1]), int(a[2])
    _audit(session, message.from_user.id, "vip_set", command.args)
    await message.answer(f"✅ {v.name}: level {v.min_level}+, chegirma {v.discount_percent}%")


@router.message(Command("quiz_add"))
async def quiz_add(message: Message, command: CommandObject, session: AsyncSession):
    """/quiz_add Savol | A | B | C | D | to'g'ri(1-4)"""
    if not await allowed(session, message.from_user.id, "tasks"):
        return
    p = [x.strip() for x in (command.args or "").split("|")]
    if len(p) != 6 or p[5] not in ("1", "2", "3", "4") or not all(p[:5]):
        await message.answer("Format: /quiz_add Savol | A | B | C | D | to'g'ri_javob(1-4)")
        return
    q = Question(text=p[0][:300], options="||".join(p[1:5]), correct=int(p[5]) - 1)
    session.add(q)
    await session.flush()
    await message.answer(f"✅ Savol #{q.id} qo'shildi.")


# ---------- market moderatsiyasi ----------
@router.message(Command("market_pending"))
async def market_pending(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "market"):
        return
    rows = (await session.execute(select(Listing).where(Listing.status == "pending").order_by(Listing.id).limit(20))).scalars().all()
    await message.answer("\n".join(f"#{li.id} {e(li.title)} — {fmt(li.price_abu_f)} ABU F" for li in rows)
                         + "\n\n/market_ok id · /market_no id" if rows else "Kutayotgan e'lon yo'q.")


async def _moderate(message, command, session, status, label):
    if not await allowed(session, message.from_user.id, "market"):
        return
    lid = _id(command)
    try:
        li = await mk.moderate(session, lid, status) if lid else None
        if not li:
            raise MarketError("E'lon topilmadi")
    except MarketError as ex:
        await message.answer(str(ex))
        return
    _audit(session, message.from_user.id, f"market_{status}", f"listing={li.id}")
    seller = await session.get(User, li.seller_id)
    await message.answer(f"✅ #{li.id}: {label}")
    await say(message.bot, seller.tg_id, [f"E'loningiz «{e(li.title)}»: {label}"])


@router.message(Command("market_ok"))
async def market_ok(message: Message, command: CommandObject, session: AsyncSession):
    await _moderate(message, command, session, "approved", "tasdiqlandi ✅")


@router.message(Command("market_no"))
async def market_no(message: Message, command: CommandObject, session: AsyncSession):
    await _moderate(message, command, session, "rejected", "rad etildi ❌")


@router.message(Command("market_hide"))
async def market_hide(message: Message, command: CommandObject, session: AsyncSession):
    await _moderate(message, command, session, "hidden", "yashirildi")


@router.message(Command("disputes"))
async def disputes(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "market"):
        return
    rows = (await session.execute(select(MarketOrder).where(MarketOrder.status == "disputed").order_by(MarketOrder.id))).scalars().all()
    await message.answer("\n".join(f"#{o.id} {fmt(o.price_abu_f)} ABU F" for o in rows) + "\n\n/market_release id · /market_refund id"
                         if rows else "Nizo yo'q.")


async def _resolve(message, command, session, release: bool):
    if not await allowed(session, message.from_user.id, "market"):
        return
    oid = _id(command)
    try:
        if not oid:
            raise MarketError("Buyurtma topilmadi")
        o = await (mk.admin_release if release else mk.admin_refund)(session, oid)
    except MarketError as ex:
        await message.answer(str(ex))
        return
    _audit(session, message.from_user.id, "market_release" if release else "market_refund", f"order={o.id}")
    buyer, seller = await session.get(User, o.buyer_id), await session.get(User, o.seller_id)
    await message.answer(f"✅ #{o.id}: {'sotuvchiga to`landi' if release else 'xaridorga qaytarildi'}")
    text = f"⚖️ Buyurtma #{o.id} bo'yicha admin qarori: " + ("pul sotuvchiga o'tdi." if release else "pul xaridorga qaytarildi.")
    await say(message.bot, buyer.tg_id, [text])
    await say(message.bot, seller.tg_id, [text])


@router.message(Command("market_release"))
async def market_release(message: Message, command: CommandObject, session: AsyncSession):
    await _resolve(message, command, session, True)


@router.message(Command("market_refund"))
async def market_refund(message: Message, command: CommandObject, session: AsyncSession):
    await _resolve(message, command, session, False)


# ---------- support ----------
@router.message(Command("tickets"))
async def tickets(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "support"):
        return
    rows = (await session.execute(select(SupportTicket).where(SupportTicket.status == "open").order_by(SupportTicket.id).limit(20))).scalars().all()
    await message.answer("\n".join(f"{sp.tid(t.id)}: {e(t.subject)}" for t in rows) + "\n\n/reply id matn · /close_ticket id"
                         if rows else "Ochiq murojaat yo'q.")


@router.message(Command("reply"))
async def reply(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "support"):
        return
    a = (command.args or "").split(maxsplit=1)
    if len(a) != 2 or not a[0].isdigit():
        await message.answer("Format: /reply ticket_id matn")
        return
    try:
        t, user = await sp.admin_reply(session, int(a[0]), a[1])
    except SupportError as ex:
        await message.answer(str(ex))
        return
    _audit(session, message.from_user.id, "ticket_reply", f"id={t.id}")
    await message.answer("✅ Yuborildi.")
    await say(message.bot, user.tg_id, [f"🛠 <b>{sp.tid(t.id)}</b> bo'yicha javob:\n{e(a[1])}"])


@router.message(Command("close_ticket"))
async def close_ticket(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "support"):
        return
    try:
        t, user = await sp.close_ticket(session, _id(command) or 0)
    except SupportError as ex:
        await message.answer(str(ex))
        return
    _audit(session, message.from_user.id, "ticket_close", f"id={t.id}")
    await message.answer("✅ Yopildi.")
    await say(message.bot, user.tg_id, [f"✅ {sp.tid(t.id)} yopildi."])
