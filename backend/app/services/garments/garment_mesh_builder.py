"""
Stage B: 3D Garment Geometry Builder
Generates separate wearable 3D meshes (tops, bottoms, outerwear) with realistic openings,
canonical UV unwrapping, and Ara 3D Gen anatomic skeleton compatibility.
"""

from typing import Tuple, List, Dict, Any
import numpy as np
import math


class GarmentMesh:
    """Represents a separate wearable 3D garment geometry."""
    def __init__(
        self,
        positions: np.ndarray,      # (N, 3) float32
        normals: np.ndarray,        # (N, 3) float32
        uvs: np.ndarray,            # (N, 2) float32
        indices: np.ndarray,        # (M, 3) uint32
        joint_indices: np.ndarray = None,  # (N, 4) uint16
        joint_weights: np.ndarray = None   # (N, 4) float32
    ):
        self.positions = positions.astype(np.float32)
        self.normals = normals.astype(np.float32)
        self.uvs = uvs.astype(np.float32)
        self.indices = indices.astype(np.uint32)
        self.joint_indices = joint_indices
        self.joint_weights = joint_weights


class GarmentMeshBuilder:
    """Constructs category-specific 3D garment meshes with proper openings and anatomic alignment."""

    def build_mesh(
        self,
        category: str,
        subcategory: str = "tshirt",
        sleeve_length: str = "short",
        neckline_type: str = "crewneck",
        fit: str = "regular"
    ) -> GarmentMesh:
        cat = category.lower()
        if cat in ["bottom", "trousers", "pants", "shorts", "jeans"]:
            return self._build_bottoms(subcategory, fit)
        else:
            return self._build_tops(subcategory, sleeve_length, neckline_type, fit)

    def _build_tops(
        self,
        subcategory: str,
        sleeve_length: str,
        neckline_type: str,
        fit: str
    ) -> GarmentMesh:
        """
        Builds a separate wearable top garment (T-shirt, Long-sleeve shirt, Hoodie, Tank top).
        Dimensions match Ara 3D Gen canonical meter scale (Y-up, Z-front).
        """
        # Fit adjustments: outer envelope margin over skin
        margin = 0.018 if fit == "slim" else (0.035 if fit == "oversized" else 0.024)
        
        # Anatomic Torso Rings (from collarbone down to hips)
        # Ring: (y, rx, rz) -> height, lateral radius (width), sagittal radius (depth)
        torso_rings_spec = [
            (1.42, 0.170 + margin, 0.110 + margin), # 0: Upper chest / clavicle
            (1.34, 0.185 + margin, 0.125 + margin), # 1: Mid-chest / bust line
            (1.24, 0.175 + margin, 0.118 + margin), # 2: Lower ribs
            (1.14, 0.165 + margin, 0.112 + margin), # 3: Natural waist
            (1.02, 0.180 + margin, 0.122 + margin), # 4: Upper hip
            (0.90, 0.192 + margin, 0.130 + margin), # 5: Lower hemline (open)
        ]
        
        n_seg = 28 # Radial subdivision for smooth curvature
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
                # Slight flattening for human ribcage / back profile
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)
                
                # Front neckline dip on top ring
                y_mod = y
                if ring_idx == 0:
                    if sin_t > 0: # Front half
                        neck_dip = 0.045 if neckline_type == "v_neck" else 0.025
                        y_mod -= neck_dip * (sin_t ** 2)
                        
                px = rx * cos_t
                pz = rz * sin_t
                py = y_mod
                
                # Normal vector
                nx = cos_t
                nz = sin_t
                ny = 0.1 if ring_idx == len(torso_rings_spec) - 1 else 0.0
                norm_len = math.sqrt(nx*nx + ny*ny + nz*nz)
                
                verts.append([px, py, pz])
                norms.append([nx / norm_len, ny / norm_len, nz / norm_len])
                
                # UV mapping: Left half = Front, Right half = Back in atlas
                u_coord = (math.atan2(pz, px) / (2.0 * math.pi)) + 0.5
                uv_coords.append([u_coord, 1.0 - v_coord])
                
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
            
            for side in [-1.0, 1.0]: # Left (-1) and Right (+1) arms
                shoulder_origin = np.array([side * 0.19, 1.34, 0.0])
                # Arm angle: angled slightly downwards and forwards in resting A-pose
                arm_dir = np.array([side * 0.85, -0.48, 0.15])
                arm_dir = arm_dir / np.linalg.norm(arm_dir)
                
                # Orthogonal frame for arm circle
                up_hint = np.array([0, 1, 0])
                arm_right = np.cross(arm_dir, up_hint)
                arm_right = arm_right / np.linalg.norm(arm_right)
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
                        
                        # UVs mapped to dedicated sleeve panel quadrants
                        u_arm = (0.75 if side > 0 else 0.25) + 0.22 * math.cos(phi)
                        v_arm = 0.25 + 0.22 * math.sin(phi)
                        uv_coords.append([u_arm, v_arm])
                        
                # Connect arm rings
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

        # Convert to numpy arrays
        pos_np = np.array(verts, dtype=np.float32)
        norm_np = np.array(norms, dtype=np.float32)
        uv_np = np.array(uv_coords, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        
        return GarmentMesh(pos_np, norm_np, uv_np, idx_np)

    def _build_bottoms(self, subcategory: str, fit: str) -> GarmentMesh:
        """
        Builds separate wearable trousers, jeans, or shorts with dual leg tubes and open waist/cuffs.
        """
        margin = 0.022 if fit == "slim" else (0.040 if fit == "relaxed" else 0.028)
        is_shorts = subcategory == "shorts"
        
        verts = []
        norms = []
        uv_coords = []
        tris = []
        n_seg = 28
        
        # 1. Waistband and Pelvis section
        pelvis_rings = [
            (1.02, 0.178 + margin, 0.124 + margin), # Waist opening
            (0.94, 0.188 + margin, 0.134 + margin), # Mid-pelvis
            (0.84, 0.194 + margin, 0.140 + margin), # Low hips / crotch apex
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
        
        for side in [-1.0, 1.0]: # Left and Right legs
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
        
        return GarmentMesh(pos_np, norm_np, uv_np, idx_np)


# Singleton mesh builder
garment_mesh_builder = GarmentMeshBuilder()
