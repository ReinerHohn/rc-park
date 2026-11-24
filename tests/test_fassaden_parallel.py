#!/usr/bin/env python3
"""test_fassaden_parallel.py - fassaden_kette: Waende parallel ohne Ergebnisaenderung (24.11.2026, Nutzer: "Das dauert alles so extrem lang").
Kette 1122x: fassaden_kette 3689 s SERIELL (Buchung 11000 MiB RAM / 6000 MiB GPU: alter RAM-Plan zog 2 x 5300 MiB fuer Feinplaetze ab -> 1 Wand),
5 x tiefe_lokal 432-650 s = 2923 s (79 %), Rest ~770 s CPU-Teile der 8 Waende; dazu teilten tiefe_lokal und steine_aus_foto EINEN GPU-Zaehler.
Prueft ohne Rechenlast (Ersatzwerkzeuge im Temp-Ordner, echte Teilprozesse):
  1. ram_plan: Spitze gf*5300 + (n-gf)*2600 <= frei; 1122x-Buchung -> 2 Waende, 1 Feinplatz; knapper RAM -> seriell wie bisher.
  2. VRAM-Konto: Summe der gleichzeitigen Bedarfe nie > Buchung; steine_aus_foto laeuft NEBEN tiefe_lokal (der Gewinn); ohne Buchung nie zwei GPU-Laeufe.
  3. BITGLEICH: gleiche Ersatz-Waende seriell (FASSADEN_PARALLEL=1) und parallel -> sha1 aller Ausgabedateien, stdout und Wand-dicts gleich; parallel schneller.
"""
import os, sys, io, json, time, hashlib, tempfile, threading, contextlib
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
import fassaden_kette as FK
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


# 1. RAM-Plan
ok(FK.ram_plan(7, 2, 9500, True) == (2, 1), "1122x (11000 - 1500 MiB frei, 2 GPU-Plaetze): 2 Waende, 1 Feinplatz (alt: 1 Wand) - 5300 + 2600 <= 9500")
ok(FK.ram_plan(7, 2, 7000, True) == (1, 1), "7000 MiB frei: seriell wie bisher (5300 + 2600 > 7000)")
ok(FK.ram_plan(7, 2, 16000, True) == (5, 1), "16000 MiB: 5 Waende mit 1 Feinplatz (15700), n vor Feinplaetzen")
ok(FK.ram_plan(7, 2, 3000, True) == (1, 1), "zu wenig RAM: mindestens (1, 1)")
ok(FK.ram_plan(7, 2, 9500, False) == (3, 2), "ohne Feinrechnung: frei // 2600 (unveraendert)")
for n_, g_, fr in ((2, 1, 9500), (5, 1, 16000)):
    ok(g_ * FK.RAM_FEIN_MB + (n_ - g_) * FK.RAM_WAND_MB <= fr, f"Plan ({n_}, {g_}) haelt {fr} MiB ein")
ok(FK.parallel_plaetze(8, {"RCPARK_RAM_MB": "8000", "RCPARK_GPU_MB": "2500"}, fein=True)[0] == 1, "Buchung 8000 + Feinrechnung -> 1 Wand (1121p-OOM-Schutz bleibt)")
ok(FK.vram_konto_mb(2, {"RCPARK_GPU_MB": "6000"}) == 6000 and FK.vram_konto_mb(1, {}) == 2300 and FK.vram_konto_mb(3, {"RCPARK_GPU_MB": "6000", "FASSADEN_GPU_PARALLEL": "3"}) == 6900,
   "VRAM-Konto = Job-Buchung; ohne Buchung bzw. von Hand g ganze Plaetze a 2300 MiB")

# Ersatzwerkzeuge: echte Teilprozesse, Ausgabe deterministisch aus Eingaben (Saat = Wandname)
T = tempfile.mkdtemp(prefix="fk_par_")
WZ = {}
for nm, dauer in (("tiefe_lokal.py", 0.6), ("steine_aus_foto.py", 0.25), ("relief_einsatz.py", 0.3)):
    p_ = os.path.join(T, nm); WZ[nm] = p_
    open(p_, "w").write(f"""import sys, time, hashlib, os
aus = sys.argv[1]; saat = int(hashlib.sha1(sys.argv[2].encode()).hexdigest()[:8], 16)
open(os.path.join(os.path.dirname(aus), "lauf_" + os.path.basename(aus) + "_" + str(os.getpid())), "w").write(str(time.time()) + " " + str(time.time() + {dauer}))
time.sleep({dauer}); import random; r = random.Random(saat)
open(aus, "wb").write(bytes(r.randrange(256) for _ in range(4096))); print("{nm}", sys.argv[2], "fertig")
""")


def wand_ersatz(od):
    def _wand(w):                                                          # Ablauf wie fassaden_kette._wand: CPU-Teil, GPU-Tor (steine_aus_foto), Fein (tiefe_lokal), Foto-Steine
        print(f"WAND {w['name']}: start", flush=True)
        for wz_, suf in (("relief_einsatz.py", ""), ("steine_aus_foto.py", "_tor"), ("tiefe_lokal.py", "_fein"), ("steine_aus_foto.py", "_foto")):
            r = (FK._gpu_run if wz_ in FK.GPU_TEILE else FK.subprocess.run)([sys.executable, "-I", WZ[wz_], os.path.join(od, w["name"] + suf + ".npz"), w["name"] + suf], capture_output=True, text=True)
            print("   ", r.stdout.strip(), flush=True); w[suf or "roh"] = r.returncode
        w["sha"] = hashlib.sha1(open(os.path.join(od, w["name"] + "_fein.npz"), "rb").read()).hexdigest()[:12]
    return _wand


def lauf_modus(env):
    od = tempfile.mkdtemp(dir=T); W = [dict(name=f"w{i:02d}") for i in range(4)]
    alt = {k: os.environ.get(k) for k in ("FASSADEN_PARALLEL", "FASSADEN_GPU_PARALLEL", "RCPARK_GPU_MB", "RCPARK_RAM_MB")}
    for k in alt: os.environ.pop(k, None)
    os.environ.update(env); buf = io.StringIO(); t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf): FK._waende_parallel(W, wand_ersatz(od))
    finally:
        for k, v in alt.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
    dt = time.time() - t0
    h = {f: hashlib.sha1(open(os.path.join(od, f), "rb").read()).hexdigest() for f in sorted(os.listdir(od)) if f.endswith(".npz")}
    spannen = []
    for f in os.listdir(od):
        if f.startswith("lauf_"): a_, b_ = map(float, open(os.path.join(od, f)).read().split()); spannen.append((f.split(".npz")[0][5:], a_, b_))
    log = "\n".join(l for l in buf.getvalue().splitlines() if not l.startswith("Waende parallel"))
    return h, log, json.dumps(W, sort_keys=True), dt, spannen


def gleichzeitig(sp, pred):
    """hoechste Zahl gleichzeitig laufender Ersatz-Laeufe mit pred(name) und hoechste VRAM-Summe."""
    ev = sorted([(a, 1, n) for n, a, b in sp if pred(n)] + [(b, -1, n) for n, a, b in sp if pred(n)])
    k = m = 0; vr = vm = 0
    for t, d, n in ev:
        mb = FK.GPU_BEDARF_MB["tiefe_lokal.py" if n.endswith("_fein") else "steine_aus_foto.py"]
        k += d; vr += d * mb; m = max(m, k); vm = max(vm, vr)
    return m, vm


h1, log1, W1, t1, sp1 = lauf_modus({"FASSADEN_PARALLEL": "1"})
h2, log2, W2, t2, sp2 = lauf_modus({"FASSADEN_PARALLEL": "3", "FASSADEN_GPU_PARALLEL": "", "RCPARK_GPU_MB": "6000"})
h3, log3, W3, t3, sp3 = lauf_modus({"FASSADEN_PARALLEL": "3", "FASSADEN_GPU_PARALLEL": "1"})
ok(len(h1) == 16 and h1 == h2 == h3, f"BITGLEICH: {len(h1)} Ausgabedateien, sha1 seriell = parallel (Konto 6000) = parallel (1 Platz)")
ok(log1 == log2 == log3, "Log Wand fuer Wand in der Reihenfolge von W, gleich zum seriellen Lauf")
ok(W1 == W2 == W3, "Wand-dicts (-> fassaden_kette.json) gleich")
gpu = lambda n: n.endswith(("_fein", "_tor", "_foto"))
m2, v2 = gleichzeitig(sp2, gpu); f2, _ = gleichzeitig(sp2, lambda n: n.endswith("_fein"))
ok(v2 <= 6000, f"Konto 6000 MiB: VRAM-Summe gleichzeitig hoechstens {v2} MiB")
ok(f2 <= 2, f"Feinlaeufe gleichzeitig {f2} <= Feinplaetze")
neben = any(a < b2 and a2 < b for n, a, b in sp2 if n.endswith("_fein") for n2, a2, b2 in sp2 if n2.endswith(("_tor", "_foto")))
ok(neben, "steine_aus_foto laeuft NEBEN tiefe_lokal (frueher ein gemeinsamer Zaehler)")
m3, _ = gleichzeitig(sp3, gpu)
ok(m3 == 1, f"1 Platz ohne Buchung (Konto 2300): nie zwei GPU-Laeufe gleichzeitig (gemessen {m3})")
ok(t2 < 0.8 * t1, f"parallel schneller: {t1:.1f} s seriell -> {t2:.1f} s (Konto 6000), {t3:.1f} s (1 Platz)")
ok(FK._VRAM[0] is None or FK._VRAM[0].belegt == 0, "VRAM-Konto nach dem Lauf leer")
import shutil; shutil.rmtree(T, ignore_errors=True)
print(f"{n_ok} Tests bestanden")
