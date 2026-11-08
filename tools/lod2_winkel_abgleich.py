#!/usr/bin/env python3
"""lod2_winkel_abgleich.py <objekt> --wolke w.npy [--synth] [--k 24] [--aus out.json]
Winkelabgleich Wolke <-> LoD2 OHNE Georeferenz (Nutzer 8.11.: LoD2 nur fuer Richtung/Winkel, nicht fuer Hoehen).
Nur relative Groessen: (1) Wand-Gierwinkel-Verteilung (flaechengewichtet) beider Quellen, EIN Freiheitsgrad = Gierversatz (Kreuzkorrelation, 0,25 Grad),
(2) Dachneigungen (Winkel der Dachnormalen zur Lotrechten) als Peaks. Wolke muss lotrecht stehen (z = oben; rahmen_lot_foto.py).
Ausgabe: Gierversatz, Restwinkel je LoD2-Wandrichtung (naechster Wolkenpeak), Dachneigungen Wolke vs LoD2, Pruefung |Rest| < 3 Grad.
Blindheit: LoD2 kennt keine Erker/Bogen/Gauben -> nur Hauptflaechen; Wolke sieht nur sichtbare Seiten (Gierverteilung einseitig) -> Korrelation nur ueber vorhandene Peaks.
GPU: Normalen per PyTorch3D knn_points (Nutzerregel). --synth: Beweistest (bekannt gedrehte Normalen + Rauschen muessen den Versatz wiederfinden)."""
import sys, os, json, argparse
sys.path.insert(0, "/media/oem/scan/p3d_site"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--wolke"); ap.add_argument("--synth", action="store_true"); ap.add_argument("--k", type=int, default=24)
ap.add_argument("--aus"); ap.add_argument("--n", type=int, default=400000); ap.add_argument("--tol", type=float, default=3.0); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = 720  # 0,5 Grad je Klasse (Yaw 0..360)

def hist_yaw(yaw_deg, w):
    h, _ = np.histogram(np.mod(yaw_deg, 360), bins=NB, range=(0, 360), weights=w); return h

def glatt(h, s=3):
    x = np.arange(-4 * s, 4 * s + 1); g = np.exp(-0.5 * (x / s) ** 2); g /= g.sum()
    return np.real(np.fft.ifft(np.fft.fft(h) * np.fft.fft(np.roll(np.pad(g, (0, NB - len(g))), -4 * s))))

def versatz(hA, hB):
    """Gierversatz d (Grad), so dass B um d gedreht auf A passt (Kreuzkorrelation ueber FFT), plus Guete (normiert)."""
    c = np.real(np.fft.ifft(np.fft.fft(glatt(hA)) * np.conj(np.fft.fft(glatt(hB))))); i = int(np.argmax(c)); d = i * 360 / NB
    if d > 180: d -= 360
    return d, float(c[i] / (np.linalg.norm(glatt(hA)) * np.linalg.norm(glatt(hB)) + 1e-12))

def peaks(h, n=6, mind=10):
    hs = glatt(h); out = []; hh = hs.copy()
    for _ in range(n):
        i = int(np.argmax(hh))
        if hh[i] <= 0.08 * hs.max(): break
        out.append(i * 360 / NB)
        for j in range(-int(mind * 2), int(mind * 2) + 1): hh[(i + j) % NB] = 0
    return out

def normalen_wolke(P, k):
    import torch
    from pytorch3d.ops import knn_points
    X = torch.as_tensor(np.asarray(P, np.float32), device="cuda")[None]; out = []
    for i in range(0, X.shape[1], 200000):
        q = X[:, i:i + 200000]; idx = knn_points(q, X, K=k).idx[0]; nb = X[0][idx]; nb = nb - nb.mean(1, keepdim=True)
        C = (nb.transpose(1, 2) @ nb).cpu().numpy().astype(np.float64); w, v = np.linalg.eigh(C); out.append(v[:, :, 0])   # kleinster Eigenwert = Normale (3x3 auf CPU: cusolver-Batch braucht >50 GB)
    N = np.vstack(out); N[N[:, 2] < 0] *= -1; return N

def lod2_normalen():
    import lod2_gebaeude as LG
    OBJ = json.load(open(os.path.join(ROOT, "modelle", a.objekt, "objekt.json"))); C0 = json.load(open(os.path.join(ROOT, "modelle", a.objekt, "anker3d.json")))["mitte_utm"]
    picked = LG.extract(OBJ["lod2"]["gml"], center=tuple(C0), radius=60.0); meta, polys = [(m, p) for m, p in picked if m.get("id") == OBJ["lod2"]["id"]][0]
    res = []
    for t, P in polys:
        P = np.asarray(P, float); n = np.zeros(3)
        for i in range(len(P)): n += np.cross(P[i], P[(i + 1) % len(P)])
        A = np.linalg.norm(n) / 2
        if A < 1e-6: continue
        n /= np.linalg.norm(n) * 1.0
        if n[2] < 0: n = -n
        res.append((t, n, A))
    return res

def auswerten(Nw, L):
    """Nw (n,3) Wolkennormalen (z oben), L Liste (typ, n, Flaeche) LoD2. Rueckgabe dict."""
    ang_w = np.degrees(np.arccos(np.clip(Nw[:, 2], -1, 1)))                                     # Winkel zur Lotrechten
    wand_w = ang_w > 75; hw = hist_yaw(np.degrees(np.arctan2(Nw[wand_w, 1], Nw[wand_w, 0])), None)
    wl = [(n, A) for t, n, A in L if t == "WallSurface" and abs(n[2]) < 0.2]
    hl = hist_yaw(np.degrees([np.arctan2(n[1], n[0]) for n, A in wl]), [A for n, A in wl])
    # LoD2-Wandrichtungen liegen beidseitig (nur Aussenflaechen) -> beide Wolken-Seiten moeglich; Versatz ueber Halbebene mod 180 NICHT erlaubt (sonst Mehrdeutigkeit), voll 360
    d, g = versatz(hw, hl)       # LoD2 um d drehen -> Wolke
    pw = peaks(hw); res = []
    for n, A in sorted(wl, key=lambda x: -x[1])[:8]:
        y = (np.degrees(np.arctan2(n[1], n[0])) + d) % 360; r = min(((y - p + 180) % 360 - 180 for p in pw), key=abs) if pw else None; res.append({"flaeche_m2": round(A, 1), "yaw_nach_versatz": round(y, 2), "rest_grad": None if r is None else round(r, 2)})
    dach_l = sorted({round(float(np.degrees(np.arccos(abs(n[2])))), 1) for t, n, A in L if t == "RoofSurface" and A > 8 and 5 < np.degrees(np.arccos(abs(n[2]))) < 80})
    dm = (Nw[:, 2] > 0.2) & (Nw[:, 2] < 0.96); hd, e = np.histogram(ang_w[dm], bins=90, range=(0, 90)); dach_w = [round(float(e[i] + 0.5), 1) for i in np.argsort(hd)[::-1][:3] if hd[i] > 0.04 * hd.max()]
    return {"gier_versatz_grad": round(float(d), 2), "korrelation": round(g, 3), "wand_rest": res, "dachneigung_lod2_grad": dach_l, "dachneigung_wolke_peaks_grad": dach_w, "wolke_wandpeaks_yaw": [round(p, 1) for p in pw]}

if a.synth:   # Beweistest: LoD2-artige Normalen (4 Wandrichtungen 0/90/180/270 + Erker 45), um d gedreht + Rauschen 1,5 Grad; Dach 38 Grad
    rng = np.random.default_rng(1); ok = True
    for d_true in (-37.3, 12.5, 118.0):
        yaw = np.array([0] * 4000 + [90] * 2500 + [180] * 2000 + [45] * 500, float); yaw = yaw + d_true + rng.normal(0, 1.5, len(yaw))
        Nw = np.stack([np.cos(np.radians(yaw)), np.sin(np.radians(yaw)), rng.normal(0, 0.02, len(yaw))], 1); Nw /= np.linalg.norm(Nw, axis=1, keepdims=True)
        ey = np.radians(np.array([0, 90, 180, 45])); A = [200, 120, 100, 30]; L = [("WallSurface", np.array([np.cos(y), np.sin(y), 0.0]), Ai) for y, Ai in zip(ey, A)]
        r = auswerten(Nw, L); fehl = abs(((r["gier_versatz_grad"] - d_true + 180) % 360) - 180); print("d_true %7.1f gefunden %7.2f Fehler %.2f Grad Korr %.2f" % (d_true, r["gier_versatz_grad"], fehl, r["korrelation"])); ok &= fehl < 1.0
    print("SYNTH", "BESTANDEN" if ok else "DURCHGEFALLEN"); sys.exit(0 if ok else 2)

P = np.load(a.wolke)[:, :3]; P = P[np.random.default_rng(0).choice(len(P), min(a.n, len(P)), replace=False)]
Nw = normalen_wolke(P, a.k); L = lod2_normalen(); r = auswerten(Nw, L); r["objekt"] = a.objekt; r["wolke"] = os.path.basename(a.wolke); r["tol_grad"] = a.tol
for w in r["wand_rest"]: w["ok"] = bool(w["rest_grad"] is not None and abs(w["rest_grad"]) < a.tol)
print(json.dumps(r, ensure_ascii=False, indent=1))
if a.aus: json.dump(r, open(a.aus, "w"), ensure_ascii=False, indent=1)
