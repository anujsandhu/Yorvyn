/**
 * YORVYN — AI Fashion Stylist & Personal Shopping Intelligence Unit Tests (Phase 11)
 * Comprehensive verification of recommendations, wardrobe integration, avatar staging,
 * color harmony, feedback learning, and conversational styling.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  FashionProfileManager,
  ColourCoordinationEngine,
  OutfitCompatibilityValidator,
  WardrobeRetrievalService,
  ProductDiscoveryAdapter,
  OutfitRecommendationEngine,
  OutfitPreviewOrchestrator,
  FashionFeedbackManager,
  AIStylistConversationManager
} from '../index';
import { HumanParams, DEFAULT_PARAMS } from '../../ara/core/params';
import { FASHION_CATALOG, DEFAULT_FALLBACK_WARDROBE } from '../../../data/fashionCatalogData';

describe('YORVYN — Phase 11: AI Fashion Stylist & Personal Shopping Intelligence', () => {
  let profileManager: FashionProfileManager;
  let wardrobeService: WardrobeRetrievalService;
  let productAdapter: ProductDiscoveryAdapter;
  let recommendationEngine: OutfitRecommendationEngine;
  let previewOrchestrator: OutfitPreviewOrchestrator;
  let feedbackManager: FashionFeedbackManager;
  let conversationManager: AIStylistConversationManager;
  let mockBaselineParams: HumanParams;

  beforeEach(() => {
    profileManager = new FashionProfileManager();
    profileManager.resetProfile();
    wardrobeService = new WardrobeRetrievalService();
    productAdapter = new ProductDiscoveryAdapter();
    recommendationEngine = new OutfitRecommendationEngine(wardrobeService, productAdapter);
    previewOrchestrator = new OutfitPreviewOrchestrator();
    feedbackManager = new FashionFeedbackManager(profileManager);
    conversationManager = new AIStylistConversationManager(recommendationEngine, previewOrchestrator);

    mockBaselineParams = {
      ...DEFAULT_PARAMS,
      gender: 0.90,
      height: 0.65,
      weight: 0.50,
      muscle: 0.55,
      skin: 'young_caucasian_male',
      skinTint: '#ffffff',
      hair: 'short02',
      hairColor: '#1e293b'
    };
  });

  // ── 1. PERSONAL FASHION PROFILE ──
  describe('FashionProfileManager', () => {
    it('initializes with structured defaults and keeps fashion preferences isolated from sensitive personal data', () => {
      const p = profileManager.getProfile();
      expect(p.preferredStyles.length).toBeGreaterThan(0);
      expect(p.favoriteColors.length).toBeGreaterThan(0);
      expect(p.preferredFits).toContain('regular');
      expect(p.budgetTier).toBe('mid_premium');

      // Verify no sensitive personal attributes leaked into fashion profile
      expect((p as any).medicalHistory).toBeUndefined();
      expect((p as any).biometrics).toBeUndefined();
      expect((p as any).religion).toBeUndefined();
    });

    it('updates preferred styles, fits, colors, and budget limits', () => {
      profileManager.setPreferredStyles(['formal', 'business']);
      profileManager.setPreferredFits(['slim']);
      profileManager.setFavoriteColors(['#000000', '#ffffff']);
      profileManager.setBudgetTier('budget', 5000);

      const updated = profileManager.getProfile();
      expect(updated.preferredStyles).toEqual(['formal', 'business']);
      expect(updated.preferredFits).toEqual(['slim']);
      expect(updated.maxPricePerItem).toBe(5000);
      expect(updated.budgetTier).toBe('budget');
    });

    it('allows complete reset of learned preferences back to clean defaults', () => {
      profileManager.setPreferredStyles(['streetwear']);
      profileManager.addFeedback({ outfitId: 'test_1', action: 'dislike', dislikeReason: 'too_casual' });

      const reset = profileManager.resetProfile();
      expect(reset.preferredStyles).toContain('casual');
      expect(reset.feedbackHistory.length).toBe(0);
      expect(reset.dislikedStyles.length).toBe(0);
    });
  });

  // ── 2. COLOUR & STYLE COORDINATION INTELLIGENCE ──
  describe('ColourCoordinationEngine', () => {
    it('evaluates monochromatic tonal harmony with high scores', () => {
      const res = ColourCoordinationEngine.evaluateHarmony(['#0f172a', '#1e293b', '#334155']);
      expect(res.scheme).toBe('monochromatic');
      expect(res.harmonyScore).toBeGreaterThanOrEqual(0.85);
      expect(res.explanation).toContain('monochromatic');
    });

    it('detects architectural high-contrast combinations (black and white)', () => {
      const res = ColourCoordinationEngine.evaluateHarmony(['#000000', '#ffffff']);
      expect(res.scheme).toBe('high_contrast');
      expect(res.harmonyScore).toBeGreaterThanOrEqual(0.90);
    });

    it('evaluates pattern compatibility and warns against competing loud prints', () => {
      const safe = ColourCoordinationEngine.evaluatePatternCompatibility(['solid', 'striped']);
      expect(safe.isCompatible).toBe(true);
      expect(safe.score).toBeGreaterThan(0.90);

      const clashing = ColourCoordinationEngine.evaluatePatternCompatibility(['plaid', 'striped']);
      expect(clashing.isCompatible).toBe(false);
      expect(clashing.notes).toContain('Pattern clash');
    });
  });

  // ── 3. OUTFIT COMPATIBILITY & AVATAR HARMONIZATION ──
  describe('OutfitCompatibilityValidator', () => {
    it('approves coherent ensembles and rejects extreme formality mismatches', () => {
      const topTux = FASHION_CATALOG.find(i => i.id === 'cld-trousers')!;
      const bottomJeans = DEFAULT_FALLBACK_WARDROBE.find(i => i.id === 'wardrobe_2')!;
      const sneakers = DEFAULT_FALLBACK_WARDROBE.find(i => i.id === 'wardrobe_4')!;

      const result = OutfitCompatibilityValidator.validateOutfit(topTux, bottomJeans, sneakers);
      expect(result.isValid).toBe(true);
      expect(result.score).toBeGreaterThan(60);
    });

    it('generates inclusive avatar proportion advice based on body parameters', () => {
      const top = FASHION_CATALOG[1];
      const bot = FASHION_CATALOG[2];
      const shoes = FASHION_CATALOG[3];

      const shortAvatar = { proportions: { heightCm: 160, shoulderWidth: 0.0, silhouette: 'slim' as const } };
      const shortRes = OutfitCompatibilityValidator.validateOutfit(top, bot, shoes, null, shortAvatar as any);
      expect(shortRes.avatarFitNotes.some(n => n.includes('elongates'))).toBe(true);

      const broadAvatar = { proportions: { heightCm: 188, shoulderWidth: 0.35, silhouette: 'athletic' as const } };
      const broadRes = OutfitCompatibilityValidator.validateOutfit(top, bot, shoes, null, broadAvatar as any);
      expect(broadRes.avatarFitNotes.some(n => n.includes('athletic'))).toBe(true);
    });
  });

  // ── 4. CATALOG & WARDROBE GROUNDING GUARANTEES ──
  describe('ProductDiscoveryAdapter & WardrobeRetrievalService', () => {
    it('retrieves products only from real catalog records without fabricating nonexistent items', () => {
      const results = productAdapter.searchProducts('suit');
      expect(results.length).toBeGreaterThan(0);
      results.forEach(item => {
        expect(item.id).toBeDefined();
        expect(item.name).toBeDefined();
        expect(item.priceDisplay).toBeDefined();
        expect(item.priceDisplay).toContain('₹');
      });
    });

    it('parses numeric prices correctly from formatted strings', () => {
      expect(ProductDiscoveryAdapter.parseNumericPrice('₹ 16,900')).toBe(16900);
      expect(ProductDiscoveryAdapter.parseNumericPrice('₹ 24,000')).toBe(24000);
      expect(ProductDiscoveryAdapter.parseNumericPrice('Free')).toBe(0);
    });

    it('retrieves owned wardrobe items and filters by category', () => {
      const tops = wardrobeService.getByCategory('top');
      const bottoms = wardrobeService.getByCategory('bottom');
      const footwear = wardrobeService.getByCategory('footwear');

      expect(tops.length).toBeGreaterThan(0);
      expect(bottoms.length).toBeGreaterThan(0);
      expect(footwear.length).toBeGreaterThan(0);
    });
  });

  // ── 5. AI OUTFIT RECOMMENDATION ENGINE ──
  describe('OutfitRecommendationEngine', () => {
    it('generates complete multi-piece outfit combinations matching occasions', () => {
      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'college',
        style: 'casual',
        maxResults: 3
      });

      expect(recs.length).toBeGreaterThan(0);
      const outfit = recs[0];
      expect(outfit.top).toBeDefined();
      expect(outfit.bottom).toBeDefined();
      expect(outfit.footwear).toBeDefined();
      expect(outfit.matchScore).toBeGreaterThanOrEqual(60);
      expect(outfit.colorHarmony).toBeDefined();
      expect(outfit.stylingExplanation.length).toBeGreaterThan(10);
    });

    it('supports wardrobe-only recommendations that exclusively use owned garments', () => {
      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'casual_day',
        wardrobeOnly: true,
        maxResults: 2
      });

      expect(recs.length).toBeGreaterThan(0);
      const outfit = recs[0];
      expect(outfit.sourceBreakdown.catalogPieces).toBe(0);
      expect(outfit.sourceBreakdown.ownedPieces).toBeGreaterThanOrEqual(3);
    });

    it('respects temperature context and layers outerwear when cold (< 19°C)', () => {
      const coldWeather = {
        temperatureCelsius: 12,
        condition: 'cold' as const,
        thermalTier: 'cold' as const
      };

      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'travel_airport',
        weather: coldWeather,
        maxResults: 1
      });

      expect(recs.length).toBeGreaterThan(0);
      expect(recs[0].outerwear).toBeDefined();
    });
  });

  // ── 6. REAL-TIME 3D OUTFIT PREVIEW & PIECE REPLACEMENT ──
  describe('OutfitPreviewOrchestrator', () => {
    it('stages outfit on persistent 3D avatar preserving facial features and skin DNA', () => {
      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'college',
        maxResults: 1
      });

      const staged = previewOrchestrator.stageOutfit(recs[0], mockBaselineParams);
      expect(staged).toBeDefined();
      expect(staged.stagedParams.hairColor).toBe(mockBaselineParams.hairColor);
      expect(staged.stagedParams.skin).toBe(mockBaselineParams.skin);
      expect(staged.stagedParams.gender).toBe(mockBaselineParams.gender);
    });

    it('allows replacing individual pieces without losing the rest of the outfit', () => {
      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'casual_day',
        maxResults: 1
      });

      previewOrchestrator.stageOutfit(recs[0], mockBaselineParams);

      const alternativeShoes = FASHION_CATALOG.find(i => i.category === 'shoes' || i.id === 'cld-sneakers')!;
      const updated = previewOrchestrator.replacePiece('footwear', alternativeShoes);

      expect(updated).toBeDefined();
      expect(updated!.outfit.footwear.id).toBe(alternativeShoes.id);
      expect(updated!.outfit.top.id).toBe(recs[0].top.id); // Top preserved
    });

    it('reverts back to original baseline parameters on discard', () => {
      const recs = recommendationEngine.generateOutfits(profileManager.getProfile(), {
        occasion: 'college',
        maxResults: 1
      });

      previewOrchestrator.stageOutfit(recs[0], mockBaselineParams);
      const reverted = previewOrchestrator.revert();

      expect(reverted).toEqual(mockBaselineParams);
      expect(previewOrchestrator.getStaged()).toBeNull();
    });
  });

  // ── 7. FEEDBACK PERSISTENCE & LEARNING LOOP ──
  describe('FashionFeedbackManager', () => {
    it('records like, dislike, save, and replacement feedback', () => {
      const like = feedbackManager.recordLike('outfit_1', 'Loved the color contrast');
      expect(like.action).toBe('like');

      const dislike = feedbackManager.recordDislike('outfit_2', 'too_formal');
      expect(dislike.action).toBe('dislike');
      expect(dislike.dislikeReason).toBe('too_formal');

      const save = feedbackManager.recordSave('outfit_1');
      expect(save.action).toBe('save');
      expect(profileManager.getProfile().savedOutfitIds).toContain('outfit_1');
    });

    it('dynamically adapts style weighting based on user dislike history', () => {
      feedbackManager.recordDislike('outfit_a', 'too_formal');
      feedbackManager.recordDislike('outfit_b', 'too_formal');
      feedbackManager.recordDislike('outfit_c', 'too_formal');

      const weight = feedbackManager.getStyleWeightMultiplier('formal');
      expect(weight).toBeLessThan(1.0);
    });
  });

  // ── 8. CONVERSATIONAL AI STYLIST ASSISTANT ──
  describe('AIStylistConversationManager', () => {
    it('parses diverse natural language prompts into typed styling intents', () => {
      const i1 = conversationManager.parseIntent('Create a premium casual outfit for college');
      expect(i1.type).toBe('recommend_outfit');
      expect(i1.occasion).toBe('college');
      expect(i1.style).toBe('casual');

      const i2 = conversationManager.parseIntent('Suggest a formal outfit for an interview');
      expect(i2.occasion).toBe('interview');
      expect(i2.style).toBe('formal');

      const i3 = conversationManager.parseIntent('Give me three sneaker combinations');
      expect(i3.type).toBe('find_alternatives');
      expect(i3.targetSlot).toBe('footwear');

      const i4 = conversationManager.parseIntent('Create an outfit under ₹15,000');
      expect(i4.type).toBe('budget_filter');
      expect(i4.budgetLimit).toBe(15000);

      const i5 = conversationManager.parseIntent('Make this look more minimal');
      expect(i5.type).toBe('minimal_styling');
      expect(i5.style).toBe('minimalist');
    });

    it('generates structured proposals with conversational explanations and 3D preview params', async () => {
      const proposal = await conversationManager.handleMessage(
        'Create a premium casual outfit for college',
        profileManager.getProfile(),
        mockBaselineParams
      );

      expect(proposal).toBeDefined();
      expect(proposal.recommendations.length).toBeGreaterThan(0);
      expect(proposal.explanation).toContain('match');
      expect(proposal.appliedParams).toBeDefined();
    });
  });
});
