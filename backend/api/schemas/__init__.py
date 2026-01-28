"""API schemas - Pydantic models for request/response validation."""

from .responses import (
    HreflangEntry,
    SEOData,
    CloakingData,
    AnalyzeResponse,
    GooglebotViewResponse,
    HealthResponse,
)

__all__ = [
    "HreflangEntry",
    "SEOData",
    "CloakingData",
    "AnalyzeResponse",
    "GooglebotViewResponse",
    "HealthResponse",
]
