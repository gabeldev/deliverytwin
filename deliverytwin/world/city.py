"""Synthetic grid city: zones, restaurants and courier home positions.

Layout is a deterministic function of (config, seed) via event-keyed draws, so the
same instance always has the same city regardless of interventions.
"""

from __future__ import annotations

from dataclasses import dataclass

from deliverytwin.core.rng import EventRng
from deliverytwin.world.config import WorldConfig

Point = tuple[int, int]


def manhattan(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def zone_of(point: Point, cfg: WorldConfig) -> int:
    """Vertical strips across the grid."""
    width = cfg.grid_size / cfg.n_zones
    return min(int(point[0] / width), cfg.n_zones - 1)


def random_point_in_zone(rng: EventRng, cfg: WorldConfig, zone: int, *key: str | int) -> Point:
    width = cfg.grid_size / cfg.n_zones
    x_lo = int(zone * width)
    x_hi = max(x_lo + 1, int((zone + 1) * width))
    x = x_lo + rng.choice_index(x_hi - x_lo, *key, "x")
    y = rng.choice_index(cfg.grid_size, *key, "y")
    return (x, y)


@dataclass(frozen=True)
class Restaurant:
    restaurant_id: str
    position: Point
    zone: int
    popularity: float = 1.0  # relative order share within its zone


@dataclass(frozen=True)
class City:
    restaurants: tuple[Restaurant, ...]
    courier_homes: tuple[tuple[str, Point], ...]

    def restaurants_in_zone(self, zone: int) -> list[Restaurant]:
        return [r for r in self.restaurants if r.zone == zone]


def build_city(cfg: WorldConfig, rng: EventRng) -> City:
    restaurants = []
    for i in range(cfg.n_restaurants):
        zone = i % cfg.n_zones
        pos = random_point_in_zone(rng, cfg, zone, "city", "restaurant", i)
        popularity = rng.lognormal_factor(cfg.restaurant_popularity_sigma, "city", "popularity", i)
        restaurants.append(Restaurant(restaurant_id=f"r{i:03d}", position=pos, zone=zone,
                                      popularity=popularity))
    homes = []
    for i in range(cfg.n_couriers):
        x = rng.choice_index(cfg.grid_size, "city", "courier_home", i, "x")
        y = rng.choice_index(cfg.grid_size, "city", "courier_home", i, "y")
        homes.append((f"c{i:03d}", (x, y)))
    return City(restaurants=tuple(restaurants), courier_homes=tuple(homes))
