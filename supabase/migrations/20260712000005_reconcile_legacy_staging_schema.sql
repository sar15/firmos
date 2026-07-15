-- Reconcile staging drift from the two historical migrations that were only partially present.
-- Forward-only: do not rewrite migration history or delete existing bank/chat data.

CREATE TABLE IF NOT EXISTS public.sales_register (
    id VARCHAR(50) PRIMARY KEY,
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50) NOT NULL,
    period VARCHAR(10) NOT NULL,
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

CREATE TABLE IF NOT EXISTS public.purchase_register (
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
    source VARCHAR(20) NOT NULL DEFAULT 'ZOHO',
    status VARCHAR(50),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(firm_id, client_id, zoho_bill_id)
);

ALTER TABLE public.sales_register ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_register ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_statements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['sales_register','purchase_register','bank_statements','bank_transactions'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS "Firm data is private" ON public.%I', table_name);
    EXECUTE format('CREATE POLICY "Firm data is private" ON public.%I FOR ALL USING (firm_id = ((current_setting(''request.jwt.claims'', true))::json ->> ''firm_id'')) WITH CHECK (firm_id = ((current_setting(''request.jwt.claims'', true))::json ->> ''firm_id''))', table_name);
  END LOOP;
END $$;

-- Checkpoints are optional LangGraph state and never browser-accessible data.
DO $$
DECLARE table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['checkpoint_migrations','checkpoints','checkpoint_blobs','checkpoint_writes'] LOOP
    IF to_regclass(format('public.%I', table_name)) IS NULL THEN
      CONTINUE;
    END IF;
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('DROP POLICY IF EXISTS "Service role manages internal checkpoints" ON public.%I', table_name);
    EXECUTE format('CREATE POLICY "Service role manages internal checkpoints" ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)', table_name);
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_sales_register_lookup ON public.sales_register (firm_id, client_id, period);
CREATE INDEX IF NOT EXISTS idx_purchase_register_lookup ON public.purchase_register (firm_id, client_id, period);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_lookup ON public.bank_transactions (firm_id, client_id, txn_date);
