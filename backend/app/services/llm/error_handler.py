"""
LLM Error Handler & Graceful Recovery for Yorvyn LLM Architecture.
Classifies external provider errors and orchestrates fallback recovery.
"""

from __future__ import annotations

import requests
import logging
from backend.app.services.ai.provider_diagnostics import ProviderHTTPError, exception_failure
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LLMErrorType(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "authentication_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    UNKNOWN = "unknown"
    BLOCKED_NO_CREDENTIALS = "blocked_no_credentials"
    INVALID_CREDENTIAL = "invalid_credential"
    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED_MODEL = "unsupported_model"
    UNSUPPORTED_MODALITY = "unsupported_modality"
    INVALID_REQUEST_SCHEMA = "invalid_request_schema"
    QUOTA_EXHAUSTED = "quota_exhausted"
    NETWORK_FAILURE = "network_failure"
    TLS_FAILED = "tls_failed"
    MALFORMED_OUTPUT = "malformed_output"
    HTTP_ERROR = "http_error"


class LLMErrorHandler:
    """Classifies errors and generates user-safe fallback explanations."""

    @staticmethod
    def classify_exception(exc: Exception) -> LLMErrorType:
        """Determines category of an encountered exception."""
        if isinstance(exc, ProviderHTTPError):
            return LLMErrorType.__members__.get(exc.code, LLMErrorType.UNKNOWN)
        if isinstance(exc, (requests.RequestException, TimeoutError)):
            return LLMErrorType.__members__.get(exception_failure(exc), LLMErrorType.UNKNOWN)
        text = str(exc).lower()
        if "not configured" in text and "api key" in text:
            return LLMErrorType.BLOCKED_NO_CREDENTIALS
        if "timeout" in text or "timed out" in text:
            return LLMErrorType.TIMEOUT
        if "429" in text or "rate limit" in text or "quota" in text:
            return LLMErrorType.RATE_LIMIT
        if "401" in text or "403" in text or "unauthorized" in text or "api key" in text:
            return LLMErrorType.AUTHENTICATION_ERROR
        if "connection" in text or "500" in text or "502" in text or "503" in text:
            return LLMErrorType.PROVIDER_UNAVAILABLE
        if "validation" in text or "json" in text:
            return LLMErrorType.SCHEMA_VALIDATION_ERROR
        return LLMErrorType.UNKNOWN

    @classmethod
    def create_fallback_response(
        cls,
        error_type: LLMErrorType,
        user_message: str,
        details: Optional[str] = None
    ) -> Dict[str, Any]:
        """Produces a helpful, grounded stylist response when a remote provider fails."""
        logger.warning("Activating LLM fallback for %s", error_type.value)

        fallbacks = {
            LLMErrorType.TIMEOUT: (
                "Our deep reasoning engine experienced high network latency, but I've assembled a curated "
                "outfit for you based directly on your Fashion DNA and color palette."
            ),
            LLMErrorType.RATE_LIMIT: (
                "Due to high stylist consultation volume, I've switched to our deterministic fashion rules engine "
                "to provide your recommendation instantly without interruption."
            ),
            LLMErrorType.AUTHENTICATION_ERROR: (
                "Stylist credentials are being refreshed. Using local haute couture knowledge rules "
                "to harmonize your wardrobe."
            ),
            LLMErrorType.PROVIDER_UNAVAILABLE: (
                "The cloud styling provider is temporarily unreachable. Switching to offline fashion intelligence."
            ),
            LLMErrorType.SCHEMA_VALIDATION_ERROR: (
                "Generated styling advice was sanitized to guarantee strictly valid wardrobe items."
            ),
            LLMErrorType.UNKNOWN: (
                "Here is a tailored styling suggestion curated from your digital wardrobe."
            )
        }

        return {
            "content": fallbacks.get(error_type, fallbacks[LLMErrorType.UNKNOWN]),
            "error_type": error_type.value,
            "is_fallback": True,
            "provider_used": "offline_rules_fallback"
        }

