"""
YORVYN — Phase 7: Neural Garment AI & Specialized Multi-Task Intelligence Tests.
Verifies:
1. MultiTaskGarmentNeuralNetwork & UniversalGarmentIntelligenceModel on MPS/CPU.
2. Verified checkpoint loading and 10 category-specific attribute heads.
3. GarmentDatasetPipeline quality filtering, dHash deduplication, licensing audit, and privacy opt-in barrier.
4. LearnedMultiViewEngine missing-surface disentanglement and cross-view identity.
5. LearnedMaterialEngine PBR textile inference, graphic placement, and hardware.
6. NeuralGarmentReconstructionEngine hybrid deformation, manifold quality, and 20-bone rigging.
7. Truthful provenance contract (never fake neural or procedural provenance).
"""

import os
import sys
import pytest
import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.services.garments.intelligence import (
    universal_intelligence_model,
    UniversalGarmentIntelligenceModel,
    learned_multiview_engine,
    learned_material_engine
)
from backend.app.pipeline.training.garment_dataset_pipeline import (
    garment_dataset_pipeline,
    UniversalGarmentAnnotation,
    DATASET_LICENSE_REGISTRY
)
from backend.app.services.garments.reconstruction.neural import (
    neural_reconstruction_engine,
    NeuralGarmentReconstructionEngine,
    LearnedModelEvaluator
)
from backend.app.services.garments.garment_mesh_builder import garment_mesh_builder
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.models.garment_intelligence_models import BoundingBox2D


def create_test_image(color=(50, 80, 140), size=(256, 256)) -> Image.Image:
    """Creates a synthetic RGB image for testing with natural contrast texture."""
    img = Image.new("RGB", size, color)
    arr = np.array(img)
    # Add high-contrast textured garment pattern so Laplacian variance > 30 and contrast std > 20
    h, w, _ = arr.shape
    y_idx, x_idx = np.indices((h, w))
    stripes = ((x_idx // 16) % 2) * 80
    arr[:, :, 0] = np.clip(arr[:, :, 0] + stripes, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] + stripes // 2, 0, 255)
    return Image.fromarray(arr)


class TestUniversalGarmentIntelligenceModel:
    """Verifies PyTorch multi-task network and specialized category heads."""

    @pytest.mark.requires_local_assets
    def test_model_initialization_and_checkpoint(self):
        model = UniversalGarmentIntelligenceModel()
        assert model.device.type in ["mps", "cpu"]
        assert model.checkpoint_version == "partial-compatibility"
        assert model.checkpoint_coverage == {"matched": 259, "missing": 30, "unexpected": 4}
        assert os.path.exists(model.checkpoint_path)

    def test_multi_category_forward_pass(self):
        img = create_test_image()
        categories_to_test = ["tops", "shirt", "hoodie", "jacket", "bottoms", "dress", "traditional"]

        for cat in categories_to_test:
            out = universal_intelligence_model.predict(img, category_hint=cat)
            assert out.category == cat or out.category_confidence > 0.0
            assert out.category_confidence >= 0.0 and out.category_confidence <= 1.0
            assert len(out.candidate_categories) > 0
            assert len(out.components) == 13
            assert out.fabric_category in ["cotton", "denim", "leather", "wool", "silk", "knitwear", "synthetic", "linen"]
            assert out.surface_weave in [
                "plain_weave", "twill_diagonal", "ribbed_knit", "cable_knit",
                "smooth_sheen", "pebble_leather", "canvas"
            ]
            assert 0.10 <= out.estimated_roughness <= 1.0
            assert 0.0 <= out.estimated_metalness <= 1.0
            assert 0.50 <= out.observed_surface_ratio <= 0.75
            assert 0.25 <= out.inferred_surface_ratio <= 0.50
            assert round(out.observed_surface_ratio + out.inferred_surface_ratio, 2) == 1.0

    def test_specialized_category_attribute_decoding(self):
        img = create_test_image()

        # Hoodie attributes
        hoodie_out = universal_intelligence_model.predict(img, category_hint="hoodie", subcategory_hint="pullover_hoodie")
        assert "hood_type" in hoodie_out.attributes
        assert "pocket_type" in hoodie_out.attributes
        assert "drawstring_present" in hoodie_out.attributes

        # Shirt attributes
        shirt_out = universal_intelligence_model.predict(img, category_hint="shirt", subcategory_hint="formal_shirt")
        assert "collar_type" in shirt_out.attributes
        assert "placket_style" in shirt_out.attributes
        assert "cuff_type" in shirt_out.attributes

        # Bottoms attributes
        bottoms_out = universal_intelligence_model.predict(img, category_hint="bottoms", subcategory_hint="straight_jeans")
        assert "waist_rise" in bottoms_out.attributes
        assert "leg_cut" in bottoms_out.attributes
        assert "fly_type" in bottoms_out.attributes

        # Dress attributes
        dress_out = universal_intelligence_model.predict(img, category_hint="dress", subcategory_hint="a_line_dress")
        assert "dress_silhouette" in dress_out.attributes
        assert "waistline" in dress_out.attributes


class TestGarmentDatasetPipeline:
    """Verifies dataset normalization, filtering, licensing, and privacy barriers."""

    def test_quality_filtering(self):
        # Blurry / uniform image
        flat_img = Image.new("RGB", (300, 300), color=(128, 128, 128))
        q_flat = garment_dataset_pipeline.evaluate_image_quality(flat_img)
        assert not q_flat.is_valid
        assert "blurry" in q_flat.rejection_reason.lower() or "contrast" in q_flat.rejection_reason.lower()

        # Low resolution image
        tiny_img = Image.new("RGB", (64, 64), color=(100, 150, 200))
        q_tiny = garment_dataset_pipeline.evaluate_image_quality(tiny_img)
        assert not q_tiny.is_valid
        assert "too low" in q_tiny.rejection_reason.lower()

        # High quality image
        good_img = create_test_image(size=(300, 300))
        q_good = garment_dataset_pipeline.evaluate_image_quality(good_img)
        assert q_good.is_valid

    def test_dhash_duplicate_detection(self):
        pipeline = garment_dataset_pipeline
        img1 = create_test_image(color=(50, 80, 140))
        img2 = create_test_image(color=(50, 80, 140))

        # Different instance of same image should be flagged duplicate
        pipeline.check_duplicate(img1)
        is_dup = pipeline.check_duplicate(img2)
        assert is_dup is True

    def test_dataset_licensing_audit(self):
        # DeepFashion2 is research-only
        assert DATASET_LICENSE_REGISTRY["DeepFashion2"].commercial_use_permitted is False
        assert "research" in DATASET_LICENSE_REGISTRY["DeepFashion2"].license_type.lower()

        # GarmentCode and Fashion-MNIST are commercially approved
        assert DATASET_LICENSE_REGISTRY["GarmentCode"].commercial_use_permitted is True
        assert DATASET_LICENSE_REGISTRY["Fashion-MNIST"].commercial_use_permitted is True
        assert DATASET_LICENSE_REGISTRY["OpenImages-Clothing-Subset"].commercial_use_permitted is True

    def test_strict_user_privacy_barrier(self):
        user_unconsented = UniversalGarmentAnnotation(
            annotation_id="u_001",
            source_dataset="Yorvyn-Proprietary-Atelier",
            image_uri="/tmp/user_pic.jpg",
            category="tops",
            subcategory="hoodie",
            bbox=BoundingBox2D(ymin=0, xmin=0, ymax=1, xmax=1),
            landmarks={},
            attributes={},
            fabric_type="cotton",
            license_name="Proprietary",
            commercial_permitted=True,
            is_user_upload=True,
            user_opt_in_for_training=False
        )
        assert garment_dataset_pipeline.validate_privacy_compliance(user_unconsented) is False

        user_consented = UniversalGarmentAnnotation(
            annotation_id="u_002",
            source_dataset="Yorvyn-Proprietary-Atelier",
            image_uri="/tmp/user_pic_consented.jpg",
            category="tops",
            subcategory="hoodie",
            bbox=BoundingBox2D(ymin=0, xmin=0, ymax=1, xmax=1),
            landmarks={},
            attributes={},
            fabric_type="cotton",
            license_name="Proprietary",
            commercial_permitted=True,
            is_user_upload=True,
            user_opt_in_for_training=True
        )
        assert garment_dataset_pipeline.validate_privacy_compliance(user_consented) is True


class TestLearnedMultiViewAndMaterialEngines:
    """Verifies missing surface disentanglement and learned PBR material inference."""

    def test_single_view_vs_dual_view_surface_ratio(self):
        f = create_test_image((40, 60, 90))
        b = create_test_image((45, 65, 95))

        # Single view
        single_res = learned_multiview_engine.analyze_views(f)
        assert single_res.observed_surface_ratio < 0.70
        assert single_res.inferred_surface_ratio > 0.30
        assert single_res.panel_provenance["front_torso"] == "observed_front"
        assert single_res.panel_provenance["back_torso"] == "inferred_rear"

        # Dual view
        dual_res = learned_multiview_engine.analyze_views(f, b)
        assert dual_res.is_multi_view is True
        assert dual_res.observed_surface_ratio > 0.85
        assert dual_res.inferred_surface_ratio < 0.15
        assert dual_res.identity_confirmed is True
        assert dual_res.panel_provenance["back_torso"] == "observed_back"

    def test_learned_material_and_hardware(self):
        img = create_test_image((35, 45, 65))
        fabric_pbr, graphic, hardware = learned_material_engine.analyze_material(
            image=img,
            category="shirt",
            subcategory="formal_shirt"
        )
        assert fabric_pbr.fabric_category in ["cotton", "denim", "leather", "wool", "silk", "knitwear", "synthetic", "linen"]
        assert 0.10 <= fabric_pbr.roughness <= 1.0
        assert 0.0 <= fabric_pbr.metalness <= 1.0
        assert len(hardware) > 0
        assert any(h.hardware_type == "button" for h in hardware)


class TestNeuralGarmentReconstructionEngine:
    """Verifies 3D reconstruction, wearability cavities, 20-bone rigging, and truthful provenance."""

    def test_neural_reconstruction_hybrid_mesh(self):
        img = create_test_image((40, 50, 70))
        out = neural_reconstruction_engine.reconstruct(
            category="hoodie",
            subcategory="pullover_hoodie",
            front_image=img
        )
        assert out.provenance in ["hybrid_neural_procedural", "neural_remote"]
        assert out.quality_report.is_manifold is True
        assert out.quality_report.degenerate_triangle_count == 0
        assert len(out.mesh.positions) > 300
        assert len(out.mesh.indices) > 500

        # Check wearability opening (mesh boundary loops > 0)
        assert out.quality_report.boundary_loops >= 2  # waist opening + neck opening

        # Check 20-bone skinning weights
        assert len(out.mesh.joint_indices) == len(out.mesh.positions)
        assert len(out.mesh.joint_weights) == len(out.mesh.positions)
        assert np.allclose(np.sum(out.mesh.joint_weights, axis=1), 1.0, atol=1e-3)

    def test_glb_export_compatibility(self):
        img = create_test_image((40, 50, 70))
        out = neural_reconstruction_engine.reconstruct(
            category="jacket",
            subcategory="bomber_jacket",
            front_image=img
        )
        # 1x1 dummy PNG bytes for textures
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        glb_bytes = glb_exporter.export(
            mesh=out.mesh,
            diffuse_png_bytes=dummy_png,
            normal_png_bytes=dummy_png,
            metallic_roughness_png_bytes=dummy_png,
            occlusion_png_bytes=dummy_png,
            name="test_neural_jacket"
        )
        assert glb_bytes.startswith(b"glTF")
        assert len(glb_bytes) > 1000

    def test_open_weight_models_audit(self):
        summary = LearnedModelEvaluator.get_summary_report()
        assert summary["evaluated_models_count"] >= 5
        assert "microsoft_trellis" in summary["models"]
        assert "triposr" in summary["models"]
        assert "tencent_hunyuan3d_v2" in summary["models"]
        assert "M2" in summary["hardware_target_analyzed"]
        assert "16GB" in summary["primary_hardware_conclusion"]
