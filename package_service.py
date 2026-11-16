from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Package

DEFAULT_TON = [(200, 50_000), (400, 100_000), (800, 200_000), (1_600, 400_000), (3_200, 800_000), (6_400, 1_600_000)]


async def ensure_default_packages(session: AsyncSession) -> None:
    n = (await session.execute(select(func.count(Package.id)))).scalar_one()
    if n == 0:
        for amount, price in DEFAULT_TON:
            session.add(Package(currency="ABU_TON", amount=amount, price_uzs=price))
        await session.flush()


async def list_packages(session: AsyncSession, currency: str = "ABU_TON") -> list[Package]:
    rows = await session.execute(select(Package).where(Package.currency == currency, Package.is_active.is_(True))
                                 .order_by(Package.price_uzs))
    return list(rows.scalars())
