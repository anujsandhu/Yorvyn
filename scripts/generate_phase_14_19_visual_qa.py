"""
YORVYN — Phase 14.19 Visual Quality Assurance & Artifact Generator
ADVANCED 3D GARMENT RECONSTRUCTION, NEURAL DEPTH ESTIMATION & PHOTOREALISTIC VIRTUAL FITTING

Generates all 12 required visual artifacts per test garment across 3 distinct hoodies:
1. Original Photograph
2. Silhouette Segmentation Mask
3. Neural Depth Disparity Map (Colorized)
4. Surface Fold & Crease Relief Map
5. Component Perception Visualization (bounding boxes & landmarks)
6. Unfitted 3D Reconstructed Mesh (Three-Quarter Angle)
7. Neutral Diagnostic Clay Render (Surface Curvature & Topology Inspection)
8. Wireframe Topology Mode (Quad-Strip Flow & Sagittal Seam Inspection)
9. 3D Surface Normal Vector Diagnostic Map
10. Front Virtual Try-On View on Avatar Mannequin
11. Side Volume View on Avatar Mannequin (Anterior Chest Depth & Back Curve)
12. Rear View on Avatar Mannequin (Hidden Surface Inference with Confidence Banner)
Plus a 12-Way Master Visual QA Contact Sheet per garment in docs/reports/phase_14_19_visual_qa/
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.garments.intelligence.component_perception import component_perception_engine
from backend.app.services.garments.reconstruction.neural.image_conditioned_reconstruction import ImageConditionedReconstructionEngine
from backend.app.services.garments.reconstruction.neural.depth_estimation_engine import garment_depth_engine
from backend.app.services.garments.evaluation.hoodie_reference_pipeline import render_mesh_view

OUTPUT_DIR = PROJECT_ROOT / "docs" / "reports" / "phase_14_19_visual_qa"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_GARMENTS = [
    {
        "id": "garment_1_oversized_pullover",
        "name": "Dark Brown Oversized Pullover Hoodie (Reference)",
        "path": PROJECT_ROOT / "docs" / "reports" / "hoodie_visual_regression" / "reference_hoodie.png",
        "subcategory": "hoodie",
        "category": "tops"
    },
    {
        "id": "garment_2_zip_hoodie",
        "name": "Athletic Zip-Front Hoodie with Split Pockets",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_14_0_garments" / "fp_tr_2084_00_zip_hoodie.jpg",
        "subcategory": "zip_hoodie",
        "category": "tops"
    },
    {
        "id": "garment_3_upright_pullover",
        "name": "Classic Upright Cowl Pullover Hoodie",
        "path": PROJECT_ROOT / "data" / "datasets" / "phase_13_6_real_photos" / "wm_05_hoodie_pullover.jpg",
        "subcategory": "hoodie",
        "category": "tops"
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
        "hood": (255, 99, 71),          # Tomato
        "torso": (70, 130, 180),        # Steel Blue
        "left_sleeve": (60, 179, 113),  # Medium Sea Green
        "right_sleeve": (46, 139, 87),  # Sea Green
        "left_cuff": (32, 178, 170),    # Light Sea Green
        "right_cuff": (0, 139, 139),    # Dark Cyan
        "kangaroo_pocket": (255, 165, 0), # Orange
        "ribbed_waistband": (147, 112, 219), # Medium Purple
        "drawstrings": (255, 215, 0)    # Gold
    }

    for comp_id, comp in perception_res.components.items():
        if comp.status != "detected":
            continue
        ymin, xmin, ymax, xmax = comp.bbox
        x1, y1 = int(xmin * w), int(ymin * h)
        x2, y2 = int(xmax * w), int(ymax * h)
        color = palette.get(comp_id, (200, 200, 200))

        # Box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        # Label banner
        label = f"{comp.name} ({comp.confidence*100:.0f}%)"
        draw.rectangle([x1, max(0, y1 - 18), min(w, x1 + len(label) * 8 + 6), y1], fill=color)
        draw.text((x1 + 3, max(0, y1 - 16)), label, fill=(255, 255, 255))

    # Landmarks
    for l_name, (lx, ly) in perception_res.landmarks.items():
        px, py = int(lx * w), int(ly * h)
        draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(255, 255, 0), outline=(0, 0, 0), width=1)
        draw.text((px + 6, py - 6), l_name, fill=(255, 255, 0))

    return vis


def colorize_depth_map(depth_array: np.ndarray, mask: np.ndarray) -> Image.Image:
    """Colorizes normalized depth using the Turbo colormap with masked background."""
    d_norm = np.clip(depth_array * 255.0, 0, 255).astype(np.uint8)
    color_mapped = cv2.applyColorMap(d_norm, cv2.COLORMAP_TURBO)
    color_mapped[mask == 0] = [245, 247, 250]  # Clean neutral background
    rgb = cv2.cvtColor(color_mapped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def colorize_fold_relief(fold_array: np.ndarray, mask: np.ndarray) -> Image.Image:
    """Colorizes fold relief map using Inferno colormap."""
    f_norm = np.clip(fold_array * 255.0, 0, 255).astype(np.uint8)
    color_mapped = cv2.applyColorMap(f_norm, cv2.COLORMAP_INFERNO)
    color_mapped[mask == 0] = [245, 247, 250]
    rgb = cv2.cvtColor(color_mapped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def build_12way_contact_sheet(
    panels: List[Tuple[str, Image.Image]],
    title: str,
    output_path: Path
):
    """Combines 12 panels into a 4x3 master contact sheet with high-resolution labels."""
    cell_w, cell_h = 420, 420
    sheet_w, sheet_h = cell_w * 4 + 50, cell_h * 3 + 100
    sheet = Image.new("RGB", (sheet_w, sheet_h), (240, 242, 245))
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.rectangle([0, 0, sheet_w, 60], fill=(30, 41, 59))
    draw.text((25, 20), f"YORVYN 14.19 RECONSTRUCTION QA — {title.upper()}", fill=(255, 255, 255))

    for idx, (label, img) in enumerate(panels[:12]):
        r = idx // 4
        c = idx % 4
        x = 20 + c * (cell_w + 8)
        y = 75 + r * (cell_h + 8)

        # Thumbnail
        thumb = img.resize((cell_w, cell_h - 28), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))

        # Footer label banner
        draw.rectangle([x, y + cell_h - 28, x + cell_w, y + cell_h], fill=(45, 55, 72))
        draw.text((x + 10, y + cell_h - 22), f"Stage {idx+1}: {label}", fill=(240, 240, 240))

    sheet.save(output_path, "PNG")


def main():
    print("=" * 80)
    print("YORVYN — PHASE 14.19 VISUAL QA ARTIFACT GENERATOR")
    print("ADVANCED 3D GARMENT RECONSTRUCTION & NEURAL DEPTH ESTIMATION")
    print("=" * 80)

    rec_engine = ImageConditionedReconstructionEngine()

    for g_idx, g_spec in enumerate(TEST_GARMENTS, 1):
        g_id = g_spec["id"]
        g_name = g_spec["name"]
        g_path = g_spec["path"]
        print(f"\n[{g_idx}/3] Processing: {g_name} ({g_id})")

        g_dir = OUTPUT_DIR / g_id
        g_dir.mkdir(parents=True, exist_ok=True)

        img_raw = Image.open(g_path).convert("RGB")
        w, h = img_raw.size

        # 1. Original Photograph
        p1 = img_raw.copy()
        p1.save(g_dir / "01_original_photo.png", "PNG")
        print("  -> Saved 01_original_photo.png")

        # 2. Perception & Silhouette
        perc_res = component_perception_engine.perceive_hoodie(img_raw)
        gray = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2GRAY)
        bg_is_light = float(np.mean(gray[:10, :10])) > 180.0
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        p2 = Image.fromarray(mask)
        p2.save(g_dir / "02_segmentation_mask.png", "PNG")
        print("  -> Saved 02_segmentation_mask.png")

        # 3. Neural Depth Disparity Map
        depth_res = garment_depth_engine.estimate_garment_depth(
            img_raw, mask, category=g_spec["category"], subcategory=g_spec["subcategory"]
        )
        p3 = colorize_depth_map(depth_res.masked_depth, mask)
        p3.save(g_dir / "03_neural_depth_map.png", "PNG")
        print("  -> Saved 03_neural_depth_map.png")

        # 4. Surface Fold Relief Map
        p4 = colorize_fold_relief(depth_res.fold_map, mask)
        p4.save(g_dir / "04_surface_fold_relief.png", "PNG")
        print("  -> Saved 04_surface_fold_relief.png")

        # 5. Component Perception Visualization
        p5 = draw_component_perception_vis(img_raw, perc_res)
        p5.save(g_dir / "05_component_perception.png", "PNG")
        print("  -> Saved 05_component_perception.png")

        # 3D Reconstruction
        mesh, glb_bytes, out = rec_engine.reconstruct_from_image(
            img_raw,
            category=g_spec["category"],
            subcategory=g_spec["subcategory"]
        )
        print(f"  -> Reconstructed Mesh: {len(mesh.positions)} verts, {len(mesh.indices)//3} tris")
        print(f"     Y bounds: [{mesh.positions[:,1].min():.3f}, {mesh.positions[:,1].max():.3f}], X span: [{mesh.positions[:,0].min():.3f}, {mesh.positions[:,0].max():.3f}]")

        diffuse_img = img_raw.copy()

        # 6. Unfitted 3D Mesh (3/4 angle)
        p6 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=25.0, pitch_deg=-10.0, size=600, draw_avatar=False)
        p6.save(g_dir / "06_unfitted_3d_mesh.png", "PNG")
        print("  -> Saved 06_unfitted_3d_mesh.png")

        # 7. Neutral Diagnostic Clay Render
        p7 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=25.0, pitch_deg=-8.0, size=600, draw_avatar=False, clay_mode=True)
        p7.save(g_dir / "07_neutral_diagnostic_clay.png", "PNG")
        print("  -> Saved 07_neutral_diagnostic_clay.png")

        # 8. Wireframe Topology Mode (Quad-strip and Sagittal seam)
        p8 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=22.0, pitch_deg=-8.0, size=600, draw_avatar=False, wireframe=True, clay_mode=True)
        p8.save(g_dir / "08_wireframe_topology.png", "PNG")
        print("  -> Saved 08_wireframe_topology.png")

        # 9. Normal Vector Diagnostic
        p9 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=22.0, pitch_deg=-8.0, size=600, draw_avatar=False, normal_mode=True)
        p9.save(g_dir / "09_normal_vector_diagnostic.png", "PNG")
        print("  -> Saved 09_normal_vector_diagnostic.png")

        # 10. Front View on Avatar
        p10 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=0.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p10.save(g_dir / "10_front_fitted_avatar.png", "PNG")
        print("  -> Saved 10_front_fitted_avatar.png")

        # 11. Side Volume View on Avatar (Anterior Chest Depth & Back Curve)
        p11 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=90.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p11.save(g_dir / "11_side_volume_avatar.png", "PNG")
        print("  -> Saved 11_side_volume_avatar.png")

        # 12. Rear View on Avatar (Hidden Surface Inference with Badge)
        p12 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=180.0, pitch_deg=0.0, size=600, draw_avatar=True, label_inferred=True)
        p12.save(g_dir / "12_rear_fitted_avatar.png", "PNG")
        print("  -> Saved 12_rear_fitted_avatar.png")

        # 13. Master 12-way Contact Sheet
        contact_panels = [
            ("Original Photo", p1),
            ("Silhouette Mask", p2),
            ("Neural Depth Disparity", p3),
            ("Surface Fold Relief", p4),
            ("Component Perception", p5),
            ("Unfitted 3D Mesh", p6),
            ("Neutral Diagnostic Clay", p7),
            ("Wireframe Topology", p8),
            ("Normal Vector Map", p9),
            ("Front Try-On Avatar", p10),
            ("Side Volume Depth", p11),
            ("Rear Inferred Surface", p12)
        ]
        build_12way_contact_sheet(contact_panels, g_name, g_dir / "contact_sheet_12way.png")
        build_12way_contact_sheet(contact_panels, g_name, OUTPUT_DIR / f"{g_id}_contact_sheet.png")
        print(f"  -> Generated Master Contact Sheet: {g_id}_contact_sheet.png")

    print("\n" + "=" * 80)
    print("ALL 3 GARMENTS COMPLETED: 36 Visual Artifacts + 3 Master Contact Sheets Written")
    print("Output directory:", OUTPUT_DIR)
    print("=" * 80)


if __name__ == "__main__":
    main()
