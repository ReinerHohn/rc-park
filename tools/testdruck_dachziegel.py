#!/usr/bin/env python3
"""testdruck_dachziegel.py - Testplatte: wie sehen Dachdeckungen im Massstab (Standard H0 1:87) auf dem Bambu P1S (0,4-mm-Duese) aus?

Eine Platte, flach gedruckt (Deckung zeigt nach oben -> Ziegelstufen entstehen als Schichtstufen in Z, viel feiner als die Duese in XY).
Vier Felder, am Rand mit 1-4 Kerben markiert:
  1 Biberschwanz massstabsgetreu: Ziegel 18 x 38 cm, sichtbare Reihe 15 cm -> 2,07 x 1,72 mm; Reihenstufe REIHE_STUFE (Keil, Unterkante sichtbar),
    Stossfugen versetzt (Breite FUGE).
  2 Biberschwanz 2-fach ueberhoeht (Breite/Reihe x 2, Stufe x 1,6) - zum Vergleich, ob massstabsgetreu im Druck ueberhaupt lesbar ist.
  3 Falzziegel/Pfanne: 26 x 33 cm sichtbar -> 2,99 x 3,79 mm, Reihenstufe + Laengswulst je Ziegel.
  4 Kupfer-Stehfalz (Martinstor-Helm): Falz alle 50 cm -> 5,75 mm, Rippe FALZ_B breit x FALZ_H hoch, quer Hafter-Stoesse alle 2 m.
Alle Masse als Argumente; Werte (m, real) werden mit 1000/massstab in mm umgerechnet. Untergrenzen fuer 0,4 mm Duese: Rippen >= 0,45 mm breit.
  ~/.venvs/rcpark/bin/python tools/testdruck_dachziegel.py modelle/export/h0/dachziegel_test.stl [--massstab 87]
"""
import sys, argparse, numpy as np
from manifold3d import Manifold as M, CrossSection as CS

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("aus"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--feld", nargs=2, type=float, default=[30.0, 20.0], help="Feldgroesse mm"); ap.add_argument("--basis", type=float, default=1.2, help="Plattendicke mm")
    ap.add_argument("--reihe_stufe", type=float, default=0.24, help="Hoehe der Ziegelunterkante mm (3 Schichten a 0,08)"); ap.add_argument("--fuge", type=float, default=0.30)
    ap.add_argument("--falz_b", type=float, default=0.50); ap.add_argument("--falz_h", type=float, default=0.40); a = ap.parse_args()
    k = 1000.0 / a.massstab; FX, FY = a.feld; B = a.basis; S = a.reihe_stufe; G = a.fuge; RAND = 2.0
    teile = []
    def platte(x0, y0): return M.cube((FX, FY, B)).translate((x0, y0, 0))
    def biber(x0, y0, w, e, stufe):
        """Reihen quer (x), Fallrichtung -y: je Reihe ein Keil von stufe (unten, sichtbare Kante) auf 0 (oben, unter der naechsten Reihe), Stossfugen versetzt."""
        out = []
        n = int(FY / e)
        for i in range(n):
            ya = y0 + i * e
            keil = CS([[(0, 0), (e, 0), (e, 0.02), (0, stufe)]])                                  # Querschnitt in (y, z): vorne hoch, hinten flach
            p = M.extrude(keil, FX).rotate((90, 0, 90)).translate((x0, ya, B))                      # extrudiert entlang x
            out.append(p)
            off = (w / 2) if i % 2 else 0.0                                                           # Verband: halber Ziegel versetzt
            xs = np.arange(x0 - off + w, x0 + FX, w)
            for x in xs:
                if x0 + 0.3 < x < x0 + FX - 0.3: out.append(("fuge", M.cube((G, e, stufe + 0.3)).translate((x - G / 2, ya, B - 0.01))))
        return out
    def pfanne(x0, y0, w, e, stufe):
        out = biber(x0, y0, w, e, stufe)
        for x in np.arange(x0 + w / 2, x0 + FX - 0.5, w):                                            # Laengswulst je Ziegel (rund, 0,6 mm breit)
            out.append(M.cylinder(FY, 0.3, 0.3, 12).rotate((-90, 0, 0)).translate((x, y0, B + stufe * 0.4)))
        return out
    def stehfalz(x0, y0, p, fb, fh, stoss):
        out = [M.cube((fb, FY, fh)).translate((x, y0, B)) for x in np.arange(x0 + p / 2, x0 + FX - fb, p)]
        for y in np.arange(y0 + stoss, y0 + FY - 0.5, stoss): out.append(M.cube((FX, 0.35, 0.12)).translate((x0, y, B)))   # Querstoesse (flach, 1-2 Schichten)
        return out
    felder = [(0, 0, lambda x, y: biber(x, y, 0.18 * k, 0.15 * k, S)),
              (FX + RAND, 0, lambda x, y: biber(x, y, 2 * 0.18 * k, 2 * 0.15 * k, 1.6 * S)),
              (0, FY + RAND, lambda x, y: pfanne(x, y, 0.26 * k, 0.33 * k, S)),
              (FX + RAND, FY + RAND, lambda x, y: stehfalz(x, y, 0.50 * k, a.falz_b, a.falz_h, 2.0 * k))]
    adds, cuts = [M.cube((2 * FX + RAND, 2 * FY + RAND, B)).translate((0, 0, 0))], []
    for i, (x0, y0, fn) in enumerate(felder, 1):
        for t in fn(x0, y0):
            (cuts if isinstance(t, tuple) else adds).append(t[1] if isinstance(t, tuple) else t)
        for j in range(i):                                                                             # Kerben 1-4 an der Vorderkante des Feldes
            cuts.append(M.cube((0.8, 1.5, B + 2)).translate((x0 + 1.5 + j * 1.6, y0 - 0.01 if y0 == 0 else y0 + FY - 1.49, -0.5)))
    body = M.batch_boolean(adds, __import__("manifold3d").OpType.Add) - M.batch_boolean(cuts, __import__("manifold3d").OpType.Add)
    mesh = body.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    import struct
    with open(a.aus, "wb") as f:
        f.write(b"dachziegel_test rc-park".ljust(80, b" ")); f.write(struct.pack("<I", len(F)))
        for t in F:
            p = V[t]; n = np.cross(p[1] - p[0], p[2] - p[0]); n = n / (np.linalg.norm(n) + 1e-12)
            f.write(struct.pack("<12fH", *n, *p[0], *p[1], *p[2], 0))
    lo, hi = V.min(0), V.max(0)
    print(f"{a.aus}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.2f} mm, {len(F)} Dreiecke, Volumen {body.volume():.0f} mm3, Genus {body.genus()}")
    print(f"  Biberschwanz 1:{a.massstab:.0f}: {0.18*k:.2f} x {0.15*k:.2f} mm, Stufe {S} | 2-fach: {0.36*k:.2f} x {0.30*k:.2f}, Stufe {1.6*S:.2f} | Pfanne {0.26*k:.2f} x {0.33*k:.2f} | Stehfalz alle {0.5*k:.2f} mm, {a.falz_b} x {a.falz_h}")

if __name__ == "__main__":
    main()
