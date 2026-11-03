import Link from "next/link";
import type { Dict, Locale } from "@/lib/i18n";
import { CONTACT_EMAIL, HF, REPO } from "@/lib/site";
import Reveal from "./Reveal";
import { LangSwitch, NavMenu } from "./NavMenu";
import s from "./chrome.module.css";

export default function SiteChrome({ locale, t, children }: { locale: Locale; t: Dict; children: React.ReactNode }) {
  return (
    <>
      <a className={s.skip} href="#main">{locale === "pt" ? "Pular para o conteúdo" : "Skip to content"}</a>
      <div className={s.banner} role="note">
        <svg aria-hidden="true" viewBox="0 0 16 16" width="14" height="14"><path d="M8 1.5 15 14H1z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M8 6v3.5M8 11.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <span>{t.banner}</span>
      </div>
      <header className={`${s.nav} wrap`}>
        <Link href={`/${locale}`} className={s.word} aria-label={t.nav.home}>DeliveryTwin AI</Link>
        <nav aria-label="Main" className={`${s.links} ${s.desktopOnly}`}>
          <Link href={`/${locale}/lab`}>{t.nav.lab}</Link>
          <Link href={`/${locale}/research`}>{t.nav.research}</Link>
          <Link href={`/${locale}#technology`} className={s.hideSm}>{t.nav.technology}</Link>
          <LangSwitch locale={locale} t={t} />
          <Link href={`/${locale}#audit`} className="btn btn-primary">{t.nav.access}</Link>
        </nav>
        <NavMenu locale={locale} t={t} />
      </header>
      <main id="main">{children}</main>
      <footer className={`${s.footer} wrap`}>
        <span className="muted">{t.footer.what}</span>
        <span className={s.flinks}>
          <a href={`mailto:${CONTACT_EMAIL}`}>{t.footer.contact}</a>
          <a href={REPO}>{t.footer.code}</a>
          <a href={HF}>{t.footer.model}</a>
          <a href={`${REPO}/tree/main/docs/reports`}>{t.footer.reports}</a>
        </span>
        <span className={`${s.fright} muted`}>2026 · <Link href={`/${locale}/privacy`}>{t.footer.privacy}</Link></span>
      </footer>
      <Reveal />
    </>
  );
}
