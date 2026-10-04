"""SETTING_SPECS-Permalink-Muster, Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio).
Alle Regler sind immer sichtbar - es gibt keinen ausblendbaren Regler (also auch kein KEPT-Muster)."""

import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import era_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "c_slider": SettingSpec("c", int, C.DEFAULT_C, C.C_MIN, C.C_MAX),
    "rho_slider": SettingSpec("rho", int, C.DEFAULT_RHO_PCT, C.RHO_PCT_MIN, C.RHO_PCT_MAX),
    "patience_slider": SettingSpec("pat", int, C.DEFAULT_PATIENCE, C.PATIENCE_MIN, C.PATIENCE_MAX),
    "n_select": SettingSpec("n", int, C.DEFAULT_N, C.N_OPTIONS[0], C.N_OPTIONS[-1]),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
}
PRESET_KEYS = {"c": "c_slider", "rho_pct": "rho_slider", "patience": "patience_slider", "n": "n_select",
               "seed": "seed_input"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def snap_n(value):
    """Der Regler für die Lauflänge kennt nur die Stufen in `N_OPTIONS`; ein Permalink-Wert dazwischen rastet auf die
    nächste Stufe ein (bei Gleichstand auf die kleinere)."""
    return min(C.N_OPTIONS, key=lambda o: (abs(o - value), o))


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                if state_key == "n_select":
                    value = snap_n(value)
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][key]
    st.session_state["window_start_h"] = 0     # neue Konfiguration: Fenster wieder an den Anfang


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
