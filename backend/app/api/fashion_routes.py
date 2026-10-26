"""
Yorvyn Fashion Intelligence API Endpoints
Exposes REST routes for Profile, Digital Wardrobe, Context,
Outfit Generation, AI Stylist Chat, and Feedback Loops.
"""

import json
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from backend.app.core.security import get_current_user_optional, UserContext
from backend.app.services.wardrobe_service import wardrobe_service
from backend.app.services.context_service import context_service
from backend.app.services.outfit_generator import outfit_generator
from backend.app.services.fashion_orchestrator import fashion_orchestrator
from backend.app.domain.fashion_knowledge import (
    STYLE_AESTHETICS,
    SEASONAL_COLOR_PALETTES,
    OCCASION_MATRIX
)

router = APIRouter(prefix="/api/fashion", tags=["Fashion Intelligence"])

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
    effective_uid = current_user.user_id if current_user else user_id
    return context_service.get_user_profile(effective_uid)

@router.post("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    effective_uid = current_user.user_id if current_user else user_id
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return context_service.update_user_profile(effective_uid, updates)

@router.get("/wardrobe")
def get_wardrobe(user_id: str = "default_user", category: Optional[str] = None):
    return {
        "items": wardrobe_service.get_wardrobe(user_id, category),
        "total": len(wardrobe_service.get_wardrobe(user_id, category))
    }

@router.post("/wardrobe")
def add_wardrobe_item(req: AddGarmentRequest, user_id: str = "default_user"):
    item = wardrobe_service.add_item(user_id, req.model_dump())
    return {"status": "success", "item": item}

@router.delete("/wardrobe/{item_id}")
def delete_wardrobe_item(item_id: str, user_id: str = "default_user"):
    success = wardrobe_service.delete_item(user_id, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "deleted_id": item_id}

@router.post("/wardrobe/{item_id}/wear")
def wear_wardrobe_item(item_id: str, user_id: str = "default_user"):
    item = wardrobe_service.record_wear(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "item": item}

@router.post("/wardrobe/{item_id}/favorite")
def toggle_favorite_item(item_id: str, user_id: str = "default_user"):
    item = wardrobe_service.toggle_favorite(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Garment not found")
    return {"status": "success", "item": item}

@router.get("/analytics")
def get_analytics(user_id: str = "default_user"):
    return wardrobe_service.get_closet_analytics(user_id)

@router.post("/outfits/generate")
def generate_outfits(req: OutfitGenerateRequest):
    return outfit_generator.generate_outfits(
        user_id=req.user_id or "default_user",
        occasion=req.occasion or "casual_day",
        temp_celsius=req.temperature_celsius if req.temperature_celsius is not None else 18.0,
        condition=req.condition or "clear",
        target_aesthetic=req.target_aesthetic,
        max_outfits=req.max_outfits or 4
    )

@router.post("/chat")
def chat_with_stylist(req: StylistChatRequest):
    return fashion_orchestrator.chat_stylist(
        message=req.message,
        user_id=req.user_id or "default_user",
        override_temp=req.temperature_celsius
    )

@router.post("/chat/stream")
def stream_chat_with_stylist(req: StylistChatRequest):
    """Streams the personal stylist guidance using text/event-stream."""
    from fastapi.responses import StreamingResponse

    def event_generator():
        for token in fashion_orchestrator.stream_chat_stylist(
            message=req.message,
            user_id=req.user_id or "default_user",
            override_temp=req.temperature_celsius
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/feedback")
def record_feedback(req: FeedbackRequest):
    return fashion_orchestrator.record_feedback(
        user_id=req.user_id or "default_user",
        outfit_id=req.outfit_id,
        action=req.action,
        note=req.note
    )

# --- 3D Avatar Engine Endpoints ---

@router.get("/avatar")
def get_avatar_config(user_id: str = "default_user"):
    return wardrobe_service.get_avatar_config(user_id)

@router.post("/avatar")
def save_avatar_config(config: Dict[str, Any], user_id: str = "default_user"):
    return wardrobe_service.save_avatar_config(user_id, config)

@router.post("/avatar/reset")
def reset_avatar_config(user_id: str = "default_user"):
    return wardrobe_service.reset_avatar_config(user_id)

@router.get("/ara-assets/{asset_path:path}")
def proxy_ara_asset(asset_path: str):
    """Proxies and serves Ara 3D Gen assets with CORS headers."""
    import urllib.request
    from fastapi.responses import Response

    target_url = f"https://ara3dgen.com/assets/{asset_path}"
    try:
        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "Yorvyn-Avatar-Engine/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
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


