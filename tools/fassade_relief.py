#!/usr/bin/env python3
"""fassade_relief.py - Fassadenrelief (Vorspruenge/Ruecksprunge) je LoD2-Fassade aus der DICHTEN SfM-Wolke, vollautomatisch (Qualitaetsstufe 3, 2026-11-05).

Warum: Fotos sehen keine Tiefe, der Erkenner (fassade_parsing) kennt nur Klassen. Die dichte Wolke (sfm/dicht_*_modell.npy, Modellrahmen) zeigt
Erker, Galerie, Figuren, Konsolen, Arkadentiefe direkt als Abstand zur Wandebene - ohne Bauteilklasse (Kaufhaus-Nordfront: Erker +0,9, Galerie +0,7,
Arkaden -4 m sichtbar). Quellen-Blindheit: SfM-Wolke sieht Fassaden (Laser DOM1 nicht); Massstab kommt aus den Buendelkameras (LoD2-Anker).

Verfahren je Fassade (Rahmen aus fassade_ortho fassaden.json: o, d, n, Wandstuecke):
  Raster `--zelle` m in (u, z); je Zelle das `--perzentil` des Abstands s zur Wandebene (+ = vor der Wand) der Punkte im Streifen s in [-tief, +vor]
  (vorderste Flaeche robust); >= `--min-punkte`; Loecher <= 3 Zellen per Median gefuellt; Stufen zu `--stufe` m (|s| < stufe/2 = Wand);
  Ruecksprunge nur unterhalb der Wandoberkante (sonst ist es das Dach); Regionen per Oeffnen entrauscht, Mindestflaeche `--min-flaeche` m2.
  Ausgabe je Stufe L (kumulativ: Region s >= L bzw. s <= -L) als Polygone (u, z) mit Loechern -> Generator-Bauteil relief_wolke.

  /media/oem/scan/venv-seg/bin/python -I tools/fassade_relief.py modelle/kaufhaus_null4/objekt.json --fassaden <ortho>/fassaden.json --aus <dir>
"""
import os, sys, json, glob, argparse, time
import numpy as np, cv2


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fassaden", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--wolke", help="Standard: sfm/dicht_*_modell.npy des Objekts (die groesste)"); ap.add_argument("--zelle", type=float, default=0.1)
    ap.add_argument("--perzentil", type=float, default=90); ap.add_argument("--min-punkte", type=int, default=3); ap.add_argument("--stufe", type=float, default=0.15)
    ap.add_argument("--vor", type=float, default=1.5); ap.add_argument("--tief", type=float, default=5.0); ap.add_argument("--min-flaeche", type=float, default=0.3)
    ap.add_argument("--oeffnen", type=int, default=3, help="Kernel (Zellen) fuer morphologisches Oeffnen je Stufe")
    ap.add_argument("--block-schwelle", type=float, default=0.2); ap.add_argument("--block-min-flaeche", type=float, default=1.5); ap.add_argument("--block-perzentil", type=float, default=90); ap.add_argument("--block-rand", type=float, default=0.05, help="Hysterese: Aussenkante bis zu dieser Tiefe (m)")
    a = ap.parse_args(argv); t0 = time.time(); od = os.path.dirname(os.path.abspath(a.objekt)); os.makedirs(a.aus, exist_ok=True)
    wp = a.wolke or max(glob.glob(os.path.join(od, "sfm", "dicht_*_modell.npy")), key=os.path.getsize); P = np.load(wp).astype(np.float64)
    FA = json.load(open(a.fassaden))["fassaden"]; z_ = a.zelle; erg = dict(wolke=os.path.abspath(wp), punkte=len(P), parameter=vars(a), fassaden={},
                                                                        quelle="fassade_relief.py: dichte SfM-Wolke (Buendel, LoD2-Anker) gegen LoD2-Wandebene")
    for F in FA:
        o, d, n = np.array(F["o"]), np.array(F["d"]), np.array(F["n"]); u = (P[:, :2] - o) @ d; s = (P[:, :2] - o) @ n; z = P[:, 2]
        u0, u1 = F["u"][0] - 0.5, F["u"][1] + 0.5; zo = F["z"][1] + 3.0
        ok = (u > u0) & (u < u1) & (s > -a.tief) & (s < a.vor) & (z > F["z"][0]) & (z < zo)
        if ok.sum() < 2000: continue
        nu, nz = int(np.ceil((u1 - u0) / z_)), int(np.ceil((zo - F["z"][0]) / z_))
        iu = ((u[ok] - u0) / z_).astype(int); iz = ((zo - z[ok]) / z_).astype(int); key = iz * nu + iu; sv = s[ok]
        o_ = np.lexsort((sv, key)); k = key[o_]; sv = sv[o_]; st = np.r_[0, np.where(np.diff(k))[0] + 1]; en = np.r_[st[1:], len(k)]; cnt = en - st
        R = np.full(nz * nu, np.nan); g = cnt >= a.min_punkte; R[k[st[g]]] = sv[st[g] + ((cnt[g] - 1) * a.perzentil / 100).astype(int)]; R = R.reshape(nz, nu)
        fin = np.isfinite(R); Rm = cv2.medianBlur(np.nan_to_num(R, nan=0).astype(np.float32), 5); R = np.where(fin, R, np.where(cv2.dilate(fin.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0, Rm, np.nan))
        # Wandoberkante je u (Wandstuecke): Ruecksprunge nur darunter
        top = np.full(nu, -1e9)
        for Q in F["polys_uz"]:
            Q = np.array(Q); a0, a1 = Q[:, 0].min(), Q[:, 0].max(); c0, c1 = int((a0 - u0) / z_), int(np.ceil((a1 - u0) / z_)); top[max(0, c0):c1] = np.maximum(top[max(0, c0):c1], Q[:, 1].max())
        zc = zo - (np.arange(nz) + 0.5) * z_; unter = zc[:, None] < (top[None, :] - 0.3)
        q = np.round(np.nan_to_num(R, nan=0.0) / a.stufe) * a.stufe; q[~np.isfinite(R)] = 0.0
        stufen = []; ker = np.ones((a.oeffnen, a.oeffnen), np.uint8); min_z = int(a.min_flaeche / z_ ** 2)
        for vz in (1, -1):
            L = a.stufe
            while L <= (a.vor if vz > 0 else a.tief) + 1e-6:
                m = ((q >= L - 1e-6) if vz > 0 else ((q <= -L + 1e-6) & unter)).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, ker)
                if m.sum() < min_z: L += a.stufe; continue
                cs, hi = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE); polys = []
                for i, c in enumerate(cs):
                    if cv2.contourArea(c) < min_z and hi[0][i][3] < 0: continue
                    c = cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2)
                    if len(c) < 3: continue
                    polys.append(dict(loch=bool(hi[0][i][3] >= 0), uz=[[round(u0 + (x + 0.5) * z_, 3), round(zo - (y + 0.5) * z_, 3)] for x, y in c]))
                if polys: stufen.append(dict(s0=round(vz * (L - a.stufe), 3), s1=round(vz * L, 3), polys=polys, zellen=int(m.sum())))
                L += a.stufe
        # Bloecke (2026-11-05): zusammenhaengende Vorspruenge (Erker, Galerie, Konsolen) als Quader statt Stufenrelief. Region = s >= block_schwelle
        # nach Oeffnen, Mindestflaeche; Tiefe = `--block-perzentil` der Zellen (Stufen verwaschen Erker auf 0,3-0,45 m), Kanten = Huelle der Region.
        bl = []; mb = cv2.morphologyEx((np.nan_to_num(R, nan=-9) >= a.block_schwelle).astype(np.uint8), cv2.MORPH_OPEN, ker)
        nlab, lab, sts, _ = cv2.connectedComponentsWithStats(mb, 8)
        for li in range(1, nlab):
            x, y, w_, h_, ar = sts[li]
            if ar * z_ ** 2 < a.block_min_flaeche: continue
            werte = R[lab == li]; werte = werte[np.isfinite(werte)]
            # Aussenkante per Hysterese (2026-11-05: polygonale Erker - Schraegfacetten springen weniger vor, Kern >= Schwelle = nur Frontfacette, Erker
            # 2,1 statt 3,3 m breit): Spaltenprofil (Median ueber die Kernzeilen) vom Kern nach aussen, solange >= block_rand und nicht wieder steigend (Tal = Nachbarbauteil)
            pr = np.nanmedian(np.where(np.isfinite(R[y:y + h_]), R[y:y + h_], np.nan), axis=0); xa, xb = x, x + w_ - 1
            while xa - 1 >= 0 and np.isfinite(pr[xa - 1]) and pr[xa - 1] >= a.block_rand and pr[xa - 1] <= pr[xa] + 0.03: xa -= 1
            while xb + 1 < len(pr) and np.isfinite(pr[xb + 1]) and pr[xb + 1] >= a.block_rand and pr[xb + 1] <= pr[xb] + 0.03: xb += 1
            bl.append(dict(u=[round(u0 + x * z_, 2), round(u0 + (x + w_) * z_, 2)], u_aussen=[round(u0 + xa * z_, 2), round(u0 + (xb + 1) * z_, 2)], z=[round(zo - (y + h_) * z_, 2), round(zo - y * z_, 2)], flaeche_m2=round(float(ar * z_ ** 2), 2),
                           fuellgrad=round(float(ar / (w_ * h_)), 2), tiefe_m=round(float(np.percentile(werte, a.block_perzentil)), 3), tiefe_median_m=round(float(np.median(werte)), 3)))
            # Profilform (2026-11-05, Erker Kaufhaus: Koerper 5,0-8,6 m bei 0,53 m, Gesims 8,9 m bei 0,85 m, darueber linear fallender Helm):
            # Plateau = Median der Kernzellen; Front = Spalten >= 0,8 Plateau; Koerper = Zeilen (ueber die Frontspalten) >= 0,5 Plateau, zusammenhaengend um die Mitte;
            # Gesims = Zeile mit groesster Tiefe in der oberen Haelfte, wenn > 1,15 Plateau; Helmneigung = lineare Anpassung der Zeilen oberhalb bis Tiefe 0.
            B = bl[-1]; pl = float(np.median(werte)); fr = np.where(np.nan_to_num(pr[x:x + w_], nan=-9) >= 0.8 * pl)[0]
            if len(fr):
                fa_, fb_ = x + fr[0], x + fr[-1] + 1; B["u_front"] = [round(u0 + fa_ * z_, 2), round(u0 + fb_ * z_, 2)]
                rp = np.nanmedian(np.where(np.isfinite(R[:, fa_:fb_]), R[:, fa_:fb_], np.nan), axis=1); rp = np.nan_to_num(rp, nan=-9); ym = y + h_ // 2
                ya, yb = ym, ym
                while ya - 1 >= 0 and rp[ya - 1] >= 0.5 * pl: ya -= 1
                while yb + 1 < len(rp) and rp[yb + 1] >= 0.5 * pl: yb += 1
                ob = slice(ya, ym); yg = ya + int(np.argmax(rp[ob])) if ym > ya else ya
                B.update(plateau_m=round(pl, 3), koerper_z=[round(zo - (yb + 1) * z_, 2), round(zo - ya * z_, 2)])
                if rp[yg] > 1.15 * pl:
                    B.update(gesims_z=round(zo - (yg + 0.5) * z_, 2), gesims_tiefe_m=round(float(rp[yg]), 3))
                    hy = [(zo - (yy + 0.5) * z_, rp[yy]) for yy in range(yg - 1, -1, -1) if rp[yy] > -1][:int(3.0 / z_)]
                    hz = [(zz, dd) for zz, dd in hy if dd > 0.05]
                    if len(hz) >= 4:
                        k_, c_ = np.polyfit([p[0] for p in hz], [p[1] for p in hz], 1)
                        if k_ < 0: B.update(helm_neigung=round(float(-k_), 3), helm_tiefe0_z=round(float(-c_ / k_), 2))
        img = np.clip((np.nan_to_num(R, nan=-a.tief) + 2) / 4 * 255, 0, 255).astype(np.uint8); img = cv2.applyColorMap(img, cv2.COLORMAP_JET); img[~np.isfinite(R)] = 0
        cv2.imwrite(os.path.join(a.aus, f"relief_{F['id']}.jpg"), cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
        np.save(os.path.join(a.aus, f"relief_{F['id']}.npy"), R.astype(np.float32))
        erg["fassaden"][F["id"]] = dict(n=F["n"], d=F["d"], o=F["o"], u0=u0, zo=zo, zelle=z_, punkte=int(ok.sum()), abdeckung=round(float(np.isfinite(R).mean()), 3), stufen=stufen, bloecke=bl)
        print(f"  {F['id']}: {ok.sum()} Punkte, Abdeckung {np.isfinite(R).mean():.0%}, {len(stufen)} Stufen ({sum(1 for x in stufen if x['s1'] > 0)} vor / {sum(1 for x in stufen if x['s1'] < 0)} zurueck)", flush=True)
    erg["sekunden"] = round(time.time() - t0, 1); json.dump(erg, open(os.path.join(a.aus, "relief.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
