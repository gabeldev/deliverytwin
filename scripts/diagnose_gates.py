"""Diagnose which generator gate rejects candidate instances, per fault family.

Usage: uv run python scripts/diagnose_gates.py [--n 30] [--families a,b]
"""

from __future__ import annotations

import argparse
from collections import Counter

from deliverytwin.benchmark.generator import (
    DEFAULT_SEVERITY,
    _sample_fault,
    impact,
    passes_impact,
)
from deliverytwin.core.rng import EventRng, derive_seed
from deliverytwin.diagnostics.detector import detect
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry
from deliverytwin.world.city import build_city
from deliverytwin.world.config import WorldConfig


def diagnose(fam: str, n: int, severity=None, max_delay: float = 90.0):
    cfg = WorldConfig(horizon_minutes=360)
    reasons, delays, imps = Counter(), [], []
    for i in range(n):
        meta = EventRng(derive_seed(1, "dbg", fam, i), strict=False)
        seed = derive_seed(1, "w", fam, i) >> 64
        city = build_city(cfg, EventRng(seed, strict=False))
        f = _sample_fault(meta, fam, cfg, "f", popularity=[r.popularity for r in city.restaurants],
                          severity=severity)
        clean, faulty = World(cfg, seed).run(), World(cfg, seed, faults=(f,)).run()
        imp = impact(faulty, clean, f.onset)
        imps.append(imp["global_time"])
        if not passes_impact(imp):
            reasons["impact"] += 1
            continue
        tel = build_telemetry(faulty, dataset_id="x", profile="customer", observed_until=360,
                              obfuscator=Obfuscator(1))
        a = detect(tel)
        if a is None:
            reasons["no_alert"] += 1
            continue
        if a.t < f.onset:
            reasons["before_onset"] += 1
            continue
        delays.append(round(a.t - f.onset))
        if a.t > f.onset + max_delay:
            reasons["late"] += 1
            continue
        ctel = build_telemetry(clean, dataset_id="x", profile="customer", observed_until=360,
                               obfuscator=Obfuscator(1))
        if detect(ctel, until=a.t) is not None:
            reasons["clean_alerts"] += 1
            continue
        reasons["ok"] += 1
    return reasons, sorted(delays), sorted(round(x, 1) for x in imps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--families", default=",".join(DEFAULT_SEVERITY))
    a = ap.parse_args()
    for fam in a.families.split(","):
        r, d, imps = diagnose(fam, a.n)
        print(fam, dict(r), "delays", d[:12], "global_time_shift", imps[::3])


if __name__ == "__main__":
    main()
