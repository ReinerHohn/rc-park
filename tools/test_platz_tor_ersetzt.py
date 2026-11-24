#!/usr/bin/env python3
"""Test des Platztors der Kette (gesamtkette.platz_tor_rc, 24.11.2026): Tests ersetzen es per RCPARK_PLATZ_TOR=test_ersetzt, damit sie nicht am echten Plattenplatz haengen.
Dieser Test prueft das Tor SELBST (ohne Ersatz): (1) platz_pruefen rc 3 -> Stufe startet nicht, SystemExit(3), Schritt 'PLATZ ZU KNAPP'; (2) mit Ersatz -> Stufe laeuft;
(3) gesamtkette.main() entfernt den Ersatz, bevor ein Kettenlauf beginnt. Attrappe: platz_pruefen.py in einem Kleinstbaum (G.ROOT umgebogen), kein Blick auf echte Platten."""
import os, sys, tempfile
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
os.environ.pop("RCPARK_PLATZ_TOR", None)
import gesamtkette as G

F = 0


def pruef(name, ok, info=""):
    global F
    print(("    ok " if ok else "    FEHLER ") + name + (f" ({info})" if info and not ok else "")); F += 0 if ok else 1


with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "tools")); open(os.path.join(d, "tools", "platz_pruefen.py"), "w").write("import sys; sys.exit(3)\n")
    G.ROOT = d; G._ABSCHLUSS[0] = None; m = os.path.join(d, "lief.txt"); B = dict(schritte=[], _pfad=os.path.join(d, "b.json")); L = os.path.join(d, "l.log")
    pruef("ohne Ersatz: platz_pruefen rc 3 wird gelesen", G.platz_tor_rc() == 3)
    try: G.lauf(B, "stufe", ["bash", "-c", f"touch {m}"], L); halt = None
    except SystemExit as e: halt = e.code
    pruef("ohne Ersatz: Stufe haelt mit rc 3 an", halt == 3 and not os.path.exists(m), f"halt {halt}")
    pruef("ohne Ersatz: Schritt nennt 'PLATZ ZU KNAPP'", bool(B["schritte"]) and "PLATZ ZU KNAPP" in B["schritte"][-1].get("fehler", ""), B["schritte"])
    os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"; B["schritte"] = []
    rc, _ = G.lauf(B, "stufe", ["bash", "-c", f"touch {m}"], L)
    pruef("mit Ersatz: Stufe laeuft trotz vollem 'Platz'", rc == 0 and os.path.exists(m))
    os.environ["RCPARK_PLATZ_TOR"] = "anders"; pruef("nur der Wert 'test_ersetzt' ersetzt", G.platz_tor_rc() == 3)
    os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"; sys.argv = ["gesamtkette.py"]
    try: G.main()
    except SystemExit: pass
    pruef("main() entfernt den Ersatz vor dem Kettenlauf", "RCPARK_PLATZ_TOR" not in os.environ)
print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
