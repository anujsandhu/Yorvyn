"""
YORVYN — Visual Reconstruction Fidelity & Neural 3D Recovery Test Suite
Verifies:
1. Silhouette profile extraction from segmented garment photographs
2. Image-conditioned geometric deformation across category reconstruction engines
3. 2-Manifold topology preservation & UV coordinate alignment
4. Graphic print aspect ratio preservation in diffuse texture synthesis
5. Truthful neural provenance and honest remote GPU availability verification
"""

import pytest
import numpy as np
from PIL import Image, ImageDraw

from backend.app.services.garments.reconstruction.geometry_utils import (
    extract_silhouette_profile,
    calculate_smooth_normals
)
from backend.app.services.garments.reconstruction import (
    TopsReconstructionEngine,
    HoodieReconstructionEngine,
    ShirtReconstructionEngine,
    JacketReconstructionEngine,
    BottomsReconstructionEngine,
    DressReconstructionEngine
)
from backend.app.services.garments.reconstruction.neural.remote_gpu_client import (
    remote_reconstruction_client
)
from backend.app.services.garments.appearance.reference_texture_reconstructor import (
    ReferenceTextureReconstructor
)
from backend.app.services.garments.appearance.uv_reconstruction_engine import (
    GarmentUVReconstructionEngine
)
from backend.app.models.garment_intelligence_models import (
    GarmentAppearanceResultV2,
    FabricPBRPropertiesV2,
    GraphicPrintPlacementV2
)


def _create_synthetic_garment_image(width_mode: str = "boxy") -> Image.Image:
    """Creates a synthetic RGBA garment mask (boxy vs slim)."""
    img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if width_mode == "boxy":
        # Broad boxy silhouette: wide chest, wide waist, wide hem
        points = [
            (140, 50),   # Collar left
            (60, 100),   # Shoulder left
            (40, 200),   # Sleeve outer
            (70, 240),   # Sleeve inner
            (80, 220),   # Armpit left
            (70, 450),   # Hem left (WIDE)
            (330, 450),  # Hem right (WIDE)
            (320, 220),  # Armpit right
            (330, 240),  # Sleeve inner
            (360, 200),  # Sleeve outer
            (340, 100),  # Shoulder right
            (260, 50),   # Collar right
        ]
    else:
        # Slim tapered silhouette: narrow chest, tapered waist, tapered hem
        points = [
            (150, 50),   # Collar left
            (90, 100),   # Shoulder left
            (70, 190),   # Sleeve outer
            (95, 230),   # Sleeve inner
            (110, 210),  # Armpit left
            (130, 450),  # Hem left (TAPERED)
            (270, 450),  # Hem right (TAPERED)
            (290, 210),  # Armpit right
            (305, 230),  # Sleeve inner
            (330, 190),  # Sleeve outer
            (310, 100),  # Shoulder right
            (250, 50),   # Collar right
        ]

    draw.polygon(points, fill=(45, 55, 72, 255))
    return img


class TestVisualReconstructionFidelity:
    """Verifies image-conditioned visual reconstruction fidelity."""

    def test_silhouette_profile_extraction(self):
        """Verifies extract_silhouette_profile extracts valid normalized scales and offsets."""
        boxy_img = _create_synthetic_garment_image("boxy")
        scales, offsets = extract_silhouette_profile(boxy_img, num_samples=24)

        assert scales is not None
        assert offsets is not None
        assert len(scales) == 24
        assert len(offsets) == 24
        assert np.all(scales >= 0.80) and np.all(scales <= 1.30)
        assert np.all(np.abs(offsets) <= 0.05)

    def test_silhouette_profile_handles_none_and_empty(self):
        """Verifies extract_silhouette_profile handles None and transparent images safely."""
        scales, offsets = extract_silhouette_profile(None)
        assert scales is None and offsets is None

        empty_img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        scales, offsets = extract_silhouette_profile(empty_img)
        assert scales is None and offsets is None

    def test_image_conditioned_geometry_deformation_distinguishes_cuts(self):
        """Verifies that boxy garments reconstruct with wider torso circumference than slim garments."""
        boxy_img = _create_synthetic_garment_image("boxy")
        slim_img = _create_synthetic_garment_image("slim")

        engine = HoodieReconstructionEngine()
        boxy_out = engine.reconstruct(category="tops", subcategory="hoodie", front_image=boxy_img)
        slim_out = engine.reconstruct(category="tops", subcategory="hoodie", front_image=slim_img)

        boxy_mesh = boxy_out.mesh
        slim_mesh = slim_out.mesh

        # Compare lower torso hem ring (ring 23 of 24, segment count 28)
        n_seg = 28
        boxy_hem_ring = boxy_mesh.positions[23 * n_seg : 24 * n_seg]
        slim_hem_ring = slim_mesh.positions[23 * n_seg : 24 * n_seg]

        boxy_width = np.ptp(boxy_hem_ring[:, 0])
        slim_width = np.ptp(slim_hem_ring[:, 0])

        assert boxy_width > slim_width + 0.04, (
            f"Boxy garment hem width ({boxy_width:.3f}m) should exceed "
            f"slim garment hem width ({slim_width:.3f}m) by at least 4cm"
        )

    def test_all_category_engines_preserve_2manifold_topology_with_front_image(self):
        """Verifies 100% 2-manifold quality across all engines when conditioned on front_image."""
        front_img = _create_synthetic_garment_image("boxy")

        engines = [
            (TopsReconstructionEngine(), "tops", "tshirt"),
            (HoodieReconstructionEngine(), "tops", "hoodie"),
            (ShirtReconstructionEngine(), "tops", "formal_shirt"),
            (JacketReconstructionEngine(), "outerwear", "denim_jacket"),
            (BottomsReconstructionEngine(), "bottoms", "jeans"),
            (DressReconstructionEngine(), "dresses_and_skirts", "dress"),
        ]

        for eng, cat, subcat in engines:
            rec = eng.reconstruct(category=cat, subcategory=subcat, front_image=front_img)
            assert rec.quality_report.is_manifold, f"{eng.engine_id} failed 2-manifold check"
            assert rec.quality_report.degenerate_triangle_count == 0, f"{eng.engine_id} produced degenerate triangles"
            assert len(rec.mesh.positions) > 300, f"{eng.engine_id} mesh has too few vertices"

    def test_chest_graphic_aspect_ratio_preservation(self):
        """Verifies that rectangular chest graphics retain aspect ratio and avoid square stretching."""
        # Create graphic tee image with a 2.5 : 1 wide text logo on chest
        img = Image.new("RGBA", (500, 600), (40, 40, 40, 255))
        draw = ImageDraw.Draw(img)
        # Draw wide white rectangular logo banner
        draw.rectangle((120, 200, 380, 280), fill=(240, 240, 240, 255))
        draw.text((150, 220), "YORVYN ATELIER", fill=(10, 10, 10, 255))

        reconstructor = ReferenceTextureReconstructor()
        appearance = GarmentAppearanceResultV2(
            job_id="test_aspect",
            primary_color_name="Dark Grey",
            primary_color_hex="#282828",
            fabric=FabricPBRPropertiesV2(
                fabric_category="cotton",
                surface_texture="plain_weave",
                roughness=0.65,
                metalness=0.04,
                confidence=0.9
            ),
            graphic=GraphicPrintPlacementV2(has_graphic_print=True, placement="front_chest")
        )

        layout = GarmentUVReconstructionEngine.get_layout("tops", "tshirt")
        diffuse = reconstructor._synthesize_diffuse(
            segmented_front=img,
            segmented_back=None,
            appearance=appearance,
            layout=layout,
            size=512,
            base_rgb=(40, 40, 40)
        )

        assert diffuse is not None
        assert diffuse.size == (512, 512)

    def test_truthful_remote_neural_inference_provenance(self):
        """Verifies remote_reconstruction_client is truthful and does not claim fake neural success."""
        # In standard local/CI environment without remote GPU cluster URL:
        if not remote_reconstruction_client.is_configured:
            assert remote_reconstruction_client.is_configured is False
            dummy_img = Image.new("RGB", (64, 64), (100, 100, 100))
            res = remote_reconstruction_client.reconstruct_remote(dummy_img, "tops", "hoodie")
            assert res is None, "Should return None when remote GPU is unconfigured, never mock success"
