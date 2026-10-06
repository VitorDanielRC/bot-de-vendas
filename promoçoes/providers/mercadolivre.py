from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models import Category, Offer, calculate_discount
from providers.base import BaseProvider


class MercadoLivreProvider(BaseProvider):
    key = "mercadolivre"
    display_name = "Mercado Livre"
    search_url = "https://api.mercadolibre.com/sites/MLB/search"

    @property
    def enabled(self) -> bool:
        # O endpoint oficial de busca passou a exigir autenticação.
        return bool(self.settings.mercadolivre_access_token)

    async def search(self, category: Category) -> list[Offer]:
        headers = {}
        if self.settings.mercadolivre_access_token:
            headers["Authorization"] = f"Bearer {self.settings.mercadolivre_access_token}"
        response = await self.request(
            "GET",
            self.search_url,
            params={"q": category.query, "limit": self.settings.max_results_per_query},
            headers=headers,
        )
        results = response.json().get("results", [])
        offers: list[Offer] = []
        for item in results:
            try:
                price = float(item["price"])
                original = item.get("original_price")
                original_price = float(original) if original is not None else None
                discount = calculate_discount(original_price, price)
                permalink = str(item.get("permalink") or "")
                if not permalink:
                    continue
                offers.append(Offer(
                    product_id=str(item["id"]),
                    title=str(item.get("title") or "Produto sem título"),
                    price=price,
                    original_price=original_price,
                    discount=discount,
                    image=item.get("thumbnail"),
                    url=self.generate_affiliate_link(permalink),
                    store=self.display_name,
                    category=category.name,
                    relevance=category.relevance,
                ))
            except (KeyError, TypeError, ValueError):
                self.log.warning("Resultado inválido ignorado: %s", item.get("id", "sem id"))
        return offers

    def generate_affiliate_link(self, product_url: str) -> str:
        tag = self.settings.mercadolivre_affiliate_tag.strip()
        if not tag:
            return product_url
        parts = urlsplit(product_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["matt_tool"] = tag
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
