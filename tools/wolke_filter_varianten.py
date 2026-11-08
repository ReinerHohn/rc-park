#!/usr/bin/env python3
"""wolke_filter_varianten.py - S10 Teil C: Wolkenvarianten F0..F3 erzeugen (Register CV). Generisch, keine Objektwerte: alles aus --dicht (COLMAP-Arbeitsordner mit
sparse/, images/, stereo/{depth_maps,normal_maps,consistency_graphs}, kameras_unverzerrt.json). Der Quellordner wird nur GELESEN (Symlinks).

  masken  : SegFormer (ADE20K) -> je Foto PNG 255=benutzen, 0=ignorieren (Himmel, Personen, Fahrzeuge, Vegetation, Staende/Markisen/Zelte); Puffer px.
            venv-seg, GPU:  tools/wolke_filter_varianten.py masken --dicht D --aus DIR [--ohne 001 024 ..]
  fusion  : stereo_fusion mit eigenen Schwellen in eigenem Arbeitsordner <aus>/<name> (Symlinks auf Tiefenkarten), eigene fusion.cfg ohne --ohne-Fotos,
            optional --masken DIR.  venv-colmap:  tools/wolke_filter_varianten.py fusion --dicht D --aus DIR --name F1 [--min-pixel 7 --reproj 1.0 --tiefe 0.005 --normal 6]
  f3      : Lage+Farbe-Filter auf einer fused.ply (Ausreisser gegen lokale Ebene/Nachbarschaftsfarbe + bilaterale Glaettung entlang der Normalen); schreibt ply + vis-Teilmenge.
            venv-seg:  tools/wolke_filter_varianten.py f3 --ein DIR_QUELLE --aus DIR --name F3 [Schwellen]
Alle Schwellen sind Parameter mit Standard; die Standardwerte wurden an einer SYNTHETISCHEN Szene (tools/test_wolke_filter_varianten.py) festgelegt, nicht am Kaufhaus.
"""
import os, sys, json, argparse, time, shutil, struct
import numpy as np

MASKEN_KLASSEN = ("sky", "person", "car", "bus", "truck", "van", "bicycle", "minibike", "animal", "boat", "airplane",      # ADE20K-Namen, objektunabhaengig
                  "tree", "plant", "grass", "flower", "palm", "booth", "tent", "canopy", "awning")


# ---------------------------------------------------------------- ply / vis
def ply_lesen_voll(p):
    with open(p, "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); a = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    return a


def ply_schreiben(p, a):
    hd = ["ply", "format binary_little_endian 1.0", f"element vertex {len(a)}"] + [f"property {'float' if a.dtype[k].kind == 'f' else 'uchar'} {k}" for k in a.dtype.names] + ["end_header"]
    with open(p, "wb") as f: f.write(("\n".join(hd) + "\n").encode("ascii")); f.write(np.ascontiguousarray(a).tobytes())


def vis_lesen(p):
    b = np.fromfile(p, dtype="<u4"); n = int(b[0]) | (int(b[1]) << 32); i = 2; out = []
    for k in range(n):
        c = int(b[i]); out.append(b[i + 1:i + 1 + c].copy()); i += 1 + c
    return out


def vis_schreiben(p, listen):
    parts = [np.array([len(listen) & 0xffffffff, len(listen) >> 32], "<u4")]
    for v in listen: parts.append(np.array([len(v)], "<u4")); parts.append(np.asarray(v, "<u4"))
    np.concatenate(parts).tofile(p)


# ---------------------------------------------------------------- Masken
def cmd_masken(a):
    import torch, cv2
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    K = json.load(open(os.path.join(a.dicht, "kameras_unverzerrt.json"))); ids = [i for i in sorted(K, key=int) if i not in a.ohne]
    proc = SegformerImageProcessor.from_pretrained(a.modell); model = SegformerForSemanticSegmentation.from_pretrained(a.modell).eval().to("cuda" if torch.cuda.is_available() else "cpu")
    cls = [int(k) for k, v in model.config.id2label.items() if v.split(",")[0].strip() in MASKEN_KLASSEN]; print("maskierte Klassen:", {i: model.config.id2label[i] for i in cls}, flush=True)
    os.makedirs(a.aus, exist_ok=True); rep = {}; t0 = time.time(); ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.puffer + 1, 2 * a.puffer + 1)); dev = next(model.parameters()).device
    for n, i in enumerate(ids):
        im = cv2.imread(os.path.join(a.dicht, "images", K[i]["bild"])); H, W = im.shape[:2]; s = a.breite / W; sm = cv2.resize(im, (a.breite, int(H * s)), interpolation=cv2.INTER_AREA)
        with torch.no_grad():
            x = proc(images=cv2.cvtColor(sm, cv2.COLOR_BGR2RGB), return_tensors="pt")["pixel_values"].to(dev); lg = model(pixel_values=x).logits
            lg = torch.nn.functional.interpolate(lg, size=sm.shape[:2], mode="bilinear", align_corners=False); seg = lg.argmax(1)[0].cpu().numpy()
        dyn = cv2.resize(np.isin(seg, cls).astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST); dyn = cv2.dilate(dyn, ke)
        m = np.where(dyn > 0, 0, 255).astype(np.uint8); cv2.imwrite(os.path.join(a.aus, K[i]["bild"] + ".png"), m); rep[i] = round(float((m == 0).mean()), 4)
        if n % 10 == 0: print(f"  {n + 1}/{len(ids)} {time.time() - t0:.0f} s, maskiert {100 * rep[i]:.1f} %", flush=True)
    v = np.array(list(rep.values())); json.dump(dict(klassen={i: model.config.id2label[i] for i in cls}, breite=a.breite, puffer=a.puffer, maskiert_anteil=rep, mittel=float(v.mean()), maximum=float(v.max())), open(os.path.join(a.aus, "bericht.json"), "w"), indent=1)
    print(f"{len(ids)} Fotos, maskiert Mittel {100 * v.mean():.1f} %, Max {100 * v.max():.1f} %, {time.time() - t0:.0f} s")


# ---------------------------------------------------------------- Fusion
def cmd_fusion(a):
    import pycolmap
    K = json.load(open(os.path.join(a.dicht, "kameras_unverzerrt.json"))); ids = [i for i in sorted(K, key=int) if i not in a.ohne]
    w = os.path.join(a.aus, a.name); os.makedirs(os.path.join(w, "stereo"), exist_ok=True)
    for src, dst in (("images", "images"), ("sparse", "sparse"), ("stereo/depth_maps", "stereo/depth_maps"), ("stereo/normal_maps", "stereo/normal_maps"), ("stereo/consistency_graphs", "stereo/consistency_graphs")):
        d = os.path.join(w, dst)
        if not os.path.lexists(d): os.symlink(os.path.realpath(os.path.join(a.dicht, src)), d)
    with open(os.path.join(w, "stereo", "fusion.cfg"), "w") as f: f.write("\n".join(K[i]["bild"] for i in ids) + "\n")
    fo = pycolmap.StereoFusionOptions(); fo.num_threads = 1                                     # deterministisch (Register CA)
    if a.min_pixel is not None: fo.min_num_pixels = a.min_pixel
    if a.reproj is not None: fo.max_reproj_error = a.reproj
    if a.tiefe is not None: fo.max_depth_error = a.tiefe
    if a.normal is not None: fo.max_normal_error = a.normal
    if a.masken: fo.mask_path = os.path.realpath(a.masken)
    print(f"{a.name}: {len(ids)} Fotos, {fo.summary().replace(chr(10), ' ')}", flush=True); t0 = time.time()
    ply = os.path.join(w, "fused.ply"); pycolmap.stereo_fusion(ply, w, options=fo, output_type="ply")
    n = len(ply_lesen_voll(ply)); print(f"{a.name}: {n} Punkte, {time.time() - t0:.0f} s", flush=True)
    for fn in ("kameras_unverzerrt.json",):
        if not os.path.lexists(os.path.join(w, fn)): os.symlink(os.path.realpath(os.path.join(a.dicht, fn)), os.path.join(w, fn))
    json.dump(dict(name=a.name, punkte=n, fotos=len(ids), ohne=a.ohne, optionen=fo.summary(), masken=a.masken, sekunden=round(time.time() - t0)), open(os.path.join(w, "variante.json"), "w"), indent=1)


# ---------------------------------------------------------------- F3: Lage + Farbe
def rgb2lab(c):
    c = c.astype(np.float64) / 255.0; c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]); xyz = (c @ M.T) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116); return np.c_[116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])]


def f3_filter(P, N, C, k=24, k_mad=3.5, ebene_mad=4.0, farbe_mad=4.0, sig_n_grad=25.0, iter_=1, log=print):
    """P (n,3) m, N (n,3) Normalen, C (n,3) uint8. Rueckgabe (keep, P_neu). Alle Schwellen RELATIV zur lokalen Streuung (MAD), keine Meterwerte:
    (1) Dichte: mittlerer kNN-Abstand > Median + k_mad*MAD (global, Mass relativ) -> Ausreisser in der Luft;
    (2) Lage: Abstand zur robusten lokalen Ebene (Median-Normalenversatz der Nachbarn) > ebene_mad * lokale MAD UND Normale weicht ab -> Ausreisser gegen lokale Ebene;
    (3) Farbe: Lab-Abstand zum Nachbarschaftsmedian > farbe_mad*MAD UND Lageversatz > lokale MAD -> Punkt passt weder in Lage noch Farbe;
    (4) bilaterale Glaettung entlang der Normalen: Gewichte Raum (Gauss ~ lokaler Abstand) * Normalenwinkel (sig_n_grad) * Lab-Farbe (lokale MAD) -> Kanten bleiben, Rauschen sinkt."""
    from scipy.spatial import cKDTree
    t0 = time.time(); n = len(P); tr = cKDTree(P); dd, ii = tr.query(P, k=k + 1, workers=-1); dd, ii = dd[:, 1:], ii[:, 1:]; log(f"kNN {time.time() - t0:.0f} s")
    keep = np.ones(n, bool); md = dd.mean(1); med = np.median(md); mad = np.median(np.abs(md - med)) + 1e-9
    k1 = md <= med + k_mad * 1.4826 * mad; keep &= k1; log(f"(1) Dichte: {int((~k1).sum())} entfernt")
    Nn = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9); off = np.einsum("nkj,nj->nk", P[ii] - P[:, None, :], Nn)             # Lage der Nachbarn entlang der Punktnormalen
    omed = np.median(off, 1); omad = np.median(np.abs(off - omed[:, None]), 1) + 1e-4                                                          # robuste lokale Streuung (>= 0,1 mm)
    sigma_loc = np.maximum(omad * 1.4826, 1e-3)
    ang = np.degrees(np.arccos(np.clip(np.einsum("nkj,nj->nk", Nn[ii], Nn), -1, 1))); angmed = np.median(ang, 1)
    k2 = ~((np.abs(omed) > ebene_mad * sigma_loc) & (angmed > sig_n_grad)); keep &= k2; log(f"(2) Lage/Ebene: {int((~k2).sum())} entfernt")
    L = rgb2lab(C); Lm = np.median(L[ii], 1); dL = np.linalg.norm(L - Lm, axis=1); dL_ref = np.median(np.linalg.norm(L[ii] - Lm[:, None, :], axis=2), 1) + 1.0
    k3 = ~((dL > farbe_mad * 1.4826 * dL_ref) & (np.abs(omed) > sigma_loc)); keep &= k3; log(f"(3) Farbe+Lage: {int((~k3).sum())} entfernt")
    Pn = P.copy()
    for _ in range(iter_):
        h = dd.mean(1, keepdims=True) + 1e-6; w_r = np.exp(-0.5 * (dd / h) ** 2)
        w_n = np.exp(-0.5 * (ang / sig_n_grad) ** 2); dc = np.linalg.norm(L[ii] - L[:, None, :], axis=2); w_c = np.exp(-0.5 * (dc / (1.4826 * dL_ref[:, None] * 2.0)) ** 2)
        W = w_r * w_n * w_c; shift = (W * off).sum(1) / np.maximum(W.sum(1), 1e-9); Pn = P + Nn * shift[:, None]
    log(f"(4) bilaterale Glaettung: mittlere Verschiebung {np.abs(shift).mean() * 100:.2f} cm, p90 {np.percentile(np.abs(shift), 90) * 100:.2f} cm; {time.time() - t0:.0f} s")
    return keep, Pn


def cmd_f3(a):
    src = a.ein; arr = ply_lesen_voll(os.path.join(src, "fused.ply")); vis = vis_lesen(os.path.join(src, "fused.ply.vis"))
    P = np.c_[arr["x"], arr["y"], arr["z"]].astype(np.float64); N = np.c_[arr["nx"], arr["ny"], arr["nz"]].astype(np.float64); C = np.c_[arr["red"], arr["green"], arr["blue"]]
    keep, Pn = f3_filter(P, N, C, a.k, a.k_mad, a.ebene_mad, a.farbe_mad, a.sig_n, a.iter)
    out = arr.copy(); out["x"], out["y"], out["z"] = Pn[:, 0], Pn[:, 1], Pn[:, 2]; out = out[keep]; w = os.path.join(a.aus, a.name); os.makedirs(w, exist_ok=True)
    ply_schreiben(os.path.join(w, "fused.ply"), out); vis_schreiben(os.path.join(w, "fused.ply.vis"), [v for v, kk in zip(vis, keep) if kk])
    for fn in ("kameras_unverzerrt.json", "stereo", "images", "sparse"):
        d = os.path.join(w, fn)
        if not os.path.lexists(d): os.symlink(os.path.realpath(os.path.join(src, fn)), d)
    json.dump(dict(name=a.name, quelle=src, ein=int(len(P)), aus=int(keep.sum()), parameter=dict(k=a.k, k_mad=a.k_mad, ebene_mad=a.ebene_mad, farbe_mad=a.farbe_mad, sig_n=a.sig_n, iter=a.iter)), open(os.path.join(w, "variante.json"), "w"), indent=1)
    print(f"{a.name}: {len(P)} -> {int(keep.sum())} Punkte")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("masken"); m.add_argument("--dicht", required=True); m.add_argument("--aus", required=True); m.add_argument("--ohne", nargs="*", default=[]); m.add_argument("--breite", type=int, default=960); m.add_argument("--puffer", type=int, default=12)
    m.add_argument("--modell", default="nvidia/segformer-b4-finetuned-ade-512-512"); m.set_defaults(f=cmd_masken)
    f = sp.add_parser("fusion"); f.add_argument("--dicht", required=True); f.add_argument("--aus", required=True); f.add_argument("--name", required=True); f.add_argument("--ohne", nargs="*", default=[]); f.add_argument("--masken")
    f.add_argument("--min-pixel", type=int); f.add_argument("--reproj", type=float); f.add_argument("--tiefe", type=float); f.add_argument("--normal", type=float); f.set_defaults(f=cmd_fusion)
    g = sp.add_parser("f3"); g.add_argument("--ein", required=True); g.add_argument("--aus", required=True); g.add_argument("--name", required=True); g.add_argument("--k", type=int, default=24); g.add_argument("--k-mad", type=float, default=3.5)
    g.add_argument("--ebene-mad", type=float, default=4.0); g.add_argument("--farbe-mad", type=float, default=4.0); g.add_argument("--sig-n", type=float, default=25.0); g.add_argument("--iter", type=int, default=1); g.set_defaults(f=cmd_f3)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__": main()
