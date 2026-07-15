-- Phase 12: evidence-first GSTR-2B/IMS reconciliation.
CREATE TABLE gstr2b_import_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  upload_hash CHAR(64) NOT NULL,
  gstin VARCHAR(20) NOT NULL,
  return_period VARCHAR(6) NOT NULL CHECK (return_period ~ '^(0[1-9]|1[0-2])[0-9]{4}$'),
  source_format VARCHAR(16) NOT NULL CHECK (source_format IN ('JSON','XLS','XLSX')),
  parser_version VARCHAR(32) NOT NULL,
  source_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_totals JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(24) NOT NULL CHECK (status IN ('PARSING','READY','IDENTITY_MISMATCH','FAILED','RECONCILED')),
  errors JSONB NOT NULL DEFAULT '[]'::jsonb,
  uploaded_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (firm_id, client_id, upload_hash)
);

CREATE TABLE gstr2b_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES gstr2b_import_runs(id) ON DELETE CASCADE,
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  identity_key CHAR(64) NOT NULL,
  supplier_gstin VARCHAR(20) NOT NULL,
  invoice_number TEXT NOT NULL,
  invoice_date DATE NOT NULL,
  document_type VARCHAR(16) NOT NULL CHECK (document_type IN ('INVOICE','CREDIT_NOTE','DEBIT_NOTE','IMPORT')),
  amendment_of_key CHAR(64),
  taxable_paise BIGINT NOT NULL DEFAULT 0,
  igst_paise BIGINT NOT NULL DEFAULT 0,
  cgst_paise BIGINT NOT NULL DEFAULT 0,
  sgst_paise BIGINT NOT NULL DEFAULT 0,
  cess_paise BIGINT NOT NULL DEFAULT 0,
  total_paise BIGINT NOT NULL DEFAULT 0,
  original JSONB NOT NULL
);

CREATE TABLE gstr2b_match_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES gstr2b_import_runs(id) ON DELETE CASCADE,
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  purchase_id VARCHAR(100),
  gstr2b_document_id UUID REFERENCES gstr2b_documents(id) ON DELETE CASCADE,
  bucket VARCHAR(32) NOT NULL CHECK (bucket IN ('EXACT','PROBABLE','MISMATCH','MISSING_IN_2B','MISSING_IN_BOOKS','DUPLICATE','AMENDMENT_CREDIT_NOTE','MANUAL_REVIEW')),
  algorithm_version VARCHAR(32) NOT NULL,
  score NUMERIC(5,4),
  reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  differences JSONB NOT NULL DEFAULT '{}'::jsonb,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  match_decision VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK (match_decision IN ('PENDING','ACCEPTED','REJECTED')),
  ims_decision VARCHAR(16) NOT NULL DEFAULT 'NO_ACTION' CHECK (ims_decision IN ('ACCEPT','REJECT','PENDING','NO_ACTION')),
  recompute_status VARCHAR(16) NOT NULL DEFAULT 'CURRENT' CHECK (recompute_status IN ('CURRENT','STALE','RECOMPUTED')),
  decided_by UUID,
  decided_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE gstr2b_itc_claim_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  identity_key CHAR(64) NOT NULL,
  amendment_root_key CHAR(64),
  claim_period VARCHAR(6) NOT NULL,
  match_result_id UUID REFERENCES gstr2b_match_results(id),
  status VARCHAR(16) NOT NULL CHECK (status IN ('ACCEPTED','REVERSED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (firm_id, client_id, identity_key, status)
);

CREATE TABLE gstr2b_workpapers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES gstr2b_import_runs(id),
  firm_id VARCHAR(255) NOT NULL,
  client_id VARCHAR(50) NOT NULL,
  version INTEGER NOT NULL CHECK (version > 0),
  source_hashes JSONB NOT NULL,
  summary JSONB NOT NULL,
  unresolved_items JSONB NOT NULL,
  reviewer_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (run_id, version)
);

ALTER TABLE gstr2b_import_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE gstr2b_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE gstr2b_match_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE gstr2b_itc_claim_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE gstr2b_workpapers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Firms own GSTR2B runs" ON gstr2b_import_runs FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own GSTR2B documents" ON gstr2b_documents FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own GSTR2B matches" ON gstr2b_match_results FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own ITC history" ON gstr2b_itc_claim_history FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE POLICY "Firms own GSTR2B workpapers" ON gstr2b_workpapers FOR ALL USING (firm_id = current_setting('request.jwt.claim.firm_id', true)) WITH CHECK (firm_id = current_setting('request.jwt.claim.firm_id', true));
CREATE INDEX idx_gstr2b_run_scope ON gstr2b_import_runs (firm_id, client_id, return_period, created_at DESC);
CREATE INDEX idx_gstr2b_identity ON gstr2b_documents (firm_id, client_id, identity_key);
CREATE INDEX idx_gstr2b_run_identity ON gstr2b_documents (run_id, identity_key);
CREATE INDEX idx_gstr2b_match_review ON gstr2b_match_results (run_id, bucket, match_decision);
