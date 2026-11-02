// Epistemic status chip (DESIGN_SYSTEM §1–2): colour + icon + text label, never colour alone.
import s from "./ui.module.css";

export type StatusKind = "observation" | "hypothesis" | "assumption" | "experiment" | "recommendation" | "truth";

const LABEL: Record<"en" | "pt", Record<StatusKind, string>> = {
  en: { observation: "Observed", hypothesis: "Hypothesis", assumption: "Assumption", experiment: "Experiment", recommendation: "Recommendation", truth: "Hidden truth" },
  pt: { observation: "Observado", hypothesis: "Hipótese", assumption: "Suposição", experiment: "Experimento", recommendation: "Recomendação", truth: "Verdade oculta" },
};

function Icon({ kind }: { kind: StatusKind }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (kind) {
    case "observation":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><path {...p} d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" /><circle {...p} cx="8" cy="8" r="2" /></svg>;
    case "hypothesis":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><path {...p} d="M5.8 6a2.3 2.3 0 1 1 3.3 2.1c-.7.3-1.1.9-1.1 1.6v.4" /><path {...p} d="M8 12.6v.1" /></svg>;
    case "assumption":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><circle {...p} cx="8" cy="8" r="2.2" /><path {...p} d="M8 1.8v1.8M8 12.4v1.8M1.8 8h1.8M12.4 8h1.8M3.6 3.6l1.3 1.3M11.1 11.1l1.3 1.3M3.6 12.4l1.3-1.3M11.1 4.9l1.3-1.3" /></svg>;
    case "experiment":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><path {...p} d="M6 1.8h4M6.6 1.8v4.4L2.8 12.6a1.2 1.2 0 0 0 1 1.8h8.4a1.2 1.2 0 0 0 1-1.8L9.4 6.2V1.8" /><path {...p} d="M4.6 10h6.8" /></svg>;
    case "recommendation":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><path {...p} d="M2 8h11M9 4l4 4-4 4" /></svg>;
    case "truth":
      return <svg viewBox="0 0 16 16" aria-hidden="true"><rect {...p} x="3" y="7" width="10" height="7" rx="1" /><path {...p} d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>;
  }
}

export default function Status({ kind, locale = "en", label }: { kind: StatusKind; locale?: "en" | "pt"; label?: string }) {
  return (
    <span className={s.chip} data-status={kind}>
      <Icon kind={kind} />
      <span>{label ?? LABEL[locale][kind]}</span>
    </span>
  );
}

export function SourceTag({ kind, text }: { kind: "recorded" | "deterministic" | "simulated" | "precomputed"; text: string }) {
  return <span className={s.source} data-kind={kind}>{text}</span>;
}
