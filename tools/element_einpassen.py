#!/usr/bin/env python3
"""element_einpassen.py - SPEC S9: Erkennen + Einpassen von Elementen mit FREIEN PARAMETERN + Restpruefung (6.11.2026). Erster Durchstich: Arkadenboegen.

Ablauf je Bogenkandidat (Kasten aus fassade_parsing.py/OWLv2, nur Suchfenster):
  1. kantenpunkte: Canny auf den Einzel-Orthos der Fassadenebene (ortho_<fid>_einzeln, ohne Holdout-Fotos), je Foto Kantenpixel + Gradientenrichtung (dunkel -> hell),
     Abstimmung ueber >= `min_stimmen` Fotos (Passanten/Schatten sind in jedem Foto anders), Rand von Leerstellen (schwarz) verworfen.
  2. einpassen: Formfamilien rund (uc,w,zs), stich (+Pfeilhoehe h<w/2), spitz (+h>w/2); robuster Kostenterm (gekappte Quadrate, Polaritaet: Oeffnung dunkler),
     differential_evolution (2 Seeds) + Nelder-Mead; Modellwahl per BIC (Strafterm Parameterzahl).
  3. gegenpruefen: Modell -> Daten (Median/P90 des Abstands entlang der Kurve; Kurve muss UEBERALL gestuetzt sein) <= Sollwerte; sonst ABGELEHNT (Messung bleibt).
  4. carving_pruefen: Durchblick/Material im Carving (material.npz) gegen die gefittete Oeffnung (unabhaengig vom Fit), 3D-Kanten (kanten_3d.json) als Stuetze.
  5. einbauen: Carving-STL (mm, 1:87) per manifold3d: Oeffnungen exakt abziehen (Laibung bis zur Hallenrueckwand), Brüstungs-/Zwickelplatte auf gefittete Ebene.
Keine Objektnamen/Festwerte: alles aus fassaden.json/objekt.json/Aufrufparametern."""
import os, sys, json, math, argparse
import numpy as np, cv2
from scipy.optimize import differential_evolution, minimize
from scipy.spatial import cKDTree

TAU = 0.15            # Kappung der Kosten (m)
MED_MAX, P90_MAX = 0.10, 0.06   # Gegenpruefung: Median < 0,10 m (Spec); P90 < 0,06 m (S9-Zusatz gegen Fremdformen; aus dem Synth-Rauschen: saubere Boegen P90 <= 0,044 m, 0,1-m-Voxel; 0,20 liess den Kleeblattbogen durch, 6.11.)
SEED_MAX = 0.10   # zwei DE-Seeds muessen Kurven liefern, die <= 0,10 m (Voxelkante) auseinanderliegen (0,05 war unter dem Daten-Rauschen: spitz_b 0,095 m, 6.11.)
FAMILIEN = {"rund": 3, "stich": 4, "spitz": 4}


# ---------------------------------------------------------------- Geometrie
def krone(fam, p, n=400):
    """Scheitelkurve (u,z) eines Bogens: p = (uc, w, zs[, h]); zs = Kaempferhoehe, h = Pfeilhoehe (rund: w/2)."""
    uc, w, zs = p[:3]; h = w / 2 if fam == "rund" else p[3]
    u = np.linspace(uc - w / 2, uc + w / 2, n)
    if fam in ("rund", "stich"):
        R = (w * w / 4 + h * h) / (2 * h); zc = zs + h - R
        z = zc + np.sqrt(np.maximum(R * R - (u - uc) ** 2, 0))
    else:   # spitz: zwei Kreisbogen vom Kaempfer, Mittelpunkte auf Kaempferhoehe gegenueber
        R = (w * w / 4 + h * h) / w
        ul = np.minimum(u, 2 * uc - u)               # Spiegelung auf die linke Haelfte
        cl = uc - w / 2 + R
        z = zs + np.sqrt(np.maximum(R * R - (ul - cl) ** 2, 0))
    return np.c_[u, z]


def profil(fam, p, zb, dz=0.01, nk=500):
    """Oeffnungsrand: linker Pfosten (unten -> Kaempfer), Krone, rechter Pfosten (Kaempfer -> unten). (N,2) in (u,z)."""
    uc, w, zs = p[:3]; k = krone(fam, p, nk)
    n = max(2, int((zs - zb) / dz))
    li = np.c_[np.full(n, uc - w / 2), np.linspace(zb, zs, n)]; re = np.c_[np.full(n, uc + w / 2), np.linspace(zs, zb, n)]
    return np.vstack([li, k, re])


def normalen_aussen(P):
    """Aussennormale (aus der Oeffnung heraus) je Randpunkt; Polygon ist links->oben->rechts->unten im Uhrzeigersinn: Aussen = links von der Laufrichtung."""
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    return np.c_[-T[:, 1], T[:, 0]]


def kosten_fn(D, G, fam, zb, polaritaet=True, k=6):
    """Rueckgabe f(p) = Modell->Daten-Kosten: je Kurvenpunkt (Krone Gewicht 1, Pfosten 0,3) gekappter quadratischer Abstand zum naechsten polaritaetsgerechten Kantenpunkt (m^2).
    Grund (6.11.): Daten->Modell (Mittel ueber alle Kantenpunkte) wird von ~10^4 Hintergrundkanten (Halle, Gesims) dominiert, Kostenlandschaft flach; Modell->Daten misst, ob die KURVE gestuetzt ist."""
    tree = cKDTree(D)
    def f(p):
        try: P = profil(fam, p, zb, 0.04, 150)
        except Exception: return 1e3
        if not np.all(np.isfinite(P)): return 1e3
        d, i = tree.query(P, k=k, distance_upper_bound=TAU)
        if polaritaet:
            Nn = normalen_aussen(P); ii = np.where(np.isfinite(d), i, 0)
            ok = ((G[ii] * Nn[:, None, :]).sum(2) > 0.0) & np.isfinite(d); d = np.where(ok, d, np.inf)
        dm = np.min(np.where(np.isfinite(d), d, TAU), axis=1)
        nj = int(round((p[2] - zb) / 0.04)); w = np.ones(len(P)); w[:max(nj, 1)] = 0.3; w[-max(nj, 1):] = 0.3
        return float(np.sum(w * np.minimum(dm, TAU) ** 2) / np.sum(w))
    return f


# ---------------------------------------------------------------- Daten
def kantenpunkte(ortho_dir, fid, raster, ausschluss=(), min_stimmen=3, min_anteil=0.3, roi=None, sigma=1.2, c_lo=30, c_hi=90, log=print):
    """Canny je Einzel-Ortho; Rueckgabe Punkte (u,z), Gradient (gu,gz), Stimmen. raster: dict u0,z1,zelle,nu,nz. Foto-Auswahl: alle ausser `ausschluss` (Holdout)."""
    ed = os.path.join(ortho_dir, f"ortho_{fid}_einzeln"); nz, nu = raster["nz"], raster["nu"]
    namen = sorted(f[:-4] for f in os.listdir(ed) if f.endswith(".png") and f[:-4] not in set(ausschluss))
    vote = np.zeros((nz, nu), np.float32); valid = np.zeros((nz, nu), np.float32); gx = np.zeros((nz, nu), np.float32); gy = np.zeros((nz, nu), np.float32)
    kern = np.ones((3, 3), np.uint8)
    for nr in namen:
        im = cv2.imread(os.path.join(ed, f"{nr}.png"))
        if im is None or im.shape[:2] != (nz, nu): continue
        g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), sigma); inval = ~im.any(2); inval = cv2.dilate(inval.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        e = cv2.Canny(g, c_lo, c_hi) > 0; e &= ~inval
        sx = cv2.Sobel(g.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3); sy = cv2.Sobel(g.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        ed_ = cv2.dilate(e.astype(np.uint8), kern) > 0
        vote += ed_.astype(np.float32); valid += (~inval).astype(np.float32)
        gx[ed_] += sx[ed_]; gy[ed_] += sy[ed_]
    sel = (vote >= min_stimmen) & (vote >= min_anteil * np.maximum(valid, 1))
    if roi is not None:
        u0, u1, z0, z1 = roi; ys, xs = np.mgrid[0:nz, 0:nu]; uu = raster["u0"] + (xs + 0.5) * raster["zelle"]; zz = raster["z1"] - (ys + 0.5) * raster["zelle"]
        sel &= (uu >= u0) & (uu <= u1) & (zz >= z0) & (zz <= z1)
    # ausduennen: nur lokale Maxima der Stimmen (Kantenband 3 px -> 1 Linie)
    vm = cv2.dilate(vote, np.ones((3, 3), np.uint8)); sel &= vote >= vm - 1e-6
    ys, xs = np.nonzero(sel); u = raster["u0"] + (xs + 0.5) * raster["zelle"]; z = raster["z1"] - (ys + 0.5) * raster["zelle"]
    gu = gx[ys, xs]; gz = -gy[ys, xs]               # Bild-y nach unten -> z nach oben
    n = np.hypot(gu, gz) + 1e-9
    log(f"  Kantenpunkte {fid}: {len(namen)} Fotos, {len(u)} Punkte (Stimmen >= {min_stimmen})")
    return np.c_[u, z], np.c_[gu / n, gz / n], vote[ys, xs], len(namen)


# ---------------------------------------------------------------- Leere-Maske (Carving) als Formdaten
def maske_rand(E, u0, z1, ds, glatt=1.0):
    """E: bool-Raster (Zeile = z von oben nach unten, Spalte = u), True = LEER (Durchblick). Rueckgabe Randpunkte (u,z) der Leere um eine halbe Zelle zum Material verschoben + Aussennormale
    (zeigt vom Leeren zum Material). Quelle der Leere: Sichtstrahlen-Carving (nicht die Fotokanten) -> unabhaengig von den Canny-Daten."""
    from scipy.ndimage import gaussian_filter, binary_erosion
    Ef = gaussian_filter(E.astype(float), glatt); gy, gx = np.gradient(Ef)
    rand = E & ~binary_erosion(E, structure=np.ones((3, 3), bool), border_value=1)
    ys, xs = np.nonzero(rand); nx = -gx[ys, xs]; nz = gy[ys, xs]            # Bild-y nach unten: z-Richtung = -dy; Normale zum Material = -grad(E)
    n = np.hypot(nx, nz) + 1e-9; nx /= n; nz /= n
    u = u0 + (xs + 0.5) * ds + 0.5 * ds * nx; z = z1 - (ys + 0.5) * ds + 0.5 * ds * nz
    return np.c_[u, z], np.c_[nx, nz]


def kosten_rand(B, fam, zb, tau=0.3):
    """Symmetrische gekappte Chamfer-Kosten Rand(Leere) <-> Modellkontur. Randpunkte unterhalb zb+0,3 m (Boden) zaehlen nicht."""
    tb = cKDTree(B)
    def f(p):
        try: P = profil(fam, p, zb, 0.04, 150)
        except Exception: return 1e3
        if not np.all(np.isfinite(P)): return 1e3
        d1 = tb.query(P)[0]; d2 = cKDTree(P).query(B)[0]
        return float(np.mean(np.minimum(d1, tau) ** 2) + np.mean(np.minimum(d2, tau) ** 2))
    return f


def einpassen_rand(B, fam, box, zb, seed=0, hmin=0.3):
    """DE (2 Seeds) + Nelder-Mead auf kosten_rand. box wie einpassen_familie. Rueckgabe (p, kosten, seedstreuung)."""
    uc0, uc1, w0, w1, z0, z1, h0, h1 = box; b = [(uc0, uc1), (w0, w1), (z0, z1)]
    if fam == "stich": b.append((hmin, h1))
    if fam == "spitz": b.append((max(w0 / 2, hmin), h1))
    f0 = kosten_rand(B, fam, zb)
    def f(p):
        if fam == "stich" and (p[3] >= p[1] / 2 - 1e-3 or p[3] < hmin): return 1e3
        if fam == "spitz" and p[3] <= p[1] / 2 + 1e-3: return 1e3
        return f0(p)
    res = []
    for sd in (seed, seed + 17):
        r = differential_evolution(f, b, seed=sd, maxiter=150, popsize=16, tol=1e-10, polish=False, init="sobol")
        r2 = minimize(f, r.x, method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-10, maxiter=1500)); res.append((r2.fun, r2.x))
    res.sort(key=lambda t: t[0]); P0 = profil(fam, res[0][1], zb, 0.03); P1 = profil(fam, res[1][1], zb, 0.03)
    st = float(max(cKDTree(P1).query(P0[P0[:, 1] >= res[0][1][2] - 1.2])[0].max(), cKDTree(P0).query(P1[P1[:, 1] >= res[1][1][2] - 1.2])[0].max()))   # Seeds uneinig = KURVEN weichen ab (Parameter duerfen sich ausgleichen: Kaempfer/Pfeil)
    return res[0][1], res[0][0], st


def kanten_kontrast(D, G, fam, p, zb, tol=0.08, versatz=0.30):
    """Unabhaengige Pruefung an den Canny-Kanten (nicht im Fit benutzt): Stuetze der Krone (Anteil Kronenpunkte mit polaritaetsgerechtem Kantenpunkt <= tol) gegen
    8 um `versatz` verschobene Kopien derselben Kurve. Hintergrundkanten stuetzen jede Kurve; nur das Verhaeltnis ist beweiskraeftig."""
    tree = cKDTree(D)
    def stuetze(dp):
        P = profil(fam, p, zb, 0.03, 200); P = P[P[:, 1] >= p[2]] + dp; Nn = normalen_aussen(profil(fam, p, zb, 0.03, 200))
        Nn = Nn[profil(fam, p, zb, 0.03, 200)[:, 1] >= p[2]]
        d, i = tree.query(P, k=4, distance_upper_bound=tol); ii = np.where(np.isfinite(d), i, 0)
        ok = ((G[ii] * Nn[:, None, :]).sum(2) > 0) & np.isfinite(d); return float(ok.any(1).mean())
    s0 = stuetze(np.zeros(2)); sh = [stuetze(versatz * np.array([np.cos(a), np.sin(a)])) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)]
    return dict(stuetze=s0, stuetze_versetzt_mittel=float(np.mean(sh)), verhaeltnis=float(s0 / (np.mean(sh) + 0.02)))


def verfeinern_kanten(D, G, fam, p, zb, schritt=0.15):
    """Lokale Verfeinerung der Maskenanpassung an den Canny-Kanten (Nelder-Mead, Start = p, Grenzen +-schritt). Rueckgabe (p_neu, kosten_alt, kosten_neu)."""
    f = kosten_fn(D, G, fam, zb, True); p = np.array(p, float)
    def g(q):
        if np.any(np.abs(q - p) > schritt): return 1e3
        if fam == "stich" and (q[3] >= q[1] / 2 - 1e-3 or q[3] < 0.3): return 1e3
        if fam == "spitz" and q[3] <= q[1] / 2 + 1e-3: return 1e3
        return f(q)
    r = minimize(g, p, method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-9, maxiter=800, initial_simplex=np.vstack([p] + [p + np.eye(len(p))[i] * 0.05 for i in range(len(p))])))
    return r.x, float(g(p)), float(r.fun)


def bogen_aus_maske(B, kasten, zb, D=None, G=None, Bn=None, familien=("rund", "stich", "spitz"), seed=0, log=print, med_max=MED_MAX, p90_max=P90_MAX, stuetze_min=0.4, verh_min=1.5):
    """Familienwahl (BIC auf Randabstand, Rauschboden 0,04 m = halbe Voxelkante) + Gegenpruefung (Median/P90 Kurve->Leerenrand; Canny-Kontrast)."""
    kc = (kasten["u0"] + kasten["u1"]) / 2; kw = kasten["u1"] - kasten["u0"]
    box = (kc - 0.7, kc + 0.7, max(1.5, kw - 1.0), kw + 0.8, max(kasten["z0"], zb + 0.5) + 1.0, kasten["z1"] - 0.6, 0.3, 4.0)
    sel = (B[:, 0] >= kasten["u0"] - 0.4) & (B[:, 0] <= kasten["u1"] + 0.4) & (B[:, 1] >= zb + 0.3) & (B[:, 1] <= kasten["z1"] + 0.6); sel &= (Bn[:, 1] > -0.3) if Bn is not None else True; Bw = B[sel]; N = len(Bw); erg = {}   # Normale nach unten = Bodenkante der Leere, keine Bogendaten
    fits = {fam: einpassen_rand(Bw, fam, box, zb, seed) for fam in familien}
    best = min(fits, key=lambda k: fits[k][1]); Pb = profil(best, fits[best][0], zb, 0.02); inl = cKDTree(Pb).query(Bw)[0] < 0.25; Nin = max(int(inl.sum()), 10)   # BIC nur auf den Randpunkten am Bogen (Halle/Boden/Nachbarn sind fuer alle Familien gleich)
    for fam in familien:
        p, c, st = fits[fam]
        P = profil(fam, p, zb, 0.02); mk = P[:, 1] >= p[2] - 1.2; d_m = cKDTree(Bw).query(P[mk])[0]; d_b = cKDTree(P).query(Bw)[0]
        rms = float(np.sqrt(np.mean(np.minimum(d_b[inl], 0.25) ** 2)))
        erg[fam] = dict(p=[round(float(x), 4) for x in p], kosten=float(c), streuung_seeds=round(st, 4), rms_rand=rms, bic=bic(rms ** 2, Nin, FAMILIEN[fam], eps=0.04),
                        median_m=float(np.median(d_m)), p90_m=float(np.percentile(d_m, 90)), max_m=float(d_m.max()), median_rand_m=float(np.median(d_b)), p90_rand_m=float(np.percentile(d_b, 90)))
        log(f"    {fam:6s} p={np.round(p, 3).tolist()} rms={rms:.3f} BIC={erg[fam]['bic']:.1f} med(Kurve->Rand)={erg[fam]['median_m']:.3f} p90={erg[fam]['p90_m']:.3f} Rand p90={erg[fam]['p90_rand_m']:.3f} seeds={st:.3f}")
    wahl = min(erg, key=lambda k: erg[k]["bic"])
    for fam in sorted(erg, key=lambda k: FAMILIEN[k]):
        if FAMILIEN[fam] < FAMILIEN[wahl] and erg[fam]["bic"] <= erg[wahl]["bic"] + 2.0: wahl = fam; break
    e = erg[wahl]; grund = []
    if e["median_m"] >= med_max: grund.append(f"Median {e['median_m']:.3f} >= {med_max}")
    if e["p90_m"] >= p90_max: grund.append(f"P90 {e['p90_m']:.3f} >= {p90_max}")
    if e["streuung_seeds"] > SEED_MAX: grund.append(f"Seeds uneinig ({e['streuung_seeds']:.3f} m > {SEED_MAX})")
    kk = kanten_kontrast(D, G, wahl, e["p"], zb) if D is not None else None
    p_mask = list(e["p"]); verf = None
    if D is not None and kk is not None and kk["stuetze"] >= stuetze_min and kk["verhaeltnis"] >= verh_min:      # Kanten tragen: Feinlage aus den Kanten (sonst bleibt die Maskenlage, kein Fit an Hintergrundkanten)
        pn, k0, k1 = verfeinern_kanten(D, G, wahl, e["p"], zb); kk2 = kanten_kontrast(D, G, wahl, pn, zb)
        verf = dict(p_neu=[round(float(x), 4) for x in pn], kosten_vor=k0, kosten_nach=k1, kontrast_nach=kk2, verschiebung_m=float(np.max(np.abs(pn - np.array(e["p"])))))
        if k1 < k0 and kk2["stuetze"] >= kk["stuetze"]:
            e = dict(e); e["p"] = verf["p_neu"]; P2 = profil(wahl, pn, zb, 0.02); d2 = cKDTree(Bw).query(P2[P2[:, 1] >= pn[2] - 1.2])[0]
            e["median_m"], e["p90_m"], e["max_m"] = float(np.median(d2)), float(np.percentile(d2, 90)), float(d2.max()); verf["uebernommen"] = True; kk = kk2
        else: verf["uebernommen"] = False
    if kk is not None and (kk["stuetze"] < stuetze_min or kk["verhaeltnis"] < verh_min): grund.append(f"Kantenkontrast {kk['stuetze']:.2f} (Verhaeltnis {kk['verhaeltnis']:.2f}) < {stuetze_min}/{verh_min}")
    return dict(familie=wahl, p=e["p"], p_maske=p_mask, verfeinerung=verf, rest=dict(median_m=e["median_m"], p90_m=e["p90_m"], p90_rand_m=e["p90_rand_m"], max_m=e["max_m"], rms_rand=e["rms_rand"]), kantenkontrast=kk,
                angenommen=not grund, ablehngrund=grund, alle_familien=erg, n_rand=int(N), zb=float(zb))


# ---------------------------------------------------------------- Einpassen
def einpassen_familie(D, G, fam, box, zb, seed=0, polaritaet=True, hmin=0.3):
    """box = (uc_lo, uc_hi, w_lo, w_hi, zs_lo, zs_hi, h_lo, h_hi); Mehrfachstart: DE mit 2 Seeds + NM. Rueckgabe (p, kosten, streuung_p)."""
    uc0, uc1, w0, w1, z0, z1, h0, h1 = box
    b = [(uc0, uc1), (w0, w1), (z0, z1)]
    if fam == "stich": b.append((hmin, 0.0))      # obere Grenze (w/2) wird je Kandidat ueber Strafe erzwungen (siehe unten)
    if fam == "spitz": b.append((0.0, 0.0))
    f0 = kosten_fn(D, G, fam, zb, polaritaet)
    def f(p):
        if fam == "stich":
            if p[3] >= p[1] / 2 - 1e-3 or p[3] < hmin: return 1e3
        if fam == "spitz":
            if p[3] <= p[1] / 2 + 1e-3: return 1e3
        return f0(p)
    if fam == "stich": b[3] = (hmin, h1)
    if fam == "spitz": b[3] = (max(w0 / 2, hmin), h1)
    res = []
    for s in (seed, seed + 17):
        r = differential_evolution(f, b, seed=s, maxiter=120, popsize=14, tol=1e-9, polish=False, init="sobol")
        r2 = minimize(f, r.x, method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-10, maxiter=1500))
        res.append((r2.fun, r2.x))
    res.sort(key=lambda t: t[0]); best = res[0]
    streu = float(np.max(np.abs(res[0][1] - res[1][1])))
    return best[1], best[0], streu


def bic(kosten, N, k, eps=0.03):
    """BIC mit Rauschboden eps (m): Pixel 0,05 m / Canny-Lage ~ 0,03 m; Unterschiede kleiner als das Rauschen sind keine Evidenz fuer mehr Parameter."""
    return N * math.log(kosten + eps * eps) + k * math.log(N)


def rest_metriken(D, fam, p, zb, G=None):
    """Modell -> Daten: je Kurvenpunkt (Krone + Pfosten) Abstand zum naechsten Datenpunkt (Stuetze). Daten -> Modell: Median der Datenpunkte im Band 0,3 m."""
    P = profil(fam, p, zb, 0.02); t = cKDTree(D); d, _ = t.query(P)
    dm = cKDTree(P).query(D)[0]; band = dm < 0.3
    # Pfosten nahe am Boden (Strassenbelag/Sockel) nicht werten: Kurve ab Kaempferhoehe - 1,2 m
    mask = P[:, 1] >= (p[2] - 1.2)
    return dict(median_m=float(np.median(d[mask])), p90_m=float(np.percentile(d[mask], 90)), max_m=float(d[mask].max()),
                stuetze_anteil=float(np.mean(d[mask] < 0.10)), daten_median_m=float(np.median(dm[band])) if band.any() else None, n_band=int(band.sum()))


def bogen_einpassen(D, G, suchfenster, zb, familien=("rund", "stich", "spitz"), seed=0, log=print, kasten=None):
    """suchfenster = (u0,u1,z0,z1) um den Kandidatenkasten. Rueckgabe Elementbuch-Eintrag (alle Familien, Wahl per BIC, Gegenpruefung)."""
    u0, u1, z0, z1 = suchfenster
    if kasten is not None:     # Suchfenster aus dem Erkennerkasten (OWLv2): Mitte +-0,7 m, Breite -1,0..+0,6 m, Kaempfer zwischen Kastenunterkante+1 m und Oberkante-0,8 m
        kc = (kasten["u0"] + kasten["u1"]) / 2; kw = kasten["u1"] - kasten["u0"]
        box = (kc - 0.7, kc + 0.7, max(1.5, kw - 1.0), kw + 0.6, max(kasten["z0"], zb + 0.5) + 1.0, kasten["z1"] - 0.8, 0.3, 4.0)
    else:
        box = (u0 + 0.8, u1 - 0.8, 1.5, min(6.0, u1 - u0), max(z0, zb + 0.5) + 0.3, z1 - 1.0, 0.3, 4.0)
    sel = (D[:, 0] >= u0) & (D[:, 0] <= u1) & (D[:, 1] >= zb) & (D[:, 1] <= z1 + 0.5); D, G = D[sel], G[sel]
    N = len(D); erg = {}; fits = {}
    for fam in familien:
        ix = np.random.default_rng(0).permutation(N)[:1500]      # Fit auf <= 1500 Punkten (Zeit), Metriken auf allen
        fits[fam] = einpassen_familie(D[ix], G[ix], fam, box, zb, seed)
    # BIC nur auf den Inliern (Kantenpunkte im Band TAU um die beste Familie): Hintergrundkanten (Halle, Gesims) sind fuer alle Familien gleich und duerfen den Vergleich nicht verwischen
    beste = min(fits, key=lambda k: fits[k][1]); Pb = profil(beste, fits[beste][0], zb, 0.02); inl = cKDTree(Pb).query(D)[0] < TAU; Nin = max(int(inl.sum()), 10)
    for fam in familien:
        p, c, st = fits[fam]; r = rest_metriken(D, fam, p, zb)
        dd = cKDTree(profil(fam, p, zb, 0.02)).query(D[inl])[0]; cin = float(np.mean(np.minimum(dd, TAU) ** 2))
        erg[fam] = dict(p=[round(float(x), 4) for x in p], kosten=float(c), kosten_inlier=cin, streuung_seeds=round(st, 4), bic=bic(cin, Nin, FAMILIEN[fam]), n_inlier=Nin, **r)
        log(f"    {fam:6s} p={np.round(p, 3).tolist()} kosten={c:.5f} inl={cin:.5f} BIC={erg[fam]['bic']:.1f} med={r['median_m']:.3f} p90={r['p90_m']:.3f} stuetze={r['stuetze_anteil']:.2f} seedstreuung={st:.3f}")
    wahl = min(erg, key=lambda k: erg[k]["bic"]); e = erg[wahl]
    # Tie-Break: ist eine einfachere Familie (weniger Parameter) innerhalb 2 BIC-Punkten, gilt sie (Sparsamkeit)
    for fam in sorted(erg, key=lambda k: FAMILIEN[k]):
        if FAMILIEN[fam] < FAMILIEN[wahl] and erg[fam]["bic"] <= e["bic"] + 2.0: wahl = fam; e = erg[fam]; break
    grund = []
    if e["median_m"] >= MED_MAX: grund.append(f"Median {e['median_m']:.3f} >= {MED_MAX}")
    if e["p90_m"] >= P90_MAX: grund.append(f"P90 {e['p90_m']:.3f} >= {P90_MAX}")
    if e["streuung_seeds"] > SEED_MAX: grund.append(f"Seeds uneinig ({e['streuung_seeds']:.3f} m > {SEED_MAX})")
    return dict(familie=wahl, p=e["p"], p_maske=p_mask, verfeinerung=verf, rest=dict(median_m=e["median_m"], p90_m=e["p90_m"], max_m=e["max_m"], stuetze_anteil=e["stuetze_anteil"]),
                angenommen=not grund, ablehngrund=grund, alle_familien=erg, n_daten=int(N), zb=float(zb))


# ---------------------------------------------------------------- Carving-Gegenpruefung
class Ebene:
    """Fassadenebene: Punkt = o + u*d + t*n (xy), z; t nach aussen."""
    def __init__(self, o, n, d): self.o = np.array(o, float); self.n = np.array(n, float); self.d = np.array(d, float)
    def welt(self, u, z, t):
        u, z, t = np.broadcast_arrays(np.asarray(u, float), np.asarray(z, float), np.asarray(t, float))
        return np.stack([self.o[0] + u * self.d[0] + t * self.n[0], self.o[1] + u * self.d[1] + t * self.n[1], z], -1)


def belegung(mat, lo, vox, X):
    i = np.floor((X - lo) / vox).astype(int); ok = np.all((i >= 0) & (i < np.array(mat.shape)), -1)
    out = np.zeros(X.shape[:-1], bool); out[ok] = mat[i[ok][:, 0], i[ok][:, 1], i[ok][:, 2]]; return out, ok


def in_oeffnung(fam, p, zb, U, Z, rand=0.0):
    """True, wenn (U,Z) innerhalb der Oeffnung liegt, um `rand` nach innen verkleinert."""
    uc, w, zs = p[:3]; k = krone(fam, p, 600)
    zk = np.interp(U, k[:, 0], k[:, 1], left=-9, right=-9)
    ok = (np.abs(U - uc) <= w / 2 - rand) & (Z >= zb + rand) & (Z <= zk - rand)
    return ok


def carving_pruefen(mat, lo, vox, eb, fam, p, zb, t_suche=(-7.0, 1.2), t_front=None, hoehe_ab=1.0):
    """Unabhaengig vom Fit: Vorderflaeche t_front aus Zwickelmaterial, Rueckwand t_back aus der Oeffnungsmitte; Anteil leer in der Oeffnung / Material im Zwickel."""
    uc, w, zs = p[:3]; ts = np.arange(t_suche[1], t_suche[0], -0.05)
    # Zwickel: Band 0,3-0,8 m ueber der Krone (Kaempferbereich ausgenommen) und Pfeilerstreifen
    uu = np.linspace(uc - w / 2 + 0.3, uc + w / 2 - 0.3, 20); k = np.interp(uu, *krone(fam, p, 600).T)
    ZW = np.concatenate([np.c_[uu, k + 0.45], np.c_[np.full(8, uc - w / 2 - 0.25), np.linspace(zb + 0.5, zs, 8)], np.c_[np.full(8, uc + w / 2 + 0.25), np.linspace(zb + 0.5, zs, 8)]])
    occ = np.array([belegung(mat, lo, vox, eb.welt(ZW[:, 0], ZW[:, 1], t))[0].mean() for t in ts])
    hit = np.nonzero(occ > 0.5)[0]
    if t_front is None: t_front = float(ts[hit[0]]) if len(hit) else None
    # Oeffnungsinneres (um 0,25 m verkleinert)
    U, Z = np.meshgrid(np.arange(uc - w / 2, uc + w / 2, 0.1), np.arange(zb, zs + w / 2, 0.1)); m = in_oeffnung(fam, p, zb, U, Z, 0.25) & (Z >= zb + hoehe_ab)     # ab 1 m ueber Boden: Waren/Baenke/Personen sind keine Rueckwand
    U, Z = U[m], Z[m]
    if len(U) == 0 or t_front is None: return dict(t_front=t_front, t_back=None, leer_anteil=None, zwickel_material=None, n_innen=int(len(U)))
    occi = np.array([belegung(mat, lo, vox, eb.welt(U, Z, t))[0].mean() for t in ts])
    # Rueckwand: erster Treffer ab 0,4 m hinter der Vorderflaeche mit Belegung > 0,5; Zwischen-Bereich zaehlt als Durchblick
    kand = [(t, o) for t, o in zip(ts, occi) if t <= t_front - 0.4]
    t_back = None
    for t, o in kand:
        if o > 0.5: t_back = float(t); break
    d_ok = np.array([o for t, o in zip(ts, occi) if (t_front - 0.3) >= t >= (t_back + 0.2 if t_back is not None else t_front - 1.3)])
    if t_back is not None and t_back > t_front - 0.5: t_back = None
    leer = float(1 - d_ok.mean()) if len(d_ok) else None
    zw_occ = float(np.mean([belegung(mat, lo, vox, eb.welt(ZW[:, 0], ZW[:, 1], t))[0].mean() for t in np.arange(t_front, t_front - 0.35, -0.05)]))
    return dict(t_front=t_front, t_back=t_back, leer_anteil=leer, zwickel_material=zw_occ, n_innen=int(len(U)))


def linien_stuetze(kanten_json, eb, fam, p, zb, tol_t=0.5, band=0.4):
    """3D-Kanten (kanten_3d.json) nahe der Ebene: Abstand der Linienpunkte (in u,z) zur Oeffnungskontur, Median der Punkte im Band."""
    J = json.load(open(kanten_json)); pts = []
    for L in J["linien"]:
        a, b = np.array(L["p0"]), np.array(L["p1"]); s = np.linspace(0, 1, max(2, int(L["laenge_m"] / 0.05)))[:, None]; pts.append(a + s * (b - a))
    X = np.vstack(pts); rel = X[:, :2] - eb.o; u = rel @ eb.d; t = rel @ eb.n; z = X[:, 2]
    sel = np.abs(t) < tol_t; P = profil(fam, p, zb, 0.02); d = cKDTree(P).query(np.c_[u[sel], z[sel]])[0]; nb = d < band
    return dict(n_punkte_ebene=int(sel.sum()), n_band=int(nb.sum()), median_m=float(np.median(d[nb])) if nb.any() else None)


# ---------------------------------------------------------------- Einbauen
def einbauen(stl_in, stl_out, eb, elemente, massstab=87.0, log=print, **kw):
    """Mehrere krumme Versaetze der Schnittflaechen probieren, bis der exportierte STL beim Laden wasserdicht ist (Splitterkanten fallen sonst im Float32-Raster zusammen)."""
    r = None
    for j in (0.0, 0.0071, 0.0113, 0.0197, 0.0311, 0.0467):
        r = einbauen_einmal(stl_in, stl_out, eb, elemente, massstab, jit=j, log=log, **kw)
        if r is None or r.get("stl_wasserdicht"): break
        log(f"  Versatz {j}: STL nach Laden nicht wasserdicht, naechster Versatz")
    return r


def einbauen_einmal(stl_in, stl_out, eb, elemente, massstab=87.0, platte_dicke=0.4973, tiefe_ueber=0.3137, boden_z=None, jit=0.0, log=print):
    """STL (Modell-mm, 1:massstab) -> Meter, Oeffnungen abziehen, Zwickelplatte vereinigen, zurueck. elemente = Liste dict(familie,p,zb,t_front,t_back)."""
    import manifold3d as M, trimesh
    s = massstab / 1000.0
    m = trimesh.load(stl_in, force="mesh"); V = np.asarray(m.vertices)      # Rechnung in Modell-mm (STL-Float32-Raster): sonst fallen beim Export Splitterpunkte zusammen -> nicht wasserdicht
    K = M.Manifold(M.Mesh(vert_properties=V.astype(np.float32), tri_verts=np.asarray(m.faces).astype(np.uint32)))
    T = np.eye(4)
    def prisma(polyuz, t0, t1):
        pu = polyuz.astype(float); ar = 0.5 * np.sum(pu[:, 0] * np.roll(pu[:, 1], -1) - np.roll(pu[:, 0], -1) * pu[:, 1])
        if ar < 0: pu = pu[::-1]          # manifold3d verlangt CCW (CW ergibt Flaeche 0 -> leerer Koerper)
        cs = M.CrossSection([pu]); pr = M.Manifold.extrude(cs, float(t1 - t0))
        Mx = np.array([[eb.d[0], 0, eb.n[0], eb.o[0] + t0 * eb.n[0]], [eb.d[1], 0, eb.n[1], eb.o[1] + t0 * eb.n[1]], [0, 1, 0, 0]])
        return pr.transform(Mx).scale((1.0 / s, 1.0 / s, 1.0 / s))
    ok = [e for e in elemente if e["angenommen"] and e.get("t_front") is not None and e.get("t_back") is not None]
    if not ok: return None
    tf = float(np.median([e["t_front"] for e in ok])) + 0.0071 + jit      # krumme Versaetze: keine Koinzidenz von Schnittflaechen mit der Voxelgitter-Wolkenflaeche
    ug0 = min(e["p"][0] - e["p"][1] / 2 for e in ok); ug1 = max(e["p"][0] + e["p"][1] / 2 for e in ok); zt = max(float(krone(e["familie"], e["p"], 50)[:, 1].max()) for e in ok) + 0.3
    zb0 = min(e["zb"] for e in ok) - 0.0173 - jit
    plate = prisma(np.array([[ug0, zb0], [ug1, zb0], [ug1, zt], [ug0, zt]]), tf - platte_dicke, tf)
    K = K + plate
    for e in ok:
        P = profil(e["familie"], e["p"], e["zb"] - 0.0173, 0.0197)
        poly = P[::2]; tb = e["t_back"] - 0.0131 - 2 * jit
        K = K - prisma(poly, tb, tf + tiefe_ueber)
    teile = K.decompose(); echt = [q for q in teile if q.volume() > 1e-3 / s ** 3]      # Schnitt kann null-volumige Splitter (Randflaechen exakt auf Wolkenflaeche) abspalten: verwerfen, melden
    K = M.Manifold.compose(echt) if len(echt) != 1 else echt[0]
    mm = K.to_mesh(); V2 = np.asarray(mm.vert_properties)[:, :3]
    for q in (0.0, 0.001, 0.002, 0.005):                   # Gitter-Snap (mm) + Wiedereinlesen als Manifold: Splitter-Kanten, die erst im STL-Float32 zusammenfallen, vorher beseitigen
        Vq = (np.round(V2 / q) * q if q else V2).astype(np.float32)
        try:
            mq = M.Mesh(vert_properties=Vq, tri_verts=np.asarray(mm.tri_verts).astype(np.uint32)); mq.merge(); Kq = M.Manifold(mq)
            if Kq.status() == M.Error.NoError and Kq.num_tri() > 0.9 * K.num_tri():
                m2 = Kq.to_mesh(); V3 = np.asarray(m2.vert_properties)[:, :3]; t3 = trimesh.Trimesh(V3, np.asarray(m2.tri_verts), process=False); t3.export(stl_out)
                if trimesh.load(stl_out, force="mesh").is_watertight: mm = m2; V2 = V3; log(f"  Snap {q} mm: STL nach Laden wasserdicht"); break
        except Exception as ex: log(f"  Snap {q}: {ex}")
    out = trimesh.Trimesh(V2, np.asarray(mm.tri_verts), process=False); out.export(stl_out)
    rep = 0
    chk = trimesh.load(stl_out, force="mesh")                           # STL-Float32-Raster fuehrt vereinzelt zu Kanten mit 4 Flaechen: wie der Pruefstand laden, Fehlkanten-Flaechen entfernen, Loecher fuellen
    if not chk.is_watertight:
        u, inv, c = np.unique(chk.edges_sorted, axis=0, return_inverse=True, return_counts=True); bad = np.nonzero(c[inv] != 2)[0] // 3
        keep = np.ones(len(chk.faces), bool); keep[np.unique(bad)] = False; rep = int((~keep).sum()); chk.update_faces(keep); trimesh.repair.fill_holes(chk); chk.merge_vertices()
        if chk.is_watertight: chk.export(stl_out); out = chk
        else: log(f"  WARNUNG: Reparatur ({rep} Flaechen) ergibt kein wasserdichtes Netz")
    log(f"  eingebaut: {len(ok)} Oeffnungen, Platte t_front {tf:.2f}, Teile {len(teile)} (echt {len(echt)}, verworfen {len(teile) - len(echt)}), wasserdicht {out.is_watertight}, repariert {rep} Flaechen")
    return dict(t_front_platte=tf, n=len(ok), teile=len(teile), teile_echt=len(echt), repariert_flaechen=rep, wasserdicht=bool(out.is_watertight), stl_wasserdicht=bool(trimesh.load(stl_out, force="mesh").is_watertight), versatz=jit)


def t_front_schaetzen(mat, lo, vox, eb, kaesten, zb, schwelle=0.6):
    """Vorderflaeche der Arkade aus den PFEILERN: Streifen +-0,15 m um die Grenze benachbarter Kandidatenkaesten, Hoehe zb+1..zb+2,3 m; von aussen nach innen das erste t,
    an dem der Streifen (Mittel ueber alle Pfeiler) zu >= `schwelle` belegt ist. (Zwickelband ueber den Boegen war falsch: Balkon/Gesims liegt 0,6-1 m weiter vorn, 6.11.)"""
    ks = sorted(kaesten, key=lambda e: e["u0"]); us = [(ks[i]["u1"] + ks[i + 1]["u0"]) / 2 for i in range(len(ks) - 1)]
    pts = [np.meshgrid(np.arange(u - 0.15, u + 0.16, 0.05), np.arange(zb + 1.0, zb + 2.3, 0.1)) for u in us]
    for t in np.arange(1.0, -2.0, -0.05):
        if np.mean([belegung(mat, lo, vox, eb.welt(U, Z, t))[0].mean() for U, Z in pts]) >= schwelle: return float(t)
    return None


def leere_raster(mat, lo, vox, eb, fenster, t0, t1, ds=0.05):
    """Leere-Raster (True = Durchblick) im Fenster (u0,u1,z0,z1) als Mittel ueber die Tiefe t0..t1 (belegt < 50 %)."""
    u0, u1, z0, z1 = fenster; us = np.arange(u0, u1, ds); zs_ = np.arange(z1, z0, -ds); U, Z = np.meshgrid(us, zs_)
    occ = np.mean([belegung(mat, lo, vox, eb.welt(U, Z, t))[0] for t in np.arange(t0, t1 - 1e-9, -0.05)], axis=0)
    return occ < 0.5


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ortho", required=True, help="Ordner mit fassaden.json + ortho_<fid>_einzeln (ohne Holdout)")
    ap.add_argument("--fassade", default="f02"); ap.add_argument("--elemente", required=True, help="elemente.json von fassade_parsing (Kandidatenkaesten)")
    ap.add_argument("--material", required=True, help="carving material.npz"); ap.add_argument("--stl", required=True); ap.add_argument("--kanten3d")
    ap.add_argument("--aus", required=True); ap.add_argument("--ausschluss", default="001,024,054,083,211,234"); ap.add_argument("--name", default="s9")
    ap.add_argument("--familie-fest", choices=list(FAMILIEN), help="Experiment: statt der BIC-Wahl diese Familie einbauen (nur mit --erzwingen sinnvoll)")
    ap.add_argument("--nur-einbau", action="store_true", help="Anpassung aus vorhandener <name>_elemente.json uebernehmen, nur Einbau wiederholen")
    ap.add_argument("--erzwingen", action="store_true", help="auch abgelehnte Bogen einbauen (nur als Experiment, im Elementbuch als erzwungen markiert; kosten_lr entscheidet)")
    ap.add_argument("--tiefe-hinter", type=float, default=0.1, help="Schnittebene der Leere-Maske: t_front - dieser Wert")
    a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
    FA = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]; F = next(f for f in FA if f["id"] == a.fassade)
    eb = Ebene([*F["o"], 0], F["n"], F["d"]); eb.o = np.array(F["o"], float)
    E = json.load(open(a.elemente))["fassaden"][a.fassade]["elemente"]; Bk = sorted([e for e in E if e["klasse"] == "bogen"], key=lambda e: e["u0"])
    D, G, V, nf = kantenpunkte(a.ortho, a.fassade, F["raster"], a.ausschluss.split(","))
    mz = np.load(a.material); mat, lo, vox = mz["material"], mz["lo"], float(mz["vox"])
    zb = float(min(F["z"][0] + 0.45, 0.0)); erg = []
    if a.nur_einbau: erg = json.load(open(os.path.join(a.aus, f"{a.name}_elemente.json")))["elemente"]; Bk = []
    tf_arkade = t_front_schaetzen(mat, lo, vox, eb, Bk, zb) if Bk else None; print(f"t_front aus Pfeilern: {tf_arkade}", flush=True)
    for i, b in enumerate(Bk):
        print(f"Bogen {i}: Kandidat u {b['u0']:.2f}..{b['u1']:.2f} z {b['z0']:.2f}..{b['z1']:.2f}", flush=True)
        tf = tf_arkade
        fen = (b["u0"] - 0.8, b["u1"] + 0.8, zb, b["z1"] + 0.9); Er = leere_raster(mat, lo, vox, eb, fen, tf - a.tiefe_hinter + 0.1, tf - a.tiefe_hinter - 0.1)
        Bp, Bn = maske_rand(Er, fen[0], fen[3], 0.05)
        print(f"  t_front(Zwickelband) {tf:.2f}, Leere-Randpunkte {len(Bp)}", flush=True)
        e = bogen_aus_maske(Bp, b, zb, D, G, Bn); e["kandidat"] = b; e["t_front_arkade"] = tf
        e.update(carving_pruefen(mat, lo, vox, eb, e["familie"], e["p"], zb, t_front=tf))
        if a.kanten3d: e["linien"] = linien_stuetze(a.kanten3d, eb, e["familie"], e["p"], zb)
        print("  ->", e["familie"], e["p"], "angenommen" if e["angenommen"] else "ABGELEHNT " + "; ".join(e["ablehngrund"]), {k: e.get(k) for k in ("t_front", "t_back", "leer_anteil", "zwickel_material")}, e["kantenkontrast"], flush=True)
        erg.append(e)
    if not a.nur_einbau: json.dump(dict(fassade=a.fassade, ebene=dict(o=F["o"], n=F["n"], d=F["d"]), zb=zb, elemente=erg, ausschluss=a.ausschluss), open(os.path.join(a.aus, f"{a.name}_elemente.json"), "w"), indent=1)
    if a.familie_fest: erg = [dict(e, familie=a.familie_fest, p=e["alle_familien"][a.familie_fest]["p"]) for e in erg]
    el = [dict(familie=e["familie"], p=e["p"], zb=zb, angenommen=e["angenommen"] or a.erzwingen, t_front=e.get("t_front"), t_back=e.get("t_back") if e.get("t_back") is not None else (e.get("t_front") - 1.0)) for e in erg]
    r = einbauen(a.stl, os.path.join(a.aus, f"{a.name}_1-87.stl"), eb, el)
    json.dump(r, open(os.path.join(a.aus, f"{a.name}_einbau.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
