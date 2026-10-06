from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    scan_interval_minutes: int = Field(30, ge=1)
    run_scan_on_startup: bool = True
    min_discount: float = Field(20, ge=0, le=100)
    min_price: float = Field(20, ge=0)
    max_price: float = Field(5000, gt=0)
    max_posts_per_run: int = Field(10, ge=0)
    repost_after_hours: int = Field(48, ge=0)
    significant_price_drop_percent: float = Field(5, ge=0)
    request_timeout_seconds: float = Field(15, gt=0)
    max_results_per_query: int = Field(20, ge=1, le=50)
    database_path: str = "data/promotions.db"
    log_level: str = "INFO"
    web_host: str = "0.0.0.0"
    web_port: int = Field(8000, ge=1, le=65535)

    waha_url: str = "http://waha:3000"
    waha_session: str = "default"
    waha_chat_id: str = ""
    waha_api_key: str = ""

    mercadolivre_access_token: str = ""
    mercadolivre_affiliate_tag: str = ""
    shopee_app_id: str = ""
    shopee_secret: str = ""
    shopee_affiliate_id: str = ""
    shopee_api_url: str = "https://open-api.affiliate.shopee.com.br/graphql"
    aliexpress_app_key: str = ""
    aliexpress_app_secret: str = ""
    aliexpress_tracking_id: str = ""
    aliexpress_api_url: str = "https://api-sg.aliexpress.com/sync"

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        return path if path.is_absolute() else BASE_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()

