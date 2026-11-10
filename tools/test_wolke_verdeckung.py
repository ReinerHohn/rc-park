#!/usr/bin/env python3
"""Synthetischer Beweis fuer wolke_verdeckung.py (L-KR26): Teil (Wand in 10 m) hinter einer Wolken-'Decke' (6 m), die nicht im Modell ist.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_wolke_verdeckung.py [--aus D]"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_verdeckung as WV

rng = np.random.default_rng(0)
W, H, f = 800, 600, 700.0; cx, cy = W / 2, H / 2
R = np.eye(3); t = np.zeros(3)
v = WV.Verdecker(np.zeros((1, 3), np.float32))


def ebene(z, x0, x1, y0, y1, n, rausch=0.03):
    return np.c_[rng.uniform(x0, x1, n), rng.uniform(y0, y1, n), z + rng.normal(0, rausch, n)].astype(np.float32)


# Teil: Wand z = 10 m; Pixel-Tiefe dp = 10 ueberall (Teil fuellt das Bild)
dp = np.full((H, W), 10.0, np.float32)
wand = ebene(10.0, -6, 6, -4.5, 4.5, 400000)                 # Wolke auf dem Teil selbst (Rauschen 3 cm)
decke_links = ebene(6.0, -3.4, 0.0, -2.6, 2.6, 60000)        # Decke bei 6 m, deckt Bildhaelfte links (x < cx) ab: u = f x/z + cx -> x in [-3.43, 0]
rippen = np.r_[tuple(ebene(6.0, x - 0.05, x + 0.05, -2.6, 2.6, 4000) for x in np.arange(-3.4, 0.01, 0.7))]   # nur duenne Rippen; hinter der geschlossenen Decke gibt es (wie in echt) keine Wolke auf dem Teil, daher links keine Wandpunkte in E; (alle 0,7 m = ~80 px), Kappen dazwischen OHNE Punkte
schweb = ebene(4.0, -3, 3, -2, 2, 30)                        # 30 Einzelpunkte vor dem Teil (Schwebteilchen): duerfen NICHT verdecken
fall = {}
for name, P in {"A ohne Decke (nur Wolke auf Teil)": wand, "B Decke links": np.r_[wand, decke_links],
                "C nur Schwebpunkte": np.r_[wand, schweb], "E Decke nur Rippen (Luecken)": np.r_[wand[wand[:, 0] > 0], rippen], "D keine Wolke": np.zeros((0, 3), np.float32) + 1e3}.items():
    v.P = __import__("torch").as_tensor(P, device="cuda")
    zc = v.zkarte(R, t, f, cx, cy, W, H); vd = WV.Verdecker.verdeckt(zc, dp, 12)
    li, re = vd[:, :W // 2 - 8], vd[:, W // 2 + 8:]
    fall[name] = {"verdeckt_gesamt": round(float(vd.mean()), 4), "links": round(float(li.mean()), 4), "rechts": round(float(re.mean()), 4)}
    print(f"{name:40s} verdeckt gesamt {vd.mean():.4f}  links {li.mean():.4f}  rechts {re.mean():.4f}")
ok = (fall["A ohne Decke (nur Wolke auf Teil)"]["verdeckt_gesamt"] < 0.005 and fall["C nur Schwebpunkte"]["verdeckt_gesamt"] < 0.005 and fall["D keine Wolke"]["verdeckt_gesamt"] == 0
      and fall["E Decke nur Rippen (Luecken)"]["links"] > 0.75 and fall["E Decke nur Rippen (Luecken)"]["rechts"] < 0.005
      and fall["B Decke links"]["links"] > 0.85 and fall["B Decke links"]["rechts"] < 0.005)
print("BESTANDEN" if ok else "FEHLGESCHLAGEN")
if "--aus" in sys.argv:
    d = sys.argv[sys.argv.index("--aus") + 1]; os.makedirs(d, exist_ok=True); json.dump({"faelle": fall, "bestanden": bool(ok)}, open(os.path.join(d, "synthetisch.json"), "w"), indent=1)
sys.exit(0 if ok else 1)
