-- Provider/version/capability certification. Writes are eligible only at L5.
ALTER TABLE capability_certifications
  ADD COLUMN provider varchar(50),
  ADD COLUMN provider_version varchar(100) NOT NULL DEFAULT 'unknown',
  ADD COLUMN certification_level smallint NOT NULL DEFAULT 0
    CHECK (certification_level BETWEEN 0 AND 5),
  ADD COLUMN installation_id uuid REFERENCES connector_installations(id) ON DELETE CASCADE,
  ADD COLUMN evidence jsonb NOT NULL DEFAULT '{}',
  ADD COLUMN certified_by uuid,
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

UPDATE capability_certifications SET provider=CASE
  WHEN capability_key LIKE 'zoho.%' THEN 'ZOHO_BOOKS'
  WHEN capability_key LIKE 'tally.%' THEN 'TALLY_PRIME'
  ELSE 'UNKNOWN'
END WHERE provider IS NULL;
ALTER TABLE capability_certifications ALTER COLUMN provider SET NOT NULL;

ALTER TABLE capability_certifications
  DROP CONSTRAINT IF EXISTS capability_certifications_firm_id_capability_key_key;
CREATE UNIQUE INDEX capability_certification_scope
  ON capability_certifications(
    firm_id, provider, provider_version, capability_key,
    COALESCE(installation_id, '00000000-0000-0000-0000-000000000000'::uuid)
  );
CREATE INDEX capability_certification_gate
  ON capability_certifications(firm_id, installation_id, provider, capability_key, certification_level);

-- Certification is server-owned. Signed-in users may inspect only their firm's evidence via RLS.
REVOKE ALL ON capability_certifications FROM anon, authenticated;
REVOKE ALL ON capability_certifications FROM PUBLIC;
GRANT SELECT ON capability_certifications TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON capability_certifications TO service_role;

-- Capability rows are provider-derived status, never client-authored state.
REVOKE ALL ON connector_capabilities FROM anon, authenticated;
REVOKE ALL ON connector_capabilities FROM PUBLIC;
GRANT SELECT ON connector_capabilities TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON connector_capabilities TO service_role;

-- Preserve complete Tally voucher read state; physical provider certification remains separate.
ALTER TABLE tally_vouchers
  ADD COLUMN reference text NOT NULL DEFAULT '',
  ADD COLUMN provider_status varchar(50) NOT NULL DEFAULT 'ACTIVE',
  ADD COLUMN gst_details jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN tax_total_paise bigint NOT NULL DEFAULT 0;
