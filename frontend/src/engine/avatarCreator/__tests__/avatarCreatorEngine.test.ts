/**
 * YORVYN — PHASE 7: Automated Test Suite for 3D Avatar Creator Engine
 * 
 * Verifies:
 * 1. 13 Customization Categories & Parameter Mapping
 * 2. Multi-level Undo / Redo History Stack
 * 3. Before/After Comparison Mechanism
 * 4. Granular Category Resets vs Full Character Reset
 * 5. Asset Registry & Slider Ranges Validation
 * 6. AI Personalization Service Interface
 * 7. Identity & Garment Preservation Across Transformations
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { AvatarCreatorEngine } from '../avatarCreatorEngine';
import { 
  CATEGORY_TABS, 
  AVATAR_SLIDERS, 
  AVATAR_PRESETS,
  HAIR_COLOR_SWATCHES,
  EYE_COLOR_SWATCHES,
  LIP_COLOR_SWATCHES
} from '../avatarCreatorAssetRegistry';
import { aiPersonalizationService } from '../aiPersonalizationInterface';
import { 
  avatarProfileToHumanParams, 
  DEFAULT_AVATAR_PROFILE,
  DEFAULT_AVATAR_PROPORTIONS_MASCULINE
} from '../../../types/avatarProfile';

describe('PHASE 7 — Snap-Style 3D Avatar Creator & Personalization Engine', () => {
  let engine: AvatarCreatorEngine;

  beforeEach(() => {
    engine = new AvatarCreatorEngine();
  });

  // ===========================================================================
  // 1. Core Engine Initialization & State Management
  // ===========================================================================
  describe('1. Engine Initialization & Profile State', () => {
    it('should initialize with default atelier profile and empty history', () => {
      const profile = engine.getProfile();
      expect(profile).toBeDefined();
      expect(profile.version).toBe(3);
      expect(profile.name).toBe('Aarav (Masculine Avatar)');
      expect(profile.genderPresentation).toBe('masculine');

      const history = engine.getHistory();
      expect(history.canUndo).toBe(false);
      expect(history.canRedo).toBe(false);
      expect(history.historyLength).toBe(0);
    });

    it('should notify subscribers immediately and upon profile mutations', () => {
      let callCount = 0;
      let lastProfile = engine.getProfile();

      const unsubscribe = engine.subscribe((p) => {
        callCount++;
        lastProfile = p;
      });

      // Initial call
      expect(callCount).toBe(1);

      // Mutate
      engine.updateProfile({ proportions: { ...lastProfile.proportions, heightCm: 192 } }, 'body', 'Height changed');
      expect(callCount).toBe(2);
      expect(lastProfile.proportions.heightCm).toBe(192);

      unsubscribe();
      engine.updateProfile({ proportions: { ...lastProfile.proportions, heightCm: 170 } }, 'body', 'Height changed again');
      expect(callCount).toBe(2); // Unsubscribed, no extra trigger
    });
  });

  // ===========================================================================
  // 2. Undo, Redo, and Comparison Mechanism
  // ===========================================================================
  describe('2. Undo, Redo, and Before/After Comparison', () => {
    it('should push snapshots to undo stack and allow stepping back and forth', () => {
      const initialHeight = engine.getProfile().proportions.heightCm;

      // 1. Change Height
      engine.updateProfile(
        { proportions: { ...engine.getProfile().proportions, heightCm: 188 } },
        'body',
        'Tall Height'
      );
      expect(engine.getProfile().proportions.heightCm).toBe(188);
      expect(engine.getHistory().canUndo).toBe(true);
      expect(engine.getHistory().canRedo).toBe(false);

      // 2. Change Hair Style
      engine.updateProfile(
        { appearance: { ...engine.getProfile().appearance, hairStyleId: 'buzz' } },
        'hair',
        'Buzz Cut'
      );
      expect(engine.getProfile().appearance.hairStyleId).toBe('buzz');

      // 3. Undo Hair Style
      const undoHairSuccess = engine.undo();
      expect(undoHairSuccess).toBe(true);
      expect(engine.getProfile().appearance.hairStyleId).not.toBe('buzz');
      expect(engine.getProfile().proportions.heightCm).toBe(188); // Height still preserved
      expect(engine.getHistory().canRedo).toBe(true);

      // 4. Undo Height
      const undoHeightSuccess = engine.undo();
      expect(undoHeightSuccess).toBe(true);
      expect(engine.getProfile().proportions.heightCm).toBe(initialHeight);

      // 5. Redo Height
      const redoHeightSuccess = engine.redo();
      expect(redoHeightSuccess).toBe(true);
      expect(engine.getProfile().proportions.heightCm).toBe(188);
    });

    it('should clear redo stack when a new action is performed after undo', () => {
      engine.updateProfile({ face: { ...engine.getProfile().face, jawWidth: 0.2 } }, 'face', 'Wide Jaw');
      engine.undo();
      expect(engine.getHistory().canRedo).toBe(true);

      // New action
      engine.updateProfile({ face: { ...engine.getProfile().face, chinWidth: 0.15 } }, 'face', 'Chin Width');
      expect(engine.getHistory().canRedo).toBe(false);
    });

    it('should support temporary before/after comparison mode without corrupting working profile', () => {
      const initialSnapshot = engine.getWorkingProfile();

      // Customise character heavily
      engine.updateProfile({
        proportions: { ...initialSnapshot.proportions, heightCm: 195, shoulderWidth: 0.4 },
        appearance: { ...initialSnapshot.appearance, hairColorHex: '#d6b372' }
      }, 'body', 'Heavy customisation');

      expect(engine.getWorkingProfile().proportions.heightCm).toBe(195);
      expect(engine.isComparisonActive()).toBe(false);

      // Toggle Comparison Mode ON
      engine.setComparing(true);
      expect(engine.isComparisonActive()).toBe(true);
      // Profile returned during comparison is the original baseline
      expect(engine.getProfile().proportions.heightCm).toBe(initialSnapshot.proportions.heightCm);
      expect(engine.getProfile().appearance.hairColorHex).toBe(initialSnapshot.appearance.hairColorHex);

      // Toggle Comparison Mode OFF
      engine.setComparing(false);
      expect(engine.isComparisonActive()).toBe(false);
      // Returns to modified working profile
      expect(engine.getProfile().proportions.heightCm).toBe(195);
      expect(engine.getProfile().appearance.hairColorHex).toBe('#d6b372');
    });
  });

  // ===========================================================================
  // 3. Category Resets vs Entire Character Reset
  // ===========================================================================
  describe('3. Category Resets vs Full Character Reset', () => {
    it('should reset only face category without losing body or hair customizations', () => {
      // Customise both body and face
      engine.updateProfile({
        proportions: { ...engine.getProfile().proportions, heightCm: 190, waistWidth: -0.2 },
        face: { ...engine.getProfile().face, jawWidth: 0.45, cheekboneProminence: 0.5 },
        appearance: { ...engine.getProfile().appearance, hairStyleId: 'mohawk' }
      }, 'face', 'Multi-category changes');

      // Reset Face only
      engine.resetCategory('face');

      const current = engine.getProfile();
      // Face is reset to neutral defaults
      expect(current.face.jawWidth).toBe(0.05); // Masculine default
      expect(current.face.cheekboneProminence).toBe(0.0);
      expect(current.face.faceWidth).toBe(0.0);

      // Body and Hair are PRESERVED!
      expect(current.proportions.heightCm).toBe(190);
      expect(current.proportions.waistWidth).toBe(-0.2);
      expect(current.appearance.hairStyleId).toBe('mohawk');
    });

    it('should reset hair category without altering face or body proportions', () => {
      engine.updateProfile({
        face: { ...engine.getProfile().face, chinWidth: 0.35 },
        appearance: { ...engine.getProfile().appearance, hairStyleId: 'afro01', hairColorHex: '#d6b372' }
      }, 'hair', 'Hair change');

      engine.resetCategory('hair');
      const current = engine.getProfile();

      expect(current.appearance.hairStyleId).toBe('short02'); // Default masculine hair
      expect(current.appearance.hairColorHex).toBe('#1e293b'); // Default color
      expect(current.face.chinWidth).toBe(0.35); // Face intact!
    });

    it('should reset entire character to defaults when full reset is confirmed', () => {
      engine.updateProfile({
        proportions: { ...engine.getProfile().proportions, heightCm: 200, silhouette: 'broad' },
        face: { ...engine.getProfile().face, restingExpression: 'happy', jawWidth: 0.4 },
        appearance: { ...engine.getProfile().appearance, hairStyleId: 'buzz' }
      }, 'body', 'Complete custom overhaul');

      engine.resetEntireCharacter();
      const reset = engine.getProfile();

      expect(reset.proportions.silhouette).toBe(DEFAULT_AVATAR_PROPORTIONS_MASCULINE.silhouette);
      expect(reset.proportions.heightCm).toBe(DEFAULT_AVATAR_PROPORTIONS_MASCULINE.heightCm);
      expect(reset.face.restingExpression).toBe('neutral');
      expect(reset.appearance.hairStyleId).toBe('short02');
    });
  });

  // ===========================================================================
  // 4. Parameter Mapping to 3D MakeHuman Modifiers
  // ===========================================================================
  describe('4. Parameter Mapping to 3D Geometry Targets', () => {
    it('should map body proportions to real MakeHuman target modifier keys', () => {
      const profile = {
        ...DEFAULT_AVATAR_PROFILE,
        proportions: {
          ...DEFAULT_AVATAR_PROPORTIONS_MASCULINE,
          heightCm: 185,
          shoulderWidth: 0.30,
          waistWidth: -0.15,
          hipWidth: -0.05,
          torsoLength: 0.10,
          neckLength: 0.20,
          chestSize: 0.25,
          armLength: 0.15,
          armThickness: 0.20,
          legLength: 0.12,
          thighThickness: 0.18,
          calfThickness: 0.10,
          footSize: 0.08
        }
      };

      const params = avatarProfileToHumanParams(profile);
      expect(params.modifiers).toBeDefined();

      const mods = params.modifiers!;
      expect(mods['shoulder/shoulder-scale-horiz']).toBe(0.30);
      expect(mods['waist/waist-width']).toBe(-0.15);
      expect(mods['hips/hip-scale-horiz']).toBe(-0.05);
      expect(mods['torso/torso-scale-vert']).toBe(0.10);
      expect(mods['neck/neck-scale-vert']).toBe(0.20);
      expect(mods['breast/breast-volume-vert']).toBe(0.25);
      expect(mods['armslegs/upperarm-scale-horiz']).toBe(0.15);
      expect(mods['armslegs/upperarm-scale-depth']).toBe(0.20);
      expect(mods['armslegs/upperlegs-height']).toBe(0.12);
      expect(mods['armslegs/upperleg-scale-depth']).toBe(0.18);
      expect(mods['armslegs/lowerleg-scale-depth']).toBe(0.10);
      expect(mods['armslegs/foot-scale']).toBe(0.08);
    });

    it('should map facial features to MakeHuman blendshape targets', () => {
      const profile = {
        ...DEFAULT_AVATAR_PROFILE,
        face: {
          ...DEFAULT_AVATAR_PROFILE.face,
          faceWidth: 0.12,
          faceHeight: 0.08,
          foreheadHeight: 0.15,
          jawWidth: 0.25,
          chinWidth: -0.10,
          chinProjection: 0.18,
          cheekFullness: 0.20,
          cheekboneProminence: 0.30,
          noseWidth: 0.05,
          noseLength: -0.10,
          noseBridgeWidth: 0.12,
          nostrilWidth: 0.15,
          upperLipFullness: 0.22,
          lowerLipFullness: 0.18,
          eyeSize: 0.10,
          eyeSpacing: -0.05,
          earSize: -0.12
        }
      };

      const params = avatarProfileToHumanParams(profile);
      const mods = params.modifiers!;

      expect(mods['head/head-scale-horiz']).toBe(0.12);
      expect(mods['head/head-scale-vert']).toBe(0.08);
      expect(mods['forehead/forehead-scale-vert']).toBe(0.15);
      expect(mods['chin/jaw-width']).toBe(0.25);
      expect(mods['chin/chin-width']).toBe(-0.10);
      expect(mods['chin/chin-prominent']).toBe(0.18);
      expect(mods['cheek/cheek-prominence']).toBe(0.20);
      expect(mods['cheek/cheek-bones']).toBe(0.30);
      expect(mods['nose/nose-scale-horiz']).toBe(0.05);
      expect(mods['nose/nose-scale-vert']).toBe(-0.10);
      expect(mods['nose/nose-width1']).toBe(0.12);
      expect(mods['nose/nose-nostrils-width']).toBe(0.15);
      expect(mods['mouth/mouth-upperlip-volume']).toBe(0.22);
      expect(mods['mouth/mouth-lowerlip-volume']).toBe(0.18);
      expect(mods['eyes/eye-scale']).toBe(0.10);
      expect(mods['eyes/eye-trans']).toBe(-0.05);
      expect(mods['ears/ear-scale']).toBe(-0.12);
    });

    it('should map face shape presets to structural morph targets', () => {
      const squareProfile = {
        ...DEFAULT_AVATAR_PROFILE,
        face: { ...DEFAULT_AVATAR_PROFILE.face, faceShapePreset: 'square' as const }
      };
      const squareParams = avatarProfileToHumanParams(squareProfile);
      expect(squareParams.modifiers?.['head/head-square']).toBe(0.75);

      const roundProfile = {
        ...DEFAULT_AVATAR_PROFILE,
        face: { ...DEFAULT_AVATAR_PROFILE.face, faceShapePreset: 'round' as const }
      };
      const roundParams = avatarProfileToHumanParams(roundProfile);
      expect(roundParams.modifiers?.['head/head-round']).toBe(0.75);
    });
  });

  // ===========================================================================
  // 5. Asset Registry & Preset Coverage Validation
  // ===========================================================================
  describe('5. Asset Registry & Slider Integrity', () => {
    it('should contain all 13 Snap-style customization category tabs', () => {
      expect(CATEGORY_TABS.length).toBe(13);
      const tabIds = CATEGORY_TABS.map(t => t.id);
      expect(tabIds).toContain('body');
      expect(tabIds).toContain('face');
      expect(tabIds).toContain('eyes');
      expect(tabIds).toContain('eyebrows');
      expect(tabIds).toContain('nose');
      expect(tabIds).toContain('mouth');
      expect(tabIds).toContain('ears');
      expect(tabIds).toContain('hair');
      expect(tabIds).toContain('facial_hair');
      expect(tabIds).toContain('skin');
      expect(tabIds).toContain('clothing');
      expect(tabIds).toContain('accessories');
      expect(tabIds).toContain('expressions');
    });

    it('should validate that all sliders have valid bounded ranges and defaults', () => {
      Object.entries(AVATAR_SLIDERS).forEach(([category, sliders]) => {
        sliders.forEach(slider => {
          expect(slider.min).toBeLessThan(slider.max);
          expect(slider.step).toBeGreaterThan(0);
          expect(slider.defaultValue).toBeGreaterThanOrEqual(slider.min);
          expect(slider.defaultValue).toBeLessThanOrEqual(slider.max);
          expect(slider.label.length).toBeGreaterThan(0);
          expect(slider.category).toBe(category);
        });
      });
    });

    it('should validate that all presets apply valid profile modifications', () => {
      Object.entries(AVATAR_PRESETS).forEach(([category, presets]) => {
        presets.forEach(preset => {
          expect(preset.name.length).toBeGreaterThan(0);
          expect(preset.category).toBe(category);
          const modified = preset.apply(DEFAULT_AVATAR_PROFILE);
          expect(modified).toBeTypeOf('object');
        });
      });
    });

    it('should provide rich color palettes with valid hex codes', () => {
      const hexRegex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

      expect(HAIR_COLOR_SWATCHES.length).toBeGreaterThanOrEqual(8);
      HAIR_COLOR_SWATCHES.forEach(s => expect(s.hex).toMatch(hexRegex));

      expect(EYE_COLOR_SWATCHES.length).toBeGreaterThanOrEqual(8);
      EYE_COLOR_SWATCHES.forEach(s => expect(s.hex).toMatch(hexRegex));

      expect(LIP_COLOR_SWATCHES.length).toBeGreaterThanOrEqual(6);
      LIP_COLOR_SWATCHES.forEach(s => expect(s.hex).toMatch(hexRegex));
    });
  });

  // ===========================================================================
  // 6. AI Personalization Interface Integration
  // ===========================================================================
  describe('6. AI Personalization Service Interface', () => {
    it('should analyze reference photo and return structured profile recommendations', async () => {
      const result = await aiPersonalizationService.analyzeReferencePhoto({
        imageFileOrBase64: 'data:image/jpeg;base64,...',
        userGenderHint: 'masculine'
      });

      expect(result.detectedFaceShape).toBeDefined();
      expect(result.estimatedSkinToneHex).toMatch(/^#/);
      expect(result.recommendedSkinModel).toBeDefined();
      expect(result.suggestedHairstyleId).toBeDefined();
      expect(result.confidenceScore).toBeGreaterThan(0.7);
    });

    it('should recommend compatible hairstyles for different face shapes', async () => {
      const squareRecs = await aiPersonalizationService.recommendHairstyles('square');
      expect(squareRecs.length).toBeGreaterThan(0);
      expect(squareRecs[0].fashionEditorialReason).toBeDefined();
      expect(squareRecs[0].faceShapeCompatibility).toContain('square');

      const ovalRecs = await aiPersonalizationService.recommendHairstyles('oval');
      expect(ovalRecs.length).toBeGreaterThan(0);
      expect(ovalRecs[0].faceShapeCompatibility).toContain('oval');
    });

    it('should determine seasonal color palette from skin and eye tones', async () => {
      const warmSeason = await aiPersonalizationService.determineColorSeason('#e5b894', 'brown');
      expect(warmSeason.seasonName).toBe('Warm Autumn');
      expect(warmSeason.recommendedMetal).toBe('gold');

      const coolSeason = await aiPersonalizationService.determineColorSeason('#fdf2f0', 'blue');
      expect(coolSeason.seasonName).toBe('Cool Winter');
      expect(coolSeason.recommendedMetal).toBe('silver');
    });

    it('should interpret natural language styling prompts into profile parameter patches', async () => {
      const current = engine.getProfile();
      const intent = await aiPersonalizationService.interpretNaturalLanguageStyling(
        'Make my jaw more chiseled and give me a friendly smile',
        current
      );

      expect(intent.confidence).toBeGreaterThan(0.8);
      expect(intent.parameterChanges.face?.jawWidth).toBeGreaterThan(0);
      expect(intent.explanation).toContain('chiseled');
    });
  });

  // ===========================================================================
  // 7. Identity & Garment Preservation Across Category Changes
  // ===========================================================================
  describe('7. Identity & Garment Preservation', () => {
    it('should preserve equipped garments when hairstyles or facial hair change', () => {
      // Equip bespoke suit
      engine.updateProfile({
        wardrobe: {
          ...engine.getProfile().wardrobe,
          isBareMannequin: false,
          outfitId: 'male_elegantsuit01',
          shoesId: 'shoes01'
        }
      }, 'clothing', 'Equipped tuxedo');

      // Change hairstyle
      engine.updateProfile({
        appearance: { ...engine.getProfile().appearance, hairStyleId: 'mohawk', hairColorHex: '#d6b372' }
      }, 'hair', 'Mohawk hair');

      const profile = engine.getProfile();
      expect(profile.wardrobe.outfitId).toBe('male_elegantsuit01');
      expect(profile.wardrobe.shoesId).toBe('shoes01');
      expect(profile.wardrobe.isBareMannequin).toBe(false);
    });

    it('should maintain base body integrity when undressed to bare mannequin', () => {
      engine.updateProfile({
        wardrobe: {
          ...engine.getProfile().wardrobe,
          isBareMannequin: true,
          outfitId: 'none',
          topId: 'none',
          bottomId: 'none',
          shoesId: 'none'
        }
      }, 'clothing', 'Undress to bare mannequin');

      const profile = engine.getProfile();
      expect(profile.wardrobe.isBareMannequin).toBe(true);

      const params = avatarProfileToHumanParams(profile);
      expect(params.outfit).toBe('none');
      expect(params.top).toBe('none');
      expect(params.bottom).toBe('none');
      // Underwear modesty briefs remain true to preserve continuous base body
      expect(params.underwear).toBe(true);
      // Face and hair are completely intact
      expect(params.hair).toBe(profile.appearance.hairStyleId);
      expect(params.skinTint).toBe(profile.appearance.skinToneHex);
    });
  });
});

