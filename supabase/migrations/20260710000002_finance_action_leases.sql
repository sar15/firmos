-- Phase 3 hardening: durable bridge leases and completed run timestamps.
-- ponytail: one action can be owned by one office bridge until its short lease expires.

ALTER TABLE finance_actions
    ADD COLUMN IF NOT EXISTS lease_device_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

ALTER TABLE finance_runs
    ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_finance_actions_tally_queue
    ON finance_actions (firm_id, provider, status, created_at)
    WHERE provider = 'TALLY_PRIME';

CREATE INDEX IF NOT EXISTS idx_finance_actions_lease
    ON finance_actions (lease_expires_at)
    WHERE lease_expires_at IS NOT NULL;
