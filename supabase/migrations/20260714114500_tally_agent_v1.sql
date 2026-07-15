-- Supported Tally desktop-agent identity and canonical paise snapshots.
CREATE TABLE tally_pairing_codes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
 user_id varchar(255) NOT NULL, client_id varchar(50) NOT NULL,
 installation_id uuid NOT NULL REFERENCES connector_installations(id) ON DELETE CASCADE,
 code_digest varchar(64) NOT NULL UNIQUE, expires_at timestamptz NOT NULL,
 consumed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tally_devices (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
 installation_id uuid NOT NULL REFERENCES connector_installations(id) ON DELETE CASCADE,
 token_digest varchar(64) NOT NULL UNIQUE, display_name varchar(255) NOT NULL,
 company_name varchar(255) NOT NULL, company_guid varchar(255) NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','REVOKED','OFFLINE')),
 agent_version varchar(50), tally_version varchar(100), license_mode varchar(50),
 protocols text[] NOT NULL DEFAULT '{XML}', last_seen_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE tally_ledgers
 ADD COLUMN client_id varchar(50), ADD COLUMN installation_id uuid REFERENCES connector_installations(id),
 ADD COLUMN company_guid varchar(255), ADD COLUMN opening_paise bigint NOT NULL DEFAULT 0,
 ADD COLUMN closing_paise bigint NOT NULL DEFAULT 0, ADD COLUMN active boolean NOT NULL DEFAULT true;
ALTER TABLE tally_vouchers
 ADD COLUMN client_id varchar(50), ADD COLUMN installation_id uuid REFERENCES connector_installations(id),
 ADD COLUMN company_guid varchar(255), ADD COLUMN remote_id varchar(255),
 ADD COLUMN snapshot_hash varchar(64), ADD COLUMN active boolean NOT NULL DEFAULT true,
 ADD COLUMN deleted boolean NOT NULL DEFAULT false, ADD COLUMN altered boolean NOT NULL DEFAULT false;
ALTER TABLE tally_sync_logs
 ADD COLUMN client_id varchar(50), ADD COLUMN installation_id uuid REFERENCES connector_installations(id),
 ADD COLUMN company_guid varchar(255), ADD COLUMN completeness varchar(20) NOT NULL DEFAULT 'COMPLETE';
ALTER TABLE sales_register ADD COLUMN tally_voucher_guid varchar(255);
ALTER TABLE purchase_register ADD COLUMN tally_voucher_guid varchar(255);

ALTER TABLE tally_pairing_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tally_devices ENABLE ROW LEVEL SECURITY;
CREATE POLICY tally_pairing_firm ON tally_pairing_codes FOR ALL
 USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
CREATE POLICY tally_devices_firm ON tally_devices FOR ALL
 USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
REVOKE ALL ON tally_pairing_codes FROM anon, authenticated;
REVOKE ALL ON tally_devices FROM anon, authenticated;

CREATE INDEX tally_devices_firm_seen_idx ON tally_devices(firm_id,last_seen_at DESC);
CREATE UNIQUE INDEX tally_device_active_company ON tally_devices(installation_id,company_guid)
 WHERE status='ACTIVE';
CREATE INDEX tally_vouchers_identity_idx ON tally_vouchers(installation_id,company_guid,remote_id);
CREATE INDEX tally_sync_installation_idx ON tally_sync_logs(installation_id,synced_at DESC);
CREATE UNIQUE INDEX sales_register_tally_identity
 ON sales_register(firm_id,client_id,tally_voucher_guid) WHERE tally_voucher_guid IS NOT NULL;
CREATE UNIQUE INDEX purchase_register_tally_identity
 ON purchase_register(firm_id,client_id,tally_voucher_guid) WHERE tally_voucher_guid IS NOT NULL;
