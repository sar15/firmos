-- A worker must prove it is alive before deployment readiness can be true.
CREATE TABLE worker_heartbeats (
    firm_id VARCHAR(255) NOT NULL,
    worker_kind VARCHAR(50) NOT NULL,
    worker_id VARCHAR(100) NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (firm_id, worker_kind, worker_id)
);

ALTER TABLE worker_heartbeats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own worker heartbeats" ON worker_heartbeats
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can write own worker heartbeats" ON worker_heartbeats
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own worker heartbeats" ON worker_heartbeats
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));
