#!/usr/bin/env python3
"""foto_rektifizieren.py — Perspektive aus einem Fassaden-Foto entzerren (2 Fluchtpunkte).

Standard-Bildverarbeitung: Kanten (Canny) -> Linien (Hough) -> nach Richtung
trennen (horizontal = Deck/Gesims/Lager, vertikal = Pfeilerkanten) -> je ein
Fluchtpunkt (robustes Schnittpunkt-Mittel) -> rektifizierende Homographie, die
beide Fluchtpunkte nach Unendlich schickt (Horizontale wirklich horizontal,
Vertikale wirklich vertikal). Danach sind gleich große Bögen auch gleich groß.

  python3 tools/foto_rektifizieren.py --foto daten/ravenna/fotos/rv_panorama.jpg \\
      --crop 700,1950,8300,3000 --out daten/ravenna/rv_rektifiziert.png
"""
import argparse, numpy as np, cv2


def vanishing_point(lines):
    """robuster Schnittpunkt vieler Linien (homogen, SVD)."""
    L = []
    for x1, y1, x2, y2 in lines:
        p1 = np.array([x1, y1, 1.0]); p2 = np.array([x2, y2, 1.0])
        L.append(np.cross(p1, p2))
    L = np.array(L)
    _, _, V = np.linalg.svd(L)
    v = V[-1]; return v / v[2] if abs(v[2]) > 1e-9 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True)
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1 (Fassade eingrenzen)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    img = cv2.imread(a.foto)
    if a.crop:
        x0, y0, x1, y1 = [int(v) for v in a.crop.split(",")]
        img = img[y0:y1, x0:x1]
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    segs = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=120,
                           minLineLength=W//12, maxLineGap=25)
    if segs is None:
        raise SystemExit("keine Linien gefunden")
    segs = segs.reshape(-1, 4)
    ang = np.degrees(np.arctan2(segs[:, 3]-segs[:, 1], segs[:, 2]-segs[:, 0]))
    hor = segs[(np.abs(ang) < 25)]                 # Deck/Gesims/Lager
    ver = segs[(np.abs(np.abs(ang)-90) < 25)]      # Pfeilerkanten
    print(f"Linien: {len(segs)} gesamt, {len(hor)} horizontal, {len(ver)} vertikal")
    vph = vanishing_point(hor); vpv = vanishing_point(ver)
    print(f"Fluchtpunkt horizontal {vph[:2].round(0)}  vertikal {vpv[:2].round(0)}")

    # Homographie: Zeile am Horizont (durch beide VP) -> ins Unendliche
    l_inf = np.cross(vph, vpv)                      # Bild der unendlichen Geraden
    l_inf = l_inf / l_inf[2] if abs(l_inf[2]) > 1e-9 else l_inf
    Hp = np.array([[1, 0, 0], [0, 1, 0], [l_inf[0], l_inf[1], l_inf[2]]], float)
    # auf Bildbereich normieren (Ecken mappen, dann in Ausgabe skalieren)
    corners = np.array([[0, 0], [W, 0], [W, H], [0, H]], float).reshape(-1, 1, 2)
    warped_c = cv2.perspectiveTransform(corners, Hp).reshape(-1, 2)
    mn = warped_c.min(0); mx = warped_c.max(0); sc = min(1800/(mx[0]-mn[0]), 1200/(mx[1]-mn[1]))
    S = np.array([[sc, 0, -mn[0]*sc], [0, sc, -mn[1]*sc], [0, 0, 1]])
    rect = cv2.warpPerspective(img, S @ Hp, (int((mx[0]-mn[0])*sc), int((mx[1]-mn[1])*sc)))
    cv2.imwrite(a.out, rect)
    print(f"rektifiziert -> {a.out}  ({rect.shape[1]}x{rect.shape[0]})")


if __name__ == "__main__":
    main()
