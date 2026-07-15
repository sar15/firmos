-- Phase 10: safe purchase-invoice ingestion and verified register projection.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS original_filename text,
  ADD COLUMN IF NOT EXISTS mime_type varchar(100),
  ADD COLUMN IF NOT EXISTS size_bytes bigint,
  ADD COLUMN IF NOT EXISTS page_count integer,
  ADD COLUMN IF NOT EXISTS ingestion_state varchar(40) NOT NULL DEFAULT 'READY_FOR_EXTRACTION',
  ADD COLUMN IF NOT EXISTS duplicate_document_id varchar(50) REFERENCES documents(id),
  ADD COLUMN IF NOT EXISTS invoice_identity_key varchar(64),
  ADD COLUMN IF NOT EXISTS validation_state varchar(30) NOT NULL DEFAULT 'PENDING';
CREATE INDEX documents_invoice_identity_idx
  ON documents(firm_id, client_id, invoice_identity_key)
  WHERE invoice_identity_key IS NOT NULL;

CREATE TABLE document_ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id varchar(255) NOT NULL,
  client_id varchar(50) NOT NULL,
  document_id varchar(50) REFERENCES documents(id) ON DELETE SET NULL,
  state varchar(40) NOT NULL CHECK (state IN (
    'RECEIVED','QUARANTINED','VALIDATED','READY_FOR_EXTRACTION','EXTRACTION_FAILED',
    'CORRUPT','PASSWORD_PROTECTED','UNSUPPORTED','OVERSIZED','DUPLICATE'
  )),
  original_filename text NOT NULL,
  object_key text,
  mime_type varchar(100),
  size_bytes bigint NOT NULL,
  content_sha256 varchar(64) NOT NULL,
  error_code varchar(100),
  user_action text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX document_ingestion_lookup_idx
  ON document_ingestion_runs(firm_id, client_id, created_at DESC);

CREATE TABLE document_validation_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id varchar(255) NOT NULL,
  document_id varchar(50) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  draft_version integer NOT NULL DEFAULT 1,
  code varchar(100) NOT NULL,
  severity varchar(20) NOT NULL CHECK (severity IN ('ERROR','WARNING')),
  field_key varchar(100),
  message text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id, draft_version, code, field_key)
);

CREATE TABLE document_field_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id varchar(255) NOT NULL,
  document_id varchar(50) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  field_key varchar(100) NOT NULL,
  page integer,
  region jsonb,
  evidence_text text,
  provider varchar(50),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id, field_key)
);

ALTER TABLE accounting_drafts
  ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS schema_version varchar(30) NOT NULL DEFAULT 'purchase.v1',
  ADD COLUMN IF NOT EXISTS validation_state varchar(30) NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS mappings jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS payload_hash varchar(64);

ALTER TABLE extraction_runs
  ADD COLUMN IF NOT EXISTS model varchar(100),
  ADD COLUMN IF NOT EXISTS prompt_version varchar(30) NOT NULL DEFAULT 'purchase.v1',
  ADD COLUMN IF NOT EXISTS schema_version varchar(30) NOT NULL DEFAULT 'purchase.v1',
  ADD COLUMN IF NOT EXISTS raw_response_url text,
  ADD COLUMN IF NOT EXISTS latency_ms integer,
  ADD COLUMN IF NOT EXISTS usage jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE accounting_draft_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL REFERENCES accounting_drafts(id) ON DELETE RESTRICT,
  firm_id varchar(255) NOT NULL,
  version integer NOT NULL,
  schema_version varchar(30) NOT NULL,
  payload jsonb NOT NULL,
  mappings jsonb NOT NULL DEFAULT '{}'::jsonb,
  totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  validation_state varchar(30) NOT NULL,
  payload_hash varchar(64),
  changed_by varchar(255),
  change_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(draft_id, version)
);

ALTER TABLE purchase_register
  ADD COLUMN IF NOT EXISTS taxable_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cgst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sgst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS igst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS other_charges_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS reverse_charge boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS itc_classification varchar(50),
  ADD COLUMN IF NOT EXISTS source_identity varchar(255),
  ADD COLUMN IF NOT EXISTS source_version varchar(100) NOT NULL DEFAULT '1',
  ADD COLUMN IF NOT EXISTS provider varchar(50),
  ADD COLUMN IF NOT EXISTS provider_object_id varchar(255),
  ADD COLUMN IF NOT EXISTS document_id varchar(50) REFERENCES documents(id),
  ADD COLUMN IF NOT EXISTS accounting_draft_id uuid REFERENCES accounting_drafts(id),
  ADD COLUMN IF NOT EXISTS finance_action_id uuid REFERENCES finance_actions(id),
  ADD COLUMN IF NOT EXISTS verification_id uuid REFERENCES verification_results(id),
  ADD COLUMN IF NOT EXISTS evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS superseded_at timestamptz;
CREATE UNIQUE INDEX purchase_register_source_version_unique
  ON purchase_register(firm_id, client_id, source_identity, source_version)
  WHERE source_identity IS NOT NULL;
ALTER TABLE purchase_register
  DROP CONSTRAINT IF EXISTS purchase_register_firm_id_client_id_zoho_bill_id_key;

CREATE TABLE register_sync_windows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id varchar(255) NOT NULL,
  client_id varchar(50) NOT NULL,
  provider varchar(50) NOT NULL,
  register_type varchar(20) NOT NULL CHECK(register_type IN ('PURCHASE','SALES')),
  period varchar(10) NOT NULL,
  state varchar(20) NOT NULL CHECK(state IN ('RUNNING','PARTIAL','COMPLETE','MISMATCH','FAILED')),
  expected_count integer,
  processed_count integer NOT NULL DEFAULT 0,
  expected_totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  processed_totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  complete_through timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(firm_id, client_id, provider, register_type, period)
);

ALTER TABLE document_ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_validation_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_field_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting_draft_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE register_sync_windows ENABLE ROW LEVEL SECURITY;

-- Backend-only financial workflow tables: service processes set tenant context.
REVOKE ALL ON document_ingestion_runs, document_validation_findings,
  document_field_evidence, accounting_draft_revisions, register_sync_windows
  FROM anon, authenticated;

CREATE POLICY document_ingestion_firm ON document_ingestion_runs FOR ALL
  USING (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)));
CREATE POLICY document_validation_firm ON document_validation_findings FOR ALL
  USING (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)));
CREATE POLICY document_evidence_firm ON document_field_evidence FOR ALL
  USING (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)));
CREATE POLICY accounting_revision_firm ON accounting_draft_revisions FOR ALL
  USING (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)));
CREATE POLICY register_window_firm ON register_sync_windows FOR ALL
  USING (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id=(SELECT current_setting('request.jwt.claim.firm_id', true)));
