"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  chartId: string;
  sport: string;
  season: number;
  seasonType: string;
  team: string;
  summary: any;
};

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

  // Make dependency stable even if callers pass a freshly-created object
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
      if (
        !summary ||
        (typeof summary === "object" && Object.keys(summary).length === 0)
      ) {
        setCaption("Not enough data yet.");
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE}/ai/chart-caption`,
          {
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
          }
        );

        const data = await res.json();
        const nextCaption =
          typeof data?.caption === "string" && data.caption.trim().length > 0
            ? data.caption
            : "Not enough data yet.";

        if (!cancelled) setCaption(nextCaption);
      } catch {
        if (!cancelled) setCaption("Not enough data yet.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchCaption();
    return () => {
      cancelled = true;
    };
  }, [chartId, sport, season, seasonType, team, summaryKey]);

  return (
    <div className="mt-2 text-xs text-white/60 italic">
      {loading ? "Generating insight..." : caption}
    </div>
  );
}