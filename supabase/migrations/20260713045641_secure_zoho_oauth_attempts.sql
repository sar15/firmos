-- One-time, server-stored OAuth state prevents callback URL tampering/replay.
CREATE TABLE oauth_connection_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL CHECK (provider = 'ZOHO_BOOKS'),
    state_digest VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_AUTH'
        CHECK (status IN ('PENDING_AUTH', 'AWAITING_ORGANIZATION', 'CONSUMED', 'FAILED')),
    access_token_enc BYTEA,
    refresh_token_enc BYTEA,
    organizations JSONB NOT NULL DEFAULT '[]'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX oauth_connection_attempts_active_idx
    ON oauth_connection_attempts (firm_id, user_id, provider, expires_at DESC)
    WHERE status IN ('PENDING_AUTH', 'AWAITING_ORGANIZATION');

ALTER TABLE oauth_connection_attempts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own OAuth attempts" ON oauth_connection_attempts
    FOR SELECT USING (
        firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true))
        AND user_id = (SELECT current_setting('request.jwt.claim.sub', true))
    );

CREATE POLICY "Firms can insert own OAuth attempts" ON oauth_connection_attempts
    FOR INSERT WITH CHECK (
        firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true))
        AND user_id = (SELECT current_setting('request.jwt.claim.sub', true))
    );

CREATE POLICY "Firms can update own OAuth attempts" ON oauth_connection_attempts
    FOR UPDATE USING (
        firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true))
        AND user_id = (SELECT current_setting('request.jwt.claim.sub', true))
    ) WITH CHECK (
        firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true))
        AND user_id = (SELECT current_setting('request.jwt.claim.sub', true))
    );
