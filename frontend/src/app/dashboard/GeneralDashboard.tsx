"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import Sparkline from "@/components/Sparkline";

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

// IMPORTANT: only these have sport-specific dashboard pages right now
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

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const [ms, mh] = await Promise.all([
        apiGet<MetaSportsResponse>("/meta/sports"),
        apiGet<MetaHealthResponse>("/meta/health"),
      ]);
      setMetaSports(ms);
      setHealth(mh);

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

  const lastRun = health?.ingestion?.last_run ?? null;

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
      {/* Top bar */}
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
                All-sports news + analysis signals (DB-backed)
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-xs text-white/60">
              DB:{" "}
              <span
                className={health?.db?.ok ? "text-emerald-300" : "text-red-300"}
              >
                {health?.db?.ok ? "ok" : "degraded"}
              </span>
              {health?.content_items?.latest_published_at ? (
                <>
                  {" "}
                  • latest item{" "}
                  <span className="text-white/80">
                    {agoLabel(
                      new Date(health.content_items.latest_published_at)
                    )}
                  </span>
                </>
              ) : null}
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
        {/* Controls */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {/* "All" stays on general dashboard */}
            <span className="rounded-full px-4 py-2 text-xs font-semibold border border-white/35 bg-white/20">
              All
            </span>

            {/* Sport chips navigate ONLY for supported sport pages */}
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
              className="rounded-full px-4 py-2 text-xs font-semibold border border-sky-400/30 bg-sky-500/10 text-sky-100 hover:bg-sky-500/15 transition"
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

        {/* KPI Strip */}
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
            label="Ingest status"
            value={lastRun ? lastRun.status : "—"}
            sub={
              lastRun?.started_at
                ? `Run #${lastRun.id} • inserted ${lastRun.inserted_count}`
                : "No ingest runs found"
            }
          />
        </div>

        {/* Main grid */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Latest Headlines */}
          <section className="lg:col-span-7 sl-plasma-card">
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

          {/* Right column: Trends + Coverage */}
          <div className="lg:col-span-5 space-y-6">
            {/* Trending Topics */}
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

            {/* Coverage by Sport */}
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
                            className="rounded-xl border border-white/10 bg-black/25 p-3"
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

        {/* Footer */}
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