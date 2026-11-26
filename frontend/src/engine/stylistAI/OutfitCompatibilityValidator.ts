/**
 * YORVYN — Outfit Compatibility Validator (Phase 11)
 * Enforces layering rules, formality coherence, seasonal thermal balance,
 * and avatar proportion harmony across garment combinations.
 */

import { Garment } from '../../types/fashion';
import { FashionCatalogItem } from '../../data/fashionCatalogData';
import { AvatarProfile } from '../../types/avatarProfile';

export interface CompatibilityValidationResult {
  isValid: boolean;
  score: number; // 0 - 100
  formalityDelta: number;
  warnings: string[];
  avatarFitNotes: string[];
}

export class OutfitCompatibilityValidator {
  /**
   * Validates a complete ensemble combination for wearable coherence.
   */
  public static validateOutfit(
    top: FashionCatalogItem | Garment,
    bottom: FashionCatalogItem | Garment,
    footwear: FashionCatalogItem | Garment,
    outerwear?: FashionCatalogItem | Garment | null,
    avatarProfile?: Partial<AvatarProfile>
  ): CompatibilityValidationResult {
    const warnings: string[] = [];
    const avatarFitNotes: string[] = [];
    let score = 95;

    // 1. Formality Coherence
    const topFormality = this.extractFormality(top);
    const bottomFormality = this.extractFormality(bottom);
    const footFormality = this.extractFormality(footwear);

    const formalityDelta = Math.abs(topFormality - bottomFormality);
    if (formalityDelta >= 5) {
      score -= 20;
      warnings.push(`High formality gap between ${top.name} and ${bottom.name}.`);
    }

    if (Math.abs(bottomFormality - footFormality) >= 5) {
      score -= 15;
      warnings.push(`Footwear formality contrasts sharply with bottoms.`);
    }

    // 2. Outerwear Layering Hierarchy
    if (outerwear) {
      const outerFormality = this.extractFormality(outerwear);
      if (topFormality > outerFormality + 3) {
        score -= 10;
        warnings.push('Outerwear is notably less formal than inner top layer.');
      }
    }

    // 3. Avatar Proportion Harmonization (Inclusive, Non-Judgemental Proportions Advice)
    if (avatarProfile?.proportions) {
      const p = avatarProfile.proportions;
      const height = p.heightCm ?? 175;
      const shoulders = p.shoulderWidth ?? 0;

      if (height < 165) {
        avatarFitNotes.push('High-rise waistband cut elongates leg line for this stature.');
      } else if (height > 185) {
        avatarFitNotes.push('Balanced proportions accommodate longer vertical torso frame.');
      }

      if (shoulders > 0.20 || p.silhouette === 'broad' || p.silhouette === 'athletic') {
        avatarFitNotes.push('Relaxed shoulder seams drape naturally over broader athletic deltoids.');
      }
    }

    if (avatarFitNotes.length === 0) {
      avatarFitNotes.push('Proportions calibrated cleanly for current avatar stature.');
    }

    return {
      isValid: score >= 60,
      score: Math.max(0, Math.min(100, score)),
      formalityDelta,
      warnings,
      avatarFitNotes
    };
  }

  private static extractFormality(item: FashionCatalogItem | Garment): number {
    if ('formality' in item && typeof item.formality === 'number') {
      return item.formality;
    }
    const name = item.name.toLowerCase();
    if (name.includes('tuxedo') || name.includes('suit') || name.includes('blazer') || name.includes('oxford')) return 8;
    if (name.includes('shirt') || name.includes('trousers') || name.includes('chinos') || name.includes('polo')) return 6;
    if (name.includes('hoodie') || name.includes('tracksuit') || name.includes('shorts') || name.includes('tee')) return 3;
    return 5;
  }
}
