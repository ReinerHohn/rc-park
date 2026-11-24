#!/usr/bin/env python3
"""Test tools/kamera_gelaende.py (24.11.2026, dauernd rot): Urteil ueber die Bilder der FUSION.
  1. ohne --fusion: Gruppe unter Gelaende -> rc 3 (alter Stand);
  2. mit Fusion, die eine tiefe Kamera noch enthaelt -> rc 3 (Neufusionieren noetig, Ausloeser unveraendert);
  3. nach dem Neufusionieren (keine tiefe Kamera in der Fusion) -> rc 0, Ausschlussliste weiter vollstaendig;
  4. Gruppe nie in der dichten Wolke (1122z: 25 von 28) + einzelne tiefe Kamera in der Fusion, aber keine schlechte Gruppe -> rc 0;
  5. Fusion-Datei fehlt -> alte Zaehlung (rc 3)."""
import os, sys, json, tempfile, subprocess
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import kamera_gelaende as KG

F = 0


def pruef(name, ok, info=""):
    global F
    print(("    ok " if ok else "    FEHLER ") + name + (f" ({info})" if info and not ok else ""))
    F += 0 if ok else 1


def lauf(d, K, fusion_zeilen=None, fusion_pfad=True):
    json.dump(dict(kameras=K), open(os.path.join(d, "aus.json"), "w")); open(os.path.join(d, "objekt.json"), "w").write("{}")
    cmd = [sys.executable, "-I", os.path.join(T, "kamera_gelaende.py"), os.path.join(d, "objekt.json"), os.path.join(d, "aus.json")]
    if fusion_pfad:
        fp = os.path.join(d, "fusion.cfg")
        if fusion_zeilen is not None: open(fp, "w").write("\n".join(fusion_zeilen) + "\n")
        elif os.path.exists(fp): os.remove(fp)
        cmd += ["--fusion", fp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, json.load(open(os.path.join(d, "audit", "kamera_plausibel.json")))


K = {f"commons__{i:03d}": dict(standort=[0, 0, -30.0 - i]) for i in range(5)}          # Gruppe: 5 Commons-Fotos tief
K.update({f"eigen__IMG_{i}": dict(standort=[0, 0, 1.6]) for i in range(20)})
K["eigen__IMG_tief"] = dict(standort=[0, 0, -1.6])
gut = [f"eigen__IMG_{i}.jpg" for i in range(20)]
with tempfile.TemporaryDirectory() as d:
    rc, out, j = lauf(d, K, fusion_pfad=False); pruef("1 ohne --fusion: Gruppe -> rc 3", rc == 3, out)
    rc, out, j = lauf(d, K, gut + ["commons__002.jpg"]); pruef("2 tiefe Kamera noch in der Fusion -> rc 3", rc == 3 and j["in_wolke"] == ["commons__002"], out)
    rc, out, j = lauf(d, K, gut); pruef("3 nach dem Neufusionieren -> rc 0", rc == 0 and j["in_wolke"] == [], out)
    pruef("3 Ausschlussliste vollstaendig (6 Kameras)", len(j["ausschliessen"]) == 6, j["ausschliessen"])
    pruef("3 Meldung 'BESTANDEN fuer die dichte Wolke'", "BESTANDEN fuer die dichte Wolke" in out, out)
    K4 = {k: v for k, v in K.items() if not k.startswith("commons__00") or k in ("commons__000", "commons__001", "commons__002")}   # nur 3 Commons tief -> keine Gruppe
    rc, out, j = lauf(d, K4, gut + ["eigen__IMG_tief.jpg"]); pruef("4 keine Gruppe, Einzelne in der Fusion -> rc 0", rc == 0, out)
    rc, out, j = lauf(d, K, None); pruef("5 Fusion-Datei fehlt -> alte Zaehlung rc 3", rc == 3 and "fehlt" in out, out)
    pruef("stamm entfernt Endung und Pfad", KG.stamm("/x/y/a__b.JPG") == "a__b" and KG.stamm("a.b__c") == "a.b__c")
print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
