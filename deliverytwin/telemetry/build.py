"""Build `telemetry/v1` from a simulated world, with obfuscation and leak scanning."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from deliverytwin.core.rng import EventRng
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.schema import Entity, GaugeRow, OrderRecord, Profile, Telemetry


@dataclass(frozen=True)
class Obfuscator:
    """Per-instance opaque tokens. The salt is private (kept in the instance manifest)."""

    salt: int

    def token(self, prefix: str, raw: str) -> str:
        h = hashlib.blake2b(raw.encode(), digest_size=5, key=self.salt.to_bytes(16, "little"))
        return f"{prefix}_{h.hexdigest()}"


_ORDER_EVENTS = {
    "order_accepted": "accepted",
    "order_rejected": "rejected",
    "order_assigned": "assigned",
    "order_ready": "ready",
    "order_picked_up": "picked_up",
    "order_delivered": "delivered",
    "order_cancelled": "cancelled",
}
# Partial observability (L5): fleet and dispatch gauges are missing.
PARTIAL_SCALAR_GAUGES = ("orders_active",)
_CUSTOMER_FIELDS = {"accepted", "rejected", "delivered", "cancelled"}


def build_telemetry(
    world: World,
    *,
    dataset_id: str,
    profile: Profile,
    observed_until: float,
    obfuscator: Obfuscator,
    gauge_noise_sigma: float = 0.0,
    noise_seed: int = 0,
) -> Telemetry:
    """Telemetry visible up to `observed_until` (events after it are censored)."""
    ob = obfuscator
    zone_tok = {z: ob.token("z", f"zone{z}") for z in range(world.cfg.n_zones)}
    rest_tok = {r.restaurant_id: ob.token("r", r.restaurant_id) for r in world.city.restaurants}
    entities = [Entity(kind="zone", token=zone_tok[z]) for z in sorted(zone_tok)]
    entities += [
        Entity(kind="restaurant", token=rest_tok[r.restaurant_id], zone=zone_tok[r.zone])
        for r in world.city.restaurants
    ]
    entities.sort(key=lambda e: (e.kind, e.token))

    rows: dict[str, dict] = {}
    for e in world.log.events:
        if e["t"] > observed_until:
            break
        ev = e["ev"]
        if ev == "order_created":
            rows[e["oid"]] = {
                "order": ob.token("o", e["oid"]),
                "zone": zone_tok[world.orders[e["oid"]].zone],
                "restaurant": rest_tok[e["rid"]],
                "created": e["t"],
            }
        elif ev in _ORDER_EVENTS and e["oid"] in rows:
            name = _ORDER_EVENTS[ev]
            if profile == "customer" and name not in _CUSTOMER_FIELDS:
                continue
            if name == "accepted":
                rows[e["oid"]]["accepted"] = True
            elif name == "rejected":
                rows[e["oid"]]["accepted"] = False
            else:
                rows[e["oid"]].setdefault(name, e["t"])
    orders = tuple(sorted((OrderRecord(**r) for r in rows.values()),
                          key=lambda o: (o.created, o.order)))

    gauges: list[GaugeRow] = []
    if profile in ("full", "partial"):
        rng = EventRng(noise_seed, strict=False)
        scalar = (("dispatch_queue", "couriers_online", "couriers_idle", "orders_active")
                  if profile == "full" else PARTIAL_SCALAR_GAUGES)

        def noisy(v: float, *key) -> float:
            if gauge_noise_sigma <= 0:
                return float(v)
            return round(v * rng.lognormal_factor(gauge_noise_sigma, "gauge_noise", *key), 3)

        for g in world.gauges:
            if g.t > observed_until:
                break
            t = g.t
            for metric in scalar:
                gauges.append(GaugeRow(t=t, metric=metric,
                                       value=noisy(getattr(g, metric), metric, int(t))))
            # Serialise in opaque-token order: raw-id order would reveal the mapping
            # (Codex review G2.1, finding 2).
            for rid, load in sorted(g.kitchen_load.items(), key=lambda kv: rest_tok[kv[0]]):
                gauges.append(GaugeRow(t=t, metric="kitchen_load", entity=rest_tok[rid],
                                       value=noisy(load, "kitchen_load", rid, int(t))))

    return Telemetry(
        source="simulated",
        dataset_id=dataset_id,
        profile=profile,
        observed_until=observed_until,
        promised_delivery_minutes=world.cfg.promised_delivery_minutes,
        entities=tuple(entities),
        orders=orders,
        gauges=tuple(gauges),
    )


_RAW_ID_PATTERNS = [
    re.compile(r"\br\d{3}\b"),          # restaurant ids
    re.compile(r"\bc\d{3}\b"),          # courier ids
    re.compile(r"\bo-\d+-\d+-\d+\b"),   # order ids
    re.compile(r"\binc\d+-\d+\b"),      # incentive courier ids
    re.compile(r"\bzone\d\b"),
]


def scan_for_leaks(payload: str, forbidden: list[str]) -> list[str]:
    """Return every forbidden token or raw identifier pattern found in a public payload."""
    found = [f for f in forbidden if f and f in payload]
    found += [p.pattern for p in _RAW_ID_PATTERNS if p.search(payload)]
    return found
