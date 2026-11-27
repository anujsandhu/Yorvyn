"""
YORVYN — 3D Garment Mesh Quality Validator
Rigorous geometric and topological validation for 3D garment meshes.
Validates manifoldness, non-degenerate triangles, boundary opening loops,
vertex normal consistency, and Ara 3D 20-bone skinning weight integrity.
"""

from typing import List, Tuple, Dict, Set, Optional, Any
import numpy as np

from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from .base_reconstruction_engine import MeshQualityReport, GarmentComponentGraph


class GarmentMeshValidator:
    """Evaluates geometric, topological, and rigging validity of garment meshes."""

    @staticmethod
    def validate(mesh: GarmentMesh) -> MeshQualityReport:
        issues: List[str] = []
        is_valid = True
        
        pos = mesh.positions
        idx = mesh.indices
        norm = mesh.normals
        uv = mesh.uvs

        num_verts = len(pos)
        num_tris = len(idx)

        # 1. Basic array shape and count checks
        if num_verts < 12:
            issues.append(f"Insufficient vertices: {num_verts} (minimum 12 required)")
            is_valid = False
        if num_tris < 8:
            issues.append(f"Insufficient triangles: {num_tris} (minimum 8 required)")
            is_valid = False

        # 2. Non-finite values (NaN / Inf)
        non_finite_verts = int(np.isnan(pos).sum() + np.isinf(pos).sum())
        if non_finite_verts > 0:
            issues.append(f"Positions contain {non_finite_verts} non-finite (NaN/Inf) values")
            is_valid = False

        non_finite_norms = int(np.isnan(norm).sum() + np.isinf(norm).sum())
        if non_finite_norms > 0:
            issues.append(f"Normals contain {non_finite_norms} non-finite (NaN/Inf) values")
            is_valid = False

        # 3. Index bounds check
        if num_tris > 0:
            max_idx = int(idx.max())
            min_idx = int(idx.min())
            if min_idx < 0 or max_idx >= num_verts:
                issues.append(f"Index out of bounds: [{min_idx}, {max_idx}] for {num_verts} vertices")
                is_valid = False

        # 4. Degenerate Triangles Check
        # Area = 0.5 * ||(v1 - v0) x (v2 - v0)||
        degenerate_count = 0
        if num_tris > 0 and num_verts > 0:
            v0 = pos[idx[:, 0]]
            v1 = pos[idx[:, 1]]
            v2 = pos[idx[:, 2]]
            cross = np.cross(v1 - v0, v2 - v0)
            areas = 0.5 * np.linalg.norm(cross, axis=1)
            
            # Area threshold: 1e-7 m^2 (0.1 mm^2)
            deg_mask = areas < 1e-7
            degenerate_count = int(np.sum(deg_mask))
            if degenerate_count > 0:
                issues.append(f"Found {degenerate_count} degenerate triangles with area < 1e-7 m²")

        # 5. Normal vector normalization check
        norm_lengths = np.linalg.norm(norm, axis=1)
        denorm_count = int(np.sum(np.abs(norm_lengths - 1.0) > 0.15))
        if denorm_count > 0:
            issues.append(f"{denorm_count} vertex normals deviate from unit length")

        # 6. Manifoldness & Boundary Loops Analysis
        # An edge is non-manifold if shared by > 2 triangles.
        edge_count: Dict[Tuple[int, int], int] = {}
        for tri in idx:
            for k in range(3):
                u, v = int(tri[k]), int(tri[(k + 1) % 3])
                canonical_edge = (min(u, v), max(u, v))
                edge_count[canonical_edge] = edge_count.get(canonical_edge, 0) + 1

        non_manifold_edges = sum(1 for c in edge_count.values() if c > 2)
        boundary_edges = [edge for edge, c in edge_count.items() if c == 1]
        
        is_manifold = non_manifold_edges == 0
        if not is_manifold:
            issues.append(f"Mesh has {non_manifold_edges} non-manifold edges (shared by >2 triangles)")

        # Count distinct boundary loops from boundary edges
        boundary_loops = GarmentMeshValidator._count_boundary_loops(boundary_edges)

        # 7. Skinning Weight Integrity Check (Ara 3D Gen 20 bones)
        if mesh.joint_indices is not None and mesh.joint_weights is not None:
            if len(mesh.joint_indices) != num_verts or len(mesh.joint_weights) != num_verts:
                issues.append("Skinning array lengths do not match vertex count")
                is_valid = False
            
            # Weight sum check (must sum to ~1.0)
            weight_sums = mesh.joint_weights.sum(axis=1)
            bad_weights = int(np.sum(np.abs(weight_sums - 1.0) > 0.01))
            if bad_weights > 0:
                issues.append(f"{bad_weights} vertices have skinning weights that do not sum to 1.0")

            # Joint index bounds (0 to 19 for 20-bone skeleton)
            max_joint = int(mesh.joint_indices.max())
            if max_joint >= 20:
                issues.append(f"Joint index {max_joint} exceeds Ara 3D 20-bone skeleton bounds [0, 19]")
                is_valid = False

        # 8. Compute overall quality score [0.0, 1.0]
        quality_score = 1.0
        if not is_valid:
            quality_score *= 0.2
        if not is_manifold:
            quality_score -= 0.25
        if degenerate_count > 0:
            deg_ratio = min(1.0, degenerate_count / max(1, num_tris))
            quality_score -= deg_ratio * 0.30
        if denorm_count > 0:
            quality_score -= 0.10
        quality_score = max(0.0, min(1.0, float(quality_score)))

        return MeshQualityReport(
            is_valid=is_valid and is_manifold and degenerate_count == 0,
            is_manifold=is_manifold,
            has_degenerate_triangles=degenerate_count > 0,
            degenerate_triangle_count=degenerate_count,
            vertex_count=num_verts,
            triangle_count=num_tris,
            boundary_loops=boundary_loops,
            non_finite_vertex_count=non_finite_verts,
            issues=issues,
            quality_score=round(quality_score, 3)
        )

    @staticmethod
    def _count_boundary_loops(boundary_edges: List[Tuple[int, int]]) -> int:
        """Finds connected boundary components forming openings."""
        if not boundary_edges:
            return 0
        
        adj: Dict[int, List[int]] = {}
        for u, v in boundary_edges:
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)

        visited: Set[int] = set()
        loops = 0
        for node in adj:
            if node not in visited:
                loops += 1
                queue = [node]
                visited.add(node)
                while queue:
                    curr = queue.pop(0)
                    for neighbor in adj.get(curr, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
        return loops

    @staticmethod
    def validate_component_graph(mesh: GarmentMesh, graph: Optional[GarmentComponentGraph]) -> Dict[str, Any]:
        """Rigorous topological and geometrical validation of component hierarchy."""
        if not graph or not graph.nodes:
            return {"is_valid": True, "node_count": 0, "issues": ["No component graph provided"]}
            
        issues: List[str] = []
        num_verts = len(mesh.positions)
        num_tris = len(mesh.indices)
        
        # 1. Total triangle coverage check
        total_comp_tris = sum(node.triangle_range[1] for node in graph.nodes.values())
        if total_comp_tris != num_tris:
            issues.append(f"Component triangle coverage mismatch: components cover {total_comp_tris} tris, mesh has {num_tris} tris")
            
        # 2. Check bounds and dimensions
        for node_id, node in graph.nodes.items():
            v_start, v_cnt = node.vertex_range
            t_start, t_cnt = node.triangle_range
            
            if v_start < 0 or (v_start + v_cnt) > num_verts:
                issues.append(f"Component '{node_id}' vertex range [{v_start}, {v_start+v_cnt}] exceeds mesh vertex count {num_verts}")
            if t_start < 0 or (t_start + t_cnt) > num_tris:
                issues.append(f"Component '{node_id}' triangle range [{t_start}, {t_start+t_cnt}] exceeds mesh triangle count {num_tris}")
                
            w, h, d = node.dimensions_m
            if w > 2.5 or h > 2.5 or d > 2.5:
                issues.append(f"Component '{node_id}' dimensions ({w:.2f}, {h:.2f}, {d:.2f})m exceed physical human scale limit (2.5m)")
                
        # 3. Hierarchy cycle and reachability check
        topo = graph.get_topological_order()
        if len(topo) != len(graph.nodes):
            issues.append("Cycle or disconnected subgraph detected in component hierarchy")
            
        return {
            "is_valid": len(issues) == 0,
            "node_count": len(graph.nodes),
            "total_component_triangles": total_comp_tris,
            "mesh_triangles": num_tris,
            "issues": issues
        }

