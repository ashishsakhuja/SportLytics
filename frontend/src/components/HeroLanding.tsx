"use client";

import { motion, useMotionValue, useSpring } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";

export default function HeroLanding() {
  const mx = useMotionValue(0);
  const my = useMotionValue(0);

  const sx = useSpring(mx, { stiffness: 70, damping: 20 });
  const sy = useSpring(my, { stiffness: 70, damping: 20 });

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

  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      {/* Scoreboard Glow Strip */}
      <div className="absolute top-0 left-0 right-0 h-16 opacity-80 z-[2]">
        <div className="absolute inset-0 bg-gradient-to-b from-white/15 via-cyan-400/15 to-transparent blur-xl" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      </div>

      {/* Cinematic Motion Background */}
      <motion.div className="absolute inset-0 z-[0]" style={{ x: sx, y: sy }}>
        {/* Flood Lights */}
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
          transition={{
            duration: 4.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.4,
          }}
        />

        {/* Color Energy */}
        <motion.div
          className="absolute -bottom-52 left-[5%] h-[800px] w-[800px] rounded-full blur-3xl opacity-85 mix-blend-screen"
          style={{
            background:
              "radial-gradient(circle at 40% 40%, rgba(34,211,238,0.65), transparent 65%), radial-gradient(circle at 70% 60%, rgba(99,102,241,0.55), transparent 60%)",
          }}
          animate={{
            x: [0, 200, -200, 0],
            y: [0, 120, -150, 0],
            rotate: [0, 15, -12, 0],
            scale: [1, 1.15, 0.95, 1],
          }}
          transition={{ duration: 6.5, repeat: Infinity, ease: "easeInOut" }}
        />

        <motion.div
          className="absolute top-0 right-[10%] h-[700px] w-[700px] rounded-full blur-3xl opacity-80 mix-blend-screen"
          style={{
            background:
              "radial-gradient(circle at 35% 30%, rgba(236,72,153,0.55), transparent 60%), radial-gradient(circle at 70% 70%, rgba(168,85,247,0.45), transparent 60%)",
          }}
          animate={{
            x: [0, -180, 150, 0],
            y: [0, 140, -120, 0],
            rotate: [0, -15, 12, 0],
            scale: [1, 1.2, 0.95, 1],
          }}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.5,
          }}
        />

        {/* Light Sweep */}
        <motion.div
          className="absolute -left-1/2 top-0 h-full w-1/2 opacity-40 blur-2xl"
          style={{
            background:
              "linear-gradient(120deg, rgba(255,255,255,0) 10%, rgba(255,255,255,0.35) 45%, rgba(255,255,255,0) 80%)",
            transform: "skewX(-15deg)",
          }}
          animate={{ x: ["-70%", "250%"] }}
          transition={{
            duration: 5,
            repeat: Infinity,
            ease: "easeInOut",
            repeatDelay: 1,
          }}
        />
      </motion.div>

      {/* FIELD SECTION */}
      <div className="absolute bottom-0 left-0 right-0 h-[380px] z-[1] pointer-events-none">
        {/* Greener Turf Base */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(to top, rgba(25,150,70,0.95) 0%, rgba(15,85,45,0.65) 48%, rgba(0,0,0,0) 100%)",
          }}
        />

        {/* Mowing Stripes */}
        <div
          className="absolute inset-0 opacity-[0.25]"
          style={{
            background:
              "repeating-linear-gradient(to top, rgba(255,255,255,0.08) 0px, rgba(255,255,255,0.08) 26px, transparent 26px, transparent 52px)",
            maskImage:
              "linear-gradient(to top, black 0%, black 72%, transparent 100%)",
          }}
        />

        {/* Yard Lines */}
        <div
          className="absolute inset-0 opacity-[0.40]"
          style={{
            background:
              "repeating-linear-gradient(to right, rgba(255,255,255,0.28) 0px, rgba(255,255,255,0.28) 2px, transparent 2px, transparent 72px)",
            maskImage:
              "linear-gradient(to top, black 0%, black 72%, transparent 100%)",
          }}
        />

        {/* Hash Marks */}
        <div
          className="absolute inset-0 opacity-[0.30]"
          style={{
            background:
              "repeating-linear-gradient(to right, transparent 0px, transparent 34px, rgba(255,255,255,0.22) 34px, rgba(255,255,255,0.22) 36px, transparent 36px, transparent 72px)",
            maskImage:
              "linear-gradient(to top, black 0%, black 64%, transparent 100%)",
          }}
        />

        {/* Yard Numbers (Brighter) */}
        <div className="absolute inset-0">
          <div className="absolute bottom-14 left-8 flex gap-8 text-white/70 font-extrabold tracking-widest select-none">
            {["10", "20", "30", "40"].map((n) => (
              <span
                key={n}
                className="text-4xl drop-shadow-[0_0_18px_rgba(255,255,255,0.35)]"
              >
                {n}
              </span>
            ))}
          </div>

          <div className="absolute bottom-14 right-8 flex gap-8 text-white/70 font-extrabold tracking-widest select-none">
            {["40", "30", "20", "10"].map((n) => (
              <span
                key={n}
                className="text-4xl drop-shadow-[0_0_18px_rgba(255,255,255,0.35)]"
              >
                {n}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Overlay */}
      <div className="absolute inset-0 z-[1] bg-gradient-to-b from-black/10 via-black/35 to-black/45" />

      {/* Vignette */}
      <div
        className="absolute inset-0 z-[2] pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at center, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 100%)",
        }}
      />

      {/* Content */}
      <section className="relative z-[3] flex min-h-screen items-center justify-center px-6">
        <div className="text-center">
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-semibold tracking-tight">
            Sport<span className="text-white/90">Lytics</span>
          </h1>

          <p className="mt-4 text-base sm:text-lg md:text-xl text-white/85">
            Where data meets Sports
          </p>

          <div className="mt-8 flex items-center justify-center">
            <Link
              href="/dashboard"
              className="group inline-flex items-center justify-center rounded-full px-6 py-3 text-sm sm:text-base font-semibold bg-white/10 border border-white/20 backdrop-blur-md hover:bg-white/20 hover:border-white/40 active:scale-[0.99] transition"
            >
              <span className="mr-2">Get in the Game</span>
              <span className="inline-block transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>

          <div className="mx-auto mt-8 h-[3px] w-32 rounded-full bg-white/30" />
        </div>
      </section>
    </main>
  );
}