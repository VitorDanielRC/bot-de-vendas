from __future__ import annotations

from statistics import median

from models import Offer


def is_suspicious_price(original_price: float | None, historical_prices: list[float]) -> bool:
    if original_price is None or len(historical_prices) < 3:
        return False
    normal_price = median(historical_prices)
    return normal_price > 0 and original_price > normal_price * 1.25


def score_offer(offer: Offer, historical_prices: list[float]) -> float:
    suspicious = is_suspicious_price(offer.original_price, historical_prices)
    offer.suspicious = suspicious
    discount_points = offer.discount or 0
    coupon_points = 8 if offer.coupon else 0
    history_bonus = 0
    if historical_prices and offer.price < min(historical_prices):
        history_bonus = 12
    elif historical_prices and offer.price < median(historical_prices):
        history_bonus = 5
    penalty = 20 if suspicious else 0
    offer.score = round(discount_points + offer.relevance + coupon_points + history_bonus - penalty, 2)
    return offer.score

