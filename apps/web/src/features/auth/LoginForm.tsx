"use client";

import React from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { getBrowserAuth } from "@/lib/auth";

export function LoginForm({ configured, configurationError }: { configured: boolean; configurationError: boolean }) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!configured || loading) return;
    setLoading(true);
    setError(null);
    const { error: authError } = await getBrowserAuth().auth.signInWithPassword({ email, password });
    if (authError) {
      setError("Sign-in failed. Check your email and password, then try again.");
      setLoading(false);
      return;
    }
    window.location.assign("/");
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--canvas)] px-4 py-10">
      <section className="w-full max-w-sm rounded-2xl border border-[var(--hairline)] bg-white p-6 shadow-sm">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--royal)] text-lg font-semibold text-white">f</div>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight text-[var(--text)]">Sign in to firmOS</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Use the account assigned to your firm. Client data remains private to your membership.</p>
        {(configurationError || !configured) && <p role="alert" className="mt-4 rounded-lg border border-[var(--red-border)] bg-[var(--red-tint)] p-3 text-sm text-[var(--red)]">Authentication is not configured. Ask the administrator to configure Supabase before continuing.</p>}
        <form onSubmit={submit} className="mt-6 grid gap-4">
          <div className="grid gap-1.5">
            <label htmlFor="email" className="text-sm font-medium text-[var(--text)]">Email</label>
            <input id="email" required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={!configured || loading} className="min-h-11 rounded-lg border border-[var(--hairline-2)] px-3 text-base outline-none focus:border-[var(--royal)]" />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="password" className="text-sm font-medium text-[var(--text)]">Password</label>
            <span className="relative">
              <input id="password" required type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={!configured || loading} className="min-h-11 w-full rounded-lg border border-[var(--hairline-2)] px-3 pr-12 text-base outline-none focus:border-[var(--royal)]" />
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"} className="absolute inset-y-0 right-0 min-h-11 min-w-11 text-[var(--muted)]">{showPassword ? <EyeOff className="mx-auto h-4 w-4" /> : <Eye className="mx-auto h-4 w-4" />}</button>
            </span>
          </div>
          {error && <p role="alert" className="text-sm text-[var(--red)]">{error}</p>}
          <button disabled={!configured || loading} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--royal)] px-4 text-sm font-medium text-white hover:bg-[var(--royal-hover)] disabled:cursor-not-allowed disabled:opacity-50">{loading && <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />} {loading ? "Signing in…" : "Sign in"}</button>
        </form>
      </section>
    </main>
  );
}
