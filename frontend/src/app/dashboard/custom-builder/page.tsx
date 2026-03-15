"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toPng } from "html-to-image";
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
  max_overlay_teams: number;
  teams: TeamOption[];
  metrics: MetricOption[];
  compare_modes: Array<{ key: string; label: string }>;
  granularities: Array<{ key: string; label: string }>;
  chart_types: Array<{ key: string; label: string }>;
  presets: Array<{ key: string; label: string }>;
};

type PlotSeries = {
  key: string;
  label: string;
  kind: string;
  team?: string | null;
  metric?: string | null;
  metric_label?: string | null;
  roll_key?: string | null;
  points?: Array<{
    x: number;
    y: number;
    label: string;
    tooltipLabel: string;
    opponent?: string | null;
    home_away?: string | null;
    result?: string | null;
  }>;
};

type BuilderPlotResp = {
  sport: string;
  team: string;
  teams: string[];
  season_from: number;
  season_to: number;
  season_type: string;
  chart_type: string;
  metric: string;
  metric_label: string;
  secondary_metric?: string | null;
  secondary_metric_label?: string | null;
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
    compare_min?: number | null;
    compare_max?: number | null;
  };
  series: PlotSeries[];
  rows: Array<Record<string, string | number | null | undefined>>;
};

type PresetKey =
  | "team_form"
  | "metric_vs_metric"
  | "team_overlay"
  | "team_vs_league"
  | "scatter_profile";

const SPORTS: Array<{ key: SportKey; label: string }> = [
  { key: "nfl", label: "NFL" },
  { key: "nba", label: "NBA" },
  { key: "mlb", label: "MLB" },
  { key: "nhl", label: "NHL" },
];

const DEFAULT_SEASON = 2025;
const DEFAULT_SEASON_TYPE = "REG";
const DEFAULT_PRIMARY_METRIC = "score_for";
const DEFAULT_SECONDARY_METRIC = "score_against";

const SERIES_COLORS = [
  "rgba(217,70,239,0.95)",
  "rgba(99,102,241,0.95)",
  "rgba(34,197,94,0.95)",
  "rgba(251,191,36,0.95)",
  "rgba(244,114,182,0.95)",
  "rgba(56,189,248,0.95)",
];

function formatNum(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "—";
  return Math.abs(n) >= 100 ? n.toFixed(1) : n.toFixed(2);
}

function titleCase(text: string) {
  return text
    .split(" ")
    .map((p) => (p ? p[0].toUpperCase() + p.slice(1) : p))
    .join(" ");
}

function ControlLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/55">
      {children}
    </div>
  );
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

function SummaryCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-white/45">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {sub ? <div className="mt-1 text-sm text-white/55">{sub}</div> : null}
    </div>
  );
}

function buildCsv(rows: Array<Record<string, string | number | null | undefined>>) {
  if (!rows.length) return "";
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const escape = (value: string | number | null | undefined) => {
    const text = value == null ? "" : String(value);
    if (text.includes(",") || text.includes("\n") || text.includes('"')) {
      return `"${text.replaceAll('"', '""')}"`;
    }
    return text;
  };
  return [
    keys.join(","),
    ...rows.map((row) => keys.map((key) => escape(row[key])).join(",")),
  ].join("\n");
}

export default function CustomBuilderPage() {
  const [sport, setSport] = useState<SportKey>("nfl");
  const [seasonType, setSeasonType] = useState(DEFAULT_SEASON_TYPE);
  const [seasonFrom, setSeasonFrom] = useState(String(DEFAULT_SEASON));
  const [seasonTo, setSeasonTo] = useState(String(DEFAULT_SEASON));

  const [options, setOptions] = useState<BuilderOptionsResp | null>(null);
  const [team, setTeam] = useState("");
  const [overlayTeams, setOverlayTeams] = useState<string[]>([]);
  const [metric, setMetric] = useState(DEFAULT_PRIMARY_METRIC);
  const [secondaryMetric, setSecondaryMetric] = useState(DEFAULT_SECONDARY_METRIC);
  const [compareMode, setCompareMode] = useState("none");
  const [granularity, setGranularity] = useState("game");
  const [chartType, setChartType] = useState("line");
  const [homeAway, setHomeAway] = useState("all");
  const [resultFilter, setResultFilter] = useState("all");
  const [rollWindow, setRollWindow] = useState("5");

  const [loadingOptions, setLoadingOptions] = useState(false);
  const [loadingPlot, setLoadingPlot] = useState(false);
  const [plot, setPlot] = useState<BuilderPlotResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);

  const chartWrapRef = useRef<HTMLDivElement | null>(null);
  const exportCardRef = useRef<HTMLDivElement | null>(null);

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
          : next.metrics[0]?.key ?? DEFAULT_PRIMARY_METRIC;
        setMetric(nextMetric);

        const fallbackSecondary = next.metrics.some((m) => m.key === secondaryMetric)
          ? secondaryMetric
          : next.metrics.find((m) => m.key !== nextMetric)?.key ?? nextMetric;
        setSecondaryMetric(fallbackSecondary);

        setOverlayTeams((prev) => {
          const validPrev = prev.filter(
            (code) => next.teams.some((t) => t.team_code === code) && code !== nextTeam
          );
          return validPrev.slice(0, Math.max(0, (next.max_overlay_teams ?? 5) - 1));
        });
      } catch (e: any) {
        setError(e?.message ?? "Failed to load builder options");
        setOptions(null);
      } finally {
        setLoadingOptions(false);
      }
    }
    loadOptions();
  }, [sport, seasonType, seasonTo, team, metric, secondaryMetric]);

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
          compare_mode: chartType === "scatter" ? "metric" : compareMode,
          granularity,
          home_away: homeAway,
          result: resultFilter,
          roll_window: rollWindow,
          chart_type: chartType,
        });
        if (secondaryMetric && (compareMode === "metric" || chartType === "scatter")) {
          params.set("secondary_metric", secondaryMetric);
        }
        if (overlayTeams.length) {
          params.set("overlay_teams", overlayTeams.join(","));
        }

        const nextPlot = await apiGet<BuilderPlotResp>(
          `/analytics/custom/plot?${params.toString()}`
        );
        setPlot(nextPlot);
      } catch (e: any) {
        setPlot(null);
        setError(e?.message ?? "Failed to load chart data");
      } finally {
        setLoadingPlot(false);
      }
    }
    loadPlot();
  }, [
    sport,
    team,
    overlayTeams,
    seasonFrom,
    seasonTo,
    seasonType,
    metric,
    secondaryMetric,
    compareMode,
    granularity,
    chartType,
    homeAway,
    resultFilter,
    rollWindow,
  ]);

  useEffect(() => {
    if (chartType === "scatter") {
      setCompareMode("metric");
      setGranularity("game");
    }
  }, [chartType]);

  useEffect(() => {
    if (compareMode !== "overlay") {
      setOverlayTeams([]);
    }
  }, [compareMode]);

  useEffect(() => {
    if (secondaryMetric === metric) {
      const fallback = options?.metrics.find((m) => m.key !== metric)?.key;
      if (fallback) setSecondaryMetric(fallback);
    }
  }, [metric, options, secondaryMetric]);

  const currentMetric = useMemo(
    () => options?.metrics.find((m) => m.key === metric) ?? null,
    [options, metric]
  );

  const currentSecondaryMetric = useMemo(
    () => options?.metrics.find((m) => m.key === secondaryMetric) ?? null,
    [options, secondaryMetric]
  );

  const seasonOptions = useMemo(() => {
    const years: string[] = [];
    for (let y = 2025; y >= 2015; y--) years.push(String(y));
    return years;
  }, []);

  const compareModeOptions = useMemo(() => {
    return (options?.compare_modes ?? []).filter(
      (mode) => mode.key !== "metric" || chartType !== "scatter"
    );
  }, [options, chartType]);

  const selectedOverlayCount = useMemo(() => overlayTeams.length + 1, [overlayTeams]);

  const chartData = useMemo(() => plot?.rows ?? [], [plot]);

  const shareUrl = useMemo(() => {
    const params = new URLSearchParams({
      sport,
      team,
      season_from: seasonFrom,
      season_to: seasonTo,
      season_type: seasonType,
      metric,
      chart_type: chartType,
      compare_mode: chartType === "scatter" ? "metric" : compareMode,
      granularity,
      home_away: homeAway,
      result: resultFilter,
      roll_window: rollWindow,
    });
    if (overlayTeams.length) params.set("overlay_teams", overlayTeams.join(","));
    if (secondaryMetric && (compareMode === "metric" || chartType === "scatter")) {
      params.set("secondary_metric", secondaryMetric);
    }
    if (typeof window === "undefined") {
      return `/dashboard/custom-builder?${params.toString()}`;
    }
    return `${window.location.origin}/dashboard/custom-builder?${params.toString()}`;
  }, [
    sport,
    team,
    seasonFrom,
    seasonTo,
    seasonType,
    metric,
    secondaryMetric,
    chartType,
    compareMode,
    granularity,
    homeAway,
    resultFilter,
    rollWindow,
    overlayTeams,
  ]);

  const quickInsights = useMemo(() => {
    if (!plot) return [] as string[];
    const insights: string[] = [];
    const series = plot.series ?? [];

    if (plot.chart_type === "scatter") {
      insights.push(
        `${plot.metric_label} vs ${
          plot.secondary_metric_label ?? "secondary metric"
        } produced ${plot.summary.points} valid points.`
      );
      if (plot.summary.primary_avg != null && plot.summary.compare_avg != null) {
        insights.push(
          `Average point: ${formatNum(plot.summary.primary_avg)} ${plot.metric_label} and ${formatNum(
            plot.summary.compare_avg
          )} ${plot.secondary_metric_label ?? "comparison metric"}.`
        );
      }
      if (series.length > 1) {
        insights.push(
          `Overlaying ${series.length} teams makes pattern differences easier to spot immediately.`
        );
      }
      return insights;
    }

    if (series[0]) {
      insights.push(
        `${series[0].label} average: ${formatNum(plot.summary.primary_avg)} ${plot.metric_label}.`
      );
    }
    if (plot.roll_window > 1 && plot.granularity === "game") {
      insights.push(
        `Rolling ${plot.roll_window}-game smoothing is active for all line-capable series.`
      );
    }
    if (plot.compare_mode === "overlay") {
      insights.push(
        `Overlay mode is comparing ${series.length} teams on the same ${plot.metric_label} axis.`
      );
    } else if (plot.compare_mode === "metric") {
      insights.push(
        `Metric-vs-metric mode compares ${plot.metric_label} against ${
          plot.secondary_metric_label ?? "the selected comparison stat"
        }.`
      );
    } else if (plot.compare_mode === "league_avg") {
      insights.push(
        `League-average mode benchmarks ${team} against a season-level league baseline.`
      );
    } else if (plot.compare_mode === "previous_season") {
      insights.push(`Previous-season mode lines up the same team across adjacent years.`);
    }
    if (plot.summary.primary_max != null && plot.summary.primary_min != null) {
      insights.push(
        `Observed range runs from ${formatNum(plot.summary.primary_min)} to ${formatNum(
          plot.summary.primary_max
        )}.`
      );
    }
    return insights;
  }, [plot, team]);

  const visibleSeries = useMemo(() => {
    return (plot?.series ?? []).map((series, index) => ({
      ...series,
      color: SERIES_COLORS[index % SERIES_COLORS.length],
      rollColor: SERIES_COLORS[(index + 3) % SERIES_COLORS.length],
    }));
  }, [plot]);

  function applyPreset(key: PresetKey) {
    if (!options) return;
    const secondaryFallback =
      options.metrics.find((m) => m.key !== metric)?.key ?? secondaryMetric;

    switch (key) {
      case "team_form":
        setChartType("line");
        setCompareMode("none");
        setMetric("score_for");
        setGranularity("game");
        setRollWindow("5");
        break;
      case "metric_vs_metric":
        setChartType("line");
        setCompareMode("metric");
        setSecondaryMetric(secondaryFallback);
        setGranularity("game");
        setRollWindow("5");
        break;
      case "team_overlay":
        setChartType("line");
        setCompareMode("overlay");
        setMetric("score_for");
        setGranularity("game");
        setRollWindow("5");
        break;
      case "team_vs_league":
        setChartType("line");
        setCompareMode("league_avg");
        setMetric("score_for");
        setGranularity("season");
        setRollWindow("1");
        break;
      case "scatter_profile":
        setChartType("scatter");
        setCompareMode("metric");
        setGranularity("game");
        setMetric("score_for");
        setSecondaryMetric(secondaryFallback);
        break;
    }
  }

  function toggleOverlayTeam(code: string) {
    if (code === team) return;
    const limit = Math.max(1, options?.max_overlay_teams ?? 5) - 1;
    setOverlayTeams((prev) => {
      if (prev.includes(code)) return prev.filter((t) => t !== code);
      if (prev.length >= limit) return prev;
      return [...prev, code];
    });
  }

  async function downloadChartPng() {
    if (!exportCardRef.current) return;

    try {
      setDownloadStatus("Preparing PNG...");

      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => resolve());
        });
      });

      const dataUrl = await toPng(exportCardRef.current, {
        cacheBust: true,
        pixelRatio: 2,
        backgroundColor: "#050507",
        skipFonts: false,
      });

      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `sportlytics-custom-chart-${sport}-${team || "chart"}.png`;
      link.click();

      setDownloadStatus("Downloaded PNG");
      window.setTimeout(() => setDownloadStatus(null), 1600);
    } catch (err) {
      console.error("PNG export failed:", err);
      setDownloadStatus("PNG export failed");
      window.setTimeout(() => setDownloadStatus(null), 1800);
    }
  }

  function downloadCsv() {
    if (!plot?.rows?.length) return;
    const csv = buildCsv(plot.rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sportlytics-custom-data-${sport}-${team}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyStatus("Copied link");
      window.setTimeout(() => setCopyStatus(null), 1600);
    } catch {
      setCopyStatus("Copy failed");
      window.setTimeout(() => setCopyStatus(null), 1600);
    }
  }

  function renderStandardChart() {
    if (!plot || !visibleSeries.length || !chartData.length) {
      return (
        <div className="flex h-[460px] items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/20 text-white/50">
          No data yet for the current builder setup.
        </div>
      );
    }

    const commonProps = {
      data: chartData,
      margin: { top: 8, right: 20, left: 0, bottom: 0 },
    };

    const grid = (
      <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
    );
    const xAxis = (
      <XAxis
        dataKey="label"
        tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }}
        minTickGap={18}
      />
    );
    const yAxis = (
      <YAxis tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }} />
    );
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
          return row?.tooltipLabel ?? String(value);
        }}
      />
    );
    const legend = (
      <Legend wrapperStyle={{ color: "rgba(255,255,255,0.72)" }} />
    );

    if (chartType === "bar") {
      return (
        <ResponsiveContainer width="100%" height={460}>
          <BarChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            {visibleSeries.map((series) => (
              <Bar
                key={series.key}
                dataKey={series.key}
                name={series.label}
                fill={series.color}
                radius={[8, 8, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (chartType === "area") {
      return (
        <ResponsiveContainer width="100%" height={460}>
          <AreaChart {...commonProps}>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {legend}
            {visibleSeries.map((series) => (
              <Area
                key={series.key}
                type="monotone"
                dataKey={series.key}
                name={series.label}
                stroke={series.color}
                fill={series.color.replace("0.95", "0.18")}
                strokeWidth={3}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={460}>
        <LineChart {...commonProps}>
          {grid}
          {xAxis}
          {yAxis}
          {tooltip}
          {legend}
          {visibleSeries.map((series) => (
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              name={series.label}
              stroke={series.color}
              strokeWidth={3}
              dot={false}
            />
          ))}
          {plot.granularity === "game" && plot.roll_window > 1 && chartType === "line"
            ? visibleSeries.map((series) =>
                series.roll_key ? (
                  <Line
                    key={series.roll_key}
                    type="monotone"
                    dataKey={series.roll_key}
                    name={`${series.label} Roll ${plot.roll_window}`}
                    stroke={series.rollColor}
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="5 5"
                  />
                ) : null
              )
            : null}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  function renderScatterChart() {
    if (!plot || !visibleSeries.length) {
      return (
        <div className="flex h-[460px] items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/20 text-white/50">
          No scatter data available for the current builder setup.
        </div>
      );
    }

    const grid = (
      <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
    );
    const tooltip = (
      <Tooltip
        cursor={{ strokeDasharray: "3 3" }}
        contentStyle={{
          background: "rgba(10,10,16,0.96)",
          border: "1px solid rgba(255,255,255,0.12)",
          borderRadius: 14,
          color: "white",
        }}
      />
    );

    return (
      <ResponsiveContainer width="100%" height={460}>
        <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          {grid}
          <XAxis
            type="number"
            dataKey="x"
            name={plot.metric_label}
            tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={plot.secondary_metric_label ?? "Comparison"}
            tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11 }}
          />
          {tooltip}
          <Legend wrapperStyle={{ color: "rgba(255,255,255,0.72)" }} />
          {visibleSeries.map((series) => (
            <Scatter
              key={series.key}
              data={series.points ?? []}
              name={series.label}
              fill={series.color}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  const previewColumns = useMemo(() => {
    if (plot?.chart_type === "scatter") {
      return ["tooltipLabel", "x", "y", "opponent", "home_away", "result"];
    }
    const dynamicSeries = (plot?.series ?? []).flatMap((series) =>
      plot?.granularity === "game" && plot?.roll_window > 1 && series.roll_key
        ? [series.key, series.roll_key]
        : [series.key]
    );
    return ["tooltipLabel", ...dynamicSeries, "opponent", "home_away", "result"];
  }, [plot]);

  const previewRows = useMemo(() => {
    if (plot?.chart_type === "scatter") {
      return (plot?.series ?? []).flatMap((series) =>
        (series.points ?? []).map((point) => ({
          tooltipLabel: point.tooltipLabel,
          x: point.x,
          y: point.y,
          opponent: point.opponent ?? "—",
          home_away: point.home_away ?? "—",
          result: point.result ?? "—",
        }))
      );
    }
    return chartData;
  }, [plot, chartData]);

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="border-b border-white/10 bg-black/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1550px] items-start justify-between gap-6 px-6 py-5">
          <div>
            <div className="flex items-center gap-3">
              <Link href="/dashboard" className="text-white/70 transition hover:text-white">
                ← General Dashboard
              </Link>
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">
              Custom Builder
            </h1>
            <p className="mt-1 text-sm text-white/60">
              Build custom overlays, stat-vs-stat comparisons, presets, scatter
              profiles, and downloadable charts.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Link
              href="/dashboard"
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
            >
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

      <div className="mx-auto grid max-w-[1550px] grid-cols-1 gap-6 px-6 py-8 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-6 xl:self-start">
          <div className="rounded-[28px] border border-fuchsia-400/20 bg-[radial-gradient(circle_at_top_left,rgba(236,72,153,0.14),transparent_38%),linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.03))] p-5 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold">Builder Controls</div>
                <div className="mt-1 text-xs text-white/55">
                  Seamless, flexible charting across teams, metrics, and seasons.
                </div>
              </div>
              {(loadingOptions || loadingPlot) && (
                <div className="text-xs text-fuchsia-200">Loading…</div>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <ControlLabel>Presets</ControlLabel>
                <div className="flex flex-wrap gap-2">
                  {(options?.presets ?? []).map((preset) => (
                    <button
                      key={preset.key}
                      type="button"
                      onClick={() => applyPreset(preset.key as PresetKey)}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80 transition hover:border-fuchsia-400/30 hover:bg-white/10"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <ControlLabel>Sport</ControlLabel>
                <Select value={sport} onChange={(v) => setSport(v as SportKey)}>
                  {SPORTS.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ControlLabel>Season From</ControlLabel>
                  <Select value={seasonFrom} onChange={setSeasonFrom}>
                    {seasonOptions.map((year) => (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <ControlLabel>Season To</ControlLabel>
                  <Select value={seasonTo} onChange={setSeasonTo}>
                    {seasonOptions.map((year) => (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    ))}
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
                <Select
                  value={team}
                  onChange={setTeam}
                  disabled={!options?.teams?.length}
                >
                  {(options?.teams ?? []).map((t) => (
                    <option key={t.team_code} value={t.team_code}>
                      {t.team_code} — {t.label}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <ControlLabel>Primary Statistic</ControlLabel>
                <Select
                  value={metric}
                  onChange={setMetric}
                  disabled={!options?.metrics?.length}
                >
                  {(options?.metrics ?? []).map((m) => (
                    <option key={m.key} value={m.key}>
                      {m.label}
                      {m.source === "team_game_stats" ? " • adv" : ""}
                    </option>
                  ))}
                </Select>
                {currentMetric ? (
                  <div className="mt-2 text-xs text-white/50">
                    {currentMetric.group} •{" "}
                    {currentMetric.source === "team_game_stats"
                      ? "Database game stat"
                      : "Built-in result metric"}
                  </div>
                ) : null}
              </div>

              {compareMode === "metric" || chartType === "scatter" ? (
                <div>
                  <ControlLabel>
                    {chartType === "scatter"
                      ? "Y-Axis Statistic"
                      : "Comparison Statistic"}
                  </ControlLabel>
                  <Select
                    value={secondaryMetric}
                    onChange={setSecondaryMetric}
                    disabled={!options?.metrics?.length}
                  >
                    {(options?.metrics ?? [])
                      .filter((m) => m.key !== metric)
                      .map((m) => (
                        <option key={m.key} value={m.key}>
                          {m.label}
                          {m.source === "team_game_stats" ? " • adv" : ""}
                        </option>
                      ))}
                  </Select>
                  {currentSecondaryMetric ? (
                    <div className="mt-2 text-xs text-white/50">
                      {chartType === "scatter"
                        ? "Used on the scatter Y-axis."
                        : "Compared directly against the primary metric."}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ControlLabel>Comparison Mode</ControlLabel>
                  <Select
                    value={compareMode}
                    onChange={setCompareMode}
                    disabled={chartType === "scatter"}
                  >
                    {compareModeOptions.map((mode) => (
                      <option key={mode.key} value={mode.key}>
                        {mode.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <ControlLabel>Chart Type</ControlLabel>
                  <Select value={chartType} onChange={setChartType}>
                    {(options?.chart_types ?? []).map((type) => (
                      <option key={type.key} value={type.key}>
                        {type.label}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              {compareMode === "overlay" ? (
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <ControlLabel>Overlay Teams</ControlLabel>
                    <div className="text-xs text-white/45">
                      {selectedOverlayCount}/{options?.max_overlay_teams ?? 5} total teams
                    </div>
                  </div>
                  <div className="max-h-40 overflow-y-auto rounded-2xl border border-white/10 bg-black/20 p-2">
                    <div className="flex flex-wrap gap-2">
                      {(options?.teams ?? []).map((t) => {
                        const isActive =
                          overlayTeams.includes(t.team_code) || t.team_code === team;
                        const isPrimary = t.team_code === team;
                        return (
                          <button
                            key={t.team_code}
                            type="button"
                            onClick={() => toggleOverlayTeam(t.team_code)}
                            className={`rounded-full border px-3 py-1.5 text-xs transition ${
                              isPrimary
                                ? "border-fuchsia-400/50 bg-fuchsia-500/20 text-fuchsia-100"
                                : isActive
                                ? "border-indigo-400/40 bg-indigo-500/20 text-indigo-100"
                                : "border-white/10 bg-white/5 text-white/75 hover:bg-white/10"
                            }`}
                          >
                            {t.team_code}
                            {isPrimary ? " • primary" : ""}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ControlLabel>Granularity</ControlLabel>
                  <Select
                    value={granularity}
                    onChange={setGranularity}
                    disabled={chartType === "scatter"}
                  >
                    <option value="game">Game by Game</option>
                    <option value="season">Season Average</option>
                  </Select>
                </div>
                <div>
                  <ControlLabel>Rolling Window</ControlLabel>
                  <Select value={rollWindow} onChange={setRollWindow}>
                    {[1, 3, 5, 7, 10].map((n) => (
                      <option key={n} value={String(n)}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
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
            <SummaryCard
              label="Points Returned"
              value={plot ? String(plot.summary.points) : "—"}
              sub={
                plot
                  ? `${plot.season_from}–${plot.season_to} ${plot.season_type}`
                  : "Waiting for chart"
              }
            />
            <SummaryCard
              label={plot?.chart_type === "scatter" ? "X Avg" : "Primary Avg"}
              value={formatNum(plot?.summary.primary_avg)}
              sub={plot?.metric_label ?? "Selected metric"}
            />
            <SummaryCard
              label={plot?.chart_type === "scatter" ? "Y Avg" : "Comparison Avg"}
              value={formatNum(plot?.summary.compare_avg)}
              sub={plot?.secondary_metric_label ?? plot?.compare_label ?? "No comparison"}
            />
            <SummaryCard
              label="Range"
              value={
                plot
                  ? `${formatNum(plot.summary.primary_min)} → ${formatNum(plot.summary.primary_max)}`
                  : "—"
              }
              sub={team ? `${team} selected` : "Choose a team"}
            />
          </div>

          <section className="rounded-[30px] border border-fuchsia-400/20 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.10),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.03))] p-5 backdrop-blur">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h2 className="text-xl font-semibold">
                  {plot?.chart_type === "scatter"
                    ? `${plot.metric_label ?? currentMetric?.label ?? "Metric"} vs ${
                        plot.secondary_metric_label ?? currentSecondaryMetric?.label ?? "Metric"
                      }`
                    : plot?.metric_label ?? currentMetric?.label ?? "Custom Chart"}
                </h2>
                <div className="mt-1 text-sm text-white/55">
                  {team || "Primary team"}
                  {plot?.compare_mode === "overlay"
                    ? ` + ${Math.max(0, (plot.teams?.length ?? 1) - 1)} overlay team(s)`
                    : ""}
                  {plot?.compare_mode === "metric" && plot?.secondary_metric_label
                    ? ` vs ${plot.secondary_metric_label}`
                    : ""}
                  {plot?.compare_mode === "league_avg" && plot?.compare_label
                    ? ` vs ${plot.compare_label}`
                    : ""}
                  {plot?.compare_mode === "previous_season" && plot?.compare_label
                    ? ` vs ${plot.compare_label}`
                    : ""}
                  {chartType !== "scatter"
                    ? ` • ${granularity === "game" ? "Game by game" : "Season average"}`
                    : " • Scatter view"}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-white/60">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                  {sport.toUpperCase()}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                  {seasonFrom}–{seasonTo}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                  {homeAway === "all" ? "All locations" : titleCase(homeAway)}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                  {resultFilter === "all" ? "All results" : resultFilter}
                </span>
              </div>
            </div>

            <div className="mb-4 flex flex-wrap gap-2">
              <button
                onClick={downloadChartPng}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
              >
                Download PNG
              </button>
              <button
                onClick={downloadCsv}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
              >
                Export CSV
              </button>
              <button
                onClick={copyShareLink}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
              >
                Copy Share Link
              </button>
              {copyStatus ? (
                <div className="self-center text-xs text-fuchsia-200">{copyStatus}</div>
              ) : null}
              {downloadStatus ? (
                <div className="self-center text-xs text-fuchsia-200">{downloadStatus}</div>
              ) : null}
            </div>

            <div
              ref={exportCardRef}
              className="rounded-[28px] border border-fuchsia-400/15 bg-[radial-gradient(circle_at_top_left,rgba(168,85,247,0.12),transparent_35%),#050507] p-4 shadow-[0_0_40px_rgba(168,85,247,0.08)]"
            >
              <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-2xl font-semibold tracking-tight text-white">
                    {plot?.chart_type === "scatter"
                      ? `${plot.metric_label ?? currentMetric?.label ?? "Metric"} vs ${
                          plot.secondary_metric_label ??
                          currentSecondaryMetric?.label ??
                          "Metric"
                        }`
                      : plot?.metric_label ?? currentMetric?.label ?? "Custom Chart"}
                  </div>
                  <div className="mt-1 text-sm text-white/55">
                    {team || "Primary team"}
                    {plot?.compare_mode === "overlay"
                      ? ` + ${Math.max(0, (plot.teams?.length ?? 1) - 1)} overlay team(s)`
                      : ""}
                    {plot?.compare_mode === "metric" && plot?.secondary_metric_label
                      ? ` vs ${plot.secondary_metric_label}`
                      : ""}
                    {plot?.compare_mode === "league_avg" && plot?.compare_label
                      ? ` vs ${plot.compare_label}`
                      : ""}
                    {plot?.compare_mode === "previous_season" && plot?.compare_label
                      ? ` vs ${plot.compare_label}`
                      : ""}
                    {chartType !== "scatter"
                      ? ` • ${granularity === "game" ? "Game by game" : "Season average"}`
                      : " • Scatter view"}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs text-white/60">
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                    {sport.toUpperCase()}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                    {seasonFrom}–{seasonTo}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                    {homeAway === "all" ? "All locations" : titleCase(homeAway)}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
                    {resultFilter === "all" ? "All results" : resultFilter}
                  </span>
                </div>
              </div>

              <div ref={chartWrapRef} className="rounded-2xl bg-black/15 p-2">
                {plot?.chart_type === "scatter"
                  ? renderScatterChart()
                  : renderStandardChart()}
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
                {quickInsights.length ? (
                  quickInsights.map((insight, idx) => (
                    <div
                      key={idx}
                      className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/75"
                    >
                      {insight}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/55">
                    Build a chart to generate quick readouts for the selected split.
                  </div>
                )}
              </div>
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
                    {previewColumns.map((col) => (
                      <th key={col} className="px-4 py-3">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 bg-black/20">
                  {previewRows.slice(0, 12).map((row, idx) => (
                    <tr
                      key={`${row.tooltipLabel ?? row.label ?? idx}-${idx}`}
                      className="text-white/80"
                    >
                      {previewColumns.map((col) => (
                        <td key={`${idx}-${col}`} className="px-4 py-3">
                          {typeof row[col] === "number"
                            ? formatNum(row[col] as number)
                            : String(row[col] ?? "—")}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {!plot || !previewRows.length ? (
                    <tr>
                      <td
                        className="px-4 py-8 text-center text-white/45"
                        colSpan={previewColumns.length || 1}
                      >
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