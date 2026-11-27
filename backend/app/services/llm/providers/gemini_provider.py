"""
Google Gemini LLM Provider Adapter for Yorvyn LLM Architecture.
Connects to Google Generative Language API with tool/function declaration support.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
import requests
from backend.app.services.intelligence import provider_meter

from backend.app.services.ai.provider_diagnostics import response_body
from backend.app.core.settings import settings
from backend.app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderHTTPError,
    ToolCallRequest,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Adapter for Google Gemini REST API."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self._api_key = api_key or settings.effective_google_key
        self.default_model = default_model or settings.gemini_model

    @property
    def provider_name(self) -> str:
        return "gemini"

    def health_check(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("AIzaSyDummy") and not self._api_key.startswith("your_"))

    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.5,
        max_tokens: int = 800,
        timeout_seconds: int = 15
    ) -> LLMResponse:
        """Executes content generation against Gemini API."""
        if not self.health_check():
            raise ValueError("Gemini API key is not configured or contains placeholder.")

        start_time = time.time()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.default_model}:generateContent"

        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        for m in messages:
            if m.role == "system":
                system_instruction = {"parts": [{"text": m.content}]}
            elif m.role == "user":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                parts: List[Dict[str, Any]] = []
                if m.content:
                    parts.append({"text": m.content})
                if m.tool_calls:
                    for tc in m.tool_calls:
                        parts.append({"functionCall": {"name": tc.function_name, "args": tc.arguments}})
                contents.append({"role": "model", "parts": parts})
            elif m.role == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": m.name or "tool_result",
                            "response": {"output": m.content}
                        }
                    }]
                })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if tools:
            payload["tools"] = [{
                "functionDeclarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parametersJsonSchema": t.parameters_schema
                    }
                    for t in tools
                ]
            }]

        headers = {"Content-Type": "application/json"}
        resp = provider_meter.post("gemini", url, json=payload, headers={**headers, "x-goog-api-key": self._api_key}, timeout=timeout_seconds)
        elapsed_ms = (time.time() - start_time) * 1000

        if resp.status_code != 200:
            raise ProviderHTTPError.from_response(resp)

        with response_body(resp, "modelVersion", "responseId") as data:
            candidates = data.get("candidates", [{}])
            first_cand = candidates[0] if candidates else {}
            content_obj = first_cand.get("content", {})
            parts = content_obj.get("parts", [])

            text_content = ""
            tool_calls: List[ToolCallRequest] = []

            for p in parts:
                if "text" in p:
                    text_content += p["text"]
                if "functionCall" in p:
                    fc = p["functionCall"]
                    tool_calls.append(ToolCallRequest(
                        id=f"gemini_call_{int(time.time()*1000)}",
                        function_name=fc.get("name", ""),
                        arguments=fc.get("args", {})
                    ))

            usage = data.get("usageMetadata", {})
            prompt_tokens = usage.get("promptTokenCount", 0)
            completion_tokens = usage.get("candidatesTokenCount", 0)

            return LLMResponse(
                content=text_content,
                tool_calls=tool_calls,
                provider_used=self.provider_name,
                model_used=data.get("modelVersion") or self.default_model,
                usage_reported=bool(usage),
                upstream_model=data.get("modelVersion"),
                upstream_request_id=resp.headers.get("x-request-id") or data.get("responseId"),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=elapsed_ms,
                finish_reason="tool_calls" if tool_calls else "stop"
            )
