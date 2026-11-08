#!/usr/bin/env python3
"""freiraum_fassaden.py - gesehenen Freiraum HINTER jeder Fassadenebene als 2D-Tiefenkarte (u, z) -> wie tief darf/muss das Modell dort offen sein.

Eingabe: strahlen.npz aus freiraum_pruefen.py (verletzende Strahlen: Kamera C, Richtung d, Abschnitt t0..t1 im Modell), fassaden.json aus fassade_ortho.py
(je Fassade o, d, n nach aussen, u-/z-Bereich). Je Strahlabschnitt werden Stuetzpunkte (--schritt) der naechsten Fassade zugeordnet, deren Ebene sie
hoechstens --max-tiefe hinter sich und innerhalb u/z haben; Zelle (--zelle m) speichert je Kamera die groesste Tiefe; Karte = Tiefe, die
>= --min-kameras verschiedene Kameras erreichen (k-groesster Wert). Allgemein: Arkaden, Durchgaenge, Nischen, Tore - ohne Bauteilregel.
Ausgabe: freiraum_fassaden.json (je Fassade Raster + Kennzahlen) und freiraum_fassaden.jpg.
  /media/oem/scan/venv-seg/bin/python -I tools/freiraum_fassaden.py <strahlen.npz> <fassaden.json> <ausordner> [--zelle 0.25] [--min-kameras 3]
"""
import os, sys, json, argparse, numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("npz"); ap.add_argument("fassaden"); ap.add_argument("aus"); ap.add_argument("--zelle", type=float, default=0.25)
    ap.add_argument("--min-kameras", type=int, default=3); ap.add_argument("--schritt", type=float, default=0.1); ap.add_argument("--max-tiefe", type=float, default=8.0)
    ap.add_argument("--min-flaeche", type=float, default=20.0)
    ap.add_argument("--max-winkel", type=float, default=180.0, help="nur Strahlen, die die Fassade unter hoechstens so viel Grad zur Gegennormalen durchqueren (5.11.: Seitendurchgang, von der Seite gesehen, wurde als Oeffnung der FRONT geschnitten; 180 = alle, bisher)")
    ap.add_argument("--stl", help="Modell (mm 1:massstab): nur Strahlstuecke IM Modell zaehlen (sonst zaehlt bereits offener Raum mit; Gegenprobe 5.11.: ausgeschnittener Durchgang blieb gemeldet)"); ap.add_argument("--massstab", type=float, default=87.0)
    a = ap.parse_args(argv); Z = np.load(a.npz); F = json.load(open(a.fassaden)); os.makedirs(a.aus, exist_ok=True)
    pts, kam, ri = [], [], []
    for j, (c, d, s, e, k) in enumerate(zip(Z["C"], Z["d"], Z["t0"], Z["t1"], Z["kam"])):
        if e > s: t = np.arange(s, e, a.schritt); pts.append(c + d * t[:, None]); kam.append(np.full(len(t), k)); ri.append(np.full(len(t), j))
    P = np.concatenate(pts); K = np.concatenate(kam); RI = np.concatenate(ri); DR = Z["d"]; erg = {}; karten = {}
    if a.stl:
        import trimesh; m = trimesh.load(a.stl); m.apply_scale(a.massstab / 1000.0); innen = np.zeros(len(P), bool)
        for i in range(0, len(P), 500000): innen[i:i + 500000] = m.contains(P[i:i + 500000])
        print(f"  Stuetzpunkte im Modell: {innen.sum()} von {len(P)}"); P, K, RI = P[innen], K[innen], RI[innen]
    L_ = F["fassaden"] if isinstance(F.get("fassaden"), list) else [dict(v, id=k) for k, v in F.items() if isinstance(v, dict)]
    fs = {v.get("id", "f%02d" % i): v for i, v in enumerate(L_) if "n" in v and v.get("flaeche_m2", 0) >= a.min_flaeche}
    # Zuordnung: Fassade mit kleinster Tiefe >= 0, innerhalb u/z (Rand 0,5 m)
    best = np.full(len(P), -1); bt = np.full(len(P), np.inf); U = {}
    for f, v in fs.items():
        n = np.array(v["n"]); dd = np.array(v["d"]); o = np.array(v["o"]); rel = P[:, :2] - o; u = rel @ dd; tief = -(rel @ n)
        ok = (tief >= 0) & (tief <= a.max_tiefe) & (u >= v["u"][0] - 0.5) & (u <= v["u"][1] + 0.5) & (P[:, 2] >= v["z"][0]) & (P[:, 2] <= v["z"][1]) & (tief < bt) & (-(DR[RI][:, :2] @ n) >= np.cos(np.radians(a.max_winkel)) - 1e-9)
        best[ok] = list(fs).index(f); bt[ok] = tief[ok]; U[f] = u
    for i, (f, v) in enumerate(fs.items()):
        q = best == i
        if q.sum() < 50: continue
        u0, z0 = v["u"][0], v["z"][0]; nu = int((v["u"][1] - u0) / a.zelle) + 1; nz = int((v["z"][1] - z0) / a.zelle) + 1
        iu = np.clip(((U[f][q] - u0) / a.zelle).astype(int), 0, nu - 1); iz = np.clip(((P[q, 2] - z0) / a.zelle).astype(int), 0, nz - 1); kk = K[q]; tt = bt[q]
        # je (Zelle, Kamera) groesste Tiefe, dann je Zelle k-groesster Wert ueber Kameras
        key = (iz * nu + iu).astype(np.int64) * 100000 + kk; o_ = np.lexsort((-tt, key)); key, tt2 = key[o_], tt[o_]; erst = np.r_[True, key[1:] != key[:-1]]
        zk, tk = key[erst] // 100000, tt2[erst]; o2 = np.lexsort((-tk, zk)); zk, tk = zk[o2], tk[o2]
        start = np.r_[0, np.where(zk[1:] != zk[:-1])[0] + 1]; anz = np.diff(np.r_[start, len(zk)])
        M = np.zeros(nz * nu); g = anz >= a.min_kameras; M[zk[start[g]]] = tk[start[g] + a.min_kameras - 1]; M = M.reshape(nz, nu)
        NK = np.zeros(nz * nu); NK[zk[start]] = anz; NK = NK.reshape(nz, nu)                              # verschiedene Kameras je Zelle (Belegstaerke)
        karten[f] = (M, u0, z0); offen = M > 0.5
        erg[f] = dict(n=v["n"], u=v["u"], z=v["z"], zelle=a.zelle, flaeche_offen_m2=round(float(offen.sum() * a.zelle ** 2), 1),
                      tiefe_p90_m=round(float(np.percentile(M[offen], 90)), 2) if offen.any() else 0.0, raster=np.round(M, 2).tolist(), kameras=NK.astype(int).tolist())
        print(f"  {f}: {erg[f]['flaeche_offen_m2']:6.1f} m2 Freiraum > 0,5 m hinter der Ebene, Tiefe p90 {erg[f]['tiefe_p90_m']:.2f} m")
    json.dump(dict(fassaden=erg, quelle="freiraum_fassaden.py aus freiraum_pruefen.py strahlen.npz", min_kameras=a.min_kameras), open(os.path.join(a.aus, "freiraum_fassaden.json"), "w"))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    ks = list(karten); f_, ax = plt.subplots(1, max(1, len(ks)), figsize=(6 * max(1, len(ks)), 6), squeeze=False)
    for a_, f in zip(ax[0], ks):
        M, u0, z0 = karten[f]; im = a_.imshow(np.where(M > 0, M, np.nan), origin="lower", extent=[u0, u0 + M.shape[1] * a.zelle, z0, z0 + M.shape[0] * a.zelle], cmap="viridis", vmin=0, vmax=5)
        a_.set_title(f"{f} n=({fs[f]['n'][0]:+.2f},{fs[f]['n'][1]:+.2f}): Freiraumtiefe hinter Modellebene (m)"); a_.set_xlabel("u (m)"); a_.set_ylabel("z (m)"); plt.colorbar(im, ax=a_, shrink=0.7)
    plt.tight_layout(); plt.savefig(os.path.join(a.aus, "freiraum_fassaden.jpg"), dpi=70); print("->", os.path.join(a.aus, "freiraum_fassaden.jpg"))


if __name__ == "__main__":
    main()
