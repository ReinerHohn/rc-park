#!/usr/bin/env python3
"""kachel_vereinen.py <alt.ply> <neu.ply> <aus.ply> --ausrichtung SFM-AUSRICHTUNG.json [--kachel 12] [--radius 60] [--faktor 1.3]

NIE SCHLECHTER ALS DER BESTAND (Nutzer 24.11.), angewandt auf die dichte Wolke: je Raumkachel (wie tools/kachelfusion.py, Modellrahmen) nimmt die
Vereinigung die KACHELFUSION nur dort, wo sie mindestens --faktor x so viele Punkte hat wie die alte Wolke; sonst bleibt die alte. Ausserhalb --radius immer alt.
Grund (Messung 26.11., Schwabentor): Kachelfusion mit 120 Bildern je Kachel gibt Nordfaeche 4,4-fach, aber Turmwaende 18-22 % weniger (viele sichtende Bilder > Deckel).
Schreibt <aus.ply> (SfM-Rahmen) und <aus.ply>.vereint.json (je Kachel Quelle und Zahlen). Danach tools/quellfilter.py auf <aus.ply> wie bei jeder Wolke.
Verwandt: tools/kachelfusion.py (liefert neu.ply), tools/teilfusion.py (alte Wolke), tools/quellfilter.py (Nachfilter), tools/dichte_diagnose.py (misst vorher/nachher).
Vorlaeufer: keiner - Bestand-Tor je Wandzone (tools/bestand_tor.py) gilt Form, nicht Punktdichte der Wolke.
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def kacheln(P, s, R, t, kachel):
    X = np.c_[P["x"], P["y"], P["z"]].astype(float); m = (X - t) @ R / s
    return np.floor(m[:, 0] / kachel).astype(np.int64), np.floor(m[:, 1] / kachel).astype(np.int64), np.hypot(m[:, 0], m[:, 1])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("alt"); ap.add_argument("neu"); ap.add_argument("aus"); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--kachel", type=float, default=12.0); ap.add_argument("--radius", type=float, default=60.0); ap.add_argument("--faktor", type=float, default=1.3)
    a = ap.parse_args()
    import cv2, teilfusion as TF
    T = json.load(open(a.ausrichtung))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
    A = TF.ply_lesen(a.alt); N = TF.ply_lesen(a.neu)
    ai, aj, ar = kacheln(A, s, R, t, a.kachel); ni, nj, nr = kacheln(N, s, R, t, a.kachel)
    key = lambda i, j: (i + 100000) * 200000 + (j + 100000)
    ak = key(ai, aj); nk = key(ni, nj); ua, ca = np.unique(ak[ar <= a.radius], return_counts=True); un, cn = np.unique(nk, return_counts=True)
    da = dict(zip(ua.tolist(), ca.tolist())); dn = dict(zip(un.tolist(), cn.tolist()))
    nimm = {k for k, v in dn.items() if v >= a.faktor * da.get(k, 0) and v > 0}
    bericht = []
    for k in sorted(set(da) | set(dn)):
        bericht.append({"kachel": [(k // 200000 - 100000) * a.kachel, (k % 200000 - 100000) * a.kachel], "alt": da.get(k, 0), "neu": dn.get(k, 0), "quelle": "neu" if k in nimm else "alt"})
    nimm_arr = np.array(sorted(nimm), np.int64)
    A_ok = ~((ar <= a.radius) & np.isin(ak, nimm_arr)); N_ok = np.isin(nk, nimm_arr)
    G = np.concatenate([A[A_ok], N[N_ok]]); TF.ply_schreiben(a.aus, G)
    json.dump({"faktor": a.faktor, "kachel_m": a.kachel, "radius_m": a.radius, "punkte_alt": int(len(A)), "punkte_neu": int(len(N)), "punkte_vereint": int(len(G)), "kacheln_neu": len(nimm), "kacheln": bericht},
              open(a.aus + ".vereint.json", "w"), indent=1)
    print(f"alt {len(A)} neu {len(N)} -> vereint {len(G)} ({len(nimm)} Kacheln aus neu, Rest alt)", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
