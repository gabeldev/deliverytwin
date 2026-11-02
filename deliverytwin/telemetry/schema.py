"""Source-agnostic telemetry contract `telemetry/v1` (ADR-0011).

The same schema is produced by the simulator and, in the future, by real-data
ingestion adapters. A dataset has exactly one `source`; entity identifiers are
opaque tokens. Courier-level identities are never exposed (data minimisation).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "telemetry/v1"

Profile = Literal["full", "partial", "customer"]
Source = Literal["simulated", "real"]


class _M(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Entity(_M):
    kind: Literal["zone", "restaurant"]
    token: str
    zone: str | None = None  # for restaurants: the zone token they belong to


class OrderRecord(_M):
    """One order as seen up to the observation cut-off. Missing = not observed (yet)."""

    order: str
    zone: str
    restaurant: str
    created: float
    accepted: bool | None = None
    assigned: float | None = None
    ready: float | None = None
    picked_up: float | None = None
    delivered: float | None = None
    cancelled: float | None = None


class GaugeRow(_M):
    t: float
    metric: Literal["dispatch_queue", "couriers_online", "couriers_idle", "orders_active",
                    "kitchen_load"]
    entity: str | None = None
    value: float


class Telemetry(_M):
    schema_version: Literal["telemetry/v1"] = SCHEMA_VERSION
    source: Source
    dataset_id: str
    profile: Profile
    observed_until: float
    promised_delivery_minutes: float
    entities: tuple[Entity, ...]
    orders: tuple[OrderRecord, ...]
    gauges: tuple[GaugeRow, ...] = ()
