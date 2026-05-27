"""WhatsApp Cloud API signature verification and payload extraction."""

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any

from src.domain.models import InboundMessage


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def parse_inbound_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    inbound: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            name = contacts[0].get("profile", {}).get("name") if contacts else None
            for item in value.get("messages", []):
                if item.get("type") != "text":
                    continue
                timestamp = item.get("timestamp")
                received_at = (
                    datetime.fromtimestamp(int(timestamp), UTC).isoformat()
                    if timestamp
                    else datetime.now(UTC).isoformat()
                )
                inbound.append(
                    InboundMessage(
                        wa_id=item["from"],
                        user_name=name,
                        message_id=item["id"],
                        text=item.get("text", {}).get("body", ""),
                        received_at=received_at,
                    )
                )
    return inbound


def parse_statuses(payload: dict[str, Any]) -> list[tuple[str, str]]:
    statuses: list[tuple[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status in change.get("value", {}).get("statuses", []):
                statuses.append((status["id"], status["status"]))
    return statuses
