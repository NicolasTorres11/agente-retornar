from src.classifier import Action, Category, RiskLevel, classify


def test_empty_does_not_require_credentials(monkeypatch) -> None:
    monkeypatch.delenv("CLASSIFIER_OFFLINE_MODE", raising=False)
    result = classify("  ")
    assert result.category == Category.NO_RELEVANTE
    assert result.suggested_action == Action.IGNORAR


def test_crisis_forces_action_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("CLASSIFIER_OFFLINE_MODE", raising=False)
    result = classify("Me quiero matar, ya tengo las pastillas")
    assert result.category == Category.CONSULTA_CLINICA
    assert result.suggested_action == Action.ESCALAR_CRISIS
    assert result.metadata.risk_level == RiskLevel.CRITICAL


def test_offline_appointment(monkeypatch) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "true")
    result = classify("Necesito agendar cita con psiquiatria", language_hint="es")
    assert result.category == Category.SOLICITUD_CITA
    assert result.metadata.model_used == "offline_rules_v1"


def test_non_spanish_always_handoffs(monkeypatch) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "true")
    result = classify("I need to book an appointment", language_hint="en")
    assert result.category == Category.SOLICITUD_CITA
    assert result.suggested_action == Action.ESCALAR_HUMANO


def test_without_configuration_fails_toward_human(monkeypatch) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "false")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    result = classify("Quiero una cita", language_hint="es")
    assert result.suggested_action == Action.ESCALAR_HUMANO
    assert result.metadata.error is not None
