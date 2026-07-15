-- Migration: Safe Finance Action Engine & Plugin Runtime Tables
-- # ponytail: Scoped RLS matching existing schema (firm_id VARCHAR(255)), payload hash verification for approvals

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- FINANCE ACTIONS (Immutable intent + payload hash binding)
CREATE TABLE IF NOT EXISTS finance_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'ZOHO_BOOKS' | 'TALLY_PRIME'
    operation VARCHAR(100) NOT NULL, -- e.g. 'zoho.write.bill.create', 'tally.write.purchase_voucher.create'
    idempotency_key VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL, -- SHA-256 hex of canonical JSON payload
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', -- DRAFT, PENDING_APPROVAL, QUEUED, EXECUTING, SUCCEEDED, FAILED, NEEDS_REVIEW
    risk_level VARCHAR(20) NOT NULL DEFAULT 'LOW',
    proposed_by VARCHAR(100) NOT NULL DEFAULT 'agent',
    approved_by VARCHAR(255),
    approved_payload_hash VARCHAR(64), -- Must exactly match payload_hash when approved
    approved_at TIMESTAMPTZ,
    external_reference_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, idempotency_key)
);

ALTER TABLE finance_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own finance actions" ON finance_actions
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own finance actions" ON finance_actions
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own finance actions" ON finance_actions
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));


-- FINANCE RUNS (Execution history per action attempt)
CREATE TABLE IF NOT EXISTS finance_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_id UUID NOT NULL REFERENCES finance_actions(id) ON DELETE CASCADE,
    firm_id VARCHAR(255) NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL, -- QUEUED, EXECUTING, SUCCEEDED, FAILED, RETRYING
    external_reference_id VARCHAR(255),
    provider_response JSONB,
    error_message TEXT,
    correlation_id VARCHAR(100) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE finance_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own finance runs" ON finance_runs
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own finance runs" ON finance_runs
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));


-- EXTERNAL MAPPINGS (Scoped mappings between firmOS records and external Zoho/Tally IDs)
CREATE TABLE IF NOT EXISTS external_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL, -- e.g. 'PURCHASE_BILL', 'LEDGER', 'CONTACT'
    internal_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    external_guid VARCHAR(255),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, client_id, provider, external_id)
);

ALTER TABLE external_mappings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own external mappings" ON external_mappings
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own external mappings" ON external_mappings
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
