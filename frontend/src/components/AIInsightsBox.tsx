"use client";

import { useEffect, useMemo, useState } from "react";

type SummaryValue = string | number | boolean | null | SummaryObject | SummaryValue[];
type SummaryObject = { [key: string]: SummaryValue };

type Props = {
  chartId: string;
  sport: string;
  season: number;
  seasonType: string;
  team: string;
  summary: SummaryObject | null;
  tip?: string | null;
};

function stableStringify(obj: SummaryObject | null) {
  try {
    return JSON.stringify(obj ?? {});
  } catch {
    return "{}";
  }
}

function isEmptySummary(summary: SummaryObject | null): boolean {
  return !summary || Object.keys(summary).length === 0;
}

function autoTip(chartId: string): string {
  switch (chartId) {
    case "offense_defense":
      return "Bottom-right is ideal: higher points scored, lower points allowed.";
    case "rolling_averages":
      return "Focus on the roll-5 direction instead of one-game spikes.";
    case "standings":
      return "Compare win percentage to point differential to spot records that may be inflated.";
    case "scoring_timeseries":
      return "Big jumps often reflect pace or efficiency changes, so compare them to schedule difficulty.";
    case "recent_form":
      return "Last 5 versus previous 5 is the cleanest momentum check on this page.";
    case "home_away_splits":
      return "The largest home-away gap is often matchup-sensitive, especially in playoff-style settings.";
    case "margin_histogram":
      return "A wider spread means more volatility, while a tight cluster near zero suggests coin-flip games.";
    case "close_games":
      return "If most wins are close, short-term results can swing quickly.";
    case "sos":
      return "Use strength of schedule to add context before judging streaks too harshly.";
    case "score_distribution":
      return "Right-skewed scoring usually signals offense and pace; left-skewed scoring hints at defensive grind.";
    case "nfl_passing":
      return "Pass rate spikes often reflect game script, especially when a team is trailing.";
    case "nfl_qb_efficiency":
      return "If yards per attempt rise while sack rate falls, the trend is usually more sustainable.";
    case "nfl_pressure_mistakes":
      return "Sacks and turnovers are drive-killers, so watch their roll-5 trend first.";
    case "nfl_conversions":
      return "Third-down and red-zone efficiency are high-leverage areas where small changes flip outcomes fast.";
    case "nfl_relationships":
      return "High yards with low points usually hints at red-zone stalls or giveaways.";
    case "nba_shooting":
      return "Three-point percentage is volatile, so use eFG% and TS% for a steadier read.";
    case "nba_efficiency":
      return "When eFG% and TS% rise together, the scoring jump is usually more believable.";
    case "nba_ball_movement":
      return "Assist-to-turnover ratio is a clean signal for decision quality and shot creation.";
    case "nba_pace_offense":
      return "Separate pace from efficiency before explaining large scoring swings.";
    case "nhl_shot_volume":
      return "If shots stay steady but goals dip, finishing variance may be the story.";
    case "nhl_special_teams":
      return "Power-play swings matter fast, so compare power-play rate to penalty volume together.";
    case "nhl_puck_battle":
      return "Faceoffs, hits, and blocks often show whether a team is dictating the game.";
    case "nhl_possession_discipline":
      return "Giveaways plus penalties can erase strong even-strength play quickly.";
    case "nhl_overview":
      return "Use shots, faceoff percentage, power play, and shooting percentage together instead of one stat alone.";
    case "mlb_offense":
      return "Runs can lag hits over small samples, so compare both before judging the lineup.";
    case "mlb_slash":
      return "OPS and ISO help separate contact quality from real power output.";
    case "mlb_discipline":
      return "If walks are flat and strikeouts rise, the offense usually becomes more volatile.";
    case "mlb_running":
      return "Stolen bases and runners left on base together show whether aggression is actually creating runs.";
    default:
      return "Use rolling trends to judge direction, not noise.";
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
  const resolvedTip = (tip ?? "").trim() || autoTip(chartId);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        if (isEmptySummary(summary)) {
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

        const data = (await res.json().catch(() => ({}))) as { caption?: string; detail?: string };
        if (!res.ok) throw new Error(data.detail ?? "AI caption request failed");

        if (cancelled) return;
        setCaption(data.caption ?? "Not enough data yet.");
        setStatus("ready");
      } catch {
        if (cancelled) return;
        setCaption("Not enough data yet.");
        setStatus("error");
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [chartId, sport, season, seasonType, team, summary, summaryKey]);

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
