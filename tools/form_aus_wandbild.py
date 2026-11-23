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


def wandbild_fotos(objekt_json, a, t, n, zone, px, w=0.0, k=5, fotos=None, fein=False, min_cos=0.45, gpu_mb=1200, stl=None, min_sicht=0.3, max_rest=0.01, tiefe=None, konsens=True, k_extra=3):
    """Wandbild der Zone direkt aus den Fotos (Ebene w vor der Wand a-t-n): je Foto Projektion der Zellmitten, Wertung cos(Blick) / (m je Pixel),
    k beste, Median der Farben (Verdecker wandern -> fallen heraus). Keine Sichtbarkeitspruefung gegen das Modell (ANNAHME: die Zone ist frei sichtbar,
    z. B. eine Erkerflaeche vor der Wand); deshalb nur Fotos von VORN (cos >= min_cos).
    tiefe (HxW, w je Zelle, NaN = unbekannt; 18.11.2026): jede Zelle wird auf IHRER Tiefe projiziert statt auf der Ebene w ("wahres Orthofoto").
    Grund: Kaufhaus Fenster 1/3/5 - Wand (w 0,12) und Glas (w 0,0) auf einer Ebene projiziert gaben je Foto Parallaxe Tiefe x tan(Blickwinkel) = 3-11 cm,
    die Feinausrichtung (glattes Feld) kann den Sprung an der Lochkante nicht abbilden -> Restversatz 2-4 cm, Rueckfall Einzelfoto."""
    import cv2
    K = _kameras(objekt_json); uu, zz = gitter(zone, px); U, Z = np.meshgrid(uu, zz); H, W_ = U.shape
    Wz = np.full(U.shape, float(w), np.float32)
    if tiefe is not None and np.isfinite(tiefe).sum() > 20:
        Wz = np.where(np.isfinite(tiefe), tiefe, np.nanmedian(tiefe)).astype(np.float32); Wz = cv2.GaussianBlur(Wz, (0, 0), 0.02 / px)    # Netztiefe 5 cm: Sprungkanten nur weich
    X = np.c_[(a[0] + U * t[0] + Wz * n[0]).ravel(), (a[1] + U * t[1] + Wz * n[1]).ravel(), Z.ravel()]; mitte = X.mean(0); wert = []
    for nm, kk in K.items():
        if fotos and nm not in fotos: continue
        sys.path.insert(0, HIER); from kamera_standort import kamera_standort
        S = kamera_standort(kk)                                            # 23.11.2026: frueher standort_xyz mit Ersatz Ursprung -> 231 Kameras mit 'standort'/nur Pose standen im Ursprung
        if S is None: continue
        v = S - mitte; dist = np.linalg.norm(v)
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
        if len(stapel) >= (k + k_extra if (fein and konsens) else k): break
    if not stapel: return None, None, dict(fehler="kein Foto sieht die Zone von vorn")
    fa = None; modus = "median"; ak = None
    if fein and konsens and len(stapel) >= 3:                                # 18.11.2026: affiner Konsens vor der Feinausrichtung (Medoid, ECC affin) - Fotos mit falscher Pose fallen heraus
        sys.path.insert(0, HIER); import wand_feinausrichtung as WF
        mk = [(x.sum(2) > 0) for x in stapel]; st_, mk_, beh, ak = WF.affin_konsens(stapel, mk, px)
        beh = beh[:k]; stapel = st_[:k]; info = [info[i] for i in beh]
        for i_, j_ in enumerate(beh): info[i_]["cc_konsens"] = ak["cc_zum_medoid"][j_]
    if fein and len(stapel) >= 3:
        sys.path.insert(0, HIER); import wand_feinausrichtung as WF
        roh = list(stapel); info_roh = list(info); weg = []
        while True:                                                          # 18.11.2026: Foto mit dem groessten Restversatz > max_rest weglassen und neu ausrichten, solange >= 3 bleiben
            mk = [(x.sum(2) > 0) for x in roh]; stapel, mk, _, fa = WF.fein_ausrichten(roh, mk, px, gpu_mb=gpu_mb); info = info_roh
            rest = [None if (r_ or {}).get("median_zellen") is None else r_["median_zellen"] * px for r_ in (fa.get("nachher") or [None] * len(stapel))]
            rw = [9.0 if r_ is None else r_ for r_ in rest]
            if len(roh) <= 3 or max(rw) <= max_rest: break
            j_ = int(np.argmax(rw)); weg.append(info_roh[j_]["foto"]); roh = roh[:j_] + roh[j_ + 1:]; info_roh = info_roh[:j_] + info_roh[j_ + 1:]
        fa["weggelassen"] = weg
        gut = [i for i, r_ in enumerate(rest) if r_ is not None and r_ <= max_rest]
        for i, r_ in enumerate(rest): info[i]["restversatz_cm"] = None if r_ is None else round(100 * r_, 2)
        if len(gut) >= 3 or (len(gut) == 2 and ak is not None): stapel = [stapel[i] for i in gut]; info = [info[i] for i in gut]; modus = "median_ausgerichtet" if len(gut) >= 3 else "mittel_2_ausgerichtet (Konsens)"
        else:                                                                # Fotos lassen sich nicht deckungsgleich ziehen (Restversatz > max_rest): Median gaebe Geisterkanten -> das beste Einzelfoto, Luecken aus den anderen
            erst = stapel[0].copy(); leer = erst.sum(2) == 0
            if len(stapel) > 1:
                S2 = np.stack(stapel[1:]).astype(np.float32); S2[S2.sum(3) == 0] = np.nan
                import warnings
                with warnings.catch_warnings(): warnings.simplefilter("ignore"); m2 = np.nan_to_num(np.nanmedian(S2, 0)).astype(np.uint8)
                erst[leer] = m2[leer]
            return erst, erst.sum(2) > 0, dict(fotos=info, feinausrichtung=True, konsens=ak, modus="bestes_einzelfoto (Restversatz > %.1f cm)" % (100 * max_rest) + (" = Medoid" if ak else ""))
    S = np.stack(stapel).astype(np.float32); g = S.sum(3) > 0
    for i in range(1, len(S)):                                               # Belichtung je Foto an das beste angleichen (Verstaerkung je Kanal auf gemeinsam gesehenen Zellen) - sonst Flecken, wo der Median andere Fotos mischt
        ge = g[0] & g[i]
        if ge.sum() > 500: S[i] *= (np.median(S[0][ge], 0) / np.maximum(np.median(S[i][ge], 0), 1.0))[None, None, :]
    S = np.clip(S, 0, 255); S[~g] = np.nan
    import warnings
    with warnings.catch_warnings(): warnings.simplefilter("ignore"); med = np.nanmedian(S, 0)
    if len(stapel) == 1 and ak: modus = "einzelfoto_medoid (kein zweites Foto stimmt zu)"
    return np.nan_to_num(med).astype(np.uint8), g.any(0), dict(fotos=info, feinausrichtung=fa is not None, konsens=ak, modus=modus)


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


# ---------------------------------------------------------------- 4b. Kanten einrasten (18.11.2026)
def _lda_bild(img, maske, gueltig, px):
    """Skalares Kantenbild: Lab auf die Fisher-Achse 'innen (Oeffnung) -> aussen (Ring um die Oeffnung)' projiziert, 0 = innen, 1 = aussen.
    Keine Farbregel: die Achse kommt je Zone aus der Maske selbst."""
    import cv2
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32); k = max(1, int(round(0.02 / px))); m8 = maske.astype(np.uint8)
    inn = cv2.erode(m8, np.ones((2 * k + 1,) * 2, np.uint8)).astype(bool) & gueltig
    aus = cv2.dilate(m8, np.ones((4 * k + 1,) * 2, np.uint8)).astype(bool) & ~cv2.dilate(m8, np.ones((3, 3), np.uint8)).astype(bool) & gueltig
    if inn.sum() < 50 or aus.sum() < 50: return None, 0.0
    mi, mo = lab[inn].mean(0), lab[aus].mean(0); Sw = np.cov(lab[inn].T) + np.cov(lab[aus].T) + np.eye(3) * 1.0
    w = np.linalg.solve(Sw, mo - mi); sk = float((mo - mi) @ w)
    f = ((lab @ w) - float(mi @ w)) / max(sk, 1e-6); f = cv2.GaussianBlur(f.astype(np.float32), (0, 0), 0.6)
    return f, float(np.sqrt(max(sk, 0.0)))          # Trennguete (Mahalanobis-Abstand der Mittel)


def _glatt_ring(P, s):
    from scipy.ndimage import gaussian_filter1d
    return np.c_[gaussian_filter1d(P[:, 0], s, mode="wrap"), gaussian_filter1d(P[:, 1], s, mode="wrap")]


def _neu_abtasten(P, d):
    Q = np.vstack([P, P[:1]]); L = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]; s = np.arange(0, L[-1], d)
    return np.c_[np.interp(s, L, Q[:, 0]), np.interp(s, L, Q[:, 1])]


def _linie(Q, w):
    """gewichtete Total-Least-Squares-Gerade, robust (Huber, 3 Runden): Punkt, Richtung, RMS, max"""
    w = w.copy()
    for _ in range(3):
        c = (Q * w[:, None]).sum(0) / w.sum(); X = (Q - c) * np.sqrt(w)[:, None]; _, _, Vt = np.linalg.svd(X, full_matrices=False); d = Vt[0]
        r = (Q - c) @ np.array([-d[1], d[0]]); w = w * np.minimum(1.0, 1.0 / np.maximum(np.abs(r), 1e-3))
    r = (Q - c) @ np.array([-d[1], d[0]]); return c, d, float(np.sqrt(np.mean(r ** 2))), float(np.abs(r).max())


def kanten_einrasten(loch, img, gueltig, px, max_m=0.025, linie_rms=0.6, linie_max=1.8, min_linie_m=0.08, ecke_grad=35.0, ecke_m=0.06, hv_grad=10.0, hv_mehr=0.15, min_m2=0.012):
    """Lochumrisse an Bildkanten einrasten und regularisieren (generisch, Kernmethode: Gestalt aus Fotokanten).
    Je Oeffnung: Umriss (1 Zelle) -> fein abgetastet; je Punkt Suche entlang der Normalen (+-max_m) nach der staerksten Kante im Kantenbild (_lda_bild,
    Anstieg innen -> aussen, Subpixel per Parabel); Ecken = Richtungswechsel > ecke_grad; zwischen den Ecken: Gerade (TLS robust), wenn RMS <= linie_rms und
    max <= linie_max Zellen, sonst gerade Endstuecke abspalten und den Rest als glatte Kurve (Glaettungs-Spline mit Kantenstuetze) - Boegen werden Kurven.
    Geraden nahe waagrecht/senkrecht (<= hv_grad) werden exakt waagrecht/senkrecht, wenn der RMS dadurch hoechstens um hv_mehr Zellen steigt (bevorzugt, nicht erzwungen).
    Pfosten = Wand zwischen zwei Loechern: beide Kanten einzeln eingerastet -> Breite gemessen, nicht vereinheitlicht.
    Rueckgabe: Liste Polygone (x, y in Zellen, Subpixel), Bericht."""
    import cv2
    from scipy import ndimage as ndi
    from scipy.ndimage import map_coordinates
    from scipy.interpolate import splprep, splev
    f, guete = _lda_bild(img, loch, gueltig, px); R = max_m / px
    if f is not None: gxf = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3) / 8.0; gyf = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3) / 8.0; ds = 0.5; S_ = np.arange(-R, R + 1e-6, 0.25)
    lab_, n_ = ndi.label(loch); polys = []; ber = dict(trenn_guete=round(guete, 2), loecher=[])
    for k in range(1, n_ + 1):
        m = lab_ == k
        if m.sum() * px * px < min_m2: continue
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); c = max(cs, key=len).reshape(-1, 2).astype(float)
        if len(c) < 8: continue
        P = _glatt_ring(_neu_abtasten(c, ds), 2.0); Ps = _glatt_ring(P, 4.0); T_ = np.gradient(Ps, axis=0); T_ /= np.maximum(np.linalg.norm(T_, axis=1, keepdims=True), 1e-9)
        N_ = np.c_[T_[:, 1], -T_[:, 0]]
        tst = P + 1.5 * N_; inn = map_coordinates(m.astype(np.float32), [tst[:, 1], tst[:, 0]], order=0)
        if inn.mean() > 0.5: N_ = -N_                                       # Normale zeigt nach aussen
        P = P + 0.5 * N_; P0 = P.copy()                                      # Zellmitte -> Zellgrenze; P0 = Grobform (Geradentest, Ecken), P = eingerastet (Kurven)
        s_ok = np.zeros(len(P), bool); s_st = np.zeros(len(P))
        if f is not None:
            X = P[:, None, :] + S_[None, :, None] * N_[:, None, :]; pr = map_coordinates(f, [X[..., 1], X[..., 0]], order=1, mode="nearest")
            dv = np.gradient(pr, 0.25, axis=1) * np.exp(-0.5 * (S_ / (0.8 * R)) ** 2)[None, :]; j = np.argmax(dv, 1); st = dv[np.arange(len(P)), j]
            jj = np.clip(j, 1, len(S_) - 2); a_ = dv[np.arange(len(P)), jj - 1]; b_ = dv[np.arange(len(P)), jj + 1]; c_ = dv[np.arange(len(P)), jj]
            den = a_ - 2 * c_ + b_; off = np.where(np.abs(den) > 1e-9, 0.5 * (a_ - b_) / den, 0.0); s_ = S_[jj] + np.clip(off, -0.5, 0.5) * 0.25
            s_ok = (st >= 0.18) & (j > 0) & (j < len(S_) - 1); s_ = ndi.median_filter(np.where(s_ok, s_, 0.0), 9, mode="wrap"); s_st = np.where(s_ok, st, 0.0)
            P = P + np.where(s_ok, s_, 0.0)[:, None] * N_
        Wt = 0.05 + np.clip(s_st, 0, 1.5)
        # Ecken: Richtungswechsel ueber +-2 Zellen
        kk = int(round(ecke_m / px / ds)); Pg = _glatt_ring(P0, 2.0); a1 = np.roll(Pg, kk, 0); a2 = np.roll(Pg, -kk, 0); v1 = Pg - a1; v2 = a2 - Pg
        ang = np.degrees(np.abs(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1))))
        nP = len(P); ec = [i for i in range(nP) if ang[i] > ecke_grad and ang[i] >= ang[np.arange(i - kk, i + kk + 1) % nP].max()]
        ec = sorted(set(ec)); red = []
        for i in ec:
            if red and i - red[-1] < kk: continue
            red.append(i)
        ec = red if len(red) >= 2 else [0, len(P) // 2]
        stuecke = [];  nP = len(P)
        for a, b in zip(ec, ec[1:] + [ec[0] + nP]):
            idx = np.arange(a, b + 1) % nP; stuecke.append(idx)
        teile = []; info = dict(geraden=0, kurven=0, hv=0, ohne_kante=0, verschiebung_px=[], rms_gerade=[], rms_kurve=[], stuetze=round(float(s_ok.mean()), 3))
        def gerade(idx):                                                     # Gerade als GANZES an die Bildkante schieben/drehen (integrierte Kantenstaerke entlang der Strecke, robust gegen Bleiruten-Textur)
            c0, d0, rms, mx = _linie(P0[idx], np.ones(len(idx))); nn = np.array([-d0[1], d0[0]])
            if nn @ N_[idx].mean(0) < 0: nn = -nn
            t = (P0[idx] - c0) @ d0; ta, tb = float(t.min()), float(t.max())
            if f is None or tb - ta < 3: return ("g", c0, d0, rms, 0.0)
            tt = np.linspace(ta + 1.0, tb - 1.0, max(5, int((tb - ta) * 2))); a0 = np.arctan2(d0[1], d0[0]); kand = [a0 + np.radians(x) for x in (-2, -1, 0, 1, 2)]
            ang_ = np.degrees(a0) % 180; ziel = min([0, 90, 180], key=lambda z: abs(ang_ - z)); hv = None
            if abs(ang_ - ziel) <= hv_grad: hv = np.radians(ziel) if abs(np.radians(ziel) - a0 % np.pi) < 0.5 else np.radians(ziel) + np.pi; kand.append(hv)
            pri = np.exp(-0.5 * (S_ / (1.5 * R)) ** 2); erg = []
            for aw in kand:
                d_ = np.array([np.cos(aw), np.sin(aw)]); n_ = np.array([-d_[1], d_[0]])
                if n_ @ nn < 0: n_ = -n_
                X = c0[None, None, :] + tt[None, :, None] * d_[None, None, :] + S_[:, None, None] * n_[None, None, :]
                g = map_coordinates(gxf, [X[..., 1], X[..., 0]], order=1, mode="nearest") * n_[0] + map_coordinates(gyf, [X[..., 1], X[..., 0]], order=1, mode="nearest") * n_[1]
                sc = g.mean(1) * pri; j = int(np.argmax(sc)); erg.append((float(sc[j]), aw, float(S_[j]), d_, n_))
            bst = max(erg[:5], key=lambda e: e[0])
            if hv is not None and erg[-1][0] >= 0.85 * bst[0]: bst = erg[-1]; info["hv"] += 1
            if bst[0] < 0.06: info["ohne_kante"] += 1; return ("g", c0, d0, rms, bst[0])
            info["verschiebung_px"].append(abs(bst[2])); return ("g", c0 + bst[2] * bst[4], bst[3], rms, bst[0])
        for idx in stuecke:
            Lm = len(idx) * ds * px
            if len(idx) < 4: continue
            c0, d0, rms, mx = _linie(P0[idx], np.ones(len(idx)))
            if rms <= linie_rms and mx <= linie_max: t_ = gerade(idx); teile.append((t_, idx)); continue
            tq = (P0[idx] - c0) @ d0; rq = (P0[idx] - c0) @ np.array([-d0[1], d0[0]])            # nur wellig, nicht gekruemmt (Pfeilhoehe der Parabel <= 1,2 Zellen): Gerade, die Kante legt gerade()
            if len(idx) >= 8:
                cq = np.polyfit(tq, rq, 2); pfeil = abs(cq[0]) * ((tq.max() - tq.min()) / 2) ** 2
                if pfeil <= 1.2 and np.abs(rq).max() <= 2.0 and np.abs(rq - np.polyval(cq, tq)).max() <= 2.0: t_ = gerade(idx); teile.append((t_, idx)); continue
            # gerade Endstuecke abspalten
            nmin = int(round(min_linie_m / px / ds)); i0, i1 = 0, len(idx)
            for von_vorn in (True, False):
                best = 0
                for L_ in range(nmin, len(idx) - nmin, 2):
                    sub = idx[:L_] if von_vorn else idx[len(idx) - L_:]
                    _, _, r_, m_ = _linie(P0[sub], np.ones(len(sub)))
                    if r_ <= linie_rms * 0.8 and m_ <= linie_max: best = L_
                    else: break
                if best: 
                    if von_vorn: i0 = best
                    else: i1 = len(idx) - best
            if i1 - i0 < 6: t_ = gerade(idx); teile.append((t_, idx)); continue
            vor = [(gerade(idx[:i0 + 1]), idx[:i0 + 1])] if i0 else []; nach = [(gerade(idx[i1 - 1:]), idx[i1 - 1:])] if i1 < len(idx) else []
            mid = idx[i0:i1]; Q = P[mid]
            try:
                tck, uu = splprep([Q[:, 0], Q[:, 1]], w=np.sqrt(Wt[mid] / Wt[mid].max()) + 0.2, s=len(Q) * 0.35 ** 2, k=3); ug = np.linspace(0, 1, max(8, len(Q)))
                K_ = np.array(splev(ug, tck)).T; Kp = np.array(splev(uu, tck)).T; rms_k = float(np.sqrt(np.mean(np.sum((Kp - Q) ** 2, 1))))
            except Exception: K_ = Q; rms_k = 0.0
            teile += vor + [(("k", K_, rms_k, float(np.mean(s_st[mid]))), mid)] + nach
        i = 0                                                                # benachbarte Geraden fast gleicher Richtung (< 8 Grad) zu einer zusammenfassen, wenn die gemeinsame Gerade passt
        while len(teile) > 2 and i < len(teile):
            j = (i + 1) % len(teile); (ta, ia), (tb, ib) = teile[i], teile[j]
            if ta[0] == "g" and tb[0] == "g" and abs(ta[2] @ np.array([-tb[2][1], tb[2][0]])) < np.sin(np.radians(8)):
                idx = np.r_[ia, ib[1:]] if j > i else np.r_[ia, ib[1:]]
                c0, d0, rms, mx = _linie(P0[idx], np.ones(len(idx)))
                if rms <= linie_rms and mx <= linie_max:
                    teile[i] = (gerade(idx), idx); del teile[j]
                    if j < i: i -= 1
                    continue
            i += 1
        geaendert = True                                                     # kurze Fase (< min_linie_m) zwischen zwei Geraden = abgerundete Ecke der Grobform: weg, die Nachbarn schneiden sich
        while geaendert and len(teile) > 3:
            geaendert = False
            for i in range(len(teile)):
                (t_, idx) = teile[i]; (ta, _), (tb, _) = teile[i - 1], teile[(i + 1) % len(teile)]
                if ta[0] != "g" or tb[0] != "g": continue
                if abs(ta[2] @ np.array([-tb[2][1], tb[2][0]])) < np.sin(np.radians(30)): continue
                if t_[0] == "k":                                             # Kurve zwischen zwei Geraden ohne eigene Bildkante (Stuetze < halbe Nachbarn) = gerundete Ecke der Grobform
                    if len(idx) * ds * px < 0.4 and t_[3] < 0.15: del teile[i]; geaendert = True; break
                    continue
                kurz = len(idx) * ds * px < min_linie_m * 0.75; schwach = len(idx) * ds * px < 0.4 and t_[4] < 0.15 and t_[4] < 0.5 * min(ta[4], tb[4])     # Fase ohne eigene Bildkante
                if not (kurz or schwach): continue
                if abs(ta[2] @ np.array([-tb[2][1], tb[2][0]])) < np.sin(np.radians(30)): continue
                del teile[i]; geaendert = True; break
        info["teile"] = [[t_[0], round(len(idx) * ds * px, 3), round(t_[4] if t_[0] == "g" else t_[3], 3), round(float(np.degrees(np.arctan2(t_[2][1], t_[2][0]))), 1) if t_[0] == "g" else None] for t_, idx in teile]
        # zusammensetzen
        pts = []
        for i, (t_, idx) in enumerate(teile):
            if t_[0] == "g":
                c0, d0 = t_[1], t_[2]; info["geraden"] += 1; info["rms_gerade"].append(t_[3])
                def schnitt(tn, ende):
                    if tn[0] != "g": return None
                    c1, d1 = tn[1], tn[2]; A_ = np.array([d0, -d1]).T
                    if abs(np.linalg.det(A_)) < np.sin(np.radians(10)): return None
                    tt = np.linalg.solve(A_, c1 - c0); q = c0 + tt[0] * d0
                    return q if np.hypot(*(q - ende)) <= 0.08 / px else None
                pa = c0 + ((P[idx[0]] - c0) @ d0) * d0; pb = c0 + ((P[idx[-1]] - c0) @ d0) * d0
                qa = schnitt(teile[i - 1][0], P[idx[0]]); qb = schnitt(teile[(i + 1) % len(teile)][0], P[idx[-1]])
                pts += [qa if qa is not None else pa, qb if qb is not None else pb]
            else:
                info["kurven"] += 1; info["rms_kurve"].append(t_[2]); pts += list(t_[1])
        Pn = np.array(pts)
        if len(Pn) >= 3: polys.append(Pn)
        info["rms_gerade_px"] = round(float(np.median(info.pop("rms_gerade"))), 3) if info["geraden"] else None
        info["rms_kurve_px"] = round(float(np.median(info.pop("rms_kurve"))), 3) if info["kurven"] else None
        vs = info.pop("verschiebung_px"); info["verschiebung_median_px"] = round(float(np.median(vs)), 2) if vs else None
        info.pop("rms_gerade", None); info.pop("rms_kurve", None); ber["loecher"].append(info)
    return polys, ber


def polys_raster(polys, shape, fak):
    """Polygone (Zellen, Subpixel) -> Maske im feinen Raster (fak x feiner)"""
    import cv2
    H, W_ = shape; m = np.zeros((H * fak, W_ * fak), np.uint8)
    for q in polys:
        qq = ((q + 0.5) * fak - 0.5) * 16; cv2.fillPoly(m, [np.round(qq).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)


# ---------------------------------------------------------------- 3.-5. Segmentierung und Gestalt
def gestalt(img, gueltig, tief, w_flaeche, px, rand=0.08, loch_stufe=0.04, min_m2=0.012, linie_m=0.03, huelle_m=0.22, band_max=0.30, w_hinten=-0.09, ohne_tiefe=False, klassen=6, vorn_m=0.06, schliessen_m=0.01, profil="stufen", rand_loch=0.03, tiefe_veto=0.25, glatt_m=0.03, klasse_anteil=0.75, flaechig_m=0.05, min_flaechig=0.35, leer_offen=False, profil_max=0.25, fak=4, tiefe_fuellen=True, gewaende_aus="kanten", feld_fuellen=True):
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
    cv2.setRNGSeed(12345)                                                    # k-means reproduzierbar (18.11.2026: zwei Laeufe gaben Oeffnungstiefe 0,19 / 0,12 m)
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
    gL = cv2.GaussianBlur(lab[..., 0], (0, 0), 0.7); gm_ = np.hypot(cv2.Sobel(gL, cv2.CV_32F, 1, 0), cv2.Sobel(gL, cv2.CV_32F, 0, 1))      # Bildkanten (Helligkeit) fuer das Gewaendeprofil:
    kante = gm_ > (np.percentile(gm_[gueltig], 80) if gueltig.any() else 1e9)       # unabhaengig davon, in wie viele Farbklassen die Wand zerfaellt (18.11.: Klasse 'Linie' flutete die Wand -> kein Gewaende)
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
    kb = None
    if fak > 1 and loch.any():                                               # 18.11.2026: Lochkanten an Bildkanten einrasten (Geraden/Kurven), dann alles im feinen Raster (px/fak)
        kr = max(3, 2 * int(round(0.02 / px)) + 1); el2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kr, kr))   # Grobform: Kerben (Bleiruten, Spiegelung) schliessen, Spitzen weg - Durchmesser 4-5 cm < Pfostenbreite
        el3 = np.ones((3, 3), np.uint8)                                      # Schliessen nur 2 cm: Kaempfer/Pfosten (4-5 cm) duerfen nicht zuwachsen
        lc = cv2.morphologyEx(cv2.morphologyEx(loch.astype(np.uint8), cv2.MORPH_CLOSE, el3), cv2.MORPH_OPEN, el2).astype(bool); lg = lc; n_tief = 0
        f0_, _ = _lda_bild(img, lc, gueltig, px); n_rahmenlinien = 0; n_feld = 0
        if f0_ is not None:                                                  # Rahmenlinien (linienhafte Farbklasse, Farbe wie Rahmen/Wand) trennen immer: nie Oeffnung
            lin_kl = [c_ for c_ in range(kk) if c_ != wand_kl and kl_flaech[c_] < min_flaechig]
            rahmen = (cv2.GaussianBlur(f0_, (0, 0), 0.7) >= 0.85) & np.isin(cl, lin_kl); n_rahmenlinien = 0
            from skimage.feature import hessian_matrix, hessian_matrix_eigvals  # + lange gerade GRATE der Rahmenfarbe (Pfosten, Kaempfer): Hessian-Grat auf f, LSD, >= 25 cm, Gratstaerke >= 0,25
            ev_ = hessian_matrix_eigvals(hessian_matrix(cv2.GaussianBlur(f0_, (0, 0), 1.0).astype(np.float64), sigma=1.5, order="rc", use_gaussian_derivatives=True)); rg_ = np.maximum(-ev_[1], 0)
            rg_ = rg_ / max(float(np.percentile(rg_[gueltig], 99.5)) if gueltig.any() else 1.0, 1e-6); LS_ = cv2.createLineSegmentDetector().detect((np.clip(rg_, 0, 1) * 255).astype(np.uint8))[0]
            for x0, y0, x1, y1 in ([] if LS_ is None else LS_.reshape(-1, 4)):
                ln_ = float(np.hypot(x1 - x0, y1 - y0))
                if ln_ * px < 0.25: continue
                mm_ = np.linspace(0, 1, int(ln_) + 1); ys_ = np.clip(np.round(y0 + mm_ * (y1 - y0)).astype(int), 0, H - 1); xs_ = np.clip(np.round(x0 + mm_ * (x1 - x0)).astype(int), 0, W_ - 1)
                if float(np.median(rg_[ys_, xs_])) < 0.25: continue
                lm_ = np.zeros((H, W_), np.uint8); cv2.line(lm_, (int(round(x0)), int(round(y0))), (int(round(x1)), int(round(y1))), 1, 2); rahmen |= lm_.astype(bool); n_rahmenlinien += 1
            lc = cv2.morphologyEx((lc & ~rahmen).astype(np.uint8), cv2.MORPH_OPEN, el3).astype(bool); lg = lc.copy()
            if feld_fuellen:                                                 # Feld zwischen Rahmenlinien: Spiegelung/Bleiruten lassen Stuecke des Lichts aussehen wie Wand. Gebiet, das von Rahmengraten
                kh2 = max(3, 2 * int(round(huelle_m / px / 2)) + 1)          # (gerade LSD-Linien + starke Grate) umschlossen ist und ueberwiegend Oeffnung ist, wird ganz Oeffnung (ohne Rahmenfarbe f >= 0,85)
                hu2 = ndi.binary_fill_holes(cv2.morphologyEx(lc.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kh2, kh2))).astype(bool))
                sperre = cv2.dilate((rahmen | (rg_ > 0.4)).astype(np.uint8), el3).astype(bool); fl_, nf_ = ndi.label(hu2 & ~sperre & gueltig); fsx = cv2.GaussianBlur(f0_, (0, 0), 1.0)
                for k_, sl_ in enumerate(ndi.find_objects(fl_), 1):
                    if sl_ is None: continue
                    rk_ = fl_[sl_] == k_
                    if rk_.sum() * px * px >= 0.02 and lc[sl_][rk_].mean() >= 0.5: lg[sl_] |= rk_ & (fsx[sl_] < 0.85)
                n_feld = int((lg & ~lc).sum()); lg = cv2.morphologyEx(lg.astype(np.uint8), cv2.MORPH_OPEN, el3).astype(bool); lc = lg
        if D > 0 and tiefe_fuellen:                                          # Oeffnung wachsen lassen, wo das Bild sie zerstueckelt (Bleiruten, Spiegelung): Zelle tief (>= 0,8 D) oder (Farbe wie Oeffnung und >= 0,4 D), in der Huelle
            kh = max(3, 2 * int(round(huelle_m / px / 2)) + 1); hu_ = ndi.binary_fill_holes(cv2.morphologyEx(loch.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kh, kh))).astype(bool))
            from skimage.segmentation import watershed
            f_, _ = _lda_bild(img, lc, gueltig, px)                          # Farbe der Oeffnung (Fisher-Achse innen/aussen, je Zone gelernt): 0 = wie die Oeffnung, 1 = wie Rahmen/Wand
            st_ = np.nan_to_num(t_wand - tief, nan=0.0); fs_ = cv2.GaussianBlur(f_, (0, 0), 1.0) if f_ is not None else np.zeros(loch.shape, np.float32)
            if D >= 0.3: hu_ = hu_ | ndi.binary_fill_holes(st_ >= 0.95 * D)      # Tor: die scharfe Tiefe begrenzt mit
            tiefz = hu_ & bild_ok & ~vorn & (st_ >= 0.8 * D) & ((fs_ < 0.7) | ((D >= 0.3) & (st_ >= 0.95 * D)))      # grosse Tiefenstufe (>= 30 cm: Tor, Durchfahrt) ist im Netz scharf -> Tiefe allein reicht
            farbz = hu_ & bild_ok & ~vorn & (fs_ < 0.8) & (st_ >= 0.4 * D)
            ml_, _ = ndi.label(lc)                                           # Wasserscheide auf der Farbe f: jede Oeffnung waechst nur bis zur Rahmenlinie (Pfosten, Kaempfer) - Nachbarlichter verschmelzen nicht
            ws = watershed(fs_ if f_ is not None else -st_, markers=ml_, mask=lc | tiefz | farbz, watershed_line=True)
            lg = cv2.morphologyEx((ws > 0).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool); n_tief = int((lg & ~lc).sum())
            if os.environ.get("FORM_DEBUG"): np.savez_compressed(os.environ["FORM_DEBUG"], f=fs_, st=st_, loch=loch, lc=lc, rahmen=rahmen if f0_ is not None else lc, hu=hu_, tiefz=tiefz, farbz=farbz, ws=ws, D=D, cl=cl)
        lg = ndi.binary_fill_holes(lg) & ~(ndi.binary_fill_holes(lg) & ~lg & (lambda l_: (np.bincount(l_[0].ravel(), minlength=l_[1] + 1) * px * px > 0.02)[l_[0]])(ndi.label(ndi.binary_fill_holes(lg) & ~lg)))
        n_kerbe = 0; fk_, _ = _lda_bild(img, lg, gueltig, px)               # Kerben: Flaeche zwischen Oeffnung und ihrer konvexen Huelle, die nach Farbe wie die Oeffnung aussieht (f < 0,6), gehoert dazu;
        if fk_ is not None:                                                  # echte Einbuchtungen (Kielbogen, Vorhangbogen) sind Rahmen/Wand (f ~ 1) und bleiben
            ll_, nl_ = ndi.label(lg); lg2 = lg.copy()
            for k_ in range(1, nl_ + 1):
                ck = ll_ == k_; cs_, _ = cv2.findContours(ck.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                hk = np.zeros_like(ck, np.uint8); cv2.fillPoly(hk, [cv2.convexHull(np.vstack(cs_))], 1)
                andere = cv2.dilate((lg & ~ck).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)     # nie bis an eine Nachbaroeffnung (sonst verschmelzen Lichter ueber Pfosten/Kaempfer)
                de = hk.astype(bool) & ~ck & ~lg & gueltig; dl_, nd_ = ndi.label(de)
                for j_ in range(1, nd_ + 1):
                    if (andere & (dl_ == j_)).any(): de[dl_ == j_] = False
                dl_, nd_ = ndi.label(de)
                for j_ in range(1, nd_ + 1):
                    dj = dl_ == j_
                    if dj.sum() * px * px >= 0.0004 and float(np.median(fk_[dj])) < 0.6: lg2 |= dj; n_kerbe += int(dj.sum())
            lg = cv2.morphologyEx(lg2.astype(np.uint8), cv2.MORPH_OPEN, el2).astype(bool)
            from skimage.segmentation import watershed                       # Lichter, die ueber einen Hals (Schatten am Pfosten) zusammenhaengen, an der Rahmenlinie trennen: Kerne = Erosion 4 cm, Wasserscheide auf f
            ke = max(3, 2 * int(round(0.04 / px)) + 1); kern = cv2.erode(lg.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ke, ke))).astype(bool)
            km_, nk_ = ndi.label(kern); gr_ = np.bincount(km_.ravel(), minlength=nk_ + 1) * px * px >= 0.01; gr_[0] = False; km_ = np.where(gr_[km_], km_, 0)
            if km_.max() > 0:
                wsl = watershed(cv2.GaussianBlur(fk_, (0, 0), 1.0), markers=km_, mask=lg, watershed_line=True); lg = cv2.morphologyEx((wsl > 0).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
        polys_px, kb = kanten_einrasten(lg, img, gueltig, px)
        if os.environ.get("FORM_DEBUG"): np.savez_compressed(os.environ["FORM_DEBUG"] + "_k.npz", lg=lg, img=img, polys=np.array(json.dumps([q.tolist() for q in polys_px])))
        up = lambda a_: np.repeat(np.repeat(a_, fak, 0), fak, 1)
        loch = polys_raster(polys_px, (H, W_), fak) & up(gueltig | ~bild_ok)
        gueltig, bild_ok, vorn, linien, lab_, kante = up(gueltig), up(bild_ok), up(vorn), up(linien), up(lab_), up(kante)
        tn = np.isnan(tief); tief = cv2.resize(np.nan_to_num(tief, nan=float(np.nanmedian(tief)) if np.isfinite(tief).any() else 0.0), (W_ * fak, H * fak), interpolation=cv2.INTER_LINEAR)
        tief[up(tn)] = np.nan; t_ok = np.isfinite(tief)
        for r in regionen: r["bbox_px"] = [v * fak for v in r["bbox_px"]]
        px = px / fak; H, W_ = loch.shape; rb = rb * fak
    nur_tiefe = np.zeros_like(loch)
    if loch.any() and D > 0:                                                 # kein Foto sieht hin (verdeckt), aber die Tiefe zeigt Oeffnung, die an eine Bild-Oeffnung anschliesst: Umriss dort nur aus der Tiefe (grob, markiert)
        kand = ~bild_ok & ~vorn & (np.nan_to_num(t_wand - tief, nan=0.0) >= 0.75 * D); kand[:rb] = kand[-rb:] = False; kand[:, :rb] = kand[:, -rb:] = False
        spalten = np.zeros(loch.shape[1], bool); ll2, nl2 = ndi.label(loch)             # 18.11.2026: nur-Tiefe-Fortsetzung nur senkrecht unter/ueber einer Bild-Oeffnung (Spaltenbereich ihres Unterrands +-0), sonst schraege Zipfel ins Brustungsfeld
        for sl2 in ndi.find_objects(ll2):
            if sl2 is None: continue
            unten = np.where(loch[sl2].any(0) & loch[sl2][-max(1, int(0.03 / px)):].any(0))[0]
            if len(unten): spalten[sl2[1].start + unten.min(): sl2[1].start + unten.max() + 1] = True
        kand &= spalten[None, :]
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
        lp = (kante if gewaende_aus == "kanten" else linien) & (dist > 0.015) & (dist <= band_max); fz = max(1, int(round(0.01 / px))); per = (hu & ~ndi.binary_erosion(hu)).sum() / fz      # Zaehlungen auf 1-cm-Zellen bezogen (feines Raster)
        hist = np.bincount(np.clip((dist[lp] / 0.01).astype(int), 0, int(band_max / 0.01)), minlength=int(band_max / 0.01) + 1) / float(fz * fz)
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
        if np.isfinite(t_wand):                                              # Gegenprobe Profil aus der Tiefe (nur Bericht): Rueckstand je cm Abstand von der Huelle nach aussen (Netz 5 cm glaettet - Band 4-10 cm ist darunter kaum aufloesbar)
            mass["profil_tiefe_je_cm"] = [None if not (t_ok & (dist > d0) & (dist <= d0 + 0.01)).sum() > 20 else round(float(t_wand - np.median(tief[t_ok & (dist > d0) & (dist <= d0 + 0.01)])), 3) for d0 in np.arange(0, 0.15, 0.01)]
        h[loch] = w_hinten; klasse[loch] = 1; klasse[G_nt] = 6
        mass.update(gewaende_breite_m=b_g, pfosten_rueck_m=round(pf_r, 3), huelle_m2=round(float(hu.sum()) * px * px, 3), loch_m2=round(float(loch.sum()) * px * px, 3),
                    linien_je_abstand=hist.tolist(), huelle_umfang_px=int(per))
    klasse[(klasse == 0) & linien] = 4
    for r in regionen:
        if not r["loch"]: x0, y0, x1, y1 = r["bbox_px"]; m_ = (lab_[y0:y1, x0:x1] > 0) & (klasse[y0:y1, x0:x1] == 0); klasse[y0:y1, x0:x1][m_] = 5
    if kb is not None: kb["tiefe_gefuellt_m2"] = round(n_tief * (px * fak) ** 2, 4); kb["kerben_gefuellt_m2"] = round(n_kerbe * (px * fak) ** 2, 4); kb["rahmenlinien"] = n_rahmenlinien; kb["feld_gefuellt_m2"] = round(n_feld * (px * fak) ** 2, 4); mass["kanten"] = kb; mass["raster_fein_px"] = px
    return dict(h=h, loch=loch, klasse=klasse, mass=mass, dw=dw, anders=anders, px=px)


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
    ol = teile[0].copy(); cs, _ = cv2.findContours(cv2.resize(G["loch"].astype(np.uint8), None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ol, cs, -1, (0, 255, 0), max(1, ol.shape[0] // 700)); teile.insert(1, ol)          # Lochumriss auf dem Wandbild (Kantenlage pruefen)
    for x, t_ in zip(teile, ("Wandbild", "Lochumriss auf Wandbild", "Segmente: rot Loch (rosa: nur Tiefe), gruen Pfosten, blau Gewaende, gelb Linie, lila Farbfeld, hellgrau davor", "Gestalt (Schummerung)", "Tiefe (Eingang)")): cv2.putText(x, t_, (4, 14), 0, 0.42, (255, 255, 255), 1)
    B = np.hstack([np.pad(x, ((0, 0), (0, 4), (0, 0))) for x in teile])
    if B.shape[0] > 700: B = cv2.resize(B, None, fx=700.0 / B.shape[0], fy=700.0 / B.shape[0], interpolation=cv2.INTER_AREA)
    cv2.imwrite(pfad, B, [cv2.IMWRITE_JPEG_QUALITY, 88])


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
    ap.add_argument("--fak", type=int, default=4, help="Kanten einrasten + feines Raster px/fak (0/1 = aus, Stand 17.11.)")
    ap.add_argument("--konsens", type=int, default=1, help="1 = (--fotos --fein 1) affiner Konsens vor der Feinausrichtung: Medoid-Foto, ECC affin, Fotos mit cc < 0,5 fallen heraus")
    ap.add_argument("--proj_tiefe", type=int, default=0, help="(Versuch 18.11., Standard aus: Netztiefe 5 cm verbiegt Rahmen in Schraegfotos - wellige Doppelkanten; der affine Konsens holt den Versatz besser) 1 = (--fotos) jede Zelle auf ihrer Tiefe aus --tiefe projizieren statt auf der Ebene --w (Parallaxe Wand/Glas)")
    ap.add_argument("--tiefe", required=True, help="Relief (relief_einsatz-Format) fuer die Tiefe je Zelle"); ap.add_argument("--flaeche", help="Relief der gebauten Platte (Lage der Wandflaeche); sonst --w_flaeche")
    ap.add_argument("--flaeche_trend", type=int, default=0); ap.add_argument("--flaeche_sockel", type=float, default=0.005); ap.add_argument("--w_flaeche", type=float, default=None)
    ap.add_argument("--loch_stufe", type=float, default=0.04); ap.add_argument("--huelle", type=float, default=0.12); ap.add_argument("--w_hinten", type=float, default=-0.09)
    ap.add_argument("--ohne_tiefe", type=int, default=0); ap.add_argument("--profil", default="stufen", choices=["stufen", "schraege"]); ap.add_argument("--leer_offen", type=int, default=0, help="1 = Zellen ohne Tiefe (Netz sah durch: Tor) gelten als 1 m tief (ANNAHME)"); ap.add_argument("--aus", required=True); a = ap.parse_args()
    A, T, N = _ebene(a.wand[0:2], a.wand[2:4], a.wand[4:6]); zone = a.zone; px = a.px
    tief = tiefe_zone(a.tiefe, A, T, N, zone, px)
    if a.ortho: img, g, qi = wandbild_ortho(a.ortho, A, T, zone, px)
    else: img, g, qi = wandbild_fotos(a.objekt, A, T, N, zone, px, w=a.w, k=a.k, fotos=None if a.fotos in (None, "auto") else a.fotos.split(","), fein=bool(a.fein), stl=a.stl,
                                      tiefe=tief if a.proj_tiefe else None, konsens=bool(a.konsens))
    if img is None: print("ABBRUCH:", qi); return 3
    if a.w_flaeche is not None: wf = a.w_flaeche
    else:
        fl = tiefe_zone(a.flaeche or a.tiefe, A, T, N, zone, px, trend=bool(a.flaeche_trend), sockel=a.flaeche_sockel); r_ = max(1, int(0.08 / px)); ring = np.zeros(fl.shape, bool); ring[:r_] = ring[-r_:] = True; ring[:, :r_] = ring[:, -r_:] = True
        wf = float(np.nanmedian(fl[ring])) if np.isfinite(fl[ring]).any() else 0.0
    G = gestalt(img, g, tief, wf, px, loch_stufe=a.loch_stufe, huelle_m=a.huelle, w_hinten=a.w_hinten, ohne_tiefe=bool(a.ohne_tiefe), profil=a.profil, leer_offen=bool(a.leer_offen), fak=a.fak); pf = G["px"]; P = polygone(G["loch"], zone, pf)
    m = G["mass"]; m.update(w_flaeche=round(wf, 4), zone=zone, px=pf, px_wandbild=px, wandbild=qi, tiefe=a.tiefe, n_polygone=len(P),
                            annahmen=["Profil im Gewaendeband: Stufenkanten an den Bildlinien, gleiche Stufenhoehe je Linie (Summe = gemessene Oeffnungstiefe) bzw. Schraege", "Pfosten = Plateau (P80 der Tiefe)", "Wandzellen der Zone eben auf der gebauten Flaeche"])
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True)
    np.savez_compressed(a.aus, rel=G["h"].astype(np.float32), a=A, t=T, n=N, u0=zone[0], z0=zone[2], px=pf, loch=G["loch"], klasse=G["klasse"], w_hinten=a.w_hinten,
                        w_flaeche=wf, oeffnungstiefe_m=m["oeffnungstiefe_m"], loecher_json=json.dumps(P), terrassen_json=json.dumps(terrassen(G["h"], G["loch"], zone, pf)), bericht_json=json.dumps(m, default=float), oeffnung=np.zeros_like(G["loch"]))
    fk = G["loch"].shape[0] // img.shape[0]
    if fk > 1: img = np.repeat(np.repeat(img, fk, 0), fk, 1); tief = np.repeat(np.repeat(tief, fk, 0), fk, 1)
    bild_bericht(a.aus[:-4] + ".jpg", img, G, tief, pf); json.dump(m, open(a.aus[:-4] + ".json", "w"), indent=1, default=float)
    print(f"{os.path.basename(a.aus)}: {m['n_loch']} Oeffnungen ({m.get('loch_m2', 0)} m2, Tiefe {m['oeffnungstiefe_m']} m), {m['n_feld']} Farbfelder, Gewaende {m.get('gewaende_breite_m')} m, "
          f"Pfosten {m.get('pfosten_rueck_m')} m zurueck, Wandflaeche w {wf:.3f}, {len(P)} Lochumrisse -> {a.aus[:-4]}.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
