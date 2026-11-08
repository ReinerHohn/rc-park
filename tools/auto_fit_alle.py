#!/usr/bin/env python3
"""auto_fit_alle.py <objekt> --wolke w.npy --fotos kam.json --bilder dir [--typen a,b,..] [--iter 40]
Automatische Annaeherung ALLER parametrischen Bauteile an die Wolke (Nutzerwunsch 8.11.: 'du naeherst an, ich editiere nur noch ein bisschen von Hand'):
je Teil param_wolke_fit.py (CMA-ES, Teilbox, Raum parameter_raum_lot2.json um die AKTUELLEN Werte) -> Parameter an der Grenze: Raum erweitern und neu (max. 3 Durchgaenge, Regel 9c)
-> teil_tor.py (Gesamtscore Wolke + Foto-Kantenterm, nur uebernehmen wenn nicht schlechter, sonst Rollback). Reihenfolge: schlechteste Teile zuerst. Protokoll auto_fit_protokoll.json.
Nicht parallel zu Editor-Speichern oder Generatorlaeufen starten (gleiche objekt.json)."""
import sys, os, json, argparse, subprocess, datetime, copy
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--typen"); ap.add_argument("--iter", type=int, default=40); ap.add_argument("--pop", type=int, default=12); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(R, "modelle", a.objekt); py = sys.executable
RAUM = os.path.join(OD, "parameter_raum_lot2.json"); PROT = os.path.join(OD, "auto_fit_protokoll.json"); roh = json.load(open(RAUM))
ORDER = a.typen.split(",") if a.typen else ["staffelgiebel:ost", "quader:laube_rueck", "fensterreihe:eg0", "fensterreihe:eg1", "fensterreihe:eg2", "balkonband:haupt", "satteldach:haupt", "stl_teil:fassade",
         "staffelgiebel:west", "stl_teil:figuren", "bogenreihe:laube", "erker:0", "erker:1", "fensterreihe:og", "stl_teil:helme_w", "stl_teil:helme_o"]
prot = json.load(open(PROT)) if os.path.exists(PROT) else []
def ausfuehren(c): return subprocess.run(c, capture_output=True, text=True).stdout
for typ in ORDER:
    if typ not in roh: print(typ, ": kein Raum"); continue
    O = json.load(open(os.path.join(OD, "objekt.json"))); b = next(x for x in O["bauteile"] if x["typ"] == typ)
    raum = copy.deepcopy(roh[typ])
    for k in raum:                                                         # Start = aktueller Wert, Raum um ihn (nach Nutzerkorrekturen aktuell halten)
        v = float(b.get(k, raum[k]["start"])); w = (raum[k]["hi"] - raum[k]["lo"]) / 2; raum[k] = dict(lo=round(v - w, 4), hi=round(v + w, 4), start=v)
    fj = os.path.join(OD, "wolkenfit_%s.json" % typ.replace(":", "_"))
    for durchgang in range(3):
        tmp = os.path.join(OD, "_raum_auto.json"); json.dump({typ: raum}, open(tmp, "w"))
        o = ausfuehren([py, "-I", os.path.join(R, "tools", "param_wolke_fit.py"), a.objekt, typ, "--raum", tmp, "--wolke", a.wolke, "--iter", str(a.iter), "--pop", str(a.pop), "--teilbox", "1.0"])
        if not os.path.exists(fj): print(typ, "Fit ohne Ergebnis:", o[-300:]); break
        f = json.load(open(fj)); grenz = [k.split(".", 1)[1] for k, v in f["nachher"].items() if k.split(".", 1)[1] in raum and (v - raum[k.split(".", 1)[1]]["lo"] < 0.03 * (raum[k.split(".", 1)[1]]["hi"] - raum[k.split(".", 1)[1]]["lo"]) or raum[k.split(".", 1)[1]]["hi"] - v < 0.03 * (raum[k.split(".", 1)[1]]["hi"] - raum[k.split(".", 1)[1]]["lo"]))]
        print("%s Durchgang %d: J %.3f -> %.3f  Median %.2f -> %.2f  an Grenze: %s" % (typ, durchgang + 1, f["J_vorher"], f["J_nachher"], f["median_vorher"], f["median_nachher"], grenz), flush=True)
        if not grenz: break
        for k in grenz: w = (raum[k]["hi"] - raum[k]["lo"]) / 2 * 1.6; c = raum[k]["start"]; raum[k] = dict(lo=round(c - w, 4), hi=round(c + w, 4), start=c)       # Grenze erweitern, nicht aufgeben (Regel 9c)
    else: pass
    if not os.path.exists(fj): continue
    t = ausfuehren([py, "-I", os.path.join(R, "tools", "teil_tor.py"), a.objekt, typ, "--wolke", a.wolke, "--fotos", a.fotos, "--bilder", a.bilder]); print(t.strip().splitlines()[-1] if t.strip() else "Tor ohne Ausgabe", flush=True)
    prot.append(dict(typ=typ, J=[f["J_vorher"], f["J_nachher"]], median=[f["median_vorher"], f["median_nachher"]], an_grenze=grenz, tor=(t.strip().splitlines() or [""])[-1], zeit=datetime.datetime.now().isoformat(timespec="seconds"))); json.dump(prot, open(PROT, "w"), indent=1)
print("FERTIG", flush=True)
