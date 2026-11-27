"""
Application configuration for Yorvyn AI Fashion Intelligence Platform.
Reads from environment variables or .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Path to backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # ── App Info ──────────────────────────────────────────────────────
    app_name: str = "Yorvyn Fashion AI"
    app_version: str = "3.0.0"
    environment: str = "development"
    debug: bool = True
    api_v1_str: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────
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

    # ── External Web Intelligence Provider (Tavily) ───────────────────
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_timeout_seconds: float = 12.0
    tavily_monthly_credit_budget: int = 1000

    ai_fallback_enabled: bool = True
    ai_max_response_tokens: int = 1500
    ai_cache_ttl: int = 3600
    ai_timeout_seconds: int = 15

    # ── Security & Auth ───────────────────────────────────────────────
    secret_key: str = ""
    admin_api_key: str = ""
    enable_simulated_training: bool = False
    cors_allowed_origins: List[str] = [
        "https://yorvyn-ai.web.app",
        "https://yorvyn-ai.firebaseapp.com",
        "http://localhost:5174",
        "http://localhost:5173",
    ]
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    algorithm: str = "HS256"

    @model_validator(mode="after")
    def validate_security_secrets(self) -> Settings:
        env_lower = (self.environment or "").lower()
        is_dev_or_test = self.debug or env_lower in ("development", "test", "testing")
        if not self.secret_key:
            if not is_dev_or_test:
                raise ValueError("SECRET_KEY must be set when debug=False in non-development environments.")
            self.secret_key = os.getenv("YORVYN_DEV_JWT_SECRET") or "dev-only-ephemeral-jwt-secret"
        return self

    # ── Supabase Backend & Database ───────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    next_public_supabase_url: str = ""
    next_public_supabase_publishable_key: str = ""

    @model_validator(mode="after")
    def populate_supabase_credentials(self) -> Settings:
        if not self.supabase_url and self.next_public_supabase_url:
            self.supabase_url = self.next_public_supabase_url
        if not self.supabase_anon_key and self.next_public_supabase_publishable_key:
            self.supabase_anon_key = self.next_public_supabase_publishable_key
        return self

    # ── Cloudinary Media Storage ──────────────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_secure: bool = True

    # ── Stripe Billing & Subscriptions ────────────────────────────────
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = "price_yorvyn_pro_monthly"
    stripe_studio_price_id: str = "price_yorvyn_studio_monthly"
    stripe_test_mode: bool = False

    # ── External Context & Services ───────────────────────────────────
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    default_city: str = "Shimla"
    default_latitude: float = 31.1048
    default_longitude: float = 77.1734

    model_config = SettingsConfigDict(
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
    def has_tavily(self) -> bool:
        return bool(self.tavily_api_key or os.getenv("TAVILY_API_KEY"))

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
        print("── Yorvyn Fashion AI Status ──")
        print(f"  Environment  : {self.environment}")
        print("  Database     :", "configured" if self.database_url else "unset")
        print(f"  Groq API     : {'configured' if self.has_groq else '❌ not set'}")
        print(f"  Gemini API   : {'configured' if self.has_gemini else '❌ not set'}")
        print(f"  OpenRouter   : {'configured' if self.has_openrouter else '❌ not set'}")
        print(f"  OpenAI API   : {'configured' if self.has_openai else '❌ not set'}")
        print("───────────────────────────────")


settings = Settings()
