#!/usr/bin/env python3
"""foto_kante_fit.py - senkrechte Bauwerkskante (LoD2-Eckkante) im Vollbild aus einer GROBEN Vorgabe praezise anpassen.

Eingabe je Kante: Ankername, grober Start- und Endpunkt (u, v) im Vollbild (z. B. vom Gitterblatt abgelesen) und die Richtung
des Helligkeitssprungs ("L": Hintergrund links, Bauwerk rechts; "R": umgekehrt). Je Bildzeile wird im Band +-BAND px um die
Vorgabe der staerkste passende Horizontalgradient gesucht, dann eine Gerade robust (RANSAC) angepasst.
Ergebnis: K-<foto>.json "linien": {name: [[u, v], [u, v]]} (2 Punkte auf der Kante) und ein Kontrollbild
messprotokoll/lupe_<foto>/kante_<name>.jpg (ANSEHEN - Zahlen allein gelten nicht).
  python3 tools/foto_kante_fit.py modelle/<objekt>/objekt.json <foto> <name>:<L|R>:<u0>,<v0>:<u1>,<v1> [...]
"""
import sys, os, json, glob, numpy as np, cv2
BAND = 40

def fit(im, u0, v0, u1, v1, seite):
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    if seite == "R": gx = -gx                  # Bauwerk links (hell/dunkel egal): wir nehmen Betrag, Vorzeichen nur zur Bevorzugung
    pts = []
    vs = np.arange(int(min(v0, v1)), int(max(v0, v1)) + 1, 2)
    for v in vs:
        if v < 0 or v >= im.shape[0]: continue
        uc = u0 + (u1 - u0) * (v - v0) / (v1 - v0 if v1 != v0 else 1)
        a, b = int(max(1, uc - BAND)), int(min(im.shape[1] - 2, uc + BAND)); row = np.abs(gx[v, a:b])
        if row.size < 5: continue
        k = int(np.argmax(row)); pts.append((a + k, v, row[k]))
    P = np.array(pts, float)
    # RANSAC: Gerade u = m v + c
    best = None; rng = np.random.default_rng(0)
    for _ in range(600):
        i, j = rng.choice(len(P), 2, replace=False)
        if P[i, 1] == P[j, 1]: continue
        m = (P[j, 0] - P[i, 0]) / (P[j, 1] - P[i, 1]); c = P[i, 0] - m * P[i, 1]
        d = np.abs(P[:, 0] - (m * P[:, 1] + c)); inl = d < 3.0
        if best is None or inl.sum() > best[0]: best = (inl.sum(), inl)
    inl = best[1]; m, c = np.polyfit(P[inl, 1], P[inl, 0], 1)
    vt, vb = float(min(v0, v1)), float(max(v0, v1))
    return [[round(float(m * vt + c), 1), vt], [round(float(m * vb + c), 1), vb]], int(inl.sum()), len(P), P[inl]

def main():
    objp, nr = sys.argv[1], sys.argv[2]; obj = json.load(open(objp))
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    foto = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(foto)
    kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp)) if os.path.exists(kp) else {"foto": nr, "punkte": {}, "linien": {}}
    K.setdefault("linien", {}); K.setdefault("punkte", {}); K["seite"] = obj["fotos"].get(nr, {}).get("seite", K.get("seite", "unbekannt")); K.setdefault("strassenfoto", True)
    ld = os.path.join(od, "messprotokoll", f"lupe_{nr}"); os.makedirs(ld, exist_ok=True)
    for arg in sys.argv[3:]:
        name, seite, p0, p1 = arg.split(":"); u0, v0 = map(float, p0.split(",")); u1, v1 = map(float, p1.split(","))
        line, ninl, n, Pi = fit(im, u0, v0, u1, v1, seite)
        K["linien"][name] = line; K.setdefault("linien_protokoll", {})[name] = dict(vorgabe=[[u0, v0], [u1, v1]], inlier=ninl, zeilen=n, methode="foto_kante_fit Gradient+RANSAC, Band +-%d px" % BAND)
        # Kontrollbild: Streifen um die Kante, 2x vergroessert, Gerade + Inlier
        x0 = int(max(0, min(line[0][0], line[1][0]) - 120)); x1 = int(min(im.shape[1], max(line[0][0], line[1][0]) + 120)); y0, y1 = int(min(v0, v1)) - 40, int(max(v0, v1)) + 40
        crop = im[max(0, y0):y1, x0:x1].copy(); s = min(2.0, 1800 / max(1, crop.shape[0]))
        crop = cv2.resize(crop, None, fx=s, fy=s)
        for u, v, _ in Pi[::3]: cv2.circle(crop, (int((u - x0) * s), int((v - max(0, y0)) * s)), 2, (0, 255, 0), -1)
        cv2.line(crop, (int((line[0][0] - x0) * s), int((line[0][1] - max(0, y0)) * s)), (int((line[1][0] - x0) * s), int((line[1][1] - max(0, y0)) * s)), (0, 0, 255), 1)
        cv2.putText(crop, f"{nr} {name} inl {ninl}/{n}", (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        cv2.imwrite(os.path.join(ld, f"kante_{name}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"{nr} {name}: {line}  Inlier {ninl}/{n}  -> {ld}/kante_{name}.jpg")
    json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
