import type { Scenario } from "./types";

// Re-bin the observed telemetry into wider windows; a window is shown only when at least
// `minResolved` of its orders have a known outcome (recent orders are still open).
// Windows whose outcomes are not yet mostly known are left blank: dividing by the known
// outcomes alone would make recent windows look better than they are (Codex site review #6).
export function badRate(tel: Scenario["telemetry"], factor = 3, minResolved = 6, minCoverage = 0.9) {
  const x: number[] = [], y: (number | null)[] = [];
  for (let i = 0; i < tel.t.length; i += factor) {
    let r = 0, b = 0, c = 0;
    for (let j = i; j < Math.min(i + factor, tel.t.length); j++) { r += tel.resolved[j]; b += tel.bad[j]; c += tel.created[j]; }
    x.push(tel.t[i]);
    y.push(r >= minResolved && c > 0 && r / c >= minCoverage ? b / r : null);
  }
  return { x, y };
}
