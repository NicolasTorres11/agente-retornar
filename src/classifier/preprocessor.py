"""Text cleanup and lightweight language detection."""

import unicodedata
from dataclasses import dataclass

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0
MAX_MESSAGE_LENGTH = 2000


@dataclass(frozen=True)
class PreprocessedMessage:
    text: str
    searchable_text: str
    detected_language: str | None
    is_empty: bool
    was_truncated: bool


def normalize_for_search(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _detect_language(text: str) -> str | None:
    searchable = normalize_for_search(text)
    spanish_markers = (
        "quiero",
        "necesito",
        "cita",
        "hola",
        "horario",
        "atencion",
        "psiquiatria",
        "queja",
        "pastillas",
        "hacerme dano",
        "sentido a nada",
    )
    if any(marker in searchable for marker in spanish_markers):
        return "es"
    if len(text.split()) < 3:
        return None
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return None
    if not candidates or candidates[0].prob < 0.70:
        return None
    return candidates[0].lang


def preprocess(message: str, language_hint: str | None = None) -> PreprocessedMessage:
    cleaned = unicodedata.normalize("NFKC", message).strip()
    if not cleaned:
        return PreprocessedMessage("", "", language_hint, True, False)
    was_truncated = len(cleaned) > MAX_MESSAGE_LENGTH
    cleaned = cleaned[:MAX_MESSAGE_LENGTH]
    language = language_hint or _detect_language(cleaned)
    return PreprocessedMessage(
        text=cleaned,
        searchable_text=normalize_for_search(cleaned),
        detected_language=language,
        is_empty=False,
        was_truncated=was_truncated,
    )
