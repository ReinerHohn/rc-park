#!/usr/bin/env python3
"""foto_dach_gemeinsam.py - GEMEINSAME Anpassung ueber viele Fotos: eine Dachform fuer alle, je Foto eine eigene Kamera.

Warum: Einzelfoto-Anpassung hat gekoppelte Kamera-Parameter (Abstand/Brennweite, Hoehe/Neigung); jedes Foto kann sich die Dachhoehe passend
verbiegen. Eine Dachform, die ueber ALLE Fotos (mit je frisch verfeinerter Kamera) das beste Gesamt-IoU gibt, ist belastbarer.
Stufe 1  `pose`: Kamera je Foto am Basismodell (Zufall + CEM), Ueberlagerungsbilder -> Sichtkontrolle, Fotos mit IoU < 0.75 entfallen.
Stufe 2  `grid`: je STL-Variante (Dateien <pfad>/<name>.stl) Kamera je Foto verfeinern (CEM ab Basiskamera), IoU je Foto/Variante.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_dach_gemeinsam.py pose OUTDIR [Foto-Nr ...]
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_dach_gemeinsam.py grid OUTDIR STLDIR [Foto-Nr ...]   (nur Fotos, deren Ueberlagerung pose_<nr>.png den Turm im gruenen ROI zeigt!)
ROI wird automatisch um die Turmspitze gelegt (Nachbarhaeuser koennen stoeren -> Ueberlagerungsbild pruefen).
"""
import sys, os, glob, json, math, numpy as np, cv2, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_silhouette_gpu as F
import foto_profil_gpu as PG
dev = F.dev; lo, hi = PG.lo, PG.hi
DEFAULT = [k for k, v in F.FOTOS.items() if v[1].get("seite")] or ["042", "043", "044"]   # aus objekt.json (silhouette_frei)

def load(nr, width=400):
    fn = glob.glob(F.FD + f"{nr}_*")[0]; im = cv2.imread(fn); h, w = im.shape[:2]; s = width / w
    im = cv2.resize(im, (width, int(h * s)), interpolation=cv2.INTER_AREA); N = ~F.sky_mask(im)
    No = cv2.morphologyEx(N.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)).astype(bool)   # Leitungen weg
    H, W = N.shape; cols = np.arange(int(W * .2), int(W * .8)); ys = [np.argmax(No[:, c]) if No[:, c].any() else H for c in cols]
    k = int(np.argmin(ys)); x0, y0 = int(cols[k]), int(ys[k])
    if nr in F.FOTOS and F.FOTOS[nr][1].get("roi"): roi = F.FOTOS[nr][1]["roi"]
    else: roi = (max(0, x0 - 85), max(0, y0 - 6), min(W, x0 + 85), min(H, y0 + 190))
    return im, N, roi

AZ_SEITE = {"Sued": math.pi / 2, "Nord": -math.pi / 2, "West": 0.0, "Ost": math.pi}   # Kameraseite -> Azimut in F.render

def grenzen(seite=None, spanne=math.radians(50)):
    """Suchgrenzen; bei bekannter Fotoseite Azimut auf +-spanne um die Seite (hebt die 90-Grad-Mehrdeutigkeit des Quadratturms auf)."""
    l, h = lo.clone(), hi.clone()
    if seite in AZ_SEITE: l[1], h[1] = AZ_SEITE[seite] - spanne, AZ_SEITE[seite] + spanne
    return l, h

def fit(P, T, roi, H, W, seeds=(0, 1, 2), seite=None):
    f0 = 5.4 / 4.29 * W; best = None; l, h = grenzen(seite); PG.lo, PG.hi = l, h
    for sd_ in seeds:
        g = torch.Generator(device=dev).manual_seed(sd_); cand = []
        for _ in range(96):
            th = l + (h - l) * torch.rand((256, 8), device=dev, generator=g); sc, _ = F.score(P, th, T, roi, f0, W, H); k = sc.topk(20).indices; cand.append((sc[k], th[k]))
        sc = torch.cat([c[0] for c in cand]); th = torch.cat([c[1] for c in cand]); k = sc.topk(40).indices
        s, t = PG.cem(P, T, roi, H, W, f0, th[k].mean(0), th[k].std(0) + 1e-3, 50, seed=sd_)
        if best is None or s > best[0]: best = (s, t)
    return best, f0

def overlay(im, P, th, f0, W, H, roi, path):
    M = F.render(P, th[None], W, H, f0)[0].cpu().numpy().astype(np.uint8); M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    o = im.copy(); cs, _ = cv2.findContours(M, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(o, cs, -1, (0, 0, 255), 1)
    cv2.rectangle(o, (roi[0], roi[1]), (roi[2], roi[3]), (0, 255, 0), 1); cv2.imwrite(path, o)

def main():
    mode, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True); cam = out + "/kameras.json"
    if mode == "pose":
        nrs = sys.argv[3:] or DEFAULT; F.STL = "/home/oem/git/rc-park/modelle/stl/martinstor_v4_1-87.stl"; P, _ = F.load_points(200000); res = {}
        for nr in nrs:
            seite = F.FOTOS.get(nr, (None, {}))[1].get("seite"); seite = seite if seite in AZ_SEITE else None
            im, N, roi = load(nr); H, W = N.shape; T = torch.as_tensor(N, device=dev); (s, th), f0 = fit(P, T, roi, H, W, seite=seite)
            _l, _h = grenzen(seite); res[nr] = dict(iou=float(s), th=[float(x) for x in th], roi=list(map(int, roi)), seite=seite, az_grad=round(math.degrees(float(th[1])), 1), grenzen=[[float(x) for x in _l], [float(x) for x in _h]]);   # grenzen: Suchschranken dieser Anpassung (M4: Pruefung 'Parameter an der Schranke' im Sichtblatt)
            overlay(im, P, th, f0, W, H, roi, f"{out}/pose_{nr}.png"); print(nr, f"IoU {s:.3f}", flush=True)
        json.dump(res, open(cam, "w"))
    else:
        stldir = sys.argv[3]; base = json.load(open(cam)); keep = [k for k, v in base.items() if v["iou"] >= 0.75 and (len(sys.argv) < 5 or k in sys.argv[4:])]; print("verwendet:", keep, flush=True)
        data = {}
        for nr in keep:
            im, N, roi = load(nr); H, W = N.shape; data[nr] = (torch.as_tensor(N, device=dev), tuple(base[nr]["roi"]), H, W, torch.tensor(base[nr]["th"], device=dev))
        stls = sorted(glob.glob(stldir + "/*.stl")); table = {}
        for st in stls:
            name = os.path.basename(st)[:-4]; F.STL = st; P, _ = F.load_points(200000); table[name] = {}
            for nr in keep:
                T, roi, H, W, th0 = data[nr]; f0 = 5.4 / 4.29 * W; PG.lo, PG.hi = grenzen(base[nr].get("seite"))
                s, th = PG.cem(P, T, roi, H, W, f0, th0.clone(), (hi - lo) * 0.02, 40, seed=0)
                table[name][nr] = float(s)
            print(name, " ".join(f"{nr}:{table[name][nr]:.3f}" for nr in keep), f"| Mittel {np.mean(list(table[name].values())):.4f}", flush=True)
            json.dump(table, open(out + "/tabelle.json", "w"))

if __name__ == "__main__":
    main()
