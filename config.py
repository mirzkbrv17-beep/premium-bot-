import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./local.db"
    ADMIN_IDS: str = ""
    WEBHOOK_SECRET: str = "change-me"
    BASE_URL: str = ""
    CARD_NUMBER: str = ""
    CARD_HOLDER: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_MERCHANT_ID: str = ""
    CLICK_SECRET_KEY: str = ""

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in re.split(r"[,\s]+", self.ADMIN_IDS) if x.strip().isdigit()}

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url

    @property
    def click_configured(self) -> bool:
        return bool(self.CLICK_SERVICE_ID and self.CLICK_MERCHANT_ID and self.CLICK_SECRET_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
