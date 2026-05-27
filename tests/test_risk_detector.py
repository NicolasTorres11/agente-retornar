from src.classifier.models import RiskLevel
from src.classifier.preprocessor import preprocess
from src.classifier.risk_detector import detect_risk


def _detect(text: str) -> RiskLevel:
    return detect_risk(preprocess(text).searchable_text).level


def test_critical_method_pattern() -> None:
    assert _detect("Me quiero matar, ya tengo las pastillas") == RiskLevel.CRITICAL


def test_high_active_ideation_pattern() -> None:
    assert _detect("Ya no quiero vivir") == RiskLevel.HIGH


def test_medium_hopelessness_pattern() -> None:
    assert _detect("No le veo sentido a nada") == RiskLevel.MEDIUM


def test_low_distress_pattern() -> None:
    assert _detect("Estoy muy ansiosa") == RiskLevel.LOW


def test_normal_message_has_no_risk() -> None:
    assert _detect("Necesito agendar una cita") == RiskLevel.NONE
