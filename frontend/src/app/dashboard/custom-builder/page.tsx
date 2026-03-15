"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
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
} from "recharts";

import { apiGet } from "@/lib/api";

type SportKey = "nfl" | "nba" | "mlb" | "nhl";

type TeamOption = {
  team_code: string;
  name: string;
  city: string | null;
  label: string;
};

type MetricOption = {
  key: string;
  label: string;
  source: string;
  group: string;
  count?: number;
};

type BuilderOptionsResp = {
  sport: string;
  season: number;
  season_type: string;
  teams: TeamOption[];
  metrics: MetricOption[];
  compare_modes: Array<{ key: string; label: string }>;
  granularities: Array<{ key: string; label: string }>;
  chart_types: Array<{ key: string; label: string }>;
};

type BuilderPlotResp = {
  sport: string;
  team: string;
  season_from: number;
  season_to: number;
  season_type: string;
  metric: string;
  metric_label: string;
  compare_mode: string;
  compare_label: string | null;
  granularity: string;
  roll_window: number;
  filters: {
    home_away: string;
    result: string;
  };
  summary: {
    points: number;
    primary_avg: number | null;
    primary_min: number | null;
    primary_max: number | null;
    compare_avg: number | null;
  };
  rows: Array<{
    x: string;
    season?: number;
    date?: string | null;
    opponent?: string;
    home_away?: string;
    result?: string | null;
    value?: number | null;
    compare_value?: number | null;
    roll_value?: number | null;
    compare_roll_value?: number | null;
    games?: number;
  }>;
};

const SPORTS: Array<{ key: SportKey; label: string }> = [
  { key: "nfl", label: "NFL" },
  { key: "nba", label: "NBA" },
  { key: "mlb", label: "MLB" },
  { key: "nhl", label: "NHL" },
];

const DEFAULT_SEASON = 2025;
const DEFAULT_SEASON_TYPE = "REG";

function formatNum(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "—";
  return Math.abs(n) >= 100 ? n.toFixed(1) : n.toFixed(2);
}

function ControlLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/55">{children}</div>;
}

function Select({
  value,
  onChange,
  children,
  disabled,
}: {
  value: string | number;
  onChange: (v: string) => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border border-white/10 bg-black/35 px-3 py-2.5 text-sm text-white outline-none transition focus:border-fuchsia-400/60 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </select>
  );
}

function SummaryCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-white/45">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {sub ? <div className="mt-1 text-sm text-white/55">{sub}</div> : null}
    </div>
  );
}

export default function CustomBuilderPage() {
  const [sport, setSport] = useState<SportKey>("nfl");
  const [seasonType, setSeasonType] = useState(DEFAULT_SEASON_TYPE);
  const [seasonFrom, setSeasonFrom] = useState(String(DEFAULT_SEASON));
  const [seasonTo, setSeasonTo] = useState(String(DEFAULT_SEASON));

  const [options, setOptions] = useState<BuilderOptionsResp | null>(null);
  const [team, setTeam] = useState("");
  const [metric, setMetric] = useState("score_for");
  const [compareMode, setCompareMode] = useState("none");
  const [compareTeam, setCompareTeam] = useState("");
  const [granularity, setGranularity] = useState("game");
  const [chartType, setChartType] = useState("line");
  const [homeAway, setHomeAway] = useState("all");
  const [resultFilter, setResultFilter] = useState("all");
  const [rollWindow, setRollWindow] = useState("5");

  const [loadingOptions, setLoadingOptions] = useState(false);
  const [loadingPlot, setLoadingPlot] = useState(false);
  const [plot, setPlot] = useState<BuilderPlotResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadOptions() {
      setLoadingOptions(true);
      setError(null);
      try {
        const next = await apiGet<BuilderOptionsResp>(
          `/analytics/custom/options?sport=${sport}&season=${seasonTo}&season_type=${seasonType}`
        );
        setOptions(next);

        const nextTeam = next.teams.some((t) => t.team_code === team)
          ? team
          : next.teams[0]?.team_code ?? "";
        setTeam(nextTeam);

        const nextMetric = next.metrics.some((m) => m.key === metric)
          ? metric
          : next.metrics[0]?.key ?? "score_for";
        setMetric(nextMetric);

        if (compareMode === "team") {
          const fallbackCompare =
            next.teams.find((t) => t.team_code !== nextTeam)?.team_code ?? nextTeam;
          setCompareTeam((prev) =>
            next.teams.some((t) => t.team_code === prev && prev !== nextTeam)
              ? prev
              : fallbackCompare
          );
        }
      } catch (e: any) {
        setError(e?.message ?? "Failed to load builder options");
        setOptions(null);
      } finally {
        setLoadingOptions(false);
      }
    }

    loadOptions();
  }, [sport, seasonType, seasonTo]);

  useEffect(() => {
    if (!team || !metric) return;
    async function loadPlot() {
      setLoadingPlot(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          sport,
          team,
          season_from: seasonFrom,
          season_to: seasonTo,
          season_type: seasonType,
          metric,
          compare_mode: compareMode,
          granularity,
          home_away: homeAway,
          result: resultFilter,
          roll_window: rollWindow,
        });
        if (compareMode === "team" && compareTeam) params.set("compare_team", compareTeam);

        const nextPlot = await apiGet<BuilderPlotResp>(`/analytics/custom/plot?${params.toString()}`);
        setPlot(nextPlot);
      } catch (e: any) {
        setPlot(null);
        setError(e?.message ?? "Failed to load chart data");
      } finally {
        setLoadingPlot(false);
      }
    }

    loadPlot();
  }, [sport, team, seasonFrom, seasonTo, seasonType, metric, compareMode, compareTeam, granularity, homeAway, resultFilter, rollWindow]);

  useEffect(() => {
    if (compareMode !== "team") return;
    if (!options?.teams?.length) return;
    if (!compareTeam || compareTeam === team) {
      const fallback = options.teams.find((t) => t.team_code !== team)?.team_code ?? "";
      setCompareTeam(fallback);
    }
  }, [compareMode, compareTeam, team, options]);

  const currentMetric = useMemo(
    () => options?.metrics.find((m) => m.key === metric) ?? null,
    [options, metric]
  );

  const chartData = useMemo(() => {
    return (plot?.rows ?? []).map((row, idx) => ({
      ...row,
      primary: row.value,
      compare: row.compare_value,
      rolling: row.roll_value,
      compareRolling: row.compare_roll_value,
      label: row.x || `P${idx + 1}`,
      tooltipLabel:
        row.date || row.x || (row.season != null ? String(row.season) : `Point ${idx + 1}`),
    }));
  }, [plot]);

  const quickInsights = useMemo(() => {
    if (!plot) return [] as string[];
    const primary = plot.rows.map((r) => r.value ?? null);
    const compare = plot.rows.map((r) => r.compare_value ?? null);
    const rolling = plot.rows.map((r) => r.roll_value ?? null);

    const latestPrimary = primary.filter((v): v is number => typeof v === "number").slice(-1)[0] ?? null;
    const latestCompare = compare.filter((v): v is number => typeof v === "number").slice(-1)[0] ?? null;
    const latestRolling = rolling.filter((v): v is number => typeof v === "number").slice(-1)[0] ?? null;

    const insights: string[] = [];
    insights.push(`${plot.metric_label} average: ${formatNum(plot.summary.primary_avg)}.`);
    if (latestRolling != null && plot.granularity === "game" && plot.roll_window > 1) {
      insights.push(`Latest rolling ${plot.roll_window}-game average: ${formatNum(latestRolling)}.`);
    }
    if (latestPrimary != null && latestCompare != null && plot.compare_mode !== "none") {
      const diff = latestPrimary - latestCompare;
      const word = diff >= 0 ? "above" : "below";
      insights.push(`Latest point sits ${formatNum(Math.abs(diff))} ${word} the comparison series.`);
    }
    return insights;
  }, [plot]);

  const seasonOptions = useMemo(() => {
    const years: string[] = [];
    for (let y = 2025; y >= 2015; y--) years.push(String(y));
    return years;
  }, []);

  const availableCompareTeams = useMemo(
    () => (options?.teams ?? []).filter((t) => t.team_code !== team),
    [options, team]
  );

  function renderChart() {
    if (!plot || !chartData.length) {
      return (
        <div className="flex h-[420px] items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/20 text-white/50">
          No data yet for the current builder setup.
        </div>
      );
    }

    const commonProps = {
      data: chartData,
      margin: { top: 8, right: 16, left: 0, bottom: 0 },
    };

    const grid = <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />;
    const xAxis = <XAxis dataKey="label" tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }} minTickGap={18} />;
    const yAxis = <YAxis tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }} />;
    const tooltip = (
      <Tooltip
        contentStyle={{
          background: "rgba(10,10,16,0.96)",
          border: "1px solid rgba(255,255,255,0.12)",
          borderRadius: 14,
          color: "white",
        }}
        labelFormatter={(value, payload) => {
          const row = payload?.[0]?.payload as { tooltipLabel?: string } | undefined;
          return row?.tooltipLabel ?? value;
        }}
      />
    );
    const legend = <Legend wrapperStyle={{ color: "rgba(255,255,255,0.72)" }} />;

    if (chartType === "bar") {
      return (
        <ResponsiveContainer width="100%" height={420}>
          <BarChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            <Bar dataKey="primary" name={plot.team} fill="rgba(217,70,239,0.85)" radius={[8, 8, 0, 0]} />
            {plot.compare_mode !== "none" ? (
              <Bar dataKey="compare" name={plot.compare_label ?? "Comparison"} fill="rgba(99,102,241,0.78)" radius={[8, 8, 0, 0]} />
            ) : null}
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (chartType === "area") {
      return (
        <ResponsiveContainer width="100%" height={420}>
          <AreaChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            <Area type="monotone" dataKey="primary" name={plot.team} stroke="rgba(217,70,239,0.95)" fill="rgba(217,70,239,0.18)" strokeWidth={3} />
            {plot.compare_mode !== "none" ? (
              <Area
                type="monotone"
                dataKey="compare"
                name={plot.compare_label ?? "Comparison"}
                stroke="rgba(99,102,241,0.95)"
                fill="rgba(99,102,241,0.16)"
                strokeWidth={3}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      );
    }

    if (chartType === "scatter") {
      return (
        <ResponsiveContainer width="100%" height={420}>
          <ScatterChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            <Scatter data={chartData} dataKey="primary" name={plot.team} fill="rgba(217,70,239,0.9)" />
            {plot.compare_mode !== "none" ? (
              <Scatter data={chartData} dataKey="compare" name={plot.compare_label ?? "Comparison"} fill="rgba(99,102,241,0.85)" />
            ) : null}
          </ScatterChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={420}>
        <LineChart {...commonProps}>
          {grid}
          {xAxis}
          {yAxis}
          {tooltip}
          {legend}
          <Line type="monotone" dataKey="primary" name={plot.team} stroke="rgba(217,70,239,0.95)" strokeWidth={3} dot={false} />
          {plot.granularity === "game" && plot.roll_window > 1 ? (
            <Line type="monotone" dataKey="rolling" name={`${plot.team} Roll ${plot.roll_window}`} stroke="rgba(244,114,182,0.95)" strokeWidth={2} dot={false} strokeDasharray="5 5" />
          ) : null}
          {plot.compare_mode !== "none" ? (
            <Line
              type="monotone"
              dataKey="compare"
              name={plot.compare_label ?? "Comparison"}
              stroke="rgba(99,102,241,0.95)"
              strokeWidth={3}
              dot={false}
            />
          ) : null}
          {plot.compare_mode !== "none" && plot.granularity === "game" && plot.roll_window > 1 ? (
            <Line
              type="monotone"
              dataKey="compareRolling"
              name={`${plot.compare_label ?? "Comparison"} Roll ${plot.roll_window}`}
              stroke="rgba(129,140,248,0.95)"
              strokeWidth={2}
              dot={false}
              strokeDasharray="5 5"
            />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="border-b border-white/10 bg-black/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-start justify-between gap-6 px-6 py-5">
          <div>
            <div className="flex items-center gap-3">
              <Link href="/dashboard" className="text-white/70 transition hover:text-white">
                ← General Dashboard
              </Link>
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Custom Builder</h1>
            <p className="mt-1 text-sm text-white/60">
              Build your own charts across sports, teams, seasons, and advanced metrics.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Link href="/dashboard" className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10">
              All
            </Link>
            {SPORTS.map((item) => (
              <Link
                key={item.key}
                href={`/dashboard/${item.key}`}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
              >
                {item.label} →
              </Link>
            ))}
            <span className="rounded-full border border-fuchsia-400/35 bg-fuchsia-500/12 px-4 py-2 text-xs font-semibold text-fuchsia-200">
              Custom Builder
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] grid-cols-1 gap-6 px-6 py-8 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-6 xl:self-start">
          <div className="rounded-[28px] border border-fuchsia-400/20 bg-[radial-gradient(circle_at_top_left,rgba(236,72,153,0.14),transparent_38%),linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.03))] p-5 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold">Builder Controls</div>
                <div className="mt-1 text-xs text-white/55">Smooth, flexible custom charting for every supported sport.</div>
              </div>
              {(loadingOptions || loadingPlot) && <div className="text-xs text-fuchsia-200">Loading…</div>}
            </div>

            <div className="space-y-4">
              <div>
                <ControlLabel>Sport</ControlLabel>
                <Select value={sport} onChange={(v) => setSport(v as SportKey)}>
                  {SPORTS.map((item) => (
                    <option key={item.key} value={item.key}>{item.label}</option>
                  ))}
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ControlLabel>Season From</ControlLabel>
                  <Select value={seasonFrom} onChange={setSeasonFrom}>
                    {seasonOptions.map((year) => <option key={year} value={year}>{year}</option>)}
                  </Select>
                </div>
                <div>
                  <ControlLabel>Season To</ControlLabel>
                  <Select value={seasonTo} onChange={setSeasonTo}>
                    {seasonOptions.map((year) => <option key={year} value={year}>{year}</option>)}
                  </Select>
                </div>
              </div>

              <div>
                <ControlLabel>Season Type</ControlLabel>
                <Select value={seasonType} onChange={setSeasonType}>
                  <option value="REG">Regular Season</option>
                  <option value="POST">Postseason</option>
                </Select>
              </div>

              <div>
                <ControlLabel>Primary Team</ControlLabel>
                <Select value={team} onChange={setTeam} disabled={!options?.teams?.length}>
                  {(options?.teams ?? []).map((t) => (
                    <option key={t.team_code} value={t.team_code}>{t.team_code} — {t.label}</option>
                  ))}
                </Select>
              </div>

              <div>
                <ControlLabel>Statistic</ControlLabel>
                <Select value={metric} onChange={setMetric} disabled={!options?.metrics?.length}>
                  {(options?.metrics ?? []).map((m) => (
                    <option key={m.key} value={m.key}>{m.label}{m.source === "team_game_stats" ? " • adv" : ""}</option>
                  ))}
                </Select>
                {currentMetric ? (
                  <div className="mt-2 text-xs text-white/50">
                    {currentMetric.group} • {currentMetric.source === "team_game_stats" ? "Derived from per-game stat rows" : "Built-in game result metric"}
                  </div>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ControlLabel>Granularity</ControlLabel>
                  <Select value={granularity} onChange={setGranularity}>
                    <option value="game">Game by Game</option>
                    <option value="season">Season Average</option>
                  </Select>
                </div>
                <div>
                  <ControlLabel>Chart Type</ControlLabel>
                  <Select value={chartType} onChange={setChartType}>
                    <option value="line">Line</option>
                    <option value="bar">Bar</option>
                    <option value="area">Area</option>
                    <option value="scatter">Scatter</option>
                  </Select>
                </div>
              </div>

              <div>
                <ControlLabel>Compare Against</ControlLabel>
                <Select value={compareMode} onChange={setCompareMode}>
                  <option value="none">No Comparison</option>
                  <option value="team">Another Team</option>
                  <option value="league_avg">League Average</option>
                  <option value="previous_season">Previous Season</option>
                </Select>
              </div>

              {compareMode === "team" ? (
                <div>
                  <ControlLabel>Comparison Team</ControlLabel>
                  <Select value={compareTeam} onChange={setCompareTeam} disabled={!availableCompareTeams.length}>
                    {availableCompareTeams.map((t) => (
                      <option key={t.team_code} value={t.team_code}>{t.team_code} — {t.label}</option>
                    ))}
                  </Select>
                </div>
              ) : null}

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <ControlLabel>Location Split</ControlLabel>
                  <Select value={homeAway} onChange={setHomeAway}>
                    <option value="all">All</option>
                    <option value="home">Home</option>
                    <option value="away">Away</option>
                  </Select>
                </div>
                <div>
                  <ControlLabel>Result Split</ControlLabel>
                  <Select value={resultFilter} onChange={setResultFilter}>
                    <option value="all">All</option>
                    <option value="W">Wins</option>
                    <option value="L">Losses</option>
                    <option value="T">Ties</option>
                  </Select>
                </div>
                <div>
                  <ControlLabel>Rolling Window</ControlLabel>
                  <Select value={rollWindow} onChange={setRollWindow}>
                    {[1, 3, 5, 7, 10].map((n) => (
                      <option key={n} value={String(n)}>{n}</option>
                    ))}
                  </Select>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main className="space-y-6">
          {error ? (
            <div className="rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              {error}
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <SummaryCard label="Points Returned" value={plot ? String(plot.summary.points) : "—"} sub={plot ? `${plot.season_from}–${plot.season_to} ${plot.season_type}` : "Waiting for chart"} />
            <SummaryCard label="Primary Avg" value={formatNum(plot?.summary.primary_avg)} sub={plot?.metric_label ?? "Selected metric"} />
            <SummaryCard label="Comparison Avg" value={formatNum(plot?.summary.compare_avg)} sub={plot?.compare_label ?? "No comparison"} />
            <SummaryCard label="Range" value={plot ? `${formatNum(plot.summary.primary_min)} → ${formatNum(plot.summary.primary_max)}` : "—"} sub={team ? `${team} selected` : "Choose a team"} />
          </div>

          <section className="rounded-[30px] border border-fuchsia-400/20 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.10),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.03))] p-5 backdrop-blur">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">{plot?.metric_label ?? currentMetric?.label ?? "Custom Chart"}</h2>
                <div className="mt-1 text-sm text-white/55">
                  {team || "Primary team"}
                  {plot && plot.compare_mode !== "none" ? ` vs ${plot.compare_label ?? "Comparison"}` : ""} • {granularity === "game" ? "Game by game" : "Season average"}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-white/60">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{sport.toUpperCase()}</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{seasonFrom}–{seasonTo}</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{homeAway === "all" ? "All locations" : homeAway}</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{resultFilter === "all" ? "All results" : resultFilter}</span>
              </div>
            </div>

            {renderChart()}

            <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
              {quickInsights.length ? (
                quickInsights.map((insight, idx) => (
                  <div key={idx} className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/75">
                    {insight}
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/55">
                  Build a chart to generate quick readouts for the selected split.
                </div>
              )}
            </div>
          </section>

          <section className="rounded-[28px] border border-white/10 bg-white/5 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold">Underlying Data Preview</h3>
              <div className="text-xs text-white/50">First 12 rows shown</div>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full divide-y divide-white/10 text-sm">
                <thead className="bg-white/5 text-left text-white/60">
                  <tr>
                    <th className="px-4 py-3">X</th>
                    <th className="px-4 py-3">Primary</th>
                    <th className="px-4 py-3">Compare</th>
                    <th className="px-4 py-3">Opponent</th>
                    <th className="px-4 py-3">Loc</th>
                    <th className="px-4 py-3">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 bg-black/20">
                  {chartData.slice(0, 12).map((row, idx) => (
                    <tr key={`${row.label}-${idx}`} className="text-white/80">
                      <td className="px-4 py-3">{row.tooltipLabel}</td>
                      <td className="px-4 py-3">{formatNum(row.primary)}</td>
                      <td className="px-4 py-3">{formatNum(row.compare)}</td>
                      <td className="px-4 py-3">{row.opponent ?? "—"}</td>
                      <td className="px-4 py-3">{row.home_away ?? "—"}</td>
                      <td className="px-4 py-3">{row.result ?? "—"}</td>
                    </tr>
                  ))}
                  {!chartData.length ? (
                    <tr>
                      <td className="px-4 py-8 text-center text-white/45" colSpan={6}>
                        No rows to preview for the current selection.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
