"""
YORVYN — 3D Reconstruction Geometry Utilities
Provides shared geometric math, quad-strip stitching, normal calculation,
Ara 3D Gen 20-bone skinning weight generators, and observed surface classification.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from backend.app.services.garments.garment_mesh_builder import (
    ARA_SKELETON_SPECS,
    CANONICAL_ARM_DIR_LEFT,
    CANONICAL_ARM_DIR_RIGHT,
    CANONICAL_SHOULDER_ORIGIN_LEFT,
    CANONICAL_SHOULDER_ORIGIN_RIGHT
)


def calculate_smooth_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Computes area-weighted vertex normals with unit normalization."""
    num_verts = len(positions)
    normals = np.zeros((num_verts, 3), dtype=np.float32)
    
    if len(indices) == 0:
        return normals

    # Handle flattened or (N, 3) indices
    if indices.ndim == 1:
        tri_indices = indices.reshape(-1, 3)
    else:
        tri_indices = indices

    v0 = positions[tri_indices[:, 0]]
    v1 = positions[tri_indices[:, 1]]
    v2 = positions[tri_indices[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)  # Area-weighted

    for i in range(3):
        np.add.at(normals, tri_indices[:, i], face_normals)

    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens[lens < 1e-8] = 1.0
    return (normals / lens).astype(np.float32)


def laplacian_smooth_mesh(
    positions: np.ndarray,
    indices: np.ndarray,
    iterations: int = 2,
    lambda_factor: float = 0.20,
    pinned_vertices: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Applies edge-preserving Laplacian surface smoothing to eliminate polygonal faceting
    while preserving physical tailoring boundaries and pinned feature seams.
    """
    if len(positions) == 0 or len(indices) == 0:
        return positions

    tris = indices.reshape(-1, 3) if indices.ndim == 1 else indices
    num_verts = len(positions)
    smoothed = positions.copy()

    # Build vertex adjacency
    adj: List[set] = [set() for _ in range(num_verts)]
    for tri in tris:
        adj[tri[0]].add(tri[1])
        adj[tri[0]].add(tri[2])
        adj[tri[1]].add(tri[0])
        adj[tri[1]].add(tri[2])
        adj[tri[2]].add(tri[0])
        adj[tri[2]].add(tri[1])

    # Identify boundary vertices (edges with count == 1)
    edges = []
    for tri in tris:
        edges.append(tuple(sorted([tri[0], tri[1]])))
        edges.append(tuple(sorted([tri[1], tri[2]])))
        edges.append(tuple(sorted([tri[2], tri[0]])))

    from collections import Counter
    edge_counts = Counter(edges)
    boundary_v = set()
    for (v_a, v_b), count in edge_counts.items():
        if count == 1:
            boundary_v.add(v_a)
            boundary_v.add(v_b)

    for _ in range(iterations):
        new_pos = smoothed.copy()
        for v in range(num_verts):
            if v in boundary_v:
                continue
            if pinned_vertices is not None and pinned_vertices[v]:
                continue
            neighbors = list(adj[v])
            if len(neighbors) == 0:
                continue
            centroid = np.mean(smoothed[neighbors], axis=0)
            new_pos[v] = smoothed[v] + lambda_factor * (centroid - smoothed[v])
        smoothed = new_pos

    return smoothed.astype(np.float32)


def compute_mesh_quality_metrics(positions: np.ndarray, indices: np.ndarray) -> Dict[str, Any]:
    """
    Authoritative computational geometry diagnostics for Phase 14.21:
    Measures aspect ratios, edge counts, non-manifold boundaries, and degenerate faces.
    """
    tris = indices.reshape(-1, 3) if indices.ndim == 1 else indices
    num_verts = len(positions)
    num_tris = len(tris)

    if num_tris == 0:
        return {"vertex_count": num_verts, "face_count": 0, "degenerate_faces": 0, "is_manifold": True}

    v0 = positions[tris[:, 0]]
    v1 = positions[tris[:, 1]]
    v2 = positions[tris[:, 2]]

    e0 = np.linalg.norm(v1 - v0, axis=1)
    e1 = np.linalg.norm(v2 - v1, axis=1)
    e2 = np.linalg.norm(v0 - v2, axis=1)

    semi = (e0 + e1 + e2) / 2.0
    areas = np.sqrt(np.maximum(semi * (semi - e0) * (semi - e1) * (semi - e2), 0.0))
    degen_count = int(np.sum(areas < 1e-8))

    max_edges = np.maximum(np.maximum(e0, e1), e2)
    inradii = 2.0 * areas / np.maximum(e0 + e1 + e2, 1e-8)
    aspect_ratios = max_edges / (np.sqrt(3.0) * np.maximum(inradii, 1e-8) + 1e-8)

    # Edge analysis
    sorted_edges = np.sort(np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    _, counts = np.unique(sorted_edges, axis=0, return_counts=True)
    boundary_edges = int(np.sum(counts == 1))
    non_manifold_edges = int(np.sum(counts > 2))

    return {
        "vertex_count": num_verts,
        "face_count": num_tris,
        "degenerate_faces": degen_count,
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "is_manifold": (non_manifold_edges == 0),
        "mean_aspect_ratio": round(float(np.mean(aspect_ratios)), 2),
        "p95_aspect_ratio": round(float(np.percentile(aspect_ratios, 95)), 2)
    }


def add_quad(tris: List[List[int]], v0: int, v1: int, v2: int, v3: int) -> None:
    """Appends two counter-clockwise triangles for a quadrilateral."""
    tris.append([v0, v1, v2])
    tris.append([v0, v2, v3])


def add_quad_strip(
    tris: List[List[int]],
    ring_curr: int,
    ring_next: int,
    segments: int,
    closed: bool = True
) -> None:
    """Stitches two vertex rings of equal segment count into triangle strips."""
    count = segments if closed else (segments - 1)
    for i in range(count):
        i_next = (i + 1) % segments
        v0 = ring_curr + i
        v1 = ring_curr + i_next
        v2 = ring_next + i_next
        v3 = ring_next + i
        add_quad(tris, v0, v1, v2, v3)


def _project_arm_distance(px: float, py: float, pz: float, shoulder_idx: int, arm_dir: np.ndarray) -> float:
    """Projects a point along a canonical arm bone direction relative to its shoulder joint origin."""
    sh_pos = ARA_SKELETON_SPECS[shoulder_idx][3]
    return float(
        (px - sh_pos[0]) * arm_dir[0]
        + (py - sh_pos[1]) * arm_dir[1]
        + (pz - sh_pos[2]) * arm_dir[2]
    )


def compute_torso_skinning(
    positions: np.ndarray,
    hem_y: float = 0.90,
    top_y: float = 1.42,
    has_hood: bool = False,
    is_kurta: bool = False,
    component_labels: Optional[List[str]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Ara 3D 20-bone skinning influences for upper body garments.
    When `component_labels` is provided, sleeve, hood, and torso/waistband
    assignments are resolved from authoritative mesh topology rather than
    fixed X-coordinate cutoffs, preventing wide hems or dropped shoulders from
    binding to hand/arm bones and eliminating discontinuous elbow blends.

    Bones:
      0: Hips, 1: Spine, 2: Spine1, 3: Spine2, 4: Neck, 5: Head,
      6: LeftShoulder, 7: LeftArm, 8: LeftForeArm, 9: LeftHand,
      10: RightShoulder, 11: RightArm, 12: RightForeArm, 13: RightHand
    """
    num_verts = len(positions)
    joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
    joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

    p_l_arm = np.array(ARA_SKELETON_SPECS[7][3], dtype=np.float32)
    p_l_elb = np.array(ARA_SKELETON_SPECS[8][3], dtype=np.float32)
    p_l_wri = np.array(ARA_SKELETON_SPECS[9][3], dtype=np.float32)
    elb_dist_l = float(np.dot(p_l_elb - p_l_arm, CANONICAL_ARM_DIR_LEFT))
    wri_dist_l = float(np.dot(p_l_wri - p_l_arm, CANONICAL_ARM_DIR_LEFT))

    p_r_arm = np.array(ARA_SKELETON_SPECS[11][3], dtype=np.float32)
    p_r_elb = np.array(ARA_SKELETON_SPECS[12][3], dtype=np.float32)
    p_r_wri = np.array(ARA_SKELETON_SPECS[13][3], dtype=np.float32)
    elb_dist_r = float(np.dot(p_r_elb - p_r_arm, CANONICAL_ARM_DIR_RIGHT))
    wri_dist_r = float(np.dot(p_r_wri - p_r_arm, CANONICAL_ARM_DIR_RIGHT))

    def _assign_sleeve_weights(idx: int, px: float, py: float, pz: float, is_left: bool) -> None:
        if is_left:
            arm_dir = CANONICAL_ARM_DIR_LEFT
            d_along = _project_arm_distance(px, py, pz, 7, arm_dir)
            elb_d, wri_d = elb_dist_l, wri_dist_l
            b_sh, b_arm, b_elb, b_hnd = 6, 7, 8, 9
        else:
            arm_dir = CANONICAL_ARM_DIR_RIGHT
            d_along = _project_arm_distance(px, py, pz, 11, arm_dir)
            elb_d, wri_d = elb_dist_r, wri_dist_r
            b_sh, b_arm, b_elb, b_hnd = 10, 11, 12, 13

        # Smooth shoulder-to-upper-arm rolloff over first 12cm along arm axis
        w_sh = max(0.0, 1.0 - max(0.0, d_along) / 0.12) * 0.40
        # Elbow blend centered around elbow joint (elb_d) with smooth Hermite transition
        # ensuring inner-wall Jacobian positivity under extreme flexion up to 120 deg
        t_raw = np.clip((d_along - (elb_d - 0.14)) / 0.28, 0.0, 1.0)
        t_elb = float(t_raw * t_raw * (3.0 - 2.0 * t_raw))
        t_wri = float(np.clip((d_along - (wri_d - 0.02)) / 0.16, 0.0, 1.0)) * 0.55
        w_arm_total = 1.0 - w_sh
        joint_indices[idx] = [b_arm, b_elb, b_sh, b_hnd]
        joint_weights[idx] = [
            w_arm_total * (1.0 - t_elb),
            w_arm_total * t_elb * (1.0 - t_wri),
            w_sh,
            w_arm_total * t_elb * t_wri
        ]

    has_labels = component_labels is not None and len(component_labels) == num_verts

    for i in range(num_verts):
        px, py, pz = float(positions[i, 0]), float(positions[i, 1]), float(positions[i, 2])
        lbl = component_labels[i] if has_labels else None

        if lbl is not None:
            is_left_sleeve = lbl in ("left_sleeve", "left_cuff")
            is_right_sleeve = lbl in ("right_sleeve", "right_cuff")
            is_hood_vert = lbl == "hood"
        else:
            # Diagonal torso-to-arm spatial fallback for legacy callers without component_labels
            arm_x_thresh = 0.195 + max(0.0, 1.35 - py) * 0.50
            is_left_sleeve = (px > arm_x_thresh and py < 1.45)
            is_right_sleeve = (px < -arm_x_thresh and py < 1.45)
            is_hood_vert = (py > 1.42 and has_hood)

        # 1. Left Sleeve (+X)
        if is_left_sleeve:
            _assign_sleeve_weights(i, px, py, pz, is_left=True)

        # 2. Right Sleeve (-X)
        elif is_right_sleeve:
            _assign_sleeve_weights(i, px, py, pz, is_left=False)

        # 3. Hood
        elif is_hood_vert:
            hood_t = float(np.clip((py - 1.42) / 0.26, 0.0, 1.0))
            joint_indices[i] = [4, 5, 3, 0]
            joint_weights[i] = [1.0 - hood_t * 0.75, hood_t * 0.75, 0.0, 0.0]

        # 4. Long Tunic / Kurta Lower Panels (py < 0.82)
        elif is_kurta and py < 0.82:
            kurta_t = float(np.clip((0.82 - py) / 0.32, 0.0, 1.0)) * 0.25
            side_w = float(np.clip((px + 0.06) / 0.12, 0.0, 1.0))
            joint_indices[i] = [0, 1, 14, 17]
            joint_weights[i] = [1.0 - kurta_t, 0.0, kurta_t * side_w, kurta_t * (1.0 - side_w)]

        # 5. Torso Body (including ribbed_waistband, pockets, plackets, collars)
        else:
            torso_span = max(0.20, top_y - hem_y)
            torso_t = float(np.clip((py - hem_y) / torso_span, 0.0, 1.0))
            if torso_t < 0.25:
                s = torso_t / 0.25
                joint_indices[i] = [0, 1, 2, 0]
                joint_weights[i] = [1.0 - s * 0.65, s * 0.65, 0.0, 0.0]
            elif torso_t < 0.60:
                s = (torso_t - 0.25) / 0.35
                joint_indices[i] = [1, 2, 3, 0]
                joint_weights[i] = [(1.0 - s) * 0.6, 0.4, s * 0.6, 0.0]
            elif torso_t < 0.88:
                s = (torso_t - 0.60) / 0.28
                joint_indices[i] = [3, 4, 2, 0]
                joint_weights[i] = [1.0 - s * 0.40, s * 0.40, 0.0, 0.0]
            else:
                s = (torso_t - 0.88) / 0.12
                joint_indices[i] = [3, 4, 6 if px >= 0 else 10, 0]
                joint_weights[i] = [(1.0 - s) * 0.35, 0.55 + s * 0.35, 0.10, 0.0]

        # Normalize weights strictly to 1.0
        w_sum = float(np.sum(joint_weights[i]))
        if w_sum > 1e-6:
            joint_weights[i] /= w_sum
        else:
            joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

    return joint_indices, joint_weights


def assign_vertex_labels(
    num_verts: int,
    spans: List[Tuple[str, int, int]],
    default: str = "torso"
) -> List[str]:
    """Builds per-vertex semantic skinning labels from (label, start_idx, count) spans."""
    labels = [default] * num_verts
    for label, start, count in spans:
        end = min(num_verts, start + count)
        for idx in range(max(0, start), end):
            labels[idx] = label
    return labels


def compute_bottoms_skinning(
    positions: np.ndarray,
    crotch_y: float = 0.84,
    waist_y: float = 1.02,
    is_shorts: bool = False,
    component_labels: Optional[List[str]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Ara 3D 20-bone skinning influences for lower body garments.
    When `component_labels` is provided (`waistband`, `left_leg`, `right_leg`),
    wide-leg inner vertices crossing X=0 stay bound to their owning leg tube.

    Bones:
      0: Hips, 1: Spine,
      14: LeftUpLeg, 15: LeftLeg, 16: LeftFoot,
      17: RightUpLeg, 18: RightLeg, 19: RightFoot
    """
    num_verts = len(positions)
    joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
    joint_weights = np.zeros((num_verts, 4), dtype=np.float32)
    has_labels = component_labels is not None and len(component_labels) == num_verts

    for i in range(num_verts):
        px, py, pz = float(positions[i, 0]), float(positions[i, 1]), float(positions[i, 2])
        lbl = component_labels[i] if has_labels else None

        if lbl in ("left_leg", "left_cuff"):
            is_left = True
        elif lbl in ("right_leg", "right_cuff"):
            is_left = False
        else:
            is_left = (px >= 0.0)

        b_hip_leg = 14 if is_left else 17
        b_knee = 15 if is_left else 18
        b_foot = 16 if is_left else 19

        # Waistband / Upper Pelvis
        waist_floor = 0.90
        if (lbl in ("waistband", "waistband_and_pelvis") and py >= crotch_y + 0.02) or (lbl is None and py >= waist_floor):
            t = float(np.clip((py - waist_floor) / max(0.05, waist_y - waist_floor), 0.0, 1.0))
            joint_indices[i] = [0, 1, b_hip_leg, 0]
            joint_weights[i] = [0.85 - t * 0.35, 0.15 + t * 0.35, 0.0, 0.0]
            w_sum = float(np.sum(joint_weights[i]))
            joint_weights[i] /= (w_sum if w_sum > 1e-6 else 1.0)
            continue

        if is_shorts:
            # Shorts terminate above the knee (y >= 0.50m); blend Hips -> UpLeg smoothly
            t_pelvis = float(np.clip((py - 0.50) / max(0.10, waist_floor - 0.50), 0.0, 1.0))
            w_hips = t_pelvis * 0.45
            w_up = 1.0 - w_hips
            joint_indices[i] = [0, b_hip_leg, 1, 0]
            joint_weights[i] = [w_hips, w_up, 0.0, 0.0]
        else:
            # Trousers: Pelvis rolloff into UpLeg, smooth Hermite knee transition, and ankle taper
            t_pelvis = float(np.clip((py - 0.70) / max(0.10, waist_floor - 0.70), 0.0, 1.0))
            w_hips = t_pelvis * 0.45
            t_k = float(np.clip((0.45 + 0.22 - py) / 0.44, 0.0, 1.0))
            w_foot = float(np.clip((0.20 - py) / 0.15, 0.0, 1.0)) * 0.40
            w_up = max(0.0, 1.0 - t_k)
            w_kn = t_k * (1.0 - w_foot)
            w_leg_tot = 1.0 - w_hips
            joint_indices[i] = [0, b_hip_leg, b_knee, b_foot]
            joint_weights[i] = [w_hips, w_leg_tot * w_up, w_leg_tot * w_kn, w_leg_tot * w_foot]

        w_sum = float(np.sum(joint_weights[i]))
        if w_sum > 1e-6:
            joint_weights[i] /= w_sum
        else:
            joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

    return joint_indices, joint_weights


def compute_footwear_skinning(positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Ara 3D 20-bone skinning influences for footwear.
    Bones:
      15: LeftLeg, 16: LeftFoot,
      18: RightLeg, 19: RightFoot
    """
    num_verts = len(positions)
    joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
    joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

    for i in range(num_verts):
        px, py, pz = positions[i]
        if px >= 0:
            # Left Foot
            ankle_t = float(np.clip(py / 0.12, 0.0, 1.0))
            joint_indices[i] = [16, 15, 14, 0]
            joint_weights[i] = [1.0 - ankle_t * 0.25, ankle_t * 0.25, 0.0, 0.0]
        else:
            # Right Foot
            ankle_t = float(np.clip(py / 0.12, 0.0, 1.0))
            joint_indices[i] = [19, 18, 17, 0]
            joint_weights[i] = [1.0 - ankle_t * 0.25, ankle_t * 0.25, 0.0, 0.0]

        w_sum = float(np.sum(joint_weights[i]))
        if w_sum > 1e-6:
            joint_weights[i] /= w_sum
        else:
            joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

    return joint_indices, joint_weights


def compute_headwear_skinning(positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Ara 3D 20-bone skinning influences for headwear/accessories.
    Bones:
      4: Neck, 5: Head, 3: Spine2
    """
    num_verts = len(positions)
    joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
    joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

    for i in range(num_verts):
        px, py, pz = positions[i]
        neck_t = float(np.clip((1.42 - py) / 0.15, 0.0, 1.0))
        joint_indices[i] = [5, 4, 3, 0]
        joint_weights[i] = [1.0 - neck_t * 0.20, neck_t * 0.20, 0.0, 0.0]

        w_sum = float(np.sum(joint_weights[i]))
        if w_sum > 1e-6:
            joint_weights[i] /= w_sum
        else:
            joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

    return joint_indices, joint_weights


def identify_observed_surface(positions: np.ndarray, has_back_view: bool = False) -> np.ndarray:
    """
    Distinguishes observed surface geometry (directly visible in front photo,
    or back photo if present) from inferred/posterior surfaces.
    Returns boolean mask of length num_verts.
    """
    if has_back_view:
        # Both front and back are observed; only internal cavities or deep crotch seams are inferred
        return (positions[:, 1] > 0.05).astype(bool)
    else:
        # Single front view: Z >= -0.01 is observed; posterior geometry (Z < -0.01) is inferred
        return (positions[:, 2] >= -0.01).astype(bool)


def extract_silhouette_profile(
    image: Any,
    num_samples: int = 24
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Extracts normalized silhouette width scale factors and horizontal center offsets
    from a segmented garment image across `num_samples` vertical elevations from top to bottom.
    
    Returns:
        (scale_factors, center_offsets) as np.ndarray of shape (num_samples,),
        or (None, None) if image is invalid, None, or empty.
    """
    if image is None:
        return None, None
        
    try:
        from PIL import Image
        if isinstance(image, Image.Image):
            if image.mode == "RGBA":
                alpha = np.array(image.split()[-1])
                mask = alpha > 25
            else:
                gray = np.array(image.convert("L"))
                bg_is_white = float(np.mean(gray[:5, :5])) > 200.0
                mask = (gray < 235) if bg_is_white else (gray > 20)
        elif isinstance(image, np.ndarray):
            if image.ndim == 3 and image.shape[2] == 4:
                mask = image[:, :, 3] > 25
            elif image.ndim == 3:
                gray = np.mean(image[:, :, :3], axis=2)
                bg_is_white = float(np.mean(gray[:5, :5])) > 200.0
                mask = (gray < 235) if bg_is_white else (gray > 20)
            elif image.ndim == 2:
                mask = image > 25
            else:
                return None, None
        else:
            return None, None

        if not np.any(mask) or int(np.sum(mask)) < 150:
            return None, None

        ys, xs = np.where(mask)
        y_min, y_max = int(np.min(ys)), int(np.max(ys))
        x_min, x_max = int(np.min(xs)), int(np.max(xs))
        h_px = y_max - y_min + 1
        w_px = x_max - x_min + 1

        if h_px < 20 or w_px < 20:
            return None, None

        widths = np.zeros(num_samples, dtype=np.float32)
        centers = np.zeros(num_samples, dtype=np.float32)
        band = max(1, int(h_px / (num_samples * 2.5)))

        for i in range(num_samples):
            t = i / max(1, num_samples - 1)
            y_i = int(y_min + t * (y_max - y_min))
            row_slice = mask[max(0, y_i - band):min(mask.shape[0], y_i + band + 1), :]
            active = np.any(row_slice, axis=0)
            if np.any(active):
                act_indices = np.where(active)[0]
                widths[i] = float(np.max(act_indices) - np.min(act_indices))
                centers[i] = float((np.max(act_indices) + np.min(act_indices)) / 2.0)
            else:
                widths[i] = 0.0
                centers[i] = float((x_min + x_max) / 2.0)

        # 2-pass smoothing filter & step-delta clamp for manifold triangle ring transitions
        smoothed_w = widths.copy()
        smoothed_c = centers.copy()
        for _pass in range(2):
            prev_w = smoothed_w.copy()
            prev_c = smoothed_c.copy()
            for i in range(1, num_samples - 1):
                if prev_w[i-1] > 0 and prev_w[i] > 0 and prev_w[i+1] > 0:
                    smoothed_w[i] = 0.25 * prev_w[i-1] + 0.50 * prev_w[i] + 0.25 * prev_w[i+1]
                    smoothed_c[i] = 0.25 * prev_c[i-1] + 0.50 * prev_c[i] + 0.25 * prev_c[i+1]

        valid_w = smoothed_w[smoothed_w > 0]
        if len(valid_w) == 0:
            return None, None

        ref_w = float(np.median(valid_w))
        if ref_w <= 1.0:
            return None, None

        scales = np.clip(smoothed_w / ref_w, 0.85, 1.25)
        # For rows with zero width, fallback to 1.0
        scales[smoothed_w <= 0] = 1.0
        # Limit adjacent ring jump to prevent sudden radius inversions
        for i in range(1, num_samples):
            scales[i] = float(np.clip(scales[i], scales[i - 1] - 0.08, scales[i - 1] + 0.08))

        mid_x = (x_min + x_max) / 2.0
        offsets = np.clip((smoothed_c - mid_x) / float(w_px) * 0.06, -0.035, 0.035)

        return scales.astype(np.float32), offsets.astype(np.float32)

    except Exception:
        return None, None

