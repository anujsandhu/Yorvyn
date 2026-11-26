"""
YORVYN Intelligence Platform (YIP) — FastAPI API Routes (Phase 17.0 Stage 8).

Authenticated endpoints exposing YIP orchestration, multimodal understanding,
fashion/fabric intelligence, fit intelligence, hybrid RAG knowledge retrieval,
independent multi-domain critic evaluation, bounded candidate optimization,
owner-isolated personalization, and admin-gated offline learning audits.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.core.security import UserContext, get_current_user
from backend.app.core.settings import settings
from backend.app.services.garments.job_manager import PERMANENT_ASSET_DIR, garment_job_manager
from backend.app.services.intelligence.capability_registry import garment_capabilities
from backend.app.services.intelligence.candidate_optimizer import candidate_optimizer
from backend.app.services.intelligence.evaluation_critic import evaluation_critic
from backend.app.services.intelligence.fashion_intelligence_v17 import fashion_intelligence_v17
from backend.app.services.intelligence.fit_intelligence import fit_intelligence
from backend.app.services.intelligence.inference_adapters import inference_telemetry
from backend.app.services.intelligence.knowledge_rag import KnowledgeDomain, knowledge_rag
from backend.app.services.intelligence.langgraph_workflows import langgraph_workflow_adapter
from backend.app.services.intelligence.multimodal_intelligence import multimodal_intelligence
from backend.app.services.intelligence.neural_recommendation_trainer import (
    CuratedInteractionEvent,
    neural_recommendation_trainer,
)
from backend.app.services.intelligence.personalization_engine import personalization_engine
from backend.app.services.intelligence.recommendation_engine import (
    RankingWeightsConfig,
    fashion_recommendation_engine,
)
from backend.app.services.intelligence.recommendation_evaluation import (
    ChronologicalEvent,
    recommendation_evaluator,
)
from backend.app.services.intelligence.recommendation_profile import recommendation_profile_store
from backend.app.services.intelligence.recommendation_taxonomy import get_taxonomy_summary
from backend.app.services.intelligence.tavily_web_adapter import tavily_web_adapter
from backend.app.services.intelligence.unified_knowledge import unified_knowledge
from backend.app.services.intelligence.yip_orchestrator import yip_orchestrator
from backend.app.services.learning.dataset_curator import CuratedSample, dataset_curator
from backend.app.services.ml.model_registry import unified_model_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence", tags=["YORVYN Intelligence Platform (YIP)"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _verify_admin_access(request: Request, current_user: UserContext) -> None:
    admin_header = request.headers.get("X-Admin-Key") or ""
    configured_admin_key = settings.admin_api_key or ""
    is_admin_header = bool(
        configured_admin_key
        and admin_header
        and secrets.compare_digest(admin_header, configured_admin_key)
    )
    is_admin_user = (
        current_user.role in ("admin", "service_role")
        or bool(current_user.email and current_user.email.endswith("@internal.yorvyn.ai"))
    )
    if not (is_admin_header or is_admin_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or service-role privileges required.",
        )


def _load_owned_job_glb(job_id: str, current_user: UserContext) -> bytes:
    safe_job_id = os.path.basename(job_id or "")
    if not safe_job_id or safe_job_id != job_id or ".." in job_id or "/" in job_id or "\\" in job_id:
        raise HTTPException(status_code=400, detail="Invalid job identifier.")
    job = garment_job_manager.get_job(safe_job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{safe_job_id}' not found.")
    if job.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: cannot inspect another owner's garment job.")
    glb_path = os.path.join(PERMANENT_ASSET_DIR, safe_job_id, "garment.glb")
    if not os.path.isfile(glb_path):
        raise HTTPException(status_code=404, detail=f"Published GLB for job '{safe_job_id}' not found.")
    with open(glb_path, "rb") as fh:
        return fh.read()


class SimilarityRequest(BaseModel):
    query_text: Optional[str] = None
    query_embedding: Optional[List[float]] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=50)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    domains: Optional[List[KnowledgeDomain]] = None
    verified_only: bool = False
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeIngestRequest(BaseModel):
    doc_id: str = Field(..., min_length=2, max_length=120)
    domain: KnowledgeDomain
    title: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=10, max_length=10000)
    source: str = Field(..., min_length=2, max_length=200)
    author_or_publisher: str = Field(default="User Contributed", max_length=200)
    license: str = Field(default="YORVYN Internal Engineering Knowledge", max_length=120)
    document_ref: str = Field(..., min_length=2, max_length=300)
    section_ref: str = Field(default="general", max_length=120)
    shared_corpus: bool = False


class FitAnalyzeRequest(BaseModel):
    job_id: Optional[str] = None
    category: str = "tops"
    avatar_profile_id: str = "standard_175"
    custom_measurements: Optional[Dict[str, float]] = None


class CriticJobRequest(BaseModel):
    job_id: str
    category: str = "tops"
    avatar_profile_id: str = "standard_175"
    expected_components: Optional[List[str]] = None


class OptimizeJobRequest(BaseModel):
    job_id: str
    category: str = "tops"
    avatar_profile_id: str = "standard_175"
    expected_components: Optional[List[str]] = None
    max_iterations: int = Field(default=2, ge=1, le=3)
    budget_ms: float = Field(default=4000.0, ge=250.0, le=8000.0)
    idempotency_key: Optional[str] = None


class DatasetAuditRequest(BaseModel):
    dataset_name: str = "yorvyn_curated_garments"
    dataset_version: str = "17.0.0"
    seed: int = 42
    samples: List[CuratedSample]


class OfflineTrainRequest(DatasetAuditRequest):
    model_name: str = "yorvyn_category_probe_v17"
    version: str = "17.0.0-rc1"
    epochs: int = Field(default=12, ge=1, le=50)
    lr: float = Field(default=0.05, gt=0.0, le=1.0)


@router.get("/health")
def intelligence_health():
    catalog = unified_model_registry.get_yip_model_catalog()
    available_count = sum(1 for m in catalog if m.availability == "AVAILABLE")
    return {
        "status": "ready",
        "platform": "YORVYN Intelligence Platform (YIP)",
        "phase": "17.0",
        "capabilities_registered": len(garment_capabilities.entries()),
        "models_total": len(catalog),
        "models_available_locally": available_count,
        "hardware": unified_model_registry.get_hardware_profile(),
        "rag": knowledge_rag.get_status(),
        "integrations": unified_model_registry.get_external_providers_and_frameworks(),
        "telemetry": inference_telemetry.snapshot(),
    }


@router.get("/capabilities")
def list_capabilities(current_user: UserContext = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "count": len(garment_capabilities.entries()),
        "capabilities": [c.model_dump() for c in garment_capabilities.entries()],
    }


@router.get("/models")
def list_models(current_user: UserContext = Depends(get_current_user)):
    models = unified_model_registry.get_yip_model_catalog()
    return {
        "user_id": current_user.user_id,
        "hardware": unified_model_registry.get_hardware_profile(),
        "models": [m.model_dump() for m in models],
        "telemetry": inference_telemetry.snapshot(),
    }


@router.post("/orchestrate")
async def orchestrate_intelligence(
    instruction: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    subcategory: Optional[str] = Form(None),
    avatar_profile_id: str = Form("standard_175"),
    include_knowledge: bool = Form(True),
    include_personalization: bool = Form(False),
    consent_granted: bool = Form(True),
    auto_optimize: bool = Form(False),
    idempotency_key: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    glb_file: Optional[UploadFile] = File(None),
    current_user: UserContext = Depends(get_current_user),
):
    img_bytes = await image.read() if image is not None else None
    if img_bytes and len(img_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds limit.")
    glb_bytes = await glb_file.read() if glb_file is not None else None
    if glb_bytes and len(glb_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded GLB exceeds limit.")

    res = await yip_orchestrator.execute_plan(
        owner_id=current_user.user_id,
        instruction=instruction,
        image_bytes=img_bytes,
        glb_bytes=glb_bytes,
        category=category,
        subcategory=subcategory,
        avatar_profile_id=avatar_profile_id,
        include_knowledge=include_knowledge,
        include_personalization=include_personalization,
        consent_granted=consent_granted,
        auto_optimize=auto_optimize,
        idempotency_key=idempotency_key,
    )
    return res.model_dump()


@router.post("/multimodal/analyze")
async def analyze_multimodal(
    instruction: Optional[str] = Form(None),
    include_embedding: bool = Form(True),
    image: Optional[UploadFile] = File(None),
    current_user: UserContext = Depends(get_current_user),
):
    img_bytes = await image.read() if image is not None else None
    if img_bytes and len(img_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds limit.")
    if not img_bytes and instruction is None:
        raise HTTPException(status_code=400, detail="Provide at least an image or an instruction.")
    out = multimodal_intelligence.understand(
        image_bytes=img_bytes,
        instruction=instruction,
        include_embedding=include_embedding,
    )
    return out.model_dump()


@router.post("/multimodal/similarity")
def rank_multimodal_similarity(
    req: SimilarityRequest,
    current_user: UserContext = Depends(get_current_user),
):
    matches = multimodal_intelligence.rank_similarity(
        req.candidates,
        query_text=req.query_text,
        query_embedding=req.query_embedding,
        top_k=req.top_k,
    )
    return {
        "user_id": current_user.user_id,
        "matches": [m.model_dump() for m in matches],
    }


@router.post("/fashion/analyze")
async def analyze_fashion(
    category: Optional[str] = Form(None),
    subcategory: Optional[str] = Form(None),
    silhouette: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    back_image: Optional[UploadFile] = File(None),
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.core.upload_validation import read_and_validate_image_upload
    front_b = await read_and_validate_image_upload(image, field_name="image") if image is not None else None
    back_b = await read_and_validate_image_upload(back_image, field_name="back_image") if back_image is not None else None
    rep = fashion_intelligence_v17.analyze_garment(
        image_bytes=front_b,
        back_image_bytes=back_b,
        category=category,
        subcategory=subcategory,
        silhouette=silhouette,
    )
    return rep.model_dump()


@router.post("/fit/analyze")
async def analyze_fit(
    req: Optional[FitAnalyzeRequest] = None,
    current_user: UserContext = Depends(get_current_user),
):
    payload = req or FitAnalyzeRequest()
    glb_bytes = _load_owned_job_glb(payload.job_id, current_user) if payload.job_id else None
    rep = fit_intelligence.analyze_fit(
        category=payload.category,
        glb_bytes=glb_bytes,
        avatar_profile_id=payload.avatar_profile_id,
        custom_measurements=payload.custom_measurements,
    )
    return rep.model_dump()


@router.post("/fit/analyze-glb")
async def analyze_fit_glb(
    category: str = Form("tops"),
    avatar_profile_id: str = Form("standard_175"),
    glb_file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
):
    glb_bytes = await glb_file.read()
    if len(glb_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded GLB exceeds limit.")
    rep = fit_intelligence.analyze_fit(
        category=category,
        glb_bytes=glb_bytes,
        avatar_profile_id=avatar_profile_id,
    )
    return rep.model_dump()


@router.post("/knowledge/search")
def search_knowledge(
    req: KnowledgeSearchRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return knowledge_rag.search(
        req.query,
        domains=req.domains,
        owner_id=current_user.user_id,
        verified_only=req.verified_only,
        top_k=req.top_k,
    ).model_dump()


@router.post("/knowledge/ingest")
def ingest_knowledge(
    req: KnowledgeIngestRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    owner_scope: Optional[str] = current_user.user_id
    verif = "PROVISIONAL"
    if req.shared_corpus:
        _verify_admin_access(request, current_user)
        owner_scope = None
        verif = "VERIFIED"
    try:
        doc = knowledge_rag.ingest_document(
            doc_id=req.doc_id,
            domain=req.domain,
            title=req.title,
            content=req.content,
            source=req.source,
            author_or_publisher=req.author_or_publisher,
            license_name=req.license,
            document_ref=req.document_ref,
            section_ref=req.section_ref,
            verification_status=verif,
            owner_id=owner_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return doc.model_dump()


@router.post("/evaluation/critic")
def evaluate_job_candidate(
    req: CriticJobRequest,
    current_user: UserContext = Depends(get_current_user),
):
    glb_bytes = _load_owned_job_glb(req.job_id, current_user)
    rep = evaluation_critic.evaluate_candidate(
        glb_bytes,
        category=req.category,
        expected_components=req.expected_components,
        avatar_profile_id=req.avatar_profile_id,
    )
    return rep.model_dump()


@router.post("/evaluation/critic-glb")
async def evaluate_uploaded_glb(
    category: str = Form("tops"),
    avatar_profile_id: str = Form("standard_175"),
    glb_file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
):
    glb_bytes = await glb_file.read()
    if len(glb_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded GLB exceeds limit.")
    rep = evaluation_critic.evaluate_candidate(
        glb_bytes,
        category=category,
        avatar_profile_id=avatar_profile_id,
    )
    return rep.model_dump()


@router.post("/evaluation/optimize")
def optimize_job_candidate(
    req: OptimizeJobRequest,
    current_user: UserContext = Depends(get_current_user),
):
    glb_bytes = _load_owned_job_glb(req.job_id, current_user)
    _best, res = candidate_optimizer.optimize_candidate(
        glb_bytes,
        category=req.category,
        avatar_profile_id=req.avatar_profile_id,
        expected_components=req.expected_components,
        max_iterations=req.max_iterations,
        budget_ms=req.budget_ms,
        owner_id=current_user.user_id,
        idempotency_key=req.idempotency_key,
    )
    return res.model_dump()


@router.get("/personalization/recommendations")
def get_personalized_recommendations(
    occasion: Optional[str] = Query(None),
    consent_granted: bool = Query(True),
    top_k: int = Query(6, ge=1, le=20),
    current_user: UserContext = Depends(get_current_user),
):
    rep = personalization_engine.recommend_for_user(
        user_id=current_user.user_id,
        consent_granted=consent_granted,
        occasion=occasion,
        top_k=top_k,
    )
    return rep.model_dump()


@router.post("/learning/dataset-audit")
def audit_learning_dataset(
    req: DatasetAuditRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    _verify_admin_access(request, current_user)
    res = dataset_curator.audit_and_split(
        req.samples,
        dataset_name=req.dataset_name,
        dataset_version=req.dataset_version,
        seed=req.seed,
    )
    return res.report.model_dump()


@router.post("/learning/train-offline")
def run_offline_training(
    req: OfflineTrainRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    _verify_admin_access(request, current_user)
    audited = dataset_curator.audit_and_split(
        req.samples,
        dataset_name=req.dataset_name,
        dataset_version=req.dataset_version,
        seed=req.seed,
    )
    if not audited.report.ready_for_offline_training:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Dataset failed curation/split gates.",
                "audit_report": audited.report.model_dump(),
            },
        )
    train_rep = dataset_curator.train_offline_probe(
        audited.splits,
        model_name=req.model_name,
        version=req.version,
        epochs=req.epochs,
        lr=req.lr,
        seed=req.seed,
    )
    return {
        "dataset_audit": audited.report.model_dump(),
        "training_report": train_rep.model_dump(),
    }


# ── Phase 17.0 Extension: Fashion Recommendation Intelligence ────────────────────────


class RecommendationProfilePreferencesRequest(BaseModel):
    preferences: Dict[str, List[str]]
    replace: bool = False


class RecommendationConsentRequest(BaseModel):
    consent_granted: bool


class RecommendationResetRequest(BaseModel):
    scope: str = Field(default="all", pattern="^(all|explicit|inferred|session)$")


class RecommendationSessionContextRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    occasion: Optional[str] = None
    search_query: Optional[str] = None
    anchor_garment: Optional[Dict[str, Any]] = None


class RecommendationQueryRequest(BaseModel):
    mode: str = "hybrid"
    surface: str = "wardrobe"
    session_id: Optional[str] = None
    occasion: Optional[str] = None
    season: Optional[str] = None
    search_query: Optional[str] = None
    anchor_item: Optional[Dict[str, Any]] = None
    query_embedding: Optional[List[float]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    preset_name: Optional[str] = None
    custom_weights: Optional[RankingWeightsConfig] = None
    top_k: int = Field(default=8, ge=1, le=50)
    exploration_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    include_knowledge: bool = False
    consent_granted: Optional[bool] = None
    min_cf_users: Optional[int] = Field(default=None, ge=1, le=100)


class OutfitRecommendationRequest(BaseModel):
    occasion: str = "casual"
    season: Optional[str] = None
    anchor_item: Optional[Dict[str, Any]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    max_outfits: int = Field(default=3, ge=1, le=10)


class RecommendationFeedbackRequest(BaseModel):
    interaction_type: str
    item_data: Optional[Dict[str, Any]] = None
    search_query: Optional[str] = None
    session_id: Optional[str] = None
    consent_granted: Optional[bool] = None
    purchase_authorized: bool = False


class RecommendationEvaluateRequest(BaseModel):
    dataset_name: str = "yorvyn_chronological_eval"
    k: int = Field(default=5, ge=1, le=20)
    preset_name: str = "hybrid_balanced"
    mode: str = "hybrid"
    train_ratio: float = Field(default=0.7, gt=0.1, lt=0.95)
    run_ablation: bool = True
    min_cf_users: int = Field(default=5, ge=1, le=100)
    catalog_items: List[Dict[str, Any]]
    events: List[ChronologicalEvent]


@router.get("/recommendations/taxonomy")
def get_recommendation_taxonomy(current_user: UserContext = Depends(get_current_user)):
    return {"user_id": current_user.user_id, **get_taxonomy_summary()}


@router.get("/recommendations/profile")
def get_recommendation_profile(current_user: UserContext = Depends(get_current_user)):
    return recommendation_profile_store.get_profile(current_user.user_id).model_dump()


@router.post("/recommendations/profile/preferences")
def update_recommendation_preferences(
    req: RecommendationProfilePreferencesRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return recommendation_profile_store.set_explicit_preferences(
        current_user.user_id, req.preferences, replace=req.replace
    ).model_dump()


@router.post("/recommendations/profile/consent")
def update_recommendation_consent(
    req: RecommendationConsentRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return recommendation_profile_store.set_consent(current_user.user_id, req.consent_granted)


@router.post("/recommendations/profile/reset")
def reset_recommendation_profile(
    req: RecommendationResetRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return recommendation_profile_store.reset_profile(current_user.user_id, scope=req.scope)


@router.post("/recommendations/session")
def update_recommendation_session(
    req: RecommendationSessionContextRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return recommendation_profile_store.update_session_context(
        owner_id=current_user.user_id,
        session_id=req.session_id,
        occasion=req.occasion,
        anchor_garment=req.anchor_garment,
        search_query=req.search_query,
    ).model_dump()


def _run_recommendation_mode(mode: str, req: RecommendationQueryRequest, user_id: str) -> Dict[str, Any]:
    return fashion_recommendation_engine.recommend(
        owner_id=user_id,
        candidates=req.candidates,
        mode=mode,
        surface=req.surface,
        session_id=req.session_id,
        occasion=req.occasion,
        season=req.season,
        search_query=req.search_query,
        anchor_item=req.anchor_item,
        query_embedding=req.query_embedding,
        preset_name=req.preset_name,
        custom_weights=req.custom_weights,
        top_k=req.top_k,
        exploration_rate=req.exploration_rate,
        include_knowledge=req.include_knowledge,
        consent_granted=req.consent_granted,
        min_cf_users=req.min_cf_users,
    ).model_dump()


@router.post("/recommendations/hybrid")
def recommend_hybrid(req: RecommendationQueryRequest, current_user: UserContext = Depends(get_current_user)):
    eff_mode = req.mode if req.mode in {"hybrid", "neural_hybrid", "neural_retrieval", "neural_ranking", "neural_sequential", "content", "category", "collaborative"} else "hybrid"
    return _run_recommendation_mode(eff_mode, req, current_user.user_id)


@router.post("/recommendations/content")
def recommend_content(req: RecommendationQueryRequest, current_user: UserContext = Depends(get_current_user)):
    return _run_recommendation_mode("content", req, current_user.user_id)


@router.post("/recommendations/categories")
def recommend_categories(req: RecommendationQueryRequest, current_user: UserContext = Depends(get_current_user)):
    return _run_recommendation_mode("category", req, current_user.user_id)


@router.post("/recommendations/collaborative")
def recommend_collaborative(req: RecommendationQueryRequest, current_user: UserContext = Depends(get_current_user)):
    return _run_recommendation_mode("collaborative", req, current_user.user_id)


@router.post("/recommendations/outfit")
def recommend_outfits(req: OutfitRecommendationRequest, current_user: UserContext = Depends(get_current_user)):
    return fashion_recommendation_engine.recommend_outfit(
        owner_id=current_user.user_id,
        candidates=req.candidates,
        anchor_item=req.anchor_item,
        occasion=req.occasion,
        season=req.season,
        max_outfits=req.max_outfits,
    ).model_dump()


@router.post("/recommendations/feedback")
def record_recommendation_signal(
    req: RecommendationFeedbackRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return recommendation_profile_store.record_interaction(
        owner_id=current_user.user_id,
        interaction_type=req.interaction_type,
        item_data=req.item_data,
        search_query=req.search_query,
        session_id=req.session_id,
        consent_granted=req.consent_granted,
        purchase_authorized=req.purchase_authorized,
    )


@router.post("/recommendations/evaluate")
def evaluate_recommendation_benchmark(
    req: RecommendationEvaluateRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    _verify_admin_access(request, current_user)
    return recommendation_evaluator.evaluate_chronological(
        catalog_items=req.catalog_items,
        events=req.events,
        k=req.k,
        preset_name=req.preset_name,
        mode=req.mode,
        dataset_name=req.dataset_name,
        train_ratio=req.train_ratio,
        run_ablation=req.run_ablation,
        min_cf_users=req.min_cf_users,
    ).model_dump()


class NeuralEmbeddingsRequest(BaseModel):
    candidates: Optional[List[Dict[str, Any]]] = None
    top_k: int = Field(default=8, ge=1, le=50)


class NeuralTrainRequest(BaseModel):
    dataset_name: str = "yorvyn_neural_rec_benchmark"
    k: int = Field(default=5, ge=1, le=20)
    epochs: int = Field(default=24, ge=1, le=50)
    lr: float = Field(default=0.03, gt=0.0, le=0.5)
    seed: int = 42
    catalog_items: List[Dict[str, Any]]
    events: List[CuratedInteractionEvent]


@router.post("/recommendations/neural/embeddings")
def get_neural_recommendation_embeddings(
    req: NeuralEmbeddingsRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return fashion_recommendation_engine.get_neural_embeddings_and_retrieval(
        owner_id=current_user.user_id,
        candidates=req.candidates,
        top_k=req.top_k,
    )


@router.post("/recommendations/neural/train")
def train_neural_recommendation_models(
    req: NeuralTrainRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    _verify_admin_access(request, current_user)
    return neural_recommendation_trainer.train_and_benchmark(
        catalog_items=req.catalog_items,
        events=req.events,
        dataset_name=req.dataset_name,
        k=req.k,
        epochs=req.epochs,
        lr=req.lr,
        seed=req.seed,
    ).model_dump()


# ── Phase 17.3: External Web Intelligence (Tavily) & LangGraph Workflows ─────────────


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=400)
    search_depth: str = Field(default="basic", pattern="^(basic|advanced)$")
    topic: str = Field(default="general", pattern="^(general|news)$")
    max_results: int = Field(default=5, ge=1, le=10)
    days: Optional[int] = Field(default=None, ge=1, le=365)
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None
    include_internal_rag: bool = True
    session_id: Optional[str] = None


class WebExtractRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=20)
    extract_depth: str = Field(default="basic", pattern="^(basic|advanced)$")
    include_images: bool = False
    session_id: Optional[str] = None


class WebResearchRequest(BaseModel):
    topic_input: str = Field(..., min_length=3, max_length=1000)
    session_id: Optional[str] = None


class WorkflowExecuteRequest(BaseModel):
    workflow_name: str = Field(..., pattern="^(garment\\.research|fashion\\.discovery|design\\.assistance)$")
    payload: Dict[str, Any] = Field(default_factory=dict)
    thread_id: Optional[str] = None
    max_steps: int = Field(default=8, ge=2, le=8)
    deadline_s: float = Field(default=20.0, ge=1.0, le=60.0)


class WorkflowResumeRequest(BaseModel):
    thread_id: str = Field(..., min_length=4, max_length=120)
    human_confirmed: bool = True
    deadline_s: float = Field(default=20.0, ge=1.0, le=60.0)
    expected_operation_hash: Optional[str] = None
    confirmation_idempotency_key: Optional[str] = None


class WorkflowCancelRequest(BaseModel):
    thread_id: str = Field(..., min_length=4, max_length=120)


class ExternalEvidencePromoteRequest(BaseModel):
    doc_id: str = Field(..., min_length=2, max_length=120)
    domain: str
    title: Optional[str] = None
    license_name: str = "CC-BY-4.0"
    explicit_approval: bool = False
    rights_verified: bool = False
    item: Dict[str, Any]


@router.get("/providers")
def list_external_providers_and_frameworks(current_user: UserContext = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "integrations": unified_model_registry.get_external_providers_and_frameworks(),
    }


@router.post("/web/search")
def search_external_web(
    req: WebSearchRequest,
    current_user: UserContext = Depends(get_current_user),
):
    if req.include_internal_rag:
        return unified_knowledge.retrieve(
            req.query,
            owner_id=current_user.user_id,
            include_external=True,
            external_max_results=req.max_results,
            session_id=req.session_id,
        ).model_dump()
    return tavily_web_adapter.search_web(
        req.query,
        owner_id=current_user.user_id,
        search_depth=req.search_depth,
        topic=req.topic,
        max_results=req.max_results,
        days=req.days,
        include_domains=req.include_domains,
        exclude_domains=req.exclude_domains,
        session_id=req.session_id,
    ).model_dump()


@router.post("/web/extract")
def extract_external_web_content(
    req: WebExtractRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return tavily_web_adapter.extract_content(
        req.urls,
        owner_id=current_user.user_id,
        extract_depth=req.extract_depth,
        include_images=req.include_images,
        session_id=req.session_id,
    ).model_dump()


@router.post("/web/research")
def research_external_web_topic(
    req: WebResearchRequest,
    current_user: UserContext = Depends(get_current_user),
):
    return tavily_web_adapter.research_topic(
        req.topic_input,
        owner_id=current_user.user_id,
        session_id=req.session_id,
    ).model_dump()


@router.post("/workflows/execute")
async def execute_langgraph_workflow(
    req: WorkflowExecuteRequest,
    current_user: UserContext = Depends(get_current_user),
):
    try:
        rec = await langgraph_workflow_adapter.execute_workflow(
            workflow_name=req.workflow_name,
            owner_id=current_user.user_id,
            payload=req.payload,
            thread_id=req.thread_id,
            max_steps=req.max_steps,
            deadline_s=req.deadline_s,
        )
        return rec.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workflows/status/{thread_id}")
def get_langgraph_workflow_status(
    thread_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    try:
        rec = langgraph_workflow_adapter.get_status(thread_id=thread_id, owner_id=current_user.user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Workflow thread '{thread_id}' not found.")
    return rec.model_dump()


@router.post("/workflows/resume")
async def resume_langgraph_workflow(
    req: WorkflowResumeRequest,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.langgraph_workflows import (
        ConfirmationExpiredError,
        WorkflowConflictError,
    )

    try:
        rec = await langgraph_workflow_adapter.resume_workflow(
            thread_id=req.thread_id,
            owner_id=current_user.user_id,
            human_confirmed=req.human_confirmed,
            deadline_s=req.deadline_s,
            expected_operation_hash=req.expected_operation_hash,
            confirmation_idempotency_key=req.confirmation_idempotency_key,
        )
        return rec.model_dump()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConfirmationExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except WorkflowConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/cancel")
def cancel_langgraph_workflow(
    req: WorkflowCancelRequest,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.langgraph_workflows import WorkflowConflictError

    try:
        rec = langgraph_workflow_adapter.cancel_workflow(
            thread_id=req.thread_id,
            owner_id=current_user.user_id,
        )
        return rec.model_dump()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/workflows/{thread_id}/events")
def get_langgraph_workflow_events(
    thread_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    try:
        events = langgraph_workflow_adapter.get_node_events(
            thread_id=thread_id,
            owner_id=current_user.user_id,
        )
        return {"thread_id": thread_id, "events": [e.model_dump() for e in events]}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/knowledge/external/promote")
def promote_external_evidence_route(
    req: ExternalEvidencePromoteRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.tavily_web_adapter import TavilyResultItem, URLSecurityError

    _verify_admin_access(request, current_user)
    try:
        dom = KnowledgeDomain(req.domain)
        item = TavilyResultItem(**req.item)
        doc = unified_knowledge.promote_validated_external_item(
            item,
            doc_id=req.doc_id,
            domain=dom,
            title=req.title,
            license_name=req.license_name,
            explicit_approval=req.explicit_approval,
            approved_by=current_user.user_id,
            rights_verified=req.rights_verified,
        )
        return doc.model_dump()
    except (ValueError, URLSecurityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Phase 17.4 — Neural Recommendation Generalization, Promotion Gates & Experiments
# ---------------------------------------------------------------------------


class ExperimentAssignRequest(BaseModel):
    experiment_id: str = "phase17_4_hybrid_vs_neural_v1"


class ExperimentLogRequest(BaseModel):
    experiment_id: str = "phase17_4_hybrid_vs_neural_v1"
    action: str = Field(..., description="'impression' or 'outcome'")
    recommended_items: List[Dict[str, Any]] = Field(default_factory=list)
    arm: Optional[str] = None
    impression_id: Optional[str] = None
    item_id: Optional[str] = None
    outcome_type: Optional[str] = None
    purchase_authorized: bool = False


class NeuralPromotionCheckRequest(BaseModel):
    model_id: str
    version: str = "17.4.0-rc1"
    is_real_production_traffic: bool = False
    accepted_events: int = 0
    user_count: int = 0
    consent_compliant: bool = True
    leak_free: bool = True
    model_metrics: Dict[str, Any] = Field(default_factory=dict)
    baseline_ndcg: float = 0.0
    baseline_diversity: float = 0.0
    checkpoint_path: Optional[str] = None
    checkpoint_sha256: Optional[str] = None


@router.post("/recommendations/experiments/assign")
async def assign_recommendation_experiment_arm(
    req: ExperimentAssignRequest,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.recommendation_experiments import recommendation_experiments

    return recommendation_experiments.assign_arm(
        owner_id=current_user.user_id,
        experiment_id=req.experiment_id,
    )


@router.post("/recommendations/experiments/log")
async def log_recommendation_experiment_event(
    req: ExperimentLogRequest,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.recommendation_experiments import recommendation_experiments

    act = req.action.strip().lower()
    if act == "impression":
        imp = recommendation_experiments.log_impression(
            owner_id=current_user.user_id,
            recommended_items=req.recommended_items,
            arm=req.arm,
            experiment_id=req.experiment_id,
        )
        return imp.model_dump()
    if act == "outcome":
        if not req.impression_id or not req.item_id or not req.outcome_type:
            raise HTTPException(
                status_code=400,
                detail="impression_id, item_id, and outcome_type are required for outcome logging",
            )
        try:
            return recommendation_experiments.log_outcome(
                impression_id=req.impression_id,
                owner_id=current_user.user_id,
                item_id=req.item_id,
                outcome_type=req.outcome_type,
                purchase_authorized=req.purchase_authorized,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="action must be 'impression' or 'outcome'")


@router.get("/recommendations/experiments/{experiment_id}/report")
async def get_recommendation_experiment_report(
    experiment_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.recommendation_experiments import recommendation_experiments

    _verify_admin_access(request, current_user)
    return recommendation_experiments.get_report(experiment_id=experiment_id).model_dump()


@router.post("/recommendations/neural/generalize")
async def run_neural_generalization_benchmark_route(
    request: Request,
    k: int = Query(5, ge=1, le=20),
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.neural_generalization_benchmark import (
        run_phase17_4_generalization_benchmark,
    )

    _verify_admin_access(request, current_user)
    report = run_phase17_4_generalization_benchmark(k=k)
    return report.model_dump()


@router.post("/recommendations/neural/promote")
async def evaluate_neural_model_promotion(
    req: NeuralPromotionCheckRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.neural_generalization_benchmark import evaluate_promotion_gates

    _verify_admin_access(request, current_user)
    decision = evaluate_promotion_gates(
        model_id=req.model_id,
        version=req.version,
        is_real_production_traffic=req.is_real_production_traffic,
        accepted_events=req.accepted_events,
        user_count=req.user_count,
        consent_compliant=req.consent_compliant,
        leak_free=req.leak_free,
        model_metrics=req.model_metrics,
        baseline_ndcg=req.baseline_ndcg,
        baseline_diversity=req.baseline_diversity,
        checkpoint_path=req.checkpoint_path,
        checkpoint_sha256=req.checkpoint_sha256,
    )
    return decision.model_dump()


# ---------------------------------------------------------------------------
# Phase 17.5 — Guided Live Garment Capture & Reconstruction Readiness Gate
# ---------------------------------------------------------------------------


class CaptureSessionCreateRequest(BaseModel):
    garment_category: str = Field(default="tops", min_length=2, max_length=60)
    garment_subcategory: str = Field(default="", max_length=60)
    capture_mode: str = Field(default="hanger", pattern="^(hanger|mannequin|flat_lay|worn)$")
    consent_granted: bool = True


class CaptureFinalizeRequest(BaseModel):
    idempotency_key: Optional[str] = Field(default=None, max_length=120)


def _raise_capture_http(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/capture/sessions")
def create_capture_session(
    req: CaptureSessionCreateRequest,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import CaptureMode, capture_session_store

    try:
        rec = capture_session_store.create_session(
            owner_id=current_user.user_id,
            garment_category=req.garment_category,
            garment_subcategory=req.garment_subcategory,
            capture_mode=CaptureMode(req.capture_mode),
            consent_granted=req.consent_granted,
        )
        return rec.model_dump()
    except Exception as exc:
        _raise_capture_http(exc)


@router.get("/capture/sessions/{session_id}")
def get_capture_session(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import capture_session_store

    try:
        return capture_session_store.get_session(
            session_id=session_id, owner_id=current_user.user_id
        ).model_dump()
    except Exception as exc:
        _raise_capture_http(exc)


@router.post("/capture/sessions/{session_id}/images")
async def upload_captured_view(
    session_id: str,
    image: UploadFile = File(...),
    view_label: str = Form("front"),
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import (
        MAX_CAPTURE_IMAGE_BYTES,
        capture_session_store,
    )

    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await image.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_CAPTURE_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Captured image exceeds 15MB limit.")
        chunks.append(chunk)
    raw_bytes = b"".join(chunks)

    try:
        view_rec = capture_session_store.add_captured_image(
            session_id=session_id,
            owner_id=current_user.user_id,
            image_bytes=raw_bytes,
            view_label=view_label,
            filename=image.filename,
        )
        readiness = capture_session_store.evaluate_readiness(
            session_id=session_id, owner_id=current_user.user_id
        )
        return {"captured_view": view_rec.model_dump(), "readiness": readiness.model_dump()}
    except Exception as exc:
        _raise_capture_http(exc)


@router.delete("/capture/sessions/{session_id}/images/{image_id}")
def delete_captured_view(
    session_id: str,
    image_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import capture_session_store

    try:
        capture_session_store.remove_captured_image(
            session_id=session_id, owner_id=current_user.user_id, image_id=image_id
        )
        readiness = capture_session_store.evaluate_readiness(
            session_id=session_id, owner_id=current_user.user_id
        )
        return {"deleted_image_id": image_id, "readiness": readiness.model_dump()}
    except Exception as exc:
        _raise_capture_http(exc)


@router.post("/capture/sessions/{session_id}/evaluate")
def evaluate_capture_session_readiness(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import capture_session_store

    try:
        return capture_session_store.evaluate_readiness(
            session_id=session_id, owner_id=current_user.user_id
        ).model_dump()
    except Exception as exc:
        _raise_capture_http(exc)


@router.post("/capture/sessions/{session_id}/finalize")
def finalize_capture_session_handoff(
    session_id: str,
    req: CaptureFinalizeRequest = CaptureFinalizeRequest(),
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import capture_session_store

    try:
        return capture_session_store.finalize_and_handoff(
            session_id=session_id,
            owner_id=current_user.user_id,
            idempotency_key=req.idempotency_key,
        )
    except Exception as exc:
        _raise_capture_http(exc)


@router.delete("/capture/sessions/{session_id}")
def cancel_capture_session(
    session_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    from backend.app.services.intelligence.capture_intelligence import capture_session_store

    try:
        return capture_session_store.cancel_and_purge_session(
            session_id=session_id, owner_id=current_user.user_id
        )
    except Exception as exc:
        _raise_capture_http(exc)


