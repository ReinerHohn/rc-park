#!/usr/bin/env python3
"""restfeld_fassade.py - Restfeld je Fassade: Tiefe der Daten d*(u,z) gegen Tiefe des Modells, Zelle fuer Zelle (Konvergenzschleife, Nutzer 5.11. 17:00).

Stand der Technik (Recherche 5.11., scratchpad recherche_konvergenz.md): Scan2LoD3 / MLS2LoD3 / Texture2LoD3 arbeiten mit einem 2,5D-Feld je Fassade
(u, z, Tiefe in Wandkoordinaten) statt freier Voxel (unser roher Voxelversuch 5.11.: 460 Koerper). Dieses Werkzeug MISST nur (Generator unveraendert):
  Daten: Punkte der dichten Wolke (fused.ply, Ausrichtung wie sfm_dicht) mit >= --min-kameras Kameras (fused.ply.vis), im Band [-tief, +vor] m um die
         Fassadenebene; je Zelle (--zelle) die VORDERSTE robuste Tiefe (Quantil --q der Punkte, Vorzeichen: + = vor der Ebene/aussen).
  Modell: Strahl von +vor m vor der Ebene entlang -n auf das Modell-STL (erste Flaeche) -> Modelltiefe je Zelle.
  Rest = Daten - Modell (> 0: Daten weiter aussen = Modell fehlt Material (Erker, Gaube zu klein); < 0: Modell steht vor der gesehenen Flaeche).
Ausgabe --aus/restfeld.json (je Fassade: beobachteter Anteil, Median |Rest|, Flaeche |Rest| > --tol, Vorzeichen) + restfeld_<fid>.jpg (Daten|Modell|Rest).
Kennzahl fuer Konvergenz: MITTEL |Rest| ueber beobachtete Zellen je Fassade (lokal; globale Freiraumvolumen sind NICHT monoton, versuche.jsonl 5.11.).
  /media/oem/scan/venv-seg/bin/python -I tools/restfeld_fassade.py --stl M.stl --dicht DIR --ausrichtung A.json --fassaden fassaden.json --aus DIR
"""
import os, sys, json, argparse, time
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freiraum_pruefen import ply_lesen, vis_lesen


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--stl", required=True); ap.add_argument("--dicht", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--fassaden", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--zelle", type=float, default=0.10)
    ap.add_argument("--vor", type=float, default=2.0); ap.add_argument("--tief", type=float, default=4.0); ap.add_argument("--min-kameras", type=int, default=3)
    ap.add_argument("--min-punkte", type=int, default=3); ap.add_argument("--q", type=float, default=0.8, help="Quantil der Tiefe je Zelle (vorderste robuste Flaeche)")
    ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--nur", nargs="*")
    ap.add_argument("--dach", action="store_true"); ap.add_argument("--dach-min", type=float, default=20.0)
    a = ap.parse_args(argv); t0 = time.time(); os.makedirs(a.aus, exist_ok=True)
    tr = json.load(open(a.ausrichtung))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    X = ((ply_lesen(os.path.join(a.dicht, "fused.ply")) - ta) @ Ra) / s
    pi, _ = vis_lesen(os.path.join(a.dicht, "fused.ply.vis")); nk = np.bincount(pi, minlength=len(X)); X = X[nk >= a.min_kameras]
    print(f"{len(X)} Punkte mit >= {a.min_kameras} Kameras ({time.time() - t0:.0f} s)", flush=True)
    m = trimesh.load(a.stl); m.apply_scale(a.massstab / 1000.0)
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    rmi = RayMeshIntersector(m); FA = json.load(open(a.fassaden))["fassaden"]
    erg = dict(stl=os.path.abspath(a.stl), modell_volumen_m3=round(abs(float(m.volume)), 3), parameter=vars(a), fassaden={},
               gegenprobe="5.11. 17:03: Modell s3_v9 um 0,30 m entlang f02-Normale verschoben -> Rest-Median -0,203 -> -0,503 (folgt exakt)")
    ebenen = []
    for F in FA:                                                                                   # Waende aus fassade_ortho (v = z)
        n = np.array(F["n"], float); n = np.r_[n[:2], 0.0] if len(n) == 2 else n; dd = np.array(F["d"], float); dd = np.r_[dd[:2], 0.0] if len(dd) == 2 else dd
        o = np.array(F["o"], float); o = np.r_[o[:2], 0.0] if len(o) == 2 else o; r = F["raster"]
        ebenen.append(dict(id=F["id"], n=n, dd=dd, e=np.array([0, 0, 1.0]), o=o, u0=r["u0"], u1=r["u0"] + r["nu"] * r["zelle"], z1=r["z1"], z0=r["z1"] - r["nz"] * r["zelle"]))
    if a.dach:                                                                                     # Dachflaechen aus dem Modell (allgemein: alle geneigten ebenen Flaechen >= --dach-min m2)
        fn = m.face_normals; ar = m.area_faces; sel = np.where((fn[:, 2] > 0.2) & (fn[:, 2] < 0.97))[0]
        key = np.c_[np.round(fn[sel] * 20), np.round(np.einsum("ij,ij->i", m.triangles_center[sel], fn[sel]) / 0.5)]
        _, lab = np.unique(key, axis=0, return_inverse=True); lab = lab.ravel()
        for j in range(lab.max() + 1):
            fs = sel[lab == j]
            if ar[fs].sum() < a.dach_min: continue
            n = (fn[fs] * ar[fs, None]).sum(0); n /= np.linalg.norm(n); dd = np.array([-n[1], n[0], 0.0]); dd /= np.linalg.norm(dd); e = np.cross(n, dd); e = e if e[2] > 0 else -e
            V = m.vertices[m.faces[fs]].reshape(-1, 3); o = V.mean(0); uu = (V - o) @ dd; vv = (V - o) @ e
            ebenen.append(dict(id=f"d{len([x for x in ebenen if x['id'].startswith('d')]):02d}", n=n, dd=dd, e=e, o=o, u0=float(uu.min()), u1=float(uu.max()), z1=float(vv.max()), z0=float(vv.min())))
    for E_ in ebenen:
        fid = E_["id"]
        if a.nur and fid not in a.nur: continue
        n, dd, e3, o, u0, u1, z0, z1 = E_["n"], E_["dd"], E_["e"], E_["o"], E_["u0"], E_["u1"], E_["z0"], E_["z1"]
        nu, nz = int(np.ceil((u1 - u0) / a.zelle)), int(np.ceil((z1 - z0) / a.zelle))
        rel = X - o; w = rel @ n; u = rel @ dd; zz = rel @ e3 + (o[2] if e3[2] > 0.999 else 0.0)
        k = (w > -a.tief) & (w < a.vor) & (u >= u0) & (u < u1) & (zz >= z0) & (zz < z1)
        iu = ((u[k] - u0) / a.zelle).astype(int); iz = ((z1 - zz[k]) / a.zelle).astype(int); wk = w[k]
        cell = iz * nu + iu; order = np.lexsort((wk, cell)); cs, ws = cell[order], wk[order]
        st = np.searchsorted(cs, np.arange(nu * nz)); en = np.searchsorted(cs, np.arange(nu * nz), side="right"); cnt = en - st
        daten = np.full(nu * nz, np.nan); ok = cnt >= a.min_punkte
        idx = st[ok] + np.minimum(cnt[ok] - 1, (a.q * (cnt[ok] - 1)).round().astype(int)); daten[ok] = ws[idx]
        daten = daten.reshape(nz, nu); cnt = cnt.reshape(nz, nu)
        # Modelltiefe: Strahlen von +vor entlang -n
        gu, gz = np.meshgrid(u0 + (np.arange(nu) + 0.5) * a.zelle, z1 - (np.arange(nz) + 0.5) * a.zelle)
        P0 = o[None] + gu.reshape(-1, 1) * dd[None] + (gz.reshape(-1, 1) - (o[2] if e3[2] > 0.999 else 0.0)) * e3[None] + a.vor * n[None]
        loc, ri, _ = rmi.intersects_location(P0, np.repeat(-n[None], len(P0), 0), multiple_hits=False)
        modell = np.full(len(P0), np.nan); modell[ri] = a.vor - np.einsum("ij,j->i", loc - P0[ri], -n); modell[modell < -a.tief] = np.nan; modell = modell.reshape(nz, nu)
        modell_r = np.where(np.isnan(modell), -a.tief, modell)                                     # kein Modell im Band = Durchsicht bis -tief
        rest = daten - modell_r; beob = ~np.isnan(daten)
        ra = np.abs(rest[beob]); flae = a.zelle ** 2
        erg["fassaden"][fid] = dict(n=[round(float(x), 5) for x in n], o=[round(float(x), 4) for x in o], dd=[round(float(x), 5) for x in dd], e=[round(float(x), 5) for x in e3], zellen=int(nu * nz), beobachtet_anteil=round(float(beob.mean()), 3), rest_mittel_abs_m=round(float(ra.mean()), 3) if ra.size else None,
                                    rest_median_abs_m=round(float(np.median(ra)), 3) if ra.size else None, flaeche_ueber_tol_m2=round(float((ra > a.tol).sum() * flae), 1),
                                    material_fehlt_m2=round(float((rest[beob] > a.tol).sum() * flae), 1), material_zuviel_m2=round(float((rest[beob] < -a.tol).sum() * flae), 1))
        np.savez_compressed(os.path.join(a.aus, f"restfeld_{fid}.npz"), daten=daten, modell=modell, anzahl=cnt, u0=u0, z1=z1, zelle=a.zelle)
        f_ = lambda A, lo, hi: cv2.applyColorMap(np.clip((np.nan_to_num(A, nan=lo) - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
        bd = f_(daten, -a.tief, a.vor); bd[~beob] = 40; bm = f_(modell_r, -a.tief, a.vor)
        br = f_(rest, -1.0, 1.0); br[~beob] = 40; br[beob & (np.abs(np.nan_to_num(rest)) <= a.tol)] = (255, 255, 255)
        sk = max(1, int(round(400 / max(nz, 1)))); bild = cv2.hconcat([cv2.resize(x, (nu * sk, nz * sk), interpolation=cv2.INTER_NEAREST) for x in (bd, bm, br)])
        cv2.putText(bild, f"{fid}: Daten | Modell (Tiefe -{a.tief}..+{a.vor} m) | Rest (blau Modell zu weit aussen, rot fehlt, weiss <= {a.tol} m)", (5, 18), 0, 0.5, (255, 255, 255), 1)
        cv2.imwrite(os.path.join(a.aus, f"restfeld_{fid}.jpg"), bild)
        print(f"{fid}: {erg['fassaden'][fid]}  ({time.time() - t0:.0f} s)", flush=True)
    erg["sekunden"] = round(time.time() - t0, 1); json.dump(erg, open(os.path.join(a.aus, "restfeld.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
