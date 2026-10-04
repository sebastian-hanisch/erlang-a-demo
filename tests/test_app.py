"""AppTest-Rauchtests: Voreinstellung, jedes Preset, Überlast, Randwerte, Würfel-Knopf, Permalink-Grenzen, Abschnitte, Footer."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import era_constants as C

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _run(**state):
    at = AppTest.from_file(APP, default_timeout=300)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]


def _metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def test_default_run_has_no_exception_and_shows_formula_and_simulation():
    at = _run()
    _ok(at)
    assert _metric(at, "Abbruchquote (Formel)") == "9.0 %"
    assert _metric(at, "Wartezeit aller Lkw (Formel)") == "0.45 min"
    assert _metric(at, "Zum Vergleich Erlang C (ohne Abbruch)") == "4.95 min"
    assert _metric(at, "Little's Gesetz im Lauf: L gegen λ·W") == "stimmt"


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_button_runs(name):
    at = _run()
    next(b for b in at.button if b.key == f"preset_{name}").click().run()
    _ok(at)
    p = C.PRESETS[name]
    assert at.session_state["c_slider"] == p["c"] and at.session_state["patience_slider"] == p["patience"]
    assert at.metric


def test_overload_has_formula_values_but_no_erlang_c():
    at = _run(rho_slider=130)
    _ok(at)
    assert _metric(at, "Abbruchquote (Formel)") == "24.8 %"
    assert _metric(at, "Zum Vergleich Erlang C (ohne Abbruch)").startswith("gilt nicht")
    assert any("keine Antwort" in s.value for s in at.success)


def test_exactly_at_the_stability_limit_has_no_erlang_c():
    at = _run(rho_slider=100)
    _ok(at)
    assert _metric(at, "Zum Vergleich Erlang C (ohne Abbruch)").startswith("gilt nicht")


@pytest.mark.parametrize("kw", [dict(c_slider=C.C_MIN), dict(c_slider=C.C_MAX), dict(rho_slider=C.RHO_PCT_MIN),
                                 dict(rho_slider=C.RHO_PCT_MAX), dict(patience_slider=C.PATIENCE_MIN),
                                 dict(patience_slider=C.PATIENCE_MAX), dict(n_select=C.N_OPTIONS[0]),
                                 dict(n_select=C.N_OPTIONS[-1], c_slider=50, rho_slider=150),
                                 dict(c_slider=1, rho_slider=150, patience_slider=30, n_select=1000),
                                 dict(staffing_load=200, staffing_target=0.05), dict(staffing_load=10, staffing_target=0.01),
                                 dict(study_c=50, study_rho=130), dict(study_c=4, study_rho=80)])
def test_extreme_settings_run(kw):
    _ok(_run(**kw))


def test_more_patience_changes_the_main_metrics():
    short, long_ = _run(patience_slider=1), _run(patience_slider=30)
    assert _metric(short, "Abbruchquote (Formel)") == "13.6 %" and _metric(long_, "Abbruchquote (Formel)") == "4.3 %"
    assert _metric(short, "Wartezeit aller Lkw (Formel)") != _metric(long_, "Wartezeit aller Lkw (Formel)")


def test_dice_button_changes_the_seed_and_the_result():
    at = _run()
    old_seed, old = at.session_state["seed_input"], _metric(at, "Abbruchquote (simuliert)")
    next(b for b in at.button if b.label == "🎲 Neuen Lauf würfeln").click().run()
    _ok(at)
    assert at.session_state["seed_input"] != old_seed and _metric(at, "Abbruchquote (simuliert)") != old


def test_window_slider_exists_for_long_runs():
    at = _run()
    sl = next(s for s in at.slider if s.key == "window_start_h")
    assert sl.min == 0 and sl.max > 20
    at.slider(key="window_start_h").set_value(sl.max).run()
    _ok(at)


def test_staffing_section_hand_values():
    at = _run(staffing_load=50, staffing_target=0.01)
    _ok(at)
    assert _metric(at, "Nötige Spuren (mit Warteplatz)") == "57" and _metric(at, "Nötige Spuren (ohne Warteplatz)") == "64"
    assert _metric(at, "Eingesparte Spuren") == "7"
    assert any("spart 7 Spuren" in i.value for i in at.info)


def test_study_section_shows_the_four_distributions():
    at = _run(study_c=50, study_rho=100)
    _ok(at)
    text = " ".join(i.value for i in at.info)
    assert "exponentieller" in text and "gleichverteilter" in text and "fester" in text and "lognormaler" in text


def test_permalink_values_are_clamped_and_snapped():
    at = AppTest.from_file(APP, default_timeout=300)
    at.query_params["c"] = "999"
    at.query_params["rho"] = "9999"
    at.query_params["pat"] = "-3"
    at.query_params["n"] = "3000"
    at.run()
    _ok(at)
    assert at.session_state["c_slider"] == C.C_MAX and at.session_state["rho_slider"] == C.RHO_PCT_MAX
    assert at.session_state["patience_slider"] == C.PATIENCE_MIN and at.session_state["n_select"] == 2000


def test_permalink_ignores_garbage():
    at = AppTest.from_file(APP, default_timeout=300)
    at.query_params["c"] = "viele"
    at.query_params["seed"] = "x"
    at.run()
    _ok(at)
    assert at.session_state["c_slider"] == C.DEFAULT_C and at.session_state["seed_input"] == C.DEFAULT_SEED


def test_charts_sections_and_limits_table_are_present():
    at = _run()
    _ok(at)
    assert len(at.get("plotly_chart")) == 6
    headers = [s.value for s in at.subheader]
    for part in ("Erlang C gegen Erlang A", "Überlast", "Form der Geduld", "Wie viele Spuren", "Wo die Annahmen enden"):
        assert any(part in h for h in headers), part
    table = next(m.value for m in at.markdown if "Wer setzt an" in m.value)
    for name in ("Halfin-Whitt", "zeitvariable Ankünfte", "Kingman", "Erlang B", "Prioritätsklassen"):
        assert name in table
    assert "geplant" not in table      # die Linie wird erst vollständig veröffentlicht, kein Status-Zusatz


def test_seed_control_uses_the_portfolio_wording():
    at = _run()
    assert [n.label for n in at.number_input] == ["Zufalls-Seed"]


def test_related_demos_are_linked_and_footer_is_present():
    at = _run()
    text = " ".join(c.value for c in at.caption)
    for name in ("mmc-queue-demo", "mm1-queue-demo", "ems-demo", "output-analysis-demo"):
        assert name in text
    assert "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net)" in text


def test_no_sentence_wide_comma_replacement_in_the_app_source():
    """Regressionsschutz: `.replace(",", ".")` auf einem ganzen (verketteten) Satz macht aus Kommas im Fließtext Punkte; Tausender
    nur über `fmt_int`."""
    source = Path(APP).read_text(encoding="utf-8")
    assert '.replace(",", ".")' not in source.replace('f"{n:,}".replace(",", ".")', "")
