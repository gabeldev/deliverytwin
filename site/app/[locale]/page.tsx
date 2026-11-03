import { notFound } from "next/navigation";
import { getDict, isLocale } from "@/lib/i18n";
import { FLAGSHIP, WHATIF, loadIndex, loadResearch, loadScenario, loadTruth } from "@/lib/data";
import HeroReel from "@/components/home/HeroReel";
import WhatIf from "@/components/home/WhatIf";
import HowItWorks from "@/components/home/HowItWorks";
import { Findings, OpenTiles, Receipt, Technology } from "@/components/home/Sections";
import Faq from "@/components/home/Faq";
import Contact from "@/components/home/Contact";
import Offer from "@/components/home/Offer";

export default async function Home({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDict(locale);
  const [sc, truth, wi, research, index] = await Promise.all([loadScenario(FLAGSHIP), loadTruth(FLAGSHIP), loadScenario(WHATIF), loadResearch(), loadIndex()]);
  return (
    <>
      <HeroReel sc={sc} truth={truth} t={t} locale={locale} />
      <WhatIf lab={wi.lab.A} scenarioId={wi.id} t={t} locale={locale} commit={index.commit} />
      <HowItWorks sc={sc} truth={truth} t={t} locale={locale} />
      <Receipt r={research} t={t} locale={locale} />
      <Findings r={research} t={t} locale={locale} />
      <Technology sc={sc} truth={truth} t={t} locale={locale} />
      <OpenTiles t={t} />
      <Offer t={t} />
      <Faq t={t} />
      <Contact t={t} locale={locale} />
    </>
  );
}
