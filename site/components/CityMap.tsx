"use client";

import { useEffect, useRef, useState } from "react";
import type { Scenario, WorldOrder } from "@/lib/types";

type World = Scenario["world"];

const ZONE_TINT = ["rgba(42,120,214,0.07)", "rgba(201,80,26,0.07)", "rgba(18,135,92,0.08)"];
const LATE = "#d03b3b";
const ON_TIME = "#232323";

function lerp(a: number, b: number, k: number) { return a + (b - a) * k; }

// Manhattan path: x first, then y (couriers follow the grid streets).
function along(from: [number, number], to: [number, number], k: number): [number, number] {
  const dx = Math.abs(to[0] - from[0]), dy = Math.abs(to[1] - from[1]);
  const total = dx + dy || 1;
  const d = k * total;
  if (d <= dx) return [lerp(from[0], to[0], dx ? d / dx : 1), from[1]];
  return [to[0], lerp(from[1], to[1], dy ? (d - dx) / dy : 1)];
}

type Dot = { x: number; y: number; state: "waiting" | "to_rest" | "at_rest" | "to_cust"; late: boolean };

export function orderAt(o: WorldOrder, t: number, promise: number): Dot | null {
  if (t < o.created || o.rejected !== undefined) return null;
  const end = o.delivered ?? o.cancelled ?? Infinity;
  if (t >= end) return null;
  const late = t - o.created > promise;
  const r: [number, number] = [o.rx, o.ry];
  if (o.assigned === undefined || t < o.assigned) return { x: r[0], y: r[1], state: "waiting", late };
  if (o.at_rest !== undefined && t < o.at_rest && o.from) {
    const k = (t - o.assigned) / Math.max(o.at_rest - o.assigned, 1e-6);
    const [x, y] = along(o.from, r, k);
    return { x, y, state: "to_rest", late };
  }
  if (o.picked === undefined || t < o.picked) return { x: r[0], y: r[1], state: "at_rest", late };
  if (o.dest && o.delivered !== undefined) {
    const k = (t - o.picked) / Math.max(o.delivered - o.picked, 1e-6);
    const [x, y] = along(r, o.dest, Math.min(k, 1));
    return { x, y, state: "to_cust", late };
  }
  return { x: r[0], y: r[1], state: "at_rest", late };
}

export function statsAt(world: World, t: number, promise: number) {
  let active = 0, late = 0, waiting = 0, moving = 0;
  for (const o of world.orders) {
    const d = orderAt(o, t, promise);
    if (!d) continue;
    active++;
    if (d.late) late++;
    if (d.state === "waiting" || d.state === "at_rest") waiting++; else moving++;
  }
  return { active, late, waiting, moving };
}

export default function CityMap({
  world, promise, t, autoplay, range, speed = 6, onTime, label, highlight,
}: {
  world: World; promise: number; t?: number; autoplay?: boolean; range?: [number, number];
  speed?: number; onTime?: (t: number) => void; label: string; highlight?: string | null;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState(480);
  const tRef = useRef(t ?? range?.[0] ?? 0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setSize(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => { if (t !== undefined) tRef.current = t; }, [t]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width = size * dpr; c.height = size * dpr;
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const N = world.grid;
    const pad = 10;
    const cell = (size - pad * 2) / N;
    const X = (x: number) => pad + (x + 0.5) * cell;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0, last = performance.now(), lastReport = 0;

    const draw = (time: number) => {
      g.clearRect(0, 0, size, size);
      const zw = (size - pad * 2) / world.zones;
      for (let z = 0; z < world.zones; z++) {
        g.fillStyle = ZONE_TINT[z % 3];
        g.fillRect(pad + z * zw, pad, zw, size - pad * 2);
      }
      g.strokeStyle = "rgba(35,35,35,0.08)";
      g.lineWidth = 1;
      for (let i = 0; i < N; i++) {
        const p = X(i);
        g.beginPath(); g.moveTo(p, pad); g.lineTo(p, size - pad); g.stroke();
        g.beginPath(); g.moveTo(pad, p); g.lineTo(size - pad, p); g.stroke();
      }
      // restaurants: halo grows with orders waiting there; it turns orange when any of them is late
      const queue = new Map<string, number>();
      const lateQ = new Map<string, number>();
      const moving: Dot[] = [];
      for (const o of world.orders) {
        const d = orderAt(o, time, promise);
        if (!d) continue;
        if (d.state === "waiting" || d.state === "at_rest") {
          queue.set(o.r, (queue.get(o.r) ?? 0) + 1);
          if (d.late) lateQ.set(o.r, (lateQ.get(o.r) ?? 0) + 1);
        } else moving.push(d);
      }
      for (const r of world.restaurants) {
        const q = queue.get(r.token) ?? 0;
        const x = X(r.x), y = X(r.y);
        const s = Math.max(7, cell * 0.42);
        if (q > 0) {
          const lateShare = (lateQ.get(r.token) ?? 0) / q;
          g.fillStyle = lateShare > 0 ? `rgba(208,59,59,${0.1 + 0.25 * lateShare})` : "rgba(35,35,35,0.08)";
          const rr = s / 2 + Math.sqrt(q) * cell * 0.16;
          g.beginPath(); g.arc(x, y, rr, 0, Math.PI * 2); g.fill();
        }
        g.fillStyle = "#232323";
        g.fillRect(x - s / 2, y - s / 2, s, s);
        if (r.token === highlight) {
          g.strokeStyle = LATE; g.lineWidth = 2;
          g.strokeRect(x - s / 2 - 3, y - s / 2 - 3, s + 6, s + 6);
        }
      }
      for (const d of moving) {
        const r0 = Math.max(2.2, cell * 0.11);
        g.fillStyle = d.late ? LATE : ON_TIME;
        g.beginPath(); g.arc(X(d.x), X(d.y), r0, 0, Math.PI * 2); g.fill();
        if (d.late) { // shape cue as well as colour: late couriers carry an outer ring
          g.strokeStyle = LATE; g.lineWidth = 1.5;
          g.beginPath(); g.arc(X(d.x), X(d.y), r0 + 3, 0, Math.PI * 2); g.stroke();
        }
      }
    };

    const loop = (now: number) => {
      if (autoplay && range) {
        const dt = (now - last) / 1000;
        tRef.current += dt * speed;
        if (tRef.current > range[1]) tRef.current = range[0];
      }
      last = now;
      draw(tRef.current);
      if (onTime && now - lastReport > 120) { onTime(tRef.current); lastReport = now; }
      raf = requestAnimationFrame(loop);
    };
    if (reduced && autoplay && range) {
      tRef.current = range[1];
      draw(tRef.current);
      onTime?.(tRef.current);
    } else {
      raf = requestAnimationFrame(loop);
    }
    return () => cancelAnimationFrame(raf);
  }, [world, promise, autoplay, range, speed, size, onTime, highlight]);

  return (
    <div ref={box} style={{ width: "100%" }}>
      <canvas ref={ref} role="img" aria-label={label} style={{ width: size, height: size }} />
      {t !== undefined && (() => { const st = statsAt(world, t, promise); return (
        <p className="sr-only" aria-live="polite">{`t=${Math.round(t)}: ${st.active} active orders, ${st.late} late, ${st.waiting} waiting at restaurants, ${st.moving} on the road.`}</p>
      ); })()}
    </div>
  );
}
