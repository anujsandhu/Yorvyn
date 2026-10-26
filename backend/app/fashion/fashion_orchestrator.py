"""Backward-compatibility forwarder for fashion_orchestrator."""
from backend.app.services.fashion_orchestrator import *
from backend.app.services.fashion_orchestrator import fashion_orchestrator, FashionOrchestrator

__all__ = ["fashion_orchestrator", "FashionOrchestrator"]
