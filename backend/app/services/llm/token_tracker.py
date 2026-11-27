"""
Token Usage & Operational Cost Tracker for Yorvyn LLM Architecture.
Tracks token consumption, latency, and estimated operational costs per user and provider.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Reference cost rates per 1,000,000 tokens (USD)
ESTIMATED_PROVIDER_RATES: Dict[str, Dict[str, float]] = {
    "groq": {
        "prompt_per_million": 0.59,
        "completion_per_million": 0.79
    },
    "gemini": {
        "prompt_per_million": 0.075,
        "completion_per_million": 0.30
    },
    "openrouter": {
        "prompt_per_million": 0.50,
        "completion_per_million": 1.50
    },
    "offline_rules": {
        "prompt_per_million": 0.0,
        "completion_per_million": 0.0
    }
}


class TokenUsageRecord(BaseModel):
    user_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    estimated_cost_usd: float = 0.0


class TokenUsageTracker:
    """Thread-safe tracker aggregating token consumption and estimated costs."""

    def __init__(self):
        self._records: List[TokenUsageRecord] = []
        self._user_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0, "requests": 0})
        self._provider_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0, "requests": 0})

    def record_usage(
        self,
        user_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float
    ) -> TokenUsageRecord:
        """Records an inference turn and calculates estimated cost."""
        rates = ESTIMATED_PROVIDER_RATES.get(provider.lower(), {"prompt_per_million": 0.50, "completion_per_million": 0.80})
        cost = (
            (prompt_tokens / 1_000_000.0) * rates["prompt_per_million"]
            + (completion_tokens / 1_000_000.0) * rates["completion_per_million"]
        )

        rec = TokenUsageRecord(
            user_id=str(user_id),
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(latency_ms, 2),
            estimated_cost_usd=round(cost, 6)
        )
        self._records.append(rec)

        # Update totals
        self._user_totals[str(user_id)]["prompt"] += prompt_tokens
        self._user_totals[str(user_id)]["completion"] += completion_tokens
        self._user_totals[str(user_id)]["requests"] += 1

        self._provider_totals[provider]["prompt"] += prompt_tokens
        self._provider_totals[provider]["completion"] += completion_tokens
        self._provider_totals[provider]["requests"] += 1

        return rec

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Returns token usage summary for a specific user."""
        totals = self._user_totals.get(str(user_id), {"prompt": 0, "completion": 0, "requests": 0})
        total_tokens = totals["prompt"] + totals["completion"]
        user_records = [r for r in self._records if r.user_id == str(user_id)]
        total_cost = sum(r.estimated_cost_usd for r in user_records)
        avg_latency = (sum(r.latency_ms for r in user_records) / len(user_records)) if user_records else 0.0

        return {
            "user_id": str(user_id),
            "requests_count": totals["requests"],
            "prompt_tokens": totals["prompt"],
            "completion_tokens": totals["completion"],
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "average_latency_ms": round(avg_latency, 2)
        }

    def get_global_metrics(self) -> Dict[str, Any]:
        """Returns platform-wide token, latency, and cost telemetry."""
        total_requests = len(self._records)
        total_prompt = sum(r.prompt_tokens for r in self._records)
        total_completion = sum(r.completion_tokens for r in self._records)
        total_cost = sum(r.estimated_cost_usd for r in self._records)
        avg_latency = (sum(r.latency_ms for r in self._records) / total_requests) if total_requests else 0.0

        return {
            "total_requests": total_requests,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_cost_usd": round(total_cost, 6),
            "average_latency_ms": round(avg_latency, 2),
            "provider_breakdown": dict(self._provider_totals)
        }


# Global singleton
token_tracker = TokenUsageTracker()

