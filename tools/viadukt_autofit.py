#!/usr/bin/env python3
"""viadukt_autofit.py — GESCHLOSSENE SCHLEIFE: Foto messen → Modell anpassen → nachmessen
→ wiederholen bis konvergiert. Die Realität (Foto-Ziele) ist fix; die Generator-Parameter
werden iterativ drangeregelt. Entscheidend: BEIDE Seiten mit DERSELBEN Messmethode
(measure_arch), damit kein systematischer Bias die Anpassung verfälscht.

Ziele kommen aus der Foto-Metrologie (SAM): Pfeiler:Spann, Stich:Spann, Bogenzahl.

  python3 tools/viadukt_autofit.py --pier-span 0.33 --rise-span 0.50 --n 9 --span-m 20
"""
import argparse, os, sys, subprocess
import numpy as np, cv2
from shapely.geometry import Polygon
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foto_metrologie import opening_masks, measure_arch

PXM = 8.0   # px pro Meter beim Rastern der Facade


def build_facade(span, pier, z_spring, n, batter=0.04):
    """Facade-Polygon: Pfeiler (Höhe z_spring) + Halbkreisbögen (R=span/2) obenauf.
    Freie Parameter: pier (Pfeilerbreite), z_spring (Kämpferhöhe). Bogen = bestätigter Halbkreis."""
    P = span + pier
    R = span / 2
    L = n * P
    crown = z_spring + R
    body_top = crown + 0.08 * span
    outer = Polygon([(0, 0), (L, 0), (L, body_top), (0, body_top)])
    holes = []
    for k in range(n):
        xc = (k + 0.5) * P
        bw = R - batter * z_spring
        pts = [(xc - bw, 0), (xc - R, z_spring)]
        for ang in np.linspace(np.pi, 0, 40):
            pts.append((xc + R*np.cos(ang), z_spring + R*np.sin(ang)))
        pts.append((xc + bw, 0))
        holes.append(Polygon(pts))
    return outer.difference(unary_union(holes)), L, body_top


def measure_model(span, pier, z_spring, n):
    """Modell mit DERSELBEN measure_arch-Pipeline messen wie das Foto. Beim Modell sind die
    Öffnungen bekannt → unten-offene Öffnungen via nur-unten-Rand-Komponenten, dann measure_arch."""
    poly, L, Ht = build_facade(span, pier, z_spring, n)
    padx, padt = 12, 12
    W = int(L*PXM)+2*padx; H = int(Ht*PXM)+padt   # Basis bündig am unteren Rand
    def to_px(xy): return np.array([[int(x*PXM)+padx, H-1-int(z*PXM)] for x, z in xy], np.int32)
    stone = np.zeros((H, W), np.uint8)
    cv2.fillPoly(stone, [to_px(poly.exterior.coords)], 255)
    # unten-offene Öffnungen: leere Komponenten, die NUR den unteren Rand berühren
    from scipy import ndimage
    empty = stone == 0
    lbl, nlab = ndimage.label(empty)
    outside = set(lbl[0, :]) | set(lbl[:, 0]) | set(lbl[:, -1])   # oben/links/rechts = außen
    arches = []
    for k in range(1, nlab+1):
        if k in outside:
            continue
        mask = (lbl == k).astype(np.uint8)
        if mask.sum() < 0.0005*H*W:
            continue
        cc, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cont = max(cc, key=cv2.contourArea)[:, 0, :]
        m = measure_arch(cont)
        if m and m["semicircle"]:
            arches.append(m)
    arches.sort(key=lambda d: d["cx"])
    if len(arches) < 2:
        return None
    spans = np.array([d["span"] for d in arches])
    rs = float(np.median([d["R"]/d["span"] for d in arches]))
    pf = float(np.median([d["pier_frac"] for d in arches]))
    ps = []
    for i in range(len(arches)-1):
        pitch = arches[i+1]["cx"]-arches[i]["cx"]; sp = (spans[i]+spans[i+1])/2
        if 1.0 < pitch/sp < 1.7:
            ps.append((pitch-sp)/sp)
    return dict(n=len(arches), rise_span=rs, pier_frac=pf,
                pier_span=float(np.median(ps)) if ps else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pier-span", type=float, required=True, help="Ziel Pfeiler:Spann (Foto)")
    ap.add_argument("--pier-frac", type=float, required=True, help="Ziel Kämpfer:Öffnung (Foto)")
    ap.add_argument("--n", type=int, default=9)
    ap.add_argument("--span-m", type=float, default=20.0)
    ap.add_argument("--tol", type=float, default=0.01)
    ap.add_argument("--max-iter", type=int, default=20)
    ap.add_argument("--regen", action="store_true")
    a = ap.parse_args()

    span = a.span_m
    R = span / 2
    # Startwerte aus den Zielen (Loop korrigiert Mess-Bias)
    pier = a.pier_span * span
    z_spring = a.pier_frac / (1 - a.pier_frac) * R      # pier_frac ≈ z_spring/(z_spring+R)
    targets = {"pier_span": a.pier_span, "pier_frac": a.pier_frac}
    print(f"ZIELE (Foto):  Pfeiler:Spann {a.pier_span:.3f}   Kämpfer:Öffnung {a.pier_frac:.3f}   N {a.n}")
    print(f"{'it':>3} {'pier_m':>7} {'z_spring':>9} {'pier:span':>10} {'pier_frac':>10} {'maxerr':>8}")
    for it in range(a.max_iter):
        mm = measure_model(span, pier, z_spring, a.n)
        if mm is None:
            print("  Modell nicht messbar — Abbruch"); return
        e_ps = targets["pier_span"] - mm["pier_span"]
        e_pf = targets["pier_frac"] - mm["pier_frac"]
        maxerr = max(abs(e_ps), abs(e_pf))
        print(f"{it:3d} {pier:7.2f} {z_spring:9.2f} {mm['pier_span']:10.3f} {mm['pier_frac']:10.3f} {maxerr:8.3f}")
        if maxerr < a.tol:
            print(f"\n✅ beide Parameter konvergiert nach {it+1} Iterationen.")
            break
        pier = max(0.5, pier + span * e_ps)                      # Pfeilerbreite ← pier:span
        z_spring = max(1.0, z_spring + (z_spring + R) * e_pf * 1.4)  # Kämpferhöhe ← pier_frac
    else:
        print("\n⚠ max-iter erreicht (nicht ganz konvergiert)")

    pitch = span + pier
    print(f"\nGEFITTETE PARAMETER (gemeinsam geregelt):")
    print(f"  Spannweite    {span:.2f} m")
    print(f"  Pfeilerbreite {pier:.2f} m   (Pfeiler:Spann {pier/span:.3f})")
    print(f"  Kämpferhöhe   {z_spring:.2f} m")
    print(f"  Feldteilung   {pitch:.2f} m   ·   Bögen {a.n}   ·   Gesamtlänge {a.n*pitch:.1f} m")
    H = z_spring + R + 0.08*span
    print(f"  Gesamthöhe    {H:.1f} m")
    if a.regen:
        cmd = ["python3", "tools/ravenna_viadukt.py", "--n", str(a.n),
               "--L", f"{a.n*pitch:.1f}", "--span", f"{span:.1f}", "--H", f"{H:.1f}",
               "--stl", "modelle/ravenna/ravenna_viadukt_autofit.stl"]
        print("\nneu bauen:", " ".join(cmd)); subprocess.run(cmd)


if __name__ == "__main__":
    main()
