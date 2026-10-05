"""Orakel mit anderem Rechenweg: (1) Abbruchquote, Wartezeit, Auslastung und Wahrscheinlichkeit zu warten gegen das lineare Gleichungssystem der abgeschnittenen Kette (die Abbruchquote über die
Durchsatzbilanz λ(1 − P(ab)) = μ·E[min(N, c)] statt über θ·Lq/λ), große c in exakter Bruchrechnung, Grenzfälle θ → 0 (Erlang C) und θ → ∞ (Erlang B); (2) Spurbedarf per Brute Force;
(3) die Ereignissimulation gegen einen Scan-Simulator (nächstes Ereignis per Minimumsuche über Ankunft, Abgänge und Abbruch-Termine, keine Ereignisliste) für alle vier Geduld-Verteilungen."""

import random
from fractions import Fraction

import numpy as np
import pytest

import era_evaluation as E
import era_formulas as F
import era_simulation as S


def _ctmc(c, lam, mu, theta, k_max):
    n = k_max + 1
    q = np.zeros((n, n))
    for i in range(n - 1):
        q[i, i + 1] = lam
        q[i + 1, i] = min(i + 1, c) * mu + max(i + 1 - c, 0) * theta
    np.fill_diagonal(q, -q.sum(axis=1))
    m = np.vstack([q.T[:-1], np.ones(n)])
    b = np.zeros(n)
    b[-1] = 1.0
    return np.linalg.solve(m, b)


def test_metrics_equal_the_linear_system_of_the_truncated_chain():
    rng = random.Random(4)
    for _ in range(30):
        c, mu, rho = rng.randint(1, 8), rng.uniform(0.1, 1.5), rng.uniform(0.2, 1.6)
        theta = 1 / (rng.choice([0.5, 1, 2, 5]) / mu)
        lam = rho * c * mu
        k_max = c + 400
        pi = _ctmc(c, lam, mu, theta, k_max)
        assert pi[-20:].sum() < 1e-12                                                   # Abschneiden ist vernachlässigbar
        busy = sum(min(n, c) * pi[n] for n in range(k_max + 1))
        m = F.stationary_metrics(c, lam, mu, theta)
        assert m["p_abandon"] == pytest.approx(1 - mu * busy / lam, abs=1e-6)       # Durchsatzbilanz
        assert m["p_wait"] == pytest.approx(pi[c:].sum(), abs=1e-6)
        assert m["Lq"] == pytest.approx(sum((n - c) * pi[n] for n in range(c, k_max + 1)), rel=1e-6, abs=1e-8)
        assert m["Wq"] == pytest.approx(m["Lq"] / lam)
        assert m["utilisation"] == pytest.approx(busy / c, abs=1e-6)
        assert m["throughput"] == pytest.approx(mu * busy, abs=1e-6)


@pytest.mark.parametrize("c,rho,patience", [(50, 1.0, 5), (100, 1.0, 5), (200, 1.1, 5), (200, 0.95, 60), (50, 1.3, 1)])
def test_large_systems_equal_exact_rational_arithmetic(c, rho, patience):
    mu = Fraction(1, 3)
    lam, theta = Fraction(rho).limit_denominator(100) * c * mu, Fraction(1, patience)
    w, n = [Fraction(1)], 1
    while n < 5000:
        w.append(w[-1] * lam / (min(n, c) * mu + max(n - c, 0) * theta))
        if n > c + 5 and w[-1] < Fraction(1, 10 ** 30) and w[-1] < w[-2]:
            break
        n += 1
    lq = sum((i - c) * w[i] for i in range(c, len(w))) / sum(w)
    assert F.stationary_metrics(c, float(lam), float(mu), float(theta))["p_abandon"] == pytest.approx(float(theta * lq / lam), abs=1e-9)


def test_limits_are_erlang_c_and_erlang_b():
    for c in (1, 3, 8, 15):
        mu, lam = 1 / 3, 0.7 * c / 3
        assert F.stationary_metrics(c, lam, mu, 0)["p_wait"] == pytest.approx(F.erlang_c(c, lam / mu), abs=1e-9)
        assert F.stationary_metrics(c, lam, mu, 1e-9)["Wq"] == pytest.approx(F.erlang_c_wq(c, lam, mu), rel=1e-3)
        assert F.stationary_metrics(c, lam, mu, 1e9)["p_abandon"] == pytest.approx(F.erlang_b(c, lam / mu), abs=1e-6)
    with pytest.raises(ValueError):
        F.stationary_metrics(2, 1.0, 0.4, 0)


def test_min_servers_equal_a_brute_force_search():
    mu = 1 / 3
    for a in (5, 10, 33, 50, 100):
        for patience in (0.5, 5, 60):
            for target in (0.01, 0.05, 0.3):
                c = F.min_servers_for_abandon(a, mu, 1 / patience, target)
                assert F.stationary_metrics(c, a * mu, mu, 1 / patience)["p_abandon"] <= target
                assert c == 1 or F.stationary_metrics(c - 1, a * mu, mu, 1 / patience)["p_abandon"] > target
                cl = F.min_servers_loss(a, target)
                assert F.erlang_b(cl, a) <= target and (cl == 1 or F.erlang_b(cl - 1, a) > target)


def _scan(c, lam, mu, mean_patience, n, seed, kind):
    gap, svc, pat = S.streams(seed)
    arr, t = [], 0.0
    for _ in range(n):
        t += gap.expovariate(lam)
        arr.append(t)
    service = [svc.expovariate(mu) for _ in range(n)]
    patience = [S.draw_patience(kind, mean_patience, pat) for _ in range(n)]
    t, nxt, serving, waiting = 0.0, 0, {}, []
    served, aband, soj, area, area_q, busy, spent, n_waited = [], [], 0.0, 0.0, 0.0, 0.0, {}, 0
    while True:
        cand = ([(arr[nxt], "A", nxt)] if nxt < n else []) + [(d, "D", i) for i, d in serving.items()] + [(arr[i] + patience[i], "B", i) for i in waiting]
        if not cand:
            break
        te, what, i = min(cand)
        size = len(serving) + len(waiting)
        area += size * (te - t)
        area_q += len(waiting) * (te - t)
        busy += len(serving) * (te - t)
        spent[size] = spent.get(size, 0.0) + te - t
        t = te
        if what == "A":
            nxt += 1
            if len(serving) < c:
                serving[i] = t + service[i]
                served.append(0.0)
            else:
                waiting.append(i)
                n_waited += 1
        elif what == "D":
            soj += t - arr[i]
            del serving[i]
            if waiting:
                j = waiting.pop(0)
                serving[j] = t + service[j]
                served.append(t - arr[j])
        else:
            waiting.remove(i)
            aband.append(t - arr[i])
            soj += t - arr[i]
    return t, served, aband, soj, area, area_q, busy, spent, n_waited


@pytest.mark.parametrize("kind", S.PATIENCE_KINDS)
def test_event_simulation_equals_a_scan_simulator(kind):
    rng = random.Random(13)
    for _ in range(25):
        c, n, mu = rng.randint(1, 5), rng.randint(1, 60), rng.uniform(0.2, 1.5)
        lam, mean_patience, seed = rng.uniform(0.3, 2.0) * c * mu, rng.choice([0.3, 1, 3, 8]) / mu, rng.randint(0, 10 ** 6)
        sim = S.simulate(c, lam, mu, mean_patience, n, seed, kind=kind, record=True)
        end, served, aband, soj, area, area_q, busy, spent, n_waited = _scan(c, lam, mu, mean_patience, n, seed, kind)
        assert sim.end_time == pytest.approx(end, rel=1e-9)
        assert sim.served_waits == pytest.approx(served, abs=1e-8) and sim.abandon_waits == pytest.approx(aband, abs=1e-8)
        assert (sim.sojourns, sim.area_in_system, sim.area_in_queue, sim.busy_integral) == pytest.approx((soj, area, area_q, busy), rel=1e-8, abs=1e-8)
        assert sim.n_waited == n_waited
        for state, value in spent.items():
            assert sim.time_in_state.get(state, 0.0) == pytest.approx(value, abs=1e-8)
        assert len(sim.served_waits) + len(sim.abandon_waits) == n
        assert E.little_check(sim)[2] < 1e-9


def _scan_window(c, lam, mu, mean_patience, n, seed, kind, warm):
    """Messfenster-Größen mit demselben Scan-Simulator: Lkw mit Ankunft ab `warm` (Zähler, Wartezeiten) und die Zeitintegrale über
    [warm, letzte Ankunft] (beschäftigte Spuren, Zeit je Zustand), jeweils am Intervall geschnitten statt über einen Zeitzeiger."""
    gap, svc, pat = S.streams(seed)
    arr, t = [], 0.0
    for _ in range(n):
        t += gap.expovariate(lam)
        arr.append(t)
    service = [svc.expovariate(mu) for _ in range(n)]
    patience = [S.draw_patience(kind, mean_patience, pat) for _ in range(n)]
    last = arr[-1]
    t, nxt, serving, waiting = 0.0, 0, {}, []
    out = {"n_eval": 0, "waited": 0, "aband": 0, "wait_all": 0.0, "wait_served": 0.0, "busy": 0.0, "state": {}}
    while True:
        cand = ([(arr[nxt], "A", nxt)] if nxt < n else []) + [(d, "D", i) for i, d in serving.items()] + [(arr[i] + patience[i], "B", i) for i in waiting]
        if not cand:
            break
        te, what, i = min(cand)
        lo, hi = max(t, warm), min(te, last)
        if hi > lo:
            out["busy"] += len(serving) * (hi - lo)
            size = len(serving) + len(waiting)
            out["state"][size] = out["state"].get(size, 0.0) + (hi - lo)
        t = te
        counted = arr[i] >= warm
        if what == "A":
            nxt += 1
            out["n_eval"] += counted
            if len(serving) < c:
                serving[i] = t + service[i]
            else:
                waiting.append(i)
                out["waited"] += counted
        elif what == "D":
            del serving[i]
            if waiting:
                j = waiting.pop(0)
                serving[j] = t + service[j]
                if arr[j] >= warm:
                    out["wait_all"] += t - arr[j]
                    out["wait_served"] += t - arr[j]
        else:
            waiting.remove(i)
            if counted:
                out["aband"] += 1
                out["wait_all"] += t - arr[i]
    return out, last


@pytest.mark.parametrize("kind", S.PATIENCE_KINDS)
def test_measurement_window_equals_the_scan_simulator(kind):
    """Auswertung nach Einschwingzeit: Zähler, Wartezeitsummen, beschäftigte Spuren und Zeit je Zustand im Fenster [warm, letzte Ankunft]."""
    rng = random.Random(29)
    for _ in range(25):
        c, n, mu = rng.randint(1, 5), rng.randint(5, 80), rng.uniform(0.2, 1.5)
        lam, mean_patience, seed = rng.uniform(0.3, 2.0) * c * mu, rng.choice([0.3, 1, 3, 8]) / mu, rng.randint(0, 10 ** 6)
        warm = rng.choice([0.0, 0.5, 2.0, 5.0]) / lam * n / 10
        sim = S.simulate(c, lam, mu, mean_patience, n, seed, kind=kind, warm_time=warm)
        ref, last = _scan_window(c, lam, mu, mean_patience, n, seed, kind, warm)
        assert (sim.n_eval, sim.eval_waited, sim.eval_abandoned) == (ref["n_eval"], ref["waited"], ref["aband"])
        assert (sim.eval_wait_all, sim.eval_wait_served, sim.eval_busy_integral) == pytest.approx(
            (ref["wait_all"], ref["wait_served"], ref["busy"]), rel=1e-8, abs=1e-8)
        assert sim.eval_window == pytest.approx(max(last - warm, 1e-12))
        for state, value in ref["state"].items():
            assert sim.eval_time_in_state.get(state, 0.0) == pytest.approx(value, abs=1e-8)
