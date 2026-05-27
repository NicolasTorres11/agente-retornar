"""Outbound messaging port."""

from typing import Protocol

from src.domain.models import OutboundMessage


class OutboundMessenger(Protocol):
    async def send(self, message: OutboundMessage) -> str | None: ...
