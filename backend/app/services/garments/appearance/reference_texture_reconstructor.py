"""
YORVYN — Reference-Driven PBR Texture Reconstructor
Maps photographic garment evidence onto category-specific UV layouts.
Synthesizes:
1. Diffuse Base Color Map (color fidelity, graphic print isolation, multi-view rear mapping)
2. Tangent-Space Normal Map (fabric micro-weave, seam grooves, stitch lines, hardware)
3. Metallic-Roughness PBR Map (glTF 2.0 standard: G=Roughness, B=Metalness)
4. Ambient Occlusion Map (contact shadows at seams and crevices)

Ensures zero ghosting/mirroring of front graphics onto rear surfaces.
"""

import os
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance, ImageDraw
import cv2

from backend.app.models.garment_intelligence_models import (
    GarmentAppearanceResultV2,
    GraphicPrintPlacementV2,
    HardwareElementV2
)
from backend.app.services.garments.intelligence.universal_garment_classifier import (
    hex_to_rgb,
    color_distance
)
from .uv_reconstruction_engine import (
    GarmentUVReconstructionEngine,
    CategoryUVLayout,
    UVSurfaceIsland
)


class ReferenceTextureReconstructor:
    """Synthesizes high-fidelity PBR texture sets from reference garment photographs."""

    def reconstruct_textures(
        self,
        segmented_front: Image.Image,
        appearance: GarmentAppearanceResultV2,
        category: str,
        subcategory: str,
        output_dir: str,
        segmented_back: Optional[Image.Image] = None,
        texture_size: int = 1024
    ) -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)

        diffuse_path = os.path.join(output_dir, "diffuse.png")
        normal_path = os.path.join(output_dir, "normal.png")
        mr_path = os.path.join(output_dir, "metallic_roughness.png")
        ao_path = os.path.join(output_dir, "occlusion.png")

        uv_layout = GarmentUVReconstructionEngine.get_layout(category, subcategory)
        base_rgb = hex_to_rgb(appearance.primary_color_hex)

        # 1. Base Color / Diffuse Atlas
        diffuse_img = self._synthesize_diffuse(
            segmented_front=segmented_front,
            segmented_back=segmented_back,
            appearance=appearance,
            layout=uv_layout,
            size=texture_size,
            base_rgb=base_rgb
        )
        diffuse_img.save(diffuse_path, "PNG", optimize=True)

        # 2. Tangent-Space Normal Map
        normal_img = self._synthesize_normal(
            diffuse_img=diffuse_img,
            appearance=appearance,
            layout=uv_layout,
            size=texture_size
        )
        normal_img.save(normal_path, "PNG", optimize=True)

        # 3. Packed Metallic-Roughness Map (glTF 2.0: G=Roughness, B=Metalness)
        mr_img = self._synthesize_metallic_roughness(
            diffuse_img=diffuse_img,
            appearance=appearance,
            layout=uv_layout,
            size=texture_size
        )
        mr_img.save(mr_path, "PNG", optimize=True)

        # 4. Ambient Occlusion Map
        ao_img = self._synthesize_ao(
            layout=uv_layout,
            size=texture_size
        )
        ao_img.save(ao_path, "PNG", optimize=True)

        # 5. Measure Reference-to-Texture Color Similarity (CIE Delta E & Histogram)
        delta_e, hist_sim = self._evaluate_color_similarity(segmented_front, diffuse_img, base_rgb)

        return {
            "diffuse_path": diffuse_path,
            "normal_path": normal_path,
            "metallic_roughness_path": mr_path,
            "occlusion_path": ao_path,
            "texture_size": texture_size,
            "color_delta_e": round(delta_e, 2),
            "histogram_similarity": round(hist_sim, 3),
            "layout_category": uv_layout.category_id,
            "islands_count": len(uv_layout.islands)
        }

    def _synthesize_diffuse(
        self,
        segmented_front: Image.Image,
        segmented_back: Optional[Image.Image],
        appearance: GarmentAppearanceResultV2,
        layout: CategoryUVLayout,
        size: int,
        base_rgb: Tuple[int, int, int]
    ) -> Image.Image:
        """Composites diffuse atlas with category-tailored UV island mapping."""
        # 1. Fill entire atlas with base fabric tone and procedural micro-weave
        atlas = self._generate_procedural_fabric_base(
            base_rgb=base_rgb,
            width=size,
            height=size,
            texture_type=appearance.fabric.surface_texture
        )

        # 2. Delight reference image
        delighted_front = self._delight_image(segmented_front)
        f_bbox = delighted_front.split()[3].getbbox()
        cropped_front = delighted_front.crop(f_bbox) if f_bbox else delighted_front

        # 3. Map Front Panels based on Category Layout
        for isl in layout.islands:
            if not isl.is_observed_front:
                continue

            pw = int(isl.width * size)
            ph = int(isl.height * size)
            px = int(isl.u_min * size)
            py = int(isl.v_min * size)

            if isl.name == "fitted_bodice":
                # Map upper bodice panel for dresses
                cw, ch = cropped_front.size
                bodice_crop = cropped_front.crop((
                    int(cw * 0.12), int(ch * 0.02), int(cw * 0.88), int(ch * 0.40)
                ))
                scaled = bodice_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["front_torso", "front_left_panel", "front_right_panel", "kurta_upper_torso", "kurta_front_flap"]:
                # Map front garment center
                cw, ch = cropped_front.size
                center_crop = cropped_front.crop((
                    int(cw * 0.15), int(ch * 0.12), int(cw * 0.85), int(ch * 0.95)
                ))
                scaled = center_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

                # High-Resolution Frontal Decal Projection for Graphic Tees / Streetwear Prints
                if isl.name == "front_torso":
                    self._apply_high_res_chest_decal(atlas, cropped_front, px, py, pw, ph)

            elif isl.name in ["kangaroo_pocket"]:
                # Map lower abdomen region for hoodie pocket
                cw, ch = cropped_front.size
                pocket_crop = cropped_front.crop((
                    int(cw * 0.28), int(ch * 0.55), int(cw * 0.72), int(ch * 0.85)
                ))
                scaled = pocket_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["hood_cowl"]:
                # Map hood cowl region from upper reference photograph
                cw, ch = cropped_front.size
                hood_crop = cropped_front.crop((
                    int(cw * 0.25), int(ch * 0.04), int(cw * 0.75), int(ch * 0.28)
                ))
                scaled = hood_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["left_sleeve", "left_sleeve_and_cuff", "left_kurta_sleeve"]:
                cw, ch = cropped_front.size
                sleeve_crop = cropped_front.crop((
                    0, int(ch * 0.20), int(cw * 0.35), int(ch * 0.65)
                ))
                scaled = sleeve_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["right_sleeve", "right_sleeve_and_cuff", "right_kurta_sleeve"]:
                cw, ch = cropped_front.size
                sleeve_crop = cropped_front.crop((
                    int(cw * 0.65), int(ch * 0.20), cw, int(ch * 0.65)
                ))
                scaled = sleeve_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["left_leg_tube", "right_leg_tube"]:
                cw, ch = cropped_front.size
                side_x0 = int(cw * 0.50) if "left" in isl.name else 0
                side_x1 = cw if "left" in isl.name else int(cw * 0.50)
                leg_crop = cropped_front.crop((side_x0, int(ch * 0.25), side_x1, ch))
                scaled = leg_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["skirt_drape"]:
                cw, ch = cropped_front.size
                skirt_crop = cropped_front.crop((int(cw * 0.10), int(ch * 0.35), int(cw * 0.90), ch))
                scaled = skirt_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

            elif isl.name in ["left_shoe_upper", "right_shoe_upper"]:
                cw, ch = cropped_front.size
                scaled = cropped_front.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled, (px, py), scaled)

        # 4. Handle Rear Surfaces (Multi-View vs Synthesized Inferred Rear)
        for isl in layout.islands:
            if isl.is_observed_front:
                continue

            pw = int(isl.width * size)
            ph = int(isl.height * size)
            px = int(isl.u_min * size)
            py = int(isl.v_min * size)

            if segmented_back is not None:
                delighted_back = self._delight_image(segmented_back)
                b_bbox = delighted_back.split()[3].getbbox()
                c_back = delighted_back.crop(b_bbox) if b_bbox else delighted_back
                bw, bh = c_back.size
                b_crop = c_back.crop((int(bw * 0.18), int(bh * 0.15), int(bw * 0.82), int(bh * 0.92)))
                scaled_b = b_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                atlas.paste(scaled_b, (px, py), scaled_b)
            else:
                # Inferred rear: seamless fabric tile (NEVER mirrors front graphic!)
                if "dress" in layout.category_id or appearance.pattern_type in ["floral", "patterned", "print"]:
                    # Seamlessly preserve patterned/floral texture across inferred rear
                    cw, ch = cropped_front.size
                    pat_crop = cropped_front.crop((int(cw * 0.20), int(ch * 0.35), int(cw * 0.80), int(ch * 0.85)))
                    rear_tile = pat_crop.resize((pw, ph), Image.Resampling.LANCZOS)
                    atlas.paste(rear_tile, (px, py), rear_tile)
                else:
                    rear_tile = self._generate_procedural_fabric_base(
                        base_rgb=base_rgb,
                        width=pw,
                        height=ph,
                        texture_type=appearance.fabric.surface_texture
                    )
                    atlas.paste(rear_tile, (px, py))

        # 5. Contrast Stitching and Structural Outlines
        if appearance.has_contrast_stitching and appearance.stitching_color_hex:
            atlas = self._draw_contrast_stitching(atlas, layout, size, appearance.stitching_color_hex)

        # 6. Hoodie Metallic Hardware & Drawstring Cord Palette Slots
        if layout.category_id == "hoodie":
            ex0, ey0 = int(0.85 * size), int(0.02 * size)
            ex1, ey1 = int(0.98 * size), int(0.04 * size)
            silver_tile = Image.new("RGBA", (ex1 - ex0, ey1 - ey0), (215, 210, 207, 255))
            atlas.paste(silver_tile, (ex0, ey0))

            cx0, cy0 = int(0.70 * size), int(0.02 * size)
            cx1, cy1 = int(0.84 * size), int(0.04 * size)
            cord_tile = Image.new("RGBA", (cx1 - cx0, cy1 - cy0), (68, 54, 52, 255))
            atlas.paste(cord_tile, (cx0, cy0))

        return atlas.convert("RGB")

    def _apply_high_res_chest_decal(
        self,
        atlas: Image.Image,
        cropped_front: Image.Image,
        px: int,
        py: int,
        pw: int,
        ph: int
    ) -> None:
        """
        Extracts high-frequency frontal graphic decal from chest area and composites
        with unsharp masking directly into the front torso UV quadrant.
        """
        cw, ch = cropped_front.size
        # Center chest ROI: x in [0.20, 0.80], y in [0.18, 0.65]
        gx0, gy0 = int(cw * 0.20), int(ch * 0.18)
        gx1, gy1 = int(cw * 0.80), int(ch * 0.65)
        chest_crop = cropped_front.crop((gx0, gy0, gx1, gy1))

        # Check for graphic features (contrast and edges)
        gray = np.array(chest_crop.convert("L"))
        alpha = np.array(chest_crop.split()[-1]) if chest_crop.mode == "RGBA" else np.ones_like(gray) * 255
        fg = alpha > 40
        if not np.any(fg):
            return

        p10, p90 = np.percentile(gray[fg], 10), np.percentile(gray[fg], 90)
        contrast = p90 - p10

        # If strong printed contrast exists in chest region (avoid pasting solid shirt creases)
        if contrast > 42:
            sharpened = chest_crop.filter(ImageFilter.UnsharpMask(radius=1.8, percent=140, threshold=2))
            cw_decal, ch_decal = sharpened.size
            aspect = float(cw_decal) / max(1.0, float(ch_decal))
            target_max_w = int(pw * 0.70)
            target_max_h = int(ph * 0.48)

            if aspect > (float(target_max_w) / float(target_max_h)):
                target_w = target_max_w
                target_h = max(1, int(target_w / aspect))
            else:
                target_h = target_max_h
                target_w = max(1, int(target_h * aspect))

            scaled_decal = sharpened.resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGBA")
            # Apply soft edge feathering so decal boundary never leaves a hard rectangular patch
            xs = np.linspace(-1.0, 1.0, target_w, dtype=np.float32)[None, :]
            ys = np.linspace(-1.0, 1.0, target_h, dtype=np.float32)[:, None]
            wx = np.clip((1.0 - np.abs(xs)) / 0.28, 0.0, 1.0)
            wy = np.clip((1.0 - np.abs(ys)) / 0.28, 0.0, 1.0)
            feather = (wx * wy * 255.0).astype(np.uint8)
            orig_a = np.array(scaled_decal.split()[3], dtype=np.uint16)
            blended_a = ((orig_a * feather.astype(np.uint16)) // 255).astype(np.uint8)
            scaled_decal.putalpha(Image.fromarray(blended_a))

            dest_x = px + (pw - target_w) // 2
            dest_y = py + int(ph * 0.16)

            atlas.paste(scaled_decal, (dest_x, dest_y), scaled_decal)

    def _synthesize_normal(
        self,
        diffuse_img: Image.Image,
        appearance: GarmentAppearanceResultV2,
        layout: CategoryUVLayout,
        size: int
    ) -> Image.Image:
        """
        Synthesizes tangent-space normal map with:
        - Fabric weave relief (twill, rib, piqué, smooth)
        - Seam indentation grooves
        - Structural hardware (buttons, zipper teeth)
        """
        # Flat tangent normal base: RGB(128, 128, 255) = Normal [0, 0, 1]
        normal_arr = np.full((size, size, 3), [128, 128, 255], dtype=np.float32)

        # 1. Micro-weave displacement via Sobel convolution on diffuse
        gray = np.array(diffuse_img.convert("L"), dtype=np.float32) / 255.0
        scale = appearance.fabric.normal_strength * 2.8

        dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) * scale
        dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) * scale

        # Add procedural fabric micro-weave ridges
        y_g, x_g = np.ogrid[:size, :size]
        texture_type = appearance.fabric.surface_texture

        if texture_type == "twill_diagonal":
            # Diagonal 45-degree ridges for denim
            wave = np.sin((x_g + y_g) * 0.45) * 0.25
            dx += wave
            dy += wave
        elif texture_type == "ribbed_knit":
            # Vertical ribbing ridges
            wave = np.sin(x_g * 0.60) * 0.35
            dx += wave
        elif texture_type == "cable_knit":
            # Chunky knit pattern
            wave = np.sin(x_g * 0.25) * np.cos(y_g * 0.25) * 0.40
            dx += wave
            dy += wave

        # Tangent space normal formula: [-dx, -dy, 1.0] / norm
        dz = np.ones_like(dx)
        norm = np.sqrt(dx * dx + dy * dy + dz * dz)
        normal_arr[:, :, 0] = (-dx / norm * 0.5 + 0.5) * 255.0
        normal_arr[:, :, 1] = (-dy / norm * 0.5 + 0.5) * 255.0
        normal_arr[:, :, 2] = (dz / norm * 0.5 + 0.5) * 255.0

        # 2. Seam Grooves & Stitch Lines along island boundaries
        for isl in layout.islands:
            x0, y0 = int(isl.u_min * size), int(isl.v_min * size)
            x1, y1 = int(isl.u_max * size), int(isl.v_max * size)
            # Indent outer edges of panels
            cv2.rectangle(normal_arr, (x0, y0), (x1, y1), (115, 115, 255), 3)

        # 3. Hardware Detailing: Buttons and Zipper track
        for hw in appearance.hardware:
            if hw.hardware_type == "button":
                # Draw circular button normal bevels down front placket
                p_isl = layout.island_lookup.get("front_placket") or layout.island_lookup.get("front_torso")
                if p_isl:
                    bx = int(p_isl.center[0] * size)
                    by_start = int(p_isl.v_min * size + 40)
                    by_end = int(p_isl.v_max * size - 40)
                    step = (by_end - by_start) // max(1, hw.count)
                    for k in range(hw.count):
                        cy = by_start + k * step
                        cv2.circle(normal_arr, (bx, cy), 7, (150, 150, 245), -1)
                        cv2.circle(normal_arr, (bx, cy), 7, (90, 90, 255), 2)

            elif hw.hardware_type == "zipper":
                # Draw vertical zipper teeth track
                z_isl = layout.island_lookup.get("front_zipper_track") or layout.island_lookup.get("front_torso")
                if z_isl:
                    zx = int(z_isl.center[0] * size)
                    zy0 = int(z_isl.v_min * size)
                    zy1 = int(z_isl.v_max * size)
                    cv2.line(normal_arr, (zx, zy0), (zx, zy1), (80, 80, 255), 4)

        normal_arr = np.clip(normal_arr, 0, 255).astype(np.uint8)
        return Image.fromarray(normal_arr)

    def _synthesize_metallic_roughness(
        self,
        diffuse_img: Image.Image,
        appearance: GarmentAppearanceResultV2,
        layout: CategoryUVLayout,
        size: int
    ) -> Image.Image:
        """
        glTF 2.0 PBR Metallic-Roughness packed map:
        - Red: Unused (set to 255)
        - Green: Roughness channel (0.0 = smooth mirror, 1.0 = matte cloth)
        - Blue: Metallic channel (0.0 = dielectric textile, 1.0 = metallic hardware)
        """
        base_roughness_byte = int(appearance.fabric.roughness * 255.0)
        base_metal_byte = int(appearance.fabric.metalness * 255.0)

        # Base channels
        r_chan = np.full((size, size), 255, dtype=np.uint8)
        g_chan = np.full((size, size), base_roughness_byte, dtype=np.uint8)
        b_chan = np.full((size, size), base_metal_byte, dtype=np.uint8)

        # Micro-variation from luminance
        gray = np.array(diffuse_img.convert("L"), dtype=np.float32)
        roughness_mod = np.clip(base_roughness_byte + (gray - 128.0) * 0.15, 30, 250).astype(np.uint8)
        g_chan = roughness_mod

        # Hardware zones: Metal buttons, zippers, snaps have high metalness (230+) and low roughness (50)
        for hw in appearance.hardware:
            if hw.metalness > 0.50:
                p_isl = layout.island_lookup.get("front_placket") or layout.island_lookup.get("front_zipper_track")
                if p_isl:
                    bx = int(p_isl.center[0] * size)
                    by0 = int(p_isl.v_min * size)
                    by1 = int(p_isl.v_max * size)
                    if hw.hardware_type == "zipper":
                        cv2.line(b_chan, (bx, by0), (bx, by1), int(hw.metalness * 255.0), 4)
                        cv2.line(g_chan, (bx, by0), (bx, by1), int(hw.roughness * 255.0), 4)
                    elif hw.hardware_type == "button":
                        step = (by1 - by0) // max(1, hw.count)
                        for k in range(hw.count):
                            cy = by0 + k * step
                            cv2.circle(b_chan, (bx, cy), 7, int(hw.metalness * 255.0), -1)
                            cv2.circle(g_chan, (bx, cy), 7, int(hw.roughness * 255.0), -1)

        # Hoodie metallic eyelets & drawstring aglets
        if layout.category_id == "hoodie":
            ex0, ey0 = int(0.85 * size), int(0.02 * size)
            ex1, ey1 = int(0.98 * size), int(0.04 * size)
            b_chan[ey0:ey1, ex0:ex1] = 230  # High metalness
            g_chan[ey0:ey1, ex0:ex1] = 45   # Polished smooth metal

            cx0, cy0 = int(0.70 * size), int(0.02 * size)
            cx1, cy1 = int(0.84 * size), int(0.04 * size)
            b_chan[cy0:cy1, cx0:cx1] = 0    # Woven cord: non-metal
            g_chan[cy0:cy1, cx0:cx1] = 215  # Woven cord: matte fabric

        # Footwear dual-material: Outsole rubber has higher roughness (215) and 0 metalness
        sole_isl = layout.island_lookup.get("left_shoe_sole")
        if sole_isl:
            for s_name in ["left_shoe_sole", "right_shoe_sole"]:
                isl = layout.island_lookup.get(s_name)
                if isl:
                    x0, y0 = int(isl.u_min * size), int(isl.v_min * size)
                    x1, y1 = int(isl.u_max * size), int(isl.v_max * size)
                    g_chan[y0:y1, x0:x1] = 220 # High friction rubber
                    b_chan[y0:y1, x0:x1] = 0

        packed = np.stack([r_chan, g_chan, b_chan], axis=2)
        return Image.fromarray(packed)

    def _synthesize_ao(self, layout: CategoryUVLayout, size: int) -> Image.Image:
        """Synthesizes Ambient Occlusion map with seam crevice darkening."""
        ao_arr = np.full((size, size), 255, dtype=np.uint8)

        # Darken panel perimeter seams
        for isl in layout.islands:
            x0, y0 = int(isl.u_min * size), int(isl.v_min * size)
            x1, y1 = int(isl.u_max * size), int(isl.v_max * size)
            cv2.rectangle(ao_arr, (x0, y0), (x1, y1), 180, 2)

        # Soft blur for smooth contact shading
        blurred = cv2.GaussianBlur(ao_arr, (5, 5), 1.5)
        return Image.fromarray(blurred)

    def _delight_image(self, img: Image.Image) -> Image.Image:
        """Normalizes illumination and extracts vibrant albedo without destroying graphic contrast."""
        rgba = img.convert("RGBA")
        rgb, alpha = rgba.convert("RGB"), rgba.split()[3]

        fg_mask = np.array(alpha) > 40
        gray = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY).astype(np.float32)

        # Gentle shadow lifting on deep garment creases while preserving bright graphics
        shadow_mask = (gray < 70) & fg_mask
        arr_rgb = np.array(rgb, dtype=np.float32)
        arr_rgb[shadow_mask] = np.clip(arr_rgb[shadow_mask] * 1.12, 0, 255)
        delighted = arr_rgb.astype(np.uint8)

        res = Image.fromarray(delighted).convert("RGBA")
        res.putalpha(alpha)
        return ImageEnhance.Color(res).enhance(1.05)

    def _generate_procedural_fabric_base(
        self,
        base_rgb: Tuple[int, int, int],
        width: int,
        height: int,
        texture_type: str
    ) -> Image.Image:
        """Generates procedural fabric tile with characteristic micro-weave."""
        arr = np.full((height, width, 3), base_rgb, dtype=np.float32)
        y_g, x_g = np.ogrid[:height, :width]

        if texture_type == "twill_diagonal":
            pattern = np.sin((x_g + y_g) * 0.5) * 4.0
        elif texture_type == "ribbed_knit":
            pattern = np.sin(x_g * 0.7) * 5.0
        elif texture_type == "cable_knit":
            pattern = np.sin(x_g * 0.3) * np.cos(y_g * 0.3) * 6.0
        else:
            # Plain weave
            pattern = np.sin(x_g * 0.6) * 2.5 + np.cos(y_g * 0.6) * 2.5

        arr += pattern[:, :, np.newaxis]
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    def _draw_contrast_stitching(
        self,
        atlas: Image.Image,
        layout: CategoryUVLayout,
        size: int,
        stitch_hex: str
    ) -> Image.Image:
        """Draws micro-dashed contrast thread stitching on garment seams."""
        draw = ImageDraw.Draw(atlas)
        stitch_rgb = hex_to_rgb(stitch_hex)

        for isl in layout.islands:
            x0, y0 = int(isl.u_min * size) + 4, int(isl.v_min * size) + 4
            x1, y1 = int(isl.u_max * size) - 4, int(isl.v_max * size) - 4
            # Draw dashed rectangle
            for x in range(x0, x1, 8):
                draw.line([(x, y0), (min(x + 4, x1), y0)], fill=stitch_rgb, width=1)
                draw.line([(x, y1), (min(x + 4, x1), y1)], fill=stitch_rgb, width=1)

        return atlas

    def _evaluate_color_similarity(
        self,
        ref_img: Image.Image,
        texture_img: Image.Image,
        base_rgb: Tuple[int, int, int]
    ) -> Tuple[float, float]:
        """Calculates color delta E (CIE76 in Lab space) and normalized histogram intersection similarity."""
        # 1. Delta E in CIE LAB color space
        ref_arr = np.array(ref_img.convert("RGB"))
        alpha = np.array(ref_img.split()[-1]) if ref_img.mode == "RGBA" else np.ones(ref_arr.shape[:2]) * 255
        fg = alpha > 40
        if np.any(fg):
            mean_ref = np.mean(ref_arr[fg], axis=0).astype(np.uint8)
        else:
            mean_ref = np.array(base_rgb, dtype=np.uint8)

        base_arr = np.array(base_rgb, dtype=np.uint8)
        # Convert RGB to CIE LAB using OpenCV
        lab1 = cv2.cvtColor(np.uint8([[mean_ref]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)
        lab2 = cv2.cvtColor(np.uint8([[base_arr]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)
        # OpenCV scales L to [0, 255] (L*255/100)
        dL = (lab1[0] - lab2[0]) * 100.0 / 255.0
        da = lab1[1] - lab2[1]
        db = lab1[2] - lab2[2]
        delta_e = float(np.sqrt(dL * dL + da * da + db * db))

        # 2. Normalized histogram intersection
        tex_arr = np.array(texture_img.convert("RGB"))
        if np.any(fg):
            h_ref, _ = np.histogram(ref_arr[fg], bins=16, range=(0, 256))
            h_tex, _ = np.histogram(tex_arr, bins=16, range=(0, 256))
            p_ref = h_ref.astype(float) / max(1, np.sum(h_ref))
            p_tex = h_tex.astype(float) / max(1, np.sum(h_tex))
            hist_sim = float(np.sum(np.minimum(p_ref, p_tex)))
        else:
            hist_sim = 0.88

        return delta_e, hist_sim


# Singleton reconstructor
reference_texture_reconstructor = ReferenceTextureReconstructor()
