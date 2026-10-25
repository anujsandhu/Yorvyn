"""
End-to-end integration test for Yorvyn AI Photo-to-3D Garment Generation Pipeline.
Tests upload, segmentation, geometry construction, texture generation, GLB packaging,
preview thumbnail rendering, temporary privacy cleanup, and wardrobe persistence.
"""

import os
import sys
import time
import io
import requests
from PIL import Image, ImageDraw

API_BASE = "http://127.0.0.1:8002/api/fashion"


def create_mock_garment_image() -> bytes:
    """Creates a sample navy blue crewneck t-shirt with a golden chest logo and textured seams."""
    img = Image.new("RGB", (600, 700), (245, 245, 245)) # Clean background
    draw = ImageDraw.Draw(img)
    
    # Draw navy T-shirt silhouette
    navy_col = (15, 23, 42)
    # Torso
    draw.polygon([
        (220, 160), # Neck left
        (150, 200), # Shoulder left
        (90, 290),  # Sleeve left outer
        (140, 330), # Sleeve left inner
        (185, 275), # Armpit left
        (185, 580), # Hem left
        (415, 580), # Hem right
        (415, 275), # Armpit right
        (460, 330), # Sleeve right inner
        (510, 290), # Sleeve right outer
        (450, 200), # Shoulder right
        (380, 160), # Neck right
    ], fill=navy_col)
    
    # Neckline curve
    draw.chord((240, 140, 360, 220), start=0, end=180, fill=(245, 245, 245))
    
    # Chest logo (golden geometric emblem)
    gold_col = (217, 164, 65)
    draw.polygon([(300, 260), (330, 310), (270, 310)], fill=gold_col)
    draw.ellipse((290, 280, 310, 300), fill=navy_col)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_pipeline():
    print("🚀 [TEST] Starting AI Photo-to-3D Garment Pipeline test...")
    
    # 1. Generate test image
    img_bytes = create_mock_garment_image()
    print(f"✓ Mock garment photograph created ({len(img_bytes)} bytes)")
    
    # 2. Submit job
    files = {
        "front_image": ("navy_shirt.jpg", img_bytes, "image/jpeg")
    }
    data = {
        "category": "top",
        "user_id": "test_user"
    }
    
    resp = requests.post(f"{API_BASE}/garment-gen/jobs", files=files, data=data)
    assert resp.status_code == 200, f"Job submission failed: {resp.text}"
    job_info = resp.json()
    job_id = job_info["job_id"]
    print(f"✓ Job created: {job_id} (status: {job_info['status']})")
    
    # 3. Poll job status
    max_wait = 20
    start_time = time.time()
    completed = False
    
    while time.time() - start_time < max_wait:
        poll_resp = requests.get(f"{API_BASE}/garment-gen/jobs/{job_id}")
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()
        print(f"  ... [{poll_data['progress']}%] {poll_data['current_stage']}")
        
        if poll_data["status"] == "completed":
            completed = True
            break
        elif poll_data["status"] == "failed":
            raise RuntimeError(f"Job failed with error: {poll_data.get('error')}")
            
        time.sleep(0.5)
        
    assert completed, "Job did not complete within timeout window"
    print("✓ Job completed successfully!")
    
    res = poll_data["result"]
    assert res is not None
    print(f"✓ Generated Garment: '{res['garment_name']}'")
    print(f"  - Category: {res['category']} / {res['subcategory']}")
    print(f"  - Detected Color: {res['features']['primary_color_name']} ({res['features']['primary_color_hex']})")
    print(f"  - Pattern: {res['features']['pattern']}")
    print(f"  - Vertices: {res['mesh_vertex_count']}, Triangles: {res['mesh_triangle_count']}")
    print(f"  - GLB URL: {res['glb_url']}")
    print(f"  - Thumbnail URL: {res['thumbnail_url']}")
    
    # 4. Verify GLB asset download
    glb_resp = requests.get(f"http://127.0.0.1:8002{res['glb_url']}")
    assert glb_resp.status_code == 200, f"Failed to download GLB: {glb_resp.status_code}"
    assert glb_resp.content[:4] == b"glTF", "Downloaded asset does not have glTF magic header!"
    print(f"✓ Valid binary GLB asset verified ({len(glb_resp.content)} bytes)")
    
    # 5. Verify 3D rendered thumbnail download
    thumb_resp = requests.get(f"http://127.0.0.1:8002{res['thumbnail_url']}")
    assert thumb_resp.status_code == 200
    assert thumb_resp.content[:8] == b"\x89PNG\r\n\x1a\n", "Thumbnail is not a valid PNG!"
    print(f"✓ Valid 3D rendered preview thumbnail verified ({len(thumb_resp.content)} bytes)")
    
    # 6. Verify PRIVACY CLEANUP: Original uploaded image must be completely erased from /tmp!
    temp_folder = f"/tmp/yorvyn_garment_pipeline/{job_id}"
    assert not os.path.exists(temp_folder), f"PRIVACY VIOLATION: Temporary folder {temp_folder} was NOT deleted!"
    print("✓ PRIVACY AUDIT PASSED: Temporary input photograph was completely purged from disk.")
    
    # 7. Save to Wardrobe
    save_resp = requests.post(f"{API_BASE}/garment-gen/jobs/{job_id}/save?user_id=test_user")
    assert save_resp.status_code == 200, f"Failed to save to wardrobe: {save_resp.text}"
    saved_data = save_resp.json()
    assert saved_data["success"] is True
    print(f"✓ Saved to My Wardrobe: ID = {saved_data['item']['id']}")
    
    # 8. Query My Wardrobe
    wardrobe_resp = requests.get(f"{API_BASE}/wardrobe?user_id=test_user")
    assert wardrobe_resp.status_code == 200
    items = wardrobe_resp.json()["items"]
    custom_items = [i for i in items if i.get("id") == f"3d_{job_id}"]
    assert len(custom_items) == 1, "Saved 3D item not found in user wardrobe query!"
    saved_item = custom_items[0]
    assert saved_item.get("is_custom_3d") is True
    assert saved_item.get("glb_url") == res["glb_url"]
    assert saved_item.get("image_url") == res["thumbnail_url"] # 3D preview, NOT original photo
    print("✓ Digital Wardrobe persistence verified with custom 3D asset link.")
    
    print("\n🎉 ALL PIPELINE TESTS PASSED!")


if __name__ == "__main__":
    test_pipeline()
