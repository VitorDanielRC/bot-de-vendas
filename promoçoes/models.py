from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def calculate_discount(original_price: float | None, price: float) -> float | None:
    if original_price is None or original_price <= price or original_price <= 0 or price < 0:
        return None
    return round((original_price - price) / original_price * 100, 2)


@dataclass(slots=True)
class Category:
    name: str
    query: str
    min_discount: float | None = None
    relevance: float = 0


@dataclass(slots=True)
class Offer:
    product_id: str
    title: str
    price: float
    original_price: float | None
    discount: float | None
    image: str | None
    url: str
    store: str
    coupon: str | None = None
    category: str = ""
    relevance: float = 0
    score: float = 0
    suspicious: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

