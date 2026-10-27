#!/usr/bin/env python3
"""autofit.py — ARCHETYP-AGNOSTISCHER Autofit-Kern.

Die Schleife „messen → Abweichung → Parameter regeln → neu bauen → nachmessen → bis konvergiert"
ist für JEDES Bauwerk dieselbe. Nur WAS gemessen wird, ist verschieden:
  Bogen   → Radius über Winkel      (arch_profile)
  Mauer   → Dicke über Höhe         (hier)
  Turm    → Radius über Höhe        (analog)
  …       → eine Kante über einem Parameter

Ein Archetyp liefert nur:  build(params)->artefakt  und  measure(artefakt)->{key:wert}
und eine Regel-Tabelle controls=[(ziel_key, param_key, verstärkung)].
Der Kern `fit()` ist universell. Gleiche Messung auf Soll- und Ist-Seite ⇒ Mess-Bias wird
automatisch rausgeregelt (bewiesen beim Viadukt).
"""
import numpy as np


def fit(build, measure, targets, params, controls, tol=0.01, max_iter=25, log=True):
    """Generischer geschlossener Fit.
      build(params)        -> Artefakt (Polygon/Raster/STL-Params …)
      measure(artefakt)    -> dict mit denselben Keys wie targets
      controls             -> [(ziel_key, param_key, gain)]  param += gain*fehler
    Gibt (gefittete params, letzte Messung, Historie) zurück."""
    params = dict(params)
    hist = []
    if log:
        print(f"{'it':>3} " + " ".join(f"{k:>12}" for k in targets) + f" {'maxerr':>8}")
    for it in range(max_iter):
        m = measure(build(params))
        errs = {k: targets[k] - m.get(k, float('nan')) for k in targets}
        maxerr = max(abs(e) for e in errs.values())
        hist.append((dict(params), dict(m), maxerr))
        if log:
            print(f"{it:3d} " + " ".join(f"{m.get(k, float('nan')):12.3f}" for k in targets) + f" {maxerr:8.3f}")
        if maxerr < tol:
            if log: print(f"✅ konvergiert nach {it+1} Iterationen")
            return params, m, hist
        for tk, pk, gain in controls:
            params[pk] = params[pk] + gain * errs[tk]
    if log: print("⚠ max-iter erreicht")
    return params, m, hist


# ======================= ARCHETYP: Gewichts-Staumauer-Querschnitt =======================
# Trapez: Breite = base am Fuß, crown an der Krone. Mess-Signatur: Dicke über Höhe.

def dam_build(params):
    return params  # (hier reicht das Param-Dict; measure rastert selbst)


def dam_measure(params, pxm=6.0):
    """Trapez-Querschnitt rastern und Dicke-über-Höhe MESSEN (gleiche Logik wie ein Foto)."""
    import cv2
    crown, base, H = params["crown"], params["base"], params["H"]
    W = int(base * pxm) + 20; Hp = int(H * pxm) + 20
    img = np.zeros((Hp, W), np.uint8)
    cx = 10                                     # Wasserseite SENKRECHT (links), Luftseite geböscht
    poly = np.array([[cx, Hp-10], [cx + base*pxm, Hp-10],
                     [cx + crown*pxm, 10], [cx, 10]], np.int32)
    cv2.fillPoly(img, [poly], 255)
    rows = np.where(img.any(1))[0]
    def thick_at(frac):
        y = int(rows.min() + frac*(rows.max()-rows.min()))
        xs = np.where(img[y] > 0)[0]
        return (xs.max()-xs.min())/pxm if len(xs) else 0.0
    base_m = thick_at(0.97); crown_m = thick_at(0.03)
    return {"crown_rel": crown_m / H, "base_rel": base_m / H}


def dam_fit(target_crown_rel, target_base_rel, H=63.5, **kw):
    params = {"crown": target_crown_rel*H, "base": target_base_rel*H, "H": H}
    controls = [("crown_rel", "crown", H), ("base_rel", "base", H)]
    return fit(dam_build, lambda p: dam_measure(p),
               {"crown_rel": target_crown_rel, "base_rel": target_base_rel},
               params, controls, **kw)


# ======================= ARCHETYP: Turm (Radius über Höhe) =======================
# Verjüngter Turm: Radius r_base am Fuß → r_top an der Spitze. Mess-Signatur: Radius über Höhe.

def tower_measure(params, pxm=6.0):
    """Turm-Silhouette rastern und Radius (halbe Breite) oben/unten MESSEN."""
    import cv2
    rb, rt, H = params["r_base"], params["r_top"], params["H"]
    W = int(2*rb*pxm)+20; Hp = int(H*pxm)+20; cx = W/2
    img = np.zeros((Hp, W), np.uint8)
    poly = np.array([[cx-rb*pxm, Hp-10], [cx+rb*pxm, Hp-10],
                     [cx+rt*pxm, 10], [cx-rt*pxm, 10]], np.int32)
    cv2.fillPoly(img, [poly], 255)
    rows = np.where(img.any(1))[0]
    def rad(frac):
        y = int(rows.min()+frac*(rows.max()-rows.min()))
        xs = np.where(img[y] > 0)[0]; return (xs.max()-xs.min())/2/pxm if len(xs) else 0.0
    return {"rbase_rel": rad(0.97)/H, "rtop_rel": rad(0.03)/H}


def tower_fit(target_rbase_rel, target_rtop_rel, H=42.0, **kw):
    controls = [("rbase_rel", "r_base", H), ("rtop_rel", "r_top", H)]
    return fit(lambda p: p, tower_measure, {"rbase_rel": target_rbase_rel, "rtop_rel": target_rtop_rel},
               {"r_base": target_rbase_rel*H, "r_top": target_rtop_rel*H, "H": H}, controls, **kw)


# ======================= ARCHETYP: Viadukt (nutzt denselben Kern) =======================
def viaduct_fit(target_pier_span, target_pier_frac, span=20.0, **kw):
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from viadukt_autofit import measure_model
    R = span/2
    params = {"pier": target_pier_span*span, "z": target_pier_frac/(1-target_pier_frac)*R, "span": span}
    def measure(p):
        m = measure_model(p["span"], p["pier"], p["z"], 9)
        return {"pier_span": m["pier_span"], "pier_frac": m["pier_frac"]} if m else {}
    controls = [("pier_span", "pier", span), ("pier_frac", "z", 1.4*(params["z"]+R))]
    return fit(lambda p: p, measure, {"pier_span": target_pier_span, "pier_frac": target_pier_frac},
               params, controls, **kw)


if __name__ == "__main__":
    import sys
    if "--viaduct" in sys.argv:
        print("=== Viadukt über den GLEICHEN generischen Kern ===")
        p, m, _ = viaduct_fit(0.33, 0.637, log=True)
        print(f"gefittet: Pfeiler {p['pier']:.2f} m, Kämpferhöhe {p['z']:.2f} m\n")
    print("=== ROUND-TRIP-BEWEIS Staumauer (generischer Kern) ===\n")
    print(f"{'Ziel crown:H':>12} {'→gemess':>9} {'Δ':>7}   {'Ziel base:H':>11} {'→gemess':>9} {'Δ':>7}")
    ok = True
    for cr, br in [(0.058, 0.79), (0.10, 0.60), (0.04, 0.90), (0.15, 0.70)]:
        p, m, _ = fit(dam_build, dam_measure, {"crown_rel": cr, "base_rel": br},
                      {"crown": cr*63.5, "base": br*63.5, "H": 63.5},
                      [("crown_rel", "crown", 63.5), ("base_rel", "base", 63.5)],
                      tol=0.003, log=False)
        d1, d2 = m["crown_rel"]-cr, m["base_rel"]-br
        ok &= abs(d1) < 0.01 and abs(d2) < 0.01
        print(f"{cr:12.3f} {m['crown_rel']:9.3f} {d1:+7.3f}   {br:11.3f} {m['base_rel']:9.3f} {d2:+7.3f}")
    print("\n" + ("✅ Staumauer: alle Vorgaben exakt getroffen — derselbe Kern wie Viadukt"
                  if ok else "⚠ nicht exakt"))

    print("\n=== ROUND-TRIP-BEWEIS Turm (3. Archetyp, gleicher Kern) ===\n")
    print(f"{'Ziel rbase:H':>12} {'→gemess':>9} {'Δ':>7}   {'Ziel rtop:H':>11} {'→gemess':>9} {'Δ':>7}")
    ok2 = True
    for rb, rt in [(0.12, 0.08), (0.20, 0.05), (0.15, 0.15), (0.10, 0.03)]:
        p, m, _ = tower_fit(rb, rt, tol=0.003, log=False)
        d1, d2 = m["rbase_rel"]-rb, m["rtop_rel"]-rt
        ok2 &= abs(d1) < 0.01 and abs(d2) < 0.01
        print(f"{rb:12.3f} {m['rbase_rel']:9.3f} {d1:+7.3f}   {rt:11.3f} {m['rtop_rel']:9.3f} {d2:+7.3f}")
    print("\n" + ("✅ Turm: alle Vorgaben exakt getroffen — 3 Archetypen, EIN Kern (fit)"
                  if ok2 else "⚠ Turm nicht exakt"))
