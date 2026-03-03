"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  BarChart,
} from "recharts";

import { apiGet } from "@/lib/api";
import ChartCaption from "@/components/ChartCaption";

const SUPPORTED = new Set(["nfl", "nba", "mlb", "nhl"]);
const SPORT_LABEL: Record<string, string> = {
  nfl: "NFL",
  nba: "NBA",
  mlb: "MLB",
  nhl: "NHL",
};

// Defaults you requested
const DEFAULT_SEASON = 2025;
const DEFAULT_SEASON_TYPE = "REG";
const DEFAULT_TEAM_CODE = "BUF";

type StandingsRow = {
  team_code: string;
  name: string | null;
  city: string | null;
  gp: number;
  w: number;
  l: number;
  t: number;
  pf: number;
  pa: number;
  diff: number;
  win_pct: number;
};

type StandingsResp = {
  sport: string;
  season: number;
  season_type: string;
  points_label: string;
  standings: StandingsRow[];
};

type TeamSummaryRow = {
  team_code: string;
  name: string | null;
  city: string | null;
  gp: number;
  pf: number;
  pa: number;
  avg_pf: number | null;
  avg_pa: number | null;
  avg_margin: number | null;
};

type TeamSummaryResp = {
  sport: string;
  season: number;
  season_type: string;
  points_label: string;
  teams: TeamSummaryRow[];
};

type TeamsResp = {
  sport: string;
  teams: Array<{ team_code: string; name: string; city: string | null }>;
};

type TeamFormResp = {
  sport: string;
  team: string;
  season: number;
  season_type: string;
  last: number;
  dates: Array<string | null>;
  opponents: string[];
  home_away: Array<"home" | "away">;
  score_for: Array<number | null>;
  score_against: Array<number | null>;
  margin: Array<number | null>;
  results: Array<"W" | "L" | "T" | null>;
};

type HomeAwaySplitsResp = {
  sport: string;
  team: string;
  season: number;
  season_type: string;
  points_label: string;
  home: {
    gp: number;
    w: number;
    l: number;
    t: number;
    avg_pf: number;
    avg_pa: number;
    avg_margin: number;
  };
  away: {
    gp: number;
    w: number;
    l: number;
    t: number;
    avg_pf: number;
    avg_pa: number;
    avg_margin: number;
  };
};

type ScoringDistributionResp = {
  sport: string;
  season: number;
  season_type: string;
  points_label: string;
  bins: number[];
  counts: number[];
  min: number | null;
  max: number | null;
  n: number;
};

type ScoringTimeseriesResp = {
  sport: string;
  start: string;
  end: string;
  bucket: "day" | "week";
  points_label: string;
  x: Array<string | null>;
  games: number[];
  avg_total_score: Array<number | null>;
};

type SosRow = {
  idx: number;
  date: string | null;
  opponent: string;
  home_away: "home" | "away";
  result: "W" | "L" | "T" | null;
  opp_win_pct: number;
  sos_cum: number;
  sos_roll5: number;
};

type SosResp = {
  sport: string;
  team: string;
  season: number;
  season_type: string;
  games: number;
  roll_window: number;
  sos_avg: number;
  rows: SosRow[];
};

type NewsItem = {
  id: number;
  source: string;
  sport: string;
  title: string;
  url: string;
  published_at: string; // ISO
  snippet?: string | null;
};

function niceTeamLabel(r: {
  team_code: string;
  name?: string | null;
  city?: string | null;
}) {
  if (r.city && r.name) return `${r.city} ${r.name}`;
  if (r.name) return r.name;
  return r.team_code;
}

function rollingAvg(vals: number[], window: number) {
  const out: Array<number | null> = [];
  for (let i = 0; i < vals.length; i++) {
    const start = Math.max(0, i - window + 1);
    const slice = vals.slice(start, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / Math.max(1, slice.length);
    out.push(mean);
  }
  return out;
}

function histogram(values: number[], binSize: number) {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const start = Math.floor(min / binSize) * binSize;
  const end = Math.ceil(max / binSize) * binSize;

  const bins: Record<string, number> = {};
  for (let b = start; b <= end; b += binSize) {
    const key = `${b} to ${b + binSize}`;
    bins[key] = 0;
  }

  for (const v of values) {
    const b = Math.floor((v - start) / binSize);
    const low = start + b * binSize;
    const key = `${low} to ${low + binSize}`;
    if (bins[key] == null) bins[key] = 0;
    bins[key] += 1;
  }

  return Object.entries(bins).map(([range, count]) => ({
    range,
    label: range.replace(" to ", "–").replace(/\s+/g, ""),
    count,
  }));
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

function closeGamesBars(
  formSeries: Array<{ margin: number; result: string }>
): Array<{ bucket: string; wins: number; losses: number }> {
  const out = [
    { bucket: "≤ 3", wins: 0, losses: 0 },
    { bucket: "≤ 7", wins: 0, losses: 0 },
    { bucket: "≤ 10", wins: 0, losses: 0 },
  ];

  if (!formSeries || formSeries.length === 0) return out;

  for (const g of formSeries) {
    const m = Math.abs(g.margin ?? 0);
    const isWin = (g.result ?? "").toUpperCase() === "W";
    const isLoss = (g.result ?? "").toUpperCase() === "L";

    if (m <= 3) {
      if (isWin) out[0].wins += 1;
      if (isLoss) out[0].losses += 1;
    }
    if (m <= 7) {
      if (isWin) out[1].wins += 1;
      if (isLoss) out[1].losses += 1;
    }
    if (m <= 10) {
      if (isWin) out[2].wins += 1;
      if (isLoss) out[2].losses += 1;
    }
  }

  return out;
}

export default function SportDashboard({ sport }: { sport: string }) {
  const s = (sport || "").toLowerCase().trim();

  const [season, setSeason] = useState<number>(DEFAULT_SEASON);
  const [seasonType, setSeasonType] = useState<string>(DEFAULT_SEASON_TYPE);
  const [team, setTeam] = useState<string>("");

  const [teams, setTeams] = useState<TeamsResp | null>(null);
  const [standings, setStandings] = useState<StandingsResp | null>(null);
  const [summary, setSummary] = useState<TeamSummaryResp | null>(null);
  const [form, setForm] = useState<TeamFormResp | null>(null);
  const [splits, setSplits] = useState<HomeAwaySplitsResp | null>(null);
  const [scoreDist, setScoreDist] = useState<ScoringDistributionResp | null>(
    null
  );
  const [scoreTs, setScoreTs] = useState<ScoringTimeseriesResp | null>(null);
  const [sos, setSos] = useState<SosResp | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Fade-in on load (premium feel)
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Dropdown styles: readable options
  const selectClass =
    "rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25 text-white";
  const optionClass = "bg-[#0b0b0b] text-white";

  // Subtle hover glow on ALL cards
  const cardClass =
    "rounded-2xl border border-white/10 bg-white/5 p-5 transition-all duration-200 " +
    "hover:border-white/20 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.10),0_16px_50px_rgba(0,0,0,0.55)]";

  // Sub-box styling for AI Insights (same glow language as dashboard cards)
  const aiBoxClass =
    "mt-4 rounded-2xl border border-white/10 bg-black/30 p-4 transition-all duration-200 " +
    "hover:border-white/20 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.10),0_16px_50px_rgba(0,0,0,0.55)]";

  useEffect(() => {
    if (!SUPPORTED.has(s)) return;

    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const [t, st, ts, nws] = await Promise.all([
          apiGet<TeamsResp>(`/analytics/teams?sport=${s}`),
          apiGet<StandingsResp>(
            `/analytics/league/${s}/standings?season=${season}&season_type=${seasonType}`
          ),
          apiGet<TeamSummaryResp>(
            `/analytics/league/${s}/team-summary?season=${season}&season_type=${seasonType}`
          ),
          apiGet<NewsItem[]>(`/news?sport=${s}&limit=60`),
        ]);

        setTeams(t);
        setStandings(st);
        setSummary(ts);
        setNews(nws);

        const codes = (t.teams ?? []).map((x) => x.team_code);
        const nextTeam =
          team ||
          (codes.includes(DEFAULT_TEAM_CODE) ? DEFAULT_TEAM_CODE : codes[0]) ||
          "";
        setTeam(nextTeam);

        try {
          const dist = await apiGet<ScoringDistributionResp>(
            `/analytics/league/${s}/scoring/distribution?season=${season}&season_type=${seasonType}&bins=14`
          );
          setScoreDist(dist);
        } catch {
          setScoreDist(null);
        }

        try {
          const end = new Date();
          const start = new Date(end.getTime() - 1000 * 60 * 60 * 24 * 90);
          const iso = (d: Date) => d.toISOString().slice(0, 10);
          const tss = await apiGet<ScoringTimeseriesResp>(
            `/analytics/league/${s}/scoring/timeseries?start=${iso(
              start
            )}&end=${iso(end)}&bucket=week`
          );
          setScoreTs(tss);
        } catch {
          setScoreTs(null);
        }
      } catch (e: any) {
        setErr(e?.message ?? "Failed to load sport dashboard");
      } finally {
        setLoading(false);
      }
    }

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s, season, seasonType]);

  useEffect(() => {
    if (!SUPPORTED.has(s) || !team) return;
    async function loadTeam() {
      try {
        const [f, sp, sosResp] = await Promise.all([
          apiGet<TeamFormResp>(
            `/analytics/teams/${s}/${team}/form?season=${season}&season_type=${seasonType}&last=16`
          ),
          apiGet<HomeAwaySplitsResp>(
            `/analytics/teams/${s}/${team}/splits/home-away?season=${season}&season_type=${seasonType}`
          ),
          apiGet<SosResp>(
            `/analytics/teams/${s}/${team}/sos?season=${season}&season_type=${seasonType}&last=50`
          ),
        ]);
        setForm(f);
        setSplits(sp);
        setSos(sosResp);
      } catch {
        setForm(null);
        setSplits(null);
        setSos(null);
      }
    }
    loadTeam();
  }, [s, team, season, seasonType]);

  const scatterData = useMemo(() => {
    const rows = summary?.teams ?? [];
    return rows
      .filter((r) => r.avg_pf != null && r.avg_pa != null)
      .map((r) => ({
        team: r.team_code,
        label: niceTeamLabel(r),
        avg_pf: Number(r.avg_pf),
        avg_pa: Number(r.avg_pa),
        avg_margin: r.avg_margin ?? 0,
        gp: r.gp,
      }));
  }, [summary]);

  const formSeries = useMemo(() => {
    if (!form) return [];
    return form.dates.map((d, i) => ({
      idx: i + 1,
      date: d ?? `G${i + 1}`,
      opponent: form.opponents[i],
      ha: form.home_away[i],
      sf: form.score_for[i] ?? 0,
      sa: form.score_against[i] ?? 0,
      margin: form.margin[i] ?? 0,
      result: form.results[i] ?? "",
    }));
  }, [form]);

  const splitBars = useMemo(() => {
    if (!splits) return [];
    return [
      {
        bucket: "Home",
        avg_for: splits.home.avg_pf,
        avg_against: splits.home.avg_pa,
        avg_margin: splits.home.avg_margin,
        gp: splits.home.gp,
      },
      {
        bucket: "Away",
        avg_for: splits.away.avg_pf,
        avg_against: splits.away.avg_pa,
        avg_margin: splits.away.avg_margin,
        gp: splits.away.gp,
      },
    ];
  }, [splits]);

  const scoringHistogram = useMemo(() => {
    if (!scoreDist || scoreDist.bins.length === 0) return [];
    return scoreDist.bins.map((b, i) => ({
      bin: b,
      count: scoreDist.counts[i] ?? 0,
    }));
  }, [scoreDist]);

  const scoringSeries = useMemo(() => {
    if (!scoreTs || scoreTs.x.length === 0) return [];
    return scoreTs.x.map((x, i) => ({
      x: x ?? `T${i + 1}`,
      avg_total: scoreTs.avg_total_score[i] ?? null,
      games: scoreTs.games[i] ?? 0,
    }));
  }, [scoreTs]);

  const sosSeries = useMemo(() => {
    if (!sos?.rows?.length) return [];
    return sos.rows.map((r) => ({
      idx: r.idx,
      date: r.date ?? `G${r.idx}`,
      opponent: r.opponent,
      opp_win_pct: r.opp_win_pct,
      sos_cum: r.sos_cum,
      sos_roll5: r.sos_roll5,
      home_away: r.home_away,
      result: r.result ?? "",
    }));
  }, [sos]);

  const rollingSeries = useMemo(() => {
    if (formSeries.length === 0) return [];
    const pf = formSeries.map((d) => d.sf);
    const pa = formSeries.map((d) => d.sa);
    const pfRoll = rollingAvg(pf, 5);
    const paRoll = rollingAvg(pa, 5);

    return formSeries.map((d, i) => ({
      ...d,
      pf_roll5: pfRoll[i],
      pa_roll5: paRoll[i],
    }));
  }, [formSeries]);

  const marginHistogram = useMemo(() => {
    if (formSeries.length === 0) return [];
    const margins = formSeries.map((d) => d.margin);
    return histogram(margins, 7);
  }, [formSeries]);

  // -----------------------------
  // AI summary objects (numbers only)
  // -----------------------------
  const recentFormSummary = useMemo(() => {
    if (!formSeries || formSeries.length === 0) return {};
    const n = formSeries.length;
    const lastN = Math.min(5, n);
    const prevN = Math.min(5, Math.max(0, n - lastN));

    const avg = (arr: number[]) =>
      arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

    const last = formSeries.slice(n - lastN);
    const prev =
      prevN > 0 ? formSeries.slice(n - lastN - prevN, n - lastN) : [];

    const r2 = (v: number | null) =>
      v == null ? null : Math.round(v * 100) / 100;

    const last_pf = avg(last.map((d) => Number(d.sf)));
    const last_pa = avg(last.map((d) => Number(d.sa)));
    const prev_pf = avg(prev.map((d) => Number(d.sf)));
    const prev_pa = avg(prev.map((d) => Number(d.sa)));
    const last_margin = avg(last.map((d) => Number(d.margin)));

    return {
      last_games: lastN,
      prev_games: prevN,
      last_pf: r2(last_pf),
      last_pa: r2(last_pa),
      prev_pf: r2(prev_pf),
      prev_pa: r2(prev_pa),
      last_margin: r2(last_margin),
      delta_pf: r2(last_pf == null || prev_pf == null ? null : last_pf - prev_pf),
      delta_pa: r2(last_pa == null || prev_pa == null ? null : last_pa - prev_pa),
    };
  }, [formSeries]);

  const rollingAvgSummary = useMemo(() => {
    if (!rollingSeries || rollingSeries.length === 0) return {};
    const n = rollingSeries.length;

    const last: any = rollingSeries[n - 1];
    const prev: any = n >= 6 ? rollingSeries[n - 6] : null;

    const r2 = (v: number | null | undefined) =>
      v == null ? null : Math.round(Number(v) * 100) / 100;

    const last_pf_roll5 = r2(last?.pf_roll5);
    const last_pa_roll5 = r2(last?.pa_roll5);
    const prev_pf_roll5 = r2(prev?.pf_roll5);
    const prev_pa_roll5 = r2(prev?.pa_roll5);

    return {
      last_pf_roll5,
      last_pa_roll5,
      prev_pf_roll5,
      prev_pa_roll5,
      delta_pf_roll5:
        last_pf_roll5 == null || prev_pf_roll5 == null
          ? null
          : r2(last_pf_roll5 - prev_pf_roll5),
      delta_pa_roll5:
        last_pa_roll5 == null || prev_pa_roll5 == null
          ? null
          : r2(last_pa_roll5 - prev_pa_roll5),
    };
  }, [rollingSeries]);

  const sosSummary = useMemo(() => {
    if (!sosSeries || sosSeries.length === 0) return {};
    const n = sosSeries.length;
    const lastN = Math.min(5, n);
    const prevN = Math.min(5, Math.max(0, n - lastN));

    const avg = (arr: number[]) =>
      arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

    const last = sosSeries.slice(n - lastN);
    const prev =
      prevN > 0 ? sosSeries.slice(n - lastN - prevN, n - lastN) : [];

    const r3 = (v: number | null) =>
      v == null ? null : Math.round(v * 1000) / 1000;

    const last_opp = avg(last.map((d) => Number(d.opp_win_pct)));
    const prev_opp = avg(prev.map((d) => Number(d.opp_win_pct)));

    const last_sos_roll5 = r3((last[last.length - 1] as any)?.sos_roll5 ?? null);
    const prev_sos_roll5 = prev.length
      ? r3((prev[prev.length - 1] as any)?.sos_roll5 ?? null)
      : null;

    return {
      last_games: lastN,
      prev_games: prevN,
      last_opp_win_pct: r3(last_opp),
      prev_opp_win_pct: r3(prev_opp),
      delta_opp_win_pct:
        last_opp == null || prev_opp == null ? null : r3(last_opp - prev_opp),
      last_sos_roll5,
      prev_sos_roll5,
      delta_sos_roll5:
        last_sos_roll5 == null || prev_sos_roll5 == null
          ? null
          : r3(last_sos_roll5 - prev_sos_roll5),
    };
  }, [sosSeries]);

  if (!SUPPORTED.has(s)) {
    return (
      <main className="min-h-screen bg-black text-white px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <Link href="/dashboard" className="text-white/80 hover:text-white">
            ← Back
          </Link>
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="text-lg font-semibold">Unsupported sport</div>
            <div className="mt-1 text-sm text-white/70">
              This page currently supports: NFL, NBA, MLB, NHL.
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
            <Link href="/dashboard" className="text-white/80 hover:text-white">
              ←
            </Link>
            <div>
              <div className="text-lg font-semibold tracking-tight">
                {SPORT_LABEL[s] ?? s.toUpperCase()} • Advanced Dashboard
              </div>
              <div className="text-xs text-white/60">
                Standings + efficiency + form, splits, rolling trends + SOS
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              value={season}
              onChange={(e) => setSeason(Number(e.target.value || 0))}
              className={`${selectClass} w-[92px]`}
              placeholder="Season"
              inputMode="numeric"
            />

            <select
              value={seasonType}
              onChange={(e) => setSeasonType(e.target.value)}
              className={selectClass}
            >
              <option className={optionClass} value="REG">
                REG
              </option>
              <option className={optionClass} value="POST">
                POST
              </option>
            </select>

            <select
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              className={`${selectClass} min-w-[180px]`}
            >
              {(teams?.teams ?? []).map((t) => (
                <option
                  key={t.team_code}
                  value={t.team_code}
                  className={optionClass}
                >
                  {t.team_code} — {niceTeamLabel(t)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Fade in the full dashboard area */}
      <div
        className={[
          "w-full px-6 py-8 transition-all duration-500 ease-out",
          mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
        ].join(" ")}
      >
        {loading ? (
          <div className="text-white/70">Loading…</div>
        ) : err ? (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
            <div className="font-semibold">Dashboard load failed</div>
            <div className="mt-1 text-sm text-white/80">{err}</div>
          </div>
        ) : (
          <div className="flex gap-6">
            {/* LEFT SIDEBAR: Sticky + independent scroll */}
            <aside className="hidden xl:block w-[340px] shrink-0">
              <section
                className={[
                  cardClass,
                  "sticky top-[88px] h-[calc(100vh-110px)] overflow-hidden",
                ].join(" ")}
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold">
                    Latest {SPORT_LABEL[s] ?? s.toUpperCase()} Headlines
                  </h2>
                  <div className="text-xs text-white/60">
                    {Math.min(12, news.length)} / {news.length}
                  </div>
                </div>

                <div className="mt-4 h-[calc(100%-42px)] overflow-y-auto pr-1 space-y-3">
                  {news.length === 0 ? (
                    <div className="text-sm text-white/60">
                      No recent articles found.
                    </div>
                  ) : (
                    news.slice(0, 12).map((n) => {
                      const d = parseISO(n.published_at);
                      return (
                        <a
                          key={n.id}
                          href={n.url}
                          target="_blank"
                          rel="noreferrer"
                          className="group block rounded-xl border border-white/10 bg-black/30 p-4 transition hover:bg-black/40 hover:border-white/20"
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
                    })
                  )}
                </div>
              </section>
            </aside>

            {/* MAIN CONTENT */}
            <div className="flex-1">
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                {/* LEFT PLOTS COLUMN */}
                <div className="lg:col-span-7 flex flex-col gap-6">
                  {/* On smaller screens, show News at top */}
                  <section className={`xl:hidden ${cardClass}`}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Latest {SPORT_LABEL[s] ?? s.toUpperCase()} Headlines
                      </h2>
                      <div className="text-xs text-white/60">
                        Showing {Math.min(6, news.length)} of {news.length}
                      </div>
                    </div>

                    <div className="mt-4 space-y-3">
                      {news.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No recent articles found.
                        </div>
                      ) : (
                        news.slice(0, 6).map((n) => {
                          const d = parseISO(n.published_at);
                          return (
                            <a
                              key={n.id}
                              href={n.url}
                              target="_blank"
                              rel="noreferrer"
                              className="group block rounded-xl border border-white/10 bg-black/30 p-4 transition hover:bg-black/40 hover:border-white/20"
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
                                      {n.source}
                                    </span>
                                    <span>
                                      {d ? agoLabel(d) : n.published_at}
                                    </span>
                                  </div>
                                </div>
                                <span className="text-white/50 group-hover:text-white/80">
                                  ↗
                                </span>
                              </div>
                            </a>
                          );
                        })
                      )}
                    </div>
                  </section>

                  {/* Offense vs Defense */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Offense vs Defense
                      </h2>
                      <div className="text-xs text-white/60">avg per game</div>
                    </div>
                    <div className="mt-4 h-[320px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart
                          margin={{ top: 10, right: 20, bottom: 10, left: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                          <XAxis
                            type="number"
                            dataKey="avg_pf"
                            name="For"
                            tick={{
                              fill: "rgba(255,255,255,0.75)",
                              fontSize: 12,
                            }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                          />
                          <YAxis
                            type="number"
                            dataKey="avg_pa"
                            name="Against"
                            tick={{
                              fill: "rgba(255,255,255,0.75)",
                              fontSize: 12,
                            }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                          />
                          <Tooltip
                            cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                            contentStyle={{
                              background: "rgba(0,0,0,0.9)",
                              border: "1px solid rgba(255,255,255,0.15)",
                              borderRadius: 12,
                              color: "white",
                            }}
                            formatter={(v: any, k: any) => [v, k]}
                            labelFormatter={(_, payload: any) =>
                              payload?.[0]?.payload?.label ?? ""
                            }
                          />
                          <Scatter
                            name="Teams"
                            data={scatterData}
                            fill="rgba(255,255,255,0.7)"
                          />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-3 text-xs text-white/60">
                      Tip: bottom-right = elite (high for, low against).
                    </div>
                  </section>

                  {/* Rolling Averages */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Rolling Averages (5-game)
                      </h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <div className="mt-4 h-[280px]">
                      {rollingSeries.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No games found for rolling averages.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={rollingSeries}
                            margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="idx"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              labelFormatter={(label: any) => `Game ${label}`}
                            />
                            <Legend
                              verticalAlign="top"
                              height={20}
                              iconSize={8}
                              wrapperStyle={{
                                fontSize: 12,
                                color: "rgba(255,255,255,0.75)",
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="pf_roll5"
                              name="PF (roll5)"
                              stroke="rgba(255,255,255,0.85)"
                              dot={false}
                            />
                            <Line
                              type="monotone"
                              dataKey="pa_roll5"
                              name="PA (roll5)"
                              stroke="rgba(255,255,255,0.45)"
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </div>

                    {rollingSeries.length === 0 ? null : (
                      <div className={aiBoxClass}>
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold tracking-tight">
                            AI Insights
                          </div>
                          <div className="text-[11px] text-white/60">
                            auto-generated
                          </div>
                        </div>
                        <div className="mt-2">
                          <ChartCaption
                            chartId="rolling-averages"
                            sport={s}
                            season={season}
                            seasonType={seasonType}
                            team={team}
                            summary={rollingAvgSummary}
                          />
                        </div>
                      </div>
                    )}
                  </section>

                  {/* Standings */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">Standings</h2>
                      <div className="text-xs text-white/60">
                        {standings?.season} {standings?.season_type}
                      </div>
                    </div>
                    <div className="mt-4 overflow-auto">
                      <table className="w-full text-sm">
                        <thead className="text-white/60">
                          <tr className="border-b border-white/10">
                            <th className="py-2 text-left font-semibold">Team</th>
                            <th className="py-2 text-right font-semibold">
                              W-L-T
                            </th>
                            <th className="py-2 text-right font-semibold">PF</th>
                            <th className="py-2 text-right font-semibold">PA</th>
                            <th className="py-2 text-right font-semibold">Diff</th>
                            <th className="py-2 text-right font-semibold">Win%</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(standings?.standings ?? []).slice(0, 16).map((r) => (
                            <tr
                              key={r.team_code}
                              className="border-b border-white/5 hover:bg-white/5"
                            >
                              <td className="py-2 pr-2">
                                <div className="font-semibold">{r.team_code}</div>
                                <div className="text-[11px] text-white/60">
                                  {niceTeamLabel(r)}
                                </div>
                              </td>
                              <td className="py-2 text-right tabular-nums">
                                {r.w}-{r.l}-{r.t}
                              </td>
                              <td className="py-2 text-right tabular-nums">
                                {r.pf}
                              </td>
                              <td className="py-2 text-right tabular-nums">
                                {r.pa}
                              </td>
                              <td className="py-2 text-right tabular-nums">
                                {r.diff}
                              </td>
                              <td className="py-2 text-right tabular-nums">
                                {(r.win_pct * 100).toFixed(1)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-3 text-xs text-white/60">
                      (Top 16 shown.) Next: division/conference grouping + playoff
                      cutlines.
                    </div>
                  </section>

                  {/* League Scoring Trend */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        League Scoring Trend
                      </h2>
                      <div className="text-xs text-white/60">
                        avg total per game (recent)
                      </div>
                    </div>
                    <div className="mt-4 h-[280px]">
                      {scoringSeries.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No scoring time series available.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={scoringSeries}
                            margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="x"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              formatter={(v: any, k: any) => [v, k]}
                            />
                            <Legend
                              verticalAlign="top"
                              height={20}
                              iconSize={8}
                              wrapperStyle={{
                                fontSize: 12,
                                color: "rgba(255,255,255,0.75)",
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="avg_total"
                              name="Avg total"
                              stroke="rgba(255,255,255,0.8)"
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </section>
                </div>

                {/* RIGHT PLOTS COLUMN */}
                <div className="lg:col-span-5 flex flex-col gap-6">
                  {/* Recent Form */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        {team} Recent Form
                      </h2>
                      <div className="text-xs text-white/60">
                        last {form?.last ?? 0}
                      </div>
                    </div>
                    <div className="mt-4 h-[320px]">
                      {formSeries.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No games found for this team/season.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={formSeries}
                            margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="idx"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              labelFormatter={(label: any) => `Game ${label}`}
                            />
                            <Legend
                              verticalAlign="top"
                              height={20}
                              iconSize={8}
                              wrapperStyle={{
                                fontSize: 12,
                                color: "rgba(255,255,255,0.75)",
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="sf"
                              name="For"
                              stroke="rgba(255,255,255,0.85)"
                              dot={false}
                            />
                            <Line
                              type="monotone"
                              dataKey="sa"
                              name="Against"
                              stroke="rgba(255,255,255,0.45)"
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </div>

                    {formSeries.length === 0 ? null : (
                      <div className={aiBoxClass}>
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold tracking-tight">
                            AI Insights
                          </div>
                          <div className="text-[11px] text-white/60">
                            auto-generated
                          </div>
                        </div>
                        <div className="mt-2">
                          <ChartCaption
                            chartId="recent-form"
                            sport={s}
                            season={season}
                            seasonType={seasonType}
                            team={team}
                            summary={recentFormSummary}
                          />
                        </div>
                      </div>
                    )}
                  </section>

                  {/* Home vs Away Splits */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Home vs Away Splits
                      </h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <div className="mt-4 h-[280px]">
                      {splitBars.length === 0 ? (
                        <div className="text-sm text-white/60">No split data.</div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={splitBars}
                            margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="bucket"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              formatter={(v: any, k: any) => [v, k]}
                            />
                            <Legend
                              verticalAlign="top"
                              height={20}
                              iconSize={8}
                              wrapperStyle={{
                                fontSize: 12,
                                color: "rgba(255,255,255,0.75)",
                              }}
                            />
                            <Bar
                              dataKey="avg_for"
                              name="Avg For"
                              fill="rgba(255,255,255,0.75)"
                            />
                            <Bar
                              dataKey="avg_against"
                              name="Avg Against"
                              fill="rgba(255,255,255,0.35)"
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </section>

                  {/* Margin Histogram */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">Margin Histogram</h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <div className="mt-4 h-[240px]">
                      {marginHistogram.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No margins available.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={marginHistogram}
                            margin={{ top: 10, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="label"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              allowDecimals={false}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              formatter={(v: any, k: any, payload: any) => {
                                const rng = payload?.payload?.range ?? "";
                                return [v, `Games (${rng})`];
                              }}
                            />
                            <Bar
                              dataKey="count"
                              name="Games"
                              fill="rgba(255,255,255,0.6)"
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </section>

                  {/* Close Games */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h2 className="text-base font-semibold">Close Games</h2>
                      <div className="text-xs text-white/60">
                        {team} (last {form?.last ?? 0})
                      </div>
                    </div>

                    <div className="mt-3 text-xs text-white/60">
                      Wins/losses in games decided by ≤3, ≤7, and ≤10 points.
                    </div>

                    <div className="mt-4 h-[240px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={closeGamesBars(
                            formSeries.map((d) => ({
                              margin: d.margin,
                              result: d.result,
                            }))
                          )}
                          margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                          <XAxis
                            dataKey="bucket"
                            tick={{
                              fill: "rgba(255,255,255,0.75)",
                              fontSize: 12,
                            }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                          />
                          <YAxis
                            tick={{
                              fill: "rgba(255,255,255,0.75)",
                              fontSize: 12,
                            }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            allowDecimals={false}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "rgba(0,0,0,0.9)",
                              border: "1px solid rgba(255,255,255,0.15)",
                              borderRadius: 12,
                              color: "white",
                            }}
                          />
                          <Legend
                            verticalAlign="top"
                            height={20}
                            iconSize={8}
                            wrapperStyle={{
                              fontSize: 12,
                              color: "rgba(255,255,255,0.75)",
                            }}
                          />
                          <Bar
                            dataKey="wins"
                            name="Wins"
                            fill="rgba(255,255,255,0.75)"
                          />
                          <Bar
                            dataKey="losses"
                            name="Losses"
                            fill="rgba(255,255,255,0.35)"
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  {/* SOS */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h2 className="text-base font-semibold">
                        Strength of Schedule (Opponent Win%)
                      </h2>
                      <div className="text-xs text-white/60">
                        avg{" "}
                        {(sos?.sos_avg ?? 0) * 100 > 0
                          ? `${((sos?.sos_avg ?? 0) * 100).toFixed(1)}%`
                          : "—"}
                      </div>
                    </div>
                    <div className="mt-3 text-xs text-white/60">
                      True SOS using opponents’ win% for {season} {seasonType}.
                    </div>

                    <div className="mt-4 h-[260px]">
                      {sosSeries.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No SOS data yet.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={sosSeries}
                            margin={{ top: 28, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="idx"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              domain={[0, 1]}
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickFormatter={(v) => `${Math.round(v * 100)}%`}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                              labelFormatter={(label: any) => `Game ${label}`}
                              formatter={(val: any, key: any, payload: any) => {
                                const p = payload?.payload;
                                if (!p) return [val, key];
                                const pct =
                                  typeof val === "number"
                                    ? `${(val * 100).toFixed(1)}%`
                                    : val;
                                const sub = `${p.opponent} (${p.home_away}) ${p.result}`;
                                return [pct, `${key} • ${sub}`];
                              }}
                            />
                            <Legend
                              verticalAlign="top"
                              height={20}
                              iconSize={8}
                              wrapperStyle={{
                                fontSize: 12,
                                color: "rgba(255,255,255,0.75)",
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="opp_win_pct"
                              name="Opponent win%"
                              stroke="rgba(255,255,255,0.45)"
                              dot={false}
                            />
                            <Line
                              type="monotone"
                              dataKey="sos_cum"
                              name="SOS (cumulative)"
                              stroke="rgba(255,255,255,0.85)"
                              dot={false}
                            />
                            <Line
                              type="monotone"
                              dataKey="sos_roll5"
                              name="SOS (roll5)"
                              stroke="rgba(255,255,255,0.65)"
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </div>

                    {sosSeries.length === 0 ? null : (
                      <div className={aiBoxClass}>
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold tracking-tight">
                            AI Insights
                          </div>
                          <div className="text-[11px] text-white/60">
                            auto-generated
                          </div>
                        </div>
                        <div className="mt-2">
                          <ChartCaption
                            chartId="strength-of-schedule"
                            sport={s}
                            season={season}
                            seasonType={seasonType}
                            team={team}
                            summary={sosSummary}
                          />
                        </div>
                      </div>
                    )}
                  </section>

                  {/* League Score Distribution */}
                  <section className={cardClass}>
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h2 className="text-base font-semibold">
                        Score Distribution (league)
                      </h2>
                      <div className="text-xs text-white/60">
                        {season} {seasonType}
                      </div>
                    </div>
                    <div className="mt-4 h-[240px]">
                      {scoringHistogram.length === 0 ? (
                        <div className="text-sm text-white/60">
                          No distribution available.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={scoringHistogram}
                            margin={{ top: 10, right: 10, bottom: 10, left: -10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis
                              dataKey="bin"
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 11,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            />
                            <YAxis
                              tick={{
                                fill: "rgba(255,255,255,0.75)",
                                fontSize: 12,
                              }}
                              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                              allowDecimals={false}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "rgba(0,0,0,0.9)",
                                border: "1px solid rgba(255,255,255,0.15)",
                                borderRadius: 12,
                                color: "white",
                              }}
                            />
                            <Bar
                              dataKey="count"
                              name="Games"
                              fill="rgba(255,255,255,0.6)"
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </section>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}