"""CLICK SHOP-API (prepare/complete). Imzo: MD5, rasmiy hujjat docs.click.uz bo'yicha.

prepare : md5(click_trans_id + service_id + SECRET + merchant_trans_id + amount + action + sign_time)
complete: md5(click_trans_id + service_id + SECRET + merchant_trans_id + merchant_prepare_id + amount + action + sign_time)
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Payment, PaymentEvent
from services.balance_service import change_balance

OK, E_SIGN, E_AMOUNT, E_ACTION, E_PAID, E_NOT_FOUND, E_TRANS, E_UPDATE, E_REQUEST, E_CANCELLED = \
    0, -1, -2, -3, -4, -5, -6, -7, -8, -9

PREPARE_FIELDS = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]


def make_sign(p: dict, secret: str, with_prepare: bool) -> str:
    parts = [p["click_trans_id"], p["service_id"], secret, p["merchant_trans_id"]]
    if with_prepare:
        parts.append(p["merchant_prepare_id"])
    parts += [p["amount"], p["action"], p["sign_time"]]
    return hashlib.md5("".join(parts).encode()).hexdigest()


def pay_url(service_id: str, merchant_id: str, payment: Payment) -> str:
    return (f"https://my.click.uz/services/pay?service_id={service_id}&merchant_id={merchant_id}"
            f"&amount={payment.amount_uzs}&transaction_param={payment.id}")


def _resp(p: dict, error: int, note: str, **extra) -> dict:
    d = {"click_trans_id": p.get("click_trans_id"), "merchant_trans_id": p.get("merchant_trans_id"),
         "error": error, "error_note": note}
    d.update(extra)
    return d


async def _log(session: AsyncSession, p: dict, event: str, payment_id: int | None, error: int):
    safe = {k: v for k, v in p.items() if k != "sign_string"}
    session.add(PaymentEvent(payment_id=payment_id, provider="click", event=event,
                             result_error=error, payload=json.dumps(safe)[:2000]))


async def _load(session: AsyncSession, raw_id: str | None) -> Payment | None:
    if not raw_id or not str(raw_id).isdigit():
        return None
    return (await session.execute(select(Payment).where(Payment.id == int(raw_id)).with_for_update())).scalar_one_or_none()


def _amount_ok(p: dict, payment: Payment) -> bool:
    try:
        return Decimal(p["amount"]) == Decimal(payment.amount_uzs)
    except (InvalidOperation, KeyError):
        return False


async def handle_prepare(session: AsyncSession, p: dict, secret: str, service_id: str) -> dict:
    if not all(p.get(k) for k in PREPARE_FIELDS) or p["service_id"] != str(service_id):
        return _resp(p, E_REQUEST, "Error in request from click")
    if not hmac.compare_digest(make_sign(p, secret, False), p["sign_string"].lower()):
        await _log(session, p, "prepare", None, E_SIGN)
        return _resp(p, E_SIGN, "SIGN CHECK FAILED!")
    if p["action"] != "0":
        return _resp(p, E_ACTION, "Action not found")
    pay = await _load(session, p["merchant_trans_id"])
    if not pay:
        await _log(session, p, "prepare", None, E_NOT_FOUND)
        return _resp(p, E_NOT_FOUND, "User does not exist", merchant_prepare_id=None)
    if not _amount_ok(p, pay):
        await _log(session, p, "prepare", pay.id, E_AMOUNT)
        return _resp(p, E_AMOUNT, "Incorrect parameter amount", merchant_prepare_id=pay.id)
    if pay.status == "paid":
        return _resp(p, E_PAID, "Already paid", merchant_prepare_id=pay.id)
    if pay.status == "cancelled":
        return _resp(p, E_CANCELLED, "Transaction cancelled", merchant_prepare_id=pay.id)
    pay.status, pay.click_trans_id = "prepared", p["click_trans_id"]
    await _log(session, p, "prepare", pay.id, OK)
    return _resp(p, OK, "Success", merchant_prepare_id=pay.id)


async def handle_complete(session: AsyncSession, p: dict, secret: str,
                          service_id: str) -> tuple[dict, Payment | None]:
    """(javob, Payment) — Payment faqat YANGI muvaffaqiyatli to'lovda qaytadi (xabar yuborish uchun)."""
    need = PREPARE_FIELDS + ["merchant_prepare_id"]
    if not all(p.get(k) for k in need) or p["service_id"] != str(service_id):
        return _resp(p, E_REQUEST, "Error in request from click"), None
    if not hmac.compare_digest(make_sign(p, secret, True), p["sign_string"].lower()):
        await _log(session, p, "complete", None, E_SIGN)
        return _resp(p, E_SIGN, "SIGN CHECK FAILED!"), None
    if p["action"] != "1":
        return _resp(p, E_ACTION, "Action not found"), None
    pay = await _load(session, p["merchant_prepare_id"])
    if not pay or str(pay.id) != p["merchant_trans_id"]:
        await _log(session, p, "complete", None, E_NOT_FOUND)
        return _resp(p, E_TRANS, "Transaction does not exist", merchant_confirm_id=None), None
    if pay.status == "paid":
        return _resp(p, E_PAID, "Already paid", merchant_confirm_id=pay.id), None
    if pay.status == "cancelled":
        return _resp(p, E_CANCELLED, "Transaction cancelled", merchant_confirm_id=pay.id), None
    if pay.status != "prepared" or pay.click_trans_id != p["click_trans_id"]:
        await _log(session, p, "complete", pay.id, E_TRANS)
        return _resp(p, E_TRANS, "Transaction does not exist", merchant_confirm_id=pay.id), None
    if not _amount_ok(p, pay):
        await _log(session, p, "complete", pay.id, E_AMOUNT)
        return _resp(p, E_AMOUNT, "Incorrect parameter amount", merchant_confirm_id=pay.id), None
    try:
        click_error = int(p.get("error", "0"))
    except ValueError:
        click_error = 0
    if click_error < 0:  # Click to'lovni bekor qildi
        pay.status = "cancelled"
        await _log(session, p, "complete", pay.id, E_CANCELLED)
        return _resp(p, E_CANCELLED, "Transaction cancelled", merchant_confirm_id=pay.id), None
    pay.status, pay.paid_at = "paid", datetime.now(timezone.utc)
    await change_balance(session, pay.user_id, pay.currency, pay.grant_amount, "click_pay", f"click:{pay.id}")
    await _log(session, p, "complete", pay.id, OK)
    return _resp(p, OK, "Success", merchant_confirm_id=pay.id), pay
