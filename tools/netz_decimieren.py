"""Je Objekt quadratisch vereinfachen (fast_simplification) auf ein Dreiecksbudget; kleine Objekte bleiben unveraendert. Aufruf: python -I tools/netz_decimieren.py IN.npz OUT.npz [--budget 550000]"""
import sys, numpy as np, fast_simplification as fs
a = sys.argv; z = np.load(a[1]); bud = int(a[a.index("--budget") + 1]) if "--budget" in a else 550000; V = z["V"]; F = z["F"]; off = np.r_[0, np.cumsum(z["ntri"])]; n = len(F); r = min(1.0, bud / n); V2 = []; F2 = []; nt = []; nv = 0
for k in range(len(z["ids"])):
    f = F[off[k]:off[k + 1]]; u, inv = np.unique(f, return_inverse=True); p = V[u].astype(np.float32); t = inv.reshape(-1, 3).astype(np.int32)
    if r < 1.0 and len(t) > 300:
        try: p, t = fs.simplify(p, t, target_reduction=1 - r, agg=5)
        except Exception: pass
    V2.append(np.asarray(p, np.float32)); F2.append(np.asarray(t, np.int32) + nv); nv += len(p); nt.append(len(t))
np.savez_compressed(a[2], V=np.vstack(V2), F=np.vstack(F2), ids=z["ids"], npts=z["npts"], ntri=np.array(nt), farbe=z["farbe"]); print("Dreiecke", int(sum(nt)), "von", n)
