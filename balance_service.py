from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Balance, Transaction

CURRENCIES = ("ABU_F", "ABU_TON")


class InsufficientFunds(Exception):
    pass


async def get_balance(session: AsyncSession, user_id: int, currency: str, lock: bool = False) -> Balance:
    if currency not in CURRENCIES:
        raise ValueError("Noma'lum valyuta")
    stmt = select(Balance).where(Balance.user_id == user_id, Balance.currency == currency)
    if lock:
        stmt = stmt.with_for_update()
    bal = (await session.execute(stmt)).scalar_one_or_none()
    if bal is None:
        bal = Balance(user_id=user_id, currency=currency, amount=0)
        session.add(bal)
        await session.flush()
    return bal


async def change_balance(session: AsyncSession, user_id: int, currency: str, delta: int,
                         kind: str, ref: str | None = None) -> Transaction:
    """Balansni ledger yozuvi bilan o'zgartiradi. (kind, ref) takrorlansa, eski yozuvni qaytaradi."""
    if ref is not None:
        existing = (await session.execute(
            select(Transaction).where(Transaction.kind == kind, Transaction.ref == ref)
        )).scalar_one_or_none()
        if existing:
            return existing
    bal = await get_balance(session, user_id, currency, lock=True)
    new_amount = bal.amount + delta
    if new_amount < 0:
        raise InsufficientFunds()
    bal.amount = new_amount
    tx = Transaction(user_id=user_id, currency=currency, amount=delta,
                     balance_after=new_amount, kind=kind, ref=ref)
    session.add(tx)
    await session.flush()
    return tx
