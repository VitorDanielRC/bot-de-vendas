from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from models import Category, Offer, calculate_discount
from providers.base import BaseProvider


class AliExpressProvider(BaseProvider):
    key = "aliexpress"
    display_name = "AliExpress"

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.aliexpress_app_key
            and self.settings.aliexpress_app_secret
            and self.settings.aliexpress_tracking_id
        )

    def _sign(self, params: dict[str, str]) -> str:
        joined = "".join(f"{key}{params[key]}" for key in sorted(params))
        raw = f"{self.settings.aliexpress_app_secret}{joined}{self.settings.aliexpress_app_secret}"
        return hashlib.md5(raw.encode()).hexdigest().upper()  # noqa: S324 - algoritmo exigido pelo TOP

    async def _api(self, method: str, business_params: dict[str, Any]) -> dict[str, Any]:
        params = {
            "app_key": self.settings.aliexpress_app_key,
            "method": method,
            "sign_method": "md5",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "format": "json",
            "v": "2.0",
            "simplify": "true",
            **{key: str(value) for key, value in business_params.items()},
        }
        params["sign"] = self._sign(params)
        response = await self.request("GET", self.settings.aliexpress_api_url, params=params)
        return response.json()

    @staticmethod
    def _find_products(data: dict[str, Any]) -> list[dict[str, Any]]:
        response = data.get("aliexpress_affiliate_product_query_response") or data.get("resp_result") or data
        result = response.get("resp_result", response)
        if isinstance(result, str):
            result = json.loads(result)
        nested = result.get("result", result) if isinstance(result, dict) else {}
        products = nested.get("products", nested.get("product", [])) if isinstance(nested, dict) else []
        if isinstance(products, dict):
            products = products.get("product", products.get("products", []))
        return products if isinstance(products, list) else []

    async def search(self, category: Category) -> list[Offer]:
        if not self.enabled:
            return []
        data = await self._api("aliexpress.affiliate.product.query", {
            "keywords": category.query,
            "tracking_id": self.settings.aliexpress_tracking_id,
            "target_currency": "BRL",
            "target_language": "PT",
            "page_size": self.settings.max_results_per_query,
            "ship_to_country": "BR",
        })
        offers: list[Offer] = []
        for item in self._find_products(data):
            try:
                price = float(item.get("target_sale_price") or item.get("sale_price") or 0)
                original = item.get("target_original_price") or item.get("original_price")
                original_price = float(original) if original else None
                url = str(item.get("promotion_link") or item.get("product_detail_url") or "")
                if price <= 0 or not url:
                    continue
                offers.append(Offer(
                    product_id=str(item.get("product_id")),
                    title=str(item.get("product_title") or "Produto AliExpress"),
                    price=price,
                    original_price=original_price,
                    discount=calculate_discount(original_price, price),
                    image=item.get("product_main_image_url"),
                    url=self.generate_affiliate_link(url),
                    store=self.display_name,
                    category=category.name,
                    relevance=category.relevance,
                ))
            except (TypeError, ValueError):
                continue
        return offers

    def generate_affiliate_link(self, product_url: str) -> str:
        # promotion_link já contém o tracking_id quando retornado pela API de afiliados.
        return product_url

