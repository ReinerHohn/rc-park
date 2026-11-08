#!/usr/bin/env python3
"""schleife_teile.py <objekt> --wolke w.npy --fotos k.json --bilder dir --basis ausrichtung_ganz.json --aus dir [--typen a,b] [--runden 3] [--tol 0.002]
Schleife JE BAUTEIL (Nutzer 8.11.): im Rahmen der Gesamt-Ausrichtung (--basis) wird jedes Teil mit Wolke + Foto-Kantenterm in engen Grenzen nachgefuehrt
(8 DoF, iterativ bis Konvergenz). Je Teil: <aus>/<typ>.json, <typ>.stl, <typ>.jpg (Overlay Wolke+Teil auf Foto); am Ende Gesamt-Overlay aller Teile + Tabelle TEILE_SCHLEIFE.md.
Nicht aufgenommen (brauchen Traeger): gaubenreihe (Satteldach), satteldach."""
import sys, os, json, argparse, subprocess, datetime
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--basis", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--typen", default=""); ap.add_argument("--runden", type=int, default=3); ap.add_argument("--tol", type=float, default=0.002)
ap.add_argument("--foto", default="ip_IMG_6161.jpg"); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); py = sys.executable; os.makedirs(a.aus, exist_ok=True); OBJ = json.load(open(os.path.join(R, "modelle", a.objekt, "objekt.json")))
typen = a.typen.split(",") if a.typen else [b["typ"] for b in OBJ["bauteile"] if b.get("aktiv", True) is not False and not b["typ"].startswith(("satteldach", "gaubenreihe"))]
log = os.path.join(R, "modelle", "LOGBUCH_" + datetime.date.today().isoformat() + ".md"); tab = []
for t in typen:
    nm = t.replace(":", "_"); start = None; prev = None; res = None
    for r in range(1, a.runden + 1):
        oj = os.path.join(a.aus, nm + ".json"); stl = os.path.join(a.aus, nm + ".stl")
        cmd = [py, "-I", os.path.join(R, "tools", "modell_ausrichten_gpu.py"), a.objekt, "--wolke", a.wolke, "--typ", t, "--sichtbar", "--fotos", a.fotos, "--bilder", a.bilder, "--basis", a.basis, "--du_max", "2.5", "--dn_max", "1.5", "--gier_max", "4",
               "--su_lo", "0.85", "--su_hi", "1.25", "--sz_lo", "0.9", "--sz_hi", "1.15", "--rand", "6", "--nfotos", "6", "--stl_aus", stl, "--out_json", oj] + (["--start", start] if start else [])
        o = subprocess.run(cmd, capture_output=True, text=True)
        if not os.path.exists(oj): print(t, "FEHLER", o.stdout[-200:], o.stderr[-200:]); res = None; break
        res = json.load(open(oj)); start = os.path.join(a.aus, nm + "_start.json"); json.dump(res, open(start, "w")); sc = res["abstand_ende"]
        if prev is not None and prev - sc < a.tol: break
        prev = sc
    if res is None: tab.append((t, None)); continue
    subprocess.run([py, "-I", os.path.join(R, "tools", "modell_foto_overlay.py"), "--stl", stl, "--fotos", a.fotos, "--bilder", a.bilder, "--foto", a.foto, "--wolke", a.wolke, "--out", os.path.join(a.aus, nm + ".jpg")], capture_output=True)
    z = "%s: Score %.3f -> %.3f | du %.2f dn %.2f dz %.2f gier %.2f nick %.2f roll %.2f su %.3f sz %.3f (Runden %d)" % (t, res["abstand_start"], res["abstand_ende"], res["du"], res["dn"], res["dz"], res["gier_grad"], res["nick_grad"], res["roll_grad"], res["su"], res["sz"], r)
    print(z, flush=True); open(log, "a").write("- Teil-Schleife " + z + "\n"); tab.append((t, res))
# Gesamt-Overlay aller Teile
import trimesh
ms = [trimesh.load(os.path.join(a.aus, t.replace(":", "_") + ".stl"), process=False) for t, r_ in tab if r_ and os.path.exists(os.path.join(a.aus, t.replace(":", "_") + ".stl"))]
if ms:
    trimesh.util.concatenate(ms).export(os.path.join(a.aus, "alle_teile.stl"))
    subprocess.run([py, "-I", os.path.join(R, "tools", "modell_foto_overlay.py"), "--stl", os.path.join(a.aus, "alle_teile.stl"), "--fotos", a.fotos, "--bilder", a.bilder, "--foto", a.foto, "--wolke", a.wolke, "--out", os.path.join(a.aus, "alle_teile.jpg")], capture_output=True)
L = ["# Teil-Schleife (Basis Gesamt-Ausrichtung)", "", "| Teil | Score vorher | nachher | du | dn | dz | gier | nick | roll | su | sz |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for t, r_ in tab: L.append("| %s | FEHLER |||||||||" % t if r_ is None else "| %s | %.3f | %.3f | %+.2f | %+.2f | %+.2f | %+.1f | %+.1f | %+.1f | %.3f | %.3f |" % (t, r_["abstand_start"], r_["abstand_ende"], r_["du"], r_["dn"], r_["dz"], r_["gier_grad"], r_["nick_grad"], r_["roll_grad"], r_["su"], r_["sz"]))
open(os.path.join(a.aus, "TEILE_SCHLEIFE.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
