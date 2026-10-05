"""Erlang A - wenn Lkw nicht ewig warten - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Viertes Stück der Konzepte-Linie "Warteschlangentheorie und Simulation": Das Terminal-Gate mit c Spuren und einer gemeinsamen
Schlange (Stück 3) bekommt ungeduldige Lkw, die nach einer Weile abbrechen (Erlang A, M/M/c+M). Die Demo zeigt, wie stark
Erlang C die Wartezeit dann überschätzt, dass auch Überlast (Auslastung über 100 %) ein Gleichgewicht hat und dass die FORM der
Geduld zählt, nicht nur ihr Mittel. Siehe README für die Einordnung in die Linie.

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import era_constants as C
import era_formulas as F
from era_evaluation import (formula_metrics, little_check, load_precomputed, nearest, run_live, staffing_row,
                            state_distribution, study_cell, theta_of, warm_time_min, window_steps)
from era_presets import (apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed,
                         sync_query_params)
from era_simulation import PATIENCE_KINDS, PATIENCE_LABELS, rates
from era_visualization import (build_c_vs_a, build_fluid_chart, build_patience_chart, build_staffing_chart,
                               build_state_distribution, build_trajectory)

st.set_page_config(page_title="Erlang A – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _precomputed():
    return load_precomputed()


@st.cache_data(show_spinner=False)
def _run(c, rho_pct, patience, n, seed):
    return run_live(c, rho_pct, patience, n, seed)


@st.cache_data(show_spinner=False)
def _staffing(a, patience, target):
    return staffing_row(a, patience, target)


def _min(x):
    return f"{x:.2f} min" if x < 10 else f"{x:.1f} min"


st.title("⏳ Erlang A: wenn Lkw nicht ewig warten")
st.markdown(
    """
In Stück 3 warteten alle Lkw, bis sie dran waren. Echte Fahrer geben auf: nach einer Weile (ihrer **Geduld**, hier im Mittel
einige Minuten) verlassen sie die Schlange, ohne abgefertigt zu werden, sie **brechen ab**. Mit exponentieller Geduld ist das
die **Erlang-A-Schlange** (M/M/c+M). Drei Folgen, jede unten gemessen: **Erlang C überschätzt die Wartezeit massiv**, sobald
Kunden abbrechen. **Auch Überlast (Auslastung über 100 %) hat ein Gleichgewicht**, weil die Schlange sich durch Abbrecher
selbst begrenzt. Und: **Die Form der Geduld zählt**, nicht nur ihr Mittel.
"""
)
st.caption(
    "Viertes Stück der Linie „Warteschlangentheorie und Simulation“, aufbauend auf "
    "[mmc-queue-demo](https://sebastianhanisch-mmc-queue-demo.streamlit.app/) (Erlang C, unendliche Geduld) und "
    "[mm1-queue-demo](https://sebastianhanisch-mm1-queue-demo.streamlit.app/). Jedes Folgestück hebt eine der Annahmen unter "
    "„Wo die Annahmen enden“ auf."
)

with st.expander("So funktioniert Erlang A", expanded=True):
    st.markdown(
        """
- **Geduld:** Wer warten muss, bricht nach einer zufälligen Zeit ab (Mittel 1/θ). Wer schon bedient wird, geht nicht mehr.
- **Gleichgewicht für jede Auslastung:** Mit Abbruchrate θ > 0 wächst die Schlange bei Überlast nicht ohne Grenze: je länger
  sie ist, desto mehr Lkw brechen ab. Die Zahl im System ist eine Geburts-Sterbe-Kette mit Sterberate
  min(n, c)·μ + max(n − c, 0)·θ.
- **Abbruchquote** P(ab) = θ·Lq/λ (aus der Bilanz: abgebrochene Lkw je Minute = θ mal mittlere Schlangenlänge).
- **Zwischen zwei Grenzfällen:** Geduld unendlich (θ → 0) ist **Erlang C**, Geduld null (θ → ∞) ist das Verlustsystem
  **Erlang B** (wer alle Spuren belegt findet, geht sofort).
- **Simulation:** Ereignis für Ereignis mit Abbruch-Terminen; dieselben Zufallsströme für Ankünfte und Bedienzeiten wie in
  Stück 3, dazu ein eigener Strom für die Geduld.
        """
    )

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_cols = st.columns(len(C.PRESET_ORDER))
for i, name in enumerate(C.PRESET_ORDER):
    with preset_cols[i]:
        st.button(name, key=f"preset_{name}", width="stretch", on_click=apply_preset, args=(name,),
                  help=C.PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    c = st.slider("Zahl der Spuren c", *bounds("c_slider"), key="c_slider",
                  help="Gleich schnelle Spuren mit einer gemeinsamen Schlange.")
    rho_pct = st.slider("Auslastung ρ je Spur", *bounds("rho_slider"), key="rho_slider", format="%d %%",
                        help="Ankunftsrate geteilt durch die Abfertigungsrate aller Spuren. Auch über 100 % (Überlast) "
                             "ist erlaubt: Abbrecher halten die Schlange endlich.")
    patience = st.slider("Mittlere Geduld (Minuten)", *bounds("patience_slider"), key="patience_slider",
                         help="Nach so langer Wartezeit bricht ein Lkw im Mittel ab (exponentiell verteilt).")
    n = st.select_slider("Ausgewertete Lkw je Lauf", options=C.N_OPTIONS, key="n_select",
                         help="Länge des ausgewerteten Teils des Simulationslaufs. Davor läuft eine Einschwingzeit vom leeren Gate aus, "
                              "die nicht ausgewertet wird (mindestens 30 Minuten, bei großer Geduld das Fünffache der mittleren Geduld). "
                              "Die mittlere Abfertigungsdauer je Spur ist fest 3 min; sie verschiebt nur die Zeitachse.")
    seed = st.number_input("Zufalls-Seed", min_value=bounds("seed_input")[0], max_value=bounds("seed_input")[1],
                           step=1, key="seed_input", help="Bestimmt alle Zufallszahlen des Laufs.")
    st.button("🎲 Neuen Lauf würfeln", on_click=randomize_seed)

c, rho_pct, patience, n, seed = int(c), int(rho_pct), int(patience), int(n), int(seed)
sync_query_params({"c_slider": c, "rho_slider": rho_pct, "patience_slider": patience, "n_select": n, "seed_input": seed})

lam, mu = rates(c, rho_pct)
theta = theta_of(patience)
formula = formula_metrics(c, rho_pct, patience)
pre = _precomputed()

with st.spinner("Simuliere das Gate …"):
    sim = _run(c, rho_pct, patience, n, seed)

st.markdown("---")
st.markdown("## ⏳ Das Gate in Zahlen")
st.caption(
    f"{c} Spuren, je μ = {mu * 60:.0f} Lkw/h (3 min Abfertigung), Ankunftsrate λ = {lam * 60:.1f} Lkw/h, mittlere Geduld "
    f"{patience} min, etwa {C.fmt_int(n)} ausgewertete Lkw nach {warm_time_min(patience):.0f} min Einschwingzeit. Auslastung der "
    f"Spuren: Formel {C.fmt_pct(formula['utilisation'])}, simuliert {C.fmt_pct(sim.utilisation)}."
)
l_hat, lw_hat, little_gap = little_check(sim)
r1 = st.columns(3)
r1[0].metric("Auslastung ρ (Angebot je Spur)", f"{rho_pct} %")
r1[1].metric("Abbruchquote (Formel)", C.fmt_pct(formula["p_abandon"], 1))
r1[2].metric("Abbruchquote (simuliert)", C.fmt_pct(sim.abandon_rate, 1),
             delta=f"{100 * (sim.abandon_rate - formula['p_abandon']):+.1f} Prozentpunkte gegen Formel", delta_color="off")
r2 = st.columns(3)
r2[0].metric("Wartezeit aller Lkw (Formel)", _min(formula["Wq"]))
r2[1].metric("Wartezeit aller Lkw (simuliert)", _min(sim.mean_wait_all),
             delta=f"{(sim.mean_wait_all - formula['Wq']) / formula['Wq']:+.1%} gegen Formel", delta_color="off")
erlang_c_wq = F.erlang_c_wq(c, lam, mu) if rho_pct < 100 else None
r2[2].metric("Zum Vergleich Erlang C (ohne Abbruch)", _min(erlang_c_wq) if erlang_c_wq is not None else "gilt nicht (ρ ≥ 100 %)")
r3 = st.columns(3)
r3[0].metric("Anteil, der warten muss (Formel)", C.fmt_pct(formula["p_wait"]))
r3[1].metric("Anteil, der warten muss (simuliert)", C.fmt_pct(sim.share_waiting),
             delta=f"{100 * (sim.share_waiting - formula['p_wait']):+.1f} Prozentpunkte gegen Formel", delta_color="off")
r3[2].metric("Little's Gesetz im Lauf: L gegen λ·W", "stimmt" if little_gap < 1e-6 else f"Abweichung {little_gap:.2%}",
             help=f"L = {l_hat:.4f} (Fläche unter der Kurve geteilt durch die Laufzeit), λ·W = {lw_hat:.4f} (Ankunftsrate mal "
                  "mittlere Verweilzeit aller Lkw, Abbrecher eingeschlossen). Auf jedem Lauf gleich.")
st.caption(
    "„Wartezeit aller Lkw“ zählt die Abbrecher mit ihrer Wartezeit bis zum Abbruch. Der Lauf startet mit leerem Gate; die Einschwingzeit "
    "wird nicht ausgewertet, sonst läge ein großes Gate bei kurzen Läufen weit unter dem Gleichgewicht. Wie in Stück 1 bis 3 ist ein "
    "einzelner Lauf eine Stichprobe: Er streut um die Formel; die Studie unten mittelt 20 Läufe à 50 000 Lkw."
)

st.markdown("### Die Schlange über der Zeit")
total_min = sim.end_time
window_min = C.WINDOW_HOURS * 60
max_start_h = int((total_min - window_min) // 60)
if max_start_h >= 1:
    start_h = st.slider("Fenster ab Stunde", 0, max_start_h, key="window_start_h", step=C.WINDOW_STEP_HOURS,
                        help=f"Zeigt {C.WINDOW_HOURS} Stunden des Laufs; 0 = vom leeren Gate aus.")
else:
    start_h = 0
start_min = start_h * 60
end_min = min(total_min, start_min + window_min)
st.plotly_chart(build_trajectory(window_steps(sim.trajectory, start_min, end_min), start_min, end_min, c, formula["L"]),
                width="stretch", key=f"traj_{c}_{rho_pct}_{patience}_{n}_{seed}_{start_h}")
shares, rest = state_distribution(sim)
st.markdown("**Wie viele Lkw stehen gleichzeitig im System?**")
st.plotly_chart(build_state_distribution(shares, rest, c, lam, mu, theta), width="stretch",
                key=f"dist_{c}_{rho_pct}_{patience}_{n}_{seed}")
if rest > 0.0005:
    st.caption(f"Weitere {rest:.1%} der Zeit stehen mehr als {C.MAX_STATE_SHOWN} Lkw im System (nicht gezeigt).")

st.markdown("---")
st.subheader("📐 Erlang C gegen Erlang A")
st.plotly_chart(build_c_vs_a(c, patience, rho_pct), width="stretch", key=f"c_vs_a_{c}_{patience}_{rho_pct}")
if erlang_c_wq is not None:
    st.success(
        f"Bei {c} Spuren und ρ = {rho_pct} % sagt Erlang C eine mittlere Wartezeit von **{_min(erlang_c_wq)}** voraus, "
        f"Erlang A mit {patience} min Geduld **{_min(formula['Wq'])}** (Erlang C liegt beim {erlang_c_wq / formula['Wq']:.1f}-Fachen), "
        f"weil {C.fmt_pct(formula['p_abandon'], 1)} der Lkw vorher abbrechen."
    )
else:
    st.success(
        f"Bei {c} Spuren und ρ = {rho_pct} % hat Erlang C keine Antwort (die Schlange würde ohne Grenze wachsen). Erlang A sagt: "
        f"mittlere Wartezeit aller Lkw **{_min(formula['Wq'])}**, **{C.fmt_pct(formula['p_abandon'], 1)}** der Lkw brechen ab."
    )
st.caption(
    "Die Kurve von Erlang C steigt bei 100 % ins Unendliche; Erlang A bleibt endlich und läuft sogar durch die 100 % hindurch. "
    "Gerechnet wird die mittlere Wartezeit ALLER Lkw (Abbrecher eingeschlossen)."
)

st.markdown("---")
st.subheader("📐 Überlast: wie viele brechen ab?")
st.plotly_chart(build_fluid_chart(patience), width="stretch", key=f"fluid_{patience}")
fluid = F.fluid_abandon_rate(rho_pct / 100)
st.info(
    f"Bei ρ = {rho_pct} % und {c} Spuren brechen {C.fmt_pct(formula['p_abandon'], 1)} der Lkw ab. Für sehr viele Spuren gilt der "
    f"Grenzwert 1 − 1/ρ = **{C.fmt_pct(fluid, 1)}**: in Überlast bricht ab, was die Spuren nicht abfertigen können. Bei wenigen "
    "Spuren liegt die Quote darüber, solange noch Schwankungen mitspielen, und unterhalb von 100 % ist sie nicht null."
)

st.markdown("---")
st.subheader("🔬 Die Form der Geduld")
st.markdown(
    f"Vier Geduld-Verteilungen mit **demselben Mittel von {pre['study_patience']} min**: exponentiell, gleichverteilt (0 bis "
    "2·Mittel), fest (jeder wartet genau das Mittel) und lognormal (stark streuend). Gemessen über "
    f"{pre['study_reps']} Läufe à {C.fmt_int(pre['study_n'])} Lkw, alle mit denselben Ankünften und Bedienzeiten."
)
sc1, sc2 = st.columns(2)
with sc1:
    study_c = st.select_slider("Spuren (Studie)", options=C.STUDY_C, value=nearest(C.STUDY_C, c), key="study_c")
with sc2:
    study_rho = st.select_slider("Auslastung (Studie)", options=C.STUDY_RHO_PCT, value=nearest(C.STUDY_RHO_PCT, rho_pct),
                                 format_func=lambda v: f"{v} %", key="study_rho")
cell = study_cell(pre, int(study_c), int(study_rho))
st.plotly_chart(build_patience_chart(cell), width="stretch", key=f"patience_{study_c}_{study_rho}")
kinds = cell["kinds"]
st.info(
    f"Bei {study_c} Spuren und ρ = {study_rho} % brechen mit **exponentieller** Geduld {C.fmt_pct(kinds['exp']['p_ab'], 1)} ab, "
    f"mit **gleichverteilter** {C.fmt_pct(kinds['uniform']['p_ab'], 1)}, mit **fester** {C.fmt_pct(kinds['fest']['p_ab'], 1)} und mit "
    f"**lognormaler** {C.fmt_pct(kinds['lognorm']['p_ab'], 1)}. Die mittlere Wartezeit aller Lkw liegt bei {_min(kinds['exp']['wq'])}, "
    f"{_min(kinds['uniform']['wq'])}, {_min(kinds['fest']['wq'])} und {_min(kinds['lognorm']['wq'])}."
)
ab_values = [k["p_ab"] for k in kinds.values()]
st.caption(
    f"Spannweite der Abbruchquote über die vier Verteilungen in dieser Zelle: {100 * (max(ab_values) - min(ab_values)):.1f} "
    "Prozentpunkte. Fehlerbalken: Standardabweichung eines Laufs."
)

st.markdown("---")
st.subheader("🔬 Wie viele Spuren braucht ein Gate mit Ungeduld?")
st.markdown(
    "Gegeben das **Angebot** a und eine **Ziel-Abbruchquote**: die kleinste Spurzahl, die sie einhält, verglichen mit einem System "
    "**ohne Warteplatz** (Erlang B), in dem jeder Lkw sofort geht, der alle Spuren belegt findet."
)
t1, t2 = st.columns(2)
with t1:
    load_a = st.select_slider("Angebot a", options=C.STAFFING_LOADS, value=C.DEFAULT_STAFFING_LOAD, key="staffing_load")
with t2:
    target = st.select_slider("Ziel: Abbruchquote höchstens", options=C.STAFFING_TARGETS, value=C.DEFAULT_STAFFING_TARGET,
                              format_func=lambda v: f"{v:.0%}", key="staffing_target")
row = _staffing(load_a, patience, target)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Nötige Spuren (mit Warteplatz)", row["c"])
m2.metric("Nötige Spuren (ohne Warteplatz)", row["c_loss"])
m3.metric("Eingesparte Spuren", row["c_loss"] - row["c"])
m4.metric("Auslastung der Spuren", C.fmt_pct(row["utilisation"]))
st.plotly_chart(build_staffing_chart(load_a, target, patience), width="stretch", key=f"staffing_{load_a}_{target}_{patience}")
st.info(
    f"Für das Angebot a = {load_a} und höchstens {C.fmt_pct(target)} Abbrecher genügen mit {patience} min Geduld **{row['c']} Spuren**, "
    f"ohne Warteplatz wären **{row['c_loss']}** nötig: das Warten-Lassen spart {row['c_loss'] - row['c']} Spuren, weil Spitzen "
    "in der Schlange abgepuffert statt abgewiesen werden. Je geduldiger die Lkw, desto größer die Ersparnis."
)

st.markdown("---")
st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist | Wer setzt an |
|---|---|---|
| **Geduld im Mittel bekannt und exponentiell** | Die Form zählt (Studie oben): bei gleichem Mittel unterscheiden sich Abbruchquote und Wartezeit je nach Verteilung deutlich, vor allem nahe 100 % Auslastung. | kein Folgestück |
| **Konstante Ankunftsrate** | Echte Gates haben Morgenspitzen; die Gleichgewichtsformeln mit dem Tagesmittel unterschätzen die Spitze. | **[Wurzel-Personalregel (Halfin-Whitt)](https://sebastianhanisch-square-root-staffing-demo.streamlit.app/)**, **[zeitvariable Ankünfte](https://sebastianhanisch-time-varying-arrivals-demo.streamlit.app/)** |
| **Abfertigungsdauer exponentiell** | Die Wartezeit hängt von der Streuung der Dauer ab. | **[M/G/1, Kingman-Näherung](https://sebastianhanisch-mg1-kingman-demo.streamlit.app/)** |
| **Unbegrenzte Schlange, Abbrecher kommen nicht wieder** | Mit begrenztem Stellplatz gehen Lkw verloren; der Grenzfall „Geduld null“ ist das Verlustsystem Erlang B. Wiederkehrende Abbrecher erhöhen die Last. | **[M/M/c/c (Erlang B)](https://sebastianhanisch-erlang-b-demo.streamlit.app/)**; Wiederkehrer: kein Folgestück |
| **Alle Lkw gleich wichtig** | Eilige Lkw brauchen Vorfahrt; das verschiebt Wartezeit und Abbrüche zwischen den Klassen. | **[Prioritätsklassen](https://sebastianhanisch-priority-queue-demo.streamlit.app/)** |
| **Kunden kennen die Schlange nicht** | Wer die Schlangenlänge sieht, entscheidet anders (gar nicht erst anstellen); hier hängt die Geduld nur vom Zufall ab. | kein Folgestück |
"""
)
st.caption(
    "Verwandt im Portfolio: [mmc-queue-demo](https://sebastianhanisch-mmc-queue-demo.streamlit.app/) (Stück 3: dieselbe Schlange mit "
    "unendlicher Geduld, Erlang C), die Rettungsdienst-Demo [ems-demo](https://sebastianhanisch-ems-demo.streamlit.app/) "
    "(prüft sich an der Erlang-B-Formel, dem Grenzfall Geduld null), [mm1-queue-demo](https://sebastianhanisch-mm1-queue-demo.streamlit.app/) "
    "(eine Spur) und [output-analysis-demo](https://sebastianhanisch-output-analysis-demo.streamlit.app/) (Intervalle für Simulationsläufe)."
)

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Modell** (Kendall-Notation M/M/c+M): Poisson-Ankünfte mit Rate $\lambda$, exponentielle Abfertigung mit Rate $\mu$ je Spur, $c$
Spuren, eine FIFO-Schlange, exponentielle Geduld mit Rate $\theta = 1/\text{mittlere Geduld}$. Auslastung je Spur
$\rho = \lambda/(c\mu)$, Angebot $a = \lambda/\mu$.

**Gleichgewicht.** Die Zahl der Lkw im System $N$ ist eine Geburts-Sterbe-Kette mit Geburtsrate $\lambda$ und Sterberate
$d_n = \min(n, c)\,\mu + (n - c)^+\,\theta$. Für $\theta > 0$ gibt es **für jedes** $\rho$ eine stationäre Verteilung
$$p_n = p_0 \prod_{k=1}^n \frac{\lambda}{d_k}.$$

**Kennzahlen.** Mittlere Schlangenlänge $L_q = \sum_{n > c} (n - c)\,p_n$. Die Bilanz der Abbrecher (abgebrochene Lkw je Minute
$= \theta L_q$, ankommende Lkw je Minute $= \lambda$) liefert die **Abbruchquote** $P(\text{ab}) = \theta L_q/\lambda$, nach
**Little** die mittlere Wartezeit aller Lkw $W_q = L_q/\lambda$ (Abbrecher bis zum Abbruch eingerechnet). Die Wahrscheinlichkeit
zu warten ist (PASTA) $\sum_{n \ge c} p_n$; der Durchsatz $\lambda(1 - P(\text{ab})) = \mu \sum_n \min(n, c)\,p_n$.

**Grenzfälle.** $\theta \to 0$ (und $\rho < 1$): Erlang C, $W_q = C(c, a)/(c\mu - \lambda)$. $\theta \to \infty$: wer alle Spuren
belegt findet, geht sofort; $P(\text{ab})$ geht gegen die Erlang-B-Verlustwahrscheinlichkeit $B(c, a)$.

**Überlast.** Für $c \to \infty$ (Fluid-Grenzwert) gilt $P(\text{ab}) \to \max(0,\ 1 - 1/\rho)$: bei $\rho > 1$ bricht ab, was die
Spuren nicht abfertigen können.

**Simulation.** Ereignisliste mit Ankünften, Abgängen und Abbruch-Terminen; die Geduld wird für jeden Lkw bei der Ankunft gezogen
(eigener Zufallsstrom, SplitMix64), ein Abbruch-Termin zählt nur, wenn der Lkw dann noch wartet. Little's Gesetz gilt auf dem Pfad
exakt: $\int_0^T N(t)\,dt$ ist die Summe der Verweilzeiten aller Lkw (bediente mit Bedienung, Abbrecher bis zum Abbruch).
Der Lauf startet mit leerem Gate; die Kennzahlen gegen die Formel (Abbruchquote, Wartezeit, Anteil Wartender, Auslastung, Verteilung der
Zahl im System) zählen nur Lkw, die nach der Einschwingzeit ankommen, und die Zeitmittel nur zwischen Ende der Einschwingzeit und
letzter Ankunft. Ohne sie läge das Gate mit 50 Spuren bei kurzen Läufen (1 000 Lkw) in Abbruchquote und Wartezeit rund 20 % unter der Formel.

Implementiert in `era_formulas.py` (Erlang A, Grenzfälle, Spurbedarf), `era_simulation.py` (Ereignissimulation mit Abbruch,
Geduld-Verteilungen), `era_evaluation.py` (Kennzahlen, Studie zur Form der Geduld), `generate_precomputed.py` (vorgerechnete Studie).
        """
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [Warteschlangentheorie: M/M/1 bis Surrogat](https://sebastianhanisch.net/konzepte-warteschlangentheorie.html)."
)
