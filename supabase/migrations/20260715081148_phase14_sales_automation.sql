-- Phase 14: verified sales projection and review-bound invoice automation.
ALTER TABLE sales_register
  ADD COLUMN IF NOT EXISTS customer_gstin varchar(20),
  ADD COLUMN IF NOT EXISTS place_of_supply varchar(100),
  ADD COLUMN IF NOT EXISTS taxable_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cgst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sgst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS igst_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cess_paise bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS e_invoice jsonb NOT NULL DEFAULT '{}'::jsonb,
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

ALTER TABLE sales_register
  DROP CONSTRAINT IF EXISTS sales_register_firm_id_client_id_zoho_invoice_id_key;
CREATE UNIQUE INDEX sales_register_source_version_unique
  ON sales_register(firm_id,client_id,source_identity,source_version)
  WHERE source_identity IS NOT NULL;
CREATE INDEX sales_register_active_period
  ON sales_register(firm_id,client_id,period,invoice_date DESC) WHERE active;

-- Generic document/draft infrastructure is reused; only its schema vocabulary expands.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS transaction_direction varchar(10)
  CHECK(transaction_direction IN ('PURCHASE','SALE'));
ALTER TABLE accounting_drafts ADD COLUMN IF NOT EXISTS review_context jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Certification evidence remains server-owned and capability-specific.
COMMENT ON COLUMN sales_register.source_version IS
  'Provider snapshot hash or immutable upload/draft version used for supersession.';
