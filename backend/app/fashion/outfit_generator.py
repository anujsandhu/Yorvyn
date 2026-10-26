"""Backward-compatibility forwarder for outfit_generator."""
from backend.app.services.outfit_generator import *
from backend.app.services.outfit_generator import outfit_generator, OutfitGenerator

__all__ = ["outfit_generator", "OutfitGenerator"]
