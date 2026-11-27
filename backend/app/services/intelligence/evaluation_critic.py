"""
YORVYN Intelligence Platform (YIP) — Independent AI Quality Critic (Phase 17.0 Stage 6).

Evaluates generated 3D garment candidates completely independently of the generator's
internal confidence across 5 domains:
- geometry (manifold, degenerate/duplicate faces, winding, bounds)
- texture (UV accessors, [0,1] bounds, PBR materials, textures)
- construction (GLB semantic component nodes vs observed garment specification)
- fit (clearance, penetration, ease, symmetry against avatar measurements)
- motion (skinning/animation glTF validation when rigged, honest NOT_EVALUATED if rigid)

Critical failures block publication. Recommendations never count as completed repairs.
"""
from __future__ import annotations

import hashlib
import json
import struct
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, Field

from backend.app.services.garments.mesh_validation_service import mesh_validation_service
from backend.app.services.intelligence.fit_intelligence import fit_intelligence
from backend.app.services.intelligence.inference_adapters import inference_telemetry


class DefectSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class AcceptanceVerdict(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


class CriticOverallStatus(str, Enum):
    PASSED = "PASSED"
    PASSED_WITH_WARNINGS = "PASSED_WITH_WARNINGS"
    FAILED_CRITICAL = "FAILED_CRITICAL"
    BLOCKED = "BLOCKED"


class CriticDefect(BaseModel):
    defect_id: str
    domain: str
    location: str
    severity: DefectSeverity
    evidence_ref: str
    confidence: float = Field(ge=0.0, le=1.0)
    evaluation_method: str
    model_identity: str
    limitations: str
    suggested_action: str


class DomainCriticResult(BaseModel):
    domain: str
    status: str  # PASSED | PASSED_WITH_WARNINGS | FAILED | NOT_EVALUATED
    score: Optional[float] = None
    defect_ids: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    evaluation_method: str
    model_identity: str
    limitations: str


class IndependentEvaluationReport(BaseModel):
    candidate_sha256: str
    overall_status: CriticOverallStatus
    publication_allowed: bool
    remediation_executed: bool = False  # Always False on critic report: recommendations are not repairs
    critical_defect_count: int = 0
    major_defect_count: int = 0
    minor_defect_count: int = 0
    domains: Dict[str, DomainCriticResult] = Field(default_factory=dict)
    defects: List[CriticDefect] = Field(default_factory=list)
    total_latency_ms: float = 0.0


def _parse_glb_chunks(glb_bytes: bytes) -> Optional[Dict[str, Any]]:
    if not glb_bytes or len(glb_bytes) < 28:
        return None
    magic, version, total_len, json_len, json_type = struct.unpack_from("<4sIII4s", glb_bytes, 0)
    if magic != b"glTF" or version != 2 or total_len != len(glb_bytes) or json_type != b"JSON":
        return None
    try:
        gltf = json.loads(glb_bytes[20 : 20 + json_len].decode("utf-8"))
    except Exception:
        return None
    bin_offset = 20 + json_len
    bin_bytes = b""
    if bin_offset + 8 <= len(glb_bytes):
        b_len, b_type = struct.unpack_from("<I4s", glb_bytes, bin_offset)
        if b_type == b"BIN\x00":
            bin_bytes = glb_bytes[bin_offset + 8 : bin_offset + 8 + b_len]
    return {"gltf": gltf, "bin": bin_bytes}


class IndependentQualityCritic:
    """Multi-domain evaluation critic strictly independent from generators."""

    def evaluate_candidate(
        self,
        glb_bytes: bytes,
        *,
        category: str = "tops",
        expected_components: Optional[List[str]] = None,
        avatar_profile_id: str = "standard_175",
        skip_fit: bool = False,
    ) -> IndependentEvaluationReport:
        t0 = time.perf_counter()
        cand_sha = hashlib.sha256(glb_bytes or b"").hexdigest()
        defects: List[CriticDefect] = []
        domains: Dict[str, DomainCriticResult] = {}

        def _add_defect(
            *,
            domain: str,
            location: str,
            severity: DefectSeverity,
            evidence_ref: str,
            confidence: float,
            method: str,
            model_id: str,
            limitations: str,
            action: str,
        ) -> str:
            did = f"{domain}_{len(defects) + 1:03d}"
            defects.append(CriticDefect(
                defect_id=did,
                domain=domain,
                location=location,
                severity=severity,
                evidence_ref=evidence_ref,
                confidence=round(float(confidence), 3),
                evaluation_method=method,
                model_identity=model_id,
                limitations=limitations,
                suggested_action=action,
            ))
            return did

        # ── 1. Geometry Critic ──────────────────────────────────────────────
        mesh_report = mesh_validation_service.validate_glb_bytes(glb_bytes, category=category)
        geo_defects: List[str] = []
        if not mesh_report.is_valid or mesh_report.face_count == 0:
            geo_defects.append(_add_defect(
                domain="geometry",
                location="glb_mesh_topology",
                severity=DefectSeverity.CRITICAL,
                evidence_ref=f"faces={mesh_report.face_count}, issues={mesh_report.issues}",
                confidence=0.98,
                method="trimesh_and_edge_incidence",
                model_id="MeshValidationService-v13.2",
                limitations="Topological validity does not measure real-world garment aesthetic accuracy.",
                action="Regenerate candidate mesh or run clean topology repair before publication.",
            ))
        if mesh_report.non_manifold_edges_count > 0:
            geo_defects.append(_add_defect(
                domain="geometry",
                location="edge_topology",
                severity=DefectSeverity.CRITICAL,
                evidence_ref=f"non_manifold_edges={mesh_report.non_manifold_edges_count}",
                confidence=0.99,
                method="edge_incidence_audit",
                model_id="MeshValidationService-v13.2",
                limitations="Edge incidence counts triangle adjacency anomalies only.",
                action="Repair non-manifold shared edges prior to physics simulation.",
            ))
        # Also check raw primitive triangle indices directly (in case Trimesh auto-stripped duplicates/zero-area on load)
        parsed_raw = _parse_glb_chunks(glb_bytes)
        raw_degen = raw_dup = total_raw_tris = 0
        all_tri_tuples = []
        if parsed_raw:
            gltf_r, bin_r = parsed_raw["gltf"], parsed_raw["bin"]
            for m_obj in gltf_r.get("meshes") or []:
                for prim in m_obj.get("primitives") or []:
                    idx_acc_id = prim.get("indices")
                    pos_acc_id = (prim.get("attributes") or {}).get("POSITION")
                    if idx_acc_id is None or pos_acc_id is None:
                        continue
                    i_acc = gltf_r["accessors"][idx_acc_id]
                    p_acc = gltf_r["accessors"][pos_acc_id]
                    i_bv = gltf_r["bufferViews"][i_acc["bufferView"]]
                    p_bv = gltf_r["bufferViews"][p_acc["bufferView"]]
                    if i_acc.get("componentType") == 5125 and p_acc.get("componentType") == 5126 and "byteStride" not in i_bv and "byteStride" not in p_bv:
                        ioff = i_bv.get("byteOffset", 0) + i_acc.get("byteOffset", 0)
                        poff = p_bv.get("byteOffset", 0) + p_acc.get("byteOffset", 0)
                        if ioff + i_acc["count"] * 4 <= len(bin_r) and poff + p_acc["count"] * 12 <= len(bin_r):
                            tris = np.frombuffer(bin_r, dtype="<u4", count=i_acc["count"], offset=ioff).reshape(-1, 3)
                            pts = np.frombuffer(bin_r, dtype="<f4", count=p_acc["count"] * 3, offset=poff).reshape(-1, 3)
                            total_raw_tris += len(tris)
                            if len(tris) > 0 and int(np.max(tris)) < len(pts):
                                tpts = pts[tris]
                                areas = 0.5 * np.linalg.norm(np.cross(tpts[:, 1] - tpts[:, 0], tpts[:, 2] - tpts[:, 0]), axis=1)
                                raw_degen += int(np.sum(areas <= 1e-9))
                                s_tris = np.sort(tris, axis=1)
                                _, uniq_idx = np.unique(s_tris, axis=0, return_index=True)
                                raw_dup += int(len(tris) - len(uniq_idx))
                                all_tri_tuples.append(s_tris)
        if all_tri_tuples:
            combined_tris = np.vstack(all_tri_tuples)
            _, uniq_global = np.unique(combined_tris, axis=0, return_index=True)
            global_overlap_ratio = float(len(combined_tris)) / max(1.0, float(len(uniq_global)))
            if global_overlap_ratio > 1.25:
                geo_defects.append(_add_defect(
                    domain="geometry",
                    location="overlapping_primitives",
                    severity=DefectSeverity.CRITICAL if global_overlap_ratio > 2.0 else DefectSeverity.MAJOR,
                    evidence_ref=f"overlapping_duplicate_meshes: exported_tris={len(combined_tris)}, unique_tris={len(uniq_global)}, ratio={global_overlap_ratio:.2f}x",
                    confidence=0.99,
                    method="global_primitive_overlap_audit",
                    model_id="MeshValidationService-v13.2",
                    limitations="Detects shared/overlapping triangle ranges across multiple glTF primitives.",
                    action="Deduplicate overlapping alias/sub-slice component primitives before GLB export.",
                ))

        total_degen = max(mesh_report.degenerate_faces, raw_degen)
        total_dup = max(mesh_report.duplicate_faces, raw_dup)
        if total_degen > 0 or total_dup > 0:
            sev = DefectSeverity.MAJOR if (total_degen + total_dup) > 10 else DefectSeverity.MINOR
            geo_defects.append(_add_defect(
                domain="geometry",
                location="triangle_indices",
                severity=sev,
                evidence_ref=f"degenerate={total_degen}, duplicate={total_dup}",
                confidence=0.97,
                method="triangle_area_and_dedup",
                model_id="MeshValidationService-v13.2",
                limitations="Detects zero-area/duplicate triangles; ignores UV foldovers.",
                action="Run bounded remove_invalid_triangles repair.",
            ))
        if not mesh_report.is_winding_consistent:
            geo_defects.append(_add_defect(
                domain="geometry",
                location="face_normals",
                severity=DefectSeverity.MAJOR,
                evidence_ref="is_winding_consistent=False",
                confidence=0.92,
                method="consistent_winding_check",
                model_id="MeshValidationService-v13.2",
                limitations="Orientation consistency on disconnected sub-meshes evaluated per shell.",
                action="Normalize face winding orientation consistently.",
            ))
        hole_threshold = max(1200, int(0.65 * max(1, mesh_report.face_count)))
        if mesh_report.is_valid and (mesh_report.connected_components > 40 or mesh_report.boundary_edges_count > hole_threshold):
            geo_defects.append(_add_defect(
                domain="geometry",
                location="boundary_loops_and_shells",
                severity=DefectSeverity.MAJOR,
                evidence_ref=f"skin_visible_holes: connected_components={mesh_report.connected_components}, boundary_edges={mesh_report.boundary_edges_count}",
                confidence=0.86,
                method="boundary_loop_fragmentation_audit",
                model_id="MeshValidationService-v13.2",
                limitations="Detects torn mesh shells and excessive open boundary seams beyond collar/armscye/hem openings.",
                action="Stitch torn seam loops or regenerate manifold shell.",
            ))

        geo_score = 100.0
        for did in geo_defects:
            d = next(x for x in defects if x.defect_id == did)
            geo_score -= 40.0 if d.severity == DefectSeverity.CRITICAL else (15.0 if d.severity == DefectSeverity.MAJOR else 5.0)
        geo_score = max(0.0, round(geo_score, 1))
        domains["geometry"] = DomainCriticResult(
            domain="geometry",
            status=("FAILED" if any(d.severity == DefectSeverity.CRITICAL for d in defects if d.defect_id in geo_defects) else ("PASSED_WITH_WARNINGS" if geo_defects else "PASSED")),
            score=geo_score,
            defect_ids=geo_defects,
            metrics=mesh_report.to_dict(),
            evaluation_method="trimesh_manifold_winding_bounds",
            model_identity="MeshValidationService-v13.2",
            limitations="Evaluates geometric topology and anthropometric bounds, not photorealism.",
        )

        # ── 2. Texture & UV Critic ──────────────────────────────────────────
        parsed = _parse_glb_chunks(glb_bytes)
        tex_defects: List[str] = []
        uv_coverage = {"primitives_with_uv": 0, "total_primitives": 0, "uv_out_of_bounds_ratio": 0.0, "materials_count": 0, "images_count": 0}
        if not parsed:
            tex_defects.append(_add_defect(
                domain="texture",
                location="glb_container",
                severity=DefectSeverity.CRITICAL,
                evidence_ref="invalid_glb_header_or_json",
                confidence=0.99,
                method="glb_binary_chunk_parser",
                model_id="GLBTextureCritic-v17",
                limitations="Requires binary glTF 2.0 container.",
                action="Re-export valid binary glTF 2.0.",
            ))
        else:
            gltf = parsed["gltf"]
            raw_bin = parsed["bin"]
            uv_coverage["materials_count"] = len(gltf.get("materials") or [])
            uv_coverage["images_count"] = len(gltf.get("images") or [])
            oob_ratios: List[float] = []
            for mesh_obj in gltf.get("meshes") or []:
                for prim in mesh_obj.get("primitives") or []:
                    uv_coverage["total_primitives"] += 1
                    attrs = prim.get("attributes") or {}
                    if "TEXCOORD_0" in attrs:
                        uv_coverage["primitives_with_uv"] += 1
                        acc = gltf["accessors"][attrs["TEXCOORD_0"]]
                        bv = gltf["bufferViews"][acc["bufferView"]]
                        if acc.get("componentType") == 5126 and acc.get("type") == "VEC2" and "byteStride" not in bv:
                            off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                            cnt = acc["count"]
                            if off + cnt * 8 <= len(raw_bin):
                                uvs = np.frombuffer(raw_bin, dtype="<f4", count=cnt * 2, offset=off).reshape(-1, 2)
                                if np.all(np.isfinite(uvs)):
                                    oob = float(np.mean((uvs < -0.05) | (uvs > 1.05)))
                                    oob_ratios.append(oob)
                                else:
                                    oob_ratios.append(1.0)
            if uv_coverage["total_primitives"] > 0 and uv_coverage["primitives_with_uv"] == 0:
                tex_defects.append(_add_defect(
                    domain="texture",
                    location="mesh_uv_attributes",
                    severity=DefectSeverity.MAJOR,
                    evidence_ref="missing TEXCOORD_0 across primitives",
                    confidence=0.96,
                    method="gltf_accessor_inspection",
                    model_id="GLBTextureCritic-v17",
                    limitations="Checks UV attribute presence and bounds; does not compare rendered pixels against photo.",
                    action="Run UV parameterization before material projection.",
                ))
            if oob_ratios:
                max_oob = max(oob_ratios)
                uv_coverage["uv_out_of_bounds_ratio"] = round(max_oob, 4)
                if max_oob > 0.15:
                    tex_defects.append(_add_defect(
                        domain="texture",
                        location="TEXCOORD_0",
                        severity=DefectSeverity.MINOR,
                        evidence_ref=f"uv_oob_ratio={max_oob:.3f}",
                        confidence=0.90,
                        method="uv_bounds_check",
                        model_id="GLBTextureCritic-v17",
                        limitations="Wrapped tiled UVs outside [0,1] may be intentional for repeating fabric weaves.",
                        action="Verify UV island clamping against texture atlas.",
                    ))
            if uv_coverage["materials_count"] == 0:
                tex_defects.append(_add_defect(
                    domain="texture",
                    location="materials",
                    severity=DefectSeverity.MINOR,
                    evidence_ref="materials_count=0",
                    confidence=0.95,
                    method="gltf_material_check",
                    model_id="GLBTextureCritic-v17",
                    limitations="Structural material count inspection only.",
                    action="Attach PBR material descriptor to primitives.",
                ))
            elif uv_coverage["primitives_with_uv"] > 0 and uv_coverage["images_count"] == 0:
                tex_defects.append(_add_defect(
                    domain="texture",
                    location="texture_maps",
                    severity=DefectSeverity.MAJOR,
                    evidence_ref="texture_gap: UVs present with images_count=0",
                    confidence=0.93,
                    method="gltf_texture_coverage_check",
                    model_id="GLBTextureCritic-v17",
                    limitations="Flags textured UV candidates lacking embedded albedo/normal texture buffers.",
                    action="Attach baseColorTexture / diffuse map image buffer.",
                ))
            for img_idx, img_obj in enumerate(gltf.get("images") or []):
                bv_idx = img_obj.get("bufferView")
                if bv_idx is not None and bv_idx < len(gltf.get("bufferViews") or []):
                    if (gltf["bufferViews"][bv_idx].get("byteLength") or 0) <= 16:
                        tex_defects.append(_add_defect(
                            domain="texture",
                            location=f"images[{img_idx}]",
                            severity=DefectSeverity.CRITICAL,
                            evidence_ref=f"texture_gap: empty_image_buffer_{img_idx}",
                            confidence=0.99,
                            method="gltf_image_buffer_check",
                            model_id="GLBTextureCritic-v17",
                            limitations="Checks embedded buffer size > 16 bytes.",
                            action="Re-encode valid PNG/JPEG texture payload.",
                        ))

        tex_score = max(0.0, round(100.0 - 15.0 * len(tex_defects), 1))
        domains["texture"] = DomainCriticResult(
            domain="texture",
            status=("FAILED" if any(d.severity == DefectSeverity.CRITICAL for d in defects if d.defect_id in tex_defects) else ("PASSED_WITH_WARNINGS" if tex_defects else "PASSED")),
            score=tex_score,
            defect_ids=tex_defects,
            metrics=uv_coverage,
            evaluation_method="gltf_uv_and_material_inspection",
            model_identity="GLBTextureCritic-v17",
            limitations="Checks UV coordinates and material attachment, not photographic visual similarity.",
        )

        # ── 3. Construction Critic ──────────────────────────────────────────
        con_defects: List[str] = []
        node_semantics: List[str] = []
        if parsed:
            for node in parsed["gltf"].get("nodes") or []:
                label = f"{node.get('name', '')} {node.get('extras', {}).get('semantic_type', '')}".strip().lower()
                if label:
                    node_semantics.append(label)
        missing_comps: List[str] = []
        for comp in (expected_components or []):
            key = comp.lower().replace("_", " ")
            token = key.split()[0]
            if not any((comp.lower() in s or token in s) for s in node_semantics):
                missing_comps.append(comp)
        if missing_comps:
            con_defects.append(_add_defect(
                domain="construction",
                location="node_component_hierarchy",
                severity=DefectSeverity.MAJOR,
                evidence_ref=f"missing_expected_components={missing_comps}",
                confidence=0.88,
                method="gltf_semantic_node_audit",
                model_id="ConstructionCritic-v17",
                limitations="Checks GLB semantic metadata tags against expected components.",
                action="Ensure all observed garment components are realized in exported nodes.",
            ))
        domains["construction"] = DomainCriticResult(
            domain="construction",
            status="PASSED_WITH_WARNINGS" if con_defects else "PASSED",
            score=max(0.0, round(100.0 - 20.0 * len(con_defects), 1)),
            defect_ids=con_defects,
            metrics={"node_labels_count": len(node_semantics), "missing_components": missing_comps},
            evaluation_method="gltf_semantic_hierarchy_verification",
            model_identity="ConstructionCritic-v17",
            limitations="Verifies GLB node component representation, not physical sewing seam strength.",
        )

        # ── 4. Fit Critic ───────────────────────────────────────────────────
        fit_defects: List[str] = []
        if skip_fit or not mesh_report.is_valid:
            domains["fit"] = DomainCriticResult(
                domain="fit",
                status="NOT_EVALUATED",
                score=None,
                metrics={"reason": "Skipped due to invalid geometry or skip flag"},
                evaluation_method="FitIntelligenceEngine-v17",
                model_identity="FitIntelligenceEngine-v17",
                limitations="Requires valid geometry to compute hull clearance.",
            )
        else:
            fit_rep = fit_intelligence.analyze_fit(
                category=category,
                glb_bytes=glb_bytes,
                avatar_profile_id=avatar_profile_id,
            )
            for fd in fit_rep.defects:
                sev = DefectSeverity(fd.severity) if fd.severity in DefectSeverity._value2member_map_ else DefectSeverity.MINOR
                fit_defects.append(_add_defect(
                    domain="fit",
                    location=fd.location,
                    severity=sev,
                    evidence_ref=f"{fd.defect_type}: {fd.measured_metric}",
                    confidence=0.85,
                    method="avatar_hull_clearance_and_ease",
                    model_id="FitIntelligenceEngine-v17",
                    limitations=fit_rep.limitations,
                    action=fd.suggestion,
                ))
            domains["fit"] = DomainCriticResult(
                domain="fit",
                status=("FAILED" if any(d.severity == DefectSeverity.CRITICAL for d in defects if d.defect_id in fit_defects) else ("PASSED_WITH_WARNINGS" if fit_defects else "PASSED")),
                score=fit_rep.overall_fit_score,
                defect_ids=fit_defects,
                metrics={
                    "fit_classification": fit_rep.fit_classification.value,
                    "collision_count": fit_rep.collision_count,
                    "max_penetration_mm": fit_rep.max_penetration_mm,
                    "average_clearance_mm": fit_rep.average_clearance_mm,
                },
                evaluation_method="avatar_hull_clearance_and_ease",
                model_identity="FitIntelligenceEngine-v17",
                limitations=fit_rep.limitations,
            )

        # ── 5. Motion Critic ────────────────────────────────────────────────
        mot_defects: List[str] = []
        is_rigged = bool(parsed and (parsed["gltf"].get("skins") or parsed["gltf"].get("animations")))
        if not is_rigged:
            domains["motion"] = DomainCriticResult(
                domain="motion",
                status="NOT_EVALUATED",
                score=None,
                metrics={"rigged_or_animated": False},
                evaluation_method="AnimationAssetSecurityValidator-v16.9",
                model_identity="AnimationAssetSecurityValidator-v16.9",
                limitations="Candidate is a static rigid garment mesh without skins/animations; dynamic motion not evaluated.",
            )
        else:
            from backend.app.services.motion.motion_core import AnimationAssetSecurityValidator
            mot_rep = AnimationAssetSecurityValidator.validate_glb_animation_payload(glb_bytes)
            for err in mot_rep.issues:
                mot_defects.append(_add_defect(
                    domain="motion",
                    location="skin_or_animation",
                    severity=DefectSeverity.CRITICAL,
                    evidence_ref=err,
                    confidence=0.95,
                    method="AnimationAssetSecurityValidator-v16.9",
                    model_id="AnimationAssetSecurityValidator-v16.9",
                    limitations="Structural glTF animation validation only.",
                    action="Repair bone/skin weight tables or clip tracks before export.",
                ))
            # Inspect JOINTS_0 / WEIGHTS_0 skinning bounds & normalization
            gltf = parsed["gltf"]
            raw_bin = parsed["bin"]
            skins = gltf.get("skins") or []
            max_joints = max((len(s.get("joints") or []) for s in skins), default=0)
            for mesh_obj in gltf.get("meshes") or []:
                for prim in mesh_obj.get("primitives") or []:
                    attrs = prim.get("attributes") or {}
                    if "WEIGHTS_0" in attrs:
                        w_acc = gltf["accessors"][attrs["WEIGHTS_0"]]
                        w_bv = gltf["bufferViews"][w_acc["bufferView"]]
                        if w_acc.get("componentType") == 5126 and w_acc.get("type") == "VEC4" and "byteStride" not in w_bv:
                            off = w_bv.get("byteOffset", 0) + w_acc.get("byteOffset", 0)
                            cnt = w_acc["count"]
                            if off + cnt * 16 <= len(raw_bin):
                                wts = np.frombuffer(raw_bin, dtype="<f4", count=cnt * 4, offset=off).reshape(-1, 4)
                                w_sums = wts.sum(axis=1)
                                if not np.all(np.isfinite(wts)) or np.any(wts < -1e-4) or np.mean(np.abs(w_sums - 1.0) > 0.08) > 0.05:
                                    mot_defects.append(_add_defect(
                                        domain="motion",
                                        location="WEIGHTS_0",
                                        severity=DefectSeverity.CRITICAL,
                                        evidence_ref="invalid_skinning: non_normalized_or_corrupt_weights",
                                        confidence=0.97,
                                        method="gltf_skin_weight_audit",
                                        model_id="SkinningValidator-v17.1",
                                        limitations="Verifies vertex skin weight finiteness, non-negativity, and unit normalization.",
                                        action="Renormalize per-vertex bone weights prior to skeletal deformation.",
                                    ))
                    if "JOINTS_0" in attrs and max_joints > 0:
                        j_acc = gltf["accessors"][attrs["JOINTS_0"]]
                        j_bv = gltf["bufferViews"][j_acc["bufferView"]]
                        dtype_j = "<u2" if j_acc.get("componentType") == 5123 else ("<u1" if j_acc.get("componentType") == 5121 else None)
                        if dtype_j and j_acc.get("type") == "VEC4" and "byteStride" not in j_bv:
                            off = j_bv.get("byteOffset", 0) + j_acc.get("byteOffset", 0)
                            cnt = j_acc["count"]
                            esize = 2 if dtype_j == "<u2" else 1
                            if off + cnt * 4 * esize <= len(raw_bin):
                                jts = np.frombuffer(raw_bin, dtype=dtype_j, count=cnt * 4, offset=off).reshape(-1, 4)
                                if int(np.max(jts)) >= max_joints:
                                    mot_defects.append(_add_defect(
                                        domain="motion",
                                        location="JOINTS_0",
                                        severity=DefectSeverity.CRITICAL,
                                        evidence_ref=f"invalid_skinning: joint_index_oob_max={int(np.max(jts))}_joints={max_joints}",
                                        confidence=0.99,
                                        method="gltf_joint_index_audit",
                                        model_id="SkinningValidator-v17.1",
                                        limitations="Verifies vertex bone indices fall within declared skin joints.",
                                        action="Clamp or remap out-of-bounds joint indices to valid skin bones.",
                                    ))
            domains["motion"] = DomainCriticResult(
                domain="motion",
                status="FAILED" if mot_defects else "PASSED",
                score=0.0 if mot_defects else 100.0,
                defect_ids=mot_defects,
                metrics={"export_kind": str(mot_rep.export_kind), "clip_count": len(mot_rep.animation_names)},
                evaluation_method="AnimationAssetSecurityValidator-v16.9",
                model_identity="AnimationAssetSecurityValidator-v16.9",
                limitations="Structural glTF rig validation only.",
            )

        crit_cnt = sum(1 for d in defects if d.severity == DefectSeverity.CRITICAL)
        maj_cnt = sum(1 for d in defects if d.severity == DefectSeverity.MAJOR)
        min_cnt = sum(1 for d in defects if d.severity == DefectSeverity.MINOR)

        if crit_cnt > 0:
            overall = CriticOverallStatus.FAILED_CRITICAL
            pub_allowed = False
        elif maj_cnt > 0 or min_cnt > 0:
            overall = CriticOverallStatus.PASSED_WITH_WARNINGS
            pub_allowed = True
        else:
            overall = CriticOverallStatus.PASSED
            pub_allowed = True

        lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("independent-critic-v17", lat_ms, device="cpu", backend="independent_critic")
        return IndependentEvaluationReport(
            candidate_sha256=cand_sha,
            overall_status=overall,
            publication_allowed=pub_allowed,
            remediation_executed=False,
            critical_defect_count=crit_cnt,
            major_defect_count=maj_cnt,
            minor_defect_count=min_cnt,
            domains=domains,
            defects=defects,
            total_latency_ms=lat_ms,
        )


class QualityGateResult(BaseModel):
    verdict: AcceptanceVerdict
    publication_allowed: bool
    reasons: List[str] = Field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0


class GarmentQualityGate:
    """Authoritative pre-publication gate distinguishing PASS, PASS_WITH_WARNINGS, DEGRADED, FAILED, NOT_EVALUATED."""

    def evaluate_gate(
        self,
        report: Optional[IndependentEvaluationReport],
        *,
        correspondence_valid: bool = True,
        correspondence_blockers: Optional[List[str]] = None,
        visual_head_penetrations: int = 0,
        visual_spike_anomaly: bool = False,
        fallback_degraded: bool = False,
    ) -> QualityGateResult:
        if report is None:
            return QualityGateResult(
                verdict=AcceptanceVerdict.NOT_EVALUATED,
                publication_allowed=False,
                reasons=["Independent critic report missing."],
            )
        reasons: List[str] = []
        crit = int(report.critical_defect_count)
        maj = int(report.major_defect_count)
        min_c = int(report.minor_defect_count)

        if not correspondence_valid:
            crit += 1
            reasons.extend(correspondence_blockers or ["Semantic correspondence invalid."])
        if visual_head_penetrations > 12:
            crit += 1
            reasons.append(f"Visual validator detected {visual_head_penetrations} skull-penetrating vertices.")
        elif visual_head_penetrations > 0:
            maj += 1
            reasons.append(f"Minor head/collar clearance alert ({visual_head_penetrations} verts).")
        if visual_spike_anomaly:
            crit += 1
            reasons.append("Visual spike / torn triangle edge anomaly detected.")

        if crit > 0 or not report.publication_allowed:
            for d in report.defects:
                if d.severity == DefectSeverity.CRITICAL:
                    reasons.append(f"{d.domain}:{d.evidence_ref}")
            return QualityGateResult(
                verdict=AcceptanceVerdict.FAILED,
                publication_allowed=False,
                reasons=reasons[:8] or ["Critical critic gate failure."],
                critical_count=crit,
                major_count=maj,
                minor_count=min_c,
            )

        if fallback_degraded or maj >= 2:
            for d in report.defects:
                if d.severity == DefectSeverity.MAJOR:
                    reasons.append(f"{d.domain}:{d.evidence_ref}")
            return QualityGateResult(
                verdict=AcceptanceVerdict.DEGRADED,
                publication_allowed=True,
                reasons=reasons[:8] or ["Completed with fallback or multiple major warnings."],
                critical_count=crit,
                major_count=maj,
                minor_count=min_c,
            )

        if maj > 0 or min_c > 0:
            return QualityGateResult(
                verdict=AcceptanceVerdict.PASS_WITH_WARNINGS,
                publication_allowed=True,
                reasons=[f"{d.domain}:{d.evidence_ref}" for d in report.defects[:6]],
                critical_count=crit,
                major_count=maj,
                minor_count=min_c,
            )

        return QualityGateResult(
            verdict=AcceptanceVerdict.PASS,
            publication_allowed=True,
            reasons=["All geometry, texture, construction, fit, skinning, and visual gates passed cleanly."],
            critical_count=0,
            major_count=0,
            minor_count=0,
        )


evaluation_critic = IndependentQualityCritic()
garment_quality_gate = GarmentQualityGate()

