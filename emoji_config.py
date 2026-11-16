"""Emoji kalitlari, zaxira (oddiy) emoji va tugma callback'lari xaritasi.

DIQQAT: custom_emoji_id lar bu yerda YO'Q. Ular haqiqiy Telegram emoji-paketidan olinadi va
admin tomonidan /emoji_pack va /emoji_set buyruqlari bilan bazaga yoziladi (to'qib yozilgan ID ishlamaydi).
"""

FALLBACK = {
    "home": "🏠", "cabinet": "👤", "balance": "💰", "abu_f": "🪙", "abu_ton": "💎", "shop": "🛍", "market": "🌐",
    "bonus": "🎁", "tasks": "📋", "rating": "🏆", "vip": "👑", "games": "🎮", "support": "💬", "settings": "⚙️",
    "payment": "💳", "referral": "👥", "transfer": "🔁", "friends": "👫", "back": "⬅️", "achievements": "🏅",
}

LABELS = {
    "home": "Bosh sahifa (animatsiyali uy)", "cabinet": "Kabinet (profil)", "balance": "Balans", "abu_f": "ABU F (oltin tanga)",
    "abu_ton": "ABU TON (ko'k olmos)", "shop": "Do'kon (sovg'a/savat)", "market": "Market (savdo)", "bonus": "Bonuslar (sovg'a)",
    "tasks": "Topshiriqlar (nishon)", "rating": "Reyting (kubok)", "vip": "VIP (toj)", "games": "O'yinlar",
    "support": "Yordam", "settings": "Sozlamalar", "payment": "To'lov (karta)", "referral": "Referral",
    "transfer": "Transfer", "friends": "Do'stlar", "back": "Orqaga", "achievements": "Yutuqlar",
}

# tugma callback_data (yoki ':' gacha bo'lgan qismi) -> emoji kaliti
CALLBACK_KEYS = {
    "home": "home", "cabinet": "cabinet", "shop": "shop", "market": "market", "mk": "market", "bonus": "bonus",
    "tasks": "tasks", "task": "tasks", "rating": "rating", "vip": "vip", "games": "games", "quiz": "games",
    "wheel": "games", "support": "support", "sup": "support", "settings": "settings", "set": "settings",
    "topup": "payment", "buy": "payment", "referral": "referral", "ref": "referral", "transfer": "transfer",
    "tr": "transfer", "friends": "friends", "fr": "friends", "ach": "achievements",
}
