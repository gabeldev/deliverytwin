"""Incident detector over customer-visible telemetry (any profile).

Statistic: **bad-order rate** of a recent cohort. At check time t the cohort is the
accepted orders created in (t - cohort_old, t - cohort_young]. An order is *bad* if it
was cancelled, delivered after the promised time, or is still open past the promised
time; *good* if delivered within the promise; open orders still within the promise are
undetermined and excluded. The score is the rate shift (absolute) versus the same
statistic at the end of the baseline window, which is placed after the warm-up
transient. Monitored series: global, each zone, each restaurant. Thresholds are
calibrated on fault-free worlds to a target run-level false-alarm rate.

Physical limit: lateness is only observable once an order passes the promised time, so
customer-side detection cannot be much faster than the promise (40 min by default).

History (G2 report): per-order z-scores had 68-80% false alarms (orders in a window are
not independent) and, once calibrated, were too slow; cohort mean age was capped by
cancellations and barely moved under large faults.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from deliverytwin.telemetry.schema import OrderRecord, Telemetry


@dataclass(frozen=True)
class DetectorConfig:
    # Baseline cohort: orders *created* in [baseline_start, baseline_end] (after warm-up),
    # evaluated at baseline_end + promise so that every order's fate is determinable.
    # Faults must start after that evaluation time (generator: onset >= 180).
    baseline_start: float = 80.0
    baseline_end: float = 120.0
    # Cohort age window. `cohort_old` is relative to the promise: an open order is only
    # determinable (as late) once it passes the promise, so the cohort must reach beyond it.
    cohort_extra_beyond_promise: float = 30.0
    cohort_young: float = 10.0
    check_every: float = 5.0
    thr_global: float = 0.2  # absolute rate shift; replaced by calibrated values
    thr_local: float = 0.5
    min_global: int = 15
    min_local: int = 6  # smaller cohorts made local "all bad" common by chance (G2 report)
    rate_floor: float = 0.05
    consecutive: int = 2


@dataclass(frozen=True)
class Alert:
    t: float
    series: str  # "global", zone token or restaurant token
    metric: str
    score: float


def bad_rate(orders: list[OrderRecord], now: float, lo: float, hi: float,
             promised: float) -> tuple[float, int]:
    bad = good = 0
    for o in orders:
        if not (lo < o.created <= hi):
            continue
        if o.cancelled is not None and o.cancelled <= now:
            bad += 1
        elif o.delivered is not None and o.delivered <= now:
            late = o.delivered - o.created > promised
            bad += late
            good += not late
        elif now - o.created > promised:
            bad += 1
    n = bad + good
    return (bad / n if n else math.nan), n


def score_trajectories(tel: Telemetry, cfg: DetectorConfig, until: float):
    """Yield (t, level, series, sustained_score): min of the last `consecutive` scores."""
    P = tel.promised_delivery_minutes
    cohort_old = P + cfg.cohort_extra_beyond_promise
    groups: dict[tuple[str, str], list[OrderRecord]] = {}
    for o in tel.orders:
        if not o.accepted:
            continue
        groups.setdefault(("global", "global"), []).append(o)
        groups.setdefault(("local", o.zone), []).append(o)
        groups.setdefault(("local", o.restaurant), []).append(o)
    base_eval = cfg.baseline_end + P
    base: dict[tuple[str, str], float] = {}
    for k, g in groups.items():
        r, n = bad_rate(g, base_eval, cfg.baseline_start, cfg.baseline_end, P)
        if n >= (cfg.min_global if k[0] == "global" else cfg.min_local):
            base[k] = max(r, cfg.rate_floor)
    history: dict[tuple, list[float]] = {}
    t = base_eval + cfg.check_every
    while t <= until + 1e-9:
        for key in sorted(base):
            r, n = bad_rate(groups[key], t, t - cohort_old, t - cfg.cohort_young, P)
            need = cfg.min_global if key[0] == "global" else cfg.min_local
            s = r - base[key] if n >= need else 0.0
            h = history.setdefault(key, [])
            h.append(s)
            if len(h) >= cfg.consecutive:
                yield t, key[0], key[1], min(h[-cfg.consecutive:])
        t += cfg.check_every


def detect(tel: Telemetry, cfg: DetectorConfig | None = None,
           until: float | None = None) -> Alert | None:
    """First alert at or before `until` (default: end of observed telemetry)."""
    cfg = cfg or CALIBRATED
    end = tel.observed_until if until is None else min(until, tel.observed_until)
    for t, level, name, s in score_trajectories(tel, cfg, end):
        thr = cfg.thr_global if level == "global" else cfg.thr_local
        if s > thr:
            return Alert(t=t, series=name, metric="bad_order_rate", score=round(s, 4))
    return None


def max_scores(tel: Telemetry, cfg: DetectorConfig) -> dict[str, float]:
    """Largest sustained score per level over the whole run (for calibration)."""
    out = {"global": -math.inf, "local": -math.inf}
    for _, level, _, s in score_trajectories(tel, cfg, tel.observed_until):
        out[level] = max(out[level], s)
    return out


def calibrate_thresholds(healthy: list[Telemetry], target_false_alarm: float = 0.05,
                         cfg: DetectorConfig | None = None) -> DetectorConfig:
    """Split the run-level false-alarm budget between global and local monitors and set
    each threshold at the corresponding upper quantile of fault-free max scores."""
    cfg = cfg or DetectorConfig()
    scores = [max_scores(t, cfg) for t in healthy]
    q = 1.0 - target_false_alarm / 2.0

    def quantile(xs: list[float]) -> float:
        s = sorted(xs)
        return s[min(len(s) - 1, math.ceil(q * len(s)) - 1)]

    # Full precision: rounding down would let the selected order statistic itself
    # trigger an alert under the strict `>` rule (Codex review G2, #3).
    return replace(cfg, thr_global=quantile([s["global"] for s in scores]),
                   thr_local=quantile([s["local"] for s in scores]))


# Calibrated 2026-11-01 by scripts/calibrate_detector.py on the G2.1 world (MDRP-calibrated
# prep and service times, 56 couriers, 55-min promise): 300 fault-free worlds with ambient
# noise (conservative), target 5% run-level false alarms. Held-out (150 seeds each): 0.7%
# without noise, 2.7% with ambient noise. See docs/reports/G2_1_REPORT.md.
CALIBRATED = DetectorConfig(thr_global=0.16891891891891891, thr_local=0.7)  # full precision
