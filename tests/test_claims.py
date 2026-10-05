"""JEDE Zahl aus README und App-Texten wird hier nachgerechnet: Formelwerte exakt, Studien-Zahlen aus der vorgerechneten Datei
(20 Läufe à 50 000 Lkw je Zelle), daher mit Marge und nie auf einen einzelnen verrauschten Wert gepinnt."""

import pytest

import era_constants as C
import era_evaluation as E
import era_formulas as F
from era_simulation import MU, PATIENCE_KINDS

PRE = E.load_precomputed()


def metrics(c, rho_pct, patience=5):
    return E.formula_metrics(c, rho_pct, patience)


def cell(c, rho):
    return E.study_cell(PRE, c, rho)["kinds"]


def test_preset_help_numbers():
    """PRESET_HELP: 10 Spuren ρ 95 %: 9.0 % Abbrecher, Wq 0.45, Erlang C 4.95; Überlast ρ 130 %: 24.8 %, Auslastung 97.8 %;
    Geduld 1 min: 13.6 %, Wq 0.14, Auslastung 82 %; 50 Spuren ρ 100 %: 4.9 %, Wq 0.25."""
    m = metrics(10, 95)
    assert m["p_abandon"] == pytest.approx(0.0898, abs=0.0005) and m["Wq"] == pytest.approx(0.449, abs=0.005)
    assert F.erlang_c_wq(10, 0.95 * 10 * MU, MU) == pytest.approx(4.95, abs=0.005)
    o = metrics(10, 130)
    assert o["p_abandon"] == pytest.approx(0.2478, abs=0.0005) and o["utilisation"] == pytest.approx(0.978, abs=0.0005)
    u = metrics(10, 95, patience=1)
    assert u["p_abandon"] == pytest.approx(0.1362, abs=0.0005) and u["Wq"] == pytest.approx(0.136, abs=0.0005)
    assert u["utilisation"] == pytest.approx(0.821, abs=0.0005)
    g = metrics(50, 100)
    assert g["p_abandon"] == pytest.approx(0.0492, abs=0.0005) and g["Wq"] == pytest.approx(0.246, abs=0.0005)
    assert metrics(10, 95, patience=30)["p_abandon"] == pytest.approx(0.0433, abs=0.0005)


def test_erlang_c_overestimates_the_wait_when_customers_abandon():
    """README (ρ = 95 %, Geduld 5 min): c = 4: Erlang C 13.4 min, Erlang A 0.77 min (17-fach); c = 10: 4.95 gegen 0.45 (11-fach);
    c = 50: 0.75 gegen 0.15 (5-fach)."""
    for c, c_wq, a_wq, ratio in ((4, 13.37, 0.77, 17.5), (10, 4.95, 0.45, 11.0), (50, 0.75, 0.15, 5.1)):
        lam = 0.95 * c * MU
        assert F.erlang_c_wq(c, lam, MU) == pytest.approx(c_wq, abs=0.01)
        assert metrics(c, 95)["Wq"] == pytest.approx(a_wq, abs=0.01)
        assert F.erlang_c_wq(c, lam, MU) / metrics(c, 95)["Wq"] == pytest.approx(ratio, abs=0.1)


def test_overload_abandon_rates_approach_the_fluid_limit():
    """README: ρ = 130 %: c = 4 28.5 %, c = 10 24.8 %, c = 50 23.1 %, c = 200 23.08 % gegen Grenzwert 23.08 %; ρ = 110 %: 20.9,
    15.3, 10.4, 9.2 % gegen 9.1 %."""
    for c, expected in ((4, 0.2851), (10, 0.2478), (50, 0.2310), (200, 0.2308)):
        assert metrics(c, 130)["p_abandon"] == pytest.approx(expected, abs=0.0006)
    for c, expected in ((4, 0.2090), (10, 0.1531), (50, 0.1041), (200, 0.0920)):
        assert metrics(c, 110)["p_abandon"] == pytest.approx(expected, abs=0.0006)
    assert F.fluid_abandon_rate(1.3) == pytest.approx(0.2308, abs=0.0001) and F.fluid_abandon_rate(1.1) == pytest.approx(0.0909, abs=0.0001)


def test_simulation_with_exponential_patience_matches_the_formula_in_every_study_cell():
    """README: Mittel der 20 Läufe liegt bei exponentieller Geduld in allen 15 Zellen innerhalb von vier Standardfehlern an der Formel."""
    n_reps = PRE["study_reps"]
    for x in PRE["study"]:
        k = x["kinds"]["exp"]
        f = metrics(x["c"], x["rho_pct"], PRE["study_patience"])
        se = k["p_ab_sd"] / n_reps ** 0.5
        assert abs(k["p_ab"] - f["p_abandon"]) <= 4 * se + 0.001, (x["c"], x["rho_pct"])


def test_patience_shape_quoted_in_readme():
    """README (50 Spuren, ρ = 100 %, Mittel 5 min): Abbruchquote exponentiell 5.0 %, gleichverteilt 4.1 %, fest 1.2 %, lognormal 4.4 %;
    mittlere Wartezeit 0.25 / 0.40 / 2.39 / 0.31 min (fest das 9.5-Fache der exponentiellen)."""
    k = cell(50, 100)
    for kind, expected in (("exp", 0.050), ("uniform", 0.041), ("fest", 0.012), ("lognorm", 0.044)):
        assert k[kind]["p_ab"] == pytest.approx(expected, abs=0.006), kind
    assert k["fest"]["p_ab"] < k["lognorm"]["p_ab"] < k["exp"]["p_ab"] * 1.0 + 0.003 and k["uniform"]["p_ab"] < k["exp"]["p_ab"]
    assert k["exp"]["wq"] == pytest.approx(0.25, abs=0.03) and k["fest"]["wq"] == pytest.approx(2.39, abs=0.2)
    assert 7 < k["fest"]["wq"] / k["exp"]["wq"] < 12


def test_patience_shape_matters_near_full_load_and_hardly_in_heavy_overload():
    """README: Spannweite der Abbruchquote über die vier Verteilungen: 50 Spuren ρ = 100 %: 3.9 Punkte; ρ = 130 %: 0.1 Punkte;
    10 Spuren ρ = 130 %: 1.8 Punkte; 4 Spuren ρ = 130 %: 4.3 Punkte."""
    def spread(c, rho):
        v = [x["p_ab"] for x in cell(c, rho).values()]
        return 100 * (max(v) - min(v))

    assert spread(50, 100) == pytest.approx(3.9, abs=0.8) and spread(50, 130) < 0.7
    assert spread(10, 130) == pytest.approx(1.8, abs=0.8) and spread(4, 130) == pytest.approx(4.3, abs=0.8)
    assert spread(50, 100) > 4 * spread(50, 130)


def test_fixed_patience_waits_longest_in_every_cell_with_waiting():
    for x in PRE["study"]:
        if x["rho_pct"] >= 90:
            k = x["kinds"]
            assert k["fest"]["wq"] > k["exp"]["wq"] and k["fest"]["wq"] > k["uniform"]["wq"], (x["c"], x["rho_pct"])


def test_staffing_quoted_in_readme():
    """README (Geduld 5 min, Ziel 1 % Abbrecher): a = 10: 15 Spuren (ohne Warteplatz 18), 20: 26 (30), 50: 57 (64), 100: 108 (117),
    200: 209 (221); a = 50 nach Geduld 0.25/1/5/60 min: 62/60/57/52 Spuren."""
    for a, c, c_loss in ((10, 15, 18), (20, 26, 30), (50, 57, 64), (100, 108, 117), (200, 209, 221)):
        row = E.staffing_row(a, 5, 0.01)
        assert (row["c"], row["c_loss"]) == (c, c_loss), a
    by_patience = dict(E.staffing_vs_patience(50, 0.01))
    assert [by_patience[p] for p in (0.25, 1, 5, 60)] == [62, 60, 57, 52]


def test_big_gates_may_run_in_overload_at_five_percent_abandonment():
    """README: Bei Ziel 5 % genügen für a = 100 nur 98 Spuren und für a = 200 nur 192 (Angebot über der Kapazität), für a = 50 genau 50."""
    assert E.staffing_row(100, 5, 0.05)["c"] == 98 and E.staffing_row(200, 5, 0.05)["c"] == 192
    assert E.staffing_row(50, 5, 0.05)["c"] == 50 and E.staffing_row(20, 5, 0.05)["c"] == 22


def test_standard_errors_of_the_study_quoted_in_readme():
    """README: Standardfehler der Abbruchquoten (Standardabweichung eines Laufs / √20) höchstens 0.13 Prozentpunkte."""
    n_reps = PRE["study_reps"]
    worst = max(k["p_ab_sd"] for x in PRE["study"] for k in x["kinds"].values()) / n_reps ** 0.5
    assert worst < 0.0015
