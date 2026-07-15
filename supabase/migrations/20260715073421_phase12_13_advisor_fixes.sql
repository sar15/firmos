-- Advisor fixes scoped to phase 12/13 tables: one cached tenant predicate per table.
DO $$
DECLARE
  item RECORD;
BEGIN
  FOR item IN SELECT * FROM (VALUES
    ('gstr2b_import_runs','Firms own GSTR2B runs'),
    ('gstr2b_documents','Firms own GSTR2B documents'),
    ('gstr2b_match_results','Firms own GSTR2B matches'),
    ('gstr2b_itc_claim_history','Firms own ITC history'),
    ('gstr2b_workpapers','Firms own GSTR2B workpapers'),
    ('bank_match_candidates','Firms own bank candidates'),
    ('bank_reconciliation_proofs','Firms own bank proofs')
  ) AS policies(table_name, policy_name)
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', item.policy_name, item.table_name);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL USING (firm_id = (SELECT current_setting(''request.jwt.claim.firm_id'', true))) WITH CHECK (firm_id = (SELECT current_setting(''request.jwt.claim.firm_id'', true)))',
      item.policy_name, item.table_name
    );
  END LOOP;
END $$;

DROP POLICY IF EXISTS "Firms can read own bank statements" ON bank_statements;
DROP POLICY IF EXISTS "Firms can insert own bank statements" ON bank_statements;
DROP POLICY IF EXISTS "Firm data is private" ON bank_statements;
CREATE POLICY "Firm data is private" ON bank_statements FOR ALL
  USING (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)));

DROP POLICY IF EXISTS "Firms can read own bank transactions" ON bank_transactions;
DROP POLICY IF EXISTS "Firms can insert own bank transactions" ON bank_transactions;
DROP POLICY IF EXISTS "Firm data is private" ON bank_transactions;
CREATE POLICY "Firm data is private" ON bank_transactions FOR ALL
  USING (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)))
  WITH CHECK (firm_id = (SELECT current_setting('request.jwt.claim.firm_id', true)));
