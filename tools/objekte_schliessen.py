"""Offene Zuschnitt-Schalen je Objekt zu wasserdichten Koerpern schliessen (pymeshfix: Loecher fuellen, Komponenten bereinigen).
Aufruf: python -I tools/objekte_schliessen.py ZUSCHNITT.npz OUT.npz [--mintri 2000]
ANNAHME: nicht gesehene Rueckseiten/Loecher sind nur geometrisch geschlossen, nicht gemessen."""
import sys, numpy as np, trimesh, pymeshfix
z = np.load(sys.argv[1]); mt = int(sys.argv[sys.argv.index("--mintri") + 1]) if "--mintri" in sys.argv else 2000
V = z["V"]; F = z["F"]; off = np.r_[0, np.cumsum(z["ntri"])]; OV = []; OF = []; ids = []; nt = []; fa = []; base = 0; wt = 0
for k in range(len(z["ids"])):
    f = F[off[k]:off[k + 1]]
    if len(f) < mt: continue
    u, inv = np.unique(f, return_inverse=True)
    try:
        mf = pymeshfix.MeshFix(V[u].astype(np.float64), inv.reshape(-1, 3).astype(np.int32)); mf.repair(); v2, f2 = mf.points, mf.faces
    except Exception as e: print("Objekt", z["ids"][k], "Fehler", e); continue
    m = trimesh.Trimesh(v2, f2, process=False)
    if len(m.faces) == 0: continue
    wt += m.is_watertight; OV.append(v2.astype(np.float32)); OF.append((f2 + base).astype(np.int32)); base += len(v2); ids.append(z["ids"][k]); nt.append(len(f2)); fa.append(z["farbe"][k])
print("Objekte", len(ids), "wasserdicht", wt)
np.savez_compressed(sys.argv[2], V=np.vstack(OV), F=np.vstack(OF), ids=np.array(ids), ntri=np.array(nt), npts=np.ones(len(ids)), farbe=np.array(fa))
