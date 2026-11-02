"""Expert investigation traces for SFT (G4, ADR-0007).

The expert acts ONLY through the public session tools, in the same tool-call format as the
LLM agent, so a fine-tuned local model can replace the API agent. Its decisions use only
public telemetry and lab results (same logic as the rules/playbook baselines). The private
ground truth is used solely to KEEP episodes the evaluator scores as correct (rejection
sampling); it never appears inside a trace.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from deliverytwin.agent.baselines import PATHS, PROBES, REMEDY
from deliverytwin.agent.llm_agent import SYSTEM_PROMPT
from deliverytwin.agent.protocol import intervention_cost
from deliverytwin.agent.session import InvestigationSession
from deliverytwin.benchmark.evaluator import evaluate
from deliverytwin.benchmark.generator import Instance
from deliverytwin.diagnostics.rules import GLOBAL_FAMILIES, diagnose_rules

HELP = -0.03


@dataclass
class Trace:
    messages: list[dict] = field(default_factory=list)
    _n: int = 0

    def call(self, s: InvestigationSession, name: str, args: dict, thought: str) -> str:
        self._n += 1
        cid = f"call_{self._n}"
        self.messages.append({"role": "assistant", "content": thought, "tool_calls": [
            {"id": cid, "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]})
        op = {"query_orders": lambda a: s.query({"kind": "orders", **a}),
              "query_gauges": lambda a: s.query({"kind": "gauges", **a}),
              "hypothesize": s.hypothesize, "experiment": s.experiment,
              "submit": s.submit}[name]
        out = op(args)
        self.messages.append({"role": "tool", "tool_call_id": cid, "content": out})
        return out


def _eid(text: str) -> str | None:
    m = re.search(r"evidence ([qx]\d+)", text)
    return m.group(1) if m else None


def expert_episode(inst: Instance) -> tuple[Trace, InvestigationSession]:
    s = InvestigationSession(inst)
    tr = Trace(messages=[{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": s.observe()}])
    t_alert = inst.private.alert["t"]
    since = max(0.0, round(t_alert - 90, 0))
    recent = max(0.0, round(t_alert - 60, 0))
    ev = []
    out = tr.call(s, "query_orders", {"window_minutes": 30, "group_by": "none", "since": since},
                  "First, the overall order picture around the alert.")
    ev.append(_eid(out))
    if s.tel.profile == "full":
        for metric, why, w, start in (
                ("couriers_online", "Is courier supply intact?", 30, since),
                ("dispatch_queue", "Is the dispatch queue building up?", 30, since),
                ("kitchen_load", "Is any kitchen overloaded right now?", 60, recent)):
            out = tr.call(s, "query_gauges", {"metric": metric, "window_minutes": w,
                                              "since": start}, why)
            ev.append(_eid(out))
    else:
        out = tr.call(s, "query_orders", {"window_minutes": 60, "group_by": "restaurant",
                                          "since": recent},
                      "Only customer data here; check whether one restaurant concentrates the problem.")
        ev.append(_eid(out))
    ev = [e for e in ev if e]
    d = diagnose_rules(s.tel, t_alert)
    if d.cause:
        alt = "dispatcher_saturation" if d.cause != "dispatcher_saturation" else "courier_scarcity"
        tr.call(s, "hypothesize", {"hypotheses": [
            {"family": d.cause, **({"scope": d.scope} if d.scope else {}),
             "rationale": f"Observed signals point here: {d.evidence}", "evidence_ids": ev},
            {"family": alt, "rationale": "Main alternative explanation of the same symptoms; "
                                         "the evidence above does not support it.",
             "evidence_ids": ev}]},
            "Two competing hypotheses; the data already favours the first.")
        rep = {"cause": d.cause, "confidence": 0.75, "evidence_ids": ev,
               "causal_path": [list(e) for e in PATHS[d.cause]],
               "summary": f"Observational evidence identifies {d.cause}."}
        if d.scope:
            rep["scope"] = d.scope
        if REMEDY.get(d.cause) is not None:
            rep["recommendation"] = REMEDY[d.cause].model_dump()
        tr.call(s, "submit", rep, "The observations are sufficient; submitting.")
        return tr, s
    alive = set(d.unresolved_between) or set(GLOBAL_FAMILIES)
    tr.call(s, "hypothesize", {"hypotheses": [
        {"family": f, "rationale": "Fits the broad degradation; not separable from data.",
         "evidence_ids": ev} for f in sorted(alive)]},
        "Several causes fit equally well; experiments are needed.")
    helped = None
    while len(alive) > 1 and s.experiments_used < s.budgets.max_experiments:
        options = []
        for name, (iv, helps) in PROBES.items():
            split = alive & helps
            if split and split != alive:
                options.append((intervention_cost(iv), name, iv, helps))
        if not options:
            break
        cost, name, iv, helps = min(options, key=lambda o: o[:2])
        if s.units_used + cost > s.budgets.experiment_units:
            break
        target = ", ".join(sorted(helps))
        out = tr.call(s, "experiment", {"interventions": [iv.model_dump()], "replicas": 3,
                                        "rationale": f"helps only if {target}"},
                      f"Test {iv.kind}: it helps only if the cause is {target}.")
        e = _eid(out)
        if e:
            ev.append(e)
        m = re.search(r"diff ([+-]\d+\.\d+), 95% CI", out)
        if not m:
            break
        if float(m.group(1)) <= HELP:
            alive &= helps
            helped = iv
        else:
            alive -= helps
    if len(alive) == 1:
        cause = next(iter(alive))
        rep = {"cause": cause, "confidence": 0.8, "evidence_ids": ev,
               "causal_path": [list(e) for e in PATHS[cause]],
               "summary": "Experiments eliminated the alternatives."}
        rec = helped or REMEDY.get(cause)
        if rec is not None:
            rep["recommendation"] = rec.model_dump()
        tr.call(s, "submit", rep, "Only one hypothesis is consistent with the experiments.")
    else:
        tr.call(s, "submit", {"cause": None, "unresolved_between": sorted(alive),
                              "confidence": 0.4, "evidence_ids": ev,
                              "summary": "Budget did not allow separating the remaining causes."},
                "The remaining causes cannot be separated within budget.")
    return tr, s


def keep(inst: Instance, s: InvestigationSession) -> bool:
    """Rejection sampling on the evaluator: keep correct diagnoses only."""
    ev = evaluate(s.bundle({"name": "expert"}), inst, measure_recommendation=False)
    return bool(ev["exact"])
