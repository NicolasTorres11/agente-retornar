"""Outgoing WhatsApp transports: local console simulation and Meta Cloud API."""

import uuid

import httpx

from src.domain.models import OutboundMessage
from src.settings import AppSettings


class ConsoleMessenger:
    """Records output through SQLite; avoids external calls during local testing."""

    async def send(self, message: OutboundMessage) -> str:
        return f"local.{uuid.uuid4()}"


class MetaWhatsAppMessenger:
    def __init__(
        self, settings: AppSettings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        settings.require_meta_send_config()
        self._settings = settings
        self._transport = transport

    async def send(self, message: OutboundMessage) -> str | None:
        url = (
            f"https://graph.facebook.com/{self._settings.whatsapp_api_version}/"
            f"{self._settings.whatsapp_phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": message.text},
        }
        headers = {"Authorization": f"Bearer {self._settings.whatsapp_access_token}"}
        async with httpx.AsyncClient(timeout=15, transport=self._transport) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        messages = data.get("messages", [])
        return messages[0].get("id") if messages else None
