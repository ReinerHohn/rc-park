#!/usr/bin/env python3
"""haufen_am_foto.py - Wolkenhaufen aus dem Grundriss-Tor AM FOTO klaeren (Regel: Haufen auf der Strasse nicht modellieren, erst am Foto ansehen).

Nimmt die Haufen aus audit/wolke_grundriss.json (strasse.haufen: mitte, ausdehnung), sucht je Haufen die Wolkenpunkte (z > 0,7 m ueber Rahmen-Null)
und zeichnet sie in die Fotos, die sie am besten sehen (nah, viele Punkte im Bild, verschiedene Richtungen). Ausgabe: audit/haufen_<nr>.jpg
(je Haufen 3 Fotos nebeneinander, Punkte rot, Ausschnitt um die Punkte) - ANSEHEN: Mauer/Nachbarhaus/Baum/Auto = echte Umgebung (nicht modellieren,
kein Lagefehler); Teil des Zielgebaeudes an falscher Stelle = falsch verortetes Teilnetz.
  /media/oem/scan/venv-seg/bin/python -I tools/haufen_am_foto.py modelle/<obj>/objekt.json <SFM-AUSRICHTUNG.json> --wolke punkte_modell.npy --bilder ORDNER [--max 3]
"""
import sys, os, json, glob, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ausrichtung"); ap.add_argument("--wolke", required=True); ap.add_argument("--bilder", required=True)
    ap.add_argument("--max", type=int, default=3); ap.add_argument("--je", type=int, default=3); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); H = json.load(open(os.path.join(od, "audit", "wolke_grundriss.json")))["strasse"]["haufen"][:a.max]
    K = json.load(open(a.ausrichtung))["kameras"]; P = np.load(a.wolke, mmap_mode="r"); P = np.asarray(P[::max(1, len(P) // 2000000)], np.float32)
    for nr, h in enumerate(H):
        m = np.array(h["mitte"], float); r = 0.5 * np.array(h["ausdehnung_m"], float) + 1.0
        X = P[(np.abs(P[:, 0] - m[0]) < r[0]) & (np.abs(P[:, 1] - m[1]) < r[1]) & (P[:, 2] > 0.7)].astype(float)
        if len(X) < 50: print(f"Haufen {nr}: nur {len(X)} Punkte ueber 0,7 m"); continue
        zen = np.r_[m, np.median(X[:, 2])]; kand = []
        for n, k in K.items():
            R = np.array(k["R"]); t = np.array(k["t"]); Xc = X @ R.T + t; z = Xc[:, 2]; ok = z > 1.0
            if ok.sum() < 0.5 * len(X): continue
            f, cx, cy = k["f_px_original"], k["cx"], k["cy"]; k1 = (k.get("k") or [0.0])[0]; x = Xc[ok, 0] / z[ok]; y = Xc[ok, 1] / z[ok]; d = 1 + k1 * (x * x + y * y)
            u = f * x * d + cx; v = f * y * d + cy; W, Hh = float(k["bild_b"]), float(k["bild_h"]); im = (u > 0) & (u < W) & (v > 0) & (v < Hh)
            C = -R.T @ t; dist = float(np.linalg.norm(C - zen))
            if im.mean() > 0.6 and 4 < dist < 60: kand.append((dist, n, C, u[im], v[im]))
        kand.sort(key=lambda c: c[0]); wahl = []
        for c in kand:                                                             # verschiedene Blickrichtungen (> 25 Grad auseinander)
            ri = (c[2] - zen)[:2]; ri /= np.linalg.norm(ri) + 1e-9
            if all(np.degrees(np.arccos(np.clip(ri @ w[5], -1, 1))) > 25 for w in wahl): wahl.append(c + (ri,))
            if len(wahl) >= a.je: break
        if not wahl: print(f"Haufen {nr} bei {h['mitte']}: kein Foto sieht ihn (60 % der Punkte im Bild, 4-60 m)"); continue
        teile = []
        for dist, n, C, u, v, _ in wahl:
            g = glob.glob(os.path.join(a.bilder, glob.escape(n) + ".*")); bild = cv2.imread(g[0], cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION) if g else None
            if bild is None: continue
            s = bild.shape[1] / float(K[n]["bild_b"]); u = u * s; v = v * s; roh = bild.copy()
            for x, y in zip(u[::max(1, len(u) // 4000)].astype(int), v[::max(1, len(v) // 4000)].astype(int)): cv2.circle(bild, (x, y), max(2, bild.shape[1] // 700), (0, 0, 255), -1)
            x0, x1 = np.percentile(u, [2, 98]); y0, y1 = np.percentile(v, [2, 98]); rx = max(x1 - x0, 200) * 0.6; ry = max(y1 - y0, 200) * 0.6
            a0, a1 = int(max(0, x0 - rx)), int(min(bild.shape[1], x1 + rx)); b0, b1 = int(max(0, y0 - ry)), int(min(bild.shape[0], y1 + ry))
            paar = np.hstack([cv2.resize(q[b0:b1, a0:a1], (600, int(600 * (b1 - b0) / max(a1 - a0, 1)))) for q in (roh, bild)])
            cv2.putText(paar, f"{n[-28:]}  {dist:.0f} m", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2); teile.append(paar)
        if not teile: continue
        hh = min(t.shape[0] for t in teile); blatt = np.vstack([cv2.resize(t, (1200, int(t.shape[0]))) [:max(hh, 300)] if False else t for t in teile])
        aus = os.path.join(od, "audit", f"haufen_{nr}.jpg"); cv2.imwrite(aus, blatt, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"Haufen {nr} bei {h['mitte']} ({h['punkte']} Punkte, Hoehe Median {np.median(X[:, 2]):.1f} m, max {np.percentile(X[:, 2], 99):.1f} m): {len(teile)} Fotos -> {aus}")


if __name__ == "__main__":
    main()
