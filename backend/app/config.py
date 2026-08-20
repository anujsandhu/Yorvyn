"""
Application configuration for Yorvyn AI Fashion Intelligence Platform.
Reads from environment variables or .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── App Info ──────────────────────────────────────────────────────
    app_name: str = "Yorvyn Fashion AI"
    app_version: str = "3.0.0"
    environment: str = "development"
    debug: bool = True
    api_v1_str: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────
    # Default to local SQLite for zero-config quickstart, easily switched to PostgreSQL + pgvector
    database_url: str = "sqlite:///./yorvyn.db"
    async_database_url: str = "sqlite+aiosqlite:///./yorvyn.db"
    enable_pgvector: bool = False

    # ── Storage & Media ───────────────────────────────────────────────
    media_storage_path: str = str(BASE_DIR / "uploads")
    max_upload_size_mb: int = 15

    # ── AI Providers (Groq, Gemini, OpenRouter, OpenAI, HF) ───────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-3-12b-it:free"

    google_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    hf_api_key: str = ""
    hf_model: str = "HuggingFaceH4/zephyr-7b-beta"

    ai_max_response_tokens: int = 1500
    ai_cache_ttl: int = 3600
    ai_timeout_seconds: int = 15

    # ── Security & Auth ───────────────────────────────────────────────
    secret_key: str = "yorvyn-super-secret-jwt-key-change-in-production-2026"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    algorithm: str = "HS256"

    # ── External Context & Services ───────────────────────────────────
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    default_city: str = "Shimla"
    default_latitude: float = 31.1048
    default_longitude: float = 77.1734

    model_config = ConfigDict(
        env_file=["backend/.env", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def effective_google_key(self) -> str:
        return self.google_api_key or self.gemini_api_key

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.effective_google_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_hf(self) -> bool:
        return bool(self.hf_api_key)

    @property
    def any_ai_available(self) -> bool:
        return (
            self.has_groq
            or self.has_openrouter
            or self.has_gemini
            or self.has_openai
            or self.has_hf
        )

    def log_status(self) -> None:
        def mask(k: str) -> str:
            return (k[:6] + "..." + k[-4:]) if len(k) > 10 else ("set" if k else "not set")

        print("── Yorvyn Fashion AI Status ──")
        print(f"  Environment  : {self.environment}")
        print(f"  Database     : {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
        print(f"  Groq API     : {'✅ ' + mask(self.groq_api_key) if self.has_groq else '❌ not set'}")
        print(f"  Gemini API   : {'✅ ' + mask(self.effective_google_key) if self.has_gemini else '❌ not set'}")
        print(f"  OpenRouter   : {'✅ ' + mask(self.openrouter_api_key) if self.has_openrouter else '❌ not set'}")
        print(f"  OpenAI API   : {'✅ ' + mask(self.openai_api_key) if self.has_openai else '❌ not set'}")
        print("───────────────────────────────")


settings = Settings()
