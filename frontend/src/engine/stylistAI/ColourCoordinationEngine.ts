/**
 * YORVYN — Colour Coordination & Style Harmony Engine (Phase 11)
 * Analyzes color relationships, luminance contrast, pattern balance,
 * and fabric compatibility between outfit pieces.
 */

import { ColorHarmonyResult } from './types';

interface HSL {
  h: number; // 0 - 360
  s: number; // 0 - 100
  l: number; // 0 - 100
}

export class ColourCoordinationEngine {
  /**
   * Evaluates the color harmony of a set of hex colors.
   */
  public static evaluateHarmony(colors: string[]): ColorHarmonyResult {
    const validColors = colors.filter(c => /^#([0-9A-Fa-f]{3}){1,2}$/.test(c));
    if (validColors.length === 0) {
      return {
        scheme: 'neutral',
        harmonyScore: 0.85,
        explanation: 'Clean, understated neutral palette.',
        palette: ['#1e293b', '#ffffff']
      };
    }

    const hslList = validColors.map(c => this.hexToHsl(c));

    // 1. Check if all colors are neutrals (very low saturation or near-black/near-white)
    const isAllNeutral = hslList.every(hsl => hsl.s < 18 || hsl.l < 15 || hsl.l > 88);
    if (isAllNeutral) {
      const minL = Math.min(...hslList.map(h => h.l));
      const maxL = Math.max(...hslList.map(h => h.l));
      const contrast = maxL - minL;

      if (contrast > 45) {
        return {
          scheme: 'high_contrast',
          harmonyScore: 0.96,
          explanation: 'Crisp architectural contrast balancing light and deep neutral tones.',
          palette: validColors
        };
      }
      return {
        scheme: 'neutral',
        harmonyScore: 0.92,
        explanation: 'Understated quiet luxury neutral palette with subtle tonal transitions.',
        palette: validColors
      };
    }

    // 2. Check for Monochromatic (similar hues within 25 degrees)
    const saturatedHues = hslList.filter(hsl => hsl.s >= 18).map(hsl => hsl.h);
    if (saturatedHues.length <= 1) {
      return {
        scheme: 'monochromatic',
        harmonyScore: 0.90,
        explanation: 'Sophisticated monochromatic ensemble anchored by a dominant tonal statement.',
        palette: validColors
      };
    }

    const hueSpread = Math.max(...saturatedHues) - Math.min(...saturatedHues);
    if (hueSpread <= 25) {
      return {
        scheme: 'monochromatic',
        harmonyScore: 0.94,
        explanation: 'Harmonious tonal monochromatic palette creating visual height and cohesion.',
        palette: validColors
      };
    }

    // 3. Check for Complementary (hues ~160° to 200° apart)
    if (saturatedHues.length === 2) {
      const diff = Math.abs(saturatedHues[0] - saturatedHues[1]);
      const circularDiff = Math.min(diff, 360 - diff);
      if (circularDiff >= 150 && circularDiff <= 210) {
        return {
          scheme: 'complementary',
          harmonyScore: 0.95,
          explanation: 'Dynamic complementary harmony pairing opposing spectrum hues for bold presence.',
          palette: validColors
        };
      }
      if (circularDiff <= 60) {
        return {
          scheme: 'analogous',
          harmonyScore: 0.91,
          explanation: 'Serene analogous harmony using adjacent color spectrums for smooth visual flow.',
          palette: validColors
        };
      }
    }

    // Fallback: Balanced versatile harmony
    return {
      scheme: 'high_contrast',
      harmonyScore: 0.88,
      explanation: 'Balanced palette pairing focused accent colors with grounded anchoring tones.',
      palette: validColors
    };
  }

  /**
   * Evaluates pattern coordination between pieces to avoid clashing prints.
   */
  public static evaluatePatternCompatibility(patterns: string[]): {
    isCompatible: boolean;
    score: number;
    notes: string;
  } {
    const boldPatterns = patterns.filter(p =>
      ['plaid', 'floral', 'graphic', 'striped', 'geometric'].includes(p.toLowerCase())
    );

    if (boldPatterns.length <= 1) {
      return {
        isCompatible: true,
        score: 0.95,
        notes: 'Clean pattern balance: one statement piece grounded by solid foundations.'
      };
    }

    if (boldPatterns.length === 2 && boldPatterns.includes('striped') && boldPatterns.includes('plaid')) {
      return {
        isCompatible: false,
        score: 0.50,
        notes: 'Pattern clash warning: competing geometric stripes and plaid may overwhelm the silhouette.'
      };
    }

    return {
      isCompatible: true,
      score: 0.80,
      notes: 'Subtle mixed textures curated for contemporary dimension.'
    };
  }

  /**
   * Converts Hex to HSL color space.
   */
  private static hexToHsl(hex: string): HSL {
    let clean = hex.replace('#', '');
    if (clean.length === 3) {
      clean = clean.split('').map(c => c + c).join('');
    }
    const r = parseInt(clean.substring(0, 2), 16) / 255;
    const g = parseInt(clean.substring(2, 4), 16) / 255;
    const b = parseInt(clean.substring(4, 6), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    let s = 0;
    const l = (max + min) / 2;

    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
        case g: h = (b - r) / d + 2; break;
        case b: h = (r - g) / d + 4; break;
      }
      h /= 6;
    }

    return {
      h: Math.round(h * 360),
      s: Math.round(s * 100),
      l: Math.round(l * 100)
    };
  }
}
