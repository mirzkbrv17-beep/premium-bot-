from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin_service import allowed
from services.prefs_service import notify_user
from models import AuditLog, Order, Package, Product, User
from services.balance_service import CURRENCIES
from utils.helpers import e, fmt

router = Router()


def _audit(session, admin_id, action, details=""):
    session.add(AuditLog(actor_tg_id=admin_id, action=action, details=details[:500]))


@router.message(Command("product_add"))
async def product_add(message: Message, command: CommandObject, session: AsyncSession):
    """/product_add Nomi | Kategoriya | narx_uzs | ombor (son yoki -) | Tavsif"""
    if not await allowed(session, message.from_user.id, "shop"):
        return
    parts = [x.strip() for x in (command.args or "").split("|")]
    if len(parts) < 4 or not parts[2].isdigit() or not (parts[3].isdigit() or parts[3] == "-"):
        await message.answer("Format: /product_add Nomi | Kategoriya | narx_uzs | ombor (son yoki -) | Tavsif")
        return
    p = Product(name=parts[0][:128], category=parts[1][:64], price_uzs=int(parts[2]),
                stock=None if parts[3] == "-" else int(parts[3]), description=(parts[4] if len(parts) > 4 else ""))
    session.add(p)
    await session.flush()
    _audit(session, message.from_user.id, "product_add", f"id={p.id}")
    await message.answer(f"✅ Mahsulot #{p.id} qo'shildi.")


@router.message(Command("product_list"))
async def product_list(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    rows = (await session.execute(select(Product).order_by(Product.id).limit(60))).scalars().all()
    lines = [f"#{p.id} {'🟢' if p.is_active else '⚪️'} {e(p.name)} | {e(p.category)} | {fmt(p.price_uzs)} so'm | "
             f"ombor: {'∞' if p.stock is None else p.stock} | −{p.discount_percent}%" for p in rows]
    await message.answer("\n".join(lines) or "Mahsulot yo'q.\n/product_off id, /product_on id, "
                         "/product_stock id son, /product_discount id foiz")


async def _product_edit(message, command, session, action):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    a = (command.args or "").split()
    p = await session.get(Product, int(a[0])) if a and a[0].isdigit() else None
    if not p:
        await message.answer("Mahsulot topilmadi.")
        return
    try:
        if action == "off":
            p.is_active = False
        elif action == "on":
            p.is_active = True
        elif action == "stock":
            p.stock = int(a[1])
        elif action == "discount":
            if not 0 <= int(a[1]) <= 90:
                raise ValueError
            p.discount_percent = int(a[1])
    except (IndexError, ValueError):
        await message.answer("Qiymat noto'g'ri.")
        return
    _audit(session, message.from_user.id, f"product_{action}", f"id={p.id}")
    await message.answer(f"✅ #{p.id} yangilandi.")


@router.message(Command("product_off"))
async def product_off(message: Message, command: CommandObject, session: AsyncSession):
    await _product_edit(message, command, session, "off")


@router.message(Command("product_on"))
async def product_on(message: Message, command: CommandObject, session: AsyncSession):
    await _product_edit(message, command, session, "on")


@router.message(Command("product_stock"))
async def product_stock(message: Message, command: CommandObject, session: AsyncSession):
    await _product_edit(message, command, session, "stock")


@router.message(Command("product_discount"))
async def product_discount(message: Message, command: CommandObject, session: AsyncSession):
    await _product_edit(message, command, session, "discount")


@router.message(Command("pack_add"))
async def pack_add(message: Message, command: CommandObject, session: AsyncSession):
    """/pack_add ABU_TON 200 50000"""
    if not await allowed(session, message.from_user.id, "shop"):
        return
    a = (command.args or "").split()
    if len(a) != 3 or a[0] not in CURRENCIES or not a[1].isdigit() or not a[2].isdigit():
        await message.answer("Format: /pack_add ABU_TON 200 50000")
        return
    p = Package(currency=a[0], amount=int(a[1]), price_uzs=int(a[2]))
    session.add(p)
    await session.flush()
    _audit(session, message.from_user.id, "pack_add", f"id={p.id}")
    await message.answer(f"✅ Paket #{p.id} qo'shildi.")


@router.message(Command("pack_list"))
async def pack_list(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    rows = (await session.execute(select(Package).order_by(Package.id))).scalars().all()
    await message.answer("\n".join(f"#{p.id} {'🟢' if p.is_active else '⚪️'} {fmt(p.amount)} {p.currency} = "
                                   f"{fmt(p.price_uzs)} so'm" for p in rows) + "\n\n/pack_del id")


@router.message(Command("pack_del"))
async def pack_del(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    p = await session.get(Package, int(command.args)) if command.args and command.args.strip().isdigit() else None
    if not p:
        await message.answer("Paket topilmadi.")
        return
    p.is_active = False
    _audit(session, message.from_user.id, "pack_del", f"id={p.id}")
    await message.answer(f"🗑 Paket #{p.id} o'chirildi.")


@router.message(Command("orders"))
async def orders(message: Message, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    rows = (await session.execute(select(Order).where(Order.status == "paid").order_by(Order.id).limit(30))).scalars().all()
    await message.answer("\n".join(f"#{o.id} user={o.user_id} product={o.product_id} {fmt(o.price_uzs)} so'm"
                                   for o in rows) + "\n\n/deliver id" if rows else "Topshirilmagan buyurtma yo'q.")


@router.message(Command("deliver"))
async def deliver(message: Message, command: CommandObject, session: AsyncSession):
    if not await allowed(session, message.from_user.id, "shop"):
        return
    o = await session.get(Order, int(command.args)) if command.args and command.args.strip().isdigit() else None
    if not o or o.status != "paid":
        await message.answer("Buyurtma topilmadi yoki allaqachon topshirilgan.")
        return
    o.status = "delivered"
    _audit(session, message.from_user.id, "order_deliver", f"id={o.id}")
    user = await session.get(User, o.user_id)
    await message.answer(f"✅ #{o.id} topshirildi.")
    await notify_user(session, message.bot, user, "orders", f"📦 Buyurtma #{o.id} topshirildi. Rahmat!")
