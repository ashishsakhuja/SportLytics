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
};

function isEmptySummary(summary: SummaryObject | null): boolean {
  return !summary || Object.keys(summary).length === 0;
}

export default function ChartCaption({
  chartId,
  sport,
  season,
  seasonType,
  team,
  summary,
}: Props) {
  const [caption, setCaption] = useState("Generating insight...");
  const [loading, setLoading] = useState(true);

  const summaryKey = useMemo(() => {
    try {
      return JSON.stringify(summary ?? {});
    } catch {
      return "{}";
    }
  }, [summary]);

  useEffect(() => {
    let cancelled = false;

    async function fetchCaption() {
      if (isEmptySummary(summary)) {
        setCaption("Not enough data yet.");
        setLoading(false);
        return;
      }

      const base = process.env.NEXT_PUBLIC_API_BASE;
      if (!base) {
        setCaption("Not enough data yet.");
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
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

        const data = (await res.json().catch(() => ({}))) as { caption?: string };
        const nextCaption =
          typeof data.caption === "string" && data.caption.trim().length > 0
            ? data.caption
            : "Not enough data yet.";

        if (!cancelled) setCaption(nextCaption);
      } catch {
        if (!cancelled) setCaption("Not enough data yet.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void fetchCaption();
    return () => {
      cancelled = true;
    };
  }, [chartId, sport, season, seasonType, team, summary, summaryKey]);

  return (
    <div className="mt-2 text-xs italic text-white/60">
      {loading ? "Generating insight..." : caption}
    </div>
  );
}
