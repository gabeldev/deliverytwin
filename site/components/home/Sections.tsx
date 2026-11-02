import Link from "next/link";
import type { Dict, Locale } from "@/lib/i18n";
import type { Research, Scenario, Truth } from "@/lib/types";
import { AccuracyRows } from "../charts";
import Status from "../ui/Status";
import x from "./sections.module.css";

const fmt = (n: number, l: Locale) => n.toLocaleString(l === "pt" ? "pt-BR" : "en-US");

export function Receipt({ r, t, locale }: { r: Research; t: Dict; locale: Locale }) {
  return (
    <section className={`${x.receipt} wrap`} aria-labelledby="receipt-h">
      <div className={x.receiptLeft}>
        <div className="rise">
          <h2 id="receipt-h" className={x.h2}>{t.receipt.heading}</h2>
          <p className={x.note}>{t.receipt.note}</p>
        </div>
        <div className="rise">
          <p className={`${x.total} tnum`}>{fmt(r.receipt.total, locale)}</p>
          <p className={x.cap}>{t.receipt.caption}</p>
        </div>
      </div>
      <div className={`${x.slip} rise`} data-ui>
        {Object.entries(r.receipt.groups).map(([g, rows]) => (
          <div key={g} className={x.group}>
            <p className={x.gname}>{t.receipt.groups[g] ?? g}</p>
            {rows.map((row) => (
              <p key={row.agent} className={x.line}><span>{row.agent}</span><i aria-hidden="true" /><span className="tnum">{fmt(row.n, locale)}</span></p>
            ))}
          </div>
        ))}
        <p className={x.sum}><span>{t.receipt.total}</span><span className="tnum">{fmt(r.receipt.total, locale)}</span></p>
        <p className={x.fine}>{t.receipt.fine}</p>
      </div>
    </section>
  );
}

export function Findings({ r, t, locale }: { r: Research; t: Dict; locale: Locale }) {
  const ab = r.experiment_ablation;
  const lv = r.levels;
  const ladder = r.ladder as Record<string, Record<string, { exact: number; ci: [number, number] }>>;
  const tw = r.twin_sweep;
  const pre = locale === "pt" ? "pré-registrado" : "pre-registered";
  return (
    <section className={`${x.findings} wrap`} aria-labelledby="find-h">
      <div className={x.findHead}>
        <h2 id="find-h" className={x.h2}>{t.findings.heading}</h2>
        <p className={x.note}>{t.findings.lead}</p>
      </div>
      <article className={`${x.finding} rise`}>
        <div>
          <h3 className={x.h3}>{t.findings.f1.title}</h3>
          <p>{t.findings.f1.body}</p>
          <p className={x.tag}><Status kind="experiment" locale={locale} label={pre} /> <span className="tnum muted">McNemar p = {ab.paired.mcnemar_p.toFixed(3)}</span></p>
        </div>
        <div data-ui className={x.fig}>
          <AccuracyRows ariaLabel={t.findings.f1.title} highlight="with" rows={[
            { key: "with", label: `${t.findings.with}`, acc: ab.with.exact, ci: ab.with.ci, note: "Qwen3-1.7B + LoRA, L2" },
            { key: "without", label: `${t.findings.without}`, acc: ab.without.exact, ci: ab.without.ci, note: "Qwen3-1.7B + LoRA, L2" },
            { key: "pb", label: "Playbook", acc: lv.playbook.L2.acc, ci: lv.playbook.L2.ci, note: "L2" },
            { key: "mini", label: "gpt-5-mini", acc: lv["gpt-5-mini"].L2.acc, ci: lv["gpt-5-mini"].L2.ci, note: "L2" },
          ]} />
        </div>
      </article>
      <article className={`${x.finding} ${x.flip} rise`}>
        <div>
          <h3 className={x.h3}>{t.findings.f2.title}</h3>
          <p>{t.findings.f2.body}</p>
          <p className={x.tag}><Status kind="hypothesis" locale={locale} label={locale === "pt" ? "exploratório" : "exploratory"} /></p>
        </div>
        <div data-ui className={x.fig}>
          <AccuracyRows ariaLabel={t.findings.f2.title} rows={[
            { key: "luna5", label: "gpt-5.6-luna", acc: ladder["gpt-5.6-luna"].L5.exact, ci: ladder["gpt-5.6-luna"].L5.ci, note: locale === "pt" ? "L5, telemetria parcial" : "L5, partial telemetry" },
            { key: "mini5", label: "gpt-5-mini", acc: ladder["gpt-5-mini"].L5.exact, ci: ladder["gpt-5-mini"].L5.ci, note: locale === "pt" ? "L5, telemetria parcial" : "L5, partial telemetry" },
            { key: "sft5", label: "Qwen3-1.7B + LoRA", acc: ladder["qwen-sft"].L5.exact, ci: ladder["qwen-sft"].L5.ci, note: locale === "pt" ? "L5, telemetria parcial" : "L5, partial telemetry" },
            { key: "mini4", label: "gpt-5-mini", acc: ladder["gpt-5-mini"].L4.exact, ci: ladder["gpt-5-mini"].L4.ci, note: locale === "pt" ? "L4, par equivalente" : "L4, equivalent pair" },
            { key: "sft4", label: "Qwen3-1.7B + LoRA", acc: ladder["qwen-sft"].L4.exact, ci: ladder["qwen-sft"].L4.ci, note: locale === "pt" ? "L4, par equivalente" : "L4, equivalent pair" },
          ]} />
        </div>
      </article>
      <article className={`${x.finding} rise`}>
        <div>
          <h3 className={x.h3}>{t.findings.f3.title}</h3>
          <p>{t.findings.f3.body}</p>
          <p className={x.tag}><Status kind="experiment" locale={locale} label={pre} /></p>
        </div>
        <div data-ui className={x.fig}>
          <AccuracyRows ariaLabel={t.findings.f3.title} rows={[
            { key: "A", label: locale === "pt" ? "Forks do mundo real (A)" : "Forks of the true world (A)", acc: tw.mode_A.exact, ci: tw.mode_A.ci },
            { key: "0", label: "Twin δ = 0", acc: tw.delta_0.exact, ci: tw.delta_0.ci },
            { key: "1", label: "Twin δ = 0.1", acc: tw["delta_0.1"].exact, ci: tw["delta_0.1"].ci },
            { key: "25", label: "Twin δ = 0.25", acc: tw["delta_0.25"].exact, ci: tw["delta_0.25"].ci },
            { key: "5", label: "Twin δ = 0.5", acc: tw["delta_0.5"].exact, ci: tw["delta_0.5"].ci },
          ]} />
        </div>
      </article>
      <p className={x.more}><Link href={`/${locale}/research`} className="btn btn-dark">{t.findings.more}</Link></p>
    </section>
  );
}

export function OpenTiles({ t }: { t: Dict }) {
  return (
    <section className={`${x.tiles} wrap`} aria-labelledby="open-h">
      <div className={`${x.tile} ${x.tileHead}`}><h2 id="open-h">{t.open.heading}</h2></div>
      {t.open.tiles.map(([name, body]) => (
        <div key={name} className={`${x.tile} rise`}>
          <p className={x.tname}>{name}</p>
          <p className={x.tbody}>{body}</p>
        </div>
      ))}
    </section>
  );
}

export function Technology({ sc, truth, t, locale }: { sc: Scenario; truth: Truth; t: Dict; locale: Locale }) {
  return (
    <section id="technology" className={`${x.tech} wrap`} aria-labelledby="tech-h">
      <div className={x.techHead}>
        <h2 id="tech-h" className={x.h2}>{t.tech.heading}</h2>
        <p className={x.note}>{t.tech.lead}</p>
      </div>
      <ol className={x.techList}>
        {t.tech.rows.map(([name, body], i) => (
          <li key={name} className={`${x.techRow} rise`}>
            <div className={x.techText}>
              <h3 className={x.h3}>{name}</h3>
              <p>{body}</p>
            </div>
            <div className={x.techFrag} data-ui>
              {i === 0 && <pre>{`family: ${truth.reveal.family}\n${Object.entries(truth.reveal.fault).filter(([k]) => k !== "family").map(([k, v]) => `${k}: ${typeof v === "number" ? +v.toFixed(3) : v}`).join("\n")}`}</pre>}
              {i === 1 && <pre>{sc.observe.split("\n").slice(1, 4).join("\n")}</pre>}
              {i === 2 && <pre>{`fork_at(t0=${sc.lab.A.t0}, replica=r)\n  control:   NoOp\n  treatment: set_retry_backoff(0.2)\nreplicas ${sc.lab.A.replica_ids[0]}–${sc.lab.A.replica_ids[1]} · placebo Δ = 0.000`}</pre>}
              {i === 3 && <pre>{`exact: true/false\npath_f1, evidence validity, Brier\nrecommendation Δ bad-rate in the true world\n(replicas 1001+, disjoint from the agent's)`}</pre>}
              <p className={x.techSee}>{i === 0 ? t.tech.hidden : `${name} ${t.tech.sees}`}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
