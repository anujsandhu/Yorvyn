"""
Yorvyn Fashion Intelligence Module
"""
from .routes_fashion import router as fashion_router
from .garment_3d import garment_3d_router

__all__ = ["fashion_router", "garment_3d_router"]
