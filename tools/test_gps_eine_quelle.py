#!/usr/bin/env python3
"""Fester Test (Sekunden, CPU): EINE Quelle der Wahrheit fuer das Foto-GPS in Ausrichtung (sfm_lod2_ausrichten) und GPS-Tor (lage_gps_pruefen) - 22.11.2026.
Befund Lauf kette-schwabentor-null-1122j: die Ausrichtung rechnete GPS-Fit + ehrliches Band nur auf dem Kamerakern (70 %, ohne die 10 Fernfotos bei 320 m) ->
'1 Gruppe, n_eff 1,0, +-10,4 Grad: GPS traegt nicht'; das Tor rechnete mit ihnen -> '2 Gruppen, +-1 Grad: kann ankern'. Jetzt beide gps_unsicherheit.gps_fit auf ALLEN
GPS-Kameras; das Veto je Loesung ist das GPS-Tor selbst.
  1 synthetisch   Nah-GPS EINER Sitzung verzerrt (zum Turm gezogen) + 10 richtige Fernfotos (andere Sitzung): Ausrichtungs-Startlage == Tor-Lage (Tor misst ~0 Grad / x1,00
                  auf ihr), beide 'kann ankern', Startlage nahe der Wahrheit (der Nah-Fit allein liegt Grad daneben); ohne Fernfotos: KEIN Anker in beiden
  2 Fixture 1122j tools/test_gps_eine_quelle_fixture.json (loesung0_zurueck des Laufs 1122j, 172 GPS-Kameras, 15 fern): alter Kamerakern-Fit -> kein Anker (Befund
                  nachgestellt), neuer Fit -> Anker; Startlage liegt bei der geschriebenen Loesung 0 (= 1120-Lage) und ihre Kameras < 1,5 m neben 1120
  3 Kaufhaus gk2  (keine Fernfotos) und Martinstor (Objektstandort-Geotags) aendern sich nicht: Tor-Zahlen wie vor dem Umbau, kein Anker
  4 Regel         Lageproben gegen ankerfaehiges GPS -> 'keine' Lage mit benannter Ursache; Kamerahoehe allein bestaetigt keine Lage
  5 Verdrahtung
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_gps_eine_quelle.py"""
import os, sys, math, json, io, contextlib
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
for k_ in ("AUSR_GPS_EINE_QUELLE", "AUSR_GPS_EHRLICH", "AUSR_GPS_ANKER"): os.environ.pop(k_, None)
import gps_unsicherheit as GU
import lage_gps_pruefen as LG
import lage_proben as LP
import sfm_lod2_ausrichten as SA

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

def dreh(X, g, k=1.0):
    a = math.radians(g); R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]); return k * np.asarray(X, float) @ R.T

def tor(nm, MU, G, z):
    with contextlib.redirect_stdout(io.StringIO()): return LG.urteil(list(nm), np.asarray(MU, float), np.asarray(G, float), zeiten=z)

def zu_modell2(start, C):   # Startlage (SfM-Einheiten/m, Drehung, tx, ty) wie zu_modell([log s, 0, 0, th, tx, ty, h]) in 2D
    s, th, tx, ty = start; return dreh(C, math.degrees(th)) / s + [tx, ty]

def kern_alt(C3, idx):      # bisherige Auswahl der Ausrichtung: Kamerakern 70 % (_nah)
    dc = np.linalg.norm(C3 - np.median(C3, 0), axis=1); return dc[idx] <= np.percentile(dc, 70)

def ausrichtung_fit(Csfm3, gps_kam, z_je_kamera):
    """Wie sfm_lod2_ausrichten (eine Quelle): alle GPS-Kameras -> GU.gps_fit; Rahmen = Identitaet (GPS schon im Modellsystem)."""
    ia, Ma, Ca = SA.gps_kameras_alle(gps_kam, Csfm3, [0.0, 0.0], [1.0, 0.0], [0.0, 1.0]); za = [z_je_kamera[int(i)] for i in ia]
    return ia, Ma, Ca, za, GU.gps_fit(Ca, Ma, za, GU.NAH_M)

# 1 synthetisch
rng = np.random.default_rng(7); n = 160; w = rng.uniform(0, 2 * np.pi, n); r = rng.uniform(10, 30, n)
Mn = np.c_[r * np.cos(w), r * np.sin(w)]
Gn = Mn - 3.0 * Mn / np.linalg.norm(Mn, axis=1, keepdims=True) + dreh(Mn, 8.0) - Mn + rng.normal(0, 1.5, (n, 2))   # zum Turm gezogen + 8 Grad Sitzungsdrehung
zn = [1.7e9 + 4 * i for i in range(n)]
wf = rng.uniform(1.8, 2.3, 10); rf = rng.uniform(300, 330, 10); Mf = np.c_[rf * np.cos(wf), rf * np.sin(wf)]; Gf = Mf + rng.normal(0, 3.0, (10, 2))
zf = [1.7e9 - 5000 + 20 * i for i in range(10)]                                               # andere Sitzung
for name, Mw, Gw, zw, soll_anker in (("mit Fernfotos", np.vstack([Mn, Mf]), np.vstack([Gn, Gf]), zn + zf, True), ("ohne Fernfotos", Mn, Gn, zn, False)):
    m = len(Mw); s_w, th_w = 0.11, math.radians(171)
    C3 = np.c_[dreh(Mw - [2, -3], -math.degrees(th_w)) * s_w, rng.normal(0, 0.02, m)]                # SfM-Lotsystem (beliebig gedreht/skaliert)
    gk = [(i, Gw[i]) for i in range(m)]
    ia, Ma, Ca, za, f = ausrichtung_fit(C3, gk, zw)
    pruef(f["ok"], f"{name}: GPS-Fit der Ausrichtung nicht moeglich: {f.get('grund')}")
    start = SA.gps_start_aus_fit(f); Xs = zu_modell2(start, C3[:, :2])                              # Kameras in der Startlage der Ausrichtung
    rc, e = tor([f"k{i}" for i in range(m)], Xs, Gw, zw); g = e["gps_fit"]
    print(f"  synthetisch {name}: Ausrichtung ehrlich +-{f['sd_drehung_grad']:.1f} Grad, Anker {f['anker'] is not None}; Tor auf der Startlage {g['drehung_grad']:+.2f} Grad x{g['massstab']:.4f}, festgelegt {g['lage_festgelegt']}")
    pruef(abs(g["drehung_grad"]) < 0.05 and abs(g["massstab"] - 1) < 5e-4, f"{name}: Tor muss auf der Ausrichtungs-Startlage 0 Grad / x1 messen (eine Quelle): {g['drehung_grad']}, {g['massstab']}")
    pruef((f["anker"] is not None) == soll_anker and g["lage_festgelegt"] == soll_anker, f"{name}: Anker Ausrichtung {f['anker']} / Tor {g['lage_festgelegt']}, soll {soll_anker}")
    if soll_anker:
        Xw = Mw; d_start = math.degrees(math.atan2(*(lambda R: (R[1, 0], R[0, 0]))(GU._fit2d(Xs, Xw)[1])))
        pruef(abs(d_start) < 1.5 and rc == 0, f"{name}: Startlage {d_start:+.1f} Grad neben der Wahrheit (soll < 1,5) bzw. Tor rc {rc}")
        nah_k = kern_alt(C3, np.arange(m)); f_alt = GU.gps_fit(C3[nah_k, :2], Gw[nah_k], [zw[i] for i in np.flatnonzero(nah_k)])
        d_alt = math.degrees(math.atan2(*(lambda R: (R[1, 0], R[0, 0]))(GU._fit2d(zu_modell2(SA.gps_start_aus_fit(f_alt), C3[:, :2]), Xw)[1])))
        pruef(f_alt["anker"] is None and abs(d_alt) > 4, f"{name}: Nachstellung: Kamerakern-Fit ohne Fernfotos muesste verzerrt ({d_alt:+.1f} Grad) und ohne Anker sein")

# 2 Fixture 1122j (loesung0_zurueck) + 1120
F = json.load(open(os.path.join(T, "test_gps_eine_quelle_fixture.json")))
a = F["schwabentor-1122j_l0"]; C = np.array(a["kamera_modell"]); G = np.array(a["gps_modell"]); Z = a["zeiten"]; nmj = a["namen"]
C3 = np.c_[dreh(C[:, :2], 64.0) * 0.1059 + [3.0, -1.0], C[:, 2] * 0.1059]                           # beliebiges SfM-System (Massstab der Loesung 0)
gk = [(i, G[i]) for i in range(len(G))]; ia, Ma, Ca, za, f = ausrichtung_fit(C3, gk, Z)
kern = np.linalg.norm(C - np.array(a["kern_median"]), axis=1) <= a["kern_grenze_m"]                    # _nah der Ausrichtung (aus allen 521 Kameras)
fa = GU.gps_fit(C3[kern, :2], G[kern], [Z[i] for i in np.flatnonzero(kern)])
print(f"  1122j: Kamerakern {int(kern.sum())} GPS-Kameras -> ehrlich +-{fa['sd_drehung_grad']:.1f} Grad, Anker {fa['anker']}; alle {len(ia)} -> +-{f['sd_drehung_grad']:.1f} Grad, "
      f"Anker {f['anker']}, Fernfotos im Fit {f['n_fern_inlier']}")
pruef(fa["anker"] is None and fa["systematik"]["n_gruppen"] == 1, f"1122j Nachstellung: Kamerakern-Fit muesste wie im Lauf 'traegt nicht' sagen (1 Gruppe): {fa['systematik']['n_gruppen']}")
pruef(f["anker"] is not None and f["n_fern_inlier"] >= 8, f"1122j: Fit mit Fernfotos muss ankern (Tor sagte 'kann ankern'): {GU.gps_fit_text(f)}")
start = SA.gps_start_aus_fit(f); Xs = zu_modell2(start, C3[:, :2])
s_d, R_d = GU._fit2d(C[:, :2], Xs); dd = math.degrees(math.atan2(R_d[1, 0], R_d[0, 0]))
print(f"  1122j: GPS-Startlage gegen geschriebene Loesung 0: {dd:+.2f} Grad x{s_d:.4f}")
pruef(abs(dd) < 2.5 and abs(s_d - 1) < 0.03, f"1122j: Startlage muss bei Loesung 0 liegen (Tor 1,1 Grad x1,012): {dd:+.2f} Grad x{s_d:.4f}")
pruef(f["anker"] is not None and abs(dd) <= f["anker"][0] and abs(s_d - 1) <= f["anker"][1], f"1122j: Loesung 0 muss im Anker-Kasten liegen: {dd:+.2f} Grad x{s_d:.4f}, Kasten {f['anker']}")
b = F["schwabentor-1120"]; ib = {n_: i for i, n_ in enumerate(b["namen"])}; gem = [i for i, n_ in enumerate(nmj) if n_ in ib and np.hypot(*G[i]) < 100]
Cb = np.array(b["kamera_modell"])[[ib[nmj[i]] for i in gem], :2]
rest_l0 = float(np.median(np.hypot(*(C[gem, :2] - Cb).T))); rest_st = float(np.median(np.hypot(*(Xs[gem] - Cb).T)))
print(f"  1122j: Kamerazentren gegen 1120 (Nahfotos mit GPS, n {len(gem)}): Loesung 0 {rest_l0:.2f} m, GPS-Startlage {rest_st:.2f} m")
pruef(rest_l0 < 1.5, f"1122j: geschriebene Loesung 0 muss bei der 1120-Lage liegen: {rest_l0:.2f} m")
pruef(rest_st < 2.5, f"1122j: GPS-Startlage (eine Quelle) muss bei der 1120-Lage liegen: {rest_st:.2f} m")
rc, e = tor(nmj, C[:, :2], G, Z); pruef(rc == 0 and e["gps_fit"]["lage_festgelegt"], f"1122j: Tor auf Loesung 0 muss bestehen und festlegen: {e.get('warnungen')}")
rc2, e2 = tor(nmj, dreh(C[:, :2], -17.0, 1 / 1.16), G, Z); pruef(rc2 == 3, "1122j: Loesung 2 (-17 Grad, x1,16 gegen GPS) muss am Tor fallen")

# 3 Kaufhaus + Martinstor unveraendert
k = F["kaufhaus_gk2"]; Ck = np.array(k["kamera_modell"]); Gk = np.array(k["gps_modell"]); xh, yh = np.array(k["xhat_utm"]), np.array(k["yhat_utm"])
rc, e = tor(k["namen"], Ck[:, :1] * xh + Ck[:, 1:2] * yh, Gk[:, :1] * xh + Gk[:, 1:2] * yh, k["zeiten"]); g = e["gps_fit"]
print(f"  Kaufhaus: Tor rc {rc}, {g['drehung_grad']:+.2f} Grad x{g['massstab']:.4f}, festgelegt {g['lage_festgelegt']}, Fernfotos {sum(np.hypot(*Gk.T) >= 100)}")
pruef(rc == 0 and abs(g["drehung_grad"] - (-5.42)) < 0.01 and abs(g["massstab"] - 0.9134) < 1e-3 and not g["lage_festgelegt"], f"Kaufhaus: Tor-Zahlen muessen wie vor dem Umbau sein (rc 0, -5,42 Grad, x0,913, nicht festgelegt): {rc} {g}")
kern_k = np.linalg.norm(Ck - np.array(k["kern_median"]), axis=1) <= k["kern_grenze_m"]
fk_neu = GU.gps_fit(Ck[:, :2], Gk, k["zeiten"]); fk_alt = GU.gps_fit(Ck[kern_k, :2], Gk[kern_k], [k["zeiten"][i] for i in np.flatnonzero(kern_k)])
print(f"  Kaufhaus: Ausrichtung Anker neu {fk_neu['anker']} (alle {len(Gk)}), alt {fk_alt['anker']} (Kern {int(kern_k.sum())}); Drehung neu {fk_neu['drehung_grad']:+.2f} / alt {fk_alt['drehung_grad']:+.2f}")
pruef(fk_neu["anker"] is None and fk_alt["anker"] is None, "Kaufhaus: weder alt noch neu darf das GPS ankern (Lageproben bleiben zustaendig)")
rng = np.random.default_rng(3); wm = rng.uniform(0, 2 * np.pi, 16); Cm = np.c_[20 * np.cos(wm), 20 * np.sin(wm)]; Gm = rng.normal(0, 1.5, (16, 2))   # Martinstor: Geotag = Objektstandort
fm = GU.gps_fit(Cm, Gm, None)
pruef((not fm["ok"]) or fm["anker"] is None or not SA.gps_anker_aktiv(int(fm["w"].sum()), fm["rest_median_m"]), f"Martinstor (16 Objektstandort-Geotags) darf nicht ankern: {GU.gps_fit_text(fm)}")
pruef(not SA.gps_anker_aktiv(16, 3.0), "Martinstor: gps_anker_aktiv(16) muss aus bleiben")

# 4 Regel Lageproben gegen ankerfaehiges GPS; Kamerahoehe schwach
ent = dict(ergebnis="bestaetigt", wahl=0, je=["besteht", "faellt"], grund="x")
pruef(SA.lage_widerspruch_gps(ent, True, [True, False]) is ent, "Regel: Proben und GPS einig -> unveraendert")
pruef(SA.lage_widerspruch_gps(ent, False, [False, False]) is ent, "Regel: ohne ankerfaehiges GPS -> unveraendert (Kaufhaus, 1122 ohne Fernfotos)")
r1 = SA.lage_widerspruch_gps(ent, True, [False, True]); pruef(r1["ergebnis"] == "keine" and "WIDERSPRUCH" in r1["grund"], f"Regel: Proben waehlen, GPS verwirft -> keine Lage: {r1}")
r2 = SA.lage_widerspruch_gps(dict(ergebnis="belegt", wahl=1, je=["faellt", "besteht"], grund="x"), True, [False, False]); pruef(r2["ergebnis"] == "keine" and "WIDERSPRUCH" in r2["grund"], "Regel: keine GPS-stimmige Loesung -> keine Lage")
r3 = SA.lage_widerspruch_gps(dict(ergebnis="keine", wahl=None, je=["faellt", "faellt"], grund="x"), True, [True, False]); pruef(r3["ergebnis"] == "keine" and "WIDERSPRUCH" in r3["grund"], "Regel: GPS-stimmige faellt an den Proben -> benannte Ursache")
kh = dict(probe="kamerahoehe", urteil="besteht", schwach=True); ob = dict(probe="oberkante", urteil="besteht"); ku = dict(probe="wandfit", urteil="kein Urteil")
pruef(LP.bestanden([kh, ku]) == "kein Urteil", "Kamerahoehe allein darf keine Lage bestaetigen (1122j: 4 von 5 falschen Loesungen bestanden sie)")
pruef(LP.bestanden([kh, ob, ku]) == "besteht" and LP.bestanden([dict(kh, urteil="faellt"), ob]) == "faellt", "starke Probe bestaetigt, schwache darf verwerfen")

# 5 Verdrahtung
q = open(os.path.join(T, "sfm_lod2_ausrichten.py")).read(); qg = open(os.path.join(T, "lage_gps_pruefen.py")).read()
pruef("GU.gps_fit(" in qg and "GU.gps_fit(_Ca, _Ma" in q, "Tor und Ausrichtung muessen denselben GU.gps_fit rechnen")
pruef("gps_tor_urteil(GPS_ALLE" in q and "lage_widerspruch_gps(_ent" in q, "Ausrichtung: Veto = GPS-Tor, Regel Lageproben/GPS nicht verdrahtet")
pruef("_nah = _dc <= np.percentile(_dc, 70)" in q and "cm = C[_nah].mean(0)" in q, "Lot und Mitte muessen beim Kamerakern bleiben (Lehre 15.11.)")
pruef("if l is _wand_l:" in q and "LP.TOL_MASS" in q, "Wandfit-Kandidat darf nicht mit der 5-%-Regel verschluckt werden (Probe 1122j: 0,1060 neben 0,1109)")
pruef('"schwach=True"' not in q and "schwach=True" in open(os.path.join(T, "lage_proben.py")).read(), "Kamerahoehe muss als schwache Probe markiert sein")

print("GPS-EINE-QUELLE-TEST:", "bestanden" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
