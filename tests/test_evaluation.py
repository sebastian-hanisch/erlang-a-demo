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
    shares, rest = E.state_distribution(mini, max_state=3)
    assert shares == pytest.approx([0.2, 3.5 / 7.5, 2 / 7.5, 0.5 / 7.5]) and rest == pytest.approx(0.0, abs=1e-12)
    shares2, rest2 = E.state_distribution(mini, max_state=1)
    assert rest2 == pytest.approx(2.5 / 7.5) and sum(shares2) + rest2 == pytest.approx(1.0)


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
