"""
Backward-compatibility forwarder for backend.app.auth.
Imports from backend.app.core.security.
"""
from backend.app.core.security import UserContext, get_current_user, get_optional_user

__all__ = ["UserContext", "get_current_user", "get_optional_user"]
