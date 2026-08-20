"""
AI-Powered Recommendation Engine

This module makes AI the PRIMARY decision engine for perfume recommendations.
Flow: User Input → AI interprets → AI selects from dataset → Backend validates → UI displays

Architecture:
1. AI receives user query + full dataset context
2. AI returns structured JSON with product IDs + reasoning
3. Backend validates IDs against database
4. Backend ranks and filters results
5. AI generates final explanation text

Key Features:
- AI-first decision making (not just text generation)
- Strict product ID validation (no invented perfumes)
- Semantic similarity using embeddings
- Confidence scoring and fallback logic
- Caching for performance
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .config import settings
from .ml_model import recommender, clean_accords, normalize_text

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────

@dataclass
class AIRecommendationRequest:
    """Structured request for AI recommendation"""
    user_query: str
    user_context: Optional[Dict[str, Any]] = None
    num_recommendations: int = 6
    conversation_history: Optional[List[Dict[str, str]]] = None


@dataclass
class AIRecommendationResponse:
    """Structured response from AI"""
    intent: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    confidence: float
    reasoning: str
    provider: str  # "gemini" | "openai" | "local"


@dataclass
class ValidatedRecommendation:
    """Validated and enriched recommendation"""
    perfume_id: str
    name: str
    brand: str
    rating: float
    accords: str
    image_url: str
    price_usd: float
    gender: str
    description: str
    match_score: float
    ai_reason: str
    algorithm: str = "ai_primary"


# ── Semantic Search with Embeddings ───────────────────────────────────

class SemanticSearchEngine:
    """
    Pre-filters dataset using semantic similarity before sending to AI.
    This reduces token usage and improves AI accuracy.
    """
    
    def __init__(self):
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        self.dataset_embeddings: Optional[np.ndarray] = None
        self.dataset_texts: List[str] = []
        self.dataset_ids: List[int] = []
        
    def initialize(self, data: pd.DataFrame):
        """Build semantic search index from dataset"""
        if data is None or len(data) == 0:
            return
            
        logger.info("Building semantic search index...")
        start = time.time()
        
        # Create rich text representations
        self.dataset_texts = []
        self.dataset_ids = []
        
        for idx, row in data.iterrows():
            text = self._build_search_text(row)
            self.dataset_texts.append(text)
            self.dataset_ids.append(int(row.get('id', idx)))
        
        # Use TF-IDF as lightweight embeddings (can upgrade to sentence transformers later)
        if recommender.tfidf_vectorizer and recommender.tfidf_matrix is not None:
            self.dataset_embeddings = recommender.tfidf_matrix.toarray().astype(np.float32)
            logger.info(f"Semantic index built in {time.time() - start:.2f}s")
        
    def _build_search_text(self, row: pd.Series) -> str:
        """Build rich searchable text from perfume data"""
        parts = [
            str(row.get('name', '')),
            str(row.get('brand', '')),
            clean_accords(row.get('accords', '')),
            str(row.get('gender', '')),
            str(row.get('description', ''))[:200],
        ]
        return ' '.join(p for p in parts if p).strip()
    
    def search(self, query: str, top_k: int = 50) -> List[Tuple[int, float]]:
        """
        Find top-k most relevant perfumes using semantic similarity.
        Returns list of (perfume_id, similarity_score) tuples.
        """
        if self.dataset_embeddings is None or not recommender.tfidf_vectorizer:
            return []
        
        try:
            # Vectorize query
            query_vector = recommender.tfidf_vectorizer.transform([query])
            query_dense = query_vector.toarray().astype(np.float32)[0]
            
            # Compute cosine similarity
            similarities = np.dot(self.dataset_embeddings, query_dense)
            norms = np.linalg.norm(self.dataset_embeddings, axis=1) * np.linalg.norm(query_dense)
            similarities = similarities / (norms + 1e-8)
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if idx < len(self.dataset_ids):
                    perfume_id = self.dataset_ids[idx]
                    score = float(similarities[idx])
                    if score > 0.1:  # Minimum relevance threshold
                        results.append((perfume_id, score))
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []


# Global semantic search engine
semantic_engine = SemanticSearchEngine()


# ── AI Recommendation Engine ──────────────────────────────────────────

class AIRecommendationEngine:
    """
    Primary AI-driven recommendation engine.
    Uses LLM to interpret intent and select products from dataset.
    Always calls AI API fresh - no caching.
    """
    
    def __init__(self):
        # No caching - always fresh AI calls
        pass
        
    def recommend(self, request: AIRecommendationRequest) -> AIRecommendationResponse:
        """
        Main recommendation flow:
        1. Pre-filter with semantic search
        2. Send to AI with dataset context
        3. Parse and validate AI response
        4. Return structured recommendations
        
        NO CACHING - Always calls AI API fresh
        """
        # Pre-filter with semantic search
        candidate_ids = self._get_candidate_perfumes(request)
        
        if not candidate_ids:
            logger.warning("No candidates found via semantic search")
            return self._fallback_response(request)
        
        # Try AI providers in order: Gemini → OpenAI → Local
        response = None
        
        if settings.ai_fallback_enabled:
            # Try Gemini first
            response = self._try_gemini(request, candidate_ids)
            
            # Fallback to OpenAI if Gemini fails
            if not response:
                response = self._try_openai(request, candidate_ids)
        
        # Fallback to local if AI fails
        if not response:
            response = self._local_fallback(request, candidate_ids)
        
        # NO CACHING - Return fresh response every time
        logger.info(f"Fresh AI response from {response.provider}")
        
        return response
    
    def _get_candidate_perfumes(self, request: AIRecommendationRequest) -> List[int]:
        """
        Pre-filter dataset using semantic search with STRICT filtering.
        Returns list of candidate perfume IDs that pass all filters.
        """
        # Build rich query from user input + context
        query_parts = [request.user_query]
        
        if request.user_context:
            ctx = request.user_context
            if ctx.get('mood'):
                query_parts.append(ctx['mood'])
            if ctx.get('occasion'):
                query_parts.append(f"for {ctx['occasion']}")
            if ctx.get('season'):
                query_parts.append(f"in {ctx['season']}")
            if ctx.get('liked_notes'):
                query_parts.extend(ctx['liked_notes'][:5])
        
        query = ' '.join(query_parts)
        
        # Get top candidates (3-5x the requested amount)
        top_k = min(200, request.num_recommendations * 10)
        results = semantic_engine.search(query, top_k=top_k)
        
        candidate_ids = [perfume_id for perfume_id, _ in results]
        
        # STRICT FILTERING: Apply all filters before sending to AI
        filtered_ids = self._apply_strict_filters(candidate_ids, request)
        
        logger.info(f"Strict filtering: {len(candidate_ids)} → {len(filtered_ids)} candidates")
        
        return filtered_ids
    
    def _apply_strict_filters(
        self,
        candidate_ids: List[int],
        request: AIRecommendationRequest
    ) -> List[int]:
        """
        Apply STRICT filters to remove:
        1. Samples, testers, oils, mists (Bug #4, #6)
        2. Low-quality products (Bug #4)
        3. Budget violations (Bug #2)
        4. Contextually inappropriate products (Bug #7)
        """
        if not candidate_ids:
            return []
        
        # Get full product data
        candidates = []
        for pid in candidate_ids:
            idx = recommender._resolve_index(pid)
            if idx is not None:
                product = recommender._safe_row(idx)
                candidates.append(product)
        
        # Filter 1: Remove samples, testers, oils, mists
        candidates = self._filter_product_type(candidates)
        
        # Filter 2: Remove low-quality products
        candidates = self._filter_quality(candidates, request)
        
        # Filter 3: Apply budget constraints
        candidates = self._filter_budget(candidates, request)
        
        # Filter 4: Apply gender filtering
        candidates = self._filter_gender(candidates, request)
        
        # Filter 5: Remove contextually inappropriate products
        candidates = self._filter_context(candidates, request)
        
        return [int(p['id']) for p in candidates]
    
    def _filter_product_type(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove samples, testers, oils, mists, body sprays."""
        noise_keywords = {
            'sample', 'samples', 'sampler', 'vial', 'vials', 'decant', 'mini', 'minis',
            'tester', 'testers', 'gift set', 'variety pack', 'discovery set',
            'oil', 'oils', 'mist', 'mists', 'body spray', 'lotion', 'room spray'
        }
        
        filtered = []
        for product in candidates:
            name = product.get('name', '').lower()
            has_noise = any(keyword in name for keyword in noise_keywords)
            
            if not has_noise:
                filtered.append(product)
        
        return filtered
    
    def _filter_quality(
        self,
        candidates: List[Dict[str, Any]],
        request: AIRecommendationRequest
    ) -> List[Dict[str, Any]]:
        """Remove low-quality products based on rating."""
        ctx = request.user_context or {}
        is_broad_query = not ctx.get('liked_notes') and not ctx.get('reference_perfumes')
        
        # Very relaxed thresholds to get more recommendations
        # Most perfumes in dataset have few reviews, so we need to be lenient
        min_rating = 2.5  # Accept anything above 2.5 stars
        min_rating_count = 0  # No minimum review count requirement
        
        filtered = []
        for product in candidates:
            rating = float(product.get('rating', 0))
            rating_count = int(product.get('rating_count', 0))
            
            # Accept if rating >= 2.5 OR if no rating data (rating = 0)
            if rating == 0 or rating >= min_rating:
                filtered.append(product)
        
        return filtered
    
    def _filter_budget(
        self,
        candidates: List[Dict[str, Any]],
        request: AIRecommendationRequest
    ) -> List[Dict[str, Any]]:
        """Apply strict budget filtering."""
        ctx = request.user_context or {}
        budget_max = ctx.get('budget_max')
        
        # If no budget specified, return all candidates
        if budget_max is None:
            return candidates
        
        try:
            budget_max = float(budget_max)
        except (TypeError, ValueError):
            return candidates
        
        filtered = []
        for product in candidates:
            price = float(product.get('price', 0))
            # Include products with price=0 (no price data) OR within budget
            if price == 0 or price <= budget_max:
                filtered.append(product)
        
        return filtered
    
    def _filter_gender(
        self,
        candidates: List[Dict[str, Any]],
        request: AIRecommendationRequest
    ) -> List[Dict[str, Any]]:
        """Apply strict gender filtering."""
        ctx = request.user_context or {}
        requested_gender = ctx.get('gender', '').lower()
        
        # If no gender specified, return all
        if not requested_gender:
            return candidates
        
        filtered = []
        for product in candidates:
            product_gender = product.get('gender', '').lower()
            
            # Match logic:
            # - If requested "men", accept "men" or "unisex"
            # - If requested "women", accept "women" or "unisex"
            # - Unisex perfumes work for everyone
            
            if requested_gender == 'men':
                if product_gender in ['men', 'unisex']:
                    filtered.append(product)
            elif requested_gender == 'women':
                if product_gender in ['women', 'unisex']:
                    filtered.append(product)
            else:
                # If requested gender is something else, include all
                filtered.append(product)
        
        return filtered
    
    def _filter_context(
        self,
        candidates: List[Dict[str, Any]],
        request: AIRecommendationRequest
    ) -> List[Dict[str, Any]]:
        """Remove products with opposite notes/vibes."""
        ctx = request.user_context or {}
        mood = ctx.get('mood', '').lower()
        season = ctx.get('season', '').lower()
        
        opposite_notes = {
            'fresh': {'oud', 'amber', 'heavy', 'intense', 'warm'},
            'citrus': {'oud', 'amber', 'heavy', 'woody'},
            'light': {'oud', 'amber', 'heavy', 'intense'},
        }
        
        season_inappropriate = {
            'summer': {'oud', 'amber', 'heavy', 'warm', 'intense'},
        }
        
        if not mood and not season:
            return candidates
        
        filtered = []
        for product in candidates:
            accords = product.get('accords', '').lower()
            
            # Check mood opposites
            if mood and mood in opposite_notes:
                has_opposite = any(opp in accords for opp in opposite_notes[mood])
                if has_opposite:
                    continue
            
            # Check season inappropriateness
            if season and season in season_inappropriate:
                has_inappropriate = any(inapp in accords for inapp in season_inappropriate[season])
                if has_inappropriate:
                    continue
            
            filtered.append(product)
        
        return filtered
    
    def _try_gemini(
        self,
        request: AIRecommendationRequest,
        candidate_ids: List[int]
    ) -> Optional[AIRecommendationResponse]:
        """Try Gemini API for recommendations - NO TOKEN LIMITS"""
        try:
            import google.generativeai as genai
            
            if not settings.effective_google_key:
                return None
            
            genai.configure(api_key=settings.effective_google_key)
            model = genai.GenerativeModel(settings.gemini_model)
            
            # Build prompt with dataset context
            prompt = self._build_ai_prompt(request, candidate_ids)
            
            # Call Gemini with generous token limit
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=1500,
                temperature=0.3,
            )
            
            response = model.generate_content(prompt, generation_config=generation_config)
            
            # Parse response
            return self._parse_ai_response(response.text, "gemini")
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def _try_openai(
        self,
        request: AIRecommendationRequest,
        candidate_ids: List[int]
    ) -> Optional[AIRecommendationResponse]:
        """Try OpenAI API for recommendations - NO TOKEN LIMITS"""
        try:
            import openai
            
            if not settings.openai_api_key:
                return None
            
            openai.api_key = settings.openai_api_key
            
            # Build prompt
            prompt = self._build_ai_prompt(request, candidate_ids)
            
            # Call OpenAI with generous token limit
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a perfume recommendation expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,  # Full responses, no conservation
            )
            
            # Parse response
            return self._parse_ai_response(response.choices[0].message.content, "openai")
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None
    
    def _build_ai_prompt(
        self,
        request: AIRecommendationRequest,
        candidate_ids: List[int]
    ) -> str:
        """
        Build structured prompt for AI with dataset context.
        
        CRITICAL: AI must ONLY select from provided IDs, never invent perfumes.
        """
        # Get candidate perfume data
        candidates = self._get_perfume_data(candidate_ids[:50])  # Limit to top 50 for token efficiency
        
        # Build dataset context
        dataset_context = self._build_dataset_context(candidates)
        
        # Build user context
        user_context = self._build_user_context(request)
        
        prompt = f"""You are a perfume recommendation expert. Your task is to select the BEST perfumes from the provided dataset that match the user's request.

**CRITICAL RULES:**
1. You MUST ONLY select perfumes from the provided dataset below
2. You MUST return valid perfume IDs from the dataset
3. You MUST NOT invent or imagine perfumes
4. You MUST provide a brief reason for each recommendation
5. You MUST respect budget constraints if specified
6. You MUST NOT include samples, testers, oils, or mists

**USER REQUEST:**
{request.user_query}

**USER CONTEXT:**
{user_context}

**AVAILABLE PERFUMES (select from these ONLY):**
{dataset_context}

**YOUR TASK:**
1. Understand the user's intent (occasion, notes, mood, budget, gender)
2. Select the {request.num_recommendations} BEST matches from the dataset above
3. Rank them by relevance
4. Provide a brief reason for each selection (max 15 words)

**OUTPUT FORMAT (strict JSON):**
{{
  "intent": {{
    "occasion": "daily|office|date|party|wedding|gym|null",
    "notes": ["note1", "note2"],
    "mood": "fresh|warm|floral|woody|sweet|null",
    "gender": "men|women|unisex|null",
    "budget_max": number or null,
    "performance": "light|moderate|strong|null"
  }},
  "recommendations": [
    {{
      "id": "exact_id_from_dataset",
      "reason": "brief reason (max 15 words)"
    }}
  ],
  "confidence": 0.0-1.0
}}

**IMPORTANT:**
- Use EXACT IDs from the dataset above
- Keep reasons concise and specific
- Rank by best match first
- Consider rating, popularity, and relevance
- ALL products in the dataset are already filtered for quality and budget

Return ONLY the JSON, no other text."""

        return prompt
    
    def _get_perfume_data(self, perfume_ids: List[int]) -> List[Dict[str, Any]]:
        """Get perfume data for given IDs"""
        if recommender.data is None:
            return []
        
        results = []
        for pid in perfume_ids:
            idx = recommender._resolve_index(pid)
            if idx is not None:
                row = recommender._safe_row(idx)
                results.append(row)
        
        return results
    
    def _build_dataset_context(self, candidates: List[Dict[str, Any]]) -> str:
        """Build compact dataset context for AI"""
        lines = []
        for i, perfume in enumerate(candidates[:50], 1):  # Limit to 50 for tokens
            line = (
                f"{i}. ID: {perfume['id']} | "
                f"{perfume['name']} by {perfume['brand']} | "
                f"Gender: {perfume['gender']} | "
                f"Rating: {perfume['rating']:.1f} | "
                f"Notes: {perfume['accords'][:80]}"
            )
            if perfume.get('price') and perfume['price'] > 0:
                line += f" | Price: ${perfume['price']:.0f}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    def _build_user_context(self, request: AIRecommendationRequest) -> str:
        """Build user context string"""
        if not request.user_context:
            return "No additional context provided."
        
        ctx = request.user_context
        parts = []
        
        if ctx.get('gender'):
            parts.append(f"Gender preference: {ctx['gender']}")
        if ctx.get('occasion'):
            parts.append(f"Occasion: {ctx['occasion']}")
        if ctx.get('season'):
            parts.append(f"Season: {ctx['season']}")
        if ctx.get('mood'):
            parts.append(f"Mood: {ctx['mood']}")
        if ctx.get('liked_notes'):
            parts.append(f"Liked notes: {', '.join(ctx['liked_notes'][:5])}")
        if ctx.get('disliked_notes'):
            parts.append(f"Disliked notes: {', '.join(ctx['disliked_notes'][:5])}")
        if ctx.get('budget_max'):
            parts.append(f"Budget: under ${ctx['budget_max']}")
        
        return '\n'.join(parts) if parts else "No additional context provided."
    
    def _parse_ai_response(self, response_text: str, provider: str) -> Optional[AIRecommendationResponse]:
        """Parse AI response into structured format"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text.strip()
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            if json_text.startswith('```'):
                json_text = json_text[3:]
            if json_text.endswith('```'):
                json_text = json_text[:-3]
            json_text = json_text.strip()
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Validate structure
            if 'intent' not in data or 'recommendations' not in data:
                logger.error("AI response missing required fields")
                return None
            
            # Extract data
            intent = data['intent']
            recommendations = data['recommendations']
            confidence = float(data.get('confidence', 0.7))
            
            # Validate recommendations have IDs
            valid_recs = []
            for rec in recommendations:
                if 'id' in rec and rec['id']:
                    valid_recs.append(rec)
            
            if not valid_recs:
                logger.error("No valid recommendations in AI response")
                return None
            
            return AIRecommendationResponse(
                intent=intent,
                recommendations=valid_recs,
                confidence=confidence,
                reasoning=data.get('reasoning', ''),
                provider=provider
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None
    
    def _local_fallback(
        self,
        request: AIRecommendationRequest,
        candidate_ids: List[int]
    ) -> AIRecommendationResponse:
        """
        Local fallback when AI is unavailable.
        Uses existing ML model with candidate pre-filtering.
        """
        logger.info("Using local fallback for recommendations")
        
        # Get perfume data for candidates
        candidates = self._get_perfume_data(candidate_ids[:request.num_recommendations * 5])
        
        # Simple scoring based on rating and relevance
        scored = []
        for perfume in candidates:
            score = perfume['rating'] / 5.0  # Normalize rating
            scored.append((perfume, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Add variety: Take top candidates but shuffle them to avoid repetition
        # Get top 2x the requested amount, then shuffle and pick
        import random
        top_candidates = scored[:request.num_recommendations * 2]
        random.shuffle(top_candidates)
        
        # Build recommendations
        recommendations = []
        for perfume, score in top_candidates[:request.num_recommendations]:
            recommendations.append({
                'id': str(perfume['id']),
                'reason': f"High-rated {perfume['gender']} fragrance with {perfume['accords'].split()[0] if perfume['accords'] else 'classic'} notes"
            })
        
        # Extract intent from context
        intent = {}
        if request.user_context:
            ctx = request.user_context
            intent = {
                'occasion': ctx.get('occasion'),
                'notes': ctx.get('liked_notes', []),
                'mood': ctx.get('mood'),
                'gender': ctx.get('gender'),
                'budget_max': ctx.get('budget_max'),
            }
        
        return AIRecommendationResponse(
            intent=intent,
            recommendations=recommendations,
            confidence=0.6,
            reasoning="Local fallback used due to AI unavailability",
            provider="local"
        )
    
    def _fallback_response(self, request: AIRecommendationRequest) -> AIRecommendationResponse:
        """Emergency fallback when no candidates found"""
        return AIRecommendationResponse(
            intent={},
            recommendations=[],
            confidence=0.0,
            reasoning="No matching perfumes found",
            provider="fallback"
        )


# Global AI engine
ai_engine = AIRecommendationEngine()


# ── Validation and Quality Control ────────────────────────────────────

class RecommendationValidator:
    """
    Validates AI recommendations against database.
    Ensures no invented perfumes, removes duplicates, applies quality filters.
    """
    
    @staticmethod
    def validate_and_enrich(
        ai_response: AIRecommendationResponse,
        request: AIRecommendationRequest
    ) -> List[ValidatedRecommendation]:
        """
        Validate AI recommendations and enrich with database data.
        
        Steps:
        1. Match IDs with database
        2. Remove invalid/missing items (HALLUCINATION CHECK)
        3. Remove duplicates
        4. Remove low-quality items (samples, testers)
        5. Apply budget double-check
        6. Apply quality scoring
        7. Sort by final score
        """
        if not ai_response.recommendations:
            return []
        
        validated = []
        seen_ids = set()
        invalid_count = 0
        duplicate_count = 0
        budget_violations = 0
        
        for rec in ai_response.recommendations:
            # Extract ID
            perfume_id = str(rec.get('id', '')).strip()
            if not perfume_id or perfume_id in seen_ids:
                if perfume_id in seen_ids:
                    duplicate_count += 1
                continue
            
            # Resolve to database index (HALLUCINATION CHECK)
            try:
                idx = recommender._resolve_index(perfume_id)
                if idx is None:
                    logger.warning(f"HALLUCINATION: Invalid perfume ID from AI: {perfume_id}")
                    invalid_count += 1
                    continue
            except Exception as e:
                logger.error(f"Error resolving ID {perfume_id}: {e}")
                invalid_count += 1
                continue
            
            # Get perfume data
            perfume_data = recommender._safe_row(idx)
            
            # Quality checks
            if not RecommendationValidator._passes_quality_check(perfume_data):
                logger.debug(f"Perfume {perfume_id} failed quality check")
                invalid_count += 1
                continue
            
            # Budget double-check
            if request.user_context and request.user_context.get('budget_max'):
                budget_max = float(request.user_context['budget_max'])
                price = float(perfume_data.get('price', 0))
                if price > budget_max:
                    logger.warning(f"BUDGET VIOLATION: {perfume_data['name']} (${price} > ${budget_max})")
                    budget_violations += 1
                    continue
            
            # Build validated recommendation
            validated_rec = ValidatedRecommendation(
                perfume_id=perfume_id,
                name=perfume_data['name'],
                brand=perfume_data['brand'],
                rating=perfume_data['rating'],
                accords=perfume_data['accords'],
                image_url=perfume_data.get('image_url', ''),
                price_usd=perfume_data.get('price', 0),
                gender=perfume_data['gender'],
                description=perfume_data.get('description', ''),
                match_score=ai_response.confidence,
                ai_reason=rec.get('reason', ''),
                algorithm="ai_primary"
            )
            
            validated.append(validated_rec)
            seen_ids.add(perfume_id)
        
        # Log validation metrics
        total = len(ai_response.recommendations)
        valid = len(validated)
        pass_rate = valid / total if total > 0 else 0.0
        
        logger.info(f"Validation: {valid}/{total} valid ({pass_rate:.1%})")
        logger.info(f"  Hallucinations: {invalid_count}")
        logger.info(f"  Duplicates: {duplicate_count}")
        logger.info(f"  Budget violations: {budget_violations}")
        
        if pass_rate < 0.95:
            logger.error(f"LOW VALIDATION PASS RATE: {pass_rate:.1%}")
        
        if invalid_count > 0:
            logger.error(f"HALLUCINATIONS DETECTED: {invalid_count} invalid IDs")
        
        # Apply final scoring and sorting
        validated = RecommendationValidator._apply_final_scoring(validated, request)
        
        return validated
    
    @staticmethod
    def _passes_quality_check(perfume_data: Dict[str, Any]) -> bool:
        """Check if perfume passes quality filters"""
        name = perfume_data.get('name', '').lower()
        
        # Remove samples, testers, gift sets
        noise_keywords = [
            'sample', 'tester', 'vial', 'decant', 'mini',
            'gift set', 'variety pack', 'discovery set', 'sampler'
        ]
        if any(keyword in name for keyword in noise_keywords):
            return False
        
        # Minimum rating threshold
        rating = perfume_data.get('rating', 0)
        if rating < 3.0:
            return False
        
        # Must have basic data
        if not perfume_data.get('brand') or not perfume_data.get('name'):
            return False
        
        return True
    
    @staticmethod
    def _apply_final_scoring(
        recommendations: List[ValidatedRecommendation],
        request: AIRecommendationRequest
    ) -> List[ValidatedRecommendation]:
        """Apply final scoring and sort recommendations"""
        import random
        
        for rec in recommendations:
            # Base score from AI confidence
            score = rec.match_score
            
            # Boost by rating
            score += (rec.rating / 5.0) * 0.2
            
            # Boost if matches user context
            if request.user_context:
                ctx = request.user_context
                
                # Gender match
                if ctx.get('gender') and ctx['gender'] == rec.gender:
                    score += 0.1
                
                # Note match
                if ctx.get('liked_notes'):
                    accords_lower = rec.accords.lower()
                    matches = sum(1 for note in ctx['liked_notes'] if note.lower() in accords_lower)
                    score += matches * 0.05
            
            # Add small random factor for variety (±5%)
            # This prevents always showing the same perfumes
            score += random.uniform(-0.05, 0.05)
            
            # Update score
            rec.match_score = min(1.0, max(0.0, score))
        
        # Sort by score
        recommendations.sort(key=lambda x: x.match_score, reverse=True)
        
        return recommendations


# ── Public API ─────────────────────────────────────────────────────────

def get_ai_recommendations(
    user_query: str,
    num_recommendations: int = 6,
    user_context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Main entry point for AI-powered recommendations.
    
    Args:
        user_query: User's natural language query
        num_recommendations: Number of recommendations to return
        user_context: User profile and preferences
        conversation_history: Previous conversation messages
    
    Returns:
        Dict with recommendations, intent, confidence, and explanation
    """
    # Build request
    request = AIRecommendationRequest(
        user_query=user_query,
        user_context=user_context,
        num_recommendations=num_recommendations,
        conversation_history=conversation_history
    )
    
    # Get AI recommendations
    ai_response = ai_engine.recommend(request)
    
    # Validate and enrich
    validated_recs = RecommendationValidator.validate_and_enrich(ai_response, request)
    
    # Convert to dict format
    recommendations = []
    for rec in validated_recs:
        recommendations.append({
            'id': rec.perfume_id,
            'name': rec.name,
            'brand': rec.brand,
            'rating': rec.rating,
            'accords': rec.accords,
            'image_url': rec.image_url,
            'price': rec.price_usd,
            'gender': rec.gender,
            'description': rec.description,
            'match_score': rec.match_score,
            'score': rec.match_score,
            'algorithm': rec.algorithm,
            'ai_reason': rec.ai_reason,
        })
    
    return {
        'recommendations': recommendations,
        'intent': ai_response.intent,
        'confidence': ai_response.confidence,
        'provider': ai_response.provider,
        'explanation': ai_response.reasoning,
    }


def initialize_ai_engine():
    """Initialize AI engine with dataset"""
    if recommender.data is not None and len(recommender.data) > 0:
        semantic_engine.initialize(recommender.data)
        logger.info("AI recommendation engine initialized")
    else:
        logger.warning("Cannot initialize AI engine: dataset not loaded")
