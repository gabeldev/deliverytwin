"""Isolated evaluator (ADR-0006): the only component that reads the private record.

Scores a sealed bundle against the hidden ground truth. Deterministic; no LLM judge.
"""

from __future__ import annotations

import re

from deliverytwin.agent.protocol import Report
from deliverytwin.agent.session import run_lab_experiment
from deliverytwin.benchmark.generator import Instance

_SCOPED = re.compile(r"\[.*\]$")
EVAL_REPLICA_OFFSET = 1000


def _node(n: str) -> str:
    return _SCOPED.sub("", n)


def path_f1(claimed: list[tuple[str, str]], true: list[tuple[str, str]]) -> float:
    c = {(_node(a), _node(b)) for a, b in claimed}
    t = {(_node(a), _node(b)) for a, b in true}
    if not c or not t:
        return 0.0
    tp = len(c & t)
    if tp == 0:
        return 0.0
    prec, rec = tp / len(c), tp / len(t)
    return 2 * prec * rec / (prec + rec)


def evaluate(bundle: dict, instance: Instance, measure_recommendation: bool = True,
             replicas: int = 3) -> dict:
    p = instance.private
    rep = Report.model_validate(bundle["report"]) if bundle.get("report") else None
    evidence_ids = {m.group(0) for t in bundle["transcript"] if t["ok"]
                    for m in re.finditer(r"\b[qx]\d+\b", t["response"])
                    if t["response"].startswith("[evidence")}
    out = {
        "dataset_id": bundle["dataset_id"],
        "level": p.level,
        "family": p.family,
        "submitted": rep is not None,
        "used": bundle["used"],
    }
    if rep is None:
        out.update(family_correct=False, exact=False, abstained=False,
                   abstained_with_truth=False, path_f1=0.0, evidence_valid=0.0)
        return out
    family_ok = rep.cause == p.family
    scope_ok = p.family != "restaurant_bottleneck" or rep.scope == p.restaurant_token
    cited = list(rep.evidence_ids)
    out.update(
        cause=rep.cause,
        scope=rep.scope,
        unresolved_between=sorted(rep.unresolved_between),
        family_correct=family_ok,
        exact=family_ok and scope_ok,
        abstained=rep.cause is None,
        abstained_with_truth=rep.cause is None and p.family in rep.unresolved_between,
        path_f1=round(path_f1(list(rep.causal_path), p.causal_dag), 3),
        evidence_valid=(sum(e in evidence_ids for e in cited) / len(cited)) if cited else 0.0,
        confidence=rep.confidence,
        # Calibration only for committed diagnoses; abstentions/non-answers are reported as
        # coverage instead (Codex review G3: a forced null with confidence 0 scored Brier 0).
        brier=(round((rep.confidence - float(family_ok and scope_ok)) ** 2, 4)
               if rep.cause is not None else None),
    )
    if measure_recommendation and rep.recommendation is not None:
        # Futures disjoint from the investigation's replicas (ids 1..5), shared across
        # agents, so a recommendation is not scored on the samples used to pick it.
        res = run_lab_experiment(instance, (rep.recommendation,), replicas,
                                 replica_offset=EVAL_REPLICA_OFFSET)
        out["recommendation"] = rep.recommendation.kind
        out["recommendation_diff_bad"] = round(res["diff_bad"], 4) if res["ok"] else None
    return out


def bundle_leaks(bundle_text: str, instance: Instance) -> list[str]:
    """Private values that must never appear in a sealed bundle."""
    p = instance.private
    secrets = [str(p.world_seed), str(p.obfuscation_salt), str(p.noise_seed), p.canary,
               p.instance_id]
    return [s for s in secrets if s and s in bundle_text]
