import type { Locale } from "./i18n";

const FAMILY: Record<string, { en: string; pt: string }> = {
  dispatch_error_surge: { en: "Dispatch error surge", pt: "Surto de erros de despacho" },
  dispatch_latency: { en: "Dispatch latency", pt: "Latência de despacho" },
  courier_scarcity: { en: "Courier scarcity", pt: "Falta de entregadores" },
  dispatcher_saturation: { en: "Dispatcher saturation", pt: "Despachante saturado" },
  restaurant_bottleneck: { en: "Restaurant bottleneck", pt: "Gargalo de restaurante" },
};

export const familyName = (f: string | null | undefined, l: Locale) =>
  f ? FAMILY[f]?.[l] ?? f : l === "pt" ? "Sem diagnóstico (abstenção)" : "No diagnosis (abstained)";

const ARM: Record<string, { en: string; pt: string }> = {
  placebo: { en: "Placebo (changes nothing)", pt: "Placebo (não muda nada)" },
  add_couriers_5: { en: "+5 couriers", pt: "+5 entregadores" },
  add_couriers_10: { en: "+10 couriers", pt: "+10 entregadores" },
  add_couriers_20: { en: "+20 couriers", pt: "+20 entregadores" },
  workers_3: { en: "3 dispatcher workers", pt: "3 trabalhadores no despachante" },
  workers_4: { en: "4 dispatcher workers", pt: "4 trabalhadores no despachante" },
  workers_6: { en: "6 dispatcher workers", pt: "6 trabalhadores no despachante" },
  workers_8: { en: "8 dispatcher workers", pt: "8 trabalhadores no despachante" },
  "retry_backoff_0.5": { en: "Retry after 0.5 min", pt: "Repetir após 0,5 min" },
  "retry_backoff_0.2": { en: "Retry after 0.2 min", pt: "Repetir após 0,2 min" },
  "retry_backoff_0.05": { en: "Retry after 0.05 min", pt: "Repetir após 0,05 min" },
  policy_eta_aware: { en: "ETA-aware dispatch policy", pt: "Política de despacho por ETA" },
  "admission_0.9": { en: "Accept 90% of orders", pt: "Aceitar 90% dos pedidos" },
  "admission_0.8": { en: "Accept 80% of orders", pt: "Aceitar 80% dos pedidos" },
};
export const armName = (k: string, l: Locale) => ARM[k]?.[l] ?? k;
