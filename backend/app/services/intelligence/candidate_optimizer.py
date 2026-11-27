"""
YORVYN Intelligence Platform (YIP) — Controlled Candidate Optimization (Phase 17.0 Stage 6).

Connects IndependentQualityCritic with bounded deterministic repair/refinement operations:
- Bounded retry iterations (hard cap max_iterations <= 3)
- Bounded compute time budget (budget_ms <= 8000)
- Idempotency key support (owner-scoped)
- Explicit rollback if a revised candidate does not strictly improve or match critic gates
- Full parent -> child candidate lineage & provenance

Never permits unlimited loops or generator self-certification.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.services.garments.chat_candidate import edit_candidate, remove_invalid_triangles
from backend.app.services.intelligence.evaluation_critic import (
    IndependentEvaluationReport,
    evaluation_critic,
)


class CandidateRevisionStep(BaseModel):
    iteration: int
    operation: str
    parent_sha256: str
    revised_sha256: str
    accepted: bool
    rollback_triggered: bool
    before_critical: int
    after_critical: int
    before_major: int
    after_major: int
    reason: str


class CandidateOptimizationResult(BaseModel):
    initial_sha256: str
    final_sha256: str
    accepted_improved_candidate: bool
    publication_allowed: bool
    stopping_reason: str
    iterations_executed: int
    budget_ms_used: float
    lineage: List[CandidateRevisionStep] = Field(default_factory=list)
    initial_report: IndependentEvaluationReport
    final_report: IndependentEvaluationReport


class ControlledCandidateOptimizer:
    """Bounded, critic-gated candidate optimizer with rollback & lineage."""

    MAX_ITERATIONS_HARD_CAP = 3
    MAX_BUDGET_MS_HARD_CAP = 8000.0

    def __init__(self) -> None:
        self._idempotency_cache: Dict[str, Tuple[bytes, CandidateOptimizationResult]] = {}

    @staticmethod
    def _rank(report: IndependentEvaluationReport) -> Tuple[int, int, int, float]:
        geo_score = report.domains["geometry"].score or 0.0 if "geometry" in report.domains else 0.0
        fit_score = (report.domains["fit"].score or 0.0) if ("fit" in report.domains and report.domains["fit"].score is not None) else 0.0
        # Lower tuple is better: fewer critical, fewer major, fewer minor, higher avg score
        return (
            report.critical_defect_count,
            report.major_defect_count,
            report.minor_defect_count,
            -(geo_score + fit_score),
        )

    @staticmethod
    def _select_bounded_operation(report: IndependentEvaluationReport, attempted_ops: set) -> Optional[str]:
        defect_refs = " ".join(f"{d.domain}:{d.evidence_ref}:{d.suggested_action}" for d in report.defects).lower()
        if (
            any(tok in defect_refs for tok in ("cylindrical_torso_bloat", "hood_head_penetration", "invalid_skinning", "non_normalized", "overlapping_duplicate_meshes"))
            and "repair_geometry_and_refit" not in attempted_ops
        ):
            return "repair_geometry_and_refit"
        if ("degenerate" in defect_refs or "duplicate" in defect_refs or "remove_invalid_triangles" in defect_refs) and "remove_invalid_triangles" not in attempted_ops:
            return "remove_invalid_triangles"
        if ("negative_ease" in defect_refs or "body_penetration" in defect_refs) and "widen" not in attempted_ops:
            return "widen"
        return None

    @staticmethod
    def _execute_geometry_repair_on_glb(
        glb_bytes: bytes,
        *,
        category: str,
        report: IndependentEvaluationReport,
    ) -> bytes:
        import json, struct, io
        import numpy as np
        from PIL import Image
        from backend.app.services.garments.garment_mesh_builder import GarmentMesh
        from backend.app.services.garments.fitting.garment_asset_inspector import geometry_repair_engine
        from backend.app.services.garments.fitting.universal_garment_fitting_engine import universal_garment_fitting_engine
        from backend.app.services.garments.glb_exporter import glb_exporter
        from backend.app.services.intelligence.multi_model_reasoning import multi_model_reasoning

        if len(glb_bytes) < 20 or glb_bytes[:4] != b"glTF":
            raise ValueError("Invalid binary GLB header")
        j_len = struct.unpack_from("<I", glb_bytes, 12)[0]
        gltf = json.loads(glb_bytes[20 : 20 + j_len].decode("utf-8"))
        bin_off = 20 + j_len + 8
        bin_data = glb_bytes[bin_off:]

        # Preserve embedded diffuse & normal PNGs if present
        embedded_pngs = []
        for img_obj in gltf.get("images") or []:
            bv_i = img_obj.get("bufferView")
            if bv_i is not None and bv_i < len(gltf.get("bufferViews") or []):
                bv = gltf["bufferViews"][bv_i]
                s0 = bv.get("byteOffset", 0)
                l0 = bv.get("byteLength", 0)
                if s0 + l0 <= len(bin_data) and l0 > 16:
                    embedded_pngs.append(bin_data[s0 : s0 + l0])
        if not embedded_pngs:
            buf = io.BytesIO()
            Image.new("RGB", (64, 64), (160, 160, 160)).save(buf, format="PNG")
            embedded_pngs = [buf.getvalue()]
        diffuse_png = embedded_pngs[0]
        normal_png = embedded_pngs[1] if len(embedded_pngs) > 1 else diffuse_png

        # Extract merged unique primitive geometry from accessors
        meshes = gltf.get("meshes") or []
        if not meshes or not meshes[0].get("primitives"):
            raise ValueError("No mesh primitives present in GLB")
        prim0 = meshes[0]["primitives"][0]
        attrs = prim0.get("attributes") or {}

        def _read_acc(acc_id: Optional[int], dtype: str, cols: int) -> Optional[np.ndarray]:
            if acc_id is None or acc_id >= len(gltf.get("accessors") or []):
                return None
            acc = gltf["accessors"][acc_id]
            bv = gltf["bufferViews"][acc["bufferView"]]
            off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            cnt = acc["count"]
            return np.frombuffer(bin_data, dtype=dtype, count=cnt * cols, offset=off).reshape(-1, cols).copy()

        pos = _read_acc(attrs.get("POSITION"), "<f4", 3)
        if pos is None or len(pos) < 3:
            raise ValueError("Missing POSITION buffer in GLB")
        norm = _read_acc(attrs.get("NORMAL"), "<f4", 3)
        uv = _read_acc(attrs.get("TEXCOORD_0"), "<f4", 2)
        ji = _read_acc(attrs.get("JOINTS_0"), "<u2", 4)
        if ji is None:
            j_u8 = _read_acc(attrs.get("JOINTS_0"), "<u1", 4)
            ji = j_u8.astype(np.uint16) if j_u8 is not None else None
        jw = _read_acc(attrs.get("WEIGHTS_0"), "<f4", 4)

        all_idx = []
        for m in meshes:
            for pr in m.get("primitives") or []:
                ia = pr.get("indices")
                if ia is None:
                    continue
                acc = gltf["accessors"][ia]
                bv = gltf["bufferViews"][acc["bufferView"]]
                off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                dt = "<u4" if acc.get("componentType") == 5125 else "<u2"
                arr = np.frombuffer(bin_data, dtype=dt, count=acc["count"], offset=off).reshape(-1, 3).astype(np.uint32)
                all_idx.append(arr)
        if not all_idx:
            raise ValueError("No triangle indices in GLB")
        stacked = np.vstack(all_idx)
        # Deduplicate overlapping primitives by canonical sorted vertex triplet
        _, uniq_rows = np.unique(np.sort(stacked, axis=1), axis=0, return_index=True)
        uniq_rows = np.sort(uniq_rows)
        idx = stacked[uniq_rows]

        plan = multi_model_reasoning.propose_geometry_repair_plan(
            category=category,
            subcategory=category,
            defects=[d.model_dump() for d in report.defects],
            mesh_metrics={
                "depth_z_m": float(np.max(pos[:, 2]) - np.min(pos[:, 2])),
                "width_x_m": float(np.max(pos[:, 0]) - np.min(pos[:, 0])),
            },
            allow_remote=False,
        )
        pos_r, idx_r, norm_r, uv_r, ji_r, jw_r, receipt = geometry_repair_engine.repair(
            pos, idx, normals=norm, uvs=uv, joint_indices=ji, joint_weights=jw,
            category=category, subcategory=category, proposal=plan.payload,
        )
        if not receipt.applied:
            raise ValueError(receipt.rejected_reason or "Geometry repair rejected")

        gmesh = GarmentMesh(positions=pos_r, normals=norm_r, uvs=uv_r, indices=idx_r, joint_indices=ji_r, joint_weights=jw_r)
        fitted_mesh, _ = universal_garment_fitting_engine.fit_garment(mesh=gmesh, category=category, subcategory=category)
        return glb_exporter.export(fitted_mesh, diffuse_png, normal_png, name=f"repaired_{category}")

    def optimize_candidate(
        self,
        glb_bytes: bytes,
        *,
        category: str = "tops",
        avatar_profile_id: str = "standard_175",
        expected_components: Optional[List[str]] = None,
        max_iterations: int = 2,
        budget_ms: float = 4000.0,
        owner_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bytes, CandidateOptimizationResult]:
        if idempotency_key and owner_id:
            cache_key = f"{owner_id}:{idempotency_key}:{hashlib.sha256(glb_bytes).hexdigest()}"
            if cache_key in self._idempotency_cache:
                return self._idempotency_cache[cache_key]

        t0 = time.perf_counter()
        iters_cap = max(1, min(int(max_iterations), self.MAX_ITERATIONS_HARD_CAP))
        time_cap = max(250.0, min(float(budget_ms), self.MAX_BUDGET_MS_HARD_CAP))

        best_bytes = glb_bytes
        initial_report = evaluation_critic.evaluate_candidate(
            best_bytes,
            category=category,
            expected_components=expected_components,
            avatar_profile_id=avatar_profile_id,
        )
        best_report = initial_report
        lineage: List[CandidateRevisionStep] = []
        attempted_ops: set = set()
        stopping_reason = "NO_OPTIMIZATION_NEEDED"

        if initial_report.critical_defect_count == 0 and initial_report.major_defect_count == 0:
            res = CandidateOptimizationResult(
                initial_sha256=initial_report.candidate_sha256,
                final_sha256=initial_report.candidate_sha256,
                accepted_improved_candidate=False,
                publication_allowed=initial_report.publication_allowed,
                stopping_reason=stopping_reason,
                iterations_executed=0,
                budget_ms_used=round((time.perf_counter() - t0) * 1000.0, 3),
                lineage=lineage,
                initial_report=initial_report,
                final_report=initial_report,
            )
            return best_bytes, res

        for idx in range(1, iters_cap + 1):
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if elapsed_ms >= time_cap:
                stopping_reason = "BUDGET_EXHAUSTED"
                break

            op = self._select_bounded_operation(best_report, attempted_ops)
            if not op:
                stopping_reason = "NO_SUPPORTED_BOUNDED_REPAIR"
                break
            attempted_ops.add(op)

            parent_sha = best_report.candidate_sha256
            try:
                if op == "repair_geometry_and_refit":
                    candidate_bytes = self._execute_geometry_repair_on_glb(
                        best_bytes, category=category, report=best_report
                    )
                elif op == "remove_invalid_triangles":
                    candidate_bytes = remove_invalid_triangles(best_bytes)
                else:
                    candidate_bytes = edit_candidate(best_bytes, op)
            except Exception as exc:
                lineage.append(CandidateRevisionStep(
                    iteration=idx,
                    operation=op,
                    parent_sha256=parent_sha,
                    revised_sha256=parent_sha,
                    accepted=False,
                    rollback_triggered=True,
                    before_critical=best_report.critical_defect_count,
                    after_critical=best_report.critical_defect_count,
                    before_major=best_report.major_defect_count,
                    after_major=best_report.major_defect_count,
                    reason=f"Bounded operation failed cleanly: {exc}",
                ))
                stopping_reason = "BOUNDED_OP_INAPPLICABLE_ROLLBACK"
                continue

            revised_report = evaluation_critic.evaluate_candidate(
                candidate_bytes,
                category=category,
                expected_components=expected_components,
                avatar_profile_id=avatar_profile_id,
            )
            improved = self._rank(revised_report) < self._rank(best_report)
            if improved:
                lineage.append(CandidateRevisionStep(
                    iteration=idx,
                    operation=op,
                    parent_sha256=parent_sha,
                    revised_sha256=revised_report.candidate_sha256,
                    accepted=True,
                    rollback_triggered=False,
                    before_critical=best_report.critical_defect_count,
                    after_critical=revised_report.critical_defect_count,
                    before_major=best_report.major_defect_count,
                    after_major=revised_report.major_defect_count,
                    reason="Independent critic verified defect reduction.",
                ))
                best_bytes = candidate_bytes
                best_report = revised_report
                if best_report.critical_defect_count == 0 and best_report.major_defect_count == 0:
                    stopping_reason = "CRITIC_GATES_SATISFIED"
                    break
            else:
                lineage.append(CandidateRevisionStep(
                    iteration=idx,
                    operation=op,
                    parent_sha256=parent_sha,
                    revised_sha256=revised_report.candidate_sha256,
                    accepted=False,
                    rollback_triggered=True,
                    before_critical=best_report.critical_defect_count,
                    after_critical=revised_report.critical_defect_count,
                    before_major=best_report.major_defect_count,
                    after_major=revised_report.major_defect_count,
                    reason="Revised candidate did not improve independent critic rank; rolled back to parent.",
                ))
                stopping_reason = "ROLLED_BACK_NO_IMPROVEMENT"
        else:
            if stopping_reason == "NO_OPTIMIZATION_NEEDED":
                stopping_reason = "MAX_ITERATIONS_REACHED"

        final_res = CandidateOptimizationResult(
            initial_sha256=initial_report.candidate_sha256,
            final_sha256=best_report.candidate_sha256,
            accepted_improved_candidate=best_report.candidate_sha256 != initial_report.candidate_sha256,
            publication_allowed=best_report.publication_allowed,
            stopping_reason=stopping_reason,
            iterations_executed=len(lineage),
            budget_ms_used=round((time.perf_counter() - t0) * 1000.0, 3),
            lineage=lineage,
            initial_report=initial_report,
            final_report=best_report,
        )
        if idempotency_key and owner_id:
            cache_key = f"{owner_id}:{idempotency_key}:{initial_report.candidate_sha256}"
            self._idempotency_cache[cache_key] = (best_bytes, final_res)
        return best_bytes, final_res


candidate_optimizer = ControlledCandidateOptimizer()
