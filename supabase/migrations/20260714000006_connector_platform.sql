-- CP-001 shared connector control plane.
CREATE TABLE connector_installations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL, client_id varchar(50),
 provider varchar(50) NOT NULL, environment varchar(20) NOT NULL CHECK(environment IN ('sandbox','production','local')), display_name varchar(255) NOT NULL,
 status varchar(30) NOT NULL DEFAULT 'CONFIGURATION_REQUIRED' CHECK(status IN ('CONFIGURATION_REQUIRED','AVAILABLE','DEGRADED','AUTH_EXPIRED','DISCONNECTED')), implementation_version varchar(50) NOT NULL,
 configuration jsonb NOT NULL DEFAULT '{}', last_probe_at timestamptz, last_success_at timestamptz,
 created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 version integer NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX connector_installation_identity ON connector_installations
 (firm_id,client_id,provider,environment) NULLS NOT DISTINCT;
CREATE TABLE connector_credentials (
 installation_id uuid PRIMARY KEY REFERENCES connector_installations(id) ON DELETE CASCADE,
 ciphertext bytea NOT NULL, data_center varchar(100), api_domain varchar(255), scopes text[] NOT NULL DEFAULT '{}',
 issued_at timestamptz, expires_at timestamptz, rotated_at timestamptz, revoked_at timestamptz,
 key_version varchar(50) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE connector_capabilities (
 installation_id uuid NOT NULL REFERENCES connector_installations(id) ON DELETE CASCADE,
 capability_key varchar(150) NOT NULL, state varchar(40) NOT NULL CHECK(state IN ('UNAVAILABLE','DISABLED','INTERNAL_ONLY','CONFIGURATION_REQUIRED','AVAILABLE','DEGRADED','BLOCKED_AUTH','BLOCKED_MAPPING','BLOCKED_DEVICE','FAILED_CERTIFICATION')), reason_code varchar(100),
 certification_version varchar(50), last_tested_at timestamptz, PRIMARY KEY(installation_id, capability_key)
);
CREATE TABLE connector_mappings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL, client_id varchar(50),
 installation_id uuid NOT NULL REFERENCES connector_installations(id), mapping_type varchar(30) NOT NULL CHECK(mapping_type IN ('company','organization','contact','ledger','item','tax','branch','cost_center')),
 internal_id varchar(255) NOT NULL, provider_id varchar(255) NOT NULL, normalized_name text,
 tax_identity varchar(50), source varchar(20) NOT NULL CHECK(source IN ('MANUAL','EXACT','LEARNED_SUGGESTION')), confidence numeric(5,4) CHECK(confidence BETWEEN 0 AND 1),
 approved_by uuid, approved_at timestamptz, version integer NOT NULL DEFAULT 1,
 active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX connector_mapping_active ON connector_mappings(installation_id,mapping_type,internal_id) WHERE active;
CREATE TABLE connector_sync_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
 installation_id uuid NOT NULL REFERENCES connector_installations(id), capability_key varchar(150) NOT NULL,
 client_id varchar(50), period varchar(20), status varchar(30) NOT NULL DEFAULT 'QUEUED', cursor text,
 completeness varchar(20) NOT NULL DEFAULT 'NONE' CHECK(completeness IN ('NONE','PARTIAL','COMPLETE')), expected_count integer CHECK(expected_count>=0), processed_count integer NOT NULL DEFAULT 0 CHECK(processed_count>=0),
 expected_total_paise bigint, processed_total_paise bigint NOT NULL DEFAULT 0, retry_count integer NOT NULL DEFAULT 0 CHECK(retry_count>=0),
 lease_owner varchar(100), lease_expires_at timestamptz, started_at timestamptz, finished_at timestamptz,
 correlation_id varchar(100) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE connector_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
 installation_id uuid NOT NULL REFERENCES connector_installations(id), provider_event_id varchar(255),
 dedupe_key varchar(255) NOT NULL, raw_payload_reference text, status varchar(30) NOT NULL DEFAULT 'PENDING',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(installation_id,dedupe_key)
);
ALTER TABLE provider_objects ADD CONSTRAINT provider_objects_installation_fk
 FOREIGN KEY (installation_id) REFERENCES connector_installations(id);

ALTER TABLE connector_installations ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_sync_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY installations_firm ON connector_installations FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY credentials_firm ON connector_credentials FOR ALL USING(EXISTS(SELECT 1 FROM connector_installations i WHERE i.id=installation_id AND i.firm_id=current_firm_id()));
CREATE POLICY capabilities_firm ON connector_capabilities FOR ALL USING(EXISTS(SELECT 1 FROM connector_installations i WHERE i.id=installation_id AND i.firm_id=current_firm_id()));
CREATE POLICY mappings_firm ON connector_mappings FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY sync_jobs_firm ON connector_sync_jobs FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY events_firm ON connector_events FOR ALL USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
REVOKE SELECT ON connector_credentials FROM anon, authenticated;
