"use client";

import { useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";
import type { LabDict } from "@/lib/lab-i18n";
import { familyName } from "@/lib/names";
import type { Scenario, Step } from "@/lib/types";
import Status, { SourceTag, type StatusKind } from "../ui/Status";
import ToolText from "../ui/ToolText";
import l from "./lab.module.css";

const OP_STATUS: Record<string, StatusKind> = { observe: "observation", query: "observation", hypothesize: "hypothesis", experiment: "experiment", submit: "recommendation" };
export const AGENT_ORDER = ["playbook", "qwen-sft", "qwen-base", "gpt-5-mini", "gpt-5.6-luna"];

export function AgentPicker({ sc, agent, setAgent, t }: { sc: Scenario; agent: string; setAgent: (a: string) => void; t: LabDict }) {
  return (
    <div className={l.agents} role="radiogroup" aria-label={t.agent}>
      {AGENT_ORDER.filter((a) => sc.sessions[a]).map((a) => (
        <button key={a} type="button" role="radio" aria-checked={a === agent} className={l.agentBtn} data-on={a === agent ? "1" : undefined} onClick={() => setAgent(a)}>
          <b>{sc.sessions[a].label.split(" (")[0]}</b>
          <SourceTag kind={sc.sessions[a].kind} text={t.agentKinds[sc.sessions[a].kind]} />
        </button>
      ))}
    </div>
  );
}

function pretty(args: unknown) {
  if (!args || (typeof args === "object" && Object.keys(args as object).length === 0)) return "";
  return JSON.stringify(args, null, 2);
}

export default function Investigation({ sc, t, locale, agent, setAgent }: { sc: Scenario; t: LabDict; locale: Locale; agent: string; setAgent: (a: string) => void }) {
  const sess = sc.sessions[agent] ?? sc.sessions.playbook;
  const steps = sess.steps;
  const [i, setI] = useState(steps.length - 1);
  const [auto, setAuto] = useState(false);

  useEffect(() => { setI(steps.length - 1); setAuto(false); }, [agent, sc.id, steps.length]);
  useEffect(() => {
    if (!auto) return;
    if (i >= steps.length - 1) { setAuto(false); return; }
    const id = window.setTimeout(() => setI((v) => v + 1), 1400);
    return () => window.clearTimeout(id);
  }, [auto, i, steps.length]);

  const shown = steps.slice(0, i + 1);
  const hyps = shown.filter((s) => s.op === "hypothesize").flatMap((s) => ((s.args as { hypotheses?: { family: string; rationale?: string; evidence_ids?: string[] }[] })?.hypotheses ?? []));
  const used = {
    q: shown.filter((s) => s.op === "query" && s.ok).length,
    e: shown.filter((s) => s.op === "experiment" && s.ok).length,
  };
  const B = sc.level === "L4" ? { q: 8, e: 1 } : { q: 25, e: 4 };

  return (
    <div className={l.investigation}>
      <div className={l.invHead} data-ui>
        <AgentPicker sc={sc} agent={agent} setAgent={setAgent} t={t} />
        <p className={l.note}>{sess.kind === "recorded" ? t.replayNote : t.agentKinds.deterministic}{sess.run ? ` · run ${sess.run}` : ""}</p>
      </div>
      <div className={l.invBody}>
        <ol className={l.steplist} data-ui>
          {shown.map((s: Step, k) => (
            <li key={k} className={l.stepCard} data-new={k === i ? "1" : undefined}>
              <div className={l.stepTop}>
                <Status kind={OP_STATUS[s.op] ?? "observation"} locale={locale} />
                <code className={l.op}>{s.op}</code>
                {!s.ok && <span className={l.err}>{locale === "pt" ? "erro de ferramenta" : "tool error"}</span>}
              </div>
              {pretty(s.args) && (
                <details open={s.op !== "submit"}>
                  <summary>{t.args}</summary>
                  <pre>{pretty(s.args)}</pre>
                </details>
              )}
              <div className={l.resp} aria-label={t.response}><ToolText text={s.response} /></div>
            </li>
          ))}
        </ol>
        <aside className={l.side} data-ui>
          <div className={l.controls}>
            <span className="tnum">{t.stepOf.replace("{i}", String(i + 1)).replace("{n}", String(steps.length))}</span>
            <div className={l.ctrlBtns}>
              <button type="button" className="btn btn-quiet" onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0}>{t.prev}</button>
              <button type="button" className="btn btn-quiet" onClick={() => setI((v) => Math.min(steps.length - 1, v + 1))} disabled={i >= steps.length - 1}>{t.next}</button>
              <button type="button" className="btn btn-dark" onClick={() => { if (!auto) setI(0); setAuto((a) => !a); }}>{auto ? t.stop : t.playAll}</button>
            </div>
          </div>
          <div className={l.sideBlock}>
            <h3 className={l.h3}>{t.ledger}</h3>
            {hyps.length === 0 ? <p className={l.note}>{t.noHyp}</p> : (
              <ul className={l.ledger}>
                {hyps.map((h, k) => (
                  <li key={k}>
                    <Status kind="hypothesis" locale={locale} label={familyName(h.family, locale)} />
                    {h.rationale && <span>{h.rationale}</span>}
                    {h.evidence_ids?.length ? <small>{h.evidence_ids.join(", ")}</small> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className={l.sideBlock}>
            <h3 className={l.h3}>{t.budget}</h3>
            <Meter label={t.queries} used={used.q} max={B.q} />
            <Meter label={t.experiments} used={used.e} max={B.e} />
          </div>
        </aside>
      </div>
    </div>
  );
}

function Meter({ label, used, max }: { label: string; used: number; max: number }) {
  return (
    <div className={l.meter}>
      <span>{label}</span>
      <span className={l.meterBar} aria-hidden="true"><i style={{ width: `${Math.min(100, (used / max) * 100)}%` }} /></span>
      <span className="tnum">{used}/{max}</span>
    </div>
  );
}
