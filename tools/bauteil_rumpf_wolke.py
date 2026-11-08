#!/usr/bin/env python3
"""bauteil_rumpf_wolke.py - Rumpf + Dach AUS DER DICHTEN PUNKTWOLKE (Spec S3b, Nutzerregel 6.11.: Wolke = erste Wahrheit).

Allgemein (kein Objektwissen): alles aus Daten (Wolkendateien, optional Ersatzquelle) und objekt.json-Parametern (cfg).
Ablauf (reine numpy/scipy-Funktionen, Koerperbau mit manifold3d getrennt in `koerper`):
  1. kern_waehlen      Wolke -> Gebaeudekern (Dichte-Voxel, groesste Zusammenhangskomponente), Boden = 1.-Perzentil z
  2. winkel_schaetzen  Wandrichtung aus Konzentration der Wandband-Punkte auf Parallelen (Hough/RANSAC-Prinzip)
  3. waende_schaetzen  je Seite (u0,u1,v0,v1) Wandebene = Dichtemaximum im Aussenstreifen; LUECKE = Zellabdeckung (Wand x Hoehe) < min_abdeckung
                       Luecke -> Ersatzquelle (nur dort, nur geprueft) -> sonst Spiegelung (Traufseite) / Wolkenhuelle (Giebelseite), immer mit Vermerk
  4. dach_schaetzen    Dachebenen per RANSAC (Neigung, First, Traufe), Gegenseite nur aus Wolke wenn belegt, sonst gespiegelt (ANNAHME)
  5. koerper           Prisma aus Grundriss, oben von den Dachebenen beschnitten (wasserdicht)
Freie Parameter (cfg, vom BAUTEIL_PARAM der Optimierschleife ueberschreibbar; Startwert immer der Wolkenwert):
  versatz: first_z_m, first_pos_m, neigung_grad, wand_u0/u1/v0/v1_m (outward +), winkel_grad   (additiv auf den Wolkenwert)
  fest:    absolute Handwerte gleicher Namen (first_z, first_pos, neigung_grad, wand_u0.., boden_z, winkel_grad) - schlagen versatz, Schleife darf nicht anfassen
  aktiv:   false schaltet das Bauteil ab (baukasten_gen)
"""
import os, sys, json, glob, math
import numpy as np
from scipy import ndimage as ndi

STD = dict(vox=0.5, min_pkt=15, wand_von=0.20, wand_bis=0.50, aussen_anteil=0.35, min_abdeckung=0.20, min_inl=1500, ransac_iter=4000,
           dach_tol=0.15, dach_min_grad=15.0, dach_max_grad=62.0, ersatz_tol=0.3, ersatz_ueber=0.005, gegen_anteil=0.15, seed=1)

# ------------------------------------------------------------------ Daten
def wolke_laden(spec, basis="."):
    """spec: Pfad/Glob oder Liste davon (.npy (N,3) im Modellrahmen) -> (N,3) float64."""
    spec = [spec] if isinstance(spec, str) else list(spec); L = []
    for s in spec:
        s = s if os.path.isabs(s) else os.path.join(basis, s)
        fs = sorted(glob.glob(s)) or ([s] if os.path.exists(s) else [])
        if not fs: raise FileNotFoundError(s)
        for f in fs: L.append(np.load(f)[:, :3])
    return np.vstack(L).astype(float)

def boden_schaetzen(P, anteil=1e-4, dz=0.1):
    """Boden = tiefste z-Lage (dz-Raster), die >= anteil der Punkte traegt (Ausreisser darunter zaehlen nicht)."""
    h, e = np.histogram(P[:, 2], bins=np.arange(P[:, 2].min(), P[:, 2].max() + dz, dz)); k = int(np.argmax(h >= anteil * len(P))); return float(e[k])

def normalen_horizontal(Q, k=16):
    """|Normale| je Punkt (PCA der k Nachbarn), nur Betrag der Komponenten: (N,3). Fuer Wandpunkte: Horizontalrichtung der Flaeche."""
    from scipy.spatial import cKDTree
    tr = cKDTree(Q); _, nb = tr.query(Q, k=k); X = Q[nb] - Q[nb].mean(1, keepdims=True); C = np.einsum("nki,nkj->nij", X, X)
    w, V = np.linalg.eigh(C); return np.abs(V[:, :, 0])

def kern_waehlen(P, p, kasten=None, boden_z=None):
    """Gebaeudekern: Voxel (p.vox) mit >= p.min_pkt Punkten, groesste 3D-Zusammenhangskomponente. kasten=[x0,x1,y0,y1] nur Vorfilter (Handvorgabe)."""
    z0 = float(boden_z) if boden_z is not None else boden_schaetzen(P)
    if kasten is not None:
        x0, x1, y0, y1 = kasten; P = P[(P[:, 0] >= x0) & (P[:, 0] <= x1) & (P[:, 1] >= y0) & (P[:, 1] <= y1)]
    Q = P[P[:, 2] > z0 + 0.3]; lo = Q.min(0); idx = np.floor((Q - lo) / p["vox"]).astype(int)
    shp = idx.max(0) + 1; cnt = np.zeros(shp, int); np.add.at(cnt, tuple(idx.T), 1)
    lab, n = ndi.label(cnt >= p["min_pkt"], structure=np.ones((3, 3, 3)))
    if n == 0: raise ValueError("kein dichter Kern in der Wolke")
    gr = np.bincount(lab.ravel(), weights=cnt.ravel())[1:]; k = 1 + int(np.argmax(gr))
    return Q[lab[tuple(idx.T)] == k], z0

def drehen(P, th):
    """Modell (x,y) -> (a,b): a entlang der Wand (u), b senkrecht (v); th in Radiant."""
    c, s = math.cos(th), math.sin(th); return np.c_[P[:, 0] * c + P[:, 1] * s, -P[:, 0] * s + P[:, 1] * c, P[:, 2]]

def zurueck(a, b, th):
    c, s = math.cos(th), math.sin(th); return np.array([a * c - b * s, a * s + b * c])

def winkel_schaetzen(Pw, bin_m=0.05):
    """Wandrichtung th (Grad, [-45,45)): Parallelen-Konzentration sum(Zaehler^2) der Wandband-Punkte; grob 1 Grad, fein 0,1 Grad."""
    rng = np.random.default_rng(1); Q = Pw[rng.choice(len(Pw), min(len(Pw), 150000), replace=False)]
    def score(deg):
        t = math.radians(deg); v = -Q[:, 0] * math.sin(t) + Q[:, 1] * math.cos(t)
        h, _ = np.histogram(v, bins=np.arange(v.min(), v.max() + bin_m, bin_m)); return float((h.astype(float) ** 2).sum())
    g = max(np.arange(-45, 45, 1.0), key=score); f = max(np.arange(g - 1, g + 1.001, 0.1), key=score); return float(f)

# ------------------------------------------------------------------ Waende
def wand_suchen(c, o, z, sg, c_rng, o_rng, z_rng, p, nc):
    """Eine Aussenwand senkrecht zur Koordinate c (sg=+1: max, -1: min). Rueckgabe dict(c, abdeckung, n, gueltig). Koordinate c*sg ist 'nach aussen'."""
    ok = nc > 0.85; c, o, z = c[ok], o[ok], z[ok]                    # nur Punkte, deren Flaechennormale entlang der Wandnormalen liegt (sonst zaehlt Fassade fuer Giebelebene)
    if len(c) < 50: return dict(c=0.0, abdeckung=0.0, n=0, gueltig=False)
    cc = c * sg; lo, hi = sorted((c_rng[0] * sg, c_rng[1] * sg)); zone = cc >= hi - p["aussen_anteil"] * (hi - lo)
    if zone.sum() < 50: return dict(c=0.0, abdeckung=0.0, n=0, gueltig=False)
    e = np.arange(float(cc[zone].min()), float(cc[zone].max()) + 0.1, 0.05); h, _ = np.histogram(cc[zone], bins=e)
    hs = np.convolve(h, np.ones(5), "same"); k = int(np.argmax(hs)); cw = float(cc[(cc > e[k] - 0.15) & (cc < e[k] + 0.2)].mean())
    inl = np.abs(cc - cw) < 0.25; ob = np.arange(o_rng[0], o_rng[1] + 0.5, 0.5); zb = np.arange(z_rng[0], z_rng[1] + 0.5, 0.5)
    H, _, _ = np.histogram2d(o[inl], z[inl], bins=[ob, zb]); ab = float((H >= 3).mean()) if H.size else 0.0
    return dict(c=cw * sg, abdeckung=ab, n=int(inl.sum()), gueltig=bool(ab >= p["min_abdeckung"] and inl.sum() >= p["min_inl"]))

def ersatz_wand(kanten, th, achse, sg, c_innen, p, c_belegt):
    """Ersatzquelle (Segmente [[x,y],[x,y]] im Modellrahmen) fuer eine LUECKEN-Wand. Kandidat = laengste zur Wandrichtung parallele (+-8 Grad) Kante, die
    ausserhalb des belegten Wolkenbereichs liegt (c*sg >= c_innen). Pruefung: Wolkenpunkte duerfen NICHT jenseits der Ebene liegen (Widerspruch)."""
    best = None; t = th if achse == "v" else th + math.pi / 2          # Richtung der Wand: achse 'v' -> Wand entlang u (Winkel th); 'u' -> entlang v
    for A, B in kanten:
        d = np.array(B, float) - np.array(A, float); L = float(np.linalg.norm(d))
        if L < 3.0: continue
        ang = abs((math.atan2(d[1], d[0]) - t + math.pi / 2) % math.pi - math.pi / 2)
        if ang > math.radians(8): continue
        m = (np.array(A, float) + np.array(B, float)) / 2; mc = (-m[0] * math.sin(th) + m[1] * math.cos(th)) if achse == "v" else (m[0] * math.cos(th) + m[1] * math.sin(th))
        if mc * sg < c_innen: continue
        if best is None or L > best[0]: best = (L, mc)
    if best is None: return None
    cw = best[1]; frac = float((c_belegt * sg > cw * sg + p["ersatz_tol"]).mean())
    return dict(c=cw, laenge=best[0], widerspruch_anteil=frac, geprueft_ok=bool(frac <= p["ersatz_ueber"]))

# ------------------------------------------------------------------ Dach
def _fit_plane(X):
    c = X.mean(0); _, _, Vt = np.linalg.svd(X - c, full_matrices=False); n = Vt[2]; n = n if n[2] > 0 else -n; return c, n

def ransac_dach(Q, p, ausser=None, richtung=None):
    """Dachebene (Neigung p.dach_min..max_grad) mit den meisten Inliern; ausser=(c,n) Vorgaenger (Gegenseite verlangt: Horizontalnormale entgegengesetzt)."""
    rng = np.random.default_rng(p["seed"]); S = Q[rng.choice(len(Q), min(len(Q), 30000), replace=False)]
    nz = np.abs(normalen_horizontal(S, 12)[:, 2]); lo_z = math.cos(math.radians(p["dach_max_grad"] + 8)); hi_z = math.cos(math.radians(max(p["dach_min_grad"] - 8, 0)))
    S = S[(nz > lo_z) & (nz < hi_z)]                                      # Kandidatenpunkte nur auf geneigten Flaechen (Wand/Fassade ausgeschlossen, sonst Ebene Wandstreifen-First)
    if len(S) < 100: return None
    i = rng.integers(0, len(S), (p["ransac_iter"], 3)); A, B, C_ = S[i[:, 0]], S[i[:, 1]], S[i[:, 2]]
    n = np.cross(B - A, C_ - A); nl = np.linalg.norm(n, axis=1); ok = nl > 1e-6; n[ok] /= nl[ok, None]; n[~ok] = (0, 0, 1); n[n[:, 2] < 0] *= -1
    tilt = np.degrees(np.arccos(np.clip(n[:, 2], -1, 1))); ok &= (tilt >= p["dach_min_grad"]) & (tilt <= p["dach_max_grad"])
    if richtung is not None:
        hz = n[:, :2] / np.maximum(np.linalg.norm(n[:, :2], axis=1, keepdims=True), 1e-9); ok &= (hz @ richtung < -0.8)
    idx = np.where(ok)[0]
    if not len(idx): return None
    cnt = np.zeros(len(idx), int)
    for q in range(0, len(idx), 250):                                    # Inlierzahl je Kandidat (Blockweise: 40k x 250 Abstaende)
        ii = idx[q:q + 250]; D = np.abs((S[:, None, :] - A[ii][None]) * n[ii][None]).sum(2); cnt[q:q + 250] = (D < p["dach_tol"]).sum(0)
    best = None
    for k in idx[np.argsort(-cnt)[:40]]:                                 # beste Kandidaten: Neuanpassung (strenge Toleranz) + Neigungspruefung (Fassade driftet sonst auf 88 Grad)
        c, n_ = A[k], n[k]; gut = True
        for _ in range(4):
            X = Q[np.abs((Q - c) @ n_) < p["dach_tol"]]
            if len(X) < 200: gut = False; break
            c, n_ = _fit_plane(X)
        tl = math.degrees(math.acos(min(1.0, n_[2])))
        if not (gut and p["dach_min_grad"] <= tl <= p["dach_max_grad"]): continue
        if richtung is not None and not (float(n_[:2] / max(np.linalg.norm(n_[:2]), 1e-9) @ richtung) < -0.8): continue
        inl = np.abs((Q - c) @ n_) < p["dach_tol"]; Xi = Q[inl]
        cell = np.floor(Xi[:, :2] / 0.5).astype(int); u_, cn = np.unique(cell, axis=0, return_counts=True); flaeche = int((cn >= 3).sum()) * 0.25   # FLAECHE (besetzte 0,5-m-Zellen), nicht Punktzahl: ein Wandstreifen/Sims ist eine Linie und gewinnt sonst
        if best is None or flaeche > best["flaeche_m2"]: best = dict(c=c, n=n_, n_inl=int(inl.sum()), inl=inl, tilt=tl, flaeche_m2=flaeche)
    return best

# ------------------------------------------------------------------ Schaetzung (alles zusammen)
def schaetzen(P, cfg=None, ersatz=None, log=print):
    """Wolke P (N,3 Modellrahmen) -> Parameter-Dict `par` mit Herkunft je Wert. ersatz = Segmente [[[x,y],[x,y]],..] (z. B. LoD2-Grundriss) oder None."""
    cfg = cfg or {}; p = {**STD, **{k: v for k, v in cfg.items() if k in STD}}; fest = cfg.get("fest") or {}; vers = cfg.get("versatz") or {}
    K, z0 = kern_waehlen(P, p, cfg.get("kasten"), fest.get("boden_z")); Hh = float(np.percentile(K[:, 2], 99.5) - z0)
    log(f"  Kern {len(K)} von {len(P)} Punkten, Boden z={z0:.2f}, Hoehe {Hh:.1f} m")
    band = K[(K[:, 2] > z0 + p["wand_von"] * Hh) & (K[:, 2] < z0 + p["wand_bis"] * Hh)]
    th_d = float(fest["winkel_grad"]) if "winkel_grad" in fest else winkel_schaetzen(band); th_d += float(vers.get("winkel_grad", 0.0)); th = math.radians(th_d)
    rng = np.random.default_rng(p["seed"]); bs = band[rng.choice(len(band), min(len(band), 200000), replace=False)]
    Nn = normalen_horizontal(bs); eu = np.array([math.cos(th), math.sin(th), 0.0]); ev = np.array([-math.sin(th), math.cos(th), 0.0])
    nu, nv = np.abs(Nn @ eu), np.abs(Nn @ ev); Rb = drehen(bs, th); a, b, z = Rb[:, 0], Rb[:, 1], Rb[:, 2]
    R = drehen(K, th); a_rng = tuple(np.percentile(R[:, 0], [1, 99])); b_rng = tuple(np.percentile(R[:, 1], [1, 99]))   # Laengenbereich je Achse aus dem GANZEN Kern (nicht nur dem Wandband)
    z_rng = (z0 + p["wand_von"] * Hh, z0 + p["wand_bis"] * Hh); seiten = {"u1": ("u", +1), "u0": ("u", -1), "v1": ("v", +1), "v0": ("v", -1)}; W = {}
    for nm, (ax, sg) in seiten.items():
        W[nm] = wand_suchen(a if ax == "u" else b, b if ax == "u" else a, z, sg, a_rng if ax == "u" else b_rng, b_rng if ax == "u" else a_rng, z_rng, p, nu if ax == "u" else nv)
        log(f"  Wand {nm}: c={W[nm]['c']:.2f} Abdeckung {W[nm]['abdeckung']:.2f} Inlier {W[nm]['n']} -> {'WOLKE' if W[nm]['gueltig'] else 'LUECKE'}")
    # --- Dach: Wolke oberhalb 0.3 H ohne die gueltigen Wandebenen ---
    hoch = R[R[:, 2] > z0 + 0.3 * Hh]
    for nm, (ax, sg) in seiten.items():
        if W[nm]["gueltig"]: hoch = hoch[hoch[:, 0 if ax == "u" else 1] * sg < W[nm]["c"] * sg - 0.4]   # Punkte an/ausserhalb gueltiger Wandebenen (Sims, Wand, Vorbauten) sind kein Dach
    d1 = ransac_dach(hoch, p)
    if d1 is None: raise ValueError("keine Dachebene gefunden")
    n1 = d1["n"]; ax_dach = "v" if abs(n1[1]) >= abs(n1[0]) else "u"; ia = 1 if ax_dach == "v" else 0      # Neigungsachse w
    ang_abw = math.degrees(math.atan2(abs(n1[1 - ia]), abs(n1[ia])))                                          # ANNAHME Satteldach parallel zur Wandachse: Abweichung wird gemeldet
    s1 = -n1[ia] / n1[2]; X1 = hoch[d1["inl"]]; w = X1[:, ia]; wc, zc = float(w.mean()), float(X1[:, 2].mean())   # s1 = z je m in +w
    w_r = float(np.percentile(w, 99.5 if s1 > 0 else 0.5)); z_r = zc + s1 * (w_r - wc)
    dach = dict(achse=ax_dach, w_r=w_r, z_r=float(z_r), t1=abs(s1), seite1=(-1 if s1 > 0 else +1), tilt1=d1["tilt"], achsabw_grad=ang_abw, n_inl1=d1["n_inl"], quer_steigung=float(abs(n1[1 - ia] / n1[2])))
    rest = hoch[~d1["inl"]]; d2 = ransac_dach(rest, p, richtung=n1[:2] / max(np.linalg.norm(n1[:2]), 1e-9)) if len(rest) > 500 else None
    if d2 is not None and d2["n_inl"] >= p["gegen_anteil"] * d1["n_inl"] and n2_s(d2, ia) * s1 < 0 and abs(math.degrees(math.atan(abs(n2_s(d2, ia)))) - math.degrees(math.atan(abs(s1)))) < 10:
        X2 = rest[d2["inl"]]; s2 = n2_s(d2, ia); wc2, zc2 = float(X2[:, ia].mean()), float(X2[:, 2].mean())
        w_x = (zc2 - zc + s1 * wc - s2 * wc2) / (s1 - s2); dach.update(t2=abs(s2), w_r=float(w_x), z_r=float(zc + s1 * (w_x - wc)), gegenseite=f"WOLKE ({d2['n_inl']} Inlier, First = Ebenenschnitt)")
    else: dach.update(t2=dach["t1"], gegenseite="ANNAHME: gespiegelt (Gegenseite ohne gueltige Wolkenpunkte)")
    # --- Waende: Luecken fuellen (nur dort; Ersatz geprueft; sonst Spiegelung/Huelle) ---
    wert = {k: W[k]["c"] for k in W}; herkunft = {k: "wolke" for k in W}; info = {k: {kk: vv for kk, vv in W[k].items() if kk != "c"} for k in W}
    for nm in W:
        if W[nm]["gueltig"]: continue
        ax, sg = seiten[nm]; cc_all = R[:, 0 if ax == "u" else 1]; e = None
        if ersatz:
            e = ersatz_wand(ersatz, th, "u" if ax == "u" else "v", sg, float(np.percentile(cc_all * sg, 99.0)) - 0.3, p, cc_all)   # Kandidat muss AUSSERHALB der beobachteten Wolke liegen
            if e is not None: info[nm]["ersatz"] = e
        if e is not None and e["geprueft_ok"]: wert[nm] = e["c"]; herkunft[nm] = f"ersatz (laengste parallele Kante {e['laenge']:.1f} m, Widerspruchsanteil {e['widerspruch_anteil']:.4f})"
        else:
            herkunft[nm] = ("ersatz VERWORFEN (Widerspruch zur Wolke) -> " if e is not None else ("Ersatz ohne gueltigen Kandidat (Kante liegt innerhalb der beobachteten Wolke/nicht parallel) -> " if ersatz else "keine Ersatzquelle -> "))
            gg = {"v1": "v0", "v0": "v1", "u1": "u0", "u0": "u1"}[nm]
            if ax == ax_dach and W[gg]["gueltig"]: wert[nm] = 2 * dach["w_r"] - W[gg]["c"]; herkunft[nm] += "ANNAHME gespiegelt am First"
            else: wert[nm] = float(np.percentile(cc_all, 99.5 if sg > 0 else 0.5)); herkunft[nm] += "Wolkenhuelle (Kern-Perzentil)"
    return dict(winkel_grad=th_d, boden_z=z0, kern_n=int(len(K)), wand=wert, wand_herkunft=herkunft, wand_info=info, dach=dach, hoehe_kern=Hh)

def n2_s(d, ia): return -d["n"][ia] / d["n"][2]

# ------------------------------------------------------------------ Parameter anwenden (Handeingriffe / Schleife)
def anwenden(par, cfg):
    """versatz (additiv) und fest (absolut) auf die Wolkenschaetzung. Rueckgabe Kopie + Liste der angewandten Eingriffe."""
    import copy; q = copy.deepcopy(par); v = cfg.get("versatz") or {}; f = cfg.get("fest") or {}; log = []
    def setze(pfad, wert, quelle):
        d = q
        for k in pfad[:-1]: d = d[k]
        alt = d[pfad[-1]]; d[pfad[-1]] = wert; log.append((".".join(pfad), alt, wert, quelle))
    for nm in ("u0", "u1", "v0", "v1"):
        sg = 1 if nm.endswith("1") else -1
        if f"wand_{nm}" in f: setze(("wand", nm), float(f[f"wand_{nm}"]), "fest")
        elif f"wand_{nm}_m" in v: setze(("wand", nm), q["wand"][nm] + sg * float(v[f"wand_{nm}_m"]), "versatz")
    d = q["dach"]
    if "first_z" in f: setze(("dach", "z_r"), float(f["first_z"]), "fest")
    elif "first_z_m" in v: setze(("dach", "z_r"), d["z_r"] + float(v["first_z_m"]), "versatz")
    if "first_pos" in f: setze(("dach", "w_r"), float(f["first_pos"]), "fest")
    elif "first_pos_m" in v: setze(("dach", "w_r"), d["w_r"] + float(v["first_pos_m"]), "versatz")
    for k, nm in (("t1", "1"), ("t2", "2")):
        if "neigung_grad" in f: setze(("dach", k), math.tan(math.radians(float(f["neigung_grad"]))), "fest")
        elif "neigung_grad" in v: setze(("dach", k), math.tan(math.atan(d[k]) + math.radians(float(v["neigung_grad"]))), "versatz")
    if "boden_z" in f: setze(("boden_z",), float(f["boden_z"]), "fest")
    return q, log

# ------------------------------------------------------------------ Koerper
def koerper(par, M, C, naht=0.0):
    """manifold3d-Koerper (Modellrahmen, Meter): Grundrissprisma, oben von zwei Dachebenen beschnitten, gedreht um die Modellachse."""
    w = par["wand"]; d = par["dach"]; zb = par["boden_z"]; th = par["winkel_grad"]
    zt = d["z_r"] + 1.0; a0, a1, b0, b1 = w["u0"], w["u1"], w["v0"], w["v1"]
    k = M.cube((a1 - a0, b1 - b0, zt - zb)).translate((a0, b0, zb)); ia = 1 if d["achse"] == "v" else 0
    for sgn, t in ((+1, d["t1"] if d["seite1"] > 0 else d["t2"]), (-1, d["t2"] if d["seite1"] > 0 else d["t1"])):      # sgn: Seite des Firsts in +w / -w
        # Ebene durch (w_r, z_r): z = z_r - t*sgn*(w - w_r); Normale (nach oben) n ~ (t*sgn in w, 1 in z); behalten: unterhalb
        n = np.zeros(3); n[ia] = t * sgn; n[2] = 1.0; n /= np.linalg.norm(n); o = np.zeros(3); o[ia] = d["w_r"]; o[2] = d["z_r"]
        # Halbraum: nur der Teil auf der jeweiligen Firstseite wird von dieser Ebene begrenzt -> Schnitt beider (Satteldach: z <= min(z1,z2))
        k = k.trim_by_plane(tuple(-n), float(-(n @ o)))
    return k.rotate((0, 0, th))


# ------------------------------------------------------------------ Bauteil-Eintrag fuer baukasten_gen
def _kompass(vec):
    return ("+x" if vec[0] > 0 else "-x") if abs(vec[0]) >= abs(vec[1]) else ("+y" if vec[1] > 0 else "-y")

def bauteil(cfg, ctx, H):
    """H: dict(M, C, ROOT, OD, beleg, lod2_flaechen). Rueckgabe wie ein Bauteil: (adds, cuts)."""
    M, beleg = H["M"], H["beleg"]; OD = H["OD"]
    if not cfg.get("wolke"): sys.exit("rumpf_wolke: cfg 'wolke' (Pfad/Glob der Punktwolkendateien) fehlt")
    P = wolke_laden(cfg["wolke"], H["ROOT"]); ersatz = None; lod2_z = None
    if cfg.get("ersatz") == "lod2":                                                                # Ersatzquelle NUR fuer Luecken (Nutzerregel 6.11.); LoD2 sieht keine Aufbauten
        _, F = H["lod2_flaechen"](); gr = [P_ for t, P_ in F if t == "GroundSurface"]
        ersatz = [[Q[i, :2].tolist(), Q[(i + 1) % len(Q), :2].tolist()] for Q in gr for i in range(len(Q))]
        rz = np.concatenate([P_[:, 2] for t, P_ in F if t == "RoofSurface"]); lod2_z = (float(rz.min()), float(rz.max()))
    par0 = schaetzen(P, cfg, ersatz); par, eingriffe = anwenden(par0, cfg); w, d = par["wand"], par["dach"]; th = math.radians(par["winkel_grad"])
    if lod2_z: d["kandidat_lod2"] = dict(first_z=lod2_z[1], first_versatz_m=lod2_z[1] - par0["dach"]["z_r"], traufe_z=lod2_z[0], hinweis="Kandidat, NICHT mitteln: Foto-Schleife entscheidet per foto_diff")
    pfad = os.environ.get("RUMPF_WOLKE_PARAMETER") or os.path.join(os.path.dirname(os.environ.get("ELEMENTE_AUS") or os.path.join(OD, "elemente.json")), "rumpf_wolke_parameter.json")
    json.dump(dict(wolkenwert=par0, aktuell=par, eingriffe=[dict(parameter=a, alt=b, neu=c, quelle=q) for a, b, c, q in eingriffe], cfg={k: v for k, v in cfg.items() if k != "wolke"}), open(pfad, "w"), indent=1, default=float)
    k = koerper(par, M, H["C"]); ctx["rumpf"] = k; ctx["boden_z"] = par["boden_z"]; ctx["rumpf_par"] = par
    eu = np.array([math.cos(th), math.sin(th)]); ev = np.array([-math.sin(th), math.cos(th)])
    q_w = f"Wolke ({len(P)} Pkt, Kern {par['kern_n']}): Wandebene = Dichtemaximum der Punkte mit Normale senkrecht zur Wand, Winkel {par['winkel_grad']:.1f} Grad aus Parallelen-Konzentration"
    for nm, vec in (("u1", eu), ("u0", -eu), ("v1", ev), ("v0", -ev)):
        hk = par["wand_herkunft"][nm]; q = q_w if hk == "wolke" else f"LUECKE (Abdeckung {par['wand_info'][nm]['abdeckung']:.2f} < {STD['min_abdeckung']}): {hk}"
        if any(e[0] == f"wand.{nm}" for e in eingriffe): q += "; Handeingriff " + ",".join(e[3] for e in eingriffe if e[0] == f"wand.{nm}")
        beleg(_kompass(vec), f"Rumpfwand {nm} bei c={w[nm]:.2f} m (gedrehter Rahmen)", q, c=float(w[nm]), abdeckung=float(par["wand_info"][nm]["abdeckung"]))
    beleg("dach", f"Satteldach: First z={d['z_r']:.2f} m bei w={d['w_r']:.2f}, Neigung {math.degrees(math.atan(d['t1'])):.1f}/{math.degrees(math.atan(d['t2'])):.1f} Grad",
          f"Wolke: Dachebene per RANSAC (Flaechenrang, ohne Wand/Sims), First = hoechster Rand der Dachebene; Gegenseite: {d['gegenseite']}; ANNAHME: Satteldach parallel zur Wandachse (Abweichung {d['achsabw_grad']:.2f} Grad)",
          first_z=float(d["z_r"]), tilt1=float(math.degrees(math.atan(d["t1"]))), tilt2=float(math.degrees(math.atan(d["t2"]))))
    beleg("alle", f"Boden z={par['boden_z']:.2f} m", "Wolke: tiefste dichte z-Lage (Raster 0,1 m, >= 1e-4 der Punkte); liegt ueber dem DGM1-Gelaende, wenn der Boden in der Wolke fehlt - freier Parameter boden_z", boden_z=float(par["boden_z"]))
    for e in eingriffe: beleg("alle", f"Parameter {e[0]} {e[1]:.3f} -> {e[2]:.3f}", f"Eingriff ({e[3]}) aus objekt.json/BAUTEIL_PARAM; Wolkenwert war {e[1]:.3f}")
    ctx["grundriss2d"] = None
    return [k], []
