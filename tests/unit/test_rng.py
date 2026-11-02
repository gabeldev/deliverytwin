import math

import pytest

from deliverytwin.core.rng import EventRng, KeyReuseError, derive_seed, encode_key


def test_same_key_same_value_across_instances():
    a = EventRng(7, strict=False)
    b = EventRng(7, strict=False)
    assert a.uniform("prep", "o-1-2-0") == b.uniform("prep", "o-1-2-0")


def test_value_does_not_depend_on_draw_order():
    a = EventRng(7)
    b = EventRng(7)
    x1 = a.uniform("k", 1)
    a.uniform("k", 2)
    b.uniform("unrelated", 99)
    b.uniform("k", 2)
    assert b.uniform("k", 1) == x1


def test_different_seed_or_key_differs():
    r = EventRng(1, strict=False)
    assert r.uniform("a") != r.uniform("b")
    assert EventRng(1, strict=False).uniform("a") != EventRng(2, strict=False).uniform("a")


def test_key_encoding_is_type_tagged():
    assert encode_key(("1",)) != encode_key((1,))
    assert encode_key(("a|b",)) != encode_key(("a", "b"))
    with pytest.raises(TypeError):
        encode_key((1.5,))
    with pytest.raises(TypeError):
        encode_key((True,))


def test_strict_mode_rejects_key_reuse():
    r = EventRng(3)
    r.uniform("prep", "o1")
    with pytest.raises(KeyReuseError):
        r.uniform("prep", "o1")


def test_uniform_moments_and_range():
    r = EventRng(11)
    xs = [r.uniform("u", i) for i in range(40_000)]
    assert all(0.0 < x < 1.0 for x in xs)
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    assert abs(mean - 0.5) < 0.01
    assert abs(var - 1 / 12) < 0.003


def test_derived_distributions_have_expected_means():
    r = EventRng(5)
    n = 20_000
    exp_mean = sum(r.exponential(10.0, "e", i) for i in range(n)) / n
    assert abs(exp_mean - 10.0) < 0.4
    pois_mean = sum(r.poisson(0.4, "p", i) for i in range(n)) / n
    assert abs(pois_mean - 0.4) < 0.02
    logs = [math.log(r.lognormal_factor(0.35, "l", i)) for i in range(n)]
    assert abs(sum(logs) / n) < 0.01


def test_derive_seed_is_deterministic_and_distinct():
    assert derive_seed(42, "replica", 1) == derive_seed(42, "replica", 1)
    assert derive_seed(42, "replica", 1) != derive_seed(42, "replica", 2)
