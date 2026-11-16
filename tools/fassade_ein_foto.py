#!/usr/bin/env python3
"""fassade_ein_foto.py <fassaden.json> <nr> <objekt.json> <FOTO> <aus.png> - entzerrtes Fassadenbild einer Wand aus EINEM kalibrierten Foto.

Fuer Waende, die kein Foto des SfM zeigt (Quellen-Blindheit). Nutzer 16.11.2026: "Nein, nicht spiegeln ... Du musst Fotos suchen von dieser ungesehenen Seite."
Ablauf fuer eine ungesehene Seite:
  1. Fotobestand (auch nicht registrierte Fremdfotos: commons/online/Videobilder) nach Ansichten dieser Seite durchsuchen (Kontaktbogen ansehen).
  2. Kamera dieses Fotos aus >= 8 gut verteilten, bereits GEMESSENEN Modellpunkten loesen (Knauf, Traufecken, Uhr, Fenster, Gesims ...) -> messprotokoll/K-<FOTO>.json;
     Restfehler in Metern angeben (px / (f / Abstand)).
  3. Dieses Werkzeug: jede Rasterzelle der Fassade (fassaden.json: o, d, raster) ins Foto projizieren -> Bild im selben Raster wie ortho_fNN_fein.png.
     Danach normale Kette: relief_einsatz.py --leer (kein Netz) -> relief_putz.py -> steine_aus_foto.py; Fenster ueber foto_mass.py auf der Wandebene.
Keine Verdeckungspruefung: was vor der Wand steht (Nachbardach), erscheint im Bild - Feld entsprechend waehlen.
"""
import sys, os, json, glob, numpy as np, cv2
fj, nr, oj, foto, aus = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
F = json.load(open(fj))["fassaden"][nr]; R = F["raster"]; o = np.array(F["o"]); d = np.array(F["d"]); od = os.path.dirname(os.path.abspath(oj)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(oj))
kf = [f for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")) if foto in os.path.basename(f)][0]; K = json.load(open(kf))["kamera"]
im = cv2.imread([f for f in glob.glob(os.path.join(root, obj["fotos_dir"], "*")) if foto in os.path.basename(f)][0])
jj, ii = np.meshgrid(np.arange(R["nu"]), np.arange(R["nz"])); u = R["u0"] + (jj + 0.5) * R["zelle"]; z = R["z1"] - (ii + 0.5) * R["zelle"]
X = np.stack([o[0] + u * d[0], o[1] + u * d[1], z], -1).reshape(-1, 3); Rm = cv2.Rodrigues(np.array(K["rvec"]))[0]; p = X @ Rm.T + np.array(K["t"]); x = p[:, 0] / p[:, 2]; y = p[:, 1] / p[:, 2]; f_ = 1 + float(K.get("k1") or 0) * (x * x + y * y)
mx = (K["f_px"] * x * f_ + K["cx"]).astype(np.float32).reshape(u.shape); my = (K["f_px"] * y * f_ + K["cy"]).astype(np.float32).reshape(u.shape)
bild = cv2.remap(im, mx, my, cv2.INTER_LINEAR, borderValue=(0, 0, 0)); cv2.imwrite(aus, bild)
print(f"{aus}: {R['nu']}x{R['nz']} Zellen a {R['zelle'] * 100:.0f} cm, Fotoaufloesung an der Wand ~{np.median(p[:, 2]) / K['f_px'] * 100:.1f} cm/px, {100 * (bild.max(2) > 8).mean():.0f} % mit Daten")
