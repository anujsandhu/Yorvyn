-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 003: 3D Avatar Quality Feedback & Customization Rating System
-- Stores user satisfaction ratings (thumbs-up / thumbs-down) after avatar
-- customization sessions, including configuration snapshots and comments.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.avatar_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    configuration_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    customization_event TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('positive', 'negative', 'thumbs_up', 'thumbs_down')),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.avatar_feedback ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Authenticated users can insert their own feedback
CREATE POLICY "Users can insert their own avatar feedback"
    ON public.avatar_feedback
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Authenticated users can view their own feedback history
CREATE POLICY "Users can view their own avatar feedback"
    ON public.avatar_feedback
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Index for efficient user and timestamp queries
CREATE INDEX IF NOT EXISTS idx_avatar_feedback_user_created 
    ON public.avatar_feedback (user_id, created_at DESC);
