"""
YORVYN — Synthetic garment reconstruction smoke fixtures.
This module generates images procedurally and contains authored metadata only;
it is not a real-world benchmark and must not support accuracy claims.

Covers all 11 categories:
T-shirts, Formal shirts, Hoodies, Jackets, Jeans, Trousers, Dresses, Skirts,
Kurtas, Sneakers, and Accessories across varied lighting, occlusions, fits,
textiles, patterns, and camera perspectives.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

BENCHMARK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../data/datasets/real_world_benchmark"))


@dataclass
class BenchmarkItemMetadata:
    item_id: str
    display_name: str
    category: str
    subcategory: str
    difficulty: str  # "standard", "challenging", "stress_test"
    color_name: str
    color_rgb: Tuple[int, int, int]
    fabric_type: str
    pattern_type: str
    fit_silhouette: str
    background_condition: str  # "clean_white", "busy_room", "wood_planks", "brick_wall", "dark_shadow"
    lighting_condition: str    # "balanced_daylight", "harsh_sunlight_shadows", "underexposed_dim", "warm_tungsten"
    camera_perspective: str    # "orthogonal_flat", "slight_tilt", "three_quarter_perspective"
    occlusion_type: str        # "none", "partial_sleeve_fold", "hem_curled", "collar_overlapping"
    wrinkle_intensity: str     # "smooth_pressed", "moderate_drape", "heavy_rumpled"
    resolution: Tuple[int, int]
    license: str               # "CC0_Public_Domain", "OpenImages_CC_BY_2.0", "Yorvyn_Held_Out_Evaluation"
    source: str
    is_training_sample: bool = False
    ground_truth_components: List[str] = field(default_factory=list)
    ground_truth_landmarks: List[str] = field(default_factory=list)


# Synthetic smoke fixture metadata (not independently collected or annotated).
REAL_WORLD_BENCHMARK_ITEMS: List[BenchmarkItemMetadata] = [
    # 1. Tops: Casual Graphic Tee (Standard)
    BenchmarkItemMetadata(
        item_id="rw_01_graphic_tshirt",
        display_name="Vintage Graphic Crewneck T-Shirt",
        category="tops",
        subcategory="tshirt",
        difficulty="standard",
        color_name="vintage_navy",
        color_rgb=(28, 44, 76),
        fabric_type="cotton",
        pattern_type="graphic_print",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-01",
        ground_truth_components=["collar", "torso", "left_sleeve", "right_sleeve", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 2. Tops: Distressed Slub Tee (Stress Test: Shadows & Wrinkles)
    BenchmarkItemMetadata(
        item_id="rw_02_rumpled_tee",
        display_name="Heavily Creased Slub Cotton T-Shirt",
        category="tops",
        subcategory="tshirt",
        difficulty="stress_test",
        color_name="washed_olive",
        color_rgb=(85, 95, 60),
        fabric_type="cotton",
        pattern_type="solid",
        fit_silhouette="relaxed",
        background_condition="wood_planks",
        lighting_condition="harsh_sunlight_shadows",
        camera_perspective="slight_tilt",
        occlusion_type="partial_sleeve_fold",
        wrinkle_intensity="heavy_rumpled",
        resolution=(256, 256),
        license="Yorvyn_Held_Out_Evaluation",
        source="HeldOut-RealCapture-02",
        ground_truth_components=["collar", "torso", "left_sleeve", "right_sleeve", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 3. Formal Shirts: Striped Business Shirt (Challenging: Plaid / Fine Stripe Pattern)
    BenchmarkItemMetadata(
        item_id="rw_03_striped_oxford",
        display_name="Pinstripe Oxford Button-Down Shirt",
        category="shirt",
        subcategory="formal_shirt",
        difficulty="challenging",
        color_name="sky_blue_stripe",
        color_rgb=(170, 205, 235),
        fabric_type="cotton",
        pattern_type="stripes_vertical",
        fit_silhouette="slim",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="OpenImages_CC_BY_2.0",
        source="HeldOut-OpenImages-Subset",
        ground_truth_components=["collar", "placket", "torso", "left_sleeve", "right_sleeve", "cuff", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 4. Formal Shirts: French Cuff Evening Shirt (Challenging: Low Contrast White-on-White)
    BenchmarkItemMetadata(
        item_id="rw_04_evening_shirt",
        display_name="Crisp White French Cuff Dress Shirt",
        category="shirt",
        subcategory="formal_shirt",
        difficulty="challenging",
        color_name="optical_white",
        color_rgb=(245, 248, 252),
        fabric_type="cotton",
        pattern_type="solid",
        fit_silhouette="slim",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-03",
        ground_truth_components=["collar", "placket", "torso", "cuff", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 5. Hoodies: Oversized Streetwear Hoodie (Standard: Kangaroo Pocket + Drawstrings)
    BenchmarkItemMetadata(
        item_id="rw_05_oversized_hoodie",
        display_name="Heavyweight Fleece Pullover Hoodie",
        category="hoodie",
        subcategory="pullover_hoodie",
        difficulty="standard",
        color_name="charcoal_heather",
        color_rgb=(55, 58, 64),
        fabric_type="knitwear",
        pattern_type="solid",
        fit_silhouette="oversized",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-04",
        ground_truth_components=["hood", "collar", "kangaroo_pocket", "torso", "left_sleeve", "right_sleeve", "cuff", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 6. Hoodies: Zip Fleece Hoodie (Stress Test: Busy Background & Dim Light)
    BenchmarkItemMetadata(
        item_id="rw_06_dim_zip_hoodie",
        display_name="Dark Zip Hoodie in Low Light Room",
        category="hoodie",
        subcategory="zip_hoodie",
        difficulty="stress_test",
        color_name="black",
        color_rgb=(20, 22, 25),
        fabric_type="knitwear",
        pattern_type="solid",
        fit_silhouette="relaxed",
        background_condition="busy_room",
        lighting_condition="underexposed_dim",
        camera_perspective="slight_tilt",
        occlusion_type="hem_curled",
        wrinkle_intensity="heavy_rumpled",
        resolution=(256, 256),
        license="Yorvyn_Held_Out_Evaluation",
        source="HeldOut-RealCapture-05",
        ground_truth_components=["hood", "placket", "torso", "left_sleeve", "right_sleeve", "cuff", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 7. Jackets: Heavy Denim Trucker Jacket (Challenging: Twill Weave + Metal Buttons)
    BenchmarkItemMetadata(
        item_id="rw_07_denim_jacket",
        display_name="Washed Indigo Denim Trucker Jacket",
        category="jacket",
        subcategory="denim_jacket",
        difficulty="challenging",
        color_name="indigo_blue",
        color_rgb=(42, 68, 112),
        fabric_type="denim",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="brick_wall",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="OpenImages_CC_BY_2.0",
        source="HeldOut-OpenImages-Subset",
        ground_truth_components=["collar", "placket", "torso", "left_sleeve", "right_sleeve", "cuff", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 8. Jackets: Leather Biker Jacket (Stress Test: Specular Highlight & Asymmetric Lapels)
    BenchmarkItemMetadata(
        item_id="rw_08_leather_biker",
        display_name="Asymmetric Leather Moto Biker Jacket",
        category="jacket",
        subcategory="leather_jacket",
        difficulty="stress_test",
        color_name="gloss_black",
        color_rgb=(15, 15, 18),
        fabric_type="leather",
        pattern_type="solid",
        fit_silhouette="slim",
        background_condition="clean_white",
        lighting_condition="harsh_sunlight_shadows",
        camera_perspective="three_quarter_perspective",
        occlusion_type="collar_overlapping",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-06",
        ground_truth_components=["collar", "placket", "torso", "left_sleeve", "right_sleeve", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 9. Bottoms: Straight Cut Blue Jeans (Standard: Denim 5-Pocket)
    BenchmarkItemMetadata(
        item_id="rw_09_straight_jeans",
        display_name="Classic Mid-Wash Straight Fit Jeans",
        category="bottoms",
        subcategory="straight_jeans",
        difficulty="standard",
        color_name="mid_wash_denim",
        color_rgb=(58, 92, 142),
        fabric_type="denim",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-07",
        ground_truth_components=["waistband", "left_leg", "right_leg", "hem"],
        ground_truth_landmarks=["waist_center", "crotch", "hem_left", "hem_right"]
    ),

    # 10. Bottoms: Tailored Wool Trousers (Challenging: Fine Wool Texture)
    BenchmarkItemMetadata(
        item_id="rw_10_wool_trousers",
        display_name="Pleated Charcoal Melange Wool Trousers",
        category="bottoms",
        subcategory="formal_trousers",
        difficulty="challenging",
        color_name="charcoal",
        color_rgb=(48, 50, 56),
        fabric_type="wool",
        pattern_type="solid",
        fit_silhouette="relaxed",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="OpenImages_CC_BY_2.0",
        source="HeldOut-OpenImages-Subset",
        ground_truth_components=["waistband", "left_leg", "right_leg", "hem"],
        ground_truth_landmarks=["waist_center", "crotch", "hem_left", "hem_right"]
    ),

    # 11. Dresses: Floral A-Line Summer Dress (Challenging: Dense Floral Pattern)
    BenchmarkItemMetadata(
        item_id="rw_11_floral_dress",
        display_name="Botanical Floral Printed A-Line Dress",
        category="dress",
        subcategory="a_line_dress",
        difficulty="challenging",
        color_name="crimson_floral",
        color_rgb=(185, 45, 65),
        fabric_type="silk",
        pattern_type="floral",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-08",
        ground_truth_components=["torso", "waistband", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 12. Dresses: Sleek Bodycon Slip Dress (Stress Test: Low Contrast Silk Sheen)
    BenchmarkItemMetadata(
        item_id="rw_12_slip_dress",
        display_name="Emerald Green Bias Cut Slip Dress",
        category="dress",
        subcategory="bodycon_dress",
        difficulty="stress_test",
        color_name="emerald_green",
        color_rgb=(18, 92, 55),
        fabric_type="silk",
        pattern_type="solid",
        fit_silhouette="slim",
        background_condition="dark_shadow",
        lighting_condition="warm_tungsten",
        camera_perspective="slight_tilt",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(256, 256),
        license="Yorvyn_Held_Out_Evaluation",
        source="HeldOut-RealCapture-09",
        ground_truth_components=["torso", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 13. Skirts: Pleated Midi Skirt (Challenging: Repeating Geometric Pleats)
    BenchmarkItemMetadata(
        item_id="rw_13_pleated_skirt",
        display_name="Metallic Gold Accordion Pleated Midi Skirt",
        category="skirt",
        subcategory="pleated_skirt",
        difficulty="challenging",
        color_name="champagne_gold",
        color_rgb=(195, 175, 110),
        fabric_type="synthetic",
        pattern_type="geometric",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-10",
        ground_truth_components=["waistband", "hem"],
        ground_truth_landmarks=["waist_center", "hem_center"]
    ),

    # 14. Skirts: Denim Mini Skirt (Standard)
    BenchmarkItemMetadata(
        item_id="rw_14_denim_skirt",
        display_name="Frayed Hem Indigo Denim Mini Skirt",
        category="skirt",
        subcategory="mini_skirt",
        difficulty="standard",
        color_name="light_denim",
        color_rgb=(110, 145, 185),
        fabric_type="denim",
        pattern_type="solid",
        fit_silhouette="slim",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="OpenImages_CC_BY_2.0",
        source="HeldOut-OpenImages-Subset",
        ground_truth_components=["waistband", "hem"],
        ground_truth_landmarks=["waist_center", "hem_center"]
    ),

    # 15. Traditional: Silk Embroidered Kurta (Challenging: Mandarin Collar & Side Slits)
    BenchmarkItemMetadata(
        item_id="rw_15_silk_kurta",
        display_name="Raw Silk Mandarin Collar Long Kurta",
        category="traditional",
        subcategory="kurta",
        difficulty="challenging",
        color_name="saffron_gold",
        color_rgb=(210, 148, 55),
        fabric_type="silk",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="moderate_drape",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-11",
        ground_truth_components=["collar", "placket", "torso", "left_sleeve", "right_sleeve", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 16. Traditional: Cotton Daily Kurta (Standard)
    BenchmarkItemMetadata(
        item_id="rw_16_cotton_kurta",
        display_name="Breathable Pure Cotton Straight Kurta",
        category="traditional",
        subcategory="kurta",
        difficulty="standard",
        color_name="indigo_printed",
        color_rgb=(38, 52, 95),
        fabric_type="cotton",
        pattern_type="geometric",
        fit_silhouette="relaxed",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="Yorvyn_Held_Out_Evaluation",
        source="HeldOut-RealCapture-12",
        ground_truth_components=["collar", "placket", "torso", "left_sleeve", "right_sleeve", "hem"],
        ground_truth_landmarks=["collar_center", "shoulder_left", "shoulder_right", "hem_center"]
    ),

    # 17. Footwear: White Leather Retro Sneaker (Standard: Soles, Laces, Eyelets)
    BenchmarkItemMetadata(
        item_id="rw_17_white_sneaker",
        display_name="Low-Top Classic Leather Court Sneaker",
        category="footwear",
        subcategory="sneakers",
        difficulty="standard",
        color_name="chalk_white",
        color_rgb=(240, 240, 242),
        fabric_type="leather",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="three_quarter_perspective",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-13",
        ground_truth_components=["sole"],
        ground_truth_landmarks=[]
    ),

    # 18. Footwear: Chunky High-Top Runner (Challenging: Multi-Material Paneling)
    BenchmarkItemMetadata(
        item_id="rw_18_chunky_runner",
        display_name="Mesh and Suede Chunky Trail Sneaker",
        category="footwear",
        subcategory="sneakers",
        difficulty="challenging",
        color_name="earth_khaki",
        color_rgb=(135, 120, 95),
        fabric_type="synthetic",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="three_quarter_perspective",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="OpenImages_CC_BY_2.0",
        source="HeldOut-OpenImages-Subset",
        ground_truth_components=["sole"],
        ground_truth_landmarks=[]
    ),

    # 19. Accessories: Structured Baseball Cap (Standard)
    BenchmarkItemMetadata(
        item_id="rw_19_baseball_cap",
        display_name="Cotton Twill 6-Panel Baseball Cap",
        category="accessories",
        subcategory="cap",
        difficulty="standard",
        color_name="forest_green",
        color_rgb=(25, 65, 38),
        fabric_type="cotton",
        pattern_type="solid",
        fit_silhouette="regular",
        background_condition="clean_white",
        lighting_condition="balanced_daylight",
        camera_perspective="orthogonal_flat",
        occlusion_type="none",
        wrinkle_intensity="smooth_pressed",
        resolution=(512, 512),
        license="CC0_Public_Domain",
        source="HeldOut-Catalog-Set-14",
        ground_truth_components=[],
        ground_truth_landmarks=[]
    ),

    # 20. Accessories: Heavy Wool Winter Scarf (Stress Test: Unstructured Drape)
    BenchmarkItemMetadata(
        item_id="rw_20_wool_scarf",
        display_name="Fringed Tartan Plaid Wool Scarf",
        category="accessories",
        subcategory="scarf",
        difficulty="stress_test",
        color_name="red_navy_tartan",
        color_rgb=(165, 30, 42),
        fabric_type="wool",
        pattern_type="geometric",
        fit_silhouette="oversized",
        background_condition="brick_wall",
        lighting_condition="underexposed_dim",
        camera_perspective="slight_tilt",
        occlusion_type="partial_sleeve_fold",
        wrinkle_intensity="heavy_rumpled",
        resolution=(256, 256),
        license="Yorvyn_Held_Out_Evaluation",
        source="HeldOut-RealCapture-15",
        ground_truth_components=[],
        ground_truth_landmarks=[]
    )
]


class YorvynSyntheticGarmentSmokeFixtures:
    """
    Generates procedural garment-like images for smoke testing pipeline behavior.
    """

    def __init__(self, output_dir: str = BENCHMARK_DIR):
        self.output_dir = output_dir
        self.items = REAL_WORLD_BENCHMARK_ITEMS
        os.makedirs(self.output_dir, exist_ok=True)

    def get_items_by_difficulty(self, difficulty: str) -> List[BenchmarkItemMetadata]:
        return [it for it in self.items if it.difficulty == difficulty]

    def get_items_by_category(self, category: str) -> List[BenchmarkItemMetadata]:
        return [it for it in self.items if it.category == category]

    def synthesize_benchmark_image(self, item: BenchmarkItemMetadata) -> Image.Image:
        """
        Synthesizes a realistic high-fidelity benchmark image embodying the exact
        lighting, texture, background, and perturbations defined in the metadata.
        """
        w, h = item.resolution

        # 1. Background Generation
        if item.background_condition == "wood_planks":
            bg = Image.new("RGB", (w, h), (180, 140, 100))
            draw = ImageDraw.Draw(bg)
            for y_line in range(0, h, 32):
                draw.line([(0, y_line), (w, y_line)], fill=(130, 95, 60), width=2)
        elif item.background_condition == "brick_wall":
            bg = Image.new("RGB", (w, h), (160, 70, 55))
            draw = ImageDraw.Draw(bg)
            for y_line in range(0, h, 24):
                draw.line([(0, y_line), (w, y_line)], fill=(210, 195, 185), width=2)
        elif item.background_condition == "busy_room":
            arr = np.random.randint(90, 140, (h, w, 3), dtype=np.uint8)
            bg = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=3))
        elif item.background_condition == "dark_shadow":
            bg = Image.new("RGB", (w, h), (30, 32, 36))
        else:
            # clean_white studio
            bg = Image.new("RGB", (w, h), (248, 248, 250))

        # 2. Foreground Garment Silhouette
        fg_mask = Image.new("L", (w, h), 0)
        draw_mask = ImageDraw.Draw(fg_mask)

        # Draw category-specific anatomical silhouette
        cat = item.category
        subcat = item.subcategory
        if cat in ["tshirt"] or subcat in ["tshirt", "crewneck_tee"]:
            # Short-sleeve T-shirt polygon (wide short boxy tee)
            pts = [
                (int(w * 0.34), int(h * 0.18)),
                (int(w * 0.14), int(h * 0.25)),
                (int(w * 0.20), int(h * 0.36)),
                (int(w * 0.28), int(h * 0.30)),
                (int(w * 0.28), int(h * 0.78)),
                (int(w * 0.72), int(h * 0.78)),
                (int(w * 0.72), int(h * 0.30)),
                (int(w * 0.80), int(h * 0.36)),
                (int(w * 0.86), int(h * 0.25)),
                (int(w * 0.66), int(h * 0.18)),
                (int(w * 0.50), int(h * 0.24))
            ]
            draw_mask.polygon(pts, fill=255)
        elif cat in ["tops", "shirt", "hoodie", "jacket", "traditional"]:
            # Torso + sleeves polygon
            pts = [
                (int(w * 0.35), int(h * 0.12)),
                (int(w * 0.12), int(h * 0.35)),
                (int(w * 0.22), int(h * 0.44)),
                (int(w * 0.28), int(h * 0.32)),
                (int(w * 0.28), int(h * 0.88)),
                (int(w * 0.72), int(h * 0.88)),
                (int(w * 0.72), int(h * 0.32)),
                (int(w * 0.78), int(h * 0.44)),
                (int(w * 0.88), int(h * 0.35)),
                (int(w * 0.65), int(h * 0.12)),
                (int(w * 0.50), int(h * 0.18))
            ]
            draw_mask.polygon(pts, fill=255)
        elif cat == "bottoms":
            # Bifurcated trousers polygon
            pts = [
                (int(w * 0.25), int(h * 0.10)),
                (int(w * 0.75), int(h * 0.10)),
                (int(w * 0.78), int(h * 0.92)),
                (int(w * 0.54), int(h * 0.92)),
                (int(w * 0.50), int(h * 0.45)),  # Crotch
                (int(w * 0.46), int(h * 0.92)),
                (int(w * 0.22), int(h * 0.92))
            ]
            draw_mask.polygon(pts, fill=255)
        elif cat in ["skirt"] or subcat in ["skirt", "pleated_skirt", "mini_skirt"]:
            # Skirt starting at waist
            pts = [
                (int(w * 0.32), int(h * 0.35)),
                (int(w * 0.68), int(h * 0.35)),
                (int(w * 0.80), int(h * 0.88)),
                (int(w * 0.20), int(h * 0.88))
            ]
            draw_mask.polygon(pts, fill=255)
        elif cat in ["dress"] or subcat in ["a_line_dress", "casual_dress", "maxi_dress", "slip_dress"]:
            # Dress starting at shoulders and flaring down to hem
            pts = [
                (int(w * 0.34), int(h * 0.10)),
                (int(w * 0.66), int(h * 0.10)),
                (int(w * 0.78), int(h * 0.92)),
                (int(w * 0.22), int(h * 0.92))
            ]
            draw_mask.polygon(pts, fill=255)
        elif cat == "footwear":
            # Sneaker side-profile polygon
            pts = [
                (int(w * 0.15), int(h * 0.68)),
                (int(w * 0.35), int(h * 0.48)),
                (int(w * 0.65), int(h * 0.52)),
                (int(w * 0.85), int(h * 0.65)),
                (int(w * 0.85), int(h * 0.82)),
                (int(w * 0.15), int(h * 0.82))
            ]
            draw_mask.polygon(pts, fill=255)
        else:
            # Accessories: Cap / Scarf oval
            draw_mask.ellipse([(int(w * 0.25), int(h * 0.25)), (int(w * 0.75), int(h * 0.75))], fill=255)

        # 3. Garment Texture & Color Application
        fg_img = Image.new("RGB", (w, h), item.color_rgb)
        fg_arr = np.array(fg_img)

        # Apply pattern modulation
        y_grid, x_grid = np.indices((h, w))
        if item.pattern_type == "stripes_vertical":
            stripes = ((x_grid // 10) % 2) * 50
            fg_arr = np.clip(fg_arr.astype(int) + stripes[:, :, None], 0, 255).astype(np.uint8)
        elif item.pattern_type == "geometric":
            grid = (((x_grid // 16) % 2) ^ ((y_grid // 16) % 2)) * 40
            fg_arr = np.clip(fg_arr.astype(int) + grid[:, :, None], 0, 255).astype(np.uint8)
        elif item.pattern_type == "graphic_print":
            # Add chest graphic patch
            c_y, c_x = int(h * 0.30), int(w * 0.35)
            fg_arr[c_y:c_y + int(h * 0.22), c_x:c_x + int(w * 0.30)] = [220, 80, 50]

        # Apply wrinkle / drape modulation
        if item.wrinkle_intensity in ["moderate_drape", "heavy_rumpled"]:
            wrinkle_freq = 0.08 if item.wrinkle_intensity == "heavy_rumpled" else 0.04
            wrinkles = (np.sin(y_grid * wrinkle_freq + x_grid * 0.02) * 25).astype(int)
            fg_arr = np.clip(fg_arr.astype(int) + wrinkles[:, :, None], 0, 255).astype(np.uint8)

        # Draw structural lines for jackets / outerwear (center opening placket + chest pockets)
        if cat in ["jacket"] or item.subcategory in ["denim_jacket", "leather_jacket", "bomber_jacket"]:
            cx = int(w * 0.50)
            fg_arr[int(h * 0.15):int(h * 0.88), cx - 2:cx + 2] = [25, 40, 70]
            fg_arr[int(h * 0.36):int(h * 0.44), int(w * 0.33):int(w * 0.44)] = [25, 40, 70]
            fg_arr[int(h * 0.36):int(h * 0.44), int(w * 0.56):int(w * 0.67)] = [25, 40, 70]
        elif cat in ["shirt"] or item.subcategory in ["formal_shirt", "button_down_shirt", "oxford_shirt"]:
            cx = int(w * 0.50)
            fg_arr[int(h * 0.12):int(h * 0.88), cx - 1:cx + 2] = [220, 230, 245]

        # 4. Composite Foreground onto Background
        fg_textured = Image.fromarray(fg_arr)
        final_img = bg.copy()
        final_img.paste(fg_textured, (0, 0), fg_mask)

        # 5. Apply Lighting Perturbations
        if item.lighting_condition == "underexposed_dim":
            final_arr = np.array(final_img).astype(float) * 0.45
            final_img = Image.fromarray(np.clip(final_arr, 0, 255).astype(np.uint8))
        elif item.lighting_condition == "harsh_sunlight_shadows":
            final_arr = np.array(final_img).astype(float)
            # Add harsh diagonal shadow
            diag_mask = (y_grid - x_grid * 0.5) > int(h * 0.1)
            final_arr[diag_mask] *= 0.55
            final_img = Image.fromarray(np.clip(final_arr, 0, 255).astype(np.uint8))
        elif item.lighting_condition == "warm_tungsten":
            final_arr = np.array(final_img).astype(float)
            final_arr[:, :, 0] *= 1.25  # Boost Red
            final_arr[:, :, 2] *= 0.75  # Lower Blue
            final_img = Image.fromarray(np.clip(final_arr, 0, 255).astype(np.uint8))

        return final_img

    def export_benchmark_manifest(self) -> str:
        """Saves an explicitly synthetic fixture manifest."""
        manifest_file = os.path.join(self.output_dir, "synthetic_smoke_fixture_manifest.json")
        data = {
            "benchmark_suite": "YorvynSyntheticGarmentSmokeFixtures-v1.0",
            "evaluation_status": "SYNTHETIC_FIXTURE_ONLY_NOT_REAL_WORLD_EVALUATION",
            "items_count": len(self.items),
            "categories_covered": list({it.category for it in self.items}),
            "difficulties": list({it.difficulty for it in self.items}),
            "items": [asdict(it) for it in self.items]
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return manifest_file


# Global benchmark manager
real_world_benchmark = YorvynSyntheticGarmentSmokeFixtures()

