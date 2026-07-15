-- Migration: documents and decisions

CREATE TABLE documents (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    doc_kind VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_REVIEW',
    vendor_name VARCHAR(255) NOT NULL,
    fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    line_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    total INTEGER NOT NULL DEFAULT 0,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own documents" ON documents
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own documents" ON documents
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own documents" ON documents
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE TABLE decisions (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    document_id VARCHAR(50) NOT NULL,
    document_url VARCHAR(255) NOT NULL,
    vendor_name VARCHAR(255) NOT NULL,
    recommendation TEXT,
    context_data JSONB,
    evidence JSONB,
    draft_response TEXT,
    amount INTEGER NOT NULL DEFAULT 0,
    flag VARCHAR(255),
    urgency VARCHAR(50) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'needs_review',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own decisions" ON decisions
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own decisions" ON decisions
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own decisions" ON decisions
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));
