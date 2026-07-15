-- Migration: connections and audit_log

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- CONNECTIONS TABLE
CREATE TABLE connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    connector_id VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DISCONNECTED',
    access_token_enc BYTEA,
    refresh_token_enc BYTEA,
    external_account_id VARCHAR(255),
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, connector_id)
);

ALTER TABLE connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own connections" ON connections
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own connections" ON connections
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own connections" ON connections
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- AUDIT LOG TABLE
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(255) NOT NULL, -- user_id or 'system'
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Append-only
REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;
-- In Supabase, the API connects as 'authenticated' or 'anon' roles
REVOKE UPDATE, DELETE ON audit_log FROM authenticated;

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own audit logs" ON audit_log
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own audit logs" ON audit_log
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
