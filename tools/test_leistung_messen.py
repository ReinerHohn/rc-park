#!/usr/bin/env python3
"""test_leistung_messen.py - Kurztest fuer tools/leistung_messen.py (22.11.2026): synthetische numpy-Schleife (~1 s, ~120 MB, 1-2 Threads),
Sweep mit Platzhalter, Auswertung 'kleinste Einstellung innerhalb 5 %', Engpass-Regeln an erfundenen Kennzahlen, rc != 0. Ziel < 15 s, < 500 MB.
  /media/oem/scan/venv-seg/bin/python -I tools/test_leistung_messen.py   (braucht numpy fuer die Last; das Werkzeug selbst nur Standardbibliothek)"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leistung_messen as L

F = 0
def ok(b, text):
    global F
    print(("    ok    " if b else "    FEHLER ") + text)
    if not b: F += 1

LAST = ("import numpy as np, os, sys, time, json\n"
        "json.dump({k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS')}, open(sys.argv[1], 'w'))\n"
        "a = np.ones(15_000_000)\n"   # 120 MB
        "t = time.time(); b = np.random.default_rng(0).random((200, 200))\n"
        "while time.time() - t < float(sys.argv[2]): b = (b @ b) / 200.0 + 0.001; a[:1000] += 1\n")

tmp = tempfile.mkdtemp(prefix="test_leistung_")
skript = os.path.join(tmp, "last.py"); open(skript, "w").write(LAST)

# 1. eine Messung
m = L.messen([sys.executable, "-I", skript, os.path.join(tmp, "env1.json"), "1.2"], os.path.join(tmp, "m1"), takt=0.3, env_extra={"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}, ruhe_s=0.3)
ok(m["rc"] == 0 and 1.1 < m["wall_s"] < 6, f"Messung laeuft, rc 0, Wallzeit {m['wall_s']} s")
ok((m.get("cpu_s") or 0) > 0.8, f"CPU-Zeit aus wait4 ({m.get('cpu_s')} s)")
ok((m.get("rss_baum_spitze_mb") or 0) > 90 and (m.get("max_rss_einzelprozess_mb") or 0) > 90, f"Spitzen-RAM erkannt (RSS-Summe {m.get('rss_baum_spitze_mb')} MB, Einzelprozess {m.get('max_rss_einzelprozess_mb')} MB, erwartet > 90)")
ok(len(m["proben"]) >= 2, f"Proben alle 0,3 s ({len(m['proben'])})")
ok(json.load(open(os.path.join(tmp, "env1.json")))["OMP_NUM_THREADS"] == "1", "Env-Variablen erreichen den Befehl")
ok(os.path.exists(os.path.join(tmp, "m1", "messung.json")) and "Engpassvermutung" in open(os.path.join(tmp, "m1", "bericht.md")).read(), "messung.json + bericht.md geschrieben")
ok(m.get("messaufwand_cpu_s", 9) < 1.0, f"Messaufwand klein ({m.get('messaufwand_cpu_s')} CPU-s)")
ok(any("CPU einfaedig" in u[0] or "FREMDLAST" in u[0] for u in m["engpass"]), "Engpass: einfaedige Last erkannt (oder Fremdlast gemeldet): " + "; ".join(u[0] for u in m["engpass"]))
ok("energie_j" in m or any("RAPL" in h for h in m["hinweise"]), "Energie gemessen oder RAPL-Fehlen gemeldet")

# 2. perf: entweder gemessen oder sauber uebersprungen
mp = L.messen([sys.executable, "-c", "pass"], os.path.join(tmp, "mp"), takt=0.3, perf=True, ruhe_s=0.0)
ok(mp["rc"] == 0 and (mp.get("perf", {}).get("ipc") is not None or "uebersprungen" in mp.get("perf", {})), f"perf gemessen oder uebersprungen: {str(mp.get('perf'))[:90]}")

# 3. rc != 0 wird gemeldet, Messung trotzdem geschrieben
mf = L.messen([sys.executable, "-c", "import sys; print('kaputt'); sys.exit(3)"], os.path.join(tmp, "mf"), takt=0.3, ruhe_s=0.0)
ok(mf["rc"] == 3 and "kaputt" in mf.get("log_ende", ""), f"rc 3 und Logende im Bericht (rc {mf['rc']})")

# 4. Sweep: Threads 1,2, Platzhalter {DAUER}
s = L.sweep([sys.executable, "-I", skript, os.path.join(tmp, "env_{THREADS}.json"), "{DAUER}"], os.path.join(tmp, "sw"), threads=[1, 2], params={"DAUER": ["0.6"]}, takt=0.3)
ok(len(s["laeufe"]) == 2 and all(l["rc"] == 0 for l in s["laeufe"]), "Sweep: 2 Laeufe rc 0")
ok(json.load(open(os.path.join(tmp, "env_2.json")))["OPENBLAS_NUM_THREADS"] == "2", "Sweep setzt OPENBLAS_NUM_THREADS und ersetzt {THREADS}")
ok(s["kleinste_innerhalb_5"] is not None and len(s["skalierung"]) == 2, "Sweep: Skalierung + kleinste Einstellung")
ok(os.path.exists(os.path.join(tmp, "sw", "sweep.json")) and "Skalierung" in open(os.path.join(tmp, "sw", "bericht.md")).read(), "sweep.json + bericht.md")
try: L.sweep(["x"], os.path.join(tmp, "sw2"), params={"FEHLT": ["1"]}); ok(False, "fehlender Platzhalter muss abbrechen")
except SystemExit: ok(True, "fehlender Platzhalter bricht ab")

# 5. Auswertung mit bekannten Zahlen: 8 Threads innerhalb 5 % der besten (28) -> 8
la = [dict(nr=i, einstellung=f"t{t}", threads=t, parameter={}, rc=0, wall_s=w, energie_j=e) for i, (t, w, e) in enumerate([(1, 100, 900), (4, 40, 700), (8, 30.5, 800), (28, 30.0, 2500)])]
r = L.auswerten(la)
ok(r["beste"]["threads"] == 28 and r["kleinste_innerhalb_5"]["threads"] == 8 and r["energie_min"]["threads"] == 4, f"kleinste innerhalb 5 % = 8 (beste 28, Energie-min 4): {r['kleinste_innerhalb_5']['threads']}")
ok(abs(r["skalierung"][-1]["beschleunigung"] - 100 / 30) < 1e-3, "Beschleunigung gegen kleinste Thread-Zahl")

# 6. Engpass-Regeln an erfundenen Kennzahlen
basis = dict(wall_s=100, ncpu=28, messaufwand_cpu_s=0.5)
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=1.0, system_cpu_kerne_mittel=1.1)); ok(any("einfaedig" in x[0] for x in u), "einfaedig erkannt")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=1.0, system_cpu_kerne_mittel=15.0)); ok(any("FREMDLAST" in x[0] for x in u), "Fremdlast erkannt (System 15 Kerne, Baum 1)")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=27.0, system_cpu_kerne_mittel=27.5, perf=dict(ipc=0.5, cache_miss_anteil=0.05))); ok(any("Spin" in x[0] for x in u), "viele Kerne + IPC 0,5 + wenig Misses -> Spin-Verdacht")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=27.0, system_cpu_kerne_mittel=27.5, perf=dict(ipc=0.5, cache_miss_anteil=0.5))); ok(any("Speicher" in x[0] for x in u), "IPC 0,5 + 50 % Misses -> speichergebunden")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=0.5, system_cpu_kerne_mittel=0.6, gpu=dict(util_mittel=90, util_max=100, w_mittel=120))); ok(any("GPU-gebunden" in x[0] for x in u), "GPU-gebunden erkannt")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=0.3, system_cpu_kerne_mittel=0.4, psi_anteil=dict(io=0.6), iowait_anteil=0.2)); ok(any("IO" in x[0] for x in u), "IO-gebunden erkannt")
u, _ = L.engpass(dict(basis, cpu_kerne_mittel=4, system_cpu_kerne_mittel=4.2, throttle_diff=dict(kern=12, package=0))); ok(any("Drosselung" in x[0] for x in u), "Throttle-Zuwachs gemeldet")

# 7. bericht-Unterbefehl schreibt Markdown neu
os.remove(os.path.join(tmp, "sw", "bericht.md")); import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): L.main(["bericht", os.path.join(tmp, "sw", "sweep.json")])
ok(os.path.exists(os.path.join(tmp, "sw", "bericht.md")), "bericht-Unterbefehl")

import shutil; shutil.rmtree(tmp, ignore_errors=True)
print(f"test_leistung_messen: {F} Fehler"); sys.exit(1 if F else 0)
