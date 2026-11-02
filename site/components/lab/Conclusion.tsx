"use client";

import { useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";
import type { LabDict } from "@/lib/lab-i18n";
import { armName, familyName } from "@/lib/names";
import type { Scenario, Truth } from "@/lib/types";
import Status from "../ui/Status";
import { AgentPicker } from "./Investigation";
import l from "./lab.module.css";

const pts = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v * 100).toFixed(1)}`;

type Report = { cause?: string | null; confidence?: number; recommendation?: Record<string, unknown> | null; summary?: string; unresolved_between?: string[]; evidence_ids?: string[] };

export default function Conclusion({ sc, t, locale, agent, setAgent }: { sc: Scenario; t: LabDict; locale: Locale; agent: string; setAgent: (a: string) => void }) {
  const [open, setOpen] = useState(false);
  const [truth, setTruth] = useState<Truth | null>(null);
  const [err, setErr] = useState(false);
  const sess = sc.sessions[agent] ?? sc.sessions.playbook;
  const rep = (sess.report ?? {}) as Report;
  const best = (m: "A" | "B") => [...sc.lab[m].arms].filter((a) => a.kind !== "placebo").sort((a, b) => a.diff_bad - b.diff_bad)[0];
  const bA = best("A"), bB = best("B");
  const recText = rep.recommendation ? Object.entries(rep.recommendation).map(([k, v]) => (k === "kind" ? v : `${k}=${v}`)).join(" ") : t.none;

  useEffect(() => { setOpen(false); setTruth(null); }, [sc.id]);

  async function reveal() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (truth?.id === sc.id) return;
    try {
      const r = await fetch(`/data/scenarios/${sc.id}.truth.json`);
      if (!r.ok) throw new Error(String(r.status));
      setTruth(await r.json());
      setErr(false);
    } catch { setErr(true); }
  }
  const ev = truth?.evaluations[agent];

  return (
    <div className={l.conc}>
      <div className={l.invHead} data-ui>
        <AgentPicker sc={sc} agent={agent} setAgent={setAgent} t={t} />
      </div>
      <div className={l.concGrid}>
        <section className={l.panel} data-ui aria-labelledby="conc-h">
          <div className={l.panelHead}>
            <h2 id="conc-h" className={l.h2}>{t.concTitle}</h2>
            <Status kind="recommendation" locale={locale} />
          </div>
          <dl className={l.facts}>
            <div><dt>{t.submitted}</dt><dd>{rep.cause ? familyName(rep.cause, locale) : t.abstained}</dd></div>
            <div><dt>{t.confidence}</dt><dd className="tnum">{rep.confidence == null ? "–" : rep.confidence.toFixed(2)}</dd></div>
            <div><dt>{t.recommendation}</dt><dd><code>{String(recText)}</code></dd></div>
          </dl>
          {rep.unresolved_between && rep.unresolved_between.length > 0 && (
            <p className={l.note}>{locale === "pt" ? "Não resolvido entre" : "Unresolved between"}: {rep.unresolved_between.map((f) => familyName(f, locale)).join(", ")}</p>
          )}
          {rep.summary && <p className={l.note}>“{rep.summary}”</p>}
          <button type="button" className={`btn ${open ? "btn-quiet" : "btn-dark"}`} onClick={() => void reveal()} aria-expanded={open} aria-controls="truth-panel">
            {open ? t.hide : t.reveal}
          </button>
        </section>

        <section className={l.panel} data-ui aria-labelledby="says-h">
          <div className={l.panelHead}>
            <h2 id="says-h" className={l.h2}>{t.labSays}</h2>
            <Status kind="experiment" locale={locale} />
          </div>
          <dl className={l.facts}>
            <div><dt>{t.bestA}</dt><dd>{armName(bA.key, locale)} <small className="tnum">{pts(bA.diff_bad)} pts</small></dd></div>
            <div><dt>{t.bestB}</dt><dd>{armName(bB.key, locale)} <small className="tnum">{pts(bB.diff_bad)} pts</small></dd></div>
          </dl>
          <p className={l.note}>{bA.key === bB.key ? t.twinAgree : bA.kind === bB.kind ? t.twinQuantity : t.twinWarn}</p>
        </section>
      </div>

      {open && (
        <section id="truth-panel" className={l.truth} data-ui aria-labelledby="truth-h" aria-busy={!truth && !err}>
          <div className={l.panelHead}>
            <h2 id="truth-h" className={l.h2}>{t.truthTitle}</h2>
            <Status kind="truth" locale={locale} />
          </div>
          <p className={l.note}>{t.truthNote}</p>
          {err && <p className={l.error} role="alert">{t.loadError}</p>}
          {!truth && !err && <p className={l.note} role="status">{t.loading}…</p>}
          {truth && (
            <div className={l.truthGrid}>
              <dl className={l.facts}>
                <div><dt>{t.family}</dt><dd>{familyName(truth.reveal.family, locale)}</dd></div>
                <div><dt>{t.params}</dt><dd><code>{Object.entries(truth.reveal.fault).filter(([k]) => k !== "family").map(([k, v]) => `${k}=${typeof v === "number" ? +v.toFixed(3) : v}`).join(", ")}</code></dd></div>
                <div><dt>{t.dag}</dt><dd><code>{truth.reveal.causal_dag.map(([a, b], i) => (i === 0 ? `${a} → ${b}` : ` → ${b}`)).join("")}</code></dd></div>
              </dl>
              {ev && (
                <dl className={l.facts}>
                  <div><dt>{t.exact}</dt><dd className={ev.exact ? l.ok : l.bad}>{ev.abstained ? t.abstained : ev.exact ? t.correct : t.wrong}</dd></div>
                  <div><dt>{t.pathF1}</dt><dd className="tnum">{ev.path_f1?.toFixed(2) ?? "–"}</dd></div>
                  <div><dt>{t.recEffect}</dt><dd className="tnum">{ev.recommendation_diff_bad == null ? "–" : `${pts(ev.recommendation_diff_bad)} pts`}</dd></div>
                </dl>
              )}
            </div>
          )}
        </section>
      )}

      <section className={l.panel} aria-labelledby="lim-h">
        <h2 id="lim-h" className={l.h3}>{t.limits}</h2>
        <ul className={l.limits}>{t.limitItems.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
    </div>
  );
}
