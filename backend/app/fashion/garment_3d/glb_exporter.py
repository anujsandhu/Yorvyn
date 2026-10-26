"""Backward-compatibility forwarder for glb_exporter."""
from backend.app.services.garments.glb_exporter import *
from backend.app.services.garments.glb_exporter import glb_exporter, GLBExporter

__all__ = ["glb_exporter", "GLBExporter"]
