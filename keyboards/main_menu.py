from aiogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M, WebAppInfo

from config import settings


def main_menu() -> M:
    top = [[B(text="📱 ABU Mini App", web_app=WebAppInfo(url=f"{settings.BASE_URL.rstrip('/')}/app/"))]] if settings.BASE_URL else []
    return M(inline_keyboard=top + [
        [B(text="👤 Kabinet", callback_data="cabinet"), B(text="🛍 Do'kon", callback_data="shop")],
        [B(text="🌐 Market", callback_data="market"), B(text="📋 Topshiriqlar", callback_data="tasks")],
        [B(text="🎁 Kunlik bonus", callback_data="bonus"), B(text="👥 Referral", callback_data="referral")],
        [B(text="🏆 Reyting", callback_data="rating"), B(text="👑 VIP", callback_data="vip")],
        [B(text="🎮 O'yinlar", callback_data="games"), B(text="👫 Do'stlar", callback_data="friends")],
        [B(text="💬 Yordam", callback_data="support"), B(text="⚙️ Sozlamalar", callback_data="settings")],
    ])


def cabinet_menu() -> M:
    return M(inline_keyboard=[
        [B(text="💳 Balansni to'ldirish", callback_data="topup")],
        [B(text="💎 Valyuta sotib olish (Click)", callback_data="buy")],
        [B(text="🔁 Transfer", callback_data="transfer"), B(text="🏅 Yutuqlar", callback_data="ach")],
        [B(text="⬅️ Orqaga", callback_data="home")],
    ])


def channels_kb(channels: list[str]) -> M:
    rows = [[B(text=f"📢 {c}", url=f"https://t.me/{c.lstrip('@')}")] for c in channels]
    rows.append([B(text="✅ Tekshirish", callback_data="ref:check")])
    return M(inline_keyboard=rows)


def back_home() -> M:
    return M(inline_keyboard=[[B(text="⬅️ Orqaga", callback_data="home")]])
