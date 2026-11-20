#!/usr/bin/env python3
"""sfm_ausrichten.py - COLMAP-Netz (alle Fotos gemeinsam) an die AMTLICHEN BODENANKER ausrichten (7 Parameter: Massstab, Drehung, Lage).

Idee: Das SfM-Netz (pycolmap, modelle/<objekt>/sfm/sparse/0) ist in sich konsistent, hat aber weder Massstab noch Lot noch Nordung.
Die fehlenden 7 Freiheitsgrade kommen NICHT aus dem Modell und nicht aus einzeln kalibrierten Kameras (Register AE, Versuch 1 und 2),
sondern aus den Picks der LoD2-Eckkanten (messprotokoll/K-<foto>.json: "punkte" ecke_boden_* und "linien" ecke_boden_*), gesehen durch
die FESTEN SfM-Kameras. Gesucht ist die Aehnlichkeitstransformation Modell -> SfM, die diese Picks am besten reprojiziert.
  - Eckkanten-LINIEN liefern Lot (alle senkrecht), Drehung um das Lot und Massstab (LoD2-Eckabstand 11,4 / 11,1 m).
  - Eck-PUNKTE am Boden (z = Gelaende) liefern die Hoehenlage.
Danach werden alle Kameras und Punkte ins Modellsystem gebracht (sfm/sparse_modell) und die freien Picks (Spitze, Goldkugeln,
Tuermchen, Kranz, Traufe) aus >= 2 Fotos TRIANGULIERT: Hoehen in Metern mit Sigma, ohne Modellmass und ohne Laser.
Pruefungen (keine Zwangsbedingungen): Kamerahoehen der Strassenfotos (~1,7 m), DOM1-Gipfel 54,8 m, Grundrissbreite der Turmpunkte.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_ausrichten.py modelle/<objekt>/objekt.json [--sparse <pfad>] [--schreiben]
Schreibt messprotokoll/SFM-AUSRICHTUNG.json (Transformation, Residuen, Kameras, triangulierte Hoehen) und sfm/sparse_modell/.
Weitere Optionen: --name <seite> (-> SFM-AUSRICHTUNG-<name>.json, sfm/sparse_modell_<name>), --fotos ..., --kamerahoehe H0 SIGMA, --luftbilder ...,
  --wand nord|sued|ost|west [--wand-z 12 26]. Oder `tools/py tools/sfm_ausrichten.py ...` (pycolmap -> venv-colmap). Braucht gepickte LoD2-Eckkanten;
  ohne Picks (neues Objekt) tools/sfm_lod2_ausrichten.py. Exit 0 = ausgerichtet; < 4 Bodenanker oder kein Start konvergiert -> Abbruch mit Text.
"""
import sys, os, json, glob, math, argparse, numpy as np, cv2
from scipy.optimize import least_squares
import pycolmap

SIGMA_PICK_PX = 3.0          # Pickgenauigkeit im Originalbild
Z_KANTE_OBEN = 30.0          # Eckkante wird von Boden bis hierhin projiziert (Linienrichtung; Zinnenkranz liegt bei ~31,5)

def rot(rvec): return cv2.Rodrigues(np.asarray(rvec, float))[0]

class Kam:
    """COLMAP-Kamera (SIMPLE_RADIAL / PINHOLE / SIMPLE_PINHOLE / RADIAL) als numpy-Projektion.
    fak = SfM-Pixel je Original-Pixel, off = Ausschnitt-Ursprung im Original (objekt.json fotos[nr].sfm_ausschnitt)."""
    off = (0.0, 0.0)
    def bild(self, uv):
        """Original-Pixel (Picks) -> SfM-Bildpixel."""
        return (np.asarray(uv, float) - np.asarray(self.off, float)) * self.fak
    def __init__(self, im, cam, fak):
        self.name = im.name; cw = im.cam_from_world(); self.R = cw.rotation.matrix(); self.t = np.array(cw.translation)
        p = list(cam.params); m = cam.model.name
        if m in ("SIMPLE_RADIAL", "SIMPLE_PINHOLE", "RADIAL"): self.fx = self.fy = p[0]; self.cx, self.cy = p[1], p[2]; self.k = p[3:]
        elif m in ("PINHOLE", "OPENCV"): self.fx, self.fy, self.cx, self.cy = p[:4]; self.k = p[4:6]
        else: raise SystemExit(f"Kameramodell {m} nicht unterstuetzt")
        self.fak = fak; self.W, self.H = cam.width, cam.height
    def zentrum(self): return -self.R.T @ self.t
    def proj(self, X):
        Xc = X @ self.R.T + self.t; z = Xc[:, 2]; x = Xc[:, 0] / z; y = Xc[:, 1] / z; r2 = x * x + y * y
        d = 1.0 + sum(kk * r2 ** (i + 1) for i, kk in enumerate(self.k))
        return np.c_[self.fx * x * d + self.cx, self.fy * y * d + self.cy], z

def kam_aus_json(nr, d):
    """Kamera aus SFM-AUSRICHTUNG-<name>.json["kameras"][nr] (Modellsystem) als Kam-Objekt."""
    km = Kam.__new__(Kam); km.name = nr; km.R = np.array(d["R"]); km.t = np.array(d["t"]); km.fak = float(d.get("fak", 1.0)); km.off = tuple(d.get("off", (0.0, 0.0)))
    km.fx = km.fy = float(d["f_px_original"]) * km.fak; km.cx, km.cy = float(d["cx"]), float(d["cy"]); km.k = list(d.get("k", [])); return km

def lade(objp, sparse):
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    rec = pycolmap.Reconstruction(sparse); kams = {}
    for im in rec.images.values():
        nr = os.path.splitext(im.name)[0]; cam = rec.cameras[im.camera_id]
        orig = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")); fak = 1.0; off = (0.0, 0.0)
        aus = obj.get("fotos", {}).get(nr, {}).get("sfm_ausschnitt")
        if aus: fak = float(aus.get("zoom", 1.0)); off = (float(aus["xywh"][0]), float(aus["xywh"][1]))
        elif orig:
            H, W = cv2.imread(orig[0]).shape[:2]; fak = cam.width / W
        kams[nr] = Kam(im, cam, fak); kams[nr].off = off
    Ks = {}
    for pth in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(pth)[2:-5]
        if nr in kams: Ks[nr] = json.load(open(pth))
    return obj, root, od, A, rec, kams, Ks

def beobachtungen(A, kams, Ks):
    """Nur Anker mit FESTER Hoehe (Boden) - keine freien Hoehen, kein Modellmass."""
    B = []   # (nr, art, name, uv_sfm[n,2], X_modell[n,3], sigma_m[, sigma_px])
    for nr, K in Ks.items():
        k = kams[nr]
        for n, uv in K.get("punkte", {}).items():
            a = A.get(n)
            if a and not a.get("z_frei") and n.startswith("ecke_boden"):
                B.append((nr, "punkt", n, k.bild([uv]), np.array([a["xyz"]], float), a["sigma"], float(K.get("punkte_sigma_px", {}).get(n, SIGMA_PICK_PX))))
        for n, pts in K.get("linien", {}).items():
            a = A.get(n)
            if a and n.startswith("ecke_boden"):
                x, y, z0 = a["xyz"]; B.append((nr, "linie", n, k.bild(pts), np.array([[x, y, z0], [x, y, Z_KANTE_OBEN]]), a["sigma"]))
    return B

def resid(p, B, kams, roh=False, prior=None, wand=None):
    s = math.exp(p[0]); R = rot(p[1:4]); t = p[4:7]; r = []; info = []
    if wand:   # LoD2-Wandebene: Xs (SfM) -> Modell, Abstand der Schaftpunkte zur Ebene
        Xs, achse, wert, sig, band, quer = wand; Rm = R.T; Xm = ((Xs - t) @ Rm.T) / s
        ia = 0 if achse == "x" else 1
        r += list((Xm[:, ia] - wert) / sig)          # Punkte wurden VOR dem Loesen ausgewaehlt (feste Residuenzahl)
    if prior:   # ANNAHME Strassenfoto: Kamerahoehe ueber Gelaende h0 +- sh (wie foto_bundle.py); Luftbilder ausgenommen
        h0, sh, nrs = prior; Rm = R.T
        for nr in nrs:
            c = kams[nr].zentrum(); cm = (Rm @ (c - t)) / s; r.append((cm[2] - h0) / sh)
    for b in B:
        nr, art, n, uv, X, sig = b[:6]; spx = b[6] if len(b) > 6 else SIGMA_PICK_PX
        k = kams[nr]; Xs = (X @ R.T) * s + t; q, z = k.proj(Xs)
        if z.min() < 0.1: r += [1e3] * (len(uv) + 1 if art == "linie" else 2 * len(uv)); info.append((nr, art, n, 999.0)); continue
        sig_px = np.sqrt((spx * k.fak) ** 2 + (sig * s * k.fx / z.mean()) ** 2)      # Pick (je Pick einstellbar: K["punkte_sigma_px"]) + Ankerunsicherheit (m -> px)
        if art == "punkt":
            d = (uv[0] - q[0]); r += list(d / sig_px); info.append((nr, art, n, float(np.linalg.norm(d) / k.fak)))
        else:
            v = q[1] - q[0]; nv = np.array([-v[1], v[0]]) / np.linalg.norm(v); d = (uv - q[0]) @ nv
            r += list(d / sig_px); info.append((nr, art, n, float(np.sqrt(np.mean(d ** 2)) / k.fak)))
            # RICHTUNG der Kante: Picks sind von OBEN nach UNTEN gespeichert (erster Pick = hoechster). Die projizierte Richtung
            # Boden->Z_KANTE_OBEN muss im Bild nach oben zeigen, sonst ist die Loesung unter einer 180-Grad-Drehung um die
            # Querachse (Turm haengt nach unten, Kameras auf der Gegenseite) nicht von der richtigen zu unterscheiden.
            dimg = uv[-1] - uv[0]; cosw = (dimg @ (q[0] - q[1])) / (np.linalg.norm(dimg) * np.linalg.norm(v) + 1e-9); r.append((1.0 - cosw) / 0.1)
    return (np.array(r), info) if roh else np.array(r)

_MS_B = _MS_KAMS = _MS_PRIOR = None
def _ms_start(p0):
    """Ein Start des Mehrfachstarts (Arbeitsprozess): (cost, x, fehlertext)."""
    try:
        sol = least_squares(resid, p0, args=(_MS_B, _MS_KAMS, False, _MS_PRIOR), method="trf", x_scale="jac", max_nfev=3000, loss="soft_l1" if _MS_PRIOR else "linear")
        return (float(sol.cost), sol.x, "")
    except Exception as e:
        return (None, None, f"{type(e).__name__}: {e}")

def starts(rec, kams):
    """Mehrfachstart: Massstab grob aus Kamera-Wolken-Abstand (Strassenfotos ~30-60 m), Drehung auf einem Raster, Lage auf die Wolke."""
    P = np.array([q.xyz for q in rec.points3D.values()]); c = np.median(P, 0)
    Z = np.array([k.zentrum() for k in kams.values()]); d = np.median(np.linalg.norm(Z - c, axis=1))
    out = []
    for s in (d / 25.0, d / 45.0, d / 80.0):
        for ax in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0), (0, -1, 0), (0, 0, -1)]:
            for ang in (0, 90, 180, 270):
                # Modell-z soll auf Achse ax zeigen, danach Drehung um diese Achse um ang
                ax = np.array(ax, float); z = np.array([0, 0, 1.0]); v = np.cross(z, ax); sn = np.linalg.norm(v)
                R0 = np.eye(3) if sn < 1e-9 and ax @ z > 0 else (rot(np.array([1.0, 0, 0]) * math.pi) if sn < 1e-9 else rot(v / sn * math.atan2(sn, z @ ax)))
                R1 = rot(ax * math.radians(ang)) @ R0; rv = cv2.Rodrigues(R1)[0].ravel()
                out.append(np.r_[math.log(s), rv, c - (np.array([0, 0, 20.0]) @ R1.T) * s])   # Turmmitte in 20 m Hoehe ~ Wolkenmedian
    return out

def triangulieren(kams_m, beob):
    """beob: Liste (Kam im Modellsystem, uv_sfm) -> X (DLT + Nachiteration), Residuen px (Original), Sigma aus Jacobi."""
    def res(X):
        r = []
        for k, uv in beob:
            q, z = k.proj(X[None]); r += list((q[0] - uv) / (SIGMA_PICK_PX * k.fak))
        return np.array(r)
    # DLT-Start (ohne Verzeichnung)
    rows = []
    for k, uv in beob:
        Pm = np.c_[k.R, k.t]; u = (uv[0] - k.cx) / k.fx; v = (uv[1] - k.cy) / k.fy
        rows += [u * Pm[2] - Pm[0], v * Pm[2] - Pm[1]]
    X0 = np.linalg.svd(np.array(rows))[2][-1]; X0 = X0[:3] / X0[3]
    sol = least_squares(res, X0, method="lm")
    J = sol.jac; dof = max(1, len(sol.fun) - 3); cov = np.linalg.pinv(J.T @ J) * max(1.0, np.sum(sol.fun ** 2) / dof)
    px = [float(np.linalg.norm((k.proj(sol.x[None])[0][0] - uv) / k.fak)) for k, uv in beob]
    return sol.x, np.sqrt(np.diag(cov)), px

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sparse"); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--fotos", nargs="*", help="nur diese Fotos fuer die Ausrichtung benutzen (Picks); Standard: alle K-*.json im Netz")
    ap.add_argument("--kamerahoehe", nargs=2, type=float, metavar=("H0", "SIGMA"), help="ANNAHME Strassenfoto: Kamerahoehe H0 +- SIGMA m fuer alle Netzkameras ausser --luftbilder")
    ap.add_argument("--luftbilder", nargs="*", default=[], help="Fotos ohne Kamerahoehen-Annahme (Luftbild, Aussichtspunkt)")
    ap.add_argument("--name", default="", help="Kennung der Ausgabe (z. B. Seite): SFM-AUSRICHTUNG-<name>.json, sparse_modell_<name>, punkte_modell_<name>.npy")
    ap.add_argument("--wand", choices=["nord", "sued", "ost", "west"], help="LoD2-Wandebene dieser Seite als Tiefenanker: Netzpunkte am Schaft (|quer| < 2,5 m, z in --wand-z) muessen in der Ebene der LoD2-Ecken liegen (Linien allein lassen die Tiefe frei)")
    ap.add_argument("--wand-z", nargs=2, type=float, default=[12.0, 26.0]); ap.add_argument("--wand-sigma", type=float, default=0.3)
    a = ap.parse_args(); a.sparse = a.sparse or os.path.join(od_from(a.objekt), "sfm", "sparse", "0"); obj, root, od, A, rec, kams, Ks = lade(a.objekt, a.sparse)
    if a.fotos: Ks = {nr: K for nr, K in Ks.items() if nr in a.fotos}
    prior = (a.kamerahoehe[0], a.kamerahoehe[1], [nr for nr in kams if nr not in a.luftbilder]) if a.kamerahoehe else None
    if prior: print(f"ANNAHME Kamerahoehe {prior[0]} +- {prior[1]} m fuer {len(prior[2])} Kameras")
    B = beobachtungen(A, kams, Ks)
    print(f"SfM: {len(kams)} Kameras, {rec.num_points3D()} Punkte; Bodenanker-Beobachtungen: {len(B)} aus Fotos {sorted({b[0] for b in B})}")
    for b in B: print(f"   {b[0]} {b[1]:5s} {b[2]:13s} {len(b[3])} Pick(s)" + (f"  sigma {b[6]:.0f} px" if len(b) > 6 and b[6] != SIGMA_PICK_PX else ""))
    if len(B) < 4: raise SystemExit("zu wenige Bodenanker-Picks (Linien/Punkte ecke_boden_* in K-<foto>.json der SfM-Fotos)")
    # Mehrfachstart
    # Mehrfachstart auf allen Kernen (fork: Beobachtungen B, Kameras, Prior als Modulzustand, kein Pickling der Kameraobjekte).
    # Verlustfrei: dieselben Starts, dieselbe Zielfunktion; die beste Loesung wird am Ende einmal nachgerechnet (liefert dasselbe sol-Objekt).
    import multiprocessing as mp
    global _MS_B, _MS_KAMS, _MS_PRIOR
    _MS_B, _MS_KAMS, _MS_PRIOR = B, kams, prior
    liste = list(starts(rec, kams)); kerne = max(1, min(len(liste), os.cpu_count() or 1)); fehler = ""
    with mp.get_context("fork").Pool(kerne) as pool: erg = pool.map(_ms_start, liste)
    best = [(c, x) for c, x, f in erg if c is not None]; fehler = next((f for c, x, f in erg if f), "")
    if not best: raise SystemExit("kein Start konvergiert: " + fehler)
    best.sort(key=lambda x: x[0]); print(f"   Mehrfachstart: {len(liste)} Starts auf {kerne} Kernen, {len(best)} konvergiert")
    sol = least_squares(resid, best[0][1], args=(B, kams, False, prior), method="trf", x_scale="jac", max_nfev=3000, loss="soft_l1" if prior else "linear"); p = sol.x
    wand = None
    if a.wand:
        # Ebene aus den LoD2-Bodenecken der Seite: nord = kleinstes x der Ecken, sued = groesstes, ost = groesstes y, west = kleinstes y
        E = np.array([A[n]["xyz"][:2] for n in A if n.startswith("ecke_boden")]); achse = "x" if a.wand in ("nord", "sued") else "y"; ia = 0 if achse == "x" else 1
        wert = float(E[:, ia].min() if a.wand in ("nord", "west") else E[:, ia].max()); sgn = -1.0 if a.wand in ("nord", "west") else 1.0
        Xs_all = np.array([q.xyz for q in rec.points3D.values()]); s0 = math.exp(p[0]); Rm0 = rot(p[1:4]).T; Xm0 = ((Xs_all - p[4:7]) @ Rm0.T) / s0
        iq = 1 - ia; k = (np.abs(Xm0[:, iq]) < 2.5) & (Xm0[:, 2] >= a.wand_z[0]) & (Xm0[:, 2] <= a.wand_z[1]) & (sgn * Xm0[:, ia] > 2.0)
        front = np.percentile(sgn * Xm0[k, ia], 90) if k.sum() else 0; k &= (sgn * Xm0[:, ia] > front - 1.0)          # nur die vordere Wandschicht (keine Fenster-/Innenpunkte)
        print(f"Wandebene {a.wand}: {achse} = {wert:.2f} m (LoD2-Ecken); {k.sum()} Schaftpunkte z {a.wand_z[0]}-{a.wand_z[1]}, vorher mittlerer Abstand {np.mean(Xm0[k, ia]) - wert:+.2f} m")
        wand = (Xs_all[k], achse, wert, a.wand_sigma, tuple(a.wand_z), 2.5)
        sol = least_squares(resid, p, args=(B, kams, False, prior, wand), method="trf", x_scale="jac", max_nfev=3000, loss="soft_l1"); p = sol.x
        Xm1 = ((Xs_all[k] - p[4:7]) @ rot(p[1:4]).T.T) / math.exp(p[0]); print(f"   nach Wandanker: mittlerer Abstand {np.mean(Xm1[:, ia]) - wert:+.2f} m, Streuung {np.std(Xm1[:, ia]):.2f}")
    s = math.exp(p[0]); R = rot(p[1:4]); t = p[4:7]
    J = sol.jac; dof = max(1, len(sol.fun) - 7); cov = np.linalg.pinv(J.T @ J) * max(1.0, np.sum(sol.fun ** 2) / dof); sig = np.sqrt(np.diag(cov))
    r, info = resid(p, B, kams, roh=True, prior=None, wand=None)
    out_annahme = dict(kamerahoehe=dict(h0=prior[0], sigma=prior[1], kameras=prior[2])) if prior else {}
    print(f"\nBeste von {len(best)} Startloesungen: Kosten {sol.cost:.2f}; naechstbeste {[round(c, 2) for c, _ in best[1:4]]}")
    print(f"Massstab SfM-Einheiten/m = {s:.5f} +- {100 * sig[0]:.1f} %   Drehung-Sigma {np.degrees(sig[1:4]).round(2)} deg   Lage-Sigma {(sig[4:7] / s).round(2)} m")
    print("Residuen (px im Originalbild):", ", ".join(f"{nr}/{n}:{v:.0f}" for nr, art, n, v in info))
    # Modell <- SfM
    Rm = R.T; sm = 1.0 / s; tm = -Rm @ t * sm
    def nach_modell(Xs): return (Xs @ Rm.T) * sm + tm
    kams_m = {}
    for nr, k in kams.items():
        km = Kam.__new__(Kam); km.__dict__.update(k.__dict__)
        # x_c = R_s (s R X + t) + t_s = s * (R_s R X + (R_s t + t_s) / s): gleiche Bildpunkte, Tiefe in Metern
        km.R = k.R @ R; km.t = (k.R @ t + k.t) / s
        kams_m[nr] = km
    # Pruefung 1: Kamerahoehen
    print("\nKameras im Modellsystem (Standort x,y,z m | Abstand zur Achse):")
    hz = []
    for nr in sorted(kams_m):
        c = kams_m[nr].zentrum(); hz.append(c[2]); mark = "" if -1.0 < c[2] < 6.0 else "  <-- nicht auf Strassenniveau?"
        print(f"   {nr}: {c.round(1).tolist()} | {np.hypot(c[0], c[1]):5.1f} m | f={kams_m[nr].fx / kams_m[nr].fak:.0f} px{mark}")
    hz = np.array(hz); print(f"   Kamerahoehen: Median {np.median(hz):.1f} m, {np.sum((hz > -1) & (hz < 6))} von {len(hz)} zwischen -1 und 6 m (Strassenfotos erwartet ~1,7)")
    # Pruefung 2: Wolke im Modellsystem - Turmkern, Hoehen, Grundriss je Band
    P = nach_modell(np.array([q.xyz for q in rec.points3D.values()]))
    rxy = np.hypot(P[:, 0], P[:, 1]); kern = P[rxy < 9.0]
    print(f"\nWolke: {len(P)} Punkte, z {np.percentile(P[:, 2], 1):.1f}..{np.percentile(P[:, 2], 99.9):.1f} m; im 9-m-Zylinder um die Achse {len(kern)} Punkte, hoechster {kern[:, 2].max():.1f} m (DOM1-Gipfel 54,8; Nadel sieht SfM kaum)")
    for z0 in range(-2, 62, 6):
        k = (kern[:, 2] >= z0) & (kern[:, 2] < z0 + 6)
        if k.sum() > 15:
            q = kern[k]; print(f"   z {z0:3d}..{z0 + 6:3d} m: {k.sum():4d} Pkt, x {np.percentile(q[:, 0], 2):6.1f}..{np.percentile(q[:, 0], 98):5.1f}  y {np.percentile(q[:, 1], 2):6.1f}..{np.percentile(q[:, 1], 98):5.1f}  (LoD2 Sockel x +-4,9, y +-5,6)")
    # Triangulation der freien Picks
    print("\nTriangulierte Picks (Modellsystem, Meter) - Quelle: SfM-Kameras + Picks, kein Modellmass:")
    tri = {}
    sammel = {}
    for nr, K in Ks.items():
        for n, uv in K.get("punkte", {}).items():
            if n.startswith("ecke_boden"): continue
            sammel.setdefault(n, []).append((kams_m[nr], kams[nr].bild(uv), nr))
    for n, lst in sorted(sammel.items()):
        if len(lst) < 2: print(f"   {n:16s} nur in {lst[0][2]} gepickt - keine Triangulation"); continue
        X, sx, px = triangulieren(kams_m, [(k, uv) for k, uv, _ in lst])
        start = A.get(n, {}).get("xyz", [None] * 3)
        tri[n] = dict(xyz=X.round(2).tolist(), sigma=sx.round(2).tolist(), fotos=[f for _, _, f in lst], residuen_px=[round(v, 1) for v in px], anker_start=start)
        print(f"   {n:16s} x {X[0]:6.2f} y {X[1]:6.2f} z {X[2]:6.2f} +- {sx[2]:.2f} m  (Fotos {[f for _, _, f in lst]}, Residuen {[round(v) for v in px]} px; Anker-Start z {start[2]})")
    out = dict(sparse=a.sparse, fotos_sfm=sorted(kams), fotos_mit_picks=sorted(Ks), transformation=dict(
        beschreibung="X_sfm = s * R @ X_modell + t ; Modellsystem siehe anker3d.json (Ursprung Turmmitte, +x Sued, +y Ost, z ueber Gelaende)",
        s=s, s_sigma_prozent=float(100 * sig[0]), rvec=p[1:4].tolist(), rvec_sigma_deg=np.degrees(sig[1:4]).tolist(), t=t.tolist(), t_sigma_m=(sig[4:7] / s).tolist(),
        kosten=float(sol.cost), naechste_kosten=[float(c) for c, _ in best[1:4]]),
        beobachtungen=[dict(foto=nr, art=art, name=n, residuum_px=round(v, 1)) for nr, art, n, v in info],
        kameras={nr: dict(standort=kams_m[nr].zentrum().round(2).tolist(), f_px_original=float(kams_m[nr].fx / kams_m[nr].fak), fak=kams_m[nr].fak, off=list(map(float, kams_m[nr].off)),
                          R=kams_m[nr].R.tolist(), t=kams_m[nr].t.tolist(), cx=kams_m[nr].cx, cy=kams_m[nr].cy, k=list(map(float, kams_m[nr].k))) for nr in kams_m},
        kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)),
        wolke=dict(n=len(P), z_p1=float(np.percentile(P[:, 2], 1)), z_p999=float(np.percentile(P[:, 2], 99.9)), kern_n=len(kern), kern_zmax=float(kern[:, 2].max())),
        trianguliert=tri, annahmen=out_annahme, wandanker=(dict(seite=a.wand, z=a.wand_z, sigma=a.wand_sigma) if a.wand else None))
    if a.schreiben:
        sfx = ("-" + a.name) if a.name else ""; usfx = ("_" + a.name) if a.name else ""
        pth = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG{sfx}.json"); json.dump(out, open(pth, "w"), indent=1, ensure_ascii=False); print("\ngeschrieben:", pth)
        np.save(os.path.join(od, "sfm", f"punkte_modell{usfx}.npy"), P)
        np.save(os.path.join(od, "sfm", f"punkte_farben{usfx}.npy"), np.array([q.color for q in rec.points3D.values()], dtype=np.uint8))   # Fotofarben (gleiche Reihenfolge)
        try:
            sim = pycolmap.Sim3d(sm, pycolmap.Rotation3d(Rm), tm); rec.transform(sim); ziel = os.path.join(od, "sfm", f"sparse_modell{usfx}"); os.makedirs(ziel, exist_ok=True); rec.write(ziel)
            print("geschrieben:", ziel, "(COLMAP-Modell im Modellsystem, Meter)")
        except Exception as e: print("sparse_modell nicht geschrieben:", type(e).__name__, e)

def od_from(objp):
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp)))); return os.path.join(root, os.path.dirname(obj["masstabelle"]))

if __name__ == "__main__":
    main()
