"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";

import { apiGet } from "@/lib/api";

type KeysResp = {
  sport: string;
  season: number;
  season_type: string;
  sampled_rows: number;
  keys: Array<{ key: string; count: number }>;
};

type TSRow = {
  idx: number;
  date: string | null;
  opponent: string;
  home_away: "home" | "away";
  result: "W" | "L" | "T" | null;
  value: number | null;
  cum_avg: number | null;
  [k: string]: any; // rollN
};

type TSResp = {
  sport: string;
  team: string;
  season: number;
  season_type: string;
  key: string;
  games: number;
  roll_window: number;
  avg: number | null;
  rows: TSRow[];
};

function prettyKey(key: string) {
  if (key.startsWith("raw:")) return key.replace("raw:", "raw • ");
  return key.replaceAll("_", " ");
}

export default function AdvancedStatTrend({
  sport,
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
  const [keys, setKeys] = useState<KeysResp | null>(null);
  const [selected, setSelected] = useState<string>("");

  const [ts, setTs] = useState<TSResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!sport) return;
      setErr(null);
      try {
        const data = await apiGet<KeysResp>(
          `/analytics/league/${sport}/advanced-stats/keys?season=${season}&season_type=${seasonType}&sample=4000`
        );
        if (cancelled) return;
        setKeys(data);

        const defaultBySport: Record<string, string> = {
          nfl: "total_yds",
          nba: "reb",
          mlb: "hits",
          nhl: "shots_for",
        };

        const all = data.keys.map((k) => k.key);
        const preferred =
          defaultBySport[sport] && all.includes(defaultBySport[sport])
            ? defaultBySport[sport]
            : all[0] || "";

        setSelected((prev) => (prev ? prev : preferred));
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load advanced stat keys.");
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [sport, season, seasonType]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!sport || !team || !selected) return;
      setLoading(true);
      setErr(null);
      try {
        const data = await apiGet<TSResp>(
          `/analytics/teams/${sport}/${team}/advanced-stats/timeseries?season=${season}&season_type=${seasonType}&key=${encodeURIComponent(
            selected
          )}&last=60&roll=5`
        );
        if (cancelled) return;
        setTs(data);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "Failed to load advanced stat series.");
        setTs(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [sport, team, season, seasonType, selected]);

  const rows = ts?.rows ?? [];
  const rollKey = ts ? `roll${ts.roll_window}` : "roll5";

  const selectClass =
    "rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none text-white/90 focus:border-white/25 focus:bg-white/10";

  const available = useMemo(() => keys?.keys ?? [], [keys]);

  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Advanced Stat Trend</h2>
          <div className="mt-1 text-xs text-white/60">
            Powered by stored boxscore/advanced stats (TeamGameStats)
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <select
            className={selectClass}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={!available.length}
            aria-label="Select stat"
          >
            {available.length === 0 ? (
              <option value="">No stats</option>
            ) : (
              available.slice(0, 200).map((k) => (
                <option key={k.key} value={k.key} className="text-black">
                  {prettyKey(k.key)}
                </option>
              ))
            )}
          </select>

          <div className="text-[11px] text-white/60">
            {ts?.avg != null ? `avg ${ts.avg}` : "avg n/a"}
          </div>
        </div>
      </div>

      <div className="mt-4 h-[280px]">
        {loading ? (
          <div className="text-sm text-white/60">Loading…</div>
        ) : err ? (
          <div className="text-sm text-red-300">{err}</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-white/60">No advanced stat data for this slice.</div>
        ) : (
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
                  background: "rgba(0,0,0,0.85)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  borderRadius: "12px",
                  color: "white",
                  fontSize: "12px",
                }}
                labelFormatter={(x) => `Game #${x}`}
                formatter={(v: any, name: any) => {
                  if (v == null) return ["n/a", name];
                  return [v, name];
                }}
              />
              <Legend wrapperStyle={{ color: "rgba(255,255,255,0.75)", fontSize: 12 }} />

              <Line
                type="monotone"
                dataKey="value"
                name={prettyKey(selected)}
                dot={false}
                strokeWidth={2.5}
              />
              <Line
                type="monotone"
                dataKey={rollKey}
                name={`rolling (${ts?.roll_window ?? 5})`}
                dot={false}
                strokeWidth={2}
                opacity={0.8}
              />
              <Line
                type="monotone"
                dataKey="cum_avg"
                name="cumulative avg"
                dot={false}
                strokeWidth={1.75}
                opacity={0.6}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-3 text-xs text-white/60">
        Tip: if a stat shows as empty, pick a different key — some ESPN fields are non-numeric strings.
      </div>
    </section>
  );
}