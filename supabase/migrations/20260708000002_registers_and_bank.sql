-- Migration: registers + bank tables (fixes ghost tables + adds data layer)

-- SALES REGISTER — synced from Zoho invoices, filtered by period
CREATE TABLE sales_register (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(10) NOT NULL,           -- MMYYYY format (matches GSTN)
    zoho_invoice_id VARCHAR(100),
    invoice_number VARCHAR(100),
    customer_name VARCHAR(255),
    invoice_date DATE,
    total_paise BIGINT NOT NULL DEFAULT 0,
    tax_total_paise BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(50),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, client_id, zoho_invoice_id)
);

ALTER TABLE sales_register ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own sales register" ON sales_register
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own sales register" ON sales_register
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own sales register" ON sales_register
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- PURCHASE REGISTER — synced from Zoho bills, merged with local OCR docs
CREATE TABLE purchase_register (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(10) NOT NULL,
    zoho_bill_id VARCHAR(100),
    bill_number VARCHAR(100),
    vendor_name VARCHAR(255),
    vendor_gstin VARCHAR(20),
    bill_date DATE,
    total_paise BIGINT NOT NULL DEFAULT 0,
    tax_total_paise BIGINT NOT NULL DEFAULT 0,
    source VARCHAR(20) NOT NULL DEFAULT 'ZOHO',  -- ZOHO | LOCAL_OCR
    status VARCHAR(50),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, client_id, zoho_bill_id)
);

ALTER TABLE purchase_register ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own purchase register" ON purchase_register
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own purchase register" ON purchase_register
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can update own purchase register" ON purchase_register
    FOR UPDATE USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- BANK STATEMENTS — metadata for uploaded bank statement files
-- (bank_statements.py:262 already INSERTs into this; it just didn't exist)
CREATE TABLE bank_statements (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    file_url VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE bank_statements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own bank statements" ON bank_statements
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own bank statements" ON bank_statements
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- BANK TRANSACTIONS — parsed rows from uploaded statements
-- (reconciliation.py:132 already queries this; it just didn't exist)
CREATE TABLE bank_transactions (
    id VARCHAR(50) PRIMARY KEY,
    statement_id VARCHAR(50) REFERENCES bank_statements(id),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    txn_date DATE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    amount BIGINT NOT NULL DEFAULT 0,  -- paise, always positive
    txn_type VARCHAR(10) NOT NULL DEFAULT 'DEBIT',  -- CREDIT | DEBIT
    running_balance BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE bank_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Firms can read own bank transactions" ON bank_transactions
    FOR SELECT USING (firm_id = current_setting('request.jwt.claim.firm_id', true));

CREATE POLICY "Firms can insert own bank transactions" ON bank_transactions
    FOR INSERT WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));

-- Indexes for common queries
CREATE INDEX idx_sales_register_lookup ON sales_register (firm_id, client_id, period);
CREATE INDEX idx_purchase_register_lookup ON purchase_register (firm_id, client_id, period);
CREATE INDEX idx_bank_transactions_lookup ON bank_transactions (firm_id, client_id, txn_date);
