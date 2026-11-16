from html import escape


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def mask_card(number: str) -> str:
    return f"{number[:4]} **** **** {number[-4:]}" if len(number) >= 8 else "—"


def card_pretty(number: str) -> str:
    return " ".join(number[i:i + 4] for i in range(0, len(number), 4))


def e(text: str | None) -> str:
    return escape(text or "")


from datetime import date, datetime
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")


def today_tashkent() -> date:
    return datetime.now(TASHKENT).date()


async def say(bot, tg_id: int, msgs: list[str]) -> None:
    for m in msgs:
        try:
            await bot.send_message(tg_id, m)
        except Exception:
            pass
