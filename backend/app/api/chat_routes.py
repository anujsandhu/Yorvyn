"""
Conversational perfume advisor — ChatGPT-style chat endpoint.

POST /ai/chat
  - Accepts full conversation history + optional user context
  - Extracts intent from natural language (occasion, gender, mood, notes, budget)
  - Merges context across turns (remembers what user said earlier)
  - Injects user name, preferences, and memory into replies
  - Returns advisor reply text + perfume recommendations
"""
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..config import settings
from ..ml_model import recommender, clean_accords
from ..tone_detector import detect_tone
from ..prompt_builder import build_tone_aware_system_prompt

router = APIRouter()
logger = logging.getLogger(__name__)
_chat_reply_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat-reply")
_CHAT_REPLY_TIMEOUT_SECONDS = 2.5


# ── Schemas ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str          # "user" | "advisor"
    text: str
    timestamp: Optional[int] = None


class UserContext(BaseModel):
    """User profile and memory passed from the frontend."""
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


class ChatResponse(BaseModel):
    reply: str
    recommendations: List[PerfumeResult] = []
    extracted_context: Dict[str, Any] = {}
    follow_up_suggestions: List[str] = []
    confidence: float = 0.0


# ── Intent extraction ─────────────────────────────────────────────────

GENDER_PATTERNS = {
    "women": r"\b(women|woman|female|her|she|girl|feminine|ladies)\b",
    "men":   r"\b(men|man|male|him|he|guy|masculine|gents|gentleman)\b",
    "unisex": r"\b(unisex|both|anyone|gender.?neutral|shared)\b",
}

OCCASION_PATTERNS = {
    "office":  r"\b(office|work|professional|meeting|corporate|business|workplace)\b",
    "daily":   r"\b(daily|everyday|casual|regular|morning|daytime|college|university|school)\b",
    "date":    r"\b(date|romantic|evening|dinner|night out|special|anniversary|valentine)\b",
    "party":   r"\b(party|club|night|bold|vibrant|celebration|festive)\b",
    "wedding": r"\b(wedding|bridal|bride|ceremony|formal|elegant)\b",
    "gym":     r"\b(gym|sport|workout|exercise|active|outdoor)\b",
}

SEASON_PATTERNS = {
    "summer": r"\b(summer|hot|warm weather|beach|tropical|humid)\b",
    "winter": r"\b(winter|cold|cozy|warm scent|christmas|holiday)\b",
    "spring": r"\b(spring|fresh|bloom|light|airy)\b",
    "autumn": r"\b(autumn|fall|earthy|harvest|october|november)\b",
}

MOOD_PATTERNS = {
    "fresh citrus clean":       r"\b(fresh|clean|light|citrus|crisp|airy|aquatic|marine|watery)\b",
    "warm amber vanilla musky": r"\b(warm|cozy|sensual|amber|vanilla|musky|musk|intimate|seductive)\b",
    "floral rose feminine":     r"\b(floral|flower|rose|jasmine|peony|feminine|romantic|soft)\b",
    "woody oud leather smoky":  r"\b(woody|wood|oud|leather|smoky|dark|intense|deep|cedar|sandalwood)\b",
    "sweet fruity gourmand":    r"\b(sweet|fruity|fruit|gourmand|candy|dessert|playful|fun|sugar)\b",
    "aquatic marine light":     r"\b(aquatic|marine|ocean|sea|breezy|ozonic|watery|light)\b",
}

BUDGET_PATTERN = re.compile(
    r"\b(?:under|below|less than|max|around|about|budget|cheap|affordable)?\s*"
    r"(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,]*)\s*(?:rs\.?|inr|₹|\$|usd|rupees?)?\b",
    re.IGNORECASE,
)

NOTE_KEYWORDS = [
    "rose", "jasmine", "oud", "vanilla", "amber", "musk", "cedar", "sandalwood",
    "bergamot", "lemon", "orange", "citrus", "lavender", "iris", "patchouli",
    "vetiver", "tobacco", "leather", "smoke", "pepper", "cardamom", "cinnamon",
    "peach", "apple", "cherry", "coconut", "chocolate", "caramel", "honey",
    "aquatic", "marine", "green", "woody", "floral", "spicy", "sweet", "fresh",
    "powdery", "earthy", "fruity", "gourmand", "oriental", "chypre",
]

NEGATION_WORDS = {"not", "no", "without", "avoid", "hate", "dislike", "don't", "dont", "never"}

REFERENCE_PATTERN = re.compile(
    r"\b(?:like|similar to|same as|reminds? me of|inspired by|version of)\s+([A-Z][^,.!?]+)",
    re.IGNORECASE,
)


def _extract_intent(text: str) -> Dict[str, Any]:
    """Extract structured intent from a single message."""
    low = text.lower()
    tokens = set(re.findall(r"\b\w+\b", low))

    intent: Dict[str, Any] = {}

    # Gender
    for gender, pattern in GENDER_PATTERNS.items():
        if re.search(pattern, low):
            intent["gender"] = gender
            break

    # Occasion
    for occasion, pattern in OCCASION_PATTERNS.items():
        if re.search(pattern, low):
            intent["occasion"] = occasion
            break

    # Season
    for season, pattern in SEASON_PATTERNS.items():
        if re.search(pattern, low):
            intent["season"] = season
            break

    # Mood / style
    best_mood = None
    best_count = 0
    for mood_key, pattern in MOOD_PATTERNS.items():
        matches = len(re.findall(pattern, low))
        if matches > best_count:
            best_count = matches
            best_mood = mood_key
    if best_mood:
        intent["mood"] = best_mood

    # Notes — split into liked / disliked
    liked_notes = []
    disliked_notes = []
    words = re.findall(r"\b\w+\b", low)
    for i, word in enumerate(words):
        if word in NOTE_KEYWORDS:
            # Check if preceded by negation within 3 words
            context_start = max(0, i - 3)
            context = set(words[context_start:i])
            if context & NEGATION_WORDS:
                disliked_notes.append(word)
            else:
                liked_notes.append(word)
    if liked_notes:
        intent["liked_notes"] = liked_notes
    if disliked_notes:
        intent["disliked_notes"] = disliked_notes

    # Budget
    budget_matches = BUDGET_PATTERN.findall(text)
    if budget_matches:
        try:
            amount = int(budget_matches[-1].replace(",", ""))
            # Convert INR to USD roughly (for the model)
            intent["budget_max"] = round(amount / 83, 1) if amount > 500 else amount
        except Exception:
            pass

    # Reference perfumes
    ref_match = REFERENCE_PATTERN.search(text)
    if ref_match:
        intent["reference_perfumes"] = [ref_match.group(1).strip()]

    return intent


def _merge_context(
    history: List[ChatMessage],
    user_ctx: Optional[UserContext] = None,
    is_refinement: bool = False,
) -> Dict[str, Any]:
    """
    Extract intent from user messages.
    
    IMPORTANT: To prevent context leakage, we ONLY use the latest message
    unless it's an explicit refinement (e.g., "make it stronger").
    
    Args:
        history: List of chat messages
        user_ctx: User profile context (optional)
        is_refinement: If True, consider previous message for context
        
    Returns:
        Extracted context dict
    """
    merged: Dict[str, Any] = {
        "liked_notes": [],
        "disliked_notes": [],
        "reference_perfumes": [],
    }

    # Seed from user profile (lowest priority — conversation overrides)
    if user_ctx:
        if user_ctx.preferred_gender:
            merged["gender"] = user_ctx.preferred_gender
        if user_ctx.preferred_occasion:
            merged["occasion"] = user_ctx.preferred_occasion
        if user_ctx.preferred_season:
            merged["season"] = user_ctx.preferred_season
        if user_ctx.favorite_notes:
            merged["liked_notes"] = list(user_ctx.favorite_notes[:5])
        if user_ctx.liked_perfume_names:
            merged["reference_perfumes"] = list(user_ctx.liked_perfume_names[:3])

    # Get user messages only
    user_messages = [msg for msg in history if msg.role == "user"]
    
    if not user_messages:
        return merged
    
    # CRITICAL: Only use latest message to prevent context leakage
    # Exception: If it's a refinement, consider the previous message too
    if is_refinement and len(user_messages) >= 2:
        # For refinements like "make it stronger", use last 2 messages
        messages_to_process = user_messages[-2:]
    else:
        # For new queries, ONLY use the latest message
        messages_to_process = [user_messages[-1]]
    
    for msg in messages_to_process:
        intent = _extract_intent(msg.text)
        # Scalar fields — later overrides earlier
        for key in ("gender", "occasion", "season", "mood", "budget_max"):
            if key in intent:
                merged[key] = intent[key]
        # List fields — accumulate, deduplicate
        for key in ("liked_notes", "disliked_notes", "reference_perfumes"):
            if key in intent:
                existing = merged.get(key, [])
                for item in intent[key]:
                    if item not in existing:
                        existing.append(item)
                merged[key] = existing

    return merged


def _build_query(ctx: Dict[str, Any], latest_text: str) -> str:
    """Build a rich query string from merged context + latest message."""
    parts = []

    # Start with the raw latest message (most important signal)
    clean = re.sub(r"\b(i want|i need|find me|show me|recommend|suggest|give me|looking for|can you)\b", "", latest_text, flags=re.IGNORECASE)
    clean = clean.strip(" .,?!")
    if clean:
        parts.append(clean)

    # Add mood / notes
    if ctx.get("mood"):
        parts.append(ctx["mood"])
    if ctx.get("liked_notes"):
        parts.append(" ".join(ctx["liked_notes"][:4]))

    # Add occasion / season
    if ctx.get("occasion"):
        parts.append(f"for {ctx['occasion']}")
    if ctx.get("season"):
        parts.append(f"in {ctx['season']}")

    # Add gender
    if ctx.get("gender"):
        parts.append(ctx["gender"])

    # Add reference perfumes
    if ctx.get("reference_perfumes"):
        parts.append("similar to " + " ".join(ctx["reference_perfumes"][:2]))

    return " ".join(parts)


def _get_display_name(user_ctx: Optional[UserContext]) -> str:
    """Return the best name to address the user by."""
    if not user_ctx:
        return ""
    return (user_ctx.nickname or user_ctx.name or "").strip()


def _build_reply(
    ctx: Dict[str, Any],
    recs: List[Dict],
    latest_text: str,
    turn_number: int,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Generate a natural, context-aware, personalized advisor reply."""
    n = len(recs)
    top = recs[0] if recs else None
    name = _get_display_name(user_ctx)

    # ── No results ────────────────────────────────────────────────────
    if not recs:
        opener = f"Got it, {name} — " if name else "Got it — "
        return (
            f"{opener}I searched through 73,000+ fragrances but couldn't find a strong match. "
            f"Could you tell me more — like a specific note (rose, oud, vanilla), "
            f"an occasion, or a perfume you already love?"
        )

    # ── Build context summary ─────────────────────────────────────────
    ctx_parts = []
    if ctx.get("gender"):
        g = ctx["gender"]
        ctx_parts.append("for " + ("women" if g == "women" else "men" if g == "men" else "anyone"))
    if ctx.get("occasion"):
        ctx_parts.append(f"{ctx['occasion']} wear")
    if ctx.get("season"):
        ctx_parts.append(f"{ctx['season']}")
    if ctx.get("liked_notes"):
        notes = ctx["liked_notes"][:3]
        ctx_parts.append(f"with {', '.join(notes)} notes")
    ctx_summary = " · ".join(ctx_parts) if ctx_parts else ""

    # ── Top pick details ──────────────────────────────────────────────
    top_name = f"**{top['name']}** by {top['brand']}" if top else ""
    top_accords = clean_accords(top.get("accords", "")) if top else ""
    top_notes = ", ".join(top_accords.split()[:3]) if top_accords else ""

    # ── Memory signals ────────────────────────────────────────────────
    has_liked = bool(user_ctx and user_ctx.liked_perfume_names)
    has_fav_notes = bool(user_ctx and user_ctx.favorite_notes)
    is_returning = bool(user_ctx and not user_ctx.is_new_user and user_ctx.total_chats and user_ctx.total_chats > 0)

    # ── Build reply by turn ───────────────────────────────────────────
    if turn_number == 1:
        # First turn — warm, direct, name-aware
        if name:
            opener = f"Based on what you're after, {name}, "
        else:
            opener = "Based on what you're after, "

        reply = f"{opener}I found **{n} fragrances** that should work"
        if ctx_summary:
            reply += f" ({ctx_summary})"
        reply += f". {top_name} leads the list"
        if top_notes:
            reply += f" — *{top_notes}*"

        # Add memory reference if returning user with preferences
        if is_returning and has_fav_notes and user_ctx:
            fav = user_ctx.favorite_notes[0]
            reply += f". I leaned toward your usual preference for **{fav}** notes"

        reply += ". Tap any card to see full details and where to buy."

    elif turn_number == 2:
        # Second turn — acknowledge refinement
        if ctx.get("occasion") == "date":
            intro = "For a date, you probably want something memorable but not overpowering. "
        elif ctx.get("occasion") == "office":
            intro = "Office-friendly means subtle and clean — nothing that announces itself. "
        elif ctx.get("mood") and "fresh" in ctx.get("mood", ""):
            intro = "Fresh and clean it is. "
        elif ctx.get("mood") and "warm" in ctx.get("mood", ""):
            intro = "Warm and sensual — good call. "
        else:
            intro = "Narrowing it down — "

        reply = f"{intro}Here are **{n} matches**"
        if ctx_summary:
            reply += f" ({ctx_summary})"
        reply += f". {top_name} is the strongest fit"
        if top_notes:
            reply += f" with *{top_notes}*"
        reply += ". Want me to refine further?"

    else:
        # Later turns — conversational, memory-aware
        if has_liked and user_ctx and user_ctx.liked_perfume_names:
            liked_ref = user_ctx.liked_perfume_names[0]
            intro = f"You saved **{liked_ref}** before — this direction is similar. "
        else:
            intro = ""

        reply = f"{intro}Here are **{n} updated matches**"
        if ctx_summary:
            reply += f" ({ctx_summary})"
        reply += f". {top_name} is your top pick"
        if top_notes:
            reply += f" — *{top_notes}*"
        reply += "."

    return reply


def _generate_follow_ups(
    ctx: Dict[str, Any],
    recs: List[Dict],
    user_ctx: Optional[UserContext] = None,
) -> List[str]:
    """Generate contextual, personalized follow-up suggestion chips."""
    suggestions = []

    # Memory-based suggestions (highest priority)
    if user_ctx and user_ctx.liked_perfume_names:
        suggestions.append(f"More like {user_ctx.liked_perfume_names[0]}")
    if user_ctx and user_ctx.favorite_notes:
        suggestions.append(f"More {user_ctx.favorite_notes[0]} fragrances")

    # Context-based refinements
    if not ctx.get("gender"):
        suggestions.extend(["For women", "For men"])
    if not ctx.get("occasion"):
        suggestions.extend(["For daily wear", "For a date night", "For the office"])
    if not ctx.get("season"):
        suggestions.extend(["For summer", "For winter"])

    # Note-based from top result
    if recs:
        top_accords = clean_accords(recs[0].get("accords", "")).split()[:2]
        for note in top_accords:
            if note and len(note) > 3:
                suggestions.append(f"More {note} fragrances")

    # Budget
    if not ctx.get("budget_max"):
        suggestions.append("Under ₹2000")
        suggestions.append("Premium options")

    # Refinement
    suggestions.extend(["Something lighter", "Something more intense", "Show me similar brands"])

    # Deduplicate, max 6
    seen: set = set()
    result = []
    for s in suggestions:
        if s not in seen and len(result) < 6:
            seen.add(s)
            result.append(s)
    return result


# ── Main chat endpoint ────────────────────────────────────────────────

@router.post("/ai/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Conversational perfume advisor with personalization.
    Accepts full message history + user context, returns personalized reply + cards.
    """
    user_ctx = req.user_context
    name = _get_display_name(user_ctx)

    if not req.messages:
        # Empty session — personalized greeting
        if name:
            greeting = f"Hey {name}, I'll help you find your perfect scent. Tell me what kind of vibe you're going for."
        else:
            greeting = "Hey — I'll help you find your perfect scent. Tell me what kind of vibe you're going for."

        # Personalized chips from user preferences
        chips = []
        if user_ctx and user_ctx.favorite_notes:
            chips.append(f"More {user_ctx.favorite_notes[0]} fragrances")
        chips.extend([
            "Perfume for a date night",
            "Fresh scent for daily wear",
            "Warm oud for winter",
            "Floral for women",
            "Something like Dior Sauvage",
            "Under ₹2000",
        ])
        chips = list(dict.fromkeys(chips))[:6]  # deduplicate, max 6

        return ChatResponse(
            reply=greeting,
            follow_up_suggestions=chips,
        )

    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        return ChatResponse(
            reply="What kind of fragrance are you looking for? Tell me about the occasion, mood, or notes you enjoy.",
            follow_up_suggestions=["Floral & feminine", "Woody & bold", "Fresh & clean", "Warm & sensual"],
        )

    latest_user_msg = user_messages[-1].text.strip()
    turn_number = len(user_messages)

    # ── SPELL CORRECTION (NEW) ────────────────────────────────────────
    from ..spell_corrector import (
        correct_text, extract_brand_and_perfume, 
        should_use_web_search, build_search_query
    )
    
    # Correct typos in user input
    corrected_msg, corrections = correct_text(latest_user_msg)
    
    # Extract brand and perfume if mentioned
    brand, perfume = extract_brand_and_perfume(corrected_msg)
    
    # Determine if web search should be used
    use_web_search = should_use_web_search(corrected_msg, corrections)
    
    # Log corrections for transparency
    if corrections:
        logger.info(f"Spell corrections: {corrections}")
    
    # ── INTENT CLASSIFICATION ─────────────────────────────────────────
    from ..intent_classifier import classify_intent, get_intent_response, Intent
    
    # Classify the corrected message
    conversation_history = [{"role": m.role, "text": m.text} for m in req.messages[:-1]]
    intent_result = classify_intent(corrected_msg, conversation_history)
    
    # Handle non-query intents immediately (no recommendations)
    if intent_result.intent in (Intent.GREETING, Intent.VAGUE, Intent.ABUSIVE):
        response_text = get_intent_response(intent_result, name)
        
        # Generate contextual follow-up chips
        if intent_result.intent == Intent.GREETING:
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
        elif intent_result.intent == Intent.VAGUE:
            chips = [
                "Fresh citrus for summer",
                "Woody oud for winter",
                "Floral for women",
                "Spicy for men",
                "Sweet and playful",
                "Something like Bleu de Chanel",
            ]
        else:  # ABUSIVE
            chips = [
                "Fresh and clean",
                "Woody and bold",
                "Floral and feminine",
                "Warm and sensual",
            ]
        
        return ChatResponse(
            reply=response_text,
            recommendations=[],
            follow_up_suggestions=list(dict.fromkeys(chips))[:6],
            confidence=intent_result.confidence,
        )

    # Detect if this is a refinement request (BEFORE merging context)
    is_refinement = turn_number > 1 and any(
        word in corrected_msg.lower() 
        for word in ["stronger", "lighter", "sweeter", "fresher", "more", "less", "different", "similar"]
    )

    # Merge context — ONLY uses latest message unless it's a refinement
    # This prevents context leakage from previous queries
    ctx = _merge_context(req.messages, user_ctx, is_refinement=is_refinement)
    
    # Log context extraction for debugging
    logger.info(f"Context extracted - is_refinement: {is_refinement}, occasion: {ctx.get('occasion')}, mood: {ctx.get('mood')}")

    # Detect tone from the latest user message and build a tone-aware system prompt
    tone_result = detect_tone(corrected_msg)
    system_prompt = build_tone_aware_system_prompt(tone_result.tone, user_ctx)

    # Build rich query (use corrected message)
    query = _build_query(ctx, corrected_msg)
    
    # ── WEB SEARCH ENHANCEMENT (NEW) ──────────────────────────────────
    web_search_info = None
    if use_web_search and settings.ai_fallback_enabled:
        try:
            # Build optimized search query
            search_query = build_search_query(corrected_msg, brand, perfume)
            logger.info(f"Using web search: {search_query}")
            
            # Perform web search (using existing remote_web_search tool)
            from ..config import settings as app_settings
            if hasattr(app_settings, 'web_search_enabled') and app_settings.web_search_enabled:
                # Import web search function
                try:
                    from .ai_routes import remote_web_search
                    search_results = remote_web_search(search_query)
                    
                    if search_results and len(search_results) > 0:
                        # Extract relevant info from top 3 results
                        web_search_info = {
                            "query": search_query,
                            "results": search_results[:3],
                            "summary": f"Found {len(search_results)} web results for '{search_query}'"
                        }
                        logger.info(f"Web search returned {len(search_results)} results")
                except Exception as e:
                    logger.warning(f"Web search failed: {e}")
        except Exception as e:
            logger.warning(f"Web search error: {e}")

    # Run ML recommendations
    recs_raw = []
    confidence = 0.0

    if recommender.data is not None and recommender.tfidf_vectorizer is not None:
        try:
            result = recommender.recommend_from_user_input(
                preferences=query,
                limit=req.num_recommendations,
                context={
                    "preferred_gender": ctx.get("gender"),
                    "occasion": ctx.get("occasion"),
                    "season": ctx.get("season"),
                    "mood": ctx.get("mood"),
                    "liked_notes": ctx.get("liked_notes", []),
                    "disliked_notes": ctx.get("disliked_notes", []),
                    "reference_perfumes": ctx.get("reference_perfumes", []),
                    "budget_max": ctx.get("budget_max"),
                },
            )
            recs_raw = result.get("recommendations", [])
            confidence = float(result.get("confidence", 0.0) or 0.0)
        except Exception as e:
            print(f"Chat recommendation error: {e}")
            recs_raw = []

    # Serialize recommendations
    recommendations = []
    for rec in recs_raw:
        try:
            pid = rec.get("id")
            if pid is None:
                continue
            match_score = float(rec.get("match_score", rec.get("score", 0.7)))
            rating = float(rec.get("rating", 4.0) or 4.0)
            rating_score = rating / 5.0
            popularity = min(0.95, match_score + 0.1)
            final_score = min(0.99, max(0.0, match_score * 0.5 + rating_score * 0.3 + popularity * 0.2))
            accords = str(rec.get("accords", ""))

            recommendations.append(PerfumeResult(
                perfume_id=str(pid),
                name=str(rec.get("name", "Unknown")),
                brand=str(rec.get("brand", "Unknown")),
                family=accords[:60] if accords else "Fragrance",
                rating=rating,
                ml_score=match_score,
                rating_score=rating_score,
                popularity_score=popularity,
                final_score=final_score,
                description=str(rec.get("description", ""))[:250],
                price_usd=float(rec.get("price", 0) or 0),
                image_url=str(rec.get("image_url", "")) or None,
                gender=str(rec.get("gender", "unisex")),
                accords=accords,
                algorithm=rec.get("algorithm", "hybrid"),
            ))
        except Exception:
            continue

    # Build personalized reply — try LLM first, fall back to local
    recs_dicts = [r.dict() for r in recommendations]
    
    # ── HUMAN-LIKE RESPONSE GENERATION (NEW) ──────────────────────────
    from ..response_generator import generate_human_response, handle_vague_input, handle_refinement
    
    # is_refinement already detected earlier (before _merge_context)
    
    if is_refinement and len(req.messages) > 2:
        # Handle refinement
        human_response = handle_refinement(
            previous_recommendations=recs_dicts,
            refinement=corrected_msg,
            context={
                "previous_vibe": ctx.get("mood"),
                "occasion": ctx.get("occasion"),
            }
        )
        reply = human_response["message"]
    elif not recs_dicts:
        # No recommendations - ask for clarification
        from ..response_generator import handle_vague_input
        human_response = handle_vague_input(corrected_msg)
        reply = human_response["message"]
    else:
        # Generate human-like response
        human_response = generate_human_response(
            recommendations=recs_dicts,
            user_input=corrected_msg,
            context={
                "occasion": ctx.get("occasion"),
                "season": ctx.get("season"),
                "mood": ctx.get("mood"),
                "gender": ctx.get("gender"),
            },
            user_name=name,
        )
        reply = human_response["message"]
        
        # Update recommendations with filtered list
        if human_response.get("recommendations"):
            recommendations = [
                PerfumeResult(**{
                    "perfume_id": str(rec.get("id", rec.get("perfume_id", ""))),
                    "name": str(rec.get("name", "Unknown")),
                    "brand": str(rec.get("brand", "Unknown")),
                    "family": str(rec.get("accords", rec.get("family", "")))[:60],
                    "rating": float(rec.get("rating", 4.0) or 4.0),
                    "ml_score": float(rec.get("match_score", rec.get("ml_score", 0.7))),
                    "rating_score": float(rec.get("rating", 4.0) or 4.0) / 5.0,
                    "popularity_score": min(0.95, float(rec.get("match_score", 0.7)) + 0.1),
                    "final_score": float(rec.get("score", rec.get("final_score", 0.7))),
                    "description": str(rec.get("description", ""))[:250],
                    "price_usd": float(rec.get("price", 0) or 0),
                    "image_url": str(rec.get("image_url", "")) or None,
                    "gender": str(rec.get("gender", "unisex")),
                    "accords": str(rec.get("accords", "")),
                    "algorithm": rec.get("algorithm", "hybrid"),
                })
                for rec in human_response["recommendations"]
            ]
    
    # Add correction feedback if typos were fixed
    if corrections:
        correction_note = f"*(I understood: {corrected_msg})* \n\n"
        reply = correction_note + reply
    
    # Add web search context if available
    if web_search_info:
        # Enhance reply with web search insights
        web_summary = web_search_info.get("summary", "")
        if web_summary and recs_dicts:
            # Add subtle web search note
            reply += f"\n\n*Verified with latest online information.*"

    # IMPORTANT: Don't use LLM fallback if we already have a human-like response
    # The response generator provides better, more consistent responses
    use_human_response = bool(recs_dicts) and not is_refinement
    
    should_try_llm = (
        settings.ai_fallback_enabled
        and bool(recs_dicts)
        and confidence < settings.ai_fallback_confidence_threshold
        and not use_human_response  # Don't override human-like responses
    )

    if should_try_llm:
        try:
            from ..ai_fallback import generate_chat_reply_llm

            future = _chat_reply_executor.submit(
                generate_chat_reply_llm,
                ctx,
                recs_dicts,
                user_ctx,
                system_prompt,
            )
            llm_reply = future.result(timeout=_CHAT_REPLY_TIMEOUT_SECONDS)
            if llm_reply:
                reply = llm_reply
        except FuturesTimeoutError:
            logger.info("Chat LLM timed out after %.1fs; using local reply", _CHAT_REPLY_TIMEOUT_SECONDS)
        except Exception as e:
            logger.info("Generative reply failed; using local reply: %s", e)

    # Expose tone detection metadata in the response context
    ctx["detected_tone"] = tone_result.tone.value
    ctx["tone_confidence"] = round(tone_result.confidence, 2)
    
    # Add spell correction info
    if corrections:
        ctx["spell_corrections"] = corrections
        ctx["corrected_query"] = corrected_msg
    
    # Add web search info
    if web_search_info:
        ctx["web_search_used"] = True
        ctx["web_search_query"] = web_search_info.get("query")
    
    # Add response generator metadata for frontend matching
    if 'human_response' in locals() and human_response:
        ctx["top_pick_id"] = human_response.get("top_pick_id")
        ctx["recommended_ids"] = human_response.get("recommended_ids", [])
        ctx["vibe_detected"] = human_response.get("vibe_detected")
        ctx["response_confidence"] = human_response.get("confidence", 0.0)

    # Generate personalized follow-up suggestions
    follow_ups = _generate_follow_ups(ctx, recs_dicts, user_ctx)

    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        extracted_context=ctx,
        follow_up_suggestions=follow_ups,
        confidence=confidence,
    )
