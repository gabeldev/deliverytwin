"use client";

import { useMemo, useState } from "react";
import { scaleLinear } from "d3-scale";
import type { Locale } from "@/lib/i18n";
import type { LabDict } from "@/lib/lab-i18n";
import { armName } from "@/lib/names";
import type { Scenario } from "@/lib/types";
import { EffectPlot, LineChart } from "../charts";
import Status, { SourceTag } from "../ui/Status";
import l from "./lab.module.css";

const GROUPS: { kind: string; en: string; pt: string }[] = [
  { kind: "add_couriers", en: "Couriers", pt: "Entregadores" },
  { kind: "set_dispatcher_workers", en: "Dispatcher workers", pt: "Trabalhadores do despachante" },
  { kind: "set_retry_backoff", en: "Retry backoff", pt: "Espera de nova tentativa" },
  { kind: "set_dispatch_policy", en: "Dispatch policy", pt: "Política de despacho" },
  { kind: "set_admission_rate", en: "Admission", pt: "Admissão" },
  { kind: "placebo", en: "Control check", pt: "Checagem de controle" },
];

const pts = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v * 100).toFixed(1)}`;
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function CounterfactualLab({ sc, t, locale, commit }: { sc: Scenario; t: LabDict; locale: Locale; commit: string }) {
  const [mode, setMode] = useState<"A" | "B">("A");
  const lab = sc.lab[mode];
  const [sel, setSel] = useState("add_couriers_10");
  const arm = lab.arms.find((a) => a.key === sel) ?? lab.arms[0];
  const ext = useMemo(() => {
    const lo = Math.min(...lab.arms.map((a) => a.ci_bad[0]), -0.02);
    const hi = Math.max(...lab.arms.map((a) => a.ci_bad[1]), 0.02);
    return [lo * 1.05, hi * 1.05] as [number, number];
  }, [lab]);
  const x = lab.control_series_bad.map((_, i) => i * lab.bin_minutes);
  const rd = arm.replica_diffs;
  const sdom: [number, number] = [Math.min(0, ...rd) - 0.01, Math.max(0, ...rd) + 0.01];
  const sx = scaleLinear().domain(sdom).range([8, 352]);

  return (
    <div className={l.cf}>
      <div className={l.cfHead}>
        <div>
          <h2 className={l.h2}>{t.labTitle}</h2>
          <p className={l.note}>{t.labLead}</p>
        </div>
        <div className={l.modes} role="radiogroup" aria-label="Lab mode" data-ui>
          {(["A", "B"] as const).map((m) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m} data-on={mode === m ? "1" : undefined} className={l.modeBtn} onClick={() => setMode(m)}>
              {m === "A" ? t.modeA : t.modeB}
            </button>
          ))}
        </div>
      </div>
      {mode === "B" && <p className={l.callout}>{t.modeBNote}</p>}

      <div className={l.cfGrid}>
        <section className={l.panel} data-ui aria-label={locale === "pt" ? "Escolha uma decisão" : "Choose a decision"}>
          {GROUPS.map((g) => (
            <fieldset key={g.kind} className={l.group}>
              <legend>{g[locale]}</legend>
              <div className={l.opts}>
                {lab.arms.filter((a) => a.kind === g.kind).map((a) => (
                  <label key={a.key} className={l.opt} data-on={a.key === sel ? "1" : undefined}>
                    <input type="radio" name="arm" value={a.key} checked={a.key === sel} onChange={() => setSel(a.key)} />
                    {armName(a.key, locale).replace(/^(\+|Accept |Aceitar |Retry after |Repetir após )/, (m) => (g.kind === "add_couriers" ? m : ""))}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <p className={l.note}>{locale === "pt" ? "Admissão abaixo de 80% não é oferecida: violaria a restrição de negócio declarada." : "Admission below 80% is not offered: it would break the declared business constraint."}</p>
        </section>

        <section className={l.panel} data-ui aria-live="polite" aria-label={armName(arm.key, locale)}>
          <div className={l.panelHead}>
            <h3 className={l.h3}>{armName(arm.key, locale)}</h3>
            <Status kind="experiment" locale={locale} label={`${locale === "pt" ? "Experimento" : "Experiment"} · ${locale === "pt" ? "modo" : "mode"} ${mode}`} />
          </div>
          <div className={l.big}>
            <div><span>{t.control}</span><b className="tnum">{pct(lab.control_bad)}</b></div>
            <div><span>{t.treatment}</span><b className="tnum">{pct(arm.treatment_bad)}</b></div>
            <div data-sign={arm.ci_bad[1] < 0 ? "-" : arm.ci_bad[0] > 0 ? "+" : "0"}>
              <span>Δ ({locale === "pt" ? "pontos" : "points"})</span>
              <b className="tnum">{pts(arm.diff_bad)}</b>
              <small className="tnum">{locale === "pt" ? "IC 95%" : "95% CI"} {pts(arm.ci_bad[0])} … {pts(arm.ci_bad[1])}</small>
            </div>
          </div>
          <p className={l.verdictLine}>
            {arm.key === "placebo" && arm.all_zero ? (locale === "pt" ? `Placebo: diferença exatamente zero na taxa de pedidos ruins em todos os ${lab.replicas} futuros pareados.` : `Placebo: exactly zero difference in the bad-order rate in all ${lab.replicas} paired futures.`)
              : arm.ci_bad[0] <= 0 && arm.ci_bad[1] >= 0 ? (locale === "pt" ? "Sem efeito detectável: o intervalo inclui zero." : "No detectable effect: the interval includes zero.")
              : arm.diff_bad < 0 ? (locale === "pt" ? "Menos pedidos atrasados ou perdidos, com intervalo inteiro abaixo de zero." : "Fewer late or failed orders, with the whole interval below zero.")
              : (locale === "pt" ? "Mais pedidos atrasados ou perdidos: esta decisão piora a situação." : "More late or failed orders: this decision makes things worse.")}
          </p>
          <LineChart x={x} height={190} yMax={1} xLabel={locale === "pt" ? "min após o alerta" : "min after alert"} ariaLabel={t.overTime}
            tableCaption={locale === "pt" ? "Ver dados" : "Show data"}
            series={[
              { id: "c", label: t.control, color: "var(--series-control)", values: lab.control_series_bad },
              { id: "t", label: t.treatment, color: "var(--series-treat)", values: arm.series_bad, dashed: true },
            ]} />
          <p className={l.mini}>{t.overTime}</p>
          <div className={l.strip} aria-label={t.perReplica} role="img">
            <svg viewBox="0 0 360 34" aria-hidden="true">
              <line x1={sx(0)} x2={sx(0)} y1={2} y2={32} stroke="var(--ink)" strokeWidth={1.5} />
              {arm.replica_diffs.map((d, k) => <circle key={k} cx={sx(d)} cy={17 + ((k % 5) - 2) * 4} r={3.5} fill="var(--series-treat)" fillOpacity={0.75} stroke="#fff" strokeWidth={1} />)}
            </svg>
          </div>
          <details className={l.mini}>
            <summary>{t.perReplica}</summary>
            <p className="tnum">{rd.map((d, k) => `#${lab.replica_ids[0] + k}: ${pts(d)}`).join(" · ")}</p>
          </details>
          <dl className={l.facts}>
            <div><dt>{t.cost}</dt><dd className="tnum">{arm.cost.toFixed(1)}</dd></div>
            <div><dt>{t.rejected}</dt><dd className="tnum">{pct(arm.treatment_rejected)}</dd></div>
            <div><dt>{t.time}</dt><dd className="tnum">{lab.control_time.toFixed(1)} → {(lab.control_time + arm.diff_time).toFixed(1)} min</dd></div>
          </dl>
          {arm.key === "admission_0.8" && <p className={l.note}>{t.constraint}</p>}
        </section>
      </div>

      <section className={l.panel} data-ui aria-label={t.effectAll}>
        <h3 className={l.h3}>{t.effectAll}</h3>
        <EffectPlot domain={ext} format={pts} zeroLabel="0" betterLabel={t.fewer} selected={sel} onSelect={setSel} ariaLabel={t.effectAll}
          rows={lab.arms.map((a) => ({ key: a.key, label: armName(a.key, locale), mean: a.diff_bad, lo: a.ci_bad[0], hi: a.ci_bad[1], note: `${locale === "pt" ? "custo" : "cost"} ${a.cost.toFixed(1)}` }))} />
      </section>
      <p className={l.prov}>
        <SourceTag kind="precomputed" text={t.provenance.replace("{seed}", String(sc.seed)).replace("{reps}", `${lab.replica_ids[0]}–${lab.replica_ids[1]}`).replace("{commit}", commit)} />
        <span>{t.reproduce}: <code>{sc.provenance.command}</code></span>
      </p>
    </div>
  );
}
