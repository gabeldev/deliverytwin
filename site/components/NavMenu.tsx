"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import s from "./chrome.module.css";

/** Same page in the other language (keeps /lab, /research, query and hash). */
export function LangSwitch({ locale, t, compact }: { locale: Locale; t: Dict; compact?: boolean }) {
  const path = usePathname() ?? `/${locale}`;
  const other = locale === "en" ? "pt" : "en";
  const [suffix, setSuffix] = useState("");
  useEffect(() => { setSuffix(window.location.search + window.location.hash); }, [path]);
  const href = path.replace(/^\/(en|pt)(?=\/|$)/, `/${other}`) + suffix;
  return (
    <Link href={href} hrefLang={other} lang={other === "pt" ? "pt-BR" : "en"} aria-label={t.nav.switchLabel}
      className={compact ? s.langPill : undefined}>
      {compact ? other.toUpperCase() : t.nav.switch}
    </Link>
  );
}

/** Small-screen menu: a panel under the header. Opens on tap, closes on Escape, outside tap or navigation. */
export function NavMenu({ locale, t }: { locale: Locale; t: Dict }) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const path = usePathname();

  useEffect(() => { setOpen(false); }, [path]);
  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector<HTMLElement>("a")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); btn.current?.focus(); } };
    const onDown = (e: PointerEvent) => {
      const n = e.target as Node;
      if (!panel.current?.contains(n) && !btn.current?.contains(n)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown); };
  }, [open]);

  const close = () => setOpen(false);
  const pt = locale === "pt";
  return (
    <div className={s.mobileOnly}>
      <LangSwitch locale={locale} t={t} compact />
      <button ref={btn} type="button" className={s.menuBtn} aria-expanded={open} aria-controls="site-menu"
        aria-label={open ? (pt ? "Fechar menu" : "Close menu") : (pt ? "Abrir menu" : "Open menu")} onClick={() => setOpen((o) => !o)}>
        <span className={s.burger} data-open={open ? "1" : undefined} aria-hidden="true"><i /><i /></span>
      </button>
      <div ref={panel} id="site-menu" className={s.panel} data-open={open ? "1" : undefined} inert={!open}>
        <nav aria-label={pt ? "Menu" : "Menu"}>
          <Link href={`/${locale}/lab`} onClick={close}>{t.nav.lab}</Link>
          <Link href={`/${locale}/research`} onClick={close}>{t.nav.research}</Link>
          <Link href={`/${locale}#technology`} onClick={close}>{t.nav.technology}</Link>
          <Link href={`/${locale}#access`} onClick={close}>{t.footer.contact}</Link>
          <Link href={`/${locale}#audit`} onClick={close} className="btn btn-primary">{t.nav.access}</Link>
        </nav>
      </div>
    </div>
  );
}
