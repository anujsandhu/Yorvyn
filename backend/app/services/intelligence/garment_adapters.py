"""Server-side bindings shared by Stylist and reference-evaluation callers."""
from .garment_execution import Binding, GarmentRouter
from .garment_policy import route_intent
from .local_perception import classifier_prediction
from .component_evidence import analyze_garment_components
from .pattern_construction_engine import pattern_construction_engine
from backend.app.services.ai.contracts import CanonicalGarmentSpecificationV2, ComponentAnalysisBundle
from backend.app.services.garments.reconstruction.pattern_geometry import ConstructionToGeometryHandoff
from backend.app.services.llm.garment_plan import GarmentPlan
from backend.app.services.garments.evaluation.geometric_evaluator import GeometricEvaluator
from backend.app.services.intelligence.multimodal_intelligence import multimodal_intelligence
from backend.app.services.intelligence.fashion_intelligence_v17 import fashion_intelligence_v17
from backend.app.services.intelligence.fit_intelligence import fit_intelligence
from backend.app.services.intelligence.knowledge_rag import knowledge_rag
from backend.app.services.intelligence.evaluation_critic import evaluation_critic
from backend.app.services.intelligence.candidate_optimizer import candidate_optimizer
from backend.app.services.intelligence.personalization_engine import personalization_engine
from backend.app.services.learning.dataset_curator import dataset_curator
from backend.app.services.intelligence.yip_orchestrator import yip_orchestrator
from backend.app.services.motion.motion_core import (
    AdaptiveFabricProfileService,
    AnimationAssetSecurityValidator,
    ComputePolicyAdvisor,
    MotionEvaluationService,
    MotionStateMachine,
    SkeletonRetargetingValidator,
)


def surface_comparison(prediction, reference, coordinates=None):
    if prediction is None or reference is None:
        return {"status": "NOT_EVALUATED", "reason": "paired geometry required"}
    return GeometricEvaluator.evaluate_surfaces(prediction, reference, coordinate_contract=coordinates)


def validated_candidate(value):
    data, report = value
    return bool(data) and report.get("is_valid") is True


def create_garment_router(isolate_subject, multiview_identify_endpoint, multiview_reconstruct_endpoint,
                          candidate_bytes, candidate_context, control_job):
    return GarmentRouter({
        "intent.plan": Binding(route_intent, lambda v: isinstance(v[0], GarmentPlan), "garment-intent-v1", "closed action vocabulary", 45),
        "subject.select": Binding(isolate_subject, lambda v: isinstance(v[1], list), "instance-detector", "one subject or choices", 90),
        "views.identify": Binding(multiview_identify_endpoint, lambda v: isinstance(v, CanonicalGarmentSpecificationV2)
                                  and not v.validate_evidence_integrity(), "multiview-v2", "source-cited V2 contract", 240, owned=True),
        "components.identify": Binding(analyze_garment_components, lambda v: isinstance(v, ComponentAnalysisBundle),
                                       "component-evidence-v16.1", "source-cited visibility, uncertainty, and structure graph", 120),
        "structure.construct": Binding(pattern_construction_engine.build_construction, lambda v: isinstance(v, ConstructionToGeometryHandoff),
                                       "pattern-construction-v16.2", "validated panels, seams, and assembly DAG", 90),
        "pattern.interpret": Binding(pattern_construction_engine.build_construction, lambda v: isinstance(v, ConstructionToGeometryHandoff)
                                     and v.validation_report.is_valid, "pattern-geometry-v16.2", "valid 2D polygons, edge seams, and handoff contract", 90),
        "geometry.submit": Binding(multiview_reconstruct_endpoint, lambda v: bool(v.get("job_id")), "category-engine-registry",
                                   "front view, source hashes, entitlement and job ID", 90, owned=True),
        "candidate.inspect": Binding(candidate_bytes, validated_candidate, "mesh-validation", "owner, checksum and mesh report", 60, owned=True),
        "candidate.edit": Binding(candidate_bytes, validated_candidate, "bounded-glb-edit", "validated edited mesh", 60, owned=True),
        "candidate.history": Binding(candidate_context, lambda v: isinstance(v, dict), "conversation-repository", "session and owner", 30, owned=True),
        "job.control": Binding(control_job, lambda v: isinstance(v, dict), "garment-job-manager", "owner and legal transition", 30, owned=True),
        "classify.category": Binding(classifier_prediction, lambda v: v is not None, "universal-garment-classifier",
                                     "release digest, taxonomy, finite normalized distributions", 45),
        "evaluate.surface": Binding(surface_comparison, lambda v: isinstance(v, dict), "surface-sampling-v15.2",
                                    "paired reference geometry", 120),
        "evaluate.silhouette": Binding(GeometricEvaluator.evaluate_silhouette, lambda v: isinstance(v, dict), "mask-comparison-v15.2",
                                       "registered mask dimensions", 30),
        "animation.retarget": Binding(SkeletonRetargetingValidator.validate_and_plan, lambda v: getattr(v, "target_skeleton_kind", None) is not None,
                                      "ara-skeleton-retarget-v16.9", "validated bone map or explicit incompatibility", 15),
        "animation.validate": Binding(AnimationAssetSecurityValidator.validate_glb_animation_payload, lambda v: hasattr(v, "export_kind"),
                                      "glb-animation-validator-v16.9", "verified glTF animation/skin/export classification", 30),
        "motion.synchronize": Binding(MotionStateMachine.evaluate_transition, lambda v: hasattr(v, "resulting_state"),
                                      "motioncore-fsm-v16.9", "deterministic state transition under single mixer ownership", 10),
        "fabric.profile": Binding(AdaptiveFabricProfileService.resolve_profile, lambda v: v.is_measured_physical is False,
                                  "adaptive-fabric-profile-v16.9", "explicit estimated material physics profile", 15),
        "compute.select": Binding(ComputePolicyAdvisor.select, lambda v: hasattr(v, "quality_tier"),
                                  "compute-policy-advisor-v16.9", "hardware-aware backend and quality tier selection", 10),
        "motion.evaluate": Binding(MotionEvaluationService.evaluate_canonical_sequences, lambda v: hasattr(v, "pose_metrics"),
                                   "motion-sequence-evaluator-v16.9", "canonical pose stability & latency percentiles", 45),
        # Phase 17.0 YIP Unified Capabilities
        "multimodal.understand": Binding(multimodal_intelligence.understand, lambda v: hasattr(v, "request_sha256"),
                                         "yip-multimodal-v17", "model identity receipts + quality checks", 60),
        "multimodal.similarity": Binding(multimodal_intelligence.rank_similarity, lambda v: isinstance(v, list),
                                         "yip-similarity-v17", "cosine/attribute match list with disclaimers", 30),
        "fabric.understand": Binding(fashion_intelligence_v17.analyze_garment, lambda v: hasattr(v, "fabric"),
                                     "yip-fashion-v17", "observed/inferred provenance + non-lab fabric flag", 60),
        "fit.analyze": Binding(fit_intelligence.analyze_fit, lambda v: hasattr(v, "fit_classification"),
                               "yip-fit-v17", "measured vs inferred dimensions + collision clearance", 45),
        "knowledge.retrieve": Binding(knowledge_rag.search, lambda v: hasattr(v, "hits") and all(not h.executable_authority for h in v.hits),
                                      "yip-rag-v17", "traceable cited sources + prompt-injection firewall", 20),
        "critic.evaluate": Binding(evaluation_critic.evaluate_candidate, lambda v: hasattr(v, "publication_allowed") and v.remediation_executed is False,
                                   "yip-critic-v17", "independent multi-domain defects & publication gate", 45),
        "candidate.optimize": Binding(candidate_optimizer.optimize_candidate, lambda v: isinstance(v, tuple) and hasattr(v[1], "lineage"),
                                      "yip-optimizer-v17", "bounded optimization with rollback & lineage", 90),
        "personalize.recommend": Binding(personalization_engine.recommend_for_user, lambda v: hasattr(v, "body_measurements_protected") and v.body_measurements_protected,
                                         "yip-personalization-v17", "owner-isolated consent-gated recommendations", 20),
        "learning.dataset_audit": Binding(dataset_curator.audit_and_split, lambda v: hasattr(v, "report") and not v.report.leakage_detected,
                                          "yip-dataset-curator-v17", "consent/license check & zero split leakage", 60),
        "yip.orchestrate": Binding(yip_orchestrator.execute_plan, lambda v: hasattr(v, "plan"),
                                   "yip-orchestrator-v17", "typed execution plan & validation receipts", 120),
    })


