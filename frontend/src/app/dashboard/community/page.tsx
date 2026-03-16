"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type Group = {
  id: number;
  name: string;
  description: string | null;
  sport: string | null;
  is_private: boolean;
  created_by: string;
  created_at: string | null;
  member_count: number;
  thread_count: number;
  is_member: boolean;
  latest_thread_title: string | null;
  latest_activity_at: string | null;
};

type Thread = {
  id: number;
  group_id: number;
  title: string;
  created_by: string;
  is_private: boolean;
  auto_source_kind: string | null;
  auto_source_key: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  latest_message_preview: string | null;
};

type Message = {
  id: number;
  thread_id: number;
  author: string;
  body: string;
  shared_plot_title: string | null;
  shared_plot_url: string | null;
  created_at: string | null;
};

type AutoSyncResponse = {
  ok: boolean;
  created_count: number;
  skipped_count: number;
  lookback_days: number;
  sports: string[];
};

function ago(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Math.max(0, Date.now() - d.getTime());
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const AUTO_SPORT_OPTIONS = ["all", "nfl", "nba", "mlb", "nhl"] as const;

export default function CommunityPage() {
  const searchParams = useSearchParams();
  const shareAppliedRef = useRef(false);
  const [viewer, setViewer] = useState("Ash");
  const [groups, setGroups] = useState<Group[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  const [groupName, setGroupName] = useState("");
  const [groupDescription, setGroupDescription] = useState("");
  const [groupSport, setGroupSport] = useState("Mixed");
  const [groupPrivate, setGroupPrivate] = useState(false);

  const [threadTitle, setThreadTitle] = useState("");
  const [threadBody, setThreadBody] = useState("");
  const [threadPlotTitle, setThreadPlotTitle] = useState("");
  const [threadPlotUrl, setThreadPlotUrl] = useState("");

  const [messageBody, setMessageBody] = useState("");
  const [messagePlotTitle, setMessagePlotTitle] = useState("");
  const [messagePlotUrl, setMessagePlotUrl] = useState("");

  const [autoSport, setAutoSport] = useState<(typeof AUTO_SPORT_OPTIONS)[number]>("all");
  const [lookbackDays, setLookbackDays] = useState(7);
  const [shareNote, setShareNote] = useState<string | null>(null);

  async function loadGroups(preferredGroupId?: number | null, preferredThreadId?: number | null) {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGet<{ items: Group[] }>(`/community/groups?viewer=${encodeURIComponent(viewer)}`);
      setGroups(res.items);
      const nextGroupId = preferredGroupId ?? res.items[0]?.id ?? null;
      setSelectedGroupId(nextGroupId);
      if (nextGroupId) {
        await loadThreads(nextGroupId, preferredThreadId);
      } else {
        setThreads([]);
        setMessages([]);
        setSelectedThreadId(null);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load community groups");
    } finally {
      setLoading(false);
    }
  }

  async function loadThreads(groupId: number, preferredThreadId?: number | null) {
    try {
      const res = await apiGet<{ group: Group; items: Thread[] }>(`/community/groups/${groupId}/threads?viewer=${encodeURIComponent(viewer)}`);
      setThreads(res.items);
      const nextThreadId = preferredThreadId ?? res.items[0]?.id ?? null;
      setSelectedThreadId(nextThreadId);
      if (nextThreadId) {
        await loadMessages(nextThreadId);
      } else {
        setMessages([]);
      }
    } catch (e: any) {
      setThreads([]);
      setMessages([]);
      setSelectedThreadId(null);
      setError(e?.message ?? "Failed to load threads");
    }
  }

  async function loadMessages(threadId: number) {
    try {
      const res = await apiGet<{ messages: Message[] }>(`/community/threads/${threadId}?viewer=${encodeURIComponent(viewer)}`);
      setMessages(res.messages);
    } catch (e: any) {
      setMessages([]);
      setError(e?.message ?? "Failed to load thread");
    }
  }

  useEffect(() => {
    loadGroups();
  }, [viewer]);

  useEffect(() => {
    if (shareAppliedRef.current) return;
    const hasShare = searchParams.get("share") === "1";
    if (!hasShare) return;

    const plotTitle = searchParams.get("plot_title") || "Shared SportLytics Plot";
    const plotUrl = searchParams.get("plot_url") || "/dashboard";
    const prefillBody = searchParams.get("prefill_body") || `Sharing ${plotTitle}.`;

    setThreadTitle((prev) => prev || `Discussion: ${plotTitle}`);
    setThreadBody((prev) => prev || prefillBody);
    setThreadPlotTitle((prev) => prev || plotTitle);
    setThreadPlotUrl((prev) => prev || plotUrl);
    setMessageBody((prev) => prev || prefillBody);
    setMessagePlotTitle((prev) => prev || plotTitle);
    setMessagePlotUrl((prev) => prev || plotUrl);
    setShareNote(`Imported ${plotTitle}. You can turn it into a new thread or post it into the currently selected thread.`);

    shareAppliedRef.current = true;
  }, [searchParams]);

  const selectedGroup = useMemo(
    () => groups.find((g) => g.id === selectedGroupId) ?? null,
    [groups, selectedGroupId]
  );

  const selectedThread = useMemo(
    () => threads.find((t) => t.id === selectedThreadId) ?? null,
    [threads, selectedThreadId]
  );

  async function createGroup() {
    if (!groupName.trim()) return;
    setBusy(true);
    setError(null);
    setSyncNote(null);
    try {
      const res = await apiPost<{ ok: boolean; group: Group }>("/community/groups", {
        name: groupName,
        description: groupDescription,
        sport: groupSport,
        is_private: groupPrivate,
        created_by: viewer,
      });
      setGroupName("");
      setGroupDescription("");
      setGroupSport("Mixed");
      setGroupPrivate(false);
      await loadGroups(res.group.id, null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create group");
    } finally {
      setBusy(false);
    }
  }

  async function joinGroup(groupId: number) {
    setBusy(true);
    setError(null);
    setSyncNote(null);
    try {
      await apiPost(`/community/groups/${groupId}/join`, { viewer });
      await loadGroups(groupId, selectedThreadId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to join group");
    } finally {
      setBusy(false);
    }
  }

  async function createThread() {
    if (!selectedGroupId || !threadTitle.trim() || !threadBody.trim()) return;
    setBusy(true);
    setError(null);
    setSyncNote(null);
    try {
      const res = await apiPost<{ ok: boolean; thread: Thread }>(`/community/groups/${selectedGroupId}/threads`, {
        title: threadTitle,
        body: threadBody,
        author: viewer,
        shared_plot_title: threadPlotTitle,
        shared_plot_url: threadPlotUrl,
        is_private: selectedGroup?.is_private ?? false,
      });
      setThreadTitle("");
      setThreadBody("");
      setThreadPlotTitle("");
      setThreadPlotUrl("");
      await loadGroups(selectedGroupId, res.thread.id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create thread");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage() {
    if (!selectedThreadId || !messageBody.trim()) return;
    setBusy(true);
    setError(null);
    setSyncNote(null);
    try {
      await apiPost(`/community/threads/${selectedThreadId}/messages`, {
        author: viewer,
        body: messageBody,
        shared_plot_title: messagePlotTitle,
        shared_plot_url: messagePlotUrl,
      });
      setMessageBody("");
      setMessagePlotTitle("");
      setMessagePlotUrl("");
      await loadMessages(selectedThreadId);
      if (selectedGroupId) await loadThreads(selectedGroupId, selectedThreadId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to send message");
    } finally {
      setBusy(false);
    }
  }

  async function syncPostgameThreads() {
    setBusy(true);
    setError(null);
    setSyncNote(null);
    try {
      const res = await apiPost<AutoSyncResponse>("/community/auto/postgames/sync", {
        viewer,
        sport: autoSport === "all" ? null : autoSport,
        lookback_days: lookbackDays,
        limit: 60,
      });
      setSyncNote(`Created ${res.created_count} postgame thread${res.created_count === 1 ? "" : "s"} and skipped ${res.skipped_count} existing one${res.skipped_count === 1 ? "" : "s"}.`);
      await loadGroups(selectedGroupId, selectedThreadId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to sync postgame threads");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-white/80 hover:text-white">←</Link>
            <div>
              <div className="text-lg font-semibold tracking-tight">Community</div>
              <div className="text-xs text-white/60">Public and private sports group discussions with plot sharing and auto postgame threads.</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={viewer}
              onChange={(e) => setViewer(e.target.value)}
              className="w-36 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
              placeholder="Display name"
            />
            <button
              onClick={() => loadGroups(selectedGroupId, selectedThreadId)}
              className="rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm hover:bg-white/15"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {error ? (
          <div className="mb-4 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">{error}</div>
        ) : null}
        {syncNote ? (
          <div className="mb-4 rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">{syncNote}</div>
        ) : null}
        {shareNote ? (
          <div className="mb-4 rounded-2xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-3 text-sm text-fuchsia-100">{shareNote}</div>
        ) : null}

        <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-base font-semibold">Auto-generate postgame debate threads</div>
              <div className="mt-1 text-sm text-white/65">
                Pull recent final games from SportLytics data and create one public discussion thread per game.
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={autoSport}
                onChange={(e) => setAutoSport(e.target.value as (typeof AUTO_SPORT_OPTIONS)[number])}
                className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none"
              >
                {AUTO_SPORT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option === "all" ? "All sports" : option.toUpperCase()}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                max={45}
                value={lookbackDays}
                onChange={(e) => setLookbackDays(Number(e.target.value) || 7)}
                className="w-24 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none"
              />
              <button
                onClick={syncPostgameThreads}
                disabled={busy}
                className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 hover:bg-cyan-500/15 disabled:opacity-60"
              >
                Sync Postgame Threads
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <section className="xl:col-span-3 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">Groups</h2>
              <span className="text-xs text-white/60">{groups.length} visible</span>
            </div>

            <div className="mt-4 space-y-3">
              {groups.map((group) => (
                <button
                  key={group.id}
                  onClick={() => {
                    setSelectedGroupId(group.id);
                    loadThreads(group.id);
                  }}
                  className={`w-full rounded-2xl border p-4 text-left transition ${selectedGroupId === group.id ? "border-cyan-400/40 bg-cyan-500/10" : "border-white/10 bg-black/30 hover:bg-black/40"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{group.name}</div>
                      <div className="mt-1 text-xs text-white/65">{group.description}</div>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[10px] ${group.is_private ? "border border-amber-400/30 bg-amber-500/10 text-amber-100" : "border border-emerald-400/30 bg-emerald-500/10 text-emerald-100"}`}>
                      {group.is_private ? "Private" : "Public"}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-white/60">
                    <span>{group.sport ?? "Mixed"}</span>
                    <span>• {group.member_count} members</span>
                    <span>• {group.thread_count} threads</span>
                    {group.latest_activity_at ? <span>• active {ago(group.latest_activity_at)}</span> : null}
                  </div>
                  {group.is_private && !group.is_member ? (
                    <div className="mt-3">
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/70">Join to view</span>
                    </div>
                  ) : null}
                </button>
              ))}
            </div>

            <div className="mt-6 border-t border-white/10 pt-5">
              <h3 className="text-sm font-semibold">Create group</h3>
              <div className="mt-3 space-y-3">
                <input value={groupName} onChange={(e) => setGroupName(e.target.value)} placeholder="Group name" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <input value={groupDescription} onChange={(e) => setGroupDescription(e.target.value)} placeholder="Description" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <input value={groupSport} onChange={(e) => setGroupSport(e.target.value)} placeholder="Sport" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <label className="flex items-center gap-2 text-sm text-white/75">
                  <input type="checkbox" checked={groupPrivate} onChange={(e) => setGroupPrivate(e.target.checked)} />
                  Private group
                </label>
                <button onClick={createGroup} disabled={busy} className="w-full rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 hover:bg-cyan-500/15 disabled:opacity-60">Create Group</button>
              </div>
            </div>
          </section>

          <section className="xl:col-span-3 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Threads</h2>
                <div className="text-xs text-white/60">{selectedGroup ? selectedGroup.name : "Select a group"}</div>
              </div>
              {selectedGroup?.is_private && !selectedGroup.is_member ? (
                <button onClick={() => joinGroup(selectedGroup.id)} disabled={busy} className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 hover:bg-amber-500/15 disabled:opacity-60">Join group</button>
              ) : null}
            </div>

            {selectedGroup?.is_private && !selectedGroup.is_member ? (
              <div className="mt-4 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-white/70">This is a private room. Join the group to view its threads and messages.</div>
            ) : (
              <>
                <div className="mt-4 space-y-3">
                  {threads.map((thread) => (
                    <button
                      key={thread.id}
                      onClick={() => {
                        setSelectedThreadId(thread.id);
                        loadMessages(thread.id);
                      }}
                      className={`w-full rounded-2xl border p-4 text-left transition ${selectedThreadId === thread.id ? "border-fuchsia-400/40 bg-fuchsia-500/10" : "border-white/10 bg-black/30 hover:bg-black/40"}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-sm font-semibold">{thread.title}</div>
                        {thread.auto_source_kind === "postgame" ? (
                          <span className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-100">Auto</span>
                        ) : null}
                      </div>
                      <div className="mt-2 text-xs text-white/60">by {thread.created_by} • {thread.message_count} messages • active {ago(thread.updated_at)}</div>
                      {thread.latest_message_preview ? <div className="mt-2 line-clamp-2 text-xs text-white/70">{thread.latest_message_preview}</div> : null}
                    </button>
                  ))}
                  {!loading && threads.length === 0 ? <div className="text-sm text-white/60">No threads yet.</div> : null}
                </div>

                <div className="mt-6 border-t border-white/10 pt-5">
                  <h3 className="text-sm font-semibold">Start a thread</h3>
                  <div className="mt-3 space-y-3">
                    <input value={threadTitle} onChange={(e) => setThreadTitle(e.target.value)} placeholder="Thread title" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                    <textarea value={threadBody} onChange={(e) => setThreadBody(e.target.value)} placeholder="Open the discussion…" rows={4} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                    <input value={threadPlotTitle} onChange={(e) => setThreadPlotTitle(e.target.value)} placeholder="Optional shared plot title" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                    <input value={threadPlotUrl} onChange={(e) => setThreadPlotUrl(e.target.value)} placeholder="Optional plot link e.g. /dashboard/nfl" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                    <button onClick={createThread} disabled={busy || !selectedGroup} className="w-full rounded-xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-sm font-medium text-fuchsia-100 hover:bg-fuchsia-500/15 disabled:opacity-60">Create Thread</button>
                  </div>
                </div>
              </>
            )}
          </section>

          <section className="xl:col-span-6 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">Discussion</h2>
                <div className="text-xs text-white/60">{selectedThread ? selectedThread.title : "Pick a thread"}</div>
              </div>
              {selectedGroup ? (
                <div className="text-xs text-white/60">{selectedGroup.name}</div>
              ) : null}
            </div>

            <div className="mt-4 space-y-3">
              {messages.map((msg) => (
                <div key={msg.id} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold">{msg.author}</div>
                    <div className="text-xs text-white/55">{ago(msg.created_at)}</div>
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-sm text-white/85">{msg.body}</div>
                  {msg.shared_plot_title && msg.shared_plot_url ? (
                    <Link href={msg.shared_plot_url} className="mt-3 inline-flex rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-500/15">
                      View Plot: {msg.shared_plot_title} ↗
                    </Link>
                  ) : null}
                </div>
              ))}
              {!loading && messages.length === 0 ? <div className="text-sm text-white/60">No messages yet.</div> : null}
            </div>

            <div className="mt-6 border-t border-white/10 pt-5">
              <h3 className="text-sm font-semibold">Reply</h3>
              <div className="mt-3 space-y-3">
                <textarea value={messageBody} onChange={(e) => setMessageBody(e.target.value)} placeholder="Drop your take, question, or plot breakdown…" rows={4} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <input value={messagePlotTitle} onChange={(e) => setMessagePlotTitle(e.target.value)} placeholder="Optional shared plot title" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <input value={messagePlotUrl} onChange={(e) => setMessagePlotUrl(e.target.value)} placeholder="Optional plot link e.g. /dashboard/nba" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-white/20" />
                <button onClick={sendMessage} disabled={busy || !selectedThread} className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 hover:bg-emerald-500/15 disabled:opacity-60">Send Message</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
