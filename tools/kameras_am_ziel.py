#!/usr/bin/env python3
"""kameras_am_ziel.py - ALLE kalibrierten Kameras eines Objekts nach Aufloesung am Ziel sortieren (VOR jeder Aufnahmebitte laufen lassen).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/kameras_am_ziel.py modelle/<objekt>/objekt.json --ziel u n z [--nx 0.3338 --ny 0.9426] [--top 12]
Ausgabe je Kamera: Abstand, px/m (f/Tiefe), Ziel im Bild?, Azimut/Hoehenwinkel der Blickrichtung zum Ziel. Anlass 13.11.2026: Nahfotos (n11_05/06, 625-718 px/m) waren
vorhanden, aber 'keine Nahfotos' wurde behauptet und ein Aufnahmeauftrag geschrieben. Reine Geometrie, keine Bildzugriffe."""
import sys, os, json, glob, math, numpy as np, cv2
a = sys.argv[1:]
if len(a) < 4 or "--ziel" not in a: sys.exit(__doc__)
opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
i = a.index("--ziel"); u, n, z = (float(v) for v in a[i + 1:i + 4]); nx, ny = opt("--nx", 0.3338), opt("--ny", 0.9426); top = int(opt("--top", 12))
od = os.path.dirname(os.path.abspath(a[0])); P = np.array([u * ny + n * nx, -u * nx + n * ny, z]); rows = []
for p in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
    try: k = json.load(open(p))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float)
    except Exception: continue
    sh = np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float); C = -R.T @ t - sh; x = R @ (P + sh) + t
    if x[2] <= 0: continue
    px = (k["f_px"] * x[0] / x[2] + k["cx"], k["f_px"] * x[1] / x[2] + k["cy"]); W, H = (k.get("bild") or [0, 0])[:2]; inb = bool(W) and 0 < px[0] < W and 0 < px[1] < H
    d = P - C; az = math.degrees(math.atan2(d[0] * ny - d[1] * nx, d[0] * nx + d[1] * ny)); el = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    rows.append((k["f_px"] / x[2], os.path.basename(p)[:-5], float(np.linalg.norm(d)), inb, az, el))
rows.sort(reverse=True); print(f"{len(rows)} Kameras mit Ziel vor der Kamera; Top {top} nach px/m (nur 'im Bild' zaehlt):")
for r in [r for r in rows if r[3]][:top]: print(f"  {r[1]:14s} {r[0]:6.0f} px/m  Abstand {r[2]:5.1f} m  Azimut {r[4]:6.1f}  Hoehe {r[5]:5.1f} Grad")
