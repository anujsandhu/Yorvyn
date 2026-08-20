"""
Yorvyn AI Stylist Orchestrator
Coordinates intent parsing, context assembly, digital wardrobe retrieval,
outfit generation, editorial styling rationale synthesis, and learning feedback.
"""

from typing import Dict, List, Optional
from .context_service import context_service
from .wardrobe_service import wardrobe_service
from .outfit_generator import outfit_generator
from .fashion_knowledge import STYLE_AESTHETICS, SEASONAL_COLOR_PALETTES

class FashionOrchestrator:
    """Conversational Fashion Intelligence Engine & Tool Dispatcher."""
    
    def __init__(self):
        # In-memory feedback store: user_id -> List of feedback events
        self._feedback_log: Dict[str, List[Dict]] = {}

    def chat_stylist(
        self,
        message: str,
        user_id: str = "default_user",
        override_temp: Optional[float] = None
    ) -> Dict:
        """
        Processes user chat messages, extracts context/intent, runs outfit recommendations,
        and returns an editorial AI response alongside structured outfit cards.
        """
        # 1. Parse Context & Intent
        context = context_service.parse_context_from_query(message, override_temp)
        profile = context_service.get_user_profile(user_id)
        
        # 2. Execute Outfit Generation Tool
        result = outfit_generator.generate_outfits(
            user_id=user_id,
            occasion=context["occasion"],
            temp_celsius=context["temperature_celsius"],
            condition=context["condition"],
            target_aesthetic=context["target_aesthetic"]
        )
        
        outfits = result.get("outfits", [])
        
        # 3. Synthesize Editorial Rationale
        response_text = self._synthesize_editorial_rationale(
            message=message,
            context=context,
            profile=profile,
            outfits=outfits
        )
        
        return {
            "reply": response_text,
            "context": context,
            "outfits": outfits,
            "profile_snippet": {
                "body_shape": profile["body_shape"].replace("_", " ").title(),
                "color_season": profile["color_season"].title(),
                "aesthetics": profile["primary_aesthetics"]
            }
        }

    def _synthesize_editorial_rationale(
        self,
        message: str,
        context: Dict,
        profile: Dict,
        outfits: List[Dict]
    ) -> str:
        temp = context["temperature_celsius"]
        cond = context["condition"]
        occasion = context["occasion"].replace("_", " ").title()
        season = profile["color_season"].title()
        
        if not outfits:
            return (
                f"I looked at your digital wardrobe for a {occasion} look in {temp}°C ({cond}) conditions, "
                "but you may need to add a few more foundational pieces (tops, trousers, or outerwear) "
                "to generate complete ensembles."
            )
            
        top_outfit = outfits[0]
        top_name = top_outfit["layer_breakdown"]["top"]["name"]
        bottom_name = top_outfit["layer_breakdown"]["bottom"]["name"]
        outerwear = top_outfit["layer_breakdown"].get("outerwear")
        outerwear_str = f" layered beneath the {outerwear['name']}" if outerwear else ""
        
        editorial = (
            f"Here are my tailored recommendations for **{occasion}** ({temp}°C, {cond}).\n\n"
            f"For your primary look (**{top_outfit['title']}**), I anchored the silhouette with your **{top_name}** "
            f"and **{bottom_name}**{outerwear_str}. The {', '.join(top_outfit['color_palette'])} palette creates a "
            f"harmonious aesthetic that complements your **{season}** color profile while maintaining effortless thermal comfort."
        )
        return editorial

    def record_feedback(self, user_id: str, outfit_id: str, action: str, note: Optional[str] = None) -> Dict:
        """
        Records user interactions (wear_today, like, dislike, save, skip)
        to refine personal style models.
        """
        if user_id not in self._feedback_log:
            self._feedback_log[user_id] = []
            
        event = {
            "outfit_id": outfit_id,
            "action": action,  # wear_today, like, dislike, save, skip
            "note": note or "",
            "timestamp": "now"
        }
        self._feedback_log[user_id].append(event)
        return {"status": "success", "event": event, "total_events": len(self._feedback_log[user_id])}

# Global singleton
fashion_orchestrator = FashionOrchestrator()
