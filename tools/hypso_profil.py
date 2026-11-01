#!/usr/bin/env python3
"""hypso_profil.py - DIAGNOSE statt Gesamtnote: Flaeche je Hoehenstufe, Laser (DOM1) gegen Modell(e), Stufe fuer Stufe.

Die Hypsometrie in `optimierung_validieren.py` gibt eine Zahl ("14,3 %"). Die sagt nicht, WO das Modell abweicht.
Dieses Werkzeug druckt je Hoehenstufe die Flaeche im 9-m-Umkreis: Laser, Modell, Differenz in m2 und %.
Damit laesst sich ein Widerspruch (z. B. "Foto will die Traufe 2 m hoeher, Laser verbietet es") an der Stelle pruefen,
an der er entsteht - und nicht an einer Summe, in der sich Fehler gegenseitig aufheben.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/hypso_profil.py modell1.stl [modell2.stl ...] [--stufen 20,24,...]
Das Modell wird wie in optimierung_validieren gedreht/verschoben (beste Lage aus einem groben Raster), damit der Vergleich fair ist.
Grenzen: DOM1 ist 1-m-Raster von oben; Flaechen < ~3 m2 und senkrechte Strukturen sind dort unsicher (siehe Quellen-Matrix).
"""
import sys, os, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DOM = "/media/oem/scan/tmp/mt_dom/mt_win.npy"; N = 60; GELAENDE = 277.98
ref = np.load(DOM) - GELAENDE
yy, xx = np.mgrid[:N, :N]; PR = np.unravel_index(np.argmax(ref), ref.shape)

def flaeche(A, pk, t, r=9.0):
    return int(((A > t) & (np.hypot(yy - pk[0], xx - pk[1]) <= r)).sum())

def punkte(stl):
    m = trimesh.load(stl); m.apply_scale(87 / 1000.0)
    v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=0.3, max_iter=14)
    return v[f].mean(1)

def hoehenfeld(P, ang, dx, dy):
    c, s = np.cos(np.radians(ang)), np.sin(np.radians(ang))
    x = c * P[:, 0] - s * P[:, 1] + dx; y = s * P[:, 0] + c * P[:, 1] + dy
    ix = np.floor(x + N / 2).astype(int); iy = np.floor(N / 2 - y).astype(int)
    ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
    H = np.zeros((N, N)); np.maximum.at(H, (iy[ok], ix[ok]), P[ok, 2]); return H

def beste_lage(P, stufen):
    """Drehung/Phase, die die Summe der Abweichungen minimiert - alle Lagen in EINEM GPU-Durchgang (render_kern.hypso_lagen)."""
    import render_kern as RK
    R = [max(flaeche(ref, PR, t), 1) for t in stufen]
    lagen = [(ang, dx, dy) for ang in range(86, 113, 2) for dx in np.arange(-1, 1.01, 0.5) for dy in np.arange(-1, 1.01, 0.5)]
    A = RK.hypso_lagen(P, stufen, lagen)                                  # (Lagen, Stufen)
    e = np.mean(np.abs(A - np.array(R)[None, :]) / np.array(R)[None, :], axis=1)
    i = int(np.argmin(e)); ang, dx, dy = lagen[i]
    H = hoehenfeld(P, ang, dx, dy); pk = np.unravel_index(np.argmax(H), H.shape)
    return (float(e[i]), ang, dx, dy, H, pk)

def main():
    a = sys.argv[1:]
    stufen = [float(x) for x in a[a.index("--stufen") + 1].split(",")] if "--stufen" in a else list(np.arange(20, 56, 2.0))
    stls = [x for x in a if x.endswith(".stl")]
    R = [flaeche(ref, PR, t) for t in stufen]
    # Messunsicherheit des LASERS selbst: Umkreismitte +-1 m und Radius 8,5/9/9,5 m -> Streuung der Flaeche je Stufe
    unsich = []
    for t in stufen:
        w = [flaeche(ref, (PR[0] + a, PR[1] + b), t, r) for a in (-1, 0, 1) for b in (-1, 0, 1) for r in (8.5, 9.0, 9.5)]
        unsich.append((min(w), max(w)))
    # GEMEINSAME Lage: beste Lage des ERSTEN Modells, fuer alle anderen uebernommen (sonst vergleicht man verschiedene Drehungen)
    e0, ang, dx, dy, _, _ = beste_lage(punkte(stls[0]), stufen)
    print(f"Gemeinsame Lage (aus {stls[0].split('/')[-1]}): Drehung {ang} Grad, Phase {dx}/{dy}, Mittelabweichung {e0*100:.1f} %")
    sp = []
    for stl in stls:
        H = hoehenfeld(punkte(stl), ang, dx, dy); pk = np.unravel_index(np.argmax(H), H.shape)
        sp.append((stl.split("/")[-1][:-4], [flaeche(H, pk, t) for t in stufen]))
    print("\n Stufe |     Laser (min-max) |" + "".join(f" {n[:14]:>14s} |" for n, _ in sp))
    for i, t in enumerate(stufen):
        lo, hi = unsich[i]; zeile = f" {t:5.1f} | {R[i]:5d} ({lo:3d}-{hi:3d}) m2 |"
        for _, M in sp:
            d = M[i] - R[i]; aus = "!" if (M[i] < lo or M[i] > hi) else " "                  # ausserhalb der Laser-Unsicherheit = echte Abweichung
            zeile += f" {M[i]:5d} {d:+5d} {aus} |"
        print(zeile)
    print("\n'!' = Modellwert liegt AUSSERHALB der Laser-Unsicherheit (Mitte +-1 m, Radius 8,5-9,5 m) -> echte Abweichung.")
    print("Ohne '!' ist die Stufe mit DOM1 NICHT entscheidbar; bei Flaechen < ~10 m2 ist die Spanne meist so gross wie der Wert selbst.")
    print("Hinweis: DOM1 misst von oben; bei Stufen, in denen ein Dach FLAECHIG liegt, ist die Messung stark; an senkrechten Waenden schwach.")

if __name__ == "__main__":
    main()
