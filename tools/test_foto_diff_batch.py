#!/usr/bin/env python3
"""Test foto_diff_batch.py (Register BS8): Ergebnisgleichheit zum Original-foto_diff (je Foto eigener Prozess).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_foto_diff_batch.py [--objekt ...] [--stl ...] [--maske-dir ...] [--fotos 000,004,073,114] [--raster]
Punktmodus: komplettes Ergebnis-JSON muss GLEICH sein (alle Felder). Raster (--raster, braucht freie GPU, VRAM-Budget JOB_GPU_MB): kosten_lr + modellkanten_px gleich;
ein CUDA-OOM durch fremde Jobs ist kein Fehler des Werkzeugs, wird aber als 'uebersprungen' gemeldet. Ausserdem: Punktmodus importiert torch nicht; Kameravariante (--k-ordner) wird benutzt."""
import sys, os, json, subprocess, tempfile, argparse, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner   # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
T = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(T)
ap = argparse.ArgumentParser(); ap.add_argument("--objekt", default=os.path.join(R, "modelle/kaufhaus_null5/objekt.json"))
ap.add_argument("--stl", default="/media/oem/scan/rc-park_null/wettbewerb_kh/netze5/pl30_saeule_median.stl"); ap.add_argument("--maske-dir", default="/media/oem/scan/rc-park_null/wettbewerb_kh9g/masken")
ap.add_argument("--fotos", default="000,004,073,114"); ap.add_argument("--raster", action="store_true"); a = ap.parse_args()
fotos = a.fotos.split(","); fehler = []; PY = sys.executable
def ok(c, t):
    print(("OK   " if c else "FEHL ") + t, flush=True)
    if not c: fehler.append(t)
tmp = temp_ordner("fdb_")
def orig(nr, modus, out):
    env = dict(os.environ, FD_RASTER="1" if modus == "raster" else "0"); env.pop("FD_GPU", None)
    if modus == "punkt": env["CUDA_VISIBLE_DEVICES"] = ""
    subprocess.run([PY, "-W", "ignore", "-I", os.path.join(T, "foto_diff.py"), a.objekt, nr, "--stl", a.stl, "--aus", out, "--bewertung-maske", os.path.join(a.maske_dir, nr + ".png")], env=env, capture_output=True)
    p = os.path.join(out, f"foto_diff_{nr}.json"); return json.load(open(p)) if os.path.exists(p) else None
def batch(modus, out, extra=()):
    r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(T, "foto_diff_batch.py"), a.objekt, "--aus", out, "--stl", "n=" + a.stl, "--fotos", a.fotos, "--maske-dir", a.maske_dir, "--modus", modus, "--threads", "2"] + list(extra),
                       capture_output=True, text=True, env=dict(os.environ, JOB_GPU_MB=os.environ.get("JOB_GPU_MB", "1500")))
    return r
# 1. Punktmodus exakt
r = batch("punkt", os.path.join(tmp, "bp")); ok(r.returncode == 0, "Batch Punktmodus Exit 0")
for nr in fotos:
    o = orig(nr, "punkt", os.path.join(tmp, "op", nr)); b = json.load(open(os.path.join(tmp, "bp", "n", nr, f"foto_diff_{nr}.json")))
    ok(o is not None and o == b, f"Punkt {nr}: gesamtes Ergebnis-JSON gleich (kosten_lr {o and o['kosten_lr']} / {b['kosten_lr']}, modellkanten_px {o and o['modellkanten_px']} / {b['modellkanten_px']})")
# 2. torch im Punktmodus nicht importiert
c = subprocess.run([PY, "-W", "ignore", "-I", "-c", "import sys; sys.argv=['x']; sys.path.insert(0, %r)\nimport os; os.environ['FD_RASTER']='0'; import render_kern as RK; RK._T=False; import foto_diff; print('torch' in sys.modules)" % T], capture_output=True, text=True)
ok(c.stdout.strip() == "False", "Punktmodus: torch nicht importiert (Import foto_diff + RK._T=False)")
# 3. Kameravariante: leere Variante (Ordner ohne K-Dateien) faellt auf Original zurueck; Variante mit K-Kopie wird benutzt
kv = os.path.join(tmp, "kvar", "messprotokoll"); os.makedirs(kv); nr0 = fotos[0]
obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); K = None
for d in (od, os.path.join(R, os.path.dirname(obj["masstabelle"]))):
    p = os.path.join(d, "messprotokoll", f"K-{nr0}.json")
    if os.path.exists(p): K = json.load(open(p)); break
if K is not None and "kamera" in K:
    K["kamera"]["f_px"] = float(K["kamera"]["f_px"]) * 1.02; json.dump(K, open(os.path.join(kv, f"K-{nr0}.json"), "w"))
    subprocess.run([PY, "-W", "ignore", "-I", os.path.join(T, "foto_diff_batch.py"), a.objekt, "--aus", os.path.join(tmp, "bv"), "--stl", "n=" + a.stl, "--fotos", nr0, "--maske-dir", a.maske_dir, "--k-ordner", "f102=" + os.path.join(tmp, "kvar")], capture_output=True, env=dict(os.environ))
    pv = os.path.join(tmp, "bv", "n@f102", nr0, f"foto_diff_{nr0}.json"); ok(os.path.exists(pv), "Kameravariante: Ausgabe in <name>@<variante>/<nr>/")
    if os.path.exists(pv):
        v = json.load(open(pv)); o = json.load(open(os.path.join(tmp, "op", nr0, f"foto_diff_{nr0}.json")))
        ok(abs(v["f_px"] - o["f_px"] * 1.02) < 1e-6 and v["kosten_lr"] != o["kosten_lr"], f"Kameravariante wirkt (f_px {o['f_px']:.1f} -> {v['f_px']:.1f})")
else: print("UEBERSPRUNGEN Kameravariante (keine K-Datei)")
# 4. Raster (optional)
if a.raster:
    r = batch("raster", os.path.join(tmp, "br")); bj = json.load(open(os.path.join(tmp, "br", "batch_ergebnis.json")))["ergebnisse"]
    for nr in fotos:
        e = bj.get("n|" + nr, {})
        if "fehler" in e: print(f"UEBERSPRUNGEN Raster {nr}: {e['fehler'][:60]}"); continue
        o = orig(nr, "raster", os.path.join(tmp, "or", nr))
        if o is None: print(f"UEBERSPRUNGEN Raster {nr}: Original scheiterte (GPU belegt)"); continue
        ok(o["kosten_lr"] == e["kosten_lr"] and o["modellkanten_px"] == e["modellkanten_px"], f"Raster {nr}: kosten_lr {o['kosten_lr']} / {e['kosten_lr']}, modellkanten_px {o['modellkanten_px']} / {e['modellkanten_px']}")
shutil.rmtree(tmp, ignore_errors=True)
print("ALLE BESTANDEN" if not fehler else "FEHLGESCHLAGEN: " + "; ".join(fehler)); sys.exit(0 if not fehler else 1)
