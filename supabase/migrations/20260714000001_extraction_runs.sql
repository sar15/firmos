-- Persist provider failures without fabricating a document or accounting values.
CREATE TABLE extraction_runs (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    document_id VARCHAR(50) REFERENCES documents(id) ON DELETE SET NULL,
    evidence_url VARCHAR(512) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_code VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX extraction_runs_firm_created_idx ON extraction_runs (firm_id, created_at DESC);

ALTER TABLE extraction_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own extraction runs" ON extraction_runs
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own extraction runs" ON extraction_runs
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
