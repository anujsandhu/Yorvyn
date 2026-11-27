"""
YORVYN — Phase 13.5: Multi-Component Garment Reconstruction & Scene Hierarchy Test Suite
Tests:
- Component graph model and data contracts
- Category-specific multi-component reconstruction (Hoodie, Shirt, Jacket, Bottoms, Dress, Tops)
- Exact triangle coverage and bounding box computation
- Multi-component glTF/GLB export with scene hierarchy and component extras
- Trimesh deserialization of multi-primitive GLB assets
- Multi-view depth calibration and explicit uncertainty modeling
- Topological validation and non-overlapping boundary checks
"""

import io
import json
import numpy as np
from PIL import Image
import trimesh

from backend.app.services.garments.reconstruction.base_reconstruction_engine import (
    GarmentComponentGraph,
    GarmentComponentNode,
    compute_component_bounds
)
from backend.app.services.garments.reconstruction.hoodie_engine import HoodieReconstructionEngine
from backend.app.services.garments.reconstruction.shirt_engine import ShirtReconstructionEngine
from backend.app.services.garments.reconstruction.jacket_engine import JacketReconstructionEngine
from backend.app.services.garments.reconstruction.bottoms_engine import BottomsReconstructionEngine
from backend.app.services.garments.reconstruction.dress_engine import DressReconstructionEngine
from backend.app.services.garments.reconstruction.tops_engine import TopsReconstructionEngine
from backend.app.services.garments.reconstruction.mesh_validator import GarmentMeshValidator
from backend.app.services.garments.reconstruction.multi_view_fuser import MultiViewGarmentFuser
from backend.app.services.garments.fitting import universal_garment_fitting_engine
from backend.app.services.garments.glb_exporter import glb_exporter


class TestPhase135MultiComponentReconstruction:
    """Rigorous verification of Phase 13.5 component graph architecture."""

    def test_hoodie_multi_component_architecture(self):
        """Verifies hoodie contains all 10 distinct physical components with proper DAG hierarchy."""
        engine = HoodieReconstructionEngine()
        out = engine.reconstruct()

        assert out.component_graph is not None
        graph = out.component_graph
        nodes = graph.nodes

        # Must contain all 10 category components
        expected_components = [
            "main_torso",
            "ribbed_waistband",
            "left_sleeve",
            "left_cuff",
            "right_sleeve",
            "right_cuff",
            "hood_cowl",
            "kangaroo_pocket",
            "eyelets",
            "drawstrings"
        ]
        for comp_id in expected_components:
            assert comp_id in nodes, f"Missing expected component '{comp_id}' in hoodie"

        # Hierarchy validation
        assert nodes["main_torso"].parent_id is None
        assert nodes["ribbed_waistband"].parent_id == "main_torso"
        assert nodes["hood_cowl"].parent_id == "main_torso"
        assert nodes["kangaroo_pocket"].parent_id == "main_torso"
        assert nodes["left_sleeve"].parent_id == "main_torso"
        assert nodes["left_cuff"].parent_id == "left_sleeve"
        assert nodes["right_sleeve"].parent_id == "main_torso"
        assert nodes["right_cuff"].parent_id == "right_sleeve"
        assert nodes["eyelets"].parent_id == "main_torso"
        assert nodes["drawstrings"].parent_id == "eyelets"

        # Semantic roles & attachments
        assert nodes["hood_cowl"].semantic_type == "hood"
        assert nodes["hood_cowl"].attachment_location == "neckline_seam"
        assert nodes["kangaroo_pocket"].semantic_type == "pocket"
        assert nodes["kangaroo_pocket"].attachment_location == "lower_abdomen"
        assert nodes["ribbed_waistband"].material_assignment == "ribbed_trim"
        assert nodes["eyelets"].material_assignment == "metallic_hardware"

        # Physical 3D dimensions
        dims_hood = nodes["hood_cowl"].dimensions_m
        assert dims_hood[0] > 0.20 and dims_hood[1] > 0.20, f"Hood dimensions unexpected: {dims_hood}"
        dims_pocket = nodes["kangaroo_pocket"].dimensions_m
        assert dims_pocket[0] > 0.20 and dims_pocket[1] > 0.15, f"Pocket dimensions unexpected: {dims_pocket}"

        # Exact triangle coverage
        tri_sum = sum(node.triangle_range[1] for node in nodes.values())
        assert tri_sum == len(out.mesh.indices), f"Triangle mismatch: {tri_sum} vs {len(out.mesh.indices)}"

        # Topological validation
        val_res = GarmentMeshValidator.validate_component_graph(out.mesh, graph)
        assert val_res["is_valid"] is True, f"Component graph validation failed: {val_res['issues']}"

    def test_shirt_multi_component_architecture(self):
        """Verifies formal/casual shirt contains upright collar stand, front placket, sleeves, and barrel cuffs."""
        engine = ShirtReconstructionEngine()
        out = engine.reconstruct()

        assert out.component_graph is not None
        graph = out.component_graph
        nodes = graph.nodes

        expected = ["main_torso", "collar_stand", "front_placket_band", "left_sleeve", "left_cuff", "right_sleeve", "right_cuff"]
        for c in expected:
            assert c in nodes, f"Missing shirt component '{c}'"

        assert nodes["collar_stand"].parent_id == "main_torso"
        assert nodes["collar_stand"].semantic_type == "collar"
        assert nodes["front_placket_band"].parent_id == "main_torso"
        assert nodes["front_placket_band"].semantic_type == "placket"
        assert nodes["left_cuff"].parent_id == "left_sleeve"
        assert nodes["right_cuff"].parent_id == "right_sleeve"

        tri_sum = sum(node.triangle_range[1] for node in nodes.values())
        assert tri_sum == len(out.mesh.indices)
        assert GarmentMeshValidator.validate_component_graph(out.mesh, graph)["is_valid"] is True

    def test_jacket_multi_component_architecture(self):
        """Verifies jacket supports both denim (shank buttons, flap pockets) and blazer (lapels, zipper) variants."""
        engine = JacketReconstructionEngine()

        # 1. Denim Jacket
        denim_out = engine.reconstruct(subcategory="denim_jacket")
        denim_nodes = denim_out.component_graph.nodes
        assert "denim_point_collar" in denim_nodes
        assert "button_placket" in denim_nodes
        assert "chest_flap_pockets" in denim_nodes
        assert "left_sleeve" in denim_nodes and "left_cuff" in denim_nodes
        denim_sum = sum(n.triangle_range[1] for n in denim_nodes.values())
        assert denim_sum == len(denim_out.mesh.indices)

        # 2. Blazer / Formal Outerwear
        blazer_out = engine.reconstruct(subcategory="blazer")
        blazer_nodes = blazer_out.component_graph.nodes
        assert "lapels_and_collar" in blazer_nodes
        assert "front_zipper_track" in blazer_nodes
        blazer_sum = sum(n.triangle_range[1] for n in blazer_nodes.values())
        assert blazer_sum == len(blazer_out.mesh.indices)

    def test_bottoms_multi_component_architecture(self):
        """Verifies trousers and shorts decompose into waistband/pelvis, leg tubes, and cuff openings."""
        engine = BottomsReconstructionEngine()

        # Jeans
        jeans_out = engine.reconstruct(subcategory="jeans")
        j_nodes = jeans_out.component_graph.nodes
        assert "waistband_and_pelvis" in j_nodes
        assert "left_leg" in j_nodes and "left_cuff" in j_nodes
        assert "right_leg" in j_nodes and "right_cuff" in j_nodes
        assert j_nodes["left_cuff"].parent_id == "left_leg"
        assert sum(n.triangle_range[1] for n in j_nodes.values()) == len(jeans_out.mesh.indices)

        # Shorts
        shorts_out = engine.reconstruct(subcategory="shorts")
        s_nodes = shorts_out.component_graph.nodes
        assert "waistband_and_pelvis" in s_nodes
        assert sum(n.triangle_range[1] for n in s_nodes.values()) == len(shorts_out.mesh.indices)

    def test_dress_and_skirt_multi_component_architecture(self):
        """Verifies dresses have bodice + waist connection + flared skirt drape, while skirts start at waistband."""
        engine = DressReconstructionEngine()

        # Full Dress
        dress_out = engine.reconstruct(subcategory="dress")
        d_nodes = dress_out.component_graph.nodes
        assert "upper_bodice" in d_nodes
        assert "waist_connection" in d_nodes
        assert "flared_skirt_drape" in d_nodes
        assert d_nodes["upper_bodice"].parent_id is None
        assert d_nodes["waist_connection"].parent_id == "upper_bodice"
        assert d_nodes["flared_skirt_drape"].parent_id == "waist_connection"
        assert sum(n.triangle_range[1] for n in d_nodes.values()) == len(dress_out.mesh.indices)

        # Standalone Skirt
        skirt_out = engine.reconstruct(subcategory="skirt")
        s_nodes = skirt_out.component_graph.nodes
        assert "waistband" in s_nodes
        assert "flared_skirt_drape" in s_nodes
        assert s_nodes["waistband"].parent_id is None
        assert s_nodes["flared_skirt_drape"].parent_id == "waistband"
        # Skirt top should be around waist Y (1.02m) NOT collarbone (1.42m)
        assert skirt_out.mesh.positions[:, 1].max() < 1.10
        assert sum(n.triangle_range[1] for n in s_nodes.values()) == len(skirt_out.mesh.indices)

    def test_tops_multi_component_architecture(self):
        """Verifies T-shirts and tank tops have proper torso, sleeves, and hem loop components."""
        engine = TopsReconstructionEngine()

        # T-Shirt
        t_out = engine.reconstruct(subcategory="tshirt", sleeve_length="short")
        t_nodes = t_out.component_graph.nodes
        assert "main_torso" in t_nodes
        assert "hem_loop" in t_nodes
        assert "left_sleeve" in t_nodes and "right_sleeve" in t_nodes
        assert sum(n.triangle_range[1] for n in t_nodes.values()) == len(t_out.mesh.indices)

        # Sleeveless Tank
        tank_out = engine.reconstruct(subcategory="tank_top", sleeve_length="sleeveless")
        tank_nodes = tank_out.component_graph.nodes
        assert "main_torso" in tank_nodes
        assert "hem_loop" in tank_nodes
        assert "left_sleeve" not in tank_nodes
        assert sum(n.triangle_range[1] for n in tank_nodes.values()) == len(tank_out.mesh.indices)

    def test_glb_multi_component_export_and_trimesh_deserialization(self):
        """Verifies GLB exporter produces a valid glTF 2.0 binary asset with full component hierarchy and Trimesh compatibility."""
        engine = HoodieReconstructionEngine()
        out = engine.reconstruct()

        im = Image.new("RGB", (64, 64), (120, 120, 120))
        b_buf = io.BytesIO()
        im.save(b_buf, format="PNG")
        tex_bytes = b_buf.getvalue()

        glb_data = glb_exporter.export(
            mesh=out.mesh,
            diffuse_png_bytes=tex_bytes,
            normal_png_bytes=tex_bytes,
            name="test_multi_comp_glb",
            component_graph=out.component_graph
        )

        assert len(glb_data) > 5000
        json_len = int.from_bytes(glb_data[12:16], "little")
        gltf = json.loads(glb_data[20:20 + json_len].decode("utf-8"))

        # Verify glTF scene hierarchy
        assert len(gltf["meshes"]) == 10
        assert len(gltf["nodes"]) >= 31 # 1 root + 10 components + 20 skeleton bones
        assert gltf["nodes"][0]["name"] == "test_multi_comp_glb"

        # Check extras metadata on component nodes
        comp_nodes_in_gltf = [n for n in gltf["nodes"] if "extras" in n and "component_id" in n["extras"]]
        assert len(comp_nodes_in_gltf) == 10

        c_hood = next(n for n in comp_nodes_in_gltf if n["extras"]["component_id"] == "hood_cowl")
        assert c_hood["extras"]["semantic_type"] == "hood"
        assert len(c_hood["extras"]["dimensions_m"]) == 3
        assert c_hood["extras"]["attachment_location"] == "neckline_seam"

        # Verify Trimesh loading
        scene = trimesh.load(io.BytesIO(glb_data), file_type="glb")
        assert len(scene.geometry) == 10

    def test_multiview_depth_calibration_and_uncertainty(self):
        """Verifies explicit uncertainty modeling: single-view default vs multi-view side calibrated."""
        engine = HoodieReconstructionEngine()
        rec_out = engine.reconstruct()

        # Single-view: initial uncertainty status
        assert rec_out.component_graph.nodes["hood_cowl"].uncertainty_status == "estimated_single_view"
        assert rec_out.component_graph.nodes["hood_cowl"].depth_confidence == 0.65

        # Fuse with authentic back and side images
        f_img = Image.new("RGBA", (100, 100), (80, 80, 80, 255))
        b_img = Image.new("RGBA", (100, 100), (80, 80, 80, 255))
        s_img = Image.new("RGBA", (100, 100), (80, 80, 80, 255))

        fused = MultiViewGarmentFuser.fuse_views(
            reconstruction=rec_out,
            front_image=f_img,
            back_image=b_img,
            side_image=s_img
        )

        assert fused.component_graph.nodes["hood_cowl"].uncertainty_status == "calibrated_multiview"
        assert fused.component_graph.nodes["hood_cowl"].depth_confidence == 0.95

    def test_multi_body_type_fitting_and_clearance_validation(self):
        """Verifies multi-component garments fit cleanly across slim, regular, athletic, and plus body archetypes."""
        category_cases = [
            (HoodieReconstructionEngine(), "tops", "hoodie", "cotton"),
            (ShirtReconstructionEngine(), "tops", "formal_shirt", "cotton"),
            (JacketReconstructionEngine(), "outerwear", "denim_jacket", "denim"),
            (BottomsReconstructionEngine(), "bottoms", "trousers", "wool"),
            (DressReconstructionEngine(), "dresses_and_skirts", "dress", "silk"),
            (TopsReconstructionEngine(), "tops", "tshirt", "cotton"),
        ]
        archetypes = ["slim_lean", "standard_175", "athletic_broad", "plus_curvy"]

        for engine, category, subcategory, fabric in category_cases:
            rec_out = engine.reconstruct(category=category, subcategory=subcategory)
            assert rec_out.component_graph is not None

            for archetype in archetypes:
                fitted_mesh, fit_res = universal_garment_fitting_engine.fit_garment(
                    mesh=rec_out.mesh,
                    category=category,
                    subcategory=subcategory,
                    avatar_profile_id=archetype,
                    fabric_type=fabric,
                    job_id=f"test_{subcategory}_{archetype}"
                )

                assert fit_res.collision.penetration_count == 0, f"Penetration on {subcategory}/{archetype}"
                assert fit_res.collision.min_clearance_guaranteed_mm == 3.0
                assert fit_res.animation_deformation.deformation_stability_score > 0.85, (
                    f"Low pose stability on {subcategory}/{archetype}: {fit_res.animation_deformation.deformation_stability_score}"
                )
                assert fit_res.animation_deformation.normal_inversion_count == 0
                assert len(fitted_mesh.indices) == len(rec_out.mesh.indices)

                graph_check = GarmentMeshValidator.validate_component_graph(fitted_mesh, rec_out.component_graph)
                assert graph_check["is_valid"] is True, (
                    f"Component graph invalid after fitting {subcategory}/{archetype}: {graph_check['issues']}"
                )

    def test_jacket_smooth_silhouette_contour_tracking(self):
        """Verifies upgraded 24-ring jacket torso accurately tracks photo silhouette width profiles without sparse slice gaps."""
        engine = JacketReconstructionEngine()

        # Synthetic silhouette mask: wide shoulders, tapered waist, flared hem
        arr = np.zeros((160, 120, 4), dtype=np.uint8)
        for y in range(15, 145):
            t = (y - 15) / 130.0
            half_w = int(42 - 14 * np.sin(t * np.pi) + (6 if t > 0.7 else 0))
            arr[y, 60 - half_w:60 + half_w] = [40, 70, 130, 255]
        sil_img = Image.fromarray(arr, mode="RGBA")

        out = engine.reconstruct(category="outerwear", subcategory="denim_jacket", front_image=sil_img)
        assert out.component_graph is not None
        assert len(out.mesh.positions) > 900, "Expected high-resolution 24-ring jacket torso geometry"

        # Compare waist vs shoulder X span to confirm contour modulation
        main_torso = out.component_graph.nodes["main_torso"]
        v0, vcnt = main_torso.vertex_range
        torso_verts = out.mesh.positions[v0:v0 + vcnt]
        top_slice = torso_verts[torso_verts[:, 1] > 1.38]
        waist_slice = torso_verts[(torso_verts[:, 1] > 1.10) & (torso_verts[:, 1] < 1.18)]
        top_span = float(top_slice[:, 0].max() - top_slice[:, 0].min())
        waist_span = float(waist_slice[:, 0].max() - waist_slice[:, 0].min())
        assert top_span > waist_span, f"Expected jacket waist ({waist_span:.3f}) narrower than top ({top_span:.3f})"
