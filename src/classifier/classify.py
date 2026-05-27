"""Public classification pipeline."""

from time import perf_counter

from .azure_client import AzureClassifierClient
from .config import Settings
from .models import Action, Category, ClassificationMetadata, ClassificationResult, RiskLevel
from .offline_client import classify_offline
from .policy import classify_by_policy
from .preprocessor import preprocess
from .risk_detector import detect_risk


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def classify(message: str, *, language_hint: str | None = None) -> ClassificationResult:
    """Classify a WhatsApp text; failures are returned as human handoff results."""
    started = perf_counter()
    prepared = preprocess(message, language_hint)
    metadata = ClassificationMetadata(
        detected_language=prepared.detected_language,
        is_empty=prepared.is_empty,
        was_truncated=prepared.was_truncated,
    )
    if prepared.is_empty:
        metadata.processing_ms = _elapsed_ms(started)
        return ClassificationResult(
            category=Category.NO_RELEVANTE,
            confidence=1.0,
            reasoning="Mensaje vacio o sin contenido textual procesable.",
            suggested_action=Action.IGNORAR,
            metadata=metadata,
        )

    risk = detect_risk(prepared.searchable_text)
    metadata.risk_level = risk.level
    metadata.risk_triggers = risk.triggers
    metadata.is_non_spanish = bool(
        prepared.detected_language and prepared.detected_language != "es"
    )

    # Medium signals are conservatively escalated for the local classifier demo.
    if risk.level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
        metadata.model_used = "local_risk_detector_v1"
        metadata.processing_ms = _elapsed_ms(started)
        return ClassificationResult(
            category=Category.CONSULTA_CLINICA,
            confidence=0.99 if risk.level == RiskLevel.CRITICAL else 0.92,
            reasoning="Detectados indicadores de riesgo emocional que requieren atencion humana.",
            suggested_action=Action.ESCALAR_CRISIS,
            metadata=metadata,
        )

    try:
        output = classify_by_policy(prepared.searchable_text)
        settings = Settings()
        if output is not None:
            metadata.model_used = "local_policy_v1"
        elif settings.classifier_offline_mode:
            output = classify_offline(prepared.searchable_text)
            metadata.model_used = "offline_rules_v1"
        else:
            output = AzureClassifierClient(settings).classify(prepared.text)
            metadata.model_used = settings.azure_openai_deployment_name
        action = (
            Action.ESCALAR_HUMANO
            if metadata.is_non_spanish and output.suggested_action != Action.IGNORAR
            else output.suggested_action
        )
        metadata.processing_ms = _elapsed_ms(started)
        return ClassificationResult(
            category=output.category,
            confidence=output.confidence,
            reasoning=output.reasoning,
            suggested_action=action,
            metadata=metadata,
        )
    except Exception as exc:  # The public boundary must fail toward human attention.
        metadata.error = str(exc)
        metadata.processing_ms = _elapsed_ms(started)
        return ClassificationResult(
            category=Category.NO_RELEVANTE,
            confidence=0.0,
            reasoning="No fue posible clasificar automaticamente; requiere revision humana.",
            suggested_action=Action.ESCALAR_HUMANO,
            metadata=metadata,
        )
