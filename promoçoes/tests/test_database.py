from database.db import Database
from models import Offer


def offer(price: float = 100, coupon: str | None = None) -> Offer:
    return Offer("ABC", "Produto", price, 150, 33, None, "https://example.com", "Loja", coupon)


def test_deduplication_and_price_drop(tmp_path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    first = offer()
    assert database.can_send(first, 48, 5)[0] is True
    database.mark_sent(first)
    assert database.can_send(first, 48, 5)[0] is False
    assert database.can_send(offer(94), 48, 5)[0] is True


def test_new_coupon_allows_repost(tmp_path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    database.mark_sent(offer())
    assert database.can_send(offer(coupon="NOVO10"), 48, 5)[0] is True


def test_better_discount_allows_repost(tmp_path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    first = offer()
    first.discount = 20
    database.mark_sent(first)
    improved = offer()
    improved.discount = 27
    assert database.can_send(improved, 48, 5)[0] is True


def test_tables_are_created_automatically(tmp_path) -> None:
    database = Database(tmp_path / "nested" / "test.db")
    database.initialize()
    tables = {row["name"] for row in database.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"offers", "sent_offers", "price_history", "run_history"} <= tables
