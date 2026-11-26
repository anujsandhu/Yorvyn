/**
 * YORVYN — Avatar Recommendation Engine (Phase 8)
 * 
 * Generates holistic, occasion-based appearance recommendations connecting
 * the 3D avatar with the digital wardrobe, seasonal color analysis, and AI stylist.
 */

import { AvatarProfile } from '../../types/avatarProfile';
import { OccasionStylingProposal, AvatarCustomizationProposal } from './avatarAITypes';

export interface OccasionContext {
  occasion: string;
  temperatureCelsius?: number;
  condition?: string;
  targetAesthetic?: string;
}

export class AvatarRecommendationEngine {
  /**
   * Generates a complete occasion styling proposal (outfit + hairstyle + expression + color palette).
   */
  public static recommendForOccasion(
    context: OccasionContext,
    profile: AvatarProfile
  ): OccasionStylingProposal {
    const occ = (context.occasion || 'casual').toLowerCase();
    const isMasc = profile.genderPresentation !== 'feminine';
    const temp = context.temperatureCelsius ?? 20;

    // 1. Determine Seasonal Color Palette from Avatar Appearance
    const season = this.getAvatarColorSeason(profile.appearance.skinToneHex, profile.appearance.eyeColorId);

    // 2. Occasion & Weather Matrix
    if (occ.includes('formal') || occ.includes('black tie') || occ.includes('keynote') || occ.includes('wedding')) {
      return {
        occasionId: 'formal_evening',
        occasionTitle: 'Black-Tie Gala & Executive Keynote',
        weatherContext: temp < 15 ? 'Cool evening — structured formal layers' : 'Mild climate — breathable wool ensemble',
        paletteName: season.name,
        paletteHexes: season.palette,
        recommendedOutfit: {
          outfitId: isMasc ? 'male_elegantsuit01' : 'female_casualsuit01',
          shoesId: isMasc ? 'shoes01' : 'shoes02',
          name: isMasc ? 'Bespoke Satin Lapel Tuxedo' : 'Haute Couture Tailored Evening Suit',
          editorialReason: 'Uncompromising sartorial elegance tailored to your avatar proportions with high-contrast peak lapels.'
        },
        recommendedHairstyleId: isMasc ? 'short02' : 'bob01',
        recommendedExpression: 'confident'
      };
    }

    if (occ.includes('techwear') || occ.includes('street') || occ.includes('urban') || occ.includes('night')) {
      return {
        occasionId: 'urban_streetwear',
        occasionTitle: 'Cyberpunk Metropolis Techwear',
        weatherContext: 'Weather-resistant technical outerwear with sealed seams',
        paletteName: 'Monochrome Cybernetic',
        paletteHexes: ['#0f172a', '#334155', '#64748b', '#00e5ff'],
        recommendedOutfit: {
          topId: 'techwear_jacket',
          bottomId: 'techwear_pants',
          shoesId: 'shoes04',
          name: 'Modular Hooded Windbreaker & Tactical Trousers',
          editorialReason: 'Contemporary street silhouette with ergonomic mobility and futuristic athletic proportions.'
        },
        recommendedHairstyleId: isMasc ? 'short01' : 'bob02',
        recommendedExpression: 'confident'
      };
    }

    if (occ.includes('summer') || occ.includes('beach') || occ.includes('vacation') || temp > 25) {
      return {
        occasionId: 'summer_resort',
        occasionTitle: 'Mediterranean Riviera Resort',
        weatherContext: `Warm weather (${temp}°C) — airy natural fibers`,
        paletteName: 'Warm Sunlit Sand',
        paletteHexes: ['#f8fafc', '#d6b372', '#ca8a04', '#0284c7'],
        recommendedOutfit: {
          topId: 'tank_top',
          bottomId: 'trousers',
          shoesId: 'sandals',
          name: 'Sleeveless Linen Tank & Relaxed Trousers',
          editorialReason: 'Lightweight fluid draping that allows freedom of movement in warm climates.'
        },
        recommendedHairstyleId: isMasc ? 'short04' : 'ponytail01',
        recommendedExpression: 'relaxed'
      };
    }

    if (occ.includes('sport') || occ.includes('gym') || occ.includes('workout') || occ.includes('athletic')) {
      return {
        occasionId: 'athletic_performance',
        occasionTitle: 'High-Performance Active Athletic',
        weatherContext: 'Moisture-wicking breathable composite textiles',
        paletteName: 'Electric Athletic',
        paletteHexes: ['#0f172a', '#2563eb', '#38bdf8', '#f8fafc'],
        recommendedOutfit: {
          outfitId: isMasc ? 'male_casualsuit04' : 'female_sportsuit01',
          shoesId: 'shoes04',
          name: 'Ergonomic Technical Tracksuit & Runners',
          editorialReason: 'Tailored to highlight your avatar’s athletic muscle definition.'
        },
        recommendedHairstyleId: isMasc ? 'short04' : 'ponytail01',
        recommendedExpression: 'excited'
      };
    }

    // Default: Smart Everyday Atelier Casual
    return {
      occasionId: 'smart_casual',
      occasionTitle: 'Atelier Smart Casual Signature',
      weatherContext: `Moderate climate (${temp}°C) — versatile layering`,
      paletteName: season.name,
      paletteHexes: season.palette,
      recommendedOutfit: {
        outfitId: isMasc ? 'male_casualsuit02' : 'female_casualsuit02',
        shoesId: isMasc ? 'shoes05' : 'shoes01',
        name: 'Structured Blazer & Chinos with Handcrafted Loafers',
        editorialReason: 'Effortless quiet luxury styling suitable for both creative office days and evening dinners.'
      },
      recommendedHairstyleId: isMasc ? 'short01' : 'bob01',
      recommendedExpression: 'smile'
    };
  }

  /**
   * Converts an OccasionStylingProposal into a live Avatar DNA Proposal for 3D preview.
   */
  public static proposalToAvatarDNA(
    occasionProposal: OccasionStylingProposal,
    current: AvatarProfile
  ): AvatarCustomizationProposal {
    const o = occasionProposal.recommendedOutfit;
    const isSuit = Boolean(o.outfitId && o.outfitId !== 'none');

    return {
      id: `occ_prop_${Date.now()}`,
      title: occasionProposal.occasionTitle,
      summary: o.name,
      category: 'clothing',
      confidence: 0.95,
      operations: [
        ...(isSuit ? [{
          action: 'set_garment' as const,
          category: 'clothing' as const,
          targetKey: 'outfitId',
          targetValue: o.outfitId,
          displayLabel: o.name
        }] : [
          { action: 'set_garment' as const, category: 'clothing' as const, targetKey: 'topId', targetValue: o.topId, displayLabel: 'Top' },
          { action: 'set_garment' as const, category: 'clothing' as const, targetKey: 'bottomId', targetValue: o.bottomId, displayLabel: 'Bottom' }
        ]),
        {
          action: 'set_garment',
          category: 'clothing',
          targetKey: 'shoesId',
          targetValue: o.shoesId || 'shoes01',
          displayLabel: 'Footwear'
        },
        ...(occasionProposal.recommendedHairstyleId ? [{
          action: 'set_preset' as const,
          category: 'hair' as const,
          targetKey: 'hairStyleId',
          targetValue: occasionProposal.recommendedHairstyleId,
          displayLabel: 'Coordinated Hairstyle'
        }] : [])
      ],
      profilePatch: {
        face: {
          ...current.face,
          restingExpression: (occasionProposal.recommendedExpression as any) || current.face.restingExpression
        },
        appearance: {
          ...current.appearance,
          hairStyleId: occasionProposal.recommendedHairstyleId || current.appearance.hairStyleId
        },
        wardrobe: {
          ...current.wardrobe,
          isBareMannequin: false,
          outfitId: isSuit ? o.outfitId! : 'none',
          topId: isSuit ? 'none' : (o.topId || 'none'),
          bottomId: isSuit ? 'none' : (o.bottomId || 'none'),
          shoesId: o.shoesId || 'shoes01'
        }
      },
      explanation: o.editorialReason,
      createdAt: new Date().toISOString(),
      source: 'occasion',
      status: 'pending'
    };
  }

  /**
   * Determines color season from skin and eyes.
   */
  public static getAvatarColorSeason(skinHex = '#f3c299', eyeColorId = 'brownlight'): { name: string; palette: string[] } {
    const isWarm = skinHex.includes('e') || skinHex.includes('b') || eyeColorId.includes('brown');
    const isDark = skinHex.startsWith('#1') || skinHex.startsWith('#2') || skinHex.startsWith('#3') || skinHex.startsWith('#4');

    if (isWarm && isDark) {
      return {
        name: 'Warm Autumn',
        palette: ['#873a1d', '#d6b372', '#4d3221', '#15803d', '#9a3412']
      };
    } else if (isWarm && !isDark) {
      return {
        name: 'Fresh Spring',
        palette: ['#e07a68', '#facc15', '#0284c7', '#10b981', '#f8fafc']
      };
    } else if (!isWarm && isDark) {
      return {
        name: 'Cool Winter',
        palette: ['#0f172a', '#1e3a8a', '#881337', '#cbd5e1', '#00e5ff']
      };
    } else {
      return {
        name: 'Soft Summer',
        palette: ['#64748b', '#a855f7', '#0d9488', '#f43f5e', '#e2e8f0']
      };
    }
  }
}
