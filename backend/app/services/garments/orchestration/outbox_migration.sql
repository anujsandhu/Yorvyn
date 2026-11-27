-- YORVYN Transactional Outbox Table (DURABLE-JOB-FIX-002)
-- Provides reliable at-least-once job delivery across process crashes,
-- Redis failures, retries and application restarts.
-- This is an ADDITIVE migration — no existing tables or columns are modified or dropped.

CREATE TABLE IF NOT EXISTS yorvyn_job_outbox (
    outbox_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          TEXT            NOT NULL REFERENCES yorvyn_jobs(job_id) ON DELETE CASCADE,
    tenant_id       TEXT            NOT NULL,
    event_type      TEXT            NOT NULL DEFAULT 'JOB_QUEUED',   -- JOB_QUEUED | JOB_RETRY
    payload         JSONB           NOT NULL,
    priority        INTEGER         NOT NULL DEFAULT 3,
    created_at      DOUBLE PRECISION NOT NULL,
    deliver_after   DOUBLE PRECISION NOT NULL DEFAULT 0,
    delivered_at    DOUBLE PRECISION,
    delivery_attempts INTEGER       NOT NULL DEFAULT 0,
    max_delivery_attempts INTEGER   NOT NULL DEFAULT 5,
    redis_message_id TEXT,
    acknowledged_at DOUBLE PRECISION,
    status          TEXT            NOT NULL DEFAULT 'PENDING',      -- PENDING | DELIVERED | ACKNOWLEDGED | EXHAUSTED
    last_error      TEXT,
    claimed_by      TEXT,
    claimed_at      DOUBLE PRECISION,
    CONSTRAINT outbox_job_id_event_type_key UNIQUE (job_id, event_type)
);

-- Additive columns in case table was already created without them
ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'PENDING';
ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS claimed_by TEXT;
ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS claimed_at DOUBLE PRECISION;

-- Index for the outbox dispatcher query: undelivered entries ordered by deliver_after
CREATE INDEX IF NOT EXISTS idx_outbox_undelivered
    ON yorvyn_job_outbox(deliver_after)
    WHERE delivered_at IS NULL;

-- Index for stale delivery recovery: delivered but unacknowledged entries
CREATE INDEX IF NOT EXISTS idx_outbox_unacked
    ON yorvyn_job_outbox(delivered_at)
    WHERE delivered_at IS NOT NULL AND acknowledged_at IS NULL;

-- Index for looking up outbox entries by job_id (for acknowledgement and compensation)
CREATE INDEX IF NOT EXISTS idx_outbox_job_id
    ON yorvyn_job_outbox(job_id);
