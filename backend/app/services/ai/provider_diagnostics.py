"""Public diagnostic codes. Upstream error bodies may contain credentials or user input."""
from contextlib import contextmanager
import json

import requests


def http_failure(response):
    status = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    detail = json.dumps(error).casefold()
    if status == 401 or any(token in detail for token in (
            "api_key_invalid", "api key not valid", "invalid_api_key", "invalid api key", "key expired")):
        return "INVALID_CREDENTIAL"
    if status == 403:
        return "PERMISSION_DENIED"
    if status == 429 and any(token in detail for token in ("perminute", "per_minute", "per minute", "per second")) and "limit: 0" not in detail:
        return "RATE_LIMIT"
    if status == 402 or any(token in detail for token in (
            "insufficient_quota", "billing_hard_limit", "insufficient credits", "insufficient_balance", "quota_exceeded", "exceeded your current quota",
            "perday", "per_day", "daily quota", "limit: 0")):
        return "QUOTA_EXHAUSTED"
    if status == 429:
        return "RATE_LIMIT"
    if status in (408, 504):
        return "TIMEOUT"
    if status in (400, 404, 415, 422):
        if status == 415 or any(token in detail for token in (
                "modality", "modalities", "image input", "image_url", "does not support image", "vision is not supported")):
            return "UNSUPPORTED_MODALITY"
        if any(token in detail for token in ("model_not_found", "not a valid model", "model_decommissioned",
                                              "model_not_supported", "no endpoints found")) or (
                "model" in detail and any(t in detail for t in ("not found", "not supported", "does not exist"))):
            return "UNSUPPORTED_MODEL"
        if status in (400, 422):
            return "INVALID_REQUEST_SCHEMA"
    return "HTTP_ERROR"


def exception_failure(exc):
    if isinstance(exc, requests.exceptions.SSLError):
        return "TLS_FAILED"
    if isinstance(exc, (requests.Timeout, TimeoutError)):
        return "TIMEOUT"
    if isinstance(exc, (AttributeError, ValueError, IndexError, KeyError, TypeError)):
        return "MALFORMED_OUTPUT"
    if isinstance(exc, requests.RequestException):
        return "NETWORK_FAILURE"
    return "CLIENT_EXCEPTION"


class ProviderHTTPError(RuntimeError):
    def __init__(self, status_code, request_id=None, code="HTTP_ERROR"):
        self.status_code = status_code
        self.request_id = request_id
        self.upstream_model = None
        self.code = code
        super().__init__(f"Provider returned HTTP {status_code} ({code})")

    @classmethod
    def from_response(cls, response):
        return cls(response.status_code, response.headers.get("x-request-id"), http_failure(response))


@contextmanager
def response_body(response, model_field, id_field):
    """Keep the receipt if a successful HTTP response fails decoding or schema validation."""
    data = {}
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        yield data
    except (ValueError, IndexError, KeyError, TypeError, AttributeError) as exc:
        fields = data if isinstance(data, dict) else {}
        error = ProviderHTTPError(response.status_code, response.headers.get("x-request-id") or fields.get(id_field),
                                  "MALFORMED_OUTPUT")
        error.upstream_model = fields.get(model_field)
        raise error from exc
