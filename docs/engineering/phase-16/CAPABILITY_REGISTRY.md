# Garment capability registry

The source inventory is `backend/app/services/intelligence/capability_registry.py`. Its immutable records carry stable IDs, descriptions, input and output contracts, compatible models, dependencies, category scope, execution type, hardware, availability, verification evidence, limitations, failure conditions, performance and cost. Duplicate identities fail initialization. Unknown IDs, unbound operations and non-executable states fail dispatch.

The table describes release evidence in this workspace. DECLARED means an interface or intended adapter exists. AVAILABLE means an implementation has been located. EXECUTABLE denotes a bound operation with a runnable contract. VERIFIED denotes scoped regression or integration evidence. DEGRADED denotes limited evidence or execution. UNAVAILABLE denotes a missing prerequisite for the registered path. Live model eligibility is checked separately, including digest, loaded tensors and hardware. Adding a catalog entry cannot make an external endpoint, model or job executable.

| Capability | Input → output | Release state | Dependency or evidence location | Limitation or failure condition |
| --- | --- | --- | --- | --- |
| `appearance.material` | photo + mask → material parameters | AVAILABLE | `garments/appearance/appearance_analyzer` | Appearance alone does not identify fabric composition. |
| `avatar.attach` | GLB + avatar → rendered attachment | VERIFIED | `frontend/src/engine/garments/GarmentAvatarFittingEngine` | Attachment does not validate physical fit. |
| `candidate.edit` | owned candidate + edit → edited GLB | VERIFIED | `garments/chat_candidate` & `api/garment_design_routes` | Requires supported topology and bounded parameters; real-time 2D/3D studio edits also sync via `DesignStateEngine`. |
| `candidate.history` | owned turn → prior candidate context | VERIFIED | `api/conversational_garments` | Requires a matching owner and session. |
| `candidate.inspect` | owned job + edit lineage → validated bytes + mesh report | VERIFIED | `garments/mesh_validation_service` | Structural validity alone does not establish appearance or accuracy. |
| `classify.category` | RGB photograph → category and subcategory distributions | VERIFIED | `garments/intelligence/universal_garment_classifier` | Requires a strict loaded release and valid probability vectors. |
| `classify.subcategory` | RGB photograph → 55 label probabilities | VERIFIED | `garments/intelligence/universal_garment_classifier` | No holdout certification of fine-grained accuracy. |
| `cloth.simulate` | garment and body mesh → deformed mesh | AVAILABLE | `garments/fitting/cloth_relaxation_engine` | Material coefficients are estimates. |
| `collision.detect` | body and garment → collision report | AVAILABLE | `garments/fitting/garment_collision_engine` | No physical fit reference. |
| `components.identify` | ordered views + category → ComponentAnalysisBundle | VERIFIED | `intelligence/component_evidence` | Real-world component precision/recall requires independently annotated component datasets; unseen regions stay `NOT_OBSERVED`. |
| `depth.estimate` | RGB photograph → disparity | DECLARED | `garments/reconstruction/neural/depth_anything_adapter` | No pinned server checkpoint or metric scale. |
| `evaluate.critic` | candidate + references → defects by domain | DECLARED | `garments/evaluation/ground_truth_evaluator` | Cross-domain candidate critic belongs to Phase 16.6. |
| `evaluate.landmarks` | matching point annotations → normalized localization error | AVAILABLE | `garments/evaluation/geometric_evaluator` | Requires matching landmark IDs and scale. |
| `evaluate.material` | aligned material references → appearance measurements | DECLARED | `garments/evaluation/ground_truth_evaluator` | No registered physical material reference for a chat turn. |
| `evaluate.multiview` | usable view records → conflicts and readiness | AVAILABLE | `ai/multiview/fusion_engine` | Heuristic consistency is not camera accuracy. |
| `evaluate.reprojection` | views + cameras + mesh → per-view residuals | DECLARED | `garments/evaluation/geometric_evaluator` | Projection primitive exists. End-to-end camera evaluation remains open. |
| `evaluate.silhouette` | two masks → IoU and boundary errors | EXECUTABLE | `garments/evaluation/geometric_evaluator` | Requires aligned reference mask. |
| `evaluate.surface` | two aligned meshes → distance metrics | EXECUTABLE | `garments/evaluation/geometric_evaluator` | Requires compatible coordinates and reference geometry. |
| `geometry.multiview` | front + rear or side → refined mesh | AVAILABLE | `garments/reconstruction/multi_view_fuser` | Heuristic views do not establish calibrated camera geometry. |
| `geometry.neural` | garment views → GLB | UNAVAILABLE | `garments/reconstruction/neural/remote_gpu_client` | Remote weights, endpoint and independent output verification required. |
| `geometry.parametric` | category + measurements → mesh | AVAILABLE | `garments/reconstruction/engine_registry` | Category defaults are approximate. |
| `geometry.pattern` | construction graph → mesh | AVAILABLE | `garments/reconstruction/professional_geometry_pipeline` | Inferred panels lack sewing ground truth. |
| `geometry.refine` | GLB → repaired GLB | AVAILABLE | `garments/chat_candidate` | Only duplicate or degenerate face repair is supported in chat. |
| `geometry.submit` | canonical V2 + matching views → owned job ID | VERIFIED | `garments/job_manager` | Requires a usable front view and an available queue. |
| `intent.plan` | instruction + turn state → GarmentPlan | VERIFIED | `llm/garment_plan` | Unsupported or ambiguous edits need clarification. |
| `job.control` | owned job + action → job state | VERIFIED | `garments/job_manager` | Terminal job states restrict transitions. |
| `landmarks.estimate` | 64-dimensional embedding → 12 coordinate pairs | AVAILABLE | `ml/model_registry` | Artifact verified. Spatial accuracy depends on reference landmarks. |
| `pattern.interpret` | garment evidence + components → ConstructionToGeometryHandoff | VERIFIED | `intelligence/pattern_construction_engine` | Single-photo inferred patterns carry explicit dimension uncertainty; no certified sewing ground truth. |
| `pose.estimate` | body image → body keypoints | DECLARED | `ml/model_registry` | Browser pose asset is a remote dependency. |
| `reason.external` | text and tool schema → validated GarmentPlan | DEGRADED | `llm/garment_plan` | Account authorization, endpoint and valid tool result required. |
| `segment.foreground` | RGB photograph → foreground alpha | AVAILABLE | `garments/segmentation/segmenter_registry` | A silhouette can include adjacent garments. |
| `segment.instance` | photograph + prompt → instance masks | DECLARED | `garments/intelligence/grounded_sam2_adapter` | No pinned Grounded-SAM checkpoint. |
| `segment.semantic` | RGB photograph → label map | AVAILABLE | `garments/segmentation/human_parsing_segmenter` | Requires cached parsing weights. |
| `stitches.generate` | panel relationships → stitch paths | DECLARED | `garments/reconstruction/garment_construction_graph` | No independent stitching reference. |
| `structure.construct` | garment evidence → ConstructionToGeometryHandoff | VERIFIED | `intelligence/pattern_construction_engine` | Hidden rear construction remains inferred without back view. |
| `subject.select` | image + instruction → crop or choices | VERIFIED | `garments/intelligence/garment_instance_detector` | Multiple plausible subjects require a selection. |
| `texture.project` | source image + UV → texture maps | AVAILABLE | `garments/garment_texture_synthesizer` | Unseen surfaces lack texture references. |
| `uv.generate` | mesh → UV coordinates | AVAILABLE | `garments/appearance/uv_reconstruction_engine` | A valid layout does not establish texture alignment. |
| `views.identify` | ordered uploads → CanonicalGarmentSpecificationV2 | VERIFIED | `ai/multiview/fusion_engine` | Single views cannot establish hidden features. |

Most dependency paths are relative to `backend/app/services`. API and frontend paths identify their owning layer. The catalog category scope describes supported garments at the capability level. Concrete category engines impose narrower constraints. Timings and dollar costs without observations are null.

Direct server bindings cover intent, subject selection, category inference, multi-view identification, reconstruction submission, candidate inspection/edit/history, job control and paired surface/mask evaluation. The existing job and browser pipelines own the remaining executable substeps. For example, avatar attachment executes in the browser. There is no server-side switch to invoke a declared feature through chat.

The router accepts trusted server bindings. It validates parameters, deadlines, application-owned operations and outputs. A particular result can legitimately be `NOT_EVALUATED` even when its evaluation operation ran correctly. Optional future operations require their own binding and verification evidence.

Phase 16.3.1 extends the capability registry boundaries with versioned `SemanticCorrespondenceMap` (`16.3.1`), explicit `MeasurementScope` unit/scope tracking (`PATTERN_PANEL_HALF` vs `HALF_GARMENT_FLAT` vs `FULL_CIRCUMFERENCE`), seven-state `SyncStatus` contracts (`SYNCHRONIZED`, `SYNCHRONIZED_WITH_UNCERTAINTY`, `REQUIRES_REBUILD`, `MAPPING_INVALID`, `CONSTRUCTION_CONFLICT`, `VALIDATION_FAILED`, `NOT_SUPPORTED`), extended construction validation (`validate_extended_construction`), and candidate-first atomic execution via `TransactionalDesignEngine`.

Phase 16.9 MotionCore registers unified character animation, retargeting, IK, XPBD garment synchronization, spatial self-collision, estimated fabric profiles (`is_measured_physical=False`), secondary spring inertia, compute selection (`webgpuExperimentalOnly=True`), animated GLB validation, and canonical evaluation under `animation.*`, `motion.*`, `cloth.animate`, `collision.resolve`, `fabric.profile`, `secondary.simulate`, and `compute.select` (`motion.capture` remains honestly `DEGRADED` offline).
