"use client";

import { RefObject, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { toPng } from "html-to-image";

import { apiPost } from "@/lib/api";
import { getStoredUser, type AuthUser } from "@/lib/auth";

type PlotActionsProps = {
  exportRef: RefObject<HTMLElement | null>;
  chartId: string;
  chartTitle: string;
  sport: string;
  season: number;
  seasonType: string;
  team?: string | null;
  summary: Record<string, unknown> | null;
  plotUrl: string;
  shareBody?: string;
  className?: string;
};

type ChartQueryResp = {
  answer: string;
  route?: {
    chart_id?: string;
    chart_title?: string;
    query_type?: string;
  };
};

type SharedPlotPayload = {
  chart_id: string;
  chart_title: string;
  sport: string;
  season: number;
  season_type: string;
  team: string | null;
  summary: Record<string, unknown> | null;
  plot_url: string;
  image_data_url: string | null;
  shared_at: string;
};

const COMMUNITY_SHARE_KEY = "sportlytics.community.share";

export default function PlotActions({
  exportRef,
  chartId,
  chartTitle,
  sport,
  season,
  seasonType,
  team,
  summary,
  plotUrl,
  shareBody,
  className = "",
}: PlotActionsProps) {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string>("");
  const [askError, setAskError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setAuthUser(getStoredUser());
    const onStorage = () => setAuthUser(getStoredUser());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const disabled = !summary || Object.keys(summary).length === 0;
  const hasPremium = Boolean(authUser?.is_premium);
  const isSignedIn = Boolean(authUser);

  const defaultShareBody = useMemo(() => {
    return (
      shareBody ||
      `Sharing the ${chartTitle} plot from the ${sport.toUpperCase()} dashboard. What stands out most here?`
    );
  }, [chartTitle, shareBody, sport]);

  async function createSnapshot() {
    if (!exportRef.current) return null;
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve());
      });
    });
    return toPng(exportRef.current, {
      cacheBust: true,
      pixelRatio: 1.35,
      backgroundColor: "#050507",
      skipFonts: false,
      filter: (node) => {
        if (!(node instanceof HTMLElement)) return true;
        return node.dataset.exportIgnore !== "true";
      },
    });
  }

  async function handleDownload() {
    if (!exportRef.current) return;
    try {
      setDownloadStatus("Preparing PNG...");
      const dataUrl = await createSnapshot();
      if (!dataUrl) throw new Error("No plot snapshot available");
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = `sportlytics-${chartId}-${sport}-${team || "chart"}.png`;
      link.click();
      setDownloadStatus("Downloaded PNG");
      window.setTimeout(() => setDownloadStatus(null), 1600);
    } catch (err) {
      console.error("PNG export failed:", err);
      setDownloadStatus("PNG export failed");
      window.setTimeout(() => setDownloadStatus(null), 1800);
    }
  }

  function openPremiumPage() {
    window.location.assign("/dashboard/premium");
  }

  function openSignInPage() {
    window.location.assign(`/auth/sign-in?returnTo=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }

  function handleOpenPulse() {
    if (disabled) return;
    setAskError(null);
    setAnswer("");
    setQuestion("");
    setOpen(true);
  }

  async function handleAskPulse() {
    if (disabled || !question.trim()) return;
    if (!isSignedIn) {
      openSignInPage();
      return;
    }
    if (!hasPremium) {
      setAskError("Pulse chart analysis is part of Premium. Upgrade to unlock Ask Pulse on charts.");
      return;
    }
    try {
      setLoading(true);
      setAskError(null);
      setAnswer("");
      const res = await apiPost<ChartQueryResp>("/ai/chart-query", {
        chart_id: chartId,
        chart_title: chartTitle,
        sport,
        season,
        season_type: seasonType,
        team: team || null,
        summary,
        question,
        page_context: {
          plot_url: plotUrl,
          source: "plot-actions",
          has_team_filter: Boolean(team),
        },
      });
      setAnswer(res.answer || "Not enough data yet.");
    } catch (e: any) {
      const message = String(e?.message ?? "Pulse could not analyze this chart right now.");
      if (message.includes("401")) {
        openSignInPage();
        return;
      }
      if (message.includes("403") || message.toLowerCase().includes("premium")) {
        setAskError("Pulse chart analysis is part of Premium. Upgrade to unlock Ask Pulse on charts.");
        return;
      }
      setAskError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleShare() {
    try {
      setSharing(true);
      setShareStatus("Preparing shared plot...");
      let imageDataUrl: string | null = null;
      try {
        imageDataUrl = await createSnapshot();
      } catch (err) {
        console.warn("Shared plot snapshot failed; continuing without image.", err);
      }
      const payload: SharedPlotPayload = {
        chart_id: chartId,
        chart_title: chartTitle,
        sport,
        season,
        season_type: seasonType,
        team: team || null,
        summary: summary || null,
        plot_url: plotUrl,
        image_data_url: imageDataUrl,
        shared_at: new Date().toISOString(),
      };
      window.sessionStorage.setItem(
        COMMUNITY_SHARE_KEY,
        JSON.stringify({
          plot_title: chartTitle,
          plot_url: plotUrl,
          prefill_body: defaultShareBody,
          plot_payload: payload,
        })
      );
      window.location.assign("/dashboard/community?share=1");
    } catch (err) {
      console.error("Share to community failed:", err);
      setShareStatus("Share failed");
      window.setTimeout(() => setShareStatus(null), 1800);
      setSharing(false);
    }
  }

  const modal = open ? (
    <div
      data-export-ignore="true"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) setOpen(false);
      }}
    >
      <div
        className="w-full max-w-2xl rounded-[28px] border border-white/10 bg-[#09090d] p-5 shadow-[0_20px_70px_rgba(0,0,0,0.65)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-lg font-semibold tracking-tight">Ask Pulse about this plot</div>
            <div className="mt-1 text-sm text-white/60">
              {chartTitle} • {sport.toUpperCase()} {team ? `• ${team}` : ""}
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            Close
          </button>
        </div>

        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-white/60">
          Pulse will answer using the exact chart summary already on this page, not a generic sports prompt.
        </div>

        {!isSignedIn ? (
          <div className="mt-4 rounded-2xl border border-white/10 bg-black/25 p-4">
            <div className="text-sm font-semibold text-white">Sign in to use Ask Pulse</div>
            <div className="mt-1 text-sm text-white/60">
              Generated AI insights stay free, but interactive Pulse chat on charts requires an account and Premium access.
            </div>
            <button
              onClick={openSignInPage}
              className="mt-4 rounded-full border border-fuchsia-400/30 bg-fuchsia-500/10 px-4 py-2 text-sm font-semibold text-fuchsia-100 transition hover:bg-fuchsia-500/15"
            >
              Sign in
            </button>
          </div>
        ) : !hasPremium ? (
          <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-500/10 p-4">
            <div className="text-sm font-semibold text-amber-100">Premium required</div>
            <div className="mt-1 text-sm text-amber-100/80">
              Ask Pulse on charts is part of SportLytics Premium. Your generated AI insights remain available for free.
            </div>
            <button
              onClick={openPremiumPage}
              className="mt-4 rounded-full border border-amber-300/30 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-50 transition hover:bg-amber-400/15"
            >
              Upgrade to Premium
            </button>
          </div>
        ) : (
          <>
            <textarea
              autoFocus
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Example: What is the clearest trend here, and is it sustainable?"
              className="mt-4 h-28 w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-400/45"
            />

            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={handleAskPulse}
                disabled={loading || !question.trim() || disabled}
                className="rounded-full border border-cyan-400/25 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Analyzing..." : "Ask Pulse"}
              </button>
              {disabled ? <div className="text-xs text-white/50">Not enough chart data yet.</div> : null}
            </div>
          </>
        )}

        {askError ? (
          <div className="mt-4 rounded-2xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-100">{askError}</div>
        ) : null}

        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-white/45">Pulse response</div>
          <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-white/85">
            {answer || (hasPremium ? "Ask a chart-specific question to get an explanation grounded in this plot’s current summary." : "Upgrade to Premium to unlock chart-specific Pulse analysis.")}
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      <div data-export-ignore="true" className={`mt-4 flex flex-wrap items-center gap-2 ${className}`.trim()}>
        <button
          onClick={handleDownload}
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white/85 transition hover:bg-white/10"
        >
          Download
        </button>
        <button
          onClick={handleOpenPulse}
          disabled={disabled}
          title={!isSignedIn ? "Sign in to use Pulse" : !hasPremium ? "Premium required" : "Ask Pulse"}
          className={`rounded-full px-4 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
            hasPremium
              ? "border border-cyan-400/25 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/15"
              : "border border-amber-400/25 bg-amber-500/10 text-amber-100 hover:bg-amber-500/15"
          }`}
        >
          {hasPremium ? "Ask Pulse" : !isSignedIn ? "Sign in to ask" : "Pulse Premium"}
        </button>
        <button
          onClick={handleShare}
          disabled={sharing}
          className="rounded-full border border-fuchsia-400/25 bg-fuchsia-500/10 px-4 py-2 text-xs font-semibold text-fuchsia-100 transition hover:bg-fuchsia-500/15 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {sharing ? "Preparing Share..." : "Share to Community"}
        </button>
        {downloadStatus ? <div className="text-xs text-fuchsia-200">{downloadStatus}</div> : null}
        {shareStatus ? <div className="text-xs text-cyan-100">{shareStatus}</div> : null}
      </div>

      {mounted && modal ? createPortal(modal, document.body) : null}
    </>
  );
}
