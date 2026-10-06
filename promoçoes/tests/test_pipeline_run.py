import asyncio
import json

from database.db import Database
from models import Offer
from services.coupons import CouponService
from services.pipeline import PromotionPipeline
from services.status import RuntimeStatus
from settings import Settings


class Provider:
    enabled = True
    key = "mercadolivre"
    display_name = "Teste"

    async def search(self, category):
        return [Offer("P1", "SSD em oferta", 80, 100, 20, None, "https://example.com", "Teste")]


class WhatsApp:
    def __init__(self):
        self.sent = 0

    async def send_offer(self, _offer):
        self.sent += 1
        return True


def test_complete_run_and_deduplication(tmp_path) -> None:
    products = tmp_path / "products.json"
    products.write_text(json.dumps({"categories": [
        {"name": "SSD", "query": "ssd", "min_discount": 20, "relevance": 10}
    ]}), encoding="utf-8")
    coupons_path = tmp_path / "coupons.json"
    coupons_path.write_text("{}", encoding="utf-8")
    database = Database(tmp_path / "db.sqlite")
    database.initialize()
    whatsapp = WhatsApp()
    pipeline = PromotionPipeline(
        Settings(_env_file=None, max_posts_per_run=10),
        database,
        [Provider()],
        whatsapp,
        CouponService(coupons_path),
        RuntimeStatus(),
        products,
    )
    first = asyncio.run(pipeline.run())
    second = asyncio.run(pipeline.run())
    assert first["sent"] == 1
    assert second["sent"] == 0
    assert whatsapp.sent == 1
