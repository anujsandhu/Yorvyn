/**
 * YORVYN — AI Outfit Recommendation Engine (Phase 11)
 * Generates coherent, personalized complete outfit ensembles
 * grounded strictly in actual catalog items and digital wardrobe pieces.
 */

import {
  OutfitRecommendation,
  OccasionType,
  ClothingStyle,
  WeatherContext,
  PersonalFashionProfile
} from './types';
import { FashionCatalogItem } from '../../data/fashionCatalogData';
import { Garment, Outfit } from '../../types/fashion';
import { AvatarProfile } from '../../types/avatarProfile';
import { WardrobeRetrievalService } from './WardrobeRetrievalService';
import { ProductDiscoveryAdapter } from './ProductDiscoveryAdapter';
import { ColourCoordinationEngine } from './ColourCoordinationEngine';
import { OutfitCompatibilityValidator } from './OutfitCompatibilityValidator';

export interface OutfitGenerationOptions {
  occasion?: OccasionType;
  style?: ClothingStyle;
  weather?: WeatherContext;
  budgetLimit?: number;
  wardrobeOnly?: boolean;
  avatarProfile?: Partial<AvatarProfile>;
  maxResults?: number;
}

export class OutfitRecommendationEngine {
  private wardrobeService: WardrobeRetrievalService;
  private productAdapter: ProductDiscoveryAdapter;

  constructor(wardrobeService?: WardrobeRetrievalService, productAdapter?: ProductDiscoveryAdapter) {
    this.wardrobeService = wardrobeService || new WardrobeRetrievalService();
    this.productAdapter = productAdapter || new ProductDiscoveryAdapter();
  }

  /**
   * Generates tailored outfit recommendations matching occasion, weather, avatar, and fashion profile.
   */
  public generateOutfits(
    profile: PersonalFashionProfile,
    options: OutfitGenerationOptions = {}
  ): OutfitRecommendation[] {
    const occasion: OccasionType = options.occasion || profile.occasionPreferences[0] || 'casual_day';
    const style: ClothingStyle = options.style || profile.preferredStyles[0] || 'casual';
    const budget = options.budgetLimit || profile.maxPricePerItem * 2.5;
    const weather = options.weather || {
      temperatureCelsius: 22,
      condition: 'mild',
      thermalTier: 'mild'
    };

    const maxResults = options.maxResults || 3;

    // 1. Pool candidate pieces from Wardrobe and Catalog
    const candidateTops: (FashionCatalogItem | Garment)[] = [];
    const candidateBottoms: (FashionCatalogItem | Garment)[] = [];
    const candidateShoes: (FashionCatalogItem | Garment)[] = [];
    const candidateOuterwear: (FashionCatalogItem | Garment)[] = [];

    // Add wardrobe pieces
    this.wardrobeService.getByCategory('top').forEach(t => candidateTops.push(t));
    this.wardrobeService.getByCategory('bottom').forEach(b => candidateBottoms.push(b));
    this.wardrobeService.getByCategory('footwear').forEach(s => candidateShoes.push(s));
    this.wardrobeService.getByCategory('outerwear').forEach(o => candidateOuterwear.push(o));

    // Add catalog pieces (if not restricted to wardrobeOnly)
    if (!options.wardrobeOnly) {
      this.productAdapter.searchProducts('', { category: 'top', maxPrice: budget }).forEach(t => candidateTops.push(t));
      this.productAdapter.searchProducts('', { category: 'bottom', maxPrice: budget }).forEach(b => candidateBottoms.push(b));
      this.productAdapter.searchProducts('', { category: 'shoes', maxPrice: budget }).forEach(s => candidateShoes.push(s));
      this.productAdapter.searchProducts('', { category: 'outerwear', maxPrice: budget }).forEach(o => candidateOuterwear.push(o));
    }

    // Safety fallback: if categories empty, retrieve curated catalog pieces
    if (candidateTops.length === 0) {
      candidateTops.push(...this.productAdapter.searchProducts('', { category: 'top' }));
    }
    if (candidateBottoms.length === 0) {
      candidateBottoms.push(...this.productAdapter.searchProducts('', { category: 'bottom' }));
    }
    if (candidateShoes.length === 0) {
      candidateShoes.push(...this.productAdapter.searchProducts('', { category: 'shoes' }));
    }

    const recommendations: OutfitRecommendation[] = [];

    // Curated combinations targeting occasion & style
    for (let t = 0; t < candidateTops.length; t++) {
      const top = candidateTops[t];
      for (let b = 0; b < candidateBottoms.length; b++) {
        const bottom = candidateBottoms[b];
        for (let s = 0; s < candidateShoes.length; s++) {
          const shoes = candidateShoes[s];

          // Determine if outerwear is needed based on temperature (< 19°C)
          let outerwear: (FashionCatalogItem | Garment) | null = null;
          if (weather.temperatureCelsius < 19 && candidateOuterwear.length > 0) {
            outerwear = candidateOuterwear[0];
          }

          // Evaluate compatibility & avatar proportions
          const compat = OutfitCompatibilityValidator.validateOutfit(
            top,
            bottom,
            shoes,
            outerwear,
            options.avatarProfile
          );

          if (!compat.isValid) continue;

          // Evaluate color harmony
          const colors = [top.color, bottom.color, shoes.color];
          if (outerwear?.color) colors.push(outerwear.color);

          const colorHarm = ColourCoordinationEngine.evaluateHarmony(colors);

          // Calculate match score
          let score = compat.score * 0.4 + colorHarm.harmonyScore * 100 * 0.4;

          // Occasion & Style bonuses
          const topName = top.name.toLowerCase();
          const botName = bottom.name.toLowerCase();

          if (occasion === 'college' || occasion === 'casual_day') {
            if (topName.includes('polo') || topName.includes('shirt') || topName.includes('rugby') || topName.includes('tee')) score += 12;
            if (botName.includes('jeans') || botName.includes('trouser') || botName.includes('pleated')) score += 8;
          } else if (occasion === 'work_office' || occasion === 'interview' || occasion === 'business_formal') {
            if (topName.includes('oxford') || topName.includes('blazer') || topName.includes('suit') || topName.includes('tuxedo')) score += 15;
            if (botName.includes('trouser') || botName.includes('tailored') || botName.includes('pleated')) score += 10;
          } else if (occasion === 'wedding_festive' || occasion === 'gala_evening') {
            if (topName.includes('tuxedo') || topName.includes('silk') || topName.includes('bomber') || topName.includes('kurta')) score += 18;
          } else if (occasion === 'travel_airport') {
            if (topName.includes('knit') || topName.includes('flannel') || topName.includes('polo')) score += 12;
          }

          // Penalize disliked styles or colors
          if (profile.dislikedStyles.includes(style)) score -= 25;
          if (colors.some(c => profile.dislikedColors.includes(c))) score -= 20;

          // Price calculation
          const topPrice = ProductDiscoveryAdapter.parseNumericPrice('priceDisplay' in top ? top.priceDisplay : undefined);
          const botPrice = ProductDiscoveryAdapter.parseNumericPrice('priceDisplay' in bottom ? bottom.priceDisplay : undefined);
          const shoePrice = ProductDiscoveryAdapter.parseNumericPrice('priceDisplay' in shoes ? shoes.priceDisplay : undefined);
          const outerPrice = outerwear ? ProductDiscoveryAdapter.parseNumericPrice('priceDisplay' in outerwear ? outerwear.priceDisplay : undefined) : 0;
          const totalPrice = topPrice + botPrice + shoePrice + outerPrice;

          if (totalPrice > budget && budget > 0) continue;

          // Source breakdown
          const isTopOwned = 'wear_count' in top;
          const isBotOwned = 'wear_count' in bottom;
          const isShoeOwned = 'wear_count' in shoes;
          const ownedCount = (isTopOwned ? 1 : 0) + (isBotOwned ? 1 : 0) + (isShoeOwned ? 1 : 0);
          const catalogCount = 3 - ownedCount + (outerwear && !('wear_count' in outerwear) ? 1 : 0);

          const title = this.generateOutfitTitle(style, occasion, top, bottom);
          const explanation = `${colorHarm.explanation} ${this.formatStylingRationale(occasion, weather, top, bottom, outerwear)}`;

          recommendations.push({
            id: `rec_${occasion}_${recommendations.length + 1}`,
            title,
            occasion,
            style,
            matchScore: Math.min(99, Math.round(score)),
            top,
            bottom,
            footwear: shoes,
            outerwear,
            totalPrice,
            priceDisplay: totalPrice > 0 ? `₹ ${totalPrice.toLocaleString('en-IN')}` : 'Wardrobe Curated',
            currency: 'INR',
            colorHarmony: colorHarm,
            stylingExplanation: explanation,
            avatarFitNotes: compat.avatarFitNotes.join(' '),
            is3DReady: true,
            sourceBreakdown: {
              ownedPieces: ownedCount,
              catalogPieces: catalogCount
            }
          });

          if (recommendations.length >= maxResults * 2) break;
        }
        if (recommendations.length >= maxResults * 2) break;
      }
      if (recommendations.length >= maxResults * 2) break;
    }

    // Sort by match score descending
    recommendations.sort((a, b) => b.matchScore - a.matchScore);
    return recommendations.slice(0, maxResults);
  }

  private generateOutfitTitle(style: ClothingStyle, occasion: OccasionType, _top: FashionCatalogItem | Garment, _bottom: FashionCatalogItem | Garment): string {
    const styleLabel = style.charAt(0).toUpperCase() + style.slice(1).replace('_', ' ');
    const occasionMap: Record<OccasionType, string> = {
      casual_day: 'Everyday Ease',
      college: 'Campus Sartorial',
      work_office: 'Executive Minimalist',
      business_formal: 'Boardroom Precision',
      interview: 'Polished First Impression',
      gala_evening: 'Soirée Elegance',
      party_night: 'Nightlife Statement',
      wedding_festive: 'Festive Haute',
      date_night: 'Intimate Sophistication',
      gym_sport: 'Technical Performance',
      travel_airport: 'Transit Luxury',
      weekend_brunch: 'Leisurely Atelier'
    };

    return `${styleLabel} ${occasionMap[occasion] || 'Ensemble'}`;
  }

  private formatStylingRationale(
    occasion: OccasionType,
    weather: WeatherContext,
    top: FashionCatalogItem | Garment,
    bottom: FashionCatalogItem | Garment,
    outerwear?: (FashionCatalogItem | Garment) | null
  ): string {
    let rationale = `Pairing ${top.name} with ${bottom.name} creates a structured, proportioned silhouette tailored for ${occasion.replace('_', ' ')}.`;
    if (weather.temperatureCelsius < 19 && outerwear) {
      rationale += ` Layered with ${outerwear.name} to provide thermal comfort for ${weather.temperatureCelsius}°C conditions.`;
    }
    return rationale;
  }

  /**
   * Converts OutfitRecommendation into legacy Outfit schema for backward compatibility.
   */
  public static toLegacyOutfit(rec: OutfitRecommendation): Outfit {
    return {
      outfit_id: rec.id,
      title: rec.title,
      match_score: rec.matchScore / 100,
      layer_breakdown: {
        top: rec.top as any,
        bottom: rec.bottom as any,
        footwear: rec.footwear as any,
        outerwear: (rec.outerwear as any) || null,
        accessory: (rec.accessory as any) || null
      },
      color_palette: rec.colorHarmony.palette,
      color_harmony_explanation: rec.colorHarmony.explanation,
      styling_rationale: rec.stylingExplanation,
      score_breakdown: {
        total_score: rec.matchScore,
        weather_score: 95,
        occasion_score: 95,
        color_score: Math.round(rec.colorHarmony.harmonyScore * 100),
        profile_score: 90,
        aesthetic_score: 92,
        rationale: rec.stylingExplanation
      }
    };
  }
}
