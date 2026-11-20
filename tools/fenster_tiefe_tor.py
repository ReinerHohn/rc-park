#!/usr/bin/env python3
"""fenster_tiefe_tor.py - Fensterliste (audit/fenster_auto.json) mit dem Ebenen-Sweep pruefen und ergaenzen (21.11.2026, Kettenstufe 'bauplan').

Anlass (Schwabentor von null, 21.11.): OWLv2 hielt die hellen Felder zwischen den Erker-Konsolen mit 10 von 10 Stimmen fuer Fenster; die zwei echten Rundbogenfenster
fielen an der Stimmenschwelle durch (3 von 7). Die Tiefe trennt beides (gemessen, fassade/tiefe_f00.npz):
  echte Fenster: 51-68 % der sicheren Zellen > 0,1 m HINTER der Wand (Nische/Laibung), <= 24 % davor;
  Konsolenfelder: 0-1 % dahinter, 23-40 % > 0,3 m DAVOR (Streben, Erkerboden).
Regeln (KERNMETHODE: Erkennen = Zone, Entscheidung aus der Triangulation):
  VERWERFEN  ein gelistetes Fenster, wenn >= --min_gut sichere Zellen und hinten < --hinten_min und vorn >= --vorn_max (etwas steht davor, keine Nische).
  ERGAENZEN  ein Erkennerkasten 'fenster' unter der Stimmenschwelle (>= 2 Stimmen), wenn hinten >= --hinten_neu und vorn < --vorn_max und er kein gelistetes Fenster schneidet.
  Ohne Tiefenkarte, zu wenig sichere Zellen im Kasten oder < --ring_min im 0,5-m-Ring: unveraendert (kein Urteil ohne Messung; Schwabentor f03).
Aufruf:  fenster_tiefe_tor.py <fenster_auto.json> <fassade-ordner (elemente.json, tiefe_fNN.npz, vorbauten_fNN.json)>
Schreibt fenster_auto.json neu (Eingang als fenster_auto_roh.json daneben) und fenster_tiefe_tor.json (Begruendung je Kasten). rc 0.
"""
import sys, os, json, argparse, shutil, numpy as np


def anteile(npz, w_wand, b):
    w, g, c, u0, z1 = npz["w"], npz["gut"], float(npz["zelle"]), float(npz["u0"]), float(npz["z1"]); H, W = w.shape
    ix = lambda u: int(np.clip((u - u0) / c, 0, W)); iz = lambda z: int(np.clip((z1 - z) / c, 0, H))
    A = w[iz(b[3]):iz(b[2]), ix(b[0]):ix(b[1])] - w_wand; G = g[iz(b[3]):iz(b[2]), ix(b[0]):ix(b[1])]
    if G.size == 0: return 0.0, 0.0, 0.0, 0.0
    r = 0.5; GR = g[iz(b[3] + r):iz(b[2] - r), ix(b[0] - r):ix(b[1] + r)].copy(); GR[iz(b[3]) - iz(b[3] + r):iz(b[2]) - iz(b[3] + r), ix(b[0]) - ix(b[0] - r):ix(b[1]) - ix(b[0] - r)] = False
    ring = float(GR.sum() / max(1, GR.size - G.size))      # Anteil sicherer Zellen im 0,5-m-Ring: misst der Sweep hier ueberhaupt? (Schwabentor f03: 33-58 % -> kein Urteil)
    return float(G.mean()), float((G & (A < -0.1)).mean()), float((G & (A > 0.3)).mean()), ring


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("ordner")
    ap.add_argument("--min_gut", type=float, default=0.3); ap.add_argument("--hinten_min", type=float, default=0.15); ap.add_argument("--vorn_max", type=float, default=0.2)
    ap.add_argument("--hinten_neu", type=float, default=0.4); ap.add_argument("--ring_min", type=float, default=0.7, help="Anteil sicherer Sweep-Zellen im Ring um den Kasten, ab dem geurteilt wird"); a = ap.parse_args()
    roh = a.fenster[:-5] + "_roh.json"
    shutil.copy(a.fenster, roh)        # immer die aktuelle Liste als Eingang (Stufe 'fenster' schreibt sie neu; ein zweiter bauplan-Lauf auf der gefilterten Liste ist idempotent)
    J = json.load(open(roh)); E = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"]; bericht = {}
    for fid, F in J.items():
        if not isinstance(F, dict) or "fenster" not in F: continue
        nz = os.path.join(a.ordner, f"tiefe_{fid}.npz"); vj = os.path.join(a.ordner, f"vorbauten_{fid}.json")
        if not os.path.exists(nz): bericht[fid] = "keine Tiefenkarte - unveraendert"; continue
        npz = np.load(nz); ww = json.load(open(vj)).get("wand_versatz_m", 0.0) if os.path.exists(vj) else 0.0; neu = []; br = []
        for q in F["fenster"]:
            gu, hi, vo, ri = anteile(npz, ww, (q["u0"], q["u1"], q["z0"], q["z1"]))
            weg = gu >= a.min_gut and ri >= a.ring_min and hi < a.hinten_min and vo >= a.vorn_max
            br.append(dict(kasten=[q["u0"], q["u1"], q["z0"], q["z1"]], sicher=round(gu, 2), ring=round(ri, 2), hinten=round(hi, 2), vorn=round(vo, 2), urteil="VERWORFEN: etwas steht davor, keine Nische" if weg else ("bleibt" if ri >= a.ring_min else "bleibt (Sweep ringsum unsicher - kein Urteil)")))
            if not weg: neu.append(q)
        for e in (E.get(fid) or {}).get("elemente", []):
            if e.get("klasse") != "fenster" or e.get("stimmen", 0) < 2: continue
            b = (e["u0"], e["u1"], e["z0"], e["z1"])
            if any(min(b[1], q["u1"]) > max(b[0], q["u0"]) and min(b[3], q["z1"]) > max(b[2], q["z0"]) for q in F["fenster"] + neu): continue
            gu, hi, vo, ri = anteile(npz, ww, b)
            if gu >= a.min_gut and ri >= a.ring_min and hi >= a.hinten_neu and vo < a.vorn_max:
                neu.append(dict(u0=round(b[0], 3), u1=round(b[1], 3), z0=round(b[2], 3), z1=round(b[3], 3), teiler=[], kaempfer=None, scheiben=1, stimmen_min=e.get("stimmen"), sprossen=[],
                                quelle="fenster_tiefe_tor: Erkennerkasten unter der Stimmenschwelle, Nische im Ebenen-Sweep belegt"))
                br.append(dict(kasten=[round(x, 2) for x in b], sicher=round(gu, 2), hinten=round(hi, 2), vorn=round(vo, 2), stimmen=e.get("stimmen"), urteil="ERGAENZT: Nische belegt"))
        F["fenster"] = neu; bericht[fid] = br
        for r in br:
            if not r["urteil"].startswith("bleibt") or "kein Urteil" in r["urteil"]: print(f"{fid}: {r['urteil']}  u {r['kasten'][0]:.2f}..{r['kasten'][1]:.2f} z {r['kasten'][2]:.2f}..{r['kasten'][3]:.2f}  (hinten {r['hinten'] * 100:.0f} %, vorn {r['vorn'] * 100:.0f} %)")
    json.dump(J, open(a.fenster, "w"), indent=1); json.dump(bericht, open(a.fenster[:-5].replace("fenster_auto", "fenster_tiefe_tor") + ".json", "w"), indent=1)
    print(f"-> {a.fenster}: " + ", ".join(f"{k} {len(v['fenster'])}" for k, v in J.items() if isinstance(v, dict) and "fenster" in v)); return 0


if __name__ == "__main__": sys.exit(main())
