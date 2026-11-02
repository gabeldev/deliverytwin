"""Investigation session: the orchestrator between an agent and a benchmark instance.

The agent-facing surface is five operations (ADR-0004): observe, query, hypothesize,
experiment, submit. Everything is validated and budgeted here; responses are plain text
with evidence ids. The private record is used only to run the lab (mode A: forks of the
true world, ADR-0003) and is never included in any response or in the sealed bundle.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter, ValidationError

from deliverytwin.agent.protocol import (
    ExperimentSpec,
    HypothesisSet,
    Query,
    Report,
    intervention_cost,
)
from deliverytwin.agent.queries import run_gauges_query, run_orders_query
from deliverytwin.benchmark.generator import LEVELS, Instance
from deliverytwin.core.rng import EventRng, derive_seed
from deliverytwin.counterfactual.twin import twin_config, twin_fault, twin_seed
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatchErrorSurge,
    DispatcherSaturation,
    DispatchLatency,
    RestaurantBottleneck,
)
from deliverytwin.simulation.interventions import Branch, NoOp
from deliverytwin.simulation.kpis import demand_cohort_metrics
from deliverytwin.simulation.world import World


def _why(e: ValidationError) -> str:
    """First validation error with its field path, so the agent can fix the call."""
    err = e.errors()[0]
    loc = ".".join(str(x) for x in err.get("loc", ())) or "(root)"
    return f"{loc}: {err['msg']}"

FAULT_CLS = {"courier_scarcity": CourierScarcity, "dispatcher_saturation": DispatcherSaturation,
             "restaurant_bottleneck": RestaurantBottleneck,
             "dispatch_error_surge": DispatchErrorSurge, "dispatch_latency": DispatchLatency}

LAB_COHORT = 90.0      # orders accepted in [t0, t0 + LAB_COHORT)
LAB_FOLLOW_UP = 150.0  # evaluated at t0 + LAB_FOLLOW_UP (>= cohort + promise)


PARTIAL_GAUGES = ("orders_active", "kitchen_load")
PROFILE_TEXT = {
    "full": "orders + operational gauges",
    "partial": "orders + only these gauges: " + ", ".join(PARTIAL_GAUGES)
               + "; fleet and dispatch gauges UNAVAILABLE",
    "customer": "customer-visible order data only; gauges UNAVAILABLE",
}
LAB_TEXT = {
    "A": "",  # unchanged L0-L2 text (G4 SFT traces were rendered with it)
    "B": "Lab: experiments run on a TWIN model of the operation, an imperfect copy whose "
         "parameters may differ from reality; treat its results as approximate.\n",
}


class SessionError(Exception):
    """A rejected agent action (returned to the agent as a tool error, never raised to it)."""


@dataclass
class Budgets:
    max_queries: int = 25
    max_experiments: int = 4
    experiment_units: float = 10.0


@dataclass
class InvestigationSession:
    instance: Instance
    budgets: Budgets | None = None       # None: the level's budgets (L4 is tighter)
    twin_delta: float | None = None      # None: the level's lab (mode B only on L6)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    queries_used: int = 0
    experiments_used: int = 0
    units_used: float = 0.0
    report: Report | None = None
    _evidence: int = 0

    def __post_init__(self):
        spec = LEVELS.get(self.instance.private.level, {})
        if self.budgets is None:
            self.budgets = Budgets(**spec.get("budgets", {}))
        if self.twin_delta is None:
            self.twin_delta = spec.get("twin_delta")

    @property
    def lab_mode(self) -> str:
        return "A" if self.twin_delta is None else "B"

    # -- helpers ----------------------------------------------------------------------

    @property
    def tel(self):
        return self.instance.public

    def _eid(self, prefix: str) -> str:
        self._evidence += 1
        return f"{prefix}{self._evidence}"

    def _log(self, op: str, args: Any, response: str, ok: bool = True) -> str:
        self.transcript.append({"op": op, "args": args, "response": response, "ok": ok})
        return response

    @property
    def sealed(self) -> bool:
        return self.report is not None

    def _check_open(self):
        if self.sealed:
            raise SessionError("session already submitted")

    # -- operations ---------------------------------------------------------------------

    def observe(self) -> str:
        p = self.instance.private
        tel = self.tel
        zones = [e.token for e in tel.entities if e.kind == "zone"]
        rests = [f"{e.token}(zone {e.zone})" for e in tel.entities if e.kind == "restaurant"]
        text = (
            "SIMULATED ENVIRONMENT - synthetic delivery operation, not a real company.\n"
            f"Incident alert at t={p.alert['t']:.1f} min on series '{p.alert['series']}' "
            f"(metric {p.alert['metric']}, score {p.alert.get('score')}).\n"
            f"Telemetry observed up to t={tel.observed_until:.1f}; profile '{tel.profile}' "
            f"({PROFILE_TEXT[tel.profile]}).\n"
            f"{LAB_TEXT[self.lab_mode]}"
            f"{LEVELS.get(p.level, {}).get('task_note', '')}"
            f"Promised delivery time: {tel.promised_delivery_minutes:.0f} min.\n"
            f"Zones: {', '.join(zones)}\nRestaurants: {', '.join(rests)}\n"
            f"Budgets: {self.budgets.max_queries} queries, {self.budgets.max_experiments} "
            f"experiments, {self.budgets.experiment_units:.1f} experiment cost units.\n"
            "Intervention costs: set_dispatcher_workers 0.5/worker, add_couriers 0.2/courier, "
            "set_admission_rate 10*(1-rate), set_dispatch_policy 1, set_retry_backoff 1.\n"
            "Fault taxonomy: courier_scarcity, dispatcher_saturation, restaurant_bottleneck, "
            "dispatch_error_surge, dispatch_latency."
        )
        return self._log("observe", {}, text)

    def query(self, raw: dict) -> str:
        self._check_open()
        try:
            q = TypeAdapter(Query).validate_python(raw)
        except ValidationError as e:
            return self._log("query", raw, f"ERROR invalid query: {_why(e)}", ok=False)
        if q.kind == "gauges" and (self.tel.profile == "customer" or not self.tel.gauges):
            return self._log("query", raw, "ERROR gauges are not available in this "
                             "observability profile (customer-visible orders only)", ok=False)
        if q.kind == "gauges" and not any(g.metric == q.metric for g in self.tel.gauges):
            return self._log("query", raw, f"ERROR gauge '{q.metric}' is not available in "
                             f"this observability profile ({PROFILE_TEXT[self.tel.profile]})",
                             ok=False)
        if self.queries_used >= self.budgets.max_queries:
            return self._log("query", raw, "ERROR query budget exhausted", ok=False)
        self.queries_used += 1
        text, _ = (run_orders_query if q.kind == "orders" else run_gauges_query)(self.tel, q)
        eid = self._eid("q")
        return self._log("query", q.model_dump(), f"[evidence {eid}]\n{text}")

    def hypothesize(self, raw: dict) -> str:
        self._check_open()
        try:
            hs = HypothesisSet.model_validate(raw)
        except ValidationError as e:
            return self._log("hypothesize", raw, f"ERROR invalid hypotheses: {_why(e)}", ok=False)
        for h in hs.hypotheses:
            self.hypotheses.append(h.model_dump())
        return self._log("hypothesize", hs.model_dump(),
                         f"recorded {len(hs.hypotheses)} hypotheses")

    def experiment(self, raw: dict) -> str:
        self._check_open()
        try:
            spec = ExperimentSpec.model_validate(raw)
        except ValidationError as e:
            return self._log("experiment", raw, f"ERROR invalid experiment: {_why(e)}", ok=False)
        cost = sum(intervention_cost(iv) for iv in spec.interventions)
        if self.experiments_used >= self.budgets.max_experiments:
            return self._log("experiment", raw, "ERROR experiment budget exhausted", ok=False)
        if self.units_used + cost > self.budgets.experiment_units + 1e-9:
            return self._log("experiment", raw,
                             f"ERROR cost {cost:.2f} exceeds remaining "
                             f"{self.budgets.experiment_units - self.units_used:.2f} units", ok=False)
        self.experiments_used += 1
        self.units_used += cost
        res = run_lab_experiment(self.instance, spec.interventions, spec.replicas,
                                 twin_delta=self.twin_delta)
        if not res["ok"]:
            return self._log("experiment", spec.model_dump(),
                             f"ERROR experiment produced no data: {res['reason']} "
                             f"(cost {cost:.2f} units was charged)", ok=False)
        eid = self._eid("x")
        text = (f"[evidence {eid}] {'twin ' if self.lab_mode == 'B' else ''}lab "
                f"experiment from t={res['t0']:.1f}: "
                f"{', '.join(iv.kind for iv in spec.interventions)} vs control, "
                f"{spec.replicas} paired replicas, cohort = all orders created in the next "
                f"{LAB_COHORT:.0f} min (rejected count as bad), outcomes at "
                f"+{LAB_FOLLOW_UP:.0f} min; 95% CI is Student-t.\n"
                f"bad_rate control {res['control_bad']:.3f} -> treatment {res['treatment_bad']:.3f} "
                f"(diff {res['diff_bad']:+.3f}, 95% CI {res['ci_bad'][0]:+.3f}..{res['ci_bad'][1]:+.3f})\n"
                f"mean click-to-door (penalised) control {res['control_time']:.1f} -> treatment "
                f"{res['treatment_time']:.1f} min (diff {res['diff_time']:+.1f}, 95% CI "
                f"{res['ci_time'][0]:+.1f}..{res['ci_time'][1]:+.1f})\n"
                f"share of orders rejected: control {res['control_rejected']:.2f}, "
                f"treatment {res['treatment_rejected']:.2f}\n"
                f"cost {cost:.2f} units; remaining {self.budgets.experiment_units - self.units_used:.2f}")
        return self._log("experiment", spec.model_dump(), text)

    def submit(self, raw: dict) -> str:
        self._check_open()
        try:
            rep = Report.model_validate(raw)
        except ValidationError as e:
            return self._log("submit", raw, f"ERROR invalid report: {_why(e)}", ok=False)
        self.report = rep
        return self._log("submit", rep.model_dump(), "report sealed")

    # -- sealed bundle (no private data) --------------------------------------------------

    def bundle(self, agent: dict) -> dict:
        return {
            "dataset_id": self.tel.dataset_id,
            "profile": self.tel.profile,
            "agent": agent,
            "budgets": vars(self.budgets),
            "used": {"queries": self.queries_used, "experiments": self.experiments_used,
                     "units": self.units_used},
            "hypotheses": self.hypotheses,
            "transcript": self.transcript,
            "report": self.report.model_dump() if self.report else None,
        }


def instance_faults(instance: Instance) -> tuple:
    p = instance.private
    out = []
    # Replay in the injection order of the observed world (fault-indexed RNG keys).
    for spec in (p.injected_faults or (p.fault, *p.extra_faults)):
        out.append(FAULT_CLS[spec["family"]](**{k: v for k, v in spec.items() if k != "family"}))
    return tuple(out)


def _world_for_lab(instance: Instance, t0: float, twin_delta: float | None = None) -> World:
    """Mode A (twin_delta None): the true world. Mode B: an imperfect twin (twin.py)."""
    p = instance.private
    faults = instance_faults(instance)
    cfg = instance.world_config.model_copy(
        update={"horizon_minutes": math.ceil(t0 + LAB_FOLLOW_UP) + 1})
    if twin_delta is None:
        return World(cfg, p.world_seed, faults=faults, noise=instance.noise)
    seed = twin_seed(p.world_seed)
    rng = EventRng(derive_seed(seed, "perturb"), strict=False)
    tcfg = twin_config(cfg, twin_delta, rng)
    tfaults = tuple(twin_fault(f, twin_delta, rng, str(i)) for i, f in enumerate(faults))
    return World(tcfg, seed, faults=tfaults, noise=instance.noise)


# Two-sided 95% Student-t critical values by degrees of freedom (replicas - 1).
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
       9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
       16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093}


def replica_metrics(instance: Instance, interventions, replica_ids,
                    twin_delta: float | None = None) -> tuple[list[dict], list[dict], float]:
    """Per-replica demand-cohort metrics for control (NoOp) and treatment arms."""
    t0 = instance.private.alert["t"]
    base = _world_for_lab(instance, t0, twin_delta)
    P = instance.world_config.promised_delivery_minutes
    hi, now = t0 + LAB_COHORT, t0 + LAB_FOLLOW_UP
    ctrl_m, trt_m = [], []
    for r in replica_ids:
        ctrl = base.fork_at(Branch(t0=t0, interventions=(NoOp(),), replica=r)).run()
        trt = base.fork_at(Branch(t0=t0, interventions=tuple(interventions), replica=r)).run()
        ctrl_m.append(demand_cohort_metrics(ctrl.log, P, t0, hi, now))
        trt_m.append(demand_cohort_metrics(trt.log, P, t0, hi, now))
    return ctrl_m, trt_m, t0


def t_ci(d: list[float]) -> tuple[float, tuple[float, float]]:
    m = statistics.fmean(d)
    if len(d) < 2:
        return m, (math.nan, math.nan)
    h = T95.get(len(d) - 1, 1.96) * statistics.stdev(d) / math.sqrt(len(d))
    return m, (m - h, m + h)


def run_lab_experiment(instance: Instance, interventions, replicas: int,
                       replica_offset: int = 0, twin_delta: float | None = None) -> dict:
    """Paired forks at the alert time: of the true world (mode A) or of a twin (mode B).

    Cohort = ALL demand created in [t0, t0 + LAB_COHORT) (rejected orders count as bad);
    small-sample Student-t intervals. `replica_offset` lets the evaluator use futures
    disjoint from the investigation's (Codex review G3)."""
    ids = range(1 + replica_offset, replicas + 1 + replica_offset)
    ctrl_m, trt_m, t0 = replica_metrics(instance, interventions, ids, twin_delta)
    if any(m["n"] == 0 for m in ctrl_m + trt_m):
        return {"t0": t0, "ok": False, "reason": "no demand in the cohort window"}
    db, ci_b = t_ci([b["bad_rate"] - a["bad_rate"] for a, b in zip(ctrl_m, trt_m, strict=True)])
    dt, ci_t = t_ci([b["penalized_time"] - a["penalized_time"]
                     for a, b in zip(ctrl_m, trt_m, strict=True)])
    return {"t0": t0, "ok": True,
            "control_bad": statistics.fmean(m["bad_rate"] for m in ctrl_m),
            "treatment_bad": statistics.fmean(m["bad_rate"] for m in trt_m),
            "diff_bad": db, "ci_bad": ci_b,
            "control_time": statistics.fmean(m["penalized_time"] for m in ctrl_m),
            "treatment_time": statistics.fmean(m["penalized_time"] for m in trt_m),
            "diff_time": dt, "ci_time": ci_t,
            "control_rejected": statistics.fmean(m["rejected"] / m["n"] for m in ctrl_m),
            "treatment_rejected": statistics.fmean(m["rejected"] / m["n"] for m in trt_m)}


def bundle_json(bundle: dict) -> str:
    return json.dumps(bundle, sort_keys=True, default=str)
