"""World configuration (all inputs are synthetic and declared; ADR-0009)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DispatchPolicyName = Literal["nearest", "eta_aware", "random"]
AcceptKeyMode = Literal["slot", "dyad"]


class ZoneDemand(BaseModel):
    model_config = ConfigDict(frozen=True)
    zone: int
    orders_per_minute: float = Field(gt=0, le=30)  # x demand jitter must stay < Poisson limit


class WorldConfig(BaseModel):
    """Synthetic world. Units: minutes, grid blocks."""

    model_config = ConfigDict(frozen=True)

    grid_size: int = Field(default=12, ge=3)
    n_zones: int = Field(default=3, ge=1)
    minutes_per_block: float = Field(default=1.5, gt=0)
    travel_noise_sigma: float = Field(default=0.25, ge=0)

    n_restaurants: int = Field(default=10, ge=1)
    kitchen_capacity: int = Field(default=2, ge=1)  # minimum servers per kitchen
    kitchen_target_utilization: float = Field(default=0.6, gt=0, lt=1)
    restaurant_popularity_sigma: float = Field(default=1.0, ge=0)  # MDRP order-count log-sd ~0.99
    # Calibrated against Grubhub MDRP seed instances (G2.1): median 15, log-sd 0.6.
    prep_mean_minutes: float = Field(default=15.0, gt=0)  # median of the log-normal
    prep_sigma: float = Field(default=0.6, ge=0)
    pickup_service_minutes: float = Field(default=4.0, ge=0)  # MDRP
    dropoff_service_minutes: float = Field(default=4.0, ge=0)  # MDRP

    n_couriers: int = Field(default=56, ge=1)  # ~77% utilization after MDRP calibration (G2.1)
    courier_shift_availability: float = Field(default=0.9, gt=0, le=1)
    courier_accept_prob: float = Field(default=0.85, gt=0, le=1)
    accept_key_mode: AcceptKeyMode = "slot"  # ADR-0002 sensitivity analysis

    dispatcher_workers: int = Field(default=2, ge=1)
    dispatch_service_minutes: float = Field(default=0.3, gt=0)
    dispatch_error_prob: float = Field(default=0.01, ge=0, lt=1)
    dispatch_retry_minutes: float = Field(default=1.0, gt=0)
    dispatch_policy: DispatchPolicyName = "nearest"

    admission_rate: float = Field(default=1.0, gt=0, le=1)
    customer_patience_floor_minutes: float = Field(default=50.0, ge=0)
    customer_patience_mean_minutes: float = Field(default=30.0, gt=0)
    # Quoted promise ~ p90 of the healthy click-to-door distribution (G2.1). MDRP's 40-min
    # target assumes optimized bundled routing, which this world does not model.
    promised_delivery_minutes: float = Field(default=55.0, gt=0)

    demand: tuple[ZoneDemand, ...] = (
        ZoneDemand(zone=0, orders_per_minute=0.35),
        ZoneDemand(zone=1, orders_per_minute=0.45),
        ZoneDemand(zone=2, orders_per_minute=0.30),
    )

    horizon_minutes: int = Field(default=240, ge=1)
    day: int = 0
