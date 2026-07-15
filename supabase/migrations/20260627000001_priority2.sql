-- Migration: clients, notifications, reconciliations

-- CLIENTS TABLE
CREATE TABLE clients (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255) NOT NULL,
    pan VARCHAR(20),
    gstin VARCHAR(20),
    entity_type VARCHAR(50),
    state VARCHAR(100),
    books_provider VARCHAR(50),
    next_due DATE,
    compliance_status VARCHAR(50) NOT NULL DEFAULT 'ON_TRACK',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own clients" ON clients
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own clients" ON clients
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own clients" ON clients
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- NOTIFICATIONS TABLE
CREATE TABLE notifications (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    "group" VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    client_name VARCHAR(255),
    "timestamp" VARCHAR(50),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    action_url VARCHAR(255),
    urgency VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own notifications" ON notifications
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own notifications" ON notifications
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- RECONCILIATIONS (Matches state)
CREATE TABLE reconciliation_matches (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE reconciliation_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own recon matches" ON reconciliation_matches
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own recon matches" ON reconciliation_matches
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own recon matches" ON reconciliation_matches
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));
