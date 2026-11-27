"""
Groq LLM Provider Adapter for Yorvyn LLM Architecture.
Connects to Groq Cloud API for ultra-low-latency Llama 3 / Mixtral inference
with tool calling and structured parameters.
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


class GroqProvider(LLMProvider):
    """Adapter for Groq Cloud API."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self._api_key = api_key or settings.groq_api_key
        self.default_model = default_model or settings.groq_model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "groq"

    def health_check(self) -> bool:
        """Returns True if Groq API key is configured with real credentials."""
        return bool(self._api_key and not self._api_key.startswith("gsk_your"))

    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.5,
        max_tokens: int = 800,
        timeout_seconds: int = 15
    ) -> LLMResponse:
        """Executes chat completion with Groq API."""
        if not self.health_check():
            raise ValueError("Groq API key is not configured or contains placeholder.")

        start_time = time.time()

        # Format messages for OpenAI compatibility
        formatted_messages = []
        for m in messages:
            msg_dict: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in m.tool_calls
                ]
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            if m.name:
                msg_dict["name"] = m.name
            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": self.default_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Format tools if provided
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema
                    }
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        resp = provider_meter.post("groq", self.endpoint, json=payload, headers=headers, timeout=timeout_seconds)
        elapsed_ms = (time.time() - start_time) * 1000

        if resp.status_code != 200:
            raise ProviderHTTPError.from_response(resp)

        with response_body(resp, "model", "id") as data:
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            finish_reason = choice.get("finish_reason", "stop")

            tool_calls: List[ToolCallRequest] = []
            if "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except (ValueError, TypeError):
                        parsed_args = {}
                    tool_calls.append(ToolCallRequest(
                        id=tc.get("id", f"call_{int(time.time()*1000)}"),
                        function_name=fn_name,
                        arguments=parsed_args
                    ))

            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                provider_used=self.provider_name,
                model_used=data.get("model") or self.default_model,
                usage_reported=bool(usage),
                upstream_model=data.get("model"),
                upstream_request_id=resp.headers.get("x-request-id") or data.get("id"),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=elapsed_ms,
                finish_reason=finish_reason
            )
