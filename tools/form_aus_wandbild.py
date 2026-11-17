#!/usr/bin/env python3
"""form_aus_wandbild.py - GESTALT einer Wandzone aus Wandbild + Tiefe NACHBILDEN (Grundsatz "Wandbild = Bauplan", Nutzer 17.11.2026:
"nicht sagen das ist eine Tuer und irgendeine Tuer als Muster nehmen").

Erkennen liefert nur die ZONE (Kasten u0..u1, z0..z1 im Wandrahmen, z. B. ein erkanntes Fenster mit Rand). Alles andere kommt aus den Daten:
  1. Wandbild der Zone im 1-cm-Raster: aus dem feinen Fassadenbild (fassade_fein.py, --ortho DIR:fid) ODER direkt aus den Fotos auf eine beliebige
     senkrechte Ebene (--fotos auto: K-Kameras aus messprotokoll, k beste nach Blickwinkel x Pixel je Meter, Median; fuer Flaechen ohne Fassadenbild,
     z. B. Erkerseiten). Optional Feinausrichtung (wand_feinausrichtung.py).
  2. Tiefe je Zelle aus einem Relief im Format relief_einsatz.py (--tiefe: Netz-Relief 5 cm, Mono-Relief, tiefe_lokal ...), auf das Raster gezogen.
  3. Segmentierung OHNE Farbregel des Gebaeudes: Wandfarbe = Median des Zonenrands (die Zone hat Rand), Abstand je Zelle in Lab, Schwelle Otsu.
     Flaechige Abweichung (Oeffnen 3 cm) = Regionen; duenne Abweichung = Linien (Rahmenkanten, Bleiruten, Fugen).
  4. Je Region entscheidet die TIEFE: liegt sie >= --loch_stufe hinter dem Wandniveau (Median der Wandzellen), ist sie OEFFNUNG (Loch, Umriss = Bildumriss);
     sonst ein flaches Farbfeld (bleibt Wand). Die Stufe ist gemessen (Median der Zellen), nicht angenommen.
  5. Rahmen/Pfosten = Wand zwischen den Oeffnungen innerhalb ihrer Huelle (Schliessen mit --huelle m); Gewaende = Band um die Huelle, Breite = haeufigster Abstand
     der Linienpixel von der Huelle (Bildkante, z. B. die Aussenkante des Steinrahmens). Profil im Band: STUFEN an den parallelen Bildlinien (Spitzen im Abstands-Histogramm; --profil schraege = lineare Schraege) von der Wandflaeche bis zur
     gemessenen Oeffnungstiefe an der Huelle (FORM DER SCHRAEGE = ANNAHME, Breite und Tiefe gemessen). Pfosten: Plateau auf dem Tiefenwert der Pfostenzellen (P80).
  6. Ausgabe: Hoehenbild im relief_einsatz-Format (rel = Lage w vor der Wandebene, absolut), Maske 'loch', Lochumrisse als Polygone (u, z), Klassenbild,
     Bericht + Bild <aus>.jpg (Wandbild | Segmente | Schummerung | Tiefe). Im Generator: teil(npz) -> (zusatz, abzug): koerper = (koerper + zusatz) - abzug.
Grenzen: Profile nur als Schraege/Plateau (keine Kehle/Wulst-Stufen; die Netz-Tiefe hat 5 cm Raster); Freistehendes (Saeule, Bruestung, Erkerkoerper) ist KEIN
Wandbild-Fall (Parallaxe) - dort Form aus Fotokanten mehrerer Ansichten. Wo die Tiefe fehlt, entscheidet --ohne_tiefe (Standard: keine Oeffnung = ehrlich flach).
Aufruf:
  form_aus_wandbild.py <objekt.json> --wand ax ay bx by sx sy --zone u0 u1 z0 z1 --ortho DIR:f02 --tiefe relief/w04.npz --flaeche relief/w04_rein.npz --aus X.npz
  form_aus_wandbild.py <objekt.json> --wand ... --zone ... --fotos auto [--w 1.1] --tiefe X_tiefe.npz --aus X.npz
Generator:  from form_aus_wandbild import teil;  zus, ab = teil("modelle/<obj>/relief/form_<zone>.npz");  koerper = (koerper + zus) - ab
"""
import os, sys, json, glob, argparse, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))


def _ebene(a, b, aussen):
    a = np.asarray(a, float); b = np.asarray(b, float); t = (b - a) / np.linalg.norm(b - a); n = np.array([t[1], -t[0]])
    return a, t, (n if (np.asarray(aussen, float) - a) @ n > 0 else -n)


def gitter(zone, px):
    u0, u1, z0, z1 = zone; nu = int(round((u1 - u0) / px)); nz = int(round((z1 - z0) / px))
    return u0 + (np.arange(nu) + 0.5) * px, z1 - (np.arange(nz) + 0.5) * px      # Zeile 0 = oben (wie Fassadenbild)


# ---------------------------------------------------------------- 1. Wandbild
def wandbild_ortho(ortho, a, t, zone, px, w=0.0, n=None):
    """Feines Fassadenbild (fassade_fein.py) auf das Zonenraster ziehen. ortho = 'DIR:fid' (DIR mit fassaden.json, ortho_<fid>_fein.png bzw. ortho_<fid>.png)."""
    import cv2
    d_, fid = ortho.rsplit(":", 1); F = [f for f in json.load(open(os.path.join(d_, "fassaden.json")))["fassaden"] if f.get("id") == fid][0]; r = F["raster"]
    p = os.path.join(d_, f"ortho_{fid}_fein.png"); p = p if os.path.exists(p) else os.path.join(d_, f"ortho_{fid}.png"); im = cv2.imread(p)
    uu, zz = gitter(zone, px); U, Z = np.meshgrid(uu, zz); o = np.array(F["o"], float); d = np.array(F["d"], float)
    X = a[None, None, :] + U[..., None] * t[None, None, :] + (0.0 if n is None else w) * (n if n is not None else 0)
    uF = (X - o) @ d; col = (uF - r["u0"]) / r["zelle"] - 0.5; row = (r["z1"] - Z) / r["zelle"] - 0.5
    out = cv2.remap(im, col.astype(np.float32), row.astype(np.float32), cv2.INTER_AREA if r["zelle"] < px else cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out, out.sum(2) > 0, dict(quelle=p, fassade=fid, zelle_bild=r["zelle"])


def _kameras(objekt_json):
    od = os.path.dirname(os.path.abspath(objekt_json)); K = {}
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        try: k = json.load(open(f))["kamera"]
        except Exception: continue
        if "rvec" in k and "f_px" in k: K[os.path.basename(f)[2:-5]] = k
    return K


def _foto_pfad(objekt_json, nm):
    od = os.path.dirname(os.path.abspath(objekt_json)); fd = json.load(open(objekt_json))["fotos_dir"]
    wurzeln = [os.path.dirname(os.path.dirname(od)), os.path.dirname(os.path.dirname(os.path.realpath(od)))]
    gf = os.path.join(wurzeln[0], ".git")                                    # git-Worktree: Fotos liegen (ungetrackt) im Haupt-Checkout
    if os.path.isfile(gf):
        g_ = open(gf).read().strip().split("gitdir:")[-1].strip()
        if "/.git/" in g_: wurzeln.append(g_.split("/.git/")[0])
    for root in wurzeln:
        g = glob.glob(os.path.join(root, fd, nm + ".*")) or glob.glob(os.path.join(root, fd, nm + "_*"))
        if g: return g[0]
    return None


def _proj(k, X):
    import cv2
    R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; p = X @ R.T + np.array(k["t"], float); z = p[:, 2]
    x = p[:, 0] / z; y = p[:, 1] / z; f = 1 + float(k.get("k1") or 0) * (x * x + y * y)
    return np.c_[k["f_px"] * x * f + k["cx"], k["f_px"] * y * f + k["cy"]], z


_MESH = {}


def _sicht(stl, massstab, X, C, tol=0.15):
    """True je Punkt, wenn der Strahl Punkt -> Kamera C frei ist (Modell-STL, Massstab wie objekt.json stl_massstab). Start tol vor dem Punkt (eigene Wand)."""
    import trimesh
    if stl not in _MESH:
        ms = trimesh.load(stl); ms.apply_scale(massstab / 1000.0)
        RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector; _MESH[stl] = RI(ms)
    sys.path.insert(0, HIER); from fassade_ortho import erster_treffer
    d = C[None, :] - X; L = np.linalg.norm(d, axis=1, keepdims=True); d = d / L
    return erster_treffer(_MESH[stl], X + tol * d, d.astype(np.float32), roh=True) < 0


def wandbild_fotos(objekt_json, a, t, n, zone, px, w=0.0, k=5, fotos=None, fein=False, min_cos=0.45, gpu_mb=1200, stl=None, min_sicht=0.3, max_rest=0.01):
    """Wandbild der Zone direkt aus den Fotos (Ebene w vor der Wand a-t-n): je Foto Projektion der Zellmitten, Wertung cos(Blick) / (m je Pixel),
    k beste, Median der Farben (Verdecker wandern -> fallen heraus). Keine Sichtbarkeitspruefung gegen das Modell (ANNAHME: die Zone ist frei sichtbar,
    z. B. eine Erkerflaeche vor der Wand); deshalb nur Fotos von VORN (cos >= min_cos)."""
    import cv2
    K = _kameras(objekt_json); uu, zz = gitter(zone, px); U, Z = np.meshgrid(uu, zz); H, W_ = U.shape
    X = np.c_[(a[0] + U * t[0] + w * n[0]).ravel(), (a[1] + U * t[1] + w * n[1]).ravel(), Z.ravel()]; mitte = X.mean(0); wert = []
    for nm, kk in K.items():
        if fotos and nm not in fotos: continue
        S = np.array(kk.get("standort_xyz", [0, 0, 0]), float)[:3]; v = S - mitte; dist = np.linalg.norm(v)
        if dist < 1e-3: continue
        cs = (v[:2] @ n) / dist
        if cs < min_cos: continue
        uv, zc = _proj(kk, X[[0, W_ - 1, (H - 1) * W_, H * W_ - 1, (H // 2) * W_ + W_ // 2]])
        bw, bh = (kk.get("bild") or [2 * kk["cx"], 2 * kk["cy"]])[:2]
        if (zc <= 0).any() or (uv[:, 0] < 0).any() or (uv[:, 1] < 0).any() or (uv[:, 0] > bw).any() or (uv[:, 1] > bh).any(): continue
        wert.append((cs * kk["f_px"] / dist, nm))
    wert.sort(reverse=True); stapel = []; info = []
    for s, nm in wert[: 3 * k]:
        p = _foto_pfad(objekt_json, nm)
        if p is None: continue
        im = cv2.imread(p)
        if im is None: continue
        uv, _ = _proj(K[nm], X); bb = K[nm].get("bild") or [im.shape[1], im.shape[0]]; sx = im.shape[1] / bb[0]; sy = im.shape[0] / bb[1]
        o = cv2.remap(im, (uv[:, 0] * sx).reshape(H, W_).astype(np.float32), (uv[:, 1] * sy).reshape(H, W_).astype(np.float32), cv2.INTER_AREA, borderValue=0); anteil = 1.0
        if stl:                                                              # Sichtbarkeit gegen das Modell: was davor steht (Bruestung, Figur), gilt in diesem Foto als nicht gesehen
            R_ = cv2.Rodrigues(np.array(K[nm]["rvec"], float))[0]; C_ = -R_.T @ np.array(K[nm]["t"], float); sv = _sicht(stl, float(json.load(open(objekt_json)).get("stl_massstab", 87)), X, C_).reshape(H, W_)
            anteil = float(sv.mean())
            if anteil < min_sicht: continue
            o[~sv] = 0
        stapel.append(o); info.append(dict(foto=nm, wert=round(s, 1), mm_je_px=round(1000.0 / s, 1), sichtbar=round(anteil, 3)))
        if len(stapel) >= k: break
    if not stapel: return None, None, dict(fehler="kein Foto sieht die Zone von vorn")
    fa = None; modus = "median"
    if fein and len(stapel) >= 3:
        sys.path.insert(0, HIER); import wand_feinausrichtung as WF
        mk = [(x.sum(2) > 0) for x in stapel]; stapel, mk, _, fa = WF.fein_ausrichten(stapel, mk, px, gpu_mb=gpu_mb)
        rest = [None if (r_ or {}).get("median_zellen") is None else r_["median_zellen"] * px for r_ in (fa.get("nachher") or [None] * len(stapel))]
        gut = [i for i, r_ in enumerate(rest) if r_ is not None and r_ <= max_rest]
        for i, r_ in enumerate(rest): info[i]["restversatz_cm"] = None if r_ is None else round(100 * r_, 2)
        if len(gut) >= 3: stapel = [stapel[i] for i in gut]; info = [info[i] for i in gut]; modus = "median_ausgerichtet"
        else:                                                                # Fotos lassen sich nicht deckungsgleich ziehen (Restversatz > max_rest): Median gaebe Geisterkanten -> das beste Einzelfoto, Luecken aus den anderen
            erst = stapel[0].copy(); leer = erst.sum(2) == 0
            if len(stapel) > 1:
                S2 = np.stack(stapel[1:]).astype(np.float32); S2[S2.sum(3) == 0] = np.nan
                import warnings
                with warnings.catch_warnings(): warnings.simplefilter("ignore"); m2 = np.nan_to_num(np.nanmedian(S2, 0)).astype(np.uint8)
                erst[leer] = m2[leer]
            return erst, erst.sum(2) > 0, dict(fotos=info, feinausrichtung=True, modus="bestes_einzelfoto (Restversatz > %.1f cm)" % (100 * max_rest))
    S = np.stack(stapel).astype(np.float32); g = S.sum(3) > 0
    for i in range(1, len(S)):                                               # Belichtung je Foto an das beste angleichen (Verstaerkung je Kanal auf gemeinsam gesehenen Zellen) - sonst Flecken, wo der Median andere Fotos mischt
        ge = g[0] & g[i]
        if ge.sum() > 500: S[i] *= (np.median(S[0][ge], 0) / np.maximum(np.median(S[i][ge], 0), 1.0))[None, None, :]
    S = np.clip(S, 0, 255); S[~g] = np.nan
    import warnings
    with warnings.catch_warnings(): warnings.simplefilter("ignore"); med = np.nanmedian(S, 0)
    return np.nan_to_num(med).astype(np.uint8), g.any(0), dict(fotos=info, feinausrichtung=fa is not None, modus=modus)


# ---------------------------------------------------------------- 2. Tiefe
def tiefe_zone(npz, a, t, n, zone, px, trend=False, sockel=0.0):
    """Relief (relief_einsatz-Format) auf das Zonenraster: Lage w vor der Ebene a-t-n (m), NaN wo das Relief nichts hat (rel == 0 = Loch in relief_einsatz).
    trend=True: Ebenentrend + Ebenenabstand wie relief_einsatz.koerper(trend=True) aufschlagen (fuer die Lage der gebauten Platte)."""
    import cv2
    Z = np.load(npz); rel = Z["rel"].astype(np.float32); Hr, Wr = rel.shape; pr = float(Z["px"]); ur0 = float(Z["u0"]); zr0 = float(Z["z0"])
    if trend:
        tu, tz = [float(v) for v in Z["trend_je_m"]]; ii, jj = np.mgrid[0:Hr, 0:Wr]
        rel = np.where(rel != 0, rel + float(Z["ebene_abstand_m"]) + tu * (jj + 0.5) * pr - tz * (ii + 0.5) * pr, 0).astype(np.float32)
    uu, zz = gitter(zone, px); U, Zg = np.meshgrid(uu, zz); X = a[None, None, :] + U[..., None] * t[None, None, :]
    ur = (X - Z["a"][:2]) @ Z["t"][:2]; off = float((a - Z["a"][:2]) @ Z["n"][:2]) * float(np.sign(n @ Z["n"][:2]))
    col = (ur - ur0) / pr - 0.5; row = Hr - 1 - ((Zg - zr0) / pr - 0.5)
    leer = (rel == 0).astype(np.float32); r_ = cv2.remap(rel, col.astype(np.float32), row.astype(np.float32), cv2.INTER_LINEAR, borderValue=0)
    l_ = cv2.remap(leer, col.astype(np.float32), row.astype(np.float32), cv2.INTER_LINEAR, borderValue=1)
    return np.where(l_ < 0.5, r_ * float(np.sign(n @ Z["n"][:2])) - off + sockel, np.nan).astype(np.float32)


# ---------------------------------------------------------------- 3.-5. Segmentierung und Gestalt
def gestalt(img, gueltig, tief, w_flaeche, px, rand=0.08, loch_stufe=0.04, min_m2=0.012, linie_m=0.03, huelle_m=0.22, band_max=0.30, w_hinten=-0.09, ohne_tiefe=False, klassen=6, vorn_m=0.06, schliessen_m=0.01, profil="stufen", rand_loch=0.03, tiefe_veto=0.25, glatt_m=0.03, klasse_anteil=0.75, flaechig_m=0.05, min_flaechig=0.35, leer_offen=False, profil_max=0.25):
    """Kern: Bild -> Regionen/Linien, Tiefe -> Entscheidung Loch/Feld und Stufenhoehen. Liefert dict mit h (w absolut), loch, klasse, polygone, mass."""
    import cv2
    from scipy import ndimage as ndi
    H, W_ = gueltig.shape; r_ = max(1, int(round(rand / px))); ring = np.zeros_like(gueltig); ring[:r_] = ring[-r_:] = True; ring[:, :r_] = ring[:, -r_:] = True; ring &= gueltig
    vorn = np.zeros_like(gueltig); bild_ok = gueltig.copy()
    if np.isfinite(tief[ring]).sum() > 20:                                   # etwas steht VOR der Wand (Bruestung, Figur, Erker): kein Wandbild-Fall -> nicht segmentieren, Wand bleibt dahinter eben
        vorn = cv2.dilate((np.nan_to_num(tief, nan=-9) > float(np.nanmedian(tief[ring])) + vorn_m).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool); gueltig = gueltig & ~vorn; ring &= gueltig
    t_rand = float(np.nanmedian(tief[ring])) if np.isfinite(tief[ring]).sum() > 20 else None      # Wandniveau = Zonenrand, nur mit leer_offen (Tor: die Wandfarbklasse liegt auch im Durchblick); sonst Median der Wandklasse (Rand enthaelt Figurenreste, Kaufhaus Fenster 2: 0,12 -> 0,19 m)
    if leer_offen and np.isfinite(tief[ring]).sum() > 20:                   # Relief leer (Netz sah durch: Tor, Durchfahrt) = offen, 1 m hinter der Wand (ANNAHME, nur mit --leer_offen 1)
        tief = np.where(~np.isfinite(tief) & gueltig, float(np.nanmedian(tief[ring])) - 1.0, tief)
    lab = cv2.cvtColor(cv2.medianBlur(img, 3), cv2.COLOR_BGR2LAB).astype(np.float32); wc = np.median(lab[ring], 0)
    dw = np.sqrt((0.5 * (lab[..., 0] - wc[0])) ** 2 + (lab[..., 1] - wc[1]) ** 2 + (lab[..., 2] - wc[2]) ** 2); dw[~gueltig] = 0
    # Farbklassen der Zone (k-means in Lab, Helligkeit halb gewichtet) - KEINE Farbregel: welche Klasse Wand ist, sagt der Zonenrand; welche Oeffnung ist, sagt die Tiefe
    X_ = lab[gueltig] * np.array([0.5, 1, 1], np.float32); kk = int(min(klassen, max(2, len(X_) // 500)))
    _, lb, zent = cv2.kmeans(X_, kk, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS); cl = np.full(gueltig.shape, -1, np.int32); cl[gueltig] = lb.ravel()
    wand_kl = int(np.bincount(cl[ring], minlength=kk).argmax()); t_ok = np.isfinite(tief)
    wandz = (cl == wand_kl) & ~cv2.dilate((cl != wand_kl).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & gueltig
    t_wand = t_rand if (leer_offen and t_rand is not None) else float(np.nanmedian(tief[wandz & t_ok])) if (wandz & t_ok).sum() > 50 else (float(np.nanmedian(tief[t_ok])) if t_ok.any() else np.nan)
    kl_stufe = []
    for c_ in range(kk):
        m_ = (cl == c_) & t_ok; kl_stufe.append(float(t_wand - np.median(tief[m_])) if m_.sum() > 30 and np.isfinite(t_wand) else np.nan)
    smax = np.nanmax(kl_stufe) if np.isfinite(kl_stufe).any() else 0.0
    ka = max(3, 2 * int(round(flaechig_m / px / 2)) + 1); el_ = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ka, ka)); kl_flaech = []
    for c_ in range(kk):                                                     # Anteil der Klasse, der ein Oeffnen mit flaechig_m uebersteht: Glas ist flaechig, Rahmenkanten/Goldlinien sind linienhaft
        m_ = (cl == c_).astype(np.uint8); kl_flaech.append(float(cv2.morphologyEx(m_, cv2.MORPH_OPEN, el_).sum()) / max(int(m_.sum()), 1))
    loch_kl = [c_ for c_ in range(kk) if c_ != wand_kl and np.isfinite(kl_stufe[c_]) and kl_stufe[c_] >= max(loch_stufe, klasse_anteil * smax) and kl_flaech[c_] >= min_flaechig]
    if ohne_tiefe and not np.isfinite(kl_stufe).any(): loch_kl = [int(np.argmin(zent[:, 0]))]          # ohne Tiefe: dunkelste Klasse (nur mit --ohne_tiefe 1, ANNAHME)
    anders = (cl != wand_kl) & gueltig; k_ = max(3, 2 * int(round(schliessen_m / px / 2)) + 1)
    flaech = np.isin(cl, loch_kl); flaech = cv2.morphologyEx(cv2.morphologyEx(flaech.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), cv2.MORPH_CLOSE,
                                                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_, k_))).astype(bool) & gueltig
    linien = anders & ~flaech; thr = 0.0
    lab_, nlab = ndi.label(flaech); loch = np.zeros_like(gueltig); regionen = []; ero = np.ones((max(3, int(0.04 / px)),) * 2, bool)
    for k, sl in enumerate(ndi.find_objects(lab_), 1):
        c = lab_[sl] == k; A = c.sum() * px * px
        if A < min_m2: continue
        ce = ndi.binary_erosion(c, ero) if c.sum() > 4 * ero.size else c; tv = tief[sl][ce]; tv = tv[np.isfinite(tv)]
        stufe = (t_wand - float(np.median(tv))) if (len(tv) >= 5 and np.isfinite(t_wand)) else None
        ist = (stufe is not None and stufe >= loch_stufe) or (stufe is None and ohne_tiefe)
        regionen.append(dict(flaeche_m2=round(A, 3), stufe_m=None if stufe is None else round(stufe, 3), loch=bool(ist), bbox_px=[sl[1].start, sl[0].start, sl[1].stop, sl[0].stop]))
        if ist: cf = ndi.binary_fill_holes(c); kl = cf & ~c; kl_l, nk = ndi.label(kl); gross = np.bincount(kl_l.ravel(), minlength=nk + 1) * px * px > 0.02; cf[gross[kl_l] & kl] = False; loch[sl] |= cf
    stufen = [r["stufe_m"] for r in regionen if r["loch"] and r["stufe_m"] is not None]; D = float(np.median(stufen)) if stufen else 0.0
    rb = max(1, int(round(rand_loch / px))); loch[:rb] = loch[-rb:] = False; loch[:, :rb] = loch[:, -rb:] = False      # eine Oeffnung liegt IN der Zone (Rand = Wand); Streifen am Zonenrand sind keine
    n_nach = 0
    if loch.any() and D > 0:                                                 # Nachpruefung in der Oeffnungshuelle: Glas mit Himmelsspiegelung faellt in eine andere Farbklasse - dort entscheidet die Tiefe je Zelle
        kh = max(3, 2 * int(round(huelle_m / px / 2)) + 1); hu0 = ndi.binary_fill_holes(cv2.morphologyEx(loch.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kh, kh))).astype(bool))
        ex = hu0 & anders & ~loch & np.isin(cl, [c_ for c_ in range(kk) if kl_flaech[c_] >= min_flaechig]) & (np.nan_to_num(t_wand - tief, nan=0.0) >= 0.75 * D); ex = cv2.morphologyEx(ex.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
        el, ne = ndi.label(ex); gr = np.bincount(el.ravel(), minlength=ne + 1) * px * px >= 0.005; gr[0] = False; ex = gr[el]; n_nach = int(ex.sum()); loch |= ex
    n_veto = 0
    if loch.any() and D > 0 and tiefe_veto > 0:                              # Bild sagt Oeffnung, Tiefe sagt Wand (Pfosten im Geisterbild verloren, Spiegelung): Tiefe gewinnt - beide muessen zustimmen
        veto = loch & t_ok & (np.nan_to_num(t_wand - tief, nan=0.0) < tiefe_veto * D); n_veto = int(veto.sum()); loch &= ~veto
        loch = cv2.morphologyEx(loch.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    el, ne = ndi.label(loch); gr = np.bincount(el.ravel(), minlength=ne + 1) * px * px >= min_m2; gr[0] = False; loch = gr[el]
    if glatt_m > 0 and loch.any():                                           # Umriss glaetten (Mehrheit im Fenster glatt_m): k-means-Pixelrauschen gab gezackte Kanten im Druckmodell
        kg = max(3, 2 * int(round(glatt_m / px / 2)) + 1); loch = cv2.medianBlur(loch.astype(np.uint8) * 255, kg) > 127
        el, ne = ndi.label(loch); gr = np.bincount(el.ravel(), minlength=ne + 1) * px * px >= min_m2; gr[0] = False; loch = gr[el]
    nur_tiefe = np.zeros_like(loch)
    if loch.any() and D > 0:                                                 # kein Foto sieht hin (verdeckt), aber die Tiefe zeigt Oeffnung, die an eine Bild-Oeffnung anschliesst: Umriss dort nur aus der Tiefe (grob, markiert)
        kand = ~bild_ok & ~vorn & (np.nan_to_num(t_wand - tief, nan=0.0) >= 0.75 * D); kand[:rb] = kand[-rb:] = False; kand[:, :rb] = kand[:, -rb:] = False
        nur_tiefe = ndi.binary_propagation(ndi.binary_dilation(loch, np.ones((3, 3), bool)) & kand, mask=kand); loch |= nur_tiefe
    mass = dict(nachgeprueft_m2=round(n_nach * px * px, 3), tiefe_veto_m2=round(n_veto * px * px, 3), nur_tiefe_m2=round(float(nur_tiefe.sum()) * px * px, 3), wandfarbe_lab=[round(float(x), 1) for x in wc], klassen_lab=np.round(zent / np.array([0.5, 1, 1]), 1).tolist(), klassen_stufe_m=[None if not np.isfinite(x) else round(x, 3) for x in kl_stufe],
                klassen_flaechig=[round(x, 3) for x in kl_flaech], wand_klasse=wand_kl, loch_klassen=[int(c_) for c_ in loch_kl], tiefe_wand=None if not np.isfinite(t_wand) else round(t_wand, 3), oeffnungstiefe_m=round(D, 3),
                regionen=regionen, n_loch=sum(r["loch"] for r in regionen), n_feld=sum(not r["loch"] for r in regionen))
    h = np.full((H, W_), w_flaeche, np.float32); klasse = np.zeros((H, W_), np.uint8)      # 0 Wand, 1 Loch, 2 Pfosten/Rahmen, 3 Gewaende, 4 Linie, 5 Feld (flach), 9 ohne Bild
    klasse[~gueltig] = 9; klasse[vorn] = 8; G_nt = nur_tiefe
    if loch.any():                                                           # Reste in der Oeffnung ohne Verbindung zum Zonenrand (Pfostenstueck, Spiegelung) wuerden frei im Fenster schweben -> Oeffnung
        fl_, nf_ = ndi.label(~loch); rand_l = set(np.unique(np.r_[fl_[0], fl_[-1], fl_[:, 0], fl_[:, -1]]).tolist()); frei = ~loch & ~np.isin(fl_, list(rand_l))
        mass["schwebend_zu_loch_m2"] = round(float(frei.sum()) * px * px, 4); loch |= frei
    if loch.any():
        kh = max(3, 2 * int(round(huelle_m / px / 2)) + 1); hu = cv2.morphologyEx(loch.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kh, kh))).astype(bool)
        hu = ndi.binary_fill_holes(hu); pf = hu & ~loch; dist = ndi.distance_transform_edt(~hu) * px
        lp = linien & (dist > 0.015) & (dist <= band_max); per = (hu & ~ndi.binary_erosion(hu)).sum()
        hist = np.bincount(np.clip((dist[lp] / 0.01).astype(int), 0, int(band_max / 0.01)), minlength=int(band_max / 0.01) + 1)
        b_g = None; hg_ = float(np.median(hist[len(hist) // 2:])); ueber = np.where(hist >= max(0.25 * per, 2.0 * hg_))[0]            # Aussenkante des Rahmenbands: letzte Abstandsstufe des ERSTEN zusammenhaengenden Laufs (Luecken <= 3 cm)
        if len(ueber):
            ende = ueber[0]
            for b_ in ueber[1:]:
                if b_ - ende > 3: break
                ende = b_
            b_g = (int(ende) + 1) * 0.01
        tp = tief[pf & t_ok]; pf_r = float(np.clip(t_wand - np.percentile(tp, 80), 0.0, D)) if (len(tp) > 20 and np.isfinite(t_wand)) else 0.0
        h[pf] = w_flaeche - pf_r; klasse[pf] = 2
        stufen_pos = []
        if b_g:                                                              # Profil aus den Kantenlinien: jede parallele Linie im Band (Spitze im Abstands-Histogramm) = eine Stufenkante
            hb = hist[: int(round(b_g / 0.01)) + 1].astype(float); hs = np.convolve(hb, [1, 1, 1], "same")
            stufen_pos = [(i_ + 1) * 0.01 for i_ in range(len(hb)) if hb[i_] >= max(0.25 * per, 2.0 * hg_) and hs[i_] >= hs[max(0, i_ - 1)] and hs[i_] >= hs[min(len(hb) - 1, i_ + 1)]]
            red = []
            for p_ in stufen_pos:                                            # Spitzen naeher als 2 cm = dieselbe Linie
                if red and p_ - red[-1] < 0.02: red[-1] = p_
                else: red.append(p_)
            stufen_pos = red or [b_g]; band = (dist > 0) & (dist <= b_g)
            if profil == "stufen":
                n_aussen = np.zeros(dist.shape, np.int32)
                for p_ in stufen_pos: n_aussen += (dist <= p_).astype(np.int32)
                h[band] = (w_flaeche - min(D, profil_max) * n_aussen[band] / (len(stufen_pos) + 1.0)).astype(np.float32)   # gleiche Stufenhoehe je Linie = ANNAHME, Summe = gemessene Oeffnungstiefe
            else: h[band] = (w_flaeche - min(D, profil_max) * (1.0 - dist[band] / b_g)).astype(np.float32)
            klasse[band] = 3
        mass["profil_stufen_m"] = stufen_pos; mass["profil"] = profil
        h[loch] = w_hinten; klasse[loch] = 1; klasse[G_nt] = 6
        mass.update(gewaende_breite_m=b_g, pfosten_rueck_m=round(pf_r, 3), huelle_m2=round(float(hu.sum()) * px * px, 3), loch_m2=round(float(loch.sum()) * px * px, 3),
                    linien_je_abstand=hist.tolist(), huelle_umfang_px=int(per))
    klasse[(klasse == 0) & linien] = 4
    for r in regionen:
        if not r["loch"]: x0, y0, x1, y1 = r["bbox_px"]; m_ = (lab_[y0:y1, x0:x1] > 0) & (klasse[y0:y1, x0:x1] == 0); klasse[y0:y1, x0:x1][m_] = 5
    return dict(h=h, loch=loch, klasse=klasse, mass=mass, dw=dw, anders=anders)


def terrassen(h, loch, zone, px, eps=1.0):
    """Hoehenbild mit wenigen Stufen (Wand, Gewaendestufen, Pfosten) als Terrassen: je Stufe L die Umrisse von {h >= L} (mit Innenringen). Statt eines
    1-cm-Gitters (330 000 Dreiecke je Fenster) baut teil() daraus Prismen - Kanten so scharf wie die Bildumrisse, wenige Dreiecke."""
    import cv2
    hh = np.round(h[~loch] / 0.002) * 0.002; lv = sorted(set(np.unique(hh).tolist())); T = []
    for L in lv:
        m = ((h >= L - 0.001) & ~loch).astype(np.uint8)
        if m.sum() < 4: continue
        cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE); P = []
        for c in cs:
            c = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(float)
            if len(c) < 3: continue
            P.append(np.c_[zone[0] + (c[:, 0] + 0.5) * px, zone[3] - (c[:, 1] + 0.5) * px].round(4).tolist())
        T.append([float(L), P])
    return T


def polygone(loch, zone, px, eps=1.0):
    """Lochumrisse (u, z) - aussen gegen den Uhrzeigersinn in (u, z)."""
    import cv2
    cs, _ = cv2.findContours(loch.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); P = []
    for c in cs:
        if len(c) < 4: continue
        c = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(float)
        if len(c) < 3: continue
        u = zone[0] + (c[:, 0] + 0.5) * px; z = zone[3] - (c[:, 1] + 0.5) * px; q = np.c_[u, z]
        if 0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]) < 0: q = q[::-1]
        P.append(q.round(4).tolist())
    return P


def bild_bericht(pfad, img, G, tief, px):
    import cv2
    H, W_ = img.shape[:2]; farben = {1: (40, 40, 220), 2: (60, 200, 60), 3: (220, 140, 30), 4: (0, 220, 255), 5: (200, 0, 200), 6: (120, 120, 255), 8: (160, 160, 160), 9: (60, 60, 60)}
    seg = img.copy() // 3
    for k, c in farben.items(): seg[G["klasse"] == k] = c
    h = G["h"].astype(np.float64); lx = np.gradient(h, px, axis=1); lz = np.gradient(h, px, axis=0); sch = (np.clip(0.6 - 0.6 * lx + 0.6 * lz, 0, 1) * 255).astype(np.uint8)
    sch = cv2.cvtColor(sch, cv2.COLOR_GRAY2BGR); sch[G["loch"]] = (30, 0, 0)
    tv = tief.copy(); ok = np.isfinite(tv); tb = np.zeros((H, W_, 3), np.uint8)
    if ok.any():
        lo, hi = np.percentile(tv[ok], 2), np.percentile(tv[ok], 98); tb = cv2.applyColorMap((np.clip((np.nan_to_num(tv, nan=lo) - lo) / max(hi - lo, 1e-3), 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS); tb[~ok] = 0
    s = max(1, int(round(500 / H))); teile = [cv2.resize(x, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST) for x in (img, seg, sch, tb)]
    for x, t_ in zip(teile, ("Wandbild", "Segmente: rot Loch (rosa: nur Tiefe), gruen Pfosten, blau Gewaende, gelb Linie, lila Farbfeld, hellgrau davor", "Gestalt (Schummerung)", "Tiefe (Eingang)")): cv2.putText(x, t_, (4, 14), 0, 0.42, (255, 255, 255), 1)
    cv2.imwrite(pfad, np.hstack([np.pad(x, ((0, 0), (0, 4), (0, 0))) for x in teile]), [cv2.IMWRITE_JPEG_QUALITY, 88])


# ---------------------------------------------------------------- 6. Generator-Teil (ohne cv2: laeuft auch in ~/.venvs/rcpark)
def teil(npz, loch_w=(-0.6, 0.6), loch_tiefe=None, sockel=0.0):
    """Hoehenbild-Platte (von w_hinten bis h) + Lochkoerper aus einer form_aus_wandbild-Datei. loch_tiefe = None: Loch durch (hohle Wand, Fenster = echtes Loch);
    Zahl: Loch nur bis so tief hinter der gemessenen Oeffnungsflaeche (massiver Koerper, z. B. Erker). Liefert (zusatz, abzug)."""
    from manifold3d import Manifold, CrossSection, FillRule
    Z = np.load(npz, allow_pickle=True); wh = float(Z["w_hinten"])
    a = Z["a"]; t = Z["t"]; n = Z["n"]; P = json.loads(str(Z["loecher_json"])); ab = None
    if loch_tiefe is not None: loch_w = (float(Z["w_flaeche"]) - float(Z["oeffnungstiefe_m"]) - loch_tiefe, loch_w[1])
    sp = (t[0] * n[1] - t[1] * n[0]) > 0; s = -1.0 if sp else 1.0
    M_ = [[s * t[0], 0.0, n[0], a[0]], [s * t[1], 0.0, n[1], a[1]], [0.0, 1.0, 0.0, 0.0]]
    if "terrassen_json" in Z.files:                                          # Terrassen: je Stufe ein Prisma von w_hinten bis zur Stufe (ueberlappend -> ein Koerper; aufeinander gesetzte Prismen blieben getrennte Teilnetze)
        Tr = json.loads(str(Z["terrassen_json"])); H, W_ = Z["rel"].shape; px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"])
        zus = None; prev = wh
        for L, polys in Tr:
            if L <= prev + 1e-4: continue
            cs = CrossSection([[[s * p[0], p[1]] for p in q] for q in polys], FillRule.EvenOdd)
            k = Manifold.extrude(cs, L - wh + sockel).translate((0, 0, wh)).transform(M_); zus = k if zus is None else zus + k; prev = L
    else:
        sys.path.insert(0, HIER); from relief_einsatz import koerper as relief_koerper
        zus = relief_koerper(npz, tiefe=-wh, sockel=sockel, rand_auslauf=False, trend=False)
    for q in P:
        q = np.array(q, float); q[:, 0] *= s
        if 0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]) < 0: q = q[::-1]
        k = Manifold.extrude(CrossSection([q.tolist()]), loch_w[1] - loch_w[0]).translate((0, 0, loch_w[0])).transform(M_)
        ab = k if ab is None else ab + k
    return zus, (ab if ab is not None else Manifold())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--wand", nargs=6, type=float, required=True, help="ax ay bx by aussen_x aussen_y")
    ap.add_argument("--zone", nargs=4, type=float, required=True, help="u0 u1 z0 z1 (u ab a Richtung b)"); ap.add_argument("--px", type=float, default=0.01)
    ap.add_argument("--ortho", help="DIR:fid - feines Fassadenbild"); ap.add_argument("--fotos", help="'auto' oder Komma-Liste: Wandbild direkt aus den Fotos"); ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--w", type=float, default=0.0, help="Ebene w vor der Wand (fuer --fotos, z. B. Erkerflaeche)"); ap.add_argument("--fein", type=int, default=0, help="1 = Feinausrichtung der Fotos (GPU)")
    ap.add_argument("--stl", help="Modell-STL fuer die Sichtbarkeit (--fotos): Verdecker vor der Zone fallen je Foto heraus")
    ap.add_argument("--tiefe", required=True, help="Relief (relief_einsatz-Format) fuer die Tiefe je Zelle"); ap.add_argument("--flaeche", help="Relief der gebauten Platte (Lage der Wandflaeche); sonst --w_flaeche")
    ap.add_argument("--flaeche_trend", type=int, default=0); ap.add_argument("--flaeche_sockel", type=float, default=0.005); ap.add_argument("--w_flaeche", type=float, default=None)
    ap.add_argument("--loch_stufe", type=float, default=0.04); ap.add_argument("--huelle", type=float, default=0.22); ap.add_argument("--w_hinten", type=float, default=-0.09)
    ap.add_argument("--ohne_tiefe", type=int, default=0); ap.add_argument("--profil", default="stufen", choices=["stufen", "schraege"]); ap.add_argument("--leer_offen", type=int, default=0, help="1 = Zellen ohne Tiefe (Netz sah durch: Tor) gelten als 1 m tief (ANNAHME)"); ap.add_argument("--aus", required=True); a = ap.parse_args()
    A, T, N = _ebene(a.wand[0:2], a.wand[2:4], a.wand[4:6]); zone = a.zone; px = a.px
    if a.ortho: img, g, qi = wandbild_ortho(a.ortho, A, T, zone, px)
    else: img, g, qi = wandbild_fotos(a.objekt, A, T, N, zone, px, w=a.w, k=a.k, fotos=None if a.fotos in (None, "auto") else a.fotos.split(","), fein=bool(a.fein), stl=a.stl)
    if img is None: print("ABBRUCH:", qi); return 3
    tief = tiefe_zone(a.tiefe, A, T, N, zone, px)
    if a.w_flaeche is not None: wf = a.w_flaeche
    else:
        fl = tiefe_zone(a.flaeche or a.tiefe, A, T, N, zone, px, trend=bool(a.flaeche_trend), sockel=a.flaeche_sockel); r_ = max(1, int(0.08 / px)); ring = np.zeros(fl.shape, bool); ring[:r_] = ring[-r_:] = True; ring[:, :r_] = ring[:, -r_:] = True
        wf = float(np.nanmedian(fl[ring])) if np.isfinite(fl[ring]).any() else 0.0
    G = gestalt(img, g, tief, wf, px, loch_stufe=a.loch_stufe, huelle_m=a.huelle, w_hinten=a.w_hinten, ohne_tiefe=bool(a.ohne_tiefe), profil=a.profil, leer_offen=bool(a.leer_offen)); P = polygone(G["loch"], zone, px)
    m = G["mass"]; m.update(w_flaeche=round(wf, 4), zone=zone, px=px, wandbild=qi, tiefe=a.tiefe, n_polygone=len(P),
                            annahmen=["Profil im Gewaendeband: Stufenkanten an den Bildlinien, gleiche Stufenhoehe je Linie (Summe = gemessene Oeffnungstiefe) bzw. Schraege", "Pfosten = Plateau (P80 der Tiefe)", "Wandzellen der Zone eben auf der gebauten Flaeche"])
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True)
    np.savez_compressed(a.aus, rel=G["h"].astype(np.float32), a=A, t=T, n=N, u0=zone[0], z0=zone[2], px=px, loch=G["loch"], klasse=G["klasse"], w_hinten=a.w_hinten,
                        w_flaeche=wf, oeffnungstiefe_m=m["oeffnungstiefe_m"], loecher_json=json.dumps(P), terrassen_json=json.dumps(terrassen(G["h"], G["loch"], zone, px)), bericht_json=json.dumps(m, default=float), oeffnung=np.zeros_like(G["loch"]))
    bild_bericht(a.aus[:-4] + ".jpg", img, G, tief, px); json.dump(m, open(a.aus[:-4] + ".json", "w"), indent=1, default=float)
    print(f"{os.path.basename(a.aus)}: {m['n_loch']} Oeffnungen ({m.get('loch_m2', 0)} m2, Tiefe {m['oeffnungstiefe_m']} m), {m['n_feld']} Farbfelder, Gewaende {m.get('gewaende_breite_m')} m, "
          f"Pfosten {m.get('pfosten_rueck_m')} m zurueck, Wandflaeche w {wf:.3f}, {len(P)} Lochumrisse -> {a.aus[:-4]}.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
