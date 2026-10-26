"""Backward-compatibility forwarder for wardrobe_service."""
from backend.app.services.wardrobe_service import *
from backend.app.services.wardrobe_service import wardrobe_service, DigitalWardrobeService

__all__ = ["wardrobe_service", "DigitalWardrobeService"]
