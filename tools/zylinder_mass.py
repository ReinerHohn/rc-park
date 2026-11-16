#!/usr/bin/env python3
"""zylinder_mass.py <objekt.json> --achse x y --radius r --mess FOTO u v [--mess FOTO u v ...] [--tri FOTO u v FOTO u v] - Punkte auf einem RUNDEN Bauteil messen.

Warum (Nutzer 16.11.2026: Treppenturm "hat auch kleine Fensterchen" / "Warum hast du es nicht automatisch gemacht?"): foto_mass.py misst nur auf Ebenen, die Fenstererkennung
nur auf ebenen Fassaden - runde Tuerme fielen durch alle Werkzeuge, die Schlitze standen als ANNAHME im Modell. Hier: Sehstrahl des Pixels (Kamera K-<FOTO>.json) mit dem
senkrechten Zylinder (Achse x y, Radius r) schneiden -> Punkt (x, y, z) und Azimut um die Achse (Grad, 0 = +x, 90 = +y). Dieselbe Stelle in zwei Fotos muss auf wenige cm
uebereinstimmen (Gegenprobe). --tri: Punkt, der NICHT auf dem Zylinder liegt (Spitze, Knauf), aus zwei Fotos triangulieren.
Pixel = Originalfoto. Ausgabe als Zeilen und <messprotokoll>/Z-zylinder-<zeit>.json.
"""
import sys, os, json, time, numpy as np, cv2
a = sys.argv; od = os.path.dirname(os.path.abspath(a[1])); mp = os.path.join(od, "messprotokoll")
ax = [float(v) for v in a[a.index("--achse") + 1:a.index("--achse") + 3]]; r = float(a[a.index("--radius") + 1])
def strahl(foto, u, v):
    kf = [f for f in os.listdir(mp) if f.startswith("K-") and foto in f][0]; K = json.load(open(os.path.join(mp, kf)))["kamera"]; R = cv2.Rodrigues(np.array(K["rvec"]))[0]
    d = np.array([(u - K["cx"]) / K["f_px"], (v - K["cy"]) / K["f_px"], 1.0]) @ R; return -R.T @ np.array(K["t"]), d / np.linalg.norm(d)
out = []; i = 2
while i < len(a):
    if a[i] == "--mess":
        C, d = strahl(a[i + 1], float(a[i + 2]), float(a[i + 3])); A_ = d[0] ** 2 + d[1] ** 2; B_ = 2 * ((C[0] - ax[0]) * d[0] + (C[1] - ax[1]) * d[1]); C_ = (C[0] - ax[0]) ** 2 + (C[1] - ax[1]) ** 2 - r * r; D_ = B_ * B_ - 4 * A_ * C_
        if D_ < 0: print(f"{a[i + 1][-24:]} ({a[i + 2]}, {a[i + 3]}): Strahl trifft den Zylinder nicht"); i += 4; continue
        P = C + (-B_ - np.sqrt(D_)) / (2 * A_) * d; az = float(np.degrees(np.arctan2(P[1] - ax[1], P[0] - ax[0]))); out.append(dict(foto=a[i + 1], px=[float(a[i + 2]), float(a[i + 3])], punkt=np.round(P, 3).tolist(), azimut=round(az, 1)))
        print(f"{a[i + 1][-24:]} ({a[i + 2]}, {a[i + 3]}): x {P[0]:.2f} y {P[1]:.2f} z {P[2]:.2f}, Azimut {az:.0f} Grad"); i += 4
    elif a[i] == "--tri":
        (C1, d1), (C2, d2) = strahl(a[i + 1], float(a[i + 2]), float(a[i + 3])), strahl(a[i + 4], float(a[i + 5]), float(a[i + 6])); l = np.linalg.lstsq(np.c_[d1, -d2], C2 - C1, rcond=None)[0]; P1, P2 = C1 + l[0] * d1, C2 + l[1] * d2
        out.append(dict(tri=[a[i + 1], a[i + 4]], punkt=np.round((P1 + P2) / 2, 3).tolist(), luecke_m=round(float(np.linalg.norm(P1 - P2)), 3))); print(f"Triangulation: {np.round((P1 + P2) / 2, 2).tolist()}, Strahlabstand {np.linalg.norm(P1 - P2):.2f} m"); i += 7
    else: i += 1
json.dump(dict(achse=ax, radius=r, messungen=out), open(os.path.join(mp, "Z-zylinder-" + time.strftime("%m%d-%H%M%S") + ".json"), "w"), indent=1)
