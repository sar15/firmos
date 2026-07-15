-- One mutable accounting draft points at immutable finance action attempts.
-- ponytail: a single table is enough for document-to-books automation; mapping
-- rules can be added only after firms have real, repeated mappings to learn.
CREATE TABLE accounting_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    document_id VARCHAR(50) NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    provider VARCHAR(50) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'NEEDS_REVIEW',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_mappings JSONB NOT NULL DEFAULT '[]'::jsonb,
    action_id UUID REFERENCES finance_actions(id) ON DELETE SET NULL,
    external_reference_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (firm_id, document_id, provider, operation)
);

CREATE INDEX accounting_drafts_firm_client_status_idx
    ON accounting_drafts (firm_id, client_id, status, updated_at DESC);

ALTER TABLE accounting_drafts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own accounting drafts" ON accounting_drafts
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own accounting drafts" ON accounting_drafts
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own accounting drafts" ON accounting_drafts
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true))
    WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- Evidence bytes must never be exposed through a public object URL.
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', false)
ON CONFLICT (id) DO UPDATE SET public = false;

DROP POLICY IF EXISTS "Allow public select" ON storage.objects;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);
CREATE UNIQUE INDEX documents_firm_client_content_hash_unique
    ON documents (firm_id, client_id, content_sha256)
    WHERE content_sha256 IS NOT NULL;
