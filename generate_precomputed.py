"""Rechnet die teure Studie vor (Build-Zeit, nicht in der App): `python generate_precomputed.py [Prozesse]` schreibt
`precomputed_sweep.json`.

  study  Spurzahl × Auslastung × Geduld-Verteilung (exponentiell, gleichverteilt, fest, lognormal, alle mit Mittel 5 min):
         Abbruchquote und mittlere Wartezeit aller Lkw, Mittel und Streuung über 20 Läufe à 50 000 Lkw"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import era_constants as C
from era_evaluation import PRECOMPUTED_PATH, patience_study


def _task(args):
    c, rho = args
    return patience_study(c, rho, C.STUDY_PATIENCE, C.STUDY_N, C.STUDY_REPS, seed_base=c * 10_000_000 + rho * 10_000)


def main(workers):
    t0 = time.time()
    jobs = [(c, r) for c in C.STUDY_C for r in C.STUDY_RHO_PCT]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        study = list(ex.map(_task, jobs))
    out = {"study_reps": C.STUDY_REPS, "study_n": C.STUDY_N, "study_patience": C.STUDY_PATIENCE, "study": study}
    Path(PRECOMPUTED_PATH).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"fertig in {time.time() - t0:.0f} s -> {PRECOMPUTED_PATH}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else min(6, os.cpu_count() or 1))
