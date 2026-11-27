"""
YORVYN — Look & Outfit Management Engine (Phase 9).
Manages multi-garment outfit combinations, compatibility validation,
look curation, persistence, and avatar try-on synchronization.

Strict Compatibility Rules:
1. One-piece conflicts: Full-body dresses/jumpsuits cannot be simultaneously combined
   with trousers/bottoms unless explicitly tagged as tunics or styling layering.
2. Slot exclusivity: Prevents multiple conflicting items in the same primary layer
   (e.g. two pairs of pants).
3. Thermal & Formality Harmony: Calculates aggregate thermal tier and warns on extreme
   coherence mismatches (e.g. tuxedo jacket + beach shorts).
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.wardrobe_service import wardrobe_service

logger = logging.getLogger(__name__)


@dataclass
class LookCompatibilityResult:
    is_compatible: bool
    compatibility_score: float  # [0.0, 1.0]
    conflicts: List[str]
    warnings: List[str]
    thermal_tier: str  # ultra_light, light, moderate, warm, heavy_winter
    mean_formality: int  # 1-10
    composition: Dict[str, str] = field(default_factory=dict)


OutfitCompatibilityResult = LookCompatibilityResult


class YorvynLookManagementEngine:
    """Production Outfit & Look Management Orchestrator."""

    def __init__(self):
        self._repo = supabase_repo

    def validate_compatibility(self, garments: List[Dict[str, Any]]) -> LookCompatibilityResult:
        """
        Validates garment slot compatibility, styling coherence, and thermal balance.
        """
        conflicts = []
        warnings = []
        composition: Dict[str, str] = {}

        if not garments:
            return LookCompatibilityResult(
                is_compatible=False,
                compatibility_score=0.0,
                conflicts=["Outfit contains no garments."],
                warnings=[],
                thermal_tier="moderate",
                mean_formality=5,
                composition={}
            )

        # Categorize garments
        categories = {}
        subcategories = {}
        warmths = []
        formalities = []

        for g in garments:
            cat = g.get("category", "other").lower()
            subcat = g.get("subcategory", "general").lower()
            gid = g.get("id", "unknown")

            categories.setdefault(cat, []).append(gid)
            subcategories.setdefault(subcat, []).append(gid)

            warmths.append(int(g.get("warmth", 4)))
            formalities.append(int(g.get("formality", 4)))

            if cat not in composition:
                composition[cat] = g.get("name", cat)

        # Rule 1: One-piece vs Separates conflict
        has_dress = "dress" in categories or "one_piece" in categories or any("dress" in s for s in subcategories)
        has_bottom = "bottom" in categories or "bottoms" in categories or any(s in ["trousers", "jeans", "shorts"] for s in subcategories)

        if has_dress and has_bottom:
            conflicts.append("Conflicting combination: Full-body dress cannot be simultaneously combined with trousers or bottoms.")

        # Rule 2: Multiple conflicting primary bottoms
        bottom_count = len(categories.get("bottom", [])) + len(categories.get("bottoms", []))
        if bottom_count > 1:
            conflicts.append("Multiple conflicting bottoms selected. Avatar can only wear one primary bottom garment.")

        # Rule 3: Multiple dresses
        dress_count = len(categories.get("dress", [])) + len(categories.get("one_piece", []))
        if dress_count > 1:
            conflicts.append("Multiple full-body dresses selected. Avatar can only wear one dress at a time.")

        # Rule 4: Essential coverage check
        has_top = "top" in categories or "tops" in categories or "shirt" in categories or "hoodie" in categories
        if not has_dress and not (has_top and has_bottom):
            if not has_top and has_bottom:
                warnings.append("Outfit is missing a top garment or shirt.")
            elif has_top and not has_bottom:
                warnings.append("Outfit is missing a bottom garment or trousers.")

        # Rule 5: Thermal disparity check
        if warmths:
            min_w = min(warmths)
            max_w = max(warmths)
            avg_w = sum(warmths) / len(warmths)
            if max_w - min_w >= 6:
                warnings.append("Extreme thermal disparity: Pairing heavy winter outerwear with ultra-light summer garments.")
        else:
            avg_w = 4.0

        # Map average warmth to thermal tier
        if avg_w <= 2.5:
            thermal_tier = "ultra_light"
        elif avg_w <= 4.0:
            thermal_tier = "light"
        elif avg_w <= 6.0:
            thermal_tier = "moderate"
        elif avg_w <= 8.0:
            thermal_tier = "warm"
        else:
            thermal_tier = "heavy_winter"

        # Rule 6: Formality clash check
        if formalities:
            min_f = min(formalities)
            max_f = max(formalities)
            mean_f = int(round(sum(formalities) / len(formalities)))
            if max_f - min_f >= 7:
                warnings.append("High formality clash: Combining black-tie formal garments with ultra-casual sportswear.")
        else:
            mean_f = 5

        # Compute numerical compatibility score [0.0, 1.0]
        score = 1.0
        score -= len(conflicts) * 0.45
        score -= len(warnings) * 0.10
        score = float(max(0.0, min(1.0, score)))

        is_compat = (len(conflicts) == 0 and score >= 0.50)

        return LookCompatibilityResult(
            is_compatible=is_compat,
            compatibility_score=round(score, 3),
            conflicts=conflicts,
            warnings=warnings,
            thermal_tier=thermal_tier,
            mean_formality=mean_f,
            composition=composition
        )

    def create_look(
        self,
        user_id: str,
        name: str,
        garment_ids: List[str],
        description: Optional[str] = None,
        avatar_snapshot: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        is_favorite: bool = False
    ) -> Dict[str, Any]:
        """
        Validates and creates a persistent saved look under the user's account.
        """
        # Fetch actual garment records to validate
        user_wardrobe = wardrobe_service.get_wardrobe(user_id)
        wardrobe_by_id = {g["id"]: g for g in user_wardrobe}

        # Resolve selected garments
        selected_garments = []
        for gid in garment_ids:
            if gid in wardrobe_by_id:
                selected_garments.append(wardrobe_by_id[gid])
            else:
                # Fallback for synthetic/catalog items
                selected_garments.append({"id": gid, "name": gid, "category": "top", "warmth": 4, "formality": 4})

        # Validate outfit compatibility
        compat = self.validate_compatibility(selected_garments)
        if not compat.is_compatible and len(compat.conflicts) > 0:
            logger.warning(f"Creating look '{name}' with compatibility conflicts: {compat.conflicts}")

        now_iso = datetime.utcnow().isoformat()
        look_payload = {
            "id": f"look_{uuid.uuid4().hex[:12]}",
            "user_id": str(user_id),
            "name": name.strip() or f"Curated Look ({now_iso[:10]})",
            "description": description or "",
            "garment_ids": garment_ids,
            "category_composition": compat.composition,
            "avatar_snapshot": avatar_snapshot or {},
            "compatibility_score": compat.compatibility_score,
            "compatibility_notes": compat.conflicts + compat.warnings,
            "thermal_tier": compat.thermal_tier,
            "estimated_formality": compat.mean_formality,
            "is_favorite": is_favorite,
            "wear_count": 0,
            "last_worn_at": None,
            "tags": tags or ["casual"],
            "created_at": now_iso,
            "updated_at": now_iso
        }

        saved = self._repo.save_look(user_id, look_payload)
        logger.info(f"[LookEngine] Created saved look '{saved['id']}' ({saved['name']}) for user {user_id}")
        return saved

    def get_looks(self, user_id: str, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all saved looks owned by user."""
        return self._repo.get_saved_looks(user_id, tag=tag)

    def get_look(self, user_id: str, look_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single saved look."""
        return self._repo.get_saved_look(user_id, look_id)

    def rename_look(self, user_id: str, look_id: str, new_name: str) -> Optional[Dict[str, Any]]:
        """Renames a saved look."""
        cleaned = new_name.strip()
        if not cleaned:
            return None
        return self._repo.update_saved_look(user_id, look_id, {"name": cleaned})

    def duplicate_look(self, user_id: str, look_id: str, new_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Duplicates a saved look."""
        return self._repo.duplicate_saved_look(user_id, look_id, new_name=new_name)

    def delete_look(self, user_id: str, look_id: str) -> bool:
        """Deletes a saved look."""
        return self._repo.delete_saved_look(user_id, look_id)

    def record_wear(self, user_id: str, look_id: str) -> Optional[Dict[str, Any]]:
        """Increments wear count and updates last_worn_at."""
        look = self.get_look(user_id, look_id)
        if not look:
            return None
        updates = {
            "wear_count": look.get("wear_count", 0) + 1,
            "last_worn_at": datetime.utcnow().isoformat()
        }
        return self._repo.update_saved_look(user_id, look_id, updates)

    def preview_look(self, user_id: str, look_id: str) -> Dict[str, Any]:
        """
        Compiles 3D ready preview payload for AvatarStudioViewer:
        garment assets, avatar measurements, and active cloth profiles.
        """
        look = self.get_look(user_id, look_id)
        if not look:
            raise ValueError(f"Look '{look_id}' not found.")

        user_wardrobe = wardrobe_service.get_wardrobe(user_id)
        wardrobe_by_id = {g["id"]: g for g in user_wardrobe}

        garments_resolved = []
        for gid in look.get("garment_ids", []):
            if gid in wardrobe_by_id:
                garments_resolved.append(wardrobe_by_id[gid])

        return {
            "look_id": look["id"],
            "name": look["name"],
            "garments": garments_resolved,
            "avatar_snapshot": look.get("avatar_snapshot", {}),
            "compatibility_score": look.get("compatibility_score", 1.0),
            "thermal_tier": look.get("thermal_tier", "moderate"),
            "estimated_formality": look.get("estimated_formality", 5),
            "wear_count": look.get("wear_count", 0)
        }


# Global singleton
look_management_service = YorvynLookManagementEngine()
