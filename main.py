import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from bot import bot, dp
from config import settings
from database import SessionLocal, engine, init_db
from miniapp_api import router as miniapp_router
from services import admin_service, click_service, emoji_service, package_service, progress_service, referral_service, reminder_service
from services.settings_service import seed_defaults

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("abu")


async def reminder_loop():
    """Toshkent 10:00 dan keyin kuniga bir marta kunlik bonus eslatmasi (faqat yoqqanlarga)."""
    while True:
        try:
            async with SessionLocal() as session:
                await reminder_service.run_reminder_once(session, bot)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("reminder_loop xatosi")
        await asyncio.sleep(300)


async def referral_loop():
    """Har 60 soniyada muddati kelgan referrallarni qayta tekshiradi."""
    while True:
        try:
            async with SessionLocal() as session:
                events = await referral_service.process_due(session, bot)
                await session.commit()
            for tg_id, text in events:
                try:
                    await bot.send_message(tg_id, text)
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("referral_loop xatosi")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_defaults(session)
        await referral_service.ensure_default_channel(session)
        await package_service.ensure_default_packages(session)
        await progress_service.ensure_defaults(session)
        await emoji_service.load(session)
        await session.commit()
    if settings.BOT_TOKEN and settings.BASE_URL:
        await bot.set_webhook(f"{settings.BASE_URL.rstrip('/')}/webhook/telegram",
                              secret_token=settings.WEBHOOK_SECRET,
                              allowed_updates=dp.resolve_used_update_types())
        log.info("Webhook o'rnatildi")
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="ABU", web_app=WebAppInfo(url=f"{settings.BASE_URL.rstrip('/')}/app/")))
        except Exception:
            log.warning("Menu tugmasi o'rnatilmadi")
    else:
        log.warning("BOT_TOKEN yoki BASE_URL yo'q: webhook o'rnatilmadi")
    tasks = [asyncio.create_task(referral_loop()), asyncio.create_task(reminder_loop())] if settings.BOT_TOKEN else []
    yield
    for t in tasks:
        t.cancel()
    await bot.session.close()
    await engine.dispose()


app = FastAPI(title="ABU BOT", lifespan=lifespan)
app.include_router(miniapp_router)


@app.get("/health")
async def health():
    return {"status": "ok", "click": "configured" if settings.click_configured else "not_configured"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request,
                           x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="forbidden")
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


def _click_off():
    return {"error": -8, "error_note": "click not_configured"}


@app.post("/webhook/click/prepare")
async def click_prepare(request: Request):
    if not settings.click_configured:
        return _click_off()
    form = {k: str(v) for k, v in (await request.form()).items()}
    async with SessionLocal() as session:
        resp = await click_service.handle_prepare(session, form, settings.CLICK_SECRET_KEY, settings.CLICK_SERVICE_ID)
        await session.commit()
    return resp


@app.post("/webhook/click/complete")
async def click_complete(request: Request):
    if not settings.click_configured:
        return _click_off()
    form = {k: str(v) for k, v in (await request.form()).items()}
    async with SessionLocal() as session:
        resp, payment = await click_service.handle_complete(session, form, settings.CLICK_SECRET_KEY,
                                                            settings.CLICK_SERVICE_ID)
        info = None
        admins = await admin_service.targets(session, "payments")
        if payment:
            from models import User
            user = await session.get(User, payment.user_id)
            info = (user.tg_id, user.abu_id, payment.grant_amount, payment.currency, payment.amount_uzs, payment.id)
        await session.commit()
    if info:
        tg_id, abu_id, amount, cur, uzs, pid = info
        try:
            await bot.send_message(tg_id, f"✅ To'lov tasdiqlandi! Balansingizga <b>{amount:,}</b> {cur} qo'shildi.".replace(",", " "))
        except Exception:
            pass
        for admin_id in admins:
            try:
                await bot.send_message(admin_id, f"💰 Click to'lovi #{pid}: {abu_id}, {amount} {cur}, {uzs} so'm")
            except Exception:
                pass
    return resp


# Mini App (statik fayllar): BASE_URL/app/
app.mount("/app", StaticFiles(directory="miniapp", html=True), name="miniapp")
