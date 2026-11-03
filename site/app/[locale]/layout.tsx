import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import { notFound } from "next/navigation";
import { getDict, isLocale, locales } from "@/lib/i18n";
import SiteChrome from "@/components/SiteChrome";
import "../globals.css";

const hanken = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-hanken", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400"], variable: "--font-mono", display: "swap" });

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDict(locale);
  return {
    title: { default: t.meta.title, template: "%s · DeliveryTwin AI" },
    description: t.meta.description,
    metadataBase: new URL(process.env.SITE_URL ?? (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "https://deliverytwin-puce.vercel.app")),
    alternates: { languages: { en: "/en", pt: "/pt" } },
    openGraph: { title: t.meta.title, description: t.meta.description, type: "website", url: `/${locale}`, siteName: "DeliveryTwin AI",
      locale: locale === "pt" ? "pt_BR" : "en_US" },
    twitter: { card: "summary_large_image", title: t.meta.title, description: t.meta.description },
    robots: { index: true, follow: true },
  };
}

export const viewport: Viewport = { themeColor: "#ffffff" };

export default async function LocaleLayout({ children, params }: { children: React.ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDict(locale);
  return (
    <html lang={locale === "pt" ? "pt-BR" : "en"} className={`${hanken.variable} ${mono.variable}`}>
      <body>
        <SiteChrome locale={locale} t={t}>{children}</SiteChrome>
      </body>
    </html>
  );
}
