import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { isLocale } from "@/lib/i18n";
import { labDicts } from "@/lib/lab-i18n";
import { FLAGSHIP, loadIndex, loadScenario } from "@/lib/data";
import LabApp from "@/components/lab/LabApp";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  return { title: labDicts[locale].title, description: labDicts[locale].lead };
}

export default async function LabPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const [index, initial] = await Promise.all([loadIndex(), loadScenario(FLAGSHIP)]);
  return <LabApp index={index} initial={initial} locale={locale} />;
}
