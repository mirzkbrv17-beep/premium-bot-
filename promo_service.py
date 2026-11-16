from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import PromoCode, PromoRedemption
from services.balance_service import CURRENCIES, change_balance


class PromoError(Exception):
    pass


async def create_promo(session: AsyncSession, code: str, currency: str, amount: int,
                       mode: str, value: int | None = None) -> PromoCode:
    code = code.strip().upper()
    if currency not in CURRENCIES or amount <= 0:
        raise PromoError("Valyuta yoki miqdor noto'g'ri")
    if mode not in ("limit", "time", "unlimited"):
        raise PromoError("Rejim: limit | time | unlimited")
    if mode in ("limit", "time") and (value is None or value <= 0):
        raise PromoError("Son (limit) yoki kun (time) ko'rsatilishi kerak")
    p = PromoCode(code=code, currency=currency, amount=amount, mode=mode)
    if mode == "limit":
        p.max_uses = value  # muddat so'ralmaydi
    elif mode == "time":
        p.expires_at = datetime.now(timezone.utc) + timedelta(days=value)  # son cheklovi yo'q
    session.add(p)
    try:
        await session.flush()
    except IntegrityError:
        raise PromoError("Bunday kod allaqachon mavjud")
    return p


async def set_active(session: AsyncSession, code: str, active: bool) -> PromoCode:
    p = (await session.execute(select(PromoCode).where(PromoCode.code == code.strip().upper()))).scalar_one_or_none()
    if not p:
        raise PromoError("Kod topilmadi")
    p.is_active = active
    await session.flush()
    return p


async def redeem(session: AsyncSession, user_id: int, code: str) -> PromoCode:
    p = (await session.execute(
        select(PromoCode).where(PromoCode.code == code.strip().upper()).with_for_update())).scalar_one_or_none()
    if not p or not p.is_active:
        raise PromoError("Promo kod topilmadi yoki to'xtatilgan")
    if p.expires_at is not None:
        exp = p.expires_at if p.expires_at.tzinfo else p.expires_at.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            raise PromoError("Promo kod muddati tugagan")
    if p.mode == "limit" and p.used_count >= (p.max_uses or 0):
        raise PromoError("Promo kod limiti tugagan")
    used = (await session.execute(select(PromoRedemption.id).where(
        PromoRedemption.promo_id == p.id, PromoRedemption.user_id == user_id))).first()
    if used:
        raise PromoError("Siz bu kodni allaqachon ishlatgansiz")
    session.add(PromoRedemption(promo_id=p.id, user_id=user_id))
    p.used_count += 1
    await change_balance(session, user_id, p.currency, p.amount, "promo", f"promo:{p.id}:{user_id}")
    return p
