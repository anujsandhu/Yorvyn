"""
Stage B: 3D Garment Geometry Builder
Generates separate wearable 3D meshes (tops, bottoms, outerwear) with realistic openings,
canonical UV unwrapping, and Ara 3D Gen anatomic skeleton compatibility.
"""

from typing import Tuple, List, Dict, Any, Optional
import numpy as np
import math


# Ara 3D Gen Canonical Humanoid Skeleton Definition (20 Bones)
# Format: (bone_name, parent_index, local_translation [x, y, z], world_position [x, y, z])
# Canonical scale: Ara 3D Gen meters (Y-up, Z-front, +X = character's left, -X = character's right)
ARA_SKELETON_SPECS = [
    ("Hips", None, [0.0, 0.815, 0.0], [0.0, 0.815, 0.0]),
    ("Spine", 0, [0.0, 0.050, 0.0], [0.0, 0.865, 0.0]),
    ("Spine1", 1, [0.0, 0.050, 0.0], [0.0, 0.915, 0.0]),
    ("Spine2", 2, [0.0, 0.125, 0.0], [0.0, 1.040, 0.0]),
    ("Neck", 3, [0.0, 0.240, 0.0], [0.0, 1.280, 0.0]),
    ("Head", 4, [0.0, 0.086, 0.0], [0.0, 1.366, 0.0]),
    ("LeftShoulder", 3, [0.050, 0.200, 0.0], [0.050, 1.240, 0.0]),
    ("LeftArm", 6, [0.160, 0.160, 0.0], [0.210, 1.400, 0.0]),
    ("LeftForeArm", 7, [0.120, -0.150, 0.0], [0.330, 1.250, 0.0]),
    ("LeftHand", 8, [0.090, -0.120, 0.05], [0.420, 1.130, 0.05]),
    ("RightShoulder", 3, [-0.050, 0.200, 0.0], [-0.050, 1.240, 0.0]),
    ("RightArm", 10, [-0.160, 0.160, 0.0], [-0.210, 1.400, 0.0]),
    ("RightForeArm", 11, [-0.120, -0.150, 0.0], [-0.330, 1.250, 0.0]),
    ("RightHand", 12, [-0.090, -0.120, 0.05], [-0.420, 1.130, 0.05]),
    ("LeftUpLeg", 0, [0.098, -0.050, 0.0], [0.098, 0.765, 0.0]),
    ("LeftLeg", 14, [0.0, -0.380, 0.0], [0.098, 0.385, 0.0]),
    ("LeftFoot", 15, [0.0, -0.360, 0.05], [0.098, 0.025, 0.05]),
    ("RightUpLeg", 0, [-0.098, -0.050, 0.0], [-0.098, 0.765, 0.0]),
    ("RightLeg", 17, [0.0, -0.380, 0.0], [-0.098, 0.385, 0.0]),
    ("RightFoot", 18, [0.0, -0.360, 0.05], [-0.098, 0.025, 0.05]),
]

# Canonical Resting A-Pose Arm Directions
# Angled downwards (~32.6° from -Y) and slightly forward (+Z)
CANONICAL_ARM_DIR_LEFT = np.array([0.52, -0.84, 0.14], dtype=np.float32)
CANONICAL_ARM_DIR_LEFT = CANONICAL_ARM_DIR_LEFT / np.linalg.norm(CANONICAL_ARM_DIR_LEFT)

CANONICAL_ARM_DIR_RIGHT = np.array([-0.52, -0.84, 0.14], dtype=np.float32)
CANONICAL_ARM_DIR_RIGHT = CANONICAL_ARM_DIR_RIGHT / np.linalg.norm(CANONICAL_ARM_DIR_RIGHT)

CANONICAL_SHOULDER_ORIGIN_LEFT = np.array([0.175, 1.38, 0.01], dtype=np.float32)
CANONICAL_SHOULDER_ORIGIN_RIGHT = np.array([-0.175, 1.38, 0.01], dtype=np.float32)


class GarmentMesh:
    """Represents a separate wearable 3D garment geometry."""
    def __init__(
        self,
        positions: np.ndarray,             # (N, 3) float32
        normals: np.ndarray,               # (N, 3) float32
        uvs: np.ndarray,                   # (N, 2) float32
        indices: np.ndarray,               # (M, 3) uint32
        joint_indices: Optional[np.ndarray] = None,  # (N, 4) uint16
        joint_weights: Optional[np.ndarray] = None   # (N, 4) float32
    ):
        self.positions = positions.astype(np.float32)
        self.normals = normals.astype(np.float32)
        self.uvs = uvs.astype(np.float32)
        self.indices = indices.astype(np.uint32)
        self.joint_indices = joint_indices.astype(np.uint16) if joint_indices is not None else None
        self.joint_weights = joint_weights.astype(np.float32) if joint_weights is not None else None


class GarmentMeshBuilder:
    """Constructs category-specific 3D garment meshes with proper openings and anatomic alignment."""

    def __init__(self):
        self.latest_reconstruction_output: Optional[Any] = None

    def build_mesh(
        self,
        category: str,
        subcategory: str = "tshirt",
        sleeve_length: str = "short",
        neckline_type: str = "crewneck",
        fit: str = "regular",
        intelligence: Optional[Any] = None,
        front_image: Optional[Any] = None,
        back_image: Optional[Any] = None,
        local_strategy: Optional[str] = None
    ) -> GarmentMesh:
        """
        Dispatches to modular category-specific 3D reconstruction engines via ReconstructionEngineRegistry.
        Returns rigged GarmentMesh with 20-bone Ara 3D skinning.
        """
        try:
            from .reconstruction import reconstruction_registry
            prefer_neural = bool(intelligence and getattr(intelligence, "model_provenance", {}).get("neural_intelligence_model"))
            if local_strategy:
                prefer_neural = local_strategy == "image_conditioned"
            engine = reconstruction_registry.get_engine(category, subcategory, prefer_neural=prefer_neural)
            policy = {"allow_remote": False} if local_strategy and prefer_neural else {}
            output = engine.reconstruct(
                intelligence=intelligence,
                category=category,
                subcategory=subcategory,
                sleeve_length=sleeve_length,
                neckline_type=neckline_type,
                fit=fit,
                front_image=front_image,
                back_image=back_image, **policy
            )
            self.latest_reconstruction_output = output
            return output.mesh
        except Exception as e:
            # Fallback to legacy procedural geometry if registry fails
            cat = category.lower()
            if cat in ["bottom", "bottoms", "trousers", "pants", "shorts", "jeans"]:
                return self._build_bottoms(subcategory, fit, intelligence)
            elif cat in ["dress", "skirt", "dresses_and_skirts"]:
                return self._build_dresses(subcategory, fit, neckline_type, intelligence)
            else:
                return self._build_tops(subcategory, sleeve_length, neckline_type, fit, intelligence)

    def _build_tops(
        self,
        subcategory: str,
        sleeve_length: str,
        neckline_type: str,
        fit: str,
        intelligence: Optional[Any] = None
    ) -> GarmentMesh:
        """
        Builds a separate wearable top garment (T-shirt, Long-sleeve shirt, Hoodie, Tank top).
        Dimensions match Ara 3D Gen canonical meter scale (Y-up, Z-front).
        """
        margin = 0.018 if fit == "slim" else (0.035 if fit == "oversized" else 0.024)
        
        # Dynamic anatomical landmarks and component adaptation
        top_y = 1.42
        hem_y = 0.90
        has_hood = subcategory in ["hoodie", "zip_hoodie"]
        has_pocket = False

        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.42 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.38, 1.45))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.90 + (0.95 - lm["hem_center"].position.y) * 0.15, 0.82, 0.98))

        if intelligence and hasattr(intelligence, "components") and intelligence.components:
            hood_c = next((c for c in intelligence.components if c.component_type == "hood"), None)
            if hood_c:
                has_hood = hood_c.status == "detected"
            pocket_c = next((c for c in intelligence.components if c.component_type == "kangaroo_pocket"), None)
            if pocket_c:
                has_pocket = pocket_c.status == "detected"
        elif subcategory in ["hoodie", "zip_hoodie"]:
            has_pocket = True

        # Anatomic Torso Rings (collarbone down to hips)
        torso_rings_spec = [
            (top_y, 0.170 + margin, 0.110 + margin),        # 0: Upper chest / clavicle
            (top_y - 0.08, 0.185 + margin, 0.125 + margin), # 1: Mid-chest / bust line
            (top_y - 0.18, 0.175 + margin, 0.118 + margin), # 2: Lower ribs
            (top_y - 0.28, 0.165 + margin, 0.112 + margin), # 3: Natural waist
            (top_y - 0.40, 0.180 + margin, 0.122 + margin), # 4: Upper hip
            (hem_y, 0.192 + margin, 0.130 + margin),        # 5: Lower hemline (open)
        ]
        
        n_seg = 28
        verts = []
        norms = []
        uv_coords = []
        tris = []
        
        # 1. Generate Torso Cylindrical Body
        ring_start_indices = []
        for ring_idx, (y, rx, rz) in enumerate(torso_rings_spec):
            ring_start_indices.append(len(verts))
            v_coord = ring_idx / (len(torso_rings_spec) - 1)
            
            for i in range(n_seg):
                theta = 2.0 * math.pi * i / n_seg
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)
                
                y_mod = y
                if ring_idx == 0:
                    if sin_t > 0:
                        neck_dip = 0.045 if neckline_type == "v_neck" else 0.025
                        y_mod -= neck_dip * (sin_t ** 2)
                        
                px = rx * cos_t
                pz = rz * sin_t
                py = y_mod
                
                nx = cos_t
                nz = sin_t
                ny = 0.1 if ring_idx == len(torso_rings_spec) - 1 else 0.0
                norm_len = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
                
                verts.append([px, py, pz])
                norms.append([nx / norm_len, ny / norm_len, nz / norm_len])
                
                if pz >= 0:
                    theta_front = theta if theta <= math.pi else (2.0 * math.pi - theta)
                    u_coord = 0.04 + (0.42 * (theta_front / math.pi))
                else:
                    theta_back = (theta - math.pi) if theta >= math.pi else (math.pi - theta)
                    u_coord = 0.54 + (0.42 * (theta_back / math.pi))
                v_coord_norm = 0.48 + v_coord * 0.48
                uv_coords.append([u_coord, v_coord_norm])
                
        # Connect Torso Quad Strips
        for r in range(len(torso_rings_spec) - 1):
            curr_start = ring_start_indices[r]
            next_start = ring_start_indices[r + 1]
            for i in range(n_seg):
                i_next = (i + 1) % n_seg
                v0 = curr_start + i
                v1 = curr_start + i_next
                v2 = next_start + i_next
                v3 = next_start + i
                tris.extend([[v0, v1, v2], [v0, v2, v3]])
                
        # 2. Generate Sleeves
        is_long = sleeve_length == "long" or subcategory in ["long_sleeve", "hoodie", "jacket"]
        is_sleeveless = sleeve_length == "sleeveless" or subcategory == "tank_top"
        
        if not is_sleeveless:
            arm_reach = 0.48 if is_long else 0.18
            n_arm_rings = 7 if is_long else 3
            arm_r_shoulder = 0.065 + margin * 0.7
            arm_r_cuff = 0.045 + margin * 0.6 if is_long else 0.058 + margin * 0.7
            
            # Canonical Left Arm (+X, side = 1.0) and Right Arm (-X, side = -1.0)
            arm_configs = [
                (1.0, CANONICAL_SHOULDER_ORIGIN_LEFT, CANONICAL_ARM_DIR_LEFT),
                (-1.0, CANONICAL_SHOULDER_ORIGIN_RIGHT, CANONICAL_ARM_DIR_RIGHT)
            ]
            
            for side, shoulder_origin, arm_dir in arm_configs:
                up_hint = np.array([0.0, 0.0, 1.0])
                arm_right = np.cross(arm_dir, up_hint)
                arm_right = arm_right / (np.linalg.norm(arm_right) or 1.0)
                arm_up = np.cross(arm_right, arm_dir)
                
                arm_start_idx = len(verts)
                arm_seg = 18
                
                for r in range(n_arm_rings):
                    frac = r / (n_arm_rings - 1)
                    center = shoulder_origin + arm_dir * (frac * arm_reach)
                    radius = arm_r_shoulder + (arm_r_cuff - arm_r_shoulder) * frac
                    
                    for i in range(arm_seg):
                        phi = 2.0 * math.pi * i / arm_seg
                        p = center + (arm_right * math.cos(phi) + arm_up * math.sin(phi)) * radius
                        n = (arm_right * math.cos(phi) + arm_up * math.sin(phi))
                        
                        verts.append(p.tolist())
                        norms.append(n.tolist())
                        
                        u_arm = (0.04 if side > 0 else 0.54) + 0.42 * (i / arm_seg)
                        v_arm = 0.24 + 0.20 * frac
                        uv_coords.append([u_arm, v_arm])
                        
                for r in range(n_arm_rings - 1):
                    r_curr = arm_start_idx + r * arm_seg
                    r_next = arm_start_idx + (r + 1) * arm_seg
                    for i in range(arm_seg):
                        i_next = (i + 1) % arm_seg
                        v0 = r_curr + i
                        v1 = r_curr + i_next
                        v2 = r_next + i_next
                        v3 = r_next + i
                        tris.extend([[v0, v1, v2], [v0, v2, v3]])

        # 3. Generate 3D Volumetric Hood (if detected or requested)
        if has_hood:
            hood_rings = 10
            hood_slices = 16
            hood_start_idx = len(verts)
            for r in range(hood_rings):
                frac_y = r / (hood_rings - 1)
                y_pos = 1.42 + frac_y * 0.26
                rad_x = 0.115 + 0.045 * math.sin(frac_y * math.pi)
                rad_z = 0.120 + 0.040 * math.sin(frac_y * math.pi)
                for s in range(hood_slices + 1):
                    u_val = s / hood_slices
                    phi = -0.35 * math.pi + u_val * (1.70 * math.pi)
                    px = rad_x * math.sin(phi)
                    pz = -0.02 - rad_z * math.cos(phi)
                    py = y_pos
                    norm_len = math.hypot(px, pz) or 1.0
                    verts.append([px, py, pz])
                    norms.append([px / norm_len, 0.2, pz / norm_len])
                    uv_coords.append([0.5 + u_val * 0.45, 0.05 + frac_y * 0.20])
            for r in range(hood_rings - 1):
                stride = hood_slices + 1
                for s in range(hood_slices):
                    i0 = hood_start_idx + r * stride + s
                    i1 = i0 + 1
                    i2 = hood_start_idx + (r + 1) * stride + s
                    i3 = i2 + 1
                    tris.extend([[i0, i2, i1], [i1, i2, i3]])

        # 4. Generate Kangaroo Pocket (Front Pouch if detected or requested)
        if has_pocket:
            pocket_rings = 5
            pocket_slices = 10
            p_start_idx = len(verts)
            p_ymin, p_ymax = 0.98, 1.15
            for r in range(pocket_rings):
                p_y = p_ymin + (r / (pocket_rings - 1)) * (p_ymax - p_ymin)
                t_val = r / (pocket_rings - 1)
                half_w = 0.13 * (1.0 - t_val * 0.18)
                elevated_z = 0.138 + margin
                for s in range(pocket_slices + 1):
                    u_p = s / pocket_slices
                    px = -half_w + u_p * (2 * half_w)
                    pz = elevated_z + 0.006 * math.sin(u_p * math.pi)
                    verts.append([px, p_y, pz])
                    norms.append([0.0, 0.1, 0.99])
                    uv_coords.append([0.15 + u_p * 0.20, 0.25 + t_val * 0.18])
            for r in range(pocket_rings - 1):
                p_stride = pocket_slices + 1
                for s in range(pocket_slices):
                    i0 = p_start_idx + r * p_stride + s
                    i1 = i0 + 1
                    i2 = p_start_idx + (r + 1) * p_stride + s
                    i3 = i2 + 1
                    tris.extend([[i0, i2, i1], [i1, i2, i3]])

        # Convert to numpy arrays
        pos_np = np.array(verts, dtype=np.float32)
        norm_np = np.array(norms, dtype=np.float32)
        uv_np = np.array(uv_coords, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)

        # Compute skinning weights (Ara 3D Gen 20-bone humanoid skeleton)
        joint_indices, joint_weights = self._compute_joint_weights_tops(pos_np, subcategory, has_hood)
        
        return GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

    def _build_bottoms(self, subcategory: str, fit: str, intelligence: Optional[Any] = None) -> GarmentMesh:
        """
        Builds separate wearable trousers, jeans, or shorts with dual leg tubes and open waist/cuffs.
        Uses dynamic anatomical landmarks when available.
        """
        margin = 0.022 if fit == "slim" else (0.040 if fit == "relaxed" else 0.028)
        is_shorts = subcategory in ["shorts", "sports_shorts"]
        
        crotch_y = 0.84
        leg_bottom_y = 0.52 if is_shorts else 0.08

        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "crotch_apex" in lm:
                crotch_y = float(np.clip(0.84 + (0.40 - lm["crotch_apex"].position.y) * 0.10, 0.78, 0.88))
            if "ankle_left" in lm and not is_shorts:
                leg_bottom_y = float(np.clip(0.08 + (0.95 - lm["ankle_left"].position.y) * 0.10, 0.04, 0.20))

        verts = []
        norms = []
        uv_coords = []
        tris = []
        n_seg = 28
        
        # 1. Waistband and Pelvis section
        pelvis_rings = [
            (1.02, 0.178 + margin, 0.124 + margin), # Waist opening
            (0.94, 0.188 + margin, 0.134 + margin), # Mid-pelvis
            (crotch_y, 0.194 + margin, 0.140 + margin), # Low hips / crotch apex
        ]
        
        p_ring_starts = []
        for r_idx, (y, rx, rz) in enumerate(pelvis_rings):
            p_ring_starts.append(len(verts))
            v_val = 0.95 - (r_idx * 0.15)
            for i in range(n_seg):
                th = 2.0 * math.pi * i / n_seg
                px = rx * math.cos(th)
                pz = rz * math.sin(th)
                verts.append([px, y, pz])
                norms.append([math.cos(th), 0.0, math.sin(th)])
                uv_coords.append([(math.atan2(pz, px) / (2.0 * math.pi)) + 0.5, v_val])
                
        # Connect pelvis rings
        for r in range(len(pelvis_rings) - 1):
            r_curr = p_ring_starts[r]
            r_next = p_ring_starts[r + 1]
            for i in range(n_seg):
                i_next = (i + 1) % n_seg
                tris.extend([[r_curr + i, r_curr + i_next, r_next + i_next],
                             [r_curr + i, r_next + i_next, r_next + i]])
                             
        # 2. Dual Leg Tubes
        leg_bottom_y = 0.52 if is_shorts else 0.08
        n_leg_rings = 4 if is_shorts else 9
        leg_seg = 18
        
        # Left Leg (+X, side = 1.0) and Right Leg (-X, side = -1.0)
        for side in [1.0, -1.0]:
            leg_center_x = side * 0.098
            r_top = 0.088 + margin
            r_bot = 0.072 + margin if is_shorts else 0.052 + margin
            
            leg_start = len(verts)
            for r in range(n_leg_rings):
                frac = r / (n_leg_rings - 1)
                y = 0.82 - frac * (0.82 - leg_bottom_y)
                r_now = r_top + frac * (r_bot - r_top)
                
                # Legs taper inwards slightly towards ankles
                cx = leg_center_x + side * (frac * 0.015)
                
                for i in range(leg_seg):
                    th = 2.0 * math.pi * i / leg_seg
                    px = cx + r_now * math.cos(th)
                    pz = r_now * math.sin(th)
                    
                    verts.append([px, y, pz])
                    norms.append([math.cos(th), 0.0, math.sin(th)])
                    
                    u_leg = (0.75 if side > 0 else 0.25) + 0.22 * math.cos(th)
                    v_leg = 0.50 - frac * 0.45
                    uv_coords.append([u_leg, v_leg])
                    
            for r in range(n_leg_rings - 1):
                r_curr = leg_start + r * leg_seg
                r_next = leg_start + (r + 1) * leg_seg
                for i in range(leg_seg):
                    i_next = (i + 1) % leg_seg
                    tris.extend([[r_curr + i, r_curr + i_next, r_next + i_next],
                                 [r_curr + i, r_next + i_next, r_next + i]])

        pos_np = np.array(verts, dtype=np.float32)
        norm_np = np.array(norms, dtype=np.float32)
        uv_np = np.array(uv_coords, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)

        # Compute skinning weights (Ara 3D Gen 20-bone humanoid skeleton)
        joint_indices, joint_weights = self._compute_joint_weights_bottoms(pos_np, subcategory)
        
        return GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

    def _compute_joint_weights_tops(
        self,
        positions: np.ndarray,
        subcategory: str,
        has_hood: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates 4 skinning influences and weights per vertex for upper body garments.
        Compatible with Ara 3D Gen 20-bone skeleton.
        Weights strictly sum to 1.0.
        """
        num_verts = len(positions)
        joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
        joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

        for i in range(num_verts):
            px, py, pz = positions[i]

            # 1. Left Sleeve (+X, x > 0.15, py < 1.45)
            if px > 0.15 and py < 1.45:
                arm_t = np.clip((1.40 - py) / 0.45, 0.0, 1.0)
                if arm_t < 0.25:
                    s = arm_t / 0.25
                    joint_indices[i] = [6, 7, 3, 0]
                    joint_weights[i] = [(1.0 - s) * 0.40, 0.50 + s * 0.10, (1.0 - s) * 0.10, 0.0]
                elif arm_t < 0.70:
                    s = (arm_t - 0.25) / 0.45
                    joint_indices[i] = [7, 8, 6, 0]
                    joint_weights[i] = [(1.0 - s) * 0.75, s * 0.75, (1.0 - s) * 0.25, 0.0]
                else:
                    s = (arm_t - 0.70) / 0.30
                    joint_indices[i] = [8, 9, 7, 0]
                    joint_weights[i] = [(1.0 - s) * 0.70, s * 0.70, (1.0 - s) * 0.10, 0.0]

            # 2. Right Sleeve (-X, px < -0.15, py < 1.45)
            elif px < -0.15 and py < 1.45:
                arm_t = np.clip((1.40 - py) / 0.45, 0.0, 1.0)
                if arm_t < 0.25:
                    s = arm_t / 0.25
                    joint_indices[i] = [10, 11, 3, 0]
                    joint_weights[i] = [(1.0 - s) * 0.40, 0.50 + s * 0.10, (1.0 - s) * 0.10, 0.0]
                elif arm_t < 0.70:
                    s = (arm_t - 0.25) / 0.45
                    joint_indices[i] = [11, 12, 10, 0]
                    joint_weights[i] = [(1.0 - s) * 0.75, s * 0.75, (1.0 - s) * 0.25, 0.0]
                else:
                    s = (arm_t - 0.70) / 0.30
                    joint_indices[i] = [12, 13, 11, 0]
                    joint_weights[i] = [(1.0 - s) * 0.70, s * 0.70, (1.0 - s) * 0.10, 0.0]

            # 3. Hood (y > 1.42, has_hood or subcategory == 'hoodie')
            elif py > 1.42 and (has_hood or subcategory in ["hoodie", "zip_hoodie"]):
                hood_t = np.clip((py - 1.42) / 0.26, 0.0, 1.0)
                joint_indices[i] = [4, 5, 3, 0]
                joint_weights[i] = [1.0 - hood_t * 0.75, hood_t * 0.75, 0.0, 0.0]

            # 4. Torso Body
            else:
                # Torso height span: 0.90m (hem) to 1.42m (collar)
                torso_t = np.clip((py - 0.90) / 0.52, 0.0, 1.0)
                if torso_t < 0.25:
                    s = torso_t / 0.25
                    # Hips (0) -> Spine (1)
                    joint_indices[i] = [0, 1, 2, 0]
                    joint_weights[i] = [1.0 - s * 0.65, s * 0.65, 0.0, 0.0]
                elif torso_t < 0.60:
                    s = (torso_t - 0.25) / 0.35
                    # Spine (1) -> Spine1 (2) -> Spine2 (3)
                    joint_indices[i] = [1, 2, 3, 0]
                    joint_weights[i] = [(1.0 - s) * 0.6, 0.4, s * 0.6, 0.0]
                elif torso_t < 0.88:
                    s = (torso_t - 0.60) / 0.28
                    # Spine2 (3) -> Neck (4)
                    joint_indices[i] = [3, 4, 2, 0]
                    joint_weights[i] = [1.0 - s * 0.40, s * 0.40, 0.0, 0.0]
                else:
                    s = (torso_t - 0.88) / 0.12
                    # Spine2 (3) -> Neck (4) (collar zone)
                    joint_indices[i] = [3, 4, 6 if px >= 0 else 10, 0]
                    joint_weights[i] = [(1.0 - s) * 0.35, 0.55 + s * 0.35, 0.10, 0.0]

            # Normalize weights to sum exactly to 1.0
            w_sum = np.sum(joint_weights[i])
            if w_sum > 1e-6:
                joint_weights[i] /= w_sum
            else:
                joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

        return joint_indices, joint_weights

    def _compute_joint_weights_bottoms(
        self,
        positions: np.ndarray,
        subcategory: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates 4 skinning influences and weights per vertex for lower body garments.
        Compatible with Ara 3D Gen 20-bone skeleton.
        Weights strictly sum to 1.0.
        """
        num_verts = len(positions)
        joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
        joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

        # Bone index lookup:
        # 0: Hips, 1: Spine
        # 14: LeftUpLeg, 15: LeftLeg, 16: LeftFoot
        # 17: RightUpLeg, 18: RightLeg, 19: RightFoot

        for i in range(num_verts):
            px, py, pz = positions[i]

            # Waistband / Upper Pelvis (py >= 0.92)
            if py >= 0.92:
                t = np.clip((py - 0.92) / 0.10, 0.0, 1.0)
                joint_indices[i] = [0, 1, 14 if px >= 0 else 17, 0]
                joint_weights[i] = [0.70 - t * 0.30, 0.30 + t * 0.30, 0.0, 0.0]

            # Left Leg (+X, px >= 0.0)
            elif px >= 0.0:
                # Leg span from crotch (0.84m) to bottom (0.08m or 0.52m)
                leg_t = np.clip((0.84 - py) / 0.76, 0.0, 1.0)
                if leg_t < 0.35:
                    s = leg_t / 0.35
                    # Hips (0) -> LeftUpLeg (14)
                    joint_indices[i] = [0, 14, 1, 0]
                    joint_weights[i] = [(1.0 - s) * 0.45, 0.55 + s * 0.45, 0.0, 0.0]
                elif leg_t < 0.80:
                    s = (leg_t - 0.35) / 0.45
                    # LeftUpLeg (14) -> LeftLeg (15)
                    joint_indices[i] = [14, 15, 0, 0]
                    joint_weights[i] = [1.0 - s, s, 0.0, 0.0]
                else:
                    s = (leg_t - 0.80) / 0.20
                    # LeftLeg (15) -> LeftFoot (16)
                    joint_indices[i] = [15, 16, 14, 0]
                    joint_weights[i] = [1.0 - s, s, 0.0, 0.0]

            # Right Leg (-X, px < 0.0)
            else:
                leg_t = np.clip((0.84 - py) / 0.76, 0.0, 1.0)
                if leg_t < 0.35:
                    s = leg_t / 0.35
                    # Hips (0) -> RightUpLeg (17)
                    joint_indices[i] = [0, 17, 1, 0]
                    joint_weights[i] = [(1.0 - s) * 0.45, 0.55 + s * 0.45, 0.0, 0.0]
                elif leg_t < 0.80:
                    s = (leg_t - 0.35) / 0.45
                    # RightUpLeg (17) -> RightLeg (18)
                    joint_indices[i] = [17, 18, 0, 0]
                    joint_weights[i] = [1.0 - s, s, 0.0, 0.0]
                else:
                    s = (leg_t - 0.80) / 0.20
                    # RightLeg (18) -> RightFoot (19)
                    joint_indices[i] = [18, 19, 17, 0]
                    joint_weights[i] = [1.0 - s, s, 0.0, 0.0]

            # Normalize weights to sum exactly to 1.0
            w_sum = np.sum(joint_weights[i])
            if w_sum > 1e-6:
                joint_weights[i] /= w_sum
            else:
                joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

        return joint_indices, joint_weights

    def _build_dresses(
        self,
        subcategory: str,
        fit: str,
        neckline_type: str = "crewneck",
        intelligence: Optional[Any] = None
    ) -> GarmentMesh:
        """
        Builds separate wearable dresses or skirts with realistic flared silhouettes
        and Ara 3D Gen 20-bone humanoid skinning influences.
        """
        margin = 0.020 if fit == "slim" else (0.038 if fit == "relaxed" else 0.026)
        is_maxi = "maxi" in subcategory or "gown" in subcategory
        hem_y = 0.18 if is_maxi else 0.48

        top_y = 1.42
        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "neckline_center" in lm or "collar_center" in lm:
                p = (lm.get("neckline_center") or lm.get("collar_center")).position
                top_y = float(np.clip(1.42 + (0.05 - p.y) * 0.10, 1.38, 1.45))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.48 + (0.95 - lm["hem_center"].position.y) * 0.25, 0.10, 0.65))

        dress_rings_spec = [
            (top_y, 0.168 + margin, 0.108 + margin),        # 0: Upper chest
            (top_y - 0.08, 0.182 + margin, 0.122 + margin), # 1: Bust
            (top_y - 0.18, 0.170 + margin, 0.114 + margin), # 2: Ribs
            (top_y - 0.28, 0.158 + margin, 0.105 + margin), # 3: Waist seam
            (1.02, 0.185 + margin, 0.125 + margin),         # 4: Hips
            (0.85, 0.215 + margin, 0.148 + margin),         # 5: Upper flare
            (0.65, 0.245 + margin, 0.170 + margin),         # 6: Mid flare
            (hem_y, 0.270 + margin, 0.190 + margin),        # 7: Lower hem
        ]

        n_seg = 28
        verts = []
        norms = []
        uv_coords = []
        tris = []

        ring_start_indices = []
        for ring_idx, (y, rx, rz) in enumerate(dress_rings_spec):
            ring_start_indices.append(len(verts))
            v_coord = ring_idx / (len(dress_rings_spec) - 1)
            for i in range(n_seg):
                th = 2.0 * math.pi * i / n_seg
                px = rx * math.cos(th)
                pz = rz * math.sin(th)
                verts.append([px, y, pz])
                norms.append([math.cos(th), 0.05, math.sin(th)])
                u_coord = (math.atan2(pz, px) / (2.0 * math.pi)) + 0.5
                uv_coords.append([u_coord, 0.95 - v_coord * 0.90])

        for r in range(len(dress_rings_spec) - 1):
            r_curr = ring_start_indices[r]
            r_next = ring_start_indices[r + 1]
            for i in range(n_seg):
                i_next = (i + 1) % n_seg
                tris.extend([[r_curr + i, r_curr + i_next, r_next + i_next],
                             [r_curr + i, r_next + i_next, r_next + i]])

        pos_np = np.array(verts, dtype=np.float32)
        norm_np = np.array(norms, dtype=np.float32)
        uv_np = np.array(uv_coords, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)

        joint_indices, joint_weights = self._compute_joint_weights_dresses(pos_np)
        return GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

    def _compute_joint_weights_dresses(self, positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        num_verts = len(positions)
        joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
        joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

        for i in range(num_verts):
            px, py, pz = positions[i]
            if py > 1.25:
                # Upper bodice: Spine1 (2) -> Spine2 (3) -> Neck (4)
                s = np.clip((py - 1.25) / 0.17, 0.0, 1.0)
                joint_indices[i] = [3, 4, 2, 0]
                joint_weights[i] = [1.0 - s * 0.40, s * 0.40, 0.0, 0.0]
            elif py > 1.00:
                # Mid torso / waist: Spine (1) -> Spine1 (2) -> Spine2 (3)
                s = np.clip((py - 1.00) / 0.25, 0.0, 1.0)
                joint_indices[i] = [1, 2, 3, 0]
                joint_weights[i] = [(1.0 - s) * 0.50, 0.40, s * 0.50, 0.0]
            elif py > 0.70:
                # Pelvis / Upper Skirt: Hips (0) -> Spine (1)
                s = np.clip((py - 0.70) / 0.30, 0.0, 1.0)
                joint_indices[i] = [0, 1, 14 if px >= 0 else 17, 0]
                joint_weights[i] = [0.80 - s * 0.30, 0.20 + s * 0.30, 0.0, 0.0]
            else:
                # Lower Skirt: Hips (0) blended with LeftUpLeg (14) / RightUpLeg (17)
                side_leg = 14 if px >= 0 else 17
                joint_indices[i] = [0, side_leg, 1, 0]
                joint_weights[i] = [0.65, 0.35, 0.0, 0.0]

            w_sum = np.sum(joint_weights[i])
            if w_sum > 1e-6:
                joint_weights[i] /= w_sum
            else:
                joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

        return joint_indices, joint_weights


# Singleton mesh builder
garment_mesh_builder = GarmentMeshBuilder()
