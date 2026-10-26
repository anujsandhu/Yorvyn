"""Backward-compatibility forwarder for context_service."""
from backend.app.services.context_service import *
from backend.app.services.context_service import context_service, ContextService

__all__ = ["context_service", "ContextService"]
