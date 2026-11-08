#!/usr/bin/env python3
"""test_kanten_feld3d.py - S10 Teil B Bewertung (1): Synth-Szene mit BEKANNTEN 3D-Kanten (analytisch gerendert: Arkadenwand mit 4 Rundboegen, Gesims-Platte mit wanderndem Schatten,
rot/gold-Band gleicher Helligkeit, Ziegelfugen, Boden). 24 Ansichten, 6 Lichtlagen. Kantenkarten = echte Pipelines P1-P4 aus den gerenderten Bildern, weiches Mittel.

SCHWELLEN VOR DEM LAUF FESTGELEGT (nicht nachtunen):
  Praezision (Punkt <= 0,15 m von geometrischer GT-Kante ODER Texturfuge)  >= 0,80
  Vollstaendigkeit (GT-Probe <= 0,15 m von einem Feldpunkt)                  >= 0,70
  Schattenanteil (Punkt <= 0,10 m von Schattenlinie, nicht nahe GT)         <= 0,05
  Boegen: alle 4 Rundboegen als Kreisbogen gefunden (Mitte <= 0,20 m, Radius <= 0,30 m, Normale zur Wand < 15 Grad)
Gegenprobe: dieselbe Rechnung mit MIN_LICHT=1 (ohne Lichtgruppen) muss MEHR Schattenanteil zeigen, sonst waere Schattenfilter wirkungslos.
Aufruf: venv-seg/bin/python -I tools/test_kanten_feld3d.py AUSORDNER [--seed 0]
"""
import os, sys, json, argparse, time
import numpy as np, cv2, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import kanten_feld3d as KF, kanten_pipelines as KP

XC = (-6.0, -2.0, 2.0, 6.0); RB = 1.6; ZS = 2.4; XW = 10.0; ZW = 8.0; ZSL = 7.0; YSL = 1.2; YBACK = -3.0
W, H, F = 800, 600, 700.0


def trace(C, d, sonne):
    """Strahlen d (n,3) von C; Rueckgabe t (n,), Flaechenart (n,), Farbe (n,3 BGR 0..255), Hitpunkt."""
    n = len(d); t = np.full(n, np.inf); art = np.zeros(n, np.int8); P = np.zeros((n, 3))
    with np.errstate(divide="ignore", invalid="ignore"):
        tw = np.where(d[:, 1] < 0, -C[1] / d[:, 1], np.inf); Pw = C + tw[:, None] * d
        inw = (tw > 0) & (np.abs(Pw[:, 0]) <= XW) & (Pw[:, 2] >= 0) & (Pw[:, 2] <= ZW)
        loch = np.zeros(n, bool)
        for xc in XC: loch |= (np.abs(Pw[:, 0] - xc) <= RB) & ((Pw[:, 2] <= ZS) | ((Pw[:, 0] - xc) ** 2 + (Pw[:, 2] - ZS) ** 2 <= RB ** 2)) & (Pw[:, 2] >= 0)
        tb = np.where(d[:, 1] < 0, (YBACK - C[1]) / d[:, 1], np.inf); Pb = C + tb[:, None] * d; inb = (tb > 0) & (np.abs(Pb[:, 0]) <= XW) & (Pb[:, 2] >= 0) & (Pb[:, 2] <= ZW)
        tg = np.where(d[:, 2] < 0, -C[2] / d[:, 2], np.inf); Pg = C + tg[:, None] * d; ing = (tg > 0) & (np.abs(Pg[:, 0]) <= XW + 6) & (Pg[:, 1] >= 0) & (Pg[:, 1] <= 12)
        ts = np.where(d[:, 2] > 0, (ZSL - C[2]) / d[:, 2], np.inf); Ps = C + ts[:, None] * d; ins = (ts > 0) & (np.abs(Ps[:, 0]) <= XW) & (Ps[:, 1] >= 0) & (Ps[:, 1] <= YSL)
    for a, (tt, ok, pp) in enumerate([(tw, inw & ~loch, Pw), (tb, inb & loch, Pb), (tg, ing, Pg), (ts, ins, Ps)], 1):
        better = ok & (tt < t); t = np.where(better, tt, t); art = np.where(better, a, art); P = np.where(better[:, None], pp, P)
    # Wand-Treffer, aber Loch -> Hinterwand nur wenn naeher als nichts: (tw schon ausgeschlossen)
    return t, art, P


def schatten(P, sonne):
    """Punkt im Schatten der Platte? (Sonnenrichtung s zeigt zur Sonne)."""
    s = sonne; tau = (ZSL - P[:, 2]) / s[2]; Q = P + tau[:, None] * s
    return (tau > 0) & (np.abs(Q[:, 0]) <= XW) & (Q[:, 1] >= 0) & (Q[:, 1] <= YSL)


def farbe(art, P, sh, rng):
    n = len(art); c = np.zeros((n, 3))
    rot = np.array([40, 40, 150.0]); gold = np.array([0, 62, 118.0]); grau = np.array([95, 95, 100.0])
    c[art == 1] = rot; c[art == 2] = np.array([45, 45, 50.0]); c[art == 3] = np.array([120, 125, 120.0]); c[art == 4] = np.array([150, 150, 155.0]); c[art == 0] = np.array([210, 190, 170.0])
    band = (art == 1) & (P[:, 2] >= 5.0) & (P[:, 2] <= 5.8); c[band] = gold
    ziegel = (art == 1) & (P[:, 2] < 1.5) & ((np.mod(P[:, 2], 0.25) < 0.02) | (np.mod(P[:, 0] + 0.125 * (np.floor(P[:, 2] / 0.25) % 2), 0.5) < 0.02)); c[ziegel] *= 0.7
    c[(sh) & (art != 0)] *= 0.55
    return c


def render(C, Rm, sonne, rng):
    u, v = np.meshgrid(np.arange(W), np.arange(H)); dc = np.stack([(u - W / 2) / F, (v - H / 2) / F, np.ones_like(u, float)], -1).reshape(-1, 3); dc /= np.linalg.norm(dc, axis=1, keepdims=True)
    dw = dc @ Rm; t, art, P = trace(C, dw, sonne); sh = schatten(P, sonne) & np.isfinite(t)
    c = farbe(art, P, sh, rng).reshape(H, W, 3) + rng.normal(0, 3, (H, W, 3)); img = np.clip(c, 0, 255).astype(np.uint8); img = cv2.GaussianBlur(img, (0, 0), 0.8)
    zc = np.where(np.isfinite(t), t * dc[:, 2], 0).reshape(H, W).astype(np.float32); return img, zc


def kameras(n=24):
    cams = []
    for i in range(n):
        th = np.radians(np.linspace(-55, 55, n)[i]); Rd = 14 + 6 * ((i * 7) % 5) / 4; C = np.array([Rd * np.sin(th), Rd * np.cos(th), 1.7]); tgt = np.array([0, 0, 3.5])
        z = tgt - C; z /= np.linalg.norm(z); x = np.cross(z, np.array([0, 0, 1.0])); x /= np.linalg.norm(x); y = np.cross(z, x)
        Rm = np.stack([x, y, z]).T                                           # Spalten = Kameraachsen in Welt; Strahl_welt = dc @ Rm.T -> hier dc @ Rm genutzt mit Rm = (x;y;z) Zeilen
        Rm = np.stack([x, y, z])                                             # Zeilen
        cams.append((C, Rm))
    return cams


def gt_kanten(sonnen):
    """GT als Punktfolgen (2 cm): geometrisch, Textur, Schatten je Licht."""
    geo = []; s = 0.02
    def lin(a, b): a, b = np.array(a, float), np.array(b, float); n = max(2, int(np.linalg.norm(b - a) / s)); return a + (b - a) * np.linspace(0, 1, n)[:, None]
    for xc in XC:
        ph = np.linspace(0, np.pi, 400); geo.append(np.c_[xc + RB * np.cos(ph), np.zeros_like(ph), ZS + RB * np.sin(ph)])
        geo += [lin((xc - RB, 0, 0), (xc - RB, 0, ZS)), lin((xc + RB, 0, 0), (xc + RB, 0, ZS))]
    geo += [lin((-XW, 0, ZW), (XW, 0, ZW)), lin((-XW, 0, 0), (-XW, 0, ZW)), lin((XW, 0, 0), (XW, 0, ZW)), lin((-XW, 0, 5.0), (XW, 0, 5.0)), lin((-XW, 0, 5.8), (XW, 0, 5.8)),
            lin((-XW, YSL, ZSL), (XW, YSL, ZSL)), lin((-XW, 0, ZSL), (XW, 0, ZSL)), lin((-XW, 0, 0), (XW, 0, 0))]
    tex = []
    for z in np.arange(0.25, 1.5, 0.25): tex.append(lin((-XW, 0, z), (XW, 0, z)))
    for z in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25):
        for x in np.arange(-XW, XW, 0.5):
            xx = x + 0.125 * ((z / 0.25) % 2)
            if abs(xx) <= XW: tex.append(lin((xx, 0, z), (xx, 0, z + 0.25)))
    sch = []
    for s_ in sonnen:                                                       # Schattenkante der Plattenvorderkante auf der Wand: z = ZSL - YSL*sz/sy
        if s_[1] > 0.05: zz = ZSL - YSL * s_[2] / s_[1]; sch.append(lin((-XW, 0, zz), (XW, 0, zz)))
    return np.vstack(geo), np.vstack(tex), np.vstack(sch)


def bewerte(P, geo, tex, sch, tol=0.15):
    from scipy.spatial import cKDTree
    tg, tt, ts = cKDTree(geo), cKDTree(tex), cKDTree(sch) if len(sch) else None
    dg, dt = tg.query(P)[0], tt.query(P)[0]; dsch = ts.query(P)[0] if ts is not None else np.full(len(P), 9.0)
    prec = float(((dg <= tol) | (dt <= tol)).mean()) if len(P) else 0.0
    schatt = float(((dsch <= 0.10) & (dg > tol)).mean()) if len(P) else 0.0
    tp = cKDTree(P) if len(P) else None; gs = geo[::3]; rec = float((tp.query(gs)[0] <= tol).mean()) if tp is not None else 0.0
    return dict(praezision=round(prec, 3), vollstaendigkeit=round(rec, 3), schattenanteil=round(schatt, 3), n_punkte=int(len(P)))


def boegen_pruefen(bg):
    ok = []
    for xc in XC:
        best = None
        for b in bg:
            m = np.array(b["mitte"]); n = np.array(b["normale"])
            if abs(n[1]) > np.cos(np.radians(15)) and np.hypot(m[0] - xc, m[2] - ZS) <= 0.20 and abs(m[1]) <= 0.2 and abs(b["radius_m"] - RB) <= 0.30: best = b
        ok.append(best is not None)
    return ok


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("aus"); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--voxel", type=float, default=0.1); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
    rng = np.random.default_rng(a.seed); t0 = time.time(); cams = kameras(); ns = 6
    sonnen = []
    for g in range(ns):
        el = np.radians(25 + 8 * g); az = np.radians(-50 + 20 * g); sonnen.append(np.array([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)]))
    camlist, K1, K2, K3, K4, tiefen, imgs = [], [], [], [], [], [], []
    for i, (C, Rm) in enumerate(cams):
        img, zc = render(C, Rm, sonnen[i % ns], rng); imgs.append(img); Km = np.array([[F, 0, W / 2], [0, F, H / 2], [0, 0, 1.0]]); Rcw = Rm; t = -Rcw @ C
        camlist.append((Km, Rcw, t, C, W, H)); k1 = KP.karte_p1(img); k2 = KP.karte_p2(img); K1.append(k1); K2.append(k2); K3.append(KP.karte_p3(img)); K4.append(KP.karte_p4(img)); tiefen.append(torch.tensor(cv2.erode(zc, np.ones((3, 3))) if False else zc, device=KF.DEV))
        if i == 0: cv2.imwrite(os.path.join(a.aus, "synth_foto0.jpg"), img)
    print(f"gerendert {time.time()-t0:.0f}s", flush=True)
    # Kandidaten: Oberflaechenproben (Wand, Hinterwand, Boden, Platte) -> Voxel + Schale
    pts = []
    for x in np.arange(-XW, XW, 0.025):
        for z in np.arange(0, ZW, 0.025): pts.append((x, 0, z))
    pts = np.array(pts); vox = a.voxel; vk = np.unique(np.round(pts / vox).astype(np.int64), axis=0); off = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)])
    cand = (np.unique((vk[:, None, :] + off[None]).reshape(-1, 3), axis=0) * vox).astype(np.float32)
    gr = np.array([i % ns for i in range(len(cams))]); geo, tex, sch = gt_kanten(sonnen); erg = {}
    def mk(maps):
        out = []
        for m in maps: mt = torch.tensor(m.astype(np.float32) * 255.0, device=KF.DEV)[None, None]; out.append(mt[0, 0].round().clamp(0, 255).to(torch.uint8))
        return out
    tiefen_ = []
    for zc in tiefen:
        D = zc.clone(); D[D <= 0] = float("inf"); Dm = -torch.nn.functional.max_pool2d(-D[None, None], 3, 1, 1)[0, 0]; tiefen_.append(torch.where(torch.isinf(Dm), torch.zeros_like(Dm), Dm))
    varianten = {"mittel P1-P4": [(a_.astype(np.float32) + b_ + c_ + d_) / 4 for a_, b_, c_, d_ in zip(K1, K2, K3, K4)], "nur P1 hell": K1, "nur P2 farbe": K2, "nur P3 gelernt": K3, "nur P4 segment": K4}
    for name, maps in varianten.items():
        o = KF.feld(camlist, mk(maps), tiefen_, cand, gr, ns, vox, log=lambda *_: None)
        for var, kw in (("k3+Licht3", {}), ("ohne Licht (MIN_LICHT=1)", dict(min_licht=1)), ("k2", dict(min_fotos=2, min_licht=2))):
            ok = KF.auswahl(o, **kw); keep = KF.nms3d(cand, o["mean"], vox, ok); P = cand[keep]; r = bewerte(P, geo, tex, sch)
            if name == "mittel P1-P4" and var == "k3+Licht3":
                np.savez_compressed(os.path.join(a.aus, "synth_voxel.npz"), cand=cand, **o)
                gl, rest = KF.geraden(P); bg, _ = KF.boegen(P[rest]); r["geraden"] = len(gl); r["boegen"] = len(bg); r["boegen_gefunden"] = boegen_pruefen(bg)
                np.savez_compressed(os.path.join(a.aus, "synth_punkte.npz"), P=P, geo=geo[::5])
            erg[f"{name} | {var}"] = r; print(name, var, r, flush=True)
    s = erg["mittel P1-P4 | k3+Licht3"]; g = erg["mittel P1-P4 | ohne Licht (MIN_LICHT=1)"]
    urteil = dict(praezision=s["praezision"] >= 0.80, vollstaendigkeit=s["vollstaendigkeit"] >= 0.70, schatten=s["schattenanteil"] <= 0.05, boegen=all(s["boegen_gefunden"]), gegenprobe_schatten_mehr_ohne_licht=g["schattenanteil"] > s["schattenanteil"])
    erg["urteil"] = urteil; json.dump(erg, open(os.path.join(a.aus, "synth_ergebnis.json"), "w"), indent=1); print(urteil, f"{time.time()-t0:.0f}s")


if __name__ == "__main__": main()
