-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 006: Body Intelligence, Skin Analysis & Personal Colour Intelligence
-- (ML Phase 2)
-- Introduces normalized continuous physical body measurements, lighting-aware
-- CIELAB colorimetric skin profiles, photo analysis consent audit logs,
-- and strict Row-Level Security (RLS) policies.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. User Continuous Body Measurements Table ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_body_measurements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    height_cm NUMERIC(5, 2) NOT NULL DEFAULT 178.0 CHECK (height_cm BETWEEN 100.0 AND 250.0),
    weight_kg NUMERIC(5, 2) CHECK (weight_kg IS NULL OR weight_kg BETWEEN 30.0 AND 300.0),
    shoulder_width_cm NUMERIC(5, 2) CHECK (shoulder_width_cm IS NULL OR shoulder_width_cm BETWEEN 20.0 AND 80.0),
    chest_cm NUMERIC(5, 2) CHECK (chest_cm IS NULL OR chest_cm BETWEEN 50.0 AND 180.0),
    waist_cm NUMERIC(5, 2) CHECK (waist_cm IS NULL OR waist_cm BETWEEN 40.0 AND 160.0),
    hip_cm NUMERIC(5, 2) CHECK (hip_cm IS NULL OR hip_cm BETWEEN 50.0 AND 180.0),
    torso_length_cm NUMERIC(5, 2) CHECK (torso_length_cm IS NULL OR torso_length_cm BETWEEN 30.0 AND 90.0),
    arm_length_cm NUMERIC(5, 2) CHECK (arm_length_cm IS NULL OR arm_length_cm BETWEEN 40.0 AND 110.0),
    inseam_cm NUMERIC(5, 2) CHECK (inseam_cm IS NULL OR inseam_cm BETWEEN 50.0 AND 120.0),
    thigh_cm NUMERIC(5, 2) CHECK (thigh_cm IS NULL OR thigh_cm BETWEEN 30.0 AND 100.0),
    neck_cm NUMERIC(5, 2) CHECK (neck_cm IS NULL OR neck_cm BETWEEN 25.0 AND 60.0),
    unit_preference TEXT NOT NULL DEFAULT 'cm' CHECK (unit_preference IN ('cm', 'in')),
    proportions JSONB NOT NULL DEFAULT '{}'::jsonb,
    silhouette TEXT NOT NULL DEFAULT 'athletic',
    fit_preference TEXT NOT NULL DEFAULT 'regular' CHECK (fit_preference IN ('slim', 'tailored', 'regular', 'relaxed', 'athletic', 'oversized')),
    measurement_source TEXT NOT NULL DEFAULT 'user_confirmed' CHECK (measurement_source IN ('user_confirmed', 'manual', 'avatar_derived', 'cv_estimated', 'inferred')),
    measurement_sources JSONB NOT NULL DEFAULT '{}'::jsonb,
    measurement_confidences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.yorvyn_body_measurements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own body measurements"
    ON public.yorvyn_body_measurements FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own body measurements"
    ON public.yorvyn_body_measurements FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own body measurements"
    ON public.yorvyn_body_measurements FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own body measurements"
    ON public.yorvyn_body_measurements FOR DELETE
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_body_measurements_user_id ON public.yorvyn_body_measurements(user_id);


-- ── 2. User Colorimetric Skin & Personal Colour Profile Table ─────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_colour_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    skin_tone_range TEXT NOT NULL DEFAULT 'medium' CHECK (skin_tone_range IN ('fair', 'light', 'medium', 'tan', 'rich', 'deep')),
    skin_undertone TEXT NOT NULL DEFAULT 'neutral' CHECK (skin_undertone IN ('warm', 'cool', 'neutral', 'uncertain')),
    skin_hex TEXT,
    cielab_l NUMERIC(5, 2) CHECK (cielab_l IS NULL OR cielab_l BETWEEN 0.0 AND 100.0),
    cielab_a NUMERIC(5, 2) CHECK (cielab_a IS NULL OR cielab_a BETWEEN -128.0 AND 127.0),
    cielab_b NUMERIC(5, 2) CHECK (cielab_b IS NULL OR cielab_b BETWEEN -128.0 AND 127.0),
    lighting_condition TEXT DEFAULT 'neutral_daylight',
    lighting_compensation_applied BOOLEAN DEFAULT FALSE,
    personal_palette TEXT NOT NULL DEFAULT 'autumn_deep',
    seasonal_palette_name TEXT DEFAULT 'Autumn Deep',
    complementary_colours JSONB DEFAULT '[]'::jsonb,
    analogous_colours JSONB DEFAULT '[]'::jsonb,
    neutral_anchors JSONB DEFAULT '["charcoal", "navy", "cream", "white"]'::jsonb,
    accent_colours JSONB DEFAULT '["terracotta", "forest_green", "mustard"]'::jsonb,
    contrast_preference TEXT DEFAULT 'medium' CHECK (contrast_preference IN ('low', 'medium', 'high', 'low_to_medium', 'medium_to_high')),
    confidence NUMERIC(3, 2) DEFAULT 0.85 CHECK (confidence BETWEEN 0.0 AND 1.0),
    source TEXT DEFAULT 'user_confirmed' CHECK (source IN ('user_confirmed', 'avatar_derived', 'cv_estimated', 'inferred')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.yorvyn_colour_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own colour profile"
    ON public.yorvyn_colour_profiles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own colour profile"
    ON public.yorvyn_colour_profiles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own colour profile"
    ON public.yorvyn_colour_profiles FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own colour profile"
    ON public.yorvyn_colour_profiles FOR DELETE
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_colour_profiles_user_id ON public.yorvyn_colour_profiles(user_id);


-- ── 3. Privacy-Preserving Body Photo Analysis Job Logs ────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_body_photo_analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_consent_granted BOOLEAN NOT NULL DEFAULT FALSE,
    model_version TEXT NOT NULL DEFAULT 'blazepose_v1',
    image_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    perspective_warnings JSONB DEFAULT '[]'::jsonb,
    estimated_ratios JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'rejected_consent')),
    confidence NUMERIC(3, 2) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.yorvyn_body_photo_analysis_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own photo analysis jobs"
    ON public.yorvyn_body_photo_analysis_jobs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own photo analysis jobs"
    ON public.yorvyn_body_photo_analysis_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_body_photo_jobs_user_id ON public.yorvyn_body_photo_analysis_jobs(user_id);

