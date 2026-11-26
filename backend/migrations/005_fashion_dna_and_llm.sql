-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 005: Fashion DNA, LLM Tool Calling & Recommendation Intelligence
-- Introduces persistent Fashion DNA profiles, tool execution tracking, and
-- multi-factor recommendation evaluation records with Row-Level Security (RLS).
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. Fashion DNA User Intelligence Profile Table ───────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_fashion_dna (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    body_profile JSONB NOT NULL DEFAULT '{
        "height_cm": 178,
        "weight_kg": 70,
        "shoulder_cm": null,
        "chest_cm": null,
        "waist_cm": null,
        "hip_cm": null,
        "torso_proportion": "balanced",
        "arm_proportion": "balanced",
        "leg_proportion": "balanced",
        "silhouette": "athletic",
        "fit_preference": "regular",
        "measurement_source": "estimated"
    }'::jsonb,
    colour_profile JSONB NOT NULL DEFAULT '{
        "skin_tone_range": "medium",
        "skin_undertone": "neutral",
        "personal_palette": "autumn_deep",
        "preferred_colours": ["navy", "charcoal", "olive", "cream"],
        "disliked_colours": ["neon_yellow"],
        "preferred_harmonies": ["complementary", "tonal"],
        "confidence": 0.85
    }'::jsonb,
    style_profile JSONB NOT NULL DEFAULT '{
        "primary_styles": ["smart_casual", "minimalist"],
        "aesthetic_tags": ["tailored", "clean", "timeless"],
        "occasion_frequency": {"work": 0.4, "casual": 0.4, "formal": 0.2}
    }'::jsonb,
    additional_preferences JSONB NOT NULL DEFAULT '{
        "gender_presentation": "androgynous",
        "age_range": "25-34",
        "preferred_brands": ["COS", "Arket", "Uniqlo"],
        "preferred_materials": ["wool", "cotton", "linen"],
        "disliked_materials": ["polyester"],
        "budget_level": "mid",
        "min_budget": 50,
        "max_budget": 300,
        "currency": "EUR",
        "climate_preference": "temperate"
    }'::jsonb,
    confidence_scores JSONB NOT NULL DEFAULT '{
        "body_fit_confidence": 0.80,
        "colour_harmony_confidence": 0.85,
        "style_affinity_confidence": 0.90,
        "overall_dna_confidence": 0.85
    }'::jsonb,
    preference_evolution JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.yorvyn_fashion_dna ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own Fashion DNA"
    ON public.yorvyn_fashion_dna FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own Fashion DNA"
    ON public.yorvyn_fashion_dna FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own Fashion DNA"
    ON public.yorvyn_fashion_dna FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own Fashion DNA"
    ON public.yorvyn_fashion_dna FOR DELETE
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_fashion_dna_user_id ON public.yorvyn_fashion_dna(user_id);


-- ── 2. LLM Tool Execution Logs ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_tool_execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    input_arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_time_ms NUMERIC(8, 2) DEFAULT 0.0,
    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.yorvyn_tool_execution_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own tool execution logs"
    ON public.yorvyn_tool_execution_logs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own tool execution logs"
    ON public.yorvyn_tool_execution_logs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_tool_logs_user_tool ON public.yorvyn_tool_execution_logs(user_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_logs_created_at ON public.yorvyn_tool_execution_logs(created_at DESC);


-- ── 3. Multi-Factor Recommendation Evaluation Records ───────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_recommendation_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    outfit_id TEXT NOT NULL,
    compatibility_scores JSONB NOT NULL DEFAULT '{
        "body_fit": 0.0,
        "colour_harmony": 0.0,
        "style_alignment": 0.0,
        "wardrobe_synergy": 0.0,
        "occasion_suitability": 0.0,
        "weather_adaptation": 0.0,
        "budget_compliance": 0.0,
        "feedback_affinity": 0.0,
        "clothing_availability": 0.0,
        "outfit_completeness": 0.0,
        "composite_score": 0.0
    }'::jsonb,
    rationale TEXT,
    feedback_status TEXT DEFAULT 'pending' CHECK (feedback_status IN ('pending', 'liked', 'saved', 'rejected', 'modified')),
    feedback_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.yorvyn_recommendation_evaluations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own recommendation evaluations"
    ON public.yorvyn_recommendation_evaluations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own recommendation evaluations"
    ON public.yorvyn_recommendation_evaluations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own recommendation evaluations"
    ON public.yorvyn_recommendation_evaluations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_rec_eval_user_outfit ON public.yorvyn_recommendation_evaluations(user_id, outfit_id);
CREATE INDEX IF NOT EXISTS idx_rec_eval_created_at ON public.yorvyn_recommendation_evaluations(created_at DESC);

