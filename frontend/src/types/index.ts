export interface Perfume {
  id: string
  name: string
  brand: string
  family: string
  rating: number
  price: number
  description?: string
  image_url?: string | null
  gender?: string
  accords?: string
  sold?: number
  rating_count?: number
  premium_score?: number
}

export interface RecommendationScore extends Perfume {
  perfume_id: string
  ml_score: number
  rating_score: number
  popularity_score: number
  final_score: number
  price_usd?: number
  algorithm?: string
}

export interface RecommendationResponse {
  recommendations: RecommendationScore[]
  explanation: string
  total_processed: number
  confidence: number
  fallback_used: boolean
  fallback_provider?: string | null
  strategy: string
}

export interface ShoppingLink {
  platform: string
  url: string
}

export interface ShoppingInfo {
  // New accurate fields
  price_inr_min?: number
  price_inr_max?: number
  price_display?: string
  price_source?: 'dataset_usd' | 'brand_tier' | 'local'
  usd_original?: number
  fx_rate?: number
  // Legacy compat
  original_price_inr?: string
  discounted_price_inr?: string
  links: ShoppingLink[]
  source: string
}

export interface Stats {
  total_perfumes: number
  unique_brands: number
  unique_families: number
  avg_rating: number
}

export interface Category {
  name: string
  key: string
  emoji: string
  count: number
}

export interface FeaturedResponse {
  featured: Perfume | null
  premium_collection: Perfume[]
}

export interface DescriptionResponse {
  enhanced_description: string
  source: string
  error?: string
}

export interface ChatResponse {
  reply: string
  recommendations: RecommendationScore[]
  extracted_context: {
    gender?: string
    occasion?: string
    season?: string
    mood?: string
    liked_notes?: string[]
    disliked_notes?: string[]
    reference_perfumes?: string[]
    budget_max?: number
  }
  follow_up_suggestions: string[]
  confidence: number
}
