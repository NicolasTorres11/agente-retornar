import asyncio
import json

import httpx
from cryptography.fernet import Fernet

from src.adapters.whatsapp.client import MetaWhatsAppMessenger
from src.domain.models import OutboundMessage
from src.settings import AppSettings


def test_meta_sender_constructs_cloud_api_request(tmp_path) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.sent.1"}]})

    settings = AppSettings(
        db_path=tmp_path / "demo.db",
        field_encryption_key=Fernet.generate_key().decode("ascii"),
        whatsapp_send_mode="meta",
        whatsapp_access_token="meta-test-token",
        whatsapp_phone_number_id="12345",
        whatsapp_api_version="v21.0",
    )
    sender = MetaWhatsAppMessenger(settings, transport=httpx.MockTransport(handler))
    meta_id = asyncio.run(sender.send(OutboundMessage(wa_id="57300", text="Respuesta demo")))

    assert meta_id == "wamid.sent.1"
    assert captured["url"] == "https://graph.facebook.com/v21.0/12345/messages"
    assert captured["authorization"] == "Bearer meta-test-token"
    assert captured["payload"]["to"] == "57300"  # type: ignore[index]
