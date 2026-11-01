#!/usr/bin/env python3
"""foto_bundle.py - MEHRERE Fotos gemeinsam gegen amtliche Anker loesen und dabei UNSICHERE HOEHEN mitschaetzen (Buendelausgleich).

Unbekannte: je Foto Kamera (Drehung 3, Lage 3, Brennweite 1 - oder EXIF-fest); je Anker mit "z_frei" dessen Hoehe (Startwert + weicher Prior).
Fest: Grundriss-Lagen aus LoD2 (x, y) und Bodenecken (z). Dadurch tragen LoD2-Breiten (11,2 m) und Bodenpunkte den Massstab; Spitze, Tuermchen,
Zinnenkranz, First (Goldkugeln) und Traufe werden aus den Fotos in Metern bestimmt - nicht aus dem Modell, nicht aus dem Laser.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_bundle.py modelle/<objekt>/objekt.json 030 041 000
Liest messprotokoll/K-<foto>.json (Picks), anker3d.json; schreibt messprotokoll/BUNDLE.json (Hoehen mit Sigma aus der Kovarianz, Kameras, Residuen).
"""
import sys, os, json, glob, math, numpy as np, cv2
from scipy.optimize import least_squares

def proj(X, rvec, t, f, cx, cy):
    R, _ = cv2.Rodrigues(rvec); Xc = X @ R.T + t; return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]

def main():
    objp = sys.argv[1]; fotos = sys.argv[2:]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    Ks = {nr: json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json"))) for nr in fotos}
    dims = {}
    for nr in fotos:
        H, W = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]).shape[:2]; dims[nr] = (W, H)
    # freie Hoehen: Anker mit z_frei -> Gruppe (gleicher Name = gemeinsame Hoehe), sonst fest
    gruppen = sorted({A[n]["z_frei"] for n in A if A[n].get("z_frei")}); zi = {g: i for i, g in enumerate(gruppen)}
    z0 = np.array([np.mean([A[n]["xyz"][2] for n in A if A[n].get("z_frei") == g]) for g in gruppen]); zs = np.array([max(A[n]["sigma"] for n in A if A[n].get("z_frei") == g) for g in gruppen])
    # Parametervektor: [je Foto 7 (rvec, t, f)] + [Hoehen]
    use_exif = {nr: Ks[nr].get("brennweite_px") for nr in fotos}
    grp = {nr: Ks[nr].get("f_gruppe") for nr in fotos}                       # gleiche Kamera/Brennweite in mehreren Fotos (z. B. eine Fotoserie)
    def unpack(p):
        cams = {}; k = 0; fg = {}
        for nr in fotos:
            f = use_exif[nr] or p[k + 6]
            if grp[nr]: f = fg.setdefault(grp[nr], f)
            cams[nr] = (p[k:k + 3], p[k + 3:k + 6], f); k += 7
        return cams, p[k:]
    def xyz_of(name, zf):
        x, y, z = A[name]["xyz"]; g = A[name].get("z_frei")
        return np.array([x, y, zf[zi[g]] if g else z])
    def resid(p):
        cams, zf = unpack(p); r = []
        for nr in fotos:
            rvec, t, f = cams[nr]; K = Ks[nr]; W, H = dims[nr]; cx, cy = W / 2, H / 2
            names = list(K["punkte"]); X = np.array([xyz_of(n, zf) for n in names]); uv, z = proj(X, rvec, t, f, cx, cy)
            sig_xy = np.array([A[n].get("sigma_xy", 0.0 if A[n].get("z_frei") else A[n]["sigma"]) for n in names])
            w = 1.0 / np.sqrt(9.0 + (sig_xy * f / np.maximum(z, 1)) ** 2)                      # Pickfehler 3 px + Lageunsicherheit des Ankers
            r += list(((uv - np.array([K["punkte"][n] for n in names])) * w[:, None]).ravel())
            for n, pts in K.get("linien", {}).items():
                xy = A[n]["xyz"][:2]; L3 = np.array([[xy[0], xy[1], 0.0], [xy[0], xy[1], 40.0]]); l2, _ = proj(L3, rvec, t, f, cx, cy)
                d = l2[1] - l2[0]; nv = np.array([-d[1], d[0]]) / np.linalg.norm(d); r += list(((np.array(pts) - l2[0]) @ nv) / 3.0)
            if K.get("strassenfoto"):
                R, _ = cv2.Rodrigues(rvec); camz = float((-R.T @ t)[2]); r.append((camz - 1.7) / 0.6)
            if z.min() < 1: r = [x * 1e3 for x in r]
        r += list((zf - z0) / zs)                                                                  # Prior der freien Hoehen
        return np.array(r)
    # Start: Einzelkameras aus K-*.json (foto_kalibrieren) oder Raster
    p0 = []
    for nr in fotos:
        k = Ks[nr].get("kamera")
        if k: p0 += list(k["rvec"]) + list(k["t"]) + [k["f_px"]]
        else:
            W, H = dims[nr]; az = {"Sued": 0.0, "Nord": math.pi, "Ost": math.pi / 2, "West": -math.pi / 2}.get(Ks[nr].get("seite"), 0.0)
            cam = np.array([40.0 * math.cos(az), 40.0 * math.sin(az), 1.7]); fw = np.array([0, 0, 25.0]) - cam      # Start auf der Fotoseite; fw /= np.linalg.norm(fw); rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt)
            R = np.vstack([rt, np.cross(fw, rt), fw]); rv, _ = cv2.Rodrigues(R); p0 += list(rv.ravel()) + list(-R @ cam) + [1.0 * H]
    p0 = np.array(p0 + list(z0))
    sol = least_squares(resid, p0, method="trf", x_scale="jac", max_nfev=20000)
    J = sol.jac; cov = np.linalg.pinv(J.T @ J) * (np.sum(sol.fun ** 2) / max(1, len(sol.fun) - len(p0)))
    cams, zf = unpack(sol.x); sig = np.sqrt(np.diag(cov))[-len(gruppen):]
    out = dict(fotos=fotos, hoehen={g: dict(z=round(float(zf[i]), 2), sigma=round(float(sig[i]), 2), start=round(float(z0[i]), 2), prior_sigma=float(zs[i])) for g, i in zi.items()}, kameras={}, rms_px={})
    print("Buendel ueber", fotos, "- freie Hoehen (m):")
    for g, i in zi.items(): print(f"  {g:14s} {zf[i]:6.2f} +- {sig[i]:.2f}   (Start {z0[i]:.1f}, Prior +-{zs[i]})")
    for nr in fotos:
        rvec, t, f = cams[nr]; W, H = dims[nr]; R, _ = cv2.Rodrigues(rvec); cam = -R.T @ t
        names = list(Ks[nr]["punkte"]); X = np.array([xyz_of(n, zf) for n in names]); uv, _ = proj(X, rvec, t, f, W / 2, H / 2)
        res = np.linalg.norm(uv - np.array([Ks[nr]["punkte"][n] for n in names]), axis=1)
        out["kameras"][nr] = dict(rvec=list(map(float, rvec)), t=list(map(float, t)), f_px=float(f), cx=W / 2, cy=H / 2, standort=cam.round(2).tolist(), hoehe=round(float(cam[2]), 2))
        out["rms_px"][nr] = round(float(np.sqrt(np.mean(res ** 2))), 1)
        print(f"  Foto {nr}: f={f:.0f} px, Standort {cam.round(1).tolist()}, RMS {out['rms_px'][nr]} px, Residuen", {n: int(r) for n, r in zip(names, res)})
        Ks[nr]["kamera_bundle"] = out["kameras"][nr]; json.dump(Ks[nr], open(os.path.join(od, "messprotokoll", f"K-{nr}.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(out, open(os.path.join(od, "messprotokoll", "BUNDLE.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
