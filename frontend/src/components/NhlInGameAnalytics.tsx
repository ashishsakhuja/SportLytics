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

  shots: number | null;
  hits: number | null;
  blocked_shots: number | null;
  faceoff_pct: number | null;
  giveaways: number | null;
  takeaways: number | null;
  penalty_minutes: number | null;
  power_play_goals: number | null;
  power_play_opportunities: number | null;
  power_play_pct: number | null;
  shooting_pct: number | null;

  [k: string]: any;
};

type Resp = {
  sport: "nhl";
  team: string;
  season: number;
  season_type: string;
  games: number;
  roll_window: number;
  rows: Row[];
};

function pct100(v: number | null | undefined) {
  if (v == null) return "n/a";
  return `${Number(v).toFixed(1)}%`;
}

function avg(nums: Array<number | null | undefined>) {
  const clean = nums.filter((x) => typeof x === "number") as number[];
  if (clean.length === 0) return null;
  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

const INGAME_BAR_BLUE = "rgba(59,130,246,0.82)";

export default function NhlInGameAnalytics({
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
  const shotVolumeRef = useRef<HTMLElement | null>(null);
  const specialTeamsRef = useRef<HTMLElement | null>(null);
  const puckBattleRef = useRef<HTMLElement | null>(null);
  const possessionRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!team || !season) return;
      setLoading(true);
      setErr(null);
      try {
        const res = await apiGet<Resp>(
          `/analytics/nhl/teams/${team}/in-game/summary?season=${season}&season_type=${seasonType}&last=82&roll=5`
        );
        if (cancelled) return;
        setData(res);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load NHL in-game stats.");
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

  const overviewSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    return {
      games: rows.length,
      last5_shots: avg(last5.map((r) => r.shots)),
      last5_faceoff_pct: avg(last5.map((r) => r.faceoff_pct)),
      last5_pp_pct: avg(last5.map((r) => r.power_play_pct)),
      last5_shooting_pct: avg(last5.map((r) => r.shooting_pct)),
      last5_margin: avg(last5.map((r) => r.margin)),
    };
  }, [rows]);

  const shotVolumeSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_shots: avg(last5.map((r) => r.shots)),
      prev5_shots: avg(prev5.map((r) => r.shots)),
      last5_goals: avg(last5.map((r) => r.pf)),
      prev5_goals: avg(prev5.map((r) => r.pf)),
      last5_shooting_pct: avg(last5.map((r) => r.shooting_pct)),
      prev5_shooting_pct: avg(prev5.map((r) => r.shooting_pct)),
    };
  }, [rows]);

  const specialTeamsSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_pp_pct: avg(last5.map((r) => r.power_play_pct)),
      prev5_pp_pct: avg(prev5.map((r) => r.power_play_pct)),
      last5_pim: avg(last5.map((r) => r.penalty_minutes)),
      prev5_pim: avg(prev5.map((r) => r.penalty_minutes)),
      last5_margin: avg(last5.map((r) => r.margin)),
      prev5_margin: avg(prev5.map((r) => r.margin)),
    };
  }, [rows]);

  const puckBattleSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_faceoff_pct: avg(last5.map((r) => r.faceoff_pct)),
      prev5_faceoff_pct: avg(prev5.map((r) => r.faceoff_pct)),
      last5_hits: avg(last5.map((r) => r.hits)),
      prev5_hits: avg(prev5.map((r) => r.hits)),
      last5_blocks: avg(last5.map((r) => r.blocked_shots)),
      prev5_blocks: avg(prev5.map((r) => r.blocked_shots)),
    };
  }, [rows]);

  const possessionDisciplineSummary = useMemo(() => {
    if (!rows.length) return null;
    const last5 = rows.slice(-5);
    const prev5 = rows.slice(-10, -5);
    return {
      games: rows.length,
      last5_giveaways: avg(last5.map((r) => r.giveaways)),
      prev5_giveaways: avg(prev5.map((r) => r.giveaways)),
      last5_takeaways: avg(last5.map((r) => r.takeaways)),
      prev5_takeaways: avg(prev5.map((r) => r.takeaways)),
      last5_pim: avg(last5.map((r) => r.penalty_minutes)),
      prev5_pim: avg(prev5.map((r) => r.penalty_minutes)),
    };
  }, [rows]);

  const scatterShotsGoals = useMemo(() => {
    const wins: any[] = [];
    const losses: any[] = [];
    const ties: any[] = [];

    for (const r of rows) {
      if (r.shots == null || r.pf == null) continue;
      const p = {
        x: r.shots,
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
          Make sure you ran backfill_team_game_stats for NHL for this season.
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
      <section ref={overviewRef} className={cardClass}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">NHL In-Game Analytics</h2>
            <div className="mt-1 text-xs text-white/60">
              shots • special teams • puck battle metrics • rolling trends
            </div>
          </div>

          {overviewSummary ? (
            <div className="text-right text-[11px] leading-relaxed text-white/60">
              <div>{rows.length} games</div>
              <div>Last 5 Shots: {overviewSummary.last5_shots?.toFixed(1) ?? "n/a"}</div>
              <div>Last 5 FO%: {pct100(overviewSummary.last5_faceoff_pct)}</div>
              <div>Last 5 PP%: {pct100(overviewSummary.last5_pp_pct)}</div>
              <div>Last 5 Sh%: {pct100(overviewSummary.last5_shooting_pct)}</div>
            </div>
          ) : null}
        </div>

        <div className="mt-4 text-sm font-semibold">Top-Level Trend Snapshot</div>
        <PlotActions exportRef={overviewRef} chartId="nhl_ingame_overview" chartTitle={`${team} NHL In-Game Trend Snapshot`} sport="nhl" season={season} seasonType={seasonType} team={team} summary={overviewSummary} plotUrl={`/dashboard/nhl`} shareBody={`Sharing the ${team} NHL in-game trend snapshot.`} />
        <div className="mt-4 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                labelFormatter={(x) => `Game #${x}`}
                formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [Number(v).toFixed(1), name])}
              />
              <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
              <Line type="monotone" dataKey={`shots_roll${roll}`} name={`Shots (roll${roll})`} dot={false} strokeWidth={2.5} />
              <Line type="monotone" dataKey="faceoff_pct" name="FO%" dot={false} strokeWidth={2} opacity={0.85} />
              <Line type="monotone" dataKey="power_play_pct" name="PP%" dot={false} strokeWidth={2} opacity={0.85} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {overviewSummary ? (
          <AIInsightsBox
            chartId="nhl_overview"
            sport="nhl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={overviewSummary}
          />
        ) : null}
      </section>

      <section ref={shotVolumeRef} className={cardClass}>
        <div className="text-sm font-semibold">Shot Volume & Finishing</div>
        <PlotActions exportRef={shotVolumeRef} chartId="nhl_shot_volume_finishing" chartTitle={`${team} Shot Volume & Finishing`} sport="nhl" season={season} seasonType={seasonType} team={team} summary={shotVolumeSummary} plotUrl={`/dashboard/nhl`} shareBody={`Sharing the ${team} shot volume and finishing chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Shots Per Game</div>
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
                  <Line type="monotone" dataKey="shots" name="shots" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`shots_roll${roll}`} name={`shots (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Shooting %</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [`${Number(v).toFixed(1)}%`, name])}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="shooting_pct" name="shooting_pct" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`shooting_pct_roll${roll}`} name={`shooting_pct (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {shotVolumeSummary ? (
          <AIInsightsBox
            chartId="nhl_shot_volume"
            sport="nhl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={shotVolumeSummary}
          />
        ) : null}
      </section>

      <section ref={specialTeamsRef} className={cardClass}>
        <div className="text-sm font-semibold">Special Teams & Discipline</div>
        <PlotActions exportRef={specialTeamsRef} chartId="nhl_special_teams_discipline" chartTitle={`${team} Special Teams & Discipline`} sport="nhl" season={season} seasonType={seasonType} team={team} summary={specialTeamsSummary} plotUrl={`/dashboard/nhl`} shareBody={`Sharing the ${team} special teams and discipline chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Power Play %</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [`${Number(v).toFixed(1)}%`, name])}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="power_play_pct" name="power_play_pct" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`pp_pct_roll${roll}`} name={`power_play_pct (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Penalty Minutes</div>
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
                  <Bar dataKey="penalty_minutes" name="penalty_minutes" fill={INGAME_BAR_BLUE} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {specialTeamsSummary ? (
          <AIInsightsBox
            chartId="nhl_special_teams"
            sport="nhl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={specialTeamsSummary}
          />
        ) : null}
      </section>

      <section ref={puckBattleRef} className={cardClass}>
        <div className="text-sm font-semibold">Puck Battle Metrics</div>
        <PlotActions exportRef={puckBattleRef} chartId="nhl_puck_battles" chartTitle={`${team} Puck Battle Metrics`} sport="nhl" season={season} seasonType={seasonType} team={team} summary={puckBattleSummary} plotUrl={`/dashboard/nhl`} shareBody={`Sharing the ${team} puck battle metrics chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Faceoff %</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 18, right: 10, bottom: 10, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="idx" tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    labelFormatter={(x) => `Game #${x}`}
                    formatter={(v: any, name: any) => (v == null ? ["n/a", name] : [`${Number(v).toFixed(1)}%`, name])}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Line type="monotone" dataKey="faceoff_pct" name="faceoff_pct" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey={`faceoff_pct_roll${roll}`} name={`faceoff_pct (roll${roll})`} dot={false} strokeWidth={2} opacity={0.7} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Hits vs Blocked Shots</div>
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
                  <Bar dataKey="blocked_shots" name="blocked_shots" fill="rgba(96,165,250,0.58)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {puckBattleSummary ? (
          <AIInsightsBox
            chartId="nhl_puck_battle"
            sport="nhl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={puckBattleSummary}
          />
        ) : null}
      </section>

      <section ref={possessionRef} className={cardClass}>
        <div className="text-sm font-semibold">Possession & Turnovers</div>
        <PlotActions exportRef={possessionRef} chartId="nhl_possession_discipline" chartTitle={`${team} Possession & Turnovers`} sport="nhl" season={season} seasonType={seasonType} team={team} summary={possessionDisciplineSummary} plotUrl={`/dashboard/nhl`} shareBody={`Sharing the ${team} possession and turnovers chart.`} />
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Giveaways vs Takeaways</div>
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
                  <Line type="monotone" dataKey="giveaways" name="giveaways" dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="takeaways" name="takeaways" dot={false} strokeWidth={2.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="text-sm font-semibold">Shots vs Goals</div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 18, right: 12, bottom: 10, left: -4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name="shots"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name="goals"
                    tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 12 }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    contentStyle={{ background: "rgba(0,0,0,0.9)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, color: "white", fontSize: 12 }}
                    formatter={(v: any, name: any) => [v, name]}
                    labelFormatter={(_, payload: any) => payload?.[0]?.payload?.label ?? ""}
                  />
                  <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />
                  <Scatter name="Wins" data={scatterShotsGoals.wins} />
                  <Scatter name="Losses" data={scatterShotsGoals.losses} />
                  <Scatter name="Ties" data={scatterShotsGoals.ties} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {possessionDisciplineSummary ? (
          <AIInsightsBox
            chartId="nhl_possession_discipline"
            sport="nhl"
            season={season}
            seasonType={seasonType}
            team={team}
            summary={possessionDisciplineSummary}
          />
        ) : null}
      </section>
    </>
  );
}