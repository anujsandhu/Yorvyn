-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 002: User Profile Onboarding & Persistent Avatar Personalization
-- Adds fields for age, measurement units, body type, skin tone, hair color,
-- avatar gender/presentation, and persistent JSONB avatar configuration.
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE public.yorvyn_profiles
    ADD COLUMN IF NOT EXISTS age INTEGER,
    ADD COLUMN IF NOT EXISTS height_value NUMERIC(5, 1) DEFAULT 175.0,
    ADD COLUMN IF NOT EXISTS height_unit TEXT DEFAULT 'cm',
    ADD COLUMN IF NOT EXISTS body_type TEXT DEFAULT 'athletic',
    ADD COLUMN IF NOT EXISTS skin_tone_id TEXT DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS skin_tone_hex TEXT DEFAULT '#f3c299',
    ADD COLUMN IF NOT EXISTS hair_colour_id TEXT DEFAULT 'brown',
    ADD COLUMN IF NOT EXISTS hair_colour_hex TEXT DEFAULT '#3a2312',
    ADD COLUMN IF NOT EXISTS avatar_gender_presentation TEXT DEFAULT 'neutral',
    ADD COLUMN IF NOT EXISTS avatar_configuration JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

-- Create an index to quickly check onboarding status
CREATE INDEX IF NOT EXISTS idx_yorvyn_profiles_onboarding ON public.yorvyn_profiles (user_id, onboarding_completed);
