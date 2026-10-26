"""Backward-compatibility forwarder for garment_texture_synthesizer."""
from backend.app.services.garments.garment_texture_synthesizer import *
from backend.app.services.garments.garment_texture_synthesizer import garment_texture_synthesizer, GarmentTextureSynthesizer

__all__ = ["garment_texture_synthesizer", "GarmentTextureSynthesizer"]
