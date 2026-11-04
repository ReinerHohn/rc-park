#!/usr/bin/env python3
"""netz_vergleich.py - GENERISCH: zwei Ausrichtungen DESSELBEN SfM-Netzes im Modellsystem vergleichen (gleiche Bildnamen, gleiche Punkt-IDs).

Zweck (Nutzerauftrag 2026-11-04 "beweise, dass die neue Pipeline auf das alte Martinstor-Ergebnis kommt"): Referenz = alte Kette (Handpicks, sfm_ausrichten.py),
Kandidat = neue Kette ohne Picks (sfm_lod2_ausrichten.py + sfm_lod2_buendel.py). Gemessen werden Kamerastandorte, Punktlagen (je Punkt-ID), Massstab und
Hoehenstreckung (z_neu = a z_alt + b) und die Punktabweichung in Hoehenbaendern.
  /media/oem/scan/venv-colmap/bin/python -I tools/netz_vergleich.py <sparse_referenz> <sparse_kandidat> [--json aus.json] [--name tag]
"""
import sys, os, json, argparse, numpy as np
import pycolmap


def lade(p):
    r = pycolmap.Reconstruction(p)
    C = {im.name: im.projection_center() if hasattr(im, "projection_center") else -im.cam_from_world().rotation.matrix().T @ np.array(im.cam_from_world().translation) for im in r.images.values() if im.has_pose}
    P = {pid: np.array(pt.xyz) for pid, pt in r.points3D.items()}
    F = {im.name: float(r.cameras[im.camera_id].params[0]) for im in r.images.values() if im.has_pose}
    return C, P, F


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ref"); ap.add_argument("kand"); ap.add_argument("--json"); ap.add_argument("--name", default="vergleich"); a = ap.parse_args()
    Cr, Pr, Fr = lade(a.ref); Ck, Pk, Fk = lade(a.kand)
    nm = sorted(set(Cr) & set(Ck)); ids = sorted(set(Pr) & set(Pk))
    dc = np.array([np.linalg.norm(np.array(Cr[n]) - np.array(Ck[n])) for n in nm]); A = np.array([Pr[i] for i in ids]); B = np.array([Pk[i] for i in ids])
    d = np.linalg.norm(A - B, axis=1); dz = B[:, 2] - A[:, 2]
    # robuste Hoehenstreckung und Massstab (Punkte mit |d| < p90)
    k = d < np.percentile(d, 90); az, bz = np.polyfit(A[k, 2], B[k, 2], 1)
    ma, mb = A[k].mean(0), B[k].mean(0); s = np.sqrt(((B[k] - mb) ** 2).sum() / ((A[k] - ma) ** 2).sum())
    baender = {}
    for z0, z1 in ((-2, 5), (5, 15), (15, 25), (25, 35), (35, 45), (45, 70)):
        m = (A[:, 2] >= z0) & (A[:, 2] < z1)
        if m.sum() >= 20: baender[f"{z0}..{z1} m"] = dict(n=int(m.sum()), d_median_m=float(np.median(d[m])), dz_median_m=float(np.median(dz[m])))
    df = np.array([Fk[n] / Fr[n] for n in nm])
    out = dict(werkzeug="netz_vergleich.py", referenz=a.ref, kandidat=a.kand, kameras=len(nm), punkte=len(ids),
               kamera_abstand_m=dict(median=float(np.median(dc)), p90=float(np.percentile(dc, 90)), max=float(dc.max())),
               punkt_abstand_m=dict(median=float(np.median(d)), p90=float(np.percentile(d, 90))), dz_median_m=float(np.median(dz)),
               massstab_kand_zu_ref=float(s), hoehenstreckung=dict(a=float(az), b_m=float(bz)), brennweite_kand_zu_ref=dict(median=float(np.median(df)), p10=float(np.percentile(df, 10)), p90=float(np.percentile(df, 90))), hoehenbaender=baender)
    print(f"{len(nm)} gemeinsame Kameras, {len(ids)} gemeinsame Punkte")
    print(f"Kamerastandorte: Median {out['kamera_abstand_m']['median']:.2f} m, p90 {out['kamera_abstand_m']['p90']:.2f} m, max {out['kamera_abstand_m']['max']:.2f} m")
    print(f"Punkte: Median {out['punkt_abstand_m']['median']:.2f} m, p90 {out['punkt_abstand_m']['p90']:.2f} m; dz Median {out['dz_median_m']:+.2f} m")
    print(f"Massstab Kandidat/Referenz {s:.4f}; Hoehenstreckung z_kand = {az:.4f} z_ref {bz:+.2f} m; Brennweite Kand/Ref Median {out['brennweite_kand_zu_ref']['median']:.3f}")
    for b, v in baender.items(): print(f"  Hoehe {b:>9s}: n={v['n']:5d}  |d| Median {v['d_median_m']:.2f} m  dz {v['dz_median_m']:+.2f} m")
    if a.json: os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True); json.dump(out, open(a.json, "w"), indent=1); print("geschrieben:", a.json)


if __name__ == "__main__":
    main()
