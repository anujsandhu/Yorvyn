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
  // 3D Garment Generation Extensions
  is_custom_3d?: boolean;
  glb_url?: string;
  thumbnail_url?: string;
  model_version?: string;
  reconstruction_metadata?: {
    mesh_vertex_count?: number;
    mesh_triangle_count?: number;
    rig_compatibility?: Record<string, any>;
    palette?: string[];
    neckline?: string;
    sleeve_length?: string;
    fit?: string;
  };
}

export interface DetectedGarmentFeatures {
  category: string;
  subcategory: string;
  primary_color_name: string;
  primary_color_hex: string;
  secondary_color_name?: string;
  secondary_color_hex?: string;
  palette: string[];
  pattern: string;
  material_hint: string;
  neckline_type?: string;
  sleeve_length?: string;
  hem_length?: string;
  fit: string;
  formality: number;
  warmth: number;
  confidence_score: number;
  requires_additional_view: boolean;
  quality_notes?: string;
}

export interface GarmentGenResult {
  job_id: string;
  garment_name: string;
  category: string;
  subcategory: string;
  glb_url: string;
  thumbnail_url: string;
  texture_url?: string;
  normal_map_url?: string;
  mesh_vertex_count: number;
  mesh_triangle_count: number;
  features: DetectedGarmentFeatures;
  model_version: string;
  created_at: string;
  rig_compatibility?: Record<string, any>;
}

export interface GarmentGenJob {
  job_id: string;
  status: 'queued' | 'analyzing' | 'generating_mesh' | 'synthesizing_textures' | 'assembling_3d' | 'rendering_preview' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_stage: string;
  error?: string | null;
  result?: GarmentGenResult | null;
  created_at?: string;
  updated_at?: string;
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
