import type { Dict, Locale } from "@/lib/i18n";
import type { Scenario, Step, Truth } from "@/lib/types";
import Status, { SourceTag } from "../ui/Status";
import ToolText from "../ui/ToolText";
import { familyName } from "@/lib/names";
import h from "./how.module.css";

type Hyp = { family: string; rationale?: string };

function excerpt(text: string, lines: number) {
  const all = text.split("\n");
  return all.slice(0, lines).join("\n") + (all.length > lines ? "\n…" : "");
}

export default function HowItWorks({ sc, truth, t, locale }: { sc: Scenario; truth: Truth; t: Dict; locale: Locale }) {
  const agentKey = sc.sessions["qwen-sft"] ? "qwen-sft" : "playbook";
  const sess = sc.sessions[agentKey];
  const res = truth.evaluations[agentKey];
  const find = (op: string) => sess.steps.find((x) => x.op === op);
  const observe = find("observe");
  const query = find("query");
  const hyp = find("hypothesize");
  const exp = find("experiment");
  const submit = find("submit");
  const hyps = ((hyp?.args as { hypotheses?: Hyp[] })?.hypotheses ?? []);
  const call = (st: Step | undefined) => (st ? `${st.op}(${st.args && Object.keys(st.args as object).length ? JSON.stringify(st.args, null, 1).replace(/\n\s*/g, " ") : ""})` : "");

  return (
    <section className={`${h.section} wrap`} aria-labelledby="how-h">
      <div className={h.col}>
        <h2 id="how-h" className={h.heading}>{t.how.heading}</h2>
        <p className={h.meta}>
          <SourceTag kind="recorded" text={`${t.common.recorded}: ${sess.label}`} />
          <span className="muted">{locale === "pt" ? `Incidente ${sc.id.toUpperCase()}, semente pública ${sc.seed}` : `Incident ${sc.id.toUpperCase()}, public seed ${sc.seed}`}</span>
        </p>

        <div className={`${h.ex} rise`}>
          <p className={h.say}>{t.how.steps[0]}</p>
          <pre className={h.call} data-ui aria-label={t.how.call}>{call(observe)}</pre>
          <div className={h.resp} data-ui>
            <Status kind="observation" locale={locale} />
            <pre>{excerpt(observe?.response ?? "", 4)}</pre>
          </div>
        </div>

        <div className={`${h.ex} rise`}>
          <p className={h.say}>{t.how.steps[1]}</p>
          <pre className={h.call} data-ui aria-label={t.how.call}>{call(query)}</pre>
          <div className={h.resp} data-ui>
            <Status kind="observation" locale={locale} />
            <ToolText text={query?.response ?? ""} maxLines={5} />
          </div>
        </div>

        <div className={`${h.ex} rise`}>
          <p className={h.say}>{t.how.steps[2]}</p>
          <div className={h.resp} data-ui>
            <Status kind="hypothesis" locale={locale} />
            <ul className={h.hyps}>
              {hyps.map((x) => <li key={x.family}><b>{familyName(x.family, locale)}</b>{x.rationale && <span>{x.rationale}</span>}</li>)}
            </ul>
          </div>
          <pre className={h.call} data-ui aria-label={t.how.call}>{call(exp)}</pre>
          <div className={h.resp} data-ui>
            <Status kind="experiment" locale={locale} />
            <pre>{excerpt(exp?.response ?? "", 3)}</pre>
          </div>
        </div>

        <div className={`${h.ex} ${h.final} rise`}>
          <p className={h.say}>{t.how.steps[3]}</p>
          <pre className={h.call} data-ui aria-label={t.how.call}>{`submit(cause="${(submit?.args as { cause?: string })?.cause ?? ""}", …)`}</pre>
          <div className={h.verdictRow} data-ui>
            <div>
              <Status kind="recommendation" locale={locale} label={t.how.submitted} />
              <p>{familyName(res.cause, locale)}</p>
            </div>
            <div className={h.truth}>
              <Status kind="truth" locale={locale} />
              <p>{familyName(truth.reveal.family, locale)}</p>
              <small>{locale === "pt" ? "Parâmetros da falha injetada" : "Injected fault parameters"}: {Object.entries(truth.reveal.fault).filter(([k]) => k !== "family").map(([k, v]) => `${k}=${typeof v === "number" ? +v.toFixed(3) : v}`).join(", ")}</small>
            </div>
            <div>
              <Status kind="experiment" locale={locale} label={t.how.verdict} />
              <p className={res.exact ? h.ok : h.bad}>{res.exact ? t.how.correct : t.how.wrong}</p>
              <small className="tnum">{locale === "pt" ? "Consultas" : "Queries"} {res.used.queries} · {locale === "pt" ? "experimentos" : "experiments"} {res.used.experiments}</small>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
