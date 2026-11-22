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
# GUELTIGKEIT: Teil 1 sieht die Westwand nicht, nur ein verschmierter Fleck (700 Punkte, 2 m breit) -> keine Flaeche, kein Teilvergleich; die Nordwand sieht er richtig
fleck = wand(-5, 6, -5, -6, 700, (-1, 0)); fleck[:, 0] += rng.uniform(0.5, 2.5, 700)
t3 = np.r_[fleck, wand(5, 6, -5, 6, 3000, (0, 1))]
K = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0, 1: t3})}; w = K[(-5.0, 6.0)]
pruef(w["urteil"] in ("ok", "dick") and w["teile"]["1"].get("flaeche") is False and "keine Flaeche" in w["teile"]["1"].get("hinweis", ""),
      f"verschmierter Fleck ohne Flaeche: kein Teilvergleich, Meldung je Teil ({w['urteil']}, {w['teile']['1'].get('hinweis')})")
pruef(WD.zusammenfassen(list(K.values()))[0] == 0 and "1" in K[(5.0, 6.0)]["vergleich_teile"], "Nordwand mit Teilvergleich -> Tor rc 0")
# Teil 1 zeigt NUR eine eigene Wand, die Teil 0 nicht sieht -> kein Teilvergleich -> nicht belegt (rc 2), nicht gruen
t0b = np.r_[wand(-5, -6, 5, -6, 3000, (0, -1)), wand(5, -6, 5, 6, 3000, (1, 0))]; t4 = west_aussen()
rc, u = WD.zusammenfassen(WD.kanten_messen(g, {0: t0b, 1: t4}))
pruef(rc == 2 and "nur eigene Wand" in u, f"nur eigene Wand, kein Teilvergleich -> rc 2 ({u})")
# Doppelwand mit Flaechen bleibt rot, auch neben einem verschmierten dritten Teil
k = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0, 1: west_aussen(s=0.57), 2: fleck})}[(-5.0, 6.0)]
pruef(k["urteil"] in ("versetzt", "doppelwand"), f"0,57 m mit Flaechen + verschmierter dritter Teil bleibt rot ({k['urteil']})")
# INNENFLAECHEN (unabhaengige Probe): beide Teile sehen eine Durchfahrtswand 3 m hinter der Westkante, Teil 1 um 0,3 m verschoben -> gemessen 0,3 m
i0 = np.r_[t0, wand(-2, 5, -2, -5, 4000, (1, 0))]; i1 = np.r_[west_aussen(), wand(-2, 5, -2, -5, 4000, (1, 0), (0.3, 0))]
I_ = [x for x in WD.innenflaechen(g, {0: i0, 1: i1}) if x["kante"] == [[-5.0, 6.0], [-5.0, -6.0]]]
pruef(len(I_) == 1 and abs(I_[0]["lageunterschied_m"] - 0.3) < 0.08 and I_[0]["winkelunterschied_grad"] < 1.5, f"Innenflaeche: Versatz 0,3 m gemessen ({I_})")
pruef(WD.innenflaechen(g, {0: i0[:, :3], 1: i1[:, :3]}) == [], "ohne Normalen keine Innenflaechen-Messung")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
