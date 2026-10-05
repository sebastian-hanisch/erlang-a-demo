"""Auswertung der Simulation gegen die Formeln: Kennzahlen, Verteilung, Little-Gegenprobe, Erlang C gegen Erlang A,
Überlast-Grenzwert, Spurbedarf bei Ungeduld und die Studie zur Form der Geduld. Die teure Studie (viele lange Läufe) steht
vorgerechnet in `precomputed_sweep.json` (Generator: generate_precomputed.py, Laden: `load_precomputed`)."""

import json
import statistics
from pathlib import Path

import era_constants as C
import era_formulas as F
from era_simulation import MU, PATIENCE_KINDS, SplitMix64, rates, simulate

PRECOMPUTED_PATH = Path(__file__).resolve().parent / "precomputed_sweep.json"


def theta_of(mean_patience):
    """Abbruchrate θ = 1/mittlere Geduld (je Minute)."""
    return 1.0 / mean_patience


def formula_metrics(c, rho_pct, mean_patience):
    lam, mu = rates(c, rho_pct)
    return F.stationary_metrics(c, lam, mu, theta_of(mean_patience))


def warm_time_min(mean_patience):
    """Einschwingzeit des leeren Starts in Minuten: nicht ausgewertet. Mindestens `WARM_MIN_FLOOR`, bei großer Geduld das
    `WARM_PATIENCE_FACTOR`-Fache der mittleren Geduld."""
    return max(C.WARM_MIN_FLOOR, C.WARM_PATIENCE_FACTOR * mean_patience)


def warmup_customers(lam, mean_patience, seed):
    """Zahl der Lkw, die in der Einschwingzeit ankommen und zusätzlich simuliert, aber nicht ausgewertet werden: gezählt am Ankunftsstrom
    des Laufs (eine Kopie des Generators mit demselben Seed), damit genau die gewünschte Zahl Lkw ausgewertet wird."""
    gap_rng, warm, t, k = SplitMix64(seed), warm_time_min(mean_patience), 0.0, 0
    while True:
        t += gap_rng.expovariate(lam)
        if t >= warm:
            return k
        k += 1


def simulate_gate(c, lam, mu, mean_patience, n_customers, seed, kind="exp", record=False):
    """Ein Lauf mit Einschwingzeit: simuliert werden die Lkw der Einschwingzeit plus `n_customers`; ausgewertet werden genau die
    `n_customers` Lkw danach."""
    return simulate(c, lam, mu, mean_patience, n_customers + warmup_customers(lam, mean_patience, seed), seed, kind=kind, record=record,
                    warm_time=warm_time_min(mean_patience))


def run_live(c, rho_pct, mean_patience, n_customers, seed, kind="exp", record=True):
    lam, mu = rates(c, rho_pct)
    return simulate_gate(c, lam, mu, mean_patience, n_customers, seed, kind=kind, record=record)


def little_check(sim):
    """Little's Gesetz auf dem simulierten Pfad: (L aus ∫N dt / T, λ̂ · Ŵ, relative Abweichung); gilt exakt, weil jeder Lauf
    leer endet und jeder Lkw (bedient oder abgebrochen) genau seine Verweilzeit zur Fläche unter N(t) beiträgt."""
    l_hat = sim.mean_in_system
    lw = sim.arrival_rate * sim.mean_sojourn
    return l_hat, lw, abs(l_hat - lw) / l_hat if l_hat else 0.0


def state_distribution(sim, max_state=C.MAX_STATE_SHOWN):
    """Anteil der Zeit mit genau n im System (n = 0 … max_state) im Messfenster (nach der Einschwingzeit); der Rest darüber wird
    zusammengefasst."""
    total = sum(sim.eval_time_in_state.values())
    shares = [sim.eval_time_in_state.get(n, 0.0) / total for n in range(max_state + 1)]
    return shares, max(0.0, 1.0 - sum(shares))


def window_steps(trajectory, start_min, end_min):
    """Treppenkurve N(t) im Fenster [start_min, end_min] für `line_shape='hv'`: links mit dem Wert zum Fensterbeginn,
    rechts mit dem letzten Wert im Fenster abgeschlossen."""
    n_start = 0
    pts = []
    for t, n in trajectory:
        if t <= start_min:
            n_start = n
        elif t <= end_min:
            pts.append((t, n))
        else:
            break
    out = [(start_min, n_start)] + pts
    out.append((end_min, out[-1][1]))
    return out


def erlang_c_vs_a(c, mean_patience, rho_pct_values):
    """Mittlere Wartezeit über der Auslastung: Erlang C (unendliche Geduld, nur ρ < 1, sonst None) gegen Erlang A. Rückgabe:
    Liste von (ρ in %, Wq Erlang C oder None, Wq Erlang A)."""
    out = []
    for rho_pct in rho_pct_values:
        lam, mu = rates(c, rho_pct)
        wq_c = F.erlang_c_wq(c, lam, mu) if rho_pct < 100 else None
        out.append((rho_pct, wq_c, F.stationary_metrics(c, lam, mu, theta_of(mean_patience))["Wq"]))
    return out


def abandon_curve(c, mean_patience, rho_pct_values):
    """Abbruchquote über der Auslastung (Formel): Liste von (ρ in %, P(abbrechen))."""
    return [(r, formula_metrics(c, r, mean_patience)["p_abandon"]) for r in rho_pct_values]


def staffing_row(a, mean_patience, target):
    """Kleinste Spurzahl für eine Ziel-Abbruchquote bei Angebot a und der gewählten Geduld, dazu die Spurzahl, die ein System
    OHNE Warteplatz brauchte (Erlang B, Geduld null), und die erreichte Abbruchquote/Auslastung."""
    theta = theta_of(mean_patience)
    c_a = F.min_servers_for_abandon(a, MU, theta, target)
    c_b = F.min_servers_loss(a, target)
    m = F.stationary_metrics(c_a, a * MU, MU, theta)
    return {"a": a, "patience": mean_patience, "target": target, "c": c_a, "c_loss": c_b, "p_abandon": m["p_abandon"],
            "utilisation": m["utilisation"], "wq": m["Wq"]}


def staffing_vs_patience(a, target, patiences=C.STAFFING_PATIENCES):
    """Spurbedarf über der mittleren Geduld (Formeln): Liste von (Geduld, Spuren)."""
    return [(p, F.min_servers_for_abandon(a, MU, theta_of(p), target)) for p in patiences]


def patience_study(c, rho_pct, mean_patience, n, reps, seed_base):
    """Über `reps` Läufe je Geduld-Verteilung (alle mit denselben Ankunfts- und Bedienzeiten-Strömen, nur die Geduld wird
    anders gezogen): Mittelwerte und Standardabweichung von Abbruchquote und mittlerer Wartezeit aller Lkw."""
    lam, mu = rates(c, rho_pct)
    out = {}
    for kind in PATIENCE_KINDS:
        p_ab, wq = [], []
        for r in range(reps):
            sim = simulate_gate(c, lam, mu, mean_patience, n, seed_base + 97 * r, kind=kind)
            p_ab.append(sim.abandon_rate)
            wq.append(sim.mean_wait_all)
        out[kind] = {"p_ab": statistics.fmean(p_ab), "p_ab_sd": statistics.stdev(p_ab),
                     "wq": statistics.fmean(wq), "wq_sd": statistics.stdev(wq)}
    return {"c": c, "rho_pct": rho_pct, "patience": mean_patience, "n": n, "reps": reps, "kinds": out}


def load_precomputed():
    with open(PRECOMPUTED_PATH, encoding="utf-8") as f:
        return json.load(f)


def nearest(grid, value):
    """Nächster Wert der Studien-Achse (bei Gleichstand der kleinere)."""
    return min(grid, key=lambda g: (abs(g - value), g))


def study_cell(precomputed, c, rho_pct):
    """Zelle der Geduld-Studie für (gemessene Spurzahl, gemessene Auslastung)."""
    return next(x for x in precomputed["study"] if x["c"] == c and x["rho_pct"] == rho_pct)
