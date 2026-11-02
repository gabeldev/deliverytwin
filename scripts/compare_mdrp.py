"""Compare the synthetic world against Grubhub MDRP instances (real, anonymized).

Data: https://github.com/grubhub/mdrplib, cloned locally into datasets/external/mdrplib
(not committed; no LICENSE file in the repository, so only local research use and
aggregate statistics; see ADR-0009).

Usage: uv run python scripts/compare_mdrp.py [--root datasets/external/mdrplib/public_instances]
Uses the 10 unmodified seed instances (o100, t100, s1, p100).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from deliverytwin.simulation.world import World
from deliverytwin.world.city import manhattan
from deliverytwin.world.config import WorldConfig


def read(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


def q(xs, p):
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


def lognormal_sigma(xs):
    logs = [math.log(x) for x in xs if x > 0]
    return statistics.pstdev(logs)


def top_share(counts, frac=0.1):
    s = sorted(counts, reverse=True)
    k = max(1, int(len(s) * frac))
    return sum(s[:k]) / sum(s)


def mdrp_stats(root: Path) -> dict:
    seeds = sorted(d for d in root.iterdir() if d.is_dir() and d.name.endswith("o100t100s1p100"))
    prep, d_rest_cust, shift_len, per_inst = [], [], [], []
    for d in seeds:
        params = read(d / "instance_parameters.txt")[0]
        mpm = float(params["meters_per_minute"])
        orders = read(d / "orders.txt")
        rest = {r["restaurant"]: (float(r["x"]), float(r["y"])) for r in read(d / "restaurants.txt")}
        couriers = read(d / "couriers.txt")
        prep += [float(o["ready_time"]) - float(o["placement_time"]) for o in orders]
        for o in orders:
            rx, ry = rest[o["restaurant"]]
            d_rest_cust.append((abs(float(o["x"]) - rx) + abs(float(o["y"]) - ry)) / mpm)
        shift_len += [float(c["off_time"]) - float(c["on_time"]) for c in couriers]
        t = [float(o["placement_time"]) for o in orders]
        span = (max(t) - min(t)) or 1.0
        hours = sum(float(c["off_time"]) - float(c["on_time"]) for c in couriers) / 60.0
        counts: dict[str, int] = {}
        for o in orders:
            counts[o["restaurant"]] = counts.get(o["restaurant"], 0) + 1
        per_inst.append({
            "orders": len(orders), "restaurants": len(rest), "couriers": len(couriers),
            "orders_per_min": len(orders) / span, "orders_per_courier_hour": len(orders) / hours,
            "top10pct_restaurant_share": top_share(list(counts.values())),
            "orders_per_restaurant_sigma_log": lognormal_sigma(list(counts.values())),
            "pickup_service_min": float(params["pickup service minutes"]),
            "dropoff_service_min": float(params["dropoff service minutes"]),
            "target_click_to_door": float(params["target click-to-door"]),
        })
    agg = {k: statistics.median(p[k] for p in per_inst) for k in per_inst[0]}
    return {
        "instances": [d.name for d in seeds],
        "prep_minutes": {"mean": statistics.fmean(prep), "p50": q(prep, .5), "p90": q(prep, .9),
                         "sigma_log": lognormal_sigma(prep)},
        "restaurant_to_customer_travel_min": {"p50": q(d_rest_cust, .5), "p90": q(d_rest_cust, .9)},
        "shift_minutes": {"p50": q(shift_len, .5), "min": min(shift_len), "max": max(shift_len)},
        "per_instance_median": agg,
    }


def world_stats(cfg: WorldConfig, seeds=range(1, 21)) -> dict:
    prep, travel, opch, top, sig = [], [], [], [], []
    for s in seeds:
        w = World(cfg, s).run()
        start = {}
        for e in w.log.events:
            if e["ev"] == "prep_started":
                start[e["oid"]] = e["t"]
            elif e["ev"] == "order_ready" and e["oid"] in start:
                prep.append(e["t"] - start[e["oid"]])
        for o in w.orders.values():
            travel.append(manhattan(o.restaurant.position, o.destination) * cfg.minutes_per_block)
        online = sum(c.available for c in w.couriers.values())
        opch.append(len(w.orders) / (online * cfg.horizon_minutes / 60))
        counts: dict[str, int] = {}
        for o in w.orders.values():
            counts[o.restaurant.restaurant_id] = counts.get(o.restaurant.restaurant_id, 0) + 1
        top.append(top_share(list(counts.values())))
        sig.append(lognormal_sigma(list(counts.values())))
    return {
        "prep_minutes": {"mean": statistics.fmean(prep), "p50": q(prep, .5), "p90": q(prep, .9),
                         "sigma_log": lognormal_sigma(prep)},
        "restaurant_to_customer_travel_min": {"p50": q(travel, .5), "p90": q(travel, .9)},
        "orders_per_courier_hour": statistics.median(opch),
        "top10pct_restaurant_share": statistics.median(top),
        "orders_per_restaurant_sigma_log": statistics.median(sig),
        "orders_per_min": sum(d.orders_per_minute for d in cfg.demand),
        "n_restaurants": cfg.n_restaurants,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets/external/mdrplib/public_instances")
    a = ap.parse_args()
    out = {"mdrp": mdrp_stats(Path(a.root)), "world": world_stats(WorldConfig(horizon_minutes=300))}
    print(json.dumps(out, indent=1, default=lambda x: round(x, 3)))


if __name__ == "__main__":
    main()
