import { ImageResponse } from "next/og";
import { isLocale, locales } from "@/lib/i18n";

// Link preview card (WhatsApp, LinkedIn, Slack). Static per locale; no remote assets.
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "DeliveryTwin AI";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function Image({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const pt = isLocale(raw) && raw === "pt";
  const dots: [number, number, boolean][] = [
    [120, 90, false], [260, 160, false], [330, 70, true], [90, 250, false], [210, 300, true], [340, 260, false],
  ];
  const rests: [number, number][] = [[60, 60], [190, 120], [300, 190], [140, 220], [60, 330]];
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#ffffff", padding: 64, fontFamily: "sans-serif" }}>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", flex: 1, paddingRight: 40 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 30, color: "#232323" }}>
            <div style={{ width: 22, height: 22, background: "#232323", display: "flex" }} />
            DeliveryTwin AI
          </div>
          <div style={{ display: "flex", flexDirection: "column", fontSize: 78, lineHeight: 1.02, letterSpacing: -3, color: "#232323" }}>
            <span>{pt ? "Encontre a causa." : "Find the cause."}</span>
            <span>{pt ? "Teste a decisão." : "Test the decision."}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ fontSize: 28, color: "#5f5f5f", maxWidth: 640 }}>
              {pt ? "Decision Audit: investigue uma decisão da sua operação de entregas, com os seus dados."
                  : "Decision Audit: investigate one decision in your delivery operation, with your own data."}
            </div>
            <div style={{ display: "flex", alignSelf: "flex-start", background: "#fef3c7", color: "#78350f", fontSize: 20, padding: "6px 14px", borderRadius: 6 }}>
              {pt ? "Pesquisa em ambiente simulado · código aberto" : "Research in a simulated environment · open source"}
            </div>
          </div>
        </div>
        <div style={{ width: 400, height: 400, alignSelf: "center", display: "flex", position: "relative", background: "#f3f3f3", borderRadius: 12 }}>
          {rests.map(([x, y], i) => (
            <div key={`r${i}`} style={{ position: "absolute", left: x, top: y, width: 22, height: 22, background: "#232323", display: "flex" }} />
          ))}
          <div style={{ position: "absolute", left: 286, top: 176, width: 50, height: 50, borderRadius: 25, border: "3px solid #d03b3b", display: "flex" }} />
          {dots.map(([x, y, late], i) => (
            <div key={`d${i}`} style={{ position: "absolute", left: x, top: y, width: 12, height: 12, borderRadius: 6, background: late ? "#d03b3b" : "#232323", display: "flex" }} />
          ))}
        </div>
      </div>
    ),
    size,
  );
}
