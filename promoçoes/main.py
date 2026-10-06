from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn

from database.db import Database
from providers import AliExpressProvider, MercadoLivreProvider, ShopeeProvider
from services.coupons import CouponService
from services.pipeline import PromotionPipeline
from services.scheduler import create_scheduler
from services.status import RuntimeStatus
from services.whatsapp import WhatsAppService
from settings import BASE_DIR, get_settings
from utils.logger import configure_logging
from web.app import create_app


settings = get_settings()
configure_logging(settings.log_level)
database = Database(settings.database_file)
database.initialize()
settings.waha_chat_id = database.get_setting("waha_chat_id", settings.waha_chat_id)
status = RuntimeStatus()
providers = [MercadoLivreProvider(settings), ShopeeProvider(settings), AliExpressProvider(settings)]
whatsapp = WhatsAppService(settings)
pipeline = PromotionPipeline(
    settings=settings,
    database=database,
    providers=providers,
    whatsapp=whatsapp,
    coupons=CouponService(BASE_DIR / "config" / "coupons.json"),
    status=status,
    products_path=BASE_DIR / "config" / "products.json",
)
scheduler = create_scheduler(settings, pipeline)


@asynccontextmanager
async def lifespan(_app):
    scheduler.start()
    startup_task = asyncio.create_task(pipeline.run()) if settings.run_scan_on_startup else None
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if startup_task and not startup_task.done():
            startup_task.cancel()
        if startup_task:
            await asyncio.gather(startup_task, return_exceptions=True)
        await asyncio.gather(*(provider.close() for provider in providers), return_exceptions=True)
        await whatsapp.close()


app = create_app(database, status, whatsapp, pipeline, lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.web_host, port=settings.web_port, reload=False)
