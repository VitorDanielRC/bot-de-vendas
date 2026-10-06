from models import Offer
from utils.formatter import format_offer_message


def test_message_contains_optional_fields_when_available() -> None:
    offer = Offer("1", "Monitor", 999.9, 1499.9, 33, None, "https://example.com", "Mercado Livre", "TECH20")
    message = format_offer_message(offer)
    assert "R$ 1.499,90" in message
    assert "R$ 999,90" in message
    assert "TECH20" in message


def test_message_does_not_invent_discount_or_coupon() -> None:
    offer = Offer("1", "Mouse", 99.9, None, None, None, "https://example.com", "Shopee")
    message = format_offer_message(offer)
    assert "De:" not in message
    assert "% OFF" not in message
    assert "CUPOM" not in message

