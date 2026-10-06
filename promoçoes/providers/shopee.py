from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from models import Category, Offer, calculate_discount
from providers.base import BaseProvider, ProviderError


class ShopeeProvider(BaseProvider):
    key = "shopee"
    display_name = "Shopee"

    @property
    def enabled(self) -> bool:
        return bool(self.settings.shopee_app_id and self.settings.shopee_secret)

    def _authorization(self, payload: str, timestamp: int) -> str:
        factor = f"{self.settings.shopee_app_id}{timestamp}{payload}{self.settings.shopee_secret}"
        signature = hashlib.sha256(factor.encode()).hexdigest()
        return (
            f"SHA256 Credential={self.settings.shopee_app_id}, "
            f"Timestamp={timestamp}, Signature={signature}"
        )

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables}, separators=(",", ":"))
        timestamp = int(time.time())
        response = await self.request(
            "POST",
            self.settings.shopee_api_url,
            content=payload,
            headers={"Content-Type": "application/json", "Authorization": self._authorization(payload, timestamp)},
        )
        data = response.json()
        if data.get("errors"):
            raise ProviderError(f"Shopee retornou erro: {data['errors'][0].get('message', 'desconhecido')}")
        return data.get("data") or {}

    async def search(self, category: Category) -> list[Offer]:
        if not self.enabled:
            return []
        query = """
        query ProductOffers($keyword: String!, $limit: Int!) {
          productOfferV2(keyword: $keyword, limit: $limit) {
            nodes { itemId productName priceMin priceMax priceDiscountRate imageUrl offerLink }
          }
        }
        """
        data = await self._graphql(query, {"keyword": category.query, "limit": self.settings.max_results_per_query})
        container = data.get("productOfferV2") or {}
        nodes = container.get("nodes") or container.get("products") or []
        offers: list[Offer] = []
        for item in nodes:
            try:
                price = float(item.get("priceMin") or item.get("price") or 0)
                rate = float(item.get("priceDiscountRate") or 0)
                original_price = round(price / (1 - rate / 100), 2) if 0 < rate < 100 else None
                url = str(item.get("offerLink") or item.get("productLink") or "")
                if price <= 0 or not url:
                    continue
                offers.append(Offer(
                    product_id=str(item.get("itemId") or item.get("productId")),
                    title=str(item.get("productName") or item.get("title") or "Produto Shopee"),
                    price=price,
                    original_price=original_price,
                    discount=calculate_discount(original_price, price),
                    image=item.get("imageUrl"),
                    url=self.generate_affiliate_link(url),
                    store=self.display_name,
                    category=category.name,
                    relevance=category.relevance,
                ))
            except (TypeError, ValueError, ZeroDivisionError):
                continue
        return offers

    def generate_affiliate_link(self, product_url: str) -> str:
        # A API de busca já retorna offerLink rastreável para a conta autenticada.
        return product_url

