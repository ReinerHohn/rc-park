#!/usr/bin/env python3
"""kanten_richtung.py - VORZEICHENBEHAFTETER Versatz Modellkante -> naechste Fotokante je Bauteil (Register BY).
Nach der Kameraanpassung (foto_kanten_loop.verfeinern): fuer jede sichtbare Modellkante der Region wird die naechste Fotokante (lange Canny-Kanten) gesucht, Versatz (dx,dy) in Pixeln.
Senkrechte Kanten (Bildrichtung +-30 Grad von senkrecht) liefern dx (Breite/Lage), waagerechte dy (Hoehe). Linke und rechte Bildhaelfte der Struktur getrennt:
  gleiche Vorzeichen links/rechts = Lagefehler (oder Kamera), entgegengesetzt = Breitenfehler. Meter = px * Tiefe / f.
Nur Mehrheit ueber Fotos zaehlt (CLAUDE.md: Gleichrichtung). Ergebnis audit/kanten_richtung.json.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/kanten_richtung.py [--fotos 030 031 040 041]
"""
import sys, os, json, glob, math, argparse, numpy as np, cv2, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_kanten_loop as L
dev = L.dev

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fotos", nargs="*", default=["030", "031", "040", "041"]); ap.add_argument("--objekt", default="modelle/martinstor"); ap.add_argument("--stl", default="modelle/stl/martinstor_v4_1-87.stl")
    ap.add_argument("--breite", type=int, default=640); ap.add_argument("--max-px", type=float, default=15.0); a = ap.parse_args(); L.gpu_warten()
    E, S, D = L.modellkanten(a.stl); out = {}
    for nr in a.fotos:
        k = json.load(open(os.path.join(a.objekt, "messprotokoll", f"K-{nr}.json"))); k = k.get("kamera", k)
        fn = glob.glob(f"daten/martinstor/fotos/{nr}_*"); im0 = cv2.imread(fn[0]); h0, w0 = im0.shape[:2]; s = a.breite / w0; im = cv2.resize(im0, (a.breite, int(h0 * s)), interpolation=cv2.INTER_AREA); H, W = im.shape[:2]
        DT, _ = L.foto_dts(im); cam = dict(r=torch.tensor(k["rvec"], device=dev, dtype=torch.float32), t=torch.tensor(k["t"], device=dev, dtype=torch.float32), lf=torch.tensor(math.log(k["f_px"] * s), device=dev, dtype=torch.float32), cx=k.get("cx", w0 / 2) * s, cy=k.get("cy", h0 / 2) * s)
        cam = L.verfeinern(E, S, D, cam, DT, W, H)
        g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0); ed = cv2.Canny(g, 50, 140); n, lab, st, _ = cv2.connectedComponentsWithStats((ed > 0).astype(np.uint8), connectivity=8)
        ed = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 20]).astype(np.uint8)
        dist, labels = cv2.distanceTransformWithLabels((1 - ed).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(ed); cl = {int(l): (xs[i], ys[i]) for i, l in enumerate(labels[ys, xs])}      # Label -> Pixel
        vis = L.sichtbar(E, S, cam, W, H); uv, z = L.projiziere(E, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"]); f = float(torch.exp(cam["lf"]))
        b, _ = L.projiziere(E + 0.1 * D, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"]); ang = (torch.rad2deg(torch.atan2(b[:, 1] - uv[:, 1], b[:, 0] - uv[:, 0])) % 180).cpu().numpy()
        U = uv.detach().cpu().numpy(); Z = z.detach().cpu().numpy(); V = vis.cpu().numpy(); P = E.cpu()
        sel = V & (U[:, 0] >= 0) & (U[:, 0] < W - 1) & (U[:, 1] >= 0) & (U[:, 1] < H - 1); iu = U[:, 0].astype(int).clip(0, W - 1); iv = U[:, 1].astype(int).clip(0, H - 1)
        dd = dist[iv, iu]; lab_ = labels[iv, iu]; sel &= dd < a.max_px
        nx = np.zeros(len(U)); ny = np.zeros(len(U))
        idx = np.nonzero(sel)[0]
        for i in idx:
            q = cl.get(int(lab_[i]));
            if q is None: sel[i] = False; continue
            nx[i] = q[0] - U[i, 0]; ny[i] = q[1] - U[i, 1]
        vert = (np.abs(ang - 90) < 30); hori = (ang < 30) | (ang > 150); res = {}
        for name, fn_ in L.REGIONEN:
            m = fn_(P).numpy() & sel
            if m.sum() < 30: continue
            xm = np.median(U[m, 0]); r = dict(punkte=int(m.sum()))
            for lr, mm in (("links", m & (U[:, 0] < xm)), ("rechts", m & (U[:, 0] >= xm))):
                v = mm & vert
                if v.sum() >= 15: r[f"dx_{lr}_px"] = round(float(np.median(nx[v])), 2); r[f"dx_{lr}_m"] = round(float(np.median(nx[v] * Z[v] / f)), 3)
            h = m & hori
            if h.sum() >= 15: r["dy_px"] = round(float(np.median(ny[h])), 2); r["dy_m"] = round(float(np.median(ny[h] * Z[h] / f)), 3)
            res[name] = r
        out[nr] = res; print(nr, json.dumps(res, ensure_ascii=False)[:600], flush=True)
    json.dump(out, open(os.path.join(a.objekt, "audit", "kanten_richtung.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
