#!/usr/bin/env python3
"""schleife_ausrichten.py <objekt> --wolke w.npy --fotos k.json --bilder dir [--foto ip_IMG_6161.jpg] [--runden 4] [--tol 0.003]
Aeussere ITERATIVE, KONVERGIERENDE Schleife (Nutzer 8.11.): modell_ausrichten_gpu (8 DoF, Wolke + Foto-Kantenterm) mit Startzustand der Vorrunde,
nach jeder Runde Overlay (Wolke+Modell aufs Foto) und Logbuch-Zeile; stoppt, wenn der Score sich um < tol verbessert. Ergebnis je Runde: audit/schleife_<n>.json/.jpg."""
import sys, os, json, argparse, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--foto", default="ip_IMG_6161.jpg"); ap.add_argument("--runden", type=int, default=4); ap.add_argument("--tol", type=float, default=0.003); ap.add_argument("--aus", required=True); ap.add_argument("--extra", default=""); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); py = sys.executable; os.makedirs(a.aus, exist_ok=True); prev = None; start = None; log = os.path.join(R, "modelle", "LOGBUCH_" + __import__("datetime").date.today().isoformat() + ".md")
for r in range(1, a.runden + 1):
    stl = os.path.join(a.aus, f"schleife_{r}.stl"); cmd = [py, "-I", os.path.join(R, "tools", "modell_ausrichten_gpu.py"), a.objekt, "--wolke", a.wolke, "--sichtbar", "--fotos", a.fotos, "--bilder", a.bilder, "--stl_aus", stl] + a.extra.split() + (["--start", start] if start else [])
    o = subprocess.run(cmd, capture_output=True, text=True).stdout; res = json.load(open(os.path.join(R, "modelle", a.objekt, "ausrichtung_ganz.json"))); start = os.path.join(a.aus, f"schleife_{r}.json"); json.dump(res, open(start, "w"), indent=1)
    subprocess.run([py, "-I", os.path.join(R, "tools", "modell_foto_overlay.py"), "--stl", stl, "--fotos", a.fotos, "--bilder", a.bilder, "--foto", a.foto, "--wolke", a.wolke, "--out", os.path.join(a.aus, f"schleife_{r}.jpg")], capture_output=True)
    sc = res["abstand_ende"]; z = "Runde %d: Score %.4f (Start %.4f) du %.2f dn %.2f dz %.2f gier %.2f nick %.2f roll %.2f su %.3f sz %.3f" % (r, sc, res["abstand_start"], res["du"], res["dn"], res["dz"], res["gier_grad"], res["nick_grad"], res["roll_grad"], res["su"], res["sz"])
    print(z, flush=True); open(log, "a").write("- Schleife " + z + "\n")
    if prev is not None and prev - sc < a.tol: print("KONVERGIERT (Verbesserung %.4f < %.4f)" % (prev - sc, a.tol)); break
    prev = sc
