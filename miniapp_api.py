"""Mini App uchun API. Har bir so'rov Telegram initData orqali serverda tekshiriladi."""
import re
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from config import settings
from database import SessionLocal
from models import (Achievement, Listing, MarketOrder, Order, Package, Product, Referral, Streak, Task,
                    TaskCompletion, Transaction, UserAchievement, VipLevel)
from services import bonus_service, market_service, progress_service, promo_service, shop_service, task_service
from services.balance_service import get_balance
from services.market_service import MarketError
from services.promo_service import PromoError
from services.shop_service import ShopError
from services.task_service import TaskError
from services.user_service import get_or_create_user
from utils.helpers import today_tashkent
from utils.security import limiter, verify_init_data

router = APIRouter(prefix="/api")
TAG = re.compile(r"<[^>]+>")


def clean(msgs: list[str]) -> list[str]:
    return [TAG.sub("", m) for m in msgs]


@asynccontextmanager
async def scope(request: Request, limit_key: str | None = None, limit: int = 40, window: float = 10):
    tg = verify_init_data(request.headers.get("X-Init-Data", ""), settings.BOT_TOKEN)
    if not tg:
        raise HTTPException(401, "Telegram orqali oching")
    if not limiter.allow(f"{tg['id']}:{limit_key or 'all'}", limit, window):
        raise HTTPException(429, "Juda tez-tez so'rov. Bir oz kuting.")
    async with SessionLocal() as s:
        name = " ".join(x for x in (tg.get("first_name"), tg.get("last_name")) if x) or "User"
        user = await get_or_create_user(s, tg["id"], tg.get("username"), name)
        if user.is_banned:
            raise HTTPException(403, "Akkaunt bloklangan")
        try:
            yield s, user
            await s.commit()
        except HTTPException:
            await s.rollback()
            raise
        except Exception:
            await s.rollback()
            raise


@router.get("/me")
async def me(request: Request):
    async with scope(request) as (s, u):
        f, t = await get_balance(s, u.id, "ABU_F"), await get_balance(s, u.id, "ABU_TON")
        xp = await progress_service.get_xp(s, u.id)
        vip = await progress_service.vip_for(s, u.id)
        st = (await s.execute(select(Streak).where(Streak.user_id == u.id))).scalar_one_or_none()
        rs = {"pending": 0, "rewarded": 0, "cancelled": 0}
        rs.update({k: v for k, v in await s.execute(select(Referral.status, func.count(Referral.id))
                                                    .where(Referral.inviter_id == u.id).group_by(Referral.status))})
        have = (await s.execute(select(func.count(UserAchievement.id)).where(UserAchievement.user_id == u.id))).scalar_one()
        total = (await s.execute(select(func.count(Achievement.code)))).scalar_one()
        from bot import bot
        username = (await bot.me()).username if settings.BOT_TOKEN else ""
        return {"abu_id": u.abu_id, "name": u.full_name, "username": u.username, "joined": u.created_at.date().isoformat(),
                "level": xp.level, "xp": xp.xp, "level_base": 100 * (xp.level - 1) ** 2, "level_next": 100 * xp.level ** 2,
                "vip": {"name": vip.name, "discount": vip.discount_percent, "title": vip.title} if vip else None,
                "f": f.amount, "ton": t.amount, "streak": st.current if st else 0,
                "referral": {**rs, "link": f"https://t.me/{username}?start=ref_{u.id}" if username else ""},
                "achievements": {"have": have, "total": total}, "bot": username}


@router.get("/bonus")
async def bonus_state(request: Request):
    async with scope(request) as (s, u):
        st = (await s.execute(select(Streak).where(Streak.user_id == u.id))).scalar_one_or_none()
        return {"streak": st.current if st else 0, "claimed_today": bool(st and st.last_claim == today_tashkent()),
                "base": bonus_service.BASE_REWARD, "milestones": bonus_service.MILESTONES}


@router.post("/bonus/claim")
async def bonus_claim(request: Request):
    async with scope(request, "claim", 5, 60) as (s, u):
        try:
            streak, reward = await bonus_service.claim_daily(s, u.id)
        except bonus_service.AlreadyClaimed:
            raise HTTPException(400, "Bugungi bonus olingan")
        extra = await progress_service.award_xp(s, u.id, "daily", f"{u.id}:{today_tashkent().isoformat()}")
        extra += await progress_service.check_achievements(s, u.id)
        return {"streak": streak, "reward": reward, "messages": clean(extra)}


@router.get("/tasks")
async def tasks(request: Request):
    async with scope(request) as (s, u):
        out = []
        for t in await task_service.active_tasks(s):
            period = "once" if t.repeat == "once" else today_tashkent().isoformat()
            done = (await s.execute(select(TaskCompletion.id).where(
                TaskCompletion.task_id == t.id, TaskCompletion.user_id == u.id, TaskCompletion.period_key == period))).first()
            out.append({"id": t.id, "title": t.title, "description": t.description, "reward_f": t.reward_f,
                        "reward_ton": t.reward_ton, "kind": t.kind, "channel": t.channel, "repeat": t.repeat, "done": bool(done)})
        return out


@router.post("/tasks/{task_id}/check")
async def task_check(task_id: int, request: Request):
    async with scope(request, "task", 10, 60) as (s, u):
        from bot import bot
        try:
            extra = await task_service.complete_task(s, bot, u, task_id)
        except TaskError as ex:
            raise HTTPException(400, str(ex))
        return {"messages": clean(extra)}


@router.get("/shop")
async def shop(request: Request):
    async with scope(request) as (s, u):
        prods = (await s.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.category, Product.id))).scalars().all()
        items = []
        for p in prods:
            price, cost = await shop_service.quote(s, u.id, p)
            items.append({"id": p.id, "category": p.category, "name": p.name, "description": p.description,
                          "price_uzs": price, "abu_f": cost, "stock": p.stock, "discount": p.discount_percent})
        packs = (await s.execute(select(Package).where(Package.is_active.is_(True)).order_by(Package.currency, Package.price_uzs))).scalars().all()
        return {"products": items, "packages": [{"id": k.id, "currency": k.currency, "amount": k.amount, "price_uzs": k.price_uzs} for k in packs]}


class BuyIn(BaseModel):
    id: int


@router.post("/shop/buy")
async def shop_buy(body: BuyIn, request: Request):
    async with scope(request, "buy", 10, 60) as (s, u):
        try:
            o = await shop_service.buy(s, u.id, body.id)
        except ShopError as ex:
            raise HTTPException(400, str(ex))
        extra = await progress_service.check_achievements(s, u.id)
        return {"order_id": o.id, "abu_f": o.price_abu_f, "messages": clean(extra)}


@router.get("/market")
async def market(request: Request, q: str = "", sort: str = "new", page: int = 0):
    async with scope(request) as (s, u):
        items = await market_service.search(s, q or None, "cheap" if sort == "cheap" else "new", max(page, 0), 12)
        out = []
        for li in items:
            avg, n = await market_service.seller_rating(s, li.seller_id)
            from models import User
            seller = await s.get(User, li.seller_id)
            out.append({"id": li.id, "title": li.title, "description": li.description, "price": li.price_abu_f,
                        "seller": seller.abu_id, "rating": avg, "reviews": n, "mine": li.seller_id == u.id})
        return out


@router.post("/market/buy")
async def market_buy(body: BuyIn, request: Request):
    async with scope(request, "mbuy", 10, 60) as (s, u):
        try:
            o = await market_service.buy(s, u.id, body.id)
        except MarketError as ex:
            raise HTTPException(400, str(ex))
        return {"order_id": o.id, "abu_f": o.price_abu_f}


class ListingIn(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    price: int = Field(ge=1, le=1_000_000_000)
    description: str = Field(default="", max_length=500)


@router.post("/market/listings")
async def market_create(body: ListingIn, request: Request):
    async with scope(request, "mlist", 5, 60) as (s, u):
        try:
            li = await market_service.create_listing(s, u.id, body.title, body.price, body.description)
        except MarketError as ex:
            raise HTTPException(400, str(ex))
        return {"id": li.id, "status": li.status}


class PromoIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)


@router.post("/promo/redeem")
async def promo_redeem(body: PromoIn, request: Request):
    # promo kodlar faqat shu yerda (Mini App Kabineti) kiritiladi; brute-force'ga qarshi qat'iy limit
    async with scope(request, "promo", 5, 60) as (s, u):
        try:
            p = await promo_service.redeem(s, u.id, body.code)
        except PromoError as ex:
            raise HTTPException(400, str(ex))
        return {"currency": p.currency, "amount": p.amount}


@router.get("/history")
async def history(request: Request):
    async with scope(request) as (s, u):
        tx = (await s.execute(select(Transaction).where(Transaction.user_id == u.id).order_by(Transaction.id.desc()).limit(40))).scalars().all()
        orders = (await s.execute(select(Order, Product.name).join(Product, Product.id == Order.product_id)
                                  .where(Order.user_id == u.id).order_by(Order.id.desc()).limit(20))).all()
        morders = (await s.execute(select(MarketOrder, Listing.title).join(Listing, Listing.id == MarketOrder.listing_id)
                                   .where((MarketOrder.buyer_id == u.id) | (MarketOrder.seller_id == u.id))
                                   .order_by(MarketOrder.id.desc()).limit(20))).all()
        return {
            "transactions": [{"currency": t.currency, "amount": t.amount, "kind": t.kind, "at": t.created_at.isoformat()} for t in tx],
            "orders": [{"id": o.id, "name": n, "abu_f": o.price_abu_f, "status": o.status} for o, n in orders],
            "market": [{"id": o.id, "title": n, "abu_f": o.price_abu_f, "status": o.status,
                        "role": "buyer" if o.buyer_id == u.id else "seller"} for o, n in morders],
        }
