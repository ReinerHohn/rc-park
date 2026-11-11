#!/usr/bin/env python3
"""relief_aus_foto.py - Relief auf einer Traegerflaeche aus EINEM Foto per monokularer Tiefe (Depth Anything V2 SMALL, Apache-2.0).
Beweistest Option B (11.11.): Hoehenfeld relativ (Hochpass, begrenzt auf --hmax m), auf die Traegerflaeche (Teil-STL) gelegt und als Netz (STL) ausgegeben,
Gegenprobe in einem ZWEITEN kalibrierten Foto. GPU (torch + render_kern).

Ablauf: Traeger in die Fotokamera rastern (Weltpunkt+Normale je Pixel = 'Entzerrung auf die Traegerflaeche' per Strahl, auch fuer Kegel/Trichter) ->
Fotoausschnitt -> DA-V2 (relative Disparitaet) -> affine Anpassung an die bekannte Traegertiefe (Robust, Trimmen) -> Residuum = Relief ->
Hochpass (--sigma_m) -> Kappung +-hmax -> Verschiebung entlang Traegernormale -> Gitter-STL (mm-Rahmen wie die Teil-STL).
Modi: --foto F (echtes Foto) | --synth STL (Bild = schattiertes Render dieses Netzes; Wahrheit = Tiefenunterschied Netz gegen Traeger).
Aufruf: python -I tools/relief_aus_foto.py <objekt> <teil> --traeger T.stl (--foto F | --synth S.stl) [--maske_zmax m] [--gegen F2[,F3]] [--aus DIR]
Lizenz: modelle/LIZENZ_WERKZEUGE.md (11.11.). Gewichte: HF_HOME=/media/oem/scan/hf_depth.
"""
import sys, os, json, glob, argparse
os.environ.setdefault("HF_HOME", "/media/oem/scan/hf_depth")
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK, foto_diff as FD
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELL = "depth-anything/Depth-Anything-V2-Small-hf"


def kamera(objp, obj, nr):
    kp = FF.k_datei(objp, obj, R0, nr)
    if not kp: raise SystemExit("keine Kamera " + nr)
    K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))[0]
    im, K = FD.foto_skalieren(cv2.imread(bild), K); kk = K["kamera"]; H, W = im.shape[:2]; im, _ = FF.foto_entzerren(im, kk)
    R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
    return dict(im=im, R=R, t=np.asarray(t, float).ravel(), f=float(f), cx=cx, cy=cy, W=W, H=H, kk=kk)


def netz_laden(pfad, obj, tr=None):
    m = trimesh.load(pfad, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    if tr is not None: m.apply_translation(tr)
    return m


def verschiebung(kk):
    return np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [0, 0, 0], float)   # zentrierung 'achse' (kaufhaus_grob3)


def raster(m, C):
    d, fid, pos = RK.dreiecke_rastern(m, C["R"], C["t"], C["f"], C["cx"], C["cy"], C["W"], C["H"])
    d = np.asarray(d, np.float32); fid = np.asarray(fid.cpu() if hasattr(fid, "cpu") else fid); pos = np.asarray(pos.cpu() if hasattr(pos, "cpu") else pos, np.float64)
    return d, fid, pos


def schattiert(m, C, richtung=(-0.4, -0.5, 0.77)):
    """Graues Lambert-Bild aus Flaechennormalen (Kameraraum) + Tiefenbild; weisser Hintergrund."""
    d, fid, _ = raster(m, C); ok = np.isfinite(d) & (fid >= 0)
    N = np.asarray(m.face_normals)[np.clip(fid, 0, None)] @ C["R"].T
    N[N[..., 2] > 0] *= -1                                    # zur Kamera drehen (Kamera blickt +z)
    s = np.clip(-N[..., 2] * 0.5 + (N @ np.array([richtung[0], richtung[1], -0.2])) * 0.8 + 0.35, 0.05, 1)
    g = np.where(ok, 40 + 200 * s, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR), d, ok


_DA = {}
def tiefe_da(bgr, lang=1190):
    """Relative Disparitaet (gross = nah) fuer ein BGR-Bild, auf Bildgroesse zurueckgerechnet."""
    import torch
    from transformers import AutoModelForDepthEstimation, AutoImageProcessor
    if "m" not in _DA:
        _DA["m"] = AutoModelForDepthEstimation.from_pretrained(MODELL).cuda().eval(); _DA["p"] = AutoImageProcessor.from_pretrained(MODELL)
    h, w = bgr.shape[:2]; s = lang / max(h, w); h2, w2 = int(round(h * s / 14)) * 14, int(round(w * s / 14)) * 14
    x = cv2.cvtColor(cv2.resize(bgr, (w2, h2), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
    pv = _DA["p"](images=x, return_tensors="pt", do_resize=False)["pixel_values"].cuda()
    with torch.no_grad(): out = _DA["m"](pixel_values=pv).predicted_depth[0].float().cpu().numpy()
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC)


def relief_schaetzen(bgr, d_tr, ok, C, sigma_m, hmax, lang=1190):
    """Relief (m, zur Kamera positiv) je Pixel in 'ok'. Rueckgabe (h, disp, fit)."""
    disp = tiefe_da(bgr, lang); inv = np.where(ok, 1.0 / np.where(np.isfinite(d_tr), d_tr, 1), 0)
    x, y = inv[ok], disp[ok]; w = np.ones_like(x, bool)
    for _ in range(6):                                           # getrimmte Kleinste Quadrate: Rippen/Fugen sind Ausreisser der glatten Traegertiefe
        A = np.stack([x[w], np.ones(w.sum())], 1); a, b = np.linalg.lstsq(A, y[w], rcond=None)[0]; r = y - (a * x + b); s = 1.4826 * np.median(np.abs(r[w] - np.median(r[w]))) + 1e-9; w = np.abs(r) < 2.0 * s
    res = np.where(ok, disp - (a * inv + b), 0)
    z = np.where(ok, d_tr, 1.0); h = res * z ** 2 / max(a, 1e-9)           # d(1/z) = -dz/z^2 -> dz = -res z^2/a ; zur Kamera positiv = res z^2/a
    # Hochpass: Mittel ueber sigma_m (Pixel = sigma_m * f / z) normiert auf Maske
    zm = float(np.median(z[ok])); sg = max(2.0, sigma_m * C["f"] / zm); mk = ok.astype(np.float32)
    lo = cv2.GaussianBlur((h * mk).astype(np.float32), (0, 0), sg) / np.maximum(cv2.GaussianBlur(mk, (0, 0), sg), 1e-3)
    hh = np.clip(np.where(ok, h - lo, 0), -hmax, hmax)
    return hh, disp, dict(a=float(a), b=float(b), sigma_px=float(sg), z_med=zm)


def gitter_stl(pos, nrm, h, ok, C, obj, tr, schritt, pfad, d_tr):
    """Verschobenes Traegernetz (Pixelgitter, jedes schritt-te Pixel) -> STL im mm-Rahmen der Teil-STL."""
    H, W = ok.shape; ys, xs = np.mgrid[0:H:schritt, 0:W:schritt]; idx = -np.ones(ys.shape, int); m_ = ok[ys, xs]; idx[m_] = np.arange(m_.sum())
    P = pos[ys, xs][m_]; Nn = nrm[ys, xs][m_]; hh = h[ys, xs][m_]; v = P - (C["R"].T @ -C["t"])[None]; v /= np.linalg.norm(v, axis=1, keepdims=True)   # Strahl Kamera->Punkt
    cosw = np.clip(-(Nn * v).sum(1), 0.3, 1); V = P + Nn * (hh / cosw)[:, None]
    dz = d_tr[ys, xs]; F = []
    for dy, dx in ((0, 0),):
        a = idx[:-1, :-1]; b = idx[:-1, 1:]; c = idx[1:, :-1]; d = idx[1:, 1:]; zz = dz
        glatt = (np.abs(zz[:-1, :-1] - zz[1:, 1:]) < 0.15) & (np.abs(zz[:-1, 1:] - zz[1:, :-1]) < 0.15); g = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0) & glatt
        F += [np.stack([a[g], c[g], b[g]], 1), np.stack([b[g], c[g], d[g]], 1)]
    mm = trimesh.Trimesh(V, np.concatenate(F), process=False); out = mm.copy(); out.apply_translation(-tr); out.apply_scale(1000.0 / obj.get("stl_massstab", 87)); out.export(pfad)
    return mm, int(len(mm.faces))


def aus_hoehe_render(mm, C, bild_roh=None):
    return schattiert(mm, C)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("teil"); ap.add_argument("--traeger", required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument("--foto"); g.add_argument("--synth", help="STL mit Relief (Wahrheit); Bild = Render davon aus --kamera")
    ap.add_argument("--kamera", help="Foto-Nr. der Kamera fuer --synth"); ap.add_argument("--gegen", default="", help="Fotos fuer die Gegenprobe (Komma)")
    ap.add_argument("--maske_zmax", type=float, help="nur Traegerpixel mit Welt-z < Wert (m)"); ap.add_argument("--maske_zmin", type=float)
    ap.add_argument("--sigma_m", type=float, default=0.25); ap.add_argument("--hmax", type=float, default=0.08); ap.add_argument("--schritt", type=int, default=3)
    ap.add_argument("--cos_min", type=float, default=0.35); ap.add_argument("--pad", type=int, default=20); ap.add_argument("--lang", type=int, default=1190); ap.add_argument("--aus"); ap.add_argument("--blur", type=float, default=0.0, help="synth: Gauss-Unschaerfe (px) auf das Bild")
    ap.add_argument("--traeger_synth", action="store_true", help="synth: Wahrheit = 0 (Bild vom Traeger selbst, Test auf erfundene Woelbungen)")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); aus = a.aus or os.path.join(R0, "modelle", a.objekt, "audit", "relief_aus_foto"); os.makedirs(aus, exist_ok=True)
    nr = a.foto or a.kamera; C = kamera(objp, obj, nr); tr = verschiebung(C["kk"]); trg = netz_laden(a.traeger, obj, tr)
    d_tr, fid, pos = raster(trg, C); ok = np.isfinite(d_tr) & (fid >= 0)
    if a.maske_zmax is not None: ok &= pos[..., 2] < a.maske_zmax
    if a.maske_zmin is not None: ok &= pos[..., 2] > a.maske_zmin
    if a.cos_min > 0:                                           # streifende Pixel (Normale fast senkrecht zum Strahl) tragen kein Relief: Treppenartefakte
        Pc = pos - (C["R"].T @ -C["t"])[None, None]; Pc /= np.linalg.norm(Pc, axis=2, keepdims=True); nn = np.asarray(trg.face_normals)[np.clip(fid, 0, None)]
        ok &= np.abs((nn * Pc).sum(2)) > a.cos_min
    ok = cv2.erode(ok.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    ys, xs = np.nonzero(ok); y0, y1, x0, x1 = max(ys.min() - a.pad, 0), min(ys.max() + a.pad, C["H"]), max(xs.min() - a.pad, 0), min(xs.max() + a.pad, C["W"])
    nrm = np.asarray(trg.face_normals)[np.clip(fid, 0, None)]; nrm = np.where(((nrm @ C["R"].T)[..., 2] > 0)[..., None], -nrm, nrm)   # zur Kamera gewandt
    wahrheit = None
    if a.synth:
        sm = netz_laden(a.synth, obj, tr); bild, d_s, ok_s = schattiert(sm, C)
        if a.blur > 0: bild = cv2.GaussianBlur(bild, (0, 0), a.blur)
        wahrheit = np.where(ok & np.isfinite(d_s), d_tr - d_s, 0.0) if not a.traeger_synth else np.zeros_like(d_tr)
        if a.traeger_synth: bild, _, _ = schattiert(trg, C)
    else:
        bild = C["im"]
    c = (slice(y0, y1), slice(x0, x1))
    hh_c, disp_c, fit = relief_schaetzen(bild[c], d_tr[c], ok[c], C, a.sigma_m, a.hmax, a.lang)
    h = np.zeros_like(d_tr); h[c] = hh_c; tag = ("synth_" + os.path.basename(a.synth).replace(".stl", "") + ("_traegerbild" if a.traeger_synth else "")) if a.synth else "echt_" + a.foto
    pst = os.path.join(aus, f"{a.teil}_{tag}_relief.stl"); mm, nf = gitter_stl(pos, nrm, h, ok, C, obj, tr, a.schritt, pst, d_tr)
    ber = dict(teil=a.teil, modus=tag, kamera=nr, fit=fit, hmax=a.hmax, sigma_m=a.sigma_m, maske_px=int(ok.sum()), faces=nf, stl=pst, h_rms_m=float(np.sqrt(np.mean(h[ok] ** 2))), h_p99_m=float(np.percentile(np.abs(h[ok]), 99)))
    if wahrheit is not None:
        wt = wahrheit.copy(); sg = fit["sigma_px"]; mk = ok.astype(np.float32)
        lo = cv2.GaussianBlur((wt * mk).astype(np.float32), (0, 0), sg) / np.maximum(cv2.GaussianBlur(mk, (0, 0), sg), 1e-3); wt = np.clip(np.where(ok, wt - lo, 0), -a.hmax, a.hmax)   # gleicher Hochpass/Kappung
        e, t_ = h[ok], wt[ok]; ber["wahrheit_hp_rms_m"] = float(np.sqrt(np.mean(t_ ** 2))); ber["fehler_rms_m"] = float(np.sqrt(np.mean((e - t_) ** 2)))
        ber["null_basis_rms_m"] = ber["wahrheit_hp_rms_m"]; ber["korrelation"] = float(np.corrcoef(e, t_)[0, 1]) if t_.std() > 1e-9 and e.std() > 1e-9 else None
        ber["steigung_est_auf_wahr"] = float(np.dot(e, t_) / max(np.dot(t_, t_), 1e-12))
        # Rippenlage: Rippen = Wahrheit > 0,03 m (vorstehend); Anteil, den die Schaetzung ebenfalls > 0,01 m hat und umgekehrt (Dilatation 2 px) -> Lage
        rw = (wt > 0.03) & ok; re = (h > 0.01) & ok; k2 = np.ones((5, 5), np.uint8)
        rwd = cv2.dilate(rw.astype(np.uint8), k2).astype(bool); red = cv2.dilate(re.astype(np.uint8), k2).astype(bool)
        ber["rippen_recall"] = float((re & rwd).sum() / max(re.sum(), 1)) if False else float((rw & red).sum() / max(rw.sum(), 1)); ber["rippen_praez"] = float((re & rwd).sum() / max(re.sum(), 1))
        ber["rippen_px_wahr"] = int(rw.sum()); ber["rippen_px_est"] = int(re.sum())
    # Bilder
    def farbe(x, lim):
        v = np.clip(x / lim, -1, 1); im = np.zeros(x.shape + (3,), np.uint8) + 255; pos_ = v > 0
        im[..., 1] = np.where(pos_, 255 * (1 - v), 255 * (1 + v)); im[..., 2] = np.where(pos_, 255, 255 * (1 + v)); im[..., 0] = np.where(pos_, 255 * (1 - v), 255)
        im[~ok] = 255; return im
    sp = [bild[c].copy()]; cv2.putText(sp[0], "Eingabe", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    dn = cv2.normalize(disp_c, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8); sp.append(cv2.applyColorMap(dn, cv2.COLORMAP_TURBO)); cv2.putText(sp[-1], "DA-V2 Disparitaet", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    if wahrheit is not None: sp.append(farbe(wt, a.hmax)[c]); cv2.putText(sp[-1], "Wahrheit (Hochpass)", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    sp.append(farbe(h, a.hmax)[c]); cv2.putText(sp[-1], "Schaetzung rot=vor blau=zurueck, +-%.2f m" % a.hmax, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    out = np.hstack(sp); sk = min(1.0, 2600 / out.shape[1]); out = cv2.resize(out, None, fx=sk, fy=sk, interpolation=cv2.INTER_AREA)
    pb = os.path.join(aus, f"{a.teil}_{tag}_felder.jpg"); cv2.imwrite(pb, out, [cv2.IMWRITE_JPEG_QUALITY, 88]); ber["bild_felder"] = pb
    # Gegenprobe: Foto | Traeger glatt | Traeger+Relief (Foto-Kanten orange)
    ber["gegenprobe"] = []
    for g2 in [x for x in a.gegen.split(",") if x]:
        C2 = kamera(objp, obj, g2); tr2 = verschiebung(C2["kk"]); t2 = netz_laden(a.traeger, obj, tr2); g_glatt, dg, okg = schattiert(t2, C2)
        mm2 = mm.copy(); mm2.apply_translation(tr2 - tr); g_rel, dr, okr = schattiert(mm2, C2)
        ysx, xsx = np.nonzero(okr | okg); p = 30; yy0, yy1, xx0, xx1 = max(ysx.min() - p, 0), min(ysx.max() + p, C2["H"]), max(xsx.min() - p, 0), min(xsx.max() + p, C2["W"])
        foto = C2["im"][yy0:yy1, xx0:xx1].copy(); gr = cv2.GaussianBlur(cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY), (0, 0), 1.2); mag = np.hypot(cv2.Sobel(gr, cv2.CV_32F, 1, 0), cv2.Sobel(gr, cv2.CV_32F, 0, 1))
        hi = max(float(np.percentile(mag, 85)), 8.0); kan = cv2.Canny(gr, 0.5 * hi, hi, L2gradient=True) > 0
        # Modellkanten des Reliefs (Tiefensprung/Normalsprung) auf dem Foto
        gl = cv2.cvtColor(g_rel[yy0:yy1, xx0:xx1], cv2.COLOR_BGR2GRAY); mk_ = cv2.Canny(gl, 30, 90) > 0
        # Lagemass: Kanten der vorstehenden Relief-Zonen (Hoehe > 2 cm gegen den glatten Traeger) liegen im Foto auf Fotokanten? Anteil <= 4 px, Vergleich mit 40 px verschobener Zone
        hz = np.where(np.isfinite(dr) & np.isfinite(dg), dg - dr, 0.0)[yy0:yy1, xx0:xx1] > 0.02; hz = cv2.morphologyEx(hz.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)); rd = (hz - cv2.erode(hz, np.ones((3, 3), np.uint8))) > 0
        dt = cv2.distanceTransform((~kan).astype(np.uint8), cv2.DIST_L2, 3)
        if rd.sum() > 50:
            ber.setdefault("lage_" + g2, dict(rand_px=int(rd.sum()), anteil_4px=float((dt[rd] <= 4).mean()), median_px=float(np.median(dt[rd])),
                 zufall_anteil_4px=float(np.mean([(dt[np.roll(rd, (dy, dx), (0, 1))] <= 4).mean() for dy, dx in ((40, 0), (-40, 0), (0, 40), (0, -40), (30, 30), (-30, -30))]))))
        ueb = foto.copy(); ueb[kan] = (255, 160, 0); ueb[mk_] = (0, 0, 255)
        for im_, nm in ((foto, "Foto " + g2), (g_glatt[yy0:yy1, xx0:xx1].copy(), "Traeger glatt"), (g_rel[yy0:yy1, xx0:xx1].copy(), "Traeger+Relief"), (ueb, "Foto orange / Relief rot")): cv2.putText(im_, nm, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        o2 = np.hstack([foto, g_glatt[yy0:yy1, xx0:xx1], g_rel[yy0:yy1, xx0:xx1], ueb]); sk = min(1.0, 2600 / o2.shape[1]); o2 = cv2.resize(o2, None, fx=sk, fy=sk, interpolation=cv2.INTER_AREA)
        pg = os.path.join(aus, f"{a.teil}_{tag}_gegen_{g2}.jpg"); cv2.imwrite(pg, o2, [cv2.IMWRITE_JPEG_QUALITY, 88]); ber["gegenprobe"].append(pg)
    json.dump(ber, open(os.path.join(aus, f"{a.teil}_{tag}.json"), "w"), indent=1, ensure_ascii=False); print(json.dumps(ber, indent=1, ensure_ascii=False))
    return ber


if __name__ == "__main__":
    main()
