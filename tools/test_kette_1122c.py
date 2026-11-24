#!/usr/bin/env python3
"""test_kette_1122c.py - fester Test (CPU, Sekunden, echte kleine Fixtures aus dem Kettenlauf schwabentor-1120 1122c, 22.11.2026).

Befund 1122c: rundbogenfenster 1 statt 2 (linkes Fenster unter der Uhr fehlt), Tor breite 5,27 statt 4,32 (Aussenkante statt lichte Weite).
 A  Fenster (tools/testdata/kette_1122c_f00_erkenner.json = OWLv2-Kaesten der 10 Rangfotos f00 + Sichtmasken 0,25 m, auf CPU nachgerechnet):
    fassade_parsing.abstimmen + boegen_vereinen. Alt verschmolz der Bogenkasten der linken Nische (z 23-25,6) mit dem Tor (z 0-6,8) zu EINEM Bogen z -0,03..25,56,
    die linke Nische verlor ihre Zone. Soll: Tor-Bogen endet unter 10 m, zwei Nischenzonen in 22-26 m (links u < 0, rechts u > 0).
    Dann nischen_fenster.fassade_auswerten mit diesen Zonen (Kantenmessung durch einen Stub ersetzt, der die Suchzone zurueckgibt): Soll ZWEI Fenster mit Nische
    in 22-26 m - das linke ueber die Nischenzone + Fenster-Suchzone vom vermessenen Geschwister (Fenster dort nur 2 von 7 Stimmen).
 B  Tor (tools/testdata/kette_1122c_tor.json = Kantenspitzen je Einzelfoto an beiden Laibungen aus Einzelortho (Messkoerper eben) und Foto (_foto_flach),
    Umriss und Gewaende-Kandidaten aus oeffnungen_aus_kanten f00_wand): Soll lichte Weite 4,32 +- 0,15 (Hand) statt Aussenkante 5,27;
    Gegenprobe: nur die Foto-Quelle (Stand 1122c) belegt den Ruecksprung NICHT (Innenkante 0,14 m statt 0,58-0,74 m tief) -> Aussenkante.
rc 0 = bestanden.
"""
import sys, os, json, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
TD = os.path.join(H, "testdata"); F_ = 0


def pruef(ok, t):
    global F_
    print(("  ok     " if ok else "  FEHLER ") + t); F_ += not ok


def teil_a():
    import fassade_parsing as fp, nischen_fenster as NF
    X = json.load(open(os.path.join(TD, "kette_1122c_f00_erkenner.json"))); r = dict(X["raster"], zelle=X["masken_zelle"])
    je = {k: (v or []) for k, v in X["je_foto"].items()}; mk = {k: np.array([[c == "1" for c in row] for row in v]) for k, v in X["masken"].items()}
    E = fp.abstimmen(je, mk, r, 2, 0.4); bo = fp.boegen_vereinen(E); alt = fp.boegen_vereinen(E, z_luecke=1e9)
    tor = [b for b in bo if b["z0"] < 1.0]; ni = [b for b in bo if 22.0 < b["z0"] < 24.0 and b["z1"] < 26.5]
    pruef(any(b["z1"] > 20 and b["z0"] < 1 for b in alt), "A Gegenprobe alte Bogenregel verschmilzt Tor und linke Nische: " + str([(round(b["u0"], 2), round(b["z0"], 2), round(b["z1"], 2)) for b in alt]))
    pruef(len(tor) == 1 and tor[0]["z1"] < 10 and len(ni) == 2 and min((b["u0"] + b["u1"]) / 2 for b in ni) < 0 < max((b["u0"] + b["u1"]) / 2 for b in ni),
          "A Boegen getrennt: " + str([(round(b["u0"], 2), round(b["u1"], 2), round(b["z0"], 2), round(b["z1"], 2)) for b in bo]))
    # nischen_fenster mit den Zonen dieses Laufs; Kantenmessung/Fotos/Sweep als Stub (die echte Bildmessung pruefen test_nischen_fenster + Kettenlauf)
    k = [(e["u0"], e["u1"], e["z0"], e["z1"], e["stimmen"]) for e in [x for x in E if x["klasse"] == "fenster"] + bo if e["stimmen"] >= 2]
    def stub_form(B, kasten, innen=None, **kw): return dict(u0=kasten[0], u1=kasten[1], z0=kasten[2], z1=kasten[3], bogen=dict(form="rund"), anteil=0.9)
    alt_f, alt_b, alt_t = NF.form_aus_kanten, NF.form_bestaetigen, NF.tiefen
    NF.form_aus_kanten = stub_form; NF.form_bestaetigen = lambda *a_, **k_: None; NF.tiefen = lambda npz, n, f, **k_: dict(nische=-0.10, fenster=-0.70)     # **k_: fremd= (24.11. weiter Wandring)
    try:
        class A_: kante = 4.0; anteil_min = 0.5; flaeche_max_anteil = 0.5; fenster_tiefe = 0.12; nische_min = 0.05
        neu, br = NF.fassade_auswerten(None, k, {}, A_, (), [], [])
    finally: NF.form_aus_kanten, NF.form_bestaetigen, NF.tiefen = alt_f, alt_b, alt_t
    fz = [q for q in neu if q.get("nische") and 22.0 < q["z0"] < 24.0]
    pruef(len(fz) == 2 and min((q["u0"] + q["u1"]) / 2 for q in fz) < 0 < max((q["u0"] + q["u1"]) / 2 for q in fz),
          f"A nischen_fenster: {len(fz)} Fenster mit Nische in 22-26 m (soll 2): " + "; ".join(f"u {q['u0']:.2f}..{q['u1']:.2f} z {q['z0']:.2f} [{r_.get('art')}]" for q, r_ in zip(neu, br)))


def teil_b():
    import oeffnungen_aus_kanten as O
    X = json.load(open(os.path.join(TD, "kette_1122c_tor.json"))); W_ = X["wahl"]; s = dict(W_["s"])
    kant = {}
    for b in X["bel"]:
        bel = [(ru, np.array(u_), np.array(s_, float), np.array(h_)) for ru, u_, s_, h_ in b["bel"]]
        seite = "links" if b["ua"] < (s["uL"] + s["uR"]) / 2 - 1.0 else "rechts"
        K, _ = O.laibungskanten(None, b["ua"], b["ub"], b["za"], b["zb"], bel=bel); kant.setdefault(seite, {})["foto" if b["foto"] else "ortho"] = [dict(k, quelle="einzelfotos") for k in K]
    kand = [(g_, b_, None if z is None else (z[0], z[1], z[2])) for g_, b_, z in W_["kand"]]
    def breite(quellen):
        zw, g, gp = O.gewaende_waehlen(s, kand, W_["untergrund"], quellen); si = zw[0] if (zw and g < 0) else s; return round(si["uR"] - si["uL"], 3), gp
    b_neu, gp = breite({n: [kant[n]["ortho"], kant[n]["foto"]] for n in ("links", "rechts")})
    pruef(abs(b_neu - 4.32) <= 0.15, f"B Tor lichte Weite {b_neu} (Hand 4,32; Aussenkante {round(s['uR'] - s['uL'], 3)}), geprueft {gp}")
    b_alt, gp = breite({n: [kant[n]["foto"]] for n in ("links", "rechts")})
    pruef(abs(b_alt - (s["uR"] - s["uL"])) < 0.01, f"B Gegenprobe nur Foto-Quelle (Stand 1122c): {b_alt} = Aussenkante (belegt den Befund), geprueft {gp}")


def main():
    teil_a(); teil_b()
    print(f"test_kette_1122c: {F_} Fehler"); return 1 if F_ else 0


if __name__ == "__main__": sys.exit(main())
