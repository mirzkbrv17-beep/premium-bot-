from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Transfer, User
from services.balance_service import CURRENCIES, change_balance, get_balance


class TransferError(Exception):
    pass


async def transfer(session: AsyncSession, sender_id: int, receiver_abu_id: str,
                   currency: str, amount: int) -> tuple[Transfer, User]:
    if currency not in CURRENCIES or amount <= 0:
        raise TransferError("Valyuta yoki miqdor noto'g'ri")
    receiver = (await session.execute(
        select(User).where(User.abu_id == receiver_abu_id.strip().upper()))).scalar_one_or_none()
    if not receiver:
        raise TransferError("Bunday ABU ID topilmadi")
    if receiver.id == sender_id:
        raise TransferError("O'zingizga o'tkaza olmaysiz")
    if receiver.is_banned:
        raise TransferError("Qabul qiluvchi bloklangan")
    locked = {}
    for uid in sorted((sender_id, receiver.id)):  # deadlockdan saqlanish uchun doim bir xil tartib
        locked[uid] = await get_balance(session, uid, currency, lock=True)
    if locked[sender_id].amount < amount:
        raise TransferError("Balans yetarli emas")
    tr = Transfer(sender_id=sender_id, receiver_id=receiver.id, currency=currency, amount=amount)
    session.add(tr)
    await session.flush()
    await change_balance(session, sender_id, currency, -amount, "transfer_out", f"tr:{tr.id}:out")
    await change_balance(session, receiver.id, currency, amount, "transfer_in", f"tr:{tr.id}:in")
    return tr, receiver
