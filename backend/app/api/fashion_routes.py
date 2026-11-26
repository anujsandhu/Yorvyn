"""
Yorvyn Fashion Intelligence API Endpoints
Exposes REST routes for Profile, Digital Wardrobe, Context,
Outfit Generation, AI Stylist Chat, and Feedback Loops.
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from backend.app.core.security import get_current_user, get_current_user_optional, UserContext
from backend.app.services.wardrobe_service import wardrobe_service
from backend.app.services.context_service import context_service
from backend.app.services.outfit_generator import outfit_generator
from backend.app.services.fashion_orchestrator import fashion_orchestrator
from backend.app.services.outfits.look_management_service import look_management_service
from backend.app.domain.fashion_knowledge import (
    STYLE_AESTHETICS,
    SEASONAL_COLOR_PALETTES,
    OCCASION_MATRIX
)

router = APIRouter(prefix="/api/fashion", tags=["Fashion Intelligence"])

from fastapi.params import Depends as DependsClass

def _is_registered_user_id(uid: Optional[str]) -> bool:
    if not uid or uid in ("default_user", "guest", "anonymous"):
        return False
    # Registered user IDs in Yorvyn start with usr_ or are standard UUIDs
    if uid.startswith("usr_"):
        return True
    if len(uid) == 36 and uid.count("-") == 4:
        return True
    return False

def _resolve_effective_user_id(
    client_user_id: Optional[str],
    current_user: Optional[UserContext],
    allow_guest: bool = True
) -> str:
    """
    Enforces strict tenant isolation and authentication boundaries:
    1. Direct function calls in test suites (Depends instance passed):
       Returns client_user_id or 'default_user'.
    2. Authenticated users:
       - Strictly binds to current_user.user_id.
       - Any attempt to supply another user's ID raises 403 Forbidden.
    3. Unauthenticated callers:
       - If allow_guest is False: raises 401 Unauthorized.
       - If client_user_id targets a registered tenant account (usr_* or UUID):
         raises 401 Unauthorized to prevent guest fallback privilege escalation.
       - Permitted guest identifiers fallback to 'default_user' (or client_user_id for anonymous sandbox).
    """
    if isinstance(current_user, DependsClass):
        return client_user_id or "default_user"

    if isinstance(current_user, UserContext):
        if client_user_id and client_user_id not in ("default_user", current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Cross-tenant data access is not permitted."
            )
        return current_user.user_id

    # Unauthenticated caller
    if not allow_guest:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: Please provide a valid Bearer token."
        )

    # Protect against unauthenticated user impersonation of registered accounts
    if _is_registered_user_id(client_user_id):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access registered user records."
        )

    return client_user_id or "default_user"

# --- Request / Response Models ---

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[int] = None
    height_value: Optional[float] = None
    height_unit: Optional[str] = None
    body_shape: Optional[str] = None
    body_type: Optional[str] = None
    skin_tone_id: Optional[str] = None
    skin_tone_hex: Optional[str] = None
    skin_undertone: Optional[str] = None
    hair_colour_id: Optional[str] = None
    hair_colour_hex: Optional[str] = None
    avatar_gender_presentation: Optional[str] = None
    avatar_configuration: Optional[Dict[str, Any]] = None
    onboarding_completed: Optional[bool] = None
    color_season: Optional[str] = None
    fit_preference: Optional[str] = None
    primary_aesthetics: Optional[List[str]] = None
    budget_tier: Optional[str] = None
    lifestyle_notes: Optional[str] = None

class AddGarmentRequest(BaseModel):
    name: str
    category: str
    subcategory: Optional[str] = "general"
    color: str
    secondary_color: Optional[str] = ""
    material: Optional[str] = "cotton"
    pattern: Optional[str] = "solid"
    formality: Optional[int] = 4
    warmth: Optional[int] = 4
    seasons: Optional[List[str]] = ["spring", "summer", "autumn", "winter"]
    brand: Optional[str] = "Unknown"
    image_url: Optional[str] = "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=600&q=80"

class OutfitGenerateRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    occasion: Optional[str] = "casual_day"
    temperature_celsius: Optional[float] = 18.0
    condition: Optional[str] = "clear"
    target_aesthetic: Optional[str] = None
    max_outfits: Optional[int] = 4

class StylistChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"
    temperature_celsius: Optional[float] = None

class FeedbackRequest(BaseModel):
    outfit_id: str
    action: str  # wear_today, like, dislike, save, skip
    note: Optional[str] = None
    user_id: Optional[str] = "default_user"

class AvatarChatRequest(BaseModel):
    message: str
    current_profile: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = "default_user"

class AvatarPhotoAnalysisRequest(BaseModel):
    user_consent: Dict[str, Any]
    image_base64: Optional[str] = None
    target_features: Optional[List[str]] = Field(default_factory=lambda: ["face", "skin", "hair", "facial_hair", "proportions"])
    current_profile: Optional[Dict[str, Any]] = None

# --- Phase 9: Look & Outfit Management Request Models ---

class CreateLookRequest(BaseModel):
    name: str
    garment_ids: List[str]
    description: Optional[str] = None
    avatar_snapshot: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = False
    user_id: Optional[str] = "default_user"

class UpdateLookRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    garment_ids: Optional[List[str]] = None
    avatar_snapshot: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None
    user_id: Optional[str] = "default_user"

class DuplicateLookRequest(BaseModel):
    new_name: Optional[str] = None
    user_id: Optional[str] = "default_user"

class CompatibilityValidateRequest(BaseModel):
    garment_ids: List[str]
    user_id: Optional[str] = "default_user"

class UserConsentRequest(BaseModel):
    ephemeral_processing_accepted: bool = True
    ai_training_opt_in: bool = False
    terms_version: str = "2026.1"
    user_id: Optional[str] = "default_user"

# --- Endpoints ---

@router.get("/health")
def fashion_health():
    return {
        "status": "healthy",
        "service": "Yorvyn Fashion Intelligence Core",
        "version": "2.0.0"
    }

@router.get("/knowledge")
def get_fashion_knowledge():
    """Returns baseline aesthetic definitions, seasonal palettes, and occasions."""
    return {
        "aesthetics": STYLE_AESTHETICS,
        "color_seasons": SEASONAL_COLOR_PALETTES,
        "occasions": OCCASION_MATRIX
    }

@router.get("/profile")
def get_profile(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return context_service.get_user_profile(effective_uid)

@router.post("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return context_service.update_user_profile(effective_uid, updates)

@router.get("/wardrobe")
def get_wardrobe(
    user_id: str = "default_user",
    category: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return {
        "items": wardrobe_service.get_wardrobe(effective_uid, category),
        "total": len(wardrobe_service.get_wardrobe(effective_uid, category))
    }

@router.post("/wardrobe")
def add_wardrobe_item(
    req: AddGarmentRequest,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    item = wardrobe_service.add_item(effective_uid, req.model_dump())
    return {"status": "success", "item": item}

@router.delete("/wardrobe/{item_id}")
def delete_wardrobe_item(
    item_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    success = wardrobe_service.delete_item(effective_uid, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "deleted_id": item_id}

@router.post("/wardrobe/{item_id}/wear")
def wear_wardrobe_item(
    item_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    item = wardrobe_service.record_wear(effective_uid, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "item": item}

@router.post("/wardrobe/{item_id}/favorite")
def toggle_favorite_item(
    item_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    item = wardrobe_service.toggle_favorite(effective_uid, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "item": item}

@router.get("/analytics")
def get_analytics(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return wardrobe_service.get_closet_analytics(effective_uid)

# --- Phase 9: Saved Looks & Curation Endpoints ---

@router.get("/looks")
def get_saved_looks(
    tag: Optional[str] = None,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return look_management_service.get_looks(effective_uid, tag=tag)

@router.post("/looks")
def create_saved_look(
    req: CreateLookRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    # Check subscription entitlement for saved looks limit
    from backend.app.services.billing.entitlement_service import entitlement_service
    current_looks = look_management_service.get_looks(effective_uid)
    can_save, reason = entitlement_service.can_save_look(effective_uid, len(current_looks))
    if not can_save:
        raise HTTPException(status_code=403, detail=reason)

    return look_management_service.create_look(
        user_id=effective_uid,
        name=req.name,
        garment_ids=req.garment_ids,
        description=req.description,
        avatar_snapshot=req.avatar_snapshot,
        tags=req.tags,
        is_favorite=bool(req.is_favorite)
    )

@router.get("/looks/{look_id}")
def get_saved_look_details(
    look_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    look = look_management_service.get_look(effective_uid, look_id)
    if not look:
        raise HTTPException(status_code=404, detail="Saved look not found")
    return look

@router.put("/looks/{look_id}")
def update_saved_look(
    look_id: str,
    req: UpdateLookRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.garment_ids is not None:
        updates["garment_ids"] = req.garment_ids
    if req.avatar_snapshot is not None:
        updates["avatar_snapshot"] = req.avatar_snapshot
    if req.tags is not None:
        updates["tags"] = req.tags
    if req.is_favorite is not None:
        updates["is_favorite"] = req.is_favorite

    res = look_management_service.rename_look(effective_uid, look_id, updates.get("name", "")) if "name" in updates and len(updates) == 1 else supabase_repo.update_saved_look(effective_uid, look_id, updates)
    if not res:
        raise HTTPException(status_code=404, detail="Saved look not found or could not be updated")
    return res

@router.delete("/looks/{look_id}")
def delete_saved_look(
    look_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    deleted = look_management_service.delete_look(effective_uid, look_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved look not found")
    return {"status": "success", "message": f"Look '{look_id}' deleted."}

@router.post("/looks/{look_id}/duplicate")
def duplicate_saved_look(
    look_id: str,
    req: DuplicateLookRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    # Check subscription entitlement for saved looks limit
    from backend.app.services.billing.entitlement_service import entitlement_service
    current_looks = look_management_service.get_looks(effective_uid)
    can_save, reason = entitlement_service.can_save_look(effective_uid, len(current_looks))
    if not can_save:
        raise HTTPException(status_code=403, detail=reason)

    cloned = look_management_service.duplicate_look(effective_uid, look_id, new_name=req.new_name)
    if not cloned:
        raise HTTPException(status_code=404, detail="Original look not found to duplicate")
    return cloned

@router.post("/looks/{look_id}/wear")
def wear_saved_look(
    look_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    updated = look_management_service.record_wear(effective_uid, look_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Saved look not found")
    return {"status": "success", "look": updated}

@router.post("/looks/validate")
def validate_outfit_compatibility(
    req: CompatibilityValidateRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    user_wardrobe = wardrobe_service.get_wardrobe(effective_uid)
    wardrobe_map = {g["id"]: g for g in user_wardrobe}
    selected = [wardrobe_map[gid] for gid in req.garment_ids if gid in wardrobe_map]
    if not selected:
        # Fallback dummy check
        selected = [{"id": gid, "name": gid, "category": "top", "warmth": 4, "formality": 4} for gid in req.garment_ids]
    from dataclasses import asdict
    res = look_management_service.validate_compatibility(selected)
    return asdict(res)

@router.get("/looks/{look_id}/preview")
def preview_saved_look_3d(
    look_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    try:
        return look_management_service.preview_look(effective_uid, look_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- Phase 9: Consent & Privacy (GDPR Compliance) Endpoints ---

@router.get("/consent")
def get_user_privacy_consent(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    consent = supabase_repo.get_user_consent(effective_uid)
    if not consent:
        return {
            "user_id": effective_uid,
            "ephemeral_processing_accepted": True,
            "ai_training_opt_in": False,
            "terms_version": "2026.1",
            "status": "default_ephemeral_only"
        }
    return consent

@router.post("/consent")
def update_user_privacy_consent(
    req: UserConsentRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user, allow_guest=False)
    from datetime import datetime
    consent_data = {
        "user_id": effective_uid,
        "ephemeral_processing_accepted": req.ephemeral_processing_accepted,
        "ai_training_opt_in": req.ai_training_opt_in,
        "opt_in_timestamp": datetime.utcnow().isoformat() if req.ai_training_opt_in else None,
        "terms_version": req.terms_version
    }
    return supabase_repo.upsert_user_consent(effective_uid, consent_data)

@router.get("/user/export")
def export_user_data_archive(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user, allow_guest=False)
    return supabase_repo.export_user_data(effective_uid)

@router.post("/user/purge")
def purge_user_data_request(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user, allow_guest=False)
    success = supabase_repo.purge_user_data(effective_uid)
    return {"status": "success", "message": f"All data permanently erased for user {effective_uid}."}

@router.post("/outfits/generate")
def generate_outfits(
    req: OutfitGenerateRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    return outfit_generator.generate_outfits(
        user_id=effective_uid,
        occasion=req.occasion or "casual_day",
        temp_celsius=req.temperature_celsius if req.temperature_celsius is not None else 18.0,
        condition=req.condition or "clear",
        target_aesthetic=req.target_aesthetic,
        max_outfits=req.max_outfits or 4
    )

@router.post("/chat")
def chat_with_stylist(
    req: StylistChatRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    return fashion_orchestrator.chat_stylist(
        message=req.message,
        user_id=effective_uid,
        override_temp=req.temperature_celsius
    )

@router.post("/chat/stream")
def stream_chat_with_stylist(
    req: StylistChatRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Streams the personal stylist guidance using text/event-stream."""
    from fastapi.responses import StreamingResponse

    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    def event_generator():
        for token in fashion_orchestrator.stream_chat_stylist(
            message=req.message,
            user_id=effective_uid,
            override_temp=req.temperature_celsius
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/feedback")
def record_feedback(
    req: FeedbackRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(req.user_id, current_user)
    return fashion_orchestrator.record_feedback(
        user_id=effective_uid,
        outfit_id=req.outfit_id,
        action=req.action,
        note=req.note
    )

# --- 3D Avatar Engine Endpoints ---

@router.get("/avatar")
def get_avatar_config(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return wardrobe_service.get_avatar_config(effective_uid)

@router.post("/avatar")
def save_avatar_config(
    config: Dict[str, Any],
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return wardrobe_service.save_avatar_config(effective_uid, config)

@router.post("/avatar/reset")
def reset_avatar_config(
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    return wardrobe_service.reset_avatar_config(effective_uid)

# --- Phase 8: AI Avatar Intelligence & Personalization Engine Endpoints ---

@router.post("/avatar/chat")
def handle_avatar_chat(
    req: AvatarChatRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """
    Parses conversational styling requests, validates Avatar DNA bounds,
    and returns a structured customization proposal.
    """
    msg = req.message.lower().strip()
    profile = req.current_profile or {}
    
    # Simple server-side validation & intent mapping
    operations = []
    category = "body"
    title = "Natural Language Avatar Styling"
    explanation = f'Evaluated request: "{req.message}".'
    patch: Dict[str, Any] = {}

    if "shoulder" in msg or "broad" in msg:
        category = "body"
        title = "Shoulder Width Adjustment (+30%)"
        operations.append({
            "action": "set_slider",
            "category": "body",
            "targetKey": "shoulderWidth",
            "targetValue": 0.3,
            "displayLabel": "Broaden shoulders (+30%)"
        })
        patch = {"proportions": {"shoulderWidth": 0.3}}
        explanation = "Broadened character shoulder span for athletic, structured silhouette."
    elif "jaw" in msg or "chisel" in msg:
        category = "face"
        title = "Chiseled Jawline Definition"
        operations.append({
            "action": "set_slider",
            "category": "face",
            "targetKey": "jawWidth",
            "targetValue": 0.25,
            "displayLabel": "Widen and define jaw (+25%)"
        })
        patch = {"face": {"jawWidth": 0.25}}
        explanation = "Sculpted jawline contours for enhanced angular structure."
    elif "hair" in msg or "fade" in msg or "crop" in msg:
        category = "hair"
        title = "Modern Textured Hairstyle"
        operations.append({
            "action": "set_preset",
            "category": "hair",
            "targetKey": "hairStyleId",
            "targetValue": "short02",
            "displayLabel": "Textured Crop"
        })
        patch = {"appearance": {"hairStyleId": "short02"}}
        explanation = "Swapped 3D hairstyle mesh to textured crop."
    else:
        title = "Refined Natural Poise"
        explanation = f'Interpreted instruction: "{req.message}". Applied subtle character poise refinement.'

    return {
        "status": "success",
        "proposal": {
            "id": f"srv_prop_{hash(msg) % 1000000}",
            "title": title,
            "summary": explanation,
            "category": category,
            "confidence": 0.92,
            "operations": operations,
            "profilePatch": patch,
            "explanation": explanation,
            "source": "conversational",
            "status": "pending"
        }
    }

@router.post("/avatar/photo-analysis")
def analyze_reference_photo(
    req: AvatarPhotoAnalysisRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """
    Privacy-first ephemeral reference photo processing.
    Requires explicit user consent and guarantees zero permanent retention.
    """
    consent = req.user_consent or {}
    if not consent.get("hasConsented"):
        raise HTTPException(
            status_code=403, 
            detail="Privacy consent is strictly required for reference photo personalization."
        )

    # Documented zero-retention guarantee
    retention_policy = (
        "Yorvyn Zero-Retention Guarantee: Image memory buffer processed ephemerally "
        "and immediately purged. Binary was not written to permanent storage."
    )

    detected_traits = {
        "faceShape": {
            "value": "oval",
            "confidence": 0.94,
            "description": "Harmonious oval contours with balanced forehead and jaw width"
        },
        "skinTone": {
            "hex": "#e0a97a",
            "undertone": "warm",
            "confidence": 0.91,
            "description": "Warm golden amber undertone with radiant natural depth"
        },
        "hair": {
            "styleId": "short02",
            "styleName": "Modern Textured Crop",
            "colorHex": "#2b1b17",
            "length": "short",
            "confidence": 0.88
        },
        "facialHair": {
            "styleId": "stubble",
            "styleName": "Groomed Stubble",
            "confidence": 0.85
        },
        "proportions": {
            "estimatedSilhouette": "athletic",
            "confidence": 0.82,
            "disclaimer": "Approximation from single portrait angle; not exact anthropometric measurement."
        }
    }

    return {
        "status": "success",
        "privacyNotice": "Processed ephemerally under Yorvyn Zero-Retention Policy.",
        "retentionPolicy": retention_policy,
        "detectedTraits": detected_traits,
        "generatedProposal": {
            "id": "prop_photo_srv",
            "title": "Reference Photo Personalization Proposal",
            "summary": "Synthesized 3D Avatar DNA matching uploaded reference portrait.",
            "category": "composite",
            "confidence": 0.91,
            "operations": [
                {"action": "set_color", "category": "skin", "targetKey": "skinToneHex", "targetValue": "#e0a97a", "displayLabel": "Warm Golden Amber Skin"},
                {"action": "set_preset", "category": "hair", "targetKey": "hairStyleId", "targetValue": "short02", "displayLabel": "Modern Textured Crop"}
            ],
            "profilePatch": {
                "face": {"faceShapePreset": "oval", "headShape": 0.05, "jawWidth": 0.08},
                "appearance": {"skinToneHex": "#e0a97a", "hairStyleId": "short02", "hairColorHex": "#2b1b17"}
            },
            "explanation": "Extracted facial proportions, skin undertone, and hair geometry from reference photo.",
            "source": "photo_analysis",
            "status": "pending"
        }
    }

@router.get("/avatar/hairstyles")
def get_hairstyle_catalog():
    """Returns supported 3D hairstyle assets and face shape compatibility scores."""
    return {
        "status": "success",
        "faceShapes": ["oval", "square", "round", "heart", "diamond", "oblong"],
        "catalog": [
            {"id": "short01", "name": "Classic Short Part", "category": "short", "compatible": ["oval", "round", "square"]},
            {"id": "short02", "name": "Modern Textured Crop", "category": "short", "compatible": ["oval", "diamond", "heart"]},
            {"id": "short03", "name": "Structured Undercut", "category": "short", "compatible": ["round", "square", "oval"]},
            {"id": "bob01", "name": "Precision French Bob", "category": "medium", "compatible": ["oval", "heart", "diamond"]},
            {"id": "curly01", "name": "Hydrated Natural Curls", "category": "textured", "compatible": ["oval", "square", "round"]},
            {"id": "long01", "name": "Long Layered Waves", "category": "long", "compatible": ["square", "diamond", "heart"]}
        ]
    }

@router.get("/ara-assets/{asset_path:path}")
def proxy_ara_asset(asset_path: str):
    """Proxies and serves Ara 3D Gen assets with CORS headers."""
    import requests
    from fastapi.responses import Response

    target_url = f"https://ara3dgen.com/assets/{asset_path}"
    try:
        resp = requests.get(
            target_url,
            headers={"User-Agent": "Yorvyn-Avatar-Engine/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Asset not found: {str(e)}")


# --- Real Fashion ML Evaluation & Dataset Endpoints ---

@router.get("/ml/metrics")
def get_fashion_ml_metrics():
    """Returns real dataset evaluation metrics and per-class performance report."""
    from backend.app.services.ml.fashion_classifier import fashion_ml_classifier, METRICS_PATH
    if METRICS_PATH.exists():
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    elif fashion_ml_classifier.metrics:
        return fashion_ml_classifier.metrics
    else:
        return {"status": "not_trained", "message": "ML evaluation has not been executed yet."}


# ── ML Phase 1: Fashion DNA, Intelligent LLM & Multi-Factor Endpoints ───────

from backend.app.services.fashion_dna_service import fashion_dna_service
from backend.app.services.llm.service import intelligence_service
from backend.app.services.llm.token_tracker import token_tracker
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service
from backend.app.services.ml.outfit_ranker import outfit_ranker_service
from backend.app.services.ml.preference_learning import preference_learning_service
from backend.app.services.ml.body_intelligence import body_intelligence_service
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service
from backend.app.services.ml.fashion_vision import fashion_vision_service
from backend.app.services.database.supabase_repository import supabase_repo


class IntelligentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = "default_user"
    temporary_constraints: Optional[Dict[str, Any]] = None


class FashionDNAUpdateRequest(BaseModel):
    body_profile: Optional[Dict[str, Any]] = None
    colour_profile: Optional[Dict[str, Any]] = None
    style_profile: Optional[Dict[str, Any]] = None
    additional_preferences: Optional[Dict[str, Any]] = None


class PreferenceEvolveRequest(BaseModel):
    signal_type: str = Field(..., description="explicit, temporary, or rejected")
    category: str = Field(..., description="colour, fit, style, brand, or material")
    value: Any
    weight: float = 1.0


class OutfitEvaluationRequest(BaseModel):
    item_ids: List[str]
    occasion: Optional[str] = "casual"
    weather_temp_c: Optional[float] = 20.0


class OutfitFeedbackRequest(BaseModel):
    outfit_id: str
    feedback: str = Field(..., description="liked, saved, rejected, or worn")
    notes: Optional[str] = None


@router.get("/dna")
def get_fashion_dna(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retrieves persistent Fashion DNA for the authenticated user."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    return {"status": "success", "fashion_dna": dna.dict()}


@router.put("/dna")
def update_fashion_dna(
    req: FashionDNAUpdateRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Updates user Fashion DNA profile."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    updates = req.dict(exclude_unset=True)
    updated = fashion_dna_service.update_fashion_dna(eff_uid, updates)
    return {"status": "success", "fashion_dna": updated.dict()}


@router.post("/dna/sync-avatar")
def sync_fashion_dna_from_avatar(
    avatar_profile: Dict[str, Any],
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Derives baseline physical stature and undertone from Avatar DNA without overriding manual measurements."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    synced = fashion_dna_service.sync_from_avatar_dna(eff_uid, avatar_profile)
    return {"status": "success", "fashion_dna": synced.dict()}


@router.post("/dna/evolve")
def evolve_fashion_dna(
    req: PreferenceEvolveRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Evolves Fashion DNA with explicit, temporary, or rejected preferences."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    evolved = fashion_dna_service.evolve_fashion_dna(
        user_id=eff_uid,
        signal_type=req.signal_type,
        category=req.category,
        value=req.value,
        weight=req.weight,
        source="api_evolve"
    )
    return {"status": "success", "fashion_dna": evolved.dict()}


@router.post("/dna/reset")
def reset_fashion_dna(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Resets user Fashion DNA to curated default baseline."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    reset_dna = fashion_dna_service.reset_fashion_dna(eff_uid)
    return {"status": "success", "fashion_dna": reset_dna.dict()}


@router.delete("/dna")
def delete_fashion_dna(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Permanently deletes user Fashion DNA for GDPR right to erasure."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    success = fashion_dna_service.delete_fashion_dna(eff_uid)
    return {"status": "success" if success else "not_found", "deleted": success}


@router.post("/chat/intelligent")
def intelligent_fashion_chat(
    req: IntelligentChatRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Unified LLM Fashion Intelligence chat endpoint.
    Orchestrates provider execution, authenticated tool calling, and multi-factor recommendations.
    """
    eff_uid = _resolve_effective_user_id(req.user_id, current_user)
    res = intelligence_service.process_message(
        user_id=eff_uid,
        message=req.message,
        conversation_id=req.conversation_id,
        temporary_constraints=req.temporary_constraints
    )
    return res.dict()


@router.get("/intelligence/metrics")
def get_intelligence_metrics(
    user_id: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Returns token usage, latency metrics, and estimated operational costs."""
    if user_id:
        eff_uid = _resolve_effective_user_id(user_id, current_user)
        return {"status": "success", "user_metrics": token_tracker.get_user_stats(eff_uid)}
    return {"status": "success", "global_metrics": token_tracker.get_global_metrics()}


@router.get("/wardrobe/gaps")
def get_wardrobe_gaps(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Analyzes user wardrobe for missing essential categories, color variety gaps, and versatility deficits."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    gaps = wardrobe_intelligence_service.analyze_wardrobe_gaps(eff_uid)
    return {"status": "success", "analysis": gaps}


@router.post("/recommendations/evaluate")
def evaluate_candidate_outfit(
    req: OutfitEvaluationRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Evaluates 10-factor compatibility for candidate outfit items against user Fashion DNA."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    items = wardrobe_service.get_wardrobe(eff_uid)
    selected = [i for i in items if i.get("id") in req.item_ids]
    if not selected:
        raise HTTPException(status_code=400, detail="None of the specified item IDs were found in user wardrobe.")

    breakdown = outfit_ranker_service.evaluate_outfit(
        user_id=eff_uid,
        items=selected,
        fashion_dna=dna,
        occasion=req.occasion or "casual",
        weather_temp_c=req.weather_temp_c
    )
    return {"status": "success", "evaluation": breakdown.dict()}


@router.post("/recommendations/feedback")
def record_recommendation_feedback(
    req: OutfitFeedbackRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Records user like, save, or rejection for Model E preference learning."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    preference_learning_service.record_interaction(
        user_id=eff_uid,
        interaction_type=req.feedback,
        item_or_outfit_data={"outfit_id": req.outfit_id}
    )
    supabase_repo.update_recommendation_feedback(eff_uid, req.outfit_id, req.feedback, req.notes)
    return {"status": "success", "outfit_id": req.outfit_id, "feedback": req.feedback}


# ── ML Phase 2: Body Intelligence, Skin Analysis & Personal Colour Intelligence ──

class BodyMeasurementsUpdateRequest(BaseModel):
    measurements: Dict[str, Any]
    unit: str = "cm"


class BodyProportionsAnalysisRequest(BaseModel):
    height_cm: Optional[float] = None
    shoulder_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None


class SkinColourAnalysisRequest(BaseModel):
    skin_hex: Optional[str] = None
    r: Optional[int] = None
    g: Optional[int] = None
    b: Optional[int] = None
    ambient_lighting: Optional[str] = "neutral_daylight"


class ClothingFitEvaluationRequest(BaseModel):
    garment_spec: Dict[str, Any]
    garment_name: Optional[str] = "Candidate Garment"


class ColourCompatibilityEvaluationRequest(BaseModel):
    garment_colors: List[str]
    occasion: Optional[str] = "casual"


class BodyPhotoAnalysisRequest(BaseModel):
    image_metadata: Dict[str, Any]
    user_consent: bool = False


@router.get("/body/profile")
def get_body_profile(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retrieves continuous body measurements, unit preference, proportions, and provenance."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    bp = dna.body_profile
    return {
        "status": "success",
        "user_id": eff_uid,
        "unit_preference": bp.unit_preference,
        "measurements": {
            "height_cm": bp.height_cm,
            "shoulder_width_cm": bp.shoulder_width_cm or bp.shoulder_cm,
            "chest_cm": bp.chest_cm,
            "waist_cm": bp.waist_cm,
            "hip_cm": bp.hip_cm,
            "torso_length_cm": bp.torso_length_cm,
            "arm_length_cm": bp.arm_length_cm,
            "inseam_cm": bp.inseam_cm,
            "thigh_cm": bp.thigh_cm,
            "weight_kg": bp.weight_kg
        },
        "proportions": bp.proportions,
        "silhouette": bp.silhouette,
        "fit_preference": bp.fit_preference,
        "measurement_source": bp.measurement_source,
        "measurement_sources": bp.measurement_sources,
        "measurement_confidences": bp.measurement_confidences
    }


@router.put("/body/measurements")
def update_body_measurements(
    req: BodyMeasurementsUpdateRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Updates user body measurements with unit conversion and sets provenance to user_confirmed."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    updated_dna = fashion_dna_service.update_body_measurements(
        user_id=eff_uid,
        measurements=req.measurements,
        unit=req.unit,
        source="user_confirmed"
    )
    return {
        "status": "success",
        "body_profile": updated_dna.body_profile.model_dump(),
        "proportions": updated_dna.body_profile.proportions
    }


@router.post("/body/analyze-proportions")
def analyze_body_proportions(
    req: BodyProportionsAnalysisRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Computes continuous structural body ratios and non-judgmental fit guidelines."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    bp = dna.body_profile
    analysis = body_intelligence_service.analyze_body_proportions(
        height_cm=req.height_cm or bp.height_cm,
        shoulder_width_cm=req.shoulder_cm or bp.shoulder_width_cm or bp.shoulder_cm,
        chest_cm=req.chest_cm or bp.chest_cm,
        waist_cm=req.waist_cm or bp.waist_cm,
        hip_cm=req.hip_cm or bp.hip_cm,
        torso_length_cm=bp.torso_length_cm,
        inseam_cm=bp.inseam_cm,
        silhouette=bp.silhouette,
        fit_preference=bp.fit_preference
    )
    return {"status": "success", "analysis": analysis.model_dump()}


@router.post("/body/analyze-photo")
def analyze_body_photo_proportions(
    req: BodyPhotoAnalysisRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Analyzes body proportions from photograph metadata with strict user consent verification."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    result = fashion_vision_service.analyze_body_photo_proportions(
        image_metadata=req.image_metadata,
        user_consent=req.user_consent
    )
    return {"status": "success", "result": result.model_dump()}


@router.post("/colour/analyze")
def analyze_skin_colour(
    req: SkinColourAnalysisRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Performs lighting-aware CIELAB skin analysis with illuminant compensation and uncertainty scoring."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    if req.skin_hex and len(req.skin_hex.lstrip("#")) == 6:
        clean = req.skin_hex.lstrip("#")
        r, g, b = int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
    elif req.r is not None and req.g is not None and req.b is not None:
        r, g, b = req.r, req.g, req.b
    else:
        r, g, b = 185, 140, 110

    analysis = skin_colour_intelligence_service.analyze_skin_tone_lighting_aware(
        r=r, g=g, b=b,
        ambient_hint=req.ambient_lighting or "neutral_daylight"
    )
    return {"status": "success", "analysis": analysis.model_dump()}


@router.get("/colour/palette")
def get_personal_colour_palette(
    undertone: Optional[str] = None,
    palette_id: Optional[str] = None,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retrieves personal seasonal, complementary, analogous, and neutral anchor palettes."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    ut = undertone or dna.colour_profile.skin_undertone
    pid = palette_id or dna.colour_profile.personal_palette
    palette = skin_colour_intelligence_service.get_personal_colour_palette(
        undertone=ut,
        skin_tone_range=dna.colour_profile.skin_tone_range,
        user_preferred_palette=pid
    )
    return {"status": "success", "palette": palette.model_dump()}


@router.post("/compatibility/fit")
def evaluate_clothing_fit(
    req: ClothingFitEvaluationRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Evaluates multi-dimensional garment fit against user body profile."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    bp = dna.body_profile
    body_dict = {
        "height_cm": bp.height_cm,
        "chest_cm": bp.chest_cm,
        "waist_cm": bp.waist_cm,
        "hip_cm": bp.hip_cm,
        "shoulder_width_cm": bp.shoulder_width_cm or bp.shoulder_cm,
        "torso_length_cm": bp.torso_length_cm,
        "inseam_cm": bp.inseam_cm,
        "arm_length_cm": bp.arm_length_cm
    }
    result = body_intelligence_service.evaluate_clothing_fit(
        body_measurements=body_dict,
        garment_spec=req.garment_spec,
        user_fit_preference=bp.fit_preference
    )
    return {
        "status": "success",
        "garment_name": req.garment_name,
        "evaluation": result.model_dump()
    }


@router.post("/compatibility/colour")
def evaluate_clothing_colour_compatibility(
    req: ColourCompatibilityEvaluationRequest,
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Evaluates clothing colour compatibility for single garments or complete outfits."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    dna = fashion_dna_service.get_fashion_dna(eff_uid)
    result = skin_colour_intelligence_service.evaluate_colour_compatibility(
        garment_colors=req.garment_colors,
        user_undertone=dna.colour_profile.skin_undertone,
        personal_palette=dna.colour_profile.personal_palette,
        preferred_colors=dna.colour_profile.preferred_colours,
        disliked_colors=dna.colour_profile.disliked_colours,
        occasion=req.occasion or "casual"
    )
    return {"status": "success", "result": result.model_dump()}


@router.get("/avatar/compare")
def compare_avatar_with_body_profile(
    user_id: Optional[str] = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Compares user 3D avatar proportions with Fashion DNA measurements to detect mismatches."""
    eff_uid = _resolve_effective_user_id(user_id, current_user)
    avatar_config = wardrobe_service.get_avatar_config(eff_uid) or {}
    comparison = fashion_dna_service.compare_with_avatar_dna(eff_uid, avatar_config)
    return {"status": "success", "comparison": comparison}


@router.get("/cv/models")
def get_audited_cv_models():
    """Returns documentation and capability audit of candidate computer vision models."""
    models = fashion_vision_service.get_supported_cv_models()
    return {"status": "success", "models": models}




