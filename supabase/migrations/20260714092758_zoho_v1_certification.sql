-- Zoho Books V1 certification state; provider secrets remain server-only.
ALTER TABLE oauth_connection_attempts
    ADD COLUMN intended_installation_id uuid NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN redirect_uri text NOT NULL DEFAULT '',
    ADD COLUMN data_center varchar(20),
    ADD COLUMN api_domain varchar(255),
    ADD COLUMN granted_scopes text[] NOT NULL DEFAULT '{}',
    ADD COLUMN token_expires_at timestamptz;

ALTER TABLE provider_objects ADD COLUMN snapshot jsonb NOT NULL DEFAULT '{}';
ALTER TABLE connector_credentials ADD COLUMN credential_version integer NOT NULL DEFAULT 1;
ALTER TABLE connector_sync_jobs
    ADD COLUMN provider_snapshot_version varchar(100),
    ADD COLUMN mapping_blockers jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN seen_provider_ids jsonb NOT NULL DEFAULT '[]';

CREATE INDEX connector_sync_jobs_installation_idx
    ON connector_sync_jobs (installation_id, capability_key, created_at DESC);
CREATE INDEX provider_objects_installation_idx
    ON provider_objects (installation_id, object_type, last_seen_at DESC);

CREATE TABLE connector_rate_budgets (
    installation_id uuid PRIMARY KEY REFERENCES connector_installations(id) ON DELETE CASCADE,
    organization_id varchar(255) NOT NULL,
    window_started_at timestamptz NOT NULL DEFAULT now(),
    requests_used integer NOT NULL DEFAULT 0 CHECK (requests_used >= 0),
    blocked_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE connector_rate_budgets ENABLE ROW LEVEL SECURITY;
CREATE POLICY rate_budgets_firm ON connector_rate_budgets FOR ALL
    USING (EXISTS (
        SELECT 1 FROM connector_installations i
        WHERE i.id = installation_id AND i.firm_id = current_firm_id()
    ));

REVOKE SELECT ON connector_rate_budgets FROM anon, authenticated;
