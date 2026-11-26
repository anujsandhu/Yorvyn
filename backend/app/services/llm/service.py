"""
Yorvyn Intelligence Service.
Master coordination service unifying LLM providers, tool execution loop,
conversational memory, structured output validation, token tracking, and error recovery.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.llm.base import LLMMessage, LLMResponse, ToolCallRequest
from backend.app.services.llm.config import LLMConfiguration
from backend.app.services.llm.conversation_manager import conversation_manager
from backend.app.services.llm.error_handler import LLMErrorHandler
from backend.app.services.llm.providers.offline_rules_provider import OfflineRulesProvider
from backend.app.services.llm.registry import llm_registry
from backend.app.services.llm.token_tracker import token_tracker
from backend.app.services.llm.tool_registry import tool_registry
from backend.app.models.animation_intent import AnimationIntent

logger = logging.getLogger(__name__)


class IntelligenceServiceResponse(BaseModel):
    conversation_id: str
    response_text: str
    tool_calls_executed: List[Dict[str, Any]] = Field(default_factory=list)
    outfits: List[Dict[str, Any]] = Field(default_factory=list)
    provider_used: str
    model_used: str
    total_tokens: int = 0
    latency_ms: float = 0.0
    is_fallback: bool = False
    animation_intent: Optional[Dict[str, Any]] = None


class YorvynIntelligenceService:
    """Central orchestrator for fashion intelligence reasoning."""

    def __init__(self, config: Optional[LLMConfiguration] = None):
        self.config = config or LLMConfiguration.from_settings()
        self.registry = llm_registry
        self.conv_mgr = conversation_manager
        self.tools = tool_registry
        self.tracker = token_tracker
        self.error_handler = LLMErrorHandler()

    def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        temporary_constraints: Optional[Dict[str, Any]] = None,
        max_tool_iterations: int = 3
    ) -> IntelligenceServiceResponse:
        """
        Executes complete conversational reasoning turn:
        1. Appends user message
        2. Resolves provider
        3. Calls LLM with tool definitions
        4. Executes any requested tools
        5. Performs synthesis turn if tools were called
        6. Tracks tokens and logs metrics
        """
        start_time = time.time()
        user_id_str = str(user_id)

        # 1. Retrieve / Initialize Session
        session = self.conv_mgr.get_or_create_session(user_id_str, conversation_id)
        cid = session.conversation_id

        if temporary_constraints:
            for k, v in temporary_constraints.items():
                session.set_temporary_constraint(k, v)

        self.conv_mgr.add_user_message(user_id_str, cid, message)

        # 2. Resolve Provider
        provider = self.registry.resolve_provider(
            primary_preference=self.config.primary_provider,
            fallback_preference=self.config.fallback_provider
        )

        executed_tools_summary: List[Dict[str, Any]] = []
        collected_outfits: List[Dict[str, Any]] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        iteration = 0
        final_text = ""
        is_fallback = False

        try:
            while iteration < max_tool_iterations:
                iteration += 1
                messages = self.conv_mgr.get_messages(user_id_str, cid)
                tool_defs = self.tools.get_tool_definitions() if self.config.enable_tools else None

                # Call Provider
                resp: LLMResponse = provider.generate(
                    messages=messages,
                    tools=tool_defs,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout_seconds=self.config.timeout_seconds
                )

                total_prompt_tokens += resp.prompt_tokens
                total_completion_tokens += resp.completion_tokens

                # Track token usage
                self.tracker.record_usage(
                    user_id=user_id_str,
                    provider=resp.provider_used,
                    model=resp.model_used,
                    prompt_tokens=resp.prompt_tokens,
                    completion_tokens=resp.completion_tokens,
                    latency_ms=resp.latency_ms
                )

                # Check if tool calls were returned
                if resp.tool_calls:
                    # Record assistant message with tool calls
                    self.conv_mgr.add_assistant_message(
                        user_id=user_id_str,
                        conversation_id=cid,
                        content=resp.content,
                        tool_calls=resp.tool_calls
                    )

                    # Execute each tool
                    for tc in resp.tool_calls:
                        tool_res = self.tools.execute_tool(
                            user_id=user_id_str,
                            tool_name=tc.function_name,
                            arguments=tc.arguments
                        )

                        executed_tools_summary.append({
                            "tool_name": tc.function_name,
                            "arguments": tc.arguments,
                            "success": tool_res.success,
                            "execution_time_ms": tool_res.execution_time_ms
                        })

                        if tc.function_name == "generate_outfit_recommendations" and tool_res.success:
                            recs = tool_res.data.get("recommendations", [])
                            collected_outfits.extend(recs)

                        # Append tool response
                        payload_str = json.dumps(tool_res.data if tool_res.success else {"error": tool_res.error})
                        self.conv_mgr.add_tool_response(
                            user_id=user_id_str,
                            conversation_id=cid,
                            tool_call_id=tc.id,
                            tool_name=tc.function_name,
                            content=payload_str
                        )

                    # Loop continues to next iteration for final response synthesis
                    continue
                else:
                    # Final textual response reached
                    final_text = resp.content
                    self.conv_mgr.add_assistant_message(
                        user_id=user_id_str,
                        conversation_id=cid,
                        content=final_text
                    )
                    break

        except Exception as exc:
            logger.warning("Primary LLM request failed: %s", self.error_handler.classify_exception(exc).value)
            is_fallback = True

            # Resilient automatic failover to OfflineRulesProvider
            if provider.provider_name != "offline_rules":
                logger.info("Executing automatic failover to OfflineRulesProvider...")
                provider = self.registry.get_provider("offline_rules") or OfflineRulesProvider()
                try:
                    # Run first turn with offline rules
                    resp = provider.generate(
                        messages=self.conv_mgr.get_messages(user_id_str, cid),
                        tools=self.tools.get_tool_definitions(),
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens
                    )
                    total_prompt_tokens += resp.prompt_tokens
                    total_completion_tokens += resp.completion_tokens

                    if resp.tool_calls:
                        self.conv_mgr.add_assistant_message(
                            user_id=user_id_str,
                            conversation_id=cid,
                            content=resp.content,
                            tool_calls=resp.tool_calls
                        )
                        for tc in resp.tool_calls:
                            tool_res = self.tools.execute_tool(
                                user_id=user_id_str,
                                tool_name=tc.function_name,
                                arguments=tc.arguments
                            )
                            executed_tools_summary.append({
                                "tool_name": tc.function_name,
                                "arguments": tc.arguments,
                                "success": tool_res.success,
                                "execution_time_ms": tool_res.execution_time_ms
                            })
                            if tc.function_name == "generate_outfit_recommendations" and tool_res.success:
                                collected_outfits.extend(tool_res.data.get("recommendations", []))

                            self.conv_mgr.add_tool_response(
                                user_id=user_id_str,
                                conversation_id=cid,
                                tool_call_id=tc.id,
                                tool_name=tc.function_name,
                                content=json.dumps(tool_res.data if tool_res.success else {"error": tool_res.error})
                            )

                        # Final synthesis turn with offline rules
                        synth_resp = provider.generate(
                            messages=self.conv_mgr.get_messages(user_id_str, cid),
                            tools=None
                        )
                        final_text = synth_resp.content
                    else:
                        final_text = resp.content

                except Exception as inner_exc:
                    error_type = self.error_handler.classify_exception(exc)
                    fallback = self.error_handler.create_fallback_response(error_type, message, str(exc))
                    final_text = fallback["content"]
            else:
                error_type = self.error_handler.classify_exception(exc)
                fallback = self.error_handler.create_fallback_response(error_type, message, str(exc))
                final_text = fallback["content"]

            if not collected_outfits:
                fallback_tool_res = self.tools.execute_tool(
                    user_id=user_id_str,
                    tool_name="generate_outfit_recommendations",
                    arguments={"occasion": "casual"}
                )
                if fallback_tool_res.success:
                    collected_outfits = fallback_tool_res.data.get("recommendations", [])

            self.conv_mgr.add_assistant_message(
                user_id=user_id_str,
                conversation_id=cid,
                content=final_text
            )

        total_elapsed_ms = (time.time() - start_time) * 1000

        # Construct validated conversational animation intent
        anim_intent = AnimationIntent.infer_from_text(final_text)

        return IntelligenceServiceResponse(
            conversation_id=cid,
            response_text=final_text,
            tool_calls_executed=executed_tools_summary,
            outfits=collected_outfits,
            provider_used=provider.provider_name if not is_fallback else "offline_rules_fallback",
            model_used=provider.default_model if hasattr(provider, "default_model") else "offline-rules-v1",
            total_tokens=total_prompt_tokens + total_completion_tokens,
            latency_ms=round(total_elapsed_ms, 2),
            is_fallback=is_fallback,
            animation_intent=anim_intent.model_dump() if hasattr(anim_intent, "model_dump") else anim_intent.dict()
        )


# Global singleton
intelligence_service = YorvynIntelligenceService()
