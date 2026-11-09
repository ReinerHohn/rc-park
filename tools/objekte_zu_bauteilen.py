"""Stufe 2: 3D-Objekte (sam_mehrfoto_3d.py) -> Vorschlag fuer Generator-Bauteile 'quader:sam_<id>' (u,n,z-Rahmen der Hauptfassade, Perzentil 2-98 der Punktmenge).
Schreibt NUR einen Vorschlag (kein Eingriff in objekt.json; Regel 3b/Pruefstand). Aufruf: python -I tools/objekte_zu_bauteilen.py IN.npz OBJEKT.json OUT.json [--minpts 300] [--maxanteil 0.15]"""
import argparse, json, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("objekt"); ap.add_argument("aus"); ap.add_argument("--minpts", type=int, default=300); ap.add_argument("--maxanteil", type=float, default=0.15); a = ap.parse_args()
O = json.load(open(a.objekt)); n_ = np.array(O["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); U_ = np.array([n_[1], -n_[0]])
z = np.load(a.ein); P = z["P"]; ob = z["obj"]; rgb = z["rgb"]; N = len(P); out = []
for oi in np.unique(ob[ob >= 0]):
    m = ob == oi; k = int(m.sum())
    if k < a.minpts or k > a.maxanteil * N: continue                    # Wand/Dach-Riesen nicht als Quader
    p = P[m]; u = p[:, :2] @ U_; s = p[:, :2] @ n_; zz = p[:, 2]; lo = [np.percentile(x, 2) for x in (u, s, zz)]; hi = [np.percentile(x, 98) for x in (u, s, zz)]
    if hi[0] - lo[0] < 0.05 or hi[1] - lo[1] < 0.02 or hi[2] - lo[2] < 0.05: continue
    out.append(dict(typ="quader:sam_%d" % oi, gruppe="SAM-Objekte (automatisch)", u0=round(float(lo[0]), 3), u1=round(float(hi[0]), 3), n0=round(float(lo[1]), 3), n1=round(float(hi[1]), 3), z0=round(float(lo[2]), 3), z1=round(float(hi[2]), 3), modus="anbau", aktiv=False,
                    quelle="tools/sam_mehrfoto_3d.py: SAM-Masken aus %d Fotos, Objekt #%d (%d Wolkenpunkte); Box = Perzentil 2-98 im u/n/z-Rahmen (Rueckseite nicht gemessen: ANNAHME)" % (len(z["fotos"]), oi, k), farbe=[int(v) for v in np.median(rgb[m], 0)], punkte=k))
json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False); print(len(out), "Quader-Vorschlaege")
