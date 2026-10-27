#!/usr/bin/env python3
"""Harter GEOMETRIE-Test für BAUWERKE (Viadukt / Bogen-Staumauer / Gewichtsmauer).

Kern-Einsicht: „Bögen" sind je nach Archetyp GEOMETRISCH GEGENSÄTZLICH:
  * Viadukt / Brücke    = echte DURCHSICHTEN (Tageslicht front→back).
  * Bogen-Staumauer     = NISCHEN auf massiver, wasserdichter Wand (NICHT durchsichtig!).
  * Gewichtsmauer       = massiver Block, gar keine Bögen.

Ein Viadukt, das in Wahrheit eine Wand mit Nischen ist → FALSCH.
Eine Staumauer, die versehentlich durchsichtig ist → FALSCH (hält kein Wasser).

Zwei unabhängige Sonden aus Oberflächen-Punkten (maßrobust):
  through : Löcher in der Frontal-Silhouette (Material in IRGENDEINER Tiefe = belegt);
            unten-offene Bögen werden behalten, nur Links/Rechts/Oben-Rand = „Himmel".
  relief  : Pfeiler-relative Fronttiefe (Nische = tiefer als Pfeiler) — zählt Relief-Bögen
            AUCH auf einer massiven Wand.
plus Silhouetten-Füllgrad (Viadukt ~0.55, Mauer ~1.0), Regelmäßigkeit (gap/width-CV),
Proportionen L:H und Mesh-Solidität.
"""
import numpy as np, trimesh
from scipy import ndimage
from scipy.stats import binned_statistic_2d


def probe(stl, res=0.5, n_sample=500000):
    m = trimesh.load(stl, force="mesh")
    np.random.seed(0)
    pts, _ = trimesh.sample.sample_surface(m, n_sample)
    (x0, y0, z0), (x1, y1, z1) = m.bounds
    # Auto-Orientierung: längste HORIZONTALE = Fassadenbreite (x), Blickrichtung = Tiefe (y)
    if (y1 - y0) > (x1 - x0):
        pts = pts[:, [1, 0, 2]]
        (x0, y0), (x1, y1) = (y0, x0), (y1, x1)
    (x0, z0), (x1, z1) = (pts[:, 0].min(), pts[:, 2].min()), (pts[:, 0].max(), pts[:, 2].max())
    y0, y1 = pts[:, 1].min(), pts[:, 1].max()
    L, Hh, D = x1 - x0, z1 - z0, max(1e-6, y1 - y0)
    nx, nz = max(12, int(L / res)), max(8, int(Hh / res))
    ix = np.clip(((pts[:, 0] - x0) / L * nx).astype(int), 0, nx - 1)
    iz = np.clip(((pts[:, 2] - z0) / Hh * nz).astype(int), 0, nz - 1)

    # --- through: Silhouetten-Belegung (Material in irgendeiner Tiefe) + Loch-Topologie
    occ = np.zeros((nx, nz), bool); occ[ix, iz] = True
    occ = ndimage.binary_closing(occ, iterations=1)
    fill = float(occ.mean())
    empty = ~occ
    lbl, n = ndimage.label(empty)
    outside = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, -1])   # x=0,x=max,z=max = Himmel
    tot = nx * nz; cxs = []; widths = []; harea = 0
    for k in range(1, n + 1):
        if k in outside:
            continue
        mask = lbl == k; a = int(mask.sum())
        if a / tot < 0.003:
            continue
        xs = np.where(mask)[0]
        harea += a; cxs.append(xs.mean()); widths.append((xs.max() - xs.min() + 1) / nx * L)
    order = np.argsort(cxs); cxs = np.array(cxs)[order]; widths = np.array(widths)[order]
    gaps = np.diff(cxs) if len(cxs) > 1 else np.array([0.0])
    n_through = len(cxs)
    openness_through = harea / tot

    # --- cols: SPALTEN-basierte Bogenzahl (robust gegen Himmel-Leck am Silhouetten-Rand).
    # Im Band klar UNTER dem Scheitel sind Pfeiler voll belegt, Bögen offen — reine
    # Spaltenstatistik, unabhängig von Loch-Topologie/Rand-Verschmelzung (behebt die
    # Falsch-Negativen bei dünnem Spandrill: 0 Durchsichten trotz 70 % offen).
    zc0, zc1 = int(0.15 * nz), int(0.55 * nz)
    colfill = occ[:, zc0:zc1].mean(axis=1) if zc1 > zc0 else np.ones(nx)
    open_col = colfill < 0.5
    runs = []                                      # Breiten der offenen Spalten-Läufe
    i = 0
    while i < len(open_col):
        if open_col[i]:
            j = i
            while j < len(open_col) and open_col[j]:
                j += 1
            runs.append(j - i); i = j
        else:
            i += 1
    # echte Bögen = breite Läufe; schmale Rand-Schlitze (Widerlager) rausfiltern (< 0.4·Median)
    if runs:
        thr = max(3.0, 0.4 * float(np.median(runs)))
        n_cols = int(sum(1 for w in runs if w >= thr))
    else:
        n_cols = 0

    # --- relief: pfeiler-relative Fronttiefe (Nischen auf massiver Wand)
    pad = 0.06 * L
    xb = np.arange(x0 + pad, x1 - pad, res)
    zb = np.arange(z0 + 0.12 * Hh, z0 + 0.92 * Hh, res)
    n_relief, openness_relief = 0, 0.0
    if len(xb) > 3 and len(zb) > 3:
        miny, _, _, _ = binned_statistic_2d(pts[:, 0], pts[:, 2], pts[:, 1],
                                            statistic="min", bins=[xb, zb])
        om = np.zeros_like(miny, bool)
        for k in range(miny.shape[1]):
            col = miny[:, k]; good = np.isfinite(col)
            if good.sum() < 3:
                om[:, k] = True; continue
            ref = np.percentile(col[good], 10)
            om[:, k] = ~good | (col > ref + 0.10 * D)     # tiefer als Pfeiler = Nische
        openness_relief = float(om.mean())
        col_open = om.mean(axis=1) > 0.40
        d = np.diff(col_open.astype(int))
        n_relief = int((d == 1).sum()) + (1 if col_open[0] else 0)

    return dict(
        L=round(L), H=round(Hh), LH=round(L / Hh, 2),
        n_through=n_through, openness_through=round(openness_through, 3),
        n_cols=n_cols,
        n_relief=n_relief, openness_relief=round(openness_relief, 3),
        fill=round(fill, 3),
        width_cv=round(float(np.std(widths) / (np.mean(widths) + 1e-9)), 3) if len(widths) else 0.0,
        gap_cv=round(float(np.std(gaps) / (np.mean(gaps) + 1e-9)), 3) if len(gaps) and gaps.any() else 0.0,
        watertight=bool(m.is_watertight), euler=int(m.euler_number),
        n_bodies=int(m.body_count),
    )


def _clamp(x, lo=0, hi=100): return max(lo, min(hi, x))
def _lin(x, a, b): return _clamp((x - a) / (b - a) * 100) if b != a else (100.0 if x >= b else 0.0)


def judge(stl, spec):
    """spec: {archetyp, n, L, H}. Gibt Verdikt-Dict wie die anderen Juroren."""
    p = probe(stl)
    arch = spec.get("archetyp", "viadukt")
    N = spec.get("n", 0); L = spec.get("L", p["L"]); H = spec.get("H", p["H"])
    reasons = [f"gemessen: L×H {p['L']}×{p['H']} m (L:H {p['LH']}, Soll {round(L/H,2)}), "
               f"Füllgrad {p['fill']}"]
    score = 100.0

    # Proportion (für alle): L:H muss stimmen
    lh_err = abs(p["LH"] / (L / H) - 1)
    if lh_err > 0.25:
        score -= 25; reasons.append(f"❌ Proportion L:H weicht {lh_err*100:.0f} % ab")

    if arch in ("viadukt", "bruecke"):
        # robuste Bogenzahl: Spaltenzähler ist rand-/topologie-fest; Durchsicht-Zähler als
        # Kreuz-Check. Wenn Durchsicht am dünnen Spandrill versagt (0), trägt der Spaltenzähler.
        n_meas = p["n_cols"] if p["n_cols"] else p["n_through"]
        reasons.append(f"Bögen: Spalten-Zähler {p['n_cols']}, Durchsicht-Zähler {p['n_through']} "
                       f"→ gewertet {n_meas}  (Soll {N})  · Öffnungsgrad {p['openness_through']}")
        # harte Tests
        if p["fill"] > 0.72:
            score -= 45; reasons.append("❌ Füllgrad zu hoch → WAND MIT NISCHEN statt echtem Viadukt (nicht durchsichtig)")
        dn = abs(n_meas - N)
        score -= _clamp(dn * 18)
        if dn == 0:
            reasons.append("✓ Bogenzahl exakt getroffen")
        elif dn > 1:
            reasons.append(f"❌ Bogenzahl falsch (Δ{dn})")
        if not (0.08 <= p["openness_through"] <= 0.55):
            score -= 12; reasons.append("⚠ Öffnungsgrad außerhalb gesunder Viadukt-Spanne 0.08–0.55")
        # Regelmäßigkeit (harter Zusatztest)
        if p["gap_cv"] > 0.15 or p["width_cv"] > 0.20:
            score -= 15; reasons.append(f"⚠ unregelmäßige Bögen (gap-CV {p['gap_cv']}, width-CV {p['width_cv']})")
        else:
            reasons.append(f"✓ regelmäßige Bögen (gap-CV {p['gap_cv']}, width-CV {p['width_cv']})")

    elif arch in ("bogenstaumauer", "bogenmauer"):
        n_meas = p["n_relief"]
        reasons.append(f"Relief-Bögen (Nischen): {n_meas}  (Soll {N})  · Nischen-Anteil {p['openness_relief']}")
        # MUSS wasserdicht/massiv sein: NICHT durchsichtig
        if p["openness_through"] > 0.06 or p["fill"] < 0.85:
            score -= 40; reasons.append("❌ durchsichtig/löchrig → eine Staumauer hält SO kein Wasser")
        else:
            reasons.append("✓ massiv/wasserdicht (nicht durchsichtig)")
        dn = abs(n_meas - N)
        score -= _clamp(dn * 15)
        if dn == 0:
            reasons.append("✓ Bogen-Rhythmus exakt getroffen")
        elif dn > 1:
            reasons.append(f"❌ falsche Nischen-Zahl (Δ{dn}) — Gefahr: glatte Massivwand ohne Gewölberhythmus")
        if not (0.12 <= p["openness_relief"] <= 0.55):
            score -= 12; reasons.append("⚠ Nischen-Anteil außerhalb 0.12–0.55 (0 = glatte Wand)")

    else:  # gewichtsstaumauer / block
        reasons.append(f"massiver Block erwartet · Durchsicht {p['openness_through']} · Füllgrad {p['fill']}")
        if p["openness_through"] > 0.06:
            score -= 35; reasons.append("❌ unerwartete Durchsichten in einer Gewichtsmauer")
        else:
            reasons.append("✓ massiv, keine Fehl-Öffnungen")

    # Mesh-Solidität (für alle, Zusatz)
    if not p["watertight"]:
        score -= 8; reasons.append(f"⚠ nicht watertight (euler {p['euler']}, {p['n_bodies']} Körper) → vor Druck reparieren")

    score = _clamp(score)
    verd = "PASS" if score >= 70 else ("WARN" if score >= 55 else "FAIL")
    return {"judge": "Geometrie-Treue", "score": round(score, 1), "verdict": verd,
            "reasons": reasons, "metrics": p}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--stl", required=True)
    ap.add_argument("--archetyp", default="viadukt")
    ap.add_argument("--n", type=int, default=9)
    ap.add_argument("--L", type=float, default=224)
    ap.add_argument("--H", type=float, default=40)
    a = ap.parse_args()
    v = judge(a.stl, dict(archetyp=a.archetyp, n=a.n, L=a.L, H=a.H))
    icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[v["verdict"]]
    print(f"{icon} {v['judge']} {v['score']}/100 [{v['verdict']}]")
    for r in v["reasons"]:
        print("   ·", r)
    print("  metrics:", json.dumps(v["metrics"]))
