"use client";

// Small SVG chart kit following the dataviz skill: thin marks, recessive axes, one axis,
// a legend for >= 2 series plus direct labels, a hover layer, and a table view.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import c from "./charts.module.css";

export type Series = { id: string; label: string; color: string; values: (number | null)[]; dashed?: boolean };

const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

// Measure the real width so the SVG is drawn 1:1 and its text never scales.
function useWidth(fallback: number) {
  const ref = useRef<HTMLElement | null>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(220, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function LineChart({
  x, series, height = 220, yMax, yFormat = pct, xFormat = (v) => `${Math.round(v)}`,
  markers = [], band, ariaLabel, xLabel, tableCaption,
}: {
  x: number[]; series: Series[]; height?: number; yMax?: number; yFormat?: (v: number) => string;
  xFormat?: (v: number) => string; markers?: { x: number; label: string }[]; band?: [number, number];
  ariaLabel: string; xLabel: string; tableCaption: string;
}) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useWidth(640);
  const H = height, m = { l: 44, r: 16, t: 14, b: 26 };
  const max = yMax ?? Math.max(0.0001, ...series.flatMap((s) => s.values.filter((v): v is number => v != null)));
  const xs = scaleLinear().domain([x[0], x[x.length - 1]]).range([m.l, W - m.r]);
  const ys = scaleLinear().domain([0, max]).nice(4).range([H - m.b, m.t]);
  const paths = useMemo(() => series.map((s) => {
    const gen = line<number | null>().defined((v) => v != null).x((_, i) => xs(x[i])).y((v) => ys(v as number));
    return gen(s.values) ?? "";
  }), [series, x, xs, ys]);
  const ticks = ys.ticks(4);
  const xticks = xs.ticks(Math.max(3, Math.min(8, Math.floor(W / 90))));
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * (W - m.l - m.r) + m.l;
    const xv = xs.invert(px);
    let best = 0;
    for (let i = 1; i < x.length; i++) if (Math.abs(x[i] - xv) < Math.abs(x[best] - xv)) best = i;
    setHover(best);
  };
  return (
    <figure className={c.fig} ref={box as React.RefObject<HTMLElement>}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className={c.svg} role="img" aria-labelledby={`${id}-t`}>
        <title id={`${id}-t`}>{ariaLabel}</title>
        {band && <rect x={xs(band[0])} y={m.t} width={Math.max(0, xs(band[1]) - xs(band[0]))} height={H - m.t - m.b} className={c.band} />}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={ys(t)} y2={ys(t)} className={c.grid} />
            <text x={m.l - 8} y={ys(t)} className={c.tickY}>{yFormat(t)}</text>
          </g>
        ))}
        {xticks.map((t) => <text key={t} x={xs(t)} y={H - 6} className={c.tickX}>{xFormat(t)}</text>)}
        {markers.map((mk) => (
          <g key={mk.label}>
            <line x1={xs(mk.x)} x2={xs(mk.x)} y1={m.t} y2={H - m.b} className={c.marker} />
            <text x={xs(mk.x) - 4} y={m.t + 10} className={c.markerText}>{mk.label}</text>
          </g>
        ))}
        {series.map((s, i) => (
          <path key={s.id} d={paths[i]} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? "5 4" : undefined} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {hover != null && (
          <g>
            <line x1={xs(x[hover])} x2={xs(x[hover])} y1={m.t} y2={H - m.b} className={c.cross} />
            {series.map((s) => s.values[hover] != null && (
              <circle key={s.id} cx={xs(x[hover])} cy={ys(s.values[hover] as number)} r={4.5} fill={s.color} stroke="#fff" strokeWidth={2} />
            ))}
          </g>
        )}
        <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      <p className={c.axisCap} aria-hidden="true">{xLabel}</p>
      {hover != null && (
        <div className={c.tip} style={{ left: `${(xs(x[hover]) / W) * 100}%` }} aria-hidden="true">
          <strong>{xLabel} {xFormat(x[hover])}</strong>
          {series.map((s) => (
            <span key={s.id}><i style={{ background: s.color }} />{s.label}: {s.values[hover] == null ? "–" : yFormat(s.values[hover] as number)}</span>
          ))}
        </div>
      )}
      {series.length > 1 && (
        <figcaption className={c.legend}>
          {series.map((s) => <span key={s.id}><i style={{ background: s.color }} data-dashed={s.dashed ? "1" : undefined} />{s.label}</span>)}
        </figcaption>
      )}
      <details className={c.table}>
        <summary>{tableCaption}</summary>
        <div className={c.tableScroll}>
          <table>
            <thead><tr><th scope="col">{xLabel}</th>{series.map((s) => <th scope="col" key={s.id}>{s.label}</th>)}</tr></thead>
            <tbody>
              {x.map((xv, i) => (
                <tr key={xv}><th scope="row">{xFormat(xv)}</th>{series.map((s) => <td key={s.id}>{s.values[i] == null ? "–" : yFormat(s.values[i] as number)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

export type EffectRow = { key: string; label: string; mean: number; lo: number; hi: number; note?: string; muted?: boolean };

// Paired differences: dot + 95% CI, zero line emphasised (DESIGN_SYSTEM §4). Never bars.
export function EffectPlot({
  rows, domain, selected, onSelect, format, ariaLabel, zeroLabel, betterLabel,
}: {
  rows: EffectRow[]; domain: [number, number]; selected?: string; onSelect?: (k: string) => void;
  format: (v: number) => string; ariaLabel: string; zeroLabel: string; betterLabel: string;
}) {
  const W = 360, rowH = 34;
  const xs = scaleLinear().domain(domain).range([8, W - 8]).clamp(true);
  return (
    <div className={c.effect} role="group" aria-label={ariaLabel}>
      <div className={c.effectHead}>
        <span />
        <span className={c.effectAxis}>
          <span style={{ left: `${(xs(0) / W) * 100}%` }}>{zeroLabel}</span>
          <span className={c.better}>← {betterLabel}</span>
        </span>
        <span />
      </div>
      {rows.map((r) => {
        const on = r.key === selected;
        const Tag = onSelect ? "button" : "div";
        return (
          <Tag key={r.key} type={onSelect ? "button" : undefined} className={c.effectRow} data-on={on ? "1" : undefined}
            data-muted={r.muted ? "1" : undefined} onClick={onSelect ? () => onSelect(r.key) : undefined}
            aria-pressed={onSelect ? on : undefined}>
            <span className={c.effectLabel}>{r.label}{r.note && <small>{r.note}</small>}</span>
            <svg viewBox={`0 0 ${W} ${rowH}`} className={c.effectSvg} aria-hidden="true">
              <line x1={xs(0)} x2={xs(0)} y1={0} y2={rowH} className={c.zero} />
              <line x1={xs(r.lo)} x2={xs(r.hi)} y1={rowH / 2} y2={rowH / 2} className={c.ci} />
              <line x1={xs(r.lo)} x2={xs(r.lo)} y1={rowH / 2 - 5} y2={rowH / 2 + 5} className={c.ci} />
              <line x1={xs(r.hi)} x2={xs(r.hi)} y1={rowH / 2 - 5} y2={rowH / 2 + 5} className={c.ci} />
              <circle cx={xs(r.mean)} cy={rowH / 2} r={5} className={c.dot} />
            </svg>
            <span className={`${c.effectVal} tnum`}>{format(r.mean)}<small>{format(r.lo)} to {format(r.hi)}</small></span>
          </Tag>
        );
      })}
    </div>
  );
}

// Accuracy with a 95% Wilson interval on a 0–1 scale (research results).
export function AccuracyRows({
  rows, ariaLabel, highlight,
}: { rows: { key: string; label: string; acc: number; ci: [number, number]; note?: string }[]; ariaLabel: string; highlight?: string }) {
  const W = 320;
  const xs = scaleLinear().domain([0, 1]).range([6, W - 6]);
  return (
    <div className={c.acc} role="table" aria-label={ariaLabel}>
      {rows.map((r) => (
        <div key={r.key} role="row" className={c.accRow} data-on={r.key === highlight ? "1" : undefined}>
          <span role="rowheader" className={c.effectLabel}>{r.label}{r.note && <small>{r.note}</small>}</span>
          <span role="cell" className={c.accPlot}>
            <svg viewBox={`0 0 ${W} 26`} aria-hidden="true">
              {[0, 0.5, 1].map((g) => <line key={g} x1={xs(g)} x2={xs(g)} y1={2} y2={24} className={c.grid} />)}
              <line x1={xs(r.ci[0])} x2={xs(r.ci[1])} y1={13} y2={13} className={c.ci} />
              <circle cx={xs(r.acc)} cy={13} r={5} className={c.dot} />
            </svg>
          </span>
          <span role="cell" className={`${c.effectVal} tnum`}>{r.acc.toFixed(2)}<small>{r.ci[0].toFixed(2)}–{r.ci[1].toFixed(2)}</small></span>
        </div>
      ))}
    </div>
  );
}
