from __future__ import annotations

import logging
import mimetypes
from urllib.parse import urlsplit

import httpx

from models import Offer
from settings import Settings
from utils.formatter import format_offer_message


class WhatsAppService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = logging.getLogger("whatsapp")
        self.client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)

    @property
    def configured(self) -> bool:
        return bool(self.settings.waha_url and self.settings.waha_chat_id)

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.settings.waha_api_key} if self.settings.waha_api_key else {}

    async def close(self) -> None:
        await self.client.aclose()

    async def send_offer(self, offer: Offer) -> bool:
        if not self.configured:
            self.log.warning("WAHA_CHAT_ID não configurado; oferta não enviada")
            return False
        message = format_offer_message(offer)
        if offer.image:
            try:
                image_path = urlsplit(offer.image).path
                filename = image_path.rsplit("/", 1)[-1] or "offer.jpg"
                mimetype = mimetypes.guess_type(filename)[0] or "image/jpeg"
                payload = {
                    "session": self.settings.waha_session,
                    "chatId": self.settings.waha_chat_id,
                    "file": {"url": offer.image, "mimetype": mimetype, "filename": filename},
                    "caption": message,
                }
                response = await self.client.post(
                    f"{self.settings.waha_url.rstrip('/')}/api/sendImage",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                self.log.warning("Falha ao enviar imagem; tentando mensagem de texto: %s", exc)
        try:
            payload = {
                "session": self.settings.waha_session,
                "chatId": self.settings.waha_chat_id,
                "text": message,
            }
            response = await self.client.post(
                f"{self.settings.waha_url.rstrip('/')}/api/sendText",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            self.log.error("Falha ao enviar pelo WAHA: %s", exc)
            return False

    async def health(self) -> bool:
        if not self.configured:
            return False
        try:
            response = await self.client.get(
                f"{self.settings.waha_url.rstrip('/')}/api/sessions/{self.settings.waha_session}",
                headers=self.headers,
            )
            return response.is_success and str(response.json().get("status", "")).upper() == "WORKING"
        except (httpx.HTTPError, ValueError):
            return False

    async def session_info(self) -> dict:
        response = await self.client.get(
            f"{self.settings.waha_url.rstrip('/')}/api/sessions/{self.settings.waha_session}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    async def get_qr(self) -> httpx.Response:
        response = await self.client.get(
            f"{self.settings.waha_url.rstrip('/')}/api/{self.settings.waha_session}/auth/qr",
            headers={**self.headers, "Accept": "image/png"},
        )
        response.raise_for_status()
        return response

    async def groups(self) -> list[dict]:
        response = await self.client.get(
            f"{self.settings.waha_url.rstrip('/')}/api/{self.settings.waha_session}/groups",
            params={"limit": 500, "offset": 0},
            headers=self.headers,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("groups", [])
