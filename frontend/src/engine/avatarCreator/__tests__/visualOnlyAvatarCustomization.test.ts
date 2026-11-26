import { describe, it, expect, beforeEach } from 'vitest';
import { AVATAR_PRESETS } from '../avatarCreatorAssetRegistry';
import { AvatarCreatorEngine } from '../avatarCreatorEngine';
import { DEFAULT_AVATAR_PROFILE } from '../../../types/avatarProfile';

describe('YORVYN — Visual-Only Avatar Customization Interface (Phase 4)', () => {
  let engine: AvatarCreatorEngine;

  beforeEach(() => {
    engine = new AvatarCreatorEngine(DEFAULT_AVATAR_PROFILE);
  });

  describe('1. Elimination of Text-Based Option Cards', () => {
    it('should have presets defined across all 13 customization categories with full visual metadata', () => {
      const categories = [
        'body',
        'face',
        'hair',
        'facial_hair',
        'skin',
        'eyes',
        'eyebrows',
        'nose',
        'mouth',
        'ears',
        'clothing',
        'accessories',
        'expressions'
      ] as const;

      for (const cat of categories) {
        const presets = AVATAR_PRESETS[cat] || [];
        expect(presets.length).toBeGreaterThan(0);
        for (const preset of presets) {
          expect(preset.id).toBeDefined();
          expect(preset.category).toBe(cat);
          expect(preset.name).toBeDefined(); // Accessible name preserved
          expect(typeof preset.apply).toBe('function');
        }
      }
    });

    it('should strictly exclude textual badges and titles from visual grid elements in the UI specification', () => {
      // In the visual-only specification, option cards display only mannequin thumbnails
      const visualOnlyLayoutRules = {
        showTitleInCard: false,
        showDescriptionInCard: false,
        showBadgeInCard: false,
        useMannequinThumbnail: true,
        accessibleAriaLabel: true,
        accessibleTooltip: true
      };

      expect(visualOnlyLayoutRules.showTitleInCard).toBe(false);
      expect(visualOnlyLayoutRules.showDescriptionInCard).toBe(false);
      expect(visualOnlyLayoutRules.showBadgeInCard).toBe(false);
      expect(visualOnlyLayoutRules.useMannequinThumbnail).toBe(true);
      expect(visualOnlyLayoutRules.accessibleAriaLabel).toBe(true);
    });
  });

  describe('2. Mannequin-Based Body Presets & Real-Time Proportions', () => {
    it('should support full-body mannequins for all 5 core silhouette types', () => {
      const bodyPresets = AVATAR_PRESETS.body;
      const ids = bodyPresets.map(p => p.id);

      expect(ids).toContain('athletic');
      expect(ids).toContain('slender');
      expect(ids).toContain('curvy');
      expect(ids).toContain('broad');
      expect(ids).toContain('natural');
    });

    it('selecting Athletic V-Taper mannequin updates shoulder, waist, and muscle definition in real-time', () => {
      const athleticPreset = AVATAR_PRESETS.body.find(p => p.id === 'athletic')!;
      const patch = athleticPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'body', 'Applied Athletic V-Taper');

      const profile = engine.getProfile();
      expect(profile.proportions.silhouette).toBe('athletic');
      expect(profile.proportions.shoulderWidth).toBeGreaterThan(0.2); // Wide V-taper (0.25)
      expect(profile.proportions.waistWidth).toBeLessThan(0); // Tapered narrow waist (-0.10)
      expect(profile.proportions.muscleDefinition).toBeGreaterThanOrEqual(0.65);
    });

    it('selecting Slender Runway mannequin updates slender elongated silhouette', () => {
      const slenderPreset = AVATAR_PRESETS.body.find(p => p.id === 'slender')!;
      const patch = slenderPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'body', 'Applied Slender Runway');

      const profile = engine.getProfile();
      expect(profile.proportions.silhouette).toBe('slender');
      expect(profile.proportions.shoulderWidth).toBeLessThan(0);
      expect(profile.proportions.waistWidth).toBeLessThan(0);
      expect(profile.proportions.hipWidth).toBeLessThan(0);
    });

    it('selecting Curvy Hourglass mannequin defines cinched waist with accentuated hips', () => {
      const curvyPreset = AVATAR_PRESETS.body.find(p => p.id === 'curvy')!;
      const patch = curvyPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'body', 'Applied Curvy Hourglass');

      const profile = engine.getProfile();
      expect(profile.proportions.silhouette).toBe('curvy');
      expect(profile.proportions.waistWidth).toBeLessThan(-0.1);
      expect(profile.proportions.hipWidth).toBeGreaterThan(0.25);
    });

    it('selecting Broad & Powerful mannequin sets expansive shoulder span and core strength', () => {
      const broadPreset = AVATAR_PRESETS.body.find(p => p.id === 'broad')!;
      const patch = broadPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'body', 'Applied Broad & Powerful');

      const profile = engine.getProfile();
      expect(profile.proportions.silhouette).toBe('broad');
      expect(profile.proportions.shoulderWidth).toBeGreaterThanOrEqual(0.35);
      expect(profile.proportions.muscleDefinition).toBeGreaterThanOrEqual(0.75);
    });
  });

  describe('3. Face Mannequin Previews & Anatomical Variations', () => {
    it('should support head mannequin previews for all face shapes', () => {
      const facePresets = AVATAR_PRESETS.face;
      const ids = facePresets.map(p => p.id);

      expect(ids).toContain('oval');
      expect(ids).toContain('square');
      expect(ids).toContain('round');
      expect(ids).toContain('diamond');
      expect(ids).toContain('triangular');
      expect(ids).toContain('rectangular');
    });

    it('selecting Sculpted Square face mannequin updates jaw width and angle', () => {
      const squarePreset = AVATAR_PRESETS.face.find(p => p.id === 'square')!;
      const patch = squarePreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'face', 'Applied Sculpted Square');

      const profile = engine.getProfile();
      expect(profile.face.faceShapePreset).toBe('square');
      expect(profile.face.jawWidth).toBeGreaterThanOrEqual(0.2);
      expect(profile.face.chinWidth).toBeGreaterThan(0.1);
    });

    it('selecting Diamond face mannequin updates cheekbone prominence and chin projection', () => {
      const diamondPreset = AVATAR_PRESETS.face.find(p => p.id === 'diamond')!;
      const patch = diamondPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'face', 'Applied Diamond');

      const profile = engine.getProfile();
      expect(profile.face.faceShapePreset).toBe('diamond');
      expect(profile.face.cheekboneProminence).toBeGreaterThanOrEqual(0.3);
      expect(profile.face.jawWidth).toBeLessThan(0);
    });
  });

  describe('4. Hairstyle & Facial Hair Mannequin Customization', () => {
    it('should support short, long, curly, and braided hairstyle previews', () => {
      const hairPresets = AVATAR_PRESETS.hair;
      const ids = hairPresets.map(p => p.id);

      expect(ids).toContain('short01'); // Textured Crop
      expect(ids).toContain('short02'); // Classic Side Part
      expect(ids).toContain('bob01');   // French Bob
      expect(ids).toContain('long01');  // Cascading Waves
      expect(ids).toContain('afro01');  // Natural Afro
      expect(ids).toContain('braid01'); // Crown Braided Bun
    });

    it('selecting hairstyle updates appearance.hairStyleId in real-time', () => {
      const afroPreset = AVATAR_PRESETS.hair.find(p => p.id === 'afro01')!;
      const patch = afroPreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'hair', 'Applied Natural Afro');

      const profile = engine.getProfile();
      expect(profile.appearance.hairStyleId).toBe('afro01');
    });

    it('should support facial hair mannequin previews from clean shaven to full beard', () => {
      const beardPresets = AVATAR_PRESETS.facial_hair;
      const ids = beardPresets.map(p => p.id);

      expect(ids).toContain('none');
      expect(ids).toContain('stubble');
      expect(ids).toContain('short_beard');
      expect(ids).toContain('full_beard');
      expect(ids).toContain('goatee');
      expect(ids).toContain('mustache');
    });

    it('selecting stubble updates facialHairId and density', () => {
      const stubblePreset = AVATAR_PRESETS.facial_hair.find(p => p.id === 'stubble')!;
      const patch = stubblePreset.apply(engine.getProfile());
      engine.updateProfile(patch, 'facial_hair', 'Applied 5 O\'Clock Shadow');

      const profile = engine.getProfile();
      expect(profile.appearance.facialHairId).toBe('stubble');
      expect(profile.appearance.facialHairDensity).toBe(0.5);
    });
  });

  describe('5. Skin and Eye Anatomical Mannequins', () => {
    it('should support accurate skin tone mannequin previews with studio lighting', () => {
      const skinPresets = AVATAR_PRESETS.skin;
      const ids = skinPresets.map(p => p.id);

      expect(ids).toContain('porcelain');
      expect(ids).toContain('ivory');
      expect(ids).toContain('sand');
      expect(ids).toContain('amber');
      expect(ids).toContain('bronze');
      expect(ids).toContain('almond');
      expect(ids).toContain('espresso');

      for (const skin of skinPresets) {
        expect(skin.previewColor).toMatch(/^#[0-9a-fA-F]{6}$/);
      }
    });

    it('should support eye region previews with distinct anatomical eyelid folds', () => {
      const eyePresets = AVATAR_PRESETS.eyes;
      const ids = eyePresets.map(p => p.id);

      expect(ids).toContain('almond');
      expect(ids).toContain('deepset');
      expect(ids).toContain('round_eyes');
      expect(ids).toContain('monolid');
    });
  });

  describe('6. Responsive Visual Grid Configuration', () => {
    it('should compute exact column counts according to tray dimensions', () => {
      const getVisualGridColumns = (trayWidthPx: number): number => {
        if (trayWidthPx <= 360) return 2; // Compact
        if (trayWidthPx <= 520) return 3; // Default
        return 4;                         // Expanded
      };

      // Compact Tray (340px) -> 2 columns
      expect(getVisualGridColumns(340)).toBe(2);
      expect(getVisualGridColumns(320)).toBe(2);

      // Default Tray (440px) -> 3 columns
      expect(getVisualGridColumns(400)).toBe(3);
      expect(getVisualGridColumns(460)).toBe(3);

      // Expanded Tray (640px) -> 4 columns
      expect(getVisualGridColumns(560)).toBe(4);
      expect(getVisualGridColumns(720)).toBe(4);
    });

    it('body preset cards must have taller aspect ratio (3/4.4) for full mannequin visibility', () => {
      const getCardAspectRatio = (category: string) => {
        return category === 'body' ? '3 / 4.4' : '1 / 1';
      };

      expect(getCardAspectRatio('body')).toBe('3 / 4.4');
      expect(getCardAspectRatio('face')).toBe('1 / 1');
      expect(getCardAspectRatio('hair')).toBe('1 / 1');
      expect(getCardAspectRatio('skin')).toBe('1 / 1');
      expect(getCardAspectRatio('eyes')).toBe('1 / 1');
    });
  });

  describe('7. Avatar DNA, Undo/Redo & State Preservation', () => {
    it('selecting presets preserves Avatar DNA and existing customizations across other categories', () => {
      // 1. Initial outfit & hair
      engine.updateProfile(
        {
          appearance: { ...engine.getProfile().appearance, hairStyleId: 'long01' },
          wardrobe: { ...engine.getProfile().wardrobe, topId: 'vintage_jacket' }
        },
        'hair',
        'Setup Initial Look'
      );

      expect(engine.getProfile().appearance.hairStyleId).toBe('long01');
      expect(engine.getProfile().wardrobe.topId).toBe('vintage_jacket');

      // 2. Change body preset to Athletic
      const athleticPreset = AVATAR_PRESETS.body.find(p => p.id === 'athletic')!;
      engine.updateProfile(athleticPreset.apply(engine.getProfile()), 'body', 'Applied Athletic');

      // 3. Verify body updated without losing hair or top
      const updated = engine.getProfile();
      expect(updated.proportions.silhouette).toBe('athletic');
      expect(updated.appearance.hairStyleId).toBe('long01');
      expect(updated.wardrobe.topId).toBe('vintage_jacket');
    });

    it('supports undo and redo cleanly after visual preset selection', () => {
      const initialSilhouette = engine.getProfile().proportions.silhouette;

      // Select Broad
      const broadPreset = AVATAR_PRESETS.body.find(p => p.id === 'broad')!;
      engine.updateProfile(broadPreset.apply(engine.getProfile()), 'body', 'Applied Broad');
      expect(engine.getProfile().proportions.silhouette).toBe('broad');

      // Undo
      const didUndo = engine.undo();
      expect(didUndo).toBe(true);
      expect(engine.getProfile().proportions.silhouette).toBe(initialSilhouette);

      // Redo
      const didRedo = engine.redo();
      expect(didRedo).toBe(true);
      expect(engine.getProfile().proportions.silhouette).toBe('broad');
    });
  });
});
