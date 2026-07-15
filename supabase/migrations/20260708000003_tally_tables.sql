-- Migration: canonical tables for Tally Prime integration
-- Why: Tally Prime data is pushed locally by the bridge daemon. We store masters
-- (tally_ledgers) and transactions (tally_vouchers) in canonical Postgres tables
-- keyed by UNIQUE(firm_id, tally_guid) to guarantee idempotency and prevent duplicates.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- TALLY LEDGERS TABLE
CREATE TABLE IF NOT EXISTS tally_ledgers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    tally_guid VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_group VARCHAR(255) NOT NULL,
    opening_balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    closing_balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    is_revenue BOOLEAN NOT NULL DEFAULT FALSE,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, tally_guid)
);

ALTER TABLE tally_ledgers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own tally ledgers" ON tally_ledgers
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own tally ledgers" ON tally_ledgers
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own tally ledgers" ON tally_ledgers
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can delete own tally ledgers" ON tally_ledgers
    FOR DELETE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));


-- TALLY VOUCHERS TABLE
CREATE TABLE IF NOT EXISTS tally_vouchers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    tally_guid VARCHAR(255) NOT NULL,
    voucher_number VARCHAR(100) NOT NULL,
    date VARCHAR(20) NOT NULL,
    voucher_type VARCHAR(100) NOT NULL,
    party_name VARCHAR(255),
    narration TEXT,
    entries JSONB NOT NULL DEFAULT '[]'::jsonb,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, tally_guid)
);

ALTER TABLE tally_vouchers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own tally vouchers" ON tally_vouchers
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own tally vouchers" ON tally_vouchers
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own tally vouchers" ON tally_vouchers
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can delete own tally vouchers" ON tally_vouchers
    FOR DELETE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));


-- TALLY SYNC LOGS TABLE (Idempotency Tracking)
CREATE TABLE IF NOT EXISTS tally_sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    ledgers_count INTEGER NOT NULL DEFAULT 0,
    vouchers_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, idempotency_key)
);

ALTER TABLE tally_sync_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own tally sync logs" ON tally_sync_logs
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own tally sync logs" ON tally_sync_logs
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
