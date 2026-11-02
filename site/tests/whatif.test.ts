import { test } from "node:test";
import assert from "node:assert/strict";
import { parseWhatIf } from "../lib/whatif.ts";

test("couriers snap to precomputed levels and report the snap", () => {
  assert.deepEqual(parseWhatIf("add 10 couriers"), { ok: true, key: "add_couriers_10", kind: "add_couriers", asked: 10, used: 10 });
  const r = parseWhatIf("add 12 couriers");
  assert.ok(r.ok && r.key === "add_couriers_10" && r.asked === 12);
});
test("portuguese phrasing works", () => {
  const r = parseWhatIf("contratar 20 entregadores");
  assert.ok(r.ok && r.key === "add_couriers_20");
  const w = parseWhatIf("6 trabalhadores no despachante");
  assert.ok(w.ok && w.key === "workers_6");
});
test("retry backoff and policy", () => {
  const r = parseWhatIf("retry failed dispatches after 0.2 min");
  assert.ok(r.ok && r.key === "retry_backoff_0.2");
  assert.ok((parseWhatIf("switch to eta-aware policy") as { key: string }).key === "policy_eta_aware");
});
test("admission below the business constraint is refused, not run", () => {
  assert.deepEqual(parseWhatIf("accept only 70% of orders"), { ok: false, reason: "below_constraint" });
  const r = parseWhatIf("accept only 90% of orders");
  assert.ok(r.ok && r.key === "admission_0.9");
  const j = parseWhatIf("reject 10% of orders");
  assert.ok(j.ok && j.key === "admission_0.9");
});
test("unknown requests are reported, not guessed", () => {
  assert.deepEqual(parseWhatIf("make it faster"), { ok: false, reason: "unknown" });
  assert.deepEqual(parseWhatIf(""), { ok: false, reason: "unknown" });
  assert.ok((parseWhatIf("a placebo") as { key: string }).key === "placebo");
});

test("removals, compound requests and the current policy are refused (Codex site review #5)", () => {
  assert.deepEqual(parseWhatIf("remove 10 couriers"), { ok: false, reason: "removal" });
  assert.deepEqual(parseWhatIf("nearest policy"), { ok: false, reason: "current_policy" });
  assert.deepEqual(parseWhatIf("add 10 couriers and 8 workers"), { ok: false, reason: "compound" });
  assert.ok((parseWhatIf("6 dispatcher workers") as { key: string }).key === "workers_6");
});
