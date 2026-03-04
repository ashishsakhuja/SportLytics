"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  BarChart,
  Scatter,
  ScatterChart,
} from "recharts";

import { apiGet } from "@/lib/api";

type Row = {
  idx: number;
  date: string | null;
  opponent: string;
  home_away: "home" | "away";
  result: "W" | "L" | "T" | null;
  pf: number | null;
  pa: number | null;
  margin: number | null;

  pass_att: number | null;
  pass_cmp: number | null;
  pass_yds: number | null;
  completion_pct: number | null;
  rush_att: number | null;
  rush_yds: number | null;
  total_yds: number | null;
  turnovers: number | null;
  third_down_pct: number | null;
  red_zone_td_pct: number | null;
  sacks: number | null;

  ypa: number | null;
  rypa: number | null;
  pass_rate: number | null;
  sack_rate: number | null;
  plays: number | null;
  ypp: number | null;

  [k: string]: any; // rolling fields
};

type Resp = {
  sport: "nfl";
  team: string;
  season: number;
  season_type: string;
  games: number;
  roll_window: number;
  rows: Row[];
};

function pct(v: number | null | undefined) {
  if (v == null) return "n/a";
  return `${(v * 100).toFixed(1)}%`;
}

export default function NflInGameAnalytics({
  team,
  season,
  seasonType,
  cardClass,
}: {
  sport: string;
  team: string;
  season: number;
  seasonType: string;
  cardClass: string;
}) {
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!team || !season) return;
      setLoading(true);
      setErr(null);
      try {
        const res = await apiGet<Resp>(
          `/analytics/nfl/teams/${team}/in-game/summary?season=${season}&season_type=${seasonType}&last=60&roll=5`
        );
        if (cancelled) return;
        setData(res);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load NFL in-game stats.");
        setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [team, season, seasonType]);

  const rows = data?.rows ?? [];

  const summary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);

    const avg = (xs: Array<number | null>) => {
      const v = xs.filter((x) => x != null) as number[];
      if (!v.length) return null;
      return v.reduce((a, b) => a + b, 0) / v.length;
    };

    return {
      games: rows.length,
      ypa_last5: avg(last5.map((r) => r.ypa)),
      pass_rate_last5: avg(last5.map((r) => r.pass_rate)),
      sack_rate_last5: avg(last5.map((r) => r.sack_rate)),
      turnovers_last5: avg(last5.map((r) => r.turnovers)),
    };
  }, [rows]);

  const scatterYardsPoints = useMemo(() => {
    const wins: any[] = [];
    const losses: any[] = [];
    const ties: any[] = [];
    for (const r of rows) {
      if (r.total_yds == null || r.pf == null) continue;
      const p = {
        x: r.total_yds,
        y: r.pf,
        label: `G#${r.idx} ${r.home_away === "home" ? "vs" : "@"} ${r.opponent} (${r.result ?? ""})`,
      };
      if (r.result === "W") wins.push(p);
      else if (r.result === "L") losses.push(p);
      else ties.push(p);
    }
    return { wins, losses, ties };
  }, [rows]);

  const scatterTurnoversMargin = useMemo(() => {
    const out: any[] = [];
    for (const r of rows) {
      if (r.turnovers == null || r.margin == null) continue;
      out.push({
        x: r.turnovers,
        y: r.margin,
        label: `G#${r.idx} ${r.home_away === "home" ? "vs" : "@"} ${r.opponent} (${r.result ?? ""})`,
      });
    }
    return out;
  }, [rows]);

  if (loading) {
    return (
      <section className={cardClass}>
        <div className="text-sm text-white/70">Loading in-game stats…</div>
      </section>
    );
  }

  if (err) {
    return (
      <section className={cardClass}>
        <div className="text-sm text-red-300">{err}</div>
        <div className="mt-2 text-xs text-white/60">
          Make sure you ran backfill_team_game_stats for NFL for this season.
        </div>
      </section>
    );
  }

  if (!rows.length) {
    return (
      <section className={cardClass}>
        <div className="text-sm text-white/60">No in-game stats available.</div>
      </section>
    );
  }

  // NOTE: This component intentionally returns multiple <section> cards,
  // so SportDashboard shows these charts in separate boxes like the other plots.
  return (
    <>
      {/* Header card */}
      <section className={cardClass}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">NFL In-Game Analytics</h2>
            <div className="mt-1 text-xs text-white/60">
              Boxscore/advanced stats per game • derived rates + rolling trends
            </div>
          </div>

          {summary ? (
            <div className="text-right text-[11px] text-white/60 leading-relaxed">
              <div>{summary.games} games</div>
              <div>Last 5 YPA: {summary.ypa_last5?.toFixed(2) ?? "n/a"}</div>
              <div>Last 5 Pass Rate: {pct(summary.pass_rate_last5)}</div>
              <div>Last 5 Sack Rate: {pct(summary.sack_rate_last5)}</div>
              <div>Last 5 TO: {summary.turnovers_last5?.toFixed(2) ?? "n/a"}</div>
            </div>
          ) : null}
        </div>

        <div className="mt-3 text-xs text-white/60">
          Tip: the roll5 lines are the smooth trend read.
        </div>
      </section>

      {/* Passing volume + rate */}
      <section className={cardClass}>
        <div className="text-sm font-semibold">Passing Volume & Rate</div>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Pass Attempts</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pass_att"
                    name="pass_att"
                    dot={false}
                    strokeWidth={2.5}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">
              Pass Rate (Pass / (Pass + Rush))
            </div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tickFormatter={(v) => `${Math.round(v * 100)}%`}
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => {
                      if (v == null) return ["n/a", name];
                      return [`${(Number(v) * 100).toFixed(1)}%`, name];
                    }}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pass_rate"
                    name="pass_rate"
                    dot={false}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="pass_rate_roll5"
                    name="pass_rate (roll5)"
                    dot={false}
                    strokeWidth={2}
                    opacity={0.7}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>

      {/* QB efficiency */}
      <section className={cardClass}>
        <div className="text-sm font-semibold">QB Efficiency</div>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">
              Passing Efficiency (Yards / Attempt)
            </div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="ypa"
                    name="ypa"
                    dot={false}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="ypa_roll5"
                    name="ypa (roll5)"
                    dot={false}
                    strokeWidth={2}
                    opacity={0.7}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Completion %</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => {
                      if (v == null) return ["n/a", name];
                      return [`${Number(v).toFixed(1)}%`, name];
                    }}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="completion_pct"
                    name="completion_pct"
                    dot={false}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="comp_roll5"
                    name="completion (roll5)"
                    dot={false}
                    strokeWidth={2}
                    opacity={0.7}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>

      {/* Pressure + mistakes */}
      <section className={cardClass}>
        <div className="text-sm font-semibold">Pressure & Mistakes</div>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Pressure (Sack Rate)</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    domain={[0, "dataMax"]}
                    tickFormatter={(v) => `${Math.round(v * 100)}%`}
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => {
                      if (v == null) return ["n/a", name];
                      return [`${(Number(v) * 100).toFixed(1)}%`, name];
                    }}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="sack_rate"
                    name="sack_rate"
                    dot={false}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="sack_rate_roll5"
                    name="sack_rate (roll5)"
                    dot={false}
                    strokeWidth={2}
                    opacity={0.7}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Turnovers (per game)</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={rows}
                  margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    dataKey="idx"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                  />
                  <YAxis
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="turnovers" name="turnovers" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>

      {/* Situational */}
      <section className={cardClass}>
        <div className="text-sm font-semibold">
          Conversion Efficiency (3rd Down & Red Zone TD%)
        </div>
        <div className="mt-3 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={rows}
              margin={{ top: 18, right: 10, bottom: 10, left: -10 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis
                dataKey="idx"
                tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              />
              <YAxis
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(0,0,0,0.9)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  borderRadius: 12,
                  color: "white",
                  fontSize: 12,
                }}
                labelFormatter={(x) => `Game #${x}`}
                formatter={(v: any, name: any) => {
                  if (v == null) return ["n/a", name];
                  return [`${Number(v).toFixed(1)}%`, name];
                }}
              />
              <Legend
                wrapperStyle={{
                  color: "rgba(255,255,255,0.75)",
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="third_down_pct"
                name="3rd down %"
                dot={false}
                strokeWidth={2.5}
              />
              <Line
                type="monotone"
                dataKey="red_zone_td_pct"
                name="red zone TD %"
                dot={false}
                strokeWidth={2.5}
                opacity={0.8}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Relationships */}
      <section className={cardClass}>
        <div className="text-sm font-semibold">Relationships</div>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Total Yards vs Points For</div>
            <div className="mt-3 h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 18, right: 12, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name="Total Yards"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name="Points"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(_, payload: any) =>
                      payload?.[0]?.payload?.label ?? ""
                    }
                  />
                  <Legend
                    wrapperStyle={{
                      color: "rgba(255,255,255,0.75)",
                      fontSize: 12,
                    }}
                  />
                  <Scatter name="Wins" data={scatterYardsPoints.wins} fill="rgba(34,197,94,0.75)" />
                  <Scatter name="Losses" data={scatterYardsPoints.losses} fill="rgba(239,68,68,0.75)" />
                  {scatterYardsPoints.ties.length ? (
                    <Scatter name="Ties" data={scatterYardsPoints.ties} fill="rgba(255,255,255,0.6)" />
                  ) : null}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-xs text-white/60">
              Quick read: high yards + low points = red zone / turnover problems.
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Turnovers vs Margin</div>
            <div className="mt-3 h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 18, right: 12, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name="Turnovers"
                    allowDecimals={false}
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name="Margin"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(_, payload: any) =>
                      payload?.[0]?.payload?.label ?? ""
                    }
                  />
                  <Scatter name="Games" data={scatterTurnoversMargin} fill="rgba(255,255,255,0.7)" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-xs text-white/60">
              Most teams live in a simple rule: fewer turnovers → better margin.
            </div>
          </div>
        </div>
      </section>
    </>
  );
}