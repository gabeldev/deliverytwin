"""Expert-rule diagnostic baseline (no LLM) and trivial floors (ADR-0004/0006).

The rule baseline sees exactly what an agent sees: `telemetry/v1` up to the alert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean, median

from deliverytwin.telemetry.schema import OrderRecord, Telemetry

# Global (non-localised) fault families. Without operational gauges the rules cannot tell
# them apart and abstain over the whole set.
GLOBAL_FAMILIES = ("courier_scarcity", "dispatcher_saturation", "dispatch_error_surge",
                   "dispatch_latency")
PAIR = ("courier_scarcity", "dispatcher_saturation")  # separable with full-profile gauges


@dataclass(frozen=True)
class Diagnosis:
    """A cause, or an explicit 'unresolved between' set."""

    cause: str | None
    unresolved_between: tuple[str, ...] = ()
    scope: str | None = None  # e.g. restaurant token for a bottleneck
    evidence: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.cause:
            return self.cause
        return "unresolved{" + ",".join(sorted(self.unresolved_between)) + "}"


def _durations(orders: list[OrderRecord], lo: float, hi: float) -> list[float]:
    return [o.delivered - o.created for o in orders
            if o.delivered is not None and lo <= o.delivered < hi]


def censored_age(orders: list[OrderRecord], now: float, created_lo: float,
                 created_hi: float) -> list[float]:
    """Time from creation to completion, or to `now` if still open (customer-visible)."""
    out = []
    for o in orders:
        if not o.accepted or not (created_lo <= o.created < created_hi):
            continue
        done = [v for v in (o.delivered, o.cancelled) if v is not None and v <= now]
        out.append((min(done) if done else now) - o.created)
    return out


def restaurant_shifts(tel: Telemetry, alert_t: float, baseline_end: float = 125.0,
                      lookback: float = 40.0, recent_gap: float = 5.0) -> dict[str, float]:
    """Per-restaurant shift in censored age: alert window vs the same shape at baseline."""
    by_r: dict[str, list[OrderRecord]] = {}
    for o in tel.orders:
        by_r.setdefault(o.restaurant, []).append(o)
    shifts = {}
    for r, os_ in by_r.items():
        b = censored_age(os_, baseline_end, baseline_end - lookback, baseline_end - recent_gap)
        w = censored_age(os_, alert_t, alert_t - lookback, alert_t - recent_gap)
        if len(b) >= 2 and len(w) >= 2:
            shifts[r] = fmean(w) - fmean(b)
    return shifts


def _mad(xs: list[float]) -> float:
    m = median(xs)
    return median(abs(x - m) for x in xs)


def _gauge_mean(tel: Telemetry, metric: str, lo: float, hi: float) -> float:
    vals = [g.value for g in tel.gauges if g.metric == metric and lo <= g.t <= hi]
    return fmean(vals) if vals else float("nan")


def kitchen_load_shifts(tel: Telemetry, alert_t: float, baseline=(80.0, 125.0),
                        window: float = 15.0) -> dict[str, float]:
    """Per-restaurant increase in kitchen load (full profile only)."""
    out = {}
    for e in tel.entities:
        if e.kind != "restaurant":
            continue
        b = [g.value for g in tel.gauges
             if g.metric == "kitchen_load" and g.entity == e.token and baseline[0] <= g.t <= baseline[1]]
        w = [g.value for g in tel.gauges
             if g.metric == "kitchen_load" and g.entity == e.token and alert_t - window <= g.t <= alert_t]
        if b and w:
            out[e.token] = fmean(w) - fmean(b)
    return out


def _localised(shifts: dict[str, float], min_gap: float) -> str | None:
    if len(shifts) < 3:
        return None
    worst = max(shifts, key=shifts.get)
    others = [v for r, v in shifts.items() if r != worst]
    if shifts[worst] - median(others) > max(min_gap, 5.0 * max(_mad(others), 0.25)):
        return worst
    return None


def diagnose_rules(tel: Telemetry, alert_t: float, baseline=(80.0, 125.0),
                   window: float = 30.0) -> Diagnosis:
    # 1a. Localised kitchen overload (mechanistic signal, full profile).
    if tel.profile in ("full", "partial") and tel.gauges:
        kshift = kitchen_load_shifts(tel, alert_t, baseline)
        worst = _localised(kshift, min_gap=2.0)
        if worst is not None:
            return Diagnosis(cause="restaurant_bottleneck", scope=worst,
                             evidence={"kitchen_load_shift": round(kshift[worst], 2)})
    # 1b. Localised degradation: one restaurant much worse than the rest (customer-visible).
    shifts = restaurant_shifts(tel, alert_t, baseline_end=baseline[1])
    if len(shifts) >= 3:
        worst = max(shifts, key=shifts.get)
        others = [v for r, v in shifts.items() if r != worst]
        spread = max(_mad(others), 1.0)
        if shifts[worst] - median(others) > max(8.0, 5.0 * spread):
            return Diagnosis(cause="restaurant_bottleneck", scope=worst,
                             evidence={"restaurant_shift": round(shifts[worst], 2),
                                       "others_median_shift": round(median(others), 2)})
    # 2. Global degradation: needs operational gauges to tell supply from dispatch.
    if tel.profile != "full" or not tel.gauges:
        return Diagnosis(cause=None, unresolved_between=GLOBAL_FAMILIES,
                         evidence={"reason": "no fleet/dispatch gauges in this profile"})
    lo, hi = alert_t - window, alert_t
    online_b = _gauge_mean(tel, "couriers_online", *baseline)
    online_w = _gauge_mean(tel, "couriers_online", lo, hi)
    queue_b = _gauge_mean(tel, "dispatch_queue", *baseline)
    queue_w = _gauge_mean(tel, "dispatch_queue", lo, hi)
    ev = {"couriers_online_ratio": round(online_w / max(online_b, 1e-9), 3),
          "dispatch_queue_baseline": round(queue_b, 2), "dispatch_queue_window": round(queue_w, 2)}
    if online_w < 0.8 * online_b:
        return Diagnosis(cause="courier_scarcity", evidence=ev)
    if queue_w >= max(3.0, 3.0 * queue_b + 1.0):
        return Diagnosis(cause="dispatcher_saturation", evidence=ev)
    return Diagnosis(cause=None, unresolved_between=PAIR, evidence=ev)


def diagnose_majority(majority_family: str) -> Diagnosis:
    """Floor: always answer the most frequent family in the training split."""
    return Diagnosis(cause=majority_family)
