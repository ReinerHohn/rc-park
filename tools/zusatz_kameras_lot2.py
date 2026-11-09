#!/usr/bin/env python3
"""zusatz_kameras_lot2.py - Posen nachregistrierter Zusatzbilder (zusatzfotos_registrieren.py, sparse_handy/0) in den lot2-Kamerarahmen bringen
und an eine vorhandene Kameradatei (Format kam_lot2.json: je Bild Rn, tn, C, f, cx, cy, W, H, modell, params) ANHAENGEN (2026-11-09).

Rahmenkette (geprueft an allen 440 Kameras des Kaufhaus-Netzes, Fehler 1e-14): Referenz-sparse liegt im "gemeinsam"-Rahmen;
  X_netz = s*R*X + t             (T_...npz mit Feldern s, R, t)
  X_lot2 = Rw*(X_netz - piv) + piv + (0,0,dz)   (<kam>.rot.json aus rahmen_lot_foto.py: Rw, piv, dz)
Kamera (x_cam = Rn X + tn): Rn' = Rn R^T, tn' = s*tn - Rn R^T t; Rn'' = Rn' Rw^T, tn'' = tn' + Rn' piv - Rn' Rw^T (piv + dzv).
Aufruf: python -I tools/zusatz_kameras_lot2.py --kam kam_lot2.json --aus kam_lot2_video.json --T T_gemeinsam_nach_netz.npz --rot kam_lot2.json.rot.json
          --ziel ZIEL1 [ZIEL2 ...] [--quelle name1 name2 ...] --bilder-aus ORDNER [--zmin 1.5 --zmax 6]
ZIEL = Ordner einer zusatzfotos_registrieren-Kette (vorbereitet.json, registrierung.json, sparse_handy/0). Nur Bilder mit skala 1 und ohne
Beschnitt werden auf die ORIGINALDATEI verlinkt, sonst auf ZIEL/bilder/<name> (Kamera gilt fuer das vorbereitete Bild).
Pruefungen (Exit 2): Kamerahoehe z in [zmin, zmax] fuer >= 90 % der neuen Bilder; Reprojektionsfehler (registrierung.json) je Bild gemeldet.
Nichts Objektspezifisches; die alte Kameradatei wird nicht veraendert."""
import sys, os, json, argparse
import numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kam", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--T", required=True); ap.add_argument("--rot", required=True)
    ap.add_argument("--ziel", nargs="+", required=True); ap.add_argument("--quelle", nargs="*", help="Kennung je ZIEL (z. B. video_iphone video_handy)")
    ap.add_argument("--bilder-aus", required=True); ap.add_argument("--zmin", type=float, default=1.5); ap.add_argument("--zmax", type=float, default=6.0)
    a = ap.parse_args(argv)
    import pycolmap
    T = np.load(a.T); Rs = np.asarray(T["R"], float); s = float(T["s"]); t = np.asarray(T["t"], float)
    rot = json.load(open(a.rot)); Rw = np.array(rot["Rw"], float); piv = np.array(rot["piv"], float); dzv = np.array([0, 0, float(rot["dz"])])
    K = json.load(open(a.kam)); alt = set(K); out = dict(K); os.makedirs(a.bilder_aus, exist_ok=True)
    quellen = a.quelle or [os.path.basename(os.path.normpath(z)) for z in a.ziel]
    if len(quellen) != len(a.ziel): raise SystemExit("--quelle muss je ZIEL eine Kennung haben")
    bericht = {}; Z = []
    for ziel, q in zip(a.ziel, quellen):
        V = json.load(open(os.path.join(ziel, "vorbereitet.json")))["bilder"]; Rg = json.load(open(os.path.join(ziel, "registrierung.json")))
        rec = pycolmap.Reconstruction(os.path.join(ziel, "sparse_handy", "0")); n_neu = 0; errs = []
        for im in rec.images.values():
            n = im.name
            if n not in V or not im.has_pose: continue
            if n in alt: raise SystemExit(f"Name {n} schon in {a.kam} - Kollision")
            cw = im.cam_from_world(); Rn = cw.rotation.matrix(); tn = np.asarray(cw.translation, float); cam = im.camera
            R1 = Rn @ Rs.T; t1 = s * tn - Rn @ Rs.T @ t                       # gemeinsam -> netz
            R2 = R1 @ Rw.T; t2 = t1 + R1 @ piv - R1 @ Rw.T @ (piv + dzv)        # netz -> lot2
            C = -R2.T @ t2; p = [float(x) for x in cam.params]
            e = dict(Rn=R2.tolist(), tn=t2.tolist(), C=C.tolist(), f=p[0], cx=p[1], cy=p[2], W=int(cam.width), H=int(cam.height), modell=cam.model.name, params=p,
                     quelle=q, reproj_px=Rg["bilder"].get(n, {}).get("reproj_mittel_px"), inlier=Rg["bilder"].get(n, {}).get("inlier"))
            out[n] = e; n_neu += 1; Z.append(C[2]); errs.append(e["reproj_px"] or 0.0)
            info = V[n]; src = os.path.realpath(info["quelle"]) if (abs(info["skala"] - 1) < 1e-9 and info["orig"] == info["bild"]) else os.path.join(ziel, "bilder", n)
            dst = os.path.join(a.bilder_aus, n)
            if os.path.lexists(dst): os.remove(dst)
            os.symlink(src, dst)
        bericht[q] = dict(ziel=ziel, neu=n_neu, von=len(V), reproj_mittel_px=float(np.mean(errs)) if errs else None, kamera_gruppen=sorted({(out[n]["W"], out[n]["H"], round(out[n]["f"], 1)) for n in out if out[n].get("quelle") == q}))
    Z = np.array(Z); ok = ((Z >= a.zmin) & (Z <= a.zmax)).mean() if len(Z) else 0.0
    json.dump(out, open(a.aus, "w"))
    bericht["gesamt"] = dict(alt=len(alt), neu=int(len(Z)), z_5_50_95=[float(x) for x in np.percentile(Z, [5, 50, 95])] if len(Z) else None, anteil_z_im_fenster=float(ok), zmin=a.zmin, zmax=a.zmax, aus=a.aus, bilder=a.bilder_aus)
    json.dump(bericht, open(a.aus + ".bericht.json", "w"), indent=1); print(json.dumps(bericht, indent=1))
    if ok < 0.9: print(f"FEHLER: nur {ok:.0%} der neuen Kameras mit z in [{a.zmin}, {a.zmax}]"); return 2
    return 0


if __name__ == "__main__": sys.exit(main())
