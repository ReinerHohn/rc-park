#!/usr/bin/env python3
"""test_html_zielgroesse.py - fester Test (23.11.2026, Kettenlauf 1122p: html-Stufe schrieb 20 MB, Artifact-Grenze 16 MB) fuer modell_3d_html.zielgroesse:
  (1) Seite ueber der Zielgroesse -> Wolke und Anzeige-Raster werden selbst verkleinert, Ergebnis <= max_mb, Wolke >= n_min;
  (2) --max_mb 0 bzw. Seite schon klein -> nichts veraendert (gleiche Seite wie vorher);
  (3) unerreichbare Zielgroesse -> Warnung und Ende (keine Endlosschleife), groebste Stufe.
Seitengroessen mit derselben Kodierung wie modell_3d_html (b64 float32/uint32, cm16), synthetisches Netz + Wolke. < 10 s."""
import os, sys, json
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import modell_3d_html as M

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

rng = np.random.default_rng(1)
g = np.linspace(0, 12, 401); UU, ZZ = np.meshgrid(g, g); V0 = np.c_[UU.ravel(), np.zeros(UU.size), ZZ.ravel()].astype(np.float32)    # Wand 12 x 12 m, 3 cm Gitter
i = np.arange(400); I, J = np.meshgrid(i, i); a_ = (J * 401 + I).ravel()
F0 = np.r_[np.c_[a_, a_ + 1, a_ + 402], np.c_[a_, a_ + 402, a_ + 401]].astype(np.uint32)      # 320 000 Dreiecke
X = rng.uniform(0, 12, (400000, 3)).astype(np.float32); C = rng.integers(0, 255, (400000, 3), np.uint8); aufrufe = []


def seite(n, raster):
    aufrufe.append((n, raster)); V, F = V0, F0
    if raster > 0:
        q_, inv_ = np.unique(np.round(V / raster).astype(np.int64), axis=0, return_inverse=True); F = inv_.ravel()[F]; F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
        V = q_.astype(np.float32) * raster
    idx = np.sort(rng.choice(len(X), min(n, len(X)), replace=False))
    D = dict(mv=M.b64(V), mf=M.b64(F.astype(np.uint32)), w=M.cm16(X[idx]), wc=M.b64(C[idx]), wn=len(idx))
    return "<html>" + json.dumps(D) + "</html>", len(F), len(idx)


h0, nf0, nw0 = seite(250000, 0.0); mb0 = len(h0) / 1e6
pruef(mb0 > 9, f"Testseite zu klein ({mb0:.1f} MB) - Test prueft nichts")
html, nf, nw, raster = M.zielgroesse(seite, 250000, 0.0, 4.0, n_min=20000); mb = len(html) / 1e6
pruef(mb <= 4.0, f"Zielgroesse nicht eingehalten: {mb:.1f} MB > 4 MB (Start {mb0:.1f} MB)")
pruef(nw < 250000 and nw >= 20000, f"Wolke nicht sinnvoll verkleinert: {nw}")
pruef(raster > 0 and nf < nf0, f"Netz nicht vergroebert (Raster {raster}, {nf} von {nf0} Dreiecken)")
aufrufe.clear(); h2, nf2, nw2, r2 = M.zielgroesse(seite, 250000, 0.0, 0, n_min=20000)
pruef(len(aufrufe) == 1 and nw2 == 250000 and r2 == 0.0, f"--max_mb 0 hat verkleinert: {aufrufe}")
aufrufe.clear(); h3, _, nw3, r3 = M.zielgroesse(seite, 250000, 0.0, 100.0)
pruef(len(aufrufe) == 1 and nw3 == 250000, f"kleine Seite unnoetig verkleinert: {aufrufe}")
aufrufe.clear(); h4, _, nw4, r4 = M.zielgroesse(seite, 250000, 0.0, 0.05, n_min=20000)
pruef(len(aufrufe) < 41 and nw4 == 20000 and r4 == M.RASTER[-1], f"unerreichbares Ziel: {len(aufrufe)} Runden, Wolke {nw4}, Raster {r4}")
print("FEHLER: " + " | ".join(fehler) if fehler else f"ALLE BESTANDEN (Seite {mb0:.1f} MB -> {mb:.1f} MB <= 4: Wolke {nw}, Raster {raster * 100:.0f} cm; max_mb 0 unveraendert; unerreichbar endet)")
sys.exit(1 if fehler else 0)
