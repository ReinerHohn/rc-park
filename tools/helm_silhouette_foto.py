#!/usr/bin/env python3
"""helm_silhouette_foto.py - Silhouettenabweichung eines Rotations-/Polygonhelms (Typ helm_geschweift) gegen Himmel in kalibrierten Fotos.

  helm_silhouette_foto.py modelle/<objekt>/objekt.json <bauteil-typ> FOTO1,FOTO2,... [--z0 16.5 --z1 21 --dz 0.5] [--profil_alt profil.json] [--protokoll M-sil-x]

Je Foto und Hoehe z: Ring des Polygons (aus objekt.json: u, n, n_seiten, profil, drehung_grad, achse_n) in das Foto projizieren (K-<foto>.json), Bildzeile durch den
Ringmittelpunkt, je Seite die Entfernung vom Modellrand bis zur Himmelskante messen. Himmel je Seite = ruhige helle/gleichfarbige Referenz 40-120 px AUSSERHALB des
Modellrands (Streuung < 8); Seiten ohne solchen Himmel zaehlen nicht. Ergebnis je Seite: Abweichung in Metern (negativ = Foto breiter als Modell = Modell zu schlank),
Pixelgroesse aus Tiefe/f. Schreibt messprotokoll/<name>.json (Messung am Foto, kein Modellbezug im Massstab: nur Pixel -> m ueber Kamera K-*). Generisch, GPU nicht noetig (Bildzeilen).
Grenze: Silhouette gegen Himmel misst Huelle inkl. Leisten/Kroeten (Grat-Zubehoer), nicht die Flaechenmitte."""
import sys, os, json, argparse, numpy as np, cv2

ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("typ"); ap.add_argument("fotos")
ap.add_argument("--z0", type=float, default=16.5); ap.add_argument("--z1", type=float, default=21.0); ap.add_argument("--dz", type=float, default=0.5)
ap.add_argument("--bilder", default="/media/oem/scan/rc-park_daten/kaufhaus_alle/bilder"); ap.add_argument("--protokoll", default=None); ap.add_argument("--profil_alt", default=None)
a = ap.parse_args()
od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt))
cfg = next(b for b in obj["bauteile"] if b["typ"] == a.typ)
pz = np.array(json.load(open(a.profil_alt)) if a.profil_alt else cfg["profil"], float)
N = int(cfg["n_seiten"]); U, Nn = float(cfg["u"]), float(cfg["n"]); an = np.array(cfg["achse_n"], float); ud = np.array([an[1], -an[0]]); dr = np.radians(float(cfg.get("drehung_grad", 0)))
cen = U * ud + Nn * an
def ring(z):
    r = np.interp(z, pz[:, 0], pz[:, 1]); R = r / np.cos(np.pi / N); ph = dr + np.pi / 2 + np.pi / N; t = ph + 2 * np.pi * np.arange(N) / N
    xy = cen + np.outer(R * np.cos(t), ud) + np.outer(R * np.sin(t), an); return np.c_[xy, np.full(N, z)]
erg = []
for f in a.fotos.split(","):
    d = json.load(open(os.path.join(od, "messprotokoll", f"K-{f}.json"))); k = d["kamera"]; Rm, _ = cv2.Rodrigues(np.array(k["rvec"])); t = np.array(k["t"])
    def pr(X):
        x = X @ Rm.T + t; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
        return np.stack([k["f_px"] * xn * (1 + k["k1"] * r2) + k["cx"], k["f_px"] * yn * (1 + k["k1"] * r2) + k["cy"]], 1), x[:, 2]
    im = cv2.imread(os.path.join(a.bilder, d["datei"])); g = cv2.GaussianBlur(im, (0, 0), 1.5).astype(float)
    for z in np.arange(a.z0, a.z1 + 1e-6, a.dz):
        Q, dep = pr(ring(z)); c, _ = pr(np.array([[cen[0], cen[1], z]])); row = int(round(c[0][1])); xl, xr = int(Q[:, 0].min()), int(Q[:, 0].max()); px = dep.mean() / k["f_px"]
        if row < 0 or row >= im.shape[0] or xl < 160 or xr > im.shape[1] - 160: continue
        res = {"foto": f, "z": round(float(z), 2), "px_m": round(float(px), 5), "modell_px": [xl, xr]}
        for seite, (s0, s1) in (("links", (xl - 120, xl - 40)), ("rechts", (xr + 40, xr + 120))):
            seg = g[row, s0:s1]; ref = np.median(seg, 0)
            if seg.std(0).max() > 8 or ref.min() < 150: continue                      # kein ruhiger heller Himmel
            sky = np.abs(g[row] - ref).max(1) < 22
            if seite == "links":
                i = xl + 20
                while i > 0 and not sky[i]: i -= 1
                edge = i + 1
            else:
                i = xr - 20
                while i < im.shape[1] - 1 and not sky[i]: i += 1
                edge = i - 1
            if not sky[i]: continue
            dev = (xl - edge) * px if seite == "links" else (edge - xr) * px           # >0: Foto breiter als Modell
            res[seite] = round(float(dev), 3)
        if "links" in res or "rechts" in res: erg.append(res)
if not erg: sys.exit("keine Zeile mit Himmel auf mindestens einer Seite")
zs = sorted({e["z"] for e in erg}); med = []
for z in zs:
    v = [e[s] for e in erg if e["z"] == z for s in ("links", "rechts") if s in e]
    med.append({"z": z, "n": len(v), "median_foto_breiter_m": round(float(np.median(v)), 3), "min": round(min(v), 3), "max": round(max(v), 3)})
    print(f"z {z:5.2f}  n {len(v):2d}  Foto breiter als Modell: Median {np.median(v):+.3f} m  [{min(v):+.3f} .. {max(v):+.3f}]")
if a.protokoll:
    out = {"id": a.protokoll, "werkzeug": "tools/helm_silhouette_foto.py", "bauteil": a.typ, "profil_modell": pz.tolist(), "fotos": a.fotos.split(","), "zeilen": erg, "je_hoehe": med,
           "vorzeichen": "positiv = Foto-Silhouette breiter als Modell (Modell zu schlank); Pixelgroesse aus Kameratiefe/f der K-Protokolle (SfM-Buendel, keine amtlichen Anker)",
           "grenze": "Silhouette gegen Himmel = Huelle inkl. Leisten/Kroeten; Flaechenmitte (Apothem) nicht direkt"}
    json.dump(out, open(os.path.join(od, "messprotokoll", a.protokoll + ".json"), "w"), indent=1, ensure_ascii=False); print("->", a.protokoll)
