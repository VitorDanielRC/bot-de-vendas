from models import Offer
from utils.scoring import is_suspicious_price, score_offer


def make_offer(coupon: str | None = None) -> Offer:
    return Offer("1", "SSD", 100, 200, 50, None, "https://example.com", "Loja", coupon, relevance=10)


def test_coupon_and_historical_low_improve_score() -> None:
    without_coupon = make_offer()
    with_coupon = make_offer("TECH20")
    assert score_offer(with_coupon, [130, 140, 150]) > score_offer(without_coupon, [130, 140, 150])


def test_suspicious_reference_price() -> None:
    assert is_suspicious_price(200, [100, 102, 105]) is True
    offer = make_offer()
    score_offer(offer, [100, 102, 105])
    assert offer.suspicious is True

