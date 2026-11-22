#!/usr/bin/env python3
"""test_temp_ordner.py - Temp nicht auf Root, Tests raeumen selbst auf (tools/pfade.temp_wurzel/temp_ordner, 22.11.2026).
Anlass: /tmp/test_vordach_* (je 23 MB) und 180 weitere Testreste blieben nach jedem Schnelltest liegen, Root (48 GB) lief zweimal voll.
Prueft: (1) Reihenfolge TMPDIR -> /media/oem/rcdaten/tmp -> /media/oem/scan/rc-park_tmp -> System-Temp; (2) temp_ordner ist nach Prozessende weg,
auch wenn der Prozess mit assert/Ausnahme endet; (3) RCPARK_TEST_BEHALTEN=1 laesst ihn stehen; (4) WAECHTER: kein tools/test_*.py ruft
tempfile.mkdtemp ohne dir= (geht sonst nach /tmp und bleibt bei einem Fehlschlag liegen) - Ausnahmen nur mit Ordner auf der Datenplatte."""
import os, sys, re, glob, subprocess, shutil
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import pfade
F = 0
def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text); F += 0 if ok else 1


basis = pfade.temp_wurzel()
pruef(not basis.startswith("/tmp") or not any(os.path.isdir(k) for k in pfade.TEMP_KANDIDATEN) or os.environ.get("TMPDIR", "").startswith("/tmp"),
      f"Temp-Wurzel {basis} (nicht /tmp, solange eine Datenplatte da ist)")
eigen = os.path.join(basis, f"test_temp_ordner_{os.getpid()}"); os.makedirs(eigen)
try:
    alt = os.environ.get("TMPDIR"); os.environ["TMPDIR"] = eigen
    pruef(pfade.temp_wurzel() == eigen, "gesetztes TMPDIR gewinnt")
    os.environ["TMPDIR"] = os.path.join(eigen, "fehlt")
    pruef(pfade.temp_wurzel() != os.environ["TMPDIR"], "TMPDIR auf fehlenden Ordner -> naechster Kandidat")
    if alt is None: os.environ.pop("TMPDIR")
    else: os.environ["TMPDIR"] = alt
    kind = ("import sys; sys.path.insert(0, %r); import pfade, os; d = pfade.temp_ordner('test_kind_'); open(os.path.join(d, 'x'), 'w').write('1'); print(d, flush=True)\n" % HIER)
    env = dict(os.environ, TMPDIR=eigen); env.pop("RCPARK_TEST_BEHALTEN", None)
    r = subprocess.run([sys.executable, "-I", "-c", kind], capture_output=True, text=True, env=env); d = r.stdout.strip()
    pruef(d.startswith(eigen) and not os.path.exists(d), "Ordner nach normalem Ende entfernt")
    r = subprocess.run([sys.executable, "-I", "-c", kind + "assert False, 'Test rot'\n"], capture_output=True, text=True, env=env); d = r.stdout.strip()
    pruef(r.returncode != 0 and d and not os.path.exists(d), "Ordner auch nach assert-Fehlschlag entfernt")
    r = subprocess.run([sys.executable, "-I", "-c", kind], capture_output=True, text=True, env=dict(env, RCPARK_TEST_BEHALTEN="1")); d = r.stdout.strip()
    pruef(os.path.isdir(d) and "bleibt stehen" in r.stderr, "RCPARK_TEST_BEHALTEN=1 laesst ihn zum Ansehen stehen")
finally: shutil.rmtree(eigen, ignore_errors=True)

boese = []
for f in sorted(glob.glob(os.path.join(HIER, "test_*.py"))):
    for i, z in enumerate(open(f, errors="replace"), 1):
        if z.lstrip().startswith("#"): continue
        for m in re.finditer(r"tempfile\.mkdtemp\(([^)]*)\)", z):
            if "dir=" not in m.group(1) or "TMPDIR" in m.group(1): boese.append(f"{os.path.basename(f)}:{i}")
pruef(not boese, "kein Test ruft tempfile.mkdtemp ohne Datenplatten-Ordner (statt pfade.temp_ordner)" + (": " + ", ".join(boese[:8]) if boese else ""))
print("TEMP-TEST:", "alle ok" if not F else f"{F} FEHLER"); sys.exit(1 if F else 0)
