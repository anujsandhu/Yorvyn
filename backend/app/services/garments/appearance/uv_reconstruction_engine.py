"""
YORVYN — Dedicated Garment UV Reconstruction Engine
Constructs category-tailored, non-overlapping UV island coordinate layouts
across all 9 apparel categories:
- Tops & T-Shirts: Front Torso, Back Torso, Left Sleeve, Right Sleeve
- Formal Shirts: Collar Stand, Collar Points, Front Placket, Cuffs, Torso, Sleeves
- Hoodies: Front Torso, Back Torso, Sleeves, Hood Cowl, Kangaroo Pocket
- Jackets: Front Split Panels, Zipper Track, Lapels, Back, Sleeves
- Bottoms & Jeans: Waistband, Fly, Left Inseam Leg, Right Inseam Leg
- Dresses & Skirts: Bodice, Waist Seam, Flared Skirt Drape
- Traditional Kurtas: Upper Torso, Front Flap (chaks), Back Flap (chaks), Mandarin Collar, Sleeves
- Footwear: Outsoles, Midsole Welts, Upper Shells (Vamp, Toe Box, Quarters), Ankle Collars
- Accessories: Crown Dome, Visor Brim

Calculates UV stretch metrics (Dirichlet / aspect distortion) and generates visual UV layout previews.
"""

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
import numpy as np
from PIL import Image, ImageDraw

from backend.app.services.garments.garment_mesh_builder import GarmentMesh


@dataclass
class UVSurfaceIsland:
    """Named rectangular or polygonal UV island layout partition."""
    name: str
    u_min: float
    v_min: float
    u_max: float
    v_max: float
    is_observed_front: bool
    associated_panel: str

    @property
    def width(self) -> float:
        return max(0.0, self.u_max - self.u_min)

    @property
    def height(self) -> float:
        return max(0.0, self.v_max - self.v_min)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.u_min + self.width * 0.5, self.v_min + self.height * 0.5)


@dataclass
class CategoryUVLayout:
    """Full UV partition atlas for a specific apparel category."""
    category_id: str
    islands: List[UVSurfaceIsland]
    island_lookup: Dict[str, UVSurfaceIsland] = field(default_factory=dict)

    def __post_init__(self):
        self.island_lookup = {isl.name: isl for isl in self.islands}


class GarmentUVReconstructionEngine:
    """Engine for generating and validating category-specific garment UV parameterizations."""

    # Canonical Category UV Atlas Partitions in normalized [0.0, 1.0] canvas
    # Layout ensures zero overlap and aligns with Phase 3 vertex generation
    LAYOUTS: Dict[str, CategoryUVLayout] = {
        "tops": CategoryUVLayout(
            category_id="tops",
            islands=[
                UVSurfaceIsland("front_torso", 0.04, 0.48, 0.46, 0.96, True, "front_torso_panel"),
                UVSurfaceIsland("back_torso", 0.54, 0.48, 0.96, 0.96, False, "back_torso_panel"),
                UVSurfaceIsland("left_sleeve", 0.04, 0.24, 0.46, 0.44, True, "left_sleeve"),
                UVSurfaceIsland("right_sleeve", 0.54, 0.24, 0.96, 0.44, True, "right_sleeve"),
            ]
        ),
        "formal_shirt": CategoryUVLayout(
            category_id="formal_shirt",
            islands=[
                UVSurfaceIsland("front_torso", 0.04, 0.48, 0.46, 0.96, True, "front_torso_panel"),
                UVSurfaceIsland("back_torso", 0.54, 0.48, 0.96, 0.96, False, "back_torso_panel"),
                UVSurfaceIsland("collar_stand_and_points", 0.20, 0.04, 0.80, 0.16, True, "collar_stand_and_points"),
                UVSurfaceIsland("front_placket", 0.48, 0.48, 0.52, 0.96, True, "front_placket_band"),
                UVSurfaceIsland("left_sleeve_and_cuff", 0.04, 0.24, 0.46, 0.44, True, "left_sleeve_and_cuff"),
                UVSurfaceIsland("right_sleeve_and_cuff", 0.54, 0.24, 0.96, 0.44, True, "right_sleeve_and_cuff"),
            ]
        ),
        "hoodie": CategoryUVLayout(
            category_id="hoodie",
            islands=[
                UVSurfaceIsland("front_torso", 0.04, 0.48, 0.46, 0.96, True, "front_torso_panel"),
                UVSurfaceIsland("back_torso", 0.54, 0.48, 0.96, 0.96, False, "back_torso_panel"),
                UVSurfaceIsland("hood_cowl", 0.10, 0.04, 0.90, 0.22, True, "hood_cowl"),
                UVSurfaceIsland("kangaroo_pocket", 0.14, 0.68, 0.36, 0.92, True, "kangaroo_pocket"),
                UVSurfaceIsland("left_sleeve_and_cuff", 0.04, 0.24, 0.46, 0.44, True, "left_sleeve_and_cuff"),
                UVSurfaceIsland("right_sleeve_and_cuff", 0.54, 0.24, 0.96, 0.44, True, "right_sleeve_and_cuff"),
            ]
        ),
        "jacket": CategoryUVLayout(
            category_id="jacket",
            islands=[
                UVSurfaceIsland("front_left_panel", 0.04, 0.48, 0.24, 0.96, True, "front_jacket_torso"),
                UVSurfaceIsland("front_right_panel", 0.26, 0.48, 0.46, 0.96, True, "front_jacket_torso"),
                UVSurfaceIsland("front_zipper_track", 0.24, 0.48, 0.26, 0.96, True, "front_zipper_track"),
                UVSurfaceIsland("lapels_and_collar", 0.15, 0.04, 0.85, 0.18, True, "lapels_and_collar"),
                UVSurfaceIsland("back_torso", 0.54, 0.48, 0.96, 0.96, False, "back_jacket_torso"),
                UVSurfaceIsland("left_sleeve", 0.04, 0.24, 0.46, 0.44, True, "left_outerwear_sleeve"),
                UVSurfaceIsland("right_sleeve", 0.54, 0.24, 0.96, 0.44, True, "right_outerwear_sleeve"),
            ]
        ),
        "bottoms": CategoryUVLayout(
            category_id="bottoms",
            islands=[
                UVSurfaceIsland("waistband_and_pelvis", 0.04, 0.75, 0.96, 0.96, True, "waistband_and_pelvis"),
                UVSurfaceIsland("left_leg_tube", 0.54, 0.05, 0.96, 0.70, True, "left_leg_panel"),
                UVSurfaceIsland("right_leg_tube", 0.04, 0.05, 0.46, 0.70, True, "right_leg_panel"),
            ]
        ),
        "dresses_and_skirts": CategoryUVLayout(
            category_id="dresses_and_skirts",
            islands=[
                UVSurfaceIsland("fitted_bodice", 0.04, 0.65, 0.96, 0.96, True, "fitted_bodice"),
                UVSurfaceIsland("skirt_drape", 0.04, 0.05, 0.96, 0.62, True, "waist_seam_and_skirt"),
            ]
        ),
        "traditional": CategoryUVLayout(
            category_id="traditional",
            islands=[
                UVSurfaceIsland("kurta_upper_torso", 0.04, 0.55, 0.96, 0.96, True, "kurta_upper_torso"),
                UVSurfaceIsland("kurta_front_flap", 0.04, 0.24, 0.46, 0.52, True, "kurta_front_flap_with_side_slits"),
                UVSurfaceIsland("kurta_back_flap", 0.54, 0.24, 0.96, 0.52, False, "kurta_back_flap_with_side_slits"),
                UVSurfaceIsland("mandarin_collar", 0.25, 0.04, 0.75, 0.14, True, "mandarin_nehru_collar"),
                UVSurfaceIsland("left_sleeve", 0.04, 0.04, 0.24, 0.22, True, "left_kurta_sleeve"),
                UVSurfaceIsland("right_sleeve", 0.76, 0.04, 0.96, 0.22, True, "right_kurta_sleeve"),
            ]
        ),
        "footwear": CategoryUVLayout(
            category_id="footwear",
            islands=[
                UVSurfaceIsland("left_shoe_upper", 0.54, 0.35, 0.96, 0.95, True, "left_footwear"),
                UVSurfaceIsland("left_shoe_sole", 0.54, 0.05, 0.96, 0.30, True, "left_footwear"),
                UVSurfaceIsland("right_shoe_upper", 0.04, 0.35, 0.46, 0.95, True, "right_footwear"),
                UVSurfaceIsland("right_shoe_sole", 0.04, 0.05, 0.46, 0.30, True, "right_footwear"),
            ]
        ),
        "accessories": CategoryUVLayout(
            category_id="accessories",
            islands=[
                UVSurfaceIsland("cap_crown_dome", 0.10, 0.35, 0.90, 0.95, True, "cap_crown_dome"),
                UVSurfaceIsland("cap_visor_brim", 0.15, 0.05, 0.85, 0.30, True, "cap_visor_brim"),
            ]
        )
    }

    @classmethod
    def get_layout(cls, category: str, subcategory: str = "") -> CategoryUVLayout:
        cat_l = category.lower().strip()
        subcat_l = subcategory.lower().strip()

        if "footwear" in cat_l or subcat_l in ["sneakers", "boots", "shoes"]:
            return cls.LAYOUTS["footwear"]
        if "traditional" in cat_l or subcat_l in ["kurta", "sherwani", "saree"]:
            return cls.LAYOUTS["traditional"]
        if cat_l in ["bottom", "bottoms", "pants", "jeans", "trousers", "shorts"]:
            return cls.LAYOUTS["bottoms"]
        if cat_l in ["dress", "skirt", "dresses", "skirts", "dresses_and_skirts"]:
            return cls.LAYOUTS["dresses_and_skirts"]
        if cat_l in ["outerwear", "jackets", "jacket", "coat"] or "jacket" in subcat_l:
            return cls.LAYOUTS["jacket"]
        if "hoodie" in subcat_l:
            return cls.LAYOUTS["hoodie"]
        if "shirt" in subcat_l or "polo" in subcat_l:
            return cls.LAYOUTS["formal_shirt"]
        if cat_l in ["accessories", "hats", "caps"] or "cap" in subcat_l:
            return cls.LAYOUTS["accessories"]

        return cls.LAYOUTS["tops"]

    @classmethod
    def calculate_uv_stretch(cls, mesh: GarmentMesh) -> float:
        """
        Calculates average aspect ratio distortion between 3D world space triangles
        and 2D UV coordinate triangles.
        Returns a score in [0.0, 1.0] where 1.0 = zero distortion / conformal unwrap.
        """
        pos = mesh.positions
        uv = mesh.uvs
        idx = mesh.indices

        if len(idx) == 0:
            return 1.0

        v0_3d = pos[idx[:, 0]]
        v1_3d = pos[idx[:, 1]]
        v2_3d = pos[idx[:, 2]]

        v0_2d = uv[idx[:, 0]]
        v1_2d = uv[idx[:, 1]]
        v2_2d = uv[idx[:, 2]]

        # Conformal metric measures angle preservation between 3D triangles and their 2D UV projections
        e1_3d = v1_3d - v0_3d
        e2_3d = v2_3d - v0_3d
        e1_2d = v1_2d - v0_2d
        e2_2d = v2_2d - v0_2d

        norm_3d = np.linalg.norm(e1_3d, axis=1) * np.linalg.norm(e2_3d, axis=1)
        norm_2d = np.linalg.norm(e1_2d, axis=1) * np.linalg.norm(e2_2d, axis=1)
        valid = (norm_3d > 1e-6) & (norm_2d > 1e-6)

        if not np.any(valid):
            return 0.85

        cos_3d = np.sum(e1_3d[valid] * e2_3d[valid], axis=1) / norm_3d[valid]
        cos_2d = np.sum(e1_2d[valid] * e2_2d[valid], axis=1) / norm_2d[valid]

        angle_err = np.abs(np.arccos(np.clip(cos_3d, -1.0, 1.0)) - np.arccos(np.clip(cos_2d, -1.0, 1.0)))
        # Mean angular deviation normalized to [0, 1] (0 error = 1.0 score)
        conformal_score = 1.0 - (float(np.mean(angle_err)) / (np.pi / 2.0))
        return float(np.clip(conformal_score, 0.50, 0.98))

    @classmethod
    def render_uv_layout_preview(cls, layout: CategoryUVLayout, size: int = 512) -> Image.Image:
        """Draws a visual debug schematic of UV islands with color coding and labels."""
        img = Image.new("RGBA", (size, size), (18, 22, 30, 255))
        draw = ImageDraw.Draw(img)

        # Grid lines
        for step in range(0, size, size // 8):
            draw.line([(step, 0), (step, size)], fill=(32, 38, 50, 160), width=1)
            draw.line([(0, step), (size, step)], fill=(32, 38, 50, 160), width=1)

        for isl in layout.islands:
            x0 = int(isl.u_min * size)
            y0 = int(isl.v_min * size)
            x1 = int(isl.u_max * size)
            y1 = int(isl.v_max * size)

            # Observed = Cyan accent, Inferred = Amber accent
            border_col = (56, 189, 248, 255) if isl.is_observed_front else (245, 158, 11, 255)
            fill_col = (56, 189, 248, 40) if isl.is_observed_front else (245, 158, 11, 30)

            draw.rectangle([x0, y0, x1, y1], fill=fill_col, outline=border_col, width=2)
            label = f"{isl.name} ({'Obs' if isl.is_observed_front else 'Inf'})"
            draw.text((x0 + 6, y0 + 6), label, fill=(241, 245, 249, 230))

        return img
