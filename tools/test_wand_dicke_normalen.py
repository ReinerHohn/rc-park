#!/usr/bin/env python3
"""Test wand_dicke_tor mit Punktnormalen (22.11.2026, Eck-Kopplung schwabentor-1122): Querwand im 3-m-Eckband und Innenwand der Tordurchfahrt (Normale nach innen)
zaehlen nicht als zweite Wand; echte Versaetze (0,57 m wie gu_probe2, 1,6 m) bleiben rot; ohne Normalen (n x 3) gilt das alte Band."""
import os, sys, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import wand_dicke_tor as WD
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
rng = np.random.default_rng(5); g = np.array([[-5.0, -6.0], [5.0, -6.0], [5.0, 6.0], [-5.0, 6.0]])   # Mitte (0, 0)


def wand(x0, y0, x1, y1, n, normale, schieb=(0.0, 0.0)):
    t = rng.uniform(0, 1, n); P = np.c_[x0 + t * (x1 - x0) + schieb[0], y0 + t * (y1 - y0) + schieb[1], rng.uniform(1, 12, n)]; P[:, :2] += rng.normal(0, 0.05, (n, 2))
    return np.c_[P, np.tile(np.r_[normale, 0.0], (n, 1))]


west_aussen = lambda n=3000, s=0.0: wand(-5, 6, -5, -6, n, (-1, 0), (-s, 0))          # Westwand, Normale nach Westen (aussen)
t0 = np.r_[west_aussen(), wand(-5, -6, 5, -6, 3000, (0, -1)), wand(5, -6, 5, 6, 3000, (1, 0)), wand(5, 6, -5, 6, 3000, (0, 1))]
# Teil 1 sieht die Westwand richtig, dazu (a) die Suedwand nur am Westende (Querwand, ins 3-m-Band der Westkante) und (b) die Innenwand der Durchfahrt 2 m innen,
# parallel zur Westwand, Normale nach innen (vom Durchgang aus fotografiert)
t1 = np.r_[west_aussen(), wand(-5, -6, -2.5, -6, 1500, (0, -1)), wand(-3, 5, -3, -5, 3000, (1, 0))]
K = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0, 1: t1})}; w = K[(-5.0, 6.0)]
pruef(w["urteil"] == "ok", f"mit Normalen: Querwand im Eckband + Innenwand der Durchfahrt -> West ok ({w['urteil']}, Dicke {w.get('dicke_gesamt_m')})")
K3 = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0[:, :3], 1: t1[:, :3]})}
pruef(K3[(-5.0, 6.0)]["urteil"] != "ok", f"Gegenprobe ohne Normalen (altes Band): West nicht ok ({K3[(-5.0, 6.0)]['urteil']})")
for s, soll in ((0.57, "versetzt"), (1.6, "versetzt")):
    t2 = np.r_[west_aussen(s=s), wand(-5, -6, 5, -6, 3000, (0, -1))]
    k = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0, 1: t2})}[(-5.0, 6.0)]
    pruef(k["urteil"] in ("versetzt", "doppelwand"), f"echter Versatz {s} m (beide Normalen aussen) bleibt rot ({k['urteil']}, {k.get('lageunterschied_m')} m)")
pruef(WD.zusammenfassen(list(K.values()))[0] == 0, "Tor gesamt rc 0 fuer den Eckband-Fall")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
