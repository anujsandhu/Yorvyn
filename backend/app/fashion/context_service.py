"""
Yorvyn Context & Personal Identity Engine
Extracts weather context, natural language occasion intents,
and manages user personal styling profiles (skin undertone, body shape, aesthetics).
"""

from typing import Dict, Optional
import re

# Default Personal Identity & Style Profile
DEFAULT_USER_PROFILE = {
    "user_id": "default_user",
    "name": "Alex",
    "body_shape": "athletic_tapered",  # athletic_tapered, hourglass, rectangle, inverted_triangle, pear
    "height_cm": 178,
    "skin_undertone": "warm-bright",   # warm-bright, cool-soft, warm-deep, cool-bright
    "color_season": "autumn",          # spring, summer, autumn, winter
    "fit_preference": "relaxed_tailored", # slim, regular, relaxed_tailored, oversized
    "primary_aesthetics": ["quiet_luxury", "minimalist_scandi", "smart_casual"],
    "budget_tier": "mid_premium",      # budget, mid_premium, luxury
    "disliked_colors": ["neon yellow", "bright magenta"],
    "lifestyle_notes": "Hybrid office & remote, likes effortless neutrals and versatile layering."
}

class ContextService:
    """Extracts and maintains dynamic environment context."""
    
    def __init__(self):
        self._user_profiles: Dict[str, Dict] = {
            "default_user": dict(DEFAULT_USER_PROFILE)
        }
        
    def get_user_profile(self, user_id: str = "default_user") -> Dict:
        return self._user_profiles.get(user_id, DEFAULT_USER_PROFILE)

    def update_user_profile(self, user_id: str, updates: Dict) -> Dict:
        current = self.get_user_profile(user_id)
        current.update(updates)
        self._user_profiles[user_id] = current
        return current

    def parse_context_from_query(self, query: str, user_temp: Optional[float] = None) -> Dict:
        """
        Parses occasion, temperature, weather condition, and aesthetic vibe
        from freeform natural language user prompts.
        """
        q_lower = query.lower()
        
        # 1. Detect Occasion
        occasion = "casual_day"
        if any(w in q_lower for w in ["office", "work", "meeting", "interview", "business", "corporate"]):
            occasion = "work_office"
        elif any(w in q_lower for w in ["date", "dinner", "evening", "cocktail", "bar", "drinks", "romantic"]):
            occasion = "date_night"
        elif any(w in q_lower for w in ["wedding", "gala", "black tie", "formal", "award", "banquet"]):
            occasion = "formal_event"
        elif any(w in q_lower for w in ["beach", "resort", "vacation", "summer trip", "tropical", "holiday"]):
            occasion = "summer_vacation"
            
        # 2. Detect Temperature & Weather
        temp = user_temp if user_temp is not None else 18.0 # Default pleasant 18°C
        condition = "clear"
        
        # Check condition keywords
        if any(w in q_lower for w in ["rain", "rainy", "storm", "wet", "drizzle"]):
            condition = "rainy"
        elif any(w in q_lower for w in ["snow", "freezing", "ice", "blizzard"]):
            condition = "snow"
        elif any(w in q_lower for w in ["hot", "sunny", "sweltering", "heatwave"]):
            condition = "sunny"
        elif any(w in q_lower for w in ["chilly", "cold", "crisp", "breezy"]):
            condition = "chilly"

        # Check for explicit temperature numbers like "12C", "5 degrees", "80F"
        temp_match = re.search(r'(\d+)\s*(?:°\s*c|c\b|deg|degrees)', q_lower)
        if temp_match:
            try:
                temp = float(temp_match.group(1))
            except ValueError:
                pass
        elif condition == "cold" or condition == "snow":
            temp = 2.0
        elif condition == "rainy":
            temp = min(temp, 14.0)
        elif condition == "sunny":
            temp = max(temp, 26.0)
        elif condition == "chilly":
            temp = min(temp, 10.0)


        # 3. Detect Aesthetic Tone
        aesthetic = None
        if any(w in q_lower for w in ["quiet luxury", "old money", "classy", "sophisticated"]):
            aesthetic = "quiet_luxury"
        elif any(w in q_lower for w in ["minimal", "minimalist", "scandi", "monochrome", "clean"]):
            aesthetic = "minimalist_scandi"
        elif any(w in q_lower for w in ["streetwear", "techwear", "urban", "edgy", "oversized"]):
            aesthetic = "streetwear_tech"
        elif any(w in q_lower for w in ["parisian", "french", "chic"]):
            aesthetic = "parisian_chic"
        elif any(w in q_lower for w in ["smart casual", "casual chic"]):
            aesthetic = "smart_casual"

        return {
            "occasion": occasion,
            "temperature_celsius": temp,
            "condition": condition,
            "target_aesthetic": aesthetic,
            "raw_prompt": query
        }

# Global singleton
context_service = ContextService()
