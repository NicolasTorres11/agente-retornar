"""Deterministic local rules for demos without Azure credentials."""

from .models import Action, Category, LLMClassificationOutput


def classify_offline(text: str) -> LLMClassificationOutput:
    if any(
        word in text
        for word in ("cita", "agendar", "reprogramar", "cancelar", "appointment", "book")
    ):
        action = (
            Action.SOLICITAR_INFO
            if "cita" in text and not any(item in text for item in ("psiqu", "psico", "control"))
            else Action.RESPONDER_AUTOMATICO
        )
        return LLMClassificationOutput(
            category=Category.SOLICITUD_CITA,
            confidence=0.88,
            reasoning="El mensaje solicita gestionar una cita.",
            suggested_action=action,
        )
    if any(word in text for word in ("medic", "sertralina", "ansios", "sintoma", "deprim")):
        return LLMClassificationOutput(
            category=Category.CONSULTA_CLINICA,
            confidence=0.88,
            reasoning="El mensaje contiene una consulta relacionada con salud o tratamiento.",
            suggested_action=Action.ESCALAR_HUMANO,
        )
    if any(word in text for word in ("queja", "reclamo", "demand", "inaceptable", "cobraron")):
        return LLMClassificationOutput(
            category=Category.PQR,
            confidence=0.91,
            reasoning="El usuario manifiesta una inconformidad o reclamacion.",
            suggested_action=Action.ESCALAR_HUMANO,
        )
    if any(
        word in text
        for word in (
            "horario",
            "direccion",
            "ubic",
            "sede",
            "sanitas",
            "eps",
            "cuanto cuesta",
        )
    ):
        return LLMClassificationOutput(
            category=Category.INFO_ADMINISTRATIVA,
            confidence=0.90,
            reasoning="El usuario solicita informacion administrativa.",
            suggested_action=Action.RESPONDER_AUTOMATICO,
        )
    if any(word in text for word in ("hola", "buenos dias", "buenas tardes", "gracias")):
        return LLMClassificationOutput(
            category=Category.NO_RELEVANTE,
            confidence=0.95,
            reasoning="Saludo o cierre sin una solicitud adicional.",
            suggested_action=Action.RESPONDER_AUTOMATICO,
        )
    return LLMClassificationOutput(
        category=Category.NO_RELEVANTE,
        confidence=0.55,
        reasoning="No se identifica una solicitud especifica con certeza.",
        suggested_action=Action.ESCALAR_HUMANO,
    )
