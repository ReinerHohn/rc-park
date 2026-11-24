#!/usr/bin/env python3
"""test_massstab_teile.py - fester synthetischer Test fuer tools/massstab_teile.py und den MASSSTAB-BELEG in tools/seiten_waende_binden.py, nur CPU, < 1 min.

Befund 24.11.2026 (Kette schwabentor-1122, rc-park_tmp/verlorene_gewinner_2026-11-24.md Punkt 1/2): Nah-GPS EINER Sitzung schrumpft den Massstab (17.11. 0,875
Telefon-Nachlauf, 22.11. x0,867, 24.11. Teil 0 8,73 statt 10,14 m/Einheit); seiten_waende_binden nahm das GPS-Verhaeltnis B/A ungeprueft als Massstab.
  1 NACHLAUF   Gehweg mit Telefon-GPS, das nachhaengt (Glaettung tau 40 s): kurz klar unter lang, Plateau trifft den wahren Massstab; ohne Nachlauf: kein Befund.
  2 SCHRUMPF   Gesamt-Fit aus kurzen Paaren (Kameras nur in 2 Minuten) -> Schrumpftest nicht messbar; geschrumpfter Fit ausserhalb des Plateaus -> nicht bestanden.
  3 FERN       Nah-GPS um die Turmachse gezogen (x0,87, zeitunabhaengig: der Nachlauf-Test sieht es nicht) + Fernfotos -> gps_fern trifft den wahren Wert;
               eingefrorene Geotags = ein Beleg; falscher Geotag 1,9 km faellt weg.
  4 GEBAEUDE   Turm mit Nadel in eigener Wolke -> turm_dom1 trifft den Massstab; dicke Spitze -> nicht messbar; DGM-Steigung mit Hangkameras.
  5 EINIGKEIT  einig -> engste Quelle (kein Mittel); GPS gegen Gebaeudemass -> gps_widerlegt (Gebaeude gilt, Tor rot); Gebaeude unter sich uneinig -> uneinig, kein Wert.
  6 BINDUNG    ROTE PROBE: alter Weg (ohne Beleg) legt Teil B mit dem geschrumpften GPS-Verhaeltnis (x0,88) an - Massstab 12 % daneben, trotzdem 'gebunden'.
               Mit Beleg: Start korrigiert, Endlage im Band, Massstab < 2 % daneben; Beleg, der der Endlage widerspricht -> MASSSTAB-TOR rot; uneiniger Teil -> abgelehnt.
  7 VERDRAHTUNG main ruft massstab_beleg vor binden(beleg=...), Schalter RCPARK_WAENDE_MASSSTAB_BELEG, Audit pruefung.massstab_teile."""
import os, sys
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.join(os.path.dirname(HIER), "tools"); sys.path.insert(0, TOOLS)
import massstab_teile as MT
import seiten_waende_binden as WB

F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


S_WAHR = 8.0                                      # m je Modelleinheit
rng = np.random.default_rng(5)


def gang(n=60, dauer_s=900.0, seed=1):
    """Fussweg um einen Turm: Wahrheit (m), Zeiten (s)."""
    r = np.random.default_rng(seed); t = np.sort(r.uniform(0, dauer_s, n)); w = 2 * np.pi * t / dauer_s * 1.2
    X = np.c_[30 * np.cos(w) + r.normal(0, 3, n), 22 * np.sin(w) + r.normal(0, 3, n)]; return X, t


def nachhaengen(X, t, tau):
    """Telefon-GPS haengt nach: exponentielle Glaettung in der Zeit (tau s) + 2 m Rauschen."""
    Y = np.zeros_like(X); Y[0] = X[0]
    for k in range(1, len(X)):
        a = 1 - np.exp(-(t[k] - t[k - 1]) / tau); Y[k] = Y[k - 1] + a * (X[k] - Y[k - 1])
    return Y + rng.normal(0, 2.0, X.shape)


print("1 NACHLAUF")
X, t = gang(); C2 = X / S_WAHR
nl = MT.nachlauf(C2, nachhaengen(X, t, 40.0), list(t))
pruef(nl["messbar"] and nl["nachlauf"] is True, f"Nachlauf erkannt: {nl['urteil'][:160]}")
pruef(abs(nl["lang"]["s"] / S_WAHR - 1) < 0.05, f"Plateau {nl['lang']['s']} trifft den wahren Massstab {S_WAHR} (< 5 %)")
pruef(nl["kurz"]["s"] < 0.85 * S_WAHR, f"kurze Paare geschrumpft ({nl['kurz']['s']})")
nl0 = MT.nachlauf(C2, X + rng.normal(0, 2.0, X.shape), list(t))
pruef(nl0["messbar"] and nl0["nachlauf"] is False and nl0["schrumpftest_bestanden"] is True, f"ohne Nachlauf kein Befund: {nl0['urteil'][:140]}")

print("2 SCHRUMPF")
Xk, tk = gang(n=30, dauer_s=120.0, seed=2)
nlk = MT.nachlauf(Xk / S_WAHR, nachhaengen(Xk, tk, 40.0), list(tk))
pruef(nlk["messbar"] is False and nlk["schrumpftest_bestanden"] is None, f"nur 2 min Fotos: {nlk['urteil'][:120]}")
pruef(MT.gps_quellen(Xk / S_WAHR, nachhaengen(Xk, tk, 40.0), list(tk), nlk)[0][0]["name"] == "gps_nah", "nicht messbarer Schrumpftest verwirft das Nah-GPS nicht (nur Bericht)")
nl_s = dict(nl, schrumpftest_bestanden=False, urteil="Gesamt-Fit ausserhalb")
q, ber = MT.gps_quellen(C2, nachhaengen(X, t, 40.0), list(t), nl_s)
pruef(not any(x["name"] == "gps_nah" for x in q) and "verworfen" in ber["gps_nah"], "Schrumpftest nicht bestanden -> gps_nah traegt den Massstab nicht")

print("3 FERN (zeitunabhaengiger Sitzungsfehler)")
Gn = 0.87 * X + rng.normal(0, 2.0, X.shape)                                              # zur Turmachse gezogen
fern_w = np.array([[300.0, 40.0], [-250.0, 160.0], [60.0, -310.0], [200.0, 220.0]]); Cf = np.vstack([fern_w / S_WAHR] * 2)
Gf = np.vstack([fern_w + rng.normal(0, 4, fern_w.shape), fern_w + rng.normal(0, 4, fern_w.shape)])
Gf[4:6] = Gf[0]                                                                          # eingefroren: gleicher Geotag
Cx = np.vstack([C2, Cf, [[1500.0 / S_WAHR, 0.0]]]); Gx = np.vstack([Gn, Gf, [[1900.0, 0.0]]]); nah = np.r_[np.ones(len(C2), bool), np.zeros(len(Cf) + 1, bool)]
fq = MT.fern_quelle(Cx, Gx, nah)
pruef("massstab" in fq and abs(fq["massstab"] / S_WAHR - 1) < 0.03, f"gps_fern {fq.get('massstab')} trifft {S_WAHR} (< 3 %), Belege {fq.get('belege')}, verworfen {fq.get('verworfen')}")
pruef(fq.get("belege", 0) <= 8, "eingefrorener Geotag zaehlt einmal")
nlf = MT.nachlauf(C2, Gn, list(t))
pruef(nlf["schrumpftest_bestanden"] is True, "der zeitunabhaengige Zug besteht den Nachlauf-Test (Grenze des Tests, darum Fern/Gebaeude)")
qx, _ = MT.gps_quellen(Cx, Gx, list(t) + [None] * (len(Cf) + 1))
e = MT.einig(qx); pruef(e["quelle"] == "gps_fern" and abs(e["massstab"] / S_WAHR - 1) < 0.03, f"Einigkeit nimmt die engste Quelle gps_fern: {e['meldung'][:150]}")

print("4 GEBAEUDE")
def turm(m_je, nadel=True):
    r = np.random.default_rng(7); W = []
    for (x0, y0), (x1, y1) in (((-5, -4), (5, -4)), ((5, -4), (5, 4)), ((5, 4), (-5, 4)), ((-5, 4), (-5, -4))):
        n = 6000; s = r.random(n); W.append(np.c_[x0 + s * (x1 - x0), y0 + s * (y1 - y0), r.uniform(0, 40, n)])
    h = r.uniform(40, 47, 4000); rr = (47 - h) / 7 * 5; a = r.uniform(0, 2 * np.pi, 4000); W.append(np.c_[rr * np.cos(a), rr * np.sin(a), h])   # Helm
    if nadel: W.append(np.c_[r.normal(0, 0.05, 800), r.normal(0, 0.05, 800), r.uniform(47, 50, 800)])
    else: W.append(np.c_[r.uniform(-3, 3, 800), r.uniform(-3, 3, 800), r.uniform(47, 50, 800)])
    W.append(np.c_[r.uniform(-30, 30, 60000), r.uniform(-30, 30, 60000), r.normal(0, 0.02, 60000)])
    return np.vstack(W) / m_je
ref = dict(h_m=50.0, halb_m=1.25)
P = turm(S_WAHR); mj_gps = 0.87 * S_WAHR                                                   # GPS-Massstab geschrumpft
tp = MT.turm_probe(P * mj_gps, ref, mj_gps)
pruef("massstab" in tp and abs(tp["massstab"] / S_WAHR - 1) < 0.03, f"turm_dom1 {tp.get('massstab')} trifft {S_WAHR} trotz GPS {mj_gps:.2f} ({tp.get('grund', '')})")
tp2 = MT.turm_probe(turm(S_WAHR, nadel=False) * mj_gps, ref, mj_gps)
pruef("massstab" not in tp2 and "schlank" in tp2.get("grund", ""), f"dicke Spitze: nicht messbar ({tp2.get('grund', '')[:80]})")
pruef("massstab" not in MT.turm_probe(P * mj_gps, None, mj_gps), "ohne DOM1/LoD2-Referenz keine Turmprobe")
he = np.r_[np.zeros(20), np.linspace(20, 35, 12)] + rng.normal(0, 0.5, 32); h_wahr = he + 1.6
dp = MT.dgm_probe(h_wahr / S_WAHR, he, mj_gps)
pruef("massstab" in dp and dp["lo"] <= S_WAHR <= dp["hi"], f"dgm_steigung {dp.get('massstab')} [{dp.get('lo')}, {dp.get('hi')}] enthaelt {S_WAHR}")
pruef("massstab" not in MT.dgm_probe(np.zeros(20), rng.normal(0, 0.3, 20), mj_gps), "ebenes Umfeld: DGM-Steigung nicht messbar")

print("5 EINIGKEIT")
q = lambda n, a, s, h: MT._q(n, a, s, s * (1 - h), s * (1 + h))
e = MT.einig([q("gps_nah", "gps", 8.1, 0.18), q("turm_dom1", "gebaeude", 7.96, 0.025), q("dgm_steigung", "gebaeude", 8.27, 0.08)])
pruef(e["urteil"] == "einig" and e["massstab"] == 7.96 and e["tor"] == "gruen", f"einig -> engste (turm_dom1 7,96, kein Mittel): {e['meldung'][:90]}")
e = MT.einig([q("gps_nah", "gps", 7.0, 0.03), q("turm_dom1", "gebaeude", 7.96, 0.025), q("dgm_steigung", "gebaeude", 8.1, 0.08)])
pruef(e["urteil"] == "gps_widerlegt" and e["massstab"] == 7.96 and e["tor"] == "rot", f"GPS widerlegt -> Gebaeudemass gilt, Tor rot: {e['meldung'][:80]}")
e = MT.einig([q("turm_dom1", "gebaeude", 7.0, 0.02), q("dgm_steigung", "gebaeude", 8.3, 0.03)])
pruef(e["urteil"] == "uneinig" and e["massstab"] is None and e["tor"] == "rot", "Gebaeudemass unter sich uneinig -> kein Wert, Tor rot")
pruef(MT.einig([])["urteil"] == "nicht_messbar", "keine Quelle -> nicht_messbar")
v = MT.verhaeltnis(dict(ergebnis=dict(massstab=10.0, lo=9.8, hi=10.2, quelle="gps_fern", urteil="einig")), dict(ergebnis=dict(massstab=8.0, lo=7.8, hi=8.2, quelle="turm_dom1", urteil="einig")))
pruef(abs(v["wert"] - 0.8) < 1e-9 and v["lo"] < 0.8 < v["hi"], f"Verhaeltnis B->A = m_B / m_A = {v['wert']} [{v['lo']}, {v['hi']}]")

print("6 BINDUNG (rote Probe: alter Weg uebernimmt das geschrumpfte GPS-Verhaeltnis)")
def wand(p0, p1, z0, z1, dichte, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float); L = np.linalg.norm(p1 - p0); n = int(dichte * L * (z1 - z0)); s = r.random(n); z = z0 + (z1 - z0) * r.random(n)
    d = (p1 - p0) / L; nn = np.array([-d[1], d[0]]); xy = p0 + np.outer(s * L, d) + np.outer(r.normal(0, 0.02, n), nn); return np.c_[xy, z]
r = np.random.default_rng(3); SW, SO, NO, NW = (-5, -4), (5, -4), (5, 4), (-5, 4)
turm_a = np.vstack([wand(SW, SO, 0, 30, 25, r), wand(SO, NO, 0, 30, 25, r), wand(NO, NW, 0, 30, 25, r), wand(NW, SW, 0, 30, 25, r)])
boden = np.c_[r.uniform(-30, 30, 30000), r.uniform(-30, 30, 30000), r.normal(0, 0.02, 30000)]; welt_a = np.vstack([turm_a, boden])
welt_b = np.vstack([wand(SW, SO, 0, 30, 25, r), wand(SO, NO, 0, 30, 25, r), np.c_[r.uniform(-20, 20, 15000), r.uniform(-30, -5, 15000), r.normal(0, 0.02, 15000)]])
kam_b = np.c_[r.uniform(-15, 15, 40), r.uniform(-40, -18, 40), np.full(40, 1.6)]
MJ = 5.0; MA = np.eye(4); MA[:3, :3] = WB.drehung(np.array([1, 2, 0.5]), 25) / MJ; MA[:3, 3] = [1.0, -2.0, 0.5]
MB = np.eye(4); MB[:3, :3] = 0.37 * WB.drehung(np.array([0.3, -1, 2.0]), 140); MB[:3, 3] = [-4.0, 3.0, 9.0]; M_wahr = MA @ np.linalg.inv(MB)
lot_a = MA[:3, :3] @ [0, 0, 1.0]; lot_a /= np.linalg.norm(lot_a); DA = WB.anwenden(MA, welt_a); DB = WB.anwenden(MB, welt_b); ref_b = WB.anwenden(MB, kam_b)
r_wahr = float(WB.zerlege(M_wahr)[0])


def gps_lage(mass):
    W = np.eye(4); c = np.r_[np.median(welt_b[:, :2], 0), np.percentile(welt_b[:, 2], 2)]; R = mass * WB.drehung(np.array([0, 0, 1.0]), 2.0); W[:3, :3] = R; W[:3, 3] = c - R @ c + [0.8, 0.6, 0]
    return MA @ W @ np.linalg.inv(MA) @ M_wahr


G = lambda Mg: dict(M=Mg, dreh_sd=1.4, mass_sd=0.03, lage_sd_m=1.0, m_je_einheit=MJ, dreh_sd_ehrlich=9.3, mass_sd_ehrlich=0.16)
Mg = gps_lage(0.88)                                                                     # GPS-Verhaeltnis 12 % geschrumpft (1122: 0,907 statt 0,785-0,800)
alt_h = WB.HEBEL_MIN_M; WB.HEBEL_MIN_M = 1e9                                            # Turmecke allein belegt keinen Massstab (wie 1122y: Wand-Massstab nicht uebernommen)
e_alt = WB.binden(DA, DB, G(Mg), lot_a, ref_b)
fa = abs(float(WB.zerlege(np.asarray(e_alt.get("B_nach_A", Mg)))[0]) / r_wahr - 1)
pruef(e_alt.get("ok") is True and fa > 0.10, f"ROTE PROBE alter Weg: {'gebunden' if e_alt.get('ok') else 'abgelehnt'} mit Massstab {100 * fa:.1f} % daneben (> 10 % = GPS-Schrumpf uebernommen)")
bel = dict(verhaeltnis=dict(wert=round(r_wahr * 1.005, 6), lo=r_wahr * 0.975, hi=r_wahr * 1.03, quelle_a="gps_fern", quelle_b="turm_dom1", urteil_a="einig", urteil_b="einig"), rot=[])
e_neu = WB.binden(DA, DB, G(Mg), lot_a, ref_b, beleg=bel); mb = e_neu["pruefung"].get("massstab_beleg") or {}
fn = abs(float(WB.zerlege(np.asarray(e_neu.get("B_nach_A", Mg)))[0]) / r_wahr - 1)
pruef(e_neu.get("ok") is True and mb.get("angewandt") is True and mb.get("ende_im_band") is True and fn < 0.02,
      f"mit Beleg: gebunden, Start korrigiert, Massstab {100 * fn:.2f} % daneben (< 2 %): {e_neu.get('urteil', '')[:160]}")
pruef("B_nach_A_gps" in e_neu and abs(float(WB.zerlege(np.asarray(e_neu["B_nach_A_gps"]))[0]) / r_wahr - 0.88) < 0.01, "Audit: B_nach_A_gps bleibt die GPS-Lage (0,88)")
e_gl = WB.binden(DA, DB, G(gps_lage(1.0)), lot_a, ref_b, beleg=bel)
pruef(e_gl.get("ok") is True and (e_gl["pruefung"].get("massstab_beleg") or {}).get("angewandt") is False, "GPS-Verhaeltnis im Band -> Start bleibt GPS (Guard greift nur bei Widerspruch)")
WB.HEBEL_MIN_M = alt_h
# Beleg gegen die Waende: nur pruefbar, wenn die Waende selbst einen Massstab messen (Hebel: B sieht auch das Nachbarhaus, wie test_seiten_waende_binden Fall 6)
nachbar = np.vstack([wand((-20, -3), (-9, -3), 0, 12, 25, r), wand((-9, -3), (-9, 6), 0, 12, 25, r)])
nb_b = np.vstack([wand((-9, -3), (-9, 6), 3.5, 12, 25, r), wand((-20, -3), (-9, -3), 3.5, 12, 25, r)])
DA6 = WB.anwenden(MA, np.vstack([welt_a, nachbar])); welt_b = np.vstack([welt_b, nb_b]); DB6 = WB.anwenden(MB, welt_b)
bel_falsch = dict(verhaeltnis=dict(wert=r_wahr * 0.85, lo=r_wahr * 0.83, hi=r_wahr * 0.87, quelle_a="x", quelle_b="y", urteil_a="einig", urteil_b="einig"), rot=[])
e_f = WB.binden(DA6, DB6, G(gps_lage(0.85)), lot_a, ref_b, beleg=bel_falsch); mf = e_f["pruefung"].get("massstab_beleg") or {}
pruef(e_f.get("ok") is False and "B_nach_A" not in e_f and "MASSSTAB-TOR" in e_f["urteil"], f"Waende messen {mf.get('ende_verhaeltnis', 0) / r_wahr:.3f} x wahr gegen Beleg 0,85 -> MASSSTAB-TOR rot ({e_f['urteil'][:150]})")
e_r = WB.binden(DA6, DB6, G(gps_lage(0.88)), lot_a, ref_b, beleg=bel)
pruef(e_r.get("ok") is True and abs(float(WB.zerlege(np.asarray(e_r["B_nach_A"]))[0]) / r_wahr - 1) < 0.01, f"Waende mit Hebel + richtiger Beleg: einig, Massstab < 1 % ({(e_r['pruefung'].get('massstab') or {}).get('uebernommen')})")
print("  Hinweis BEKANNTE GRENZE:sieht B nur eine Turmecke (Hebel 0), pruefen die Waende den Massstab nicht - dann traegt der Beleg allein (alter Weg: das GPS allein)")
e_u = WB.binden(DA, DB, G(gps_lage(1.0)), lot_a, ref_b, beleg=dict(verhaeltnis=None, rot=["Teil A: MASSSTAB-TOR ROT (Quellen uneinig)"]))
pruef(e_u.get("ok") is False and "uneinig" in e_u["urteil"], "uneiniger Teil -> Tor rot, abgelehnt mit Bericht")

print("7 VERDRAHTUNG")
src = open(os.path.join(TOOLS, "seiten_waende_binden.py")).read()
pruef("bel, mt = massstab_beleg(a, vj, DA, DB, G)" in src and "beleg=bel)" in src and src.index("massstab_beleg(a, vj") < src.index("erg = binden(DA, DB"),
      "main: massstab_beleg vor binden(beleg=...)")
pruef("RCPARK_WAENDE_MASSSTAB_BELEG" in src and 'erg["pruefung"]["massstab_teile"] = mt' in src and "RCPARK_SEITEN_OBJEKT" in src, "Schalter, Audit, objekt.json aus der Kette")
pruef("massstab_teile" in src.split("def massstab_beleg")[1][:3000], "seiten_waende_binden importiert massstab_teile (Code-Stand der Nachstufe folgt den Importen)")

print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER")
sys.exit(1 if F else 0)
