"""Validated models returned by the classifier."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    SOLICITUD_CITA = "solicitud_cita"
    CONSULTA_CLINICA = "consulta_clinica"
    PQR = "pqr"
    INFO_ADMINISTRATIVA = "info_administrativa"
    NO_RELEVANTE = "no_relevante"


class Action(StrEnum):
    RESPONDER_AUTOMATICO = "responder_automatico"
    SOLICITAR_INFO = "solicitar_info_adicional"
    ESCALAR_HUMANO = "escalar_humano"
    ESCALAR_CRISIS = "escalar_crisis_emocional"
    IGNORAR = "ignorar"


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClassificationMetadata(BaseModel):
    detected_language: str | None = None
    risk_level: RiskLevel = RiskLevel.NONE
    risk_triggers: list[str] = Field(default_factory=list)
    is_empty: bool = False
    is_non_spanish: bool = False
    was_truncated: bool = False
    processing_ms: int | None = None
    model_used: str | None = None
    error: str | None = None


class ClassificationResult(BaseModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=300)
    suggested_action: Action
    metadata: ClassificationMetadata = Field(default_factory=ClassificationMetadata)


class LLMClassificationOutput(BaseModel):
    """Fields the language model is allowed to decide."""

    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=300)
    suggested_action: Action
