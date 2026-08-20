"""
AI Text Generator for Perfume Recommendations

This module generates natural, personalized explanations for AI-selected perfumes.
It receives the EXACT products selected by AI and generates matching text.

Flow:
1. Receive validated recommendations from AI engine
2. Extract key features (notes, vibe, occasion)
3. Generate personalized explanation
4. Ensure text matches the actual products shown
"""

import logging
from typing import Any, Dict, List, Optional

from .config import settings

logger = logging.getLogger(__name__)


def generate_recommendation_text(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str] = None,
    provider: str = "local"
) -> str:
    """
    Generate natural explanation text for recommendations.
    
    CRITICAL: Text must match the actual products in recommendations list.
    
    Args:
        recommendations: List of validated perfume recommendations
        user_query: Original user query
        intent: Extracted intent from AI
        user_name: User's name for personalization
        provider: AI provider used ("gemini"|"openai"|"local")
    
    Returns:
        Natural language explanation text
    """
    if not recommendations:
        return _generate_no_results_text(user_query, user_name)
    
    # Try AI generation first if available
    if settings.ai_fallback_enabled and provider in ("gemini", "openai"):
        ai_text = _try_ai_generation(recommendations, user_query, intent, user_name, provider)
        if ai_text:
            return ai_text
    
    # Fallback to template-based generation
    return _generate_template_text(recommendations, user_query, intent, user_name)


def _try_ai_generation(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str],
    provider: str
) -> Optional[str]:
    """Try AI-powered text generation"""
    try:
        if provider == "gemini":
            return _generate_with_gemini(recommendations, user_query, intent, user_name)
        elif provider == "openai":
            return _generate_with_openai(recommendations, user_query, intent, user_name)
    except Exception as e:
        logger.error(f"AI text generation failed: {e}")
    
    return None


def _generate_with_gemini(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str]
) -> Optional[str]:
    """Generate text using Gemini - NO TOKEN LIMITS"""
    try:
        import google.generativeai as genai
        
        if not settings.gemini_api_key:
            return None
        
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = _build_text_generation_prompt(recommendations, user_query, intent, user_name)
        
        # Call with generous token limit
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=500,  # Increased for full explanations
            temperature=0.7,
        )
        
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Gemini text generation error: {e}")
        return None


def _generate_with_openai(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str]
) -> Optional[str]:
    """Generate text using OpenAI - NO TOKEN LIMITS"""
    try:
        import openai
        
        if not settings.openai_api_key:
            return None
        
        openai.api_key = settings.openai_api_key
        
        prompt = _build_text_generation_prompt(recommendations, user_query, intent, user_name)
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly perfume advisor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,  # Increased for full explanations
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI text generation error: {e}")
        return None


def _build_text_generation_prompt(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str]
) -> str:
    """Build prompt for AI text generation"""
    # Build product list
    products_text = []
    for i, rec in enumerate(recommendations[:6], 1):
        products_text.append(
            f"{i}. {rec['name']} by {rec['brand']} - "
            f"{rec['accords'][:60]} (Rating: {rec['rating']:.1f})"
        )
    
    products_str = '\n'.join(products_text)
    
    # Build intent summary
    intent_parts = []
    if intent.get('occasion'):
        intent_parts.append(f"Occasion: {intent['occasion']}")
    if intent.get('mood'):
        intent_parts.append(f"Mood: {intent['mood']}")
    if intent.get('notes'):
        intent_parts.append(f"Notes: {', '.join(intent['notes'][:3])}")
    
    intent_str = ' | '.join(intent_parts) if intent_parts else "General recommendation"
    
    # Build name greeting
    greeting = f"{user_name}, " if user_name else ""
    
    prompt = f"""Generate a natural, friendly explanation for these perfume recommendations.

**USER QUERY:** {user_query}

**INTENT:** {intent_str}

**SELECTED PRODUCTS (you MUST mention these EXACT products):**
{products_str}

**REQUIREMENTS:**
1. Start with a brief greeting{f" using name '{user_name}'" if user_name else ""}
2. Mention the TOP PICK (first product) by name and brand
3. Briefly describe why it matches their request
4. Mention 1-2 other options from the list
5. Keep it conversational and under 80 words
6. Use markdown for product names (**bold**)
7. Use italics for notes (*citrus, woody*)

**STYLE:**
- Warm and helpful (like a friend recommending)
- Specific (mention actual notes and vibes)
- Concise (no fluff)
- Match the user's tone (casual if they're casual)

**EXAMPLE OUTPUT:**
"{greeting}I found 6 fragrances that match your vibe. Your top pick is **Dior Sauvage** — fresh *citrus* with a *woody* base, perfect for daily wear. Also check out **Bleu de Chanel** for something similar but slightly sweeter, and **Acqua di Gio** if you want more aquatic freshness. All are versatile and well-loved."

Generate the explanation now (ONLY the text, no extra commentary):"""

    return prompt


def _generate_template_text(
    recommendations: List[Dict[str, Any]],
    user_query: str,
    intent: Dict[str, Any],
    user_name: Optional[str]
) -> str:
    """Generate text using templates (fallback) - ONLY mentions validated products."""
    if not recommendations:
        return _generate_no_results_text(user_query, user_name)
    
    # Extract top pick - MUST use exact name from recommendations[0]
    top = recommendations[0]
    top_name = f"**{top['name']}**"  # Exact name, no "by Brand" to avoid mismatch
    
    # Extract notes from top pick
    accords = top.get('accords', '').split()[:3]
    notes_text = ', '.join(f"*{note}*" for note in accords) if accords else "classic notes"
    
    # Build greeting
    greeting = f"{user_name}, " if user_name else ""
    
    # Build context phrase
    context_parts = []
    if intent.get('occasion'):
        context_parts.append(f"{intent['occasion']} wear")
    if intent.get('mood'):
        mood = intent['mood']
        if mood == 'fresh':
            context_parts.append("fresh and clean")
        elif mood == 'warm':
            context_parts.append("warm and sensual")
        elif mood == 'floral':
            context_parts.append("floral and romantic")
        elif mood == 'woody':
            context_parts.append("woody and bold")
        elif mood == 'sweet':
            context_parts.append("sweet and playful")
    
    context_phrase = " for " + " · ".join(context_parts) if context_parts else ""
    
    # Build main text - ONLY mention products in recommendations list
    num_found = len(recommendations)
    
    text = f"{greeting}I found **{num_found} fragrances**{context_phrase}. "
    text += f"Your top pick is {top_name} — {notes_text}. "
    
    # Add AI reason if available
    if top.get('ai_reason'):
        text += f"{top['ai_reason']}. "
    
    # Mention other options - ONLY from recommendations list
    if num_found > 1:
        other_names = []
        for rec in recommendations[1:3]:  # Mention 2 more - EXACT names only
            other_names.append(f"**{rec['name']}**")
        
        if other_names:
            text += f"Also check out {' and '.join(other_names)}. "
    
    text += "Tap any card to see full details."
    
    return text


def _generate_no_results_text(user_query: str, user_name: Optional[str]) -> str:
    """Generate text when no results found"""
    greeting = f"{user_name}, " if user_name else ""
    
    return (
        f"{greeting}I searched through 73,000+ fragrances but couldn't find a strong match for "
        f'"{user_query}". Could you tell me more — like a specific note (rose, oud, vanilla), '
        f"an occasion (date, office, party), or a perfume you already love?"
    )


def generate_follow_up_suggestions(
    recommendations: List[Dict[str, Any]],
    intent: Dict[str, Any],
    user_context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Generate contextual follow-up suggestion chips.
    
    Args:
        recommendations: Current recommendations
        intent: Extracted intent
        user_context: User profile context
    
    Returns:
        List of follow-up suggestion strings
    """
    suggestions = []
    
    # Memory-based suggestions
    if user_context:
        if user_context.get('liked_perfume_names'):
            suggestions.append(f"More like {user_context['liked_perfume_names'][0]}")
        if user_context.get('favorite_notes'):
            suggestions.append(f"More {user_context['favorite_notes'][0]} fragrances")
    
    # Intent-based refinements
    if not intent.get('gender'):
        suggestions.extend(["For women", "For men", "Unisex options"])
    
    if not intent.get('occasion'):
        suggestions.extend(["For daily wear", "For a date night", "For the office"])
    
    if not intent.get('mood'):
        suggestions.extend(["Something fresh", "Something warm", "Something floral"])
    
    # Note-based from top result
    if recommendations:
        top_accords = recommendations[0].get('accords', '').split()[:2]
        for note in top_accords:
            if note and len(note) > 3:
                suggestions.append(f"More {note} fragrances")
    
    # Budget
    if not intent.get('budget_max'):
        suggestions.append("Under ₹2000")
        suggestions.append("Premium options")
    
    # Refinement
    suggestions.extend([
        "Something lighter",
        "Something more intense",
        "Show me similar brands"
    ])
    
    # Deduplicate and limit to 6
    seen = set()
    result = []
    for s in suggestions:
        if s not in seen and len(result) < 6:
            seen.add(s)
            result.append(s)
    
    return result


def verify_text_product_alignment(
    text: str,
    recommendations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verify that the generated text only mentions products from the recommendations list.
    
    Args:
        text: Generated explanation text
        recommendations: List of validated recommendations
    
    Returns:
        Dict with alignment metrics:
        - is_aligned: bool (True if all mentioned products are in recommendations)
        - mentioned_products: List[str] (product names mentioned in text)
        - missing_products: List[str] (mentioned but not in recommendations)
        - alignment_rate: float (0.0-1.0)
    """
    if not recommendations:
        return {
            'is_aligned': True,
            'mentioned_products': [],
            'missing_products': [],
            'alignment_rate': 1.0
        }
    
    # Extract product names from recommendations
    actual_names = set()
    for rec in recommendations:
        name = rec.get('name', '').strip()
        if name:
            actual_names.add(name.lower())
    
    # Extract product names mentioned in text (look for **bold** markdown)
    import re
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
    mentioned_names = bold_pattern.findall(text)
    
    # Also check for plain text mentions of product names
    text_lower = text.lower()
    all_mentioned = set()
    
    for name in mentioned_names:
        all_mentioned.add(name.lower().strip())
    
    # Check for plain text mentions
    for rec in recommendations:
        name = rec.get('name', '').strip()
        if name and name.lower() in text_lower:
            all_mentioned.add(name.lower())
    
    # Find missing products (mentioned but not in recommendations)
    missing = []
    for mentioned in all_mentioned:
        # Check if this mentioned name matches any actual name
        found = False
        for actual in actual_names:
            # Allow partial matches (e.g., "Dior Sauvage" matches "Dior Sauvage EDT")
            if mentioned in actual or actual in mentioned:
                found = True
                break
        
        if not found:
            missing.append(mentioned)
    
    # Calculate alignment rate
    if len(all_mentioned) == 0:
        alignment_rate = 1.0  # No products mentioned = perfect alignment
    else:
        alignment_rate = 1.0 - (len(missing) / len(all_mentioned))
    
    is_aligned = len(missing) == 0
    
    result = {
        'is_aligned': is_aligned,
        'mentioned_products': list(all_mentioned),
        'missing_products': missing,
        'alignment_rate': alignment_rate
    }
    
    if not is_aligned:
        logger.warning(f"TEXT-CARD MISMATCH: {len(missing)} products mentioned but not in recommendations")
        logger.warning(f"Missing products: {missing}")
    
    return result
