import pytest

from src.classifier import Action, Category, RiskLevel, classify


@pytest.mark.parametrize(
    ("message", "category", "action", "minimum_confidence"),
    [
        (
            "Hola, necesito agendar cita con psiquiatria",
            Category.SOLICITUD_CITA,
            Action.SOLICITAR_INFO,
            0.80,
        ),
        ("Quiero una cita", Category.SOLICITUD_CITA, Action.SOLICITAR_INFO, 0.80),
        (
            "Necesito cancelar mi cita del jueves",
            Category.SOLICITUD_CITA,
            Action.SOLICITAR_INFO,
            0.80,
        ),
        (
            "Reprogramar la consulta con el dr. Mendez",
            Category.SOLICITUD_CITA,
            Action.SOLICITAR_INFO,
            0.80,
        ),
        (
            "Olvide tomar la sertralina anoche, que hago?",
            Category.CONSULTA_CLINICA,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        (
            "Llevo tres dias sin dormir y me siento muy ansiosa",
            Category.CONSULTA_CLINICA,
            Action.ESCALAR_HUMANO,
            0.80,
        ),
        (
            "Es la tercera vez que llamo y nadie atiende, voy a poner queja",
            Category.PQR,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        ("Solicito copia de mi historia clinica", Category.PQR, Action.ESCALAR_HUMANO, 0.80),
        (
            "Me cobraron mal la consulta, exijo devolucion",
            Category.PQR,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        (
            "Cuales son los horarios de atencion los sabados?",
            Category.INFO_ADMINISTRATIVA,
            Action.RESPONDER_AUTOMATICO,
            0.85,
        ),
        ("Donde estan ubicados?", Category.INFO_ADMINISTRATIVA, Action.RESPONDER_AUTOMATICO, 0.85),
        ("Atienden por Sanitas?", Category.INFO_ADMINISTRATIVA, Action.RESPONDER_AUTOMATICO, 0.80),
        (
            "Cuanto cuesta una consulta particular?",
            Category.INFO_ADMINISTRATIVA,
            Action.RESPONDER_AUTOMATICO,
            0.85,
        ),
        (
            "Como solicito autorizacion de mi EPS?",
            Category.INFO_ADMINISTRATIVA,
            Action.RESPONDER_AUTOMATICO,
            0.80,
        ),
        ("Hola buenas tardes", Category.NO_RELEVANTE, Action.RESPONDER_AUTOMATICO, 0.90),
        ("Gracias", Category.NO_RELEVANTE, Action.RESPONDER_AUTOMATICO, 0.90),
        ("GANA 500.000 PESOS YA! Click: bit.ly/abc", Category.NO_RELEVANTE, Action.IGNORAR, 0.90),
        ("test 123", Category.NO_RELEVANTE, Action.IGNORAR, 0.90),
        ("asdfgh", Category.NO_RELEVANTE, Action.IGNORAR, 0.90),
        (
            "Estoy en la sede pero no encuentro psiquiatria, donde queda",
            Category.INFO_ADMINISTRATIVA,
            Action.RESPONDER_AUTOMATICO,
            0.80,
        ),
        (
            "Cuando entregan el certificado de incapacidad",
            Category.INFO_ADMINISTRATIVA,
            Action.RESPONDER_AUTOMATICO,
            0.80,
        ),
        ("kskskskskskksksksks", Category.NO_RELEVANTE, Action.IGNORAR, 0.80),
        (
            "Voy a demandar a esta clinica, son unos irresponsables",
            Category.PQR,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        (
            "Estoy embarazada y tomando aripiprazol, es riesgoso?",
            Category.CONSULTA_CLINICA,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        (
            "Mi hijo de 14 anos esta muy deprimido, que hago",
            Category.CONSULTA_CLINICA,
            Action.ESCALAR_HUMANO,
            0.85,
        ),
        (
            "Hola, mi mama tiene 70 anos y necesita psiquiatra. Tiene Sura",
            Category.SOLICITUD_CITA,
            Action.SOLICITAR_INFO,
            0.80,
        ),
    ],
)
def test_required_policy_matrix(
    monkeypatch, message: str, category: Category, action: Action, minimum_confidence: float
) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "false")
    result = classify(message)
    assert result.category == category
    assert result.suggested_action == action
    assert result.confidence >= minimum_confidence
    assert result.metadata.model_used == "local_policy_v1"


@pytest.mark.parametrize("message", ["", "    "])
def test_empty_messages_are_ignored_without_model(monkeypatch, message: str) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "false")
    result = classify(message)
    assert result.category == Category.NO_RELEVANTE
    assert result.suggested_action == Action.IGNORAR
    assert result.confidence == 1.0
    assert result.metadata.model_used is None


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("Hi, I need to book an appointment with a psychiatrist", "en"),
        ("Bonjour, je voudrais prendre rendez-vous", "fr"),
    ],
)
def test_foreign_language_appointment_goes_to_human(
    monkeypatch, message: str, language: str
) -> None:
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "false")
    result = classify(message)
    assert result.category == Category.SOLICITUD_CITA
    assert result.suggested_action == Action.ESCALAR_HUMANO
    assert result.metadata.detected_language == language


@pytest.mark.parametrize(
    ("message", "risk"),
    [
        ("Ya no le veo sentido a nada, mejor desaparecer", RiskLevel.MEDIUM),
        ("Me quiero matar, ya tengo las pastillas", RiskLevel.CRITICAL),
        ("Ayer pense en hacerme dano pero hoy estoy mejor", RiskLevel.HIGH),
        ("Me corte anoche pero no fue grave", RiskLevel.HIGH),
    ],
)
def test_required_crisis_matrix(message: str, risk: RiskLevel) -> None:
    result = classify(message)
    assert result.category == Category.CONSULTA_CLINICA
    assert result.suggested_action == Action.ESCALAR_CRISIS
    assert result.metadata.risk_level == risk


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("Necesito ayuda urgente", Category.CONSULTA_CLINICA),
        ("Necesito cita YA, me siento muy mal", Category.SOLICITUD_CITA),
        ("Llame tres veces, nadie atiende, que horarios tienen", Category.PQR),
        ("Me siento triste pero ya estoy mejor que antes", Category.CONSULTA_CLINICA),
    ],
)
def test_ambiguous_cases_have_low_confidence(message: str, category: Category) -> None:
    result = classify(message)
    assert result.category == category
    assert result.confidence < 0.70


def test_movie_reference_is_not_crisis() -> None:
    result = classify("Vi una pelicula sobre suicidio, que triste")
    assert result.category == Category.NO_RELEVANTE
    assert result.suggested_action == Action.ESCALAR_HUMANO
    assert result.suggested_action != Action.ESCALAR_CRISIS
