"""API routes."""

from .analyze import router as analyze_router
from .googlebot import router as googlebot_router
from .health import router as health_router

__all__ = ["analyze_router", "googlebot_router", "health_router"]
