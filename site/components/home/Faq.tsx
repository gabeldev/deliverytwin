"use client";

import { useState } from "react";
import type { Dict } from "@/lib/i18n";
import f from "./faq.module.css";

export default function Faq({ t }: { t: Dict }) {
  const [sel, setSel] = useState(0);
  const items = t.faq.items;
  return (
    <section className={`${f.section} wrap`} aria-labelledby="faq-h">
      <div className={f.list}>
        <h2 id="faq-h" className={f.h}>{t.faq.heading}</h2>
        {items.map(([q, a], i) => (
          <div key={q} className={f.item}>
            <button type="button" className={f.q} aria-expanded={sel === i} aria-controls={`faq-a-${i}`}
              data-on={sel === i ? "1" : undefined} onClick={() => setSel(i)} onMouseEnter={() => setSel(i)} onFocus={() => setSel(i)}>
              <i aria-hidden="true" />{q}
            </button>
            <p id={`faq-a-${i}`} className={f.inline} hidden={sel !== i}>{a}</p>
          </div>
        ))}
      </div>
      <div className={f.pane} aria-hidden="true">
        <p key={sel} className={f.answer}>{items[sel][1]}</p>
      </div>
    </section>
  );
}
