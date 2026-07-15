-- Server-owned certification records and fail-closed operator kill switches.
CREATE TABLE capability_certifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    capability_key VARCHAR(100) NOT NULL,
    certification_version VARCHAR(50) NOT NULL,
    certified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (firm_id, capability_key)
);

CREATE TABLE capability_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255),
    client_id VARCHAR(50),
    installation_id VARCHAR(100),
    provider VARCHAR(50),
    capability_key VARCHAR(100),
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    reason_code VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (firm_id IS NOT NULL OR provider IS NOT NULL OR capability_key IS NOT NULL)
);

CREATE INDEX capability_overrides_scope_idx
    ON capability_overrides (firm_id, client_id, provider, capability_key);

ALTER TABLE capability_certifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE capability_overrides ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own capability certifications" ON capability_certifications
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can read own capability overrides" ON capability_overrides
    FOR SELECT USING (firm_id IS NULL OR firm_id = current_setting('request.jwt.claim.firm_id', true));
