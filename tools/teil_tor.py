#!/usr/bin/env python3
"""teil_tor.py <objekt> <typ>[,<typ>..] --wolke w.npy --fotos kam.json --bilder dir [--eps 0.002] [--trocken]
ANNAHME-TOR fuer Teilfits (Nutzer 8.11.: 'bist du sicher, dass wir konvergieren?'): uebernimmt die 'nachher'-Werte aus <objekt>/wolkenfit_<typ>.json NUR, wenn der GESAMTSCORE
(Wolkenabstand + Foto-Kantenterm ueber das ganze Modell, tools/modell_ausrichten_gpu.py --nur_bewerten, Gesamttransformation = Identitaet) nicht schlechter wird;
sonst Rollback von objekt.json. Je Teil eine Zeile im Logbuch + tor_protokoll.json. Ein Teilfit, der nur seinen eigenen Abstand senkt, aber das Gesamtbild verschlechtert, wird so abgelehnt.
Gesamtscore = abstand_start des Optimierers (getrimmter Mittelwert, m); Sollwerte werden nicht gelockert."""
import sys, os, json, argparse, subprocess, shutil, datetime
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("typen"); ap.add_argument("--wolke", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--eps", type=float, default=0.002); ap.add_argument("--trocken", action="store_true"); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(R, "modelle", a.objekt); OJ = os.path.join(OD, "objekt.json"); py = sys.executable
log = os.path.join(R, "modelle", "LOGBUCH_" + datetime.date.today().isoformat() + ".md"); prot = os.path.join(OD, "tor_protokoll.json")

def score():
    c = [py, "-I", os.path.join(R, "tools", "modell_ausrichten_gpu.py"), a.objekt, "--wolke", a.wolke, "--sichtbar", "--fotos", a.fotos, "--bilder", a.bilder,
         "--su_lo", "1", "--su_hi", "1", "--sz_lo", "1", "--sz_hi", "1", "--ns", "40000", "--nur_bewerten"]
    o = subprocess.run(c, capture_output=True, text=True).stdout
    for z in o.splitlines():
        if z.startswith("SCORE"): return float(z.split()[1])
    raise SystemExit("Score nicht ermittelbar:\n" + o[-800:])

P = json.load(open(prot)) if os.path.exists(prot) else []
for typ in a.typen.split(","):
    fj = os.path.join(OD, "wolkenfit_%s.json" % typ.replace(":", "_").replace(",", "+"))
    if not os.path.exists(fj): print(typ, ": keine", fj); continue
    f = json.load(open(fj)); s0 = score(); shutil.copy(OJ, OJ + ".tor_bak"); O = json.load(open(OJ)); geaendert = {}
    for b in O["bauteile"]:
        for n, v in f["nachher"].items():
            t_, n_ = n.split(".", 1)
            if t_ == b["typ"]: geaendert[n] = (b.get(n_), v); b[n_] = v; b.setdefault("werte_quellen", {})[n_] = "param_wolke_fit.py gegen lot2-Wolke, durch teil_tor.py (Gesamtscore) angenommen"
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); s1 = score(); ok = s1 <= s0 + a.eps
    if not ok or a.trocken: shutil.copy(OJ + ".tor_bak", OJ)
    z = "Tor %s: Gesamtscore %.4f -> %.4f (%s)" % (typ, s0, s1, "ANGENOMMEN" if ok and not a.trocken else ("abgelehnt/Rollback" if not ok else "trocken")); print(z, flush=True)
    open(log, "a").write("- " + z + "\n"); P.append(dict(typ=typ, vorher=s0, nachher=s1, angenommen=bool(ok and not a.trocken), werte={k: list(v) for k, v in geaendert.items()}, zeit=datetime.datetime.now().isoformat(timespec="seconds")))
    json.dump(P, open(prot, "w"), indent=1)
