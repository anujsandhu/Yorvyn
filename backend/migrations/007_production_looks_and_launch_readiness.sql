-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 007: Production Saved Looks, Privacy Consents & Launch Readiness
-- Introduces:
-- 1. public.yorvyn_saved_looks: Normalized multi-garment outfits with avatar state,
--    compatibility scores, and strict Row-Level Security (RLS).
-- 2. public.yorvyn_user_consents: Ephemeral photo processing & AI training opt-in
--    audit trail with cryptographic verification timestamps.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. Saved Outfits & Looks Table ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_saved_looks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    garment_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    category_composition JSONB NOT NULL DEFAULT '{}'::jsonb,
    avatar_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    compatibility_score NUMERIC(4, 3) NOT NULL DEFAULT 1.0 CHECK (compatibility_score BETWEEN 0.0 AND 1.0),
    compatibility_notes JSONB DEFAULT '[]'::jsonb,
    thermal_tier TEXT NOT NULL DEFAULT 'moderate' CHECK (thermal_tier IN ('ultra_light', 'light', 'moderate', 'warm', 'heavy_winter')),
    estimated_formality INTEGER NOT NULL DEFAULT 5 CHECK (estimated_formality BETWEEN 1 AND 10),
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    wear_count INTEGER NOT NULL DEFAULT 0,
    last_worn_at TIMESTAMPTZ,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance & Isolation Indexes
CREATE INDEX IF NOT EXISTS idx_saved_looks_user_created 
    ON public.yorvyn_saved_looks (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_looks_user_favorite 
    ON public.yorvyn_saved_looks (user_id, is_favorite);

-- Row-Level Security (RLS) Policies
ALTER TABLE public.yorvyn_saved_looks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own saved looks"
    ON public.yorvyn_saved_looks FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved looks"
    ON public.yorvyn_saved_looks FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own saved looks"
    ON public.yorvyn_saved_looks FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved looks"
    ON public.yorvyn_saved_looks FOR DELETE
    USING (auth.uid() = user_id);


-- ── 2. User Privacy & AI Training Consent Table ──────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_user_consents (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    ephemeral_processing_accepted BOOLEAN NOT NULL DEFAULT TRUE,
    ai_training_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    opt_in_timestamp TIMESTAMPTZ,
    opt_in_ip_hash TEXT,
    terms_version TEXT NOT NULL DEFAULT '2026.1',
    data_export_requested_at TIMESTAMPTZ,
    data_purge_requested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row-Level Security (RLS) Policies for Consent
ALTER TABLE public.yorvyn_user_consents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own consent records"
    ON public.yorvyn_user_consents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own consent records"
    ON public.yorvyn_user_consents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own consent records"
    ON public.yorvyn_user_consents FOR UPDATE
    USING (auth.uid() = user_id);

