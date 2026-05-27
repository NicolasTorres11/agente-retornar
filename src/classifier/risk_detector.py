"""Conservative local risk detector executed before any LLM call."""

import re
from dataclasses import dataclass

from .models import RiskLevel


@dataclass(frozen=True)
class RiskDetection:
    level: RiskLevel
    triggers: list[str]


_CRITICAL = [
    r"\btengo\s+(las\s+)?(pastillas|pistola|cuerda|veneno)\b",
    r"\bvoy\s+a\s+saltar\b",
    r"\besta\s+noche\b.*\b(me\s+mato|suicid|hacerme\s+dano)\b",
]
_HIGH = [
    r"\bme\s+(quiero|voy\s+a)\s+(matar|suicidar)\b",
    r"\b(quiero|deseo)\s+(morir|morirme|estar\s+muert[oa])\b",
    r"\bsuicidarme\b",
    r"\bquitarme\s+la\s+vida\b",
    r"\bya\s+no\s+quiero\s+(vivir|seguir|estar\s+aqui)\b",
    r"\bme\s+(corto|hago\s+dano|lastimo)\b",
    r"\b(me\s+corte|cortarme|hacerme\s+dano)\b",
    r"\b(pense|pensaba)\s+en\s+hacerme\s+dano\b",
]
_MEDIUM = [
    r"\bya\s+no\s+(puedo|aguanto|soporto)\s+mas\b",
    r"\bno\s+(le\s+)?veo\s+sentido\s+a\s+(nada|la\s+vida|esto)\b",
    r"\bsoy\s+una\s+carga\b",
    r"\bmejor\s+(desaparecer|desaparezco|no\s+estar)\b",
    r"\bsin\s+esperanza\b",
]
_LOW = [
    r"\b(muy\s+)?(triste|ansios[oa]|deprimid[oa])\b",
    r"\bllorando\b",
    r"\bme\s+siento\s+(mal|fatal|horrible)\b",
    r"\bno\s+(puedo|logro)\s+dormir\b",
]
_NEGATED_ACTIVE = re.compile(
    r"\b(no\s+quiero\s+morir|ya\s+no\s+quiero\s+morir|antes\s+pensaba\s+en\s+"
    r"(suicidarme|hacerme\s+dano))\b"
)


def _matches(text: str, patterns: list[str]) -> list[str]:
    return [match.group(0) for pattern in patterns if (match := re.search(pattern, text))]


def detect_risk(searchable_text: str) -> RiskDetection:
    for level, patterns in (
        (RiskLevel.CRITICAL, _CRITICAL),
        (RiskLevel.HIGH, _HIGH),
        (RiskLevel.MEDIUM, _MEDIUM),
        (RiskLevel.LOW, _LOW),
    ):
        triggers = _matches(searchable_text, patterns)
        if triggers:
            if level in (RiskLevel.CRITICAL, RiskLevel.HIGH) and _NEGATED_ACTIVE.search(
                searchable_text
            ):
                return RiskDetection(RiskLevel.MEDIUM, triggers)
            return RiskDetection(level, triggers)
    return RiskDetection(RiskLevel.NONE, [])
