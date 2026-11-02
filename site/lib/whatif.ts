// Parse a plain-language decision into one of the simulator's precomputed lab arms.
// Only single interventions the simulator models are accepted; values snap to the nearest
// precomputed level and the snap is reported. Removals, compound requests and the policy the
// city already uses are refused with a reason, never silently reinterpreted.

export type Parsed =
  | { ok: true; key: string; kind: string; asked?: number; used?: number }
  | { ok: false; reason: "unknown" | "below_constraint" | "compound" | "removal" | "current_policy" };

const LEVELS: Record<string, number[]> = {
  add_couriers: [5, 10, 20],
  workers: [3, 4, 6, 8],
  retry_backoff: [0.5, 0.2, 0.05],
  admission: [0.9, 0.8],
};

function nearest(xs: number[], v: number) {
  return xs.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));
}

export function parseWhatIf(raw: string): Parsed {
  const s = raw.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  if (!s) return { ok: false, reason: "unknown" };
  if (/placebo|nothing|nada/.test(s)) return { ok: true, key: "placebo", kind: "placebo" };

  const has = {
    couriers: /courier|driver|rider|entregador|motoboy/.test(s),
    workers: /worker|trabalhador|dispatcher|despach/.test(s) && !/policy|politica/.test(s),
    retry: /retry|backoff|tentativa|espera/.test(s),
    policy: /eta|policy|politica|nearest|mais proximo/.test(s),
    admission: /accept|admi|aceit|reject|turn away|recus|rejeit|%/.test(s),
  };
  const n = Object.values(has).filter(Boolean).length;
  if (n > 1) return { ok: false, reason: "compound" };
  if (/\b(remove|fewer|less|reduce|cut|lay off|menos|tirar|remover|reduzir|cortar)\b/.test(s) && !has.admission) {
    return { ok: false, reason: "removal" };
  }

  const m = s.match(/(\d+(?:[.,]\d+)?)/)?.[1];
  const v = m ? Number(m.replace(",", ".")) : null;

  if (has.retry) {
    const x = v ?? 0.2;
    const used = nearest(LEVELS.retry_backoff, x);
    return { ok: true, key: `retry_backoff_${used}`, kind: "set_retry_backoff", asked: x, used };
  }
  if (has.policy) {
    if (/nearest|mais proximo/.test(s) && !/eta/.test(s)) return { ok: false, reason: "current_policy" };
    return { ok: true, key: "policy_eta_aware", kind: "set_dispatch_policy" };
  }
  if (has.admission) {
    let rate = v == null ? 0.9 : v > 1 ? v / 100 : v;
    if (/reject|turn away|recus|rejeit/.test(s)) rate = 1 - rate;
    if (rate < 0.8) return { ok: false, reason: "below_constraint" };
    const used = nearest(LEVELS.admission, Math.min(rate, 0.9));
    return { ok: true, key: `admission_${used}`, kind: "set_admission_rate", asked: rate, used };
  }
  if (has.workers) {
    const w = v ?? 6;
    const used = nearest(LEVELS.workers, w);
    return { ok: true, key: `workers_${used}`, kind: "set_dispatcher_workers", asked: w, used };
  }
  if (has.couriers) {
    const c = v ?? 10;
    const used = nearest(LEVELS.add_couriers, c);
    return { ok: true, key: `add_couriers_${used}`, kind: "add_couriers", asked: c, used };
  }
  return { ok: false, reason: "unknown" };
}
