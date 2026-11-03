"use client";

import { useState } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import { CONTACT_EMAIL } from "@/lib/site";
import c from "./contact.module.css";

type State = { kind: "idle" | "sending" | "ok" | "error"; msg?: string };

export default function Contact({ t, locale }: { t: Dict; locale: Locale }) {
  const [email, setEmail] = useState("");
  const [kind, setKind] = useState("operator");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [hp, setHp] = useState("");
  const [st, setSt] = useState<State>({ kind: "idle" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return setSt({ kind: "error", msg: t.contact.errEmail });
    if (!consent) return setSt({ kind: "error", msg: t.contact.errConsent });
    setSt({ kind: "sending" });
    try {
      const r = await fetch("/api/interest", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, kind, message, consent, locale, website: hp }),
      });
      if (!r.ok) throw new Error(String(r.status));
      setSt({ kind: "ok", msg: t.contact.ok });
      setEmail(""); setMessage(""); setConsent(false);
    } catch {
      setSt({ kind: "error", msg: t.contact.errServer });
    }
  }

  return (
    <section id="access" className={`${c.section} wrap`} aria-labelledby="access-h">
      <form className={c.col} onSubmit={submit} noValidate>
        <h2 id="access-h" className={c.h}>{t.contact.heading}</h2>
        <p className={c.prompt}><span className="muted">{t.contact.l1}</span> {t.contact.l2}</p>
        <p className={c.direct}>{t.contact.direct} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
        <div className={c.field}>
          <label htmlFor="ea-email" className="sr-only">{t.contact.email}</label>
          <input id="ea-email" type="email" inputMode="email" autoComplete="email" placeholder={t.contact.email}
            value={email} onChange={(e) => setEmail(e.target.value)} required aria-describedby="ea-status" />
          <button type="submit" className={c.go} aria-label={t.contact.submit} disabled={st.kind === "sending"}>
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11M11 5l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </div>
        <fieldset className={c.kinds}>
          <legend>{t.contact.interest}</legend>
          {t.contact.kinds.map(([v, label]) => (
            <label key={v} className={c.kind} data-on={kind === v ? "1" : undefined}>
              <input type="radio" name="kind" value={v} checked={kind === v} onChange={() => setKind(v)} />{label}
            </label>
          ))}
        </fieldset>
        <label className={c.msgLabel} htmlFor="ea-msg">{t.contact.message}</label>
        <textarea id="ea-msg" className={c.msg} rows={3} maxLength={1200} value={message} onChange={(e) => setMessage(e.target.value)} />
        <div className={c.hp} aria-hidden="true">
          <label htmlFor="ea-web">Website</label>
          <input id="ea-web" tabIndex={-1} autoComplete="off" value={hp} onChange={(e) => setHp(e.target.value)} />
        </div>
        <label className={c.consent}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>{t.contact.consent}</span>
        </label>
        <p id="ea-status" className={c.status} role={st.kind === "error" ? "alert" : "status"} data-kind={st.kind}>
          {st.kind === "sending" ? `${t.contact.sending}…` : st.msg ?? t.contact.next}
        </p>
      </form>
    </section>
  );
}
