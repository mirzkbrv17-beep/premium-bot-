from aiogram.types import CopyTextButton, InlineKeyboardButton as B, InlineKeyboardMarkup as M


def topup_methods() -> M:
    return M(inline_keyboard=[
        [B(text="💳 Karta orqali to'lov", callback_data="topup:card")],
        [B(text="⬅️ Orqaga", callback_data="cabinet")],
    ])


def card_details_kb(card_number: str, request_id: int) -> M:
    return M(inline_keyboard=[
        [B(text="📋 Nusxalash", copy_text=CopyTextButton(text=card_number))],
        [B(text="✅ To'lov qildim", callback_data=f"topup:paid:{request_id}")],
        [B(text="⬅️ Orqaga", callback_data="topup")],
    ])
