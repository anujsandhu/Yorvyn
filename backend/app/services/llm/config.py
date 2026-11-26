"""
Configuration Models for Yorvyn LLM Architecture.
Allows dynamic selection of providers, models, timeouts, and generation parameters.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from backend.app.core.settings import settings


class LLMConfiguration(BaseModel):
    """Runtime configuration for LLM requests."""
    primary_provider: str = Field(
        default="groq",
        description="Default provider to attempt: groq, gemini, openrouter, or offline_rules."
    )
    fallback_provider: str = Field(
        default="offline_rules",
        description="Fallback provider if primary fails or is unconfigured."
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Override specific model ID (e.g. llama-3.3-70b-versatile, gemini-1.5-flash)."
    )
    temperature: float = Field(0.5, ge=0.0, le=2.0)
    max_tokens: int = Field(800, ge=50, le=4096)
    timeout_seconds: int = Field(12, ge=2, le=60)
    enable_tools: bool = Field(True, description="Whether to expose backend tools to the model.")

    @classmethod
    def from_settings(cls) -> "LLMConfiguration":
        """Instantiates default configuration based on environment settings."""
        provider = getattr(settings, "ai_primary_provider", "groq")
        return cls(
            primary_provider=provider,
            fallback_provider="offline_rules",
            timeout_seconds=getattr(settings, "ai_timeout_seconds", 12),
            max_tokens=getattr(settings, "ai_max_response_tokens", 800)
        )

