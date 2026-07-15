-- Phase 15: versioned GST workpapers and manual filing packs. No portal submission.
CREATE TABLE gst_rule_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), jurisdiction varchar(30) NOT NULL DEFAULT 'IN',
 rule_key varchar(100) NOT NULL, version varchar(30) NOT NULL,
 effective_from date NOT NULL, effective_to date, source_citation text NOT NULL,
 rule jsonb NOT NULL, tests jsonb NOT NULL DEFAULT '[]', reviewed_by uuid NOT NULL,
 reviewed_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(effective_to IS NULL OR effective_to>=effective_from), UNIQUE(jurisdiction,rule_key,version)
);

CREATE TABLE gst_workpapers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
 client_id varchar(50) NOT NULL, return_type varchar(10) NOT NULL CHECK(return_type IN ('GSTR1','GSTR3B')),
 period varchar(6) NOT NULL CHECK(period~'^(0[1-9]|1[0-2])[0-9]{4}$'), version integer NOT NULL,
 status varchar(32) NOT NULL DEFAULT 'DATA_REQUIRED' CHECK(status IN (
  'DATA_REQUIRED','PREPARING','NEEDS_REVIEW','APPROVED','READY_FOR_MANUAL_FILING',
  'FILED_EXTERNALLY','ACKNOWLEDGEMENT_UPLOADED','COMPLETED')),
 source_versions jsonb NOT NULL, rule_versions jsonb NOT NULL, adjustments jsonb NOT NULL DEFAULT '[]',
 tables jsonb NOT NULL DEFAULT '{}', exceptions jsonb NOT NULL DEFAULT '[]', filing_pack jsonb,
 source_hash varchar(64) NOT NULL, approved_source_hash varchar(64), stale boolean NOT NULL DEFAULT false,
 prepared_by uuid, reviewed_by uuid, approved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(firm_id,client_id,return_type,period,version),
 CHECK(status NOT IN ('APPROVED','READY_FOR_MANUAL_FILING','FILED_EXTERNALLY','ACKNOWLEDGEMENT_UPLOADED','COMPLETED')
       OR (approved_at IS NOT NULL AND approved_source_hash=source_hash AND NOT stale))
);

CREATE TABLE gst_workpaper_sources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workpaper_id uuid NOT NULL REFERENCES gst_workpapers(id) ON DELETE CASCADE,
 firm_id varchar(255) NOT NULL, table_key varchar(50) NOT NULL, source_kind varchar(30) NOT NULL,
 source_id varchar(255) NOT NULL, source_version varchar(100) NOT NULL, amount_paise bigint NOT NULL DEFAULT 0,
 treatment varchar(30) NOT NULL CHECK(treatment IN ('SYSTEM_CALCULATED','IMPORTED','REVIEWER_ADJUSTED')),
 details jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(workpaper_id,table_key,source_kind,source_id,source_version)
);

CREATE TABLE gst_filing_acknowledgements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workpaper_id uuid NOT NULL UNIQUE REFERENCES gst_workpapers(id),
 firm_id varchar(255) NOT NULL, acknowledgement_number text NOT NULL, filed_at timestamptz NOT NULL,
 evidence_reference text NOT NULL, uploaded_by uuid NOT NULL, uploaded_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE gst_rule_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_workpapers ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_workpaper_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_filing_acknowledgements ENABLE ROW LEVEL SECURITY;
CREATE POLICY gst_rules_read ON gst_rule_versions FOR SELECT TO authenticated USING(true);
CREATE POLICY gst_workpapers_firm ON gst_workpapers FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY gst_sources_firm ON gst_workpaper_sources FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY gst_ack_firm ON gst_filing_acknowledgements FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
REVOKE INSERT,UPDATE,DELETE ON gst_rule_versions FROM anon,authenticated;
CREATE INDEX gst_workpaper_scope ON gst_workpapers(firm_id,client_id,period,return_type,version DESC);
CREATE INDEX gst_workpaper_source_link ON gst_workpaper_sources(workpaper_id,table_key);
