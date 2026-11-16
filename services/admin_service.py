from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Admin, AdminPermission, AuditLog

PERMS = {
    "payments": "To'lovlar (karta, chek tasdiqlash)", "shop": "Do'kon, paketlar, buyurtmalar",
    "market": "Market moderatsiyasi va nizolar", "support": "Yordam markazi", "promo": "Promo kodlar",
    "tasks": "Topshiriq, XP, VIP, viktorina", "balance": "Foydalanuvchiga valyuta berish",
    "stats": "Statistika", "channels": "Majburiy kanallar", "broadcast": "Xabar tarqatish", "emoji": "Emoji sozlamalari",
}


class AdminError(Exception):
    pass


def is_super(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


async def _admin(session: AsyncSession, tg_id: int) -> Admin | None:
    return (await session.execute(select(Admin).where(Admin.tg_id == tg_id))).scalar_one_or_none()


async def allowed(session: AsyncSession, tg_id: int, perm: str) -> bool:
    """Superadmin (ADMIN_IDS) hamma narsaga ruxsatli; qolgan adminlar faqat berilgan ruxsatlarga."""
    if is_super(tg_id):
        return True
    adm = await _admin(session, tg_id)
    if not adm:
        return False
    return (await session.execute(select(AdminPermission.id).where(
        AdminPermission.admin_id == adm.id, AdminPermission.perm == perm))).first() is not None


async def targets(session: AsyncSession, perm: str) -> set[int]:
    """Xabar yuboriladigan adminlar: superadminlar + shu ruxsati bor adminlar."""
    ids = set(settings.admin_ids)
    rows = await session.execute(select(Admin.tg_id).join(AdminPermission, AdminPermission.admin_id == Admin.id)
                                 .where(AdminPermission.perm == perm))
    return ids | {r[0] for r in rows}


async def add_admin(session: AsyncSession, tg_id: int, by: int) -> Admin:
    if is_super(tg_id):
        raise AdminError("Bu foydalanuvchi allaqachon superadmin")
    if await _admin(session, tg_id):
        raise AdminError("Admin allaqachon qo'shilgan")
    adm = Admin(tg_id=tg_id, added_by=by)
    session.add(adm)
    await session.flush()
    session.add(AuditLog(actor_tg_id=by, action="admin_add", details=str(tg_id)))
    return adm


async def remove_admin(session: AsyncSession, tg_id: int, by: int) -> None:
    adm = await _admin(session, tg_id)
    if not adm:
        raise AdminError("Admin topilmadi")
    for p in (await session.execute(select(AdminPermission).where(AdminPermission.admin_id == adm.id))).scalars():
        await session.delete(p)
    await session.delete(adm)
    session.add(AuditLog(actor_tg_id=by, action="admin_del", details=str(tg_id)))
    await session.flush()


async def set_perm(session: AsyncSession, tg_id: int, perm: str, on: bool, by: int) -> None:
    adm = await _admin(session, tg_id)
    if not adm:
        raise AdminError("Avval /admin_add bilan qo'shing")
    names = list(PERMS) if perm == "all" else [perm]
    if any(n not in PERMS for n in names):
        raise AdminError("Noma'lum ruxsat. Ro'yxat: " + ", ".join(PERMS))
    for n in names:
        row = (await session.execute(select(AdminPermission).where(
            AdminPermission.admin_id == adm.id, AdminPermission.perm == n))).scalar_one_or_none()
        if on and not row:
            session.add(AdminPermission(admin_id=adm.id, perm=n))
        elif not on and row:
            await session.delete(row)
    session.add(AuditLog(actor_tg_id=by, action="admin_perm", details=f"{tg_id} {perm} {'on' if on else 'off'}"))
    await session.flush()


async def list_admins(session: AsyncSession) -> list[tuple[int, list[str]]]:
    out = []
    for adm in (await session.execute(select(Admin).order_by(Admin.id))).scalars():
        perms = [r[0] for r in await session.execute(select(AdminPermission.perm).where(AdminPermission.admin_id == adm.id))]
        out.append((adm.tg_id, sorted(perms)))
    return out
