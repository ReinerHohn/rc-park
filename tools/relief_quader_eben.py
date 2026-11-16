#!/usr/bin/env python3
"""relief_quader_eben.py <relief.npz> <aus.npz> --feld u0 u1 z0 z1 [--feld ...] - glatt behauene Eckquader: Steinzellen eines Feldes auf EINE Hoehe.

Warum (Nutzer 16.11.2026, 3D-Seite: Beulen neben der Suedhr): oberhalb des Gesimses sind die Eckquader des Schwabentors glatt behauen (feines Fassadenbild),
das Scan-Relief zeigt dort nur Rauschen (Beulen bis 15 cm). Die verzahnte KONTUR Stein/Putz stammt aus der Fotofarbe (Maske 'putz' von tools/relief_putz.py) und
bleibt; nur die Flaeche wird eben: alle Nicht-Putz-Zellen im Feld = Median dieser Zellen (mindestens 2 cm ueber dem Putz, sonst zeichnet sich die Kontur nicht ab).
Fugen zwischen den Quadern fehlen (nicht gemessen). Bruchstein (unten) NICHT so behandeln - dort ist das Relief echt.
"""
import sys, os, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("aus"); ap.add_argument("--feld", nargs=4, type=float, action="append", required=True); ap.add_argument("--min_vor_putz", type=float, default=0.02); a = ap.parse_args()
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float64); H, W = rel.shape; px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"])
    if "putz" not in Z: print("keine Putzmaske - erst tools/relief_putz.py"); return 2
    ii, jj = np.mgrid[0:H, 0:W]; U = u0 + (jj + 0.5) * px; ZZ = z0 + (H - 1 - ii + 0.5) * px; niv = float(Z.get("putz_niveau_m", 0.0)); eben = np.zeros((H, W), bool)
    for f0, f1, g0, g1 in a.feld:
        m = (U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1) & ~Z["putz"]
        if m.sum() < 20: continue
        h = max(float(np.median(rel[m & (rel != 0.0)])) if (m & (rel != 0.0)).sum() > 20 else 0.0, niv + a.min_vor_putz); rel[m] = h; eben |= m
        print(f"Feld u {f0}-{f1}, z {g0}-{g1}: {m.sum() * px * px:.1f} m2 Stein eben auf {h * 100:+.1f} cm (Putz {niv * 100:+.1f} cm)")
    Z["rel"] = rel.astype(np.float32); Z["quader_eben"] = eben; np.savez_compressed(a.aus, **Z)
    lx = np.gradient(rel, px, axis=1); lz = np.gradient(rel, px, axis=0); s = np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    im[eben] = (im[eben] * np.array([1.0, 0.85, 0.85])).astype(np.uint8); cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", cv2.resize(im, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))


if __name__ == "__main__":
    sys.exit(main())
