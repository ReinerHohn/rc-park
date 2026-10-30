#!/usr/bin/env python3
"""fassade_entzerren.py — robuste fronto-parallele Entzerrung einer Fassade.

Fluchtpunkte per Eigenvektor (kein RANSAC-Zufall): Linien in vertikal/horizontal
clustern, VP = kleinster Eigenvektor von sum(l·lᵀ). Homographie schickt beide VPs
ins Unendliche (affin entzerrt) + metrische Korrektur (die zwei Richtungen senkrecht).
Danach ist die Fassade gerade → Pixel ∝ Meter, Kanten mit Lineal messbar.

  python3 tools/fassade_entzerren.py --img foto.jpg --out rect.png [--crop x0,y0,x1,y1(frac)]
"""
import argparse
import numpy as np
import cv2


def lines(gray, min_len):
    lsd = cv2.createLineSegmentDetector()
    segs = lsd.detect(gray)[0]
    if segs is None:
        return np.empty((0, 4))
    S = segs.reshape(-1, 4)
    Ln = np.hypot(S[:, 2]-S[:, 0], S[:, 3]-S[:, 1])
    return S[Ln >= min_len]


def homog_line(s):
    l = np.cross([s[0], s[1], 1.0], [s[2], s[3], 1.0])
    return l / (np.linalg.norm(l[:2]) + 1e-12)


def vp_eig(segs):
    """VP = Richtung v mit min sum (lᵀv)² → kleinster Eigenvektor von Σ l lᵀ."""
    if len(segs) < 2:
        return None
    L = np.array([homog_line(s) for s in segs])
    M = L.T @ L
    w, V = np.linalg.eigh(M)
    v = V[:, 0]
    return v / v[2] if abs(v[2]) > 1e-9 else None


def rectify(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    S = lines(g, min_len=max(30, img.shape[1]//40))
    ang = np.degrees(np.arctan2(S[:, 3]-S[:, 1], S[:, 2]-S[:, 0]))
    a = np.abs(((ang+90) % 180)-90)
    vert = S[a > 72]; horiz = S[a < 18]
    vpv, vph = vp_eig(vert), vp_eig(horiz)
    if vpv is None or vph is None:
        return img, None, (len(vert), len(horiz))
    H, W = img.shape[:2]
    vanish = np.cross(vpv, vph)
    Hp = np.array([[1, 0, 0], [0, 1, 0], vanish/(vanish[2]+1e-12)])
    # METRISCH: die zwei VP-Richtungen nach Hp auf X-/Y-Achse abbilden (Scherung/Drehung weg)
    da = Hp @ vph; db = Hp @ vpv
    da = da[:2]/(np.linalg.norm(da[:2])+1e-12)
    db = db[:2]/(np.linalg.norm(db[:2])+1e-12)
    Mcols = np.array([[da[0], db[0]], [da[1], db[1]]])
    try:
        A2 = np.linalg.inv(Mcols)                 # da->(1,0), db->(0,1)
    except np.linalg.LinAlgError:
        A2 = np.eye(2)
    Aff = np.array([[A2[0, 0], A2[0, 1], 0], [A2[1, 0], A2[1, 1], 0], [0, 0, 1]])
    Hp = Aff @ Hp
    # bbox durch Hp, dann auf Bildgröße skalieren (Seitenverhältnis grob halten)
    corners = np.float32([[0, 0], [W, 0], [W, H], [0, H]]).reshape(-1, 1, 2)
    p = cv2.perspectiveTransform(corners, Hp).reshape(-1, 2)
    p -= p.min(0)
    sc = min(1600/max(p[:, 0].max(), 1), 1600/max(p[:, 1].max(), 1))
    p2 = p*sc
    Ht = np.array([[sc, 0, 0], [0, sc, 0], [0, 0, 1]]) @ Hp
    wO, hO = int(p[:, 0].max()*sc), int(p[:, 1].max()*sc)
    out = cv2.warpPerspective(img, Ht, (max(wO, 50), max(hO, 50)))
    return out, Ht, (len(vert), len(horiz))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1 als Anteile 0..1 (vor Entzerrung)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    img = cv2.imread(a.img)
    if a.crop:
        x0, y0, x1, y1 = [float(v) for v in a.crop.split(",")]
        H, W = img.shape[:2]
        img = img[int(y0*H):int(y1*H), int(x0*W):int(x1*W)]
    rect, Ht, (nv, nh) = rectify(img)
    cv2.imwrite(a.out, rect)
    print(f"Linien: {nv} vertikal, {nh} horizontal → entzerrt {rect.shape[1]}x{rect.shape[0]}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
