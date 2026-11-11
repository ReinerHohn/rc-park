#!/usr/bin/env python3
"""Rueckblick-Test des lokalen Foto-Tors an verworfenen Kreis-Runden: <lauf>:<runde> ... -> foto_lokal.py je Runde, Ergebnis nach /media/oem/scan/rc-park_tmp/foto_lokal/rb_<lauf>_r<n>.json"""
import sys, os, json, time, subprocess
PY = "/media/oem/scan/venv-seg/bin/python"; KD = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3"; R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for arg in sys.argv[1:]:
    lauf, r = arg.split(":"); d = f"{KD}/{lauf}"
    z = next(json.loads(l) for l in open(d + "/kreis.jsonl") if json.loads(l).get("runde") == int(r))
    v = next((p for p in (f"{d}/teile_r{r}_vorher_form", f"{d}/teile_r{r}_vorher") if os.path.isdir(p)), None); n = f"{d}/teile_r{r}_nachher"
    if not v or not os.path.isdir(n): print(arg, "nicht messbar"); continue
    teil = z["ziel"]["teil"]; aus = f"/media/oem/scan/rc-park_tmp/foto_lokal/rb_{lauf}_r{r}.json"
    cmd = [PY, "-W", "ignore", "-I", "tools/foto_lokal.py", "kaufhaus_grob3", "--vorher", v, "--nachher", n, "--fotos", ",".join(z["foto_fotos"]), "--aus", aus,
           "--bilder", f"/media/oem/scan/rc-park_tmp/foto_lokal/bilder_{lauf}_r{r}"] + ([] if teil.endswith("__neu") else ["--nur", teil])
    t0 = time.time(); p = subprocess.run(cmd, cwd=R0, capture_output=True, text=True); print(arg, teil, "rc", p.returncode, f"{time.time()-t0:.0f}s", flush=True)
    if p.returncode: print(p.stderr[-1500:])
    else: print(p.stdout[-800:])
