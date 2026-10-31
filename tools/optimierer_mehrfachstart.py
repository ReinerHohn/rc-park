#!/usr/bin/env python3
"""optimierer_mehrfachstart.py - Konvergenztest: K Startpunkte (Basis + zufaellig, feste Seeds), Koordinatenabstieg OHNE Rauschschwelle auf
f = e_train + e_holdout + ept/20 (ept in m), Schrittweite wird halbiert, wenn eine Runde nichts bringt. Landen alle am selben Punkt (oder in einer
flachen Mulde mit gleichem f), ist das Modell am Boden; streuende Masse sind von den Daten NICHT bestimmt (nicht identifizierbar).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/optimierer_mehrfachstart.py [K=4]"""
import sys, json, numpy as np
K = int(sys.argv[1]) if len(sys.argv) > 1 else 4; sys.argv = sys.argv[:1]
sys.path.insert(0, "tools"); import generator_optimierer as G
f_of = lambda r: r["e"] + r["eho"] + r["ept"] / 20.0
def descend(start, tag):
    cur = dict(start); rc = G.evaluate(cur); fc = f_of(rc); scale = 1.0; hist = []
    for rd in range(10):
        improved = False
        for k, st in G.STEP.items():
            best = None
            for sgn in (-1, 1):
                v = dict(cur); v[k] = round(v[k] + sgn * st * scale, 3)
                if not (G.LO[k] - 1e-9 <= v[k] <= G.HI[k] + 1e-9): continue
                r = G.evaluate(v)
                if r is not None and f_of(r) < fc - 1e-9 and (best is None or f_of(r) < f_of(best[1])): best = (v, r)
            if best: cur, rc = best; fc = f_of(rc); improved = True
        hist.append((rd, round(scale, 3), round(fc, 4))); print(f"  [{tag}] Runde {rd} Schritt x{scale:.2f}  f={fc:.4f}  (e {rc['e']:.3f}, hold-out {rc['eho']:.3f}, punktweise {rc['ept']:.2f})", flush=True)
        if not improved:
            if scale <= 0.26: break
            scale /= 2
    return cur, rc, fc
rng = np.random.default_rng(777); starts = {"basis": dict(G.BASE)}
for i in range(K): starts[f"zufall{i+1}"] = {k: round(float(np.clip(G.BASE[k] + rng.uniform(-1.5, 1.5) * G.STEP[k], G.LO[k], G.HI[k])), 3) for k in G.BASE}
out = {}
for tag, st in starts.items():
    f0 = f_of(G.evaluate(st)); cur, rc, fc = descend(st, tag); out[tag] = dict(start=st, ende=cur, f0=f0, f=fc, e=rc["e"], eho=rc["eho"], ept=rc["ept"])
    print(f"START {tag}: f {f0:.4f} -> {fc:.4f}", flush=True)
E=out; P=np.array([[v["ende"][k] for k in G.BASE] for v in out.values()])
print("\nMASS         Basis-Wert  Mittel    Streuung  Schritt  Streuung/Schritt  (klein = von den Daten bestimmt)")
tab = {}
for j, k in enumerate(G.BASE):
    sd = P[:, j].std(); tab[k] = dict(mittel=float(P[:, j].mean()), streuung=float(sd), schritt=G.STEP[k]); print(f"{k:6s} {G.BASE[k]:10.2f} {P[:, j].mean():9.3f} {sd:9.3f} {G.STEP[k]:8.2f} {sd/G.STEP[k]:10.2f}")
print("f je Start:", {t: round(v["f"], 4) for t, v in E.items()})
json.dump(dict(starts=E, tabelle=tab), open("modelle/optimierung_martinstor_mehrfachstart.json", "w"), indent=1, default=float)
print("ENDE")
