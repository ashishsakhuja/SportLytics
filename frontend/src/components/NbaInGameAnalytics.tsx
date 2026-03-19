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

  fg_m: number | null;
  fg_a: number | null;
  fg_pct: number | null; // percent (0-100)
  tp_m: number | null;
  tp_a: number | null;
  tp_pct: number | null; // percent (0-100)
  ft_m: number | null;
  ft_a: number | null;
  ft_pct: number | null; // percent (0-100)

  oreb: number | null;
  dreb: number | null;
  reb: number | null;
  ast: number | null;
  tov: number | null;
  stl: number | null;
  blk: number | null;
  pfouls: number | null;

  possessions_est: number | null;
  efg: number | null; // 0-1
  ts: number | null; // 0-1
  ppp: number | null;
  ast_tov: number | null;

  [k: string]: any;
};

type Resp = {
  sport: "nba";
  team: string;
  season: number;
  season_type: string;
  games: number;
  roll_window: number;
  rows: Row[];
};

function pct01(v: number | null | undefined) {
  if (v == null) return "n/a";
  return `${(v * 100).toFixed(1)}%`;
}

function pct100(v: number | null | undefined) {
  if (v == null) return "n/a";
  return `${v.toFixed(1)}%`;
}

function avg(nums: Array<number | null | undefined>) {
  const clean = nums.filter((x) => typeof x === "number") as number[];
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

const INGAME_BAR_BLUE = "rgba(59,130,246,0.82)";

export default function NbaInGameAnalytics({
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

  const shootingChartRef = useRef<HTMLDivElement | null>(null);
  const efficiencyChartRef = useRef<HTMLDivElement | null>(null);
  const ballMovementChartRef = useRef<HTMLDivElement | null>(null);
  const paceChartRef = useRef<HTMLDivElement | null>(null);
  const activityChartRef = useRef<HTMLDivElement | null>(null);

  const shootingRef = useRef<HTMLElement | null>(null);
  const efficiencyRef = useRef<HTMLElement | null>(null);
  const ballMovementRef = useRef<HTMLElement | null>(null);
  const paceOffenseRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!team || !season) return;
      setLoading(true);
      setErr(null);
      try {
        const res = await apiGet<Resp>(
          `/analytics/nba/teams/${team}/in-game/summary?season=${season}&season_type=${seasonType}&last=120&roll=5`
        );
        if (cancelled) return;
        setData(res);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load NBA in-game stats.");
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

  const shootingSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_fg_pct: avg(last5.map((r) => r.fg_pct)),
      prev5_fg_pct: avg(prev5.map((r) => r.fg_pct)),
      last5_tp_pct: avg(last5.map((r) => r.tp_pct)),
      prev5_tp_pct: avg(prev5.map((r) => r.tp_pct)),
      last5_ft_pct: avg(last5.map((r) => r.ft_pct)),
      prev5_ft_pct: avg(prev5.map((r) => r.ft_pct)),
    };
  }, [rows]);

  const efficiencySummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_efg: avg(last5.map((r) => r.efg)),
      prev5_efg: avg(prev5.map((r) => r.efg)),
      last5_ts: avg(last5.map((r) => r.ts)),
      prev5_ts: avg(prev5.map((r) => r.ts)),
      last5_ppp: avg(last5.map((r) => r.ppp)),
      prev5_ppp: avg(prev5.map((r) => r.ppp)),
      last5_poss: avg(last5.map((r) => r.possessions_est)),
      prev5_poss: avg(prev5.map((r) => r.possessions_est)),
    };
  }, [rows]);

  const ballMovementSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_ast: avg(last5.map((r) => r.ast)),
      prev5_ast: avg(prev5.map((r) => r.ast)),
      last5_tov: avg(last5.map((r) => r.tov)),
      prev5_tov: avg(prev5.map((r) => r.tov)),
      last5_ast_tov: avg(last5.map((r) => r.ast_tov)),
      prev5_ast_tov: avg(prev5.map((r) => r.ast_tov)),
    };
  }, [rows]);

  const paceOffenseSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_pf: avg(last5.map((r) => r.pf)),
      prev5_pf: avg(prev5.map((r) => r.pf)),
      last5_margin: avg(last5.map((r) => r.margin)),
      prev5_margin: avg(prev5.map((r) => r.margin)),
      last5_poss: avg(last5.map((r) => r.possessions_est)),
      prev5_poss: avg(prev5.map((r) => r.possessions_est)),
    };
  }, [rows]);

  const activitySummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_reb: avg(last5.map((r) => r.reb)),
      prev5_reb: avg(prev5.map((r) => r.reb)),
      last5_stl: avg(last5.map((r) => r.stl)),
      prev5_stl: avg(prev5.map((r) => r.stl)),
      last5_blk: avg(last5.map((r) => r.blk)),
      prev5_blk: avg(prev5.map((r) => r.blk)),
    };
  }, [rows]);

  const scatterPossPoints = useMemo(() => {
    const wins: any[] = [];
    const losses: any[] = [];
    const ties: any[] = [];
    for (const r of rows) {
      if (r.possessions_est == null || r.pf == null) continue;
      const p = {
        x: r.possessions_est,
        y: r.pf,
        label: `G#${r.idx} ${r.home_away === "home" ? "vs" : "@"} ${r.opponent} (${r.result ?? ""})`,
      };
      if (r.result === "W") wins.push(p);
      else if (r.result === "L") losses.push(p);
      else ties.push(p);
    }
    return { wins, losses, ties };
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
          Make sure you ran backfill_team_game_stats for NBA for this season.
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

  const roll = data?.roll_window ?? 5;

  return (
    <section className={cardClass}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">NBA In-Game (Boxscore) Analytics</h2>
          <div className="mt-1 text-xs text-white/60">
            shooting • efficiency • pace • ball movement (last {rows.length} games)
          </div>
        </div>
        <div className="text-xs text-white/60">roll-{roll}</div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div>
      {/* Shooting % trend */}
      <div className="mt-4 text-sm font-semibold">Shooting Trends</div>
      <PlotActions exportRef={shootingChartRef} chartId="nba_shooting" chartTitle={`${team} Shooting Trends`} sport="nba" season={season} seasonType={seasonType} team={team} summary={shootingSummary} plotUrl={`/dashboard/nba`} shareBody={`Sharing the ${team} shooting trends chart.`} />
      <div ref={shootingChartRef} className="mt-4 h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 28, right: 10, bottom: 10, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
            <XAxis
              dataKey="idx"
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                background: "rgba(0,0,0,0.9)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 12,
                color: "white",
              }}
              formatter={(v: any, k: any) => [typeof v === "number" ? v.toFixed(1) : v, k]}
              labelFormatter={(l) => `Game #${l}`}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconSize={8}
              wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
            />
            <Line type="monotone" dataKey={`fg_pct_roll${roll}`} name="FG% (roll)" dot={false} />
            <Line type="monotone" dataKey={`tp_pct_roll${roll}`} name="3P% (roll)" dot={false} />
            <Line type="monotone" dataKey={`ft_pct_roll${roll}`} name="FT% (roll)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {shootingSummary ? (
        <AIInsightsBox
          chartId="nba_shooting"
          sport="nba"
          season={season}
          seasonType={seasonType}
          team={team}
          summary={shootingSummary}
          tip="Look for FG% + 3P% moving together; FT% is usually steadier."
        />
      ) : null}

        </div>

        <div>
      {/* Efficiency trend */}
      <div className="mt-6 text-sm font-semibold">Efficiency Trends</div>
      <PlotActions exportRef={efficiencyChartRef} chartId="nba_efficiency" chartTitle={`${team} Efficiency Trends`} sport="nba" season={season} seasonType={seasonType} team={team} summary={efficiencySummary} plotUrl={`/dashboard/nba`} shareBody={`Sharing the ${team} efficiency trends chart.`} />
      <div ref={efficiencyChartRef} className="mt-6 h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 28, right: 10, bottom: 10, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
            <XAxis
              dataKey="idx"
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
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
              formatter={(v: any, k: any) => {
                if (typeof v !== "number") return [v, k];
                if (k === `efg_roll${roll}` || k === `ts_roll${roll}`) return [pct01(v), k];
                return [v.toFixed(3), k];
              }}
              labelFormatter={(l) => `Game #${l}`}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconSize={8}
              wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
            />
            <Line type="monotone" dataKey={`efg_roll${roll}`} name="eFG% (roll)" dot={false} />
            <Line type="monotone" dataKey={`ts_roll${roll}`} name="TS% (roll)" dot={false} />
            <Line type="monotone" dataKey={`ppp_roll${roll}`} name="Pts/Poss (roll)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {efficiencySummary ? (
        <AIInsightsBox
          chartId="nba_efficiency"
          sport="nba"
          season={season}
          seasonType={seasonType}
          team={team}
          summary={efficiencySummary}
          tip="If TS% is up and possessions are stable, the scoring bump is usually real."
        />
      ) : null}

        </div>

        <div>
      {/* Ball movement */}
      <div className="mt-6 text-sm font-semibold">Ball Movement</div>
      <PlotActions exportRef={ballMovementChartRef} chartId="nba_ball_movement" chartTitle={`${team} Ball Movement`} sport="nba" season={season} seasonType={seasonType} team={team} summary={ballMovementSummary} plotUrl={`/dashboard/nba`} shareBody={`Sharing the ${team} ball movement chart.`} />
      <div ref={ballMovementChartRef} className="mt-6 h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows.slice(-12)} margin={{ top: 28, right: 10, bottom: 10, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
            <XAxis
              dataKey="idx"
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
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
              labelFormatter={(l) => `Game #${l}`}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconSize={8}
              wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
            />
            <Bar dataKey="ast" name="AST" fill={INGAME_BAR_BLUE} />
            <Bar dataKey="tov" name="TOV" fill="rgba(96,165,250,0.58)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {ballMovementSummary ? (
        <AIInsightsBox
          chartId="nba_ball_movement"
          sport="nba"
          season={season}
          seasonType={seasonType}
          team={team}
          summary={ballMovementSummary}
          tip="AST/TOV rising usually signals cleaner creation, not just hot shooting."
        />
      ) : null}

        </div>

        <div>
      {/* Possessions vs points */}
      <div className="mt-6 text-sm font-semibold">Pace & Offense Relationship</div>
      <PlotActions exportRef={paceChartRef} chartId="nba_pace_offense" chartTitle={`${team} Possessions vs Points`} sport="nba" season={season} seasonType={seasonType} team={team} summary={paceOffenseSummary} plotUrl={`/dashboard/nba`} shareBody={`Sharing the ${team} possessions vs points chart.`} />
      <div ref={paceChartRef} className="mt-6 h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 18, right: 10, bottom: 10, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
            <XAxis
              type="number"
              dataKey="x"
              name="Possessions"
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Points"
              tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{
                background: "rgba(0,0,0,0.9)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 12,
                color: "white",
              }}
              formatter={(v: any, k: any, p: any) => {
                if (k === "x") return [Number(v).toFixed(1), "Possessions"];
                if (k === "y") return [v, "Points"];
                return [v, k];
              }}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ""}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconSize={8}
              wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
            />
            <Scatter name="Wins" data={scatterPossPoints.wins} />
            <Scatter name="Losses" data={scatterPossPoints.losses} />
            <Scatter name="Other" data={scatterPossPoints.ties} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {paceOffenseSummary ? (
        <AIInsightsBox
          chartId="nba_pace_offense"
          sport="nba"
          season={season}
          seasonType={seasonType}
          team={team}
          summary={paceOffenseSummary}
          tip="If points rise with possessions flat, it’s efficiency; if possessions rise, it’s pace."
        />
      ) : null}


        </div>

        <div>
      {/* Rebounding & activity */}
      <div className="text-sm font-semibold">Rebounding & Activity</div>
      <PlotActions exportRef={activityChartRef} chartId="nba_activity" chartTitle={`${team} Rebounding & Activity`} sport="nba" season={season} seasonType={seasonType} team={team} summary={activitySummary} plotUrl={`/dashboard/nba`} shareBody={`Sharing the ${team} rebounding and activity chart.`} />
      <div ref={activityChartRef} className="mt-4 h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows.slice(-12)} margin={{ top: 28, right: 10, bottom: 10, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
            <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} axisLine={{ stroke: "rgba(255,255,255,0.15)" }} tickLine={{ stroke: "rgba(255,255,255,0.15)" }} />
            <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} axisLine={{ stroke: "rgba(255,255,255,0.15)" }} tickLine={{ stroke: "rgba(255,255,255,0.15)" }} />
            <Tooltip contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white" }} labelFormatter={(l) => `Game #${l}`} />
            <Legend verticalAlign="top" height={20} iconSize={8} wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }} />
            <Bar dataKey="reb" name="REB" fill={INGAME_BAR_BLUE} />
            <Bar dataKey="stl" name="STL" fill="rgba(96,165,250,0.58)" />
            <Bar dataKey="blk" name="BLK" fill="rgba(147,197,253,0.45)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activitySummary ? (
        <AIInsightsBox
          chartId="nba_activity"
          sport="nba"
          season={season}
          seasonType={seasonType}
          team={team}
          summary={activitySummary}
          tip="Rebounding plus steals and blocks helps separate effort-driven wins from hot shooting nights."
        />
      ) : null}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs text-white/60">Latest game</div>
          <div className="mt-1 font-semibold">
            Game #{rows[rows.length - 1]?.idx} {rows[rows.length - 1]?.home_away === "home" ? "vs" : "@"} {rows[rows.length - 1]?.opponent}
          </div>
          <div className="mt-2 text-white/75">
            Score: {rows[rows.length - 1]?.pf ?? "—"}–{rows[rows.length - 1]?.pa ?? "—"} ({rows[rows.length - 1]?.result ?? ""})
          </div>
          <div className="mt-2 text-white/75">
            FG%: {pct100(rows[rows.length - 1]?.fg_pct)} • 3P%: {pct100(rows[rows.length - 1]?.tp_pct)} • FT%: {pct100(rows[rows.length - 1]?.ft_pct)}
          </div>
          <div className="mt-1 text-white/75">
            eFG%: {pct01(rows[rows.length - 1]?.efg)} • TS%: {pct01(rows[rows.length - 1]?.ts)} • Pts/Poss: {rows[rows.length - 1]?.ppp?.toFixed?.(3) ?? "n/a"}
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs text-white/60">Last 5 averages</div>
          <div className="mt-2 text-white/75">
            eFG%: {pct01(efficiencySummary?.last5_efg)} • TS%: {pct01(efficiencySummary?.last5_ts)}
          </div>
          <div className="mt-1 text-white/75">
            Pts/Poss: {efficiencySummary?.last5_ppp != null ? efficiencySummary.last5_ppp.toFixed(3) : "n/a"} • Poss: {efficiencySummary?.last5_poss != null ? efficiencySummary.last5_poss.toFixed(1) : "n/a"}
          </div>
          <div className="mt-1 text-white/75">
            AST/TOV: {ballMovementSummary?.last5_ast_tov != null ? ballMovementSummary.last5_ast_tov.toFixed(2) : "n/a"}
          </div>
        </div>
      </div>
    </section>
  );
}
