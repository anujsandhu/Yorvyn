-- Phase 17.4 Non-Destructive Additive Migration:
-- Hardens PostgreSQL durability for LangGraph checkpoints, pending writes,
-- bound design confirmation security tokens, optimistic concurrency versioning,
-- and bounded node observability telemetry.

CREATE TABLE IF NOT EXISTS yip_langgraph_checkpoints (
    thread_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE yip_langgraph_checkpoints
    ADD COLUMN IF NOT EXISTS workflow_version TEXT NOT NULL DEFAULT '17.4.0',
    ADD COLUMN IF NOT EXISTS checkpoint_id TEXT,
    ADD COLUMN IF NOT EXISTS checkpoint_ns TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS pending_writes JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS interrupt_state JSONB,
    ADD COLUMN IF NOT EXISTS resume_metadata JSONB,
    ADD COLUMN IF NOT EXISTS operation_hash TEXT,
    ADD COLUMN IF NOT EXISTS confirmation_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS confirmation_idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_yip_lg_owner ON yip_langgraph_checkpoints (owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_yip_lg_status_updated ON yip_langgraph_checkpoints (status, updated_at DESC);

-- Native BaseCheckpointSaver tuple & writes persistence tables (langgraph-checkpoint 2.1.2)
CREATE TABLE IF NOT EXISTS yip_langgraph_cp_tuples (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    owner_id TEXT NOT NULL DEFAULT '',
    checkpoint_type TEXT NOT NULL,
    checkpoint_blob BYTEA NOT NULL,
    metadata_type TEXT NOT NULL,
    metadata_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS yip_langgraph_cp_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_blob BYTEA NOT NULL,
    task_path TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Privacy-safe structured workflow node observability log
CREATE TABLE IF NOT EXISTS yip_langgraph_node_events (
    event_id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    owner_correlation_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    checkpoint_id TEXT,
    interrupt_reason TEXT,
    failure_category TEXT,
    external_credits_used INTEGER NOT NULL DEFAULT 0,
    duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_yip_lg_events_thread ON yip_langgraph_node_events (thread_id, start_ts ASC);
