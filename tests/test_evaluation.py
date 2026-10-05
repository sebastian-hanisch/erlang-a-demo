"""Auswertung: Mini-Instanz von Hand, Erlang C gegen A, Spurbedarf, kleine Studie, Vollständigkeit der vorgerechneten Datei."""

import pytest

import era_constants as C
import era_evaluation as E
import era_formulas as F
import era_simulation as S


@pytest.fixture
def mini(mini_streams):
    gap, svc, pat = mini_streams
    return S.simulate(1, 1.0, 1.0, 5.0, 4, seed=0, kind="uniform", record=True, gap_rng=gap, svc_rng=svc, pat_rng=pat)


def test_theta_of():
    assert E.theta_of(5) == pytest.approx(0.2) and E.theta_of(0.5) == pytest.approx(2.0)


def test_little_check_on_the_mini_instance(mini):
    l_hat, lw, gap = E.little_check(mini)
    assert l_hat == pytest.approx(9.0 / 7.5) and lw == pytest.approx(9.0 / 7.5) and gap < 1e-12


def test_state_distribution_on_the_mini_instance(mini):
    """Messfenster = [0, letzte Ankunft 5.5] (ohne Einschwingzeit): Zeit je Zustand {0: 1.5, 1: 1.5, 2: 2, 3: 0.5}; das Auslaufen
    5.5 bis 7.5 (Zustand 1) zählt nicht mit."""
    shares, rest = E.state_distribution(mini, max_state=3)
    assert shares == pytest.approx([1.5 / 5.5, 1.5 / 5.5, 2 / 5.5, 0.5 / 5.5]) and rest == pytest.approx(0.0, abs=1e-12)
    shares2, rest2 = E.state_distribution(mini, max_state=1)
    assert rest2 == pytest.approx(2.5 / 5.5) and sum(shares2) + rest2 == pytest.approx(1.0)


def test_window_steps_on_the_mini_trajectory(mini):
    """Treppe (t, n): (0,0) (1,1) (1.5,2) (2,3) (2.5,2) (4,1) (5,0) (5.5,1) (7.5,0)."""
    assert E.window_steps(mini.trajectory, 2.0, 4.5) == [(2.0, 3), (2.5, 2), (4.0, 1), (4.5, 1)]
    assert E.window_steps(mini.trajectory, 0.0, 1.2)[0] == (0.0, 0)


def test_run_live_records_a_trajectory_without_ignored_events():
    sim = E.run_live(4, 120, 5, 500, 3)
    assert sim.trajectory[0] == (0.0, 0) and sim.c == 4
    steps = [n for _, n in sim.trajectory]
    assert all(abs(b - a) == 1 for a, b in zip(steps, steps[1:]))               # jedes Ereignis ändert N um genau 1


def test_erlang_c_vs_a_branches():
    rows = E.erlang_c_vs_a(4, 5, [50, 95, 100, 130])
    assert [r[0] for r in rows] == [50, 95, 100, 130]
    assert rows[0][1] is not None and rows[1][1] is not None and rows[2][1] is None and rows[3][1] is None
    assert rows[1][1] == pytest.approx(13.37, abs=0.01) and rows[1][2] == pytest.approx(0.77, abs=0.01)
    assert all(a is not None and a > 0 for _, _, a in rows)


def test_abandon_curve_is_increasing_in_load():
    curve = [v for _, v in E.abandon_curve(10, 5, [50, 80, 100, 120, 150])]
    assert curve == sorted(curve) and curve[0] < 0.01 and curve[-1] > 0.3


def test_staffing_rows_by_hand_and_saving():
    row = E.staffing_row(50, 5, 0.01)
    assert row["c"] == 57 and row["c_loss"] == 64 and row["p_abandon"] <= 0.01 and row["utilisation"] == pytest.approx(0.869, abs=0.001)
    assert E.staffing_row(100, 5, 0.05)["c"] == 98 and E.staffing_row(100, 5, 0.05)["c"] < 100       # Überlast genügt


def test_staffing_vs_patience_is_non_increasing():
    cs = [c for _, c in E.staffing_vs_patience(50, 0.01)]
    assert cs == sorted(cs, reverse=True) and cs[0] < F.min_servers_loss(50, 0.01)


def test_patience_study_small_cell_structure_and_branches():
    cell = E.patience_study(10, 100, 5, 4000, 6, seed_base=5)
    assert set(cell["kinds"]) == set(S.PATIENCE_KINDS) and cell["reps"] == 6
    for k in cell["kinds"].values():
        assert 0 < k["p_ab"] < 1 and k["wq"] > 0 and k["p_ab_sd"] >= 0
    assert cell["kinds"]["fest"]["p_ab"] < cell["kinds"]["exp"]["p_ab"]                  # Zweig: feste Geduld bricht seltener ab
    assert cell["kinds"]["fest"]["wq"] > cell["kinds"]["exp"]["wq"]


def test_nearest_ties_go_to_the_smaller_value():
    assert E.nearest(C.STUDY_RHO_PCT, 95) == 90 and E.nearest(C.STUDY_RHO_PCT, 96) == 100 and E.nearest(C.STUDY_RHO_PCT, 150) == 130
    assert E.nearest(C.STUDY_C, 7) == 4 and E.nearest(C.STUDY_C, 8) == 10 and E.nearest(C.STUDY_C, 30) == 10


def test_precomputed_file_is_complete():
    pre = E.load_precomputed()
    assert {(x["c"], x["rho_pct"]) for x in pre["study"]} == {(c, r) for c in C.STUDY_C for r in C.STUDY_RHO_PCT}
    assert pre["study_n"] == C.STUDY_N and pre["study_reps"] == C.STUDY_REPS and pre["study_patience"] == C.STUDY_PATIENCE
    for x in pre["study"]:
        assert x["reps"] == C.STUDY_REPS and set(x["kinds"]) == set(S.PATIENCE_KINDS)


def test_warm_time_rule_and_warmup_customers():
    """Mindestens 30 min, bei großer Geduld das Fünffache der mittleren Geduld; die Zusatz-Lkw sind die Ankünfte vor Ende der Einschwingzeit."""
    assert E.warm_time_min(1) == 30.0 and E.warm_time_min(5) == 30.0 and E.warm_time_min(10) == 50.0 and E.warm_time_min(30) == 150.0
    g, k, t = S.SplitMix64(3), 0, 0.0
    while True:                                                    # Zählung am selben Ankunftsstrom von Hand
        t += g.expovariate(0.5)
        if t >= 30.0:
            break
        k += 1
    assert E.warmup_customers(0.5, 5, 3) == k and 5 < k < 30
    sim = E.simulate_gate(2, 0.5, 1 / 3, 5, 100, 3)
    assert sim.n_eval == 100 and sim.n_customers == 100 + k


def test_short_runs_of_a_big_gate_are_not_biased_low_by_the_empty_start():
    """Messung (README): ohne Einschwingzeit lagen 1 000 Lkw an 50 Spuren bei ρ = 100 %, Geduld 5 min, im Mittel bei Auslastung 79 % statt 95 %
    und Wartezeit rund 21 % zu niedrig; bei ρ = 150 %, Geduld 30 min waren Abbruchquote und Wartezeit rund 54 % zu niedrig. Mit Einschwingzeit
    liegt das Mittel über 40 Läufe an der Formel (Seeds 100 bis 139)."""
    for c, rho, pat in [(50, 100, 5), (50, 150, 30)]:
        f = E.formula_metrics(c, rho, pat)
        runs = [E.run_live(c, rho, pat, 1000, 100 + i, record=False) for i in range(40)]
        assert all(r.n_eval == 1000 for r in runs)
        mean = lambda g: sum(g(r) for r in runs) / len(runs)
        assert mean(lambda r: r.utilisation) == pytest.approx(f["utilisation"], abs=0.01)
        assert mean(lambda r: r.abandon_rate) == pytest.approx(f["p_abandon"], abs=0.006)
        assert mean(lambda r: r.mean_wait_all) == pytest.approx(f["Wq"], rel=0.07)
