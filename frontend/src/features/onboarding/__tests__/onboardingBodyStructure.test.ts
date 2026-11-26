import { describe, it, expect } from 'vitest';
import { BODY_TYPES, STATURE_PRESETS } from '../OnboardingWizard';

describe('ONBOARDING STEP 3: Visual Body Structure & Stature Presets', () => {
  it('should define all 6 supported visual body archetypes with neutral terminology', () => {
    const ids = BODY_TYPES.map(b => b.id);
    expect(ids).toEqual(['slender', 'athletic', 'regular', 'broad', 'curvy', 'fuller']);

    const names = BODY_TYPES.map(b => b.name);
    expect(names).toEqual(['Slim', 'Athletic', 'Average', 'Broad', 'Curvy', 'Fuller']);

    BODY_TYPES.forEach(bt => {
      expect(bt.tag).toBeTruthy();
      expect(bt.description).toBeTruthy();
      expect(bt.muscleValue).toBeGreaterThanOrEqual(0);
      expect(bt.muscleValue).toBeLessThanOrEqual(1);
      expect(bt.weightValue).toBeGreaterThanOrEqual(0);
      expect(bt.weightValue).toBeLessThanOrEqual(1);
    });
  });

  it('should preserve stature calibration presets independently from body structure', () => {
    expect(STATURE_PRESETS.length).toBe(4);
    const statureIds = STATURE_PRESETS.map(s => s.id);
    expect(statureIds).toEqual(['petite', 'classic', 'studio', 'statuesque']);

    STATURE_PRESETS.forEach(preset => {
      expect(preset.cm).toBeGreaterThanOrEqual(145);
      expect(preset.cm).toBeLessThanOrEqual(210);
      expect(preset.ft).toMatch(/^\d+'\d+"$/);
    });
  });

  it('should ensure each body archetype has distinct anatomical weight or muscle parameters', () => {
    const slim = BODY_TYPES.find(b => b.id === 'slender')!;
    const athletic = BODY_TYPES.find(b => b.id === 'athletic')!;
    const average = BODY_TYPES.find(b => b.id === 'regular')!;
    const broad = BODY_TYPES.find(b => b.id === 'broad')!;
    const curvy = BODY_TYPES.find(b => b.id === 'curvy')!;
    const fuller = BODY_TYPES.find(b => b.id === 'fuller')!;

    // Slim has lower weight than average
    expect(slim.weightValue).toBeLessThan(average.weightValue);

    // Athletic has higher muscle than average
    expect(athletic.muscleValue).toBeGreaterThan(average.muscleValue);

    // Broad has power build with high muscle and solid weight
    expect(broad.muscleValue).toBeGreaterThanOrEqual(0.7);
    expect(broad.weightValue).toBeGreaterThanOrEqual(0.7);

    // Curvy has hourglass weight value
    expect(curvy.weightValue).toBeGreaterThan(average.weightValue);

    // Fuller has generous contours
    expect(fuller.weightValue).toBeGreaterThan(curvy.weightValue);
  });
});

describe('ONBOARDING STEP 2 & 4: Visual Skin Tones & Hair Appearance', () => {
  it('should define all 6 studio skin tones with valid hex codes and undertones', async () => {
    const { SKIN_TONES } = await import('../OnboardingWizard');
    expect(SKIN_TONES.length).toBe(6);
    SKIN_TONES.forEach(tone => {
      expect(tone.id).toBeTruthy();
      expect(tone.name).toBeTruthy();
      expect(tone.hex).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(tone.undertone).toBeTruthy();
      expect(tone.description).toBeTruthy();
    });
  });

  it('should define all 7 studio hair colors with valid hex codes', async () => {
    const { HAIR_COLORS } = await import('../OnboardingWizard');
    expect(HAIR_COLORS.length).toBe(7);
    HAIR_COLORS.forEach(hair => {
      expect(hair.id).toBeTruthy();
      expect(hair.name).toBeTruthy();
      expect(hair.hex).toMatch(/^#[0-9a-fA-F]{6}$/);
    });
  });

  it('should define all 12 studio hairstyles matching reference squircle card catalog', async () => {
    const { HAIR_STYLES } = await import('../OnboardingWizard');
    expect(HAIR_STYLES.length).toBe(12);
    HAIR_STYLES.forEach(style => {
      expect(style.id).toBeTruthy();
      expect(style.name).toBeTruthy();
    });
  });
});
