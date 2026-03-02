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
    // shorter, readable tick label like "-21–-14"
    label: range.replace(" to ", "–").replace(/\s+/g, ""),
    count,
  }));
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

  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Dropdown styles: readable options
  const selectClass =
    "rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25 text-white";
  const optionClass = "bg-[#0b0b0b] text-white";

  useEffect(() => {
    if (!SUPPORTED.has(s)) return;

    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const [t, st, ts] = await Promise.all([
          apiGet<TeamsResp>(`/analytics/teams?sport=${s}`),
          apiGet<StandingsResp>(
            `/analytics/league/${s}/standings?season=${season}&season_type=${seasonType}`
          ),
          apiGet<TeamSummaryResp>(
            `/analytics/league/${s}/team-summary?season=${season}&season_type=${seasonType}`
          ),
        ]);

        setTeams(t);
        setStandings(st);
        setSummary(ts);

        // Default team selection: keep current, else BUF if exists, else first
        const codes = (t.teams ?? []).map((x) => x.team_code);
        const nextTeam =
          team ||
          (codes.includes(DEFAULT_TEAM_CODE) ? DEFAULT_TEAM_CODE : codes[0]) ||
          "";
        setTeam(nextTeam);

        // League distribution + recent scoring trend (best effort)
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

  // Rolling averages
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

  // Team margin histogram (bin size ~TD)
  const marginHistogram = useMemo(() => {
    if (formSeries.length === 0) return [];
    const margins = formSeries.map((d) => d.margin);
    return histogram(margins, 7);
  }, [formSeries]);

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

            {/* Only REG and POST */}
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

      <div className="mx-auto max-w-6xl px-6 py-8">
        {loading ? (
          <div className="text-white/70">Loading…</div>
        ) : err ? (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
            <div className="font-semibold">Dashboard load failed</div>
            <div className="mt-1 text-sm text-white/80">{err}</div>
          </div>
        ) : (
          <>
            {/* KEY LAYOUT FIX:
                At lg+, keep a persistent Left column (7) + Right column (5).
                This prevents the "blank black gap" under shorter right cards when the left card is taller. */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* LEFT COLUMN */}
              <div className="lg:col-span-7 flex flex-col gap-6">
                {/* Offense vs Defense */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
                </section>

                {/* Standings */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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

              {/* RIGHT COLUMN */}
              <div className="lg:col-span-5 flex flex-col gap-6">
                {/* Recent Form */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold">{team} Recent Form</h2>
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
                </section>

                {/* Home vs Away Splits */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
                            formatter={(v: any, k: any) => [
                              Number(v).toFixed(2),
                              k,
                            ]}
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
                            name="For"
                            fill="rgba(255,255,255,0.7)"
                          />
                          <Bar
                            dataKey="avg_against"
                            name="Against"
                            fill="rgba(255,255,255,0.35)"
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </section>

                {/* Margin Distribution */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <h2 className="text-base font-semibold">
                      Margin Distribution
                    </h2>
                    <div className="text-xs text-white/60">{team}</div>
                  </div>

                  <div className="mt-4 h-[240px]">
                    {marginHistogram.length === 0 ? (
                      <div className="text-sm text-white/60">
                        No margins to chart.
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={marginHistogram}
                          margin={{ top: 10, right: 10, bottom: 26, left: -10 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                          <XAxis
                            dataKey="label"
                            tick={{
                              fill: "rgba(255,255,255,0.75)",
                              fontSize: 10,
                            }}
                            axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                            interval="preserveStartEnd"
                            angle={-25}
                            textAnchor="end"
                            height={44}
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
                            // show the original "range" in tooltip
                            labelFormatter={(lbl: any, payload: any) =>
                              payload?.[0]?.payload?.range ?? lbl
                            }
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

                  <div className="mt-2 text-[11px] text-white/60">
                    Bucketed by ~TD (7 pts).
                  </div>
                </section>

                {/* Close Games */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <h2 className="text-base font-semibold">Close Games</h2>
                    <div className="text-xs text-white/60">{team}</div>
                  </div>

                  <div className="mt-3 text-xs text-white/60">
                    Wins vs losses in tight games (from the recent form window).
                  </div>

                  <div className="mt-4 h-[240px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={closeGamesBars(
                          formSeries.map((g) => ({
                            margin: g.margin,
                            result: String(g.result ?? ""),
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
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
                          // extra top margin because legend is now on top (prevents overlap)
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
                </section>

                {/* League Score Distribution */}
                <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
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
          </>
        )}
      </div>
    </main>
  );
}