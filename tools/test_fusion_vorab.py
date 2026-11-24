#!/usr/bin/env python3
"""Test tools/fusion_vorab.py (24.11.2026, Laufzeit 1122z: dichte Wolke je Lauf ZWEIMAL fusioniert, 470 s + 445 s).
Ersatzwerkzeuge zaehlen die Fusionsaufrufe (keine echte Fusion, keine GPU):
  alt (ohne Plan)                 -> 2 Fusionen, Ergebnis = Bilder nach den Listen der Tore
  neu (Plan sicher, Listen gleich) -> 1 Fusion, gleiche Bilder wie alt
  Rueckfall A (Listen weichen ab)  -> 2 Fusionen + Logzeile RUECKFALL, Ergebnis = Listen der Tore
  Rueckfall B (Regel feuert spaet nicht) -> --vorab-zurueck: 2 Fusionen + Logzeile, Ergebnis = alle Bilder (wie alt ohne Neufusion)
  Regel noetig() = Ausdruck der Kette vor dem 24.11. (alle Wertekombinationen), sicher() nur wenn unabhaengig vom Lage-Urteil; plan() mit Ersatz-'lauf'.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_fusion_vorab.py (braucht numpy + scipy)."""
import os, sys, json, io, contextlib, itertools
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import pfade, fusion_vorab as FV, wolke_neu_fusionieren as WNF

ZAEHL = []                                                               # je Fusion: Bildliste der fusion.cfg in diesem Moment


def ply(ziel, n):
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("red", "u1"), ("green", "u1"), ("blue", "u1")]); V = np.zeros(n, dt); V["z"] = np.arange(n)
    with open(ziel, "wb") as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {n}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n".encode()); f.write(V.tobytes())


def ersatz_fusion(ziel, D, stufe="schnell"):
    b = WNF.zeilen(os.path.join(D, "stereo", "fusion.cfg")); ZAEHL.append(b); ply(ziel, 100 + len(b))


WNF.fusionieren = ersatz_fusion


def anlegen(wurzel, n=10, plan=None):
    od = os.path.join(wurzel, "modelle", "obj"); P = os.path.join(wurzel, "pipe"); D = os.path.join(P, "dicht"); L = os.path.join(P, "lage_frueh")
    for d in (os.path.join(od, "audit"), os.path.join(od, "messprotokoll"), os.path.join(od, "sfm"), os.path.join(D, "stereo"), os.path.join(L, "audit"), os.path.join(P, "sfm", "sparse", "0")): os.makedirs(d, exist_ok=True)
    json.dump({"name": "obj"}, open(os.path.join(od, "objekt.json"), "w"))
    json.dump(dict(transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-obj.json"), "w"))
    for q in ("images.bin", "points3D.bin"): open(os.path.join(P, "sfm", "sparse", "0", q), "wb").write(b"x" * 16)
    open(os.path.join(D, "stereo", "fusion.cfg"), "w").write("\n".join(f"b{i}.jpg" for i in range(n)) + "\n")
    if plan is not None: json.dump(dict(sicher=plan, grund="Test", stempel=FV.stempel(P), audit=L), open(os.path.join(L, FV.PLAN), "w"))
    return od, P, D, L


def listen(od, kg, insel, gruppen=()):
    json.dump(dict(ausschliessen=list(kg)), open(os.path.join(od, "audit", "kamera_plausibel.json"), "w"))
    json.dump(dict(ausschliessen=list(insel)), open(os.path.join(od, "audit", "kette_insel.json"), "w"))
    json.dump(dict(ausschliessen=list(gruppen)), open(os.path.join(od, "audit", "wolke_gruppen.json"), "w"))


def erste_fusion(D, P, vorab):
    if vorab: FV.anwenden(D, P)
    ersatz_fusion(os.path.join(D, "fused.ply"), D)


def neu_fusionieren(od, P, *extra):
    alt = sys.argv; sys.argv = ["wolke_neu_fusionieren.py", os.path.join(od, "objekt.json"), P, "--stufe", "schnell", *extra]; buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): rc = WNF.main()
    finally: sys.argv = alt
    return rc, buf.getvalue()


def fall(name, vorab, vorher, nachher, feuert=True):
    """vorher = Listen der Vorstufe (lage_frueh/audit), nachher = Listen der Tore nach der dichten Wolke (Objekt-audit)."""
    w = pfade.temp_ordner("test_fusion_vorab_"); od, P, D, L = anlegen(w, plan=True if vorab else None); ZAEHL.clear()
    listen(L, *vorher); listen(od, *nachher)
    with contextlib.redirect_stdout(io.StringIO()) as b1: erste_fusion(D, P, vorab)
    log = b1.getvalue(); rc = None
    if feuert: rc, out = neu_fusionieren(od, P); log += out
    elif FV.offen(P): rc, out = neu_fusionieren(od, P, "--vorab-zurueck"); log += out
    return dict(n=len(ZAEHL), bilder=ZAEHL[-1], rc=rc, log=log, marke=os.path.exists(os.path.join(D, "stereo", WNF.VORAB)), P=P)


def main():
    fehler = []
    def pruef(ok, text):
        print(("ok    " if ok else "FEHLER") + " " + text)
        if not ok: fehler.append(text)
    A = (["b2"], ["b5"], [])                                              # Listen: Kamera unter Gelaende b2, Insel-Kette b5
    alt = fall("alt", False, A, A); neu = fall("neu", True, A, A)
    soll = [f"b{i}.jpg" for i in range(10) if i not in (2, 5)]
    pruef(alt["n"] == 2 and alt["bilder"] == soll, f"alt: 2 Fusionen, Ergebnis ohne b2/b5 (n {alt['n']}, {len(alt['bilder'])} Bilder)")
    pruef(neu["n"] == 1 and neu["rc"] == 2 and neu["bilder"] == alt["bilder"], f"neu: 1 Fusion, rc 2, gleiche Bilder wie alt (n {neu['n']}, rc {neu['rc']})")
    pruef("BESTAETIGT" in neu["log"] and not neu["marke"], "neu: Logzeile 'BESTAETIGT', Marke danach entfernt")
    pruef(not FV.offen(neu["P"]), "neu: nach der Nachpruefung keine offene Marke")
    ra = fall("rueckfall_a", True, (["b2", "b7"], ["b5"], []), A)
    pruef(ra["n"] == 2 and ra["bilder"] == soll and "RUECKFALL" in ra["log"], f"Rueckfall A (Vorhersage nahm b7 zu viel): 2 Fusionen, Ergebnis = Listen der Tore, Logzeile (n {ra['n']})")
    rb = fall("rueckfall_b", True, A, A, feuert=False)
    pruef(rb["n"] == 2 and rb["bilder"] == [f"b{i}.jpg" for i in range(10)] and "RUECKFALL" in rb["log"] and rb["rc"] == 0, f"Rueckfall B (Regel feuert spaet nicht): --vorab-zurueck, alle 10 Bilder wie alt ohne Neufusion (n {rb['n']}, rc {rb['rc']})")
    al = fall("alt_ohne", False, A, A, feuert=False)
    pruef(al["n"] == 1 and len(al["bilder"]) == 10, "alt ohne Neufusion: 1 Fusion mit allen Bildern (Referenz fuer Rueckfall B)")
    # Plan 'nicht sicher' -> keine Kuerzung
    w = pfade.temp_ordner("test_fusion_vorab_"); od, P, D, L = anlegen(w, plan=False); listen(L, *A); ZAEHL.clear()
    with contextlib.redirect_stdout(io.StringIO()) as b_: erste_fusion(D, P, True)
    pruef(len(ZAEHL[-1]) == 10 and "nicht angewandt" in b_.getvalue(), "Plan 'nicht sicher': erste Fusion mit allen Bildern + Logzeile")
    # anderes SfM-Netz (Stempel) -> keine Kuerzung
    w = pfade.temp_ordner("test_fusion_vorab_"); od, P, D, L = anlegen(w, plan=True); listen(L, *A); open(os.path.join(P, "sfm", "sparse", "0", "images.bin"), "wb").write(b"y" * 99); ZAEHL.clear()
    with contextlib.redirect_stdout(io.StringIO()) as b_: erste_fusion(D, P, True)
    pruef(len(ZAEHL[-1]) == 10 and "anderen SfM-Netz" in b_.getvalue(), "Plan eines anderen SfM-Netzes: nicht angewandt")
    # zweiter anwenden-Aufruf (Wiederholung nach Speichermangel) rechnet von der alten fusion.cfg aus und behaelt die Marke
    w = pfade.temp_ordner("test_fusion_vorab_"); od, P, D, L = anlegen(w, plan=True); listen(L, *A)
    with contextlib.redirect_stdout(io.StringIO()): FV.anwenden(D, P); m2 = FV.anwenden(D, P)
    pruef(m2 is not None and len(m2["aktiv_vorher"]) == 10 and len(m2["bleibt"]) == 8, "Wiederholung: Marke mit fusion.cfg von vorher (10 -> 8)")
    # Regel: noetig() gleich dem alten Ausdruck, sicher() nur bei Unabhaengigkeit vom Lage-Urteil
    altregel = lambda erg, b, ga: ((not b(erg) or erg.get("insel") == 3) and (erg.get("kamera_gelaende") == 3 or erg.get("insel") == 3) and erg.get("gps") in (0, None)) or (erg.get("gruppen") == 3 and ga())
    gleich = sicher_ok = True
    for ins, kg, gps, gr, best, ga in itertools.product((0, 3, None), (0, 3, None), (0, 2, 3, None), (0, 3, None), (True, False), (True, False)):
        e = dict(insel=ins, kamera_gelaende=kg, gps=gps, gruppen=gr)
        if bool(altregel(e, lambda _: best, lambda: ga)) != FV.noetig(e, lambda _: best, lambda: ga): gleich = False
        if FV.sicher(e, lambda: ga) and not (FV.noetig(e, lambda _: True, lambda: ga) and FV.noetig(e, lambda _: False, lambda: ga)): sicher_ok = False
    pruef(gleich, "noetig() = Ausloese-Regel der Kette vor dem 24.11. (alle Kombinationen)")
    pruef(sicher_ok and FV.sicher(dict(insel=3, gps=0), lambda: False) and not FV.sicher(dict(kamera_gelaende=3, insel=0, gps=0), lambda: False), "sicher(): Insel-Kette + GPS ok -> sicher; nur Kameras unter Gelaende -> haengt am Lage-Urteil, nicht sicher")
    # plan() mit Ersatz-'lauf' (schreibt die Listen wie die Werkzeuge)
    w = pfade.temp_ordner("test_fusion_vorab_"); od, P, D, L = anlegen(w); os.makedirs(os.path.join(L, "messprotokoll"), exist_ok=True)
    json.dump({}, open(os.path.join(L, "objekt.json"), "w")); json.dump({}, open(os.path.join(L, "messprotokoll", "SFM-AUSRICHTUNG-obj.json"), "w"))
    json.dump(dict(laeufe=[dict(loesung=0, tore=dict(gps=0))]), open(os.path.join(L, "lage_frueh.json"), "w"))
    rcs = dict(vorab_insel=3, vorab_kamera_gelaende=3, vorab_gruppen=0); datei = dict(vorab_insel="kette_insel.json", vorab_kamera_gelaende="kamera_plausibel.json", vorab_gruppen="wolke_gruppen.json")
    def lauf(B, name, cmd, log, ok=(0,), **k):
        json.dump(dict(ausschliessen=["b5"] if name == "vorab_insel" else []), open(os.path.join(L, "audit", datei[name]), "w")); return rcs[name], ""
    with contextlib.redirect_stdout(io.StringIO()): R = FV.plan(P, "obj", lauf, {}, None)
    pruef(R["sicher"] and R["tore"]["insel"] == 3, f"plan(): Insel-Kette + GPS 0 -> sicher ({R['grund'][:60]})")
    json.dump(dict(laeufe=[dict(loesung=0, tore=dict(gps=0)), dict(loesung=1, tore=dict(gps=0))]), open(os.path.join(L, "lage_frueh.json"), "w"))
    with contextlib.redirect_stdout(io.StringIO()): R = FV.plan(P, "obj", lauf, {}, None)
    pruef(not R["sicher"] and "Loesung 0" in R["grund"], "plan(): Vorstufe endete auf Loesung 1, keine .loesung0-Datei -> nicht sicher")
    open(os.path.join(L, "messprotokoll", "SFM-AUSRICHTUNG-obj.loesung0.json"), "w").write("{}")
    with contextlib.redirect_stdout(io.StringIO()): R = FV.plan(P, "obj", lauf, {}, None)
    pruef(R["sicher"], "plan(): mit gesicherter Loesung 0 (lage_frueh .loesung0.json) -> sicher")
    os.environ["RCPARK_FUSION_VORAB"] = "0"
    with contextlib.redirect_stdout(io.StringIO()): R = FV.plan(P, "obj", lauf, {}, None)
    del os.environ["RCPARK_FUSION_VORAB"]
    pruef(not R["sicher"] and "abgeschaltet" in R["grund"], "RCPARK_FUSION_VORAB=0 -> kein Vorab (alte Doppelfusion)")
    print(f"{len(fehler)} Fehler"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
