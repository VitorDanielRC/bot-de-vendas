from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from models import Offer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            store TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            image TEXT,
            category TEXT,
            original_price REAL,
            price REAL NOT NULL,
            discount REAL,
            coupon TEXT,
            score REAL NOT NULL DEFAULT 0,
            suspicious INTEGER NOT NULL DEFAULT 0,
            found_at TEXT NOT NULL,
            UNIQUE(product_id, store, price, coupon)
        );
        CREATE TABLE IF NOT EXISTS sent_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            store TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            original_price REAL,
            price REAL NOT NULL,
            discount REAL,
            coupon TEXT,
            sent_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sent_product ON sent_offers(product_id, store, sent_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_offer_unique
            ON offers(product_id, store, price, IFNULL(coupon, ''));
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            store TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_history_product ON price_history(product_id, store, timestamp);
        CREATE TABLE IF NOT EXISTS run_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            found_count INTEGER NOT NULL DEFAULT 0,
            approved_count INTEGER NOT NULL DEFAULT 0,
            sent_count INTEGER NOT NULL DEFAULT 0,
            errors TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
        with self._lock, self.connect() as connection:
            connection.executescript(schema)

    def save_offer(self, offer: Offer) -> None:
        now = utc_now().isoformat()
        with self._lock, self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO offers
                (product_id, store, title, url, image, category, original_price, price,
                 discount, coupon, score, suspicious, found_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (offer.product_id, offer.store, offer.title, offer.url, offer.image,
                 offer.category, offer.original_price, offer.price, offer.discount,
                 offer.coupon, offer.score, int(offer.suspicious), now),
            )
            connection.execute(
                "INSERT INTO price_history(product_id, store, price, timestamp) VALUES (?, ?, ?, ?)",
                (offer.product_id, offer.store, offer.price, now),
            )

    def price_history(self, product_id: str, store: str, limit: int = 30) -> list[float]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT price FROM price_history WHERE product_id = ? AND store = ?
                ORDER BY timestamp DESC LIMIT ?""", (product_id, store, limit)
            ).fetchall()
        return [float(row["price"]) for row in rows]

    def can_send(self, offer: Offer, repost_hours: int, price_drop_percent: float) -> tuple[bool, str]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT price, discount, coupon, sent_at FROM sent_offers
                WHERE product_id = ? AND store = ? ORDER BY sent_at DESC LIMIT 1""",
                (offer.product_id, offer.store),
            ).fetchone()
        if not row:
            return True, "nova oferta"
        last_price = float(row["price"])
        last_coupon = row["coupon"] or None
        sent_at = datetime.fromisoformat(row["sent_at"])
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        if offer.price <= last_price * (1 - price_drop_percent / 100):
            return True, "preço diminuiu significativamente"
        last_discount = float(row["discount"] or 0)
        if offer.discount is not None and offer.discount >= last_discount + price_drop_percent:
            return True, "desconto melhorou significativamente"
        if offer.coupon and offer.coupon != last_coupon:
            return True, "novo cupom"
        if utc_now() - sent_at >= timedelta(hours=repost_hours):
            return True, "prazo para republicação atingido"
        return False, "produto enviado recentemente"

    def mark_sent(self, offer: Offer) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """INSERT INTO sent_offers
                (product_id, store, title, url, original_price, price, discount, coupon, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (offer.product_id, offer.store, offer.title, offer.url, offer.original_price,
                 offer.price, offer.discount, offer.coupon, utc_now().isoformat()),
            )

    def start_run(self) -> int:
        with self._lock, self.connect() as connection:
            cursor = connection.execute("INSERT INTO run_history(started_at) VALUES (?)", (utc_now().isoformat(),))
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, found: int, approved: int, sent: int, errors: list[str]) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """UPDATE run_history SET finished_at=?, found_count=?, approved_count=?,
                sent_count=?, errors=? WHERE id=?""",
                (utc_now().isoformat(), found, approved, sent, json.dumps(errors, ensure_ascii=False), run_id),
            )

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def health(self) -> bool:
        try:
            return self.query("SELECT 1 AS ok")[0]["ok"] == 1
        except sqlite3.Error:
            return False

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO app_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
