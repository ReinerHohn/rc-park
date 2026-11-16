#!/usr/bin/env python3
"""steine_aus_foto.py <relief.npz> <aus.npz> <fassaden.json> <nr> <ortho_fein.png> --feld u0 u1 z0 z1 [--px 0.02] [--fuge 0.03] [--massstab k x y z]

Quader mit ECHTEN Fugen aus dem feinen Fassadenbild (Nutzer 16.11.2026: "die Steine sind nach oben noch nicht korrekt").
Weiter oben am Turm ist das Scan-Relief nur noch Brei (Fotos von unten, flacher Winkel) - im 1-cm-Fassadenbild (tools/fassade_fein.py) steht aber jede Fuge
scharf. KERNMETHODE: Form aus Fotokanten. Ablauf:
  1. Feld (Wandkoordinaten des Reliefs) im 1-cm-Raster aus dem Fassadenbild lesen (Lage ueber fassaden.json: o, d, raster).
  2. FUGEN = schmale Linien, die von ihrer Umgebung abweichen: Helligkeit minus oertlicher Median (15 cm). Polaritaet (helle Moertelfuge / dunkle
     Schattenfuge) wird NICHT vorgegeben: beide Masken, es gewinnt die mit mehr langen duennen Linien. Keine Farbregel (gruenes/gelbes Haus geht genauso).
  3. Steine = Flaechen zwischen den Fugen, nur wo das Relief Stein ist (Maske 'putz' von relief_putz.py = Putz; Kontur damit aus der Fotofarbe wie bisher).
  4. Hoehe: Steinflaeche = geglaettetes Scan-Relief (echtes Niveau, 30 cm Glaettung), Fuge --fuge tiefer, Kante ueber 3 cm gefast.
     Putz = Putzniveau. Stellen ohne Fotodaten (verdeckt) = Scan-Relief.
aus.npz hat das Format der Relief-Einsaetze (px 2 cm, Maske 'fein' = alles) und wird wie ein Feineinsatz vor das grobe Relief gesetzt
(Generator: relief_koerper(aus, rand_auslauf=False), grobes Relief dort tief_felder). aus.jpg ANSEHEN. Fugentiefe und Bosse sind ANNAHME, die Fugenlage ist echt.
"""
import sys, os, json, argparse, numpy as np, cv2
from scipy import ndimage as ndi


def linien(m, min_len):
    lab, n = ndi.label(m, np.ones((3, 3)))
    if not n: return m & False, 0.0
    sl = ndi.find_objects(lab); gut = np.zeros(n + 1, bool); summe = 0.0
    fl = ndi.sum(m, lab, np.arange(1, n + 1))
    for i, s in enumerate(sl, 1):
        L = max(s[0].stop - s[0].start, s[1].stop - s[1].start)
        if L >= min_len and fl[i - 1] <= 6.0 * L * 4: gut[i] = True; summe += L          # lang und duenn (mittlere Breite <= ~24 Zellen ueber verzweigte Netze)
    return gut[lab], summe


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("aus"); ap.add_argument("fassaden"); ap.add_argument("nr"); ap.add_argument("ortho")
    ap.add_argument("--feld", nargs=4, type=float, required=True); ap.add_argument("--px", type=float, default=0.02); ap.add_argument("--fuge", type=float, default=0.03); ap.add_argument("--massstab", nargs=4, type=float)
    ap.add_argument("--ohne", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1 ohne Steine (Vordach, Wandbild: Generator baut dort selbst)"); ap.add_argument("--bosse", type=float, default=0.04, help="Buckel der Steinflaeche (m), 0 = eben"); ap.add_argument("--putz_s", type=float, default=0.22); ap.add_argument("--foto", help="statt des Orthos: Bild direkt aus diesem kalibrierten Foto auf der Reliefebene lesen (fassaden/nr/ortho dann als - - 0 - angeben)"); ap.add_argument("--objekt"); ap.add_argument("--stl", help="Modell-STL(s) fuer die Verdeckungspruefung"); ap.add_argument("--rand", type=float, default=0.3); ap.add_argument("--nah", type=float, default=0.25, help="Stein nur so nah (m) an der groben Steinmaske; 0 = aus (Wand ohne Wandbilder: sonst gehen Steinbaender verloren, die die grobe Maske nicht kennt)"); ap.add_argument("--duenn", type=float, default=0.12, help="Steinflaechen duenner als dies (m) verwerfen; 0 = aus"); ap.add_argument("--putz_v", type=float, default=0.45)
    ap.add_argument("--schwelle", type=float, default=2.4, help="Fuge ab so vielen Standardabweichungen der Abweichung vom oertlichen Median"); a = ap.parse_args()
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float32); H, W = rel.shape; rp = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); A = Z["a"]; t = Z["t"]; niv = float(Z.get("putz_niveau_m", 0.0))
    if not a.foto: F = json.load(open(a.fassaden))["fassaden"][int(a.nr)]; R = F["raster"]; o = np.array(F["o"]); d = np.array(F["d"]); im = cv2.imread(a.ortho)
    f0, f1, g0, g1 = a.feld; c = 0.01; nu = int(round((f1 - f0) / c)); nz = int(round((g1 - g0) / c)); jj, ii = np.meshgrid(np.arange(nu), np.arange(nz)); U = f0 + (jj + 0.5) * c; ZZ = g1 - (ii + 0.5) * c
    if a.foto:
        # 16.11.2026: DIREKT aus dem Foto auf der WANDEBENE DES RELIEFS lesen (nicht ueber ein Ortho auf der LoD2-Fassadenebene): die LoD2-Ebene liegt bis 0,75 m neben der Wand,
        # bei schraegem Blick verschiebt das den Bildinhalt seitlich um Dezimeter (West Schwabentor: Nordwestecke erschien 1 m zu frueh, dahinter "Steine" aus Himmel).
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import glob, fassade_ein_foto as FE
        nv_ = Z["n"]; tu_, tz_ = [float(v) for v in Z["trend_je_m"]]; dpl = float(Z["ebene_abstand_m"]) + tu_ * (U - u0) - tz_ * ((z0 + H * rp) - ZZ)
        X = A[0] + U * t[0] + dpl * nv_[0]; Y = A[1] + U * t[1] + dpl * nv_[1]; Zw = ZZ
        if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
        od_ = os.path.dirname(os.path.abspath(a.objekt)); root_ = os.path.dirname(os.path.dirname(od_)); obj_ = json.load(open(a.objekt)); Kc = FE.kamera(os.path.join(od_, "messprotokoll", "K-" + a.foto + ".json")); mm_ = None; rk_ = None
        if a.stl:
            import trimesh, render_kern as rk_
            ms_ = [trimesh.load(q_) for q_ in a.stl.split(",")]; mm_ = trimesh.util.concatenate(ms_) if len(ms_) > 1 else ms_[0]; mm_.apply_scale(float(obj_.get("stl_massstab", 87)) / 1000.0)
        P_ = np.stack([X, Y, Zw], -1).reshape(-1, 3); ok_, mx_, my_, zc_ = FE.sichtbar(mm_, Kc, P_, rk_, tol=0.6)
        if a.stl and a.rand > 0: ok_ = cv2.erode(ok_.reshape(U.shape).astype(np.uint8), np.ones((2 * int(a.rand / c) + 1,) * 2, np.uint8)).astype(bool).ravel()
        im = cv2.imread(glob.glob(os.path.join(root_, obj_["fotos_dir"], a.foto + ".*"))[0]); bild = cv2.remap(im, mx_.astype(np.float32).reshape(U.shape), my_.astype(np.float32).reshape(U.shape), cv2.INTER_LINEAR, borderValue=(0, 0, 0)); bild[~ok_.reshape(U.shape)] = 0
        print(f"Foto {a.foto[-40:]}: {np.median(zc_[ok_]) / Kc['f_px'] * 100:.1f} cm/px an der Wand, {ok_.mean() * 100:.0f} % des Feldes sichtbar")
    else:
        X = A[0] + U * t[0]; Y = A[1] + U * t[1]; Zw = ZZ
        if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
        uo = (X - o[0]) * d[0] + (Y - o[1]) * d[1]; bild = cv2.remap(im, ((uo - R["u0"]) / R["zelle"] - 0.5).astype(np.float32), ((R["z1"] - Zw) / R["zelle"] - 0.5).astype(np.float32), cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    daten = bild.max(2) > 8; grau = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY).astype(np.float32)
    def gross(x, interp=cv2.INTER_LINEAR): return cv2.remap(x, ((U - u0) / rp - 0.5).astype(np.float32), (H - (ZZ - z0) / rp - 0.5).astype(np.float32), interp, borderMode=cv2.BORDER_REPLICATE)
    putz = gross(Z["putz"].astype(np.float32)) > 0.5; grob = gross(rel)
    hsv = cv2.cvtColor(cv2.GaussianBlur(bild, (0, 0), 2.0), cv2.COLOR_BGR2HSV).astype(np.float32); pf = (hsv[..., 1] / 255 < a.putz_s) & (hsv[..., 2] / 255 > a.putz_v)   # Kontur Putz/Stein im 1-cm-Bild neu (gleiche Regel wie relief_putz.py, dort nur 5 cm): Verzahnung scharf statt ausgefranst
    if (putz & daten).sum() > 500: pf &= hsv[..., 2] > 0.82 * float(np.median(hsv[..., 2][putz & daten]))      # Putz ist so hell wie der sichere Putz daneben - graue (wenig gesaettigte) Steine sind dunkler
    pf = ndi.binary_closing(ndi.binary_opening(pf, np.ones((7, 7))), np.ones((7, 7))); nah = ndi.binary_dilation(~putz, np.ones((2 * int(a.nah / c) + 1,) * 2)) if a.nah > 0 else np.ones(putz.shape, bool)          # Stein nur in der Naehe (25 cm) der groben Steinmaske: Wandbilder/Fenster im Putz bleiben Putz
    putz = np.where(daten, pf | ~nah, putz)
    if a.duenn > 0: st_ = ndi.binary_opening(~putz & daten, np.ones((int(a.duenn / c) | 1,) * 2)); putz = np.where(daten, ~st_, putz)      # duenne 'Stein'-Linien (Ortgangkante, Draht, Rand einer Verdeckung) sind keine Quader
    for wert, min_zellen in ((True, 3000), (False, 1000)):               # Inseln weg: helle Steine mitten im Quaderfeld sind kein Putz (< 0,3 m2), Farbflecken im Putz kein Stein (< 0,1 m2)
        lab_, n_ = ndi.label(putz == wert)
        if n_: gr_ = ndi.sum(np.ones(putz.shape), lab_, np.arange(1, n_ + 1)); putz[np.isin(lab_, 1 + np.flatnonzero(gr_ < min_zellen))] = not wert
    for q0, q1, r0, r1 in a.ohne: putz |= (U >= q0) & (U <= q1) & (ZZ >= r0) & (ZZ <= r1)
    stein = ~putz & daten
    if stein.sum() < 2000: print("kaum Stein mit Fotodaten im Feld"); return 2
    from scipy.signal import find_peaks
    g = cv2.GaussianBlur(grau, (0, 0), 1.0); ab = g - cv2.medianBlur(np.clip(g, 0, 255).astype(np.uint8), 21).astype(np.float32); best = None
    komp, nk = ndi.label(ndi.binary_opening(stein, np.ones((9, 9))))
    for name, vz in (("hell", 1.0), ("dunkel", -1.0)):                    # Polaritaet nicht vorgegeben: beide rechnen, die mit den deutlicheren Lagerfugen gewinnt
        r = vz * ab; fuge = np.zeros(stein.shape, bool); guete = 0.0; summe = 0.0
        for ki in range(1, nk + 1):                                       # je zusammenhaengendem Steinfeld (Eckstreifen): Schichten = Zeilenprofil, Stossfugen = Spaltenprofil je Schicht
            m = komp == ki
            if m.sum() < 3000: continue
            ys, xs = np.nonzero(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; mm = m[y0:y1, x0:x1]; rr = np.where(mm, r[y0:y1, x0:x1], 0.0)
            nrow = mm.sum(1); p = ndi.gaussian_filter1d(rr.sum(1) / np.maximum(nrow, 1), 1.0); p[nrow < 15] = 0
            lager, pr = find_peaks(p, distance=16, prominence=a.schwelle * 0.5 * float(p.std())); guete += float(pr["prominences"].sum()) if len(lager) else 0.0
            grenzen = [0] + list(lager) + [y1 - y0]
            for l_ in lager: fuge[y0 + l_ - 1:y0 + l_ + 2, x0:x1] |= mm[l_ - 1:l_ + 2] if l_ >= 1 else False; summe += mm[l_].sum()
            for b0, b1 in zip(grenzen[:-1], grenzen[1:]):
                if b1 - b0 < 8: continue
                band = mm[b0 + 2:b1 - 2]; ncol = band.sum(0); q = ndi.gaussian_filter1d(rr[b0 + 2:b1 - 2].sum(0) / np.maximum(ncol, 1), 1.0); q[ncol < 0.6 * max(b1 - b0 - 4, 1)] = 0
                stoss, _ = find_peaks(q, distance=20, prominence=a.schwelle * 0.6 * float(q.std()) + 1e-6)
                for s_ in stoss: fuge[y0 + b0:y0 + b1, x0 + max(s_ - 1, 0):x0 + s_ + 2] |= mm[b0:b1, max(s_ - 1, 0):s_ + 2]; summe += b1 - b0
        fuge |= stein & ~ndi.binary_erosion(stein, np.ones((3, 3)), border_value=1) & False
        print(f"Fugen {name}: {summe / 100:.0f} m, Deutlichkeit der Lagerfugen {guete:.1f}")
        if best is None or guete > best[3]: best = (name, fuge, summe, guete)
    name, fuge, summe = best[:3]
    lab, n = ndi.label(stein & ~fuge); fl = ndi.sum(stein, lab, np.arange(1, n + 1)); klein = np.isin(lab, 1 + np.flatnonzero(fl < 60)); fuge |= klein & stein          # Kruemel < 60 cm2 zur Fuge
    fl = fl[fl >= 60]; dt = ndi.distance_transform_edt(~fuge) * c
    niveau = cv2.GaussianBlur(np.where(stein, grob, 0).astype(np.float32), (0, 0), 30) / np.maximum(cv2.GaussianBlur(stein.astype(np.float32), (0, 0), 30), 1e-3)
    niveau = np.maximum(niveau, niv + 0.02); h = niveau - a.fuge * (1.0 - np.clip(dt / 0.03, 0, 1))
    if a.bosse > 0:                                                       # Buckelquader: Kissen je Stein + rauhe Bruchflaeche. ERFUNDEN (Form der einzelnen Bosse ist nicht gemessen), nur Fugenlage und Kontur sind echt
        rng = np.random.default_rng(1); lab2, n2 = ndi.label(stein & ~fuge); je = np.r_[0.0, rng.uniform(0.6, 1.2, n2)][lab2]
        rauh = ndi.gaussian_filter(rng.standard_normal(stein.shape), 3.0); rauh = rauh / (rauh.std() + 1e-9) * 0.008 + ndi.gaussian_filter(rng.standard_normal(stein.shape), 9.0) * 0.12
        h = h + (a.bosse * je * np.sqrt(np.clip(dt / 0.10, 0, 1)) + rauh * np.clip(dt / 0.04, 0, 1)).astype(np.float32)
    aus = np.where(stein, h, np.where(putz, niv if abs(niv) > 1e-6 else 1e-4, grob)).astype(np.float32)
    kq = int(round(a.px / c)); aus2 = cv2.resize(aus, (nu // kq, nz // kq), interpolation=cv2.INTER_AREA)
    Zo = {k_: Z[k_] for k_ in ("a", "t", "n", "ebene_abstand_m") if k_ in Z}; tu, tz = [float(v) for v in Z["trend_je_m"]]
    Zo["ebene_abstand_m"] = float(Z["ebene_abstand_m"]) + tu * (f0 - u0) + tz * (g1 - (z0 + H * rp))      # Ebene des Trends am neuen Ursprung (links oben)
    Zo.update(rel=aus2, u0=f0, z0=g0, px=a.px, trend_je_m=Z["trend_je_m"], putz_niveau_m=niv, fein=np.ones(aus2.shape, bool), fugen_polaritaet=name, fugen_m=summe / 100, steine=len(fl), stein_median_m2=float(np.median(fl)) * c * c if len(fl) else 0.0)
    np.savez_compressed(a.aus, **Zo)
    lx = np.gradient(aus, c, axis=1); lz = np.gradient(aus, c, axis=0); sh = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8)
    cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", np.hstack([bild, cv2.cvtColor(sh, cv2.COLOR_GRAY2BGR)]))
    print(f"{os.path.basename(a.aus)}: Fugen {name}, {summe / 100:.0f} m, {len(fl)} Steine, Median {Zo['stein_median_m2']:.3f} m2, Stein mit Fotodaten {stein.sum() * c * c:.1f} m2, ohne Daten {(~daten & ~putz).sum() * c * c:.1f} m2")


if __name__ == "__main__":
    sys.exit(main())
