#!/usr/bin/env python3
"""test_verlustbilanz.py - Verlustbilanz (tools/verlustbilanz.py) an synthetischen Kettenordnern (Sekunden, keine echten Daten).
Faelle: (1) Nulllauf schwabentor-1122: gewaehlter Clip ohne Bilder und ohne Fehlerzeile -> WARNUNG; mit Fehlerzeile frames_<id> -> benannt, keine WARNUNG.
(2) Vorpruefung/Sammeln/Bildwahl/Seitenmodelle: Verluste mit Grund zaehlen nicht als still; Mapper verliert 30 % ohne Grund -> WARNUNG.
(3) Grenze je Stufe ueber RCPARK_VERLUST_MAX_<STUFE>; (4) Datei aelter als der Laufstart -> stand 'frueher'; (5) Log-Abschnitt nur ab der Startzeile des Laufs;
(6) kaputte JSON -> Zeile NICHT LESBAR statt Absturz; (7) gesamtkette.abschluss ruft die Bilanz auf (Quelltext)."""
import os, sys, json, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verlustbilanz as VB


F = 0
def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text); F += 0 if ok else 1


def bild(p):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"\xff\xd8\xff")


with tempfile.TemporaryDirectory(prefix="test_verlustbilanz_") as T:
    D = os.path.join(T, "daten"); Z = os.path.join(T, "modell"); os.makedirs(os.path.join(Z, "audit")); os.makedirs(os.path.join(D, "pipe", "sfm"))
    json.dump(dict(gewaehlt=[dict(id="aa"), dict(id="bb"), dict(id="cc")]), open(os.path.join(D, "clips.json"), "w"))
    for i in range(3): bild(os.path.join(D, "video_frames", "aa", f"vf_{i}.jpg")); bild(os.path.join(D, "video_frames", "cc", f"vf_{i}.jpg"))
    os.makedirs(os.path.join(D, "video_frames", "bb"))                         # kaputter Download: Ordner da, 0 Bilder, Stufe rc 0
    B = dict(schritte=[dict(stufe="LAUF_START"), dict(stufe="frames_bb", rc=0, ok=True, ende=["0 scharfe Frames (von 0)"])])
    V = VB.bilanz(D, Z, B=B)
    e = [x for x in V["stufen"] if x["stufe"] == "video_clips"][0]
    pruef(e["rein"] == 3 and e["raus"] == 2 and e["ohne_grund"] == 1 and "bb" in e.get("hinweis", ""), f"Clip ohne Bilder und ohne Fehlerzeile = still verloren ({e['rein']} -> {e['raus']}, ohne Grund {e['ohne_grund']})")
    pruef(any("video_clips" in w for w in V["warnungen"]), "-> WARNUNG video_clips (33 % > 5 %)")
    B["schritte"][-1].update(rc=1, ok=False, fehler="yt-dlp: Download kaputt")
    V = VB.bilanz(D, Z, B=B); e = [x for x in V["stufen"] if x["stufe"] == "video_clips"][0]
    pruef(e["ohne_grund"] == 0 and "yt-dlp" in e["verloren"][0]["grund"] and not V["warnungen"], "mit Fehlerzeile frames_bb im Bericht = benannter Grund, keine WARNUNG")

    vb = {f"/x/rc-park_daten/o/netz/q/{i}.jpg": dict(inlier=100 if i < 6 else 10) for i in range(10)}
    json.dump(dict(min_inlier=60, bilder=vb), open(os.path.join(D, "vorpruefung.json"), "w"))
    os.makedirs(os.path.join(D, "quarantaene"))
    json.dump(dict(bilder=[dict(name=f"b{i}", quelle="eigen") for i in range(20)], dubletten=[dict(weg=f"/x/rc-park_daten/o/netz/q/{i}.jpg", bleibt="/y") for i in range(4)]), open(os.path.join(D, "quarantaene", "sammlung.json"), "w"))
    json.dump(dict(n=20), open(os.path.join(D, "pipe", "fotosatz.json"), "w"))
    json.dump(dict(seiten=[dict(bilder=15), dict(bilder=3)], fremd=["f1", "f2"]), open(os.path.join(D, "pipe", "sfm", "seiten.json"), "w"))
    json.dump(dict(teile=[dict(teil=0, bilder=15, gerechnet=True, im_modell=10), dict(teil=1, bilder=3, gerechnet=False, grund="unter 30 Bildern")], vereint=[0]),
              open(os.path.join(D, "pipe", "sfm", "seiten_modelle.json"), "w"))
    os.makedirs(os.path.join(D, "pipe", "dicht", "sparse_dicht"))
    json.dump(dict(registriert=10, behalten=8, weg_zu_wenig_kern=2, weg_video_doppelt=0), open(os.path.join(D, "pipe", "dicht", "sparse_dicht", "dicht_bildwahl.json"), "w"))
    V = VB.bilanz(D, Z, B=B); S = {x["stufe"]: x for x in V["stufen"]}
    pruef(S["vorpruefen"]["rein"] == 10 and S["vorpruefen"]["raus"] == 6 and S["vorpruefen"]["ohne_grund"] == 0, "Vorpruefung: 4 unter der Inlier-Schwelle = benannt")
    pruef(S["sammeln"]["rein"] == 24 and S["sammeln"]["raus"] == 20 and S["sammeln"]["ohne_grund"] == 0, "Sammeln: Dubletten benannt (sammlung.json aus quarantaene/ gelesen)")
    pruef(S["sfm_seiten"]["ohne_grund"] == 0 and S["sfm_teile"]["verloren"][0]["grund"] == "unter 30 Bildern", "Seitenerkennung fremd + Teil unter 30 Bildern = benannt")
    pruef(S["sfm_registriert"]["ohne_grund"] == 5 and S["dicht_bildwahl"]["ohne_grund"] == 0, "Mapper 15 -> 10 ohne Grund, Bildwahl 10 -> 8 mit Grund 'zu wenig kern'")
    pruef(any(w.startswith("sfm_registriert") for w in V["warnungen"]), "-> WARNUNG sfm_registriert (33 %)")
    V = VB.bilanz(D, Z, B=B, umg=dict(RCPARK_VERLUST_MAX_SFM_REGISTRIERT="0.5"))
    pruef(not any(w.startswith("sfm_registriert") for w in V["warnungen"]), "Grenze je Stufe konfigurierbar (RCPARK_VERLUST_MAX_SFM_REGISTRIERT=0.5 -> keine WARNUNG)")
    V = VB.bilanz(D, Z, B=B, seit=time.time() + 60)
    pruef(all(x.get("stand", "").startswith("frueher") for x in V["stufen"] if x.get("quelle")), "Dateien vor dem Laufstart -> stand 'frueher'")

    L = os.path.join(T, "g.log")
    open(L, "w").write("=== fototor_kameras  [alt]\n  K-a: f 100 px, rms 1 px\n  K-b: UNPLAUSIBEL, nicht geschrieben: Standort 5000 m\n=== sammeln  [x]\n"
                       "=== fototor_kameras  [neu]\n  K-a: f 100 px, rms 1 px\n  K-c: nur 3 Netzpunkte (< 30) - Lage unbelegt, nicht geschrieben\n=== html  [y]\n")
    pruef(len(VB.log_abschnitt(L, "fototor_kameras")) == 2 and "K-c" in VB.log_abschnitt(L, "fototor_kameras")[1], "Log-Abschnitt: der LETZTE der Stufe")
    pruef(VB.log_abschnitt(L, "fototor_kameras", ab_zeile=7) == [], "Log-Abschnitt: nur ab der Startzeile des Laufs")
    V = VB.bilanz(D, Z, B=B, log=L); k = [x for x in V["stufen"] if x["stufe"] == "kameras"][0]
    pruef(k["rein"] == 2 and k["raus"] == 1 and k["verloren"][0]["grund"].startswith("nur N Netzpunkte"), "Kameras: Gruende je Kamera aus dem Log, Zahlen zusammengefasst")

    open(os.path.join(Z, "audit", "fassaden_kette.json"), "w").write("{kaputt")
    json.dump(dict(f00=dict(fenster=[{}, {}, {}])), open(os.path.join(Z, "audit", "fenster_auto_roh.json"), "w"))
    json.dump(dict(f00=dict(fenster=[{}, {}])), open(os.path.join(Z, "audit", "fenster_bau.json"), "w"))
    json.dump(dict(f00=[dict(urteil="VERWORFEN: etwas steht davor")]), open(os.path.join(Z, "audit", "fenster_tiefe_tor.json"), "w"))
    V = VB.bilanz(D, Z, B=B); f = [x for x in V["stufen"] if x["stufe"] == "fenster"][0]
    pruef(f["rein"] == 3 and f["raus"] == 2 and f["ohne_grund"] == 0, "Fenster: 3 erkannt, 1 vom Tiefen-Tor verworfen, 2 gebaut")
    pruef(not any(x["stufe"].startswith("fassaden") for x in V["stufen"]) and "VERLUSTBILANZ" in "\n".join(VB.tabelle(V)), "kaputte JSON -> keine Zeile, kein Absturz; Tabelle druckbar")

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesamtkette.py")).read()
pruef("VB.bilanz(" in src and "VB.drucken(" in src and "verlust_warnungen" in src, "gesamtkette.abschluss ruft die Verlustbilanz (Bericht 'verlustbilanz', lauf_ergebnis.verlust_warnungen)")
print("VERLUSTBILANZ-TEST:", "alle ok" if not F else f"{F} FEHLER"); sys.exit(1 if F else 0)
