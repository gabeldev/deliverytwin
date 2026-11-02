"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

// Staggered entrance for elements marked .rise. Content is visible without JS;
// the class .rise-ready is only added once the observer is running.
export default function Reveal() {
  const path = usePathname();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = document.documentElement;
    root.classList.add("rise-ready");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const el = e.target as HTMLElement;
          const group = el.parentElement ? Array.from(el.parentElement.querySelectorAll(":scope > .rise")) : [el];
          const i = Math.max(0, group.indexOf(el));
          el.style.transitionDelay = `${Math.min(i, 4) * 75}ms`;
          el.classList.add("in");
          io.unobserve(el);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    document.querySelectorAll(".rise:not(.in)").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [path]);
  return null;
}
