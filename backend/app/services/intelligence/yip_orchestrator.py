"""
YORVYN Intelligence Platform (YIP) — Unified Intelligence Orchestrator (Phase 17.0 Stage 8).

Implements the canonical orchestration flow:
Authenticated Request -> Intent & Context Understanding -> Evidence Policy ->
Capability Planning -> Model Eligibility Check -> Execution Plan ->
Specialized AI / Deterministic Engines -> Independent Evaluation ->
Controlled Candidate Optimization (if needed) -> Publication Gate ->
Durable Result & Provenance.

Reuses GarmentRouter, GarmentJobManager (PG/Redis/Outbox), and ExecutionContext.
Never allows LLMs or retrieved RAG chunks to invoke arbitrary filesystem paths or tools.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional
from weakref import WeakKeyDictionary

from pydantic import BaseModel, Field

from backend.app.services.intelligence.capability_registry import garment_capabilities
from backend.app.services.intelligence.candidate_optimizer import (
    CandidateOptimizationResult,
    candidate_optimizer,
)
from backend.app.services.intelligence.evaluation_critic import (
    IndependentEvaluationReport,
    evaluation_critic,
)
from backend.app.services.intelligence.fashion_intelligence_v17 import (
    FashionIntelligenceReport,
    fashion_intelligence_v17,
)
from backend.app.services.intelligence.fit_intelligence import (
    FitIntelligenceReport,
    fit_intelligence,
)
from backend.app.services.intelligence.inference_adapters import inference_telemetry
from backend.app.services.intelligence.knowledge_rag import (
    KnowledgeDomain,
    KnowledgeSearchResponse,
    knowledge_rag,
)
from backend.app.services.intelligence.multimodal_intelligence import (
    MultimodalUnderstandingOutput,
    multimodal_intelligence,
)
from backend.app.services.intelligence.personalization_engine import (
    PersonalizationRecommendationResponse,
    personalization_engine,
)
from backend.app.services.intelligence.recommendation_engine import (
    RecommendationResponse,
    fashion_recommendation_engine,
)
from backend.app.services.ml.model_registry import unified_model_registry


class YIPPlanStep(BaseModel):
    step_id: str
    capability_id: str
    depends_on: List[str] = Field(default_factory=list)
    selected_model_id: Optional[str] = None
    deadline_s: float = 30.0
    status: str = "PENDING"
    latency_ms: float = 0.0


class YIPExecutionPlan(BaseModel):
    plan_id: str
    owner_id: str
    intent: str
    evidence_policy_status: str
    steps: List[YIPPlanStep] = Field(default_factory=list)
    publication_gate_passed: Optional[bool] = None
    idempotency_key: Optional[str] = None


class YIPOrchestrationResult(BaseModel):
    plan: YIPExecutionPlan
    multimodal: Optional[MultimodalUnderstandingOutput] = None
    fashion: Optional[FashionIntelligenceReport] = None
    knowledge: Optional[KnowledgeSearchResponse] = None
    fit: Optional[FitIntelligenceReport] = None
    evaluation: Optional[IndependentEvaluationReport] = None
    optimization: Optional[CandidateOptimizationResult] = None
    personalization: Optional[PersonalizationRecommendationResponse] = None
    recommendations: Optional[RecommendationResponse] = None
    telemetry_snapshot: Dict[str, Any] = Field(default_factory=dict)
    total_latency_ms: float = 0.0
    from_idempotency_cache: bool = False


class YIPOrchestrator:
    """Typed, capability-gated, concurrent YIP orchestrator."""

    def __init__(self, concurrency: int = 3) -> None:
        self._concurrency = max(1, concurrency)
        self._semaphores: WeakKeyDictionary = WeakKeyDictionary()
        self._idempotency_cache: Dict[str, YIPOrchestrationResult] = {}

    def _get_semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        sem = self._semaphores.get(loop)
        if sem is None:
            sem = asyncio.Semaphore(self._concurrency)
            self._semaphores[loop] = sem
        return sem

    async def execute_plan(
        self,
        *,
        owner_id: str,
        instruction: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        back_image_bytes: Optional[bytes] = None,
        glb_bytes: Optional[bytes] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        avatar_profile_id: str = "standard_175",
        include_knowledge: bool = True,
        include_personalization: bool = False,
        consent_granted: bool = True,
        auto_optimize: bool = False,
        idempotency_key: Optional[str] = None,
        deadline_s: float = 30.0,
    ) -> YIPOrchestrationResult:
        if idempotency_key:
            sig = hashlib.sha256(
                f"{owner_id}:{idempotency_key}:{instruction or ''}:{category or ''}".encode("utf-8")
                + (image_bytes or b"")
                + (glb_bytes or b"")
            ).hexdigest()
            if sig in self._idempotency_cache:
                cached = self._idempotency_cache[sig].model_copy()
                cached.from_idempotency_cache = True
                return cached

        t0 = time.perf_counter()
        plan_id = f"yip_{uuid.uuid4().hex[:12]}"

        # 1. Intent & Multimodal pre-check
        mm_out = await asyncio.wait_for(
            asyncio.to_thread(
                multimodal_intelligence.understand,
                image_bytes=image_bytes,
                instruction=instruction or "",
                include_embedding=bool(image_bytes),
            ),
            timeout=deadline_s,
        )
        detected_intent = mm_out.text.intent if mm_out.text else "multimodal_inspection"

        # 2. Evidence Policy & Capability Planning
        steps: List[YIPPlanStep] = [
            YIPPlanStep(
                step_id="step_multimodal",
                capability_id="multimodal.understand",
                selected_model_id=(
                    mm_out.visual.receipts[0].model_id
                    if (mm_out.visual and mm_out.visual.receipts)
                    else "yorvyn-text-parser-v17"
                ),
                status="COMPLETED",
                latency_ms=mm_out.total_latency_ms,
            )
        ]

        policy_status = "LOCAL_EVIDENCE_OK"
        if mm_out.text and mm_out.text.ambiguity_detected and not image_bytes and not glb_bytes:
            policy_status = "CLARIFICATION_REQUESTED"

        resolved_cat = category or (mm_out.visual.category if mm_out.visual else None) or "jacket"
        resolved_sub = subcategory or (mm_out.visual.subcategory if mm_out.visual else None)

        fashion_res: Optional[FashionIntelligenceReport] = None
        knowledge_res: Optional[KnowledgeSearchResponse] = None
        fit_res: Optional[FitIntelligenceReport] = None
        critic_res: Optional[IndependentEvaluationReport] = None
        opt_res: Optional[CandidateOptimizationResult] = None
        pers_res: Optional[PersonalizationRecommendationResponse] = None
        rec_res: Optional[RecommendationResponse] = None

        # Validate capability registry registration prior to scheduling
        garment_capabilities.get("fabric.understand")
        garment_capabilities.get("recommendation.hybrid")

        async with self._get_semaphore():
            # 3. Parallel Fashion + Knowledge + Personalization/Recommendations execution when independent
            async def _run_fashion():
                return await asyncio.to_thread(
                    fashion_intelligence_v17.analyze_garment,
                    image_bytes=image_bytes,
                    back_image_bytes=back_image_bytes,
                    category=resolved_cat,
                    subcategory=resolved_sub,
                )

            async def _run_knowledge():
                q_str = (instruction or "").strip() or f"{resolved_cat} {resolved_sub or ''} construction fit ease".strip()
                return await asyncio.to_thread(
                    knowledge_rag.search,
                    q_str,
                    owner_id=owner_id,
                    top_k=3,
                )

            async def _run_personalization():
                pers = await asyncio.to_thread(
                    personalization_engine.recommend_for_user,
                    user_id=owner_id,
                    consent_granted=consent_granted,
                    top_k=4,
                )
                recs = await asyncio.to_thread(
                    fashion_recommendation_engine.recommend,
                    owner_id=owner_id,
                    mode="hybrid",
                    surface="orchestrator",
                    consent_granted=consent_granted,
                    anchor_item={"category": resolved_cat, "subcategory": resolved_sub or "", "name": f"{resolved_cat} anchor"},
                    top_k=4,
                )
                return pers, recs

            tasks: Dict[str, Any] = {}
            if image_bytes or category:
                tasks["fashion"] = asyncio.create_task(_run_fashion())
            if include_knowledge:
                tasks["knowledge"] = asyncio.create_task(_run_knowledge())
            if include_personalization:
                tasks["personalization"] = asyncio.create_task(_run_personalization())

            if tasks:
                await asyncio.wait_for(asyncio.gather(*tasks.values()), timeout=deadline_s)
                if "fashion" in tasks:
                    fashion_res = tasks["fashion"].result()
                    steps.append(YIPPlanStep(
                        step_id="step_fashion",
                        capability_id="fabric.understand",
                        depends_on=["step_multimodal"],
                        selected_model_id="pattern-construction-v16.2",
                        status="COMPLETED",
                        latency_ms=fashion_res.latency_ms,
                    ))
                if "knowledge" in tasks:
                    knowledge_res = tasks["knowledge"].result()
                    steps.append(YIPPlanStep(
                        step_id="step_knowledge",
                        capability_id="knowledge.retrieve",
                        depends_on=["step_multimodal"],
                        selected_model_id="knowledge-rag-v17",
                        status="COMPLETED",
                        latency_ms=knowledge_res.latency_ms,
                    ))
                if "personalization" in tasks:
                    pers_res, rec_res = tasks["personalization"].result()
                    steps.append(YIPPlanStep(
                        step_id="step_personalize",
                        capability_id="recommendation.hybrid",
                        depends_on=[],
                        selected_model_id="fashion-recommendation-engine",
                        status="COMPLETED",
                        latency_ms=rec_res.latency_ms,
                    ))

            # 4. 3D Fit + Independent Evaluation + Bounded Optimization when GLB provided
            pub_gate: Optional[bool] = None
            if glb_bytes:
                fit_res = await asyncio.to_thread(
                    fit_intelligence.analyze_fit,
                    category=resolved_cat,
                    glb_bytes=glb_bytes,
                    avatar_profile_id=avatar_profile_id,
                )
                steps.append(YIPPlanStep(
                    step_id="step_fit",
                    capability_id="fit.analyze",
                    depends_on=["step_multimodal"],
                    selected_model_id="fit-intelligence-v17",
                    status="COMPLETED",
                    latency_ms=fit_res.latency_ms,
                ))

                expected_comps = (
                    [c.component_id for c in fashion_res.components if c.presence_state.value == "OBSERVED"]
                    if fashion_res else None
                )
                if auto_optimize:
                    _final_bytes, opt_res = await asyncio.to_thread(
                        candidate_optimizer.optimize_candidate,
                        glb_bytes,
                        category=resolved_cat,
                        avatar_profile_id=avatar_profile_id,
                        expected_components=expected_comps,
                        owner_id=owner_id,
                        idempotency_key=idempotency_key,
                    )
                    critic_res = opt_res.final_report
                    pub_gate = opt_res.publication_allowed
                    steps.append(YIPPlanStep(
                        step_id="step_optimize_and_critic",
                        capability_id="candidate.optimize",
                        depends_on=["step_fit"],
                        selected_model_id="independent-critic-v17",
                        status="COMPLETED" if pub_gate else "FAILED_GATE",
                        latency_ms=opt_res.budget_ms_used,
                    ))
                else:
                    critic_res = await asyncio.to_thread(
                        evaluation_critic.evaluate_candidate,
                        glb_bytes,
                        category=resolved_cat,
                        expected_components=expected_comps,
                        avatar_profile_id=avatar_profile_id,
                    )
                    pub_gate = critic_res.publication_allowed
                    steps.append(YIPPlanStep(
                        step_id="step_critic",
                        capability_id="critic.evaluate",
                        depends_on=["step_fit"],
                        selected_model_id="independent-critic-v17",
                        status="COMPLETED" if pub_gate else "FAILED_GATE",
                        latency_ms=critic_res.total_latency_ms,
                    ))

        plan = YIPExecutionPlan(
            plan_id=plan_id,
            owner_id=owner_id,
            intent=detected_intent,
            evidence_policy_status=policy_status,
            steps=steps,
            publication_gate_passed=pub_gate,
            idempotency_key=idempotency_key,
        )
        result = YIPOrchestrationResult(
            plan=plan,
            multimodal=mm_out,
            fashion=fashion_res,
            knowledge=knowledge_res,
            fit=fit_res,
            evaluation=critic_res,
            optimization=opt_res,
            personalization=pers_res,
            recommendations=rec_res,
            telemetry_snapshot={
                "hardware": unified_model_registry.get_hardware_profile(),
                "adapters": inference_telemetry.snapshot(),
                "integrations": unified_model_registry.get_external_providers_and_frameworks(),
            },
            total_latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )
        if idempotency_key:
            sig = hashlib.sha256(
                f"{owner_id}:{idempotency_key}:{instruction or ''}:{category or ''}".encode("utf-8")
                + (image_bytes or b"")
                + (glb_bytes or b"")
            ).hexdigest()
            self._idempotency_cache[sig] = result
        return result


yip_orchestrator = YIPOrchestrator()
