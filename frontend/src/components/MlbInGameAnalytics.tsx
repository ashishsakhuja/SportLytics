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
  result: "W" | "L" | null;
  pf: number | null;
  pa: number | null;
  margin: number | null;

  ab: number | null;
  hits: number | null;
  doubles: number | null;
  triples: number | null;
  home_runs: number | null;
  rbi: number | null;
  walks: number | null;
  strikeouts: number | null;
  stolen_bases: number | null;
  left_on_base: number | null;
  total_bases: number | null;

  batting_avg: number | null;
  obp: number | null;
  slg: number | null;
  ops: number | null;
  iso: number | null;
  kbb: number | null;

  [k: string]: any;
};

type Resp = {
  sport: "mlb";
  team: string;
  season: number;
  season_type: string;
  games: number;
  roll_window: number;
  rows: Row[];
};

function pct1k(v: number | null | undefined) {
  if (v == null) return "n/a";
  return v.toFixed(3);
}

function avg(nums: Array<number | null | undefined>) {
  const clean = nums.filter((x) => typeof x === "number") as number[];
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

const INGAME_BAR_BLUE = "rgba(59,130,246,0.82)";

export default function MlbInGameAnalytics({
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
  const offenseRef = useRef<HTMLElement | null>(null);
  const slashRef = useRef<HTMLElement | null>(null);
  const disciplineRef = useRef<HTMLElement | null>(null);
  const powerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!team || !season) return;
      setLoading(true);
      setErr(null);

      try {
        const res = await apiGet<Resp>(
          `/analytics/mlb/teams/${team}/in-game/summary?season=${season}&season_type=${seasonType}&last=162&roll=5`
        );
        if (cancelled) return;
        setData(res);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load MLB in-game stats.");
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
  const roll = data?.roll_window ?? 5;

  const offenseSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_runs: avg(last5.map((r) => r.pf)),
      prev5_runs: avg(prev5.map((r) => r.pf)),
      last5_hits: avg(last5.map((r) => r.hits)),
      prev5_hits: avg(prev5.map((r) => r.hits)),
      last5_hr: avg(last5.map((r) => r.home_runs)),
      prev5_hr: avg(prev5.map((r) => r.home_runs)),
    };
  }, [rows]);

  const slashSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_obp: avg(last5.map((r) => r.obp)),
      prev5_obp: avg(prev5.map((r) => r.obp)),
      last5_slg: avg(last5.map((r) => r.slg)),
      prev5_slg: avg(prev5.map((r) => r.slg)),
      last5_ops: avg(last5.map((r) => r.ops)),
      prev5_ops: avg(prev5.map((r) => r.ops)),
      last5_iso: avg(last5.map((r) => r.iso)),
      prev5_iso: avg(prev5.map((r) => r.iso)),
    };
  }, [rows]);

  const disciplineSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_walks: avg(last5.map((r) => r.walks)),
      prev5_walks: avg(prev5.map((r) => r.walks)),
      last5_strikeouts: avg(last5.map((r) => r.strikeouts)),
      prev5_strikeouts: avg(prev5.map((r) => r.strikeouts)),
      last5_kbb: avg(last5.map((r) => r.kbb)),
      prev5_kbb: avg(prev5.map((r) => r.kbb)),
    };
  }, [rows]);

  const runningSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_sb: avg(last5.map((r) => r.stolen_bases)),
      prev5_sb: avg(prev5.map((r) => r.stolen_bases)),
      last5_lob: avg(last5.map((r) => r.left_on_base)),
      prev5_lob: avg(prev5.map((r) => r.left_on_base)),
      last5_margin: avg(last5.map((r) => r.margin)),
      prev5_margin: avg(prev5.map((r) => r.margin)),
    };
  }, [rows]);

  const scatterPower = useMemo(() => {
    const wins: any[] = [];
    const losses: any[] = [];
    for (const r of rows) {
      if (r.hits == null || r.pf == null) continue;
      const p = {
        x: r.hits,
        y: r.pf,
        label: `G#${r.idx} ${r.home_away === "home" ? "vs" : "@"} ${r.opponent} (${r.result ?? ""})`,
      };
      if (r.result === "W") wins.push(p);
      else losses.push(p);
    }
    return { wins, losses };
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
          Make sure you ran MLB ingest + backfill_team_game_stats.
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
      <section className={cardClass}>
        <div>
          <h2 className="text-base font-semibold">MLB In-Game Analytics</h2>
          <div className="mt-1 text-xs text-white/60">
            offense • slash line trends • discipline • power • baserunning
          </div>
        </div>

        <div className="mt-4 text-sm font-semibold">Top-Level Trend Snapshot</div>
        <PlotActions exportRef={overviewRef} chartId="mlb_ingame_overview" chartTitle={`${team} MLB In-Game Trend Snapshot`} sport="mlb" season={season} seasonType={seasonType} team={team} summary={offenseSummary} plotUrl={`/dashboard/mlb`} shareBody={`Sharing the ${team} MLB in-game trend snapshot.`} />
        <div className="mt-4 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                labelFormatter={(x) => `Game #${x}`}
              />
              <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Line type="monotone" dataKey={`runs_roll${roll}`} name={`Runs (roll${roll})`} dot={false} strokeWidth={2.5} />
              <Line type="monotone" dataKey="hits" name="Hits" dot={false} strokeWidth={2} opacity={0.85} />
              <Line type="monotone" dataKey="home_runs" name="HR" dot={false} strokeWidth={2} opacity={0.85} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {offenseSummary ? (
          <AIInsightsBox
            chartId="mlb_offense"
            sport="mlb"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={offenseSummary}
          />
        ) : null}
      </section>

      <section ref={offenseRef} className={cardClass}>
        <div className="text-sm font-semibold">Runs & Hit Production</div>
        <PlotActions exportRef={offenseRef} chartId="mlb_runs_hit_production" chartTitle={`${team} Runs & Hit Production`} sport="mlb" season={season} seasonType={seasonType} team={team} summary={offenseSummary} plotUrl={`/dashboard/mlb`} shareBody={`Sharing the ${team} runs and hit production chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Runs Per Game</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="pf" name="runs" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`runs_roll${roll}`} name={`runs (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Hits & Homers</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Bar dataKey="hits" name="hits" fill={INGAME_BAR_BLUE} />
                  <Bar dataKey="home_runs" name="home_runs" fill="rgba(96,165,250,0.58)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>

      <section ref={slashRef} className={cardClass}>
        <div className="text-sm font-semibold">Slash Line Trends</div>
        <PlotActions exportRef={slashRef} chartId="mlb_slash_line" chartTitle={`${team} Slash Line Trends`} sport="mlb" season={season} seasonType={seasonType} team={team} summary={slashSummary} plotUrl={`/dashboard/mlb`} shareBody={`Sharing the ${team} slash line chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">OBP / SLG / OPS</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis domain={["auto", "auto"]} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [Number(v).toFixed(3), name])}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="obp" name="obp" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="slg" name="slg" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="ops" name="ops" dot={false} strokeWidth={2.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">ISO</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis domain={["auto", "auto"]} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [Number(v).toFixed(3), name])}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="iso" name="iso" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`iso_roll${roll}`} name={`iso (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {slashSummary ? (
          <AIInsightsBox
            chartId="mlb_slash"
            sport="mlb"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={slashSummary}
          />
        ) : null}
      </section>

      <section ref={disciplineRef} className={cardClass}>
        <div className="text-sm font-semibold">Plate Discipline</div>
        <PlotActions exportRef={disciplineRef} chartId="mlb_plate_discipline" chartTitle={`${team} Plate Discipline`} sport="mlb" season={season} seasonType={seasonType} team={team} summary={disciplineSummary} plotUrl={`/dashboard/mlb`} shareBody={`Sharing the ${team} plate discipline chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Walks vs Strikeouts</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Bar dataKey="walks" name="walks" fill={INGAME_BAR_BLUE} />
                  <Bar dataKey="strikeouts" name="strikeouts" fill="rgba(96,165,250,0.58)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">K/BB Trend</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="kbb" name="kbb" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`kbb_roll${roll}`} name={`kbb (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {disciplineSummary ? (
          <AIInsightsBox
            chartId="mlb_discipline"
            sport="mlb"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={disciplineSummary}
          />
        ) : null}
      </section>

      <section ref={powerRef} className={cardClass}>
        <div className="text-sm font-semibold">Power & Pressure</div>
        <PlotActions exportRef={powerRef} chartId="mlb_power_pressure" chartTitle={`${team} Power & Pressure`} sport="mlb" season={season} seasonType={seasonType} team={team} summary={runningSummary} plotUrl={`/dashboard/mlb`} shareBody={`Sharing the ${team} power and pressure chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Hits vs Runs</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 18, right: 12, bottom: 10, left: -4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis type="number" dataKey="x" name="hits" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <YAxis type="number" dataKey="y" name="runs" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    formatter={(v: any, name: any) => [v, name]}
                    labelFormatter={(_, payload: any) => payload?.[0]?.payload?.label ?? ""}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Scatter name="Wins" data={scatterPower.wins} />
                  <Scatter name="Losses" data={scatterPower.losses} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Stolen Bases & Left on Base</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Bar dataKey="stolen_bases" name="stolen_bases" fill={INGAME_BAR_BLUE} />
                  <Bar dataKey="left_on_base" name="left_on_base" fill="rgba(96,165,250,0.58)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {runningSummary ? (
          <AIInsightsBox
            chartId="mlb_running"
            sport="mlb"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={runningSummary}
          />
        ) : null}
      </section>
    </>
  );
}
