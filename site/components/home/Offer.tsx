import type { Dict } from "@/lib/i18n";
import { CONTACT_EMAIL } from "@/lib/site";
import o from "./offer.module.css";

export default function Offer({ t }: { t: Dict }) {
  const f = t.offer;
  return (
    <section id="audit" className={`${o.section} wrap`} aria-labelledby="audit-h">
      <div className={o.head}>
        <p className={o.kicker}>{f.kicker}</p>
        <h2 id="audit-h" className={o.h}>{f.heading}</h2>
        <p className={o.lead}>{f.lead}</p>
        <p className={o.body}>{f.body}</p>
        <ul className={o.questions}>
          {f.questions.map((q) => <li key={q}>“{q}”</li>)}
        </ul>
      </div>

      <div className={o.steps}>
        <h3 className={o.h3}>{f.stepsHeading}</h3>
        <ol>
          {f.steps.map(([name, body], i) => (
            <li key={name} className="rise">
              <span className={o.num} aria-hidden="true">{i + 1}</span>
              <div>
                <p className={o.sname}>{name}</p>
                <p className={o.sbody}>{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className={o.side}>
        <h3 className={o.h3}>{f.notHeading}</h3>
        <ul className={o.not}>{f.not.map((x) => <li key={x}>{x}</li>)}</ul>
        <p className={o.caveat}>{f.caveat}</p>
        <a href="#access" className="btn btn-primary">{f.cta}</a>
        <p className={o.who}>{f.who} · <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
      </div>
    </section>
  );
}
