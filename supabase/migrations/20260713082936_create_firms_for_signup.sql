CREATE TABLE IF NOT EXISTS public.firms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.firms ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    new_firm_id uuid;
BEGIN
    INSERT INTO public.firms (name)
    VALUES (COALESCE(NEW.email, 'New Firm'))
    RETURNING id INTO new_firm_id;

    NEW.raw_app_meta_data = COALESCE(NEW.raw_app_meta_data, '{}'::jsonb)
        || jsonb_build_object('firm_id', new_firm_id, 'role', 'owner');
    RETURN NEW;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
