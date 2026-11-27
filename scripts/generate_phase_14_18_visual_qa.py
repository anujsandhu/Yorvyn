"""
YORVYN — Phase 14.18 Visual Quality Assurance & Artifact Generator
Generates all 9 required visual artifacts per test garment across 3 distinct hoodies:
1. Original Photograph
2. Segmentation Mask
3. Component Perception Visualization (bounding boxes & landmarks)
4. Unfitted 3D Reconstructed Mesh
5. Front View on Avatar Mannequin
6. Side View on Avatar Mannequin
7. Rear View on Avatar Mannequin (Hidden Surface Inference)
8. Neutral Diagnostic Clay Render (Surface Topology & Shading Inspection)
9. PBR Textured Try-On View
Plus a 3x3 Master Visual QA Contact Sheet per garment.
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
from backend.app.services.garments.evaluation.hoodie_reference_pipeline import render_mesh_view

OUTPUT_DIR = PROJECT_ROOT / "docs" / "reports" / "phase_14_18_visual_qa"
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


def build_9way_contact_sheet(
    panels: List[Tuple[str, Image.Image]],
    title: str,
    output_path: Path
):
    """Combines 9 panels into a 3x3 master contact sheet with high-resolution labels."""
    cell_w, cell_h = 500, 500
    sheet_w, sheet_h = cell_w * 3 + 40, cell_h * 3 + 100
    sheet = Image.new("RGB", (sheet_w, sheet_h), (240, 242, 245))
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.rectangle([0, 0, sheet_w, 60], fill=(30, 41, 59))
    draw.text((25, 20), f"YORVYN 14.18 RECONSTRUCTION QA — {title.upper()}", fill=(255, 255, 255))

    for idx, (label, img) in enumerate(panels[:9]):
        r = idx // 3
        c = idx % 3
        x = 20 + c * (cell_w + 5)
        y = 75 + r * (cell_h + 5)

        # Thumbnail
        thumb = img.resize((cell_w, cell_h - 28), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))

        # Footer label banner
        draw.rectangle([x, y + cell_h - 28, x + cell_w, y + cell_h], fill=(45, 55, 72))
        draw.text((x + 12, y + cell_h - 22), f"Stage {idx+1}: {label}", fill=(240, 240, 240))

    sheet.save(output_path, "PNG")


def main():
    print("=" * 80)
    print("YORVYN — PHASE 14.18 VISUAL QA ARTIFACT GENERATOR")
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
        # Mask
        gray = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2GRAY)
        bg_is_light = float(np.mean(gray[:10, :10])) > 180.0
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        p2 = Image.fromarray(mask)
        p2.save(g_dir / "02_segmentation_mask.png", "PNG")
        print("  -> Saved 02_segmentation_mask.png")

        # 3. Component Perception Visualization
        p3 = draw_component_perception_vis(img_raw, perc_res)
        p3.save(g_dir / "03_component_perception.png", "PNG")
        print("  -> Saved 03_component_perception.png")

        # 3D Reconstruction
        mesh, glb_bytes, out = rec_engine.reconstruct_from_image(
            img_raw,
            category=g_spec["category"],
            subcategory=g_spec["subcategory"]
        )
        print(f"  -> Reconstructed Mesh: {len(mesh.positions)} verts, {len(mesh.indices)//3} tris")
        print(f"     Y bounds: [{mesh.positions[:,1].min():.3f}, {mesh.positions[:,1].max():.3f}], X span: [{mesh.positions[:,0].min():.3f}, {mesh.positions[:,0].max():.3f}]")

        # Texture for renders
        diffuse_img = img_raw.copy()

        # 4. Unfitted 3D Mesh
        p4 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=22.0, pitch_deg=-10.0, size=600, draw_avatar=False)
        p4.save(g_dir / "04_unfitted_3d_mesh.png", "PNG")
        print("  -> Saved 04_unfitted_3d_mesh.png")

        # 5. Front View on Avatar
        p5 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=0.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p5.save(g_dir / "05_front_fitted_avatar.png", "PNG")
        print("  -> Saved 05_front_fitted_avatar.png")

        # 6. Side View on Avatar
        p6 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=90.0, pitch_deg=0.0, size=600, draw_avatar=True)
        p6.save(g_dir / "06_side_fitted_avatar.png", "PNG")
        print("  -> Saved 06_side_fitted_avatar.png")

        # 7. Rear View on Avatar
        p7 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=180.0, pitch_deg=0.0, size=600, draw_avatar=True, label_inferred=True)
        p7.save(g_dir / "07_rear_fitted_avatar.png", "PNG")
        print("  -> Saved 07_rear_fitted_avatar.png")

        # 8. Neutral Diagnostic Clay Render
        p8 = render_mesh_view(mesh, diffuse_img=None, yaw_deg=25.0, pitch_deg=-8.0, size=600, draw_avatar=False, clay_mode=True)
        p8.save(g_dir / "08_neutral_diagnostic_clay.png", "PNG")
        print("  -> Saved 08_neutral_diagnostic_clay.png")

        # 9. PBR Textured Try-On View
        p9 = render_mesh_view(mesh, diffuse_img=diffuse_img, yaw_deg=15.0, pitch_deg=-4.0, size=600, draw_avatar=True)
        p9.save(g_dir / "09_pbr_textured_tryon.png", "PNG")
        print("  -> Saved 09_pbr_textured_tryon.png")

        # 10. Master 3x3 Contact Sheet
        contact_panels = [
            ("Original Photo", p1),
            ("Silhouette Mask", p2),
            ("Component Perception", p3),
            ("Unfitted 3D Mesh", p4),
            ("Front View on Avatar", p5),
            ("Side View on Avatar", p6),
            ("Rear Hidden Surface", p7),
            ("Neutral Diagnostic Clay", p8),
            ("PBR Textured Try-On", p9)
        ]
        build_9way_contact_sheet(contact_panels, g_name, g_dir / "contact_sheet_9way.png")
        # Also copy to root QA dir
        build_9way_contact_sheet(contact_panels, g_name, OUTPUT_DIR / f"{g_id}_contact_sheet.png")
        print(f"  -> Generated Master Contact Sheet: {g_id}_contact_sheet.png")

    print("\n" + "=" * 80)
    print("ALL 3 GARMENTS COMPLETED: 27 Visual Artifacts + 3 Master Contact Sheets Written")
    print(f"Location: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
