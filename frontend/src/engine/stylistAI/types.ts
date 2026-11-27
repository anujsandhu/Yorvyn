/**
 * YORVYN — AI Fashion Stylist & Personal Shopping Intelligence (Phase 11)
 * Data contracts, schemas, and type definitions for fashion profiles,
 * recommendations, color harmony, and conversational intelligence.
 */

import { Garment } from '../../types/fashion';
import { FashionCatalogItem } from '../../data/fashionCatalogData';
import { HumanParams } from '../ara/core/params';

export type ClothingStyle =
  | 'casual'
  | 'formal'
  | 'business'
  | 'streetwear'
  | 'minimalist'
  | 'festive'
  | 'sportswear'
  | 'vintage'
  | 'quiet_luxury';

export type OccasionType =
  | 'casual_day'
  | 'college'
  | 'work_office'
  | 'business_formal'
  | 'interview'
  | 'gala_evening'
  | 'party_night'
  | 'wedding_festive'
  | 'date_night'
  | 'gym_sport'
  | 'travel_airport'
  | 'weekend_brunch';

export type FitPreference = 'slim' | 'regular' | 'relaxed' | 'oversized';

export type BudgetTier = 'budget' | 'mid_premium' | 'luxury';

export type DislikeReason =
  | 'too_formal'
  | 'too_casual'
  | 'color_mismatch'
  | 'unflattering_fit'
  | 'over_budget'
  | 'disliked_brand'
  | 'weather_inappropriate';

export interface FashionFeedbackRecord {
  id: string;
  outfitId: string;
  timestamp: string;
  action: 'like' | 'dislike' | 'save' | 'wear_today' | 'replace_item';
  dislikeReason?: DislikeReason;
  note?: string;
  replacedItemSlot?: 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory';
  replacedWithItemId?: string;
}

export interface PersonalFashionProfile {
  userId: string;
  preferredStyles: ClothingStyle[];
  favoriteColors: string[];
  preferredFits: FitPreference[];
  preferredCategories: string[];
  preferredBrands: string[];
  budgetTier: BudgetTier;
  maxPricePerItem: number;
  occasionPreferences: OccasionType[];
  preferredFootwear: string[];
  accessoryPreferences: string[];
  savedOutfitIds: string[];
  dislikedStyles: string[];
  dislikedColors: string[];
  feedbackHistory: FashionFeedbackRecord[];
  updatedAt: string;
}

export type ColorHarmonyScheme =
  | 'monochromatic'
  | 'complementary'
  | 'analogous'
  | 'neutral'
  | 'high_contrast'
  | 'triadic';

export interface ColorHarmonyResult {
  scheme: ColorHarmonyScheme;
  harmonyScore: number; // 0.0 - 1.0
  explanation: string;
  palette: string[];
}

export interface OutfitRecommendation {
  id: string;
  title: string;
  occasion: OccasionType;
  style: ClothingStyle;
  matchScore: number; // 0 - 100
  top: FashionCatalogItem | Garment;
  bottom: FashionCatalogItem | Garment;
  footwear: FashionCatalogItem | Garment;
  outerwear?: FashionCatalogItem | Garment | null;
  accessory?: FashionCatalogItem | Garment | null;
  totalPrice: number;
  priceDisplay: string;
  currency: string;
  colorHarmony: ColorHarmonyResult;
  stylingExplanation: string;
  avatarFitNotes: string;
  is3DReady: boolean;
  sourceBreakdown: {
    ownedPieces: number;
    catalogPieces: number;
  };
}

export interface WeatherContext {
  temperatureCelsius: number;
  condition: 'sunny' | 'rainy' | 'cold' | 'mild' | 'hot' | 'windy';
  thermalTier: 'cold' | 'mild' | 'warm' | 'hot';
  locationName?: string;
}

export type StylistIntentType =
  | 'recommend_outfit'
  | 'style_piece'
  | 'find_alternatives'
  | 'swap_item'
  | 'color_advice'
  | 'budget_filter'
  | 'weather_outfit'
  | 'minimal_styling'
  | 'general_advice';

export interface StylistIntent {
  type: StylistIntentType;
  occasion?: OccasionType;
  style?: ClothingStyle;
  targetSlot?: 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory';
  targetItemId?: string;
  budgetLimit?: number;
  colorPreference?: string;
  query: string;
}

export interface StylistProposal {
  id: string;
  intent: StylistIntent;
  recommendations: OutfitRecommendation[];
  selectedOutfitIndex: number;
  explanation: string;
  appliedParams: Partial<HumanParams>;
  stagedAt: string;
}

