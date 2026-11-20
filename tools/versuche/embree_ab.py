"""embree_ab.py - A/B 20.11.2026: trimesh-Strahlen mit dem reinen numpy-Verfahren (ray_triangle, Standard in unseren Umgebungen) gegen Embree (Paket embreex,
NICHT installiert - nur aus einem Ordner zugeladen). Gleiches Netz, gleiche Strahlen (Raster von aussen auf alle 4 Seiten + von oben, wie Pruefstand/Fehlerkarte).
Messgroessen: Sekunden fuer intersects_location (alle Treffer) und intersects_first; Trefferzahl; Abweichung der ersten Trefferentfernung je Strahl (mm im Modell).
Aufruf:  python -I tools/versuche/embree_ab.py <stl> <embree-ordner> [--strahlen 20000]      (startet sich selbst zweimal: ohne / mit Embree)
"""
import sys, os, time, json, subprocess
if "--kind" in sys.argv:
    stl, emb, n, aus = sys.argv[1], sys.argv[2], int(sys.argv[sys.argv.index("--strahlen") + 1]), sys.argv[sys.argv.index("--kind") + 1]
    if aus.endswith("mit.npz"): sys.path.insert(0, emb)
    import numpy as np, trimesh
    m = trimesh.load(stl, force="mesh"); lo, hi = m.bounds; c = (lo + hi) / 2; d = hi - lo; k = int((n / 5) ** 0.5); O = []; R = []
    u = np.linspace(0.02, 0.98, k)
    for ax, sg in ((0, 1), (0, -1), (1, 1), (1, -1)):                    # 4 Seiten: Raster quer x Hoehe, Strahl waagrecht nach innen
        q = 1 - ax; A, B = np.meshgrid(lo[q] + u * d[q], lo[2] + u * d[2]); o = np.zeros((A.size, 3)); o[:, q] = A.ravel(); o[:, 2] = B.ravel(); o[:, ax] = c[ax] + sg * d[ax]
        r = np.zeros((A.size, 3)); r[:, ax] = -sg; O.append(o); R.append(r)
    A, B = np.meshgrid(lo[0] + u * d[0], lo[1] + u * d[1]); o = np.stack([A.ravel(), B.ravel(), np.full(A.size, hi[2] + d[2])], 1); r = np.tile([0, 0, -1.0], (A.size, 1)); O.append(o); R.append(r)
    O = np.concatenate(O); R = np.concatenate(R); art = type(m.ray).__module__.split(".")[-1]
    t = time.time(); loc, ir, it = m.ray.intersects_location(O, R, multiple_hits=True); t1 = time.time() - t
    t = time.time(); f = m.ray.intersects_first(O, R); t2 = time.time() - t
    e = np.full(len(O), np.nan); dist = np.linalg.norm(loc - O[ir], axis=1); o_ = np.argsort(dist)[::-1]; e[ir[o_]] = dist[o_]      # je Strahl kleinste Entfernung
    np.savez(aus, e=e, f=f, n=np.bincount(ir, minlength=len(O)))
    print(json.dumps(dict(art=art, dreiecke=len(m.faces), strahlen=len(O), alle_s=round(t1, 2), erster_s=round(t2, 2), treffer=int(len(loc)), strahlen_mit_treffer=int((f >= 0).sum()), groesse_m=[round(float(x), 2) for x in d])))
    sys.exit(0)
import numpy as np
stl, emb = sys.argv[1], sys.argv[2]; n = sys.argv[sys.argv.index("--strahlen") + 1] if "--strahlen" in sys.argv else "20000"; tmp = os.environ.get("TMPDIR", "/tmp")
E_ = {}
for w in ("ohne", "mit"):
    aus = os.path.join(tmp, f"embree_ab_{w}.npz"); r = subprocess.run([sys.executable, "-I", __file__, stl, emb, "--strahlen", n, "--kind", aus], capture_output=True, text=True)
    if r.returncode: print(w, "FEHLER", r.stderr[-400:]); sys.exit(1)
    E_[w] = (json.loads(r.stdout.strip().splitlines()[-1]), np.load(aus)); print(w, E_[w][0], flush=True)
a, b = E_["ohne"], E_["mit"]; ea, eb = a[1]["e"], b[1]["e"]; beide = ~np.isnan(ea) & ~np.isnan(eb); dd = np.abs(ea - eb)[beide] * 1000
print(f"schneller: alle Treffer x{a[0]['alle_s'] / max(b[0]['alle_s'], 1e-3):.1f}, erster Treffer x{a[0]['erster_s'] / max(b[0]['erster_s'], 1e-3):.1f}")
print(f"Strahlen mit Treffer nur ohne: {int((~np.isnan(ea) & np.isnan(eb)).sum())}, nur mit: {int((np.isnan(ea) & ~np.isnan(eb)).sum())}, beide: {int(beide.sum())}")
print(f"erste Trefferentfernung: Abweichung Median {np.median(dd):.4f} mm, p99 {np.percentile(dd, 99):.4f} mm, max {dd.max():.3f} mm; > 0,1 mm: {int((dd > 0.1).sum())} Strahlen")
print(f"anderes erstes Dreieck: {int((a[1]['f'] != b[1]['f']).sum())} von {len(ea)}; andere Trefferzahl je Strahl: {int((a[1]['n'] != b[1]['n']).sum())}")
