import asyncio

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models import AuditLog, User, UserPrefs
from services import admin_service as adm, emoji_service
from services.admin_service import PERMS, AdminError, allowed, is_super
from utils.emoji_config import FALLBACK, LABELS
from utils.helpers import e

router = Router()


# ---------- adminlar va ruxsatlar (faqat superadmin) ----------
@router.message(Command("admins"))
async def admins(message: Message, session: AsyncSession):
    if not is_super(message.from_user.id):
        return
    rows = await adm.list_admins(session)
    lines = [f"<code>{tg}</code>: {', '.join(p) or 'ruxsat yo`q'}" for tg, p in rows]
    await message.answer("👮 <b>Adminlar</b>\n" + ("\n".join(lines) or "Qo'shilgan admin yo'q.") +
                         "\n\n/admin_add tg_id · /admin_del tg_id · /admin_perm tg_id ruxsat on|off\n"
                         "Ruxsatlar: " + ", ".join(PERMS) + ", all")


@router.message(Command("admin_add"))
async def admin_add(message: Message, command: CommandObject, session: AsyncSession):
    if not is_super(message.from_user.id):
        return
    arg = (command.args or "").strip()
    try:
        if not arg.isdigit():
            raise AdminError("Format: /admin_add telegram_id")
        await adm.add_admin(session, int(arg), message.from_user.id)
    except AdminError as ex:
        await message.answer(str(ex))
        return
    await message.answer("✅ Admin qo'shildi. Ruxsat berish: /admin_perm " + arg + " all on")


@router.message(Command("admin_del"))
async def admin_del(message: Message, command: CommandObject, session: AsyncSession):
    if not is_super(message.from_user.id):
        return
    try:
        await adm.remove_admin(session, int((command.args or "0").strip() or 0), message.from_user.id)
    except (AdminError, ValueError) as ex:
        await message.answer(str(ex) or "Format: /admin_del telegram_id")
        return
    await message.answer("🗑 Admin o'chirildi.")


@router.message(Command("admin_perm"))
async def admin_perm(message: Message, command: CommandObject, session: AsyncSession):
    if not is_super(message.from_user.id):
        return
    a = (command.args or "").split()
    try:
        if len(a) != 3 or not a[0].isdigit() or a[2] not in ("on", "off"):
            raise AdminError("Format: /admin_perm tg_id ruxsat on|off")
        await adm.set_perm(session, int(a[0]), a[1], a[2] == "on", message.from_user.id)
    except AdminError as ex:
        await message.answer(str(ex))
        return
    await message.answer("✅ Saqlandi.")


@router.message(Command("logs"))
async def logs(message: Message, session: AsyncSession):
    if not is_super(message.from_user.id):
        return
    rows = (await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(25))).scalars().all()
    await message.answer("📜 <b>Audit jurnali</b>\n" + "\n".join(
        f"{r.created_at:%m-%d %H:%M} <code>{r.actor_tg_id}</code> {e(r.action)} {e(r.details)}" for r in rows) if rows else "Bo'sh.")


# ---------- premium emoji ----------
@router.message(Command("emoji_list"))
async def emoji_list(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    lines = [f"{'✅' if k in emoji_service.CACHE else '▫️'} <code>{k}</code> {FALLBACK[k]} — {LABELS[k]}" for k in FALLBACK]
    await message.answer("🎨 <b>Premium emoji</b> (holat: " + ("yoqilgan" if emoji_service.STATE["enabled"] else "o'chirilgan") + ")\n" +
                         "\n".join(lines) + "\n\n1) /emoji_pack paket_nomi — ID larni ko'rish\n"
                         "2) /emoji_set kalit ID  yoki  /emoji_set kalit 🪙(premium emoji)\n"
                         "/emoji_clear kalit · /emoji on|off · /emoji_test\n"
                         "<i>Eslatma: bot egasida Telegram Premium bo'lishi yoki bot Fragment'da qo'shimcha username sotib olgan bo'lishi kerak.</i>")


@router.message(Command("emoji_pack"))
async def emoji_pack(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    name = (command.args or "").strip().rsplit("/", 1)[-1]
    if not name:
        await message.answer("Format: /emoji_pack paket_nomi (t.me/addemoji/<paket_nomi>)")
        return
    try:
        st = await message.bot.get_sticker_set(name)
    except TelegramAPIError:
        await message.answer("Paket topilmadi.")
        return
    items = [s for s in getattr(st, "stickers", None) or [] if s.custom_emoji_id]
    if not items:
        await message.answer("Bu paket custom emoji paketi emas.")
        return
    lines = [f"{i}. {s.emoji} <code>{s.custom_emoji_id}</code>" for i, s in enumerate(items, 1)]
    for i in range(0, len(lines), 40):
        await message.answer("\n".join(lines[i:i + 40]))
    await message.answer("Tanlaganingizni o'rnating: /emoji_set kalit ID")


@router.message(Command("emoji_set"))
async def emoji_set(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    parts = (command.args or "").split(maxsplit=1)
    key = parts[0] if parts else ""
    if key not in FALLBACK or len(parts) < 2:
        await message.answer("Format: /emoji_set kalit ID (yoki premium emoji). Kalitlar: " + ", ".join(FALLBACK))
        return
    cid = next((en.custom_emoji_id for en in (message.entities or []) if en.type == "custom_emoji" and en.custom_emoji_id), None)
    if not cid:
        cid = parts[1].strip()
    if not cid.isdigit():
        await message.answer("ID raqamlardan iborat bo'lishi kerak, yoki premium emoji yuboring.")
        return
    try:  # ID haqiqiyligini Telegram'dan tekshiramiz
        found = await message.bot.get_custom_emoji_stickers([cid])
        valid = isinstance(found, list) and len(found) > 0
    except TelegramAPIError:
        valid = False
    if not valid:
        await message.answer("❌ Bu ID Telegram'da topilmadi. Rasmiy emoji paketidan oling (/emoji_pack).")
        return
    await emoji_service.set_emoji(session, key, cid)
    session.add(AuditLog(actor_tg_id=message.from_user.id, action="emoji_set", details=f"{key}={cid}"))
    await message.answer(f"✅ {key} o'rnatildi. Tekshirish: /emoji_test")


@router.message(Command("emoji_clear"))
async def emoji_clear(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    key = (command.args or "").strip()
    if key not in FALLBACK:
        await message.answer("Kalit noto'g'ri.")
        return
    await emoji_service.clear_emoji(session, key)
    await message.answer("🗑 O'chirildi (oddiy emoji ishlatiladi).")


@router.message(Command("emoji"))
async def emoji_toggle(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    arg = (command.args or "").strip()
    if arg not in ("on", "off"):
        await message.answer("Format: /emoji on|off")
        return
    await emoji_service.set_enabled(session, arg == "on")
    await message.answer("✅ Premium emoji " + ("yoqildi." if arg == "on" else "o'chirildi."))


@router.message(Command("emoji_test"))
async def emoji_test(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "emoji"):
        return
    await message.answer("\n".join(f"{emoji_service.E(k)} {LABELS[k]}" for k in FALLBACK))


# ---------- ommaviy xabar ----------
@router.message(Command("broadcast"))
async def broadcast(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "broadcast"):
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer("Format: /broadcast xabar matni")
        return
    rows = (await session.execute(select(User.tg_id, UserPrefs.notify_news).outerjoin(UserPrefs, UserPrefs.user_id == User.id)
                                  .where(User.is_banned.is_(False)))).all()
    ids = [tg for tg, news in rows if news is None or news]  # yangiliklarni o'chirganlarga yuborilmaydi
    session.add(AuditLog(actor_tg_id=message.from_user.id, action="broadcast", details=f"n={len(ids)}"))
    await message.answer(f"📢 {len(ids)} ta foydalanuvchiga yuborish boshlandi...")
    asyncio.create_task(_send_all(message.bot, message.from_user.id, ids, f"📢 {e(text)}"))


async def _send_all(bot, admin_id: int, ids: list[int], text: str) -> None:
    ok = 0
    for tg in ids:
        try:
            await bot.send_message(tg, text)
            ok += 1
        except TelegramAPIError:
            pass
        await asyncio.sleep(0.05)  # Telegram limiti (~30 xabar/soniya) dan past
    try:
        await bot.send_message(admin_id, f"✅ Yuborildi: {ok}/{len(ids)}")
    except TelegramAPIError:
        pass
