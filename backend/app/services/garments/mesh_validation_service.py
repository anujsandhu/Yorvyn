"""
YORVYN — Authoritative 3D Mesh Topology & Validation Service (Phase 13.2 Remediated)
Leverages Trimesh and analytical computational geometry to evaluate true 2-manifold topology,
edge incidence, boundary edge loops, degenerate faces, duplicate faces, winding consistency,
watertightness, and category-calibrated anthropometric bounding envelopes.
"""

import io
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


class MeshValidationReport:
    def __init__(
        self,
        is_valid: bool,
        is_watertight: bool,
        vertex_count: int,
        face_count: int,
        is_manifold: bool,
        connected_components: int,
        degenerate_faces: int,
        duplicate_faces: int,
        boundary_edges_count: int,
        non_manifold_edges_count: int,
        is_winding_consistent: bool,
        bounds_min: List[float],
        bounds_max: List[float],
        extents: List[float],
        volume_m3: float,
        issues: List[str],
        warnings: List[str]
    ):
        self.is_valid = is_valid
        self.is_watertight = is_watertight
        self.vertex_count = vertex_count
        self.face_count = face_count
        self.is_manifold = is_manifold
        self.connected_components = connected_components
        self.degenerate_faces = degenerate_faces
        self.duplicate_faces = duplicate_faces
        self.boundary_edges_count = boundary_edges_count
        self.non_manifold_edges_count = non_manifold_edges_count
        self.is_winding_consistent = is_winding_consistent
        self.bounds_min = bounds_min
        self.bounds_max = bounds_max
        self.extents = extents
        self.volume_m3 = volume_m3
        self.issues = issues
        self.warnings = warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "is_watertight": self.is_watertight,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "is_manifold": self.is_manifold,
            "connected_components": self.connected_components,
            "degenerate_faces": self.degenerate_faces,
            "duplicate_faces": self.duplicate_faces,
            "boundary_edges_count": self.boundary_edges_count,
            "non_manifold_edges_count": self.non_manifold_edges_count,
            "is_winding_consistent": self.is_winding_consistent,
            "bounds_min": [round(v, 4) for v in self.bounds_min],
            "bounds_max": [round(v, 4) for v in self.bounds_max],
            "extents": [round(v, 4) for v in self.extents],
            "volume_m3": round(self.volume_m3, 6),
            "issues": self.issues,
            "warnings": self.warnings
        }


# Category-specific anthropometric bounding boxes (min, max in meters)
CATEGORY_BOUNDS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "top": {"x": (0.15, 1.40), "y": (0.25, 1.40), "z": (0.04, 0.90)},
    "hoodie": {"x": (0.15, 1.50), "y": (0.30, 1.50), "z": (0.04, 1.00)},
    "shirt": {"x": (0.15, 1.40), "y": (0.25, 1.40), "z": (0.04, 0.90)},
    "jacket": {"x": (0.15, 1.60), "y": (0.30, 1.60), "z": (0.04, 1.10)},
    "outerwear": {"x": (0.15, 1.60), "y": (0.30, 1.60), "z": (0.04, 1.10)},
    "bottoms": {"x": (0.15, 1.10), "y": (0.30, 1.60), "z": (0.04, 0.80)},
    "bottom": {"x": (0.15, 1.10), "y": (0.30, 1.60), "z": (0.04, 0.80)},
    "dress": {"x": (0.15, 1.60), "y": (0.40, 2.10), "z": (0.04, 1.20)},
    "skirt": {"x": (0.15, 1.30), "y": (0.20, 1.30), "z": (0.04, 0.90)},
    "footwear": {"x": (0.05, 0.50), "y": (0.05, 0.60), "z": (0.10, 0.50)},
    "accessories": {"x": (0.01, 1.80), "y": (0.01, 1.80), "z": (0.01, 1.20)}
}


class MeshValidationService:
    @classmethod
    def validate_glb_bytes(cls, glb_bytes: bytes, category: str = "top") -> MeshValidationReport:
        """
        Performs authoritative forensic inspection of an exported GLB binary buffer:
        - True edge incidence & 2-manifold verification (non-manifold edges count)
        - Boundary edge isolation (collar, armscye, hem openings)
        - Duplicate and degenerate zero-area faces
        - Consistent winding normals
        - Watertightness
        - Category-specific anthropometric bounding extents
        """
        issues: List[str] = []
        warnings: List[str] = []
        norm_cat = category.lower().strip()

        if not glb_bytes or len(glb_bytes) < 20:
            return MeshValidationReport(
                is_valid=False,
                is_watertight=False,
                vertex_count=0,
                face_count=0,
                is_manifold=False,
                connected_components=0,
                degenerate_faces=0,
                duplicate_faces=0,
                boundary_edges_count=0,
                non_manifold_edges_count=0,
                is_winding_consistent=False,
                bounds_min=[0, 0, 0],
                bounds_max=[0, 0, 0],
                extents=[0, 0, 0],
                volume_m3=0.0,
                issues=["Invalid or empty GLB binary payload"],
                warnings=[]
            )

        if not TRIMESH_AVAILABLE:
            warnings.append("UNVERIFIED: Trimesh is unavailable; only the GLB header can be checked.")
            has_magic = glb_bytes[:4] == b"glTF"
            return MeshValidationReport(
                is_valid=False,
                is_watertight=False,
                vertex_count=0,
                face_count=0,
                is_manifold=False,
                connected_components=0,
                degenerate_faces=0,
                duplicate_faces=0,
                boundary_edges_count=0,
                non_manifold_edges_count=0,
                is_winding_consistent=False,
                bounds_min=[0, 0, 0],
                bounds_max=[0, 0, 0],
                extents=[0, 0, 0],
                volume_m3=0.0,
                issues=["Mesh topology validation unavailable"] + ([] if has_magic else ["Missing glTF binary header magic"]),
                warnings=warnings
            )

        try:
            # Load GLB with Trimesh
            scene_or_mesh = trimesh.load(
                io.BytesIO(glb_bytes),
                file_type="glb",
                force="scene"
            )

            # Combine geometry if scene
            if isinstance(scene_or_mesh, trimesh.Scene):
                geoms = [m for m in scene_or_mesh.geometry.values() if isinstance(m, trimesh.Trimesh)]
                if len(geoms) == 0:
                    return MeshValidationReport(
                        is_valid=False,
                        is_watertight=False,
                        vertex_count=0,
                        face_count=0,
                        is_manifold=False,
                        connected_components=0,
                        degenerate_faces=0,
                        duplicate_faces=0,
                        boundary_edges_count=0,
                        non_manifold_edges_count=0,
                        is_winding_consistent=False,
                        bounds_min=[0, 0, 0],
                        bounds_max=[0, 0, 0],
                        extents=[0, 0, 0],
                        volume_m3=0.0,
                        issues=["GLB scene contains no valid geometric meshes."],
                        warnings=[]
                    )
                mesh = trimesh.util.concatenate(geoms)
            elif isinstance(scene_or_mesh, trimesh.Trimesh):
                mesh = scene_or_mesh
            else:
                mesh = trimesh.Trimesh()

            v_count = len(mesh.vertices)
            f_count = len(mesh.faces)

            if v_count < 20 or f_count < 10:
                issues.append(f"Insufficient geometry density: {v_count} vertices, {f_count} faces.")

            # 1. Edge incidence & 2-manifold validation
            # For 2-manifold meshes:
            # - Interior edges have exactly 2 adjacent faces (count == 2)
            # - Boundary edges have exactly 1 adjacent face (count == 1, open cuffs/neck/hem)
            # - Non-manifold edges have > 2 adjacent faces (counts > 2) -> FATAL ERROR
            edges_sorted = mesh.edges_sorted
            if len(edges_sorted) > 0:
                _, edge_counts = np.unique(edges_sorted, axis=0, return_counts=True)
                boundary_edges_count = int(np.sum(edge_counts == 1))
                non_manifold_edges_count = int(np.sum(edge_counts > 2))
            else:
                boundary_edges_count = 0
                non_manifold_edges_count = 0

            if non_manifold_edges_count > 0:
                issues.append(f"Non-manifold geometry: {non_manifold_edges_count} edges are shared by 3 or more faces.")

            # 2. Duplicate faces check
            if len(mesh.faces) > 0:
                sorted_faces = np.sort(mesh.faces, axis=1)
                unique_faces_count = len(np.unique(sorted_faces, axis=0))
                duplicate_faces = int(len(mesh.faces) - unique_faces_count)
            else:
                duplicate_faces = 0

            if duplicate_faces > 0:
                issues.append(f"Topological defect: {duplicate_faces} duplicate overlapping faces detected.")

            # 3. Degenerate zero-area faces check
            try:
                area_per_face = mesh.area_faces
                degenerate_faces = int(np.sum(area_per_face <= 1e-9))
                if degenerate_faces > 0:
                    issues.append(f"Geometric defect: {degenerate_faces} degenerate zero-area faces detected.")
            except Exception:
                degenerate_faces = 0

            # 4. Watertightness & Winding Consistency
            is_watertight = bool(mesh.is_watertight)
            is_winding_consistent = bool(mesh.is_winding_consistent)

            if not is_watertight:
                if boundary_edges_count > 0:
                    warnings.append(f"Open-bordered garment construction: {boundary_edges_count} boundary edges (expected for neck/cuff/hem openings).")
                else:
                    warnings.append("Mesh is not watertight.")

            if not is_winding_consistent:
                warnings.append("Inconsistent face normal winding detected.")

            # 5. Connected components
            try:
                components = mesh.split(only_watertight=False)
                comp_count = len(components)
                if comp_count > 12:
                    warnings.append(f"Mesh has {comp_count} disconnected sub-components (trims, buttons, or loose panels).")
            except Exception:
                comp_count = 1

            # 6. Category-specific anthropometric bounding limits
            bounds = mesh.bounds
            bounds_min = [float(b) for b in bounds[0]] if bounds is not None else [-0.5, -0.5, -0.5]
            bounds_max = [float(b) for b in bounds[1]] if bounds is not None else [0.5, 0.5, 0.5]
            ext = [float(e) for e in mesh.extents] if mesh.extents is not None else [1.0, 1.0, 1.0]

            cat_limit = CATEGORY_BOUNDS.get(norm_cat, CATEGORY_BOUNDS["top"])
            x_min, x_max = cat_limit["x"]
            y_min, y_max = cat_limit["y"]
            z_min, z_max = cat_limit["z"]

            if ext[0] < x_min or ext[1] < y_min or ext[2] < z_min:
                issues.append(
                    f"Garment extents [{ext[0]:.2f}, {ext[1]:.2f}, {ext[2]:.2f}]m are below minimum viable garment dimensions for '{norm_cat}'."
                )

            if ext[0] > x_max or ext[1] > y_max or ext[2] > z_max:
                issues.append(
                    f"Garment extents [{ext[0]:.2f}, {ext[1]:.2f}, {ext[2]:.2f}]m exceed human avatar scale limits [{x_max}, {y_max}, {z_max}]m for '{norm_cat}'."
                )

            # Volume computation (if watertight, else 0.0)
            vol = float(mesh.volume) if is_watertight else 0.0

            # True 2-manifold determination:
            # No non-manifold edges, no duplicate faces, no degenerate faces
            is_manifold = bool(
                non_manifold_edges_count == 0 and
                duplicate_faces == 0 and
                degenerate_faces == 0
            )

            is_valid = bool(len(issues) == 0 and is_manifold)

            return MeshValidationReport(
                is_valid=is_valid,
                is_watertight=is_watertight,
                vertex_count=v_count,
                face_count=f_count,
                is_manifold=is_manifold,
                connected_components=comp_count,
                degenerate_faces=degenerate_faces,
                duplicate_faces=duplicate_faces,
                boundary_edges_count=boundary_edges_count,
                non_manifold_edges_count=non_manifold_edges_count,
                is_winding_consistent=is_winding_consistent,
                bounds_min=bounds_min,
                bounds_max=bounds_max,
                extents=ext,
                volume_m3=vol,
                issues=issues,
                warnings=warnings
            )

        except Exception as e:
            return MeshValidationReport(
                is_valid=False,
                is_watertight=False,
                vertex_count=0,
                face_count=0,
                is_manifold=False,
                connected_components=0,
                degenerate_faces=0,
                duplicate_faces=0,
                boundary_edges_count=0,
                non_manifold_edges_count=0,
                is_winding_consistent=False,
                bounds_min=[0, 0, 0],
                bounds_max=[0, 0, 0],
                extents=[0, 0, 0],
                volume_m3=0.0,
                issues=[f"Corrupted or invalid GLB payload: {str(e)}"],
                warnings=[]
            )


mesh_validation_service = MeshValidationService()
