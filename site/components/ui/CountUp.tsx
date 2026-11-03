"use client";

import { useEffect, useRef, useState } from "react";

/** Counts up once when first scrolled into view. Server render and reduced motion show the final value. */
export default function CountUp({ value, locale, className }: { value: number; locale: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(value);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now(), dur = 1100;
      const tick = (now: number) => {
        const k = Math.min(1, (now - t0) / dur);
        setShown(Math.round(value * (1 - Math.pow(1 - k, 4)))); // ease-out quart
        if (k < 1) raf = requestAnimationFrame(tick);
      };
      setShown(0);
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.6 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [value]);
  const fmt = shown.toLocaleString(locale === "pt" ? "pt-BR" : "en-US");
  return (
    <span ref={ref} className={className}>
      <span aria-hidden="true">{fmt}</span>
      <span className="sr-only">{value.toLocaleString(locale === "pt" ? "pt-BR" : "en-US")}</span>
    </span>
  );
}
