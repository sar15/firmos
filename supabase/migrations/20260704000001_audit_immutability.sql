-- Migration: harden audit_log immutability + index for firm queries
--
-- The initial migration revoked UPDATE/DELETE from PUBLIC and authenticated.
-- Supabase roles that can still reach the table: anon, service_role, and any
-- future role. TRUNCATE was never revoked either. A superuser can always bypass
-- (that's inherent to Postgres), but no application role should be able to
-- mutate or truncate the audit log. Trust is the product: INSERT only.

-- Revoke every mutation path from every non-superuser role we know of.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM authenticated;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM anon;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM service_role;

-- Belt-and-suspenders: if a future migration adds the service_role back, this
-- trigger re-asserts immutability at the database layer. Any UPDATE/DELETE/
-- TRUNCATE attempt raises an exception rather than silently succeeding.
CREATE OR REPLACE FUNCTION firmos_block_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only (INSERT only). Mutation blocked.';
END;
$$;

DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION firmos_block_audit_mutation();

DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;
CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION firmos_block_audit_mutation();

DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION firmos_block_audit_mutation();

-- Performance index: every audit screen filters by firm + recency.
CREATE INDEX IF NOT EXISTS idx_audit_log_firm_created
    ON audit_log (firm_id, created_at DESC);
