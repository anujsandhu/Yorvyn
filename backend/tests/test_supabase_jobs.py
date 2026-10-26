"""
Automated Unit Tests for Supabase PostgreSQL Database Repository and Job Persistence.
Validates:
1. User profile creation and retrieval
2. Wardrobe item insertion and category filtering
3. Garment 3D generation job state tracking and updates
4. Legacy identity mapping (Firebase UID to Supabase UUID)
"""

import uuid
from backend.app.services.database.supabase_repository import SupabaseRepository


def test_supabase_profile_lifecycle():
    repo = SupabaseRepository()
    user_id = str(uuid.uuid4())
    profile_data = {
        "display_name": "Elena Rostova",
        "avatar_url": "https://res.cloudinary.com/yorvyn/avatar1.png",
        "bio": "Haute couture & digital atelier enthusiast",
        "aesthetic_preferences": {"colors": ["sky_blue", "white"], "style": "minimalist"}
    }

    saved = repo.upsert_profile(user_id, profile_data)
    assert saved["user_id"] == user_id
    assert saved["display_name"] == "Elena Rostova"

    retrieved = repo.get_profile(user_id)
    assert retrieved is not None
    assert retrieved["display_name"] == "Elena Rostova"
    assert retrieved["bio"] == profile_data["bio"]


def test_supabase_wardrobe_items():
    repo = SupabaseRepository()
    user_id = str(uuid.uuid4())

    item_top = {
        "item_id": f"item_{uuid.uuid4().hex[:8]}",
        "title": "Cashmere Knit Sweater",
        "category": "tops",
        "cloudinary_url": "https://res.cloudinary.com/yorvyn/cashmere.png",
        "mesh_path": "/assets/garments/cashmere.glb",
        "color": "sky_blue"
    }

    item_bottom = {
        "item_id": f"item_{uuid.uuid4().hex[:8]}",
        "title": "Pleated Wool Trousers",
        "category": "bottoms",
        "cloudinary_url": "https://res.cloudinary.com/yorvyn/trousers.png",
        "mesh_path": "/assets/garments/trousers.glb",
        "color": "charcoal"
    }

    repo.insert_wardrobe_item(user_id, item_top)
    repo.insert_wardrobe_item(user_id, item_bottom)

    all_items = repo.get_wardrobe_items(user_id)
    assert len(all_items) == 2

    tops = repo.get_wardrobe_items(user_id, category="tops")
    assert len(tops) == 1
    assert tops[0]["title"] == "Cashmere Knit Sweater"


def test_supabase_garment_jobs_lifecycle():
    repo = SupabaseRepository()
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    user_id = str(uuid.uuid4())

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "queued",
        "category": "jackets",
        "pipeline_version": "2.0-photogrammetry"
    }

    # 1. Create Queued Job
    repo.save_job(job_data)
    job = repo.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"

    # 2. Update to Processing
    job["status"] = "processing"
    repo.save_job(job)
    assert repo.get_job(job_id)["status"] == "processing"

    # 3. Complete with Cloudinary Asset Metadata
    job["status"] = "completed"
    job["cloudinary_asset_id"] = f"yorvyn/users/{user_id[:8]}/garments/{job_id}"
    job["cloudinary_url"] = "https://res.cloudinary.com/yorvyn/preview.png"
    repo.save_job(job)

    completed_job = repo.get_job(job_id)
    assert completed_job["status"] == "completed"
    assert "cloudinary_url" in completed_job


def test_supabase_legacy_identity_relinking():
    repo = SupabaseRepository()
    firebase_uid = "legacy_firebase_user_99x"
    supabase_uuid = str(uuid.uuid4())
    email = "legacy_member@yorvyn.com"

    result = repo.relink_legacy_user(firebase_uid, supabase_uuid, email)
    assert result["firebase_uid"] == firebase_uid
    assert result["supabase_user_id"] == supabase_uuid
    assert result["email"] == email
