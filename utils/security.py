import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str, max_age: int = 86400, now: float | None = None) -> dict | None:
    """Telegram Mini App initData ni serverda tekshiradi. To'g'ri bo'lsa user dict, aks holda None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = pairs.pop("hash", None)
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    try:
        if (now or time.time()) - int(pairs.get("auth_date", "0")) > max_age:
            return None
        user = json.loads(pairs["user"])
    except (ValueError, KeyError):
        return None
    return user if isinstance(user, dict) and isinstance(user.get("id"), int) else None


class RateLimiter:
    """Oddiy xotiradagi limiter: `limit` ta so'rov / `window` soniya (kalit bo'yicha)."""

    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float, now: float | None = None) -> bool:
        now = now or time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


limiter = RateLimiter()
