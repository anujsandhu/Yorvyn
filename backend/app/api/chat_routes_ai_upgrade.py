"""
UPGRADED Chat Routes with AI-Primary Architecture

This is the new chat endpoint that uses AI as the PRIMARY decision engine.

Flow:
1. User sends query
2. Extract intent and context
3. AI selects products from dataset (with semantic pre-filtering)
4. Backend validates product IDs
5. AI generates explanation text for THOSE EXACT products
6. Return matched recommendations + text

Key improvements:
- AI makes product selection decisions (not just text)
- Semantic search pre-filters candidates
- Strict validation prevents invented products
- Text always matches displayed cards
- Confidence scoring and fallback logic
"""

import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
from ..ai_recommendation_engine import get_ai_recommendations, initialize_ai_engine
from ..ai_text_generator import (
    generate_recommendation_text,
    generate_follow_up_suggestions,
    verify_text_product_alignment
)
from ..conversational_ai import generate_conversational_response
from ..intent_classifier import classify_intent, get_intent_response, Intent
from ..spell_corrector import correct_text
from ..tone_detector import detect_tone

router = APIRouter()
logger = logging.getLogger(__name__)

# Budget extraction pattern (matches INR amounts like "₹2000", "under 2000", "Rs. 1500")
BUDGET_PATTERN = re.compile(
    r"\b(?:under|below|less than|max|around|about|budget|cheap|affordable)?\s*"
    r"(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,]*)\s*(?:rs\.?|inr|₹|\$|usd|rupees?)?\b",
    re.IGNORECASE,
)


# ── Schemas ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str          # "user" | "advisor"
    text: str
    timestamp: Optional[int] = None


class UserContext(BaseModel):
    """User profile and memory"""
    name: Optional[str] = ""
    nickname: Optional[str] = ""
    gender: Optional[str] = ""
    date_of_birth: Optional[str] = ""
    preferred_gender: Optional[str] = ""
    favorite_notes: Optional[List[str]] = []
    preferred_occasion: Optional[str] = ""
    preferred_season: Optional[str] = ""
    preferred_intensity: Optional[str] = ""
    liked_perfume_names: Optional[List[str]] = []
    recent_searches: Optional[List[str]] = []
    is_new_user: Optional[bool] = False
    total_chats: Optional[int] = 0


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    num_recommendations: int = Field(default=6, ge=1, le=20)
    user_context: Optional[UserContext] = None


class PerfumeResult(BaseModel):
    perfume_id: str
    name: str
    brand: str
    family: str
    rating: float
    ml_score: float
    rating_score: float
    popularity_score: float
    final_score: float
    description: Optional[str] = None
    price_usd: Optional[float] = None
    image_url: Optional[str] = None
    gender: Optional[str] = None
    accords: Optional[str] = None
    algorithm: Optional[str] = None
    ai_reason: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    recommendations: List[PerfumeResult] = []
    extracted_context: Dict[str, Any] = {}
    follow_up_suggestions: List[str] = []
    confidence: float = 0.0
    ai_provider: Optional[str] = None


# ── Helper Functions ──────────────────────────────────────────────────

def _get_display_name(user_ctx: Optional[UserContext]) -> str:
    """Get user's display name"""
    if not user_ctx:
        return ""
    return (user_ctx.nickname or user_ctx.name or "").strip()


def _build_user_context_dict(user_ctx: Optional[UserContext]) -> Dict[str, Any]:
    """Convert UserContext to dict for AI engine"""
    if not user_ctx:
        return {}
    
    return {
        'gender': user_ctx.preferred_gender or user_ctx.gender or "",
        'occasion': user_ctx.preferred_occasion or "",
        'season': user_ctx.preferred_season or "",
        'favorite_notes': user_ctx.favorite_notes or [],
        'liked_perfume_names': user_ctx.liked_perfume_names or [],
        'recent_searches': user_ctx.recent_searches or [],
        'is_new_user': user_ctx.is_new_user or False,
    }


def _extract_context_from_history(messages: List[ChatMessage]) -> Dict[str, Any]:
    """Extract context from conversation history"""
    # For now, use simple extraction from latest message
    # Can be enhanced with multi-turn context merging
    if not messages:
        return {}
    
    latest = messages[-1].text if messages else ""
    
    # Simple keyword extraction
    context = {}
    
    # Gender
    if any(word in latest.lower() for word in ['women', 'woman', 'female', 'her', 'she', 'girlfriend', 'wife', 'mom', 'mother', 'sister']):
        context['gender'] = 'women'
    elif any(word in latest.lower() for word in ['men', 'man', 'male', 'him', 'he', 'boyfriend', 'husband', 'dad', 'father', 'brother']):
        context['gender'] = 'men'
    
    # Occasion
    if any(word in latest.lower() for word in ['office', 'work', 'professional']):
        context['occasion'] = 'office'
    elif any(word in latest.lower() for word in ['date', 'romantic', 'evening']):
        context['occasion'] = 'date'
    elif any(word in latest.lower() for word in ['party', 'club', 'night']):
        context['occasion'] = 'party'
    elif any(word in latest.lower() for word in ['daily', 'everyday', 'casual']):
        context['occasion'] = 'daily'
    
    # Mood
    if any(word in latest.lower() for word in ['fresh', 'clean', 'light', 'citrus']):
        context['mood'] = 'fresh'
    elif any(word in latest.lower() for word in ['warm', 'cozy', 'sensual', 'amber']):
        context['mood'] = 'warm'
    elif any(word in latest.lower() for word in ['floral', 'flower', 'rose']):
        context['mood'] = 'floral'
    elif any(word in latest.lower() for word in ['woody', 'wood', 'oud', 'cedar']):
        context['mood'] = 'woody'
    elif any(word in latest.lower() for word in ['sweet', 'fruity', 'gourmand']):
        context['mood'] = 'sweet'
    elif any(word in latest.lower() for word in ['bold', 'strong', 'intense', 'powerful', 'spicy']):
        context['mood'] = 'bold'
    
    # Season
    if any(word in latest.lower() for word in ['summer', 'hot', 'warm weather']):
        context['season'] = 'summer'
    elif any(word in latest.lower() for word in ['winter', 'cold', 'cold weather']):
        context['season'] = 'winter'
    elif any(word in latest.lower() for word in ['spring']):
        context['season'] = 'spring'
    elif any(word in latest.lower() for word in ['fall', 'autumn']):
        context['season'] = 'fall'
    
    # Budget extraction (INR to USD conversion)
    budget_matches = BUDGET_PATTERN.findall(latest)
    if budget_matches:
        try:
            # Take the last match (most specific)
            amount = int(budget_matches[-1].replace(",", ""))
            # Convert INR to USD (divide by 84) if amount > 500
            # Amounts <= 500 are assumed to be already in USD
            context['budget_max'] = round(amount / 84.0, 1) if amount > 500 else float(amount)
            logger.info(f"Extracted budget: ₹{amount} → ${context['budget_max']}")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse budget from '{budget_matches[-1]}': {e}")
    
    return context


def _has_sufficient_context(user_message: str, context: Dict[str, Any], history: List[Dict[str, str]]) -> bool:
    """
    Universal check: Do we have enough information to make good recommendations?
    
    RELAXED MODE: Be more lenient to provide recommendations more often
    
    Required information (at least 1 piece):
    1. Gender/recipient (for yourself, him, her)
    2. Occasion (daily, date, office, party) OR Mood (fresh, woody, floral, sweet)
    3. Budget (optional but helpful)
    
    Returns True if we have ANY context to recommend.
    """
    msg_lower = user_message.lower()
    
    # Special case 1: Follow-up queries (more, another, different, similar)
    # If there's conversation history and this is a follow-up, assume we have context
    if history and len(history) > 0:
        follow_up_keywords = ['more', 'another', 'different', 'similar', 'other', 'else', 'alternatives']
        if any(keyword in msg_lower for keyword in follow_up_keywords):
            # This is a follow-up query, assume we have enough context from history
            return True
    
    # Special case 2: Preference refinement in conversation
    # If there's history and current message has mood/occasion/notes, combine contexts
    if history and len(history) > 0:
        # Check if current message adds preference information
        has_preference = (
            context.get('mood') or 
            context.get('occasion') or
            any(word in msg_lower for word in ['fresh', 'woody', 'floral', 'sweet', 'bold', 'citrus', 'vanilla', 'rose'])
        )
        if has_preference:
            # This is adding preferences to existing conversation, use combined context
            return True
    
    # Special case 3: Any perfume-related query
    # If the message contains perfume keywords, try to recommend
    perfume_keywords = ['perfume', 'fragrance', 'scent', 'cologne']
    if any(keyword in msg_lower for keyword in perfume_keywords):
        # This is clearly a perfume query, try to help
        return True
    
    # Count how many key pieces of information we have
    info_count = 0
    
    # 1. Gender/recipient
    if context.get('gender'):
        info_count += 1
    elif any(word in msg_lower for word in ['myself', 'me', 'i want', 'i need']):
        info_count += 1  # For themselves
    
    # 2. Occasion OR Mood OR Season
    if context.get('occasion') or context.get('mood') or context.get('season'):
        info_count += 1
    
    # 3. Budget (optional, gives +0.5)
    if context.get('budget_max'):
        info_count += 0.5
    
    # RELAXED: Need at least 1 piece of information (was 2)
    # This makes the system more helpful and less strict
    # Examples that now pass:
    # - "I want perfume" → Has perfume keyword ✅
    # - "perfume for gifting" → Has perfume keyword ✅
    # - "suggest me perfume" → Has perfume keyword ✅
    # - "fresh perfume" → Has mood ✅
    # - "perfume for my girlfriend" → Has gender ✅
    #
    # Only fails for completely unrelated queries:
    # - "hello" (greeting, no perfume context) ❌
    
    return info_count >= 1 or any(keyword in msg_lower for keyword in perfume_keywords)


def _generate_preference_questions(user_message: str, context: Dict[str, Any], user_name: Optional[str]) -> str:
    """
    Generate smart questions based on what information is missing.
    Universal for all perfume queries with icons and step indicators.
    """
    msg_lower = user_message.lower()
    
    # Check what's missing
    has_gender = bool(context.get('gender')) or any(word in msg_lower for word in ['myself', 'me', 'i want'])
    has_occasion_or_mood = bool(context.get('occasion') or context.get('mood') or context.get('season'))
    has_budget = bool(context.get('budget_max'))
    
    # Count what we have
    info_count = sum([has_gender, has_occasion_or_mood, has_budget])
    
    # Determine if it's for gifting
    is_gift = any(word in msg_lower for word in ['gift', 'gifting', 'present', 'someone'])
    
    # Build questions based on what's missing
    if is_gift and not has_gender:
        # Gifting but don't know who - Step 1
        return f"🎁 I'll help you find the perfect gift!\n\n**Step 1 of 3: Who is this fragrance for?**\n• For him 👨\n• For her 👩\n• Unisex (anyone) ✨"
    
    if not has_gender and not is_gift:
        # Don't know if for themselves or gift - Step 1
        greeting = f"{user_name}, " if user_name else ""
        return f"👋 {greeting}I'll help you find your perfect fragrance!\n\n**Step 1 of 4: Who is this fragrance for?**\n• For myself 🙋\n• For him 👨\n• For her 👩\n• As a gift 🎁"
    
    if has_gender and not has_occasion_or_mood:
        # Know gender but not occasion/mood - Step 2
        gender_text = "for her" if context.get('gender') == 'women' else "for him" if context.get('gender') == 'men' else "for you"
        return f"✨ Got it, {gender_text}!\n\n**Step 2 of 4: What's the vibe?**\n• Fresh & citrusy 🍋\n• Warm & woody 🌲\n• Sweet & floral 🌸\n• Bold & spicy 🔥\n\n**Step 3 of 4: What's the occasion?**\n• Daily wear 📅\n• Date night 💕\n• Office/Work 💼\n• Special event 🎉"
    
    if has_gender and has_occasion_or_mood and not has_budget:
        # Know gender and mood but not budget - Step 3
        return f"Perfect! 🎯\n\n**Step 4 of 4: What's your budget?**\n• Under ₹2000 💰\n• Under ₹3000 💰💰\n• Under ₹5000 💰💰💰\n• No budget limit ✨"
    
    if not has_gender and has_occasion_or_mood:
        # Know mood but not gender - Step 1
        mood_text = context.get('mood', context.get('occasion', context.get('season', 'that')))
        return f"Nice, {mood_text} scents! 🌟\n\n**Step 1 of 3: Who is this for?**\n• For myself 🙋\n• For him 👨\n• For her 👩"
    
    # Default: ask for all - Step 1
    greeting = f"{user_name}, " if user_name else ""
    return f"👋 {greeting}I'll help you find your perfect fragrance!\n\n**Step 1 of 4: Who is this fragrance for?**\n• For myself 🙋\n• For him 👨\n• For her 👩\n• As a gift 🎁\n\n**Step 2 of 4: What's the vibe?**\n• Fresh & citrusy 🍋\n• Warm & woody 🌲\n• Sweet & floral 🌸\n• Bold & spicy 🔥"


def _generate_context_chips(context: Dict[str, Any]) -> List[str]:
    """Generate suggestion chips based on missing context"""
    chips = []
    
    # If no gender, suggest gender options
    if not context.get('gender'):
        chips.extend(["For myself", "For her", "For him"])
    
    # If no mood, suggest mood options
    if not context.get('mood'):
        chips.extend(["Fresh & citrusy", "Warm & woody", "Sweet & floral", "Bold & spicy"])
    
    # If no occasion, suggest occasions
    if not context.get('occasion'):
        chips.extend(["Daily wear", "Date night", "Office", "Special occasions"])
    
    # Always include budget options
    if not context.get('budget_max'):
        chips.extend(["Under ₹2000", "Under ₹3000", "Under ₹5000"])
    
    # Return unique chips, max 6
    return list(dict.fromkeys(chips))[:6]




# ── Main Chat Endpoint ────────────────────────────────────────────────

@router.post("/ai/chat-v2", response_model=ChatResponse)
def chat_v2(req: ChatRequest):
    """
    AI-POWERED Chat Endpoint (Version 2)
    
    This endpoint uses AI as the PRIMARY decision engine:
    1. AI interprets user intent
    2. AI selects products from dataset (with semantic pre-filtering)
    3. Backend validates product IDs
    4. AI generates explanation for THOSE EXACT products
    5. Returns matched recommendations + text
    
    Key differences from v1:
    - AI makes product selection (not just text generation)
    - Semantic search pre-filters candidates
    - Strict validation prevents hallucinations
    - Text always matches cards
    """
    # Debug: Log received messages
    logger.info(f"📥 Received {len(req.messages)} messages in conversation")
    for i, msg in enumerate(req.messages):
        logger.info(f"  [{i}] {msg.role}: {msg.text[:50]}...")
    
    user_ctx = req.user_context
    name = _get_display_name(user_ctx)
    
    # ── Handle empty session ──────────────────────────────────────────
    if not req.messages:
        greeting = f"Hey {name}, " if name else "Hey — "
        greeting += "I'll help you find your perfect scent. Tell me what kind of vibe you're going for."
        
        # Personalized chips
        chips = []
        if user_ctx and user_ctx.favorite_notes:
            chips.append(f"More {user_ctx.favorite_notes[0]} fragrances")
        chips.extend([
            "Fresh citrus for summer",
            "Woody oud for winter",
            "Floral for a wedding",
            "Something like Dior Sauvage",
            "Under ₹2000",
            "For daily wear",
        ])
        
        return ChatResponse(
            reply=greeting,
            follow_up_suggestions=list(dict.fromkeys(chips))[:6],
        )
    
    # ── Extract latest user message ───────────────────────────────────
    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        return ChatResponse(
            reply="What kind of fragrance are you looking for?",
            follow_up_suggestions=["Fresh & clean", "Woody & bold", "Floral & feminine"],
        )
    
    latest_user_msg = user_messages[-1].text.strip()
    
    # ── Spell correction ──────────────────────────────────────────────
    corrected_msg, corrections = correct_text(latest_user_msg)
    
    # ── Intent classification ─────────────────────────────────────────
    conversation_history = [{"role": m.role, "text": m.text} for m in req.messages[:-1]]
    intent_result = classify_intent(corrected_msg, conversation_history)
    
    # Handle non-query intents (greeting, vague, abusive)
    if intent_result.intent in (Intent.GREETING, Intent.VAGUE, Intent.ABUSIVE):
        # Use conversational AI for natural responses
        response_text = generate_conversational_response(
            user_message=corrected_msg,
            conversation_history=[{"role": m.role, "text": m.text} for m in req.messages[:-1]],
            user_name=name,
            has_recommendations=False,
            recommendations=None
        )
        
        # Generate contextual chips
        if intent_result.intent == Intent.GREETING:
            chips = ["Fresh citrus", "Woody oud", "Floral romantic", "Under ₹2000"]
        elif intent_result.intent == Intent.VAGUE:
            chips = ["Fresh & clean", "Woody & bold", "Floral & feminine", "Warm & sensual"]
        else:
            chips = ["Fresh and clean", "Woody and bold"]
        
        return ChatResponse(
            reply=response_text,
            recommendations=[],
            follow_up_suggestions=chips,
            confidence=intent_result.confidence,
        )
    
    # ── Build context for AI ──────────────────────────────────────────
    # Merge user profile context + conversation context
    user_context_dict = _build_user_context_dict(user_ctx)
    conversation_context = _extract_context_from_history(user_messages)
    
    # Merge contexts (conversation overrides profile)
    merged_context = {**user_context_dict, **conversation_context}
    
    # ── Check if we have enough information to recommend ──────────────
    # Universal rule: Ask questions if missing key information
    has_enough_info = _has_sufficient_context(corrected_msg, merged_context, conversation_history)
    
    if not has_enough_info:
        # Ask for more information instead of recommending
        response_text = _generate_preference_questions(
            user_message=corrected_msg,
            context=merged_context,
            user_name=name
        )
        
        # Generate contextual chips based on what's missing
        chips = _generate_context_chips(merged_context)
        
        return ChatResponse(
            reply=response_text,
            recommendations=[],
            follow_up_suggestions=chips,
            confidence=0.5,
        )
    
    # ── Get AI recommendations ────────────────────────────────────────
    logger.info(f"Getting AI recommendations for: {corrected_msg}")
    
    try:
        ai_result = get_ai_recommendations(
            user_query=corrected_msg,
            num_recommendations=req.num_recommendations,
            user_context=merged_context,
            conversation_history=[{"role": m.role, "text": m.text} for m in req.messages]
        )
    except Exception as e:
        logger.error(f"AI recommendation error: {e}")
        return ChatResponse(
            reply=f"I encountered an error processing your request. Please try rephrasing your query.",
            recommendations=[],
            follow_up_suggestions=["Fresh citrus", "Woody oud", "Floral romantic"],
            confidence=0.0,
        )
    
    recommendations = ai_result.get('recommendations', [])
    intent = ai_result.get('intent', {})
    confidence = ai_result.get('confidence', 0.0)
    provider = ai_result.get('provider', 'local')
    
    # ── Generate CONVERSATIONAL response (ChatGPT-like) ──────────────
    # Use conversational AI to generate natural, friendly responses
    reply_text = generate_conversational_response(
        user_message=corrected_msg,
        conversation_history=[{"role": m.role, "text": m.text} for m in req.messages[:-1]],
        user_name=name,
        has_recommendations=len(recommendations) > 0,
        recommendations=recommendations
    )
    
    # Verify text-product alignment if we have recommendations
    if recommendations:
        alignment = verify_text_product_alignment(reply_text, recommendations)
        if not alignment['is_aligned']:
            logger.warning(f"TEXT-CARD MISMATCH: {alignment['missing_products']}")
            # If mismatch, regenerate with template as fallback
            reply_text = generate_recommendation_text(
                recommendations=recommendations,
                user_query=corrected_msg,
                intent=intent,
                user_name=name,
                provider=provider
            )
        else:
            logger.info(f"Text-product alignment verified: {alignment['alignment_rate']:.1%}")
    
    # Add spell correction feedback
    if corrections:
        correction_note = f"*(I understood: {corrected_msg})* \n\n"
        reply_text = correction_note + reply_text
    
    # ── Generate follow-up suggestions ────────────────────────────────
    follow_ups = generate_follow_up_suggestions(
        recommendations=recommendations,
        intent=intent,
        user_context=merged_context
    )
    
    # ── Convert to response format ────────────────────────────────────
    perfume_results = []
    for rec in recommendations:
        try:
            rating = float(rec.get('rating', 4.0) or 4.0)
            match_score = float(rec.get('match_score', rec.get('score', 0.7)))
            
            perfume_results.append(PerfumeResult(
                perfume_id=str(rec.get('id', rec.get('perfume_id', ''))),
                name=str(rec.get('name', 'Unknown')),
                brand=str(rec.get('brand', 'Unknown')),
                family=str(rec.get('accords', ''))[:60] or "Fragrance",
                rating=rating,
                ml_score=match_score,
                rating_score=rating / 5.0,
                popularity_score=min(0.95, match_score + 0.1),
                final_score=match_score,
                description=str(rec.get('description', ''))[:250],
                price_usd=float(rec.get('price', 0) or 0),
                image_url=str(rec.get('image_url', '')) or None,
                gender=str(rec.get('gender', 'unisex')),
                accords=str(rec.get('accords', '')),
                algorithm=rec.get('algorithm', 'ai_primary'),
                ai_reason=rec.get('ai_reason', ''),
            ))
        except Exception as e:
            logger.error(f"Error converting recommendation: {e}")
            continue
    
    # ── Build extracted context ───────────────────────────────────────
    extracted_context = {
        **intent,
        'detected_tone': detect_tone(corrected_msg).tone.value,
        'ai_provider': provider,
        'spell_corrections': corrections if corrections else None,
        'corrected_query': corrected_msg if corrections else None,
    }
    
    return ChatResponse(
        reply=reply_text,
        recommendations=perfume_results,
        extracted_context=extracted_context,
        follow_up_suggestions=follow_ups,
        confidence=confidence,
        ai_provider=provider,
    )


# ── Initialize AI Engine on Startup ───────────────────────────────────

@router.on_event("startup")
async def startup_event():
    """Initialize AI recommendation engine"""
    logger.info("Initializing AI recommendation engine...")
    initialize_ai_engine()
    logger.info("AI recommendation engine ready")
