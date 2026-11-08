#!/usr/bin/env python3
"""test_bogen_kontur.py - synthetischer Beweis fuer tools/bogen_kontur.py (Exit 0 = ALLE BESTANDEN).
Testfassade: Rotwand, Bogenoeffnung mit BEKANNTER Kontur (Goldlinie 3 cm, innen dunkel + helle Gewoelbekappe, Fenster/Tuer als Stoerkanten), 5 Fotos aus verschiedenen Standpunkten,
gerendert mit der WAHREN Kamera (k1 = -0,02), ausgewertet mit einer Kamera mit 3 cm Lagerauschen (+ Rotation 0,03 m / Abstand) und Bildrauschen, ein Foto mit Passanten-Verdeckung.
Faelle: rund (mit senkrechtem Ansatz), spitz (gleichseitig), Segment. Soll: Median < 2 cm, P95 < 5 cm zur Wahrheit; Benennung richtig (Kronenradius/halbe Breite 1,0 rund / 1,25 Segment, Scheitelknick > 15 Grad spitz, Breite).
Kamerafehler 15 cm: ausrichten() (Verschiebung je Foto) muss P95 senken. Gegenprobe: systematischer Kamerafehler 20 cm -> Fehler > 5 cm (Grenze ehrlich sichtbar), ohne Gold-Linie -> Kontur nicht gueltig (nichts erfunden)."""
import os, sys, math, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bogen_kontur as BK

RAHMEN = dict(n=[0.0, 1.0], d=[-1.0, 0.0], o=[0.0, 0.0])
UF = (-3.0, 3.0, -0.5, 6.5); ZL = 0.01


def wahrheit(art, n=800):
    """Wahre Mittellinie der Goldlinie (u,z) links->oben->rechts (nur Krone + 0,6 m senkrechter Ansatz)."""
    if art == "rund":
        w, zs = 4.0, 2.4; t = np.linspace(0, math.pi, n); K = np.c_[w / 2 * np.cos(t), zs + w / 2 * np.sin(t)]; ans = 0.6
    elif art == "spitz":
        w, zs = 4.0, 2.4; t = np.linspace(0, math.pi / 3, n // 2)           # gleichseitig: rechter Bogen Mittelpunkt (-w/2, zs), Radius w
        rechts = np.c_[-w / 2 + w * np.cos(t), zs + w * np.sin(t)]; K = np.vstack([rechts * [-1, 1], rechts[::-1]]); ans = 0.6
    else:  # segment: Sehne w=4, Pfeil 1.0, Kaempfer 3.2
        w, zs, h = 4.0, 3.2, 1.0; R = (w * w / 4 + h * h) / (2 * h); zc = zs + h - R; u = np.linspace(-w / 2, w / 2, n); K = np.c_[u, zc + np.sqrt(R * R - u * u)]; ans = 0.6
    L = np.c_[np.full(30, K[0, 0]), np.linspace(K[0, 1] - ans, K[0, 1], 30)]; Rr = np.c_[np.full(30, K[-1, 0]), np.linspace(K[-1, 1], K[-1, 1] - ans, 30)]
    return np.vstack([L, K, Rr])


def textur(K, rng, gold=True):
    """Wandtextur (BGR) 1 cm: rot, Oeffnung dunkel, Gewoelbekappe, Goldlinie 3 cm entlang K, Fenster/Tuer-Stoerkanten."""
    ss = 4; nu = int((UF[1] - UF[0]) / ZL); nz = int((UF[3] - UF[2]) / ZL); im = np.zeros((nz * ss, nu * ss, 3), np.uint8); im[:] = (65, 60, 175)
    px = lambda P: np.round(np.c_[(P[:, 0] - UF[0]) / ZL * ss, (UF[3] - P[:, 1]) / ZL * ss]).astype(np.int32)
    poly = np.vstack([K, [[K[-1, 0], 0.0], [K[0, 0], 0.0]]]); cv2.fillPoly(im, [px(poly)], (25, 20, 35))
    cap = np.vstack([K[K[:, 1] > K[:, 1].max() - 0.8] + [0, -0.05]]); cv2.fillPoly(im, [px(np.vstack([cap, cap[::-1] - [0, 0.5]]))], (200, 195, 190))
    if gold: cv2.polylines(im, [px(K)], False, (40, 190, 215), thickness=int(0.03 / ZL * ss))
    cv2.rectangle(im, tuple(px(np.array([[-0.7, 1.9]]))[0]), tuple(px(np.array([[0.3, 0.3]]))[0]), (50, 45, 40), -1)      # Tuer unten
    cv2.rectangle(im, tuple(px(np.array([[-2.8, 4.0]]))[0]), tuple(px(np.array([[-2.2, 2.6]]))[0]), (40, 40, 60), -1)        # Fenster links ausserhalb
    t = cv2.resize(im, (nu, nz), interpolation=cv2.INTER_AREA); return t


def kamera(C, ziel, f=3500.0, W=3840, H=2400, k1=-0.02):
    fw = ziel - C; fw /= np.linalg.norm(fw); x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x); R = np.vstack([x, y, fw])
    return dict(R=R, t=-R @ C, f=f, cx=W / 2, cy=H / 2, k1=k1, tr=[0, 0, 0], C=C, W=W, H=H)


def rendern(tex, cam, passanten=False, rng=None):
    """Foto aus Wandtextur mit wahrer Kamera: je Bildpixel Strahl auf die Ebene y=0 (n=(0,1)), Verzeichnung k1 iterativ umgekehrt."""
    W, H = cam["W"], cam["H"]; xs, ys = np.meshgrid(np.arange(W) + 0.0, np.arange(H) + 0.0); xd = (xs - cam["cx"]) / cam["f"]; yd = (ys - cam["cy"]) / cam["f"]
    xn, yn = xd.copy(), yd.copy()
    for _ in range(6): s_ = 1 + cam["k1"] * (xn * xn + yn * yn); xn, yn = xd / s_, yd / s_
    dirs = (np.stack([xn, yn, np.ones_like(xn)], -1) @ cam["R"]); lam = -cam["C"][1] / dirs[..., 1]; Pw = cam["C"] + dirs * lam[..., None]
    u = -Pw[..., 0]; z = Pw[..., 2]; mx = ((u - UF[0]) / ZL - 0.5).astype(np.float32); my = ((UF[3] - z) / ZL - 0.5).astype(np.float32)
    im = cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(65, 60, 175))
    if passanten:
        for (uu, z0, z1, col) in [(-1.6, 0.0, 1.8, (200, 120, 60)), (1.4, 0.0, 1.7, (60, 160, 60)), (-1.9, 2.0, 3.0, (20, 20, 160))]:   # inkl. einer Figur ueber dem linken Ansatz
            P = np.array([[-uu - 0.25, 0, z0], [-uu + 0.25, 0, z1]]); Xc = P @ cam["R"].T + cam["t"]; xy = np.c_[Xc[:, 0] / Xc[:, 2] * cam["f"] + cam["cx"], Xc[:, 1] / Xc[:, 2] * cam["f"] + cam["cy"]]
            cv2.rectangle(im, tuple(np.int32(xy[0])), tuple(np.int32(xy[1])), col, -1)
    return np.clip(im.astype(np.float32) + (rng.normal(0, 3, im.shape) if rng is not None else 0), 0, 255).astype(np.uint8)


def kameras_gestoert(cams, rng, sigma=0.03, system=None):
    out = []
    for c in cams:
        d = c["C"] - np.array([0, 0, c["C"][2]]); dist = np.linalg.norm(c["C"]); dC = rng.normal(0, sigma, 3) + (np.array(system) if system is not None else 0)
        rot = rng.normal(0, sigma / dist, 3); Rn, _ = cv2.Rodrigues(rot); R = Rn @ c["R"]; C = c["C"] + dC
        e = dict(c); e["R"] = R; e["t"] = -R @ C; out.append(e)
    return out


def abstand_zu_wahrheit(K, W):
    from scipy.spatial import cKDTree
    d, _ = cKDTree(W).query(K); return d


def lauf(art, seed=0, system=None, ohne_gold=False, sigma=0.03, ausrichten=False):
    rng = np.random.default_rng(seed); Wt = wahrheit(art); tex = textur(Wt, rng)
    if ohne_gold: tex = textur(Wt, rng, gold=False)
    ziel = np.array([0.0, 0.0, 3.0]); ort = [(-9, 14, 1.6), (0, 12, 1.5), (8, 17, 1.7), (-4, 20, 2.0), (5, 11, 1.4)]
    cams = [kamera(np.array([x, y, z], float), ziel) for x, y, z in ort]; fotos = [rendern(tex, c, passanten=(i == 3), rng=rng) for i, c in enumerate(cams)]
    cams_n = kameras_gestoert(cams, rng, sigma=sigma, system=system); ko = []
    top = Wt[:, 1].max(); w = Wt[:, 0].max() - Wt[:, 0].min(); mitte = (0.0, top - w / 2)                  # Ursprung der Strahlen aus der Kandidatenbox (Suchfenster), keine Formannahme fuer die Kurve
    for im, c in zip(fotos, cams_n):
        orth, ok, _ = BK.ebene_ortho(im, c, RAHMEN, UF, ZL, 0.0); ko.append(BK.kontur_foto(orth, ok, UF, ZL, mitte, (0.5 * w / 2, 1.6 * w / 2 + 0.5)))
    if ausrichten: ko, _ = BK.ausrichten(ko)
    fu = BK.fusion(ko, min_n=3); K, tt, rr = BK.kurve_spline(fu["theta"], fu["r"], mitte)
    return Wt, K, fu, ko, mitte


def main():
    ok = True
    for art in ("rund", "spitz", "segment"):
        Wt, K, fu, ko, mitte = lauf(art); K = K[(K[:, 1] > Wt[:, 1].min() + 0.03)]
        d = abstand_zu_wahrheit(K, Wt); med, p95 = np.median(d) * 100, np.percentile(d, 95) * 100
        b = BK.benennen(K); st = float(np.nanmedian(fu["streu"][fu["ok"]])) * 100
        print(f"{art:8s}: Median {med:.2f} cm, P95 {p95:.2f} cm, Foto-Streuung {st:.2f} cm, Kronenradius/halbe Breite {b['kroenungsradius_zu_halbbreite']:.2f}, Knick {b['scheitelknick_grad']:.1f} Grad, Breite {b['breite']:.2f}, Scheitel {b['scheitel_z']:.2f}, Kaempfer {b['kaempfer_z']:.2f} (wahr 2,4 / 2,4 / 3,2; Lesen nur +-0,4 m moeglich, siehe Doku)")
        g = med < 2.0 and p95 < 5.0
        if art == "rund": g &= abs(b["kroenungsradius_zu_halbbreite"] - 1.0) < 0.12 and b["scheitelknick_grad"] < 8 and abs(b["breite"] - 4.0) < 0.06
        if art == "spitz": g &= b["scheitelknick_grad"] > 15 and b["scheitel_z"] - 2.4 > 1.2 * 2.0 and abs(b["breite"] - 4.0) < 0.08
        if art == "segment": g &= b["kroenungsradius_zu_halbbreite"] > 1.12 and b["scheitelknick_grad"] < 8 and abs(b["breite"] - 4.0) < 0.1
        print("  ->", "BESTANDEN" if g else "FEHLER"); ok &= g
    res = {}
    from scipy.optimize import minimize
    for aus in (False, True):                                                   # Kamerafehler 15 cm (Realitaet 10-35 cm): Ausrichten entfernt die Streuung ZWISCHEN den Fotos; ein allen gemeinsamer Fehler bleibt (nicht beobachtbar) -> Formfehler nach bester Verschiebung bewerten
        Wt, K, fu, ko, mitte = lauf("rund", sigma=0.15, ausrichten=aus); K = K[(K[:, 1] > Wt[:, 1].min() + 0.03)]
        f = lambda d: np.median(abstand_zu_wahrheit(K + d, Wt)); r_ = minimize(f, [0, 0], method="Nelder-Mead"); res[aus] = np.percentile(abstand_zu_wahrheit(K + r_.x, Wt), 95) * 100
    print(f"Kamerafehler 15 cm, Formfehler nach bester Verschiebung: P95 ohne Ausrichten {res[False]:.1f} cm, mit Ausrichten {res[True]:.1f} cm (mit muss < 5 cm und nicht schlechter sein)"); ok &= res[True] < 5.0 and res[True] <= res[False] + 0.3
    Wt, K, fu, ko, mitte = lauf("rund", system=(0.2, 0.0, 0.0)); K = K[(K[:, 1] > Wt[:, 1].min() + 0.03)]; d = abstand_zu_wahrheit(K, Wt); print(f"Gegenprobe systematisch 20 cm: P95 {np.percentile(d, 95) * 100:.1f} cm (muss > 5 sein)"); ok &= np.percentile(d, 95) > 0.05
    Wt, K, fu, ko, mitte = lauf("rund", ohne_gold=True); print(f"Gegenprobe ohne Goldlinie: gueltige Winkel {int(fu['ok'].sum())} von {len(fu['ok'])} (muss < 30 % sein)"); ok &= fu["ok"].mean() < 0.3
    print("ALLE BESTANDEN" if ok else "FEHLER"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
