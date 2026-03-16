"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Message = {
  id: string;
  author: string;
  text: string;
  createdAt: string;
  sharedPlotTitle?: string;
  sharedPlotUrl?: string;
};

type Thread = {
  id: string;
  title: string;
  createdBy: string;
  createdAt: string;
  visibility: "public" | "private";
  messages: Message[];
};

type Group = {
  id: string;
  name: string;
  description: string;
  isPrivate: boolean;
  members: number;
  sport: string;
  threads: Thread[];
};

type CommunityState = {
  groups: Group[];
};

const STORAGE_KEY = "sportlytics-community-v1";

function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function timeAgo(iso: string) {
  const d = new Date(iso);
  const diff = Math.max(0, Date.now() - d.getTime());
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function seedCommunity(): CommunityState {
  const now = Date.now();
  return {
    groups: [
      {
        id: "group-nfl",
        name: "NFL Film Room",
        description: "Share team trends, matchup plots, and weekly takes.",
        isPrivate: false,
        members: 182,
        sport: "NFL",
        threads: [
          {
            id: "thread-nfl-1",
            title: "Which offense is heating up fastest?",
            createdBy: "PulseFan21",
            createdAt: new Date(now - 1000 * 60 * 80).toISOString(),
            visibility: "public",
            messages: [
              {
                id: "msg-nfl-1",
                author: "PulseFan21",
                text: "I think Miami and Detroit are the biggest recent movers. Anyone have a plot comparing last 5 vs previous 5 offensive output?",
                createdAt: new Date(now - 1000 * 60 * 78).toISOString(),
              },
              {
                id: "msg-nfl-2",
                author: "GridironGraphs",
                text: "I shared a rolling points plot below. Detroit's consistency jumps out more than the raw ceiling.",
                createdAt: new Date(now - 1000 * 60 * 52).toISOString(),
                sharedPlotTitle: "Rolling Points For — DET last 10",
                sharedPlotUrl: "/dashboard/nfl",
              },
            ],
          },
        ],
      },
      {
        id: "group-nba",
        name: "NBA Shot Quality",
        description: "Discuss team form, shot profile changes, and playoff trends.",
        isPrivate: false,
        members: 126,
        sport: "NBA",
        threads: [
          {
            id: "thread-nba-1",
            title: "Best under-the-radar playoff riser",
            createdBy: "HoopsIntel",
            createdAt: new Date(now - 1000 * 60 * 220).toISOString(),
            visibility: "public",
            messages: [
              {
                id: "msg-nba-1",
                author: "HoopsIntel",
                text: "I'm watching teams whose defense has improved over the last 5 without the offense dropping off.",
                createdAt: new Date(now - 1000 * 60 * 215).toISOString(),
              },
            ],
          },
        ],
      },
      {
        id: "group-private-friends",
        name: "Friends Pick Circle",
        description: "Private room for your own sports discussion group.",
        isPrivate: true,
        members: 8,
        sport: "Mixed",
        threads: [
          {
            id: "thread-private-1",
            title: "Sunday locks",
            createdBy: "Ash",
            createdAt: new Date(now - 1000 * 60 * 35).toISOString(),
            visibility: "private",
            messages: [
              {
                id: "msg-private-1",
                author: "Ash",
                text: "Let's keep this room just for our personal slate notes and plot shares.",
                createdAt: new Date(now - 1000 * 60 * 33).toISOString(),
              },
            ],
          },
        ],
      },
    ],
  };
}

export default function CommunityPage() {
  const [community, setCommunity] = useState<CommunityState>({ groups: [] });
  const [ready, setReady] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<string>("group-nfl");
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>("thread-nfl-1");
  const [newMessage, setNewMessage] = useState("");
  const [author, setAuthor] = useState("You");
  const [plotTitle, setPlotTitle] = useState("");
  const [plotUrl, setPlotUrl] = useState("");
  const [newThreadTitle, setNewThreadTitle] = useState("");
  const [newThreadVisibility, setNewThreadVisibility] = useState<"public" | "private">("public");
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupDescription, setNewGroupDescription] = useState("");
  const [newGroupPrivate, setNewGroupPrivate] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as CommunityState) : seedCommunity();
      setCommunity(parsed);
      setSelectedGroupId(parsed.groups[0]?.id ?? "");
      setSelectedThreadId(parsed.groups[0]?.threads[0]?.id ?? null);
    } catch {
      const seeded = seedCommunity();
      setCommunity(seeded);
      setSelectedGroupId(seeded.groups[0]?.id ?? "");
      setSelectedThreadId(seeded.groups[0]?.threads[0]?.id ?? null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(community));
  }, [community, ready]);

  const groups = community.groups;
  const selectedGroup = useMemo(
    () => groups.find((g) => g.id === selectedGroupId) ?? groups[0] ?? null,
    [groups, selectedGroupId]
  );
  const selectedThread = useMemo(
    () => selectedGroup?.threads.find((t) => t.id === selectedThreadId) ?? selectedGroup?.threads[0] ?? null,
    [selectedGroup, selectedThreadId]
  );

  function updateGroups(updater: (prev: Group[]) => Group[]) {
    setCommunity((prev) => ({ ...prev, groups: updater(prev.groups) }));
  }

  function handleSelectGroup(groupId: string) {
    setSelectedGroupId(groupId);
    const group = groups.find((g) => g.id === groupId);
    setSelectedThreadId(group?.threads[0]?.id ?? null);
  }

  function createThread() {
    if (!selectedGroup || !newThreadTitle.trim()) return;
    const thread: Thread = {
      id: uid("thread"),
      title: newThreadTitle.trim(),
      createdBy: author.trim() || "You",
      createdAt: new Date().toISOString(),
      visibility: newThreadVisibility,
      messages: [
        {
          id: uid("msg"),
          author: author.trim() || "You",
          text: "Thread created. Start the discussion.",
          createdAt: new Date().toISOString(),
        },
      ],
    };

    updateGroups((prev) =>
      prev.map((group) =>
        group.id === selectedGroup.id
          ? { ...group, threads: [thread, ...group.threads] }
          : group
      )
    );
    setSelectedThreadId(thread.id);
    setNewThreadTitle("");
    setNewThreadVisibility(selectedGroup.isPrivate ? "private" : "public");
  }

  function createGroup() {
    if (!newGroupName.trim()) return;
    const group: Group = {
      id: uid("group"),
      name: newGroupName.trim(),
      description: newGroupDescription.trim() || "Custom community room.",
      isPrivate: newGroupPrivate,
      members: 1,
      sport: "Mixed",
      threads: [],
    };
    updateGroups((prev) => [group, ...prev]);
    setSelectedGroupId(group.id);
    setSelectedThreadId(null);
    setNewGroupName("");
    setNewGroupDescription("");
    setNewGroupPrivate(false);
  }

  function sendMessage() {
    if (!selectedGroup || !selectedThread || !newMessage.trim()) return;

    const message: Message = {
      id: uid("msg"),
      author: author.trim() || "You",
      text: newMessage.trim(),
      createdAt: new Date().toISOString(),
      sharedPlotTitle: plotTitle.trim() || undefined,
      sharedPlotUrl: plotUrl.trim() || undefined,
    };

    updateGroups((prev) =>
      prev.map((group) =>
        group.id !== selectedGroup.id
          ? group
          : {
              ...group,
              threads: group.threads.map((thread) =>
                thread.id !== selectedThread.id
                  ? thread
                  : {
                      ...thread,
                      messages: [...thread.messages, message],
                    }
              ),
            }
      )
    );

    setNewMessage("");
    setPlotTitle("");
    setPlotUrl("");
  }

  if (!ready) {
    return (
      <main className="min-h-screen bg-black px-6 py-8 text-white">
        <div className="mx-auto max-w-7xl text-white/70">Loading community…</div>
      </main>
    );
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
              <div className="text-lg font-semibold tracking-tight">Community</div>
              <div className="text-xs text-white/60">
                Group chats for sports takes, plot sharing, and private discussion rooms
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-white/70">
            <span className="rounded-full border border-emerald-400/25 bg-emerald-500/10 px-3 py-1 text-emerald-200">
              Frontend prototype
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
              local storage only
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex flex-wrap gap-2">
          <Link
            href="/dashboard"
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold hover:bg-white/10"
          >
            General Dashboard
          </Link>
          <Link
            href="/dashboard/custom-builder"
            className="rounded-full border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-xs font-semibold text-fuchsia-100 hover:bg-fuchsia-500/15"
          >
            Custom Builder
          </Link>
          <Link
            href="/dashboard/signal-center"
            className="rounded-full border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-xs font-semibold text-fuchsia-100 hover:bg-fuchsia-500/15"
          >
            Signal Center
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <section className="xl:col-span-3 sl-plasma-card">
            <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold">Groups</h2>
                <span className="text-xs text-white/60">iMessage-style rooms</span>
              </div>

              <div className="mt-4 space-y-3">
                {groups.map((group) => {
                  const active = group.id === selectedGroup?.id;
                  return (
                    <button
                      key={group.id}
                      onClick={() => handleSelectGroup(group.id)}
                      className={`w-full rounded-2xl border p-4 text-left transition ${
                        active
                          ? "border-sky-400/40 bg-sky-500/10"
                          : "border-white/10 bg-black/30 hover:bg-black/40"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="font-semibold">{group.name}</div>
                          <div className="mt-1 text-xs text-white/60">{group.description}</div>
                        </div>
                        <span
                          className={`rounded-full px-2 py-1 text-[11px] ${
                            group.isPrivate
                              ? "border border-amber-400/30 bg-amber-500/10 text-amber-200"
                              : "border border-emerald-400/30 bg-emerald-500/10 text-emerald-200"
                          }`}
                        >
                          {group.isPrivate ? "Private" : "Public"}
                        </span>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[11px] text-white/55">
                        <span>{group.sport}</span>
                        <span>{group.members} members</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4">
                <div className="text-sm font-semibold">Create group</div>
                <div className="mt-3 space-y-2">
                  <input
                    value={newGroupName}
                    onChange={(e) => setNewGroupName(e.target.value)}
                    placeholder="Group name"
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                  />
                  <textarea
                    value={newGroupDescription}
                    onChange={(e) => setNewGroupDescription(e.target.value)}
                    placeholder="What is this room for?"
                    rows={3}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                  />
                  <label className="flex items-center gap-2 text-xs text-white/70">
                    <input
                      type="checkbox"
                      checked={newGroupPrivate}
                      onChange={(e) => setNewGroupPrivate(e.target.checked)}
                    />
                    Make this group private
                  </label>
                  <button
                    onClick={createGroup}
                    className="w-full rounded-xl border border-sky-400/30 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-100 hover:bg-sky-500/15"
                  >
                    Create Group
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="xl:col-span-4 sl-plasma-card">
            <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Threads</h2>
                  <div className="text-xs text-white/60">
                    {selectedGroup ? `${selectedGroup.name} · ${selectedGroup.threads.length} threads` : "No group selected"}
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-2xl border border-white/10 bg-black/30 p-4">
                <div className="text-sm font-semibold">New thread</div>
                <div className="mt-3 space-y-2">
                  <input
                    value={newThreadTitle}
                    onChange={(e) => setNewThreadTitle(e.target.value)}
                    placeholder="Thread title"
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      value={author}
                      onChange={(e) => setAuthor(e.target.value)}
                      placeholder="Display name"
                      className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                    />
                    <select
                      value={newThreadVisibility}
                      onChange={(e) => setNewThreadVisibility(e.target.value as "public" | "private")}
                      className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                    >
                      <option value="public">Public</option>
                      <option value="private">Private</option>
                    </select>
                  </div>
                  <button
                    onClick={createThread}
                    disabled={!selectedGroup}
                    className="w-full rounded-xl border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-sm font-semibold text-fuchsia-100 hover:bg-fuchsia-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Create Thread
                  </button>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {selectedGroup?.threads.length ? (
                  selectedGroup.threads.map((thread) => {
                    const active = thread.id === selectedThread?.id;
                    const lastMessage = thread.messages[thread.messages.length - 1];
                    return (
                      <button
                        key={thread.id}
                        onClick={() => setSelectedThreadId(thread.id)}
                        className={`w-full rounded-2xl border p-4 text-left transition ${
                          active
                            ? "border-fuchsia-400/35 bg-fuchsia-500/10"
                            : "border-white/10 bg-black/30 hover:bg-black/40"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-semibold">{thread.title}</div>
                            <div className="mt-1 text-xs text-white/60">
                              Started by {thread.createdBy} · {timeAgo(thread.createdAt)}
                            </div>
                          </div>
                          <span className={`rounded-full px-2 py-1 text-[11px] ${thread.visibility === "private" ? "border border-amber-400/30 bg-amber-500/10 text-amber-200" : "border border-emerald-400/30 bg-emerald-500/10 text-emerald-200"}`}>
                            {thread.visibility}
                          </span>
                        </div>
                        <div className="mt-3 text-sm text-white/75 line-clamp-2">
                          {lastMessage?.text ?? "No messages yet."}
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-6 text-sm text-white/60">
                    No threads yet. Create the first discussion for this room.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="xl:col-span-5 sl-plasma-card">
            <div className="sl-plasma-inner rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Conversation</h2>
                  <div className="text-xs text-white/60">
                    {selectedThread ? `${selectedThread.title} · ${selectedThread.messages.length} messages` : "Select a thread to join the conversation"}
                  </div>
                </div>
              </div>

              <div className="mt-4 max-h-[560px] space-y-3 overflow-y-auto pr-1">
                {selectedThread ? (
                  selectedThread.messages.map((message) => (
                    <div key={message.id} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-semibold">{message.author}</div>
                        <div className="text-xs text-white/50">{timeAgo(message.createdAt)}</div>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-white/85">{message.text}</div>

                      {message.sharedPlotTitle || message.sharedPlotUrl ? (
                        <div className="mt-3 rounded-2xl border border-sky-400/25 bg-sky-500/10 p-4">
                          <div className="text-xs uppercase tracking-[0.2em] text-sky-200/80">Shared Plot</div>
                          <div className="mt-1 font-semibold text-sky-50">
                            {message.sharedPlotTitle || "Untitled plot"}
                          </div>
                          <div className="mt-1 text-xs text-sky-100/80 break-all">
                            {message.sharedPlotUrl || "No URL provided"}
                          </div>
                          {message.sharedPlotUrl ? (
                            <Link
                              href={message.sharedPlotUrl}
                              className="mt-3 inline-flex rounded-xl border border-sky-300/30 bg-white/10 px-3 py-2 text-xs font-semibold text-sky-50 hover:bg-white/15"
                            >
                              Open Plot →
                            </Link>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-6 text-sm text-white/60">
                    Pick a thread on the left to view messages.
                  </div>
                )}
              </div>

              <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-4">
                <div className="text-sm font-semibold">Send message</div>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input
                    value={plotTitle}
                    onChange={(e) => setPlotTitle(e.target.value)}
                    placeholder="Optional shared plot title"
                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                  />
                  <input
                    value={plotUrl}
                    onChange={(e) => setPlotUrl(e.target.value)}
                    placeholder="Optional plot URL (ex: /dashboard/nfl)"
                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                  />
                </div>
                <textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Drop your take, share a plot, or start a sports debate..."
                  rows={4}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/25"
                />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs text-white/50">
                    Public threads are visible to everyone in the community. Private rooms are meant for invite-only conversations.
                  </div>
                  <button
                    onClick={sendMessage}
                    disabled={!selectedThread || !newMessage.trim()}
                    className="rounded-xl border border-sky-400/30 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-100 hover:bg-sky-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
