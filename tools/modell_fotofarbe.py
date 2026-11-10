#!/usr/bin/env python3
"""modell_fotofarbe.py - Modelloberflaeche mit echten Fotofarben einfaerben (Viewer, Nutzer 10.11.: "Echtheitseindruck").

Je Oberflaechenpunkt (gleiche Stichprobe wie viewer_kanten_bauen: sample_surface_even, seed 0) wird die Farbe aus den kalibrierten Fotos geholt:
  - Sicht: Tiefe je Kamera exakt gerastert (render_kern.dreiecke_rastern, GPU); Punkt sichtbar, wenn er nicht hinter dem Modell liegt
    (Toleranz 1 % + 5 cm) -> keine Farbe von davorliegenden Bauteilen.
  - Gewicht je Ansicht: cos(Einfallswinkel)^2 / Abstand (frontal und nah = scharf); Ansichten mit cos < 0,25 entfallen.
  - Farbe = Median je Kanal ueber die bis zu 6 besten Ansichten: Marktstaende/Leute/Autos vor der Fassade (Foto handy_03) stehen nur in
    einzelnen Fotos -> faerben nicht durch. Kein Mitteln von Quellen gleicher Art ueber Ausrichtungsfehler hinaus noetig, nur Darstellung.
  - Punkte ohne Ansicht: keine Farbe (Viewer zeigt sie grau schattiert = nicht fotografiert).
Rahmen: Kameras und Modell im gleichen Rahmen (kam_lot2 + Modell-STL in Metern wie im Viewer); Pruefung per Kantenueberlagerung (--pruefbild).
  venv-seg python -I tools/modell_fotofarbe.py MODELL_m.stl KAM.json BILDER_DIR AUS.npz [--n 400000] [--n_kam 160] [--skala 0.25]
"""
import sys, os, json, time, argparse, numpy as np, trimesh, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as RK

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("kam"); ap.add_argument("bilder"); ap.add_argument("aus")
    ap.add_argument("--n", type=int, default=400000); ap.add_argument("--n_kam", type=int, default=160); ap.add_argument("--skala", type=float, default=0.25)
    ap.add_argument("--k", type=int, default=6)
    a = ap.parse_args(); import torch; t0 = time.time()
    m = trimesh.load(a.stl, force="mesh")
    P, fi = trimesh.sample.sample_surface_even(m, a.n, seed=0) if hasattr(trimesh.sample, "sample_surface_even") else trimesh.sample.sample_surface(m, a.n)
    N = m.face_normals[fi]
    K = json.load(open(a.kam)); nam = [k for k in K if os.path.exists(os.path.join(a.bilder, k))]
    # Kameraauswahl: Fernpunkt-Auswahl auf Blickrichtung+Standort (Vielfalt), damit jede Seite ihre besten Fotos bekommt
    dirs = np.array([np.asarray(K[k]["Rn"])[2] for k in nam]); Cs = np.array([K[k]["C"] for k in nam]); ctr = P.mean(0)
    mrk = np.concatenate([dirs * 10.0, (Cs - ctr) / 3.0], 1); wahl = [0]; dmin = np.linalg.norm(mrk - mrk[0], axis=1)
    while len(wahl) < min(a.n_kam, len(nam)):
        j = int(np.argmax(dmin)); wahl.append(j); dmin = np.minimum(dmin, np.linalg.norm(mrk - mrk[j], axis=1))
    dev = "cuda"; Pg = torch.as_tensor(P, dtype=torch.float64, device=dev); Ng = torch.as_tensor(N, dtype=torch.float64, device=dev)
    KB = a.k; Wt = torch.zeros((len(P), KB), dtype=torch.float32, device=dev); Cl = torch.zeros((len(P), KB, 3), dtype=torch.float32, device=dev)
    for n_, j in enumerate(wahl):
        k = K[nam[j]]; s = a.skala; Wd, Hd = int(k["W"] * s), int(k["H"] * s); f, cx, cy = k["f"] * s, k["cx"] * s, k["cy"] * s
        R = np.asarray(k["Rn"], float); t = np.asarray(k["tn"], float)
        im = cv2.imread(os.path.join(a.bilder, nam[j]), cv2.IMREAD_REDUCED_COLOR_4 if s <= 0.25 else cv2.IMREAD_COLOR)
        if im is None: continue
        if im.shape[1] != Wd or im.shape[0] != Hd: im = cv2.resize(im, (Wd, Hd), interpolation=cv2.INTER_AREA)
        d, _, _ = RK.dreiecke_rastern(m, R, t, f, cx, cy, Wd, Hd, als_torch=True); D = torch.as_tensor(np.asarray(d), device=dev)
        Rg = torch.as_tensor(R, device=dev); tg = torch.as_tensor(t, device=dev)
        X = Pg @ Rg.T + tg; z = X[:, 2]; u = f * X[:, 0] / z.clamp(min=1e-6) + cx; v = f * X[:, 1] / z.clamp(min=1e-6) + cy
        iu, iv = torch.round(u).long(), torch.round(v).long(); ok = (z > 1) & (iu >= 0) & (iv >= 0) & (iu < Wd) & (iv < Hd)
        Cw = torch.as_tensor(np.asarray(k["C"], float), device=dev); sicht = (Cw - Pg); dist = sicht.norm(dim=1); cos = (Ng * sicht).sum(1) / dist
        ok &= cos > 0.25
        idx = torch.nonzero(ok, as_tuple=True)[0]; dz = D[iv[idx], iu[idx]].double(); vis = z[idx] <= dz * 1.01 + 0.05; idx = idx[vis]
        if not len(idx): continue
        w = (cos[idx] ** 2 / dist[idx]).float()
        img = torch.as_tensor(im[:, :, ::-1].copy(), device=dev).float()   # RGB
        col = img[iv[idx], iu[idx]]
        # Top-K je Punkt nach Gewicht fortschreiben
        Wc = torch.cat([Wt[idx], w[:, None]], 1); Cc = torch.cat([Cl[idx], col[:, None]], 1)
        top = torch.topk(Wc, KB, dim=1).indices; Wt[idx] = torch.gather(Wc, 1, top); Cl[idx] = torch.gather(Cc, 1, top[:, :, None].expand(-1, -1, 3))
        if n_ % 20 == 0: print(f"Kamera {n_ + 1}/{len(wahl)} {nam[j]}: {len(idx)} Punkte sichtbar, {time.time() - t0:.0f} s", flush=True)
    belegt = (Wt > 0).sum(1)
    Cm = torch.where(Wt[:, :, None] > 0, Cl, torch.full_like(Cl, float("nan")))
    med = torch.nanmedian(Cm, dim=1).values; med = torch.nan_to_num(med, nan=-1.0)
    C = med.clamp(-1, 255).round().cpu().numpy().astype(np.int16); bel = belegt.cpu().numpy()
    np.savez_compressed(a.aus, P=P.astype(np.float32), C=C, n=bel.astype(np.uint8), N=N.astype(np.float32))
    print(f"fertig: {len(P)} Punkte, gefaerbt {np.mean(bel > 0) * 100:.1f} %, >= 3 Ansichten {np.mean(bel >= 3) * 100:.1f} %, {time.time() - t0:.0f} s -> {a.aus}")

if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("modell_fotofarbe")
    main()
