#!/usr/bin/env python3
"""online_dach_overlay.py - Dach-Kanten des Gitters (z >= --zmin) auf ein kalibriertes Foto legen, nummeriert, neue Kanten (nicht im Vergleichsgitter) farbig.
Aufruf: python -I tools/online_dach_overlay.py KAM.json BILDER GITTER_NEU.json GITTER_ALT.json OUT_PREFIX bild1.jpg bild2.jpg ... [--zmin 12] [--maxn 60]
Ausgabe: OUT_PREFIX_<bild>.jpg + OUT_PREFIX_<bild>.json (Nummer -> Segment, Quelle, neu/alt, Laenge). Kein Z-Puffer (verdeckte Kanten erscheinen mit): das Urteil trifft die Sichtprobe.
Gruen = auch im alten Gitter (Abstand < 0,15 m), Rot/Orange = nur im neuen Gitter. Nichts Objektspezifisches."""
import sys, os, json, numpy as np, cv2


def proj(k, P, W, H):
    R = np.array(k["Rn"]); t = np.array(k["tn"]); X = P @ R.T + t; z = X[:, 2]; zz = np.maximum(z, 0.3); x = X[:, 0] / zz; y = X[:, 1] / zz
    f1 = 1 + k["params"][3] * (x * x + y * y); s = W / k["W"]
    return np.stack([(k["f"] * x * f1 + k["cx"]) * s, (k["f"] * y * f1 + k["cy"]) * s], 1), z


def main():
    a = sys.argv[1:]; opt = {}
    for o, d in (("--zmin", 12.0), ("--maxn", 60)):
        if o in a: i = a.index(o); opt[o] = type(d)(a[i + 1]); del a[i:i + 2]
        else: opt[o] = d
    kam, bd, gn, ga, out = a[:5]; bilder = a[5:]; K = json.load(open(kam)); N = json.load(open(gn))["segmente"]; A = json.load(open(ga))["segmente"]
    pa = []
    for s in A:
        p0 = np.array(s[0]); p1 = np.array(s[1]); n = max(2, int(np.linalg.norm(p1 - p0) / 0.1)); pa.append(p0 + (p1 - p0) * np.linspace(0, 1, n)[:, None])
    PA = np.vstack(pa)
    from scipy.spatial import cKDTree
    T = cKDTree(PA)
    for b in bilder:
        im = cv2.imread(os.path.join(bd, b)); H, W = im.shape[:2]; k = K[b]; lst = []
        for i, s in enumerate(N):
            p0 = np.array(s[0]); p1 = np.array(s[1])
            if min(p0[2], p1[2]) < opt["--zmin"]: continue
            m = (p0 + p1) / 2; L = float(np.linalg.norm(p1 - p0))
            q = np.stack([p0, p1, m]); uv, z = proj(k, q, W, H)
            if (z < 0.5).any(): continue
            inb = [(0 <= u < W and 0 <= v < H) for u, v in uv]
            if not inb[2]: continue
            n = max(2, int(L / 0.1)); pp = p0 + (p1 - p0) * np.linspace(0, 1, n)[:, None]; neu = float((T.query(pp)[0] > 0.15).mean()) > 0.5
            lst.append((L, i, s, uv, neu))
        lst.sort(key=lambda x: -x[0]); lst = lst[:opt["--maxn"]]; info = {}
        for j, (L, i, s, uv, neu) in enumerate(lst):
            col = (0, 140, 255) if neu else (0, 220, 0)
            cv2.line(im, tuple(int(x) for x in uv[0]), tuple(int(x) for x in uv[1]), col, max(2, W // 700), cv2.LINE_AA)
            cv2.putText(im, str(j), tuple(int(x) for x in uv[2]), cv2.FONT_HERSHEY_SIMPLEX, max(0.5, W / 2500), (255, 255, 0), max(1, W // 1200), cv2.LINE_AA)
            info[j] = dict(idx=i, laenge=round(L, 2), quelle=s[2] if len(s) > 2 else None, neu_gegen_alt=neu, p0=s[0], p1=s[1])
        cv2.imwrite(f"{out}_{os.path.splitext(b)[0]}.jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 90]); json.dump(info, open(f"{out}_{os.path.splitext(b)[0]}.json", "w"), indent=1)
        print(b, len(lst), "Kanten im Bild,", sum(v["neu_gegen_alt"] for v in info.values()), "davon neu")


if __name__ == "__main__":
    main()
