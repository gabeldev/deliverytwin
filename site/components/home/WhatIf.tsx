"use client";

import { REPO } from "@/lib/site";
import { useMemo, useState } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import type { Lab } from "@/lib/types";
import { parseWhatIf } from "@/lib/whatif";
import { armName } from "@/lib/names";
import { SourceTag } from "../ui/Status";
import w from "./whatif.module.css";

export default function WhatIf({ lab, scenarioId, t, locale, commit }: { lab: Lab; scenarioId: string; t: Dict; locale: Locale; commit: string }) {
  const [q, setQ] = useState(t.whatif.placeholder);
  const parsed = useMemo(() => parseWhatIf(q), [q]);
  const arm = parsed.ok ? lab.arms.find((a) => a.key === parsed.key) : undefined;
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  const pts = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v * 100).toFixed(1)}`;
  const verdict = !arm ? "" : arm.key === "placebo" ? t.whatif.placebo
    : arm.ci_bad[0] <= 0 && arm.ci_bad[1] >= 0 ? t.whatif.noeffect
    : arm.diff_bad < 0 ? t.whatif.better : t.whatif.worse;
  const snapped = parsed.ok && parsed.asked !== undefined && parsed.used !== undefined && Math.abs(parsed.asked - parsed.used) > 1e-9;

  return (
    <section className={`${w.section} wrap`} aria-labelledby="whatif-h">
      <h2 id="whatif-h" className="sr-only">{t.whatif.heading}</h2>
      <div className={w.line} data-ui>
        <label htmlFor="whatif-input" className={w.prefix}>{t.whatif.prefix}</label>
        <input id="whatif-input" className={w.input} value={q} onChange={(e) => setQ(e.target.value)} spellCheck={false}
          autoComplete="off" aria-describedby="whatif-answer" />
      </div>
      <div id="whatif-answer" className={w.answer} aria-live="polite" data-ui>
        {!parsed.ok && (
          <p className={w.refuse}>{{
            below_constraint: locale === "pt" ? "Recusado: aceitar menos de 80% dos pedidos viola a restrição de negócio declarada (recusa esperada de no máximo 20%). O laboratório não roda isso." : "Refused: accepting fewer than 80% of orders breaks the declared business constraint (expected rejection at most 20%). The lab will not run it.",
            compound: locale === "pt" ? "Uma decisão por vez: o laboratório compara cada decisão sozinha contra a mesma linha de base." : "One decision at a time: the lab compares each decision alone against the same baseline.",
            removal: locale === "pt" ? "O laboratório desta demonstração só testa acréscimos de capacidade, não cortes." : "This demo's lab only tests adding capacity, not removing it.",
            current_policy: locale === "pt" ? "Essa já é a política atual da cidade (despacho pelo mais próximo). Tente a política por ETA." : "That is already the city's current policy (nearest courier). Try the ETA-aware policy.",
            unknown: t.whatif.unknown,
          }[parsed.reason]}</p>
        )}
        {arm && (
          <>
            <p className={w.interp}>{locale === "pt" ? "Interpretado como" : "Interpreted as"}: <b>{armName(arm.key, locale)}</b></p>
            <div className={w.row}>
              <span>{t.whatif.late}</span>
              <span className="tnum"><b>{pct(lab.control_bad)}</b> → <b>{pct(arm.treatment_bad)}</b></span>
              <span className={`tnum ${w.diff}`} data-sign={arm.ci_bad[0] <= 0 && arm.ci_bad[1] >= 0 ? "0" : arm.diff_bad < 0 ? "-" : "+"}>
                {pts(arm.diff_bad)} pts <small>{locale === "pt" ? "IC 95%" : "95% CI"} {pts(arm.ci_bad[0])} {locale === "pt" ? "a" : "to"} {pts(arm.ci_bad[1])}</small>
              </span>
            </div>
            <div className={w.row}>
              <span>{t.whatif.cost}</span><span className="tnum">{arm.cost.toFixed(1)} {t.whatif.units}</span>
              <span className="tnum muted">{t.whatif.rejected}: {pct(arm.treatment_rejected)}</span>
            </div>
            <p className={w.verdict}>{verdict}{snapped && (locale === "pt" ? ` Valor mais próximo calculado: ${parsed.used}.` : ` Nearest precomputed value: ${parsed.used}.`)}</p>
            <p className={w.ctx}><SourceTag kind="precomputed" text={t.whatif.context.replace("{id}", scenarioId.toUpperCase()).replace("{n}", String(lab.replicas))} /> <a className="muted" href={`${REPO}/tree/${commit}`}>commit {commit}</a></p>
          </>
        )}
      </div>
      <div className={w.examples}>
        {t.whatif.examples.map((ex) => (
          <button key={ex} type="button" className={w.ex} onClick={() => setQ(ex)}>{ex}</button>
        ))}
      </div>
    </section>
  );
}
