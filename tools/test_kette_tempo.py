#!/usr/bin/env python3
"""test_kette_tempo.py - Tempo-Umbau der Kette (21.11.2026) ohne Rechenlast pruefen:
  1. fassaden_kette._waende_parallel: Ausgabe in Wandreihenfolge (wie seriell), GPU-Teil (_gpu_run) nie mehr als die GPU-Plaetze gleichzeitig, Absturz einer Wand kommt an,
     FASSADEN_PARALLEL=1 = serieller Ablauf im Hauptthread; parallel_plaetze aus RAM/Kernen/Buchung.
  2. gesamtkette.bauen/abnahme_nachholen: Zwischenbau mit RCPARK_NUR_BAUEN=1 nur waehrend der Stufe, Abnahme genau einmal auf dem Endstand, RCPARK_ZWISCHENABNAHME=1 = alter Ablauf.
  3. bauen_abnehmen.sh: der Schalter RCPARK_NUR_BAUEN steht NACH dem Generator und VOR dem Pruefstand, endet mit einer ERGEBNIS-Zeile (die Kette prueft sie).
"""
import os, sys, io, time, threading, contextlib
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import fassaden_kette as FK
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


# 1a parallel_plaetze
ok(FK.parallel_plaetze(8, {"FASSADEN_PARALLEL": "1"}) == (1, 1), "FASSADEN_PARALLEL=1 -> seriell, 1 GPU-Platz")
ok(FK.parallel_plaetze(3, {"FASSADEN_PARALLEL": "6"})[0] == 3, "nie mehr Threads als Waende")
ok(FK.parallel_plaetze(8, {"FASSADEN_PARALLEL": "4", "RCPARK_GPU_MB": "2500"})[1] == 1, "Buchung 2500 MiB -> 1 PatchMatch gleichzeitig")
ok(FK.parallel_plaetze(8, {"FASSADEN_PARALLEL": "4", "RCPARK_GPU_MB": "6000"})[1] == 2, "Buchung 6000 MiB -> 2 gleichzeitig (hoechstens 2)")
ok(FK.parallel_plaetze(8, {"FASSADEN_PARALLEL": "4", "FASSADEN_GPU_PARALLEL": "3"})[1] == 3, "FASSADEN_GPU_PARALLEL setzt die Plaetze von Hand")
ok(FK.parallel_plaetze(8, {"RCPARK_RAM_MB": "8000", "RCPARK_GPU_MB": "2500"}, fein=True)[0] == 1, "Buchung 8000 + Feinrechnung (5,3 GB) -> nur 1 Wand (1121p: OOM, Signal 6)")
# 23.11.2026: freier RAM aus /proc/meminfo haengt von der Last ab (Schnelltest neben Kettenlauf -> 1 statt 2) -> fest 16 GB frei vorspielen
import io as _io
FK.open = lambda pf, *a, **k: _io.StringIO("MemAvailable:   16000000 kB\n") if pf == "/proc/meminfo" else open(pf, *a, **k)
ok(FK.parallel_plaetze(8, {"RCPARK_RAM_MB": "8000", "RCPARK_GPU_MB": "2500"}, fein=False)[0] == min(2, max(1, (os.cpu_count() or 4) // 4)), "Buchung 8000 ohne Fein -> 2 Waende (RAM-Last vorgespielt)")
del FK.open

# 1b Reihenfolge + GPU-Grenze
W = [dict(name=f"w{i:02d}", dauer=0.05 * (5 - i)) for i in range(5)]; sperre = threading.Lock()
def wand(w):
    print(f"WAND {w['name']} start", flush=True); time.sleep(w["dauer"])
    FK._gpu_run(["sleep", "0.05"])
    print(f"    {w['name']} fertig"); w["erg"] = w["name"].upper()
for modus in ("1", "4"):
    os.environ.update(FASSADEN_PARALLEL=modus, FASSADEN_GPU_PARALLEL="1"); buf = io.StringIO(); t0 = time.time()
    with contextlib.redirect_stdout(buf): FK._waende_parallel(W, wand)
    z = [l for l in buf.getvalue().splitlines() if l.startswith("WAND") or "fertig" in l]
    ok(z == sum(([f"WAND {w['name']} start", f"    {w['name']} fertig"] for w in W), []), f"FASSADEN_PARALLEL={modus}: Ausgabe Wand fuer Wand in der Reihenfolge von W")
    ok(all(w.get("erg") == w["name"].upper() for w in W), f"FASSADEN_PARALLEL={modus}: jede Wand traegt ihr Ergebnis in ihr dict ein")

# GPU-Grenze direkt: 4 Threads, 1 Platz -> nie 2 gleichzeitig in _gpu_run
im = [0]; mx = [0]; echt_run = FK.subprocess.run
def zaehl_run(cmd, **k):
    with sperre: im[0] += 1; mx[0] = max(mx[0], im[0])
    time.sleep(0.05)
    with sperre: im[0] -= 1
FK.subprocess.run = zaehl_run
try:
    for g in (1, 2):
        os.environ.update(FASSADEN_PARALLEL="4", FASSADEN_GPU_PARALLEL=str(g)); mx[0] = 0
        with contextlib.redirect_stdout(io.StringIO()): FK._waende_parallel([dict(name=f"g{i}") for i in range(6)], lambda w: FK._gpu_run(["x"]))
        ok(mx[0] == g, f"GPU-Plaetze {g}: hoechstens {g} GPU-Laeufe gleichzeitig (gemessen {mx[0]})")
finally: FK.subprocess.run = echt_run

# Absturz einer Wand
def kaputt(w):
    print("vor dem Absturz", w["name"])
    if w["name"] == "w02": raise ValueError("Testabsturz")
os.environ.update(FASSADEN_PARALLEL="3"); buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf): FK._waende_parallel(W, kaputt)
    ok(False, "Absturz muss ankommen")
except ValueError: ok("vor dem Absturz w02" in buf.getvalue() and "Testabsturz" in buf.getvalue(), "Absturz einer Wand kommt mit ihrer Ausgabe und dem Traceback an")
ok(sys.stdout is not None and not isinstance(sys.stdout, FK._Weiche), "stdout nach dem Lauf zurueckgesetzt")

# 2 gesamtkette.bauen / abnahme_nachholen
import gesamtkette as GK
aufrufe = []
def lauf_ersatz(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
    aufrufe.append((name, list(cmd), os.environ.get("RCPARK_NUR_BAUEN"))); return 0, "ERGEBNIS: x"
GK.lauf = lauf_ersatz; os.environ.pop("RCPARK_ZWISCHENABNAHME", None); os.environ.pop("RCPARK_NUR_BAUEN", None)
GK.bauen({}, "bauen_mit_fassaden", "obj", "/dev/null"); GK.bauen({}, "bauen_mit_bauplan", "obj", "/dev/null"); GK.abnahme_nachholen({}, "obj", "/dev/null"); GK.abnahme_nachholen({}, "obj", "/dev/null")
ok([a[2] for a in aufrufe[:2]] == ["1", "1"] and os.environ.get("RCPARK_NUR_BAUEN") is None, "Zwischenbauten mit RCPARK_NUR_BAUEN=1, danach wieder ungesetzt")
ok(len(aufrufe) == 3 and aufrufe[2][1][-1] == "--nur-pruefen" and aufrufe[2][0] == "abnahme_nach_bauen_mit_bauplan" and aufrufe[2][2] is None, "volle Abnahme genau einmal auf dem Endstand (ohne NUR_BAUEN)")
aufrufe.clear(); os.environ["RCPARK_ZWISCHENABNAHME"] = "1"; GK.bauen({}, "bauen_mit_fenstern", "obj", "/dev/null"); GK.abnahme_nachholen({}, "obj", "/dev/null"); os.environ.pop("RCPARK_ZWISCHENABNAHME")
ok(len(aufrufe) == 1 and aufrufe[0][2] is None, "RCPARK_ZWISCHENABNAHME=1: Abnahme in jedem Bau, nichts nachzuholen")

# 3 bauen_abnehmen.sh
s = open(os.path.join(HIER, "bauen_abnehmen.sh")).read(); i_gen = s.index('eval "$GEN"'); i_nur = s.index('RCPARK_NUR_BAUEN:-0'); i_pr = s.index("$PY -W ignore -I tools/pruefstand.py")
ok(i_gen < i_nur < i_pr and "ERGEBNIS: nur gebaut" in s[i_nur:i_pr], "bauen_abnehmen.sh: NUR_BAUEN nach dem Generator, vor dem Pruefstand, mit ERGEBNIS-Zeile")
# 4 kantenstufe.modellkanten vektorisiert = bitgleich zur alten Schleife (offene + geknickte Kanten, Laengen ueber/unter dem Schritt)
import numpy as np, trimesh
from kantenstufe import modellkanten
def alt(m, winkel=30.0, schritt=0.05):
    E = m.face_adjacency_edges[m.face_adjacency_angles > np.radians(winkel)]
    rand = trimesh.grouping.group_rows(m.edges_sorted, require_count=1); E = np.vstack([E, m.edges_sorted[rand]]) if len(rand) else E
    P = []
    for a, b in E:
        A, B = m.vertices[a], m.vertices[b]; L = np.linalg.norm(B - A); k = max(2, int(L / schritt) + 1); P.append(A + (B - A) * np.linspace(0, 1, k)[:, None])
    return np.vstack(P) if P else np.zeros((0, 3))
rng = np.random.default_rng(1); kasten = trimesh.creation.box((3.1, 0.7, 2.3)); kugel = trimesh.creation.icosphere(2, 1.3); kugel.vertices += rng.normal(0, 0.05, kugel.vertices.shape)
offen = trimesh.Trimesh(kasten.vertices, kasten.faces[:-3], process=False)
for nm, m in (("Kasten", kasten), ("verrauschte Kugel", kugel), ("offener Kasten", offen)):
    a_, b_ = alt(m), modellkanten(m); ok(a_.shape == b_.shape and np.array_equal(a_, b_), f"modellkanten {nm}: {len(a_)} Punkte bitgleich zur Schleife")
ok(modellkanten(trimesh.creation.icosphere(1, 1.0), winkel=179.0).shape == (0, 3), "modellkanten ohne Kanten -> leeres Feld (0, 3)")
print(f"{n_ok} Tests bestanden")
