"""
Abstract Base Interfaces and Data Structures for Yorvyn LLM Architecture.
Enables provider-independent LLM calling with tool-use, token usage tracking,
and structured outputs.
"""

from __future__ import annotations

from backend.app.services.ai.provider_diagnostics import ProviderHTTPError

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    """Structured tool execution request emitted by an LLM."""
    id: str = Field(..., description="Unique tool call execution identifier.")
    function_name: str = Field(..., description="Target tool name to invoke.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parsed arguments matching tool input schema.")


class LLMMessage(BaseModel):
    """Individual conversational turn in a multi-turn chat."""
    role: str = Field(..., description="user, assistant, system, or tool.")
    content: str = Field("", description="Text content of the message.")
    tool_calls: Optional[List[ToolCallRequest]] = Field(None, description="Tool calls initiated by assistant.")
    tool_call_id: Optional[str] = Field(None, description="Referenced tool call ID if role is tool.")
    name: Optional[str] = Field(None, description="Optional name of the tool or persona.")


class ToolDefinition(BaseModel):
    """Specification of an authenticated backend tool exposed to the LLM."""
    name: str
    description: str
    parameters_schema: Dict[str, Any]


class LLMResponse(BaseModel):
    """Unified response payload returned by any LLM provider."""
    upstream_request_id: Optional[str] = None
    upstream_model: Optional[str] = None
    usage_reported: bool = False
    content: str = Field("", description="Generated natural language response.")
    tool_calls: List[ToolCallRequest] = Field(default_factory=list, description="Requested tool invocations.")
    provider_used: str = Field(..., description="Name of the provider that produced this response.")
    model_used: str = Field(..., description="Exact model version identifier.")
    prompt_tokens: int = Field(0, description="Estimated or actual input token count.")
    completion_tokens: int = Field(0, description="Estimated or actual completion token count.")
    latency_ms: float = Field(0.0, description="Wall-clock inference time in milliseconds.")
    finish_reason: Optional[str] = Field("stop", description="stop, tool_calls, length, error.")


class LLMProvider(ABC):
    """Abstract interface that all LLM provider adapters must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns unique identifier for this provider."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 800,
        timeout_seconds: int = 15
    ) -> LLMResponse:
        """Executes completion or tool calling against provider API."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verifies API connectivity and credentials validity."""
        pass

