#!/usr/bin/env python3
"""Test laufzeit_bericht.py: Familien, Doppel-Fusion (Kettenlog + Unterlog), Wiederholung teurer Bauten, Vorlauf aus derselben Datei, Job-Log-Format."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laufzeit_bericht as LB

F = 0
def pruef(b, t):
    global F
    print(("    ok    " if b else "    FEHLER ") + t); F += (not b)

d = tempfile.mkdtemp(dir="/media/oem/rcdaten/tmp" if os.path.isdir("/media/oem/rcdaten/tmp") else None)
g = os.path.join(d, "gesamtkette.log")
vor = ["=== vorpruefen  [2026-11-24 07:00:00]", "=== sfm  [2026-11-24 07:01:00]", "=== bauen  [2026-11-24 07:03:00]", "=== ende  [2026-11-24 07:04:00]"]
jetzt = ["=== vorpruefen  [2026-11-24 12:00:00]", "=== sfm  [2026-11-24 12:01:00]", "=== neu_fusionieren  [2026-11-24 12:13:00]",
         "TEILFUSION 17052759 Punkte aus 6 Teilen (445 s) -> x", "=== bauen  [2026-11-24 12:21:00]", "=== bauen_mit_fassaden  [2026-11-24 12:25:00]",
         "=== bauen_mit_fenstern  [2026-11-24 12:30:00]", "=== fototor_eigen__IMG_1  [2026-11-24 12:31:00]", "=== fototor_eigen__IMG_2  [2026-11-24 12:32:00]",
         "=== ende  [2026-11-24 12:33:00]"]
open(g, "w").write("\n".join(vor + jetzt) + "\n")
u = os.path.join(d, "pipeline.log")
open(u, "w").write("TEILFUSION 1 Punkte aus 5 Teilen (279 s) -> alt\nGPU-Buchung kette-x-1122z: 6000 MiB\nTEILFUSION 2 Punkte aus 7 Teilen (470 s) -> neu\n")
r = LB.bericht(g, ab_zeile=len(vor), unterlog=u, job="kette-x-1122z")
fam = {f["familie"]: f for f in r["familien"]}
pruef(fam.get("bauen", {}).get("laeufe") == 3 and abs(fam["bauen"]["minuten"] - 10.0) < 0.01, f"bauen_mit_* zu einer Familie: {fam.get('bauen')}")
pruef(fam.get("fototor", {}).get("laeufe") == 2, "fototor_<foto> zu einer Familie")
pruef(any(h.startswith("DOPPELARBEIT Fusion: 2") for h in r["hinweise"]), f"Doppel-Fusion (Unterlog ab Job + Kettenlog), alte Fusion vor dem Job zaehlt nicht: {r['hinweise']}")
pruef(any(h.startswith("WIEDERHOLUNG bauen: 2") for h in r["hinweise"]), "2 teure Bauten (4 + 5 min) = Wiederholung, der 1-min-Bau zaehlt nicht")
pruef(any(h.startswith("GEWACHSEN sfm") for h in r["hinweise"]), "sfm 2 -> 12 min gegen Vorlauf aus derselben Datei = gewachsen")
pruef(not any("vorpruefen" in h for h in r["hinweise"]), "kurze Stufe ohne Hinweis")
j = os.path.join(d, "job.log")
open(j, "w").write("[12:00:00] sfm: python x\n    rc 0 (760 s) fertig\n[12:13:00] bauen: bash y\n    rc 0 (200 s) ok\n[12:20:00] bauen_mit_fotodach: bash y\n    rc 0 (300 s) ok\n")
r2 = LB.bericht(j)
pruef(abs(r2["summe_min"] - 21.0) < 0.01 and any(h.startswith("WIEDERHOLUNG bauen: 2") for h in r2["hinweise"]), f"Job-Log-Format (rc-Zeilen): {r2['summe_min']} min, {r2['hinweise']}")
pruef(LB.main([os.path.join(d, "fehlt.log")]) == 2, "fehlendes Log -> rc 2")
import shutil; shutil.rmtree(d, ignore_errors=True)
print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
