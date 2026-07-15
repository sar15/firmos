-- Harden functions introduced by the trust-spine migration on existing databases.
ALTER FUNCTION public.current_firm_id() SET search_path = '';
ALTER FUNCTION public.current_user_id() SET search_path = '';
ALTER FUNCTION public.require_verified_success() SET search_path = public, pg_catalog;
ALTER FUNCTION public.enforce_finance_action_transition() SET search_path = public, pg_catalog;
