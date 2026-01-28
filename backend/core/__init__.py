"""Core module - configuration and logging."""

from .config import settings
from .logging import setup_logging, get_logger

__all__ = ["settings", "setup_logging", "get_logger"]
