"""Chiquvchi so'rovlarni qayta ishlaydi: inline tugmalarga icon_custom_emoji_id qo'shadi.
Telegram rad etsa (masalan bot egasida Premium yo'q), oddiy emojiga qaytib, qayta yuboradi."""
import logging
import re

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from services import emoji_service
from utils.emoji_config import CALLBACK_KEYS

log = logging.getLogger("abu.emoji")
LEADING = re.compile(r"^[^\w]+", re.UNICODE)  # tugma matnidagi oldingi oddiy emojini olib tashlash


def _key_for(btn) -> str | None:
    if btn.text.startswith("⬅️"):
        return "back"
    if btn.callback_data:
        data = btn.callback_data
        return CALLBACK_KEYS.get(data) or CALLBACK_KEYS.get(data.split(":")[0])
    if btn.web_app:
        return "home"
    return None


def apply_icons(markup):
    """Yangi markup qaytaradi (yoki o'zgarish bo'lmasa None)."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return None
    changed, rows = False, []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            key = _key_for(btn)
            cid = emoji_service.CACHE.get(key) if key else None
            if cid and not btn.icon_custom_emoji_id:
                text = LEADING.sub("", btn.text) or btn.text
                btn = btn.model_copy(update={"icon_custom_emoji_id": cid, "text": text})
                changed = True
            new_row.append(btn)
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows) if changed else None


def strip_icons(markup):
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    return InlineKeyboardMarkup(inline_keyboard=[[b.model_copy(update={"icon_custom_emoji_id": None}) for b in row]
                                                 for row in markup.inline_keyboard])


class EmojiRequestMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot: Bot, method):
        has_text = any(isinstance(getattr(method, f, None), str) for f in ("text", "caption"))
        has_markup = isinstance(getattr(method, "reply_markup", None), InlineKeyboardMarkup)
        if not (has_text or has_markup):
            return await make_request(bot, method)
        upd, used_custom = {}, False
        if emoji_service.active():
            new_markup = apply_icons(method.reply_markup) if has_markup else None
            if new_markup:
                upd["reply_markup"], used_custom = new_markup, True
            for f in ("text", "caption"):
                v = getattr(method, f, None)
                if isinstance(v, str) and "<tg-emoji" in v:
                    used_custom = True
            if upd:
                method = method.model_copy(update=upd)
            if used_custom:
                try:
                    return await make_request(bot, method)
                except TelegramBadRequest as ex:
                    log.warning("Custom emoji rad etildi, oddiy emojiga o'tildi: %s", ex)
                    emoji_service.disable_for(600)
        # oddiy rejim: tg-emoji teglari va icon_custom_emoji_id olib tashlanadi
        clean = {}
        for f in ("text", "caption"):
            v = getattr(method, f, None)
            if isinstance(v, str) and "<tg-emoji" in v:
                clean[f] = emoji_service.strip_tags(v)
        if has_markup and any(b.icon_custom_emoji_id for r in method.reply_markup.inline_keyboard for b in r):
            clean["reply_markup"] = strip_icons(method.reply_markup)
        return await make_request(bot, method.model_copy(update=clean) if clean else method)
