#!/usr/bin/env python3
"""hoehe_gegen_dom1.py <objekt.json> [--radius 12] [--zmin 8] [--tol 0.5] - HOEHEN-TOR: Oberseite des gebauten Modells gegen den DOM1-Laser (1-m-Pixel).

Lehre Schwabentor v3 15.11.2026: das Modell stand 5,3 % zu gross im Rahmen (Dachtraufe 39,26 statt 37,2 m), ohne dass ein Tor es merkte - der Turm passte
scheinbar zum LoD2-Grundriss (Sockelumring), das Foto-GPS streute. Der Laser sieht Flaechenhoehen direkt (KERNMETHODE: Hoehe = Sache von DOM1).
Verfahren: je DOM1-Pixel im Umkreis der Objektmitte die Laserhoehe ueber rahmen.gelaende und die Modell-Oberseite (Strahl von oben auf das STL, 5 Strahlen je
Pixel, Median). Nur FLAECHEN-Pixel zaehlen: Laser > zmin, Modell getroffen, und beide liegen im 3x3-Umfeld auf einer Ebene (Rest < 0,35 m, auch steile Daecher) - Kanten, Laternen, Nachbarn fallen
weg (Laser ist fuer duenne Bauteile blind). Ausgabe: Median Modell - Laser, Streuung, und der Massstab k = Median(Laser / Modell), um den die Hoehen
(bei einheitlichem Massstabsfehler: der ganze Rahmen, tools/ausrichtung_massstab_korrigieren.py) zu aendern waeren. rc 3, wenn |Median| > tol.
Schreibt audit/hoehe_gegen_dom1.json. STL im Rahmen (zentrierung 'achse').
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import trimesh
    from dom1_kachel import dom1_hoehe
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--radius", type=float, default=12.0); ap.add_argument("--zmin", type=float, default=8.0); ap.add_argument("--tol", type=float, default=0.5); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); r = obj["rahmen"]
    m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); g0 = float(r["gelaende"])
    m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0); c = m.bounds.mean(0)[:2]
    E0, N0 = m0 + c[0] * xh + c[1] * yh; es = np.arange(np.floor(E0 - a.radius) + 0.5, E0 + a.radius, 1.0); ns = np.arange(np.floor(N0 - a.radius) + 0.5, N0 + a.radius, 1.0)
    L = np.full((len(es), len(ns)), np.nan); Mo = np.full_like(L, np.nan); off = [(0, 0), (.3, .3), (-.3, .3), (.3, -.3), (-.3, -.3)]
    for i, E in enumerate(es):
        for j, N in enumerate(ns):
            try: L[i, j] = float(dom1_hoehe(E, N, "dom1")) - g0
            except Exception: continue
            P = np.array([[(E + de - m0[0]), (N + dn - m0[1])] for de, dn in off]); xy = np.c_[P @ xh, P @ yh]
            loc, ir, _ = m.ray.intersects_location(np.c_[xy, np.full(5, 500.0)], np.tile([0, 0, -1.0], (5, 1)), multiple_hits=False)
            if len(ir) >= 4: Mo[i, j] = float(np.median(loc[:, 2]))
    gi, gj = np.mgrid[-1:2, -1:2]; G9 = np.c_[gi.ravel(), gj.ravel(), np.ones(9)]
    def ruhig(Z):
        out = np.zeros(Z.shape, bool)
        for i in range(1, Z.shape[0] - 1):
            for j in range(1, Z.shape[1] - 1):
                w = Z[i - 1:i + 2, j - 1:j + 2]
                if not np.isfinite(w).all(): continue
                res_ = w.ravel() - G9 @ np.linalg.lstsq(G9, w.ravel(), rcond=None)[0]; out[i, j] = np.sqrt((res_ ** 2).mean()) < 0.35      # 3x3-Umfeld liegt auf EINER (auch steilen) Ebene
        return out
    ok = ruhig(L) & ruhig(Mo) & (L > a.zmin) & (Mo > a.zmin); n = int(ok.sum())
    if n < 8: print(f"HOEHEN-TOR: nur {n} ruhige Flaechenpixel - kein Urteil"); return 0
    # Lageversatz mitschaetzen: auf steilen Daechern machen 0,35 m waagerechter Versatz (Pixelraster 1 m, Lage der Ausrichtung) schon 0,5 m Hoehe aus.
    # Modell um (dx, dy) verschoben abtasten, Versatz mit kleinster Streuung nehmen; das Hoehenurteil gilt beim besten Versatz.
    ii, jj = np.nonzero(ok); Pm = np.array([[(es[i] - m0[0]), (ns[j] - m0[1])] for i, j in zip(ii, jj)]); xy0 = np.c_[Pm @ xh, Pm @ yh]; Lk = L[ok]; best = None
    for dx in np.arange(-1.0, 1.01, 0.25):
        for dy in np.arange(-1.0, 1.01, 0.25):
            q = xy0 - np.array([dx, dy]); loc, ir, _ = m.ray.intersects_location(np.c_[q, np.full(len(q), 500.0)], np.tile([0, 0, -1.0], (len(q), 1)), multiple_hits=False)
            if len(ir) < 0.8 * len(q): continue
            dd = loc[:, 2] - Lk[ir]; md = float(np.median(dd)); sp = float(np.median(np.abs(dd - md)))
            if best is None or sp < best[0]: best = (sp, dx, dy, md, len(ir))
    d = (Mo - L)[ok]; k = float(np.median((L / Mo)[ok])); med0 = float(np.median(d)); mad0 = float(np.median(np.abs(d - med0)))
    mad, vdx, vdy, med, _ = best if best else (mad0, 0.0, 0.0, med0, 0); k = float(np.median(Lk) / (np.median(Lk) + med))
    res = dict(werkzeug="hoehe_gegen_dom1.py", pixel=n, median_modell_minus_laser_m=round(med, 2), streuung_mad_m=round(mad, 2), p10_p90=[round(float(v), 2) for v in np.percentile(d, [10, 90])],
               massstab_k=round(k, 4), versatz_modell_xy_m=[float(vdx), float(vdy)], median_ohne_versatz_m=round(med0, 2), hoehen_laser=[round(float(v), 1) for v in np.percentile(L[ok], [10, 50, 90])], tol_m=a.tol)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(res, open(os.path.join(od, "audit", "hoehe_gegen_dom1.json"), "w"), indent=1)
    print(f"HOEHEN-TOR: {n} Flaechenpixel (Laser {res['hoehen_laser'][0]}-{res['hoehen_laser'][2]} m): Modell - Laser Median {med:+.2f} m (MAD {mad:.2f}) beim Lageversatz des Modells ({vdx:+.2f}, {vdy:+.2f}) m; ohne Versatz {med0:+.2f}; Massstab k {k:.4f}"
          + ("  -> NICHT BESTANDEN" if abs(med) > a.tol else "  -> bestanden"))
    return 3 if abs(med) > a.tol else 0


if __name__ == "__main__":
    sys.exit(main())
