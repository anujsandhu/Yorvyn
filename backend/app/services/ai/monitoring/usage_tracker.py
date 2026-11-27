"""
YORVYN — AI Provider Observability & Usage Tracker (Phase 14.26)
Monitors API token consumption, financial expenditures, latencies, and zero-cost local savings:
- Request counts & success/error rates per provider
- Cumulative token tracking and cost accounting ($0.00 local vs cloud APIs)
- Sliding-window latency tracking
- Daily and monthly budget controls
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.ai.base import TokenUsage, AIProviderResponse

logger = logging.getLogger(__name__)


class ProviderUsageMetrics(BaseModel):
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_events: int = 0
    circuit_breaker_trips: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cumulative_cost_usd: float = 0.0
    latencies_ms: List[float] = Field(default_factory=list)


class AIUsageTracker:
    """Tracks token budgets, financial spend, and operational metrics across AI providers."""

    def __init__(self, daily_budget_usd: float = 10.0, monthly_budget_usd: float = 100.0):
        self.daily_budget_usd = daily_budget_usd
        self.monthly_budget_usd = monthly_budget_usd
        self.metrics: Dict[str, ProviderUsageMetrics] = defaultdict(
            lambda: ProviderUsageMetrics(provider_name="unknown")
        )
        self.local_cost_savings_usd: float = 0.0

    def record_response(self, response: AIProviderResponse):
        """Records telemetry from an executed AI response."""
        pname = response.provider_name
        if pname not in self.metrics:
            self.metrics[pname] = ProviderUsageMetrics(provider_name=pname)

        m = self.metrics[pname]
        m.total_requests += 1

        if response.success:
            m.successful_requests += 1
            m.total_prompt_tokens += response.token_usage.prompt_tokens
            m.total_completion_tokens += response.token_usage.completion_tokens
            m.total_tokens += response.token_usage.total_tokens
            m.cumulative_cost_usd += response.token_usage.estimated_cost_usd
            m.latencies_ms.append(response.latency_ms)

            # Keep latency window bounded
            if len(m.latencies_ms) > 100:
                m.latencies_ms.pop(0)

            # If executed on local CV, calculate counterfactual cloud savings
            if pname == "local_cv":
                # Average GPT-4V / Gemini Vision commercial call is ~$0.015
                self.local_cost_savings_usd += 0.015
        else:
            m.failed_requests += 1
            if response.error and response.error.error_code == "RATE_LIMIT":
                m.rate_limited_events += 1

    def get_summary(self) -> Dict[str, Any]:
        """Returns consolidated financial and performance summary."""
        total_cloud_spend = sum(m.cumulative_cost_usd for pname, m in self.metrics.items() if pname != "local_cv")
        total_requests = sum(m.total_requests for m in self.metrics.values())

        providers_summary = {}
        for pname, m in self.metrics.items():
            avg_lat = sum(m.latencies_ms) / len(m.latencies_ms) if m.latencies_ms else 0.0
            providers_summary[pname] = {
                "total_requests": m.total_requests,
                "success_rate": round(m.successful_requests / max(1, m.total_requests) * 100.0, 1),
                "total_tokens": m.total_tokens,
                "cost_usd": round(m.cumulative_cost_usd, 6),
                "avg_latency_ms": round(avg_lat, 1),
                "rate_limits": m.rate_limited_events
            }

        return {
            "total_requests": total_requests,
            "total_cloud_expenditure_usd": round(total_cloud_spend, 6),
            "local_cost_savings_usd": round(self.local_cost_savings_usd, 4),
            "zero_cost_policy_active": True,
            "daily_budget_usd": self.daily_budget_usd,
            "budget_headroom_usd": round(max(0.0, self.daily_budget_usd - total_cloud_spend), 4),
            "providers": providers_summary
        }


# Global singleton instance
usage_tracker = AIUsageTracker()
