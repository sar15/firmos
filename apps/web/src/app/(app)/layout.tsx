import { AppShell } from "@/components/AppShell";
import { redirect } from "next/navigation";
import { createServerSupabaseClient, serverSupabaseConfigured } from "@/lib/supabase/server";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!serverSupabaseConfigured()) redirect("/login?reason=config");
  const supabase = await createServerSupabaseClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) redirect("/login");
  return <AppShell userEmail={data.user.email ?? "Signed-in user"}>{children}</AppShell>;
}
