"""Backward-compatibility forwarder for garment_analyzer."""
from backend.app.services.garments.garment_analyzer import *
from backend.app.services.garments.garment_analyzer import garment_analyzer

__all__ = ["garment_analyzer"]
