"use client";

import { motion, useMotionValue, useSpring } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

const TOS_ACCEPTANCE_KEY = "sportlytics.tos.accepted.v1";

const dataSources = [
  {
    title: "League data and game context",
    body:
      "SportLytics aggregates schedules, game results, standings context, and selected statistical fields from third-party sports data sources and public web endpoints used by the platform. Current integrations include ESPN-powered league/game endpoints for NFL, NBA, MLB, and NHL data, plus NFL-related standings/game references from NFL.com where applicable.",
  },
  {
    title: "News and content feeds",
    body:
      "News cards and content discovery may incorporate RSS or article metadata from publishers and feeds such as ESPN, Yahoo Sports, and CBS Sports. All article titles, publisher names, links, and external coverage remain the property of their respective owners.",
  },
  {
    title: "AI features",
    body:
      "Pulse, chart explanations, and other AI-assisted summaries may use OpenAI-powered language models to transform already-available platform data into readable insights. AI responses are generated content, may contain mistakes, and should be treated as informational assistance rather than guaranteed fact, official analysis, or professional advice.",
  },
  {
    title: "Community and user content",
    body:
      "Community posts, shared charts, comments, and other user submissions may include user-authored text, uploaded chart snapshots, or generated summaries. Users remain responsible for the content they submit or share through the platform.",
  },
];

const communityRules = [
  "Be respectful. No harassment, hate speech, discrimination, threats, bullying, or personal attacks.",
  "Keep discussions sports-focused, constructive, and safe for a broad audience.",
  "Do not spam, troll, flood chats, post repetitive content, or intentionally derail conversations.",
  "Avoid excessive profanity, abusive language, sexually explicit material, or violent/gory descriptions in community spaces.",
  "Do not impersonate athletes, teams, leagues, staff, brands, or other users.",
  "Do not post private, confidential, or personally identifying information about yourself or anyone else.",
  "Do not share unlawful, infringing, deceptive, malicious, or harmful content, including scams or malware links.",
  "Give proper context when sharing charts or claims. Do not intentionally misrepresent data, screenshots, or analysis.",
  "Use Pulse and AI features responsibly. Do not try to generate abusive, deceptive, or unsafe content through the platform.",
  "Moderation decisions may include content removal, access restrictions, or account-related action to protect the community and platform integrity.",
];

const featureCards = [
  {
    title: "League dashboards",
    text:
      "Explore NFL, NBA, MLB, and NHL pages with team-level insights, standings context, trend views, and recent performance summaries.",
  },
  {
    title: "Custom Builder",
    text:
      "Create your own chart combinations, compare teams, explore stat relationships, and download polished visuals for sharing.",
  },
  {
    title: "Pulse AI",
    text:
      "Ask sports questions in natural language and get structured, platform-aware answers grounded in SportLytics data and recent team trends.",
  },
  {
    title: "News and story discovery",
    text:
      "Browse sports coverage, publisher links, and article summaries in one place so you can move from data to context quickly.",
  },
  {
    title: "Community features",
    text:
      "Share takes, discuss trends, react to charts, and build a sports conversation layer around analytics and league storylines.",
  },
  {
    title: "Premium tools",
    text:
      "Unlock deeper charting, richer analysis workflows, and an expanded SportLytics experience designed for serious fans and power users.",
  },
];

const usageSteps = [
  "Start on the dashboard to see the latest platform activity, league coverage, and quick entry points into each sport.",
  "Open a league page to view team analytics, rolling trends, in-game breakdowns, and standings context.",
  "Use Custom Builder to compare teams, create plots, and generate downloadable visual breakdowns.",
  "Ask Pulse a sports question like recent movers, team comparisons, offense or defense trends, and contextual performance questions.",
  "Check news cards and linked stories to understand the real-world context behind spikes, slumps, and emerging narratives.",
  "Upgrade to premium when you want a more advanced research workflow and broader access across the app.",
];

const premiumItems = [
  "Expanded access to advanced dashboards and premium analytics surfaces",
  "Deeper chart generation and custom comparison workflows",
  "Enhanced AI-assisted analysis and premium experience touches",
  "A more powerful all-in-one workflow for dedicated fans, creators, and sports researchers",
];

const sourceCredits = [
  "ESPN for league data endpoints, schedules, standings references, game summaries, and article ecosystem integrations used across supported sports.",
  "NFL.com for selected NFL standings or reference context where applicable within the platform workflow.",
  "Yahoo Sports and CBS Sports for external news coverage and article feed discovery when surfaced through linked content workflows.",
  "OpenAI for AI-assisted product features such as Pulse and generated natural-language insights layered on top of platform data.",
];

function SectionHeading({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="max-w-3xl">
      <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-cyan-200/70">
        {eyebrow}
      </div>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-sm leading-7 text-white/72 sm:text-base">{body}</p>
    </div>
  );
}

export default function HeroLanding() {
  const router = useRouter();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 70, damping: 20 });
  const sy = useSpring(my, { stiffness: 70, damping: 20 });

  const [mounted, setMounted] = useState(false);
  const [tosOpen, setTosOpen] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreeCommunity, setAgreeCommunity] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 20;
      const y = (e.clientY / window.innerHeight - 0.5) * 16;
      mx.set(x);
      my.set(y);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mx, my]);

  useEffect(() => {
    if (!tosOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setTosOpen(false);
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [tosOpen]);

  const canContinue = useMemo(() => agreeTerms && agreeCommunity, [agreeTerms, agreeCommunity]);

  const handleEnter = () => {
    if (typeof window !== "undefined") {
      const accepted = window.localStorage.getItem(TOS_ACCEPTANCE_KEY);
      if (accepted === "true") {
        router.push("/dashboard");
        return;
      }
    }
    setTosOpen(true);
  };

  const handleAcceptAndContinue = () => {
    if (!canContinue) return;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOS_ACCEPTANCE_KEY, "true");
    }
    setTosOpen(false);
    router.push("/dashboard");
  };

  const modal = mounted && tosOpen
    ? createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-start justify-center overflow-y-auto bg-black/70 px-3 backdrop-blur-sm sm:items-center sm:px-4"
          style={{
            paddingTop: "max(0.75rem, env(safe-area-inset-top))",
            paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))",
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setTosOpen(false);
          }}
        >
          <div
            className="flex w-full max-w-5xl flex-col overflow-hidden rounded-[24px] border border-white/10 bg-[#09090d] shadow-[0_24px_90px_rgba(0,0,0,0.72)] sm:rounded-[30px]"
            style={{ maxHeight: "calc(100dvh - max(1.5rem, env(safe-area-inset-top) + env(safe-area-inset-bottom)))" }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="shrink-0 border-b border-white/10 bg-gradient-to-r from-cyan-500/10 via-fuchsia-500/10 to-transparent px-5 py-4 sm:px-8 sm:py-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.26em] text-cyan-200/70">
                    SportLytics access agreement
                  </div>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                    Terms of Service, Data Sources, and Community Guidelines
                  </h2>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-white/70 sm:text-[15px]">
                    Before entering the dashboard, please review and accept the current SportLytics platform terms. This notice explains how the platform uses third-party sports data, news feeds, and AI-generated features, along with the standards expected in community spaces.
                  </p>
                </div>
                <button
                  onClick={() => setTosOpen(false)}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
                >
                  Close
                </button>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-8 sm:py-6">
              <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
                <div className="space-y-6">
                  <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">1. Platform use and important disclaimers</h3>
                    <div className="mt-3 space-y-3 text-sm leading-7 text-white/72">
                      <p>
                        SportLytics is an analytics, visualization, community, and AI-assisted sports experience. By continuing, you acknowledge that platform content is provided for informational, educational, and entertainment purposes only.
                      </p>
                      <p>
                        SportLytics does not guarantee that every chart, article, feed item, score, advanced metric, AI-generated explanation, or community post is complete, current, error-free, uninterrupted, or suitable for any specific decision.
                      </p>
                      <p>
                        Nothing on SportLytics should be relied upon as legal, financial, betting, gambling, medical, or professional advice. You remain solely responsible for how you interpret and use platform content.
                      </p>
                    </div>
                  </section>

                  <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">2. Data sources, APIs, and attribution</h3>
                    <div className="mt-4 space-y-4 text-sm leading-7 text-white/72">
                      {dataSources.map((item) => (
                        <div key={item.title} className="rounded-2xl border border-white/8 bg-black/20 p-4">
                          <div className="font-semibold text-white/92">{item.title}</div>
                          <div className="mt-2">{item.body}</div>
                        </div>
                      ))}
                      <p>
                        Third-party names, logos, marks, headlines, league references, and source materials belong to their respective owners. SportLytics does not claim ownership of external league data, publisher content, or linked articles unless expressly stated.
                      </p>
                      <p>
                        Source availability, rate limits, format changes, licensing restrictions, endpoint updates, or provider outages may affect platform functionality, historical completeness, and freshness of displayed information.
                      </p>
                    </div>
                  </section>

                  <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">3. AI-generated insights and Pulse usage</h3>
                    <div className="mt-3 space-y-3 text-sm leading-7 text-white/72">
                      <p>
                        Pulse responses, chart captions, chart Q&amp;A, and other AI-assisted outputs may summarize trends, compare teams, or convert structured data into natural language. These outputs can be helpful, but they may occasionally be incomplete, stale, approximate, or incorrect.
                      </p>
                      <p>
                        By using AI features, you understand that generated text should be verified against the underlying chart, article, table, or source context before being relied upon or shared as fact.
                      </p>
                      <p>
                        You may not use SportLytics AI features to generate abusive, harassing, illegal, fraudulent, or misleading content, or to intentionally produce harmful prompts or community content.
                      </p>
                    </div>
                  </section>

                  <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">4. User content, sharing, and moderation</h3>
                    <div className="mt-3 space-y-3 text-sm leading-7 text-white/72">
                      <p>
                        If you share charts, write posts, reply in discussions, or interact in community features, you are responsible for the accuracy, tone, legality, and appropriateness of your submissions.
                      </p>
                      <p>
                        SportLytics may remove, restrict, review, or moderate content that appears abusive, deceptive, infringing, spammy, unsafe, or otherwise inconsistent with platform rules or community health.
                      </p>
                      <p>
                        Repeated or severe violations may lead to content removal, temporary restrictions, or loss of access to certain platform areas.
                      </p>
                    </div>
                  </section>
                </div>

                <div className="space-y-6">
                  <section className="rounded-[24px] border border-fuchsia-400/15 bg-fuchsia-500/[0.04] p-5">
                    <h3 className="text-lg font-semibold text-white">Community guidelines</h3>
                    <p className="mt-3 text-sm leading-7 text-white/72">
                      SportLytics is intended to be sharp, insightful, and competitive without becoming hostile. By joining community areas, you agree to uphold the following standards:
                    </p>
                    <ul className="mt-4 space-y-3 text-sm leading-6 text-white/78">
                      {communityRules.map((rule) => (
                        <li key={rule} className="flex gap-3 rounded-2xl border border-white/8 bg-black/20 p-3">
                          <span className="mt-[2px] h-2.5 w-2.5 shrink-0 rounded-full bg-fuchsia-300/80" />
                          <span>{rule}</span>
                        </li>
                      ))}
                    </ul>
                  </section>

                  <section className="rounded-[24px] border border-cyan-400/15 bg-cyan-500/[0.04] p-5">
                    <h3 className="text-lg font-semibold text-white">Privacy and account expectations</h3>
                    <div className="mt-3 space-y-3 text-sm leading-7 text-white/72">
                      <p>
                        Do not post sensitive personal data, private conversations, payment information, or anything you would not want publicly associated with your name or profile.
                      </p>
                      <p>
                        You are responsible for protecting your own device, browser session, and any account credentials associated with your access to SportLytics.
                      </p>
                      <p>
                        SportLytics may store preference, session, or acceptance state locally in your browser to improve usability, including remembering acceptance of this agreement.
                      </p>
                    </div>
                  </section>

                  <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">Acknowledgment</h3>
                    <div className="mt-4 space-y-4 text-sm text-white/80">
                      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                        <input
                          type="checkbox"
                          checked={agreeTerms}
                          onChange={(e) => setAgreeTerms(e.target.checked)}
                          className="mt-1 h-4 w-4 rounded border-white/20 bg-transparent accent-cyan-400"
                        />
                        <span className="leading-6">
                          I have reviewed and accept the SportLytics Terms of Service, platform disclaimers, AI-use notice, and source attribution information above.
                        </span>
                      </label>

                      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                        <input
                          type="checkbox"
                          checked={agreeCommunity}
                          onChange={(e) => setAgreeCommunity(e.target.checked)}
                          className="mt-1 h-4 w-4 rounded border-white/20 bg-transparent accent-fuchsia-400"
                        />
                        <span className="leading-6">
                          I agree to follow the SportLytics community guidelines, engage respectfully, avoid harassment or abusive language, and use shared spaces responsibly.
                        </span>
                      </label>
                    </div>
                  </section>
                </div>
              </div>
            </div>

            <div
              className="shrink-0 border-t border-white/10 bg-[#09090d]/95 px-5 pt-4 sm:px-8 sm:pt-5"
              style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-3xl text-xs leading-6 text-white/50">
                By selecting continue, you acknowledge this agreement and understand it may be updated as SportLytics features, data providers, community tools, and AI capabilities evolve.
              </p>
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
                <button
                  onClick={() => setTosOpen(false)}
                  className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white/70 transition hover:bg-white/10 hover:text-white sm:w-auto"
                >
                  Not now
                </button>
                <button
                  onClick={handleAcceptAndContinue}
                  disabled={!canContinue}
                  className="w-full rounded-full border border-cyan-400/30 bg-cyan-500/12 px-5 py-2.5 text-sm font-semibold text-cyan-50 transition hover:bg-cyan-500/18 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
                >
                  Agree and continue
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )
    : null;

  return (
    <>
      <main className="relative min-h-screen bg-black text-white">
        <div className="absolute top-0 left-0 right-0 h-16 opacity-80 z-[2]">
          <div className="absolute inset-0 bg-gradient-to-b from-white/15 via-cyan-400/15 to-transparent blur-xl" />
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent" />
        </div>

        <motion.div className="absolute inset-0 z-[0]" style={{ x: sx, y: sy }}>
          <motion.div
            className="absolute -top-32 -left-52 h-[600px] w-[800px] blur-2xl opacity-70"
            style={{
              background:
                "conic-gradient(from 200deg at 65% 35%, rgba(255,255,255,0.45), rgba(255,255,255,0) 65%)",
            }}
            animate={{ opacity: [0.5, 0.9, 0.6] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          />

          <motion.div
            className="absolute -top-32 -right-52 h-[600px] w-[800px] blur-2xl opacity-70"
            style={{
              background:
                "conic-gradient(from 340deg at 35% 35%, rgba(255,255,255,0.45), rgba(255,255,255,0) 65%)",
            }}
            animate={{ opacity: [0.5, 0.9, 0.6] }}
            transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut", delay: 0.4 }}
          />

          <motion.div
            className="absolute -bottom-52 left-[5%] h-[800px] w-[800px] rounded-full blur-3xl opacity-85 mix-blend-screen"
            style={{
              background:
                "radial-gradient(circle at 40% 40%, rgba(34,211,238,0.65), transparent 65%), radial-gradient(circle at 70% 60%, rgba(99,102,241,0.55), transparent 60%)",
            }}
            animate={{ x: [0, 200, -200, 0], y: [0, 120, -150, 0], rotate: [0, 15, -12, 0], scale: [1, 1.15, 0.95, 1] }}
            transition={{ duration: 6.5, repeat: Infinity, ease: "easeInOut" }}
          />

          <motion.div
            className="absolute top-0 right-[10%] h-[700px] w-[700px] rounded-full blur-3xl opacity-80 mix-blend-screen"
            style={{
              background:
                "radial-gradient(circle at 35% 30%, rgba(236,72,153,0.55), transparent 60%), radial-gradient(circle at 70% 70%, rgba(168,85,247,0.45), transparent 60%)",
            }}
            animate={{ x: [0, -180, 150, 0], y: [0, 140, -120, 0], rotate: [0, -15, 12, 0], scale: [1, 1.2, 0.95, 1] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          />

          <motion.div
            className="absolute -left-1/2 top-0 h-full w-1/2 opacity-40 blur-2xl"
            style={{
              background:
                "linear-gradient(120deg, rgba(255,255,255,0) 10%, rgba(255,255,255,0.35) 45%, rgba(255,255,255,0) 80%)",
              transform: "skewX(-15deg)",
            }}
            animate={{ x: ["-70%", "250%"] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", repeatDelay: 1 }}
          />
        </motion.div>

        <div className="absolute bottom-0 left-0 right-0 h-[380px] z-[1] pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(to top, rgba(25,150,70,0.95) 0%, rgba(15,85,45,0.65) 48%, rgba(0,0,0,0) 100%)",
            }}
          />

          <div
            className="absolute inset-0 opacity-[0.25]"
            style={{
              background:
                "repeating-linear-gradient(to top, rgba(255,255,255,0.08) 0px, rgba(255,255,255,0.08) 26px, transparent 26px, transparent 52px)",
              maskImage:
                "linear-gradient(to top, black 0%, black 72%, transparent 100%)",
            }}
          />

          <div
            className="absolute inset-0 opacity-[0.40]"
            style={{
              background:
                "repeating-linear-gradient(to right, rgba(255,255,255,0.28) 0px, rgba(255,255,255,0.28) 2px, transparent 2px, transparent 72px)",
              maskImage:
                "linear-gradient(to top, black 0%, black 72%, transparent 100%)",
            }}
          />

          <div
            className="absolute inset-0 opacity-[0.30]"
            style={{
              background:
                "repeating-linear-gradient(to right, transparent 0px, transparent 34px, rgba(255,255,255,0.22) 34px, rgba(255,255,255,0.22) 36px, transparent 36px, transparent 72px)",
              maskImage:
                "linear-gradient(to top, black 0%, black 64%, transparent 100%)",
            }}
          />

          <div className="absolute inset-0">
            <div className="absolute bottom-14 left-8 flex gap-8 select-none font-extrabold tracking-widest text-white/70">
              {["10", "20", "30", "40"].map((n) => (
                <span key={n} className="text-4xl drop-shadow-[0_0_18px_rgba(255,255,255,0.35)]">
                  {n}
                </span>
              ))}
            </div>

            <div className="absolute bottom-14 right-8 flex gap-8 select-none font-extrabold tracking-widest text-white/70">
              {["40", "30", "20", "10"].map((n) => (
                <span key={n} className="text-4xl drop-shadow-[0_0_18px_rgba(255,255,255,0.35)]">
                  {n}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="absolute inset-0 z-[1] bg-gradient-to-b from-black/10 via-black/35 to-black/45" />

        <div
          className="absolute inset-0 z-[2] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at center, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 100%)",
          }}
        />

        <section className="relative z-[3] flex min-h-screen items-center justify-center px-6">
          <div className="text-center">
            <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
              Sport<span className="text-white/90">Lytics</span>
            </h1>

            <p className="mt-4 text-base text-white/85 sm:text-lg md:text-xl">
              Where Data Meets Sports
            </p>

            <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-white/70 sm:text-base">
              A modern sports analytics platform for exploring league trends, asking smarter questions, building custom charts, following news, and turning raw numbers into readable insight.
            </p>

            <div className="mt-8 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={handleEnter}
                className="group inline-flex items-center justify-center rounded-full border border-white/20 bg-white/10 px-6 py-3 text-sm font-semibold backdrop-blur-md transition hover:border-white/40 hover:bg-white/20 active:scale-[0.99] sm:text-base"
              >
                <span className="mr-2">Get in the Game</span>
                <span className="inline-block transition-transform group-hover:translate-x-1">
                  →
                </span>
              </button>
              <a
                href="#about"
                className="inline-flex items-center justify-center rounded-full border border-white/12 bg-black/25 px-6 py-3 text-sm font-medium text-white/80 transition hover:border-white/25 hover:bg-white/8 hover:text-white sm:text-base"
              >
                Explore the platform
              </a>
            </div>

            <div className="mx-auto mt-8 h-[3px] w-32 rounded-full bg-white/30" />

            <div className="mt-10 animate-bounce text-xs uppercase tracking-[0.35em] text-white/45">
              Scroll to learn more
            </div>
          </div>
        </section>

        <section id="about" className="relative z-[3] border-t border-white/10 bg-[#05070c]/90 px-6 py-20 backdrop-blur-sm sm:py-24">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              eyebrow="About SportLytics"
              title="Built for fans who want more than box scores"
              body="SportLytics brings together league dashboards, custom charting, AI-assisted explanations, and story discovery into one sports research experience. The goal is to make it easier to move from a headline, to a chart, to a team trend, to a real answer without bouncing between disconnected tools."
            />

            <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {featureCards.map((card) => (
                <div key={card.title} className="rounded-[24px] border border-white/10 bg-white/[0.04] p-5 shadow-[0_14px_40px_rgba(0,0,0,0.22)]">
                  <div className="text-lg font-semibold text-white">{card.title}</div>
                  <p className="mt-3 text-sm leading-7 text-white/70">{card.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="relative z-[3] border-t border-white/10 bg-[#070b12] px-6 py-20 sm:py-24">
          <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
            <SectionHeading
              eyebrow="How to use"
              title="A simple flow from discovery to analysis"
              body="The app is designed so a casual user can browse quickly, while a more advanced user can dive into comparisons, trends, and structured sports analysis."
            />

            <div className="space-y-4">
              {usageSteps.map((step, index) => (
                <div key={step} className="flex gap-4 rounded-[24px] border border-white/10 bg-white/[0.04] p-5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-cyan-400/25 bg-cyan-500/10 text-sm font-semibold text-cyan-100">
                    {index + 1}
                  </div>
                  <p className="text-sm leading-7 text-white/75">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="relative z-[3] border-t border-white/10 bg-[#06080e] px-6 py-20 sm:py-24">
          <div className="mx-auto max-w-6xl">
            <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[28px] border border-fuchsia-400/18 bg-gradient-to-br from-fuchsia-500/[0.08] via-white/[0.03] to-cyan-500/[0.04] p-7 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
                <SectionHeading
                  eyebrow="Premium"
                  title="A more advanced layer for serious users"
                  body="SportLytics Premium is positioned as the higher-powered version of the platform for fans, analysts, and creators who want deeper tooling and a richer workflow."
                />
                <div className="mt-8 grid gap-3">
                  {premiumItems.map((item) => (
                    <div key={item} className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm leading-7 text-white/76">
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-7">
                <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-fuchsia-200/70">
                  Why it matters
                </div>
                <h3 className="mt-3 text-2xl font-semibold text-white">One platform, multiple workflows</h3>
                <p className="mt-4 text-sm leading-7 text-white/72">
                  Instead of using one site for standings, another for charts, another for stories, and another for opinions, SportLytics is built to connect those layers. Premium pushes that concept further by giving users a more complete analytics environment inside the same product.
                </p>
                <div className="mt-8 rounded-[24px] border border-white/10 bg-black/25 p-5">
                  <div className="text-sm font-semibold text-white">Ideal for</div>
                  <p className="mt-3 text-sm leading-7 text-white/70">
                    Power users, content creators, fantasy players, sports researchers, and fans who want cleaner workflows and better sports intelligence than a standard stats page can provide.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="relative z-[3] border-t border-white/10 bg-[#05070c] px-6 py-20 sm:py-24">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_1fr]">
            <div>
              <SectionHeading
                eyebrow="Sources"
                title="Built on credited external data and content"
                body="SportLytics depends on third-party league data, publisher content, and AI infrastructure. This section makes those dependencies clear and reinforces that external marks, data, and linked materials remain owned by their respective providers."
              />
              <div className="mt-8 space-y-4">
                {sourceCredits.map((item) => (
                  <div key={item} className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4 text-sm leading-7 text-white/72">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-gradient-to-b from-white/[0.05] to-white/[0.02] p-7">
              <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-cyan-200/70">
                Important note
              </div>
              <h3 className="mt-3 text-2xl font-semibold text-white">Data, news, and AI are all different layers</h3>
              <p className="mt-4 text-sm leading-7 text-white/72">
                Scores and statistics may refresh on different timelines than article feeds. AI-generated summaries may lag or simplify what the raw data shows. That is why SportLytics is strongest when users combine the charts, sources, and written explanations together.
              </p>
              <div className="mt-8 rounded-[24px] border border-cyan-400/15 bg-cyan-500/[0.05] p-5 text-sm leading-7 text-white/74">
                External source names such as ESPN, NFL.com, Yahoo Sports, and CBS Sports are used for attribution and credit. SportLytics is a separate product experience layered on top of sourced data and linked content.
              </div>
            </div>
          </div>
        </section>

        <section className="relative z-[3] border-t border-white/10 bg-[#04060a] px-6 py-20 sm:py-24">
          <div className="mx-auto max-w-6xl rounded-[30px] border border-white/10 bg-gradient-to-r from-cyan-500/[0.08] via-white/[0.03] to-fuchsia-500/[0.08] p-8 text-center shadow-[0_18px_60px_rgba(0,0,0,0.28)] sm:p-10">
            <div className="text-[11px] font-semibold uppercase tracking-[0.34em] text-white/55">
              Ready to explore
            </div>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Step into the full SportLytics experience
            </h2>
            <p className="mx-auto mt-4 max-w-3xl text-sm leading-7 text-white/72 sm:text-base">
              Browse the dashboards, compare teams, follow news, and use Pulse to ask smarter sports questions. When you are ready, continue into the app and start exploring.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleEnter}
                className="inline-flex items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-500/12 px-6 py-3 text-sm font-semibold text-cyan-50 transition hover:bg-cyan-500/18 sm:text-base"
              >
                Enter SportLytics
              </button>
              <a
                href="#about"
                className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/[0.04] px-6 py-3 text-sm font-medium text-white/78 transition hover:bg-white/[0.08] hover:text-white sm:text-base"
              >
                Back to overview
              </a>
            </div>
          </div>
        </section>
      </main>
      {modal}
    </>
  );
}
