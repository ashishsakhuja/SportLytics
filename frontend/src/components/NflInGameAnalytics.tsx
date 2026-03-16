"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import PlotActions from "@/components/PlotActions";
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
import AIInsightsBox from "@/components/AIInsightsBox";

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

function avg(nums: Array<number | null | undefined>) {
  const clean = nums.filter((x) => typeof x === "number") as number[];
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
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

  const overviewRef = useRef<HTMLElement | null>(null);
  const passingRef = useRef<HTMLElement | null>(null);
  const qbRef = useRef<HTMLElement | null>(null);
  const pressureRef = useRef<HTMLElement | null>(null);
  const conversionsRef = useRef<HTMLElement | null>(null);
  const relationshipsRef = useRef<HTMLElement | null>(null);

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

  const overviewSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    return {
      games: rows.length,
      last5_ypa: avg(last5.map((r) => r.ypa)),
      last5_pass_rate: avg(last5.map((r) => r.pass_rate)),
      last5_sack_rate: avg(last5.map((r) => r.sack_rate)),
      last5_turnovers: avg(last5.map((r) => r.turnovers)),
      last5_third_down: avg(last5.map((r) => r.third_down_pct)),
      last5_red_zone_td: avg(last5.map((r) => r.red_zone_td_pct)),
    };
  }, [rows]);

  const passingSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_pass_att: avg(last5.map((r) => r.pass_att)),
      prev5_pass_att: avg(prev5.map((r) => r.pass_att)),
      last5_pass_rate: avg(last5.map((r) => r.pass_rate)),
      prev5_pass_rate: avg(prev5.map((r) => r.pass_rate)),
    };
  }, [rows]);

  const qbEfficiencySummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_ypa: avg(last5.map((r) => r.ypa)),
      prev5_ypa: avg(prev5.map((r) => r.ypa)),
      last5_completion_pct: avg(last5.map((r) => r.completion_pct)),
      prev5_completion_pct: avg(prev5.map((r) => r.completion_pct)),
      last5_ypp: avg(last5.map((r) => r.ypp)),
      prev5_ypp: avg(prev5.map((r) => r.ypp)),
    };
  }, [rows]);

  const pressureMistakesSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_sack_rate: avg(last5.map((r) => r.sack_rate)),
      prev5_sack_rate: avg(prev5.map((r) => r.sack_rate)),
      last5_turnovers: avg(last5.map((r) => r.turnovers)),
      prev5_turnovers: avg(prev5.map((r) => r.turnovers)),
      last5_margin: avg(last5.map((r) => r.margin)),
      prev5_margin: avg(prev5.map((r) => r.margin)),
    };
  }, [rows]);

  const conversionsSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_third_down: avg(last5.map((r) => r.third_down_pct)),
      prev5_third_down: avg(prev5.map((r) => r.third_down_pct)),
      last5_red_zone_td: avg(last5.map((r) => r.red_zone_td_pct)),
      prev5_red_zone_td: avg(prev5.map((r) => r.red_zone_td_pct)),
    };
  }, [rows]);

  const relationshipsSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_total_yds: avg(last5.map((r) => r.total_yds)),
      prev5_total_yds: avg(prev5.map((r) => r.total_yds)),
      last5_pf: avg(last5.map((r) => r.pf)),
      prev5_pf: avg(prev5.map((r) => r.pf)),
      last5_turnovers: avg(last5.map((r) => r.turnovers)),
      prev5_turnovers: avg(prev5.map((r) => r.turnovers)),
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

  return (
    <>
      {/* Header */}
      <section ref={overviewRef} className={cardClass}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">NFL In-Game Analytics</h2>
            <div className="mt-1 text-xs text-white/60">
              Boxscore/advanced stats per game • derived rates + rolling trends
            </div>
          </div>

          {overviewSummary ? (
            <div className="text-right text-[11px] text-white/60 leading-relaxed">
              <div>{rows.length} games</div>
              <div>Last 5 YPA: {overviewSummary.last5_ypa?.toFixed(2) ?? "n/a"}</div>
              <div>Last 5 Pass Rate: {pct(overviewSummary.last5_pass_rate)}</div>
              <div>Last 5 Sack Rate: {pct(overviewSummary.last5_sack_rate)}</div>
              <div>Last 5 TO: {overviewSummary.last5_turnovers?.toFixed(2) ?? "n/a"}</div>
            </div>
          ) : null}
        </div>

        <div className="mt-3 text-xs text-white/60">
          Tip: the roll5 lines are the smooth trend read.
        </div>

        <div className="mt-4 text-sm font-semibold">Top-Level Trend Snapshot</div>
        <PlotActions exportRef={overviewRef} chartId="nfl_ingame_overview" chartTitle={`${team} NFL In-Game Trend Snapshot`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={overviewSummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} NFL in-game trend snapshot.`} />
        <div className="mt-4 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
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
              <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Line type="monotone" dataKey="ypa_roll5" name="YPA (roll5)" dot={false} strokeWidth={2.5} />
              <Line type="monotone" dataKey="completion_pct" name="Completion %" dot={false} strokeWidth={2} opacity={0.8} />
              <Line type="monotone" dataKey="third_down_pct" name="3rd Down %" dot={false} strokeWidth={2} opacity={0.8} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {overviewSummary ? (
          <AIInsightsBox
            chartId="nfl_ingame_overview"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={overviewSummary}
          />
        ) : null}
      </section>

      {/* Passing volume + rate */}
      <section ref={passingRef} className={cardClass}>
        <div className="text-sm font-semibold">Passing Volume & Rate</div>
        <PlotActions exportRef={passingRef} chartId="nfl_passing_volume_rate" chartTitle={`${team} Passing Volume & Rate`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={passingSummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} passing volume and rate chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Pass Attempts</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="pass_att" name="pass_att" dot={false} strokeWidth={2.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Pass Rate (Pass / (Pass + Rush))</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="pass_rate" name="pass_rate" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="pass_rate_roll5" name="pass_rate (roll5)" dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {passingSummary ? (
          <AIInsightsBox
            chartId="nfl_passing"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={passingSummary}
          />
        ) : null}
      </section>

      {/* QB efficiency */}
      <section ref={qbRef} className={cardClass}>
        <div className="text-sm font-semibold">QB Efficiency</div>
        <PlotActions exportRef={qbRef} chartId="nfl_qb_efficiency" chartTitle={`${team} QB Efficiency`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={qbEfficiencySummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} QB efficiency chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Passing Efficiency (Yards / Attempt)</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="ypa" name="ypa" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="ypa_roll5" name="ypa (roll5)" dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Completion %</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="completion_pct" name="completion_pct" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="comp_roll5" name="completion (roll5)" dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {qbEfficiencySummary ? (
          <AIInsightsBox
            chartId="nfl_qb_efficiency"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={qbEfficiencySummary}
          />
        ) : null}
      </section>

      {/* Pressure + mistakes */}
      <section ref={pressureRef} className={cardClass}>
        <div className="text-sm font-semibold">Pressure & Mistakes</div>
        <PlotActions exportRef={pressureRef} chartId="nfl_pressure_mistakes" chartTitle={`${team} Pressure, Mistakes & Margin`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={pressureMistakesSummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} pressure and mistakes chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Pressure (Sack Rate)</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="sack_rate" name="sack_rate" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="sack_rate_roll5" name="sack_rate (roll5)" dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Turnovers (per game)</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
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
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Bar dataKey="turnovers" name="turnovers" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {pressureMistakesSummary ? (
          <AIInsightsBox
            chartId="nfl_pressure_mistakes"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={pressureMistakesSummary}
          />
        ) : null}
      </section>

      {/* Situational */}
      <section ref={conversionsRef} className={cardClass}>
        <div className="text-sm font-semibold">Conversion Efficiency (3rd Down & Red Zone TD%)</div>
        <PlotActions exportRef={conversionsRef} chartId="nfl_conversions" chartTitle={`${team} Conversions & Red Zone`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={conversionsSummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} conversions and red zone chart.`} />
        <div className="mt-3 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
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
              <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Line type="monotone" dataKey="third_down_pct" name="3rd down %" dot={false} strokeWidth={2.5} />
              <Line type="monotone" dataKey="red_zone_td_pct" name="red zone TD %" dot={false} strokeWidth={2.5} opacity={0.8} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {conversionsSummary ? (
          <AIInsightsBox
            chartId="nfl_conversions"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={conversionsSummary}
          />
        ) : null}
      </section>

      {/* Relationships */}
      <section ref={relationshipsRef} className={cardClass}>
        <div className="text-sm font-semibold">Relationships</div>
        <PlotActions exportRef={relationshipsRef} chartId="nfl_yards_points_relationships" chartTitle={`${team} Yards / Points Relationships`} sport="nfl" season={season} seasonType={seasonType} team={team} summary={relationshipsSummary} plotUrl={`/dashboard/nfl`} shareBody={`Sharing the ${team} yards and points relationships chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Total Yards vs Points For</div>
            <div className="mt-3 h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 18, right: 12, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis type="number" dataKey="x" name="Total Yards" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <YAxis type="number" dataKey="y" name="Points" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(_, payload: any) => payload?.[0]?.payload?.label ?? ""}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
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
                  <XAxis type="number" dataKey="x" name="Turnovers" allowDecimals={false} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <YAxis type="number" dataKey="y" name="Margin" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    cursor={{ stroke: "rgba(255,255,255,0.15)" }}
                    contentStyle={{
                      background: "rgba(0,0,0,0.9)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                    labelFormatter={(_, payload: any) => payload?.[0]?.payload?.label ?? ""}
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

        {relationshipsSummary ? (
          <AIInsightsBox
            chartId="nfl_relationships"
            sport="nfl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={relationshipsSummary}
          />
        ) : null}
      </section>
    </>
  );
}