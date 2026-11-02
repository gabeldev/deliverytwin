"""Lab mode B: an imperfect twin of the true world (ADR-0003, PREREG_G5 study 2).

The twin runs the same simulator code with a DIFFERENT seed (derived from the private
record, never the world seed itself) and perturbed parameters: each listed parameter is
multiplied by exp(delta * Z), Z ~ N(0, 1) drawn per parameter; the fault severity is
perturbed the same way and its onset shifted by delta * 20 * Z minutes.

The twin knows the fault STRUCTURE (right mechanism, wrong parameters), so it is an
optimistic bound on a real estimated twin. Structural mismatch is out of scope (declared
limitation). delta = 0 isolates the effect of a different realisation (seed only).
"""

from __future__ import annotations

from deliverytwin.core.rng import EventRng, derive_seed
from deliverytwin.world.config import WorldConfig, ZoneDemand

ONSET_SHIFT_MINUTES = 20.0
_SEVERITY = {  # field -> (min, max) valid range after perturbation
    "offline_fraction": (0.05, 0.95),
    "service_multiplier": (1.01, 50.0),
    "prep_multiplier": (1.01, 10.0),
    "error_prob": (0.01, 0.99),
    "hang_prob": (0.01, 0.99),
}


def twin_seed(world_seed: int) -> int:
    return derive_seed(world_seed, "twin") >> 64


def twin_config(cfg: WorldConfig, delta: float, rng: EventRng) -> WorldConfig:
    def f(name: str) -> float:
        return rng.lognormal_factor(delta, "twin_param", name) if delta > 0 else 1.0

    demand = tuple(ZoneDemand(zone=z.zone, orders_per_minute=min(
        30.0, z.orders_per_minute * f(f"demand{z.zone}"))) for z in cfg.demand)
    return cfg.model_copy(update={
        "n_couriers": max(1, round(cfg.n_couriers * f("n_couriers"))),
        "demand": demand,
        "prep_mean_minutes": cfg.prep_mean_minutes * f("prep_mean"),
        "dispatch_service_minutes": cfg.dispatch_service_minutes * f("dispatch_service"),
        "dispatch_retry_minutes": cfg.dispatch_retry_minutes * f("dispatch_retry"),
        "customer_patience_mean_minutes": cfg.customer_patience_mean_minutes * f("patience"),
    })


def twin_fault(fault, delta: float, rng: EventRng, tag: str = "0"):
    if delta <= 0:
        return fault
    upd = {}
    for name, (lo, hi) in _SEVERITY.items():
        if hasattr(fault, name):
            v = getattr(fault, name) * rng.lognormal_factor(delta, "twin_sev", tag, name)
            upd[name] = min(hi, max(lo, v))
    z = _z(rng, "twin_onset", tag)
    upd["onset"] = max(0.0, fault.onset + delta * ONSET_SHIFT_MINUTES * z)
    return fault.model_copy(update=upd)


def _z(rng: EventRng, *key) -> float:
    import math
    return math.log(rng.lognormal_factor(1.0, *key))
