"""Count real transport attempts only while an owned garment turn is executing."""
import math
import time
import requests
from .garment_execution import current_execution


def post(provider, url, *, retry=False, **kwargs):
    context = current_execution.get()
    if context is None:
        return requests.post(url, **kwargs)
    record = {"provider": provider, "retry": int(retry), "input_tokens": None, "output_tokens": None}
    context.requests.append(record)
    start = time.monotonic()
    try:
        response = requests.post(url, **kwargs)
        record["http_status"] = response.status_code
        if response.ok:
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict):
                usage = data.get("usage") or data.get("usageMetadata")
                if isinstance(usage, dict):
                    billed = usage.get("cost_usd")
                    if type(billed) in (float, int) and math.isfinite(billed) and billed >= 0:
                        record["billed_usd"] = billed
                    record["input_tokens"] = usage.get("prompt_tokens", usage.get("promptTokenCount"))
                    record["output_tokens"] = usage.get("completion_tokens", usage.get("candidatesTokenCount"))
                record["model"] = data.get("model") or data.get("modelVersion")
                record["request_id"] = response.headers.get("x-request-id") or data.get("responseId") or data.get("id")
        return response
    except requests.RequestException as exc:
        from backend.app.services.ai.provider_diagnostics import exception_failure
        record["error"] = exception_failure(exc)
        raise
    finally:
        record["duration_ms"] = round((time.monotonic() - start) * 1000, 3)
