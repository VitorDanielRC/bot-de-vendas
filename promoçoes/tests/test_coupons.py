import json
from datetime import date

from services.coupons import CouponService


def test_ignores_expired_and_minimum_value(tmp_path) -> None:
    path = tmp_path / "coupons.json"
    path.write_text(json.dumps({"loja": [
        {"code": "OLD", "discount": "50%", "min_value": 0, "expires_at": "2020-01-01"},
        {"code": "MIN", "discount": "30%", "min_value": 500, "expires_at": "2099-01-01"},
        {"code": "OK20", "discount": "20%", "min_value": 50, "expires_at": "2099-01-01"}
    ]}), encoding="utf-8")
    service = CouponService(path)
    assert service.best_for("loja", 100) == "OK20"
    assert service.is_valid({"code": "X", "expires_at": "2024-01-01"}, 100, date(2025, 1, 1)) is False

