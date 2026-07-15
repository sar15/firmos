-- Phase 13: canonical bank ingestion and explainable reconciliation.
ALTER TABLE bank_statements ADD COLUMN upload_hash CHAR(64);
ALTER TABLE bank_statements ADD COLUMN source_format VARCHAR(16);
ALTER TABLE bank_statements ADD COLUMN parser_adapter VARCHAR(64);
ALTER TABLE bank_statements ADD COLUMN parser_version VARCHAR(32);
ALTER TABLE bank_statements ADD COLUMN bank_name TEXT;
ALTER TABLE bank_statements ADD COLUMN account_number_masked TEXT;
ALTER TABLE bank_statements ADD COLUMN period_start DATE;
ALTER TABLE bank_statements ADD COLUMN period_end DATE;
ALTER TABLE bank_statements ADD COLUMN opening_balance_paise BIGINT;
ALTER TABLE bank_statements ADD COLUMN closing_balance_paise BIGINT;
ALTER TABLE bank_statements ADD COLUMN integrity_status VARCHAR(24) DEFAULT 'NOT_CHECKED';
ALTER TABLE bank_statements ADD COLUMN integrity_details JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE UNIQUE INDEX bank_statement_upload_identity ON bank_statements (firm_id, client_id, upload_hash) WHERE upload_hash IS NOT NULL;

ALTER TABLE bank_transactions ADD COLUMN value_date DATE;
ALTER TABLE bank_transactions ADD COLUMN reference TEXT;
ALTER TABLE bank_transactions ADD COLUMN debit_paise BIGINT NOT NULL DEFAULT 0;
ALTER TABLE bank_transactions ADD COLUMN credit_paise BIGINT NOT NULL DEFAULT 0;
ALTER TABLE bank_transactions ADD COLUMN source_row INTEGER;
ALTER TABLE bank_transactions ADD COLUMN source_page INTEGER;
ALTER TABLE bank_transactions ADD COLUMN normalized_tokens TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE bank_transactions ADD COLUMN canonical_hash CHAR(64);

CREATE TABLE bank_match_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  statement_id VARCHAR(50) NOT NULL REFERENCES bank_statements(id) ON DELETE CASCADE,
  bank_transaction_id VARCHAR(50) NOT NULL REFERENCES bank_transactions(id) ON DELETE CASCADE,
  candidate_source VARCHAR(24) NOT NULL CHECK (candidate_source IN ('INVOICE','RECEIPT','PAYMENT','VOUCHER','PROVIDER_BANK_TXN')),
  candidate_id VARCHAR(100) NOT NULL,
  algorithm_version VARCHAR(32) NOT NULL,
  score NUMERIC(5,4) NOT NULL CHECK (score BETWEEN 0 AND 1),
  reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  candidate_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(16) NOT NULL DEFAULT 'SUGGESTED' CHECK (status IN ('SUGGESTED','ACCEPTED','REJECTED')),
  decided_by UUID,
  decided_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (bank_transaction_id, candidate_source, candidate_id, algorithm_version)
);

CREATE TABLE bank_reconciliation_proofs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  statement_id VARCHAR(50) NOT NULL REFERENCES bank_statements(id),
  version INTEGER NOT NULL CHECK (version > 0),
  statement_balance_paise BIGINT NOT NULL,
  matched_paise BIGINT NOT NULL DEFAULT 0,
  unmatched_paise BIGINT NOT NULL DEFAULT 0,
  created_entries JSONB NOT NULL DEFAULT '[]'::jsonb,
  linked_entries JSONB NOT NULL DEFAULT '[]'::jsonb,
  unresolved_difference_paise BIGINT NOT NULL DEFAULT 0,
  explanation TEXT,
  completed BOOLEAN NOT NULL DEFAULT FALSE,
  reviewer_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (NOT completed OR unresolved_difference_paise = 0),
  UNIQUE (statement_id, version)
);

ALTER TABLE bank_match_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_reconciliation_proofs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Firms own bank candidates" ON bank_match_candidates FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own bank proofs" ON bank_reconciliation_proofs FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE INDEX idx_bank_candidate_review ON bank_match_candidates (statement_id, status, score DESC);
CREATE INDEX idx_bank_transaction_canonical ON bank_transactions (firm_id, client_id, canonical_hash);
