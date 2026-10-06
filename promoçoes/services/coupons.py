from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


class CouponService:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, list[dict[str, Any]]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def is_valid(coupon: dict[str, Any], price: float, today: date | None = None) -> bool:
        today = today or date.today()
        try:
            minimum = float(coupon.get("min_value") or 0)
        except (TypeError, ValueError):
            return False
        if price < minimum or not coupon.get("code"):
            return False
        expires = coupon.get("expires_at")
        if not expires:
            return True
        try:
            return datetime.strptime(str(expires), "%Y-%m-%d").date() >= today
        except ValueError:
            return False

    def best_for(self, store_key: str, price: float) -> str | None:
        valid = [c for c in self.load().get(store_key, []) if self.is_valid(c, price)]
        if not valid:
            return None
        def value(coupon: dict[str, Any]) -> float:
            raw = str(coupon.get("discount") or "0").replace("%", "").replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                return 0
        return str(max(valid, key=value)["code"])

