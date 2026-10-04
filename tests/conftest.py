import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class ScriptedRng:
    """Liefert vorgegebene Werte statt Zufall (Mini-Instanzen von Hand gerechnet). `expovariate(rate)` ignoriert die
    Rate und gibt der Reihe nach die Werte zurück, `uniform()` ebenso aus einer eigenen Liste."""

    def __init__(self, exp_values=(), uniform_values=()):
        self.exp_values, self.uniform_values = list(exp_values), list(uniform_values)
        self.n_exp = self.n_uniform = 0

    def expovariate(self, rate):
        v = self.exp_values[self.n_exp]
        self.n_exp += 1
        return v

    def uniform(self):
        v = self.uniform_values[self.n_uniform]
        self.n_uniform += 1
        return v


@pytest.fixture
def mini_streams():
    """Vier Lkw an EINER Spur mit Geduld (Art "uniform", Mittel 5: Geduld = 10·u1): Zwischenankünfte 1 / 0.5 / 0.5 / 3.5
    (Ankünfte bei 1, 1.5, 2, 5.5), Bedienzeiten 3 / 9 / 1 / 2, Geduld 5 / 1 / 5 / 5.
    Von Hand: Lkw 1 startet bei 1 (Abgang 4); Lkw 2 wartet ab 1.5 und bricht bei 2.5 ab (Wartezeit 1); Lkw 3 wartet ab 2,
    startet bei 4 (Wartezeit 2, Abgang 5; sein Abbruch-Termin bei 7 verfällt); Lkw 4 startet bei 5.5 (Abgang 7.5)."""
    gap = ScriptedRng(exp_values=[1, 0.5, 0.5, 3.5])
    svc = ScriptedRng(exp_values=[3, 9, 1, 2])
    pat = ScriptedRng(uniform_values=[0.5, 0.0, 0.1, 0.0, 0.5, 0.0, 0.5, 0.0])
    return gap, svc, pat
