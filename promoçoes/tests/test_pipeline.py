from database.db import Database
from models import Category, Offer
from services.pipeline import PromotionPipeline
from services.status import RuntimeStatus
from settings import Settings


class Dummy:
    pass


def test_category_specific_discount(tmp_path) -> None:
    settings = Settings(_env_file=None, min_discount=20, min_price=20, max_price=5000)
    database = Database(tmp_path / "db.sqlite")
    database.initialize()
    pipeline = PromotionPipeline(settings, database, [], Dummy(), Dummy(), RuntimeStatus(), tmp_path / "products.json")
    category = Category("GPU", "gpu", min_discount=15)
    accepted = Offer("1", "GPU", 850, 1000, 15, None, "https://example.com", "Loja")
    rejected = Offer("2", "GPU", 900, 1000, 10, None, "https://example.com", "Loja")
    assert pipeline.approve(accepted, category) is True
    assert pipeline.approve(rejected, category) is False

