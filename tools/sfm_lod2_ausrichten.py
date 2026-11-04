#!/usr/bin/env python3
"""sfm_lod2_ausrichten.py - GENERISCH: SfM-Netz OHNE Handpicks an die amtliche Umgebung ausrichten (LoD2-Gebaeude + DGM1-Gelaende).

Kaltstart-Ersatz fuer sfm_ausrichten.py (das braucht gepickte LoD2-Eckkanten in K-*.json; ein neues Objekt hat keine; Plan B7).
Gesucht: Aehnlichkeit X_sfm = s * R @ X_modell + t (7 Parameter), Modellsystem = anker3d.json/objekt.json rahmen.
  1. Lot: Strassenfotos liegen fast in einer Ebene (Kamerazentren) -> Normale = Lot; Vorzeichen: die Mehrzahl der Punkte liegt UEBER den Kameras.
  2. Grob (2D): Netzpunkte waagrecht projizieren; Ziel = Wandlinien ALLER LoD2-Gebaeude im Umkreis (die Wolke enthaelt die Nachbarfassaden -
     die machen die Loesung eindeutig). Gittersuche Drehung x Massstab, Verschiebung je Paar per FFT-Korrelation.
  3. Fein (3D): Punkt-zu-Flaeche-Ausgleich (7 Parameter, getrimmt) gegen abgetastete LoD2-Waende/-Daecher und DGM1-Boden.
  4. Guete: Massstab-Sigma aus Teilstichproben (Bootstrap), Inlier-Anteil, Abstands-RMS, Kamerahoehen (Strassenfotos ~1,5-2 m: nur Pruefung).
Quellen-Blindheit: LoD2 kennt keine Aufbauten/Erker/Arkadentiefe -> Punkte dort sind Ausreisser (Trimmung), nicht Fehler der Ausrichtung.
Schreibt dasselbe Format wie sfm_ausrichten.py: messprotokoll/SFM-AUSRICHTUNG-<name>.json, sfm/sparse_modell_<name>, sfm/punkte_modell_<name>.npy.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_lod2_ausrichten.py modelle/<objekt>/objekt.json --sparse <pfad> --name <name> [--schreiben] [--radius 80]
"""
import sys, os, json, glob, math, argparse, numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pycolmap


def lod2_ziel(obj, radius, dichte=0.35):
    """LoD2-Flaechen (alle Gebaeude im Umkreis) im Modellsystem, abgetastet: Punkte, Normalen, Typ (0 Wand, 1 Dach)."""
    import lod2_gebaeude as LG
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"]); gel = R["gelaende"]
    gml = obj["lod2"]["gml"]; picked = LG.extract(gml, center=tuple(c0), radius=radius)
    lok = lambda P: np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - gel]
    pts, nrm, typ, wand2d, grund2d, eigen = [], [], [], [], [], []
    rng = np.random.default_rng(0)
    for meta, polys in picked:
        for t, P in polys:
            if t == "GroundSurface": grund2d.append(lok(P)[:, :2])
            if t not in ("WallSurface", "RoofSurface"): continue
            Q = lok(P); n = np.cross(Q[1] - Q[0], Q[2] - Q[0])
            for i in range(2, len(Q) - 1): n = n if np.linalg.norm(n) > 1e-6 else np.cross(Q[i] - Q[0], Q[i + 1] - Q[0])
            if np.linalg.norm(n) < 1e-9: continue
            n = n / np.linalg.norm(n)
            for i in range(1, len(Q) - 1):                                                    # Faecher-Dreiecke, flaechentreu abgetastet
                a, b, c = Q[0], Q[i], Q[i + 1]; A = 0.5 * np.linalg.norm(np.cross(b - a, c - a)); k = max(1, int(A / dichte ** 2))
                u = rng.random((k, 2)); f = u.sum(1) > 1; u[f] = 1 - u[f]
                pts.append(a + u[:, :1] * (b - a) + u[:, 1:] * (c - a)); nrm.append(np.repeat(n[None], k, 0)); typ.append(np.full(k, 0 if t == "WallSurface" else 1))
                eigen.append(np.full(k, meta.get("id") == obj["lod2"].get("id")))
            if t == "WallSurface": wand2d.append(Q[:, :2])
    return np.vstack(pts), np.vstack(nrm), np.concatenate(typ), wand2d, grund2d, len(picked), np.concatenate(eigen)


def dgm_ziel(obj, halb):
    """DGM1-Boden im Modellsystem (Punkte, Normale nach oben); fehlt die Kachel: Ebene z = 0 (ANNAHME)."""
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    ek, nk = int(c0[0] // 1000), int(c0[1] // 1000)
    f = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/dgm1_32_{ek}_{nk}_1_bw_*.xyz", recursive=True)
    if f:
        g = np.loadtxt(f[0]); L = np.c_[(g[:, :2] - c0) @ xh, (g[:, :2] - c0) @ yh, g[:, 2] - R["gelaende"]]
        L = L[(np.abs(L[:, 0]) < halb) & (np.abs(L[:, 1]) < halb)]; quelle = os.path.basename(f[0])
    else:
        xx, yy = np.meshgrid(np.arange(-halb, halb, 1.0), np.arange(-halb, halb, 1.0)); L = np.c_[xx.ravel(), yy.ravel(), np.zeros(xx.size)]; quelle = "ANNAHME Ebene z=0 (keine DGM1-Kachel)"
    return L, np.repeat([[0, 0, 1.0]], len(L), 0), quelle


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sparse", required=True); ap.add_argument("--name", default=""); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--radius", type=float, default=80.0, help="LoD2-Gebaeude in diesem Umkreis um die Objektmitte (m)"); ap.add_argument("--zelle", type=float, default=0.25, help="Rasterweite Grobsuche (m)")
    ap.add_argument("--mitte-max", type=float, default=20.0, help="Wolkenmitte hoechstens so weit von der Objektmitte (m): die Bilder sind um das Objekt ausgewaehlt")
    ap.add_argument("--kamerahoehe", nargs=2, type=float, default=[1.6, 1.0], metavar=("H0", "SIGMA"), help="ANNAHME Strassenfotos: Kamerahoehe ueber Boden (robust gewichtet)")
    ap.add_argument("--kamera-gewicht", type=float, default=0.3, help="Gewicht der Kamerahoehen gegen die Punkte (0 = aus)")
    ap.add_argument("--wand", help="ignoriert (Kompatibilitaet zu sfm_ausrichten.py-Aufrufen)"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od)
    rec = pycolmap.Reconstruction(a.sparse)
    ids = list(rec.points3D.keys()); P = np.array([rec.points3D[i].xyz for i in ids]); err = np.array([rec.points3D[i].error for i in ids]); tl = np.array([rec.points3D[i].track.length() for i in ids])
    gut = (tl >= 3) & (err < np.percentile(err, 90)); Pg = P[gut]
    ims = list(rec.images.values()); C = np.array([im.projection_center() for im in ims])
    print(f"SfM: {len(ims)} Kameras, {len(P)} Punkte ({gut.sum()} mit Spur >= 3)")
    # 1. Lot aus der Kameraebene
    cm = C.mean(0); _, sv, vt = np.linalg.svd(C - cm); up = vt[2]
    if np.median((Pg - cm) @ up) < 0: up = -up
    flach = sv[2] / sv[0]
    print(f"Lot aus Kameraebene: Streuung {sv.round(2).tolist()} (Dicke/Laenge {flach:.2f}; < 0,25 = Strassenfotos in einer Ebene)")
    # Basis: e3 = up, e1/e2 beliebig senkrecht
    e1 = np.cross(up, [1, 0, 0]); e1 = e1 if np.linalg.norm(e1) > 0.1 else np.cross(up, [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    B0 = np.vstack([e1, e2, up])                                                              # Zeilen: SfM -> lotrechtes Netzsystem
    Q = (Pg - cm) @ B0.T; Cq = (C - cm) @ B0.T
    # Ziel
    T, Tn, Tt, wand2d, grund2d, nb, Te = lod2_ziel(obj, a.radius)
    Wo = T[Te & (Tt == 0)]; Wn = Tn[Te & (Tt == 0)]                                             # Waende des Objekts selbst (Abdeckungsmass)
    print(f"Objekt-Waende (LoD2 {obj['lod2'].get('id')}): {len(Wo)} Abtastpunkte"); G, Gn, gq = dgm_ziel(obj, a.radius)
    print(f"Ziel: {nb} LoD2-Gebaeude im Umkreis {a.radius:.0f} m ({len(T)} Flaechenpunkte), Boden {gq} ({len(G)} Punkte)")
    # 2. Grobsuche 2D: Wandlinien-Raster (Naehe) gegen Punktdichte
    from scipy.ndimage import distance_transform_edt
    z = a.zelle; H = a.radius * 1.25; n = int(2 * H / z); W = np.zeros((n, n), bool)
    for Pw in wand2d:
        for i in range(len(Pw)):
            p0, p1 = Pw[i], Pw[(i + 1) % len(Pw)]; m = int(np.linalg.norm(p1 - p0) / (z / 2)) + 2
            s_ = np.linspace(0, 1, m)[:, None]; L = p0 + s_ * (p1 - p0); ij = ((L + H) / z).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1); W[ij[ok, 1], ij[ok, 0]] = True
    Dw = distance_transform_edt(~W) * z; Nahe = np.exp(-0.5 * (Dw / 0.5) ** 2)
    import cv2
    innb = np.zeros((n, n), np.uint8)
    for Pg_ in grund2d: cv2.fillPoly(innb, [np.round((Pg_ + H) / z - 0.5).astype(np.int32)], 1)
    inn = innb.astype(bool); Tief = (distance_transform_edt(inn) * z > 1.0).astype(float)    # mehr als 1 m im Gebaeude: dort kann kein Fassadenpunkt liegen
    FT = np.fft.rfft2(Tief); zc_q = np.median(Cq[:, 2])
    print(f"Grobsuche: Fassadenpunkte (1-7 m ueber Boden beim Probemassstab) muessen an LoD2-Waenden liegen (Naehe, Sigma 0,5 m) und nicht > 1 m im Gebaeude (Strafe x2)")
    ext = np.percentile(np.hypot(Q[:, 0], Q[:, 1]), 80); ziel_ext = 0.8 * a.radius * 0.5
    s0 = ext / ziel_ext                                                                       # grober Startmassstab (SfM-Einheiten je m), Suche ueber Faktor 6 in beide Richtungen
    best = []
    print(f"Startmassstab s0 = {s0:.4f} SfM-Einheiten/m (Wolkenausdehnung), Suche s0/4 .. 4 s0; Toleranz 0,75 m * s0/s (konstant in SfM-Einheiten)")
    for ls in np.linspace(math.log(s0 / 4), math.log(s0 * 4), 33):
        s = math.exp(ls); hq = (Q[:, 2] - zc_q) / s + 1.6; fs = (hq > 1.0) & (hq < 7.0)
        if fs.sum() < 50: continue
        sig_m = max(z, 0.75 * s0 / s)                                                          # Toleranz in SfM-EINHEITEN konstant (massstabsneutral; in Metern bevorzugt jede Toleranz das geschrumpfte Modell)
        FN = np.fft.rfft2(np.exp(-0.5 * (Dw / sig_m) ** 2))
        for th in np.radians(np.arange(0, 360, 3)):
            c, si = math.cos(th), math.sin(th); xy = (Q[fs, :2] @ np.array([[c, -si], [si, c]]).T) / s
            ij = ((xy + H) / z).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
            if ok.sum() < 0.3 * len(xy): continue
            D = np.zeros((n, n)); np.add.at(D, (ij[ok, 1], ij[ok, 0]), 1.0)
            FD = np.conj(np.fft.rfft2(D)); K = np.fft.irfft2((FN - 2.0 * FT) * FD, s=(n, n))   # K[dy,dx] = sum D(p) * (Nahe - 2 Tief)(p + d)
            m0 = np.median(xy, 0); sh = np.fft.fftfreq(n, 1.0 / n) * z                          # Verschiebung je Rasterindex (m)
            fern = np.hypot(m0[0] + sh[None, :], m0[1] + sh[:, None]) > a.mitte_max                 # Fotos sind um das Objekt ausgewaehlt: Wolkenmitte (Median) <= mitte_max vom Objekt
            K[fern] = -np.inf
            k = np.unravel_index(np.argmax(K), K.shape); dy, dx = [(v if v < n // 2 else v - n) * z for v in k]
            best.append((K[k] / len(Q), s, th, dx, dy))                                       # durch ALLE Punkte teilen: wenige Punkte im Band (zu kleines Modell) gewinnen nicht
    best.sort(key=lambda b: -b[0]); top = []
    for b in best:                                                                            # je Massstabsband die beste Loesung (die Grobsumme allein bevorzugt kleine Modelle)
        if not any(abs(math.log(b[1] / t[1])) < 0.15 for t in top): top.append(b)
        # KEINE Obergrenze (Martinstor 2026-11-04): mit 'top 12' fiel das richtige Band (s = 0,071, alte Pick-Kette) heraus, weil die Grobsumme kleine
        # Modelle bevorzugt -> Turm 0,66-fach. Jedes Massstabsband (Abstand 0,15 in log s, ~19 Baender) bekommt eine Feinloesung; entschieden wird dort.
    print("Grobsuche (Anteil nahe LoD2-Wand, Massstab, Drehung, Verschiebung): " + "; ".join(f"{b[0]:.2f} s={b[1]:.3f} {math.degrees(b[2]):.0f} Grad" for b in top[:4]))

    # 3. Fein: 7 Parameter, Punkt-zu-Flaeche, getrimmt; Startwerte aus den besten Grobloesungen
    Tall = np.vstack([T, G]); Nall = np.vstack([Tn, Gn]); baum = cKDTree(Tall)

    def zu_modell(p, X):                                                                      # X im lotrechten Netzsystem -> Modell
        s = math.exp(p[0]); return Rot.from_rotvec(p[1:4]).apply(X) / s + p[4:7]

    def fein(p0, X, schwellen=(3.0, 1.5, 0.8)):
        p = np.array(p0, float); ls0 = p[0]
        for sw in schwellen:
            for _ in range(3):
                M = zu_modell(p, X); d, j = baum.query(M, distance_upper_bound=sw * 2)
                ok = np.isfinite(d); jj = j[ok]; Xo = X[ok]
                if ok.sum() < 30: return p, 0.0, np.inf, ok
                wk = a.kamera_gewicht * math.sqrt(len(Xo) / len(Cq))
                def r(q):
                    rp = np.einsum("ij,ij->i", zu_modell(q, Xo) - Tall[jj], Nall[jj]) * math.exp(q[0])  # Residuum in SfM-Einheiten (massstabsneutral, kein Kollaps)
                    rk = (zu_modell(q, Cq)[:, 2] - a.kamerahoehe[0]) / a.kamerahoehe[1] * math.exp(ls0) * wk   # ANNAHME Strassenfotos: Kamerahoehe h0 +- sigma (robust: Turm-/Fensterfotos sind Ausreisser)
                    return np.r_[rp, rk]
                lo = np.full(7, -np.inf); hi = np.full(7, np.inf); lo[0], hi[0] = ls0 - 0.35, ls0 + 0.35   # Massstab begrenzt (+-40 % um den Start): sonst Kollaps aller Punkte auf eine Flaeche
                p = least_squares(r, np.clip(p, lo + 1e-9, hi - 1e-9), loss="huber", f_scale=sw / 3 * math.exp(ls0), max_nfev=200, bounds=(lo, hi)).x
        M = zu_modell(p, X); d, _ = baum.query(M); ok = d * math.exp(p[0]) < schwellen[-1] * s0      # Inlier-Schwelle in SfM-Einheiten (massstabsneutral)
        return p, ok.mean(), float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else np.inf, ok

    def abdeckung(p, X):
        """Anteil der zur Kamera gewandten Objektwand-Flaeche (unter der Traufe) mit einem Netzpunkt im Umkreis 0,6 m: ein geschrumpftes Netz deckt nur einen Fleck."""
        M = zu_modell(p, X); Cm_ = zu_modell(p, Cq); cz = Cm_.mean(0)
        sicht = ((cz - Wo) * Wn).sum(1) > 0
        if sicht.sum() < 20: return 0.0
        d, _ = cKDTree(M).query(Wo[sicht]); return float((d < 0.6).mean())

    loes = []
    for sc, s, th, dx, dy in top:
        p0 = [math.log(s), 0, 0, th, dx, dy, 0.0]
        zc = np.median(Cq[:, 2]) / s; p0[6] = 1.6 - zc                                         # Hoehenstart: Kameras ~1,6 m ueber Boden (nur Start, ANNAHME)
        p, frac, rms, ok = fein(p0, Q); ab = abdeckung(p, Q); loes.append((frac * ab, rms, p, ok, frac, ab))
        print(f"   Start {math.degrees(th):5.0f} Grad s={s:.3f}: Inlier {100 * frac:.0f} %, Objektwand-Abdeckung {100 * ab:.0f} %, RMS {rms:.2f} m, Massstab {math.exp(p[0]):.4f}")
    loes.sort(key=lambda l: -l[0]); guete, rms, p, ok, frac, ab = loes[0]
    # Bootstrap: Massstab-/Lage-Streuung aus Teilstichproben
    rng = np.random.default_rng(1); bs = []
    for _ in range(8):
        sub = rng.choice(len(Q), len(Q) // 2, replace=False); pb, *_ = fein(p, Q[sub], schwellen=(1.5, 0.8)); bs.append(pb)
    bs = np.array(bs); s_sig = 100 * np.std(np.exp(bs[:, 0])) / math.exp(p[0]); t_sig = np.std(bs[:, 4:7], 0)
    zweit = loes[1][0] if len(loes) > 1 else 0; frac = guete                                   # Guete = Inlier x Abdeckung
    # Gesamt: X_modell = Rz(X_sfm - cm) B0^T / s + t  ->  X_sfm = s * R @ X_modell + t
    s = math.exp(p[0]); Rl = Rot.from_rotvec(p[1:4]).as_matrix(); Rm = Rl @ B0                  # X_m = Rm (X_s - cm)/s + tm
    tm = p[4:7]; R_s = Rm.T; t_s = cm - s * R_s @ tm
    print(f"\nMassstab SfM-Einheiten/m = {s:.5f} +- {s_sig:.1f} %   Lage-Sigma {t_sig.round(2).tolist()} m   Guete (Inlier x Abdeckung) {100 * frac:.0f} % (zweitbeste {100 * zweit:.0f} %), RMS {rms:.2f} m")
    Pm = ((P - cm) @ Rm.T) / s + tm; Cm = ((C - cm) @ Rm.T) / s + tm
    hz = Cm[:, 2]; print(f"Kamerahoehen (robuste Bedingung, ANNAHME h0 {a.kamerahoehe[0]} +- {a.kamerahoehe[1]} m; Rest = Ausreisser): Median {np.median(hz):.2f} m, {np.sum((hz > -1) & (hz < 6))} von {len(hz)} zwischen -1 und 6 m (Strassenfotos ~1,5-2)")
    dg = baum.query(Pm[gut])[0]; print(f"Wolke im Modellsystem: z p1 {np.percentile(Pm[:, 2], 1):.1f} .. p99 {np.percentile(Pm[:, 2], 99):.1f} m; Abstand zu LoD2/DGM: Median {np.median(dg):.2f} m")
    if a.schreiben:
        sfx = ("-" + a.name) if a.name else ""; usfx = ("_" + a.name) if a.name else ""
        kam = {}
        for im, c in zip(ims, Cm):
            nr = os.path.splitext(im.name)[0]; cw = im.cam_from_world(); Rc = cw.rotation.matrix() @ R_s; tc = (cw.rotation.matrix() @ t_s + np.array(cw.translation)) / s
            cam = rec.cameras[im.camera_id]; pr = list(cam.params)
            kam[nr] = dict(standort=c.round(2).tolist(), f_px_original=float(pr[0]), fak=1.0, off=[0.0, 0.0], R=Rc.tolist(), t=tc.tolist(), cx=float(pr[2] if cam.model.name in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[1]), cy=float(pr[3] if cam.model.name in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[2]),
                           k=[float(v) for v in pr[3:]] if cam.model.name in ("SIMPLE_RADIAL", "RADIAL") else [], bild_b=cam.width, bild_h=cam.height, hinweis="f/cx/cy in SfM-Bildpixeln (fak nicht bestimmt)")
        out = dict(verfahren="sfm_lod2_ausrichten.py (ohne Picks: Kameraebene -> Lot, LoD2-Wandlinien -> Grob, Punkt-zu-Flaeche LoD2+DGM1 -> Fein)", sparse=a.sparse, fotos_sfm=sorted(kam), fotos_mit_picks=[],
                   transformation=dict(beschreibung="X_sfm = s * R @ X_modell + t ; Modellsystem = objekt.json rahmen (anker3d.json)", s=s, s_sigma_prozent=float(s_sig), rvec=Rot.from_matrix(R_s).as_rotvec().tolist(),
                                       t=t_s.tolist(), t_sigma_m=t_sig.tolist(), inlier_anteil=float(frac), rms_m=float(rms), zweitbeste_inlier=float(zweit)),
                   ziel=dict(lod2_gebaeude=nb, radius_m=a.radius, boden=gq), kameras=kam,
                   kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)),
                   wolke=dict(n=len(Pm), z_p1=float(np.percentile(Pm[:, 2], 1)), z_p999=float(np.percentile(Pm[:, 2], 99.9))), annahmen=dict(kamerahoehe=dict(h0=a.kamerahoehe[0], sigma=a.kamerahoehe[1], gewicht=a.kamera_gewicht, hinweis="ANNAHME Strassenfotos, robuste Bedingung (Huber)")))
        os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); pth = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG{sfx}.json"); json.dump(out, open(pth, "w"), indent=1, ensure_ascii=False); print("geschrieben:", pth)
        np.save(os.path.join(od, "sfm", f"punkte_modell{usfx}.npy"), Pm); np.save(os.path.join(od, "sfm", f"punkte_farben{usfx}.npy"), np.array([rec.points3D[i].color for i in ids], dtype=np.uint8))
        try:
            sim = pycolmap.Sim3d(1.0 / s, pycolmap.Rotation3d(Rm), tm - Rm @ cm / s); rec.transform(sim); ziel = os.path.join(od, "sfm", f"sparse_modell{usfx}"); os.makedirs(ziel, exist_ok=True); rec.write(ziel)
            print("geschrieben:", ziel, "(COLMAP-Modell im Modellsystem, Meter)")
        except Exception as e: print("sparse_modell nicht geschrieben:", type(e).__name__, e)


if __name__ == "__main__":
    main()
