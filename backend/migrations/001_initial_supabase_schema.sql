-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Master Supabase PostgreSQL Schema & Row Level Security (RLS)
-- Migration: 001_initial_supabase_schema.sql
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. User Profiles Table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    body_shape TEXT DEFAULT 'athletic',
    height_cm INTEGER DEFAULT 178,
    skin_undertone TEXT DEFAULT 'warm',
    color_season TEXT DEFAULT 'autumn',
    fit_preference TEXT DEFAULT 'relaxed',
    primary_aesthetics JSONB DEFAULT '["quiet_luxury", "minimalist_scandi"]'::jsonb,
    budget_tier TEXT DEFAULT 'premium',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. Legacy Identity Mapping (Firebase UID to Supabase UUID) ───────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_legacy_identity_map (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firebase_uid TEXT UNIQUE NOT NULL,
    supabase_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    migrated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_legacy_map_firebase_uid ON public.yorvyn_legacy_identity_map(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_legacy_map_email ON public.yorvyn_legacy_identity_map(email);

-- ── 3. Digital Wardrobe Items Table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_wardrobe_items (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- top, bottom, outerwear, footwear, accessory
    subcategory TEXT DEFAULT 'general',
    color TEXT NOT NULL,
    secondary_color TEXT,
    material TEXT DEFAULT 'cotton',
    pattern TEXT DEFAULT 'solid',
    formality INTEGER DEFAULT 4 CHECK (formality BETWEEN 1 AND 10),
    warmth INTEGER DEFAULT 4 CHECK (warmth BETWEEN 1 AND 10),
    seasons JSONB DEFAULT '["spring", "summer", "autumn", "winter"]'::jsonb,
    aesthetic JSONB DEFAULT '["smart_casual"]'::jsonb,
    brand TEXT DEFAULT 'Unknown',
    image_url TEXT,
    wear_count INTEGER DEFAULT 0,
    favorite BOOLEAN DEFAULT FALSE,
    custom_3d_asset JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wardrobe_user_id ON public.yorvyn_wardrobe_items(user_id);
CREATE INDEX IF NOT EXISTS idx_wardrobe_category ON public.yorvyn_wardrobe_items(user_id, category);

-- ── 4. Garment 3D Generation Jobs Table ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_garment_jobs (
    job_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'analyzing', 'segmenting', 'building_mesh', 'synthesizing_pbr', 'assembling_3d', 'rendering_preview', 'completed', 'failed', 'cancelled')),
    category TEXT NOT NULL DEFAULT 'top',
    progress INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    current_stage TEXT DEFAULT 'Queued in reconstruction pipeline',
    cloudinary_public_id TEXT,
    cloudinary_delivery_url TEXT,
    glb_url TEXT,
    model_version TEXT DEFAULT 'yorvyn-garment3d-v2.0',
    mesh_vertex_count INTEGER,
    mesh_triangle_count INTEGER,
    features JSONB,
    error_details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_garment_jobs_user_status ON public.yorvyn_garment_jobs(user_id, status);

-- ── 5. Garment Asset Metadata Table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_garment_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id TEXT REFERENCES public.yorvyn_garment_jobs(job_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('glb_mesh', 'preview_thumbnail', 'diffuse_pbr', 'normal_pbr', 'roughness_pbr')),
    cloudinary_public_id TEXT,
    delivery_url TEXT NOT NULL,
    byte_size INTEGER,
    mime_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_garment_assets_job ON public.yorvyn_garment_assets(job_id);

-- ── 6. Conversations Table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'Styling Session',
    mode TEXT DEFAULT 'text' CHECK (mode IN ('text', 'voice')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON public.yorvyn_conversations(user_id);

-- ── 7. Conversation Messages Table ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES public.yorvyn_conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK (sender IN ('user', 'stylist')),
    content TEXT NOT NULL,
    outfits JSONB,
    context_snapshot JSONB,
    provider_used TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON public.yorvyn_messages(conversation_id, created_at);

-- ── 8. User Preferences & Feedback Learning ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    liked_outfit_ids JSONB DEFAULT '[]'::jsonb,
    worn_outfit_ids JSONB DEFAULT '[]'::jsonb,
    disliked_features JSONB DEFAULT '[]'::jsonb,
    feedback_history JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS) POLICIES
-- Ensures users can strictly read, insert, update, and delete ONLY their own rows.
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE public.yorvyn_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_wardrobe_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_garment_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_garment_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_legacy_identity_map ENABLE ROW LEVEL SECURITY;

-- Profiles: Users manage their own profile
CREATE POLICY "Users can view own profile" ON public.yorvyn_profiles FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can update own profile" ON public.yorvyn_profiles FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own profile" ON public.yorvyn_profiles FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Wardrobe Items: User isolation
CREATE POLICY "Users can view own wardrobe items" ON public.yorvyn_wardrobe_items FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own wardrobe items" ON public.yorvyn_wardrobe_items FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own wardrobe items" ON public.yorvyn_wardrobe_items FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own wardrobe items" ON public.yorvyn_wardrobe_items FOR DELETE USING (auth.uid() = user_id);

-- Garment Jobs: User isolation
CREATE POLICY "Users can view own garment jobs" ON public.yorvyn_garment_jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own garment jobs" ON public.yorvyn_garment_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own garment jobs" ON public.yorvyn_garment_jobs FOR UPDATE USING (auth.uid() = user_id);

-- Garment Assets: User isolation
CREATE POLICY "Users can view own garment assets" ON public.yorvyn_garment_assets FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own garment assets" ON public.yorvyn_garment_assets FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Conversations & Messages: User isolation
CREATE POLICY "Users can view own conversations" ON public.yorvyn_conversations FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own conversations" ON public.yorvyn_conversations FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can view own messages" ON public.yorvyn_messages FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own messages" ON public.yorvyn_messages FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Preferences: User isolation
CREATE POLICY "Users can view own preferences" ON public.yorvyn_user_preferences FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can update own preferences" ON public.yorvyn_user_preferences FOR ALL USING (auth.uid() = user_id);

-- Legacy Identity: User can view their own mapping
CREATE POLICY "Users can view own legacy map" ON public.yorvyn_legacy_identity_map FOR SELECT USING (auth.uid() = supabase_user_id);
