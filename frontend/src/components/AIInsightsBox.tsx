"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  chartId: string;
  sport: string;
  season: number;
  seasonType: string;
  team: string;
  summary: any;
  tip?: string | null;
};

function stableStringify(obj: any) {
  try {
    return JSON.stringify(obj ?? {});
  } catch {
    return "{}";
  }
}

function autoTip(chartId: string, summary: any): string {
  if (!summary || (typeof summary === "object" && Object.keys(summary).length === 0)) {
    return "Not enough data yet — add more games to sharpen the read.";
  }

  switch (chartId) {
    case "offense_defense":
      return "Bottom-right is ideal: higher points scored, lower points allowed.";
    case "rolling_averages":
      return "Focus on the roll-5 direction (up/down), not one-game spikes.";
    case "standings":
      return "Check your team’s win% vs point differential — it flags ‘lucky’ records.";
    case "scoring_timeseries":
      return "Big jumps usually mean pace/efficiency changes — compare to schedule strength.";
    case "recent_form":
      return "Compare last 5 vs previous 5 for momentum shifts.";
    case "home_away_splits":
      return "The biggest home-away margin gap is often matchup-sensitive — watch it in playoffs.";
    case "margin_histogram":
      return "Wider spread = volatility; tight near 0 = lots of coin-flip games.";
    case "close_games":
      return "If most wins are close, results can swing quickly week-to-week.";
    case "sos":
      return "Use SOS to contextualize streaks — tough runs can hide strong play.";
    case "score_distribution":
      return "Skewed right means frequent high totals (pace/offense); left means defensive grind.";

    case "nfl_passing":
      return "Pass rate spikes often reflect game script — check if you were trailing.";
    case "nfl_qb_efficiency":
      return "If YPA is up while sack rate is down, that’s usually sustainable.";
    case "nfl_pressure_mistakes":
      return "Sacks + turnovers are drive-killers — watch their roll-5 first.";
    case "nfl_conversions":
      return "3rd down and red zone are high leverage — small shifts flip outcomes fast.";
    case "nfl_relationships":
      return "High yards + low points usually means red zone stalls or turnovers.";

    case "nba_shooting":
      return "3P% is volatile; eFG% and TS% are better ‘true’ efficiency reads.";
    case "nba_efficiency":
      return "If eFG% and TS% rise together, it’s usually sustainable offense.";
    case "nba_ball_movement":
      return "AST/TOV is a clean proxy for decision quality and shot creation.";
    case "nba_pace_offense":
      return "Separate pace from efficiency to explain scoring swings.";

    case "nhl_shot_volume":
      return "If shots are steady but goals dip, finishing variance may be the story.";
    case "nhl_special_teams":
      return "Power-play swings matter fast — compare PP% and penalty minutes together.";
    case "nhl_puck_battle":
      return "Faceoffs, hits, and blocks often show whether the team is dictating the game.";
    case "nhl_possession_discipline":
      return "Giveaways plus penalties can erase strong even-strength play quickly.";
    case "nhl_overview":
      return "Use shots, FO%, PP%, and shooting% together — one stat alone can mislead.";

    default:
      return "Use the rolling lines to judge direction, not noise.";
  }
}

export default function AIInsightsBox({
  chartId,
  sport,
  season,
  seasonType,
  team,
  summary,
  tip,
}: Props) {
  const [caption, setCaption] = useState<string>("Generating insight...");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  const summaryKey = useMemo(() => stableStringify(summary), [summary]);
  const resolvedTip = (tip ?? "").trim() || autoTip(chartId, summary);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        if (!summary || (typeof summary === "object" && Object.keys(summary).length === 0)) {
          setCaption("Not enough data yet.");
          setStatus("ready");
          return;
        }

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
        if (!res.ok) throw new Error(data?.detail ?? "AI caption request failed");

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
  }, [chartId, sport, season, seasonType, team, summaryKey]);

  return (
    <div className="mt-5 sl-plasma-card">
      <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold tracking-tight">AI Insights</div>
          <div className="text-xs text-white/60">
            {status === "loading" ? "generating…" : "auto-generated"}
          </div>
        </div>

        <div className="mt-3 text-sm italic leading-relaxed text-white/75">{caption}</div>

        <div className="mt-3 text-xs text-white/60">
          <span className="font-semibold text-white/70">Tip:</span> {resolvedTip}
        </div>
      </div>
    </div>
  );
}