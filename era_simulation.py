"""Ereignisdiskrete Simulation einer Schlange mit c Spuren, einer gemeinsamen FIFO-Schlange und ungeduldigen Kunden
(M/M/c+G): wer wartet, bricht nach seiner Geduld ab.

Aufbau nach Einheiten (je Ereignistyp ein Handler, kein versteckter Zustand):
  - `draw_patience`: eine Geduld ziehen (exponentiell, gleichverteilt, fest oder lognormal, gleiches Mittel)
  - `handle_arrival`, `handle_departure`, `handle_abandon`: Zustandsübergänge
  - `simulate`: Ereignisschleife (Komposition, keine eigene Regel)

Zufall nur über übergebene `SplitMix64`-Generatoren (reine Ganzzahl-Arithmetik, Portfolio-Konvention): Ankünfte, Bedienzeiten
und Geduld haben je einen EIGENEN Strom, und die Geduld wird für JEDEN Lkw bei der Ankunft gezogen (auch wenn er sofort
bedient wird), damit der Strom bei verschiedenen Geduld-Verteilungen im Gleichschritt bleibt."""

import heapq
import math
from collections import deque
from dataclasses import dataclass, field

_MASK = (1 << 64) - 1
ARRIVAL, DEPARTURE, ABANDON = 0, 1, 2
MEAN_SERVICE_MIN = 3.0          # mittlere Abfertigungsdauer je Spur (Minuten) in allen Läufen der Demo
MU = 1.0 / MEAN_SERVICE_MIN
LOGNORMAL_CV = 1.5              # Variationskoeffizient der lognormalen Geduld
PATIENCE_KINDS = ("exp", "uniform", "fest", "lognorm")
PATIENCE_LABELS = {"exp": "exponentiell", "uniform": "gleichverteilt (0 bis 2·Mittel)", "fest": "fest (immer das Mittel)",
                   "lognorm": f"lognormal (Variationskoeffizient {LOGNORMAL_CV})"}


class SplitMix64:
    """Kleiner, gut gemischter 64-Bit-Zufallsgenerator (Vigna); reine Ganzzahl-Arithmetik."""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def uniform(self):
        """Gleichverteilt auf [0, 1) mit 53 Bit."""
        return (self.next() >> 11) * (1.0 / (1 << 53))

    def expovariate(self, rate):
        """Exponentiell mit Mittel 1/rate (Inversion; 1 − u liegt in (0, 1], der Logarithmus ist endlich)."""
        return -math.log(1.0 - self.uniform()) / rate


def rates(c, rho_pct):
    """(λ, μ) je Minute: Auslastung `rho_pct` (%) JE SPUR bei c Spuren und 3 min mittlerer Abfertigung, λ = ρ·c·μ (auch
    ρ ≥ 100 % ist erlaubt)."""
    return rho_pct / 100.0 * c * MU, MU


def streams(seed):
    """Die drei Zufallsströme eines Laufs: Ankünfte, Bedienzeiten, Geduld."""
    return SplitMix64(seed), SplitMix64(seed + 7_777_777), SplitMix64(seed + 15_555_555)


def draw_patience(kind, mean, rng):
    """Eine Geduld mit dem Mittel `mean`: exponentiell, gleichverteilt auf [0, 2·mean], fest (= mean) oder lognormal mit
    Variationskoeffizient 1.5 (Box-Muller). Zieht je Aufruf immer zwei Zufallszahlen, auch wo eine genügt, damit der Strom
    bei jeder Verteilung gleich weiterläuft."""
    u1, u2 = rng.uniform(), rng.uniform()
    if kind == "exp":
        return -math.log(1.0 - u1) * mean
    if kind == "uniform":
        return 2.0 * mean * u1
    if kind == "fest":
        return mean
    if kind == "lognorm":
        s2 = math.log(1.0 + LOGNORMAL_CV ** 2)
        z = math.sqrt(-2.0 * math.log(1.0 - u1)) * math.cos(2.0 * math.pi * u2)
        return math.exp(math.log(mean) - s2 / 2.0 + math.sqrt(s2) * z)
    raise ValueError(f"unbekannte Geduld-Verteilung: {kind}")


@dataclass
class SimResult:
    c: int
    n_customers: int
    end_time: float
    served_waits: list               # Wartezeit der bedienten Lkw (0 bei sofortiger Abfertigung)
    abandon_waits: list              # Wartezeit der Abbrecher bis zum Abbruch
    sojourns: float                  # Summe der Verweilzeiten aller Lkw (bediente: Warten + Bedienung, Abbrecher: Warten)
    area_in_system: float            # ∫ N(t) dt über [0, end_time]
    area_in_queue: float             # ∫ Nq(t) dt
    busy_integral: float             # ∫ (Zahl beschäftigter Spuren) dt
    time_in_state: dict
    n_waited: int                    # Lkw, die nicht sofort bedient wurden
    trajectory: list = field(default_factory=list)

    @property
    def abandon_rate(self):
        return len(self.abandon_waits) / self.n_customers

    @property
    def share_waiting(self):
        return self.n_waited / self.n_customers

    @property
    def mean_wait_all(self):
        """Mittlere Wartezeit ALLER Lkw (Bediente und Abbrecher)."""
        return (sum(self.served_waits) + sum(self.abandon_waits)) / self.n_customers

    @property
    def mean_wait_served(self):
        return sum(self.served_waits) / len(self.served_waits) if self.served_waits else 0.0

    @property
    def mean_in_system(self):
        return self.area_in_system / self.end_time

    @property
    def utilisation(self):
        return self.busy_integral / (self.c * self.end_time)

    @property
    def arrival_rate(self):
        return self.n_customers / self.end_time

    @property
    def mean_sojourn(self):
        return self.sojourns / self.n_customers


class _State:
    __slots__ = ("c", "t", "n", "queue", "busy", "events", "seq", "n_customers", "lam", "mu", "area_n", "area_q",
                 "busy_integral", "time_in_state", "status", "patience", "service_time", "arrival_time", "served_waits",
                 "abandon_waits", "sojourns", "n_waited", "trajectory", "record")


def _advance_clock(s, t_new):
    """Zeit auf t_new vorstellen und die Flächen sowie die Zeit je Zustand fortschreiben."""
    dt = t_new - s.t
    s.area_n += s.n * dt
    s.area_q += max(s.n - s.c, 0) * dt
    s.busy_integral += s.busy * dt
    s.time_in_state[s.n] = s.time_in_state.get(s.n, 0.0) + dt
    s.t = t_new


def _start_service(s, cid):
    """Kunde cid beginnt die Bedienung jetzt: Wartezeit festhalten, Abgang einplanen."""
    s.status[cid] = "served"
    s.served_waits.append(s.t - s.arrival_time[cid])
    s.busy += 1
    s.seq += 1
    heapq.heappush(s.events, (s.t + s.service_time[cid], s.seq, DEPARTURE, cid))


def handle_arrival(s, cid, gap_rng, svc_rng, pat_rng, kind, mean_patience):
    """Ein Lkw kommt an. Bedienzeit und Geduld werden beim Eintreffen gezogen (eigene Ströme); danach wird die nächste Ankunft
    eingeplant. Ist eine Spur frei, beginnt die Abfertigung sofort, sonst reiht er sich ein und bekommt einen Abbruch-Termin."""
    s.arrival_time[cid] = s.t
    s.service_time[cid] = svc_rng.expovariate(s.mu)
    s.patience[cid] = draw_patience(kind, mean_patience, pat_rng)
    s.n += 1
    if s.busy < s.c:
        _start_service(s, cid)
    else:
        s.status[cid] = "waiting"
        s.n_waited += 1
        s.queue.append(cid)
        s.seq += 1
        heapq.heappush(s.events, (s.t + s.patience[cid], s.seq, ABANDON, cid))
    if cid + 1 < s.n_customers:
        s.seq += 1
        heapq.heappush(s.events, (s.t + gap_rng.expovariate(s.lam), s.seq, ARRIVAL, cid + 1))
    return True


def handle_departure(s, cid):
    """Ein Lkw ist abgefertigt und gibt seine Spur frei. Der nächste Wartende (FIFO) rückt nach; wer schon abgebrochen hat,
    wird übersprungen."""
    s.sojourns += s.t - s.arrival_time[cid]
    s.n -= 1
    s.busy -= 1
    while s.queue:
        nxt = s.queue.popleft()
        if s.status[nxt] == "waiting":
            _start_service(s, nxt)
            break
    return True


def handle_abandon(s, cid):
    """Der Abbruch-Termin eines Lkw ist erreicht: war er noch in der Schlange, verlässt er sie ohne Bedienung; war er
    schon in Bedienung, passiert nichts (Rückgabe False: Zustand unverändert)."""
    if s.status[cid] != "waiting":
        return False
    s.status[cid] = "gone"
    s.abandon_waits.append(s.t - s.arrival_time[cid])
    s.sojourns += s.t - s.arrival_time[cid]
    s.n -= 1
    return True


def simulate(c, lam, mu, mean_patience, n_customers, seed, kind="exp", record=False, gap_rng=None, svc_rng=None,
             pat_rng=None):
    """Simuliert `n_customers` Ankünfte (Rate lam) an c Spuren mit Bedienrate mu je Spur und Geduld der Art `kind` mit Mittel
    `mean_patience` und läuft, bis alle bedient sind oder abgebrochen haben. Start leer. `record=True` schreibt die
    Treppenkurve N(t) mit; `*_rng` ersetzen die Ströme aus `seed` (für Tests mit vorgegebenen Zahlen)."""
    if gap_rng is None or svc_rng is None or pat_rng is None:
        gap_rng, svc_rng, pat_rng = streams(seed)
    s = _State()
    s.c, s.t, s.n, s.queue, s.busy = c, 0.0, 0, deque(), 0
    s.events, s.seq, s.n_customers, s.lam, s.mu = [], 0, n_customers, lam, mu
    s.area_n = s.area_q = s.busy_integral = 0.0
    s.time_in_state = {}
    s.status = [""] * n_customers
    s.patience, s.service_time, s.arrival_time = [0.0] * n_customers, [0.0] * n_customers, [0.0] * n_customers
    s.served_waits, s.abandon_waits, s.sojourns, s.n_waited = [], [], 0.0, 0
    s.trajectory, s.record = [(0.0, 0)] if record else [], record
    heapq.heappush(s.events, (gap_rng.expovariate(lam), 0, ARRIVAL, 0))
    while s.events:
        t, _, ev, cid = heapq.heappop(s.events)
        if ev == ABANDON and s.status[cid] != "waiting":
            continue            # Abbruch-Termin eines Lkw, der schon in Bedienung ist: Uhr und Flächen bleiben unberührt
        _advance_clock(s, t)
        if ev == ARRIVAL:
            changed = handle_arrival(s, cid, gap_rng, svc_rng, pat_rng, kind, mean_patience)
        elif ev == DEPARTURE:
            changed = handle_departure(s, cid)
        else:
            changed = handle_abandon(s, cid)
        if s.record and changed:
            s.trajectory.append((t, s.n))
    return SimResult(c, n_customers, s.t, s.served_waits, s.abandon_waits, s.sojourns, s.area_n, s.area_q,
                     s.busy_integral, s.time_in_state, s.n_waited, s.trajectory)
