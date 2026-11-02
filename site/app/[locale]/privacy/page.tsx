import { notFound } from "next/navigation";
import { getDict, isLocale } from "@/lib/i18n";

export const metadata = { title: "Privacy" };

export default async function Privacy({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDict(locale);
  return (
    <article className="wrap" style={{ maxWidth: 720, marginInline: "auto", paddingBlock: "96px 0", display: "grid", gap: 20 }}>
      <h1 style={{ fontSize: "var(--step-head)" }}>{t.privacy.title}</h1>
      {t.privacy.body.map((p) => <p key={p}>{p}</p>)}
    </article>
  );
}
