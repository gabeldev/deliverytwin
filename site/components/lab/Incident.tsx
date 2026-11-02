"use client";

import { useCallback, useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";
import type { LabDict } from "@/lib/lab-i18n";
import type { Scenario } from "@/lib/types";
import { badRate } from "@/lib/series";
import CityMap, { statsAt } from "../CityMap";
import { LineChart } from "../charts";
import Status from "../ui/Status";
import l from "./lab.module.css";

const ZONES = ["var(--zone-0)", "var(--zone-1)", "var(--zone-2)"];
const GAUGES: Record<string, { en: string; pt: string }> = {
  couriers_online: { en: "Couriers online", pt: "Entregadores online" },
  couriers_idle: { en: "Couriers idle", pt: "Entregadores ociosos" },
  dispatch_queue: { en: "Dispatch queue", pt: "Fila do despachante" },
  orders_active: { en: "Orders in progress", pt: "Pedidos em andamento" },
  kitchen_load_max: { en: "Busiest kitchen load", pt: "Cozinha mais carregada" },
};

export default function Incident({ sc, t, locale }: { sc: Scenario; t: LabDict; locale: Locale }) {
  const end = sc.alert.t;
  const [time, setTime] = useState(end);
  const [playing, setPlaying] = useState(false);
  const promise = sc.telemetry.promise;

  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      setTime((v) => {
        const n = v + ((now - last) / 1000) * 10;
        if (n >= end) { setPlaying(false); return end; }
        return n;
      });
      last = now;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, end]);

  const toggle = useCallback(() => {
    setPlaying((p) => {
      if (!p && time >= end - 0.5) setTime(Math.max(0, end - 120));
      return !p;
    });
  }, [time, end]);

  const st = statsAt(sc.world, time, promise);
  const tel = sc.telemetry;
  const br = badRate(tel);
  const zoneIds = Object.keys(tel.zones);
  const agg = (arr: number[]) => { const out: number[] = []; for (let i = 0; i < arr.length; i += 3) out.push(arr.slice(i, i + 3).reduce((a, b) => a + b, 0)); return out; };
  const zx = br.x;
  const gaugeKeys = Object.keys(GAUGES).filter((k) => tel.gauges[k]?.length);

  return (
    <div className={l.split}>
      <section className={l.panel} aria-labelledby="map-h" data-ui>
        <div className={l.panelHead}>
          <h2 id="map-h" className={l.h2}>{t.mapTitle}</h2>
          <Status kind="assumption" locale={locale} label={locale === "pt" ? "Visão do simulador" : "Simulator view"} />
        </div>
        <p className={l.note}>{t.mapNote}</p>
        <CityMap world={sc.world} promise={promise} t={time} label={`${t.mapTitle}, ${t.minute} ${Math.round(time)}`} />
        <div className={l.scrub}>
          <button type="button" className="btn btn-dark" onClick={toggle} aria-pressed={playing}>{playing ? t.pause : t.play}</button>
          <label className={l.range}>
            <span className="sr-only">{t.minute}</span>
            <input type="range" min={0} max={end} step={1} value={Math.round(time)} onChange={(e) => { setPlaying(false); setTime(Number(e.target.value)); }} />
          </label>
          <span className="tnum">{t.minute} {Math.round(time)}</span>
        </div>
        <dl className={l.kpis}>
          <div><dt>{t.active}</dt><dd className="tnum">{st.active}</dd></div>
          <div><dt>{t.late}</dt><dd className={`tnum ${l.late}`}>{st.late}</dd></div>
          <div><dt>{t.waiting}</dt><dd className="tnum">{st.waiting}</dd></div>
          <div><dt>{t.moving}</dt><dd className="tnum">{st.moving}</dd></div>
        </dl>
      </section>

      <section className={l.panel} aria-labelledby="obs-h" data-ui>
        <div className={l.panelHead}>
          <h2 id="obs-h" className={l.h2}>{t.observedTitle}</h2>
          <Status kind="observation" locale={locale} />
        </div>
        <h3 className={l.h3}>{t.badRate}</h3>
        <LineChart x={br.x} series={[{ id: "bad", label: t.badRate, color: "var(--series-control)", values: br.y }]} yMax={1} height={200}
          markers={[{ x: end, label: locale === "pt" ? "alerta" : "alert" }]} xLabel="min" ariaLabel={t.badRate} tableCaption={locale === "pt" ? "Ver dados" : "Show data"} />
        <h3 className={l.h3}>{t.byZone}</h3>
        <LineChart x={zx} height={180} yFormat={(v) => `${Math.round(v)}`} xLabel="min" ariaLabel={t.byZone} tableCaption={locale === "pt" ? "Ver dados" : "Show data"}
          series={zoneIds.map((z, i) => ({ id: z, label: z, color: ZONES[i % 3], values: agg(tel.zones[z].created) }))} />
        <h3 className={l.h3}>{t.gauges}</h3>
        {gaugeKeys.length === 0 ? <p className={l.callout}>{t.noGauges}</p> : (
          <div className={l.multiples}>
            {gaugeKeys.map((k) => {
              const pts = tel.gauges[k];
              const step = Math.max(1, Math.floor(pts.length / 60));
              const sel = pts.filter((_, i) => i % step === 0);
              return (
                <div key={k}>
                  <p className={l.mini}>{GAUGES[k][locale]}</p>
                  <LineChart x={sel.map((p) => p[0])} height={120} yFormat={(v) => (v < 2 ? v.toFixed(1) : `${Math.round(v)}`)} xLabel="min" ariaLabel={GAUGES[k][locale]}
                    tableCaption={locale === "pt" ? "Ver dados" : "Show data"} markers={[{ x: end, label: "" }]}
                    series={[{ id: k, label: GAUGES[k][locale], color: "var(--series-control)", values: sel.map((p) => p[1]) }]} />
                </div>
              );
            })}
          </div>
        )}
        <details className={l.observe}>
          <summary>{t.observeText}</summary>
          <pre>{sc.observe}</pre>
        </details>
      </section>
    </div>
  );
}
