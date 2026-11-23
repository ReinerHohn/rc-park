"""Rot-Probe: Kopplung Eckmodell -> verfaelschter Teil (Spiegel, Massstabsverlauf 5 %, Biegung 3 Grad, Zufall), mit Kamera-Probe. Arg: Eckmodelle [teil0 teil1]."""
import sys, os, numpy as np, pycolmap
W = "/home/oem/git/rc-park/.claude/worktrees/agent-a38678dacd05d031c/tools"; sys.path.insert(0, W); sys.path.insert(0, W + "/versuche")
import seiten_eck_koppeln as EK
from eck_rest_eichung import verformen
A = "/media/oem/rcdaten/tmp/bruecke_sued_agent"
mods = [x for x in sys.argv[1:] if not x.startswith("teil=")]; tp = dict(x.split("=", 1)[1].split(":") for x in sys.argv[1:] if x.startswith("teil="))
R = {t: pycolmap.Reconstruction(tp.get(str(t), f"{A}/teil{t}")) for t in (0, 1)}
P = {t: np.array([p.xyz for p in R[t].points3D.values()]) for t in R}; at = {t: EK.ausdehnung(P[t]) for t in R}
for m in mods:
    rE = pycolmap.Reconstruction(m); ausdE = EK.ausdehnung([p.xyz for p in rE.points3D.values()])
    for t in (0, 1):
        X, Y, ns, td = EK.punkte(rE, R[t], mit_tiefe=True); CX, CY = EK.kamerazentren(rE, R[t], ns)
        for art, w in (("richtig", 0), ("spiegel", 0), ("massstab", 0.05), ("biegung", 3.0), ("zufall", 0)):
            Z, CZ = (Y, CY) if art == "richtig" else (verformen(Y, art, w, P[t]), CY if art == "zufall" else verformen(CY, art, w, P[t]))
            for mk in (False, True):
                M, pr, ok, g = EK.kopplung_pruefen(X, Z, ausdE, at[t], tiefe=td, kameras=(CX, CZ) if mk else None)
                print(m.split("bruecke_sued_agent/")[1][:30], "T", t, f"{art:8s}", "mitKam" if mk else "ohneKam", "OK " if ok else "rot", "ant", pr.get("anteil"), "rest", pr.get("rest_rel"),
                      "hael", pr.get("massstab_haelften_rel"), "kam", pr.get("kameras_rel"), "|", g[:70])
