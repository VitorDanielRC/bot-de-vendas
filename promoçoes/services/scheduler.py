from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.pipeline import PromotionPipeline
from settings import Settings


def create_scheduler(settings: Settings, pipeline: PromotionPipeline) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        pipeline.run,
        IntervalTrigger(minutes=settings.scan_interval_minutes),
        id="promotion-scan",
        name="Busca automática de promoções",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logging.getLogger("scheduler").info(
        "Busca agendada a cada %d minutos", settings.scan_interval_minutes
    )
    return scheduler

