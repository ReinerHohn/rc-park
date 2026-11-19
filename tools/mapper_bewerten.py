#!/usr/bin/env python3
"""mapper_bewerten.py <sparse-ordner> --fotos <fotoordner> [--label NAME] [--sek N] [--befehl "..."] [--protokoll datei.jsonl]
Einheitliche Kennzahlen fuer SfM-Varianten (globaler/schrittweiser Mapper), damit Versuche vergleichbar bleiben (19.11.2026, modelle/GLOBALER_MAPPER_STABIL.md).
Je Modell: Teilmodelle, groesstes Teilmodell (Bilder, Punkte, mittlerer Reprojektionsfehler, Spurlaenge), Kameras je Gruppe (eigen/fotos/mapillary/Video),
Brennweiten-Streuung je Videoclip (ein Clip = eine Kamera, wenn er nicht zoomt), Plausibilitaet (f/Breite 0,3..12 wie tools/kamera_plausibel.py, Standort < 20 x Medianabstand),
GPS-Tor (tools/mapper_gps_vergleich.py --alle: Median, Anteil > 15 m; Foto-GPS hat 30-40 % falsche Geotags, nur die Mehrheit zaehlt),
Kamera-Abdeckung je 30-Grad-Sektor (tools/kamera_abdeckung.py), Hoehenstreuung der Kameras in m (Ebene durch den Kamerakern, Massstab aus dem GPS-Fit; ANNAHME: Strassenniveau eben,
p90 > 10 m = Kameras 'in der Luft' wie Schwabentor 13.11.). Schreibt eine JSON-Zeile ins Protokoll. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap)."""
import sys, os, re, json, time, subprocess, argparse, collections
import numpy as np, pycolmap
from PIL import Image

T = os.path.dirname(os.path.abspath(__file__))
_cfw = lambda im: im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world   # pycolmap 4.2.1: Methode; neuere: Attribut


def gps_xy(pfad):
    try:
        g = (Image.open(pfad)._getexif() or {}).get(34853); dm = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        la, lo = dm(g[2]), dm(g[4]); return np.array([(lo - 7.85) * 111320 * np.cos(np.radians(la)), (la - 47.99) * 110574])
    except Exception: return None


def gps_fit(C, fd, nah_m=None, praefix=""):
    """robuste 2D-Aehnlichkeit Kamerakern -> Foto-GPS (wie mapper_gps_vergleich.py); gibt Massstab m/Einheit, Median-Rest, Anteil > 15 m, n.
    nah_m: nur Fotos, deren GPS hoechstens nah_m vom GPS-Median liegt (Martinstor: Fernfotos vom Schlossberg/KaJo 300-500 m, dort sind Brennweite und
    Abstand kaum trennbar -> Kernpruefung getrennt ausweisen)."""
    pf = {os.path.basename(x): x for x in __import__("glob").glob(os.path.join(fd, "**", "*"), recursive=True)}
    keys = [k for k in C if k in pf]; P = {k: gps_xy(pf[k]) for k in keys}; keys = [k for k in keys if P[k] is not None]
    if nah_m and len(keys) >= 3:
        med = np.median(np.array([P[k] for k in keys]), 0); keys = [k for k in keys if np.linalg.norm(P[k] - med) <= nah_m]
    if len(keys) < 5: return {praefix + "n_gps": len(keys)}
    X = np.array([C[k] for k in keys]); Y = np.array([P[k] for k in keys])
    Xc = X - np.median(X, 0); d = np.linalg.norm(Xc, axis=1); kern = d <= np.percentile(d, 75)
    _, _, Vt = np.linalg.svd(Xc[kern], full_matrices=False); X2 = Xc @ Vt[:2].T
    best = None
    for sp in (1, -1):
        Z = X2 * [1, sp]; sel = kern.copy(); s = 1.0
        for _ in range(6):
            mx, my = Z[sel].mean(0), Y[sel].mean(0); U, S_, V2 = np.linalg.svd((Y[sel] - my).T @ (Z[sel] - mx) / sel.sum())
            D = np.diag([1, np.sign(np.linalg.det(U @ V2))]); R = U @ D @ V2; s = np.trace(np.diag(S_) @ D) / Z[sel].var(0).sum()
            r = np.linalg.norm((s * (R @ (Z - mx).T)).T + my - Y, axis=1); sel = r < max(2.5 * np.median(r), 10)
            if sel.sum() < 3: sel = kern.copy(); break
        if best is None or np.median(r) < best[0]: best = (float(np.median(r)), float(np.mean(r > 15) * 100), float(s))
    return {praefix + "n_gps": len(keys), praefix + "gps_median_m": round(best[0], 1), praefix + "gps_anteil_ueber_15m": round(best[1]), praefix + "massstab_m_je_einheit": best[2]}


def modell_vergleich(C, ref_sparse, massstab=None):
    """3D-Aehnlichkeit (Umeyama, robust ueber 6 Runden) ueber gemeinsame registrierte Bilder gegen ein Referenzmodell; Rest in Referenz-Einheiten
    bzw. in m (massstab = m je Referenzeinheit, z.B. aus dessen GPS-Fit). Stabilitaetsmass: zwei Laeufe/Varianten muessen hier uebereinstimmen."""
    mods = [k for k in os.listdir(ref_sparse) if os.path.isfile(os.path.join(ref_sparse, k, "cameras.bin"))]
    if not mods: return dict(vergleich="Referenz ohne Modell")
    rr = max((pycolmap.Reconstruction(os.path.join(ref_sparse, k)) for k in mods), key=lambda r: r.num_reg_images())
    R_ = {os.path.basename(im.name): im.projection_center() for im in rr.images.values() if im.has_pose}
    keys = [k for k in C if k in R_]
    if len(keys) < 5: return dict(vergleich_n=len(keys))
    X = np.array([C[k] for k in keys]); Y = np.array([R_[k] for k in keys]); sel = np.ones(len(keys), bool)
    RR = {os.path.basename(im.name): _cfw(im).rotation.matrix() for im in rr.images.values() if im.has_pose}
    # Drehung der Ausrichtung aus den KAMERA-ROTATIONEN (chordaler Mittelwert von R_ref^T R_src), nicht aus den Standorten: Kameras entlang EINER Strasse
    # (Martinstor) liegen fast auf einer Linie, da ist die Drehung um die Strassenachse aus Standorten unbestimmt (Fehlmessung 16 Grad am 19.11.).
    RA = np.array([ROT[k] for k in keys]); RB = np.array([RR[k] for k in keys])
    for _ in range(6):
        M = sum(RB[i].T @ RA[i] for i in np.where(sel)[0]); U, _, Vt = np.linalg.svd(M); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt   # R: Welt src -> Welt ref
        mx, my = X[sel].mean(0), Y[sel].mean(0); Xr = (R @ (X - mx).T).T; s = float(np.sum((Y[sel] - my) * Xr[sel]) / np.sum(Xr[sel] ** 2))
        r = np.linalg.norm(s * Xr + my - Y, axis=1); w = np.array([np.degrees(np.arccos(np.clip((np.trace(RB[i] @ (RA[i] @ R.T).T) - 1) / 2, -1, 1))) for i in range(len(keys))])
        neu = (r < max(2.5 * np.median(r), 1e-9)) & (w < max(2.5 * np.median(w), 0.5))
        if neu.sum() < 4: break
        sel = neu
    e = dict(vergleich_n=len(keys), vergleich_inlier=int(sel.sum()), vergleich_rot_median_grad=round(float(np.median(w)), 2), vergleich_rot_anteil_ueber_2grad=round(float(np.mean(w > 2) * 100)))
    rk = np.linalg.norm(Y[sel] - Y[sel].mean(0), axis=1).mean()   # Rest relativ zum Kernradius der Referenz (massstabsfrei)
    e.update(vergleich_median_einheiten=round(float(np.median(r)), 4), vergleich_median_rel_kern=round(float(np.median(r) / rk), 4), vergleich_anteil_ueber_10proz_kern=round(float(np.mean(r > 0.1 * rk) * 100)))
    if massstab: r = r * massstab; e.update(vergleich_median_m=round(float(np.median(r)), 1), vergleich_anteil_ueber_5m=round(float(np.mean(r > 5) * 100)))
    return e


ROT, ROT_REF = {}, None   # Rotationen (cam_from_world) des bewerteten Modells, gefuellt in bewerten()


def bewerten(sparse, fd, vergleich="", nah_m=120.0):
    mods = sorted([k for k in os.listdir(sparse) if os.path.isfile(os.path.join(sparse, k, "cameras.bin"))], key=lambda k: int(k) if k.isdigit() else 999)
    if not mods: return dict(fehler="kein Teilmodell", n_modelle=0)
    recs = {k: pycolmap.Reconstruction(os.path.join(sparse, k)) for k in mods}
    groesstes = max(recs, key=lambda k: recs[k].num_reg_images()); r = recs[groesstes]
    e = dict(n_modelle=len(mods), groesstes=groesstes, n_reg=r.num_reg_images(), n_bilder_modelle=sorted([x.num_reg_images() for x in recs.values()], reverse=True)[:6],
             n_punkte=r.num_points3D(), reproj_px=round(r.compute_mean_reprojection_error(), 3), spur=round(r.compute_mean_track_length(), 2), beob_je_bild=round(r.compute_mean_observations_per_reg_image(), 1))
    C, grp, clipf, unplaus_f, pos = {}, collections.Counter(), collections.defaultdict(list), 0, []
    global ROT, ROT_REF; ROT = {}; ROT_REF = True
    for im in r.images.values():
        if not im.has_pose: continue
        n = os.path.basename(im.name); C[n] = im.projection_center(); pos.append(C[n]); cam = im.camera; f = cam.focal_length / cam.width; ROT[n] = _cfw(im).rotation.matrix()
        if "__vf_" in n: grp["video"] += 1; clipf[n.rsplit("__vf_", 1)[0]].append(f)
        else: grp[n.split("__")[0]] += 1
        if not (0.3 <= f <= 12): unplaus_f += 1
    pos = np.array(pos); d = np.linalg.norm(pos - np.median(pos, 0), axis=1); fern = int((d > 20 * np.median(d)).sum())
    e.update(gruppen=dict(grp), f_unplausibel=unplaus_f, kameras_fern=fern)
    cv = {k: round(float(np.std(v) / np.mean(v)), 3) for k, v in clipf.items() if len(v) >= 5}
    e["clip_f_cv"] = dict(sorted(cv.items(), key=lambda kv: -kv[1])); e["clip_f_cv_median"] = round(float(np.median(list(cv.values()))), 3) if cv else None
    e.update(gps_fit(C, fd)); e.update(gps_fit(C, fd, nah_m=nah_m, praefix="nah_"))
    if vergleich:
        ms = None
        try: ms = gps_fit({os.path.basename(im.name): im.projection_center() for im in max((pycolmap.Reconstruction(os.path.join(vergleich, k)) for k in os.listdir(vergleich) if os.path.isfile(os.path.join(vergleich, k, "cameras.bin"))), key=lambda r: r.num_reg_images()).images.values() if im.has_pose}, fd, nah_m=nah_m).get("massstab_m_je_einheit")
        except Exception: pass
        e.update(modell_vergleich(C, vergleich, ms)); e["vergleich_ref"] = os.path.abspath(vergleich)
    if e.get("massstab_m_je_einheit"):   # Hoehenstreuung: Ebene durch den Kamerakern (PCA), Abstand senkrecht in m
        kern = d <= np.percentile(d, 75); pc = pos[kern] - pos[kern].mean(0); _, _, Vt = np.linalg.svd(pc, full_matrices=False)
        h = np.abs((pos - pos[kern].mean(0)) @ Vt[2]) * e["massstab_m_je_einheit"]; e["hoehe_p50_m"] = round(float(np.percentile(h, 50)), 1); e["hoehe_p90_m"] = round(float(np.percentile(h, 90)), 1)
    o = subprocess.run([sys.executable, "-I", os.path.join(T, "kamera_abdeckung.py"), os.path.join(sparse, groesstes)], capture_output=True, text=True).stdout
    m = re.search(r"Sektor: (\{.*?\})", o); g = re.search(r"Luecke: (\d+) Grad", o)
    if m: sek = eval(m.group(1), {}, {}); e["sektoren_leer"] = sum(1 for v in sek.values() if v == 0); e["sektoren_min"] = min(sek.values()); e["sektoren"] = sek
    if g: e["luecke_grad"] = int(g.group(1))
    return e


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--fotos", required=True); ap.add_argument("--label", default=""); ap.add_argument("--sek", type=float, default=None)
    ap.add_argument("--befehl", default=""); ap.add_argument("--protokoll", default=""); ap.add_argument("--vergleich", default="", help="Referenz-Sparse (Stabilitaet: Rest ueber gemeinsame Bilder)")
    ap.add_argument("--nah-m", type=float, default=120.0, help="Kern-GPS: nur Fotos bis so viele m vom GPS-Median (ANNAHME 120)"); a = ap.parse_args()
    e = bewerten(a.sparse, a.fotos, a.vergleich, a.nah_m); e.update(label=a.label or os.path.basename(a.sparse.rstrip("/")), sparse=os.path.abspath(a.sparse), sek=a.sek, befehl=a.befehl, zeit=time.strftime("%Y-%m-%d %H:%M"))
    kurz = {k: e.get(k) for k in ("label", "n_modelle", "n_reg", "n_punkte", "reproj_px", "spur", "n_gps", "gps_median_m", "gps_anteil_ueber_15m", "nah_n_gps", "nah_gps_median_m", "nah_gps_anteil_ueber_15m", "hoehe_p50_m", "hoehe_p90_m", "luecke_grad", "sektoren_leer", "f_unplausibel", "kameras_fern", "clip_f_cv_median", "vergleich_n", "vergleich_inlier", "vergleich_median_m", "vergleich_anteil_ueber_5m", "vergleich_median_rel_kern", "vergleich_anteil_ueber_10proz_kern", "vergleich_rot_median_grad", "vergleich_rot_anteil_ueber_2grad", "gruppen", "sek") if k in e}
    print(json.dumps(kurz, ensure_ascii=False))
    if a.protokoll:
        with open(a.protokoll, "a") as fh: fh.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
