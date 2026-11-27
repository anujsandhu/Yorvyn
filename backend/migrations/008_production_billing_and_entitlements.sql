-- ==============================================================================
-- YORVYN DATABASE MIGRATION 008: Production Billing, Subscriptions & Entitlements
-- Adds normalized tables for Stripe subscriptions, billing event idempotency,
-- per-user usage tracking, and strict Row-Level Security (RLS) policies.
-- ==============================================================================

-- 1. Subscriptions Table
CREATE TABLE IF NOT EXISTS public.yorvyn_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES public.yorvyn_profiles(user_id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    plan_id TEXT NOT NULL DEFAULT 'explorer', -- 'explorer', 'pro', 'studio'
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'trialing', 'past_due', 'canceled', 'unpaid', 'incomplete'
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_period_end TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days'),
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    canceled_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_yorvyn_subscriptions_user UNIQUE (user_id)
);

-- Indexes for subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON public.yorvyn_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON public.yorvyn_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON public.yorvyn_subscriptions(plan_id, status);

-- 2. Billing Events Table (Idempotency and Audit Log)
CREATE TABLE IF NOT EXISTS public.yorvyn_billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL, -- Stripe Event ID (evt_xxx)
    event_type TEXT NOT NULL,
    user_id TEXT,
    stripe_customer_id TEXT,
    payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    error_message TEXT
);

-- Index for billing events idempotency lookups
CREATE INDEX IF NOT EXISTS idx_billing_events_id ON public.yorvyn_billing_events(event_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_user ON public.yorvyn_billing_events(user_id);

-- 3. Usage Records Table (Quota & Cost Accounting)
CREATE TABLE IF NOT EXISTS public.yorvyn_usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES public.yorvyn_profiles(user_id) ON DELETE CASCADE,
    metric TEXT NOT NULL, -- 'garment_reconstruction', 'commercial_export', 'saved_look'
    quantity INT NOT NULL DEFAULT 1,
    job_id TEXT,
    cost_usd NUMERIC(10, 6) DEFAULT 0.000000,
    provenance TEXT,
    billing_period_start TIMESTAMPTZ NOT NULL,
    billing_period_end TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for usage calculations
CREATE INDEX IF NOT EXISTS idx_usage_user_metric_period 
    ON public.yorvyn_usage_records(user_id, metric, billing_period_start);
CREATE INDEX IF NOT EXISTS idx_usage_job_id 
    ON public.yorvyn_usage_records(job_id);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.yorvyn_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_billing_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yorvyn_usage_records ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies: Subscriptions
DROP POLICY IF EXISTS "Users can view own subscription" ON public.yorvyn_subscriptions;
CREATE POLICY "Users can view own subscription"
    ON public.yorvyn_subscriptions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access on subscriptions" ON public.yorvyn_subscriptions;
CREATE POLICY "Service role full access on subscriptions"
    ON public.yorvyn_subscriptions FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- 6. RLS Policies: Usage Records
DROP POLICY IF EXISTS "Users can view own usage records" ON public.yorvyn_usage_records;
CREATE POLICY "Users can view own usage records"
    ON public.yorvyn_usage_records FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access on usage records" ON public.yorvyn_usage_records;
CREATE POLICY "Service role full access on usage records"
    ON public.yorvyn_usage_records FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- 7. RLS Policies: Billing Events (Internal Audit Log)
DROP POLICY IF EXISTS "Service role full access on billing events" ON public.yorvyn_billing_events;
CREATE POLICY "Service role full access on billing events"
    ON public.yorvyn_billing_events FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

