#!/usr/bin/env python3
"""epilinie.py - Epipolarlinie eines Pixelpicks in weiteren Kameras (Hilfe fuer foto_mass.py --tri).

Aufruf:
  epilinie.py OBJ.json K-A x y K-B [K-C ...] [--tiefe 2 60] [--fenster x0 y0 x1 y1] [--aus DIR] [--name N] [--ncc [Halbbreite_px]]
Der Strahl durch (x,y) in Kamera A wird auf Tiefen --tiefe (m, Standard 2..60) abgetastet und in jede Zielkamera
projiziert. Ausgabe je Ziel: DIR/epi_<name>_<K-B>.jpg mit der Linie, Tiefenmarken (m, Beschriftung alle 5 m, kleine Striche
je 1 m) und Gitter; mit --fenster nur dieser Bildausschnitt (Originalpixel, Gitter in Originalkoordinaten).
Der gesuchte Objektpunkt liegt IRGENDWO auf der Linie; wo die Kante die Linie schneidet, ist der Pick fuer foto_mass --tri.
Kameramodell wie foto_mass.py (SIMPLE_RADIAL: u = f*x*(1+k1*r^2)+cx, rvec/t Welt->Kamera). Reine Geometrie, keine GPU noetig.
Hinweis: Nur Schnitt Strahl x Bild; Verdeckung und Mehrdeutigkeit (Linie laeuft laengs der Kante) prueft der Mensch.
Umgebung: cv2 -> /media/oem/scan/venv-seg/bin/python -I tools/epilinie.py ... (oder `tools/py tools/epilinie.py ...`); Standard --aus = aktueller Ordner, --name pick.
Exit 0 = Bilder geschrieben; ohne genug Argumente Hilfe + Exit 1, ohne Zielkamera Abbruch mit Text.
"""
import sys, os, json, glob
import numpy as np, cv2


def kam(od, kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]
    R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float)
    return dict(R=R, t=t, c=-R.T @ t, f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0.0))


def strahl(K, uv):
    x, y = (uv[0] - K["cx"]) / K["f"], (uv[1] - K["cy"]) / K["f"]; xu, yu = x, y
    for _ in range(10):
        r2 = xu * xu + yu * yu; xu, yu = x / (1 + K["k1"] * r2), y / (1 + K["k1"] * r2)
    d = K["R"].T @ np.array([xu, yu, 1.0]); return K["c"], d / np.linalg.norm(d)


def projekt(K, P):
    q = K["R"] @ P + K["t"]
    if q[2] <= 1e-6: return None
    xn, yn = q[0] / q[2], q[1] / q[2]; r2 = xn * xn + yn * yn; s = 1 + K["k1"] * r2
    return K["f"] * xn * s + K["cx"], K["f"] * yn * s + K["cy"]


def kante(im):
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.2).astype(np.float32)
    return cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))


def flicke(E, p, a, n=41):
    """n x n Ausschnitt um p (Pixel), Schrittweite a Pixel je Ausgabepixel."""
    M = np.array([[a, 0, p[0] - (n // 2) * a], [0, a, p[1] - (n // 2) * a]], np.float32)
    return cv2.warpAffine(E, M, (n, n), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def ncc(u, v):
    u, v = u - u.mean(), v - v.mean(); d = np.sqrt((u * u).sum() * (v * v).sum())
    return float((u * v).sum() / d) if d > 1e-6 else 0.0


def tiefenscan(KA, EA, uv, c0, d0, ziele, tiefen, halb):
    """Je Tiefe NCC des Kantenausschnitts (Kamera A um uv, Halbbreite halb px) gegen Kanten in jedem Ziel. Massstab: Strahlabstand/Brennweite."""
    fa = flicke(EA, uv, 2.0 * halb / 40.0); res = []
    for t in tiefen:
        P = c0 + d0 * t; sc = []
        for K, E in ziele:
            p = projekt(K, P)
            if p is None or not (0 <= p[0] < E.shape[1] and 0 <= p[1] < E.shape[0]): sc.append(-1.0); continue
            dist = float(np.linalg.norm(P - K["c"])); s = (t / dist) * (K["f"] / KA["f"])
            sc.append(ncc(fa, flicke(E, p, 2.0 * halb / 40.0 / max(s, 1e-3))))
        res.append((float(t), sc))
    return res


def main():
    a = sys.argv[1:]
    if len(a) < 5 or a[0].startswith("-"): sys.exit(__doc__)
    obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    opt = lambda n, k, d: [float(v) for v in a[a.index(n) + 1:a.index(n) + 1 + k]] if n in a else d
    t0, t1 = opt("--tiefe", 2, [2.0, 60.0]); fw = opt("--fenster", 4, None)
    aus = a[a.index("--aus") + 1] if "--aus" in a else "."; name = a[a.index("--name") + 1] if "--name" in a else "pick"
    pos = []; i = 4; kidA = a[1]; uv = (float(a[2]), float(a[3]))
    while i < len(a) and a[i].startswith("K-"): pos.append(a[i]); i += 1
    if not pos: sys.exit("Zielkamera(s) fehlen")
    KA = kam(od, kidA); c0, d0 = strahl(KA, uv); tiefen = np.arange(t0, t1 + 1e-9, 0.25)
    os.makedirs(aus, exist_ok=True)
    if "--ncc" in a:                                                       # Glied 2 (Version 1): Tiefenscan statt Augenmass
        halb = float(a[a.index("--ncc") + 1]) if a.index("--ncc") + 1 < len(a) and not a[a.index("--ncc") + 1].startswith("-") else 60.0
        fa_ = glob.glob(os.path.join(root, obj["fotos_dir"], kidA[2:] + "_*")); EA = kante(cv2.imread(fa_[0])); ziele = []
        for kid in pos:
            fn = glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*")); ziele.append((kam(od, kid), kante(cv2.imread(fn[0]))))
        res = tiefenscan(KA, EA, uv, c0, d0, ziele, tiefen, halb); gem = [(t, float(np.mean(sc))) for t, sc in res]
        print("Tiefe m | NCC je Ziel (" + ", ".join(pos) + ") | Mittel; beste 8 nach Mittel:")
        for (t, sc), (_, m) in sorted(zip(res, gem), key=lambda x: -x[1][1])[:8]: print(f"{t:6.2f} | " + " ".join(f"{v:+.2f}" for v in sc) + f" | {m:+.2f}")
        return
    for kid in pos:
        K = kam(od, kid); fn = glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))
        if not fn: print(kid, "Foto nicht gefunden"); continue
        im = cv2.imread(fn[0]); H, W = im.shape[:2]
        pts = [(t, projekt(K, c0 + d0 * t)) for t in tiefen]; pts = [(t, p) for t, p in pts if p is not None]
        if not pts: print(kid, "Linie nicht im Bild (hinter der Kamera)"); continue
        x0, y0, x1, y1 = (int(v) for v in fw) if fw else (0, 0, W, H); st = 50 if fw and (x1 - x0) <= 800 else 200
        c = im[y0:y1, x0:x1].copy(); sk = 1.0 if fw else min(1.0, 1600 / max(c.shape[:2]))
        for x in range(x0 - x0 % st + st, x1, st):
            cv2.line(c, (x - x0, 0), (x - x0, c.shape[0]), (255, 255, 255), 1); cv2.putText(c, str(x), (x - x0 + 2, 18), 0, 0.55, (255, 255, 255), 2)
        for y in range(y0 - y0 % st + st, y1, st):
            cv2.line(c, (0, y - y0), (c.shape[1], y - y0), (255, 255, 255), 1); cv2.putText(c, str(y), (3, y - y0 - 3), 0, 0.55, (255, 255, 255), 2)
        pol = np.array([(p[0] - x0, p[1] - y0) for _, p in pts], np.int32)
        inn = [(t, p) for t, p in pts if x0 <= p[0] < x1 and y0 <= p[1] < y1]
        cv2.polylines(c, [pol], False, (0, 255, 255), 2)
        for t, p in inn:
            m = abs(t - round(t)) < 1e-6
            if m:
                q = (int(p[0] - x0), int(p[1] - y0)); cv2.circle(c, q, 5 if int(round(t)) % 5 else 9, (0, 0, 255), -1)
                if int(round(t)) % 5 == 0: cv2.putText(c, f"{int(round(t))}m", (q[0] + 8, q[1] - 6), 0, 0.8, (0, 0, 255), 2)
        if sk < 1: c = cv2.resize(c, None, fx=sk, fy=sk)
        out = os.path.join(aus, f"epi_{name}_{kid}.jpg"); cv2.imwrite(out, c, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"{kid}: {len(inn)} von {len(pts)} Tiefenstufen im Bild/Fenster -> {out}")


if __name__ == "__main__":
    main()
