from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from models import Category, Offer
from settings import Settings


class ProviderError(RuntimeError):
    pass


class BaseProvider(ABC):
    key = "base"
    display_name = "Base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = logging.getLogger(f"provider.{self.key}")
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "promo-bot/1.0 (+local automation)"},
        )

    @property
    def enabled(self) -> bool:
        return True

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        raise ProviderError(f"{self.display_name}: falha após 3 tentativas: {last_error}")

    @abstractmethod
    async def search(self, category: Category) -> list[Offer]:
        raise NotImplementedError

    def generate_affiliate_link(self, product_url: str) -> str:
        return product_url

