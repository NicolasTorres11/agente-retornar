"""Conversation domain objects."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from src.classifier.models import ClassificationResult


class FlowState(StrEnum):
    NEW = "new"
    AWAITING_CONSENT = "awaiting_consent"
    AWAITING_APPOINTMENT_INFO = "awaiting_appointment_info"
    AWAITING_APPOINTMENT_SLOT = "awaiting_appointment_slot"
    APPOINTMENT_REQUESTED = "appointment_requested"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    IN_PROGRESS = "in_progress"
    HANDOFF = "handoff"
    CRISIS_ACTIVE = "crisis_active"
    CLOSED = "closed"


class Priority(StrEnum):
    NORMAL = "normal"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass(frozen=True)
class InboundMessage:
    wa_id: str
    text: str
    message_id: str
    user_name: str | None = None
    received_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class OutboundMessage:
    wa_id: str
    text: str
    kind: str = "text"


@dataclass(frozen=True)
class ProcessOutcome:
    status: str
    responses: list[str]
    classification: ClassificationResult | None = None
