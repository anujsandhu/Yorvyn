"""
Backward-compatibility forwarder for backend.app.config.
Imports from backend.app.core.settings.
"""
from backend.app.core.settings import (
    Settings,
    settings,
    BASE_DIR
)

__all__ = ["Settings", "settings", "BASE_DIR"]
