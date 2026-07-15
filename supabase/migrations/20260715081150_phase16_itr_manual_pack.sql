-- Phase 16: AY-specific ITR drafting and external filing evidence tracking.
CREATE TABLE itr_workspaces (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL, client_id varchar(50) NOT NULL,
 assessment_year varchar(7) NOT NULL CHECK(assessment_year~'^[0-9]{4}-[0-9]{2}$'), taxpayer_pan varchar(10) NOT NULL,
 taxpayer_name text NOT NULL, status varchar(28) NOT NULL DEFAULT 'DATA_REQUIRED' CHECK(status IN (
  'DATA_REQUIRED','PREPARING','NEEDS_REVIEW','APPROVED','READY_FOR_MANUAL_FILING','FILED_EXTERNALLY',
  'E_VERIFICATION_PENDING','REJECTED','ACKNOWLEDGEMENT_UPLOADED','COMPLETED')),
 source_hash varchar(64), approved_source_hash varchar(64), stale boolean NOT NULL DEFAULT false,
 computation jsonb NOT NULL DEFAULT '{}', filing_pack jsonb, approved_by uuid, approved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(firm_id,client_id,assessment_year),
 CHECK(status NOT IN ('APPROVED','READY_FOR_MANUAL_FILING','FILED_EXTERNALLY','E_VERIFICATION_PENDING',
  'ACKNOWLEDGEMENT_UPLOADED','COMPLETED') OR (approved_at IS NOT NULL AND approved_source_hash=source_hash AND NOT stale))
);

CREATE TABLE itr_sources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES itr_workspaces(id) ON DELETE CASCADE,
 firm_id varchar(255) NOT NULL, source_type varchar(20) NOT NULL CHECK(source_type IN (
  'AIS','TIS','26AS','FORM16','FORM16A','BOOKS','BANK','EVIDENCE')),
 source_period varchar(20) NOT NULL, taxpayer_pan varchar(10) NOT NULL, document_id varchar(50) REFERENCES documents(id),
 source_version varchar(100) NOT NULL, extracted_values jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(workspace_id,source_type,source_version)
);

CREATE TABLE itr_authorizations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES itr_workspaces(id),
 firm_id varchar(255) NOT NULL, authorized_by text NOT NULL, evidence_reference text NOT NULL,
 permissions text[] NOT NULL CHECK(permissions<@ARRAY['VIEW','PREPARE','APPROVE']::text[]),
 granted_to uuid NOT NULL, granted_at timestamptz NOT NULL, revoked_at timestamptz
);

CREATE TABLE itr_rule_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), assessment_year varchar(7) NOT NULL,
 rule_key varchar(100) NOT NULL, version varchar(30) NOT NULL, source_citation text NOT NULL,
 rule jsonb NOT NULL, tests jsonb NOT NULL DEFAULT '[]', reviewed_by uuid NOT NULL,
 reviewed_at timestamptz NOT NULL DEFAULT now(), UNIQUE(assessment_year,rule_key,version)
);

CREATE TABLE itr_schedule_lines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES itr_workspaces(id) ON DELETE CASCADE,
 firm_id varchar(255) NOT NULL, schedule_key varchar(50) NOT NULL, line_key varchar(100) NOT NULL,
 amount_paise bigint NOT NULL, source_links jsonb NOT NULL, rule_id uuid REFERENCES itr_rule_versions(id),
 rounding_rule varchar(50) NOT NULL DEFAULT 'NEAREST_RUPEE', reviewer_adjustment_paise bigint NOT NULL DEFAULT 0,
 explanation text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(workspace_id,schedule_key,line_key)
);

CREATE TABLE itr_reconciliation_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES itr_workspaces(id) ON DELETE CASCADE,
 firm_id varchar(255) NOT NULL, category varchar(50) NOT NULL, source_values jsonb NOT NULL,
 difference_paise bigint NOT NULL DEFAULT 0, status varchar(20) NOT NULL CHECK(status IN ('MATCHED','CONFLICT','MISSING_EVIDENCE','RESOLVED')),
 resolution text, resolved_by uuid, resolved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE itr_filing_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES itr_workspaces(id),
 firm_id varchar(255) NOT NULL, event_type varchar(30) NOT NULL CHECK(event_type IN (
  'FILED_EXTERNALLY','PAYMENT_RECORDED','E_VERIFIED','REJECTED','ACKNOWLEDGEMENT_UPLOADED')),
 reference text NOT NULL, evidence_reference text, occurred_at timestamptz NOT NULL, recorded_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE itr_workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_authorizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_rule_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_schedule_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_reconciliation_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE itr_filing_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY itr_workspace_firm ON itr_workspaces FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY itr_sources_firm ON itr_sources FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY itr_auth_firm ON itr_authorizations FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY itr_rules_read ON itr_rule_versions FOR SELECT TO authenticated USING(true);
CREATE POLICY itr_lines_firm ON itr_schedule_lines FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY itr_recon_firm ON itr_reconciliation_items FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY itr_events_firm ON itr_filing_events FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
REVOKE INSERT,UPDATE,DELETE ON itr_rule_versions FROM anon,authenticated;
CREATE INDEX itr_workspace_scope ON itr_workspaces(firm_id,client_id,assessment_year);
CREATE INDEX itr_sources_workspace ON itr_sources(workspace_id,source_type);
