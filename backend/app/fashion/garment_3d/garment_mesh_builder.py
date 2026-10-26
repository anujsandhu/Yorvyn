"""Backward-compatibility forwarder for garment_mesh_builder."""
from backend.app.services.garments.garment_mesh_builder import *
from backend.app.services.garments.garment_mesh_builder import garment_mesh_builder, GarmentMesh

__all__ = ["garment_mesh_builder", "GarmentMesh"]
