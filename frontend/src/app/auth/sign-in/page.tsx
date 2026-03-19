"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { apiPost } from "@/lib/api";
import { setAuthSession, type AuthUser } from "@/lib/auth";

type AuthResponse = {
  ok: boolean;
  token: string;
  user: AuthUser;
};

export default function SignInPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = useMemo(() => searchParams.get("returnTo") || "/dashboard/community", [searchParams]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<AuthResponse>("/auth/login", { email, password });
      setAuthSession(res.token, res.user);
      router.push(returnTo);
    } catch (err: any) {
      setError(err?.message ?? "Failed to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">
      <div className="mx-auto max-w-md rounded-3xl border border-white/10 bg-white/5 p-6">
        <Link href="/dashboard/community" className="text-sm text-white/70 hover:text-white">← Back</Link>
        <h1 className="mt-4 text-2xl font-semibold">Sign in to SportLytics</h1>
        <p className="mt-2 text-sm text-white/65">Browse freely without an account. Sign in only when you want to post in Community or unlock future Pulse features.</p>
        {error ? <div className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">{error}</div> : null}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <input className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 outline-none" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 outline-none" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button disabled={busy} className="w-full rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 font-medium text-cyan-100 disabled:opacity-60">{busy ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="mt-5 text-sm text-white/65">No account yet? <Link className="text-cyan-300 hover:text-cyan-200" href={`/auth/sign-up?returnTo=${encodeURIComponent(returnTo)}`}>Create one</Link></p>
      </div>
    </main>
  );
}
