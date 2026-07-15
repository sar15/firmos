-- Evidence and review scope for manual GST reconciliation. No GSP portal access.
CREATE TABLE IF NOT EXISTS gstr2b_uploads (
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(6) NOT NULL CHECK (period ~ '^(0[1-9]|1[0-2])[0-9]{4}$'),
    payload JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (firm_id, client_id, period)
);
ALTER TABLE gstr2b_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Firms can read own GSTR2B evidence" ON gstr2b_uploads FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms can write own GSTR2B evidence" ON gstr2b_uploads FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

ALTER TABLE reconciliation_matches ADD COLUMN IF NOT EXISTS client_id VARCHAR(50);
ALTER TABLE reconciliation_matches ADD COLUMN IF NOT EXISTS period VARCHAR(6);
ALTER TABLE reconciliation_matches ADD COLUMN IF NOT EXISTS mode VARCHAR(32);
ALTER TABLE reconciliation_matches ADD COLUMN IF NOT EXISTS target_id VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_scope ON reconciliation_matches (firm_id, client_id, period, mode);
