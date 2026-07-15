-- Migration: User signup trigger to create firm and set app_metadata
--
-- When a new user signs up in Supabase Auth, they need a firm_id to pass
-- the backend JWT validation. This trigger intercepts the INSERT on auth.users,
-- creates a new firm for them, and sets the firm_id in their app_metadata.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
DECLARE
  new_firm_id uuid;
BEGIN
  -- Create a new firm for the user (defaulting to their email or 'New Firm')
  INSERT INTO public.firms (name)
  VALUES (COALESCE(NEW.email, 'New Firm'))
  RETURNING id INTO new_firm_id;

  -- Update the user's app_metadata with the new firm_id and role
  NEW.raw_app_meta_data = 
    COALESCE(NEW.raw_app_meta_data, '{}'::jsonb) || 
    jsonb_build_object('firm_id', new_firm_id, 'role', 'owner');

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if it exists to allow re-running
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create the trigger
CREATE TRIGGER on_auth_user_created
  BEFORE INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
