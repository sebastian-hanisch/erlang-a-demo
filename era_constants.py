"""Konstanten der Erlang-A-Demo: Regler, Voreinstellungen, Messreihen-Parameter. Zeiten in Minuten."""


def fmt_int(n):
    """Ganzzahl mit Punkt als Tausendertrenner (10000 -> 10.000)."""
    return f"{n:,}".replace(",", ".")


def fmt_pct(x, digits=0):
    """Anteil als Prozent mit Leerzeichen (0.086 -> "9 %", mit digits=1 "8.6 %")."""
    return f"{x:.{digits}%}".replace("%", " %")


C_MIN, C_MAX, DEFAULT_C = 1, 50, 10                          # Spuren
RHO_PCT_MIN, RHO_PCT_MAX, DEFAULT_RHO_PCT = 10, 150, 95      # Auslastung JE SPUR in Prozent (auch Überlast)
PATIENCE_MIN, PATIENCE_MAX, DEFAULT_PATIENCE = 1, 30, 5      # mittlere Geduld (Minuten)
N_OPTIONS = (1000, 2000, 5000, 10000, 20000, 50000)          # Lkw je Lauf
DEFAULT_N = 10000
SEED_MAX = 999999
DEFAULT_SEED = 35

WINDOW_HOURS = 4                  # Fensterbreite der Treppenkurve N(t)
WINDOW_STEP_HOURS = 1
MAX_STATE_SHOWN = 120             # Balken der Verteilung der Zahl im System (darüber zusammengefasst)

# Vergleich Erlang C gegen Erlang A, Überlast-Grenzwert (nur Formeln)
FLUID_C = (4, 10, 50, 200)
FLUID_RHO_PCT = tuple(range(20, 201, 5))

# Spurbedarf bei Ungeduld (nur Formeln)
STAFFING_LOADS = (10, 20, 50, 100, 200)             # Angebot a = λ/μ in Erlang
STAFFING_TARGETS = (0.01, 0.02, 0.05)               # Ziel-Abbruchquote
DEFAULT_STAFFING_LOAD, DEFAULT_STAFFING_TARGET = 50, 0.01
STAFFING_PATIENCES = (0.25, 0.5, 1, 2, 5, 10, 20, 60)   # mittlere Geduld für das Diagramm

# Vorgerechnete Studie zur Form der Geduld (generate_precomputed.py)
STUDY_C = (4, 10, 50)
STUDY_RHO_PCT = (80, 90, 100, 110, 130)
STUDY_PATIENCE = 5
STUDY_N = 50000
STUDY_REPS = 20

PRESET_ORDER = ("Normalfall (10 Spuren, ρ = 95 %)", "Überlast (ρ = 130 %)", "Sehr ungeduldig (Geduld 1 min)",
                "Großes Gate (50 Spuren, ρ = 100 %)")


def _preset(c=DEFAULT_C, rho_pct=DEFAULT_RHO_PCT, patience=DEFAULT_PATIENCE, n=DEFAULT_N):
    return {"c": c, "rho_pct": rho_pct, "patience": patience, "n": n, "seed": DEFAULT_SEED}


PRESETS = {
    "Normalfall (10 Spuren, ρ = 95 %)": _preset(),
    "Überlast (ρ = 130 %)": _preset(rho_pct=130),
    "Sehr ungeduldig (Geduld 1 min)": _preset(patience=1),
    "Großes Gate (50 Spuren, ρ = 100 %)": _preset(c=50, rho_pct=100),
}
# Formelwerte bei 3 min Abfertigung je Spur (exakt, tests/test_claims.py rechnet sie nach)
PRESET_HELP = {
    "Normalfall (10 Spuren, ρ = 95 %)": "10 Spuren, ρ = 95 %, Geduld 5 min: 9.0 % der Lkw brechen ab, die mittlere Wartezeit aller Lkw beträgt 0.45 min. Erlang C (unendliche Geduld) würde 4.95 min sagen.",
    "Überlast (ρ = 130 %)": "ρ = 130 %: mehr Lkw als abgefertigt werden können, und trotzdem gibt es ein Gleichgewicht: 24.8 % brechen ab, die Spuren sind zu 97.8 % ausgelastet. Erlang C gilt hier nicht.",
    "Sehr ungeduldig (Geduld 1 min)": "10 Spuren, ρ = 95 %, aber nur 1 min Geduld: 13.6 % brechen ab, die mittlere Wartezeit aller Lkw sinkt auf 0.14 min, die Spuren sind zu 82 % ausgelastet.",
    "Großes Gate (50 Spuren, ρ = 100 %)": "50 Spuren genau am Limit (ρ = 100 %), Geduld 5 min: 4.9 % brechen ab, mittlere Wartezeit 0.25 min. Hier entscheidet die Form der Geduld über das Ergebnis (siehe Abschnitt dazu).",
}
