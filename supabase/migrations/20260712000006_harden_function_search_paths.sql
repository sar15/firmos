-- Keep SECURITY DEFINER and trigger functions deterministic when resolving names.
ALTER FUNCTION public.handle_new_user() SET search_path = public, pg_catalog;
ALTER FUNCTION public.firmos_block_audit_mutation() SET search_path = public, pg_catalog;
