-- Provider-native bank matching review cases and normalized GST tax components.
CREATE TABLE IF NOT EXISTS zoho_bank_match_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(6) NOT NULL CHECK (period ~ '^(0[1-9]|1[0-2])[0-9]{4}$'),
    account_id VARCHAR(100) NOT NULL,
    bank_transaction_id VARCHAR(100) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    provider_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (firm_id, client_id, account_id, bank_transaction_id)
);

CREATE TABLE IF NOT EXISTS zoho_bank_match_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES zoho_bank_match_cases(id) ON DELETE CASCADE,
    external_transaction_id VARCHAR(100) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    transaction_date DATE,
    amount_paise BIGINT NOT NULL DEFAULT 0,
    counterparty TEXT,
    reference_number TEXT,
    is_best_match BOOLEAN NOT NULL DEFAULT FALSE,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (case_id, external_transaction_id, transaction_type)
);

CREATE TABLE IF NOT EXISTS gst_tax_components (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(6) NOT NULL CHECK (period ~ '^(0[1-9]|1[0-2])[0-9]{4}$'),
    source_type VARCHAR(16) NOT NULL CHECK (source_type IN ('SALES', 'PURCHASE')),
    source_id VARCHAR(100) NOT NULL,
    taxable_paise BIGINT NOT NULL DEFAULT 0,
    igst_paise BIGINT NOT NULL DEFAULT 0,
    cgst_paise BIGINT NOT NULL DEFAULT 0,
    sgst_paise BIGINT NOT NULL DEFAULT 0,
    cess_paise BIGINT NOT NULL DEFAULT 0,
    components_verified BOOLEAN NOT NULL DEFAULT FALSE,
    itc_eligible BOOLEAN,
    source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (firm_id, client_id, source_type, source_id)
);

ALTER TABLE zoho_bank_match_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE zoho_bank_match_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_tax_components ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Firms own Zoho bank match cases" ON zoho_bank_match_cases FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own Zoho bank match candidates" ON zoho_bank_match_candidates FOR ALL
USING (EXISTS (SELECT 1 FROM zoho_bank_match_cases c WHERE c.id = case_id AND c.firm_id = current_setting('request.jwt.claim.firm_id', true)))
WITH CHECK (EXISTS (SELECT 1 FROM zoho_bank_match_cases c WHERE c.id = case_id AND c.firm_id = current_setting('request.jwt.claim.firm_id', true)));
CREATE POLICY "Firms own GST components" ON gst_tax_components FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE INDEX IF NOT EXISTS idx_gst_tax_components_period ON gst_tax_components (firm_id, client_id, period, source_type);
