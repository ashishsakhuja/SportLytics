"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import { getStoredUser, type AuthUser } from "@/lib/auth";
import PulseGeneratedPlotCard from "@/components/PulseGeneratedPlotCard";

type SportKey = "nfl" | "nba" | "mlb" | "nhl";

type TeamRow = {
  team_code: string;
  name: string;
  city: string | null;
  meta?: Record<string, unknown> | null;
};

type TeamsResp = {
  teams: TeamRow[];
};

type SupportingItem = {
  team_code: string;
  label: string;
  games: number;
  wins: number;
  losses: number;
  season_avg_pf: number | null;
  season_avg_pa: number | null;
  season_avg_margin: number | null;
  last5_avg_pf: number | null;
  last5_avg_pa: number | null;
  last5_avg_margin: number | null;
  prev5_avg_pf: number | null;
  prev5_avg_pa: number | null;
  prev5_avg_margin: number | null;
  offense_delta: number | null;
  defense_delta: number | null;
  margin_delta: number | null;
  recent_record: string;
};

type Storyline = {
  id: string;
  title: string;
  team_code: string;
  team_label: string;
  category: string;
  direction: string;
  caption: string;
  metric_value: number | null;
  support: Record<string, number | string | null>;
};

type StorylinesResp = {
  assistant_name: string;
  items: Storyline[];
};

type PulseGeneratedPlot = {
  chart_id: string;
  title: string;
  subtitle?: string | null;
  kind: "bar" | "line";
  data: Array<Record<string, string | number | null>>;
  series: Array<{ key: string; label: string }>;
  share_body?: string | null;
};

type ChatResp = {
  assistant_name: string;
  answer: string;
  supporting_items: SupportingItem[];
  storylines: Storyline[];
  session_id?: string | null;
  memory_used?: boolean;
  generated_plot?: PulseGeneratedPlot | null;
  prediction?: Record<string, unknown> | null;
  prediction_disclaimer?: string | null;
};

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
  supporting?: SupportingItem[];
  generatedPlot?: PulseGeneratedPlot | null;
  predictionDisclaimer?: string | null;
};

type SavedSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  sport: SportKey;
  season: string;
  seasonType: string;
  team: string;
  messages: ChatMessage[];
};

const SPORTS: Array<{ key: SportKey; label: string }> = [
  { key: "nfl", label: "NFL" },
  { key: "nba", label: "NBA" },
  { key: "mlb", label: "MLB" },
  { key: "nhl", label: "NHL" },
];

const SUGGESTED: Record<SportKey, string[]> = {
  nfl: [
    "Which NFL teams are trending up over the last 5 games?",
    "Compare BUF and BAL on recent offensive form.",
    "How do we think the Eagles will do in the near future?",
  ],
  nba: [
    "Which NBA teams have improved the most recently?",
    "Compare BOS and CLE on recent form.",
    "Predict how the Celtics might perform over the next few games.",
  ],
  mlb: [
    "Which MLB teams are gaining momentum lately?",
    "Compare LAD and ATL on recent run margin.",
    "Which MLB teams look most likely to keep scoring well going forward?",
  ],
  nhl: [
    "Which NHL teams are trending up recently?",
    "Compare NYR and CAR on recent goal margin.",
    "What do we think the Rangers will look like in the next game?",
  ],
};

const WELCOME_TEXT =
  "I’m Pulse, your SportLytics signal assistant. Ask about recent movers, team comparisons, offense, defense, or home-away splits.";
const STORAGE_KEY = "sportlytics.pulse.sessions.v1";
const MAX_SAVED_SESSIONS = 8;

function formatNum(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2);
}

function makeWelcomeMessage(): ChatMessage {
  return { id: "welcome", role: "assistant", text: WELCOME_TEXT };
}

function newSessionId() {
  return `pulse-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function buildSessionTitle(messages: ChatMessage[]) {
  const firstUser = messages.find((m) => m.role === "user" && m.text.trim());
  if (!firstUser) return "New Pulse chat";
  const clean = firstUser.text.trim();
  return clean.length > 46 ? `${clean.slice(0, 46)}…` : clean;
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string | number;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border border-white/10 bg-black/35 px-3 py-2.5 text-sm text-white outline-none transition focus:border-fuchsia-400/60"
    >
      {children}
    </select>
  );
}

export default function SignalCenterPage() {
  const router = useRouter();

  const [sport, setSport] = useState<SportKey>("nfl");
  const [season, setSeason] = useState("2025");
  const [seasonType, setSeasonType] = useState("REG");
  const [team, setTeam] = useState("all");

  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [storyLoading, setStoryLoading] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);

  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([makeWelcomeMessage()]);
  const [savedSessions, setSavedSessions] = useState<SavedSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>(newSessionId());
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setAuthUser(getStoredUser());
    const onStorage = () => setAuthUser(getStoredUser());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        setHydrated(true);
        return;
      }
      const parsed = JSON.parse(raw) as SavedSession[];
      if (!Array.isArray(parsed) || !parsed.length) {
        setHydrated(true);
        return;
      }
      const normalized = parsed.slice(0, MAX_SAVED_SESSIONS).map((item) => ({
        ...item,
        messages: Array.isArray(item.messages) && item.messages.length ? item.messages : [makeWelcomeMessage()],
      }));
      setSavedSessions(normalized);
      const latest = normalized[0];
      setCurrentSessionId(latest.id);
      setSport(latest.sport);
      setSeason(latest.season);
      setSeasonType(latest.seasonType);
      setTeam(latest.team);
      setMessages(latest.messages);
    } catch {
      // ignore broken local data
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    async function loadTeams() {
      try {
        const resp = await apiGet<TeamsResp>(`/analytics/teams?sport=${sport}`);
        setTeams(resp.teams ?? []);
      } catch {
        setTeams([]);
      }
    }
    loadTeams();
  }, [sport]);

  useEffect(() => {
    async function loadStorylines() {
      setStoryLoading(true);
      setStoryError(null);
      try {
        const qs = new URLSearchParams({
          sport,
          season,
          season_type: seasonType,
          limit: "6",
        });
        if (team !== "all") qs.set("team", team);
        const resp = await apiGet<StorylinesResp>(`/ai/storylines?${qs.toString()}`);
        setStorylines(resp.items ?? []);
      } catch (e: any) {
        setStoryError(e?.message ?? "Failed to load AI storylines.");
        setStorylines([]);
      } finally {
        setStoryLoading(false);
      }
    }
    loadStorylines();
  }, [sport, season, seasonType, team]);

  useEffect(() => {
    if (!hydrated) return;
    const safeMessages = messages.length ? messages : [makeWelcomeMessage()];
    const nextSession: SavedSession = {
      id: currentSessionId,
      title: buildSessionTitle(safeMessages),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      sport,
      season,
      seasonType,
      team,
      messages: safeMessages,
    };
    setSavedSessions((prev) => {
      const existing = prev.find((item) => item.id === currentSessionId);
      const createdAt = existing?.createdAt || nextSession.createdAt;
      const merged: SavedSession = { ...nextSession, createdAt, updatedAt: new Date().toISOString() };
      const ordered = [merged, ...prev.filter((item) => item.id !== currentSessionId)].slice(0, MAX_SAVED_SESSIONS);
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ordered));
      } catch {
        // ignore local storage failures
      }
      return ordered;
    });
  }, [currentSessionId, hydrated, messages, season, seasonType, sport, team]);

  const selectedTeamLabel = useMemo(() => {
    if (team === "all") return "League-wide";
    const match = teams.find((t) => t.team_code === team);
    return match ? `${match.city ? `${match.city} ` : ""}${match.name}` : team;
  }, [team, teams]);

  function promptSignIn() {
    router.push(`/auth/sign-in?returnTo=${encodeURIComponent("/dashboard/signal-center")}`);
  }

  function startNewChat() {
    setCurrentSessionId(newSessionId());
    setMessages([makeWelcomeMessage()]);
    setInput("");
    setChatError(null);
  }

  function openSavedSession(session: SavedSession) {
    setCurrentSessionId(session.id);
    setSport(session.sport);
    setSeason(session.season);
    setSeasonType(session.seasonType);
    setTeam(session.team);
    setMessages(session.messages?.length ? session.messages : [makeWelcomeMessage()]);
    setInput("");
    setChatError(null);
  }

  function deleteSavedSession(sessionId: string) {
    setSavedSessions((prev) => {
      const filtered = prev.filter((item) => item.id !== sessionId);
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
      } catch {}
      if (sessionId === currentSessionId) {
        if (filtered.length) {
          const next = filtered[0];
          setCurrentSessionId(next.id);
          setSport(next.sport);
          setSeason(next.season);
          setSeasonType(next.seasonType);
          setTeam(next.team);
          setMessages(next.messages?.length ? next.messages : [makeWelcomeMessage()]);
        } else {
          startNewChat();
        }
      }
      return filtered;
    });
  }

  async function submitQuestion(question: string) {
    const trimmed = question.trim();
    if (!trimmed) return;

    if (!authUser) {
      promptSignIn();
      return;
    }

    setChatError(null);
    setChatLoading(true);
    const nextUserMessage: ChatMessage = { id: `u-${Date.now()}`, role: "user", text: trimmed };
    const nextHistory = [...messages, nextUserMessage];
    setMessages(nextHistory);
    setInput("");

    try {
      const resp = await apiPost<ChatResp>("/ai/query", {
        sport,
        season: Number(season),
        season_type: seasonType,
        team: team === "all" ? null : team,
        question: trimmed,
        session_id: currentSessionId,
        history: nextHistory.slice(-8).map((msg) => ({ role: msg.role, text: msg.text })),
      });

      const assistantMessage: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: resp.answer,
        supporting: resp.supporting_items,
        generatedPlot: resp.generated_plot || null,
        predictionDisclaimer: resp.prediction_disclaimer || null,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      if (resp.storylines?.length) {
        setStorylines(resp.storylines);
      }
      if (resp.session_id && resp.session_id !== currentSessionId) {
        setCurrentSessionId(resp.session_id);
      }
    } catch (e: any) {
      const message = String(e?.message ?? "Failed to get an answer from Pulse.");
      if (message.includes("401") || message.toLowerCase().includes("sign in required")) {
        promptSignIn();
        return;
      }
      setChatError(message);
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-white/80 hover:text-white">
              ←
            </Link>
            <div>
              <div className="text-lg font-semibold tracking-tight">Signal Center</div>
              <div className="text-xs text-white/60">
                Pulse + AI storylines grounded in your SportLytics database
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/custom-builder"
              className="rounded-full border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-xs font-semibold text-fuchsia-100 transition hover:bg-fuchsia-500/15"
            >
              Custom Builder →
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-3xl border border-white/10 bg-white/5 p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-white">Pulse Command Deck</div>
                    <div className="mt-1 text-sm text-white/60">
                      Query trends, compare teams, and surface what matters right now.
                    </div>
                  </div>

                  <div className="grid w-full grid-cols-2 gap-3 xl:w-auto xl:grid-cols-4">
                    <div>
                      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Sport</div>
                      <Select value={sport} onChange={(v) => setSport(v as SportKey)}>
                        {SPORTS.map((item) => (
                          <option key={item.key} value={item.key}>{item.label}</option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Season</div>
                      <Select value={season} onChange={setSeason}>
                        {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map((yr) => (
                          <option key={yr} value={String(yr)}>{yr}</option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Type</div>
                      <Select value={seasonType} onChange={setSeasonType}>
                        <option value="REG">Regular Season</option>
                        <option value="POST">Postseason</option>
                      </Select>
                    </div>
                    <div>
                      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Scope</div>
                      <Select value={team} onChange={setTeam}>
                        <option value="all">League-wide</option>
                        {teams.map((t) => (
                          <option key={t.team_code} value={t.team_code}>
                            {t.city ? `${t.city} ${t.name}` : t.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                </div>

                {!authUser ? (
                  <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-cyan-400/20 bg-cyan-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-cyan-100">Sign in to use Pulse</div>
                      <div className="mt-1 text-sm text-cyan-50/80">
                        Signal Center storylines stay visible to everyone, but sending Pulse prompts now requires an account.
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={promptSignIn}
                      className="rounded-2xl border border-cyan-300/35 bg-cyan-500/15 px-4 py-2.5 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20"
                    >
                      Sign in to ask Pulse
                    </button>
                  </div>
                ) : (
                  <div className="mt-4 rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                    Signed in as <span className="font-semibold">{authUser.display_name}</span>. Pulse queries are unlocked.
                  </div>
                )}

                <div className="mt-4 flex flex-wrap gap-2">
                  {SUGGESTED[sport].map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => submitQuestion(prompt)}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/75 transition hover:bg-white/10 hover:text-white"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-3xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold">Ask Pulse</div>
                    <div className="text-sm text-white/60">
                      Grounded answers for {SPORTS.find((s) => s.key === sport)?.label} • {selectedTeamLabel}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                      DB-backed AI
                    </div>
                    <button
                      type="button"
                      onClick={startNewChat}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/75 transition hover:bg-white/10 hover:text-white"
                    >
                      New chat
                    </button>
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={msg.role === "assistant"
                        ? "rounded-2xl border border-fuchsia-400/20 bg-fuchsia-500/10 p-4"
                        : "ml-auto max-w-[85%] rounded-2xl border border-white/10 bg-white/5 p-4"}
                    >
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45">
                        {msg.role === "assistant" ? "Pulse" : "You"}
                      </div>
                      <div className="whitespace-pre-wrap text-sm leading-7 text-white/90">{msg.text}</div>

                      {msg.supporting?.length ? (
                        <div className="mt-3 grid grid-cols-1 gap-2 xl:grid-cols-2">
                          {msg.supporting.slice(0, 4).map((item) => (
                            <div key={`${msg.id}-${item.team_code}`} className="rounded-2xl border border-white/10 bg-black/25 p-3 text-xs text-white/75">
                              <div className="font-semibold text-white">{item.label}</div>
                              <div className="mt-2 flex flex-wrap gap-2">
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Recent record {item.recent_record}</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Margin Δ {formatNum(item.margin_delta)}</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Offense Δ {formatNum(item.offense_delta)}</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Defense Δ {formatNum(item.defense_delta)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      {msg.generatedPlot ? (
                        <PulseGeneratedPlotCard
                          plot={msg.generatedPlot}
                          sport={sport}
                          season={Number(season)}
                          seasonType={seasonType}
                          team={team === "all" ? null : team}
                        />
                      ) : null}

                      {msg.predictionDisclaimer ? (
                        <div className="mt-3 rounded-2xl border border-amber-400/20 bg-amber-500/10 p-3 text-xs leading-6 text-amber-100/90">
                          {msg.predictionDisclaimer}
                        </div>
                      ) : null}
                    </div>
                  ))}

                  {chatLoading ? (
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-white/60">
                      Pulse is analyzing the latest signals…
                    </div>
                  ) : null}
                </div>

                {chatError ? (
                  <div className="mt-4 rounded-2xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200">
                    {chatError}
                  </div>
                ) : null}

                <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                  <textarea
                    value={input}
                    onChange={(e) => {
                      if (!authUser) {
                        promptSignIn();
                        return;
                      }
                      setInput(e.target.value);
                    }}
                    onFocus={() => {
                      if (!authUser) promptSignIn();
                    }}
                    onClick={() => {
                      if (!authUser) promptSignIn();
                    }}
                    readOnly={!authUser}
                    placeholder={authUser ? "Ask Pulse about recent trends, offensive improvement, defense, comparisons, or location splits…" : "Sign in to start asking Pulse questions…"}
                    className="min-h-[96px] flex-1 rounded-2xl border border-white/10 bg-black/35 px-4 py-3 text-sm text-white outline-none focus:border-fuchsia-400/60"
                  />
                  <button
                    onClick={() => submitQuestion(input)}
                    disabled={chatLoading || (authUser ? !input.trim() : false)}
                    className="rounded-2xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-5 py-3 text-sm font-semibold text-fuchsia-100 transition hover:bg-fuchsia-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {authUser ? "Send to Pulse" : "Sign in to ask"}
                  </button>
                </div>
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-3xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold">Recent chats</div>
                    <div className="text-sm text-white/60">
                      Pulse remembers the current session, and the last {MAX_SAVED_SESSIONS} chats stay saved here.
                    </div>
                  </div>
                  <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-white/55">
                    Session memory
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {savedSessions.length === 0 ? (
                    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-white/60">
                      Your Pulse chats will start saving here after the first exchange.
                    </div>
                  ) : null}

                  {savedSessions.map((session) => {
                    const active = session.id === currentSessionId;
                    return (
                      <div key={session.id} className={`rounded-2xl border p-3 ${active ? "border-fuchsia-400/30 bg-fuchsia-500/10" : "border-white/10 bg-black/25"}`}>
                        <div className="flex items-start justify-between gap-3">
                          <button
                            type="button"
                            onClick={() => openSavedSession(session)}
                            className="flex-1 text-left"
                          >
                            <div className="text-sm font-semibold text-white">{session.title}</div>
                            <div className="mt-1 text-xs text-white/55">{session.sport.toUpperCase()} • {session.season} • {session.team === "all" ? "League-wide" : session.team}</div>
                            <div className="mt-2 text-xs text-white/45">{session.messages.length} messages saved</div>
                          </button>
                          <button
                            type="button"
                            onClick={() => deleteSavedSession(session.id)}
                            className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-white/55 transition hover:bg-white/10 hover:text-white"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            <section className="sl-plasma-card">
              <div className="sl-plasma-inner rounded-3xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold">AI Storylines</div>
                    <div className="text-sm text-white/60">
                      League signals generated from recent performance data.
                    </div>
                  </div>
                  <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-white/55">
                    {selectedTeamLabel}
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {storyLoading ? (
                    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-white/60">
                      Generating storylines…
                    </div>
                  ) : null}

                  {storyError ? (
                    <div className="rounded-2xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200">
                      {storyError}
                    </div>
                  ) : null}

                  {!storyLoading && !storyError && storylines.length === 0 ? (
                    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-white/60">
                      Not enough data yet.
                    </div>
                  ) : null}

                  {storylines.map((item) => (
                    <div key={item.id} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-white">{item.title}</div>
                          <div className="mt-1 text-xs uppercase tracking-[0.18em] text-white/45">
                            {item.team_code} • {item.category}
                          </div>
                        </div>
                        <div className="rounded-full border border-fuchsia-400/20 bg-fuchsia-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-fuchsia-200">
                          {item.direction}
                        </div>
                      </div>
                      <div className="mt-3 text-sm leading-6 text-white/80">{item.caption}</div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-white/60">
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Metric {formatNum(item.metric_value)}</span>
                        {item.support.last5_avg_margin != null ? (
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Last 5 margin {formatNum(Number(item.support.last5_avg_margin))}</span>
                        ) : null}
                        {item.support.recent_record ? (
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">Recent {String(item.support.recent_record)}</span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
