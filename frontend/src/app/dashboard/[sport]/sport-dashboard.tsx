"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
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
  Area,
  AreaChart,
} from "recharts";

import { apiGet } from "@/lib/api";
import NflInGameAnalytics from "@/components/NflInGameAnalytics";
import NbaInGameAnalytics from "@/components/NbaInGameAnalytics";
import NhlInGameAnalytics from "@/components/NhlInGameAnalytics";
import MlbInGameAnalytics from "@/components/MlbInGameAnalytics";
import PlotActions from "@/components/PlotActions";

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



type OffenseDefenseTooltipProps = {
  active?: boolean;
  payload?: Array<{ payload?: { label?: string; team?: string; avg_pf?: number; avg_pa?: number; avg_margin?: number; gp?: number; isSelected?: boolean } }>;
};

function OffenseDefenseTooltip({ active, payload }: OffenseDefenseTooltipProps) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;

  return (
    <div className="rounded-xl border border-white/15 bg-black/90 px-3 py-2 text-sm text-white shadow-2xl backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <div className="font-semibold">{point.label ?? point.team ?? "Team"}</div>
        {point.isSelected ? (
          <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-cyan-200">
            selected
          </span>
        ) : null}
      </div>
      <div className="mt-2 space-y-1 text-xs text-white/75">
        <div>Offense: {typeof point.avg_pf === "number" ? point.avg_pf.toFixed(1) : "—"}</div>
        <div>Defense: {typeof point.avg_pa === "number" ? point.avg_pa.toFixed(1) : "—"}</div>
        <div>Margin: {typeof point.avg_margin === "number" ? point.avg_margin.toFixed(1) : "—"}</div>
        <div>Games: {typeof point.gp === "number" ? point.gp : "—"}</div>
      </div>
    </div>
  );
}

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
  const sec = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000));
  if (sec < 5) return "just now";
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

// ---------- AI INSIGHTS (plasma style, matches GeneralDashboard) ----------
function avg(nums: Array<number | null | undefined>) {
  const clean = nums.filter((x) => typeof x === "number") as number[];
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

function recordFromResults(res: Array<string | null | undefined>) {
  let w = 0,
    l = 0,
    t = 0;
  for (const r of res) {
    const u = (r ?? "").toUpperCase();
    if (u === "W") w += 1;
    else if (u === "L") l += 1;
    else if (u === "T") t += 1;
  }
  return { w, l, t };
}

function AIInsightsBox({
  chartId,
  sport,
  season,
  seasonType,
  team,
  summary,
}: {
  chartId: string;
  sport: string;
  season: number;
  seasonType: string;
  team: string;
  summary: any;
}) {
  const [caption, setCaption] = useState<string>("Generating insight...");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setStatus("loading");
        setCaption("Generating insight...");

        const base = process.env.NEXT_PUBLIC_API_BASE;
        if (!base) throw new Error("NEXT_PUBLIC_API_BASE is not set");

        const res = await fetch(`${base}/ai/chart-caption`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chart_id: chartId,
            sport,
            season,
            season_type: seasonType,
            team,
            summary,
          }),
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail ?? "AI caption request failed");
        }

        if (cancelled) return;
        setCaption(data?.caption ?? "Not enough data yet.");
        setStatus("ready");
      } catch {
        if (cancelled) return;
        setCaption("Not enough data yet.");
        setStatus("error");
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [chartId, sport, season, seasonType, team, summary]);

  return (
    <div className="mt-5 sl-plasma-card">
      <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold tracking-tight">AI Insights</div>
          <div className="text-xs text-white/60">
            {status === "loading" ? "generating…" : "auto-generated"}
          </div>
        </div>

        <div className="mt-3 text-sm text-white/75 italic leading-relaxed">
          {caption}
        </div>
      </div>
    </div>
  );
}

export default function SportDashboard({ sport }: { sport: string }) {
  const s = (sport || "").toLowerCase().trim();

  const [season, setSeason] = useState<number>(DEFAULT_SEASON);
  const [seasonType, setSeasonType] = useState<string>(DEFAULT_SEASON_TYPE);
  const [team, setTeam] = useState<string>("");
  const [showInGame, setShowInGame] = useState<boolean>(false);

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

  const offenseDefenseRef = useRef<HTMLElement | null>(null);
  const rollingRef = useRef<HTMLElement | null>(null);
  const leagueScoringRef = useRef<HTMLElement | null>(null);
  const standingsRef = useRef<HTMLElement | null>(null);
  const sosRef = useRef<HTMLElement | null>(null);
  const recentFormRef = useRef<HTMLElement | null>(null);
  const homeAwayRef = useRef<HTMLElement | null>(null);
  const marginRef = useRef<HTMLElement | null>(null);
  const closeGamesRef = useRef<HTMLElement | null>(null);
  const scoreDistributionRef = useRef<HTMLElement | null>(null);
  const resultsBreakdownRef = useRef<HTMLElement | null>(null);
  const cumulativeMarginRef = useRef<HTMLElement | null>(null);

  // Dropdown styles: readable options
  const selectClass =
    "rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25 text-white";
  const optionClass = "bg-[#0b0b0b] text-white";

  // Subtle hover glow on ALL cards
  const cardClass =
    "rounded-2xl border border-white/10 bg-white/5 p-5 transition-all duration-200 " +
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
        isSelected: r.team_code === team,
      }))
      .sort((a, b) => Number(b.isSelected) - Number(a.isSelected));
  }, [summary, team]);

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

  const resultsBreakdown = useMemo(() => {
    if (formSeries.length === 0) return [];
    const counts = { W: 0, L: 0, T: 0 };
    for (const g of formSeries) {
      const key = (g.result || "").toUpperCase() as keyof typeof counts;
      if (key in counts) counts[key] += 1;
    }
    return [
      { outcome: "Wins", count: counts.W },
      { outcome: "Losses", count: counts.L },
      { outcome: "Ties", count: counts.T },
    ].filter((row) => row.count > 0 || row.outcome !== "Ties");
  }, [formSeries]);

  const cumulativeMarginSeries = useMemo(() => {
    if (formSeries.length === 0) return [];
    let running = 0;
    return formSeries.map((g) => {
      running += g.margin ?? 0;
      return {
        idx: g.idx,
        opponent: g.opponent,
        result: g.result,
        margin: g.margin,
        cumulative_margin: running,
      };
    });
  }, [formSeries]);

  // ---- AI summaries (small numeric objects only) ----
  const aiRecentFormSummary = useMemo(() => {
    if (formSeries.length === 0) return null;

    const sf = formSeries.map((g) => g.sf);
    const sa = formSeries.map((g) => g.sa);
    const res = formSeries.map((g) => g.result);

    const last5 = formSeries.slice(-5);
    const prev5 = formSeries.slice(-10, -5);

    const last5_sf = avg(last5.map((g) => g.sf));
    const prev5_sf = avg(prev5.map((g) => g.sf));
    const last5_sa = avg(last5.map((g) => g.sa));
    const prev5_sa = avg(prev5.map((g) => g.sa));
    const last5_margin = avg(last5.map((g) => g.margin));
    const prev5_margin = avg(prev5.map((g) => g.margin));

    const lastRec = recordFromResults(last5.map((g) => g.result));
    const prevRec = recordFromResults(prev5.map((g) => g.result));

    return {
      games: formSeries.length,
      pf_avg: avg(sf),
      pa_avg: avg(sa),
      last5_pf: last5_sf,
      prev5_pf: prev5_sf,
      last5_pa: last5_sa,
      prev5_pa: prev5_sa,
      last5_margin,
      prev5_margin,
      last5_record: lastRec,
      prev5_record: prevRec,
    };
  }, [formSeries]);

  const aiRollingSummary = useMemo(() => {
    if (rollingSeries.length === 0) return null;
    const last = rollingSeries[rollingSeries.length - 1];
    const first = rollingSeries[0];

    return {
      games: rollingSeries.length,
      pf_roll5_last: last?.pf_roll5 ?? null,
      pf_roll5_first: first?.pf_roll5 ?? null,
      pa_roll5_last: last?.pa_roll5 ?? null,
      pa_roll5_first: first?.pa_roll5 ?? null,
    };
  }, [rollingSeries]);

  const aiSosSummary = useMemo(() => {
    if (!sosSeries.length) return null;
    const last5 = sosSeries.slice(-5);

    return {
      games: sosSeries.length,
      sos_avg: sos?.sos_avg ?? null,
      last5_opp_win_pct_avg: avg(last5.map((g) => g.opp_win_pct)),
      last5_sos_roll5_avg: avg(last5.map((g) => g.sos_roll5)),
      last_sos_roll5: sosSeries[sosSeries.length - 1]?.sos_roll5 ?? null,
      last_sos_cum: sosSeries[sosSeries.length - 1]?.sos_cum ?? null,
    };
  }, [sosSeries, sos]);


const aiOffenseDefenseSummary = useMemo(() => {
  if (!scatterData.length) return null;

  const pf = scatterData.map((d) => d.avg_pf);
  const pa = scatterData.map((d) => d.avg_pa);

  const pfAvg = avg(pf);
  const paAvg = avg(pa);

  // Pearson correlation (PF vs PA) to capture "shootout-y" teams/leagues
  const n = scatterData.length;
  const meanX = pfAvg ?? 0;
  const meanY = paAvg ?? 0;
  let num = 0,
    dx2 = 0,
    dy2 = 0;

  for (let i = 0; i < n; i++) {
    const dx = (pf[i] ?? 0) - meanX;
    const dy = (pa[i] ?? 0) - meanY;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  const corr =
    dx2 > 0 && dy2 > 0 ? num / Math.sqrt(dx2 * dy2) : null;

  const bestOffense = Math.max(...pf);
  const bestDefense = Math.min(...pa);
  const bestMargin = Math.max(...scatterData.map((d) => d.avg_margin ?? 0));

  return {
    teams: n,
    pf_avg: pfAvg,
    pa_avg: paAvg,
    pf_pa_corr: corr,
    best_offense_pf: bestOffense,
    best_defense_pa: bestDefense,
    best_margin: bestMargin,
  };
}, [scatterData]);

const aiStandingsSummary = useMemo(() => {
  const rows = standings?.standings ?? [];
  if (!rows.length) return null;

  const leader = rows[0];
  const teamIdx = rows.findIndex((r) => r.team_code === team);

  return {
    teams: rows.length,
    leader_win_pct: leader?.win_pct ?? null,
    leader_diff: leader?.diff ?? null,
    selected_rank: teamIdx >= 0 ? teamIdx + 1 : null,
    selected_win_pct: teamIdx >= 0 ? rows[teamIdx]?.win_pct ?? null : null,
    selected_diff: teamIdx >= 0 ? rows[teamIdx]?.diff ?? null : null,
  };
}, [standings, team]);

const aiLeagueScoringSummary = useMemo(() => {
  if (!scoringSeries.length) return null;
  const first = scoringSeries[0]?.avg_total ?? null;
  const last = scoringSeries[scoringSeries.length - 1]?.avg_total ?? null;
  const vals = scoringSeries.map((d) => d.avg_total);

  return {
    buckets: scoringSeries.length,
    avg_total_first: first,
    avg_total_last: last,
    avg_total_change: first != null && last != null ? last - first : null,
    avg_total_min: Math.min(...(vals.filter((v) => typeof v === "number") as number[])),
    avg_total_max: Math.max(...(vals.filter((v) => typeof v === "number") as number[])),
  };
}, [scoringSeries]);

const aiHomeAwaySummary = useMemo(() => {
  if (!splits) return null;
  return {
    home_gp: splits.home.gp,
    away_gp: splits.away.gp,
    home_avg_pf: splits.home.avg_pf,
    home_avg_pa: splits.home.avg_pa,
    home_avg_margin: splits.home.avg_margin,
    away_avg_pf: splits.away.avg_pf,
    away_avg_pa: splits.away.avg_pa,
    away_avg_margin: splits.away.avg_margin,
    margin_gap_home_minus_away: splits.home.avg_margin - splits.away.avg_margin,
  };
}, [splits]);

const aiMarginSummary = useMemo(() => {
  if (!formSeries.length) return null;
  const margins = formSeries.map((g) => g.margin);
  const absMargins = margins.map((m) => Math.abs(m));
  const close7 = absMargins.filter((m) => m <= 7).length;
  const blowout = Math.max(...absMargins);

  const last5 = formSeries.slice(-5);
  return {
    games: formSeries.length,
    margin_avg: avg(margins),
    close_rate_7: formSeries.length ? close7 / formSeries.length : null,
    biggest_blowout_abs: blowout,
    last5_margin_avg: avg(last5.map((g) => g.margin)),
  };
}, [formSeries]);

const aiCloseGamesSummary = useMemo(() => {
  if (!formSeries.length) return null;
  const bars = closeGamesBars(formSeries.map((d) => ({ margin: d.margin, result: d.result })));
  const le7 = bars.find((b) => b.bucket === "≤ 7");
  const le3 = bars.find((b) => b.bucket === "≤ 3");
  return {
    games: formSeries.length,
    le3_wins: le3?.wins ?? 0,
    le3_losses: le3?.losses ?? 0,
    le7_wins: le7?.wins ?? 0,
    le7_losses: le7?.losses ?? 0,
  };
}, [formSeries]);

const aiResultsBreakdownSummary = useMemo(() => {
  if (!resultsBreakdown.length) return null;
  const wins = resultsBreakdown.find((r) => r.outcome === "Wins")?.count ?? 0;
  const losses = resultsBreakdown.find((r) => r.outcome === "Losses")?.count ?? 0;
  const ties = resultsBreakdown.find((r) => r.outcome === "Ties")?.count ?? 0;
  return {
    games: wins + losses + ties,
    wins,
    losses,
    ties,
    win_rate: wins + losses + ties > 0 ? wins / (wins + losses + ties) : null,
  };
}, [resultsBreakdown]);

const aiCumulativeMarginSummary = useMemo(() => {
  if (!cumulativeMarginSeries.length) return null;
  const first = cumulativeMarginSeries[0]?.cumulative_margin ?? 0;
  const last = cumulativeMarginSeries[cumulativeMarginSeries.length - 1]?.cumulative_margin ?? 0;
  return {
    games: cumulativeMarginSeries.length,
    cumulative_margin_first: first,
    cumulative_margin_last: last,
    cumulative_margin_change: last - first,
    best_single_margin: Math.max(...cumulativeMarginSeries.map((g) => g.margin ?? 0)),
    worst_single_margin: Math.min(...cumulativeMarginSeries.map((g) => g.margin ?? 0)),
  };
}, [cumulativeMarginSeries]);

const aiScoreDistributionSummary = useMemo(() => {
  if (!scoreDist || !scoreDist.bins?.length) return null;

  const bins = scoreDist.bins;
  const counts = scoreDist.counts ?? [];
  const n = scoreDist.n ?? counts.reduce((a, b) => a + b, 0);

  // Approximate mean using bin midpoints
  let num = 0;
  let den = 0;
  for (let i = 0; i < bins.length; i++) {
    const low = bins[i];
    const high = bins[i + 1] ?? (low + (bins[i] - (bins[i - 1] ?? low - 1)));
    const mid = (low + high) / 2;
    const c = counts[i] ?? 0;
    num += mid * c;
    den += c;
  }
  const meanApprox = den > 0 ? num / den : null;

  // Mode bin
  let modeIdx = 0;
  for (let i = 1; i < counts.length; i++) {
    if ((counts[i] ?? 0) > (counts[modeIdx] ?? 0)) modeIdx = i;
  }

  return {
    n,
    min: scoreDist.min,
    max: scoreDist.max,
    mean_approx: meanApprox,
    mode_bin_low: bins[modeIdx] ?? null,
    mode_bin_count: counts[modeIdx] ?? null,
  };
}, [scoreDist]);


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

            {s === "nfl" || s === "nba" || s === "nhl" || s === "mlb" ? (
              <button
                onClick={() => setShowInGame((v) => !v)}
                className={
                  "ml-1 rounded-xl border px-3 py-2 text-xs transition " +
                  (showInGame
                    ? "border-white/30 bg-white/10 text-white"
                    : "border-white/10 bg-white/5 text-white/70 hover:text-white hover:border-white/20")
                }
                title={`Toggle ${s.toUpperCase()} in-game (boxscore) analytics`}
              >
                {showInGame ? "Hide In-Game" : "Show In-Game"}
              </button>
            ) : null}
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
              {showInGame ? (
                <div className="mb-6">
                  {s === "nfl" ? (
                    <NflInGameAnalytics
                      sport={s}
                      team={team}
                      season={season}
                      seasonType={seasonType}
                      cardClass={cardClass}
                    />
                  ) : null}

                  {s === "nba" ? (
                    <NbaInGameAnalytics
                      sport={s}
                      team={team}
                      season={season}
                      seasonType={seasonType}
                      cardClass={cardClass}
                    />
                  ) : null}

                  {s === "nhl" ? (
                    <NhlInGameAnalytics
                      sport={s}
                      team={team}
                      season={season}
                      seasonType={seasonType}
                      cardClass={cardClass}
                    />
                  ) : null}

                  {s === "mlb" ? (
                    <MlbInGameAnalytics
                      sport={s}
                      team={team}
                      season={season}
                      seasonType={seasonType}
                      cardClass={cardClass}
                    />
                  ) : null}
                </div>
              ) : null}

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
                  <section ref={offenseDefenseRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Offense vs Defense
                      </h2>
                      <div className="text-xs text-white/60">avg per game</div>
                    </div>
                    <PlotActions exportRef={offenseDefenseRef} chartId="offense_vs_defense" chartTitle="Offense vs Defense" sport={s} season={season} seasonType={seasonType} team={team} summary={aiOffenseDefenseSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} offense vs defense view from the ${s.toUpperCase()} dashboard.`} />
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
                            tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                          />
                          <YAxis
                            type="number"
                            dataKey="avg_pa"
                            name="Against"
                            tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                          />
                          <Tooltip
                            cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                            content={<OffenseDefenseTooltip />}
                          />
                          <Scatter
                            name="Teams"
                            data={scatterData}
                            shape={(props: any) => {
                              const { cx, cy, payload } = props;
                              const isSelected = !!payload?.isSelected;
                              return (
                                <g>
                                  {isSelected ? (
                                    <circle
                                      cx={cx}
                                      cy={cy}
                                      r={11}
                                      fill="rgba(34,211,238,0.14)"
                                      stroke="rgba(34,211,238,0.35)"
                                      strokeWidth={1}
                                    />
                                  ) : null}
                                  <circle
                                    cx={cx}
                                    cy={cy}
                                    r={isSelected ? 6.5 : 5}
                                    fill={isSelected ? "rgba(34,211,238,0.95)" : "rgba(255,255,255,0.78)"}
                                    stroke={isSelected ? "rgba(103,232,249,1)" : "rgba(255,255,255,0.18)"}
                                    strokeWidth={isSelected ? 2 : 1}
                                  />
                                </g>
                              );
                            }}
                          />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-3 text-xs text-white/60">
  Tip: bottom-right = elite (high for, low against).
</div>

{aiOffenseDefenseSummary ? (
  <AIInsightsBox
    chartId="offense_vs_defense"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiOffenseDefenseSummary}
  />
) : null}
                  </section>

                  {/* Rolling Averages */}
                  <section ref={rollingRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Rolling Averages (5-game)
                      </h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <PlotActions exportRef={rollingRef} chartId="rolling_averages" chartTitle={`${team} Rolling Averages`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiRollingSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} rolling averages chart from the ${s.toUpperCase()} dashboard.`} />
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

                    {aiRollingSummary ? (
                      <AIInsightsBox
                        chartId="rolling_averages"
                        sport={s}
                        season={season}
                        seasonType={seasonType}
                        team={team}
                        summary={aiRollingSummary}
                      />
                    ) : null}
                  </section>

                  {/* League Scoring Trend */}
                  <section ref={leagueScoringRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        League Scoring Trend
                      </h2>
                      <div className="text-xs text-white/60">
                        avg total per game (recent)
                      </div>
                    </div>
                    <PlotActions exportRef={scoreDistributionRef} chartId="score_distribution" chartTitle="Score Distribution (league)" sport={s} season={season} seasonType={seasonType} team={team} summary={aiScoreDistributionSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the league score distribution from the ${s.toUpperCase()} dashboard.`} />
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

{aiLeagueScoringSummary ? (
  <AIInsightsBox
    chartId="league_scoring_trend"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiLeagueScoringSummary}
  />
) : null}

</section>
{/* Standings */}
                  <section ref={standingsRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">Standings</h2>
                      <div className="text-xs text-white/60">
                        {standings?.season} {standings?.season_type}
                      </div>
                    </div>
                    <PlotActions exportRef={standingsRef} chartId="standings" chartTitle={`${team} Standings Context`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiStandingsSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the standings context from the ${s.toUpperCase()} dashboard.`} />
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

{aiStandingsSummary ? (
  <AIInsightsBox
    chartId="standings"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiStandingsSummary}
  />
) : null}

</section>


{/* SOS */}
                  <section ref={sosRef} className={cardClass}>
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
                    <PlotActions exportRef={sosRef} chartId="sos" chartTitle={`${team} Strength of Schedule`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiSosSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} strength-of-schedule chart from the ${s.toUpperCase()} dashboard.`} />

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

                    {aiSosSummary ? (
                      <AIInsightsBox
                        chartId="sos"
                        sport={s}
                        season={season}
                        seasonType={seasonType}
                        team={team}
                        summary={aiSosSummary}
                      />
                    ) : null}
                  </section>


                </div>

                {/* RIGHT PLOTS COLUMN */}
                <div className="lg:col-span-5 flex flex-col gap-6">


                  {/* Recent Form */}
                  <section ref={recentFormRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        {team} Recent Form
                      </h2>
                      <div className="text-xs text-white/60">
                        last {form?.last ?? 0}
                      </div>
                    </div>
                    <PlotActions exportRef={recentFormRef} chartId="recent_form" chartTitle={`${team} Recent Form`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiRecentFormSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} recent form chart from the ${s.toUpperCase()} dashboard.`} />
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

                    {aiRecentFormSummary ? (
                      <AIInsightsBox
                        chartId="recent_form"
                        sport={s}
                        season={season}
                        seasonType={seasonType}
                        team={team}
                        summary={aiRecentFormSummary}
                      />
                    ) : null}
                  </section>

                  {/* Home vs Away Splits */}
                  <section ref={homeAwayRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">
                        Home vs Away Splits
                      </h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <PlotActions exportRef={homeAwayRef} chartId="home_away_splits" chartTitle={`${team} Home vs Away Splits`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiHomeAwaySummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} home vs away splits from the ${s.toUpperCase()} dashboard.`} />
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

{aiHomeAwaySummary ? (
  <AIInsightsBox
    chartId="home_away_splits"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiHomeAwaySummary}
  />
) : null}

</section>

                  {/* Results Breakdown */}
                  <section ref={resultsBreakdownRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">Results Breakdown</h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <PlotActions exportRef={resultsBreakdownRef} chartId="results_breakdown" chartTitle={`${team} Results Breakdown`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiResultsBreakdownSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} results breakdown from the ${s.toUpperCase()} dashboard.`} />
                    <div className="mt-4 h-[230px]">
                      {resultsBreakdown.length === 0 ? (
                        <div className="text-sm text-white/60">No result data available.</div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={resultsBreakdown} margin={{ top: 10, right: 10, bottom: 10, left: -10 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                            <XAxis dataKey="outcome" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} axisLine={{ stroke: "rgba(255,255,255,0.15)" }} tickLine={{ stroke: "rgba(255,255,255,0.15)" }} />
                            <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} axisLine={{ stroke: "rgba(255,255,255,0.15)" }} tickLine={{ stroke: "rgba(255,255,255,0.15)" }} allowDecimals={false} />
                            <Tooltip contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white" }} />
                            <Bar dataKey="count" name="Games" fill="rgba(59,130,246,0.82)" />
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                    {aiResultsBreakdownSummary ? (
                      <AIInsightsBox
                        chartId="results_breakdown"
                        sport={s}
                        season={season}
                        seasonType={seasonType}
                        team={team}
                        summary={aiResultsBreakdownSummary}
                      />
                    ) : null}
                  </section>

                  {/* Margin Histogram */}
                  <section ref={marginRef} className={cardClass}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-semibold">Margin Histogram</h2>
                      <div className="text-xs text-white/60">{team}</div>
                    </div>
                    <PlotActions exportRef={marginRef} chartId="margin_histogram" chartTitle={`${team} Margin Histogram`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiMarginSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} margin histogram from the ${s.toUpperCase()} dashboard.`} />
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

{aiMarginSummary ? (
  <AIInsightsBox
    chartId="margin_histogram"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiMarginSummary}
  />
) : null}

</section>

                  {/* Close Games */}
                  <section ref={closeGamesRef} className={cardClass}>
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h2 className="text-base font-semibold">Close Games</h2>
                      <div className="text-xs text-white/60">
                        {team} (last {form?.last ?? 0})
                      </div>
                    </div>

                    <div className="mt-3 text-xs text-white/60">
                      Wins/losses in games decided by ≤3, ≤7, and ≤10 points.
                    </div>

                    <PlotActions exportRef={closeGamesRef} chartId="close_games" chartTitle={`${team} Close Games`} sport={s} season={season} seasonType={seasonType} team={team} summary={aiCloseGamesSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the ${team} close-games chart from the ${s.toUpperCase()} dashboard.`} />

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

{aiCloseGamesSummary ? (
  <AIInsightsBox
    chartId="close_games"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiCloseGamesSummary}
  />
) : null}

</section>

                  {/* League Score Distribution */}
                  <section ref={scoreDistributionRef} className={cardClass}>
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h2 className="text-base font-semibold">
                        Score Distribution (league)
                      </h2>
                      <div className="text-xs text-white/60">
                        {season} {seasonType}
                      </div>
                    </div>
                    <PlotActions exportRef={leagueScoringRef} chartId="league_scoring_trend" chartTitle="League Scoring Trend" sport={s} season={season} seasonType={seasonType} team={team} summary={aiLeagueScoringSummary} plotUrl={`/dashboard/${s}`} shareBody={`Sharing the league scoring trend from the ${s.toUpperCase()} dashboard.`} />
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

{aiScoreDistributionSummary ? (
  <AIInsightsBox
    chartId="score_distribution"
    sport={s}
    season={season}
    seasonType={seasonType}
    team={team}
    summary={aiScoreDistributionSummary}
  />
) : null}

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