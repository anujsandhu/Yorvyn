"""
Yorvyn Fashion Intelligence API Endpoints
Exposes REST routes for Profile, Digital Wardrobe, Context,
Outfit Generation, AI Stylist Chat, and Feedback Loops.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from .wardrobe_service import wardrobe_service
from .context_service import context_service
from .outfit_generator import outfit_generator
from .fashion_orchestrator import fashion_orchestrator
from .fashion_knowledge import (
    STYLE_AESTHETICS,
    SEASONAL_COLOR_PALETTES,
    OCCASION_MATRIX
)

router = APIRouter(prefix="/api/fashion", tags=["Fashion Intelligence"])

# --- Request / Response Models ---

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    body_shape: Optional[str] = None
    height_cm: Optional[int] = None
    skin_undertone: Optional[str] = None
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
def get_profile(user_id: str = "default_user"):
    return context_service.get_user_profile(user_id)

@router.post("/profile")
def update_profile(req: ProfileUpdateRequest, user_id: str = "default_user"):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return context_service.update_user_profile(user_id, updates)

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

@router.post("/feedback")
def record_feedback(req: FeedbackRequest):
    return fashion_orchestrator.record_feedback(
        user_id=req.user_id or "default_user",
        outfit_id=req.outfit_id,
        action=req.action,
        note=req.note
    )
