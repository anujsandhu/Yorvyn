/**
 * YORVYN — PHASE 8: AI Avatar Intelligence Test Suite
 * 
 * Verifies:
 * 1. AvatarCommandValidator: Strict parameter bounds, catalog verification, and sanitize checks
 * 2. AvatarIntentParser: Natural language intent parsing, typed proposals, and alternative generation
 * 3. AvatarAIPrivacyManager: Explicit user consent enforcement, zero-retention guarantee, and revocation
 * 4. PhotoAnalysisService: Reference photo traits extraction and privacy validation
 * 5. HairstyleRecommendationService: Face shape matrix, 3-option comparison sets, and favorites
 * 6. AvatarRecommendationEngine: Occasion styling and seasonal color palette mapping
 * 7. AvatarPreviewOrchestrator: Staging, Before/After comparison, and commit/revert flows
 * 8. AvatarAIConversationManager: Multi-turn dialogue, message history, and action dispatching
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { 
  DEFAULT_AVATAR_PROFILE, 
  AvatarProfile 
} from '../../../types/avatarProfile';
import { AvatarCreatorEngine } from '../../avatarCreator/avatarCreatorEngine';
import {
  AvatarCommandValidator,
  AvatarIntentParser,
  AvatarAIPrivacyManager,
  PhotoPrivacyConsentError,
  PhotoAnalysisService,
  HairstyleRecommendationService,
  AvatarRecommendationEngine,
  AvatarPreviewOrchestrator,
  AvatarAIConversationManager,
  AvatarCustomizationProposal,
  AvatarCommandOperation
} from '../index';

describe('YORVYN — Phase 8: AI Avatar Intelligence Engine', () => {
  let profile: AvatarProfile;

  beforeEach(() => {
    profile = JSON.parse(JSON.stringify(DEFAULT_AVATAR_PROFILE));
    AvatarAIPrivacyManager.revokeConsent();
  });

  // ── 1. AVATAR COMMAND VALIDATOR ──
  describe('AvatarCommandValidator', () => {
    it('validates and clamps in-bounds and out-of-bounds slider values', () => {
      const validOp: AvatarCommandOperation = {
        action: 'set_slider',
        category: 'face',
        targetKey: 'jawWidth',
        targetValue: 0.35,
        displayLabel: 'Jaw Width +35%'
      };
      const res = AvatarCommandValidator.validateOperation(validOp);
      expect(res.isValid).toBe(true);
      expect(res.sanitizedOperation?.targetValue).toBe(0.35);

      const excessiveOp: AvatarCommandOperation = {
        action: 'set_slider',
        category: 'face',
        targetKey: 'jawWidth',
        targetValue: 4.5, // Exceeds 1.0 limit
        displayLabel: 'Extreme Jaw'
      };
      const clampedRes = AvatarCommandValidator.validateOperation(excessiveOp);
      expect(clampedRes.isValid).toBe(true);
      expect(clampedRes.sanitizedOperation?.targetValue).toBe(1.0); // Clamped
      expect(clampedRes.issues.some(i => i.severity === 'warning')).toBe(true);
    });

    it('rejects unsupported slider keys', () => {
      const invalidOp: AvatarCommandOperation = {
        action: 'set_slider',
        category: 'face',
        targetKey: 'non_existent_joint_bone',
        targetValue: 0.5,
        displayLabel: 'Invalid Joint'
      };
      const res = AvatarCommandValidator.validateOperation(invalidOp);
      expect(res.isValid).toBe(false);
      expect(res.issues.length).toBeGreaterThan(0);
    });

    it('validates supported hex colors', () => {
      const validColor: AvatarCommandOperation = {
        action: 'set_color',
        category: 'skin',
        targetKey: 'skinToneHex',
        targetValue: '#f3c299',
        displayLabel: 'Warm Amber'
      };
      expect(AvatarCommandValidator.validateOperation(validColor).isValid).toBe(true);

      const invalidColor: AvatarCommandOperation = {
        action: 'set_color',
        category: 'skin',
        targetKey: 'skinToneHex',
        targetValue: 'not-a-color-value',
        displayLabel: 'Bad Color'
      };
      expect(AvatarCommandValidator.validateOperation(invalidColor).isValid).toBe(false);
    });

    it('validates facial resting expressions against supported blendshape rigs', () => {
      const happyOp: AvatarCommandOperation = {
        action: 'set_expression',
        category: 'expressions',
        targetKey: 'restingExpression',
        targetValue: 'happy',
        displayLabel: 'Happy'
      };
      expect(AvatarCommandValidator.validateOperation(happyOp).isValid).toBe(true);

      const invalidExp: AvatarCommandOperation = {
        action: 'set_expression',
        category: 'expressions',
        targetKey: 'restingExpression',
        targetValue: 'hyper_ecstatic_frown',
        displayLabel: 'Invalid Rig Expression'
      };
      expect(AvatarCommandValidator.validateOperation(invalidExp).isValid).toBe(false);
    });
  });

  // ── 2. AVATAR INTENT PARSER ──
  describe('AvatarIntentParser', () => {
    it('parses facial structure instructions (narrow/wide jaw)', () => {
      const proposal = AvatarIntentParser.parse('Make my face slightly narrower and define my jaw', profile);
      expect(proposal).toBeDefined();
      expect(proposal.confidence).toBeGreaterThan(0.7);
      expect(proposal.operations.some(op => op.targetKey.includes('jaw') || op.targetKey.includes('head'))).toBe(true);
      expect(proposal.profilePatch.face).toBeDefined();
    });

    it('parses hairstyle requests into supported 3D hair asset presets', () => {
      const proposal = AvatarIntentParser.parse('Give me a modern textured hairstyle', profile);
      expect(proposal.category).toBe('hair');
      expect(proposal.operations.some(op => op.targetKey === 'hairStyleId')).toBe(true);
      expect(proposal.profilePatch.appearance?.hairStyleId).toBeDefined();
    });

    it('parses body proportion instructions (broaden shoulders)', () => {
      const proposal = AvatarIntentParser.parse('Make my shoulders broader (+35%)', profile);
      expect(proposal.category).toBe('body');
      expect(proposal.operations.some(op => op.targetKey.includes('shoulderWidth'))).toBe(true);
      expect(proposal.profilePatch.proportions?.shoulderWidth).toBeGreaterThan(0);
    });

    it('parses eye color modification requests with realistic iris swatches', () => {
      const proposal = AvatarIntentParser.parse('Change my eye color to emerald green', profile);
      expect(proposal.category).toBe('eyes');
      expect(proposal.operations.some(op => op.targetKey === 'eyeColorId')).toBe(true);
      expect(proposal.profilePatch.appearance?.eyeColorId).toBe('green');
    });

    it('generates multi-option alternatives for combo prompts', () => {
      const proposal = AvatarIntentParser.parse('Show me three different hairstyle combinations', profile);
      expect(proposal.alternatives).toBeDefined();
      expect(proposal.alternatives?.length).toBeGreaterThanOrEqual(2);
      expect(proposal.alternatives![0].profilePatch.appearance?.hairStyleId).toBeDefined();
    });
  });

  // ── 3. PRIVACY MANAGER & ZERO RETENTION ──
  describe('AvatarAIPrivacyManager', () => {
    it('enforces explicit consent before allowing reference photo access', () => {
      expect(AvatarAIPrivacyManager.hasValidConsent()).toBe(false);
      expect(() => AvatarAIPrivacyManager.verifyConsentOrThrow()).toThrow(PhotoPrivacyConsentError);

      AvatarAIPrivacyManager.grantConsent([
        'ephemeral_feature_extraction',
        'zero_retention_guarantee'
      ]);
      expect(AvatarAIPrivacyManager.hasValidConsent()).toBe(true);
      expect(() => AvatarAIPrivacyManager.verifyConsentOrThrow()).not.toThrow();
    });

    it('allows instant user consent revocation', () => {
      AvatarAIPrivacyManager.grantConsent();
      expect(AvatarAIPrivacyManager.hasValidConsent()).toBe(true);

      AvatarAIPrivacyManager.revokeConsent();
      expect(AvatarAIPrivacyManager.hasValidConsent()).toBe(false);
    });

    it('provides documented zero-retention policy and non-anthropometric disclaimer', () => {
      expect(AvatarAIPrivacyManager.DOCUMENTED_RETENTION_POLICY).toContain('Zero-Retention');
      expect(AvatarAIPrivacyManager.PHOTO_ANALYSIS_DISCLAIMER).toContain('approximate');
    });
  });

  // ── 4. PHOTO ANALYSIS SERVICE ──
  describe('PhotoAnalysisService', () => {
    it('blocks photo analysis when consent is absent', async () => {
      const mockFile = new File(['fake-image-bytes'], 'selfie.jpg', { type: 'image/jpeg' });
      await expect(PhotoAnalysisService.analyzePhoto(mockFile, profile)).rejects.toThrow(PhotoPrivacyConsentError);
    });

    it('extracts traits and generates non-destructive proposal when consented', async () => {
      AvatarAIPrivacyManager.grantConsent();
      const mockFile = new File(['fake-image-bytes'], 'portrait.jpg', { type: 'image/jpeg' });

      const result = await PhotoAnalysisService.analyzePhoto(mockFile, profile);
      expect(result).toBeDefined();
      expect(result.detectedTraits.faceShape).toBeDefined();
      expect(result.detectedTraits.skinTone.hex).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(result.detectedTraits.proportions.disclaimer).toBeDefined();
      expect(result.generatedProposal.operations.length).toBeGreaterThan(0);
      expect(result.retentionPolicy).toContain('Zero-Retention');
    });
  });

  // ── 5. HAIRSTYLE RECOMMENDATION SERVICE ──
  describe('HairstyleRecommendationService', () => {
    it('ranks hairstyles by face shape compatibility', () => {
      const ovalRecs = HairstyleRecommendationService.getRecommendations('oval', 'masculine');
      const squareRecs = HairstyleRecommendationService.getRecommendations('square', 'masculine');
      expect(ovalRecs.length).toBeGreaterThan(0);
      expect(squareRecs.length).toBeGreaterThan(0);
      expect(ovalRecs[0].matchScore).toBeGreaterThanOrEqual(80);
    });

    it('provides 3-way hairstyle comparison alternatives', () => {
      const comparisonSet = HairstyleRecommendationService.getThreeWayHairstyleComparison(profile);
      expect(comparisonSet.length).toBe(3);
      expect(comparisonSet[0].profilePatch.appearance?.hairStyleId).toBeDefined();
      expect(comparisonSet[1].profilePatch.appearance?.hairStyleId).toBeDefined();
      expect(comparisonSet[2].profilePatch.appearance?.hairStyleId).toBeDefined();
    });

    it('toggles and persists favorite hairstyles', () => {
      const styleId = 'short02';
      const added = HairstyleRecommendationService.toggleFavorite(styleId);
      expect(added).toBe(true);
      expect(HairstyleRecommendationService.getFavorites()).toContain(styleId);

      const removed = HairstyleRecommendationService.toggleFavorite(styleId);
      expect(removed).toBe(false);
      expect(HairstyleRecommendationService.getFavorites()).not.toContain(styleId);
    });
  });

  // ── 6. AVATAR RECOMMENDATION ENGINE ──
  describe('AvatarRecommendationEngine', () => {
    it('recommends occasion-aligned looks with weather context', () => {
      const styling = AvatarRecommendationEngine.recommendForOccasion(
        {
          occasion: 'gala',
          temperatureCelsius: 16
        },
        profile
      );

      expect(styling.occasionTitle).toBeDefined();
      expect(styling.paletteHexes.length).toBeGreaterThan(0);
      expect(styling.recommendedOutfit.editorialReason).toBeDefined();

      const proposal = AvatarRecommendationEngine.proposalToAvatarDNA(styling, profile);
      expect(proposal.profilePatch.wardrobe).toBeDefined();
      expect(proposal.operations.some(op => op.category === 'clothing')).toBe(true);
    });

    it('derives seasonal color palettes for avatar skin and eye traits', () => {
      const palette = AvatarRecommendationEngine.getAvatarColorSeason('#f3c299', 'brownlight');
      expect(palette.name).toBeDefined();
      expect(palette.palette.length).toBeGreaterThanOrEqual(4);
    });
  });

  // ── 7. AVATAR PREVIEW ORCHESTRATOR ──
  describe('AvatarPreviewOrchestrator', () => {
    let orchestrator: AvatarPreviewOrchestrator;
    let engine: AvatarCreatorEngine;

    beforeEach(() => {
      engine = new AvatarCreatorEngine(profile);
      orchestrator = new AvatarPreviewOrchestrator(engine);
    });

    it('stages proposals in preview mode without altering engine baseline', () => {
      const baselineBefore = engine.getProfile();
      const proposal: AvatarCustomizationProposal = {
        id: 'prop_test_1',
        title: 'Broader Shoulders Test',
        summary: 'Preview test',
        category: 'body',
        confidence: 0.9,
        operations: [],
        profilePatch: {
          proportions: {
            ...baselineBefore.proportions,
            shoulderWidth: 0.75
          }
        },
        explanation: 'Test',
        createdAt: new Date().toISOString(),
        source: 'conversational',
        status: 'pending'
      };

      const previewProfile = orchestrator.startPreview(proposal, baselineBefore);
      expect(orchestrator.isPreviewing()).toBe(true);
      expect(previewProfile.proportions.shoulderWidth).toBe(0.75);
      // Engine baseline must remain untouched
      expect(engine.getProfile().proportions.shoulderWidth).toBe(baselineBefore.proportions.shoulderWidth);
    });

    it('toggles Before/After comparison correctly', () => {
      const baselineBefore = engine.getProfile();
      const proposal: AvatarCustomizationProposal = {
        id: 'prop_test_2',
        title: 'Jaw Width Test',
        summary: 'Preview test',
        category: 'face',
        confidence: 0.9,
        operations: [],
        profilePatch: {
          face: {
            ...baselineBefore.face,
            jawWidth: 0.6
          }
        },
        explanation: 'Test',
        createdAt: new Date().toISOString(),
        source: 'conversational',
        status: 'pending'
      };

      orchestrator.startPreview(proposal, baselineBefore);
      expect(orchestrator.getEffectiveProfile()?.face.jawWidth).toBe(0.6);

      // Show original (Before)
      orchestrator.toggleBeforeAfter(true);
      expect(orchestrator.getEffectiveProfile()?.face.jawWidth).toBe(baselineBefore.face.jawWidth);

      // Toggle back to proposed (After)
      orchestrator.toggleBeforeAfter(false);
      expect(orchestrator.getEffectiveProfile()?.face.jawWidth).toBe(0.6);
    });

    it('commits accepted proposal into AvatarCreatorEngine with undo snapshot', () => {
      const baselineBefore = engine.getProfile();
      const proposal: AvatarCustomizationProposal = {
        id: 'prop_test_3',
        title: 'Skin Tone Test',
        summary: 'Commit test',
        category: 'skin',
        confidence: 0.95,
        operations: [],
        profilePatch: {
          appearance: {
            ...baselineBefore.appearance,
            skinToneHex: '#00ffee'
          }
        },
        explanation: 'Test',
        createdAt: new Date().toISOString(),
        source: 'conversational',
        status: 'pending'
      };

      orchestrator.startPreview(proposal, baselineBefore);
      orchestrator.acceptPreview();

      expect(orchestrator.isPreviewing()).toBe(false);
      expect(engine.getProfile().appearance.skinToneHex).toBe('#00ffee');
      expect(engine.getHistory().canUndo).toBe(true);
    });

    it('reverts preview on reject without mutating engine profile', () => {
      const baselineBefore = engine.getProfile();
      const proposal: AvatarCustomizationProposal = {
        id: 'prop_test_4',
        title: 'Hair Style Test',
        summary: 'Reject test',
        category: 'hair',
        confidence: 0.9,
        operations: [],
        profilePatch: {
          appearance: {
            ...baselineBefore.appearance,
            hairStyleId: 'bob01'
          }
        },
        explanation: 'Test',
        createdAt: new Date().toISOString(),
        source: 'conversational',
        status: 'pending'
      };

      orchestrator.startPreview(proposal, baselineBefore);
      const reverted = orchestrator.rejectPreview();

      expect(orchestrator.isPreviewing()).toBe(false);
      expect(reverted?.appearance.hairStyleId).toBe(baselineBefore.appearance.hairStyleId);
      expect(engine.getProfile().appearance.hairStyleId).toBe(baselineBefore.appearance.hairStyleId);
    });
  });

  // ── 8. AVATAR AI CONVERSATION MANAGER ──
  describe('AvatarAIConversationManager', () => {
    let convManager: AvatarAIConversationManager;
    let orchestrator: AvatarPreviewOrchestrator;
    let engine: AvatarCreatorEngine;

    beforeEach(() => {
      engine = new AvatarCreatorEngine(profile);
      orchestrator = new AvatarPreviewOrchestrator(engine);
      convManager = new AvatarAIConversationManager(orchestrator);
    });

    it('initializes with greeting and quick action suggestions', () => {
      const msgs = convManager.getMessages();
      expect(msgs.length).toBeGreaterThanOrEqual(1);
      expect(msgs[0].sender).toBe('assistant');
      expect(msgs[0].quickActions?.length).toBeGreaterThan(0);
    });

    it('handles user messages and attaches structured proposals', async () => {
      const proposal = await convManager.handleUserMessage('Make my shoulders broader', profile);
      expect(proposal).toBeDefined();
      expect(orchestrator.isPreviewing()).toBe(true);

      const msgs = convManager.getMessages();
      const lastMsg = msgs[msgs.length - 1];
      expect(lastMsg.sender).toBe('assistant');
      expect(lastMsg.proposal).toBeDefined();
    });

    it('dispatches accept action and appends system confirmation', () => {
      convManager.acceptProposal();
      const msgs = convManager.getMessages();
      const lastMsg = msgs[msgs.length - 1];
      expect(lastMsg.sender).toBe('system');
      expect(lastMsg.text).toContain('applied');
    });

    it('dispatches reject action and appends system reversion notice', () => {
      convManager.rejectProposal();
      const msgs = convManager.getMessages();
      const lastMsg = msgs[msgs.length - 1];
      expect(lastMsg.sender).toBe('system');
      expect(lastMsg.text).toContain('discarded');
    });
  });
});
