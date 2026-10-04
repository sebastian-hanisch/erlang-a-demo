"""Erlang-A-Formeln gegen Handrechnung, gegen eine UNABHÄNGIGE Referenz (lineares Gleichungssystem der abgeschnittenen Kette)
und gegen die Grenzfälle Erlang C (θ → 0) und Erlang B (θ → ∞)."""

import math

import numpy as np
import pytest

import era_formulas as F

MU = 1 / 3


def _ctmc_stationary(c, lam, mu, theta, k_max=500):
    """Stationäre Verteilung der auf 0..k_max abgeschnittenen Kette: π Q = 0, Σπ = 1 (lineares Gleichungssystem)."""
    n = k_max + 1
    q = np.zeros((n, n))
    for i in range(n - 1):
        q[i, i + 1] = lam
        q[i + 1, i] = min(i + 1, c) * mu + max(i + 1 - c, 0) * theta
    np.fill_diagonal(q, -q.sum(axis=1))
    a = np.vstack([q.T[:-1], np.ones(n)])
    b = np.zeros(n)
    b[-1] = 1.0
    return np.linalg.solve(a, b)


@pytest.mark.parametrize("c,rho,theta", [(1, 0.8, 0.2), (2, 1.0, 0.1), (4, 1.3, 0.2), (10, 0.95, 0.2), (6, 2.0, 0.5),
                                         (3, 0.5, 1.0)])
def test_erlang_a_matches_the_ctmc_reference(c, rho, theta):
    lam = rho * c * MU
    pi = _ctmc_stationary(c, lam, MU, theta)
    states = np.arange(len(pi))
    p = F.stationary_distribution(c, lam, MU, theta)
    for n in (0, 1, c, c + 1, c + 7):
        assert p[n] == pytest.approx(pi[n], rel=1e-6, abs=1e-12)
    m = F.stationary_metrics(c, lam, MU, theta)
    lq = (pi[c:] * (states[c:] - c)).sum()
    assert m["Lq"] == pytest.approx(lq, rel=1e-6)
    assert m["p_abandon"] == pytest.approx(theta * lq / lam, rel=1e-6)
    assert m["p_wait"] == pytest.approx(pi[c:].sum(), rel=1e-6)
    assert m["L"] == pytest.approx((pi * states).sum(), rel=1e-6)


def test_hand_value_one_server_unit_rates():
    """c = 1, λ = μ = θ = 1: Sterberaten 1, 2, 3, …, also p_n = e^{-1}/n!; Lq = 1/e, P(ab) = 1/e, P(warten) = 1 − 1/e, L = 1."""
    m = F.stationary_metrics(1, 1.0, 1.0, 1.0)
    assert m["p_abandon"] == pytest.approx(1 / math.e) and m["Lq"] == pytest.approx(1 / math.e)
    assert m["p_wait"] == pytest.approx(1 - 1 / math.e) and m["L"] == pytest.approx(1.0)
    p = F.stationary_distribution(1, 1.0, 1.0, 1.0)
    assert p[:3] == pytest.approx([math.exp(-1), math.exp(-1), math.exp(-1) / 2])


@pytest.mark.parametrize("c,rho,theta", [(2, 0.9, 0.3), (10, 1.2, 0.2), (30, 0.95, 0.05), (4, 1.5, 1.0)])
def test_throughput_balance(c, rho, theta):
    """Durchsatz λ(1 − P(ab)) = μ · mittlere Zahl beschäftigter Spuren (Bilanz der Bedienten, ohne Bezug auf Lq)."""
    lam = rho * c * MU
    p = F.stationary_distribution(c, lam, MU, theta)
    busy = sum(min(n, c) * pn for n, pn in enumerate(p))
    m = F.stationary_metrics(c, lam, MU, theta)
    assert m["throughput"] == pytest.approx(MU * busy, rel=1e-9)
    assert m["utilisation"] == pytest.approx(busy / c)


@pytest.mark.parametrize("c,rho", [(4, 0.8), (10, 0.95), (20, 0.5)])
def test_no_patience_limit_is_erlang_c(c, rho):
    lam = rho * c * MU
    m = F.stationary_metrics(c, lam, MU, 1e-9)
    assert m["Wq"] == pytest.approx(F.erlang_c_wq(c, lam, MU), rel=1e-5)
    assert m["p_wait"] == pytest.approx(F.erlang_c(c, lam / MU), rel=1e-5) and m["p_abandon"] < 1e-6


@pytest.mark.parametrize("c,rho", [(4, 0.8), (10, 0.95), (10, 1.3), (50, 1.0)])
def test_zero_patience_limit_is_erlang_b(c, rho):
    lam = rho * c * MU
    assert F.stationary_metrics(c, lam, MU, 1e7)["p_abandon"] == pytest.approx(F.erlang_b(c, lam / MU), rel=1e-4)


def test_erlang_b_and_c_hand_values():
    """B(1, 1) = 1/2, B(2, 1) = 0.2, C(2, 1) = 1/3; Erlang C verlangt ρ < 1."""
    assert F.erlang_b(1, 1.0) == pytest.approx(0.5) and F.erlang_b(2, 1.0) == pytest.approx(0.2)
    assert F.erlang_c(2, 1.0) == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        F.erlang_c(2, 2.0)
    with pytest.raises(ValueError):
        F.stationary_distribution(2, 2.0, 1.0, 0.0)


def test_distribution_sums_to_one_and_has_no_overflow_for_large_systems():
    p = F.stationary_distribution(200, 1.3 * 200 * MU, MU, 0.2)
    assert sum(p) == pytest.approx(1.0) and all(math.isfinite(x) for x in p)
    assert F.stationary_metrics(200, 1.5 * 200 * MU, MU, 0.2)["p_abandon"] == pytest.approx(1 - 1 / 1.5, abs=0.02)


def test_overload_has_an_equilibrium_and_abandonment_grows_with_load():
    rates_ = [F.stationary_metrics(10, rho * 10 * MU, MU, 0.2)["p_abandon"] for rho in (0.8, 0.95, 1.0, 1.1, 1.3, 1.5)]
    assert all(b > a for a, b in zip(rates_, rates_[1:])) and rates_[-1] < 1


def test_more_patience_means_fewer_abandons_and_longer_waits():
    lam = 0.95 * 10 * MU
    ab = [F.stationary_metrics(10, lam, MU, 1 / p)["p_abandon"] for p in (1, 5, 30)]
    wq = [F.stationary_metrics(10, lam, MU, 1 / p)["Wq"] for p in (1, 5, 30)]
    assert ab[0] > ab[1] > ab[2] and wq[0] < wq[1] < wq[2]


def test_fluid_limit_by_hand_and_as_the_many_server_limit():
    assert F.fluid_abandon_rate(0.9) == 0.0 and F.fluid_abandon_rate(2.0) == pytest.approx(0.5)
    assert F.fluid_abandon_rate(1.3) == pytest.approx(1 - 1 / 1.3)
    small = F.stationary_metrics(4, 1.3 * 4 * MU, MU, 0.2)["p_abandon"]
    big = F.stationary_metrics(200, 1.3 * 200 * MU, MU, 0.2)["p_abandon"]
    assert abs(big - F.fluid_abandon_rate(1.3)) < abs(small - F.fluid_abandon_rate(1.3))


def test_staffing_searches_are_minimal_and_waiting_saves_lanes():
    a, target = 50, 0.01
    c = F.min_servers_for_abandon(a, MU, 0.2, target)
    assert F.stationary_metrics(c, a * MU, MU, 0.2)["p_abandon"] <= target
    assert F.stationary_metrics(c - 1, a * MU, MU, 0.2)["p_abandon"] > target
    c_loss = F.min_servers_loss(a, target)
    assert F.erlang_b(c_loss, a) <= target < F.erlang_b(c_loss - 1, a) and c < c_loss
    assert F.min_servers_for_abandon(a, MU, 1 / 60, target) <= c <= F.min_servers_for_abandon(a, MU, 1 / 0.25, target)
