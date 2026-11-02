"""Event-keyed randomness (ADR-0002).

Every random draw is a pure function of (world seed, event key):

    U_e = g(seed, event_key_e)

implemented with keyed BLAKE2b, a hash-based counter RNG. There is no mutable
generator state, so an intervention that changes the execution path cannot shift
the noise assigned to any other event ("execution invariance", arXiv 2603.11084).

Rules enforced here:
- keys are tuples of str/int only (no floats, no endogenous quantities by convention);
- in strict mode, drawing the same key twice within one world raises, forcing the
  model to sample each event once and cache the result.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

RNG_IMPLEMENTATION = "blake2b-keyed-64/v1"

_TWO_POW_53 = float(1 << 53)
_BELOW_ONE = math.nextafter(1.0, 0.0)
POISSON_MAX_LAMBDA = 100.0

KeyPart = str | int
EventKey = tuple[KeyPart, ...]


class KeyReuseError(RuntimeError):
    """Raised when the same event key is drawn twice in one world (strict mode)."""


def encode_key(key: EventKey) -> bytes:
    """Canonical, type-tagged encoding of an event key."""
    parts: list[str] = []
    for part in key:
        if isinstance(part, bool) or not isinstance(part, (str, int)):
            raise TypeError(f"event key parts must be str or int, got {type(part).__name__}")
        tag = "i" if isinstance(part, int) else "s"
        text = str(part)
        parts.append(f"{tag}{len(text)}:{text}")
    return "|".join(parts).encode("utf-8")


def derive_seed(base_seed: int, *labels: KeyPart) -> int:
    """Derive a 128-bit seed from a base seed and labels (e.g. replica index)."""
    material = encode_key((base_seed, *labels))
    return int.from_bytes(hashlib.blake2b(material, digest_size=16).digest(), "little")


class EventRng:
    """Pure-function random draws keyed by event identity."""

    def __init__(self, seed: int, *, strict: bool = True,
                 seen: set[bytes] | None = None) -> None:
        if seed < 0 or seed >= 1 << 128:
            raise ValueError("seed must be in [0, 2**128)")
        self.seed = seed
        self._key_bytes = seed.to_bytes(16, "little")
        self.strict = strict
        # A registry can be shared by several generators of the same world (e.g. before
        # and after a fork) so a key cannot be drawn twice across the switch.
        self._seen: set[bytes] = set() if seen is None else seen

    def uniform(self, *key: KeyPart) -> float:
        """U(0,1) draw in [2**-53, 1 - 2**-53] (never exactly 0 or 1)."""
        enc = encode_key(key)
        if self.strict:
            if enc in self._seen:
                raise KeyReuseError(f"event key drawn twice: {key!r}")
            self._seen.add(enc)
        digest = hashlib.blake2b(enc, digest_size=8, key=self._key_bytes).digest()
        bits = int.from_bytes(digest, "little") >> 11
        # (2**53 - 0.5) / 2**53 rounds to 1.0; clamp to keep the open interval (0, 1).
        # Only that single extreme value changes. Codex review G1, finding 1.
        return min((bits + 0.5) / _TWO_POW_53, _BELOW_ONE)

    # --- derived distributions (each consumes exactly one key) -------------------

    def bernoulli(self, p: float, *key: KeyPart) -> bool:
        return self.uniform(*key) < p

    def exponential(self, mean: float, *key: KeyPart) -> float:
        return -mean * math.log(1.0 - self.uniform(*key))

    def lognormal_factor(self, sigma: float, *key: KeyPart) -> float:
        """Multiplicative noise with median 1: exp(sigma * Z)."""
        return math.exp(sigma * _std_normal_ppf(self.uniform(*key)))

    def poisson(self, lam: float, *key: KeyPart) -> int:
        """Poisson by inverse CDF from a single uniform.

        Supported for 0 <= lam <= POISSON_MAX_LAMBDA (exp(-lam) must not underflow);
        larger rates are rejected instead of silently returning a cap. Codex review G1,
        finding 2."""
        if not (0.0 <= lam <= POISSON_MAX_LAMBDA) or math.isnan(lam):
            raise ValueError(f"poisson rate must be in [0, {POISSON_MAX_LAMBDA}], got {lam}")
        u = self.uniform(*key)
        k, p = 0, math.exp(-lam)
        cdf = p
        limit = int(lam + 40 * math.sqrt(lam) + 50)
        while u > cdf:
            k += 1
            if k > limit:
                raise ArithmeticError(f"poisson inverse CDF did not converge (lam={lam})")
            p *= lam / k
            cdf += p
        return k

    def choice_index(self, n: int, *key: KeyPart) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        return min(int(self.uniform(*key) * n), n - 1)

    def weighted_index(self, weights: Iterable[float], *key: KeyPart) -> int:
        w = list(weights)
        if any(not math.isfinite(x) or x < 0 for x in w):
            raise ValueError("weights must be finite and non-negative")
        total = sum(w)
        if not math.isfinite(total):  # overflow: rescale (Codex review G1, finding 3)
            m = max(w)
            w = [x / m for x in w]
            total = sum(w)
        if total <= 0:
            raise ValueError("weights must sum to a positive value")
        target = self.uniform(*key) * total
        acc = 0.0
        for i, wi in enumerate(w):
            acc += wi
            if target < acc:
                return i
        # Floating-point fallback: last index with positive weight, never a zero weight.
        return max(i for i, wi in enumerate(w) if wi > 0)


def _std_normal_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation, |err| < 1.2e-9)."""
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
