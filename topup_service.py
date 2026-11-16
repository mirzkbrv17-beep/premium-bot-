from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, TopupRequest
from services.balance_service import change_balance
from services.settings_service import get_setting


class TopupError(Exception):
    pass


async def create_request(session: AsyncSession, user_id: int, abu_f_amount: int) -> TopupRequest:
    min_amount = int(await get_setting(session, "abu_f_min", "5"))
    rate = int(await get_setting(session, "abu_f_rate_uzs", "10"))
    if abu_f_amount < min_amount:
        raise TopupError(f"Minimal miqdor: {min_amount} ABU F")
    req = TopupRequest(user_id=user_id, abu_f_amount=abu_f_amount, amount_uzs=abu_f_amount * rate)
    session.add(req)
    await session.flush()
    return req


async def attach_receipt(session: AsyncSession, request_id: int, user_id: int, file_id: str) -> TopupRequest:
    req = (await session.execute(
        select(TopupRequest).where(TopupRequest.id == request_id).with_for_update()
    )).scalar_one_or_none()
    if not req or req.user_id != user_id or req.status not in ("created", "awaiting_review"):
        raise TopupError("So'rov topilmadi yoki yopilgan")
    req.receipt_file_id = file_id
    req.status = "awaiting_review"
    await session.flush()
    return req


async def _review(session: AsyncSession, request_id: int, admin_tg_id: int, approve: bool) -> TopupRequest:
    req = (await session.execute(
        select(TopupRequest).where(TopupRequest.id == request_id).with_for_update()
    )).scalar_one_or_none()
    if not req:
        raise TopupError("So'rov topilmadi")
    if req.status != "awaiting_review":
        raise TopupError("Bu so'rov allaqachon ko'rib chiqilgan yoki chek yuborilmagan")
    req.status = "approved" if approve else "rejected"
    req.reviewed_by = admin_tg_id
    req.reviewed_at = datetime.now(timezone.utc)
    if approve:
        # ref = topup:<id> -> bir so'rov uchun faqat bitta marta pul yoziladi
        await change_balance(session, req.user_id, "ABU_F", req.abu_f_amount, "topup_card", f"topup:{req.id}")
    session.add(AuditLog(actor_tg_id=admin_tg_id,
                         action="topup_approve" if approve else "topup_reject",
                         details=f"request_id={req.id}"))
    await session.flush()
    return req


async def approve(session: AsyncSession, request_id: int, admin_tg_id: int) -> TopupRequest:
    return await _review(session, request_id, admin_tg_id, True)


async def reject(session: AsyncSession, request_id: int, admin_tg_id: int) -> TopupRequest:
    return await _review(session, request_id, admin_tg_id, False)
