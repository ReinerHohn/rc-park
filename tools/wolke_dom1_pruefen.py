#!/usr/bin/env python3
"""wolke_dom1_pruefen.py - GENERISCH: unabhaengige Kontrolle einer Fotowolke gegen das DOM1-Laserraster (Kaufhaus 2026-11-04).

DOM1 ist NICHT Teil der Ausrichtung/des Buendels (die nutzen LoD2/DGM1) und damit eine fremde Referenz (Regel "Rohraster vor Kennzahl").
Je DOM1-Zelle (1 m) mit >= 3 Wolkenpunkten ueber 3 m: Wolkenhoehe (p90 in der Zelle) minus DOM1-Hoehe. Getrennt: eigener Grundriss (LoD2-id) / Nachbarn.
Sehr steile Flaechen (DOM1-Gradient > --steil, Standard 2,5 = 68 Grad) zaehlen nicht (Laser sieht dort Kanten, Wolke Flaeche; Register AR).
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_dom1_pruefen.py modelle/<obj>/objekt.json <wolke.npy> [--name tag] [--bild audit/wolke_dom1_<tag>.png]
Ausgabe: Median/IQR der Differenz je Gruppe + Karte; audit/wolke_dom1_<tag>.json.
"""
import sys, os, json, math, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("wolke"); ap.add_argument("--name", default=None)
    ap.add_argument("--steil", type=float, default=2.5, help="DOM1-Gradient, ab dem eine Zelle nicht zaehlt (2,5 = 68 Grad; steile Helme Register AR)"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od); tag = a.name or os.path.splitext(os.path.basename(a.wolke))[0]
    R = obj.get("rahmen") or json.load(open(os.path.join(od, "anker3d.json"))); c0 = np.array(R["mitte_utm"], float); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"]); L = obj["laser"]
    # DOM1 direkt aus der amtlichen GeoTIFF-Kachel (.tfw = Mitte des Pixels links oben), 80 x 80 m um die Rahmenmitte. Fallback: Fenster-npy (objekt_daten.py).
    # Grund (2026-11-04): das Martinstor-Fenster war um eine Lat/Lon-Lage geschnitten, nicht um den Rahmen -> Fenster-npy ist nicht objektuebergreifend verlaesslich.
    import glob as _g
    ek, nk = int(c0[0] // 1000), int(c0[1] // 1000); tif = sorted(_g.glob(f"/media/oem/scan/rc-park_daten/_geo/**/dom1_32_{ek}_{nk}_1_bw_*.tif", recursive=True))
    if tif:
        from PIL import Image
        A = np.array(Image.open(tif[0])).astype(float); A[A < -100] = np.nan; tf = [float(x) for x in open(tif[0][:-4] + ".tfw")]; xc, yc = tf[4], tf[5]
        h = 40; cc, rr = int(round(c0[0] - xc)), int(round(yc - c0[1])); W = A[rr - h:rr + h, cc - h:cc + h]; n = W.shape[0]
        yy, xx = np.mgrid[:n, :n]; E = xc + cc - h + xx; N = yc - (rr - h) - yy; quelle_dom = os.path.basename(tif[0])
        x0 = None
    else:
        W = np.load(L["fenster_npy"]).astype(float); n = W.shape[0]; h = n // 2; quelle_dom = L["fenster_npy"]
        x0 = math.floor(c0[0] / 1000) * 1000; y0 = (math.floor(c0[1] / 1000) + 1) * 1000          # LGL-Kachel 1 km: Ursprung links oben (wie objekt_daten.py)
        cc, rr = int(c0[0] - x0), int(y0 - c0[1])
        yy, xx = np.mgrid[:n, :n]; E = x0 + cc - h + xx + 0.5; N = y0 - (rr - h) - yy - 0.5
    lx = (E - c0[0]) * xh[0] + (N - c0[1]) * xh[1]; ly = (E - c0[0]) * yh[0] + (N - c0[1]) * yh[1]; Z = W - R["gelaende"]
    gy, gx = np.gradient(W); steil = np.hypot(gx, gy) > a.steil
    # eigener Grundriss aus LoD2 (alle Flaechen des Gebaeudes, xy-Projektion)
    import lod2_gebaeude as LG
    from matplotlib.path import Path
    eigen = np.zeros_like(Z, bool)
    for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=40):
        if meta["id"] != obj["lod2"]["id"]: continue
        for t, P in polys:
            if t != "RoofSurface": continue
            q = np.c_[(P[:, 0] - c0[0]) * xh[0] + (P[:, 1] - c0[1]) * xh[1], (P[:, 0] - c0[0]) * yh[0] + (P[:, 1] - c0[1]) * yh[1]]
            eigen |= Path(q).contains_points(np.c_[lx.ravel(), ly.ravel()]).reshape(Z.shape)
    P = np.load(a.wolke).astype(float); P = P[P[:, 2] > 3]
    # Wolkenpunkte den Zellen zuordnen (Zelle = naechste DOM1-Mitte; Raster ist um den Rahmenwinkel gedreht -> ueber UTM)
    Eu = c0[0] + P[:, 0] * xh[0] + P[:, 1] * yh[0]; Nu = c0[1] + P[:, 0] * xh[1] + P[:, 1] * yh[1]
    jj = np.floor(Eu - (E[0, 0] - 0.5)).astype(int); ii = np.floor((N[0, 0] + 0.5) - Nu).astype(int)          # Zelle = Pixel mit Mitte E/N, Kante +-0,5 m
    ok = (ii >= 0) & (ii < n) & (jj >= 0) & (jj < n); ii, jj, pz = ii[ok], jj[ok], P[ok, 2]
    zell = ii * n + jj; o = np.argsort(zell); zell, pz = zell[o], pz[o]; u, st, cnt = np.unique(zell, return_index=True, return_counts=True)
    D = np.full(Z.shape, np.nan)
    for z_, s_, c_ in zip(u, st, cnt):
        if c_ >= 3: D.flat[z_] = np.percentile(pz[s_:s_ + c_], 90) - Z.flat[z_]
    erg = {}
    for nm, m in (("eigen", eigen), ("nachbarn", ~eigen & (Z > 3))):
        d = D[m & ~steil & np.isfinite(D)]
        erg[nm] = dict(zellen=int(len(d)), median_m=float(np.median(d)) if len(d) else None, p25_m=float(np.percentile(d, 25)) if len(d) else None, p75_m=float(np.percentile(d, 75)) if len(d) else None)
        print(f"{nm}: {len(d)} Zellen, Wolke - DOM1 Median {erg[nm]['median_m']:+.2f} m (p25 {erg[nm]['p25_m']:+.2f}, p75 {erg[nm]['p75_m']:+.2f})" if len(d) else f"{nm}: keine Zellen")
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="wolke_dom1_pruefen.py", wolke=a.wolke, dom1=quelle_dom, ergebnis=erg, hinweis="DOM1 = fremde Referenz (nicht in Ausrichtung/Buendel); p90 je Zelle, steile Zellen ausgenommen"),
              open(os.path.join(od, "audit", f"wolke_dom1_{tag}.json"), "w"), indent=1)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 6))
    im0 = ax[0].imshow(Z, cmap="viridis", vmin=0, vmax=np.nanpercentile(Z, 99)); ax[0].contour(eigen, [0.5], colors="w"); ax[0].set_title("DOM1 ueber Gelaende (m), weiss = eigener LoD2-Grundriss"); plt.colorbar(im0, ax=ax[0])
    im1 = ax[1].imshow(D, cmap="RdBu_r", vmin=-4, vmax=4); ax[1].contour(eigen, [0.5], colors="k"); plt.colorbar(im1, ax=ax[1])
    ax[1].set_title(f"Wolke p90 - DOM1 (m)  eigen {erg['eigen']['median_m'] if erg['eigen']['median_m'] is not None else float('nan'):+.2f}, Nachbarn {erg['nachbarn']['median_m'] if erg['nachbarn']['median_m'] is not None else float('nan'):+.2f}")
    for x in ax: x.set_xticks([]); x.set_yticks([])
    fig.suptitle(f"{os.path.basename(od)}: {os.path.basename(a.wolke)} gegen DOM1 (unabhaengig)"); fig.tight_layout()
    bp = os.path.join(od, "audit", f"wolke_dom1_{tag}.png"); fig.savefig(bp, dpi=90); print("geschrieben:", bp)


if __name__ == "__main__":
    main()
