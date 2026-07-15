-- TA-003/004/006/016/023: signed devices, replay protection and explicit write state.
ALTER TABLE tally_devices
  ALTER COLUMN token_digest DROP NOT NULL,
  ADD COLUMN public_key text,
  ADD COLUMN write_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN last_read_at timestamptz,
  ADD COLUMN last_write_at timestamptz,
  ADD COLUMN local_queue_depth integer NOT NULL DEFAULT 0 CHECK (local_queue_depth >= 0),
  ADD COLUMN disk_available_bytes bigint CHECK (disk_available_bytes >= 0),
  ADD COLUMN last_error_code varchar(100);

ALTER TABLE tally_sync_logs
  ADD COLUMN payload_hash varchar(64),
  ADD COLUMN total_paise bigint NOT NULL DEFAULT 0;

ALTER TABLE tally_ledgers
  ADD COLUMN gstin varchar(50),
  ADD COLUMN tax_type varchar(100),
  ADD COLUMN deactivated_at timestamptz;

ALTER TABLE tally_vouchers
  ADD COLUMN master_id varchar(100),
  ADD COLUMN alteration_id varchar(100);

CREATE TABLE tally_device_nonces (
  device_id uuid NOT NULL REFERENCES tally_devices(id) ON DELETE CASCADE,
  nonce varchar(100) NOT NULL,
  requested_at bigint NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (device_id, nonce)
);

ALTER TABLE tally_device_nonces ENABLE ROW LEVEL SECURITY;
CREATE POLICY tally_device_nonces_firm ON tally_device_nonces FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM tally_devices d
    WHERE d.id=device_id AND d.firm_id=current_firm_id()
  ));

REVOKE ALL ON tally_device_nonces FROM anon, authenticated;
REVOKE ALL ON tally_device_nonces FROM PUBLIC;
GRANT SELECT ON tally_device_nonces TO authenticated;
GRANT SELECT, INSERT, DELETE ON tally_device_nonces TO service_role;

CREATE INDEX tally_device_nonces_received_idx ON tally_device_nonces(received_at);
CREATE INDEX tally_actions_claim_idx ON finance_actions(
  firm_id, client_id, installation_id, provider, operation, created_at
) WHERE status IN ('QUEUED','CLAIMED','RETRY_SCHEDULED');

-- Existing bearer-token devices must pair again before signed requests are accepted.
UPDATE tally_devices SET status='REVOKED' WHERE public_key IS NULL;
