/**
 * Yorvyn Personal AI Fashion Intelligence - Type Definitions
 */

export type GarmentCategory = 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory' | 'one_piece';

export interface Garment {
  id: string;
  name: string;
  category: GarmentCategory;
  subcategory: string;
  color: string;
  secondary_color?: string;
  material: string;
  pattern: string;
  formality: number; // 1 - 10
  warmth: number;    // 1 - 10
  seasons: string[];
  weather_tags: string[];
  aesthetic: string[];
  brand: string;
  image_url: string;
  wear_count: number;
  favorite: boolean;
  created_at?: string;
}

export interface UserProfile {
  user_id: string;
  name: string;
  body_shape: 'athletic_tapered' | 'hourglass' | 'rectangle' | 'inverted_triangle' | 'pear';
  height_cm: number;
  skin_undertone: 'warm-bright' | 'cool-soft' | 'warm-deep' | 'cool-bright';
  color_season: 'spring' | 'summer' | 'autumn' | 'winter';
  fit_preference: 'slim' | 'regular' | 'relaxed_tailored' | 'oversized';
  primary_aesthetics: string[];
  budget_tier: 'budget' | 'mid_premium' | 'luxury';
  disliked_colors?: string[];
  lifestyle_notes?: string;
}

export interface LayerBreakdown {
  top: Garment;
  bottom: Garment;
  footwear: Garment;
  outerwear?: Garment | null;
  accessory?: Garment | null;
}

export interface AffiliateGapItem {
  id: string;
  name: string;
  category: string;
  color: string;
  brand: string;
  price: string;
  affiliate_url: string;
  image_url: string;
  reason: string;
}

export interface OutfitScoreBreakdown {
  total_score: number;
  weather_score: number;
  occasion_score: number;
  color_score: number;
  profile_score: number;
  aesthetic_score: number;
  rationale: string;
}

export interface Outfit {
  outfit_id: string;
  title: string;
  match_score: number;
  layer_breakdown: LayerBreakdown;
  color_palette: string[];
  color_harmony_explanation: string;
  styling_rationale: string;
  score_breakdown: OutfitScoreBreakdown;
  missing_piece_recommendation?: AffiliateGapItem;
}

export interface OutfitGenerationResponse {
  outfits: Outfit[];
  context: {
    occasion: string;
    temperature_celsius: number;
    condition: string;
    thermal_tier: string;
  };
  total_candidates_analyzed: number;
}

export interface StylistChatResponse {
  reply: string;
  context: {
    occasion: string;
    temperature_celsius: number;
    condition: string;
    target_aesthetic?: string;
    raw_prompt: string;
  };
  outfits: Outfit[];
  profile_snippet: {
    body_shape: string;
    color_season: string;
    aesthetics: string[];
  };
}

export interface ClosetAnalytics {
  total_items: number;
  category_breakdown: Record<string, number>;
  color_palette_distribution: Record<string, number>;
  most_worn_staples: Garment[];
  closet_utilization_rate: number;
}
