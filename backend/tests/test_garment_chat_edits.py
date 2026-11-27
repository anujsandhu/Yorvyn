"""Check candidate edits against independent GLB parsing and known vertex positions."""
import io
import json
import struct

import numpy as np
import pytest
from PIL import Image

from backend.app.services.garments.chat_candidate import edit_candidate, remove_invalid_triangles
from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from backend.app.services.garments.glb_exporter import glb_exporter


def fixture():
    points = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],dtype=float)
    faces = np.array([[0,1,2],[1,2,0],[0,0,0],[0,3,1]])
    mesh = GarmentMesh(points,np.tile([0,0,1],(4,1)),np.zeros((4,2)),faces)
    image = io.BytesIO()
    Image.new("RGB",(4,4),"white").save(image,format="PNG")
    return glb_exporter.export(mesh,image.getvalue(),image.getvalue())


def unpack(data):
    length = struct.unpack_from("<I",data,12)[0]
    return json.loads(data[20:20+length]), data[28+length:]


def test_material_preserves_binary_and_texture_links():
    source = fixture()
    original, binary = unpack(source)
    edited, result = unpack(edit_candidate(source,"denim"))
    assert result == binary
    assert edited["textures"] == original["textures"]
    assert edited["materials"][0]["pbrMetallicRoughness"]["roughnessFactor"] == .92


@pytest.mark.parametrize("operation,expected", [("widen",[1.1,1,1]),("shorten",[1,.9,1])])
def test_dimensions_after_edit(operation,expected):
    import trimesh
    source = fixture()
    edited = trimesh.load(io.BytesIO(edit_candidate(source,operation)),file_type="glb")
    np.testing.assert_allclose(edited.extents, expected, atol=1e-6)
    with pytest.raises(ValueError):
        edit_candidate(source,"arbitrary_tool")
    with pytest.raises(ValueError,match="isolated"):
        edit_candidate(source,"widen_sleeves")


def test_index_repair_preserves_attributes_and_removes_only_bad_faces():
    model, data = unpack(remove_invalid_triangles(fixture()))
    prim = model["meshes"][0]["primitives"][0]
    indices = model["accessors"][prim["indices"]]
    view = model["bufferViews"][indices["bufferView"]]
    result = np.frombuffer(data,dtype="<u4",count=indices["count"],offset=view["byteOffset"])
    assert result.tolist() == [0,1,2,0,3,1]
    _, original = unpack(fixture())
    assert data.startswith(original)


def test_failed_provider_records_local_plan_without_live_usage(monkeypatch):
    from backend.app.services.llm.garment_plan import llm_registry, plan_turn

    class Unavailable:
        def health_check(self):
            return True

        def generate(self, *args, **kwargs):
            raise TimeoutError

    monkeypatch.setenv("GARMENT_CHAT_PLANNER", "test_provider")
    monkeypatch.setenv("GARMENT_CHAT_FALLBACK_PLANNER", "offline_rules")
    monkeypatch.setattr(llm_registry, "get_provider", lambda name: Unavailable())
    plan, trace = plan_turn("Create a 3D model of this denim jacket", True, False)
    assert plan.action == "reconstruct"
    assert trace == {"provider": "local_rules", "previous_attempts": [
        {"provider": "test_provider", "status": "failed", "error_type": "TimeoutError", "error": "TIMEOUT",
         "upstream_request_id": None, "upstream_model": None}]}


def test_unsupported_component_edit_keeps_current_shape(monkeypatch):
    from backend.app.services.llm.garment_plan import plan_turn

    monkeypatch.setenv("GARMENT_CHAT_PLANNER", "offline_rules")
    plan, _ = plan_turn("Make the collar wider", False, True)
    assert plan.action == "clarify"


def test_retry_after_input_purge_preserves_failure(monkeypatch, tmp_path):
    from datetime import datetime
    from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus
    from backend.app.services.garments import job_manager

    monkeypatch.setattr(job_manager, "TEMP_BASE_DIR", str(tmp_path))
    job = GarmentGenJob(job_id="expired-photos", user_id="owner", status=GarmentGenJobStatus.FAILED,
                        created_at=datetime.utcnow(), updated_at=datetime.utcnow(), error="Original failure")
    manager = job_manager.garment_job_manager
    monkeypatch.setitem(manager._jobs, job.job_id, job)
    assert manager.retry_job(job.job_id) is None
    assert job.retry_count == 0 and job.error == "Original failure"
    assert job.status == GarmentGenJobStatus.FAILED


def test_reencoded_view_references_the_original_photo(monkeypatch):
    from PIL.PngImagePlugin import PngInfo
    from backend.app.services.ai.multiview.fusion_engine import multi_view_fusion_engine

    image = Image.new("RGB", (32, 32), "white")
    files = []
    for label in ("original", "copy"):
        metadata = PngInfo()
        metadata.add_text("source", label)
        buf = io.BytesIO()
        image.save(buf, "PNG", pnginfo=metadata)
        files.append((label, buf.getvalue(), None))
    monkeypatch.setattr(multi_view_fusion_engine.classifier, "evaluate_quality",
                        lambda image: {"quality_score": 0, "resolution": [32, 32], "image_usable": False})
    views = multi_view_fusion_engine.fuse_garment_views(files).views
    assert views[1].image_hash != views[0].image_hash
    assert views[1].duplicate_of_image_id == views[0].image_id
    assert views[1].duplicate_type == "perceptual_near_duplicate"
    assert not views[1].usable
