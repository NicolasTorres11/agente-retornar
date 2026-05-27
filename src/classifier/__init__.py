"""Public interface for the message classifier."""

from .classify import classify
from .models import Action, Category, ClassificationResult, RiskLevel

__all__ = ["Action", "Category", "ClassificationResult", "RiskLevel", "classify"]
