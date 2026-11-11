#!/usr/bin/env python3
"""teil_render_foto.py - schattiertes Teil-Render aus der kalibrierten Fotokamera NEBEN dem Fotoausschnitt (Pruefbild fuer Agenten/Pruefer).
Warum (11.11., modelle/SPEC_ORNAMENT_FEINMASS.md): die Foto-Metrik (teil_fotoform, 0,18-m-Glaettung) ist blind fuer Rippen/Sprossen/Masswerk/Schuppen; im schattierten
Render sieht man sie sofort. Foto wird wie in foto_diff um k1 entzerrt (Renderer = Lochkamera); Teilpixel hinter dem GANZEN Modell (Verdeckung) werden schraffiert
statt gezeigt; GPU-Raster render_kern.

Aufruf: python -I tools/teil_render_foto.py <objekt> <teil> --fotos a,b --teile_dir D --stl S [--vergleich NAME:D2:S2 ...] [--name basis] [--aus DIR] [--kontur]
Ausgabe: <aus>/<teil>_<foto>.jpg (Foto | Variante 1 | Variante 2 ...), Standard <aus> = modelle/<objekt>/audit/teil_render_foto
"""
import sys, os, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK, foto_diff as FD
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _np(d): return np.asarray(d.cpu() if hasattr(d, "cpu") else d, np.float32)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("teil"); ap.add_argument("--fotos", required=True)
    ap.add_argument("--teile_dir", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--name", default="Teil")
    ap.add_argument("--vergleich", action="append", default=[], help="NAME:TEILE_DIR:STL (mehrfach)"); ap.add_argument("--aus"); ap.add_argument("--pad", type=int, default=30)
    ap.add_argument("--maxbreite", type=int, default=2400); ap.add_argument("--kontur", action="store_true", help="zusaetzlich Fotokanten (Canny, voll aufgeloest) orange ueber das Render")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); aus = a.aus or os.path.join(R0, "modelle", a.objekt, "audit", "teil_render_foto"); os.makedirs(aus, exist_ok=True)
    var = [(a.name, a.teile_dir, a.stl)] + [tuple(v.split(":")) for v in a.vergleich]; ausg = []
    for nr in a.fotos.split(","):
        kp = FF.k_datei(objp, obj, R0, nr)
        if not kp: print("keine Kamera", nr); continue
        K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))[0]
        im, K = FD.foto_skalieren(cv2.imread(bild), K); kk = K["kamera"]; H, W = im.shape[:2]
        im, _ = FF.foto_entzerren(im, kk)
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        spalten = []; box = None
        for name, td, stl in var:
            m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
            c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
            tr = np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)
            ganz = m.copy(); ganz.apply_translation(tr); dv = _np(RK.dreiecke_rastern(ganz, R, t, f, cx, cy, W, H, nur_tiefe=True)[0])
            p = trimesh.load(os.path.join(td, a.teil + ".stl"), force="mesh"); p.apply_scale(obj.get("stl_massstab", 87) / 1000.0); p.apply_translation(tr)
            d = _np(RK.dreiecke_rastern(p, R, t, f, cx, cy, W, H, nur_tiefe=True)[0]); fin = np.isfinite(d)
            if box is None:
                ys, xs = np.nonzero(fin); box = (max(ys.min() - a.pad, 0), min(ys.max() + a.pad, H), max(xs.min() - a.pad, 0), min(xs.max() + a.pad, W))
            y0, y1, x0, x1 = box; sicht = fin & (d <= dv * 1.003 + 0.03); dd = np.where(fin, d, np.nan)[y0:y1, x0:x1]
            gy, gx = np.gradient(np.nan_to_num(dd, nan=np.nanmax(dd))); n = np.dstack([-gx, -gy, np.full_like(gx, 0.004)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
            s = np.clip(n @ np.array([-0.4, -0.5, 0.77]), 0, 1); g = (40 + 215 * s).astype(np.uint8); g[~np.isfinite(dd)] = 255
            g = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
            vh = (fin & ~sicht)[y0:y1, x0:x1]   # vom Gesamtmodell verdeckt: rot getoent
            g[vh] = (0.5 * g[vh] + 0.5 * np.array((80, 80, 255))).astype(np.uint8)
            if a.kontur:
                gr = cv2.GaussianBlur(cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY), (0, 0), 1.0); mag = np.hypot(cv2.Sobel(gr, cv2.CV_32F, 1, 0), cv2.Sobel(gr, cv2.CV_32F, 0, 1))
                hi = max(float(np.percentile(mag, 80)), 8.0); g[cv2.Canny(gr, 0.5 * hi, hi, L2gradient=True) > 0] = (255, 160, 0)
            cv2.putText(g, name, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2); spalten.append(g)
        y0, y1, x0, x1 = box; foto = im[y0:y1, x0:x1].copy(); cv2.putText(foto, "Foto " + nr, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        out = np.hstack([foto] + spalten); sk = min(1.0, a.maxbreite / out.shape[1]); out = cv2.resize(out, None, fx=sk, fy=sk, interpolation=cv2.INTER_AREA)
        pf = os.path.join(aus, f"{a.teil}_{nr}.jpg"); cv2.imwrite(pf, out, [cv2.IMWRITE_JPEG_QUALITY, 90]); print(pf, out.shape, flush=True); ausg.append(pf)
    return ausg


if __name__ == "__main__":
    main()
