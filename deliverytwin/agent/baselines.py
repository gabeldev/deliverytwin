"""Non-LLM agents that use exactly the same session protocol as an LLM agent.

- rules: expert rules over the public telemetry (G2 baseline), no experiments.
- playbook: knowledge-based interventional separation (ISS-style). Starting from the rules'
  candidate set, it repeatedly runs the cheapest intervention whose *expected* effect
  differs among surviving hypotheses (from a hand-written effect table), keeps the
  hypotheses consistent with the observed effect, and stops when one survives or the
  budget ends. It is the floor an experimenting LLM agent must beat.
"""

from __future__ import annotations

import re

from deliverytwin.agent.protocol import intervention_cost
from deliverytwin.agent.session import InvestigationSession
from deliverytwin.diagnostics.rules import GLOBAL_FAMILIES, diagnose_rules
from deliverytwin.simulation.interventions import (
    AddCouriers,
    SetDispatcherWorkers,
    SetRetryBackoff,
)

# Expected effect of each probe on the bad-order rate under each family: True = helps.
PROBES = {
    "retry_backoff": (SetRetryBackoff(minutes=0.2), {"dispatch_error_surge"}),
    "workers": (SetDispatcherWorkers(workers=6), {"dispatcher_saturation"}),
    "couriers": (AddCouriers(count=10), {"courier_scarcity"}),
}
REMEDY = {
    "dispatch_error_surge": SetRetryBackoff(minutes=0.2),
    "dispatcher_saturation": SetDispatcherWorkers(workers=6),
    "courier_scarcity": AddCouriers(count=10),
}
HELP_THRESHOLD = -0.03  # diff in bad-order rate counted as "helped"

PATHS = {
    "courier_scarcity": [("courier_supply", "idle_couriers"), ("idle_couriers", "assignment_delay"),
                         ("assignment_delay", "delivery_time"), ("delivery_time", "late_rate")],
    "dispatcher_saturation": [("dispatch_service_time", "dispatch_queue"),
                              ("dispatch_queue", "assignment_delay"),
                              ("assignment_delay", "delivery_time"), ("delivery_time", "late_rate")],
    "dispatch_error_surge": [("dispatch_errors", "dispatch_retries"),
                             ("dispatch_retries", "assignment_delay"),
                             ("assignment_delay", "delivery_time"), ("delivery_time", "late_rate")],
    "dispatch_latency": [("dependency_latency", "dispatch_hang"),
                         ("dispatch_hang", "assignment_delay"),
                         ("assignment_delay", "delivery_time"), ("delivery_time", "late_rate")],
    "restaurant_bottleneck": [("prep_time", "ready_delay"), ("ready_delay", "delivery_time"),
                              ("delivery_time", "late_rate")],
}


def _report(cause, scope=None, unresolved=(), evidence=(), recommendation=None, confidence=0.5,
            summary=""):
    rep = {"cause": cause, "scope": scope, "unresolved_between": list(unresolved),
           "causal_path": PATHS.get(cause, []) if cause else [],
           "evidence_ids": list(evidence), "confidence": confidence, "summary": summary}
    if recommendation is not None:
        rep["recommendation"] = recommendation.model_dump()
    return rep


def run_rules_agent(s: InvestigationSession) -> dict:
    s.observe()
    d = diagnose_rules(s.tel, s.instance.private.alert["t"])
    if d.cause:
        s.submit(_report(d.cause, d.scope, confidence=0.7, recommendation=REMEDY.get(d.cause),
                         summary=f"rules: {d.evidence}"))
    else:
        s.submit(_report(None, unresolved=d.unresolved_between, confidence=0.5,
                         summary="rules: cannot separate global causes from this profile"))
    return {"name": "rules"}


def run_playbook_agent(s: InvestigationSession) -> dict:
    s.observe()
    d = diagnose_rules(s.tel, s.instance.private.alert["t"])
    if d.cause:
        s.submit(_report(d.cause, d.scope, confidence=0.7, recommendation=REMEDY.get(d.cause),
                         summary=f"rules: {d.evidence}"))
        return {"name": "playbook"}
    alive = set(d.unresolved_between) or set(GLOBAL_FAMILIES)
    evidence, helped = [], None
    while len(alive) > 1 and s.experiments_used < s.budgets.max_experiments:
        options = []
        for name, (iv, helps) in PROBES.items():
            split = alive & helps
            if split and split != alive:
                options.append((intervention_cost(iv), name, iv, helps))
        if not options:
            break
        cost, _, iv, helps = min(options, key=lambda o: o[:2])
        if s.units_used + cost > s.budgets.experiment_units:
            break
        text = s.experiment({"interventions": [iv.model_dump()], "replicas": 3,
                             "rationale": "separate surviving hypotheses"})
        m = re.search(r"diff ([+-]\d+\.\d+), 95% CI", text)
        eid = re.search(r"evidence (x\d+)", text)
        if not m:
            break
        if eid:
            evidence.append(eid.group(1))
        if float(m.group(1)) <= HELP_THRESHOLD:
            alive &= helps
            helped = iv
        else:
            alive -= helps
    if len(alive) == 1:
        cause = next(iter(alive))
        s.submit(_report(cause, evidence=evidence, confidence=0.8,
                         recommendation=helped or REMEDY.get(cause),
                         summary="playbook: interventional separation"))
    else:
        s.submit(_report(None, unresolved=sorted(alive), evidence=evidence, confidence=0.4,
                         summary="playbook: budget or probes exhausted"))
    return {"name": "playbook"}
