"""YORVYN Phase 16.9 MotionCore: Unified Backend Orchestration, Retargeting, Adaptive Material Profiles, Compute Selection & Security Validation."""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import time
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.garments.fitting.animation_deformation_validator import AnimationDeformationValidator
from backend.app.services.garments.fitting.cloth_relaxation_engine import FABRIC_DATABASE
from backend.app.services.garments.garment_mesh_builder import ARA_SKELETON_SPECS, GarmentMesh


class MotionState(str, Enum):
    IDLE = "IDLE"
    WALK = "WALK"
    RUN = "RUN"
    TURN = "TURN"
    RAISE_ARMS = "RAISE_ARMS"
    BEND = "BEND"
    SIT = "SIT"
    STAND = "STAND"
    CUSTOM = "CUSTOM"
    PAUSED = "PAUSED"
    RESETTING = "RESETTING"
    ERROR = "ERROR"


class QualityTier(str, Enum):
    LOW = "low"
    BALANCED = "balanced"
    HIGH = "high"
    MAXIMUM = "maximum"


class ComputeBackendKind(str, Enum):
    CPU_XPBD = "cpu_xpbd"
    WEBWORKER_XPBD = "webworker_xpbd"
    WASM_SIMD_XPBD = "wasm_simd_xpbd"
    WEBGPU_EXPERIMENTAL = "webgpu_experimental"


class ExportAnimationKind(str, Enum):
    SKELETAL_ANIMATION_EXPORT = "skeletal_animation_export"
    SKELETAL_WITH_GARMENT_DEFORMATION = "skeletal_with_garment_deformation"
    BAKED_SIMULATION_EXPORT = "baked_simulation_export"
    STATIC_GARMENT_EXPORT = "static_garment_export"


# Legal state machine transitions (prevents simultaneous conflicting updates)
LEGAL_MOTION_TRANSITIONS: Dict[MotionState, Tuple[MotionState, ...]] = {
    MotionState.IDLE: (
        MotionState.IDLE, MotionState.WALK, MotionState.RUN, MotionState.TURN,
        MotionState.RAISE_ARMS, MotionState.BEND, MotionState.SIT, MotionState.CUSTOM,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.WALK: (
        MotionState.IDLE, MotionState.WALK, MotionState.RUN, MotionState.TURN,
        MotionState.RAISE_ARMS, MotionState.BEND, MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.RUN: (
        MotionState.IDLE, MotionState.WALK, MotionState.RUN, MotionState.TURN,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.TURN: (
        MotionState.IDLE, MotionState.WALK, MotionState.RUN, MotionState.TURN,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.RAISE_ARMS: (
        MotionState.IDLE, MotionState.WALK, MotionState.BEND, MotionState.TURN,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.BEND: (
        MotionState.IDLE, MotionState.STAND, MotionState.RAISE_ARMS,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.SIT: (
        MotionState.STAND, MotionState.IDLE, MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.STAND: (
        MotionState.IDLE, MotionState.WALK, MotionState.TURN, MotionState.SIT,
        MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.CUSTOM: (
        MotionState.IDLE, MotionState.CUSTOM, MotionState.PAUSED, MotionState.RESETTING, MotionState.ERROR,
    ),
    MotionState.PAUSED: tuple(MotionState),
    MotionState.RESETTING: (MotionState.IDLE, MotionState.ERROR),
    MotionState.ERROR: (MotionState.RESETTING, MotionState.IDLE),
}


STATE_PRIORITIES: Dict[MotionState, int] = {
    MotionState.ERROR: 100,
    MotionState.RESETTING: 90,
    MotionState.PAUSED: 80,
    MotionState.RUN: 40,
    MotionState.SIT: 35,
    MotionState.STAND: 35,
    MotionState.BEND: 30,
    MotionState.RAISE_ARMS: 30,
    MotionState.TURN: 25,
    MotionState.WALK: 20,
    MotionState.CUSTOM: 15,
    MotionState.IDLE: 10,
}


class MotionTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_state: MotionState
    target_state: MotionState
    time_scale: float = Field(1.0, ge=0.0, le=3.0)
    requested_blend_s: float = Field(0.28, ge=0.0, le=2.0)
    interrupted_active: bool = False


class MotionTransitionResult(BaseModel):
    accepted: bool
    resulting_state: MotionState
    blend_duration_s: float
    blending_policy: str
    priority: int
    reason: str


class MotionStateMachine:
    """Deterministic FSM ensuring a single skeleton never executes conflicting animations."""

    @classmethod
    def evaluate_transition(cls, req: MotionTransitionRequest) -> MotionTransitionResult:
        allowed = LEGAL_MOTION_TRANSITIONS.get(req.current_state, ())
        if req.target_state not in allowed:
            return MotionTransitionResult(
                accepted=False,
                resulting_state=req.current_state,
                blend_duration_s=0.0,
                blending_policy="rejected_invalid_transition",
                priority=STATE_PRIORITIES[req.current_state],
                reason=f"Transition {req.current_state.value} -> {req.target_state.value} must transition cleanly through STAND or IDLE first.",
            )

        if req.target_state == MotionState.SIT or req.current_state == MotionState.SIT:
            blend_s = max(req.requested_blend_s, 0.35)
        elif req.target_state in {MotionState.RESETTING, MotionState.ERROR, MotionState.PAUSED}:
            blend_s = min(req.requested_blend_s, 0.12)
        else:
            blend_s = req.requested_blend_s

        policy = "interrupt_crossfade_single_mixer" if req.interrupted_active else "smooth_crossfade_single_mixer"
        return MotionTransitionResult(
            accepted=True,
            resulting_state=req.target_state,
            blend_duration_s=round(blend_s, 3),
            blending_policy=policy,
            priority=STATE_PRIORITIES[req.target_state],
            reason="Valid deterministic transition under single MotionCore mixer ownership.",
        )


# Canonical Ara skeleton + optional Mixamo bone aliases
MIXAMO_TO_ARA_BONE_ALIASES: Dict[str, str] = {
    "mixamorig:hips": "Hips",
    "mixamorighips": "Hips",
    "hips": "Hips",
    "pelvis": "Hips",
    "mixamorig:spine": "Spine",
    "spine": "Spine",
    "mixamorig:spine1": "Spine1",
    "spine1": "Spine1",
    "mixamorig:spine2": "Spine2",
    "spine2": "Spine2",
    "chest": "Spine2",
    "mixamorig:neck": "Neck",
    "neck": "Neck",
    "mixamorig:head": "Head",
    "head": "Head",
    "mixamorig:leftshoulder": "LeftShoulder",
    "leftshoulder": "LeftShoulder",
    "mixamorig:leftarm": "LeftArm",
    "leftarm": "LeftArm",
    "upperarm.l": "LeftArm",
    "mixamorig:leftforearm": "LeftForeArm",
    "leftforearm": "LeftForeArm",
    "mixamorig:lefthand": "LeftHand",
    "lefthand": "LeftHand",
    "mixamorig:rightshoulder": "RightShoulder",
    "rightshoulder": "RightShoulder",
    "mixamorig:rightarm": "RightArm",
    "rightarm": "RightArm",
    "upperarm.r": "RightArm",
    "mixamorig:rightforearm": "RightForeArm",
    "rightforearm": "RightForeArm",
    "mixamorig:righthand": "RightHand",
    "righthand": "RightHand",
    "mixamorig:leftupleg": "LeftUpLeg",
    "leftupleg": "LeftUpLeg",
    "thigh.l": "LeftUpLeg",
    "mixamorig:leftleg": "LeftLeg",
    "leftleg": "LeftLeg",
    "shin.l": "LeftLeg",
    "mixamorig:leftfoot": "LeftFoot",
    "leftfoot": "LeftFoot",
    "mixamorig:rightupleg": "RightUpLeg",
    "rightupleg": "RightUpLeg",
    "thigh.r": "RightUpLeg",
    "mixamorig:rightleg": "RightLeg",
    "rightleg": "RightLeg",
    "shin.r": "RightLeg",
    "mixamorig:rightfoot": "RightFoot",
    "rightfoot": "RightFoot",
}


class SkeletonValidationResult(BaseModel):
    is_compatible: bool
    bone_count: int
    canonical_matched_count: int
    unmapped_bones: List[str] = Field(default_factory=list)
    missing_core_bones: List[str] = Field(default_factory=list)
    has_cycle: bool = False
    issues: List[str] = Field(default_factory=list)


class RetargetingPlan(BaseModel):
    source_skeleton_kind: str
    target_skeleton_kind: str = "yorvyn_ara_20"
    is_compatible: bool
    bone_mapping: Dict[str, str] = Field(default_factory=dict)
    unmapped_source_bones: List[str] = Field(default_factory=list)
    validation: SkeletonValidationResult


class SkeletonRetargetingValidator:
    """Validates bone hierarchies and creates explicit retargeting plans without assuming compatibility."""

    REQUIRED_CORE_BONES = ("Hips", "Spine", "Spine2", "LeftArm", "RightArm", "LeftUpLeg", "RightUpLeg")
    CANONICAL_BONES = {spec[0] for spec in ARA_SKELETON_SPECS}

    @classmethod
    def validate_and_plan(
        cls,
        bone_names: Sequence[str],
        parent_pairs: Optional[Sequence[Tuple[str, Optional[str]]]] = None,
    ) -> RetargetingPlan:
        if not bone_names:
            val = SkeletonValidationResult(
                is_compatible=False, bone_count=0, canonical_matched_count=0,
                missing_core_bones=list(cls.REQUIRED_CORE_BONES),
                issues=["Empty skeleton cannot be animated or retargeted."],
            )
            return RetargetingPlan(source_skeleton_kind="empty", is_compatible=False, validation=val)

        # Cycle check if parent hierarchy provided
        has_cycle = False
        if parent_pairs:
            pmap = {b: p for b, p in parent_pairs}
            for b in pmap:
                seen = set()
                cur: Optional[str] = b
                while cur is not None:
                    if cur in seen:
                        has_cycle = True
                        break
                    seen.add(cur)
                    cur = pmap.get(cur)
                if has_cycle:
                    break

        mapping: Dict[str, str] = {}
        unmapped: List[str] = []
        is_mixamo = any("mixamorig" in b.lower() for b in bone_names)

        for raw in bone_names:
            norm = raw.strip().lower().replace(" ", "")
            if raw in cls.CANONICAL_BONES:
                mapping[raw] = raw
            elif norm in MIXAMO_TO_ARA_BONE_ALIASES:
                mapping[raw] = MIXAMO_TO_ARA_BONE_ALIASES[norm]
            else:
                unmapped.append(raw)

        matched_targets = set(mapping.values())
        missing_core = [b for b in cls.REQUIRED_CORE_BONES if b not in matched_targets]
        issues: List[str] = []
        if has_cycle:
            issues.append("Skeleton hierarchy contains a cyclic bone parent chain.")
        if missing_core:
            issues.append(f"Missing required humanoid core bones: {', '.join(missing_core)}.")

        compatible = (not has_cycle) and len(missing_core) == 0
        kind = "mixamo_retargeted" if is_mixamo else ("yorvyn_ara_20" if len(matched_targets) >= 16 and not unmapped else "custom_humanoid")

        val = SkeletonValidationResult(
            is_compatible=compatible,
            bone_count=len(bone_names),
            canonical_matched_count=len(matched_targets),
            unmapped_bones=unmapped,
            missing_core_bones=missing_core,
            has_cycle=has_cycle,
            issues=issues,
        )
        return RetargetingPlan(
            source_skeleton_kind=kind,
            is_compatible=compatible,
            bone_mapping=mapping,
            unmapped_source_bones=unmapped,
            validation=val,
        )


class MaterialPhysicsProfileV3(BaseModel):
    """Distinguishes visual material appearance from physical simulation coefficients with explicit estimation provenance."""
    profile_id: str
    garment_category: str
    fabric_family: str
    areal_density_kg_m2: float
    stretch_resistance: float
    shear_resistance: float
    bending_resistance: float
    damping: float
    friction: float
    thickness_m: float
    structural_anisotropy_ratio: float
    seam_constraint_stiffness: float
    secondary_sway_gain: float
    surface_roughness_visual: float
    is_measured_physical: Literal[False] = False
    provenance: str = "estimated_from_category_and_component_evidence"
    evidence_notes: List[str] = Field(default_factory=list)


CATEGORY_DEFAULT_FABRIC: Dict[str, str] = {
    "denim_jacket": "denim",
    "jacket": "denim",
    "jeans": "denim",
    "hoodie": "cotton",
    "shirt": "cotton",
    "tshirt": "cotton",
    "tops": "cotton",
    "top": "cotton",
    "trousers": "wool",
    "bottoms": "denim",
    "dress": "silk",
    "skirt": "linen",
    "traditional": "silk",
    "sportswear": "polyester",
    "footwear": "leather",
}


class AdaptiveFabricProfileService:
    """Computes physical simulation estimates without conflating visual shading or altering garment dimensions."""

    @classmethod
    def resolve_profile(
        cls,
        *,
        category: str,
        subcategory: Optional[str] = None,
        fabric_hint: Optional[str] = None,
        observed_components: Optional[Sequence[str]] = None,
        inferred_components: Optional[Sequence[str]] = None,
        has_construction_seams: bool = False,
        seam_count: int = 0,
        visual_roughness: float = 0.65,
    ) -> MaterialPhysicsProfileV3:
        cat_key = (subcategory or category or "tops").lower().strip()
        fam = (fabric_hint or CATEGORY_DEFAULT_FABRIC.get(cat_key) or CATEGORY_DEFAULT_FABRIC.get((category or "").lower(), "cotton")).lower()
        if fam in {"knitted", "knit"}:
            fam = "knitwear"
        if fam == "synthetic":
            fam = "polyester"
        db = FABRIC_DATABASE.get(fam, FABRIC_DATABASE["cotton"])

        stretch_res = round(max(0.25, min(0.99, 1.0 - min(0.75, db.stretch_compliance * 1200.0))), 4)
        bend_res = round(max(0.10, min(0.96, 1.0 - min(0.85, math.exp(-db.bending_compliance * 18.0) * 0.65))), 4)
        if fam in {"denim", "leather"}:
            bend_res = round(max(bend_res, 0.82), 4)
        elif fam in {"silk"}:
            bend_res = round(min(bend_res, 0.22), 4)

        notes: List[str] = [
            f"Initialized from metadata textile preset '{fam}' (estimated computational parameters, not lab-measured physical fabric).",
        ]
        obs = list(observed_components or [])
        inf = list(inferred_components or [])
        if obs:
            notes.append(f"Observed Phase 16.1 components integrated ({len(obs)}): {', '.join(obs[:6])}.")
        if inf:
            notes.append(f"Inferred/unobserved regions remain constrained ({len(inf)}): {', '.join(inf[:4])}.")

        seam_stiff = 0.94 if has_construction_seams and seam_count > 0 else 0.88
        anisotropy = 1.15 if fam in {"denim", "wool", "linen"} else (1.35 if fam == "knitwear" else 1.05)
        sway_gain = round(max(0.15, min(1.0, (1.0 - bend_res * 0.7) * (1.0 if category.lower() in {"dress", "skirt", "traditional", "hoodie"} else 0.72))), 3)

        return MaterialPhysicsProfileV3(
            profile_id=f"{cat_key}_{fam}",
            garment_category=cat_key,
            fabric_family=fam,
            areal_density_kg_m2=round(db.mass_g_m2 / 1000.0, 4),
            stretch_resistance=stretch_res,
            shear_resistance=round(db.shear_stiffness, 4),
            bending_resistance=bend_res,
            damping=round(db.damping, 4),
            friction=round(db.friction_coeff, 4),
            thickness_m=round(db.thickness_mm / 1000.0, 5),
            structural_anisotropy_ratio=anisotropy,
            seam_constraint_stiffness=seam_stiff,
            secondary_sway_gain=sway_gain,
            surface_roughness_visual=round(max(0.05, min(1.0, visual_roughness)), 3),
            provenance="estimated_from_category_and_component_evidence",
            evidence_notes=notes,
        )


class ComputeSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webgl2_supported: bool = True
    webgpu_adapter_available: bool = False
    webgpu_parity_verified: bool = False
    worker_available: bool = True
    wasm_simd_supported: bool = True
    hardware_concurrency: int = Field(4, ge=1, le=256)
    cloth_vertex_count: int = Field(2000, ge=0, le=250000)
    is_software_renderer: bool = False
    recent_frame_time_ms: Optional[float] = Field(None, ge=0.0, le=1000.0)


class ComputeSelectionResult(BaseModel):
    render_backend: Literal["webgl2", "software_fallback"]
    physics_backend: ComputeBackendKind
    quality_tier: QualityTier
    substeps: int
    solver_iterations: int
    enable_bending: bool
    enable_self_collision: bool
    webgpu_experimental_only: bool = True
    is_software_environment: bool
    decision_reason: str


class ComputePolicyAdvisor:
    """Selects optimal verified compute backend & adaptive quality tier internally (never exposed to ordinary users)."""

    @classmethod
    def select(cls, req: ComputeSelectionRequest) -> ComputeSelectionResult:
        render_backend: Literal["webgl2", "software_fallback"] = "webgl2" if req.webgl2_supported else "software_fallback"
        # WebGPU remains strictly experimental until shader/simulation parity & device-loss checks pass.
        if req.webgpu_parity_verified and req.webgpu_adapter_available:
            physics = ComputeBackendKind.WEBGPU_EXPERIMENTAL
        elif req.worker_available and req.cloth_vertex_count >= 1800 and not req.is_software_renderer:
            physics = ComputeBackendKind.WEBWORKER_XPBD
        elif req.wasm_simd_supported and req.cloth_vertex_count >= 3500:
            physics = ComputeBackendKind.WASM_SIMD_XPBD
        else:
            physics = ComputeBackendKind.CPU_XPBD

        if req.is_software_renderer or not req.webgl2_supported or req.hardware_concurrency <= 2:
            tier = QualityTier.LOW
        elif req.recent_frame_time_ms is not None and req.recent_frame_time_ms > 22.0:
            tier = QualityTier.LOW
        elif req.hardware_concurrency >= 10 and req.cloth_vertex_count <= 4500 and (req.recent_frame_time_ms is None or req.recent_frame_time_ms <= 10.0):
            tier = QualityTier.MAXIMUM
        elif req.hardware_concurrency >= 6 and (req.recent_frame_time_ms is None or req.recent_frame_time_ms <= 16.0):
            tier = QualityTier.HIGH
        else:
            tier = QualityTier.BALANCED

        presets = {
            QualityTier.LOW: (1, 4, False, False),
            QualityTier.BALANCED: (2, 8, True, False),
            QualityTier.HIGH: (3, 12, True, True),
            QualityTier.MAXIMUM: (4, 16, True, True),
        }
        substeps, iters, bend, self_col = presets[tier]
        reason = (
            f"Selected {render_backend}/{physics.value} at '{tier.value}' quality "
            f"(software_env={req.is_software_renderer}, webgpu_experimental_only=True)."
        )
        return ComputeSelectionResult(
            render_backend=render_backend,
            physics_backend=physics,
            quality_tier=tier,
            substeps=substeps,
            solver_iterations=iters,
            enable_bending=bend,
            enable_self_collision=self_col,
            webgpu_experimental_only=True,
            is_software_environment=req.is_software_renderer,
            decision_reason=reason,
        )


class AnimatedGLBValidationReport(BaseModel):
    is_valid: bool
    export_kind: ExportAnimationKind
    byte_length: int
    sha256: str
    bone_count: int
    animation_count: int
    animation_names: List[str] = Field(default_factory=list)
    max_duration_s: float = 0.0
    has_skin_weights: bool = False
    has_garment_attachment_metadata: bool = False
    has_baked_cloth_simulation: bool = False
    skeleton_compatible: bool = False
    issues: List[str] = Field(default_factory=list)


class AnimationAssetSecurityValidator:
    """Enforces Phase 16.0 path/handler/size/ownership/GLB integrity checks on animated assets."""

    MAX_GLB_BYTES = 50 * 1024 * 1024
    FORBIDDEN_PATH_PATTERN = re.compile(r"(\.\.|^/|\\\\|[;|&`$<>])")

    @classmethod
    def validate_safe_asset_ref(cls, asset_ref: str) -> None:
        if not asset_ref or len(asset_ref) > 512 or cls.FORBIDDEN_PATH_PATTERN.search(asset_ref):
            raise ValueError("Unsafe or invalid asset path reference.")

    @classmethod
    def validate_glb_animation_payload(
        cls,
        glb_bytes: bytes,
        *,
        claimed_baked_cloth: bool = False,
    ) -> AnimatedGLBValidationReport:
        issues: List[str] = []
        if len(glb_bytes) < 20 or len(glb_bytes) > cls.MAX_GLB_BYTES:
            return AnimatedGLBValidationReport(
                is_valid=False,
                export_kind=ExportAnimationKind.STATIC_GARMENT_EXPORT,
                byte_length=len(glb_bytes),
                sha256=hashlib.sha256(glb_bytes).hexdigest(),
                bone_count=0,
                animation_count=0,
                issues=[f"GLB size out of allowed bounds ({len(glb_bytes)} bytes)."],
            )

        magic, version, total_len, chunk_len, chunk_type = struct.unpack_from("<4sIII4s", glb_bytes)
        if magic != b"glTF" or version != 2 or chunk_type != b"JSON" or 20 + chunk_len > len(glb_bytes):
            return AnimatedGLBValidationReport(
                is_valid=False,
                export_kind=ExportAnimationKind.STATIC_GARMENT_EXPORT,
                byte_length=len(glb_bytes),
                sha256=hashlib.sha256(glb_bytes).hexdigest(),
                bone_count=0,
                animation_count=0,
                issues=["Malformed GLB v2 header or JSON chunk."],
            )

        gltf = json.loads(glb_bytes[20:20 + chunk_len].decode("utf-8"))
        nodes = gltf.get("nodes", [])
        skins = gltf.get("skins", [])
        animations = gltf.get("animations", [])
        accessors = gltf.get("accessors", [])
        meshes = gltf.get("meshes", [])

        joint_indices = []
        for sk in skins:
            joint_indices.extend(sk.get("joints", []))
        bone_names = [nodes[i].get("name", f"bone_{i}") for i in joint_indices if 0 <= i < len(nodes)]
        skel_plan = SkeletonRetargetingValidator.validate_and_plan(bone_names) if bone_names else None

        has_skin = any(
            "JOINTS_0" in prim.get("attributes", {}) and "WEIGHTS_0" in prim.get("attributes", {})
            for m in meshes for prim in m.get("primitives", [])
        )
        has_garment_meta = any(
            isinstance(n.get("extras"), dict) and bool(n["extras"].get("component_id") or n["extras"].get("isCustomAiGarment") or n["extras"].get("garment_attached"))
            for n in nodes
        )
        # Check for morph-target/baked deformation channels on mesh targets
        has_baked_targets = any(
            "weights" in str(ch.get("target", {}).get("path", "")) and m.get("primitives") and any("targets" in p for p in m["primitives"])
            for anim in animations for ch in anim.get("channels", []) for m in meshes
        )
        if claimed_baked_cloth and not has_baked_targets:
            issues.append("Export cannot claim baked cloth simulation without validated vertex/morph animation tracks.")

        anim_names: List[str] = []
        max_dur = 0.0
        for a in animations:
            anim_names.append(str(a.get("name", "unnamed")))
            for smp in a.get("samplers", []):
                acc_idx = smp.get("input")
                if isinstance(acc_idx, int) and 0 <= acc_idx < len(accessors):
                    mx = accessors[acc_idx].get("max")
                    if isinstance(mx, list) and mx:
                        max_dur = max(max_dur, float(mx[0]))

        if animations and max_dur <= 0.0:
            issues.append("Animation clip reports non-positive duration.")

        if not animations:
            kind = ExportAnimationKind.STATIC_GARMENT_EXPORT
        elif has_baked_targets:
            kind = ExportAnimationKind.BAKED_SIMULATION_EXPORT
        elif has_garment_meta:
            kind = ExportAnimationKind.SKELETAL_WITH_GARMENT_DEFORMATION
        else:
            kind = ExportAnimationKind.SKELETAL_ANIMATION_EXPORT

        if skel_plan and not skel_plan.is_compatible:
            issues.extend(skel_plan.validation.issues)

        return AnimatedGLBValidationReport(
            is_valid=len(issues) == 0,
            export_kind=kind,
            byte_length=len(glb_bytes),
            sha256=hashlib.sha256(glb_bytes).hexdigest(),
            bone_count=len(bone_names),
            animation_count=len(animations),
            animation_names=anim_names,
            max_duration_s=round(max_dur, 4),
            has_skin_weights=has_skin,
            has_garment_attachment_metadata=has_garment_meta,
            has_baked_cloth_simulation=has_baked_targets,
            skeleton_compatible=bool(skel_plan and skel_plan.is_compatible) if bone_names else True,
            issues=issues,
        )


class MotionEvaluationReport(BaseModel):
    status: Literal["PASSED", "FAILED", "DEGRADED"]
    poses_evaluated: List[str]
    all_stable: bool
    pose_metrics: Dict[str, Dict[str, Any]]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    is_synthetic_fixture: bool = True
    physical_accuracy_claimed: Literal[False] = False


class MotionEvaluationService:
    """Evaluates garment skeletal stability using the canonical AnimationDeformationValidator."""

    @classmethod
    def evaluate_canonical_sequences(
        cls,
        *,
        positions: np.ndarray,
        indices: np.ndarray,
        joint_indices: Optional[np.ndarray] = None,
        joint_weights: Optional[np.ndarray] = None,
        poses: Optional[Sequence[str]] = None,
    ) -> MotionEvaluationReport:
        mesh = GarmentMesh(
            positions=positions.astype(np.float32),
            normals=np.tile(np.array([0.0, 0.0, 1.0], dtype=np.float32), (len(positions), 1)),
            uvs=np.zeros((len(positions), 2), dtype=np.float32),
            indices=indices.astype(np.uint32),
            joint_indices=joint_indices,
            joint_weights=joint_weights,
        )
        # Ensure neutral synthetic weights when unrigged fixture passed to motion evaluator
        if mesh.joint_indices is None or mesh.joint_weights is None:
            n = len(mesh.positions)
            mesh.joint_indices = np.zeros((n, 4), dtype=np.uint16)
            mesh.joint_indices[:, 0] = 3  # Spine2
            mesh.joint_weights = np.zeros((n, 4), dtype=np.float32)
            mesh.joint_weights[:, 0] = 1.0

        selected = list(poses or ["idle", "walking", "running", "arm_raising", "forward_bending", "sitting", "turning"])
        pose_metrics: Dict[str, Dict[str, Any]] = {}
        timings: List[float] = []
        all_ok = True

        for p_name in selected:
            t0 = time.perf_counter()
            if p_name not in AnimationDeformationValidator.CONTINUOUS_10_POSES:
                pose_metrics[p_name] = {"stable": False, "error": f"Unknown canonical pose '{p_name}'"}
                all_ok = False
                continue
            pose_dict = AnimationDeformationValidator.CONTINUOUS_10_POSES[p_name]
            metrics = AnimationDeformationValidator.validate_garment_deformation(
                mesh, poses={p_name: pose_dict}
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            timings.append(dt_ms)
            max_disp = round(metrics.max_vertex_displacement_mm / 1000.0, 4)
            stable = bool(metrics.deformation_stability_score >= 0.70 and max_disp <= 2.5)
            if not stable:
                all_ok = False
            pose_metrics[p_name] = {
                "stable": stable,
                "max_displacement_m": max_disp,
                "normal_inversions": metrics.normal_inversion_count,
                "stability_score": metrics.deformation_stability_score,
                "eval_ms": round(dt_ms, 3),
            }

        arr = np.sort(np.array(timings or [0.0], dtype=np.float64))
        return MotionEvaluationReport(
            status="PASSED" if all_ok else "FAILED",
            poses_evaluated=selected,
            all_stable=all_ok,
            pose_metrics=pose_metrics,
            p50_ms=round(float(np.percentile(arr, 50)), 3),
            p95_ms=round(float(np.percentile(arr, 95)), 3),
            p99_ms=round(float(np.percentile(arr, 99)), 3),
            is_synthetic_fixture=True,
            physical_accuracy_claimed=False,
        )
