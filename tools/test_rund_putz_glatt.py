#!/usr/bin/env python3
"""test_rund_putz_glatt.py - glatter Putz-Schaft am Rundkoerper (rund_aus_umriss.profil_bereinigen + bauteile.drehkoerper_aus_wolkenrest), 24.11.2026.
Anlass: Kettenlauf 1122zb Schwabentor f04 (Treppenturm, Foto: glatter weisser Putz bis zum Gesims). Modell: 0,7-m-Kerbe z 10,5-12,2 m (Profil r 0,835/0,855 = Untergrenze
des Suchbereichs 0,5 x Wolkenradius 1,75 -> kein Umriss gefunden, trotzdem gebaut) und 48-Eck mit 0,2-m-Facetten (7,5-Grad-Knicke).
A) profil_bereinigen: Suchrand-Hoehen weg, Uebergangswert an der Luecke per Median weg, Luecke = Radius darunter; idempotent; ohne Suchrand unveraendert.
B) ROT-PROBE: eine echte, gemessene Kehle (r 1,30 im Schaft 1,55, weit ueber der Untergrenze) bleibt; Wert an der OBERgrenze faellt ebenfalls weg.
C) Generator: Rundkoerper (mass_quelle foto_umriss) mit Kerbe am Suchrand -> Radius in der Kerbe = Schaft, Facette <= Druckmindestmass, Beleg nennt den Suchrand;
   Wolken-Rundkoerper (ohne foto_umriss) bleibt im Profil unveraendert. Nur pfade.temp_ordner, < 10 s."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rund_aus_umriss as RU
from pfade import temp_ordner

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

R0 = 1.75                                                         # Startradius (Wolke) -> Suchbereich 0,875 .. 2,45
SCHAFT = [[1.25 + 0.5 * i, 1.55 + 0.005 * (i % 3), 50] for i in range(19)]        # z 1,25 .. 10,25
KERBE = SCHAFT + [[10.75, 1.215, 60], [11.25, 0.835, 60], [11.75, 0.855, 40], [12.25, 2.015, 30], [12.75, 2.185, 30]]

# A) Bereinigen
P, weg = RU.profil_bereinigen(KERBE, R0)
pruef(weg == [11.25, 11.75], f"Suchrand-Hoehen verworfen: {weg}")
r = {p[0]: p[1] for p in P}
pruef(abs(r[10.75] - r[10.25]) < 0.02 and abs(r[11.25] - r[10.25]) < 0.02 and abs(r[11.75] - r[10.25]) < 0.02, f"Kerbe zu: r 10,75/11,25/11,75 = {r[10.75]}/{r[11.25]}/{r[11.75]} (Schaft {r[10.25]})")
pruef(abs(r[12.25] - 2.015) < 1e-6 and abs(r[12.75] - 2.185) < 1e-6, "Ueberstand ueber der Luecke bleibt gemessen")
pruef(all(abs(a[1] - b[1]) < 1e-9 for a, b in zip(P[:19], SCHAFT[:18])), "Schaft unter der Luecke unveraendert (nur der Lueckennachbar wird gemittelt)")
pruef(len(P) == len(KERBE) and all(len(a) == len(b) for a, b in zip(P, KERBE)), "Hoehen und Felder bleiben erhalten (Stuetze/Zahl je Hoehe)")
P2, w2 = RU.profil_bereinigen(P, R0); pruef(P2 == P and not w2, "idempotent")
P3, w3 = RU.profil_bereinigen(SCHAFT, R0); pruef(P3 == [list(p) for p in SCHAFT] and not w3, "ohne Suchrand-Wert unveraendert")
Pu, wu = RU.profil_bereinigen([[0.75, 0.86, 9], [1.25, 0.87, 9]] + SCHAFT, R0)
pruef(wu == [0.75, 1.25] and abs(Pu[0][1] - Pu[2][1]) < 0.01, f"Luecke ganz unten -> Radius der Hoehe darueber ({Pu[0][1]})")

# B) Rot-Probe: echte Kehle bleibt, Obergrenze faellt
KEHLE = SCHAFT[:8] + [[5.25, 1.30, 70], [5.75, 1.30, 70]] + SCHAFT[10:]
Pk, wk = RU.profil_bereinigen(KEHLE, R0)
pruef(not wk and Pk == [list(p) for p in KEHLE], "gemessene Kehle r 1,30 (weit ueber der Untergrenze 0,875) bleibt - kein Glaetten ohne Grund")
Po, wo = RU.profil_bereinigen(SCHAFT + [[10.75, 2.44, 20]], R0)
pruef(wo == [10.75] and abs(Po[-1][1] - Po[-2][1]) < 0.01, "Wert an der Obergrenze 2,45 faellt ebenfalls weg")
pruef(RU.profil_bereinigen(KERBE, None) == ([list(p) for p in KERBE], []), "ohne Startradius unveraendert (kein Suchbereich bekannt)")

# C) Generator
try:
    import bauteile as BT
    from manifold3d import Manifold as M
    td = temp_ordner("rundputz_")
    def bau(H):
        kp = os.path.join(td, "k.json"); json.dump(dict(haufen=[H]), open(kp, "w"))
        return BT.drehkoerper_aus_wolkenrest(M.cube((0.5, 0.5, 0.5)).translate((-30, -30, 0)), kp)
    H = dict(id="r", form="rund", kreis=dict(x=0.0, y=0.0, r=1.55), kreis_wolke=dict(x=0.1, y=0.0, r=R0), profil=[p[:3] for p in KERBE], mass_quelle="foto_umriss",
             umriss=dict(start_wolke=dict(x=0.1, y=0.0, r=R0)), kasten=[-2, -2, 1, 2, 2, 13])
    k, bel = bau(H); mm = k.to_mesh(); V = np.asarray(mm.vert_properties)[:, :3]
    def r_bei(V, z, tol=0.02):
        s = np.abs(V[:, 2] - z) < tol; return float(np.hypot(V[s, 0], V[s, 1]).max()) if s.any() else float("nan")
    rr = r_bei(V, 11.25)
    pruef(abs(rr - 1.555) < 0.03, f"Generator: Radius in der frueheren Kerbe z 11,25 = {rr:.3f} (Schaft 1,555)")
    pruef(any("Suchrand" in b["element"] for b in bel), "Beleg nennt die verworfenen Suchrand-Hoehen")
    dmin = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    s = np.abs(V[:, 2] - 5.25) < 0.01; ang = np.sort(np.arctan2(V[s, 1], V[s, 0])); sehne = 2 * 1.6 * np.sin(np.max(np.diff(ang)) / 2) if s.sum() > 3 else 9.0
    pruef(sehne <= dmin + 0.005, f"Facette {sehne:.3f} m <= Druckmindestmass {dmin:.3f} m (glatter Putz statt 48-Eck)")
    Hw = dict(H, mass_quelle=None, punkte=1000, kreis=dict(H["kreis"], rest=0.05)); Hw.pop("umriss")
    k2, bel2 = bau(Hw); V2 = np.asarray(k2.to_mesh().vert_properties)[:, :3]
    pruef(r_bei(V2, 11.25) < 1.0 and not any("Suchrand" in b["element"] for b in bel2), "Wolken-Rundkoerper (ohne Foto-Umriss) bleibt im Profil unveraendert")
except ImportError as e_:
    pruef(False, f"Generator nicht pruefbar: {e_}")

print("FEHLER:", len(fehler)) if fehler else print("alle Pruefungen bestanden")
sys.exit(1 if fehler else 0)
