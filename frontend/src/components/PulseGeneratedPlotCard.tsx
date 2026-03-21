"use client";

import { useMemo, useRef, useState } from "react";
import { toPng } from "html-to-image";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  Rectangle,
} from "recharts";

const COMMUNITY_SHARE_KEY = "sportlytics.community.share";
const SERIES_COLORS = ["#22d3ee", "#c084fc", "#f472b6", "#60a5fa", "#34d399"];

type PlotSeries = {
  key: string;
  label: string;
};

type PulseGeneratedPlot = {
  chart_id: string;
  title: string;
  subtitle?: string | null;
  kind: "bar" | "line";
  data: Array<Record<string, string | number | null>>;
  series: PlotSeries[];
  share_body?: string | null;
};

type Props = {
  plot: PulseGeneratedPlot;
  sport: string;
  season: number;
  seasonType: string;
  team?: string | null;
};

function normalizeBucketLabel(label: string) {
  const raw = String(label || "").trim();
  const lower = raw.toLowerCase();
  if (lower === "previous 5") return "Games 6–10 ago";
  if (lower === "last 5") return "Most recent 5";
  return raw;
}

function valueText(value: unknown) {
  return typeof value === "number" ? value.toFixed(2) : String(value ?? "—");
}

function SharedTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-xl border border-white/15 bg-black/90 px-3 py-2 text-sm text-white shadow-2xl backdrop-blur-sm">
      <div className="font-semibold text-white">{normalizeBucketLabel(String(label ?? ""))}</div>
      <div className="mt-2 space-y-1.5 text-xs text-white/75">
        {payload.map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: entry.color || entry.fill || "#fff" }}
              />
              <span>{entry.name}</span>
            </div>
            <span className="font-medium text-white">{valueText(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function legendFormatter(value: string) {
  return <span className="text-sm text-white/80">{value}</span>;
}

function renderRoundedBar(props: any) {
  const { fill, x, y, width, height, value } = props;
  if (width == null || height == null || x == null || y == null) return null;
  const radius: [number, number, number, number] =
    typeof value === "number" && value < 0 ? [0, 0, 10, 10] : [10, 10, 0, 0];
  return <Rectangle x={x} y={y} width={width} height={height} fill={fill} radius={radius} />;
}

export default function PulseGeneratedPlotCard({ plot, sport, season, seasonType, team }: Props) {
  const exportRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const series = useMemo(() => plot.series || [], [plot.series]);
  const colorMap = useMemo(
    () =>
      Object.fromEntries(series.map((item, idx) => [item.key, SERIES_COLORS[idx % SERIES_COLORS.length]])),
    [series]
  );

  async function createSnapshot() {
    if (!exportRef.current) return null;
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    return toPng(exportRef.current, {
      cacheBust: true,
      pixelRatio: 1.5,
      backgroundColor: "#050507",
      skipFonts: false,
      filter: (node) => !(node instanceof HTMLElement) || node.dataset.exportIgnore !== "true",
    });
  }

  async function handleDownload() {
    try {
      setStatus("Preparing PNG...");
      const dataUrl = await createSnapshot();
      if (!dataUrl) throw new Error("Snapshot unavailable");
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${plot.chart_id}.png`;
      a.click();
      setStatus("Downloaded PNG");
      window.setTimeout(() => setStatus(null), 1600);
    } catch {
      setStatus("Download failed");
      window.setTimeout(() => setStatus(null), 1800);
    }
  }

  async function handleShare() {
    try {
      setStatus("Preparing community draft...");
      const imageDataUrl = await createSnapshot().catch(() => null);
      window.sessionStorage.setItem(
        COMMUNITY_SHARE_KEY,
        JSON.stringify({
          plot_title: plot.title,
          plot_url: "/dashboard/signal-center",
          prefill_body:
            plot.share_body || `Sharing a Pulse-generated ${plot.title.toLowerCase()} view from SportLytics.`,
          plot_payload: {
            chart_id: plot.chart_id,
            chart_title: plot.title,
            sport,
            season,
            season_type: seasonType,
            team: team || null,
            summary: {
              source: "pulse-generated",
              subtitle: plot.subtitle,
              points: plot.data,
              series,
            },
            plot_url: "/dashboard/signal-center",
            image_data_url: imageDataUrl,
            shared_at: new Date().toISOString(),
          },
        })
      );
      window.location.assign("/dashboard/community?share=1");
    } catch {
      setStatus("Share failed");
      window.setTimeout(() => setStatus(null), 1800);
    }
  }

  return (
    <section className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-5 transition-all duration-200 hover:border-white/20 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.10),0_16px_50px_rgba(0,0,0,0.55)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-white">{plot.title}</h3>
          {plot.subtitle ? <div className="mt-1 text-sm text-white/65">{plot.subtitle}</div> : null}
          {(plot.data.some((row) => String(row.label ?? "").toLowerCase() === "previous 5") ||
            plot.data.some((row) => String(row.label ?? "").toLowerCase() === "last 5")) ? (
            <div className="mt-2 text-xs text-white/45">
              “Most recent 5” means the latest five games. “Games 6–10 ago” is the five right before that.
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-2" data-export-ignore="true">
          <button
            type="button"
            onClick={handleDownload}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/75 transition hover:bg-white/10 hover:text-white"
          >
            Download
          </button>
          <button
            type="button"
            onClick={handleShare}
            className="rounded-full border border-fuchsia-400/25 bg-fuchsia-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-fuchsia-100 transition hover:bg-fuchsia-500/15"
          >
            Share to community
          </button>
        </div>
      </div>

      <div ref={exportRef} className="mt-4 rounded-2xl border border-white/10 bg-black/30 p-4">
        <div className="h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            {plot.kind === "line" ? (
              <LineChart data={plot.data} margin={{ top: 10, right: 20, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis
                  dataKey="label"
                  tickFormatter={normalizeBucketLabel}
                  tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                  tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                />
                <YAxis
                  tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                  tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                />
                <Tooltip cursor={{ stroke: "rgba(255,255,255,0.15)" }} content={<SharedTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 14 }} formatter={legendFormatter} />
                {series.map((item) => (
                  <Line
                    key={item.key}
                    type="monotone"
                    dataKey={item.key}
                    name={item.label}
                    stroke={colorMap[item.key]}
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: colorMap[item.key], stroke: colorMap[item.key] }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            ) : (
              <BarChart data={plot.data} margin={{ top: 10, right: 20, left: 0, bottom: 8 }} barGap={10}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} vertical={false} />
                <XAxis
                  dataKey="label"
                  tickFormatter={normalizeBucketLabel}
                  tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                  tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                />
                <YAxis
                  tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                  tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
                />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }} content={<SharedTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 14 }} formatter={legendFormatter} />
                {series.map((item) => (
                  <Bar key={item.key} dataKey={item.key} name={item.label} shape={renderRoundedBar}>
                    {plot.data.map((_, index) => (
                      <Cell key={`${item.key}-${index}`} fill={colorMap[item.key]} />
                    ))}
                  </Bar>
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {status ? <div className="mt-3 text-xs text-white/60">{status}</div> : null}
    </section>
  );
}
