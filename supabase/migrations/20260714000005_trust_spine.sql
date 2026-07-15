-- TS-002..013: identity, tenant helpers, durable jobs, and verified finance actions.
CREATE OR REPLACE FUNCTION current_firm_id() RETURNS text LANGUAGE sql STABLE SET search_path = '' AS
$$ SELECT NULLIF(current_setting('request.jwt.claim.firm_id', true), '') $$;
CREATE OR REPLACE FUNCTION current_user_id() RETURNS text LANGUAGE sql STABLE SET search_path = '' AS
$$ SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '') $$;
CREATE TABLE firm_memberships (
    firm_id varchar(255) NOT NULL,
    user_id uuid NOT NULL,
    role varchar(20) NOT NULL CHECK (role IN ('OWNER','ADMIN','PREPARER','REVIEWER','VIEWER')),
    status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED','REVOKED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (firm_id, user_id)
);
CREATE TABLE firm_invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
    email text NOT NULL, role varchar(20) NOT NULL, invited_by uuid NOT NULL,
    expires_at timestamptz NOT NULL, accepted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firm_id, email)
);
ALTER TABLE firm_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE firm_invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY memberships_read ON firm_memberships FOR SELECT
    USING (user_id::text=current_user_id() OR firm_id=current_firm_id());
CREATE POLICY invitations_firm ON firm_invitations FOR ALL
    USING (firm_id=current_firm_id()) WITH CHECK (firm_id=current_firm_id());

CREATE TABLE outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
    topic varchar(100) NOT NULL, aggregate_id varchar(255) NOT NULL, payload jsonb NOT NULL,
    correlation_id varchar(100) NOT NULL, published_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE automation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
    kind varchar(100) NOT NULL, aggregate_id varchar(255) NOT NULL, payload jsonb NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'QUEUED', attempt_count int NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(), lease_owner varchar(100), lease_expires_at timestamptz,
    correlation_id varchar(100) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, aggregate_id)
);
CREATE TABLE automation_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job_id uuid NOT NULL REFERENCES automation_jobs(id),
    attempt_number int NOT NULL, status varchar(30) NOT NULL, error_code varchar(100),
    started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, UNIQUE(job_id, attempt_number)
);
CREATE TABLE dead_letters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job_id uuid NOT NULL UNIQUE REFERENCES automation_jobs(id),
    reason_code varchar(100) NOT NULL, safe_message text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE automation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE automation_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_letters ENABLE ROW LEVEL SECURITY;
CREATE POLICY outbox_firm ON outbox_events FOR ALL USING (firm_id=current_firm_id()) WITH CHECK (firm_id=current_firm_id());
CREATE POLICY jobs_firm ON automation_jobs FOR ALL USING (firm_id=current_firm_id()) WITH CHECK (firm_id=current_firm_id());
CREATE POLICY attempts_firm ON automation_attempts FOR ALL USING (EXISTS(
  SELECT 1 FROM automation_jobs j WHERE j.id=job_id AND j.firm_id=current_firm_id()));
CREATE POLICY dead_letters_firm ON dead_letters FOR ALL USING (EXISTS(
  SELECT 1 FROM automation_jobs j WHERE j.id=job_id AND j.firm_id=current_firm_id()));

DROP POLICY IF EXISTS "Users can insert their firm's chat messages" ON chat_messages;
DROP POLICY IF EXISTS "Users can read their firm's chat messages" ON chat_messages;
CREATE POLICY chat_firm ON chat_messages FOR ALL
  USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());
DROP POLICY IF EXISTS "Firms can read own worker heartbeats" ON worker_heartbeats;
DROP POLICY IF EXISTS "Firms can write own worker heartbeats" ON worker_heartbeats;
DROP POLICY IF EXISTS "Firms can update own worker heartbeats" ON worker_heartbeats;
CREATE POLICY heartbeat_firm ON worker_heartbeats FOR ALL
  USING(firm_id=current_firm_id()) WITH CHECK(firm_id=current_firm_id());

ALTER TABLE finance_actions
    ADD COLUMN IF NOT EXISTS installation_id uuid,
    ADD COLUMN IF NOT EXISTS source_identity varchar(255),
    ADD COLUMN IF NOT EXISTS source_version varchar(100) NOT NULL DEFAULT '1',
    ADD COLUMN IF NOT EXISTS correlation_id varchar(100),
    ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS attempt_number integer NOT NULL DEFAULT 0;
UPDATE finance_actions SET status=CASE status
    WHEN 'PENDING_APPROVAL' THEN 'AWAITING_APPROVAL'
    WHEN 'RETRYING' THEN 'RETRY_SCHEDULED'
    ELSE status END;
ALTER TABLE finance_actions DROP CONSTRAINT IF EXISTS finance_actions_status_check;
ALTER TABLE finance_actions ADD CONSTRAINT finance_actions_status_check CHECK (status IN (
    'DRAFT','VALIDATED','AWAITING_APPROVAL','APPROVED','QUEUED','CLAIMED','EXECUTING',
    'PROVIDER_ACCEPTED','VERIFYING','SUCCEEDED','NEEDS_INPUT','NEEDS_REVIEW','RETRY_SCHEDULED',
    'AUTH_EXPIRED','FAILED','DEAD_LETTER','CANCELLED'));

CREATE TABLE provider_objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
    installation_id uuid, object_type varchar(100) NOT NULL, provider_id varchar(255) NOT NULL,
    internal_source_id varchar(255), provider_version varchar(100), snapshot_hash varchar(64) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE', active boolean NOT NULL DEFAULT true,
    void boolean NOT NULL DEFAULT false, deleted boolean NOT NULL DEFAULT false,
    last_seen_at timestamptz NOT NULL DEFAULT now(), last_verified_at timestamptz,
    UNIQUE (firm_id, installation_id, object_type, provider_id)
);
CREATE TABLE verification_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), firm_id varchar(255) NOT NULL,
    action_id uuid NOT NULL REFERENCES finance_actions(id), provider_object_id uuid NOT NULL REFERENCES provider_objects(id),
    status varchar(30) NOT NULL CHECK (status IN ('MATCHED','MISMATCH','AMBIGUOUS','FAILED')),
    verified_fields jsonb NOT NULL DEFAULT '{}', mismatches jsonb NOT NULL DEFAULT '{}',
    provider_version varchar(100), fetched_at timestamptz NOT NULL DEFAULT now(), correlation_id varchar(100) NOT NULL
);
ALTER TABLE provider_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY provider_objects_firm ON provider_objects FOR ALL USING (firm_id=current_firm_id()) WITH CHECK (firm_id=current_firm_id());
CREATE POLICY verification_firm ON verification_results FOR ALL USING (firm_id=current_firm_id()) WITH CHECK (firm_id=current_firm_id());

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS correlation_id varchar(100);
ALTER TABLE finance_runs ADD COLUMN IF NOT EXISTS verification_result_id uuid REFERENCES verification_results(id);

CREATE OR REPLACE FUNCTION require_verified_success() RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_catalog AS $$
BEGIN
  IF NEW.status='SUCCEEDED' AND NOT EXISTS (
    SELECT 1 FROM verification_results WHERE action_id=NEW.id AND status='MATCHED'
  ) THEN RAISE EXCEPTION 'SUCCEEDED requires a matched verification result'; END IF;
  IF OLD.approved_at IS NOT NULL AND NEW.payload IS DISTINCT FROM OLD.payload THEN
    RAISE EXCEPTION 'Approved finance action payload is immutable'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER finance_action_verified_success BEFORE UPDATE ON finance_actions
FOR EACH ROW EXECUTE FUNCTION require_verified_success();

CREATE OR REPLACE FUNCTION enforce_finance_action_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_catalog AS $$
DECLARE allowed boolean;
BEGIN
  IF NEW.status=OLD.status THEN RETURN NEW; END IF;
  allowed := CASE OLD.status
    WHEN 'DRAFT' THEN NEW.status IN ('VALIDATED','CANCELLED','NEEDS_INPUT')
    WHEN 'VALIDATED' THEN NEW.status IN ('AWAITING_APPROVAL','NEEDS_INPUT','CANCELLED')
    WHEN 'AWAITING_APPROVAL' THEN NEW.status IN ('APPROVED','CANCELLED')
    WHEN 'APPROVED' THEN NEW.status IN ('QUEUED','CANCELLED')
    WHEN 'QUEUED' THEN NEW.status IN ('CLAIMED','CANCELLED')
    WHEN 'CLAIMED' THEN NEW.status IN ('EXECUTING','RETRY_SCHEDULED','FAILED')
    WHEN 'EXECUTING' THEN NEW.status IN ('PROVIDER_ACCEPTED','RETRY_SCHEDULED','AUTH_EXPIRED','FAILED','NEEDS_REVIEW')
    WHEN 'PROVIDER_ACCEPTED' THEN NEW.status IN ('VERIFYING','NEEDS_REVIEW')
    WHEN 'VERIFYING' THEN NEW.status IN ('SUCCEEDED','NEEDS_REVIEW','RETRY_SCHEDULED','FAILED')
    WHEN 'RETRY_SCHEDULED' THEN NEW.status IN ('QUEUED','DEAD_LETTER','CANCELLED')
    WHEN 'NEEDS_INPUT' THEN NEW.status IN ('VALIDATED','CANCELLED')
    WHEN 'NEEDS_REVIEW' THEN NEW.status IN ('QUEUED','FAILED','CANCELLED')
    WHEN 'AUTH_EXPIRED' THEN NEW.status IN ('QUEUED','CANCELLED')
    WHEN 'FAILED' THEN NEW.status IN ('QUEUED','DEAD_LETTER','CANCELLED')
    ELSE false END;
  IF NOT allowed THEN RAISE EXCEPTION 'Invalid finance action transition: % -> %', OLD.status, NEW.status; END IF;
  NEW.version := OLD.version + 1;
  RETURN NEW;
END $$;
CREATE TRIGGER finance_action_transition BEFORE UPDATE ON finance_actions
FOR EACH ROW EXECUTE FUNCTION enforce_finance_action_transition();
