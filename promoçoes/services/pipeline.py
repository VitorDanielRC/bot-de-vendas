from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from database.db import Database
from models import Category, Offer
from providers.base import BaseProvider
from services.coupons import CouponService
from services.status import RuntimeStatus
from services.whatsapp import WhatsAppService
from settings import Settings
from utils.scoring import score_offer


class PromotionPipeline:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        providers: list[BaseProvider],
        whatsapp: WhatsAppService,
        coupons: CouponService,
        status: RuntimeStatus,
        products_path: str | Path,
    ) -> None:
        self.settings = settings
        self.database = database
        self.providers = providers
        self.whatsapp = whatsapp
        self.coupons = coupons
        self.status = status
        self.products_path = Path(products_path)
        self.log = logging.getLogger("pipeline")
        self._scan_lock = asyncio.Lock()

    def load_categories(self) -> list[Category]:
        data = json.loads(self.products_path.read_text(encoding="utf-8"))
        return [Category(**item) for item in data.get("categories", [])]

    def approve(self, offer: Offer, category: Category) -> bool:
        if not self.settings.min_price <= offer.price <= self.settings.max_price:
            return False
        minimum = category.min_discount if category.min_discount is not None else self.settings.min_discount
        return offer.discount is not None and offer.discount >= minimum

    async def run(self) -> dict[str, int | list[str] | str]:
        if self._scan_lock.locked():
            self.log.info("Uma busca já está em andamento; execução ignorada")
            return {"status": "already_running", "found": 0, "approved": 0, "sent": 0, "errors": []}
        async with self._scan_lock:
            self.status.running = True
            run_id = self.database.start_run()
            found_offers: dict[tuple[str, str], tuple[Offer, Category, str]] = {}
            errors: list[str] = []
            try:
                categories = self.load_categories()
                for provider in self.providers:
                    if not provider.enabled:
                        self.log.info("%s sem credenciais; ignorando", provider.display_name)
                        self.status.set_provider(provider.key, False)
                        continue
                    self.log.info("Pesquisando %s...", provider.display_name)
                    provider_ok = True
                    provider_count = 0
                    for category in categories:
                        try:
                            offers = await provider.search(category)
                            provider_count += len(offers)
                            for offer in offers:
                                key = (offer.store, offer.product_id)
                                current = found_offers.get(key)
                                if current is None or (offer.discount or 0) > (current[0].discount or 0):
                                    found_offers[key] = (offer, category, provider.key)
                        except Exception as exc:  # cada provider é uma fronteira de falha
                            provider_ok = False
                            message = f"Erro {provider.display_name}: {exc}"
                            self.log.error(message)
                            errors.append(message)
                            break
                    self.status.set_provider(provider.key, provider_ok)
                    self.log.info("%d produtos encontrados em %s", provider_count, provider.display_name)

                approved: list[Offer] = []
                for offer, category, provider_key in found_offers.values():
                    history = self.database.price_history(offer.product_id, offer.store)
                    offer.coupon = offer.coupon or self.coupons.best_for(provider_key, offer.price)
                    score_offer(offer, history)
                    self.database.save_offer(offer)
                    if self.approve(offer, category):
                        approved.append(offer)

                approved.sort(key=lambda item: (item.score, item.discount or 0), reverse=True)
                self.log.info("%d promoções aprovadas", len(approved))
                sent = 0
                for offer in approved:
                    if sent >= self.settings.max_posts_per_run:
                        break
                    can_send, reason = self.database.can_send(
                        offer,
                        self.settings.repost_after_hours,
                        self.settings.significant_price_drop_percent,
                    )
                    if not can_send:
                        self.log.info("Produto já enviado. Ignorando: %s (%s)", offer.title, reason)
                        continue
                    self.log.info("Enviando promoção: %s", offer.title)
                    if await self.whatsapp.send_offer(offer):
                        self.database.mark_sent(offer)
                        sent += 1
                        self.log.info("Promoção enviada")

                self.database.finish_run(run_id, len(found_offers), len(approved), sent, errors)
                self.status.finish_scan(errors)
                return {
                    "status": "completed",
                    "found": len(found_offers),
                    "approved": len(approved),
                    "sent": sent,
                    "errors": errors,
                }
            except Exception as exc:
                message = f"Erro geral na busca: {exc}"
                self.log.exception(message)
                errors.append(message)
                self.database.finish_run(run_id, len(found_offers), 0, 0, errors)
                self.status.finish_scan(errors)
                return {"status": "failed", "found": len(found_offers), "approved": 0, "sent": 0, "errors": errors}

