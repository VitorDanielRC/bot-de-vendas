from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class RuntimeStatus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.providers: dict[str, bool] = {"mercadolivre": False, "shopee": False, "aliexpress": False}
        self.last_scan: str | None = None
        self.last_errors: list[str] = []
        self.running = False

    def set_provider(self, key: str, healthy: bool) -> None:
        with self._lock:
            self.providers[key] = healthy

    def finish_scan(self, errors: list[str]) -> None:
        with self._lock:
            self.last_scan = datetime.now(timezone.utc).isoformat()
            self.last_errors = errors[-20:]
            self.running = False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "providers": dict(self.providers),
                "last_scan": self.last_scan,
                "last_errors": list(self.last_errors),
                "running": self.running,
            }

