-- ═══════════════════════════════════════════════════════════════════════════════
-- Yorvyn Migration 010: Persistent AI Sessions, Message Context & Search History
-- Provides full multi-turn conversational persistence, search provenance,
-- idempotent message handling, session lifecycle events, and strict RLS.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. Persistent AI Sessions Table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New conversation',
    description TEXT,
    session_type TEXT NOT NULL DEFAULT 'general' CHECK (
        session_type IN (
            'general',
            'fashion_stylist',
            'garment_reconstruction',
            'wardrobe',
            'avatar',
            'shopping',
            'outfit_recommendation'
        )
    ),
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'archived', 'deleted')
    ),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    context_summary TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    search_count INTEGER NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Indexes for session querying, chronological sorting, and status filtering
CREATE INDEX IF NOT EXISTS idx_ai_sessions_user_updated
    ON public.yorvyn_ai_sessions(user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_user_status
    ON public.yorvyn_ai_sessions(user_id, status);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_user_type
    ON public.yorvyn_ai_sessions(user_id, session_type);


-- ── 2. Persistent AI Messages Table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.yorvyn_ai_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (
        role IN ('user', 'assistant', 'system', 'tool')
    ),
    content TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT 'text' CHECK (
        content_type IN (
            'text',
            'image_reference',
            'outfit_recommendation',
            'garment_analysis',
            'reconstruction_result',
            'tool_call',
            'tool_result',
            'error'
        )
    ),
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_id TEXT,
    parent_message_id UUID REFERENCES public.yorvyn_ai_messages(id) ON DELETE SET NULL,
    sequence_number BIGINT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index for idempotent request retry handling per user/session
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_messages_user_req
    ON public.yorvyn_ai_messages(user_id, request_id)
    WHERE request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_messages_session_created
    ON public.yorvyn_ai_messages(session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_ai_messages_user_created
    ON public.yorvyn_ai_messages(user_id, created_at DESC);


-- ── 3. Persistent AI Searches & Tool Provenance Table ─────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.yorvyn_ai_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_id UUID REFERENCES public.yorvyn_ai_messages(id) ON DELETE SET NULL,
    search_type TEXT NOT NULL CHECK (
        search_type IN (
            'general',
            'garment',
            'outfit',
            'wardrobe',
            'product',
            'stylist',
            'image_analysis',
            'reconstruction'
        )
    ),
    query TEXT NOT NULL,
    normalized_query TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    ),
    result_summary TEXT,
    result_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    provider TEXT,
    model_name TEXT,
    execution_provenance TEXT,
    error_code TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_searches_session_created
    ON public.yorvyn_ai_searches(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_searches_user_created
    ON public.yorvyn_ai_searches(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_searches_user_type_status
    ON public.yorvyn_ai_searches(user_id, search_type, status);


-- ── 4. Session Lifecycle Events Table ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_session_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.yorvyn_ai_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'session_created',
            'message_sent',
            'search_started',
            'search_completed',
            'search_failed',
            'session_renamed',
            'session_archived',
            'session_restored',
            'session_deleted',
            'context_summarized'
        )
    ),
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_session_events_session
    ON public.yorvyn_ai_session_events(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_session_events_user
    ON public.yorvyn_ai_session_events(user_id, created_at DESC);


-- ── 5. AI Session Attachments Table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.yorvyn_ai_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.yorvyn_ai_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_id UUID REFERENCES public.yorvyn_ai_messages(id) ON DELETE SET NULL,
    storage_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'uploaded' CHECK (
        processing_status IN ('uploaded', 'processing', 'processed', 'failed')
    ),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_attachments_session
    ON public.yorvyn_ai_attachments(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_attachments_user
    ON public.yorvyn_ai_attachments(user_id, created_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. ROW-LEVEL SECURITY (RLS) POLICIES
-- Strict multi-tenant isolation: Users may only SELECT, INSERT, UPDATE, DELETE
-- their own records.
-- ═══════════════════════════════════════════════════════════════════════════════

-- A. Sessions RLS
ALTER TABLE public.yorvyn_ai_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_sessions_owner_select"
    ON public.yorvyn_ai_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "ai_sessions_owner_insert"
    ON public.yorvyn_ai_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "ai_sessions_owner_update"
    ON public.yorvyn_ai_sessions FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "ai_sessions_owner_delete"
    ON public.yorvyn_ai_sessions FOR DELETE
    USING (auth.uid() = user_id);


-- B. Messages RLS
ALTER TABLE public.yorvyn_ai_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_messages_owner_select"
    ON public.yorvyn_ai_messages FOR SELECT
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_messages.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_messages_owner_insert"
    ON public.yorvyn_ai_messages FOR INSERT
    WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_messages.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_messages_owner_update"
    ON public.yorvyn_ai_messages FOR UPDATE
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_messages.session_id
            AND s.user_id = auth.uid()
        )
    )
    WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_messages.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_messages_owner_delete"
    ON public.yorvyn_ai_messages FOR DELETE
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_messages.session_id
            AND s.user_id = auth.uid()
        )
    );


-- C. Searches RLS
ALTER TABLE public.yorvyn_ai_searches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_searches_owner_select"
    ON public.yorvyn_ai_searches FOR SELECT
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_searches.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_searches_owner_insert"
    ON public.yorvyn_ai_searches FOR INSERT
    WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_searches.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_searches_owner_update"
    ON public.yorvyn_ai_searches FOR UPDATE
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_searches.session_id
            AND s.user_id = auth.uid()
        )
    )
    WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_searches.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_searches_owner_delete"
    ON public.yorvyn_ai_searches FOR DELETE
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_searches.session_id
            AND s.user_id = auth.uid()
        )
    );


-- D. Session Events RLS
ALTER TABLE public.yorvyn_ai_session_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_events_owner_select"
    ON public.yorvyn_ai_session_events FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "ai_events_owner_insert"
    ON public.yorvyn_ai_session_events FOR INSERT
    WITH CHECK (auth.uid() = user_id);


-- E. Session Attachments RLS
ALTER TABLE public.yorvyn_ai_attachments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_attachments_owner_select"
    ON public.yorvyn_ai_attachments FOR SELECT
    USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_attachments.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_attachments_owner_insert"
    ON public.yorvyn_ai_attachments FOR INSERT
    WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM public.yorvyn_ai_sessions s
            WHERE s.id = yorvyn_ai_attachments.session_id
            AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "ai_attachments_owner_update"
    ON public.yorvyn_ai_attachments FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "ai_attachments_owner_delete"
    ON public.yorvyn_ai_attachments FOR DELETE
    USING (auth.uid() = user_id);

