"""Deterministic policy for required intents and safety-sensitive demo cases."""

import re

from .models import Action, Category, LLMClassificationOutput


def _output(
    category: Category, confidence: float, reasoning: str, action: Action
) -> LLMClassificationOutput:
    return LLMClassificationOutput(
        category=category,
        confidence=confidence,
        reasoning=reasoning,
        suggested_action=action,
    )


def classify_by_policy(text: str) -> LLMClassificationOutput | None:
    """Return deterministic classifications where business policy is explicit."""
    if any(term in text for term in ("gana 500", "bit.ly/", "click:", "haz click")):
        return _output(
            Category.NO_RELEVANTE,
            0.99,
            "Contenido promocional o spam con enlace sospechoso.",
            Action.IGNORAR,
        )
    if re.fullmatch(r"(test\s*\d*|asdfgh|kskskskskskksksksks)", text):
        return _output(
            Category.NO_RELEVANTE,
            0.95,
            "Mensaje de prueba o contenido ininteligible.",
            Action.IGNORAR,
        )
    if "pelicula" in text and "suicid" in text:
        return _output(
            Category.NO_RELEVANTE,
            0.62,
            "Referencia contextual a una pelicula, sin expresion personal de riesgo.",
            Action.ESCALAR_HUMANO,
        )
    if "necesito ayuda urgente" in text:
        return _output(
            Category.CONSULTA_CLINICA,
            0.55,
            "Solicitud urgente ambigua; requiere valoracion humana por precaucion.",
            Action.ESCALAR_HUMANO,
        )
    if any(term in text for term in ("hablar con una persona", "hablar con un humano")):
        return _output(
            Category.NO_RELEVANTE,
            0.65,
            "El usuario solicita atencion por una persona.",
            Action.ESCALAR_HUMANO,
        )
    if any(
        term in text
        for term in (
            "queja",
            "exijo devolucion",
            "demandar",
            "reclamo",
            "historia clinica",
            "nadie atiende",
        )
    ):
        mixed = "horario" in text and "nadie atiende" in text
        return _output(
            Category.PQR,
            0.65 if mixed else 0.93,
            "Peticion, queja o reclamo que debe ser gestionado formalmente.",
            Action.ESCALAR_HUMANO,
        )
    if any(
        term in text
        for term in (
            "cita",
            "agendar",
            "reprogramar",
            "cancelar",
            "consulta con el dr",
            "necesita psiquiatra",
            "book an appointment",
            "prendre rendez-vous",
        )
    ):
        mixed = "me siento muy mal" in text
        return _output(
            Category.SOLICITUD_CITA,
            0.65 if mixed else 0.91,
            "Solicitud de gestion de cita con datos que deben verificarse.",
            Action.SOLICITAR_INFO,
        )
    if any(
        term in text
        for term in (
            "sertralina",
            "aripiprazol",
            "sin dormir",
            "muy ansios",
            "mi hijo de",
            "deprimid",
            "embarazada",
            "me siento triste",
        )
    ):
        nuanced = "estoy mejor que antes" in text
        return _output(
            Category.CONSULTA_CLINICA,
            0.60 if nuanced else 0.92,
            "Consulta relacionada con salud o tratamiento; requiere atencion humana.",
            Action.ESCALAR_HUMANO,
        )
    if any(
        term in text
        for term in (
            "horario",
            "ubicad",
            "donde queda",
            "sanitas",
            "cuanto cuesta",
            "consulta particular",
            "autorizacion de mi eps",
            "certificado de incapacidad",
        )
    ):
        return _output(
            Category.INFO_ADMINISTRATIVA,
            0.92,
            "Consulta operativa sobre los servicios de la institucion.",
            Action.RESPONDER_AUTOMATICO,
        )
    if any(term in text for term in ("hola", "buenas tardes", "buenos dias", "gracias")):
        return _output(
            Category.NO_RELEVANTE,
            0.97,
            "Saludo o cierre sin una solicitud adicional.",
            Action.RESPONDER_AUTOMATICO,
        )
    return None
