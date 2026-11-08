#!/usr/bin/env python3
"""sweep_alle.py <objekt> --wolke w.npy [--bereich 2.5] [--typen a,b,..]
Fuehrt tools/teil_sweep_gpu.py (GPU-Pyramide grob->fein) fuer ALLE Bauteile des Objekts aus (Nutzer 8.11.: "ich will es ueberall haben") und
schreibt modelle/<objekt>/sweep_alle.json + SWEEP_ALLE.md: je Teil Verschiebung (du,dn,dz), Abstand vorher/nachher, Schaerfe, Mehrdeutigkeit.
Traegerbauteile (Gauben -> Satteldach) per MIT-Tabelle. Mehrere Teile parallel auf der GPU (je ~1 GB)."""
import sys, os, json, subprocess, argparse, concurrent.futures as cf
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--bereich", default="2.5"); ap.add_argument("--typen"); ap.add_argument("--par", type=int, default=3); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); obj = json.load(open(os.path.join(OD, "objekt.json")))
MIT = {"gaubenreihe": "satteldach:haupt"}
typen = a.typen.split(",") if a.typen else [b["typ"] for b in obj["bauteile"] if b.get("aktiv", True) is not False and not b["typ"].startswith("satteldach")]
PY = "/media/oem/scan/venv-seg/bin/python"
def lauf(t):
    cmd = [PY, "-I", os.path.join(ROOT, "tools", "teil_sweep_gpu.py"), a.objekt, t, "--wolke", a.wolke, "--bereich", a.bereich]
    if t.split(":")[0] in MIT: cmd += ["--mit", MIT[t.split(":")[0]]]
    r = subprocess.run(cmd, capture_output=True, text=True); f = os.path.join(OD, "sweep_" + t.replace(":", "_") + ".json")
    if r.returncode != 0 or not os.path.exists(f): return t, None, (r.stderr or r.stdout)[-160:].replace("\n", " ")
    return t, json.load(open(f)), ""
res = {}
with cf.ThreadPoolExecutor(a.par) as ex:
    for t, j, err in ex.map(lauf, typen):
        res[t] = j if j else {"fehler": err}; print(t, "OK" if j else "FEHLER " + err, flush=True)
json.dump(res, open(os.path.join(OD, "sweep_alle.json"), "w"), indent=1)
L = ["# Sweep aller Bauteile (GPU, Pyramide grob->fein)", "", "Verschiebung des Bauteils gegen die Wolke. du = entlang der Fassade, dn = senkrecht (negativ = Richtung Strasse), dz = Hoehe (Meter, Netzrahmen).",
     "Abstand = Mittel aus Modell->Wolke und Wolke->Modell (80 % getrimmt). Ein Peak ist nur dann belastbar, wenn der zweitbeste weit entfernte Peak deutlich schlechter ist.", "",
     "| Bauteil | du | dn | dz | Abstand vorher | nachher | zweitbester Peak (Abstand) | Urteil |", "|---|---|---|---|---|---|---|---|"]
for t, j in res.items():
    if "fehler" in j: L.append(f"| {t} | | | | | | | FEHLER: {j['fehler'][:60]} |"); continue
    gl = j.get("abstand_zweit") or 0; shift = (j["du"] ** 2 + j["dn"] ** 2 + j["dz"] ** 2) ** 0.5; gewinn = j["abstand_start"] - j["abstand_peak"]
    pl = j.get("plateau", [9, 9, 9]); ach = ["du", "dn", "dz"]; off = [ach[k] for k in range(3) if pl[k] > 0.3]
    urteil = "Lage ok (<0,15 m)" if shift < 0.15 else ("kein Gewinn: nicht uebernehmen" if gewinn <= 0.05 else ("alle Achsen bestimmt" if not off else "offen: " + ",".join(off)))
    L.append(f"| {t} | {j['du']:+.2f} | {j['dn']:+.2f} | {j['dz']:+.2f} | {j['abstand_start']:.3f} | {j['abstand_peak']:.3f} | {gl:.3f} | {urteil} |")
open(os.path.join(OD, "SWEEP_ALLE.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
