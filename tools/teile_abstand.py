#!/usr/bin/env python3
"""teile_abstand.py - Rangfolge der Bauteile nach Abstand zur Wolke (Sweet Spots zuerst, Nutzerregel): je Bauteil von objekt.json einzeln bauen (NUR_BAUTEIL), dann
 - Median/P90 Abstand Wolkenpunkt -> Bauteilflaeche fuer Wolkenpunkte innerhalb --nah (0,6 m) um das Teil (Wolke sieht nur Sichtbares, Regel 4),
 - 'gestuetzt' = Anteil der Bauteil-Oberflaechenpunkte mit Wolkenpunkt < 0,3 m (niedrig = Wolke blind oder erfundenes Teil),
 - Flaeche (m2) -> Prioritaet = Median * sqrt(Flaeche).
  /media/oem/scan/venv-seg/bin/python -I tools/teile_abstand.py kaufhaus_grob3 [--aus modelle/kaufhaus_grob3/teile_abstand.json]"""
import os, sys, json, argparse, subprocess, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import min_abstand
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus"); ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/wolke_netzrahmen.npy"); ap.add_argument("--nah", type=float, default=0.6)
ap.add_argument("--py", default=os.path.expanduser("~/.venvs/rcpark/bin/python")); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); O = json.load(open(os.path.join(OD, "objekt.json"))); SC = float(O.get("stl_massstab", 87)); K = 1000.0 / SC
P = np.load(a.wolke)[:, :3].astype(np.float32); rows = []
for b in O["bauteile"]:
    if b.get("aktiv", True) is False: continue
    stl = f"_ta_{os.getpid()}.stl"; env = dict(os.environ, NUR_BAUTEIL=b["typ"], OBJ_DIR=a.objekt, STL_NAME=stl, SCALE=str(SC), ELEMENTE_AUS="/dev/null")
    # stl_teil-Gruppen haengen nur Rohdreiecke an; ctx['dach'] fuer gaubenreihe braucht das Satteldach davor -> Vorgaenger mitbauen
    typs = [b["typ"]]
    if b["typ"].startswith("gaubenreihe"): typs = [x["typ"] for x in O["bauteile"] if x["typ"].startswith("satteldach")] + typs
    env["NUR_BAUTEIL"] = ",".join(typs); r = subprocess.run([a.py, os.path.join(ROOT, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True); p = os.path.join(ROOT, "modelle", "stl", stl)
    if not os.path.exists(p): rows.append(dict(typ=b["typ"], fehler=r.stderr[-200:])); continue
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(1.0 / K)
    if b["typ"].startswith("gaubenreihe"):                                                    # Satteldach wieder herausrechnen (nur Gauben bewerten): Dreiecke ueber Dachebene
        pass
    if len(m.faces) == 0: rows.append(dict(typ=b["typ"], fehler="leer")); continue
    Q, _ = trimesh.sample.sample_surface(m, 40000, seed=1); lo, hi = Q.min(0) - a.nah, Q.max(0) + a.nah
    sel = np.all((P >= lo) & (P <= hi), 1); d = min_abstand(P[sel], Q); d = d[d < a.nah]; ds = min_abstand(Q, P)
    rows.append(dict(typ=b["typ"], n_wolke=int(len(d)), median=float(np.median(d)) if len(d) else None, p90=float(np.percentile(d, 90)) if len(d) else None, gestuetzt=float((ds < 0.3).mean()), flaeche_m2=float(m.area / 2),
                     prioritaet=float(np.median(d) * np.sqrt(m.area / 2)) if len(d) else 0.0))
rows.sort(key=lambda r: -(r.get("prioritaet") or 0)); json.dump(rows, open(a.aus or os.path.join(OD, "teile_abstand.json"), "w"), indent=1)
for r in rows: print(f"{r['typ']:28s}" + (f" Median {r['median']:.3f}  P90 {r['p90']:.3f}  gestuetzt {r['gestuetzt']:.2f}  Flaeche {r['flaeche_m2']:.0f} m2  Prio {r['prioritaet']:.2f}" if r.get("median") is not None else " " + str(r.get("fehler"))))
