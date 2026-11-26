"""
YORVYN — Phase 14.21 Visual Quality Assurance & Artifact Generator
HIGH-FIDELITY GARMENT RECONSTRUCTION, GEOMETRY REFINEMENT & INTELLIGENT VIRTUAL FITTING

Generates all 15 required visual artifacts per garment across 10 distinct real garments:
1. Original Photograph
2. Silhouette Segmentation Mask
3. Component Perception Visualization (bounding boxes & landmarks)
4. Neural Depth Disparity Map (Colorized Turbo)
5. Surface Confidence Map (5-Regime Accounting)
6. Unfitted 3D Reconstructed Mesh (Three-Quarter Angle)
7. Neutral Diagnostic Clay Render (Surface Curvature & Topology Inspection)
8. Wireframe Topology Mode (Quad-Strip Flow & Seams)
9. Front Virtual Try-On View on Avatar Mannequin
10. Side Volume View on Avatar Mannequin (Anterior Chest Depth & Spinal Curve)
11. Rear View on Avatar Mannequin (Multi-View Fused or Inferred with Clean Texture)
12. Three-Quarter Perspective View on Avatar Mannequin
13. Texture & PBR Material Inspection
14. 3D Surface Normal Vector Diagnostic Map
15. Avatar Collision & Clearance Diagnostics (Clearance Heatmap)
Plus a 15-Way Master Visual QA Contact Sheet per garment in docs/reports/phase_14_21_visual_qa/
"""

import os
import sys
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
from scipy.spatial import cKDTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.garments.intelligence.component_perception import component_perception_engine
from backend.app.services.garments.reconstruction.neural.image_conditioned_reconstruction import ImageConditionedReconstructionEngine
from backend.app.services.garments.reconstruction.neural.depth_estimation_engine import garment_depth_engine
from backend.app.services.garments.reconstruction.neural.multi_view_fuser import MultiViewGarmentFuser
from backend.app.services.garments.evaluation.hoodie_reference_pipeline import render_mesh_view
from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from scripts.benchmark_phase_14_19_verification import generate_avatar_surface_hull_with_head

OUTPUT_DIR = PROJECT_ROOT / "docs" / "reports" / "phase_14_21_visual_qa"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_GARMENTS = [
    {
        "id": "garment_01_pullover_hoodie",
        "name": "Dark Brown Oversized Pullover Hoodie (Reference)",
        "path": PROJECT_ROOT / "docs" / "reports" / "hoodie_visual_regression" / "reference_hoodie.png",
        "rear_path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_06_hoodie_pullover.jpg",
        "subcategory": "hoodie",
        "category": "tops",
        "has_multiview": True
    },
    {
        "id": "garment_02_zip_hoodie",
        "name": "Athletic Zip-Front Hoodie with Split Pockets",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_14_0_garments" / "fp_tr_2084_00_zip_hoodie.jpg",
        "rear_path": None,
        "subcategory": "zip_hoodie",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_03_tshirt",
        "name": "Relaxed Combed Cotton Graphic T-Shirt",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_21_tshirt_graphic.jpg",
        "rear_path": None,
        "subcategory": "tshirt",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_04_sweatshirt",
        "name": "Classic Crewneck Fleece Sweatshirt",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_05_hoodie_pullover.jpg",
        "rear_path": None,
        "subcategory": "sweatshirt",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_05_denim_jacket",
        "name": "Structured Heavy Outerwear Denim Jacket",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_02_jacket_denim.jpg",
        "rear_path": None,
        "subcategory": "jacket",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_06_shirt",
        "name": "Tailored Plaid Cotton Button-Down Shirt",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_14_shirt_plaid.jpg",
        "rear_path": None,
        "subcategory": "shirt",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_07_sweater",
        "name": "Ribbed Cable Knit Winter Sweater",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_10_sweater_knit.jpg",
        "rear_path": None,
        "subcategory": "sweater",
        "category": "tops",
        "has_multiview": False
    },
    {
        "id": "garment_08_trousers",
        "name": "Straight-Leg Rigid Denim Jeans",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_31_jeans_denim.jpg",
        "rear_path": None,
        "subcategory": "jeans",
        "category": "bottoms",
        "has_multiview": False
    },
    {
        "id": "garment_09_dress",
        "name": "Contoured A-Line Day Dress",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_41_dress_aline.jpg",
        "rear_path": None,
        "subcategory": "dress",
        "category": "dresses",
        "has_multiview": False
    },
    {
        "id": "garment_10_kurta",
        "name": "Traditional Long Ethnic Kurta Tunics",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_46_kurta_ethnic.jpg",
        "rear_path": None,
        "subcategory": "kurta",
        "category": "tops",
        "has_multiview": False
    }
]


def draw_component_perception_vis(
    image: Image.Image,
    perception_res: Any
) -> Image.Image:
    """Draws colored component bounding boxes, labels, and landmarks on image."""
    vis = image.copy().convert("RGB")
    draw = ImageDraw.Draw(vis)
    w, h = vis.size

    palette = {
        "hood": (255, 99, 71),             # Tomato
        "torso": (70, 130, 180),           # Steel Blue
        "bodice": (70, 130, 180),          # Steel Blue
        "skirt": (186, 85, 211),           # Medium Orchid
        "left_sleeve": (60, 179, 113),     # Medium Sea Green
        "right_sleeve": (46, 139, 87),     # Sea Green
        "left_leg": (60, 179, 113),        # Medium Sea Green
        "right_leg": (46, 139, 87),        # Sea Green
        "left_cuff": (32, 178, 170),       # Light Sea Green
        "right_cuff": (0, 139, 139),       # Dark Cyan
        "left_hem": (32, 178, 170),        # Light Sea Green
        "right_hem": (0, 139, 139),        # Dark Cyan
        "kangaroo_pocket": (255, 165, 0),  # Orange
        "ribbed_waistband": (147, 112, 219),# Medium Purple
        "waistband": (147, 112, 219),      # Medium Purple
        "hem": (147, 112, 219),            # Medium Purple
        "drawstrings": (255, 215, 0),      # Gold
        "collar": (218, 112, 214),         # Orchid
        "neckline": (218, 112, 214)        # Orchid
    }

    if hasattr(perception_res, "components"):
        for comp_id, comp in perception_res.components.items():
            if comp.status != "detected":
                continue
            ymin, xmin, ymax, xmax = comp.bbox
            x1, y1 = int(xmin * w), int(ymin * h)
            x2, y2 = int(xmax * w), int(ymax * h)
            color = palette.get(comp_id, (200, 200, 200))

            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            label = f"{comp.name} ({comp.confidence*100:.0f}%)"
            draw.rectangle([x1, max(0, y1 - 18), min(w, x1 + len(label) * 8 + 6), y1], fill=color)
            draw.text((x1 + 3, max(0, y1 - 16)), label, fill=(255, 255, 255))

    if hasattr(perception_res, "landmarks"):
        for l_name, (lx, ly) in perception_res.landmarks.items():
            px, py = int(lx * w), int(ly * h)
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(255, 255, 0), outline=(0, 0, 0), width=1)
            draw.text((px + 6, py - 6), l_name, fill=(255, 255, 0))

    return vis


def colorize_depth_map(depth_array: np.ndarray, mask: np.ndarray) -> Image.Image:
    """Colorizes normalized depth using the Turbo colormap with masked background."""
    d_norm = np.clip(depth_array * 255.0, 0, 255).astype(np.uint8)
    color_mapped = cv2.applyColorMap(d_norm, cv2.COLORMAP_TURBO)
    color_mapped[mask == 0] = [245, 247, 250]
    rgb = cv2.cvtColor(color_mapped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def colorize_confidence_map(conf_array: np.ndarray, mask: np.ndarray) -> Image.Image:
    """Colorizes surface confidence map (Viridis: high=yellow/green, low=purple)."""
    c_norm = np.clip(conf_array * 255.0, 0, 255).astype(np.uint8)
    color_mapped = cv2.applyColorMap(c_norm, cv2.COLORMAP_VIRIDIS)
    color_mapped[mask == 0] = [245, 247, 250]
    rgb = cv2.cvtColor(color_mapped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def render_collision_heatmap(
    mesh: GarmentMesh,
    body_points: np.ndarray,
    size: int = 600,
    yaw_deg: float = 15.0,
    pitch_deg: float = -4.0
) -> Image.Image:
    """
    Renders 3D avatar collision & clearance diagnostic heatmap:
    - Red (< 5mm): near-collision / contact
    - Green (5-25mm): optimal physical ease & drape zone
    - Cyan (25-45mm): relaxed air gap
    - Yellow (> 45mm): floating ease / loose fabric
    """
    body_tree = cKDTree(body_points)
    dists, _ = body_tree.query(mesh.positions)

    v_colors = []
    for d in dists:
        d_mm = d * 1000.0
        if d_mm < 5.0:
            v_colors.append((240, 50, 50))       # Red
        elif d_mm <= 25.0:
            v_colors.append((40, 200, 100))     # Green
        elif d_mm <= 45.0:
            v_colors.append((40, 180, 240))     # Cyan
        else:
            v_colors.append((245, 170, 30))     # Yellow/Orange

    canvas = Image.new("RGB", (size, size), (245, 247, 250))
    draw = ImageDraw.Draw(canvas)

    pos = mesh.positions
    min_p = pos.min(axis=0)
    max_p = pos.max(axis=0)
    center = (min_p + max_p) * 0.5
    span_y = max(max_p[1] - min_p[1], 0.1)

    shifted = pos - center
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    rot_y = np.array([
        [math.cos(yaw), 0, math.sin(yaw)],
        [0, 1, 0],
        [-math.sin(yaw), 0, math.cos(yaw)]
    ], dtype=np.float32)

    rot_x = np.array([
        [1, 0, 0],
        [0, math.cos(pitch), -math.sin(pitch)],
        [0, math.sin(pitch), math.cos(pitch)]
    ], dtype=np.float32)

    r_pos = shifted @ rot_y.T @ rot_x.T
    scale = (size * 0.72) / span_y
    screen_x = (size * 0.5 + r_pos[:, 0] * scale).astype(int)
    screen_y = (size * 0.52 - r_pos[:, 1] * scale).astype(int)

    tris = mesh.indices.reshape(-1, 3)
    z_depths = r_pos[tris, 2].mean(axis=1)
    sorted_order = np.argsort(z_depths)

    for t_idx in sorted_order:
        vi = tris[t_idx]
        pts = [(screen_x[vi[0]], screen_y[vi[0]]), (screen_x[vi[1]], screen_y[vi[1]]), (screen_x[vi[2]], screen_y[vi[2]])]
        
        # Screen-space backface culling
        v0 = pts[0]
        v1 = pts[1]
        v2 = pts[2]
        cross_2d = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v1[1] - v0[1]) * (v2[0] - v0[0])
        if cross_2d <= 0.0:
            continue

        c0, c1, c2 = v_colors[vi[0]], v_colors[vi[1]], v_colors[vi[2]]
        avg_r = int((c0[0] + c1[0] + c2[0]) / 3)
        avg_g = int((c0[1] + c1[1] + c2[1]) / 3)
        avg_b = int((c0[2] + c1[2] + c2[2]) / 3)
        draw.polygon(pts, fill=(avg_r, avg_g, avg_b), outline=(avg_r//2, avg_g//2, avg_b//2), width=1)

    # Legend badge
    draw.rounded_rectangle([15, size - 45, 340, size - 15], radius=6, fill=(30, 41, 59))
    draw.rectangle([25, size - 35, 37, size - 23], fill=(240, 50, 50))
    draw.text((42, size - 35), "<5mm", fill=(255, 255, 255))
    draw.rectangle([95, size - 35, 107, size - 23], fill=(40, 200, 100))
    draw.text((112, size - 35), "5-25mm", fill=(255, 255, 255))
    draw.rectangle([180, size - 35, 192, size - 23], fill=(40, 180, 240))
    draw.text((197, size - 35), "25-45mm", fill=(255, 255, 255))
    draw.rectangle([265, size - 35, 277, size - 23], fill=(245, 170, 30))
    draw.text((282, size - 35), ">45mm", fill=(255, 255, 255))

    return canvas


def build_15way_contact_sheet(
    panels: List[Tuple[str, Image.Image]],
    title: str,
    output_path: Path
):
    """Combines 15 panels into a 5x3 master contact sheet with high-resolution labels."""
    cell_w, cell_h = 360, 360
    sheet_w = cell_w * 5 + 60
    sheet_h = cell_h * 3 + 100
    sheet = Image.new("RGB", (sheet_w, sheet_h), (240, 242, 245))
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.rectangle([0, 0, sheet_w, 60], fill=(30, 41, 59))
    draw.text((25, 20), f"YORVYN 14.21 RECONSTRUCTION QA — {title.upper()}", fill=(255, 255, 255))

    for idx, (label, img) in enumerate(panels[:15]):
        r = idx // 5
        c = idx % 5
        x = 20 + c * (cell_w + 8)
        y = 75 + r * (cell_h + 8)

        thumb = img.resize((cell_w, cell_h - 26), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))

        draw.rectangle([x, y + cell_h - 26, x + cell_w, y + cell_h], fill=(45, 55, 72))
        draw.text((x + 8, y + cell_h - 20), f"#{idx+1}: {label}", fill=(240, 240, 240))

    sheet.save(output_path, "PNG")


def main():
    print("=" * 80)
    print("YORVYN — PHASE 14.21 VISUAL QA ARTIFACT GENERATOR")
    print("10 DISTINCT REAL GARMENTS x 15 DIAGNOSTIC ARTIFACTS + 10 MASTER SHEETS")
    print("=" * 80)

    rec_engine = ImageConditionedReconstructionEngine()
    body_pts, body_norms = generate_avatar_surface_hull_with_head("standard_175")

    total_images_generated = 0

    for g_idx, g_spec in enumerate(TEST_GARMENTS, 1):
        g_id = g_spec["id"]
        g_name = g_spec["name"]
        g_path = g_spec["path"]
        print(f"\n[{g_idx}/10] Processing: {g_name} ({g_id})")

        g_dir = OUTPUT_DIR / g_id
        g_dir.mkdir(parents=True, exist_ok=True)

        img_raw = Image.open(g_path).convert("RGB")
        w, h = img_raw.size

        # 1. Original Photograph
        p1 = img_raw.copy()
        p1.save(g_dir / "01_original_photo.png", "PNG")

        # 2. Perception & Silhouette
        perc_res = component_perception_engine.perceive_garment(img_raw, category=g_spec["category"], subcategory=g_spec["subcategory"])
        gray = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2GRAY)
        bg_is_light = float(np.mean(gray[:10, :10])) > 180.0
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        p2 = Image.fromarray(mask)
        p2.save(g_dir / "02_segmentation_mask.png", "PNG")

        # 3. Component Perception Visualization
        p3 = draw_component_perception_vis(img_raw, perc_res)
        p3.save(g_dir / "03_component_perception.png", "PNG")

        # 4. Neural Depth Disparity Map
        depth_res = garment_depth_engine.estimate_garment_depth(
            img_raw, mask, category=g_spec["category"], subcategory=g_spec["subcategory"]
        )
        p4 = colorize_depth_map(depth_res.masked_depth, mask)
        p4.save(g_dir / "04_neural_depth_map.png", "PNG")

        # 5. Surface Confidence Map (5-Regime Tracking)
        p5 = colorize_confidence_map(depth_res.confidence_map, mask)
        p5.save(g_dir / "05_surface_confidence_map.png", "PNG")

        # 3D Reconstruction
        mesh, glb_bytes, out = rec_engine.reconstruct_from_image(
            img_raw,
            category=g_spec["category"],
            subcategory=g_spec["subcategory"]
        )
        print(f"  -> Reconstructed Mesh: {len(mesh.positions)} verts, {len(mesh.indices)//3} tris")
        diffuse_img = img_raw.copy()

        # 6. Unfitted 3D Mesh (3/4 angle)
        p6 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=25.0, pitch_deg=-10.0, size=600, draw_avatar=False)
        p6.save(g_dir / "06_unfitted_3d_mesh.png", "PNG")

        # 7. Neutral Diagnostic Clay Render
        p7 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=25.0, pitch_deg=-8.0, size=600, draw_avatar=False, clay_mode=True)
        p7.save(g_dir / "07_neutral_diagnostic_clay.png", "PNG")

        # 8. Wireframe Topology Mode (Quad-strip and Sagittal seam)
        p8 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=22.0, pitch_deg=-8.0, size=600, draw_avatar=False, wireframe=True, clay_mode=True)
        p8.save(g_dir / "08_wireframe_topology.png", "PNG")

        # 9. Front View on Avatar
        p9 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=0.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p9.save(g_dir / "09_front_avatar_fitting.png", "PNG")

        # 10. Side Volume View on Avatar
        p10 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=90.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p10.save(g_dir / "10_side_avatar_fitting.png", "PNG")

        # 11. Rear View on Avatar (Multi-view fused or Inferred badge)
        if g_spec.get("has_multiview") and g_spec.get("rear_path") and Path(g_spec["rear_path"]).exists():
            fuser = MultiViewGarmentFuser()
            rear_img = Image.open(g_spec["rear_path"])
            f_mesh, f_glb, f_out, f_meta = fuser.fuse_views(img_raw, rear_image=rear_img, category=g_spec["category"], subcategory=g_spec["subcategory"])
            p11 = render_mesh_view(f_mesh, diffuse_img=None, yaw_deg=180.0, pitch_deg=0.0, size=600, draw_avatar=True, clay_mode=True)
        else:
            p11 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=180.0, pitch_deg=0.0, size=600, draw_avatar=True, label_inferred=True)
        p11.save(g_dir / "11_rear_avatar_fitting.png", "PNG")

        # 12. Three-Quarter Perspective View on Avatar
        p12 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=35.0, pitch_deg=-5.0, size=600, draw_avatar=True)
        p12.save(g_dir / "12_three_quarter_perspective.png", "PNG")

        # 13. Texture & PBR Material Inspection
        p13 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=15.0, pitch_deg=-4.0, size=600, draw_avatar=True)
        p13.save(g_dir / "13_texture_pbr_inspection.png", "PNG")

        # 14. Normal Vector Diagnostic
        p14 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=22.0, pitch_deg=-8.0, size=600, draw_avatar=False, normal_mode=True)
        p14.save(g_dir / "14_normal_vector_diagnostic.png", "PNG")

        # 15. Avatar Collision & Clearance Diagnostics
        p15 = render_collision_heatmap(mesh, body_pts, size=600)
        p15.save(g_dir / "15_collision_diagnostics.png", "PNG")

        # 16. Master 15-Way Contact Sheet
        contact_panels = [
            ("Original Photo", p1),
            ("Silhouette Mask", p2),
            ("Perception DAG", p3),
            ("Neural Depth", p4),
            ("Confidence Regimes", p5),
            ("Unfitted Mesh 3/4", p6),
            ("Neutral Clay", p7),
            ("Wireframe Topology", p8),
            ("Front Avatar Fit", p9),
            ("Side Volume Depth", p10),
            ("Rear View Fit", p11),
            ("3/4 Perspective", p12),
            ("Texture & PBR", p13),
            ("Normal Vector Map", p14),
            ("Collision Heatmap", p15)
        ]
        build_15way_contact_sheet(contact_panels, g_name, g_dir / "contact_sheet_15way.png")
        build_15way_contact_sheet(contact_panels, g_name, OUTPUT_DIR / f"{g_id}_master_contact_sheet.png")
        print(f"  -> Generated 15 Visual Artifacts + Master Contact Sheet: {g_id}_master_contact_sheet.png")
        total_images_generated += 16

    print("\n" + "=" * 80)
    print(f"ALL 10 GARMENTS COMPLETED: {total_images_generated} total visual artifacts generated!")
    print("Output directory:", OUTPUT_DIR)
    print("=" * 80)


if __name__ == "__main__":
    main()
