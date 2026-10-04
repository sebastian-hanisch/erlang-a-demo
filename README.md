# Erlang A – wenn Lkw nicht ewig warten (Streamlit-Demo)

Interaktive Demo zur **Erlang-A-Schlange** (M/M/c+M): das Terminal-Gate mit c Spuren und einer gemeinsamen Schlange aus
[mmc-queue-demo](https://github.com/sebastian-hanisch/mmc-queue-demo), jetzt mit **ungeduldigen Lkw**, die nach einer Weile
abbrechen. **Viertes Stück der Konzepte-Linie „Warteschlangentheorie und Simulation“** im Portfolio von
[Sebastian Hanisch](https://sebastianhanisch.net) (Operations Research und Machine Learning): ein Verfahren, ein wachsendes
Beispiel, jedes Folgestück hebt genau eine Annahme auf.

Erlang A liegt zwischen zwei Grenzfällen: **unendliche Geduld** ist Erlang C (Stück 3), **Geduld null** ist das Verlustsystem
Erlang B (Grundlage von [ems-demo](https://github.com/sebastian-hanisch/ems-demo)). Drei Befunde stehen im Mittelpunkt: Erlang C
überschätzt die Wartezeit massiv, sobald Kunden abbrechen; auch **Überlast (Auslastung über 100 %)** hat ein Gleichgewicht; und
**die Form der Geduld zählt**, nicht nur ihr Mittel.

## Kernfrage

Was ändert sich an Wartezeit, Auslastung und Spurbedarf, wenn Lkw nach einer zufälligen Geduld abbrechen, und wie robust sind die
Formeln dagegen, dass die Geduld nicht exponentiell verteilt ist?

## Modell und Methodik

- **Modell:** Poisson-Ankünfte (λ), exponentielle Abfertigung (μ je Spur, 3 min Mittel), c Spuren, eine FIFO-Schlange, Geduld mit
  Mittel 1/θ (Voreinstellung 5 min). Auslastung je Spur ρ = λ/(cμ), **auch über 100 %**. Regler: Spuren (1–50), Auslastung
  (10–150 %), mittlere Geduld (1–30 min), Lauflänge (1 000–50 000 Lkw), Zufalls-Seed. Voreinstellung: 10 Spuren, ρ = 95 %,
  Geduld 5 min, 10 000 Lkw.
- **Formeln** (`era_formulas.py`): Geburts-Sterbe-Kette mit Sterberate min(n, c)·μ + max(n − c, 0)·θ, in Logarithmen gerechnet
  (kein Überlauf bei großen c). Abbruchquote P(ab) = θ·Lq/λ, mittlere Wartezeit **aller** Lkw Wq = Lq/λ (Little, Abbrecher bis zum
  Abbruch eingerechnet), Wahrscheinlichkeit zu warten, Durchsatz, Auslastung; Grenzwert 1 − 1/ρ für sehr viele Spuren; Spurbedarf
  für eine Ziel-Abbruchquote. Unabhängige Referenz im Test: das lineare Gleichungssystem der abgeschnittenen Kette; zusätzlich die
  Grenzfälle θ → 0 (Erlang C) und θ → ∞ (Erlang-B-Verlustwahrscheinlichkeit).
- **Simulation** (`era_simulation.py`): Ereignisliste mit Ankünften, Abgängen und Abbruch-Terminen, je Ereignistyp ein Handler; Zufall
  aus SplitMix64 mit getrennten Strömen für Ankünfte, Bedienzeiten und Geduld (für jeden Lkw bei der Ankunft gezogen, damit der
  Strom bei jeder Verteilung gleich weiterläuft). Geduld exponentiell, gleichverteilt (0 bis 2·Mittel), fest oder lognormal
  (Variationskoeffizient 1.5), alle mit demselben Mittel.
- **Vorgerechnete Studie** (`generate_precomputed.py` → `precomputed_sweep.json`, knapp zwei Minuten parallel): 3 Spurzahlen × 5
  Auslastungen × 4 Geduld-Verteilungen, je 20 Läufe à 50 000 Lkw. Live läuft nur der gewählte Einzellauf.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stehen in `tests/test_claims.py`; Zeiten bei 3 min Abfertigung je Spur, Geduld im Mittel 5 min, wo nichts anderes steht.

| Frage | Befund |
|---|---|
| Wie viele brechen ab? | 10 Spuren, ρ = 95 %: **9.0 %**, mittlere Wartezeit aller Lkw 0.45 min. Mit nur 1 min Geduld 13.6 % (Wq 0.14 min, Auslastung 82 %), mit 30 min Geduld 4.3 %. |
| Wie falsch liegt Erlang C? | ρ = 95 %: 4 Spuren sagt Erlang C 13.4 min, Erlang A 0.77 min (das **17-Fache**); 10 Spuren 4.95 gegen 0.45 min (**11-fach**); 50 Spuren 0.75 gegen 0.15 min (5-fach). |
| Und in Überlast? | Es gibt ein Gleichgewicht: ρ = 130 %, 10 Spuren: **24.8 %** brechen ab, die Spuren sind zu 97.8 % ausgelastet. Erlang C hat dort keine Antwort. |
| Wie nah ist der Grenzwert 1 − 1/ρ? | ρ = 130 %: c = 4 28.5 %, c = 10 24.8 %, c = 50 23.1 %, c = 200 **23.08 %** gegen Grenzwert 23.08 %; ρ = 110 %: 20.9, 15.3, 10.4, 9.2 % gegen 9.1 %. |
| Stimmt die Simulation? | Bei exponentieller Geduld liegt das Mittel der 20 Läufe in allen 15 Zellen innerhalb von vier Standardfehlern an der Formel. |
| Zählt die Form der Geduld? | **Ja, nahe 100 % Auslastung.** 50 Spuren, ρ = 100 %, Mittel 5 min: Abbruchquote exponentiell **5.0 %**, gleichverteilt 4.1 %, lognormal 4.4 %, **fest 1.2 %**; mittlere Wartezeit 0.25 / 0.39 / 0.31 / **2.36 min** (fest: das 9-Fache). |
| Und in starker Überlast? | Kaum: ρ = 130 %: Spannweite der Abbruchquote über die vier Verteilungen 0.2 Prozentpunkte bei 50 Spuren (3.8 Punkte bei ρ = 100 %), 1.9 bei 10 Spuren, 4.3 bei 4 Spuren. |
| Wie viele Spuren spart das Warten-Lassen (Ziel höchstens 1 % Abbrecher, Geduld 5 min)? | Angebot a = 10: **15 gegen 18** Spuren ohne Warteplatz (Erlang B), a = 20: 26 gegen 30, a = 50: **57 gegen 64**, a = 100: 108 gegen 117, a = 200: 209 gegen 221. Bei a = 50 nach Geduld 0.25 / 1 / 5 / 60 min: 62 / 60 / 57 / 52 Spuren. |
| Darf das Angebot die Kapazität übersteigen? | Bei Ziel 5 % Abbrecher: a = 100 braucht nur **98 Spuren**, a = 200 nur **192** (a = 50: genau 50, a = 20: 22). Große Gates dürfen Überlast einplanen. |

## Befunde und Korrekturen gegenüber dem Plan

- **Fehler beim Handrechnen der Mini-Instanz gefunden und behoben:** Ein Abbruch-Termin eines Lkw, der inzwischen schon bedient
  wird, ließ in der ersten Fassung die Uhr weiterlaufen und hätte bei leerem Gate Zeit im Zustand 0 (und damit Laufzeit und
  Auslastung) verfälscht. Jetzt werden solche Termine übersprungen, bevor die Uhr vorgestellt wird; der Test mit der von Hand
  gerechneten Vier-Lkw-Instanz enthält genau diesen Fall (Termin bei 7, Abgang bei 7.5).
- **Die Form der Geduld zählt, aber nicht überall gleich stark.** Schon die Vorab-Messreihe zeigte bei 50 Spuren, dass das Mittel
  der Geduld nicht reicht. Die vollständige Studie zeigt, wo: nahe 100 % Auslastung am stärksten, in starker Überlast (ρ = 130 %,
  50 Spuren) praktisch nicht mehr (Tabelle). Die Literatur (Garnett, Mandelbaum, Reiman 2002 für exponentielle Geduld; Zeltyn und
  Mandelbaum 2005 für allgemeine Geduld) wurde nur auf Existenz und Gegenstand geprüft, nicht auf ihre einzelnen Aussagen.
- **Zusätzlich gefunden:** Bei Ziel 5 % darf das Angebot die Kapazität übersteigen (98 Spuren für a = 100), im Plan nicht vorgesehen.
- **Die Spurbedarf-Suche startet bei ⌈a·(1 − Ziel)⌉:** weniger Spuren kann das Ziel wegen des Durchsatzes nie erreichen; spart
  Rechenzeit und ist im Test an der Minimalität geprüft.

## Ehrliche Grenzen

- Die Geduld ist unabhängig vom Zustand der Schlange; Kunden kennen die Schlangenlänge nicht und kommen nach dem Abbruch nicht wieder.
- Die vier Geduld-Verteilungen sind eine Auswahl, keine Vollständigkeit; die Studie hat 20 Läufe je Zelle (Standardfehler der
  Abbruchquoten höchstens 0.13 Prozentpunkte, die Unterschiede bei 130 % sind teilweise Rauschen).
- Die Studie läuft bei drei Spurzahlen (4, 10, 50) und fünf Auslastungen (80 bis 130 %); die App zeigt die nächste Zelle.
- Wartezeit ist die mittlere Wartezeit **aller** Lkw einschließlich der Abbrecher bis zum Abbruch; die Wartezeit der Bedienten allein
  steht nur in der Simulation, nicht als Formel.
- Der Spurbedarf rechnet mit der Abbruchquote als Ziel; Ziele wie „95 % der Bedienten warten höchstens 5 min“ führen zu anderen Zahlen.
- Die Live-Ansicht rechnet **einen** Lauf; er streut wie in Stück 1 bis 3 um die Formel.

## Verwandte Demos im Portfolio

- [`mmc-queue-demo`](https://github.com/sebastian-hanisch/mmc-queue-demo) (Stück 3): dieselbe Schlange mit unendlicher Geduld (Erlang C).
- [`ems-demo`](https://github.com/sebastian-hanisch/ems-demo): Rettungsdienst-Standortplanung, prüft sich an der Erlang-B-Formel, dem
  Grenzfall „Geduld null“ dieser Demo.
- [`mm1-queue-demo`](https://github.com/sebastian-hanisch/mm1-queue-demo) (Stück 1) und
  [`output-analysis-demo`](https://github.com/sebastian-hanisch/output-analysis-demo) (Stück 2: Intervalle für Simulationsläufe).

## Bewusst nicht umgesetzt

Jede dieser Annahmen hebt ein Folgestück der Linie auf:

| Annahme | Folgestück |
|---|---|
| Konstante Ankunftsrate | Wurzel-Personalregel (Halfin-Whitt), zeitvariable Ankünfte |
| Abfertigungsdauer exponentiell | M/G/1, Kingman-Näherung |
| Unbegrenzte Schlange | M/M/c/c (Erlang B) |
| Alle Lkw gleich wichtig | Prioritätsklassen |

Kein Folgestück: Form der Geduld über die vier Beispiele hinaus, Wiederkehrer nach dem Abbruch, Kunden mit Kenntnis der Schlangenlänge.

## Tests

116 Tests, rund 50 s: Erlang A gegen die abgeschnittene Kette (auch Überlast), Handwert (c = 1, λ = μ = θ = 1: P(ab) = 1/e), Grenzfälle
Erlang B und C, Durchsatz-Bilanz, Spurbedarf auf Minimalität, Simulation gegen eine von Hand gerechnete Vier-Lkw-Instanz mit
Abbruch (Wartezeiten, ∫N dt, ∫Nq dt, Auslastung, Zeit je Zustand, Treppenkurve, verfallener Abbruch-Termin), Geduld-Verteilungen
(Mittel, Spannweite, Variationskoeffizient, Zufallsverbrauch), Little's Gesetz als Pfadidentität auch in Überlast, Simulation gegen
Formel (langer Lauf und Überlast), Grenzfälle der Simulation (Geduld 1e-9 gleich Erlang B, Geduld 1e9 gleich Erlang C),
Vollständigkeit der vorgerechneten Datei, Presets/Permalink, AppTest-Rauchtests, ein Quelltext-Test gegen Satz-Komma-Fehler und
`test_claims.py` für jede Zahl dieser README.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `era_formulas.py` | Erlang A, Grenzfälle (Erlang B/C), Grenzwert, Spurbedarf |
| `era_simulation.py` | Generator, Geduld-Verteilungen, Ereignissimulation mit Abbruch |
| `era_evaluation.py` | Kennzahlen, Verteilung, Erlang C gegen A, Spurbedarf, Studie zur Form der Geduld |
| `generate_precomputed.py` | rechnet die Studie vor → `precomputed_sweep.json` |
| `era_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `era_presets.py`, `era_constants.py` | Presets, Permalink, Grenzen |
| `tests/` | siehe oben |

## Literatur

- Garnett, O., Mandelbaum, A., Reiman, M. (2002): Designing a call center with impatient customers. *Manufacturing & Service
  Operations Management* 4(3), 208–227 (exakte Analyse und Näherungen für M/M/N+M).
- Zeltyn, S., Mandelbaum, A. (2005): Call centers with impatient customers: many-server asymptotics of the M/M/n+G queue.
  Technion-Manuskript (Betrieb in drei Regimen für viele Server und allgemeine Geduld).

## Lokal ausführen

```
pip install -r requirements.txt
streamlit run app.py
```

Tests: `pip install -r requirements-dev.txt` und `python -m pytest tests/ -v`. Studie neu rechnen: `python generate_precomputed.py`.

Gebaut mit Streamlit und Plotly.
