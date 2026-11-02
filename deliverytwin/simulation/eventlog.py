"""Append-only event log with a canonical hash for replay/determinism checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventLog:
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, t: float, ev: str, **fields: Any) -> None:
        self.events.append({"t": t, "ev": ev, **fields})

    def canonical_lines(self, since: float | None = None) -> list[str]:
        rows = self.events if since is None else [e for e in self.events if e["t"] >= since]
        return [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in rows]

    def digest(self, since: float | None = None) -> str:
        h = hashlib.sha256()
        for line in self.canonical_lines(since):
            h.update(line.encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()

    def __len__(self) -> int:
        return len(self.events)
