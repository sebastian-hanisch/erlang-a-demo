"""Formeln der Erlang-A-Schlange (M/M/c+M): Poisson-Ankünfte (λ), exponentielle Abfertigung (μ je Spur), c Spuren, EINE
FIFO-Schlange, ungeduldige Kunden brechen mit Rate θ = 1/mittlere Geduld ab, solange sie warten. Zeiten in Minuten, Raten je
Minute. Anders als bei Erlang C (θ = 0) gibt es auch für ρ = λ/(cμ) ≥ 1 ein Gleichgewicht.

Erlang A liegt zwischen Erlang C (Geduld unendlich, θ → 0) und Erlang B (Geduld null, θ → ∞): die Erlang-B- und -C-Formeln
stehen hier zur Gegenprobe (Kopie aus mmc-queue-demo, Stück 3 - bewusst ohne Import zwischen Repos)."""

import math

MAX_STATES = 200_000       # Obergrenze der Kettenlänge (Sicherheitsnetz, wird in der Praxis nie erreicht)


def erlang_b(c, a):
    """Erlang-B-Verlustwahrscheinlichkeit B(c, a) über die stabile Rekursion B_k = a·B_{k-1}/(k + a·B_{k-1})."""
    b = 1.0
    for k in range(1, c + 1):
        b = a * b / (k + a * b)
    return b


def erlang_c(c, a):
    """Erlang C: Wahrscheinlichkeit zu warten (alle Spuren belegt), C = B/(1 − ρ(1 − B)), nur für ρ = a/c < 1."""
    rho = a / c
    if rho >= 1:
        raise ValueError("ρ ≥ 1: bei unendlicher Geduld keine stationäre Verteilung")
    b = erlang_b(c, a)
    return b / (1 - rho * (1 - b))


def erlang_c_wq(c, lam, mu):
    """Mittlere Wartezeit bei Erlang C (unendliche Geduld): Wq = C/(cμ − λ)."""
    return erlang_c(c, lam / mu) / (c * mu - lam)


def stationary_distribution(c, lam, mu, theta):
    """Stationäre Verteilung p_n der Zahl im System. Geburts-Sterbe-Kette mit Geburtsrate λ und Sterberate
    min(n, c)·μ + max(n − c, 0)·θ, gerechnet in Logarithmen (kein Überlauf bei großen c) und abgeschnitten, sobald die
    Wahrscheinlichkeiten nach dem Gipfel unter 1e-18 fallen. θ > 0 ist nötig (θ = 0 nur für ρ < 1, dann Erlang C)."""
    if theta <= 0 and lam >= c * mu:
        raise ValueError("θ = 0 und ρ ≥ 1: keine stationäre Verteilung")
    logs = [0.0]
    peak = 0.0
    for n in range(1, MAX_STATES):
        death = min(n, c) * mu + max(n - c, 0) * theta
        logs.append(logs[-1] + math.log(lam) - math.log(death))
        peak = max(peak, logs[-1])
        if n > c and logs[-1] < peak - 41.5:        # e^-41.5 ≈ 1e-18 unter dem Gipfel
            break
    shift = max(logs)
    weights = [math.exp(x - shift) for x in logs]
    total = sum(weights)
    return [w / total for w in weights]


def stationary_metrics(c, lam, mu, theta):
    """Kennzahlen im Gleichgewicht: Abbruchquote P(ab) = θ·Lq/λ, Wahrscheinlichkeit zu warten (alle c Spuren belegt, nach
    PASTA), mittlere Wartezeit ALLER Lkw (auch der Abbrecher) Wq = Lq/λ (Little), mittlere Zahl im System L, Durchsatz
    λ·(1 − P(ab)) und Auslastung je Spur."""
    p = stationary_distribution(c, lam, mu, theta)
    lq = sum((n - c) * p[n] for n in range(c, len(p)))
    p_ab = theta * lq / lam
    busy = sum(min(n, c) * p[n] for n in range(len(p)))
    return {"c": c, "rho": lam / (c * mu), "p_abandon": p_ab, "p_wait": sum(p[c:]), "Wq": lq / lam, "Lq": lq,
            "L": sum(n * p[n] for n in range(len(p))), "throughput": lam * (1 - p_ab), "utilisation": busy / c}


def fluid_abandon_rate(rho):
    """Grenzwert der Abbruchquote bei sehr vielen Spuren: max(0, 1 − 1/ρ) (Überlast: alles Überschüssige bricht ab)."""
    return max(0.0, 1.0 - 1.0 / rho)


def min_servers_for_abandon(a, mu, theta, target):
    """Kleinste Spurzahl c, bei der die Abbruchquote höchstens `target` beträgt (Angebot a = λ/μ)."""
    lam = a * mu
    c = max(1, math.ceil(a * (1 - target) - 1e-9))    # Durchsatz λ(1 − P(ab)) ≤ cμ: weniger Spuren kann das Ziel nie erreichen
    while stationary_metrics(c, lam, mu, theta)["p_abandon"] > target:
        c += 1
    return c


def min_servers_loss(a, target):
    """Kleinste Spurzahl c mit Erlang-B-Verlustwahrscheinlichkeit ≤ target (niemand wartet: Geduld null)."""
    c = max(1, math.ceil(a * (1 - target) - 1e-9))    # gleiche Durchsatz-Untergrenze wie oben
    while erlang_b(c, a) > target:
        c += 1
    return c
