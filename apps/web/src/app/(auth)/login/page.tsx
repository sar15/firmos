import { redirect } from "next/navigation";
import { LoginForm } from "@/features/auth/LoginForm";
import { createServerSupabaseClient, serverSupabaseConfigured } from "@/lib/supabase/server";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  const configured = serverSupabaseConfigured();
  if (configured) {
    const supabase = await createServerSupabaseClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/");
  }
  const reason = (await searchParams).reason;
  return <LoginForm configured={configured} configurationError={reason === "config"} />;
}
