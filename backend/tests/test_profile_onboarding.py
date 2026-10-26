"""
Automated Unit Tests for User Profile Onboarding and Persistent Avatar Configuration.
Validates:
1. Retrieval of user profile with onboarding defaults
2. Updating onboarding attributes (age, height, skin tone, hair color, avatar configuration)
3. Transition of onboarding_completed to True
4. Prevention of cross-user profile leakage / separate user profiles
5. Pydantic request model validation
"""

import uuid
from backend.app.services.context_service import ContextService
from backend.app.api.fashion_routes import ProfileUpdateRequest


def test_default_user_profile():
    service = ContextService()
    profile = service.get_user_profile("test_user_new")
    assert profile is not None
    assert "name" in profile
    assert profile["user_id"] == "test_user_new"


def test_complete_onboarding_persistence():
    service = ContextService()
    user_id = str(uuid.uuid4())

    onboarding_data = {
        "display_name": "Maya Sterling",
        "name": "Maya Sterling",
        "age": 28,
        "height_value": 172.5,
        "height_unit": "cm",
        "body_type": "athletic",
        "skin_tone_id": "sand",
        "skin_tone_hex": "#e0a574",
        "hair_colour_id": "warm_chestnut",
        "hair_colour_hex": "#6a3b1a",
        "avatar_gender_presentation": "feminine",
        "avatar_configuration": {
            "gender": 0.1,
            "skinTint": "#e0a574",
            "hairColor": "#6a3b1a",
            "height": 0.52,
            "muscle": 0.75,
            "weight": 0.5
        },
        "onboarding_completed": True
    }

    # 1. Update Profile with Onboarding completion
    updated = service.update_user_profile(user_id, onboarding_data)
    assert updated["onboarding_completed"] is True
    assert updated["display_name"] == "Maya Sterling"
    assert updated["avatar_gender_presentation"] == "feminine"
    assert updated["avatar_configuration"]["skinTint"] == "#e0a574"

    # 2. Re-read to ensure state persistence
    reloaded = service.get_user_profile(user_id)
    assert reloaded["onboarding_completed"] is True
    assert reloaded["age"] == 28
    assert reloaded["skin_tone_hex"] == "#e0a574"
    assert reloaded["hair_colour_hex"] == "#6a3b1a"


def test_separate_user_profiles_isolation():
    service = ContextService()
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    service.update_user_profile(user_a, {
        "display_name": "User Alpha",
        "skin_tone_hex": "#f9d4b8",
        "onboarding_completed": True
    })

    service.update_user_profile(user_b, {
        "display_name": "User Beta",
        "skin_tone_hex": "#4a2912",
        "onboarding_completed": False
    })

    profile_a = service.get_user_profile(user_a)
    profile_b = service.get_user_profile(user_b)

    assert profile_a["display_name"] == "User Alpha"
    assert profile_a["skin_tone_hex"] == "#f9d4b8"
    assert profile_a["onboarding_completed"] is True

    assert profile_b["display_name"] == "User Beta"
    assert profile_b["skin_tone_hex"] == "#4a2912"
    assert profile_b["onboarding_completed"] is False


def test_profile_update_request_validation():
    req = ProfileUpdateRequest(
        display_name="Liam Parker",
        age=32,
        height_value=182.0,
        height_unit="cm",
        body_type="athletic",
        skin_tone_id="ivory",
        skin_tone_hex="#f3c299",
        hair_colour_id="jet_black",
        hair_colour_hex="#111111",
        avatar_gender_presentation="masculine",
        onboarding_completed=True
    )

    dumped = req.model_dump(exclude_none=True)
    assert dumped["display_name"] == "Liam Parker"
    assert dumped["age"] == 32
    assert dumped["avatar_gender_presentation"] == "masculine"
    assert dumped["onboarding_completed"] is True
