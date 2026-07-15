-- handle_new_user is invoked only by the auth.users trigger, never as a public RPC.
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
