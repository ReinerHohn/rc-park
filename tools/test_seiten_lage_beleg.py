#!/usr/bin/env python3
"""Fester Test (synthetisch, < 5 s) fuer tools/seiten_lage_beleg.py - REGEL "Teil nur bei belegter Lage einsetzen" (22.11.2026, schwabentor-1122 Teil 1).
  1 lage_belegt   Klappung / Querspur / LoD2 je Teil -> belegt; nur GPS: ehrlich belegt UND Wanddicke der GPS-Lage ok -> belegt; GPS-Band zu weit, Doppelwand, versetzt,
                  keine Kante mit beiden Teilen, kein LoD2-Ergebnis -> NICHT belegt (Grund benannt).
  2 Richtung      Teil B westlich der Gebaeudemitte -> 'Westseite' (270 Grad); ohne Mitte grob A -> B; zu wenig GPS -> None. Fotoluecke-Text fuer Kette/Fotoauftrag.
  3 Fotoauftrag   foto_auftrag.seiten_bedarf: Luecke 'Westseite' waehlt die Westfassade (Rahmen wie schwabentor: +x Nord, +y West), ganze Wand, auto; ohne Azimut -> Meldung.
  4 Folgestufen   wand_dicke_tor mit 'teil_a_allein' -> rc 2 (kein Absturz); gesamtkette meldet 'seiten_fotoluecke' in der Stufe tore und gibt foto_auftrag --seiten-modelle;
                  iphone_sfm reicht 'fotoluecken' weiter; Schalter RCPARK_TEIL_NUR_BELEGT und Code-Stand der Nachstufe.
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_lage_beleg.py"""
import os, sys, json, tempfile, io, contextlib, shutil
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_lage_beleg as SLB

# ---------- 1 lage_belegt
kante = lambda u, d=0.4: dict(von=[0, 0], bis=[0, 10], urteil=u, lageunterschied_m=d, dicke_gesamt_m=3.9 if u == "doppelwand" else 0.4)
wd = lambda *K: dict(vorher=dict(kanten=list(K), kanten_mit_beiden=sum(1 for k in K if k.get("lageunterschied_m") is not None)))
gps = lambda ok: dict(lage_b_belegt=ok, dreh_sd_ehrlich_grad=3.0 if ok else 9.5, mass_sd_ehrlich_rel=0.09 if ok else 0.17)
F = lambda weg="gps", p=None, w=None: dict(weg=weg, pruefung=p or {}, lod2_je_teil=None if w is None else dict(wand_dicke=w))
for e, soll, was in [(F("klappung"), True, "Klappung"), (F("gps+querspur"), True, "Querspur"), (F("gps+lod2"), True, "LoD2 je Teil"),
                     (F(p=gps(True), w=wd(kante("ok", 0.12))), True, "GPS ehrlich + Wanddicke ok"),
                     (F(p=gps(False), w=wd(kante("ok", 0.12))), False, "GPS-Band zu weit (schwabentor-1122 Teil 1: +-9,5 Grad / 17 %)"),
                     (F(p=gps(True), w=wd(kante("doppelwand", 3.6))), False, "Doppelwand (Teile 3,6 m auseinander)"),
                     (F(p=gps(True), w=wd(kante("versetzt", 0.9))), False, "versetzt 0,9 m > 0,5 m"),
                     (F(p=gps(True), w=wd(dict(von=[0, 0], bis=[0, 10], urteil="ok", lageunterschied_m=None))), False, "keine Kante mit beiden Teilen"),
                     (F(p=gps(True)), False, "kein LoD2-je-Teil-Ergebnis"), (F(p=dict(dreh_sd_grad=2.0)), False, "alter GPS-Bericht ohne ehrliche Unsicherheit"), (F("??"), False, "unbekannter Weg")]:
    b, g, pr = SLB.lage_belegt(e); assert b is soll and g, f"{was}: belegt {b} (soll {soll}) - {g}"
b, g, pr = SLB.lage_belegt(F(p=gps(True), w=wd(kante("doppelwand", 3.6)))); assert "doppelwand" in g and "3.6" in g and "1.2" in g, f"Grund nennt Kante/Grenze nicht: {g}"
assert SLB.DICKE_MAX_M == 1.2 and SLB.VERSATZ_MAX_M == 0.5, "Grenzen nicht aus wand_dicke_tor (am 1120 begruendet)"
print("ok 1: lage_belegt - 3 Bindungswege belegt, GPS nur mit ehrlichem Band + widerspruchsfreier Wanddicke, 7 Gegenfaelle mit benanntem Grund")

# ---------- 2 Richtung, Seite, Luecke
rng = np.random.default_rng(1); B = np.c_[rng.uniform(-30, -20, 25), rng.uniform(-6, 6, 25)]; A = np.c_[rng.uniform(-10, 25, 80), rng.uniform(10, 30, 80)]
az, her = SLB.richtung_aus_punkten(B, mitte=[0, 0]); assert abs(az - 270) < 10 and SLB.seite_name(az) == "Westseite" and "Gebaeudemitte" in her, f"West: {az} {her}"
az2, her2 = SLB.richtung_aus_punkten(B, None, A); assert 180 < az2 < 270 and "ANNAHME" in her2, f"ohne Mitte: {az2} {her2}"
assert SLB.richtung_aus_punkten(B[:2], [0, 0])[0] is None and SLB.seite_name(None) is None and SLB.seite_name(0) == "Nordseite" and SLB.seite_name(95) == "Ostseite"
L = SLB.luecke(1, 127, "nur GPS ...", az, her); assert L["seite"] == "Westseite" and L["text"].startswith("Seite Westseite: Lage nicht belegt, nicht gebaut - Fotos noetig: Brueckenfotos schraeg ueber Eck / Fernfotos") and len(L["fotos_noetig"]) == 2
L0 = SLB.luecke(2, 40, "x"); assert "Richtung unbekannt" in L0["seite"] and L0["azimut_grad"] is None
az3, her3 = SLB.richtung("/gibt/es/nicht", "/gibt/es/nicht/a", "/gibt/es/nicht/b"); assert az3 is None and her3, "richtung() muss ohne Daten ohne Absturz None liefern"
print(f"ok 2: Richtung West {az:.0f} Grad -> Westseite, ohne Mitte grob {az2:.0f} Grad, Fotoluecke-Text, ohne Daten kein Absturz")

# ---------- 3 Fotoauftrag
import foto_auftrag as FAU
xh, yh = np.array([-0.2426, 0.9701]), np.array([-0.9701, -0.2426])          # schwabentor-Rahmen: +x ~ Nord, +y ~ West
FA = [dict(n=[1, 0], u=[0, 12], z=[0, 30], flaeche_m2=360), dict(n=[0, 1], u=[0, 10], z=[0, 30], flaeche_m2=300), dict(n=[-1, 0], u=[0, 12], z=[0, 30], flaeche_m2=360), dict(n=[0, -1], u=[0, 10], z=[0, 30], flaeche_m2=300)]
bed, mel = FAU.seiten_bedarf(FA, [L, L0], xh, yh, 0.01)
assert len(bed) == 1 and bed[0]["wand"] == 1 and bed[0]["auto"] and bed[0]["u"] == [0, 10] and "Lage nicht belegt, nicht gebaut" in bed[0]["titel"] and "Brueckenfotos" in bed[0]["warum"], f"Westwand nicht gewaehlt: {bed}"
assert len(mel) == 1 and "Richtung unbekannt" in mel[0], f"Luecke ohne Azimut nicht gemeldet: {mel}"
assert FAU.seiten_bedarf(FA, None, xh, yh, 0.01) == ([], [])
print("ok 3: Fotoauftrag - Westseite -> Westfassade (ganze Wand, ungesehen), ohne Richtung Meldung")

# ---------- 4 Folgestufen
import wand_dicke_tor as WD
S = tempfile.mkdtemp(prefix="test_lage_beleg_")
try:
    sm = os.path.join(S, "seiten_modelle.json"); au = os.path.join(S, "au.json"); oj = os.path.join(S, "objekt.json")
    json.dump(dict(ergebnis=dict(art="teil_a_allein"), vereint=[0], nicht_vereint=[1], fotoluecken=[L]), open(sm, "w")); json.dump(dict(kameras={}), open(au, "w")); json.dump(dict(lod2=dict(id="X")), open(oj, "w"))
    with contextlib.redirect_stdout(io.StringIO()): rc = WD.main([oj, "--seiten", sm, "--ausrichtung", au, "--aus", os.path.join(S, "wd.json")])
    assert rc == 2 and "keine vereinten" in json.load(open(os.path.join(S, "wd.json")))["urteil"], f"wand_dicke_tor mit Teil A allein: rc {rc}"
finally: shutil.rmtree(S, ignore_errors=True)
q = lambda n: open(os.path.join(T, n)).read()
assert "seiten_fotoluecke_teil" in q("gesamtkette.py") and '"--seiten-modelle"' in q("gesamtkette.py"), "gesamtkette meldet die Fotoluecke nicht / gibt sie dem Fotoauftrag nicht"
assert 'fotoluecken=_sm.get("fotoluecken")' in q("iphone_sfm.py"), "iphone_sfm reicht fotoluecken nicht weiter"
import sfm_seiten_modelle as SM
assert "seiten_lage_beleg.py" in SM.NACHSTUFE and "SLB.lage_belegt(" in q("sfm_seiten_modelle.py") and "RCPARK_TEIL_NUR_BELEGT" in q("seiten_lage_beleg.py")
an = SM.nachstufe_code(); SM.NUR_BELEGT = False
try: assert SM.nachstufe_code() == an + "+belegt0", "Schalter nicht im Code-Stand der Nachstufe"
finally: SM.NUR_BELEGT = True
print("ok 4: Folgestufen - wand_dicke_tor rc 2 ohne Absturz, Kette meldet seiten_fotoluecke + Fotoauftrag, Schalter im Code-Stand")
