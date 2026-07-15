-- Approval records the reviewed content; delivery is intentionally out of scope.
CREATE TABLE decision_review_versions (
    id VARCHAR(50) PRIMARY KEY,
    decision_id VARCHAR(50) NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    firm_id VARCHAR(255) NOT NULL,
    reviewed_response TEXT NOT NULL,
    reviewed_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX decision_review_versions_decision_idx
    ON decision_review_versions (decision_id, created_at DESC);

ALTER TABLE decision_review_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own decision review versions" ON decision_review_versions
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own decision review versions" ON decision_review_versions
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
