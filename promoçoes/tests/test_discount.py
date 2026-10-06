from models import calculate_discount


def test_calculate_discount() -> None:
    assert calculate_discount(1500, 1000) == 33.33


def test_discount_is_none_without_real_reduction() -> None:
    assert calculate_discount(None, 100) is None
    assert calculate_discount(100, 100) is None
    assert calculate_discount(90, 100) is None

