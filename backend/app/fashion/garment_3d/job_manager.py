"""Backward-compatibility forwarder for job_manager."""
from backend.app.services.garments.job_manager import *
from backend.app.services.garments.job_manager import garment_job_manager, PERMANENT_ASSET_DIR

__all__ = ["garment_job_manager", "PERMANENT_ASSET_DIR"]
