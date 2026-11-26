"""Garment capabilities. Catalog entries describe contracts; only bound operations can run."""
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict


class State(str, Enum):
    DECLARED = "DECLARED"
    AVAILABLE = "AVAILABLE"
    EXECUTABLE = "EXECUTABLE"
    VERIFIED = "VERIFIED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class Capability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    description: str
    input_schema: str
    output_schema: str
    dependencies: Tuple[str, ...]
    compatible_models: Tuple[str, ...] = ()
    categories: Tuple[str, ...] = ("any supported garment",)
    execution_type: str
    hardware: str
    availability: State
    verification: str
    limitation: str
    failure_conditions: str
    performance_ms: Optional[float] = None
    cost_usd: Optional[float] = None


class CapabilityRegistry:
    def __init__(self, capabilities):
        self._entries = {}
        for cap in capabilities:
            if cap.id in self._entries:
                raise ValueError(f"Duplicate capability {cap.id}")
            self._entries[cap.id] = cap

    def get(self, capability_id):
        if capability_id not in self._entries:
            raise ValueError(f"Unknown garment capability {capability_id}")
        return self._entries[capability_id]

    def classifier_status(self, model):
        """Effective availability of the resident model, independent of release certification."""
        spec = self.get("classify.category")
        receipt = getattr(model, "checkpoint_receipt", {}) or {}
        expected = receipt.get("expected_sha")
        if not receipt.get("valid") or not expected or receipt.get("actual_sha") != expected:
            return State.UNAVAILABLE
        if not getattr(model, "_has_neural_model", False) or model._neural_model is None:
            return State.UNAVAILABLE
        if model.device.type not in {"cpu", "mps"}:
            return State.UNAVAILABLE
        return spec.availability

    def entries(self):
        return tuple(self._entries[k] for k in sorted(self._entries))


def capability(key, description, inputs, outputs, source, state, limit, models=(), kind="local algorithm", hardware="CPU"):
    return Capability(id=key, description=description, input_schema=inputs, output_schema=outputs,
                      dependencies=(source,), compatible_models=models, execution_type=kind, hardware=hardware,
                      availability=state, verification=(
                          "Regression or browser evidence listed in Phase 16 acceptance" if state == State.VERIFIED
                          else "No independent end-to-end certification for this capability"),
                      limitation=limit, failure_conditions=limit)


def catalog():
    verified, available, declared = State.VERIFIED, State.AVAILABLE, State.DECLARED
    rows = [
        ("intent.plan", "Interpret a garment instruction", "instruction + turn state", "GarmentPlan", "llm/garment_plan", verified, "Unsupported or ambiguous edits need clarification."),
        ("subject.select", "Select one garment in a photograph", "image + instruction", "crop or choices", "garments/intelligence/garment_instance_detector", verified, "Multiple plausible subjects require a selection."),
        ("views.identify", "Identify, deduplicate and fuse usable views", "ordered uploads", "CanonicalGarmentSpecificationV2", "ai/multiview/fusion_engine", verified, "Single views cannot establish hidden features."),
        ("classify.category", "Classify garment and subcategory", "RGB photograph", "category and subcategory distributions", "garments/intelligence/universal_garment_classifier", verified, "Requires a strict loaded release and valid probability vectors.", ("universal-garment-classifier",), "local neural", "CPU or MPS"),
        ("classify.subcategory", "Distinguish within-category variants", "RGB photograph", "55 label probabilities", "garments/intelligence/universal_garment_classifier", verified, "No holdout certification of fine-grained accuracy.", ("universal-garment-classifier",), "local neural", "CPU or MPS"),
        ("segment.foreground", "Extract the garment silhouette", "RGB photograph", "foreground alpha", "garments/segmentation/segmenter_registry", available, "A silhouette can include adjacent garments."),
        ("segment.instance", "Separate individual garment masks", "photograph + prompt", "instance masks", "garments/intelligence/grounded_sam2_adapter", declared, "No pinned Grounded-SAM checkpoint.", ("grounded_sam2",)),
        ("segment.semantic", "Parse image into garment regions", "RGB photograph", "label map", "garments/segmentation/human_parsing_segmenter", available, "Requires cached parsing weights."),
        ("landmarks.estimate", "Estimate normalized garment keypoints", "64-dimensional embedding", "12 coordinate pairs", "ml/model_registry", available, "Artifact verified. Spatial accuracy depends on reference landmarks.", ("human-pose-and-landmarks",)),
        ("pose.estimate", "Estimate body pose", "body image", "body keypoints", "ml/model_registry", declared, "Browser pose asset is a remote dependency.", ("human-pose-and-landmarks",)),
        ("depth.estimate", "Estimate relative depth", "RGB photograph", "disparity", "garments/reconstruction/neural/depth_anything_adapter", declared, "No pinned server checkpoint or metric scale.", ("depth_anything_v2",)),
        ("components.identify", "Recognize visible components, visibility states, uncertainty and structure graph", "ordered views + category", "ComponentAnalysisBundle", "intelligence/component_evidence", verified, "Real-world component precision/recall requires independently annotated component datasets; unseen regions stay NOT_OBSERVED.", ("human_parsing_segformer_b2", "universal-garment-classifier"), "local hybrid cv/neural", "CPU or MPS"),
        ("structure.construct", "Infer seams, panels and construction relationships", "garment evidence", "ConstructionToGeometryHandoff", "intelligence/pattern_construction_engine", verified, "Hidden rear construction remains inferred without back view."),
        ("pattern.interpret", "Interpret 2D garment patterns and validate assembly", "garment evidence + components", "ConstructionToGeometryHandoff", "intelligence/pattern_construction_engine", verified, "Single-photo inferred patterns carry explicit dimension uncertainty; no certified sewing ground truth."),
        ("appearance.material", "Estimate material and surface detail", "photo + mask", "material parameters", "garments/appearance/appearance_analyzer", available, "Appearance alone does not identify fabric composition."),
        ("texture.project", "Project texture and reconstruct appearance", "source image + UV", "texture maps", "garments/garment_texture_synthesizer", available, "Unseen surfaces lack texture references."),
        ("geometry.submit", "Queue evidence-conditioned reconstruction", "canonical V2 + matching views", "owned job ID", "garments/job_manager", verified, "Requires a usable front view and an available queue."),
        ("geometry.parametric", "Generate procedural category geometry", "category + measurements", "mesh", "garments/reconstruction/engine_registry", available, "Category defaults are approximate."),
        ("geometry.pattern", "Build panel-based geometry", "construction graph", "mesh", "garments/reconstruction/professional_geometry_pipeline", available, "Inferred panels lack sewing ground truth."),
        ("geometry.neural", "Run a remote neural reconstructor", "garment views", "GLB", "garments/reconstruction/neural/remote_gpu_client", State.UNAVAILABLE, "Remote weights, endpoint and independent output verification required."),
        ("geometry.multiview", "Fuse additional view constraints", "front + rear or side", "refined mesh", "garments/reconstruction/multi_view_fuser", available, "Heuristic views do not establish calibrated camera geometry."),
        ("geometry.refine", "Refine candidate topology", "GLB", "repaired GLB", "garments/chat_candidate", available, "Only duplicate or degenerate face repair is supported in chat."),
        ("uv.generate", "Generate a UV layout", "mesh", "UV coordinates", "garments/appearance/uv_reconstruction_engine", available, "A valid layout does not establish texture alignment."),
        ("stitches.generate", "Generate construction stitching", "panel relationships", "stitch paths", "garments/reconstruction/garment_construction_graph", declared, "No independent stitching reference."),
        ("cloth.simulate", "Relax cloth on a body", "garment and body mesh", "deformed mesh", "garments/fitting/cloth_relaxation_engine", available, "Material coefficients are estimates."),
        ("collision.detect", "Find garment/body intersections", "body and garment", "collision report", "garments/fitting/garment_collision_engine", available, "No physical fit reference."),
        ("avatar.attach", "Attach a wearable candidate to an avatar", "GLB + avatar", "rendered attachment", "frontend/src/engine/garments/GarmentAvatarFittingEngine", verified, "Attachment does not validate physical fit.", (), "browser renderer", "WebGL-capable browser"),
        ("candidate.edit", "Apply a bounded edit", "owned candidate + edit", "edited GLB", "garments/chat_candidate", verified, "Requires supported topology and an editable component."),
        ("candidate.inspect", "Check asset integrity and mesh structure", "owned job + edit lineage", "validated bytes + mesh report", "garments/mesh_validation_service", verified, "Structural validity alone does not establish appearance or accuracy."),
        ("candidate.history", "Restore a prior candidate", "owned turn", "prior candidate context", "api/conversational_garments", verified, "Requires a matching owner and session."),
        ("job.control", "Cancel or retry a reconstruction", "owned job + action", "job state", "garments/job_manager", verified, "Terminal job states restrict transitions."),
        ("evaluate.surface", "Measure reference surface distance", "two aligned meshes", "distance metrics", "garments/evaluation/geometric_evaluator", State.EXECUTABLE, "Requires compatible coordinates and reference geometry."),
        ("evaluate.silhouette", "Measure silhouette agreement", "two masks", "IoU and boundary errors", "garments/evaluation/geometric_evaluator", State.EXECUTABLE, "Requires aligned reference mask."),
        ("evaluate.landmarks", "Measure landmark error", "matching point annotations", "normalized localization error", "garments/evaluation/geometric_evaluator", available, "Requires matching landmark IDs and scale."),
        ("evaluate.reprojection", "Measure camera-conditioned reprojection", "views + cameras + mesh", "per-view residuals", "garments/evaluation/geometric_evaluator", declared, "Projection primitive exists. End-to-end camera evaluation remains open."),
        ("evaluate.multiview", "Check consistency across observations", "usable view records", "conflicts and readiness", "ai/multiview/fusion_engine", available, "Heuristic consistency is not camera accuracy."),
        ("evaluate.material", "Compare appearance to references", "aligned material references", "appearance measurements", "garments/evaluation/ground_truth_evaluator", declared, "No registered physical material reference for a chat turn."),
        ("evaluate.critic", "Independently criticize reconstruction quality", "candidate + references", "defects by domain", "garments/evaluation/ground_truth_evaluator", declared, "Cross-domain candidate critic belongs to Phase 16.6."),
        ("reason.external", "Request a constrained planning recommendation", "text and tool schema", "validated GarmentPlan", "llm/garment_plan", State.DEGRADED, "Account authorization, endpoint and valid tool result required.", (), "external service", "provider managed"),
        # Phase 16.9 MotionCore Unified Animation & Cloth Physics Capabilities
        ("animation.load", "Load and validate GLB skeletal animation clips", "GLB clips + skeleton", "validated AnimationClip list", "motionCore/CharacterMotionEngine", verified, "Requires compatible rigged glTF 2.0 skeleton.", ("three_animation_mixer",), "browser animation", "WebGL browser"),
        ("animation.play", "Play character skeletal animations with FSM guarantees", "MotionState + blend duration", "active animation action", "motionCore/MotionStateManager", verified, "Core transitions require compatible clips or procedural pose tracks.", ("three_animation_mixer",), "browser animation", "WebGL browser"),
        ("animation.blend", "Crossfade compatible skeletal animation states", "source + target MotionState", "blended AnimationAction", "motionCore/CharacterMotionEngine", verified, "Incompatible skeleton track counts are not force-blended.", ("three_animation_mixer",), "browser animation", "WebGL browser"),
        ("animation.retarget", "Inspect skeleton hierarchy and plan bone retargeting", "source bone list + parent hierarchy", "RetargetingPlan", "motion/motion_core", verified, "Incompatible non-humanoid rigs are explicitly rejected without guessing.", ("ara_skeleton_20",), "local algorithm", "CPU"),
        ("animation.validate", "Validate animated GLB clips, skeleton weights, and export fidelity", "GLB bytes + claimed mode", "AnimatedGLBValidationReport", "motion/motion_core", verified, "Structural validation only; does not establish visual or tailor fidelity.", ("ara_skeleton_20",), "local algorithm", "CPU"),
        ("motion.pose", "Apply anatomically bounded pose targets to skeleton", "pose keyframe / landmark weights", "damped bone transforms", "motionCore/PoseInputAdapter", State.EXECUTABLE, "Requires finite landmarks above confidence threshold.", ("ara_skeleton_20",), "local algorithm", "CPU / browser"),
        ("motion.ik", "Solve damped 2-bone arm and leg IK within joint limits", "effector target + pole vector + order", "bounded bone rotations", "motionCore/InverseKinematicsEngine", verified, "Evaluated strictly post-clip / pre-cloth to avoid skeleton override.", ("three_ik_ccd",), "local algorithm", "browser CPU"),
        ("motion.capture", "Optional live pose estimation capture adapter", "video frame / landmarks", "confidence-weighted PoseFrame", "orchestration/MediaPipeVisionAdapter", State.DEGRADED, "Optional browser webcam/MediaPipe adapter; core animation works offline without webcam.", ("mediapipe_pose_landmarker",), "browser neural optional", "WebAssembly / GPU delegate"),
        ("motion.synchronize", "Advance fixed-timestep animation, bone anchors, collision, and cloth step", "deltaTime + MotionState + garments", "synchronized frame transforms", "motionCore/MotionCoreOrchestrator", verified, "Bounded substeps protect frame stability; not physical lab accuracy.", ("xpbd_cloth_solver",), "browser simulation", "CPU / Worker"),
        ("cloth.animate", "Deform rigged and multi-component garments during avatar movement", "SkinnedMesh/Group + avatar skeleton", "updated vertex buffers + anchors", "motionCore/GarmentDynamicsEngine", verified, "Updates runtime simulation buffers cleanly without mutating stored revisions.", ("xpbd_cloth_solver",), "browser simulation", "CPU / Worker"),
        ("collision.resolve", "Resolve garment-to-body capsule and proxy collisions cleanly", "cloth particles + bone capsules/BVH", "penetration resolution report", "clothPhysics/ClothCollisionSystem", verified, "Spatial bounds depend on hull fit accuracy.", ("three_mesh_bvh",), "local geometric", "CPU / browser"),
        ("fabric.profile", "Derive garment- and construction-aware estimated physics coefficients", "category + component evidence + seams", "MaterialPhysicsProfileV3", "motion/motion_core", verified, "Coefficients are explicitly labeled computational estimates, not physical tests.", ("fabric_database_v3",), "local algorithm", "CPU"),
        ("secondary.simulate", "Solve bounded secondary spring motion for hems, cuffs, hood, and hair", "inertia + gravity + non-cloth targets", "bounded secondary transforms", "motionCore/SecondaryMotionSolver", verified, "Complements cloth solver without double-deforming primary XPBD vertices.", ("damped_spring_inertia",), "local algorithm", "browser CPU"),
        ("compute.select", "Select verified render/physics backend and adaptive quality tier", "capabilities + hardware metrics", "ComputeSelectionResult", "motion/motion_core", verified, "WebGPU remains experimental behind parity gates; SwiftShader separated from native.", ("webgl2_xpbd",), "policy selector", "CPU / browser"),
        ("motion.evaluate", "Evaluate canonical garment deformation stability and P50/P95/P99 latency", "mesh vertices + triangles + poses", "MotionEvaluationReport", "motion/motion_core", verified, "Synthetic benchmark stability does not certify real physical cloth accuracy.", ("animation_deformation_validator",), "local algorithm", "CPU"),
        # Phase 17.0 YORVYN Intelligence Platform (YIP) Capabilities
        ("multimodal.understand", "Coordinate image quality, classification, semantic parsing, DINOv2, CLIP and text intent", "image_bytes + instruction + views", "MultimodalUnderstandingResult", "intelligence/multimodal_intelligence", State.EXECUTABLE, "Generic CLIP and local heuristics are not a replacement for FashionCLIP or holdout calibration.", ("universal-garment-classifier", "human_parsing_segformer_b2", "dinov2_small", "clip_vit_b32_local"), "hybrid local neural/cv", "CPU or MPS"),
        ("multimodal.similarity", "Rank visual and cross-modal garment similarity using L2-normalized embeddings", "query image/text + wardrobe candidates", "SimilarityMatchList", "intelligence/multimodal_intelligence", State.EXECUTABLE, "Embedding cosine similarity indicates visual proximity, not semantic/construction equivalence.", ("dinov2_small", "clip_vit_b32_local"), "local neural embedding", "CPU or MPS"),
        ("fabric.understand", "Estimate visual fabric weave, surface specularity, and drape properties", "image + alpha_mask + category", "FabricIntelligenceReport", "intelligence/fashion_intelligence_v17", State.EXECUTABLE, "Visual appearance cues cannot establish certified laboratory fiber composition.", ("clip_vit_b32_local",), "local hybrid cv/neural", "CPU or MPS"),
        ("fit.analyze", "Extract mesh vs body dimensions, ease tolerances, clearance, and fit defects", "garment_mesh + avatar_profile", "FitIntelligenceReport", "intelligence/fit_intelligence", State.EXECUTABLE, "Assesses computational mesh-to-avatar clearance; requires physical sample for tailor certification.", ("avatar_body_measurement_engine",), "local geometric/physics", "CPU"),
        ("knowledge.retrieve", "Hybrid dense + lexical + trigram retrieval over verified domain knowledge with injection firewall", "query + domain + metadata_filters", "KnowledgeRetrievalResult", "intelligence/knowledge_rag", State.EXECUTABLE, "Host lacks pgvector extension; hybrid dense+BM25+pg_trgm retrieval executes cleanly without tool execution.", ("clip_vit_b32_local",), "hybrid retrieval", "CPU"),
        ("critic.evaluate", "Independent multi-domain quality inspection across geometry, texture, construction, fit and motion", "glb_bytes + context + avatar", "IndependentCriticReport", "intelligence/evaluation_critic", State.EXECUTABLE, "Blocks publication on critical structural defects; recommendations are not auto-applied repairs.", ("mesh_validation_service",), "independent critic", "CPU"),
        ("candidate.optimize", "Bounded critic-guided candidate optimization with lineage and rollback protection", "glb_bytes + critic_report + budget", "CandidateOptimizationResult", "intelligence/candidate_optimizer", State.EXECUTABLE, "Applies only bounded topological and supported parametric repairs within iteration and time caps.", ("mesh_validation_service",), "bounded optimization", "CPU"),
        ("personalize.recommend", "Owner-isolated consent-gated garment and fit recommendations", "user_id + wardrobe + context", "PersonalizedRecommendations", "intelligence/personalization_engine", State.EXECUTABLE, "Strictly isolated per owner; requires explicit consent and never mutates saved measurements.", ("outfit_ranker_service",), "local ranking", "CPU"),
        ("learning.dataset_audit", "Offline dataset deduplication, split leakage audit, consent/license verification and PyTorch training", "dataset_samples + config", "DatasetAuditAndTrainReport", "learning/dataset_curator", State.EXECUTABLE, "Candidate releases never self-promote without independent holdout evaluation and admin approval.", ("universal-garment-classifier",), "offline pytorch", "CPU or MPS"),
        ("yip.orchestrate", "Typed planning, policy enforcement, concurrent capability scheduling and durable evaluation gate", "authenticated_yip_request", "YIPOrchestrationResponse", "intelligence/yip_orchestrator", State.EXECUTABLE, "Delegates long-running 3D jobs to PostgreSQL/Redis/outbox; external LLMs cannot invoke unvalidated tools.", ("universal-garment-classifier",), "orchestrator", "CPU or MPS"),
        # Phase 17.0 Extension — Fashion Recommendation Intelligence
        ("recommendation.profile", "Build owner-isolated explicit and time-decayed inferred fashion preference profiles with consent & reset governance", "owner_id + consented_signals", "UserPreferenceProfile", "intelligence/recommendation_profile", State.EXECUTABLE, "Product views never auto-promote positive affinity; sensitive traits are strictly excluded.", ("preference_learning_service",), "local profile store", "CPU"),
        ("recommendation.category", "Rank preferred categories and subcategories using exponential time decay across normalized taxonomy", "owner_id + candidates", "RecommendationResponse", "intelligence/recommendation_algorithms", State.EXECUTABLE, "Requires consented interactions or explicit category selection; falls back cleanly in cold start.", ("universal-garment-classifier",), "local ranking", "CPU"),
        ("recommendation.content", "Recommend garments by matching style, silhouette, fit, color, material, and verified visual similarity", "owner_id + candidates + optional query_embedding", "RecommendationResponse", "intelligence/recommendation_algorithms", State.EXECUTABLE, "Visual embedding proximity via DINOv2/CLIP is not guaranteed fashion-semantic equivalence.", ("dinov2_small", "clip_vit_b32_local"), "hybrid content/embedding", "CPU or MPS"),
        ("recommendation.collaborative", "Privacy-preserving implicit collaborative filtering across users above minimum reliability thresholds", "owner_id + aggregated_interactions", "CollaborativeStatus + scores", "intelligence/recommendation_algorithms", State.DECLARED, "Requires sufficient active multi-user interaction history; never verified in single-user or sparse deployments.", (), "privacy-preserving cf", "CPU"),
        ("recommendation.hybrid", "Unified multi-signal ranking engine with versioned weights, session context, cold-start, diversity, and explainability", "owner_id + surface + session + candidates", "RecommendationResponse", "intelligence/recommendation_engine", State.EXECUTABLE, "Explanations strictly reflect active contributing signals; weights require offline benchmark calibration.", ("outfit_ranker_service", "dinov2_small"), "hybrid ranking", "CPU or MPS"),
        ("recommendation.outfit", "Compose multi-garment outfits, complementary items, and wardrobe gap guidance across Wardrobe, Stylist & Design Studio", "owner_id + occasion + optional anchor_garment", "OutfitRecommendationResponse", "intelligence/recommendation_engine", State.EXECUTABLE, "Outfit and compatibility scores are probabilistic ranking predictions, not deterministic fashion rules.", ("outfit_ranker_service",), "combinatorial ranking", "CPU"),
        ("recommendation.feedback", "Record explicit and behavioral recommendation interactions cleanly with view vs positive separation & retention control", "owner_id + interaction_type + item_data", "FeedbackRecordReceipt", "intelligence/recommendation_profile", State.EXECUTABLE, "Respects personalization consent, purchase authorization checks, and non-mutation of views.", ("preference_learning_service",), "governance service", "CPU"),
        ("recommendation.evaluate", "Evaluate recommendation presets using chronological train/test splits without future interaction leakage", "catalog_items + chronological_events + k", "RecommendationBenchmarkReport", "intelligence/recommendation_evaluation", State.EXECUTABLE, "Offline ranking metrics (NDCG@K, MRR, coverage, diversity) do not directly equate to live user satisfaction.", (), "offline benchmark", "CPU"),
        # Phase 17.2 Neural Fashion Recommendation Capabilities
        ("recommendation.neural_retrieval", "Two-Tower PyTorch encoder producing L2 user/item embeddings with BPR retrieval and algorithmic fallback", "owner_id + profile + candidates", "RecommendationResponse + embeddings", "intelligence/neural_recommendation_models", State.DECLARED, "Requires verified SHA-256 checkpoint and sufficient multi-user interaction scale; falls back to content/hybrid when unverified.", ("two_tower_recommender",), "pytorch two-tower", "CPU or MPS"),
        ("recommendation.neural_rank", "Neural Ranking Network combining embeddings with verified masked scalar factors and attribution explainability", "user_emb + item_embs + verified_signals", "RecommendationResponse", "intelligence/neural_recommendation_models", State.DECLARED, "Masks out unverified signals completely; requires offline holdout improvement before promotion.", ("neural_ranking_network",), "pytorch mlp ranker", "CPU or MPS"),
        ("recommendation.neural_sequential", "Causal time-aware Transformer learning chronological progression without future leakage or weak-view state mutation", "chronological_interactions + time_deltas", "RecommendationResponse", "intelligence/neural_recommendation_models", State.DECLARED, "Causal masking enforced strictly; weak browsing views do not persist to long-term sequence parameters.", ("sequential_transformer_recommender",), "pytorch transformer", "CPU or MPS"),
        ("recommendation.neural_graph", "Provenance-aware pure-PyTorch graph message passing over consented Users-Garments-Categories-Styles", "consented_graph_edges + candidates", "NeuralModelMetrics", "intelligence/neural_recommendation_models", State.DECLARED, "Evaluated against Two-Tower & Ranker; excludes private cross-owner uploads and unconsented edges.", ("graph_recommendation_model",), "pytorch graph propagation", "CPU or MPS"),
        ("recommendation.neural_train", "Reproducible consent/license-gated PyTorch training, chronological evaluation, calibration ECE, and non-auto-promotion audit", "catalog_items + CuratedInteractionEvent[]", "NeuralTrainingBenchmarkReport", "intelligence/neural_recommendation_trainer", State.EXECUTABLE, "Flags small-dataset overfit risk honestly and never self-promotes to production without passing gates.", ("two_tower_recommender", "neural_ranking_network"), "offline pytorch", "CPU or MPS"),
        # Phase 17.4 — Neural Generalization, Outfit Compatibility & Experimentation
        ("recommendation.outfit_neural", "Symmetric set/pairwise PyTorch outfit compatibility scorer with algorithmic fallback", "2..4 garment items + slot stats", "OutfitRecommendationResponse", "intelligence/neural_recommendation_models", State.DECLARED, "Requires verified SHA-256 checkpoint and promotion gates before replacing pairwise baseline.", ("neural_outfit_compatibility",), "pytorch set+pairwise", "CPU or MPS"),
        ("recommendation.experiment", "Owner-isolated consent-gated online A/B bucketing, impression/outcome logging and power analysis", "owner_id + experiment_id + outcomes", "ExperimentReport", "intelligence/recommendation_experiments", State.EXECUTABLE, "Requires >=100 impressions per arm for statistical power; excludes non-consented users cleanly.", (), "experiment telemetry", "CPU"),
        ("recommendation.promote", "Multi-gate neural checkpoint promotion, calibration, leak, and fallback rollback verifier", "model_id + traffic_volume + metrics", "PromotionDecision", "intelligence/neural_generalization_benchmark", State.EXECUTABLE, "Blocks promotion unless non-synthetic real traffic thresholds and holdout gains are satisfied.", ("two_tower_recommender", "neural_ranking_network"), "governance gate", "CPU"),
        # Phase 17.3 — LangGraph Workflows & External Web Intelligence (Tavily)
        ("knowledge.external.search", "Search external fashion & textile sources via Tavily REST API with SSRF & injection firewall", "query + search_depth + domain_filters", "TavilyOperationResponse", "intelligence/tavily_web_adapter", State.DECLARED, "Untrusted external snippets stay isolated from GarmentKnowledgeRAG; requires TAVILY_API_KEY for live verification.", (), "external http provider", "Network"),
        ("knowledge.external.extract", "Extract sanitized public text content from validated public URLs via Tavily /extract", "urls[] + extract_depth", "TavilyOperationResponse", "intelligence/tavily_web_adapter", State.DECLARED, "SSRF guard rejects loopback/private/metadata IPs; requires TAVILY_API_KEY for live verification.", (), "external http provider", "Network"),
        ("knowledge.external.research", "Conduct bounded multi-step external fashion & textile research via Tavily /research", "topic_input", "TavilyOperationResponse", "intelligence/tavily_web_adapter", State.DECLARED, "External reports are provenance-tagged references, not verified YORVYN policy.", (), "external http provider", "Network"),
        ("knowledge.external.promote", "Explicit approval-, hash-, rights-, and duplicate-gated promotion of validated external evidence into RAG", "TavilyResultItem + explicit_approval + rights_verified", "KnowledgeDocument", "intelligence/unified_knowledge", State.EXECUTABLE, "Requires explicit admin/reviewer approval, verified SHA-256 content hash, and non-injection audit.", (), "knowledge governance gate", "CPU"),
        ("workflow.garment.research", "Bounded LangGraph workflow combining GarmentKnowledgeRAG with optional validated Tavily external research", "owner_id + query + use_external", "WorkflowThreadRecord", "intelligence/langgraph_workflows", State.EXECUTABLE, "Max 8 nodes, PG BaseCheckpointSaver durability & strict timeout; external content stays isolated.", (), "langgraph stateful workflow", "CPU"),
        ("workflow.fashion.discovery", "Bounded LangGraph workflow uniting owner profile, internal knowledge, optional trends & recommendation ranking", "owner_id + occasion + query", "WorkflowThreadRecord", "intelligence/langgraph_workflows", State.EXECUTABLE, "Respects personalization consent & isolates private profiles across thread checkpoints.", (), "langgraph stateful workflow", "CPU"),
        ("workflow.design.assistance", "Confirmation-gated LangGraph workflow with SHA-256 operation binding and optimistic PG checkpoint recovery", "owner_id + instruction + category", "WorkflowThreadRecord", "intelligence/langgraph_workflows", State.EXECUTABLE, "Requires single-use owner confirmation bound to operation hash & TTL; resumes via PostgreSQL without node replay.", (), "langgraph interruptible workflow", "CPU"),
        # Phase 17.5 — Guided Live Garment Capture & Reconstruction Readiness
        ("capture.session.create", "Create owner-isolated garment capture session with adaptive view checklist and capture-mode guidance", "owner_id + garment_category + capture_mode", "CaptureSessionRecord", "intelligence/capture_intelligence", State.EXECUTABLE, "Flat-lay and worn modes include explicit 3D reconstruction limitations.", (), "capture governance", "CPU"),
        ("capture.image.validate", "Decode, EXIF-strip, and measure sharpness, exposure, visibility, framing, occlusion, and background quality", "image_bytes + view_label", "CapturedViewRecord", "intelligence/capture_intelligence", State.EXECUTABLE, "Measurements are pixel/contour heuristics; never fabricates confidence scores.", (), "local cv quality", "CPU"),
        ("capture.view.classify", "Classify captured garment viewpoint (front, back, sides, details) with confidence and usability checks", "image + user_hint", "GarmentViewType + confidence", "ai/multiview/view_classifier", State.EXECUTABLE, "Heuristic edge/symmetry viewpoint classification.", (), "local cv heuristic", "CPU"),
        ("capture.multiview.validate", "Verify multi-view garment identity consistency, exact/perceptual duplicate suppression, and color coherence", "session_id + captured_views", "MultiViewConsistencyReport", "intelligence/capture_intelligence", State.EXECUTABLE, "Flags extreme color divergence and duplicate shots; cannot certify fabric brand identity.", (), "multiview consistency", "CPU"),
        ("capture.readiness.evaluate", "Server-authoritative Reconstruction Readiness Gate checking views, quality, consistency, and UnifiedModelRegistry", "session_id + owner_id", "ReadinessEvaluation", "intelligence/capture_intelligence", State.EXECUTABLE, "Blocks insufficient or contradicted captures cleanly; ignores client-submitted quality scores.", ("universal-garment-classifier", "human_parsing_segformer_b2"), "readiness gate", "CPU"),
        ("capture.session.finalize", "Freeze verified capture evidence set and hand off idempotently to durable reconstruction job pipeline", "session_id + owner_id + idempotency_key", "HandoffReceipt", "intelligence/capture_intelligence", State.EXECUTABLE, "Freezes image hashes prior to job creation; mutations require a new session version.", ("universal-garment-classifier",), "durable job handoff", "CPU"),
    ]
    return CapabilityRegistry(capability(*row) for row in rows)


garment_capabilities = catalog()
