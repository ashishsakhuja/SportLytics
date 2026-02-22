"use client";

import React from "react";

export default function Sparkline({
  values,
  height = 28,
}: {
  values: number[];
  height?: number;
}) {
  if (!values || values.length === 0) return null;

  const w = 180;
  const h = height;

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);

  const scaleX = (i: number) => (i / (values.length - 1)) * w;
  const scaleY = (v: number) => {
    // invert y
    const t = (v - min) / (max - min || 1);
    return h - t * h;
  };

  const d = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(2)} ${scaleY(v).toFixed(2)}`)
    .join(" ");

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" opacity="0.65" />
    </svg>
  );
}