"""
AI fallback — query enrichment when local ML confidence is low.

Provider priority (free-tier only, no OpenAI):
  1. Groq          — 14,400 req/day, sub-second responses
  2. OpenRouter    — 200 req/day, :free models
  3. Google Gemini — 1,500 req/day
  4. HuggingFace   — ~30 req/hr

Token conservation:
  - Cache: identical queries cost 0 tokens (1hr TTL)
  - Prompt: ~120 tokens
  - Response: capped at 150 tokens
  - Only called when ML confidence < 0.24
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Optional

import requests

from .config import settings


# ── In-memory cache ───────────────────────────────────────────────────
_cache: dict[str, dict] = {}


def _cache_key(text: str) -> str:
    return hashlib.md5(re.sub(r"\s+", " ", text.lower().strip()).encode()).hexdigest()


def _cache_get(text: str) -> Optional[dict[str, Any]]:
    entry = _cache.get(_cache_key(text))
    if entry and (time.time() - entry["ts"]) < settings.ai_cache_ttl:
        return entry["result"]
    return None


def _cache_set(text: str, result: dict[str, Any]) -> None:
    if len(_cache) > 500:
        cutoff = time.time() - settings.ai_cache_ttl
        for k in [k for k, v in _cache.items() if v["ts"] < cutoff]:
            del _cache[k]
        if len(_cache) > 400:
            for k in sorted(_cache, key=lambda k: _cache[k]["ts"])[:100]:
                del _cache[k]
    _cache[_cache_key(text)] = {"result": result, "ts": time.time()}


# ── Helpers ───────────────────────────────────────────────────────────

def _extract_json_block(text: str) -> str:
    """Extract JSON from AI response — handles thinking blocks, fences, plain JSON."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON in response: {text[:120]!r}")
    return match.group(0)


def _normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    def _list(v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return [str(v).strip()]

    return {
        "gender":             str(raw.get("gender", "")).strip().lower(),
        "occasion":           str(raw.get("occasion", "")).strip().lower(),
        "season":             str(raw.get("season", "")).strip().lower(),
        "mood":               str(raw.get("mood", "")).strip().lower(),
        "liked_notes":        _list(raw.get("liked_notes")),
        "disliked_notes":     _list(raw.get("disliked_notes")),
        "keywords":           _list(raw.get("keywords")),
        "expanded_terms":     _list(raw.get("expanded_terms")),
        "reference_perfumes": _list(raw.get("reference_perfumes")),
        "budget_min":         raw.get("budget_min"),
        "budget_max":         raw.get("budget_max"),
    }


# Compact system prompt — ~60 tokens
_SYSTEM = (
    "Extract perfume preferences as JSON. "
    "Keys: gender, occasion, season, mood, liked_notes, disliked_notes, "
    "keywords, expanded_terms, reference_perfumes, budget_min, budget_max. "
    "Use empty string or [] for unknown. Return JSON only."
)


def _build_prompt(user_text: str, context: Optional[dict[str, Any]] = None) -> str:
    ctx = ""
    if context:
        relevant = {k: v for k, v in context.items() if v}
        if relevant:
            ctx = f" Context: {json.dumps(relevant, ensure_ascii=True)}"
    return f"Request: {user_text.strip()}{ctx}"


# ── Generic OpenAI-compatible call ────────────────────────────────────

def _call_compat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    extra_headers: Optional[dict] = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    resp = requests.post(
        f"{base_url}/chat/completions",
        timeout=settings.ai_fallback_timeout,
        headers=headers,
        json={"model": model, "temperature": 0.1,
              "max_tokens": settings.ai_max_response_tokens, "messages": messages},
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return _normalize_profile(json.loads(_extract_json_block(text)))


# ── Provider 1: Groq ──────────────────────────────────────────────────

def _call_groq(prompt: str) -> dict[str, Any]:
    """14,400 req/day free — fastest provider."""
    return _call_compat(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )


# ── Provider 2: OpenRouter ────────────────────────────────────────────

def _call_openrouter(prompt: str) -> dict[str, Any]:
    """200 req/day free — :free models, no billing needed."""
    model = settings.openrouter_model
    # Gemma models don't support system role
    if "gemma" in model.lower():
        messages = [{"role": "user", "content": f"{_SYSTEM}\n\n{prompt}"}]
    else:
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ]
    return _call_compat(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        model=model,
        messages=messages,
        extra_headers={"HTTP-Referer": "https://yorvyn.app", "X-Title": "Yorvyn"},
    )


# ── Provider 3: Google Gemini ─────────────────────────────────────────

def _call_gemini(prompt: str) -> dict[str, Any]:
    """1,500 req/day free — tries gemini-2.5-flash then gemini-flash-latest."""
    key = settings.effective_google_key
    last_error: Exception | None = None

    for model in ["gemini-2.5-flash", "gemini-flash-latest"]:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        try:
            resp = requests.post(url, timeout=settings.ai_fallback_timeout, json={
                "contents": [{"parts": [{"text": f"{_SYSTEM}\n\n{prompt}"}]}],
                "generationConfig": {"temperature": 0.1,
                                     "maxOutputTokens": settings.ai_max_response_tokens},
            })
            if resp.status_code in (429, 503):
                last_error = Exception(f"HTTP {resp.status_code} on {model}")
                continue
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _normalize_profile(json.loads(_extract_json_block(text)))
        except (ValueError, KeyError, json.JSONDecodeError):
            raise
        except Exception as e:
            last_error = e
            continue

    raise last_error or Exception("All Gemini models unavailable")


# ── Provider 4: HuggingFace ───────────────────────────────────────────

def _call_huggingface(prompt: str) -> dict[str, Any]:
    """~30 req/hr free — uses HF router OpenAI-compatible endpoint."""
    resp = requests.post(
        "https://router.huggingface.co/hf-inference/v1/chat/completions",
        timeout=settings.ai_fallback_timeout,
        headers={"Authorization": f"Bearer {settings.hf_api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": settings.hf_model,
            "max_tokens": settings.ai_max_response_tokens,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt},
            ],
        },
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return _normalize_profile(json.loads(_extract_json_block(text)))


# ── Public API ────────────────────────────────────────────────────────

def enrich_preference_profile(
    user_text: str,
    context: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Enrich a low-confidence query using AI.
    Returns {"provider": str, "profile": dict} or None.
    """
    if not user_text.strip():
        return None

    # Cache hit — 0 tokens
    cached = _cache_get(user_text)
    if cached:
        print("✅ AI fallback: cache hit (0 tokens)")
        return cached

    prompt = _build_prompt(user_text, context=context)

    attempts: list[tuple[str, Any]] = []
    if settings.has_groq:
        attempts.append(("groq", _call_groq))
    if settings.has_openrouter:
        attempts.append(("openrouter", _call_openrouter))
    if settings.has_gemini:
        attempts.append(("gemini", _call_gemini))
    if settings.has_hf:
        attempts.append(("huggingface", _call_huggingface))

    if not attempts:
        return None

    for provider, fn in attempts:
        try:
            profile = fn(prompt)
            result = {"provider": provider, "profile": profile}
            _cache_set(user_text, result)
            print(f"✅ AI fallback: {provider}")
            return result
        except Exception as exc:
            print(f"⚠️  {provider}: {str(exc)[:80]}")

    return None


def get_ai_status() -> dict[str, Any]:
    return {
        "providers": {
            "groq":        {"configured": settings.has_groq,       "model": settings.groq_model,       "free_tier": "14,400 req/day"},
            "openrouter":  {"configured": settings.has_openrouter, "model": settings.openrouter_model, "free_tier": "200 req/day"},
            "gemini":      {"configured": settings.has_gemini,     "model": settings.gemini_model,     "free_tier": "1,500 req/day"},
            "huggingface": {"configured": settings.has_hf,         "model": settings.hf_model,         "free_tier": "~30 req/hr"},
        },
        "token_conservation": {
            "max_response_tokens":  settings.ai_max_response_tokens,
            "cache_ttl_seconds":    settings.ai_cache_ttl,
            "cache_entries":        len(_cache),
            "confidence_threshold": settings.ai_fallback_confidence_threshold,
        },
        "fallback_enabled": settings.ai_fallback_enabled,
    }

# ── Generative Chat Reply ─────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are Yorvyn, a personal fragrance advisor. Your job is to help users find perfumes they'll genuinely love.

TONE RULES:
- Natural and direct — like a knowledgeable friend, not a salesperson
- Use the user's name occasionally (not every sentence)
- Never fake enthusiasm ("Amazing choice!") — be real
- No emojis
- Keep responses concise — 2-4 sentences max before the recommendation

RESPONSE STRUCTURE (always follow this):
1. One short human-like acknowledgment of what they want
2. Top recommendation with a clear reason tied to their preferences
3. One optional follow-up question to refine further

STRICT RULES:
- Only recommend perfumes from the provided dataset
- Never invent perfume names
- Base reasoning on actual notes, accords, occasion, and season from the data

PERSONALIZATION:
- If user has a name, use it naturally once in the response
- If they have favorite notes, reference them: "Since you like [note]..."
- If they have liked perfumes, reference similarity: "This is in the same direction as [perfume]..."
- If it's their first time, be welcoming but not over-the-top
- If they're returning, acknowledge context: "Based on what you've been exploring..."

OCCASION INTELLIGENCE:
- Date night → "memorable but not overpowering"
- Office → "subtle, nothing that announces itself"
- Daily → "effortless, wearable all day"
- Party → "bold, makes an impression"

OUTPUT FORMAT:
[Short acknowledgment]

Top pick: **[Name]** by [Brand]
Why: [1-2 sentences linking to their preferences]

[Optional: one follow-up question]
"""

def _call_groq_text(messages: list) -> str:
    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        timeout=settings.ai_fallback_timeout,
        headers=headers,
        json={"model": settings.groq_model, "temperature": 0.5, "max_tokens": 800, "messages": messages},
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def _call_openrouter_text(messages: list) -> str:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yorvyn.app",
        "X-Title": "Yorvyn"
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        timeout=settings.ai_fallback_timeout,
        headers=headers,
        json={"model": settings.openrouter_model, "temperature": 0.5, "max_tokens": 800, "messages": messages},
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def generate_chat_reply_llm(
    user_profile: dict,
    recommendations: list,
    user_ctx: Any = None,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a personalized chat reply using an LLM.
    Injects user name, memory, and preferences into the prompt.

    Args:
        user_profile:  Merged intent context dict from _merge_context.
        recommendations: List of recommendation dicts from the ML model.
        user_ctx:      Optional UserContext with user profile data.
        system_prompt: If provided, replaces CHAT_SYSTEM_PROMPT for this call.
                       Falls back to CHAT_SYSTEM_PROMPT when None.
    """
    if not recommendations:
        return None

    # Build user context block
    name = ""
    memory_lines = []

    if user_ctx:
        # Handle both dict and Pydantic model
        if hasattr(user_ctx, "nickname"):
            name = user_ctx.nickname or user_ctx.name or ""
            fav_notes = user_ctx.favorite_notes or []
            liked = user_ctx.liked_perfume_names or []
            occasion = user_ctx.preferred_occasion or ""
            is_new = user_ctx.is_new_user or False
            total_chats = user_ctx.total_chats or 0
        else:
            name = user_ctx.get("nickname") or user_ctx.get("name") or ""
            fav_notes = user_ctx.get("favorite_notes") or []
            liked = user_ctx.get("liked_perfume_names") or []
            occasion = user_ctx.get("preferred_occasion") or ""
            is_new = user_ctx.get("is_new_user") or False
            total_chats = user_ctx.get("total_chats") or 0

        if name:
            memory_lines.append(f"User's name: {name}")
        if fav_notes:
            memory_lines.append(f"Favorite notes: {', '.join(fav_notes[:4])}")
        if liked:
            memory_lines.append(f"Previously liked: {', '.join(liked[:3])}")
        if occasion:
            memory_lines.append(f"Preferred occasion: {occasion}")
        if is_new:
            memory_lines.append("First-time user — be welcoming")
        elif total_chats > 0:
            memory_lines.append(f"Returning user ({total_chats} previous chats) — acknowledge context")

    # Build the prompt
    user_memory_block = "\nUSER MEMORY:\n" + "\n".join(memory_lines) if memory_lines else ""
    extracted_block = "\nEXTRACTED INTENT:\n" + json.dumps({
        k: v for k, v in user_profile.items() if v
    }, indent=2) if user_profile else ""

    dataset_block = "\nTOP MATCHES FROM DATASET:\n" + json.dumps([
        {
            "name": r.get("name"),
            "brand": r.get("brand"),
            "accords": r.get("accords", ""),
            "rating": r.get("rating"),
            "price_usd": r.get("price_usd", ""),
        }
        for r in recommendations[:5]
    ], indent=2)

    prompt = f"{user_memory_block}{extracted_block}{dataset_block}"

    messages = [
        {"role": "system", "content": system_prompt if system_prompt is not None else CHAT_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    if settings.has_groq:
        try:
            return _call_groq_text(messages)
        except Exception as e:
            print(f"Groq text failed: {e}")

    if settings.has_openrouter:
        try:
            return _call_openrouter_text(messages)
        except Exception as e:
            print(f"OpenRouter text failed: {e}")

    return None
