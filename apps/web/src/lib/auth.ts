import { createBrowserClient } from "@supabase/ssr";

let supabase: ReturnType<typeof createBrowserClient> | null = null;

export const getBrowserAuth = () => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("Authentication is not configured.");
  supabase ??= createBrowserClient(url, key);
  return supabase;
};

export const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const { data, error } = await getBrowserAuth().auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Your session has expired. Sign in again.");
  return { "Content-Type": "application/json", Authorization: `Bearer ${data.session.access_token}`, "X-Correlation-ID": crypto.randomUUID() };
};
