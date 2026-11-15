#!/usr/bin/env python3
"""steine_generieren.py <relief.npz> <aus.npz> --zone u0 u1 z0 z1 [--zone ...] [--unten 0.0] [--seed 1] - Loecher eines Relief-Einsatzes mit GENERIERTEN Quadern fuellen.

Warum (Nutzer 15.11.2026, Schwabentor: "Kannst du den Rest der Steine noch machen, notfalls generieren?"): das Scan-Relief (tools/relief_einsatz.py) hat Loecher
(Verdeckung durch Schilder, Autos, Sockel unter z0) - dort war die Wand glatt. Hier: innerhalb der angegebenen STEINZONEN (u, z in Wandkoordinaten des Reliefs)
werden Lochzellen (rel == 0, zusammenhaengend) mit einem Quaderverband gefuellt, der zum echten Relief daneben passt:
  - Lagerfugen: aus dem echten Relief derselben Zeilen uebernommen (Minima des Zeilenmedians), wo genug echte Zellen da sind; sonst Schichthoehen gewuerfelt
    aus der Verteilung der gefundenen echten Schichten.
  - Stossfugen gewuerfelt (Laengen aus --laenge), Kissenform je Stein (Buckelquader), Hub auf p5/p95 des echten Reliefs der Zone skaliert, leichtes Rauschen.
  - --unten: Relief nach unten bis zu dieser Hoehe verlaengern (Zeilen anfuegen) und dort ebenfalls generieren.
ERFUNDEN, KEIN MASS: aus.npz traegt die Maske 'generiert'; im Generator als ANNAHME belegen. aus.jpg zeigt generierte Zellen blau getoent - ANSEHEN.
  /media/oem/scan/venv-seg/bin/python -I tools/steine_generieren.py modelle/schwab_v3/relief/nord.npz modelle/schwab_v3/relief/nord_voll.npz --zone 0 12 0 9.7 --unten 0
"""
import sys, os, argparse, numpy as np, cv2
from scipy import ndimage as ndi


def lagerfugen(rel, gueltig, px, min_zellen=30):
    """Zeilenindizes der Lagerfugen aus dem echten Relief (Minima des geglaetteten Zeilenmedians); nur Zeilen mit genug echten Zellen."""
    H = rel.shape[0]; r = np.full(H, np.nan)
    for i in range(H):
        v = rel[i][gueltig[i]]
        if len(v) >= min_zellen: r[i] = np.percentile(v, 35)
    ok = np.isfinite(r); rs = np.where(ok, r, np.nanmedian(r) if ok.any() else 0.0); rs = ndi.gaussian_filter1d(rs, 1.0); J = []
    for i in range(2, H - 2):
        if ok[i] and rs[i] <= rs[i - 1] and rs[i] < rs[i + 1] and rs[i] < min(rs[max(0, i - 4):i + 5].mean(), np.nanmedian(rs)) - 0.004: J.append(i)
    K = []
    for j in J:                                                           # Mindestabstand 0,2 m
        if not K or (j - K[-1]) * px >= 0.2: K.append(j)
    return np.array(K, int), ok


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("aus"); ap.add_argument("--zone", nargs=4, type=float, action="append", required=True)
    ap.add_argument("--ohne", nargs=4, type=float, action="append", default=[], help="Felder u0 u1 z0 z1, in denen NICHT generiert wird (Toroeffnungen - Nutzer 15.11.: 'nicht im Tor kuenstlich')"); ap.add_argument("--fremd", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1 mit einem FREMDKOERPER vor der Wand (Nachbardach, Schild): Zellen an der oberen Klemme und Nullzellen darin gelten als Loch"); ap.add_argument("--unten", type=float); ap.add_argument("--seed", type=int, default=1); ap.add_argument("--laenge", nargs=2, type=float, default=[0.4, 1.25])
    ap.add_argument("--min_loch", type=int, default=12, help="kleinste Lochgroesse in Zellen"); a = ap.parse_args(); rng = np.random.default_rng(a.seed)
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float64); px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"])
    if a.unten is not None and a.unten < z0 - 1e-6:
        k = int(round((z0 - a.unten) / px)); rel = np.vstack([rel, np.zeros((k, rel.shape[1]))]); z0 = z0 - k * px          # Zeilen laufen von oben nach unten
    H, W = rel.shape; ii, jj = np.mgrid[0:H, 0:W]; U = u0 + (jj + 0.5) * px; ZZ = z0 + (H - 1 - ii + 0.5) * px
    zone = np.zeros((H, W), bool)
    for f0, f1, g0, g1 in a.zone: zone |= (U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1)
    for f0, f1, g0, g1 in a.ohne: zone &= ~((U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1))
    if "putz" in Z: zone &= ~np.vstack([Z["putz"], np.zeros((H - Z["putz"].shape[0], W), bool)])       # Putzflaechen (tools/relief_putz.py) sind absichtlich eben - keine Steine hinein
    flach = ndi.maximum_filter(rel, 3) == ndi.minimum_filter(rel, 3)       # konstante Flecken = an der Klemme abgeschnittene Fremdkoerper (Schild, Auto, Kasten vor der Wand) -> ebenfalls Loch
    lab, n = ndi.label(ndi.binary_dilation(flach, iterations=2) | (rel == 0.0)); gr = ndi.sum(np.ones_like(rel), lab, np.arange(1, n + 1)); loch = np.isin(lab, 1 + np.flatnonzero(gr >= a.min_loch)) & zone
    for f0, f1, g0, g1 in a.fremd:                                        # 15.11.2026 Nutzerbild: Nachbardach lag als schraege Rippe im Suedrelief (an der Klemme abgeschnitten)
        feld = (U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1); fr = ndi.binary_dilation(feld & (rel >= rel.max() - 1e-3), iterations=2) | (feld & (rel == 0.0))
        loch |= ndi.binary_fill_holes(ndi.binary_closing(fr, iterations=2)) & feld & zone
    gueltig = zone & ~loch & (rel != 0.0)
    if gueltig.sum() < 500: print("zu wenig echtes Relief in der Zone"); return 2
    J, zeile_ok = lagerfugen(rel, gueltig, px); hs = np.diff(J) * px; hs = hs[(hs > 0.2) & (hs < 0.7)]
    if len(hs) < 4: hs = np.array([0.32, 0.38, 0.42, 0.36])
    q5, q95 = np.percentile(rel[gueltig], [5, 95]); print(f"echte Lagerfugen {len(J)}, Schichthoehe Median {np.median(hs):.2f} m (p10 {np.percentile(hs, 10):.2f}, p90 {np.percentile(hs, 90):.2f}); Hub p5 {q5*100:.1f} / p95 {q95*100:.1f} cm")
    # Schichten: gewuerfelt um die gemessene mittlere Schichthoehe (+-25 %). Die echten Lagerfugen laufen im Bruchsteinverband NICHT ueber die ganze Wand durch -
    # der erste Versuch, sie zeilenweise zu uebernehmen, gab zu duenne Schichten (0,25 m statt 0,45 m).
    hm_ = float(np.clip(np.median(hs), 0.3, 0.6)); voll = [0]
    while voll[-1] < H: voll.append(voll[-1] + max(4, int(round(hm_ * rng.uniform(0.75, 1.25) / px))))
    voll[-1] = H
    gen = np.zeros((H, W))
    for r0, r1 in zip(voll[:-1], voll[1:]):                                # eine Schicht: Zeilen r0..r1-1, Fuge = Zeile r0
        if r1 - r0 < 2: continue
        c = int(-rng.uniform(0, a.laenge[1]) / px)
        while c < W:
            l = max(4, int(round(rng.uniform(*a.laenge) / px))); c0, c1 = max(c, 0), min(c + l, W)
            if c1 - c0 >= 1:
                yy = np.linspace(-1, 1, r1 - r0 - 1)[:, None] if r1 - r0 > 2 else np.zeros((1, 1)); xx = (np.arange(c0, c1) - (c + (l - 1) / 2.0)) / max((l - 1) / 2.0, 1)
                kis = (1 - np.abs(yy) ** 3) * (1 - np.abs(xx[None, :]) ** 3); A = float(np.clip(rng.lognormal(-0.2, 0.45), 0.35, 2.2)); kipp = rng.uniform(-0.15, 0.15) * xx[None, :] + rng.uniform(-0.15, 0.15) * yy
                blk = A * (0.15 + 0.85 * kis ** 0.6) + kipp; blk[:, xx <= -1 + 1e-9] = -0.15                                  # Stossfuge = erste Spalte des Steins
                gen[r0 + 1:r1, c0:c1] = blk[:, :c1 - c0]
            c += l
        gen[r0, :] = -0.15                                                 # Lagerfuge
    gen += 0.7 * ndi.gaussian_filter(rng.standard_normal((H, W)), 1.5) / 0.19 * 0.5 * 0.5; gen = ndi.gaussian_filter(gen, 0.45)
    g5, g95 = np.percentile(gen, [25, 75]); r25, r75 = np.percentile(rel[gueltig], [25, 75]); gen = np.clip(r25 + (gen - g5) / (g95 - g5) * (r75 - r25), q5 - 0.02, q95)   # auf den mittleren Hub des echten Reliefs (p25/p75), nicht auf die Ausreisser
    w = np.clip(ndi.distance_transform_edt(loch) / 2.0, 0, 1); neu = np.where(loch, gen * w, rel); neu[loch & (neu == 0.0)] = 1e-4
    Z["rel"] = neu.astype(np.float32); Z["z0"] = z0; Z["generiert"] = loch; Z["generiert_anteil"] = float(loch.mean())
    np.savez_compressed(a.aus, **Z)
    lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); s = np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    im[loch] = (im[loch] * np.array([1.0, 0.8, 0.7])).astype(np.uint8); im[(neu == 0.0)] = (0, 0, 255)
    cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", cv2.resize(im, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print(f"{os.path.basename(a.aus)}: {W}x{H} Zellen, generiert {loch.mean()*100:.1f} % der Flaeche ({loch.sum() * px * px:.1f} m2), z ab {z0:.2f} m")


if __name__ == "__main__":
    sys.exit(main())
