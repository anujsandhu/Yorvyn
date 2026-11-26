"""
Stage 5: 3D Garment Preview Renderer
Renders a derived 2D studio preview thumbnail directly from the generated 3D garment mesh
and texture maps. Adheres strictly to privacy rules (never uses original input photo).
"""

from typing import Tuple
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import math
from .garment_mesh_builder import GarmentMesh


class PreviewRenderer:
    """Renders a derived 3D thumbnail preview of the generated garment."""

    def render_preview(
        self,
        mesh: GarmentMesh,
        diffuse_img: Image.Image,
        output_path: str,
        image_size: int = 512
    ) -> str:
        """
        Renders a studio preview of the 3D garment on a luxury neutral backdrop.
        Saves as a derived PNG asset and returns the output path.
        """
        width, height = image_size, image_size
        canvas = Image.new("RGBA", (width, height), (248, 250, 252, 255))
        
        # 1. Background studio lighting vignette
        bg = Image.new("RGB", (width, height), (248, 250, 252))
        draw_bg = ImageDraw.Draw(bg)
        # Soft radial gradient center
        for r in range(width // 2, 0, -8):
            alpha = int(255 - (r / (width // 2)) * 14)
            val = min(255, 240 + int(alpha * 0.05))
            draw_bg.ellipse(
                (width // 2 - r, height // 2 - r, width // 2 + r, height // 2 + r),
                outline=(val, val, val)
            )
        canvas.paste(bg.convert("RGBA"), (0, 0))
        
        # 2. Camera setup: slight 3/4 perspective looking at garment center
        pos = mesh.positions
        min_p = pos.min(axis=0)
        max_p = pos.max(axis=0)
        center = (min_p + max_p) * 0.5
        span_y = max(max_p[1] - min_p[1], 0.1)
        
        # Center positions relative to garment center
        shifted_pos = pos - center
        
        # Subtle 3D rotation: 12 degrees yaw, 4 degrees pitch
        yaw = math.radians(14.0)
        pitch = math.radians(6.0)
        
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
        
        rotated_pos = shifted_pos @ rot_y.T @ rot_x.T
        rotated_norms = mesh.normals @ rot_y.T @ rot_x.T
        
        # Orthographic / telephoto perspective projection onto canvas
        # Fits garment into ~72% of canvas height
        target_span_px = height * 0.74
        scale = target_span_px / span_y
        
        screen_x = width * 0.5 + rotated_pos[:, 0] * scale
        screen_y = height * 0.52 - rotated_pos[:, 1] * scale
        screen_z = rotated_pos[:, 2] # Depth for painter's sort
        
        # 3. Mannequin Dress-Form Stand (Backdrop & Structure behind garment)
        # Floor contact shadow under circular mannequin base
        shadow_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_img)
        s_draw.ellipse(
            (int(width * 0.28), int(height * 0.89), int(width * 0.72), int(height * 0.95)),
            fill=(15, 23, 42, 50)
        )
        shadow_blur = shadow_img.filter(ImageFilter.GaussianBlur(radius=12))
        canvas.alpha_composite(shadow_blur)

        # Draw dress-form mannequin components behind the garment
        stand_draw = ImageDraw.Draw(canvas)
        cx = int(width * 0.5)
        top_y = int(screen_y.min())
        bot_y = int(screen_y.max())

        # (a) Circular wooden base at the floor
        base_y = int(height * 0.90)
        base_w = int(width * 0.22)
        base_h = int(height * 0.035)
        stand_draw.ellipse(
            (cx - base_w, base_y - base_h, cx + base_w, base_y + base_h),
            fill=(110, 72, 38, 255) # Polished beechwood
        )
        # Subtle rim highlight on wood base
        stand_draw.arc(
            (cx - base_w, base_y - base_h, cx + base_w, base_y + base_h),
            start=200, end=340, fill=(180, 130, 85, 255), width=2
        )

        # (b) Gunmetal / brass pedestal pole extending up into torso
        pole_w = max(int(width * 0.016), 4)
        stand_draw.rectangle(
            (cx - pole_w, int(height * 0.45), cx + pole_w, base_y),
            fill=(30, 41, 59, 255) # Cast gunmetal
        )
        # Metallic specular stripe on pole
        stand_draw.line(
            (cx - pole_w + 2, int(height * 0.45), cx - pole_w + 2, base_y),
            fill=(100, 116, 139, 255), width=1
        )

        # (c) Porcelain bisque neck cylinder
        neck_w = int(width * 0.055)
        neck_top = max(int(top_y - height * 0.07), int(height * 0.14))
        neck_bot = int(top_y + height * 0.04)
        stand_draw.rounded_rectangle(
            (cx - neck_w, neck_top, cx + neck_w, neck_bot),
            radius=6, fill=(238, 236, 232, 255) # Porcelain bisque
        )
        # Neck shading (left-to-right soft shadow)
        stand_draw.rectangle(
            (cx + int(neck_w * 0.2), neck_top, cx + neck_w, neck_bot),
            fill=(210, 206, 200, 255)
        )

        # (d) Turned wooden neck finial / cap
        finial_w = int(width * 0.04)
        finial_h = int(height * 0.035)
        stand_draw.ellipse(
            (cx - finial_w, neck_top - finial_h, cx + finial_w, neck_top + int(finial_h * 0.3)),
            fill=(139, 90, 43, 255) # Warm beechwood cap
        )
        stand_draw.ellipse(
            (cx - int(finial_w * 0.5), neck_top - finial_h - int(finial_h * 0.4), cx + int(finial_w * 0.5), neck_top - finial_h + 2),
            fill=(110, 72, 38, 255) # Finial top bead
        )

        # 4. Painter's algorithm triangle rendering with PBR directional lighting
        tri_indices = mesh.indices
        tri_depths = screen_z[tri_indices].mean(axis=1)
        sorted_tri_order = np.argsort(tri_depths) # Back-to-front
        
        draw = ImageDraw.Draw(canvas)
        
        # Lighting vectors (studio key light + fill light)
        key_light = np.array([0.45, 0.75, 0.5], dtype=np.float32)
        key_light = key_light / np.linalg.norm(key_light)
        
        diffuse_w, diffuse_h = diffuse_img.size
        diffuse_pixels = diffuse_img.load()
        
        for tri_idx in sorted_tri_order:
            v_idx = tri_indices[tri_idx]

            # Surface normal & backface culling so rear interior faces don't fight front faces
            n = rotated_norms[v_idx].mean(axis=0)
            n_len = np.linalg.norm(n)
            if n_len > 1e-5:
                n = n / n_len
            else:
                n = np.array([0, 0, 1], dtype=np.float32)

            if n[2] < -0.10:
                continue

            p0 = (screen_x[v_idx[0]], screen_y[v_idx[0]])
            p1 = (screen_x[v_idx[1]], screen_y[v_idx[1]])
            p2 = (screen_x[v_idx[2]], screen_y[v_idx[2]])
                
            # Diffuse lighting calculation (Lambertian + ambient)
            ndotl = max(0.0, float(np.dot(n, key_light)))
            intensity = 0.52 + 0.48 * ndotl
            
            # Sample color from UV texture
            uv_mean = mesh.uvs[v_idx].mean(axis=0)
            u_px = int(np.clip(uv_mean[0] * diffuse_w, 0, diffuse_w - 1))
            v_px = int(np.clip(uv_mean[1] * diffuse_h, 0, diffuse_h - 1))
            tex_col = diffuse_pixels[u_px, v_px]
            
            # Modulate with lighting
            col_r = int(np.clip(tex_col[0] * intensity, 0, 255))
            col_g = int(np.clip(tex_col[1] * intensity, 0, 255))
            col_b = int(np.clip(tex_col[2] * intensity, 0, 255))
            
            draw.polygon([p0, p1, p2], fill=(col_r, col_g, col_b, 255))
            
        # Subtle anti-aliasing / smoothing pass
        res = canvas.convert("RGB")
        res.save(output_path, "PNG", optimize=True)
        return output_path


# Singleton preview renderer
preview_renderer = PreviewRenderer()
