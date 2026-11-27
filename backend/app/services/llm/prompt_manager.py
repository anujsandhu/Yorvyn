"""
Prompt Engineering & Template Manager for Yorvyn LLM Architecture.
Encapsulates system instructions, anti-hallucination guardrails, and role prompts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class PromptManager:
    """Generates standardized system prompts and instructions for the LLM."""

    BASE_SYSTEM_INSTRUCTIONS = (
        "You are the Yorvyn AI Personal Stylist, a premier haute couture, contemporary tailoring, "
        "and personal style advisor. Your mission is to provide personalized, sophisticated fashion advice "
        "grounded in the user's authentic physical proportions, colorimetry, style preferences, and real wardrobe.\n\n"
        "STRICT OPERATIONAL RULES:\n"
        "1. GROUND TRUTH ONLY: Never invent imaginary garment IDs, fictional brands, or nonexistent wardrobe items. "
        "Every recommended outfit must be assembled from real items returned by tools or present in the wardrobe snapshot.\n"
        "2. FASHION INTELLIGENCE: Respect user skin undertones and seasonal color palettes. Suggest harmonious color pairings "
        "(analogous, complementary, tonal) and respect fit preferences (slim, tailored, regular, relaxed, oversized).\n"
        "3. TOOL USAGE: When information is needed (e.g. user Fashion DNA, wardrobe contents, weather context, or outfit scoring), "
        "invoke the registered backend tools rather than guessing.\n"
        "4. PREFERENCE SEPARATION: Distinguish permanent preferences (e.g. 'I prefer relaxed-fit trousers') from temporary "
        "session constraints (e.g. 'For this wedding, suggest traditional attire'). Do NOT overwrite persistent profiles with temporary requests.\n"
        "5. REJECTION HANDLING: When the user expresses dislike for a color, material, or fit, acknowledge it warmly, "
        "update preferences accordingly, and never recommend that rejected attribute in the same context.\n"
        "6. INCLUSIVE RESPECT: Never body-shame, criticize natural proportions, or treat skin tones as limitations on what someone can wear. "
        "Celebrate individuality with refined fashion rationale."
    )

    @classmethod
    def get_system_prompt(
        cls,
        fashion_dna: Optional[Dict[str, Any]] = None,
        wardrobe_summary: Optional[Dict[str, Any]] = None,
        weather_context: Optional[Dict[str, Any]] = None,
        temporary_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Constructs a fully grounded system prompt with user context."""
        parts = [cls.BASE_SYSTEM_INSTRUCTIONS]

        if fashion_dna:
            body = fashion_dna.get("body_profile", {})
            colour = fashion_dna.get("colour_profile", {})
            style = fashion_dna.get("style_profile", {})
            prefs = fashion_dna.get("additional_preferences", {})

            dna_text = (
                "\n\n=== USER FASHION DNA ===\n"
                f"- Height: {body.get('height_cm')} cm, Silhouette: {body.get('silhouette')}, Fit Preference: {body.get('fit_preference')}\n"
                f"- Skin Tone: {colour.get('skin_tone_range')}, Undertone: {colour.get('skin_undertone')}, Palette: {colour.get('personal_palette')}\n"
                f"- Preferred Colours: {', '.join(colour.get('preferred_colours', []))}\n"
                f"- Disliked Colours: {', '.join(colour.get('disliked_colours', []))}\n"
                f"- Primary Styles: {', '.join(style.get('primary_styles', []))}\n"
                f"- Preferred Brands: {', '.join(prefs.get('preferred_brands', []))}\n"
                f"- Preferred Materials: {', '.join(prefs.get('preferred_materials', []))}\n"
                f"- Disliked Materials: {', '.join(prefs.get('disliked_materials', []))}\n"
                f"- Budget Tier: {prefs.get('budget_level')} (${prefs.get('min_budget')}-${prefs.get('max_budget')})"
            )
            parts.append(dna_text)

        if wardrobe_summary:
            w_text = (
                "\n\n=== WARDROBE SNAPSHOT ===\n"
                f"- Total Items Owned: {wardrobe_summary.get('total_items', 0)}\n"
                f"- Categories: {wardrobe_summary.get('category_breakdown', {})}\n"
                f"- Dominant Colors: {wardrobe_summary.get('dominant_colors', {})}\n"
                f"- Utilization Rate: {int(wardrobe_summary.get('utilization_rate', 0) * 100)}%"
            )
            parts.append(w_text)

        if weather_context:
            temp = weather_context.get("temperature_c", 20)
            cond = weather_context.get("condition", "clear")
            parts.append(f"\n\n=== LOCAL WEATHER CONTEXT ===\n- Temperature: {temp}°C, Condition: {cond}")

        if temporary_context:
            parts.append(f"\n\n=== TEMPORARY SESSION CONSTRAINTS ===\n{temporary_context}")

        return "".join(parts)


# Global singleton
prompt_manager = PromptManager()

