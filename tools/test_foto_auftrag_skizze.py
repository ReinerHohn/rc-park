#!/usr/bin/env python3
"""Fester Test (synthetisch, ~5 s) fuer tools/foto_auftrag_skizze.py - Fotoauftrag frueh und als Bild (22.11.2026, schwabentor-1122: Suedseite nicht angebunden).
  1 Rechteck frei  Ziel 12 x 10 m (Rahmen wie Schwabentor: +x Nord, +y West), Wolke auf Nord/Ost/West, Suedseite ohne Punkte -> Sued rot, Rest gruen;
                   Uebereck-Boegen an GENAU den zwei Suedecken (Sued/Ost und Sued/West), Frontalreihe Sued, Fernstandorte; kein Standpunkt in einem Nachbarhaus
                   (Nachbar liegt genau auf dem Sued/West-Bogen); Skizze/JSON/Text geschrieben, WGS84 je Foto.
  2 Fotoluecke     seiten_modelle 'fotoluecken' Azimut 165 Grad -> Suedwand 'nicht angebunden' mit Begruendung aus 'grund'.
  3 angebaut       niedriger Nachbar an der Ostseite -> Ostwand des Ziels 'frei ab' Nachbarhoehe, Umriss laeuft ueber den Block (Nachbarwaende markiert).
  4 Foto pruefen   GPS am Soll-Ort + Kompass in Blickrichtung -> erfuellt; 20 m dahinter -> 'PASST NICHT' mit Meterangabe; Kompass falsch -> drehen; ohne GPS -> Hinweis.
  5 Kette          gesamtkette ruft das Werkzeug nach der SfM und am Laufende auf (Schalter RCPARK_FOTOAUFTRAG_SKIZZE), Bildpfad im Bericht.
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_foto_auftrag_skizze.py"""
import os, sys, json, math, tempfile, shutil
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import foto_auftrag_skizze as FS

OBJ = dict(name="Testturm", lod2=dict(id="Z"), rahmen=dict(mitte_utm=[414000.0, 5316000.0], xhat_utm=[0.0, 1.0], yhat_utm=[-1.0, 0.0], gelaende=280.0))
R = FS.Rahmen(OBJ)
G = lambda i, ring, oben, ziel=False: dict(id=i, ziel=ziel, ringe=[FS.ring_sauber(np.array(ring, float))], oben=oben, boden=0.0, traufe=oben * 0.7, first=oben)
ZIEL = G("Z", [[0, 0], [12, 0], [12, 10], [0, 10]], 20.0, True)          # x 0..12 (Sued..Nord), y 0..10 (Ost..West)
NACHBAR_SW = G("N1", [[-14, 12], [-7, 12], [-7, 21], [-14, 21]], 9.0)    # liegt auf dem Bogen um die Sued/West-Ecke (0, 10)
FERN = G("N2", [[40, -30], [60, -30], [60, -10], [40, -10]], 12.0)
KAM = (np.array([[30.0, 5.0, 1.6], [25.0, -8.0, 1.6], [6.0, 30.0, 1.6], [6.0, -25.0, 1.6]]), [], (66.0, 52.0), 3000.0, 5.0)


def wolke(pfad, waende):
    rng = np.random.default_rng(1); P = []
    for (a, b) in waende:
        t = rng.random(40000); z = 2 + 18 * rng.random(40000); a, b = np.array(a, float), np.array(b, float); xy = a + np.outer(t, b - a); P.append(np.c_[xy + rng.normal(0, 0.1, xy.shape), z])
    np.save(pfad, np.vstack(P))


tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR") or "/media/oem/rcdaten/tmp")
try:
    # ---------- 1 Rechteck frei, Suedseite leer
    wp = os.path.join(tmp, "w.npy"); wolke(wp, [([12, 0], [12, 10]), ([0, 0], [12, 0]), ([0, 10], [12, 10])])      # Nord, Ost, West
    e = FS.erzeugen(None, wp, None, None, None, os.path.join(tmp, "a1"), obj=OBJ, geb=[ZIEL, NACHBAR_SW, FERN], kam=KAM)
    kl = {w["seite"]: w["klasse"] for w in e["waende"] if w["frei"]}
    assert kl == {"Nordseite": "gruen", "Ostseite": "gruen", "Westseite": "gruen", "Südseite": "rot"}, kl
    ue = [s for s in e["standpunkte"] if s["art"] == "uebereck"]; ecken = sorted(tuple(np.round(s["ziel_xy"]).astype(int)) for s in ue)
    assert ecken == [(0, 0), (0, 10)], f"Uebereck nicht an den zwei Suedecken: {ecken}"
    for s in ue: assert 3 <= s["anzahl"] <= 30 and s["schritt_m"] > 0.5 and s["radius_m"] >= 2, s
    assert any(s["art"] == "frontal" and "Süd" in s["titel"] for s in e["standpunkte"]), "keine Frontalreihe Sued"
    alle = np.array([[f["x"], f["y"]] for s in e["standpunkte"] for f in s["fotos"]])
    assert not FS.innen(alle, NACHBAR_SW["ringe"] + FERN["ringe"] + ZIEL["ringe"]).any(), "Standpunkt in einem Gebaeude"
    sw = [s for s in ue if tuple(np.round(s["ziel_xy"]).astype(int)) == (0, 10)][0]; se = [s for s in ue if s is not sw][0]
    assert sw["anzahl"] < se["anzahl"] or any(np.hypot(f["x"], f["y"] - 10) < se["radius_m"] - 0.5 for f in sw["fotos"]), "Nachbar auf dem SW-Bogen hat nichts verschoben/verworfen"
    fe = [s for s in e["standpunkte"] if s["art"] == "fern"]
    assert fe and all(e["fern"]["d_min_m"] - 1 <= s["entfernung_m"] <= e["fern"]["d_max_m"] + 1 for s in fe), f"Fernstandorte fehlen/ausserhalb: {[s['entfernung_m'] for s in fe]} {e['fern']}"
    f0 = ue[0]["fotos"][0]; assert 47 < f0["lat"] < 49 and 7 < f0["lon"] < 9 and all(s["gps_an"] for s in e["standpunkte"]), f0
    for x in ("png", "json", "md"): assert os.path.getsize(os.path.join(tmp, "a1", "foto_auftrag." + x)) > 200, x
    assert os.path.getsize(os.path.join(tmp, "a1", "foto_auftrag.png")) < 1_000_000, "Skizze > 1 MB"
    print(f"ok 1: Rechteck - Sued rot, Uebereck an (0,0) und (0,10) mit {[s['anzahl'] for s in ue]} Fotos, Frontalreihe, {len(fe)} Fernstandorte, nichts in Gebaeuden")

    # ---------- 2 Fotoluecke aus seiten_modelle
    sm = os.path.join(tmp, "seiten_modelle.json")
    json.dump(dict(nicht_vereint=[1], fotoluecken=[dict(teil=1, bilder=127, seite="Suedostseite", azimut_grad=165.0, grund="nur GPS, Lage NICHT unabhaengig belegt - gps_ehrlich: NICHT bestanden (Drehung +-16 Grad); wanddicke_gps_lage: bestanden (ok)")]), open(sm, "w"))
    e2 = FS.erzeugen(None, wp, None, sm, None, os.path.join(tmp, "a2"), obj=OBJ, geb=[ZIEL, NACHBAR_SW, FERN], kam=KAM, zeichnen=False)
    w = [w for w in e2["waende"] if w.get("luecke")]; assert len(w) == 1 and w[0]["seite"] == "Südseite" and w[0]["klasse"] == "rot", w
    L = [l for l in e2["luecken"] if l.get("teil") == 1][0]; assert "127 Bilder" in L["satz"] and "Drehung +-16 Grad" in L["satz"] and "wanddicke" not in L["satz"], L["satz"]
    print("ok 2: Fotoluecke Azimut 165 -> Suedwand 'nicht angebunden', Begruendung nur aus den NICHT bestandenen Proben")

    # ---------- 3 niedriger Nachbar an der Ostseite
    OST = G("N3", [[0, -8], [12, -8], [12, 0], [0, 0]], 8.0)
    wolke(wp, [([12, 0], [12, 10]), ([0, 10], [12, 10]), ([12, -8], [12, 0])])
    e3 = FS.erzeugen(None, wp, None, None, None, os.path.join(tmp, "a3"), obj=OBJ, geb=[ZIEL, OST, NACHBAR_SW, FERN], kam=KAM, zeichnen=False)
    ost = [w for w in e3["waende"] if w["seite"] == "Ostseite" and w["frei_ab_m"] > 0]
    assert ost and abs(ost[0]["frei_ab_m"] - 8.0) < 0.01, [(w["seite"], w["frei_ab_m"]) for w in e3["waende"]]
    assert any(w["seite"] == "Südseite" and w["laenge_m"] > 7 and w["klasse"] == "rot" for w in e3["waende"]), "Block-Suedseite fehlt"
    print(f"ok 3: Ostseite ueber dem Nachbardach frei ab {ost[0]['frei_ab_m']} m, Umriss ueber den Block ({len(e3['waende'])} Waende)")

    # ---------- 4 Foto pruefen
    A = json.load(open(os.path.join(tmp, "a1", "foto_auftrag.json"))); s = [s for s in A["standpunkte"] if s["art"] == "frontal"][0]; f = s["fotos"][1]
    r = FS.pruefen(A, "x.jpg", gps=(f["lat"], f["lon"], f["blick_grad"])); assert r["urteil"] == "erfuellt" and f"Standpunkt {s['nr']}" in r["text"], r
    v = R.richtung(f["blick_grad"]); q = np.array([f["x"], f["y"]]) - v * 20.0; la, lo = R.geo(q)     # 20 m hinter dem Soll (weg von der Wand)
    r = FS.pruefen(A, "x.jpg", gps=(la, lo, f["blick_grad"])); assert r["urteil"] == "nicht" and "PASST NICHT" in r["text"] and " m " in r["text"] and ("näher" in r["text"] or "nach" in r["text"]), r
    r = FS.pruefen(A, "x.jpg", gps=(f["lat"], f["lon"], (f["blick_grad"] + 90) % 360)); assert r["urteil"] == "nicht" and "drehen" in r["text"], r
    r = FS.pruefen(A, os.path.join(tmp, "gibtsnicht.jpg")); assert r["urteil"] == "ohne_gps" and "GPS" in r["text"], r
    print("ok 4: Foto pruefen - am Soll erfuellt, 20 m dahinter -> Meterangabe, Kompass falsch -> drehen, ohne GPS -> Hinweis")

    # ---------- 5 Kette
    gk = open(os.path.join(T, "gesamtkette.py")).read()
    assert gk.count("foto_auftrag_skizze(") >= 3 and "RCPARK_FOTOAUFTRAG_SKIZZE" in gk and '"frueh"' in gk and '"ende"' in gk, "Kettenaufruf fehlt"
    print("ok 5: gesamtkette ruft die Skizze frueh (nach SfM) und am Laufende, Schalter RCPARK_FOTOAUFTRAG_SKIZZE")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("ALLE TESTS BESTANDEN")
