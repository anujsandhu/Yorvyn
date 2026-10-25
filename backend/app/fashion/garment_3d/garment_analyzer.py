"""
Stage A: Garment Understanding and Analysis
Extracts silhouette, color palette, patterns, neckline, sleeves, and texture metrics
from uploaded clothing photographs.
"""

from typing import Tuple, List, Dict, Optional, Any
from PIL import Image, ImageFilter, ImageStat
import numpy as np
import math
from .models import DetectedGarmentFeatures, GarmentCategory

# Curated reference color map for fashion classification
FASHION_COLOR_NAMES = {
    "#000000": "black",
    "#ffffff": "white",
    "#1e293b": "charcoal",
    "#64748b": "grey",
    "#0f172a": "midnight navy",
    "#1e3a8a": "royal navy",
    "#0284c7": "sky blue",
    "#bae6fd": "powder blue",
    "#15803d": "forest green",
    "#4ade80": "sage green",
    "#5b6b3a": "olive khaki",
    "#ca8a04": "mustard yellow",
    "#fef08a": "pale yellow",
    "#b45309": "camel",
    "#78350f": "warm brown",
    "#f5f5f4": "cream",
    "#d6d3d1": "sand beige",
    "#b91c1c": "crimson red",
    "#831843": "burgundy",
    "#f472b6": "blush pink",
    "#9333ea": "deep purple",
    "#ea580c": "terracotta orange"
}


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_clean = hex_str.lstrip("#")
    return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    # Perceptually weighted Euclidean color distance
    rm = 0.5 * (c1[0] + c2[0])
    dr = c1[0] - c2[0]
    dg = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return math.sqrt((2 + rm / 256.0) * dr * dr + 4.0 * dg * dg + (2 + (255 - rm) / 256.0) * db * db)


def find_closest_fashion_color(rgb: Tuple[int, int, int]) -> Tuple[str, str]:
    best_dist = float("inf")
    best_hex = "#1e293b"
    best_name = "charcoal"
    for ref_hex, name in FASHION_COLOR_NAMES.items():
        ref_rgb = hex_to_rgb(ref_hex)
        d = color_distance(rgb, ref_rgb)
        if d < best_dist:
            best_dist = d
            best_hex = ref_hex
            best_name = name
    return best_name, best_hex


class GarmentAnalyzer:
    """Performs garment segmentation, feature extraction, and silhouette analysis."""

    def analyze(self, image_path: str, category_hint: str = "top") -> Tuple[DetectedGarmentFeatures, Image.Image]:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            
            # Check image quality
            width, height = rgb_img.size
            if width < 120 or height < 120:
                raise ValueError("Image resolution is too low for 3D garment reconstruction (min 120x120px required).")
                
            # Resize working copy for fast, robust analytical processing
            max_dim = 768
            scale = min(max_dim / width, max_dim / height, 1.0)
            work_w, work_h = int(width * scale), int(height * scale)
            work_img = rgb_img.resize((work_w, work_h), Image.Resampling.LANCZOS)
            
            # Segment foreground garment from background
            mask, segmented_img = self._segment_garment(work_img)
            
            # Extract dominant colors & palette
            palette_hex = self._extract_palette(segmented_img, mask)
            primary_hex = palette_hex[0] if palette_hex else "#1e293b"
            secondary_hex = palette_hex[1] if len(palette_hex) > 1 else palette_hex[0]
            
            p_name, p_hex = find_closest_fashion_color(hex_to_rgb(primary_hex))
            s_name, s_hex = find_closest_fashion_color(hex_to_rgb(secondary_hex))
            
            # Analyze silhouette features
            features = self._analyze_silhouette(mask, category_hint)
            
            # Pattern analysis (variance & frequency)
            pattern_type = self._detect_pattern(segmented_img, mask)
            
            # Quality assessment
            quality_notes = []
            requires_more = False
            if scale < 0.35:
                quality_notes.append("High-resolution input processed.")
            elif width < 300 or height < 300:
                quality_notes.append("Lower resolution input. Back view recommended.")
                requires_more = True
                
            detected = DetectedGarmentFeatures(
                category=category_hint.lower(),
                subcategory=features.get("subcategory", "tshirt"),
                primary_color_name=p_name,
                primary_color_hex=primary_hex,
                secondary_color_name=s_name if s_hex != p_hex else None,
                secondary_color_hex=secondary_hex if s_hex != p_hex else None,
                palette=palette_hex[:5],
                pattern=pattern_type,
                material_hint=features.get("material_hint", "cotton"),
                neckline_type=features.get("neckline", "crewneck"),
                sleeve_length=features.get("sleeve_length", "short"),
                hem_length=features.get("hem_length", "standard"),
                fit=features.get("fit", "regular"),
                formality=features.get("formality", 4),
                warmth=features.get("warmth", 4),
                confidence_score=0.90 if not requires_more else 0.75,
                requires_additional_view=requires_more,
                quality_notes=" ".join(quality_notes) if quality_notes else "Optimal garment silhouette captured."
            )
            
            return detected, segmented_img

    def _segment_garment(self, img: Image.Image) -> Tuple[np.ndarray, Image.Image]:
        """Isolates the clothing item from the background using edge and border color sampling."""
        arr = np.array(img, dtype=np.float32)
        h, w, _ = arr.shape
        
        # Sample border pixels to detect background color distribution
        border_pixels = np.concatenate([
            arr[:15, :, :].reshape(-1, 3),
            arr[-15:, :, :].reshape(-1, 3),
            arr[:, :15, :].reshape(-1, 3),
            arr[:, -15:, :].reshape(-1, 3)
        ], axis=0)
        
        bg_mean = np.median(border_pixels, axis=0)
        
        # Calculate color distance of each pixel to background mean
        diff = np.linalg.norm(arr - bg_mean, axis=2)
        
        # Adaptive thresholding
        threshold = max(24.0, np.percentile(diff, 18))
        raw_mask = (diff > threshold).astype(np.uint8) * 255
        
        # Morphological clean up using PIL filters
        mask_img = Image.fromarray(raw_mask, mode="L")
        mask_clean = mask_img.filter(ImageFilter.MedianFilter(size=5))
        mask_clean = mask_clean.filter(ImageFilter.GaussianBlur(radius=1.5))
        mask_np = (np.array(mask_clean) > 90).astype(np.uint8)
        
        # Composite segmented image with alpha channel
        rgba = img.convert("RGBA")
        alpha = Image.fromarray((mask_np * 255).astype(np.uint8), mode="L")
        rgba.putalpha(alpha)
        
        return mask_np, rgba

    def _extract_palette(self, segmented_img: Image.Image, mask: np.ndarray) -> List[str]:
        """Extracts dominant clothing colors from masked foreground pixels."""
        rgb_arr = np.array(segmented_img.convert("RGB"))
        fg_pixels = rgb_arr[mask > 0]
        
        if len(fg_pixels) == 0:
            return ["#1e293b", "#ffffff"]
            
        # Downsample foreground pixels for clustering
        if len(fg_pixels) > 5000:
            step = len(fg_pixels) // 5000
            fg_pixels = fg_pixels[::step]
            
        # Simple fast binning / quantizing
        quantized = (fg_pixels // 32) * 32 + 16
        unique_colors, counts = np.unique(quantized, axis=0, return_counts=True)
        
        sorted_indices = np.argsort(-counts)
        sorted_colors = unique_colors[sorted_indices]
        
        palette = []
        for color in sorted_colors[:6]:
            hex_val = rgb_to_hex(color[0], color[1], color[2])
            if hex_val not in palette:
                palette.append(hex_val)
                
        return palette if palette else ["#1e293b", "#ffffff"]

    def _analyze_silhouette(self, mask: np.ndarray, category: str) -> Dict[str, Any]:
        """Analyzes bounding dimensions and profile of the mask to determine garment subcategory and fit."""
        y_indices, x_indices = np.where(mask > 0)
        if len(y_indices) == 0:
            return {"subcategory": "tshirt", "sleeve_length": "short", "neckline": "crewneck"}
            
        min_y, max_y = np.min(y_indices), np.max(y_indices)
        min_x, max_x = np.min(x_indices), np.max(x_indices)
        
        garment_h = max_y - min_y
        garment_w = max_x - min_x
        aspect_ratio = garment_h / max(garment_w, 1)
        
        cat = category.lower()
        if cat in ["bottom", "trousers", "pants"]:
            if aspect_ratio < 0.75:
                return {
                    "subcategory": "shorts",
                    "hem_length": "short",
                    "fit": "regular",
                    "material_hint": "denim",
                    "formality": 3,
                    "warmth": 2
                }
            elif aspect_ratio > 1.4:
                return {
                    "subcategory": "trousers",
                    "hem_length": "standard",
                    "fit": "relaxed_tailored",
                    "material_hint": "wool_blend",
                    "formality": 6,
                    "warmth": 5
                }
            else:
                return {
                    "subcategory": "jeans",
                    "hem_length": "standard",
                    "fit": "regular",
                    "material_hint": "denim",
                    "formality": 4,
                    "warmth": 4
                }
                
        elif cat in ["outerwear", "jacket", "coat"]:
            return {
                "subcategory": "jacket",
                "sleeve_length": "long",
                "neckline": "collar",
                "fit": "relaxed",
                "material_hint": "leather_or_heavy_wool",
                "formality": 6,
                "warmth": 7
            }
            
        elif cat in ["dress", "skirt"]:
            return {
                "subcategory": "dress" if cat == "dress" else "skirt",
                "neckline": "scoop",
                "sleeve_length": "short",
                "fit": "tailored",
                "material_hint": "silk_blend",
                "formality": 7,
                "warmth": 4
            }
            
        else: # Tops
            # Analyze upper contour for neckline & sleeve span
            # Row widths along torso
            top_quarter = min_y + int(garment_h * 0.25)
            mid_torso = min_y + int(garment_h * 0.55)
            
            top_span = np.sum(mask[top_quarter, :] > 0)
            mid_span = np.sum(mask[mid_torso, :] > 0)
            
            span_ratio = top_span / max(mid_span, 1)
            
            if span_ratio > 1.35 or aspect_ratio > 1.05:
                sleeve = "long"
                sub = "long_sleeve"
                warmth = 5
            elif span_ratio < 0.90:
                sleeve = "sleeveless"
                sub = "tank_top"
                warmth = 2
            else:
                sleeve = "short"
                sub = "tshirt"
                warmth = 3
                
            return {
                "subcategory": sub,
                "sleeve_length": sleeve,
                "neckline": "crewneck",
                "fit": "regular",
                "material_hint": "cotton",
                "formality": 4,
                "warmth": warmth
            }

    def _detect_pattern(self, img: Image.Image, mask: np.ndarray) -> str:
        """Evaluates pixel variance and edge complexity to distinguish solid vs patterned cloth."""
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges)[mask > 0]
        
        if len(edge_arr) == 0:
            return "solid"
            
        edge_density = np.mean(edge_arr)
        if edge_density > 45.0:
            return "graphic_print"
        elif edge_density > 28.0:
            return "textured_knit"
        else:
            return "solid"


# Singleton analyzer instance
garment_analyzer = GarmentAnalyzer()
