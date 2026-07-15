-- Immutable workpaper approvals become stale when their verified registers change.
CREATE OR REPLACE FUNCTION mark_gst_workpapers_stale_from_register()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=public AS $$
BEGIN
  UPDATE gst_workpapers SET stale=true,status='NEEDS_REVIEW',updated_at=NOW()
  WHERE firm_id=NEW.firm_id AND client_id=NEW.client_id AND period=NEW.period
    AND status IN ('APPROVED','READY_FOR_MANUAL_FILING');
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION mark_gst_workpapers_stale_from_register() FROM PUBLIC,anon,authenticated;

DROP TRIGGER IF EXISTS sales_register_stales_gst_workpaper ON sales_register;
CREATE TRIGGER sales_register_stales_gst_workpaper
AFTER INSERT OR UPDATE OF active,source_version,taxable_paise,cgst_paise,sgst_paise,igst_paise,cess_paise,total_paise
ON sales_register FOR EACH ROW EXECUTE FUNCTION mark_gst_workpapers_stale_from_register();

DROP TRIGGER IF EXISTS purchase_register_stales_gst_workpaper ON purchase_register;
CREATE TRIGGER purchase_register_stales_gst_workpaper
AFTER INSERT OR UPDATE OF active,source_version,taxable_paise,cgst_paise,sgst_paise,igst_paise,reverse_charge,itc_classification
ON purchase_register FOR EACH ROW EXECUTE FUNCTION mark_gst_workpapers_stale_from_register();

-- Direct Data API access is intentionally read-only and remains firm-scoped by RLS.
GRANT SELECT ON gst_rule_versions,gst_workpapers,gst_workpaper_sources,gst_filing_acknowledgements TO authenticated;
GRANT SELECT ON itr_workspaces,itr_sources,itr_authorizations,itr_rule_versions,
  itr_schedule_lines,itr_reconciliation_items,itr_filing_events TO authenticated;
