"""
Offline Deterministic Fashion Rule Engine Provider for Yorvyn LLM Architecture.
Provides reliable, zero-latency, zero-cost fashion styling intelligence when cloud LLMs
are unavailable, unconfigured, or during automated test executions.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from backend.app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCallRequest,
    ToolDefinition,
)


class OfflineRulesProvider(LLMProvider):
    """Deterministic fashion knowledge provider with zero external dependencies."""

    @property
    def provider_name(self) -> str:
        return "offline_rules"

    def health_check(self) -> bool:
        return True

    def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 800,
        timeout_seconds: int = 15
    ) -> LLMResponse:
        """Analyzes conversational turns and generates structured fashion advice or tool calls."""
        start_time = time.time()

        # Find latest user prompt
        user_text = ""
        for m in reversed(messages):
            if m.role == "user":
                user_text = m.content.lower()
                break

        # Check if tools are requested and available
        tool_calls: List[ToolCallRequest] = []
        tool_names = {t.name for t in (tools or [])}

        # Intent detection for tool invocation
        if "outfit" in user_text or "wear" in user_text or "suggest" in user_text or "college" in user_text or "wedding" in user_text:
            if "generate_outfit_recommendations" in tool_names:
                occasion = "casual"
                if "college" in user_text:
                    occasion = "college"
                elif "wedding" in user_text:
                    occasion = "wedding"
                elif "work" in user_text or "office" in user_text:
                    occasion = "business"
                elif "dinner" in user_text or "date" in user_text:
                    occasion = "smart_casual"

                tool_calls.append(ToolCallRequest(
                    id=f"call_{int(time.time() * 1000)}",
                    function_name="generate_outfit_recommendations",
                    arguments={"occasion": occasion, "formality_level": 5}
                ))

        elif "balance" in user_text or "proportions" in user_text:
            if "analyze_body_profile" in tool_names:
                tool_calls.append(ToolCallRequest(
                    id=f"call_{int(time.time() * 1000)}",
                    function_name="analyze_body_profile",
                    arguments={}
                ))

        elif "colour" in user_text or "color" in user_text or "skin" in user_text:
            if "analyze_colour_profile" in tool_names:
                tool_calls.append(ToolCallRequest(
                    id=f"call_{int(time.time() * 1000)}",
                    function_name="analyze_colour_profile",
                    arguments={}
                ))

        elif "wardrobe" in user_text or "closet" in user_text:
            if "get_wardrobe" in tool_names:
                tool_calls.append(ToolCallRequest(
                    id=f"call_{int(time.time() * 1000)}",
                    function_name="get_wardrobe",
                    arguments={}
                ))

        # If a tool call was generated, return tool call response
        if tool_calls:
            elapsed_ms = (time.time() - start_time) * 1000
            return LLMResponse(
                content="",
                tool_calls=tool_calls,
                provider_used=self.provider_name,
                model_used="offline-rules-v1",
                prompt_tokens=len(user_text.split()) + 50,
                completion_tokens=25,
                latency_ms=elapsed_ms,
                finish_reason="tool_calls"
            )

        # Handle tool result response or direct user reply
        # Check if the last message was a tool result
        tool_result_content = None
        for m in reversed(messages):
            if m.role == "tool":
                tool_result_content = m.content
                break

        if tool_result_content:
            try:
                data = json.loads(tool_result_content)
                if "recommendations" in data:
                    recs = data["recommendations"]
                    if recs:
                        top = recs[0]
                        editorial = (
                            f"I've tailored a refined combination for your day: the {top.get('name', 'Curated Outfit')}. "
                            f"This selection balances your personal palette with structured silhouette harmony, "
                            f"achieving a compatibility score of {top.get('composite_score', 92)}/100. "
                            f"{top.get('styling_rationale', 'Items coordinate effortlessly.')}"
                        )
                    else:
                        editorial = "I checked your wardrobe, but couldn't find a complete set matching that occasion. Consider adding versatile layers."
                elif "silhouette" in data:
                    editorial = (
                        f"Based on your body profile ({data.get('silhouette', 'athletic')} silhouette), "
                        f"I recommend pairing tailored mid-rise trousers with structured knitwear to visually balance the torso and legs."
                    )
                elif "personal_palette" in data:
                    editorial = (
                        f"Your skin undertone is classified as {data.get('undertone', 'neutral')}, harmonizing beautifully "
                        f"with your {data.get('personal_palette', 'autumn_deep')} palette. Rich earthy tones, deep navy, and off-white "
                        f"provide maximum natural radiance."
                    )
                else:
                    editorial = f"Based on your profile data, here is your personalized fashion guidance."
            except Exception:
                editorial = "Here is a tailored styling recommendation curated for your exact specifications."
        else:
            # Direct response based on user keywords
            if "don't like" in user_text or "dislike" in user_text:
                editorial = (
                    "I completely understand and have noted your rejection. I will strictly avoid that tone "
                    "in future styling recommendations. Would you prefer a warmer neutral or a deeper contrast instead?"
                )
            elif "college" in user_text or "class" in user_text:
                editorial = (
                    "For college tomorrow, I recommend an elevated yet effortless smart-casual combination: "
                    "relaxed pleated trousers paired with an oversized merino crewneck and minimalist leather low-tops. "
                    "This delivers all-day comfort while maintaining sharp, intentional proportions."
                )
            elif "formal" in user_text or "wedding" in user_text:
                editorial = (
                    "For a celebratory wedding or formal gathering, structured tailoring in deep midnight navy or charcoal "
                    "creates an impeccable silhouette. Complete the look with polished dress footwear."
                )
            else:
                editorial = (
                    "Hello! As your Yorvyn AI Stylist, I'm here to curate outfits from your real digital wardrobe, "
                    "analyze colour harmonies for your personal undertone, and refine your style silhouette. "
                    "What occasion are you dressing for today?"
                )

        elapsed_ms = (time.time() - start_time) * 1000
        words = editorial.split()

        return LLMResponse(
            content=editorial,
            tool_calls=[],
            provider_used=self.provider_name,
            model_used="offline-rules-v1",
            prompt_tokens=len(user_text.split()) + 80,
            completion_tokens=len(words),
            latency_ms=elapsed_ms,
            finish_reason="stop"
        )

