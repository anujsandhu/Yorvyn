-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 004: User Profile Contact, Gender & Measurements
-- Adds columns for gender, phone number, location, and weight.
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE public.yorvyn_profiles
    ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT 'female',
    ADD COLUMN IF NOT EXISTS phone_number TEXT,
    ADD COLUMN IF NOT EXISTS location TEXT,
    ADD COLUMN IF NOT EXISTS weight_value NUMERIC(5, 1) DEFAULT 65.0,
    ADD COLUMN IF NOT EXISTS weight_unit TEXT DEFAULT 'kg';
