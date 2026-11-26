-- ==============================================================================
-- YORVYN MIGRATION 009: Controlled Private Beta Onboarding & Feedback Subsystem
-- Phase 11: Production Operations, Beta Cohort Management & Defect Registry
-- ==============================================================================

-- 1. Beta Invitations Table
CREATE TABLE IF NOT EXISTS public.yorvyn_beta_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    cohort VARCHAR(64) NOT NULL DEFAULT 'closed_pilot',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'suspended', 'revoked')),
    max_uses INTEGER NOT NULL DEFAULT 1,
    uses_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    activated_at TIMESTAMPTZ,
    activated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for invitation validation
CREATE INDEX IF NOT EXISTS idx_beta_invitations_token ON public.yorvyn_beta_invitations(token);
CREATE INDEX IF NOT EXISTS idx_beta_invitations_email ON public.yorvyn_beta_invitations(email);
CREATE INDEX IF NOT EXISTS idx_beta_invitations_status ON public.yorvyn_beta_invitations(status);

-- Enable RLS
ALTER TABLE public.yorvyn_beta_invitations ENABLE ROW LEVEL SECURITY;

-- Beta invitations policies:
-- Users can view their own activated invitation
DROP POLICY IF EXISTS "Users can view their own activated invitation" ON public.yorvyn_beta_invitations;
CREATE POLICY "Users can view their own activated invitation"
    ON public.yorvyn_beta_invitations
    FOR SELECT
    USING (auth.uid() = activated_by);

-- Service role has full administrative access
DROP POLICY IF EXISTS "Service role manages invitations" ON public.yorvyn_beta_invitations;
CREATE POLICY "Service role manages invitations"
    ON public.yorvyn_beta_invitations
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');


-- 2. Beta Feedback & Defect Registry Table
CREATE TABLE IF NOT EXISTS public.yorvyn_beta_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id VARCHAR(64),
    correlation_id VARCHAR(64),
    software_version VARCHAR(32) NOT NULL DEFAULT 'v2026.11-beta',
    reconstruction_rating SMALLINT CHECK (reconstruction_rating BETWEEN 1 AND 5),
    fitting_rating SMALLINT CHECK (fitting_rating BETWEEN 1 AND 5),
    texture_rating SMALLINT CHECK (texture_rating BETWEEN 1 AND 5),
    category_correct BOOLEAN DEFAULT TRUE,
    usability_rating SMALLINT CHECK (usability_rating BETWEEN 1 AND 5),
    feedback_text TEXT,
    failure_category VARCHAR(64),
    reproduction_steps TEXT,
    include_raw_image BOOLEAN NOT NULL DEFAULT FALSE,
    severity VARCHAR(16) DEFAULT 'normal' CHECK (severity IN ('low', 'normal', 'high', 'critical')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for feedback analytics
CREATE INDEX IF NOT EXISTS idx_beta_feedback_user ON public.yorvyn_beta_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_job ON public.yorvyn_beta_feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_created ON public.yorvyn_beta_feedback(created_at DESC);

-- Enable RLS
ALTER TABLE public.yorvyn_beta_feedback ENABLE ROW LEVEL SECURITY;

-- Feedback policies:
-- Users can insert their own feedback
DROP POLICY IF EXISTS "Users can insert their own feedback" ON public.yorvyn_beta_feedback;
CREATE POLICY "Users can insert their own feedback"
    ON public.yorvyn_beta_feedback
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can view their own submitted feedback
DROP POLICY IF EXISTS "Users can view their own feedback" ON public.yorvyn_beta_feedback;
CREATE POLICY "Users can view their own feedback"
    ON public.yorvyn_beta_feedback
    FOR SELECT
    USING (auth.uid() = user_id);

-- Service role has full administrative access
DROP POLICY IF EXISTS "Service role manages feedback" ON public.yorvyn_beta_feedback;
CREATE POLICY "Service role manages feedback"
    ON public.yorvyn_beta_feedback
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

