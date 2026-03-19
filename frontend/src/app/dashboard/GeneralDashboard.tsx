"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import Sparkline from "@/components/Sparkline";
import { clearAuthSession, getStoredUser, type AuthUser } from "@/lib/auth";

type NewsItem = {
  id: number;
  source: string;
  sport: string;
  title: string;
  url: string;
  published_at: string; // ISO
  snippet?: string | null;
};

type MetaSportsResponse = {
  sports: Array<{
    key: string;
    label: string;
    count: number;
    last_published_at: string | null;
  }>;
  sources: Array<{
    key: string;
    label: string;
    count: number;
    last_published_at: string | null;
  }>;
  global_last_published_at: string | null;
};

type LiveSidebarItem = {
  thread_id: number;
  group_id: number;
  sport: string;
  status: string;
  phase?: string | null;
  game_date: string | null;
  away_team: string;
  home_team: string;
  away_score?: number | null;
  home_score?: number | null;
  title: string;
  message_count: number;
  latest_message_preview?: string | null;
  dashboard_url: string;
};

type MetaHealthResponse = {
  status: "ok" | "degraded";
  db: { ok: boolean };
  content_items: { total: number | null; latest_published_at: string | null };
  ingestion: {
    last_run: null | {
      id: number;
      status: string;
      started_at: string | null;
      finished_at: string | null;
      inserted_count: number;
      error: string | null;
    };
  };
  server_time_utc: string;
};

const SPORT_ORDER = ["top", "nfl", "nba", "mlb", "nhl", "cfb", "f1", "nascar"];
const SPORT_LABEL: Record<string, string> = {
  top: "All",
  nfl: "NFL",
  nba: "NBA",
  mlb: "MLB",
  nhl: "NHL",
  cfb: "CFB",
  f1: "F1",
  nascar: "NASCAR",
};

const SUPPORTED_SPORT_PAGES = new Set(["nfl", "nba", "mlb", "nhl"]);

const STOPWORDS = new Set([
  "the",
  "a",
  "an",
  "and",
  "or",
  "but",
  "to",
  "of",
  "in",
  "on",
  "for",
  "with",
  "at",
  "by",
  "from",
  "as",
  "is",
  "are",
  "was",
  "were",
  "be",
  "been",
  "being",
  "it",
  "its",
  "this",
  "that",
  "these",
  "those",
  "after",
  "before",
  "over",
  "under",
  "into",
  "out",
  "up",
  "down",
  "vs",
  "v",
  "new",
  "news",
  "report",
  "game",
  "games",
  "season",
  "team",
  "teams",
  "player",
  "players",
  "coach",
  "coaches",
]);

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

function parseISO(s: string) {
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function agoLabel(dt: Date) {
  const sec = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 48) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

function bucketSeries(items: NewsItem[], hours: number, sport: string | null) {
  const now = Date.now();
  const bucket = new Array(hours).fill(0);

  for (const it of items) {
    if (sport && it.sport !== sport) continue;
    const d = parseISO(it.published_at);
    if (!d) continue;
    const diffH = (now - d.getTime()) / (1000 * 60 * 60);
    if (diffH < 0 || diffH > hours) continue;

    const idx = Math.floor(hours - diffH);
    const bi = clamp(idx - 1, 0, hours - 1);
    bucket[bi] += 1;
  }
  return bucket;
}

function extractKeywords(text: string) {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .map((w) => w.trim())
    .filter((w) => w.length >= 3 && !STOPWORDS.has(w));
}

export default function GeneralDashboard() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const [news, setNews] = useState<NewsItem[]>([]);
  const [metaSports, setMetaSports] = useState<MetaSportsResponse | null>(null);
  const [health, setHealth] = useState<MetaHealthResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [liveThreads, setLiveThreads] = useState<LiveSidebarItem[]>([]);

  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const [ms, mh, live] = await Promise.all([
        apiGet<MetaSportsResponse>("/meta/sports"),
        apiGet<MetaHealthResponse>("/meta/health"),
        apiGet<{ items: LiveSidebarItem[] }>("/community/live/sidebar?viewer=Ash&limit=6"),
      ]);
      setMetaSports(ms);
      setHealth(mh);
      setLiveThreads(live.items ?? []);

      const items = await apiGet<NewsItem[]>(`/news?limit=250`);
      setNews(items);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    setAuthUser(getStoredUser());

    const onStorage = () => {
      setAuthUser(getStoredUser());
    };

    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  async function handleSignOut() {
    setAuthBusy(true);
    try {
      await apiPost("/auth/logout", {});
    } catch {
      // clear local session even if backend logout fails
    } finally {
      clearAuthSession();
      setAuthUser(null);
      setAuthBusy(false);
    }
  }

  const filteredNews = useMemo(() => {
    const query = q.trim().toLowerCase();
    return news.filter((n) => {
      if (!query) return true;
      const hay = `${n.title} ${n.snippet ?? ""}`.toLowerCase();
      return hay.includes(query);
    });
  }, [news, q]);

  const kpis = useMemo(() => {
    const now = Date.now();
    const items = news;

    let last24 = 0;
    let last7d = 0;
    let latest: Date | null = null;

    for (const it of items) {
      const d = parseISO(it.published_at);
      if (!d) continue;
      if (!latest || d > latest) latest = d;

      const diffMs = now - d.getTime();
      if (diffMs <= 24 * 3600 * 1000) last24 += 1;
      if (diffMs <= 7 * 24 * 3600 * 1000) last7d += 1;
    }

    const baseline = last7d / 7;
    const velocity = baseline > 0 ? last24 / baseline : 0;

    return {
      total: items.length,
      last24,
      last7d,
      velocity,
      latest,
      spark24h: bucketSeries(items, 24, null),
      spark72h: bucketSeries(items, 72, null),
    };
  }, [news]);

  const trends = useMemo(() => {
    const now = Date.now();
    const recent = news.filter((n) => {
      const d = parseISO(n.published_at);
      if (!d) return false;
      return now - d.getTime() <= 72 * 3600 * 1000;
    });

    const counts = new Map<string, number>();
    for (const it of recent) {
      const words = extractKeywords(`${it.title} ${it.snippet ?? ""}`);
      for (const w of words) counts.set(w, (counts.get(w) ?? 0) + 1);
    }

    const in24 = recent.filter((n) => {
      const d = parseISO(n.published_at);
      return d ? now - d.getTime() <= 24 * 3600 * 1000 : false;
    });

    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([term, count]) => {
        let c24 = 0;
        for (const it of in24) {
          const words = extractKeywords(`${it.title} ${it.snippet ?? ""}`);
          if (words.includes(term)) c24 += 1;
        }
        const momentum = c24 / Math.max(1, count);
        return { term, count, c24, momentum };
      });
  }, [news]);

  const sportsCoverage = useMemo(() => {
    const rows = metaSports?.sports ?? [];
    const orderIndex = new Map<string, number>(
      SPORT_ORDER.map((s, idx) => [s, idx])
    );

    return [...rows].sort((a, b) => {
      const ai = orderIndex.get(a.key) ?? 999;
      const bi = orderIndex.get(b.key) ?? 999;
      if (ai !== bi) return ai - bi;
      return a.key.localeCompare(b.key);
    });
  }, [metaSports]);

  const topCoverageSport = useMemo(() => {
    const supported = sportsCoverage.filter((s) => SUPPORTED_SPORT_PAGES.has(s.key));
    if (supported.length === 0) return null;
    return [...supported].sort((a, b) => b.count - a.count)[0];
  }, [sportsCoverage]);

  if (loading) {
    return (
      <main className="min-h-screen bg-black text-white px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <div className="text-white/70">Loading dashboard…</div>
        </div>
      </main>
    );
  }

  if (err) {
    return (
      <main className="min-h-screen bg-black text-white px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <div className="sl-plasma-card">
            <div className="sl-plasma-inner rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
              <div className="font-semibold">Dashboard load failed</div>
              <div className="mt-1 text-white/80 text-sm">{err}</div>
              <button
                onClick={load}
                className="mt-4 rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm hover:bg-white/15"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-white/80 hover:text-white">
              ←
            </Link>
            <div>
              <div className="text-lg font-semibold tracking-tight">
                General Dashboard
              </div>
              <div className="text-xs text-white/60">
                All-sports news + analysis signals
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45">
                  Identity
                </div>
                {authUser ? (
                  <div className="mt-1 text-sm text-white/90">
                    <span className="font-semibold">{authUser.display_name}</span>
                    <span className="text-white/45"> • {authUser.email}</span>
                  </div>
                ) : (
                  <div className="mt-1 text-sm text-white/70">
                    Browse freely. Sign in for Pulse and Community posting.
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {authUser ? (
                  <button
                    onClick={handleSignOut}
                    disabled={authBusy}
                    className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {authBusy ? "Signing out..." : "Sign out"}
                  </button>
                ) : (
                  <>
                    <Link
                      href="/auth/sign-in?returnTo=%2Fdashboard"
                      className="rounded-xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-3 py-2 text-sm text-fuchsia-100 hover:bg-fuchsia-500/15"
                    >
                      Sign in
                    </Link>
                    <Link
                      href="/auth/sign-up?returnTo=%2Fdashboard"
                      className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm hover:bg-white/15"
                    >
                      Create account
                    </Link>
                  </>
                )}
              </div>
            </div>

            <button
              onClick={load}
              className="rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm hover:bg-white/15"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-4 md:hidden rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45">
            Identity
          </div>
          {authUser ? (
            <>
              <div className="mt-2 text-sm text-white/90">
                <span className="font-semibold">{authUser.display_name}</span>
              </div>
              <div className="text-xs text-white/55">{authUser.email}</div>
              <button
                onClick={handleSignOut}
                disabled={authBusy}
                className="mt-3 rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {authBusy ? "Signing out..." : "Sign out"}
              </button>
            </>
          ) : (
            <>
              <div className="mt-2 text-sm text-white/70">
                Browse freely. Sign in for Pulse and Community posting.
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link
                  href="/auth/sign-in?returnTo=%2Fdashboard"
                  className="rounded-xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-3 py-2 text-sm text-fuchsia-100 hover:bg-fuchsia-500/15"
                >
                  Sign in
                </Link>
                <Link
                  href="/auth/sign-up?returnTo=%2Fdashboard"
                  className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm hover:bg-white/15"
                >
                  Create account
                </Link>
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full px-4 py-2 text-xs font-semibold border border-white/35 bg-white/20">
              All
            </span>

            {sportsCoverage
              .map((s) => s.key)
              .filter((v, i, a) => a.indexOf(v) === i)
              .filter((key) => SUPPORTED_SPORT_PAGES.has(key))
              .map((key) => (
                <Link
                  key={key}
                  href={`/dashboard/${key}`}
                  className="rounded-full px-4 py-2 text-xs font-semibold border border-white/10 bg-white/5 hover:bg-white/10 transition"
                >
                  {SPORT_LABEL[key] ?? key.toUpperCase()} →
                </Link>
              ))}

            <Link
              href="/dashboard/custom-builder"
              className="rounded-full px-4 py-2 text-xs font-semibold border border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100 hover:bg-fuchsia-500/15 transition"
            >
              Custom Builder →
            </Link>

            <Link
              href="/dashboard/signal-center"
              className="rounded-full px-4 py-2 text-xs font-semibold border border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100 hover:bg-fuchsia-500/15 transition"
            >
              Signal Center →
            </Link>

            <Link
              href="/dashboard/community"
              className="rounded-full px-4 py-2 text-xs font-semibold border border-cyan-400/30 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/15 transition"
            >
              Community →
            </Link>
          </div>

          <div className="flex items-center gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search headlines, topics…"
              className="w-full sm:w-[320px] rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm outline-none focus:border-white/25"
            />
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Items loaded"
            value={`${kpis.total.toLocaleString()}`}
            sub={`${kpis.last24.toLocaleString()} in last 24h`}
            series={kpis.spark24h}
          />
          <KpiCard
            label="7-day volume"
            value={`${kpis.last7d.toLocaleString()}`}
            sub={`Velocity ${kpis.velocity ? kpis.velocity.toFixed(2) : "0.00"}×`}
            series={kpis.spark72h}
          />
          <KpiCard
            label="Latest publish"
            value={kpis.latest ? agoLabel(kpis.latest) : "—"}
            sub={kpis.latest ? kpis.latest.toISOString() : ""}
          />
          <KpiCard
            label="Top sport volume"
            value={topCoverageSport ? (topCoverageSport.label ?? SPORT_LABEL[topCoverageSport.key] ?? topCoverageSport.key.toUpperCase()) : "—"}
            sub={topCoverageSport ? `${topCoverageSport.count.toLocaleString()} items loaded` : "No supported sports yet"}
          />
        </div>

        <div className="mt-6 grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          <aside className="lg:col-span-3 lg:self-start">
            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-2xl border border-cyan-400/20 bg-white/5 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">Live Game Threads</h2>
                    <div className="mt-1 text-xs text-white/60">
                      Active and near-start community rooms, top-aligned with the feed
                    </div>
                  </div>
                  <Link
                    href="/dashboard/community"
                    className="rounded-full border border-cyan-400/25 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold text-cyan-100 hover:bg-cyan-500/15"
                  >
                    Open Community
                  </Link>
                </div>

                <div className="mt-4 space-y-3">
                  {liveThreads.length === 0 ? (
                    <div className="rounded-xl border border-white/10 bg-black/25 p-4 text-sm text-white/60">
                      No live or near-tipoff threads right now. Once games enter the active window, Pulse will surface them here.
                    </div>
                  ) : (
                    liveThreads.map((item) => {
                      const dt = item.game_date ? new Date(item.game_date) : null;
                      const isLive = item.status === "live";
                      const scoreline = `${item.away_team} ${item.away_score ?? "—"} at ${item.home_team} ${item.home_score ?? "—"}`;
                      return (
                        <div
                          key={item.thread_id}
                          className="rounded-2xl border border-white/10 bg-black/30 p-4"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span
                              className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                                isLive
                                  ? "border border-red-400/35 bg-red-500/10 text-red-200"
                                  : "border border-white/10 bg-white/5 text-white/70"
                              }`}
                            >
                              {isLive ? "Live" : item.status}
                            </span>
                            <span className="text-[11px] text-white/55">
                              {dt
                                ? isLive
                                  ? agoLabel(dt)
                                  : dt.toLocaleTimeString([], {
                                      hour: "numeric",
                                      minute: "2-digit",
                                    })
                                : "TBD"}
                            </span>
                          </div>

                          <div className="mt-3 text-sm font-semibold leading-snug">
                            {scoreline}
                          </div>
                          <div className="mt-1 text-[11px] text-white/55">
                            {SPORT_LABEL[item.sport] ?? item.sport.toUpperCase()}
                            {item.phase ? ` • ${item.phase}` : ""}
                            {item.message_count
                              ? ` • ${item.message_count} messages`
                              : " • new thread"}
                          </div>

                          {item.latest_message_preview ? (
                            <div className="mt-3 text-xs text-white/65 line-clamp-3">
                              {item.latest_message_preview}
                            </div>
                          ) : null}

                          <div className="mt-4 flex gap-2">
                            <Link
                              href={`/dashboard/community?thread=${item.thread_id}`}
                              className="rounded-xl border border-cyan-400/25 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-500/15"
                            >
                              Join Thread
                            </Link>
                            <Link
                              href={item.dashboard_url}
                              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10"
                            >
                              View Dashboard
                            </Link>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </section>
          </aside>

          <section className="lg:col-span-6 sl-plasma-card">
            <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold">Latest Headlines</h2>
                <div className="text-xs text-white/60">
                  Showing {filteredNews.slice(0, 20).length} of{" "}
                  {filteredNews.length.toLocaleString()}
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {filteredNews.slice(0, 20).map((n) => {
                  const d = parseISO(n.published_at);
                  return (
                    <a
                      key={n.id}
                      href={n.url}
                      target="_blank"
                      rel="noreferrer"
                      className="group block rounded-xl border border-white/10 bg-black/30 p-4 hover:bg-black/40"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold leading-snug group-hover:text-white">
                            {n.title}
                          </div>
                          {n.snippet ? (
                            <div className="mt-1 text-xs text-white/70 line-clamp-2">
                              {n.snippet}
                            </div>
                          ) : null}
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/60">
                            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                              {SPORT_LABEL[n.sport] ?? n.sport.toUpperCase()}
                            </span>
                            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                              {n.source}
                            </span>
                            <span>{d ? agoLabel(d) : n.published_at}</span>
                          </div>
                        </div>
                        <span className="text-white/50 group-hover:text-white/80">
                          ↗
                        </span>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          </section>

          <div className="lg:col-span-3 space-y-6">
            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold">Trending Topics</h2>
                  <div className="text-xs text-white/60">last 72h</div>
                </div>

                <div className="mt-4 space-y-2">
                  {trends.length === 0 ? (
                    <div className="text-sm text-white/60">
                      Not enough recent items to compute trends.
                    </div>
                  ) : (
                    trends.map((t) => (
                      <div
                        key={t.term}
                        className="rounded-xl border border-white/10 bg-black/25 p-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold">{t.term}</div>
                          <div className="text-xs text-white/70">
                            {t.count} hits • {t.c24} in 24h
                          </div>
                        </div>

                        <div className="mt-2 h-2 w-full rounded-full bg-white/10 overflow-hidden">
                          <div
                            className="h-full bg-white/40"
                            style={{
                              width: `${clamp(t.momentum * 100, 8, 100)}%`,
                            }}
                          />
                        </div>
                        <div className="mt-1 text-[11px] text-white/60">
                          Momentum: {(t.momentum * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>

            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold">Coverage by Sport</h2>
                  <div className="text-xs text-white/60">from DB</div>
                </div>

                <div className="mt-4 space-y-2">
                  {sportsCoverage.filter((s) =>
                    SUPPORTED_SPORT_PAGES.has(s.key)
                  ).length === 0 ? (
                    <div className="text-sm text-white/60">
                      No supported sport pages available.
                    </div>
                  ) : (
                    sportsCoverage
                      .filter((s) => SUPPORTED_SPORT_PAGES.has(s.key))
                      .map((s) => {
                        const last = s.last_published_at
                          ? agoLabel(new Date(s.last_published_at))
                          : "—";
                        return (
                          <Link
                            key={s.key}
                            href={`/dashboard/${s.key}`}
                            className="block rounded-xl border border-white/10 bg-black/25 p-3 hover:bg-black/35 transition"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-semibold">
                                {s.label ??
                                  SPORT_LABEL[s.key] ??
                                  s.key.toUpperCase()}
                              </div>
                              <div className="text-xs text-white/70">
                                {s.count.toLocaleString()} items
                              </div>
                            </div>
                            <div className="mt-1 text-[11px] text-white/60">
                              last publish: {last}
                            </div>
                          </Link>
                        );
                      })
                  )}
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className="mt-8 text-xs text-white/50">
          Powered by your DB via <span className="text-white/70">/news</span>,{" "}
          <span className="text-white/70">/meta/sports</span>,{" "}
          <span className="text-white/70">/meta/health</span>.
        </div>
      </div>
    </main>
  );
}

function KpiCard(props: {
  label: string;
  value: string;
  sub?: string;
  series?: number[];
}) {
  return (
    <div className="sl-plasma-card">
      <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
        <div className="text-xs text-white/60">{props.label}</div>
        <div className="mt-2 text-2xl font-semibold tracking-tight">
          {props.value}
        </div>
        {props.sub ? (
          <div className="mt-1 text-xs text-white/60">{props.sub}</div>
        ) : null}
        {props.series ? (
          <div className="mt-4 text-white/70">
            <Sparkline values={props.series} />
          </div>
        ) : null}
      </div>
    </div>
  );
}