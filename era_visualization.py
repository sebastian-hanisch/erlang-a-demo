"""Plotly-Abbildungen der Erlang-A-Demo: Treppenkurve mit Spurlinie, Verteilung der Zahl im System, Erlang C gegen Erlang A,
Überlast-Grenzwert, Form der Geduld, Spurbedarf. Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht
zoomen."""

import plotly.graph_objects as go

import era_constants as C
import era_evaluation as E
import era_formulas as F
from era_simulation import MU, PATIENCE_KINDS, PATIENCE_LABELS

SIM_COLOR = "#4c78a8"
FORMULA_COLOR = "#f58518"
GOOD_COLOR = "#54a24b"
BAD_COLOR = "#e45756"
KIND_COLORS = {"exp": "#4c78a8", "uniform": "#54a24b", "fest": "#e45756", "lognorm": "#7f3c8d"}
C_COLORS = {4: "#9ecae1", 10: "#4c78a8", 50: "#08519c", 200: "#08306b"}


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height, legend_y=-0.25, top=10):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=top, b=10), legend=dict(orientation="h", y=legend_y),
                      plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_trajectory(steps, start_min, end_min, c, formula_l):
    """Treppenkurve N(t) im Fenster (Minuten); waagerecht die Spurzahl c (darüber warten Lkw) und der Formelwert L."""
    x0, x1 = start_min / 60, end_min / 60
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[t / 60 for t, _ in steps], y=[n for _, n in steps], mode="lines", line_shape="hv",
                             line=dict(color=SIM_COLOR, width=2), name="Lkw im System (simuliert)",
                             hovertemplate="%{x:.2f} h: %{y} Lkw<extra></extra>"))
    fig.add_trace(go.Scatter(x=[x0, x1], y=[c, c], mode="lines", line=dict(color=BAD_COLOR, width=2, dash="dot"),
                             name=f"alle {c} Spuren belegt (darüber warten Lkw)"))
    fig.add_trace(go.Scatter(x=[x0, x1], y=[formula_l, formula_l], mode="lines",
                             line=dict(color=FORMULA_COLOR, width=2, dash="dash"), name=f"Formel L = {formula_l:.1f}"))
    fig.update_xaxes(title_text="Zeit seit Start (Stunden)", range=[x0, x1])
    fig.update_yaxes(title_text="Lkw im System", rangemode="tozero")
    return _base(fig, 320)


def build_state_distribution(shares, rest, c, lam, mu, theta):
    """Balken: Zeitanteil mit genau n Lkw im System; Punkte: Formel (Geburts-Sterbe-Kette mit Abbruch)."""
    ns = list(range(len(shares)))
    p = F.stationary_distribution(c, lam, mu, theta)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=ns, y=shares, marker_color=SIM_COLOR, name="simuliert (Zeitanteil)",
                         hovertemplate="n = %{x}: %{y:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=ns, y=[p[n] if n < len(p) else 0.0 for n in ns], mode="markers",
                             marker=dict(color=FORMULA_COLOR, size=6, symbol="diamond"), name="Formel"))
    fig.add_vline(x=c + 0.5, line=dict(color=BAD_COLOR, width=1.5, dash="dot"), annotation_text="ab hier warten Lkw",
                  annotation_position="top")
    fig.update_xaxes(title_text="Zahl der Lkw im System n")
    fig.update_yaxes(title_text="Anteil der Zeit", tickformat=".0%")
    return _base(fig, 320, top=30)


def build_c_vs_a(c, mean_patience, rho_pct):
    """Mittlere Wartezeit über der Auslastung: Erlang C (nur unter 100 %) gegen Erlang A (auch darüber)."""
    xs = list(range(10, 151, 2))
    rows = E.erlang_c_vs_a(c, mean_patience, xs)
    fig = go.Figure()
    c_pts = [(x, w) for x, w, _ in rows if w is not None]
    fig.add_trace(go.Scatter(x=[x for x, _ in c_pts], y=[w for _, w in c_pts], mode="lines",
                             line=dict(color=BAD_COLOR, width=2.5), name="Erlang C (unendliche Geduld)"))
    fig.add_trace(go.Scatter(x=[x for x, _, _ in rows], y=[a for _, _, a in rows], mode="lines",
                             line=dict(color=GOOD_COLOR, width=2.5), name=f"Erlang A (Geduld {mean_patience} min)"))
    fig.add_vline(x=100, line=dict(color="#888", width=1, dash="dot"), annotation_text="ρ = 100 %",
                  annotation_position="top")
    if rho_pct != 100:
        fig.add_vline(x=rho_pct, line=dict(color=FORMULA_COLOR, width=1, dash="dot"))
    ticks = [0.01, 0.1, 1, 10, 100]
    fig.update_xaxes(title_text="Auslastung je Spur ρ (%)", range=[10, 150])
    fig.update_yaxes(title_text="Mittlere Wartezeit aller Lkw (Minuten, log)", type="log", range=[-2.5, 2.7],
                     tickmode="array", tickvals=ticks, ticktext=["0.01", "0.1", "1", "10", "100"])
    return _base(fig, 340, top=30)


def build_fluid_chart(mean_patience):
    """Abbruchquote über der Auslastung für verschiedene Spurzahlen (Formel) gegen den Grenzwert 1 − 1/ρ."""
    xs = list(C.FLUID_RHO_PCT)
    fig = go.Figure()
    for c in C.FLUID_C:
        fig.add_trace(go.Scatter(x=xs, y=[v for _, v in E.abandon_curve(c, mean_patience, xs)], mode="lines",
                                 line=dict(color=C_COLORS[c], width=2.5), name=f"c = {c}",
                                 hovertemplate="ρ = %{x} %: %{y:.1%}<extra>" + f"c = {c}</extra>"))
    fig.add_trace(go.Scatter(x=xs, y=[F.fluid_abandon_rate(x / 100) for x in xs], mode="lines",
                             line=dict(color=FORMULA_COLOR, width=2, dash="dash"), name="Grenzwert 1 − 1/ρ (sehr viele Spuren)"))
    fig.update_xaxes(title_text="Auslastung je Spur ρ (%)")
    fig.update_yaxes(title_text="Abbruchquote", tickformat=".0%")
    return _base(fig, 360)


def build_patience_chart(cell):
    """Zwei Balkengruppen für eine gemessene Zelle: Abbruchquote und mittlere Wartezeit aller Lkw je Geduld-Verteilung
    (Mittel über die Läufe, Fehlerbalken: Standardabweichung eines Laufs)."""
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Abbruchquote", "Mittlere Wartezeit aller Lkw (min)"),
                        horizontal_spacing=0.14)
    labels = [PATIENCE_LABELS[k].split(" (")[0] for k in PATIENCE_KINDS]
    kinds = cell["kinds"]
    fig.add_trace(go.Bar(x=labels, y=[kinds[k]["p_ab"] for k in PATIENCE_KINDS],
                         marker_color=[KIND_COLORS[k] for k in PATIENCE_KINDS], showlegend=False,
                         error_y=dict(type="data", array=[kinds[k]["p_ab_sd"] for k in PATIENCE_KINDS]),
                         hovertemplate="%{x}: %{y:.1%}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=[kinds[k]["wq"] for k in PATIENCE_KINDS],
                         marker_color=[KIND_COLORS[k] for k in PATIENCE_KINDS], showlegend=False,
                         error_y=dict(type="data", array=[kinds[k]["wq_sd"] for k in PATIENCE_KINDS]),
                         hovertemplate="%{x}: %{y:.2f} min<extra></extra>"), row=1, col=2)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(rangemode="tozero", row=1, col=2)
    _base(fig, 360, top=40)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def build_staffing_chart(a, target, current_patience):
    """Spurbedarf über der mittleren Geduld (Formel); waagerecht die Spurzahl ohne Warteplatz (Erlang B)."""
    rows = E.staffing_vs_patience(a, target)
    c_loss = F.min_servers_loss(a, target)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[p for p, _ in rows], y=[c for _, c in rows], mode="lines+markers",
                             line=dict(color=GOOD_COLOR, width=2.5), name="mit Warteplatz (Erlang A)",
                             hovertemplate="Geduld %{x} min: %{y} Spuren<extra></extra>"))
    fig.add_trace(go.Scatter(x=[rows[0][0], rows[-1][0]], y=[c_loss, c_loss], mode="lines",
                             line=dict(color=BAD_COLOR, width=2, dash="dash"), name="ohne Warteplatz (Erlang B)"))
    fig.add_vline(x=current_patience, line=dict(color="#888", width=1, dash="dot"))
    fig.update_xaxes(title_text="Mittlere Geduld (Minuten, log)", type="log", tickmode="array",
                     tickvals=list(C.STAFFING_PATIENCES), ticktext=[str(p) for p in C.STAFFING_PATIENCES])
    fig.update_yaxes(title_text="Nötige Spuren", rangemode="normal")
    return _base(fig, 340)
