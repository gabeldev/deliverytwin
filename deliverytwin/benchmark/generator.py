"""Benchmark instance generation with rejection gates (ADR-0005).

Pipeline per attempt:
  1. sample world seed, fault (family, onset, severity), noise and obfuscation salt;
  2. impact gate: paired counterfactual (same seed, no fault) must show an SLI shift;
  3. detection gate: the detector must alert after onset and within `max_detect_delay`;
  4. public payload = telemetry/v1 up to the alert; private payload = everything else.

All sampling is event-keyed from (master_seed, level, index, attempt), so a manifest
regenerates identically.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from deliverytwin.core.rng import EventRng, derive_seed
from deliverytwin.diagnostics.detector import Alert, DetectorConfig, detect
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatchErrorSurge,
    DispatcherSaturation,
    DispatchLatency,
    NoiseSpec,
    RestaurantBottleneck,
    causal_dag,
)
from deliverytwin.simulation.kpis import cohort_outcomes
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry, scan_for_leaks
from deliverytwin.telemetry.schema import Profile, Telemetry
from deliverytwin.world.city import build_city
from deliverytwin.world.config import WorldConfig

LEVELS: dict[str, dict] = {
    "L0": {"families": ("courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck"),
           "profile": "full", "noise": NoiseSpec()},
    "L1": {"families": ("courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck"),
           "profile": "full",
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)},
    # G2.1: constructed pair, observationally equivalent for customers (probe at chance,
    # n=300) and separable by intervention (retry backoff). See G2_1_REPORT.md.
    "L2": {"families": ("dispatch_error_surge", "dispatch_latency"),
           "profile": "customer",
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)},
    # G5 ladder (docs/methods/PREREG_G5.md).
    # L3: a global fault plus a restaurant bottleneck in the same incident. The answer is
    # the PRIMARY fault: the one whose isolated impact (global bad-rate shift vs the
    # paired fault-free world) is larger, measured by the generator.
    "L3": {"families": ("courier_scarcity", "dispatcher_saturation"),
           "secondary": "restaurant_bottleneck", "profile": "full",
           "task_note": ("This incident may involve MORE THAN ONE simultaneous fault. Report "
                         "the PRIMARY fault as the cause: the one that on its own produces the "
                         "larger increase in the share of bad (late or failed) orders. Mention "
                         "any secondary fault in the summary; it is not scored.\n"),
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)},
    # L4: the L2 pair with zero budget slack (exactly one discriminating probe fits).
    "L4": {"families": ("dispatch_error_surge", "dispatch_latency"),
           "profile": "customer",
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15),
           "budgets": {"max_queries": 8, "max_experiments": 1, "experiment_units": 1.0}},
    # L5: L0 families without fleet/dispatch gauges (orders + orders_active + kitchen_load).
    "L5": {"families": ("courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck"),
           "profile": "partial",
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)},
    # L6: the L2 pair with lab mode B (imperfect twin, delta = 0.25).
    "L6": {"families": ("dispatch_error_surge", "dispatch_latency"),
           "profile": "customer",
           "noise": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15),
           "twin_delta": 0.25},
}
INTERVENTIONAL_LEVELS = ("L2", "L4", "L6")  # pair probe-verified in G2.1

# Impact gate on a closed, mature cohort (Codex review G2, finding 4): orders accepted in
# [onset, onset + IMPACT_COHORT), evaluated once all are determinable. Overdue open orders
# count as bad, and groups without data are skipped (never substituted by zero).
IMPACT_COHORT = 60.0
IMPACT_THRESHOLDS = {"global_time": 2.0, "global_bad": 0.05, "zone_bad": 0.08,
                     "restaurant_time": 6.0}
FORBIDDEN_TERMS = ["courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck",
                   "dispatch_error_surge", "error_prob", "dispatch_latency", "hang_prob",
                   "offline_fraction", "service_multiplier", "prep_multiplier",
                   "restaurant_index", "courier_offline", "fault"]


PUBLIC_DEV_MASTER_SEED = 2026
SECRET_SEED_ENV = "DELIVERYTWIN_MASTER_SEED"


def resolve_master_seed(master_seed: int | None) -> tuple[int, bool]:
    """Return (seed, sealed). Instances from the public default seed are reproducible by
    anyone with the code and are for development only; sealed evaluation sets must use a
    secret seed (argument or $DELIVERYTWIN_MASTER_SEED). Codex review G2.1, finding 1."""
    if master_seed is not None:
        return master_seed, master_seed != PUBLIC_DEV_MASTER_SEED
    env = os.environ.get(SECRET_SEED_ENV)
    if env:
        return int(env), True
    return PUBLIC_DEV_MASTER_SEED, False


class PrivateRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    instance_id: str
    sealed: bool
    level: str
    split: str
    world_seed: int
    obfuscation_salt: int
    noise_seed: int
    canary: str
    fault: dict
    extra_faults: tuple[dict, ...] = ()  # L3: secondary fault(s), private
    injected_faults: tuple[dict, ...] = ()  # L3: all faults in injection (replay) order
    family: str
    restaurant_token: str | None
    causal_dag: list[tuple[str, str]]
    impact: dict[str, float]
    alert: dict
    identifiability_assumed: str
    attempts: int


@dataclass
class Instance:
    private: PrivateRecord
    public: Telemetry
    world_config: WorldConfig = field(default_factory=WorldConfig)
    noise: NoiseSpec | None = None  # private: needed to rebuild the world in the lab


def _split(instance_seed: int) -> str:
    r = instance_seed % 10
    return "train" if r < 6 else ("dev" if r < 8 else "test")


DEFAULT_SEVERITY: dict[str, tuple[float, float]] = {
    "courier_scarcity": (0.45, 0.70),       # offline fraction
    "dispatcher_saturation": (9.0, 14.0),   # service-time multiplier
    "restaurant_bottleneck": (3.0, 6.0),    # prep-time multiplier
    "dispatch_error_surge": (0.95, 0.98),   # error probability per attempt (G2.1)
    "dispatch_latency": (0.95, 0.98),       # hang probability per step (same draws)
}


def _sample_fault(rng: EventRng, family: str, cfg: WorldConfig, *key,
                  popularity: list[float] | None = None,
                  severity: dict[str, tuple[float, float]] | None = None):
    lo, hi = (severity or DEFAULT_SEVERITY).get(family, DEFAULT_SEVERITY[family])
    sev = lo + (hi - lo) * rng.uniform(*key, "sev")
    onset = 180.0 + 35.0 * rng.uniform(*key, "onset")  # after baseline evaluation
    if family == "courier_scarcity":
        return CourierScarcity(onset=onset, offline_fraction=sev)
    if family == "dispatcher_saturation":
        return DispatcherSaturation(onset=onset, service_multiplier=sev)
    if family == "dispatch_error_surge":
        return DispatchErrorSurge(onset=onset, error_prob=sev)
    if family == "dispatch_latency":
        return DispatchLatency(onset=onset, hang_prob=sev)
    if family == "restaurant_bottleneck":
        # Incidents surface at busy restaurants: pick the restaurant proportionally to
        # its popularity (a public property of the world, not a hint about the cause).
        weights = popularity or [1.0] * cfg.n_restaurants
        return RestaurantBottleneck(onset=onset,
                                    restaurant_index=rng.weighted_index(weights, *key, "r"),
                                    prep_multiplier=sev)
    raise ValueError(family)


def _group_stats(world: World, onset: float, keyf) -> dict:
    P = world.cfg.promised_delivery_minutes
    hi = onset + IMPACT_COHORT
    rows = cohort_outcomes(world.log, P, onset, hi, min(hi + P, world.cfg.horizon_minutes))
    groups: dict = {}
    for oid, (bad, t) in rows.items():
        groups.setdefault(keyf(world.orders[oid]), []).append((bad, t))
    return {k: (sum(b for b, _ in v) / len(v), sum(t for _, t in v) / len(v), len(v))
            for k, v in groups.items()}


def impact(faulty: World, clean: World, since: float) -> dict[str, float]:
    """SLI shifts of the faulty world vs its paired no-fault counterfactual, on the same
    closed cohort of orders accepted after onset."""
    def shifts(keyf, idx, min_n):
        f, c = _group_stats(faulty, since, keyf), _group_stats(clean, since, keyf)
        return [f[k][idx] - c[k][idx] for k in c if k in f and min(f[k][2], c[k][2]) >= min_n]

    g_time = shifts(lambda o: "g", 1, 5)
    g_bad = shifts(lambda o: "g", 0, 5)
    z_bad = shifts(lambda o: o.zone, 0, 5)
    r_time = shifts(lambda o: o.restaurant.restaurant_id, 1, 5)
    nan = float("nan")
    return {
        "global_time": round(g_time[0], 3) if g_time else nan,
        "global_bad": round(g_bad[0], 4) if g_bad else nan,
        "zone_bad": round(max(z_bad), 4) if z_bad else nan,
        "restaurant_time": round(max(r_time), 3) if r_time else nan,
    }


def passes_impact(imp: dict[str, float]) -> bool:
    return any(imp[k] >= v for k, v in IMPACT_THRESHOLDS.items() if imp[k] == imp[k])


def generate_instance(level: str | dict, index: int, master_seed: int | None = None,
                      cfg: WorldConfig | None = None, max_attempts: int = 25,
                      max_detect_delay: float = 120.0,  # promise (55) + 65: physical limit
                      detector: DetectorConfig | None = None) -> Instance:
    cfg = cfg or WorldConfig(horizon_minutes=360)
    master_seed, sealed = resolve_master_seed(master_seed)
    spec = LEVELS[level] if isinstance(level, str) else level
    level = spec.get("name", level) if isinstance(level, dict) else level
    profile: Profile = spec["profile"]
    noise: NoiseSpec = spec["noise"]
    meta = EventRng(derive_seed(master_seed, "manifest", level, index), strict=False)
    family = spec["families"][meta.choice_index(len(spec["families"]), "family")]
    for attempt in range(max_attempts):
        world_seed = derive_seed(master_seed, "world", level, index, attempt) >> 64
        city = build_city(cfg, EventRng(world_seed, strict=False))
        fault = _sample_fault(meta, family, cfg, "fault", attempt,
                              popularity=[r.popularity for r in city.restaurants],
                              severity=spec.get("severity"))
        faults = [fault]
        if spec.get("secondary"):
            second = _sample_fault(meta, spec["secondary"], cfg, "fault2", attempt,
                                   popularity=[r.popularity for r in city.restaurants],
                                   severity=spec.get("severity"))
            shift = -15.0 + 30.0 * meta.uniform("fault2", attempt, "shift")
            faults.append(second.model_copy(update={"onset": max(180.0, fault.onset + shift)}))
        clean = World(cfg, world_seed, noise=noise).run()
        faulty = World(cfg, world_seed, faults=tuple(faults), noise=noise).run()
        onset = min(f.onset for f in faults)
        imp = impact(faulty, clean, since=onset)
        if not passes_impact(imp):
            continue
        # `faults` keeps the INJECTION order (fault-indexed RNG keys depend on it, Codex
        # review G4/G5 #5); the primary is chosen separately and `family` (the sampled
        # global family) is never overwritten across attempts (#4).
        primary, others = fault, faults[1:]
        if len(faults) > 1:
            # Primary = larger isolated global bad-rate shift (each fault alone vs clean).
            alone = [impact(World(cfg, world_seed, faults=(f,), noise=noise).run(), clean,
                            since=onset)["global_bad"] for f in faults]
            alone = [float("-inf") if math.isnan(a) else a for a in alone]
            k = max(range(len(faults)), key=lambda i: (alone[i], -i))
            primary, others = faults[k], [f for i, f in enumerate(faults) if i != k]
        salt = derive_seed(master_seed, "salt", level, index, attempt)
        noise_seed = derive_seed(master_seed, "noise", level, index, attempt)
        ob = Obfuscator(salt)
        full_obs = build_telemetry(faulty, dataset_id="probe", profile="customer",
                                   observed_until=cfg.horizon_minutes, obfuscator=ob)
        alert: Alert | None = detect(full_obs, detector)
        if alert is None or alert.t < onset or alert.t > onset + max_detect_delay:
            continue
        # Attribution gate: the paired fault-free world must not alert by the same time.
        clean_obs = build_telemetry(clean, dataset_id="probe", profile="customer",
                                    observed_until=cfg.horizon_minutes, obfuscator=ob)
        if detect(clean_obs, detector, until=alert.t) is not None:
            continue
        instance_id = f"{level}-{index:04d}"
        rid = None
        rtok = None
        if isinstance(primary, RestaurantBottleneck):
            rid = faulty.city.restaurants[primary.restaurant_index % len(faulty.city.restaurants)]
            rtok = ob.token("r", rid.restaurant_id)
        # Public id is an opaque token (private salt): level and index must not be
        # recoverable from it (Codex review G2.1, finding 1).
        public_id = ob.token("ds", instance_id)
        public = build_telemetry(faulty, dataset_id=public_id, profile=profile,
                                 observed_until=alert.t, obfuscator=ob,
                                 gauge_noise_sigma=noise.gauge_noise_sigma, noise_seed=noise_seed)
        canary = f"CANARY-{derive_seed(master_seed, 'canary', level, index):032x}"
        leaks = scan_for_leaks(public.model_dump_json(),
                               [*FORBIDDEN_TERMS, canary, str(world_seed), str(salt)])
        if leaks:
            raise RuntimeError(f"telemetry leak in {instance_id}: {leaks}")
        private = PrivateRecord(
            instance_id=instance_id, sealed=sealed, level=level, split=_split(world_seed),
            world_seed=world_seed, obfuscation_salt=salt, noise_seed=noise_seed, canary=canary,
            fault=json.loads(primary.model_dump_json()),
            extra_faults=tuple(json.loads(f.model_dump_json()) for f in others),
            injected_faults=(tuple(json.loads(f.model_dump_json()) for f in faults)
                             if len(faults) > 1 else ()),
            family=primary.family, restaurant_token=rtok,
            causal_dag=causal_dag(primary, rtok), impact=imp,
            alert={"t": alert.t, "series": alert.series, "metric": alert.metric, "score": alert.score},
            identifiability_assumed=("interventional (probe-verified)"
                                     if level in INTERVENTIONAL_LEVELS
                                     else "observational (not probe-verified)"),
            attempts=attempt + 1,
        )
        return Instance(private=private, public=public, world_config=cfg, noise=noise)
    raise RuntimeError(f"no valid instance for {level}-{index} after {max_attempts} attempts")
