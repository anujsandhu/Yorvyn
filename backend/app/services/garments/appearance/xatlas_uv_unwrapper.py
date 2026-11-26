"""
YORVYN — xatlas Automated UV Parameterization Engine (Phase 14.22 Workstream C3)
Automated parameterization of 3D garment meshes into non-overlapping 2D UV charts:
- Conformal surface flattening with minimal isometric and area distortion
- Automated chart boundary segmentation and seam packing
- Resolution-independent [0, 1] UV coordinates
- Seamless integration with PBR texture atlases
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import xatlas
    XATLAS_AVAILABLE = True
except ImportError:
    XATLAS_AVAILABLE = False


class XatlasUVUnwrapper:
    """Automated UV unrolling and chart packing using xatlas."""

    def __init__(self):
        self.is_available = XATLAS_AVAILABLE
        logger.info(f"XatlasUVUnwrapper initialized (xatlas available: {self.is_available})")

    def unwrap_mesh(
        self,
        positions: np.ndarray,
        indices: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        Unwraps 3D mesh into optimized 2D UV charts.
        Returns:
            new_positions: (V', 3) float32
            new_indices: (F, 3) int32
            new_uvs: (V', 2) float32 in [0, 1]
            metadata: dict with chart_count, latency_ms, status
        """
        t0 = time.perf_counter()

        pos_f32 = positions.astype(np.float32)
        idx_i32 = indices.reshape(-1, 3).astype(np.int32)

        if not self.is_available:
            # Fallback: Cylindrical projection
            v_cnt = len(pos_f32)
            u = (np.arctan2(pos_f32[:, 0], pos_f32[:, 2]) + np.pi) / (2 * np.pi)
            y_min, y_max = pos_f32[:, 1].min(), pos_f32[:, 1].max()
            v = (pos_f32[:, 1] - y_min) / max(y_max - y_min, 1e-5)
            fallback_uvs = np.column_stack((u, v)).astype(np.float32)
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return pos_f32, idx_i32.flatten(), fallback_uvs, {
                "method": "cylindrical_fallback",
                "chart_count": 1,
                "latency_ms": dur_ms,
                "status": "FALLBACK"
            }

        try:
            # xatlas.parametrize takes positions (N, 3) and indices (M, 3)
            vmapping, new_indices, uvs = xatlas.parametrize(pos_f32, idx_i32)
            new_positions = pos_f32[vmapping]
            
            # Normalize UVs strictly to [0, 1]
            uv_min = uvs.min(axis=0)
            uv_max = uvs.max(axis=0)
            uv_span = np.maximum(uv_max - uv_min, 1e-6)
            norm_uvs = (uvs - uv_min) / uv_span

            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return (
                new_positions.astype(np.float32),
                new_indices.flatten().astype(np.int32),
                norm_uvs.astype(np.float32),
                {
                    "method": "xatlas_atlas_packing",
                    "original_vertex_count": len(pos_f32),
                    "unwrapped_vertex_count": len(new_positions),
                    "face_count": len(new_indices),
                    "latency_ms": dur_ms,
                    "status": "XATLAS_SUCCESS"
                }
            )
        except Exception as e:
            logger.error(f"xatlas parameterization failed ({e}). Using planar fallback.")
            u = (pos_f32[:, 0] - pos_f32[:, 0].min()) / max(pos_f32[:, 0].ptp(), 1e-5)
            v = (pos_f32[:, 1] - pos_f32[:, 1].min()) / max(pos_f32[:, 1].ptp(), 1e-5)
            fallback_uvs = np.column_stack((u, v)).astype(np.float32)
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return pos_f32, idx_i32.flatten(), fallback_uvs, {
                "method": "planar_fallback",
                "chart_count": 1,
                "latency_ms": dur_ms,
                "status": f"FAILED: {e}"
            }


xatlas_unwrapper = XatlasUVUnwrapper()
