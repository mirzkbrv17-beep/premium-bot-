from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from handlers import (admin, admin_more, admin_shop, admin_super, friends, settings as settings_h, bonus, cabinet, games, market, payments, progress, referral,
                      shop, start, support, tasks, transfer)
from middlewares.database import DbSessionMiddleware
from middlewares.emoji_request import EmojiRequestMiddleware

bot = Bot(settings.BOT_TOKEN or "0:placeholder",
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
bot.session.middleware(EmojiRequestMiddleware())
dp = Dispatcher(storage=MemoryStorage())
dp.update.outer_middleware(DbSessionMiddleware())
dp.include_router(start.router)
dp.include_router(cabinet.router)
dp.include_router(bonus.router)
dp.include_router(referral.router)
dp.include_router(transfer.router)
dp.include_router(payments.router)
dp.include_router(shop.router)
dp.include_router(admin_shop.router)
dp.include_router(admin_more.router)
for _r in (admin_super.router, friends.router, settings_h.router, progress.router, tasks.router, support.router, market.router, games.router):
    dp.include_router(_r)
dp.include_router(admin.router)
