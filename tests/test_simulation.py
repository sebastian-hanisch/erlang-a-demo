"""Simulation mit Abbruch: Generator, Geduld-Verteilungen, Vier-Lkw-Instanz von Hand, Little's Gesetz als Pfadidentität,
Grenzfälle (keine Geduld = Erlang B, unendliche Geduld = Erlang C) und Übereinstimmung mit den Formeln."""

import math
import statistics

import pytest

import era_formulas as F
import era_simulation as S
from conftest import ScriptedRng


def test_splitmix64_matches_the_reference_sequence():
    rng = S.SplitMix64(0)
    assert [rng.next() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_streams_are_distinct_and_rates_allow_overload():
    g, s, p = S.streams(7)
    assert len({g.state, s.state, p.state}) == 3
    lam, mu = S.rates(4, 130)
    assert mu == pytest.approx(1 / 3) and lam == pytest.approx(1.3 * 4 / 3) and lam > 4 * mu


@pytest.mark.parametrize("kind", S.PATIENCE_KINDS)
def test_draw_patience_always_consumes_two_uniforms_and_is_positive(kind):
    rng = ScriptedRng(uniform_values=[0.3, 0.6, 0.3, 0.6])
    assert S.draw_patience(kind, 5.0, rng) > 0 and rng.n_uniform == 2
    S.draw_patience(kind, 5.0, rng)
    assert rng.n_uniform == 4


def test_draw_patience_by_hand():
    """u1 = 0.5: exponentiell −ln(0.5)·5, gleichverteilt 2·5·0.5 = 5, fest 5."""
    mk = lambda: ScriptedRng(uniform_values=[0.5, 0.25])
    assert S.draw_patience("exp", 5.0, mk()) == pytest.approx(5 * math.log(2))
    assert S.draw_patience("uniform", 5.0, mk()) == pytest.approx(5.0)
    assert S.draw_patience("fest", 5.0, mk()) == 5.0
    with pytest.raises(ValueError):
        S.draw_patience("unbekannt", 5.0, mk())


@pytest.mark.parametrize("kind", S.PATIENCE_KINDS)
def test_every_patience_kind_has_the_requested_mean(kind):
    rng = S.SplitMix64(9)
    draws = [S.draw_patience(kind, 5.0, rng) for _ in range(60000)]
    assert statistics.fmean(draws) == pytest.approx(5.0, rel=0.04)


def test_lognormal_patience_has_the_stated_coefficient_of_variation_and_uniform_the_stated_range():
    rng = S.SplitMix64(11)
    ln = [S.draw_patience("lognorm", 5.0, rng) for _ in range(200000)]
    assert statistics.pstdev(ln) / statistics.fmean(ln) == pytest.approx(S.LOGNORMAL_CV, rel=0.15)
    un = [S.draw_patience("uniform", 5.0, rng) for _ in range(2000)]
    assert 0 <= min(un) and max(un) < 10.0


def test_mini_instance_with_abandonment_by_hand(mini_streams):
    """Von Hand (siehe conftest): Bediente warten 0 / 2 / 0 (in Startreihenfolge), Lkw 2 bricht nach 1.0 ab, Ende 7.5,
    Verweilzeiten 3 + 1 + 3 + 2 = 9 = ∫N dt, ∫Nq dt = 3, beschäftigte Spuren ∫ = 6 (Auslastung 0.8), Zeit je Zustand
    {0: 1.5, 1: 3.5, 2: 2, 3: 0.5}; Abbruch-Termin des bedienten Lkw 3 (bei 7) bleibt ohne Wirkung."""
    gap, svc, pat = mini_streams
    r = S.simulate(1, 1.0, 1.0, 5.0, 4, seed=0, kind="uniform", record=True, gap_rng=gap, svc_rng=svc, pat_rng=pat)
    assert r.served_waits == pytest.approx([0.0, 2.0, 0.0]) and r.abandon_waits == pytest.approx([1.0])
    assert r.end_time == pytest.approx(7.5) and r.sojourns == pytest.approx(9.0)
    assert r.area_in_system == pytest.approx(9.0) and r.area_in_queue == pytest.approx(3.0)
    assert r.busy_integral == pytest.approx(6.0) and r.utilisation == pytest.approx(0.8)
    assert r.time_in_state == pytest.approx({0: 1.5, 1: 3.5, 2: 2.0, 3: 0.5})
    assert [n for _, n in r.trajectory] == [0, 1, 2, 3, 2, 1, 0, 1, 0]
    assert r.abandon_rate == pytest.approx(0.25) and r.share_waiting == pytest.approx(0.5)
    assert r.mean_wait_all == pytest.approx(0.75) and r.mean_wait_served == pytest.approx(2 / 3)


def test_handle_abandon_ignores_a_customer_who_is_already_served():
    """Unit: handle_abandon für einen Lkw ohne Wartestatus ändert nichts und meldet das mit False."""
    s = S._State()
    s.status, s.n, s.t, s.abandon_waits, s.arrival_time, s.sojourns = ["served"], 1, 3.0, [], [0.0], 0.0
    assert S.handle_abandon(s, 0) is False and s.n == 1 and s.abandon_waits == []


@pytest.mark.parametrize("c,rho,kind", [(1, 90, "exp"), (4, 130, "exp"), (10, 95, "uniform"), (6, 100, "fest"),
                                         (20, 120, "lognorm")])
def test_littles_law_holds_exactly_on_every_path(c, rho, kind):
    """∫N dt = Σ Verweilzeiten (bediente mit Bedienung, Abbrecher bis zum Abbruch), auch in Überlast."""
    lam, mu = S.rates(c, rho)
    sim = S.simulate(c, lam, mu, 5.0, 4000, 7, kind=kind)
    assert sim.area_in_system == pytest.approx(sim.sojourns, rel=1e-9)
    assert sim.mean_in_system == pytest.approx(sim.arrival_rate * sim.mean_sojourn, rel=1e-9)


def test_invariants_of_a_long_run():
    lam, mu = S.rates(5, 120)
    sim = S.simulate(5, lam, mu, 5.0, 5000, 3)
    assert len(sim.served_waits) + len(sim.abandon_waits) == 5000
    assert sum(sim.time_in_state.values()) == pytest.approx(sim.end_time)
    assert 0 < sim.utilisation <= 1 and min(sim.served_waits) >= 0 and min(sim.abandon_waits) >= 0
    assert 0 < sim.abandon_rate < 1 and sim.n_waited >= len(sim.abandon_waits)


def test_same_seed_same_result_and_patience_kind_changes_only_the_patience():
    lam, mu = S.rates(4, 100)
    a, b = S.simulate(4, lam, mu, 5.0, 800, 11), S.simulate(4, lam, mu, 5.0, 800, 11)
    other = S.simulate(4, lam, mu, 5.0, 800, 12)
    assert a.served_waits == b.served_waits and a.served_waits != other.served_waits
    fixed = S.simulate(4, lam, mu, 5.0, 800, 11, kind="fest")
    assert fixed.abandon_rate != a.abandon_rate                         # Zweig: die Verteilung wirkt wirklich


def test_long_run_matches_the_erlang_a_formula():
    """c = 10, ρ = 95 %, Geduld 5 min: 200 000 Lkw liegen nahe an Abbruchquote und Wartezeit der Formel."""
    lam, mu = S.rates(10, 95)
    sim = S.simulate(10, lam, mu, 5.0, 200_000, 1)
    f = F.stationary_metrics(10, lam, mu, 0.2)
    assert sim.abandon_rate == pytest.approx(f["p_abandon"], abs=0.006)
    assert sim.mean_wait_all == pytest.approx(f["Wq"], rel=0.06)
    assert sim.share_waiting == pytest.approx(f["p_wait"], abs=0.015)
    assert sim.utilisation == pytest.approx(f["utilisation"], abs=0.012)


def test_overload_run_matches_the_formula():
    lam, mu = S.rates(10, 130)
    sim = S.simulate(10, lam, mu, 5.0, 100_000, 2)
    assert sim.abandon_rate == pytest.approx(F.stationary_metrics(10, lam, mu, 0.2)["p_abandon"], abs=0.01)


def test_almost_no_patience_is_the_erlang_b_loss_system():
    """Geduld 1e-9: jeder Lkw, der alle Spuren belegt findet, geht sofort - Abbruchquote = Erlang-B-Verlustwahrscheinlichkeit."""
    lam, mu = S.rates(10, 95)
    sim = S.simulate(10, lam, mu, 1e-9, 100_000, 3, kind="fest")
    assert sim.abandon_rate == pytest.approx(F.erlang_b(10, lam / mu), abs=0.01)


def test_enormous_patience_is_erlang_c():
    """Geduld 1e9 und ρ < 1: es bricht niemand ab, die Wartezeit liegt nahe an Erlang C."""
    lam, mu = S.rates(4, 80)
    sim = S.simulate(4, lam, mu, 1e9, 150_000, 4, kind="fest")
    assert sim.abandon_rate == 0.0
    assert sim.mean_wait_all == pytest.approx(F.erlang_c_wq(4, lam, mu), rel=0.12)
