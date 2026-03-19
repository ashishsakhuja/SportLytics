"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiGet, apiPost } from "@/lib/api";
import { getStoredUser, setStoredUser, type AuthUser } from "@/lib/auth";

type BillingMeResponse = {
  ok: boolean;
  subscription: {
    is_premium: boolean;
    plan_code: string | null;
    status: string | null;
    access_source: string | null;
    price_cents: number;
    currency: string;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
    stripe_customer_id: string | null;
  };
};

function priceLabel(cents: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: (currency || "usd").toUpperCase(),
  }).format((cents || 0) / 100);
}

export default function PremiumPage() {
  const searchParams = useSearchParams();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [subscription, setSubscription] = useState<BillingMeResponse["subscription"] | null>(null);
  const [busy, setBusy] = useState<"checkout" | "portal" | "admin" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adminKey, setAdminKey] = useState("");

  const checkoutState = useMemo(() => searchParams.get("checkout"), [searchParams]);

  useEffect(() => {
    const stored = getStoredUser();
    setUser(stored);
    if (!stored) {
      return;
    }

    apiGet<BillingMeResponse>("/billing/me")
      .then((res) => {
        setSubscription(res.subscription);
        const mergedUser = { ...stored, ...res.subscription };
        setUser(mergedUser);
        setStoredUser(mergedUser);
      })
      .catch((err: any) => {
        setError(err?.message ?? "Failed to load billing info.");
      })
      .finally(() => undefined);
  }, []);

  async function startCheckout() {
    setBusy("checkout");
    setError(null);
    try {
      const res = await apiPost<{ ok: boolean; url: string }>("/billing/checkout-session", {});
      window.location.href = res.url;
    } catch (err: any) {
      setError(err?.message ?? "Could not start checkout.");
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setError(null);
    try {
      const res = await apiPost<{ ok: boolean; url: string }>("/billing/portal-session", {});
      window.location.href = res.url;
    } catch (err: any) {
      setError(err?.message ?? "Could not open billing portal.");
      setBusy(null);
    }
  }

  async function redeemAdminKey(e: React.FormEvent) {
    e.preventDefault();
    setBusy("admin");
    setError(null);
    try {
      const res = await apiPost<BillingMeResponse>("/billing/admin-access", { admin_key: adminKey });
      setSubscription(res.subscription);
      if (user) {
        const merged = { ...user, ...res.subscription };
        setUser(merged);
        setStoredUser(merged);
      }
      setAdminKey("");
    } catch (err: any) {
      setError(err?.message ?? "Admin key redemption failed.");
    } finally {
      setBusy(null);
    }
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-black px-6 py-10 text-white">
        <div className="mx-auto max-w-3xl rounded-3xl border border-white/10 bg-white/5 p-6">
          <Link href="/dashboard" className="text-sm text-white/70 hover:text-white">← Back to dashboard</Link>
          <h1 className="mt-4 text-3xl font-semibold">Pulse Premium</h1>
          <p className="mt-2 max-w-2xl text-sm text-white/70">Pulse Premium is linked directly to your SportLytics account, so you need to be signed in before starting checkout or redeeming an admin access key.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/auth/sign-in?returnTo=%2Fdashboard%2Fpremium" className="rounded-2xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-3 font-medium text-fuchsia-100 hover:bg-fuchsia-500/15">Sign in to continue</Link>
            <Link href="/auth/sign-up?returnTo=%2Fdashboard%2Fpremium" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 font-medium hover:bg-white/15">Create account</Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white">
      <div className="mx-auto max-w-5xl">
        <Link href="/dashboard" className="text-sm text-white/70 hover:text-white">← Back to dashboard</Link>

        <div className="mt-5 grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          <section className="rounded-3xl border border-fuchsia-400/20 bg-gradient-to-br from-fuchsia-500/10 via-black to-cyan-500/10 p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-fuchsia-200/70">Pulse Premium</div>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight">Sharper signals, cleaner workflows.</h1>
                <p className="mt-3 max-w-2xl text-sm text-white/70">Unlock Premium for <span className="font-semibold text-white">{priceLabel(subscription?.price_cents ?? 499, subscription?.currency ?? "usd")}/month</span>. Billing is handled with Stripe Checkout so payment details are collected on Stripe-hosted pages instead of inside SportLytics.</p>
              </div>
              <div className={`rounded-2xl border px-4 py-3 text-sm ${subscription?.is_premium ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100" : "border-white/10 bg-white/5 text-white/70"}`}>
                {subscription?.is_premium ? "Premium active" : "Free account"}
              </div>
            </div>

            {checkoutState === "success" ? (
              <div className="mt-5 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">Checkout completed. If the badge below has not updated yet, refresh after your Stripe webhook lands.</div>
            ) : null}
            {checkoutState === "cancelled" ? (
              <div className="mt-5 rounded-2xl border border-yellow-400/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100">Checkout was cancelled. Your account is still on the free plan.</div>
            ) : null}
            {error ? (
              <div className="mt-5 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">{error}</div>
            ) : null}

            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                "Premium Pulse tools tied to your login",
                "Secure Stripe-hosted recurring checkout",
                "Billing portal access for card changes and cancellations",
                "Complimentary admin key path for trusted users",
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-white/75">{item}</div>
              ))}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={startCheckout}
                disabled={busy !== null || subscription?.access_source === "admin"}
                className="rounded-2xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-5 py-3 font-medium text-fuchsia-100 hover:bg-fuchsia-500/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === "checkout" ? "Redirecting..." : subscription?.is_premium ? "Start new Stripe checkout" : `Upgrade for ${priceLabel(subscription?.price_cents ?? 499, subscription?.currency ?? "usd")}/mo`}
              </button>

              <button
                onClick={openPortal}
                disabled={busy !== null || !subscription?.stripe_customer_id || subscription?.access_source === "admin"}
                className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 font-medium hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === "portal" ? "Opening..." : "Manage billing"}
              </button>
            </div>
          </section>

          <aside className="space-y-6">
            <section className="rounded-3xl border border-white/10 bg-white/5 p-6">
              <div className="text-sm font-semibold">Current account</div>
              <div className="mt-3 text-sm text-white/80">{user.display_name}</div>
              <div className="text-xs text-white/55">{user.email}</div>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center justify-between gap-3"><span className="text-white/60">Plan</span><span>{subscription?.is_premium ? "Pulse Premium" : "Free"}</span></div>
                <div className="flex items-center justify-between gap-3"><span className="text-white/60">Access source</span><span className="capitalize">{subscription?.access_source ?? "none"}</span></div>
                <div className="flex items-center justify-between gap-3"><span className="text-white/60">Status</span><span className="capitalize">{subscription?.status ?? "inactive"}</span></div>
                <div className="flex items-center justify-between gap-3"><span className="text-white/60">Renews / ends</span><span>{subscription?.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : "—"}</span></div>
              </div>
            </section>

            <section className="rounded-3xl border border-cyan-400/20 bg-cyan-500/5 p-6">
              <div className="text-sm font-semibold text-cyan-100">Admin access key</div>
              <p className="mt-2 text-sm text-white/70">For trusted developers, testers, or partners. The key is validated server-side and grants complimentary Premium on the signed-in account.</p>
              <form onSubmit={redeemAdminKey} className="mt-4 space-y-3">
                <input
                  type="password"
                  value={adminKey}
                  onChange={(e) => setAdminKey(e.target.value)}
                  placeholder="Enter admin access key"
                  className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm outline-none"
                />
                <button
                  disabled={busy !== null || !adminKey.trim()}
                  className="w-full rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 font-medium text-cyan-100 hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy === "admin" ? "Redeeming..." : "Redeem key"}
                </button>
              </form>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
