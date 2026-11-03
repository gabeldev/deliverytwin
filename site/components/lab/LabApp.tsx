"use client";

import { useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { labDicts } from "@/lib/lab-i18n";
import type { Scenario, ScenarioIndex } from "@/lib/types";
import Incident from "./Incident";
import Investigation from "./Investigation";
import CounterfactualLab from "./CounterfactualLab";
import Conclusion from "./Conclusion";
import { onRadioKeys } from "../ui/radio";
import l from "./lab.module.css";

export default function LabApp({ index, initial, locale }: { index: ScenarioIndex; initial: Scenario; locale: Locale }) {
  const t = labDicts[locale];
  const [sc, setSc] = useState<Scenario>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [step, setStep] = useState(0);
  const [agent, setAgent] = useState<string>(initial.sessions["qwen-sft"] ? "qwen-sft" : "playbook");

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const id = p.get("incident");
    if (id && id !== initial.id && index.scenarios.some((s) => s.id === id)) void choose(id);
    const st = Number(p.get("step"));
    if (st >= 0 && st <= 3) setStep(st);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function choose(id: string) {
    if (id === sc.id) return;
    setLoading(true); setError(false);
    try {
      const r = await fetch(`/data/scenarios/${id}.json`);
      if (!r.ok) throw new Error(String(r.status));
      const next: Scenario = await r.json();
      setSc(next);
      if (!next.sessions[agent]) setAgent("playbook");
      const u = new URL(window.location.href);
      u.searchParams.set("incident", id);
      window.history.replaceState(null, "", u);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  function go(i: number) {
    setStep(i);
    const u = new URL(window.location.href);
    u.searchParams.set("step", String(i));
    window.history.replaceState(null, "", u);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById("lab-stage")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  return (
    <div className={l.app}>
      <header className={`${l.head} wrap`}>
        <h1 className={l.h1}>{t.title}</h1>
        <p className={l.lead}>{t.lead}</p>
        <p className={l.precomputed}>{t.precomputed}</p>
      </header>

      <div className={`${l.bar} wrap`} data-ui>
        <div className={l.incidents} role="radiogroup" aria-label={t.pickIncident} onKeyDown={onRadioKeys}>
          {index.scenarios.map((s) => (
            <button key={s.id} type="button" role="radio" aria-checked={s.id === sc.id} tabIndex={s.id === sc.id ? 0 : -1} className={l.inc} data-on={s.id === sc.id ? "1" : undefined}
              onClick={() => void choose(s.id)} disabled={loading}>
              <b>{s.id.toUpperCase()}</b>
              <span>{t.level[s.level] ?? s.level} · {t.alertAt} {Math.round(s.alert.t)}</span>
            </button>
          ))}
        </div>
        <nav className={l.steps} aria-label="Steps">
          {t.steps.map((name, i) => (
            <button key={name} type="button" className={l.step} data-on={i === step ? "1" : undefined} aria-current={i === step ? "step" : undefined} onClick={() => go(i)}>
              <span className={l.stepLetter} aria-hidden="true">{t.stepNames[i]}</span>{name}
            </button>
          ))}
        </nav>
      </div>

      <div id="lab-stage" className={`${l.stage} wrap`} aria-busy={loading}>
        {error && <p className={l.error} role="alert">{t.loadError}</p>}
        {loading && <p className={l.loading} role="status">{t.loading}…</p>}
        {!loading && !error && (
          <>
            {step === 0 && <Incident sc={sc} t={t} locale={locale} />}
            {step === 1 && <Investigation sc={sc} t={t} locale={locale} agent={agent} setAgent={setAgent} />}
            {step === 2 && <CounterfactualLab sc={sc} t={t} locale={locale} commit={index.commit} />}
            {step === 3 && <Conclusion sc={sc} t={t} locale={locale} agent={agent} setAgent={setAgent} />}
            <div className={l.nextRow}>
              {step > 0 && <button type="button" className="btn btn-quiet" onClick={() => go(step - 1)}>← {t.steps[step - 1]}</button>}
              {step < 3 && <button type="button" className="btn btn-dark" onClick={() => go(step + 1)}>{t.steps[step + 1]} →</button>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
