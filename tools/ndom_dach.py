#!/usr/bin/env python3
"""ndom_dach.py — nDOM = DOM1 − DGM1 = OBJEKTHÖHE über Boden, aus den amtlichen Laserdaten (LGL).
Liefert die ECHTE Dachhaut über dem Gebäude-Grundriss: First-/Traufhöhe über Boden (Quercheck
gegen LOD2), Geländehöhe am Sockel (DGM), und eine Dach-Höhenkarte. Verbaut die bisher ungenutzten
Quellen DGM1, DOM1, nDOM (Quellen-Gate).

Lauf: python3 tools/ndom_dach.py --name hofgut_sternen
  --dom <dom1.tif> --dgm <dgm1.xyz>  (sonst Default-Pfade Ravenna-Kachel)
Schreibt modelle/<name>/ndom.json (First/Traufe/Gelände) + ndom.png (Dach-Höhenkarte) +
terrain.json (Geländehöhe) + dom_roof.json → Gate markiert DOM1/DGM1/nDOM als genutzt.
"""
import argparse, glob, json, os
import numpy as np
import cv2


def load_dgm_grid(xyz_path, E0, N0, n=1000):
    """DGM1-XYZ (1 m, Zellmitten X.5/Y.5) → Raster G[r,c], r=Nord oben. Kachelursprung (E0,N0)=NW-Ecke."""
    d = np.loadtxt(xyz_path)
    G = np.full((n, n), np.nan, np.float32)
    c = np.round(d[:, 0] - 0.5 - E0).astype(int)
    r = np.round(N0 - 0.5 - d[:, 1]).astype(int)
    ok = (c >= 0) & (c < n) & (r >= 0) & (r < n)
    G[r[ok], c[ok]] = d[ok, 2]
    return G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--dom", default="daten/ravenna/dom1/dom1_32_429_5306_2_bw/dom1_32_430_5307_1_bw_2017.tif")
    ap.add_argument("--dgm", default="daten/ravenna/dgm1_32_429_5306_2_bw/dgm1_32_430_5307_1_bw_2017.xyz")
    a = ap.parse_args()
    md = f"modelle/{a.name}"

    # Kachel-NW-Ecke aus DOM-tfw
    tfw = open(os.path.splitext(a.dom)[0] + ".tfw").read().split()
    px, _, _, py, ox_c, oy_c = [float(x) for x in tfw]
    E0 = ox_c - px / 2.0                      # NW-Ecke (px>0)
    N0 = oy_c - py / 2.0                      # py<0 → oy_c + |py|/2
    DOM = cv2.imread(a.dom, cv2.IMREAD_UNCHANGED).astype(np.float32)
    n = DOM.shape[0]
    DGM = load_dgm_grid(a.dgm, E0, N0, n)
    nDOM = DOM - DGM                          # Objekthöhe über Boden

    # Footprint (UTM) laden → Maske über dem Gebäude
    fp = json.load(open(f"{md}/footprint.json"))
    o = np.array(fp["origin_utm"][:2])
    rings = [np.array(t["ring_xy_m"]) + o for t in fp["teile"]]  # UTM
    mask = np.zeros((n, n), np.uint8)
    for r_ in rings:
        c = np.round(r_[:, 0] - 0.5 - E0).astype(np.int32)
        rr = np.round(N0 - 0.5 - r_[:, 1]).astype(np.int32)
        cv2.fillPoly(mask, [np.c_[c, rr]], 1)
    m = mask > 0
    if m.sum() < 20:
        print("⚠️ Footprint-Maske fast leer — Georef prüfen");

    roof = nDOM[m]
    roof = roof[np.isfinite(roof)]
    ground = DGM[m]; ground = ground[np.isfinite(ground)]
    # Traufe/First robust: Perzentile (Antennen/Kamine = Ausreißer kappen)
    eave = float(np.percentile(roof, 55))
    ridge = float(np.percentile(roof, 99))
    out = {
        "quelle": f"nDOM = DOM1 − DGM1 (LGL Laser 1 m); DOM {os.path.basename(a.dom)}",
        "gelaende_z_nn_m": round(float(np.median(ground)), 2),
        "first_ueber_boden_m": round(ridge, 2),
        "traufe_ueber_boden_m": round(eave, 2),
        "lod2_first_m": fp["teile"][int(np.argmax([len(t['ring_xy_m']) for t in fp['teile']]))].get("ridge_m"),
        "footprint_zellen": int(m.sum()),
    }
    # Quercheck gegen LOD2-First (amtlich)
    lod2_first = max((t.get("ridge_m") or 0) for t in fp["teile"])
    out["lod2_first_max_m"] = lod2_first
    out["quercheck_first"] = "PASS" if abs(ridge - lod2_first) < 2.5 else "FLAG"

    json.dump(out, open(f"{md}/ndom.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"gelaende_z_nn_m": out["gelaende_z_nn_m"], "quelle": "DGM1 LGL"},
              open(f"{md}/terrain.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"first_ueber_boden_m": out["first_ueber_boden_m"], "traufe_ueber_boden_m": out["traufe_ueber_boden_m"],
               "quelle": "DOM1 LGL"}, open(f"{md}/dom_roof.json", "w"), indent=1, ensure_ascii=False)

    # Dach-Höhenkarte (nur Footprint) als Bild
    vis = np.clip(nDOM, 0, max(2, ridge))
    vis = (vis / vis.max() * 255).astype(np.uint8)
    vis = cv2.applyColorMap(vis, cv2.COLORMAP_TURBO)
    vis[~m] = (vis[~m] * 0.25).astype(np.uint8)
    ys, xs = np.where(m)
    pad = 15; crop = vis[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    cv2.imwrite(f"{md}/ndom.png", cv2.resize(crop, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST))

    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"-> {md}/ndom.json, terrain.json, dom_roof.json, ndom.png")


if __name__ == "__main__":
    main()
