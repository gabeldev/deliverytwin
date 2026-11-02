"""Calibrate detector thresholds on fault-free worlds and measure held-out false alarms.

Usage: uv run python scripts/calibrate_detector.py [--n-cal 200] [--n-eval 100]
Calibration seeds: 100_000+; evaluation seeds: 200_000+ (disjoint).
"""

from __future__ import annotations

import argparse
import json

from deliverytwin.diagnostics.detector import DetectorConfig, calibrate_thresholds, detect
from deliverytwin.faults.spec import NoiseSpec
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry
from deliverytwin.world.config import WorldConfig

CFG = WorldConfig(horizon_minutes=360)
NOISE = {"none": NoiseSpec(), "ambient": NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)}


def healthy(seed: int, noise: NoiseSpec):
    w = World(CFG, seed, noise=noise).run()
    return build_telemetry(w, dataset_id="cal", profile="customer", observed_until=360,
                           obfuscator=Obfuscator(seed))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-cal", type=int, default=200)
    ap.add_argument("--n-eval", type=int, default=100)
    ap.add_argument("--target", type=float, default=0.05)
    args = ap.parse_args()
    cal = [healthy(100_000 + i, NOISE["ambient"]) for i in range(args.n_cal)]  # conservative: noisier condition
    cfg = calibrate_thresholds(cal, args.target, DetectorConfig())
    out = {"target_false_alarm": args.target, "thr_global": cfg.thr_global, "thr_local": cfg.thr_local,
           "n_calibration": args.n_cal, "held_out": {}}
    for name, noise in NOISE.items():
        fa = sum(detect(healthy(200_000 + i, noise), cfg) is not None for i in range(args.n_eval))
        out["held_out"][name] = {"false_alarm_runs": fa, "n": args.n_eval, "rate": fa / args.n_eval}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
