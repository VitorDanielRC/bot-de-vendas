import asyncio

import httpx

from models import Offer
from services.whatsapp import WhatsAppService
from settings import Settings


def test_image_failure_falls_back_to_text() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(500 if request.url.path.endswith("sendImage") else 200, json={})

    service = WhatsAppService(Settings(
        _env_file=None,
        waha_url="http://waha:3000",
        waha_chat_id="120363000@g.us",
    ))
    asyncio.run(service.client.aclose())
    service.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(service.send_offer(Offer(
        "1", "Monitor", 100, 200, 50, "https://example.com/image.jpg",
        "https://example.com/product", "Loja",
    )))
    asyncio.run(service.client.aclose())
    assert result is True
    assert paths == ["/api/sendImage", "/api/sendText"]
