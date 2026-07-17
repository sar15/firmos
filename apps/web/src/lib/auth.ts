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

const selectedFirmKey = "firmos:selectedFirmId";

export const setSelectedFirmId = (firmId: string) => {
  window.localStorage.setItem(selectedFirmKey, firmId);
};

export const getAuthHeaders = async (
  options: { includeFirm?: boolean } = {},
): Promise<Record<string, string>> => {
  const { data, error } = await getBrowserAuth().auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Your session has expired. Sign in again.");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${data.session.access_token}`,
    "X-Correlation-ID": crypto.randomUUID(),
  };
  const selectedFirmId = window.localStorage.getItem(selectedFirmKey);
  if (options.includeFirm !== false && selectedFirmId) headers["X-FirmOS-Firm"] = selectedFirmId;
  return headers;
};
