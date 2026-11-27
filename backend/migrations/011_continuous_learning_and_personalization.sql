-- ============================================================================
-- Migration: 011_continuous_learning_and_personalization.sql
-- Description: Continuous AI Learning & Personalization Engine for Yorvyn
-- Entities:
--   1. yorvyn_user_preferences: Per-user editable memory (fit, style, color, etc.)
--   2. yorvyn_ai_feedback: Explicit and behavioral feedback on AI responses/searches
--   3. yorvyn_learning_examples: Sanitized, validated datasets for offline model improvement
--   4. yorvyn_model_registry: Versioned machine learning models & evaluations
--   5. yorvyn_training_jobs: Remote/offline training execution queue & telemetry
--   6. yorvyn_learning_consent: Granular opt-in privacy & training consent
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Table: yorvyn_user_preferences
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    preference_category TEXT NOT NULL CHECK (preference_category IN (
        'fit', 'style', 'colour', 'fabric', 'brand', 'occasion', 'budget', 'outfit', 'shopping', 'general'
    )),
    preference_key TEXT NOT NULL,
    preference_value JSONB NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'explicit', 'behavioral', 'temporary', 'inferred', 'correction'
    )),
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_count INTEGER NOT NULL DEFAULT 1 CHECK (evidence_count >= 1),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived', 'deleted')),
    last_confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yorvyn_user_preferences_unique_pref UNIQUE (user_id, preference_category, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_user_pref_user_id ON public.yorvyn_user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_yorvyn_user_pref_category ON public.yorvyn_user_preferences(user_id, preference_category);
CREATE INDEX IF NOT EXISTS idx_yorvyn_user_pref_status ON public.yorvyn_user_preferences(user_id, status);

-- ----------------------------------------------------------------------------
-- 2. Table: yorvyn_ai_feedback
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.yorvyn_ai_sessions(id) ON DELETE SET NULL,
    message_id UUID REFERENCES public.yorvyn_ai_messages(id) ON DELETE SET NULL,
    search_id UUID REFERENCES public.yorvyn_ai_searches(id) ON DELETE SET NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN (
        'positive', 'negative', 'correction', 'preference',
        'accepted_recommendation', 'rejected_recommendation',
        'edited_result', 'confirmed_result', 'reported_error'
    )),
    rating SMALLINT CHECK (rating BETWEEN 1 AND 5),
    original_output JSONB,
    corrected_output JSONB,
    feedback_text TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    consent_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_ai_feedback_user ON public.yorvyn_ai_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_yorvyn_ai_feedback_session ON public.yorvyn_ai_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_yorvyn_ai_feedback_message ON public.yorvyn_ai_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_yorvyn_ai_feedback_type ON public.yorvyn_ai_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_yorvyn_ai_feedback_created ON public.yorvyn_ai_feedback(created_at DESC);

-- ----------------------------------------------------------------------------
-- 3. Table: yorvyn_learning_examples
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_learning_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_feedback_id UUID REFERENCES public.yorvyn_ai_feedback(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL CHECK (task_type IN (
        'classification', 'subcategorization', 'segmentation', 'human_parsing',
        'component_detection', 'fabric_estimation', 'color_pattern',
        'silhouette_prediction', 'reconstruction', 'avatar_fitting',
        'recommendation_ranking', 'preference_prediction', 'response_quality'
    )),
    input_reference JSONB NOT NULL,
    target_output JSONB NOT NULL,
    quality_score FLOAT NOT NULL DEFAULT 0.0 CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    validation_status TEXT NOT NULL DEFAULT 'pending' CHECK (validation_status IN (
        'pending', 'validated', 'rejected', 'quarantined'
    )),
    consent_scope TEXT NOT NULL CHECK (consent_scope IN (
        'personalization_only', 'global_model_training', 'research_internal'
    )),
    dataset_version TEXT,
    exclusion_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_learn_ex_task ON public.yorvyn_learning_examples(task_type, validation_status);
CREATE INDEX IF NOT EXISTS idx_yorvyn_learn_ex_status ON public.yorvyn_learning_examples(validation_status);
CREATE INDEX IF NOT EXISTS idx_yorvyn_learn_ex_dataset ON public.yorvyn_learning_examples(dataset_version);
CREATE INDEX IF NOT EXISTS idx_yorvyn_learn_ex_created ON public.yorvyn_learning_examples(created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Table: yorvyn_model_registry
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    artifact_uri TEXT,
    artifact_checksum TEXT,
    base_model TEXT,
    training_dataset_version TEXT,
    evaluation_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN (
        'candidate', 'training', 'evaluation', 'approved', 'deployed', 'rejected', 'archived'
    )),
    deployed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yorvyn_model_registry_unique_ver UNIQUE (model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_model_name_ver ON public.yorvyn_model_registry(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_yorvyn_model_status ON public.yorvyn_model_registry(task_type, status);

-- ----------------------------------------------------------------------------
-- 5. Table: yorvyn_training_jobs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'validating', 'completed', 'failed', 'cancelled'
    )),
    training_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation_results JSONB NOT NULL DEFAULT '{}'::jsonb,
    resource_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_train_jobs_status ON public.yorvyn_training_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_yorvyn_train_jobs_task ON public.yorvyn_training_jobs(task_type);

-- ----------------------------------------------------------------------------
-- 6. Table: yorvyn_learning_consent
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.yorvyn_learning_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    personalization_enabled BOOLEAN NOT NULL DEFAULT true,
    global_model_training_enabled BOOLEAN NOT NULL DEFAULT false,
    image_training_enabled BOOLEAN NOT NULL DEFAULT false,
    conversation_training_enabled BOOLEAN NOT NULL DEFAULT false,
    consent_version TEXT NOT NULL DEFAULT 'v1.0',
    consent_updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_yorvyn_consent_user ON public.yorvyn_learning_consent(user_id);

-- ----------------------------------------------------------------------------
-- Row-Level Security (RLS) Enablement & Strict Policies
-- ----------------------------------------------------------------------------
ALTER TABLE public.yorvyn_user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_ai_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_learning_consent ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_learning_examples ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_model_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_training_jobs ENABLE ROW LEVEL SECURITY;

-- Preferences Policies: Users access only their own records
CREATE POLICY "Users view own preferences" ON public.yorvyn_user_preferences
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users insert own preferences" ON public.yorvyn_user_preferences
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own preferences" ON public.yorvyn_user_preferences
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users delete own preferences" ON public.yorvyn_user_preferences
    FOR DELETE USING (auth.uid() = user_id);

-- Feedback Policies: Users view and submit their own feedback
CREATE POLICY "Users view own feedback" ON public.yorvyn_ai_feedback
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users insert own feedback" ON public.yorvyn_ai_feedback
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users delete own feedback" ON public.yorvyn_ai_feedback
    FOR DELETE USING (auth.uid() = user_id);

-- Consent Policies: Users manage their own consent record
CREATE POLICY "Users view own consent" ON public.yorvyn_learning_consent
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users insert own consent" ON public.yorvyn_learning_consent
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own consent" ON public.yorvyn_learning_consent
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users delete own consent" ON public.yorvyn_learning_consent
    FOR DELETE USING (auth.uid() = user_id);

-- Model Registry Policies: Authenticated users can view deployed models; admin/service-role can manage
CREATE POLICY "Users view deployed models" ON public.yorvyn_model_registry
    FOR SELECT USING (status = 'deployed' OR auth.jwt() ->> 'role' = 'service_role');

-- Service role policies for global learning artifacts (quarantined from raw user access)
CREATE POLICY "Service role full access on learning_examples" ON public.yorvyn_learning_examples
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access on model_registry" ON public.yorvyn_model_registry
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access on training_jobs" ON public.yorvyn_training_jobs
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

