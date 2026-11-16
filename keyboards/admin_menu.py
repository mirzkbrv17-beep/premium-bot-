from aiogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M


def review_kb(request_id: int) -> M:
    return M(inline_keyboard=[[
        B(text="✅ Tasdiqlash", callback_data=f"adm:ok:{request_id}"),
        B(text="❌ Rad etish", callback_data=f"adm:no:{request_id}"),
    ]])
