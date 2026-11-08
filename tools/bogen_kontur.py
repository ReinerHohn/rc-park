#!/usr/bin/env python3
"""bogen_kontur.py - KONTUR zuerst messen, dann benennen (Nutzerwunsch 7.11.2026, Pilot Arkadenboegen). Kein Familien-Raten.
Stufen (Unterbefehle):
  ortho    : je kalibriertem Foto metrische Ortho auf der Fassadenebene (Homographie + Verzeichnung k1 wie COLMAP/fassade_ortho.projizieren), 1 cm/px, ohne Modellsichtbarkeit.
  segment  : je Foto/Bogenfenster die OEFFNUNG segmentieren (SAM-Punkt/Box-Prompt aus Fensterlage, oder Helligkeitsschwelle) -> Kontur in Metern (u,z).
  fuse     : Konturen aller Fotos in Fassadenkoordinaten, robuste Mittelung (Median der Randlage je Richtung), Streuung als Unsicherheit.
  fit      : freie glatte Kurve (Spline) an die gemittelte Kontur, DANACH benennen (Kaempferhoehe, Breite, Scheitel, Stich/Radius, Art); Familienfit nur als Vergleich.
Reine Funktionen unten sind testbar (tools/test_bogen_kontur.py). Keine Objektnamen/Festwerte: Fassadenrahmen kommt als Argument/JSON."""
import os, sys, json, glob, math, argparse
import numpy as np, cv2

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)


def projizieren(X, R, t, f, cx, cy, k1):
    """Lochkamera + Verzeichnung k1 (COLMAP SIMPLE_RADIAL: Verzerrung auf normierten Koordinaten) - identisch fassade_ortho.projizieren."""
    Xc = X @ R.T + t; z = Xc[:, 2]; xn = Xc[:, 0] / z; yn = Xc[:, 1] / z; s = 1 + k1 * (xn * xn + yn * yn)
    return np.c_[f * xn * s + cx, f * yn * s + cy], z


def ebene_ortho(img, cam, rahmen, fenster, zelle=0.01, s=0.0, max_winkel=75.0):
    """Foto -> metrische Ortho der Ebene (n,d,o) um s verschoben (s>0 vor die Wand).
    cam: dict R(3x3), t, f, cx, cy, k1, tr (Rahmenverschiebung). rahmen: n,d (2D), o (2D). fenster: u0,u1,z0,z1 (m).
    Rueckgabe: ortho (nz,nu,3 uint8), gueltig (nz,nu bool), mpp (Meter je Foto-Pixel, nz x nu float32). Zeile 0 = oben."""
    n = np.array(list(rahmen["n"]) + [0.0]); d = np.array(list(rahmen["d"]) + [0.0]); o = np.array(list(rahmen["o"]) + [0.0])
    u0, u1, z0, z1 = fenster; nu = int(round((u1 - u0) / zelle)); nz = int(round((z1 - z0) / zelle))
    uu = u0 + (np.arange(nu) + 0.5) * zelle; zz = z1 - (np.arange(nz) + 0.5) * zelle
    U, Z = np.meshgrid(uu, zz)
    X = o[None] + U.reshape(-1, 1) * d[None] + s * n[None]; X[:, 2] = Z.ravel()
    R = np.asarray(cam["R"], float); t = np.asarray(cam["t"], float); tr = np.asarray(cam.get("tr", [0, 0, 0]), float)
    Cw = -R.T @ t - tr
    px, zc = projizieren(X + tr, R, t, cam["f"], cam["cx"], cam["cy"], cam["k1"])
    v = Cw - X; dist = np.linalg.norm(v, axis=1); cosw = (v @ n) / dist
    H, W = img.shape[:2]
    ok = (cosw > math.cos(math.radians(max_winkel))) & (zc > 1) & (px[:, 0] >= 0) & (px[:, 0] < W - 1) & (px[:, 1] >= 0) & (px[:, 1] < H - 1)
    mx = np.where(ok, px[:, 0], -1).astype(np.float32).reshape(nz, nu); my = np.where(ok, px[:, 1], -1).astype(np.float32).reshape(nz, nu)
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)).reshape(nz, nu, 3)
    mpp = (dist / (cam["f"] * np.maximum(cosw, 1e-3))).astype(np.float32)
    return out, ok.reshape(nz, nu), mpp.reshape(nz, nu)


def kamera_aus_k(K, obj, nr, W, H):
    import fehlteile_finden as FF
    R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); kk = K["kamera"]
    return dict(R=R, t=np.asarray(t, float), f=float(f), cx=float(kk.get("cx", W / 2)), cy=float(kk.get("cy", H / 2)), k1=float(kk.get("k1") or 0.0),
                tr=kk.get("rahmen_verschiebung", [0, 0, 0]))


# ------------------------------------------------------------------ Kontur je Foto (Polar-DP, keine Formannahme)
def kantensignal(bgr, sigma=1.5):
    """Goldlinien-Hinweis (Farbkante des Bogenrandes): (min(R,G) - B) / (Helligkeit + 24), minus lokaler Hintergrund, >= 0. Rot: min(R,G)=G ~ B -> ~0; Gold: R,G hoch, B niedrig -> hoch;
    Weiss/Gewoelbe: B hoch -> ~0. Begruendung: im Sonnenfoto ist die Oeffnung nicht dunkel (Gewoelbekappe hell) - Dunkel-Schwelle misst dort falsch."""
    f = bgr.astype(np.float32); B, G, R = f[..., 0], f[..., 1], f[..., 2]
    g = np.maximum(np.minimum(R, G) - B, 0) / ((R + G + B) / 3 + 24)
    g = cv2.GaussianBlur(g, (0, 0), sigma); bg = cv2.GaussianBlur(g, (0, 0), 12)
    return np.maximum(g - bg, 0)


def polar_probe(sig, gueltig, mitte_px, r_px, theta):
    """Signal in Polarkoordinaten: P[theta, r] (Zeilen = Winkel, Spalten = Radius), mitte_px = (x,y) im Bild, r_px Radien in px, theta in rad (0 = +u, pi/2 = oben)."""
    T, Rr = np.meshgrid(theta, r_px, indexing="ij")
    mx = (mitte_px[0] + Rr * np.cos(T)).astype(np.float32); my = (mitte_px[1] - Rr * np.sin(T)).astype(np.float32)
    P = cv2.remap(sig, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    V = cv2.remap(gueltig.astype(np.float32), mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0.5
    return P * V, V


def dp_pfad(P, max_sprung=2, lam=0.02):
    """Viterbi: je Winkelzeile ein Radiusindex, Sprung <= max_sprung Spalten, Strafe lam*|Sprung|*Median(P+). Rueckgabe Indexvektor."""
    n, m = P.shape; pen = lam * (np.median(P[P > 0]) if (P > 0).any() else 1.0)
    S = np.full((n, m), -1e9, np.float64); B = np.zeros((n, m), np.int32); S[0] = P[0]
    for i in range(1, n):
        best = np.full(m, -1e9); arg = np.zeros(m, np.int32)
        for dj in range(-max_sprung, max_sprung + 1):
            sh = np.full(m, -1e9)
            if dj >= 0: sh[dj:] = S[i - 1][:m - dj] if dj else S[i - 1]
            else: sh[:dj] = S[i - 1][-dj:]
            v = sh - pen * abs(dj); better = v > best; best = np.where(better, v, best); arg = np.where(better, np.arange(m) - dj, arg)
        S[i] = best + P[i]; B[i] = arg
    j = int(np.argmax(S[-1])); pf = np.zeros(n, np.int32)
    for i in range(n - 1, -1, -1): pf[i] = j; j = B[i][j]
    return pf


def kontur_foto(orth, gueltig, fenster, zelle, mitte_uz, r_bereich, theta_deg=(-40.0, 220.0), dtheta=0.5, min_antwort=0.35, min_abs=0.08):
    """Bogenkontur r(theta) um mitte_uz=(u,z) in Metern aus EINEM Orthobild. Rueckgabe dict theta (rad), r (m), antwort, gueltig (bool: Antwort >= min_antwort * P90 der Pfadantworten UND im Bild).
    Gueltig = Antwort >= max(min_abs (absoluter Farbkontrast, ohne Gold-Linie kein Treffer), min_antwort * P90 des Fotos). Randbehandlung: Winkel ohne Bildgueltigkeit werden ungueltig (nicht erfunden)."""
    sig = kantensignal(orth); u0, u1, z0, z1 = fenster
    cx = (mitte_uz[0] - u0) / zelle - 0.5; cy = (z1 - mitte_uz[1]) / zelle - 0.5
    th = np.deg2rad(np.arange(theta_deg[0], theta_deg[1] + 1e-9, dtheta)); rp = np.arange(r_bereich[0], r_bereich[1], zelle) / zelle
    P, V = polar_probe(sig, gueltig, (cx, cy), rp, th); pf = dp_pfad(P)
    ant = P[np.arange(len(th)), pf]; vv = V[np.arange(len(th)), pf]; ref = np.percentile(ant[vv], 90) if vv.any() else 1.0
    return dict(theta=th, r=(rp[pf]) * zelle, antwort=ant, gueltig=vv & (ant >= max(min_abs, min_antwort * ref)))


def fusion(konturen, min_anteil=0.25, min_n=5, max_streu=0.30):
    """Konturen mehrerer Fotos (gleiche theta-Gitter) -> Median je Winkel, MAD-Streuung (m), n. Ungueltig: < min_n Fotos, < min_anteil der Fotos, Streuung > max_streu; es bleibt nur der laengste zusammenhaengende Winkellauf."""
    import warnings; warnings.simplefilter("ignore", RuntimeWarning)
    R = np.array([k["r"] for k in konturen]); G = np.array([k["gueltig"] for k in konturen]); Rm = np.where(G, R, np.nan)
    n = G.sum(0); med = np.nanmedian(np.where(G, R, np.nan), 0); mad = np.nanmedian(np.abs(Rm - med), 0) * 1.4826
    ok = (n >= min_n) & (n >= min_anteil * len(konturen)) & (mad <= max_streu)                  # Fotos muessen sich einig sein (ANNAHME 30 cm = Kamerafehler-Rahmen 10-35 cm: nur grob Widerspruechliches fliegt raus; 12 cm war zu streng und zerlegte die Kurven)
    ok = ok & (np.r_[False, ok[:-1]] | np.r_[ok[1:], False])                                         # einzelne Winkel ohne Nachbarn verwerfen
    best, cur, bs, st = (0, 0), 0, 0, 0                                                              # nur der laengste zusammenhaengende Lauf (ein Bogen = eine Kurve)
    for i, v in enumerate(np.r_[ok, False]):
        if v: cur += 1
        else:
            if cur > best[0]: best = (cur, i - cur)
            cur = 0
    keep = np.zeros_like(ok); keep[best[1]:best[1] + best[0]] = True; ok = ok & keep
    return dict(theta=konturen[0]["theta"], r=np.where(ok, med, np.nan), streu=np.where(ok, mad, np.nan), n=n, ok=ok)


def ausrichten(konturen, n_iter=4, grenze=0.5):
    """Kamerafehler (je Foto eine Verschiebung der Ortho in der Fassadenebene) herausrechnen: je Foto (du,dz) per robuster (IRLS) Kleinste-Quadrate-Anpassung der eigenen Kontur an den Median aller Fotos
    (Radialform erster Ordnung: r_i + d.e_r(theta) = r_Median), Schwerpunkt der Verschiebungen = 0 (Rahmen bleibt; ein allen Fotos GEMEINSAMER Fehler ist nicht beobachtbar).
    Rueckgabe (ausgerichtete Konturen, Verschiebungen (n,2) in m)."""
    th = konturen[0]["theta"]; E = np.c_[np.cos(th), np.sin(th)]; R = np.array([k["r"] for k in konturen]); G = np.array([k["gueltig"] for k in konturen]); D = np.zeros((len(konturen), 2))
    import warnings; warnings.simplefilter("ignore", RuntimeWarning)
    for _ in range(n_iter):
        Ra = R + D @ E.T; C = np.nanmedian(np.where(G, Ra, np.nan), 0)
        for i in range(len(konturen)):
            m = G[i] & np.isfinite(C)
            if m.sum() < 20: continue
            A = E[m]; b = C[m] - R[i, m]; w = np.ones(m.sum())
            for _ in range(6):
                d = np.linalg.lstsq(A * w[:, None], b * w, rcond=None)[0]; w = 1.0 / np.maximum(np.abs(b - A @ d), 0.02)
            D[i] = np.clip(d, -grenze, grenze)
    D -= D.mean(0)
    out = []
    for k, d in zip(konturen, D):
        k2 = dict(k); k2["r"] = k["r"] + E @ d; out.append(k2)
    return out, D


def kurve_spline(theta, r, mitte_uz, glaettung_m=0.01):
    """Freie glatte Kurve: periodenfreie Glaettungs-Spline r(theta) (scipy UnivariateSpline, s = n*glaettung^2), dann (u,z)-Punkte. Keine Formannahme."""
    from scipy.interpolate import UnivariateSpline
    ok = np.isfinite(r)
    if ok.sum() < 20: return None, None, None                                          # nichts gemessen: nichts erfinden
    sp = UnivariateSpline(theta[ok], r[ok], k=3, s=ok.sum() * glaettung_m ** 2)
    tt = np.linspace(theta[ok].min(), theta[ok].max(), 721); rr = sp(tt)
    return np.c_[mitte_uz[0] + rr * np.cos(tt), mitte_uz[1] + rr * np.sin(tt)], tt, rr


def benennen(K, glatt=4):
    """Erst DANACH benennen: aus der gemessenen Kurve K (N,2: u,z, nach u sortiert ueber den Scheitel). Rueckgabe Breite, Kaempferhoehe, Scheitel, Pfeil, Pfeil/halbe Breite,
    Kruemmungsradius am Scheitel (Parabelfit +-15 % Breite) / halbe Breite, Scheitelknick (Grad).
    Kaempfer = Hoehe, unterhalb der die Kurve gerade wird: von der Krone abwaerts der erste Punkt, an dem die Kruemmung unter 50 % des Medians der oberen Seitenhaelfte faellt (sonst tiefster Punkt).
    Scheitelknick = Tangentenwinkel-Aenderung ueber den Scheitel (Fenster 0,04-0,2 w) MINUS die aus der Flankenkruemmung erwartete glatte Aenderung -> 0 beim Rund-/Segmentbogen, gross beim Spitzbogen."""
    from scipy.ndimage import gaussian_filter1d
    u, z = K[:, 0], K[:, 1]; i0 = int(np.argmax(z)); w = float(u.max() - u.min()); uc = float(0.5 * (u.max() + u.min()))
    ds = np.r_[0, np.cumsum(np.hypot(np.diff(u), np.diff(z)))]; sg = glatt
    x1, z1 = gaussian_filter1d(u, sg), gaussian_filter1d(z, sg); dx, dz = np.gradient(x1, ds), np.gradient(z1, ds); ddx, ddz = np.gradient(dx, ds), np.gradient(dz, ds)
    kap = np.abs(dx * ddz - dz * ddx)
    def kaempfer(seite):                                                                  # seite -1 links, +1 rechts, ab Krone abwaerts; Zweistufen-Modell der Kruemmung (Aenderungspunkt)
        idx = np.arange(i0, -1, -1) if seite < 0 else np.arange(i0, len(u))
        idx = idx[np.abs(ds[idx] - ds[i0]) > 0.15 * w]                                   # Scheitelbereich (Knick, Glaettung) ausnehmen
        if len(idx) < 12: return float(z.min())
        k_ = kap[idx]; best, jb = None, None
        for j in range(5, len(k_) - 5):
            c_ = np.sum((k_[:j] - k_[:j].mean()) ** 2) + np.sum((k_[j:] - k_[j:].mean()) ** 2)
            if best is None or c_ < best: best, jb = c_, j
        if jb is None or k_[jb:].mean() > 0.5 * k_[:jb].mean(): return float(z[idx[-1]])   # kein Ende der Kruemmung: Kurve reicht bis zum Kaempfer
        return float(z[idx[jb]])
    zk = 0.5 * (kaempfer(-1) + kaempfer(1)); h = float(z[i0] - zk)
    m = np.abs(u - u[i0]) <= 0.15 * w; A = np.c_[u[m] ** 2, u[m], np.ones(m.sum())]; c = np.linalg.lstsq(A, z[m], rcond=None)[0]
    Rk = abs((1 + (2 * c[0] * u[i0] + c[1]) ** 2) ** 1.5 / (2 * c[0])) if abs(c[0]) > 1e-9 else float("inf")
    def winkel(ul, ur):
        mm = (u >= ul) & (u <= ur); return math.atan(np.polyfit(u[mm], z[mm], 1)[0]) if mm.sum() > 3 else float("nan")
    al, ar = winkel(u[i0] - 0.2 * w, u[i0] - 0.04 * w), winkel(u[i0] + 0.04 * w, u[i0] + 0.2 * w)
    fl = (np.abs(u - u[i0]) > 0.1 * w) & (np.abs(u - u[i0]) < 0.3 * w); kfl = float(np.median(kap[fl])) if fl.any() else 0.0
    knick = math.degrees(abs(al - ar) - kfl * 0.24 * w) if np.isfinite(al) and np.isfinite(ar) else float("nan")
    return dict(mitte_u=uc, breite=w, kaempfer_z=zk, scheitel_z=float(z[i0]), scheitel_u=float(u[i0]), pfeil=h, pfeil_zu_halbbreite=h / (w / 2), kroenungsradius=float(Rk), kroenungsradius_zu_halbbreite=float(Rk / (w / 2)), scheitelknick_grad=knick)


def fenster_aus_kandidaten(kand, min_breite=3.5, max_breite=5.5, min_hoehe=1.0, cluster_m=1.0):
    """Bogenfenster aus den OWLv2-Kandidatenboxen (nur Suchfenster): Boxen mit min_breite < Breite < max_breite (Bogenspannweite ~ Pfeilerabstand; ANNAHME: schliesst Erkerseiten/Fenster aus) und Hoehe > min_hoehe, Cluster nach Mittelpunkt-u, je Cluster Median der Kanten, Oberkante = Maximum."""
    bs = [e["box"] for e in kand if min_breite < (e["box"][1] - e["box"][0]) < max_breite and (e["box"][3] - e["box"][2]) > min_hoehe]
    cl = []
    for b in sorted(bs, key=lambda b: b[0] + b[1]):
        for c in cl:
            if abs(np.mean([(x[0] + x[1]) / 2 for x in c]) - (b[0] + b[1]) / 2) < cluster_m: c.append(b); break
        else: cl.append([b])
    return [dict(u0=float(np.median([x[0] for x in c])), u1=float(np.median([x[1] for x in c])), z1=float(np.max([x[3] for x in c])), boxen=len(c)) for c in cl]


def familien_fit(K, fam):
    """Familienfit NUR als Vergleich mit der gemessenen Kurve K (N,2): freie Parameter der Familie (element_einpassen.profil), robuste Kleinste Quadrate (Huber, Abstand zur Modellkurve). Rueckgabe Parameter, Median/P95 Rest (m)."""
    from scipy.optimize import least_squares
    from scipy.spatial import cKDTree
    import element_einpassen as EE
    b = benennen(K); zb = float(K[:, 1].min()); x0 = [b["mitte_u"], b["breite"], max(b["kaempfer_z"], zb + 0.05)] + ([] if fam == "rund" else [max(b["pfeil"], 0.2)])
    def modell(p): return EE.profil(fam, p, zb, 0.02, 400)
    def res(p):
        try: M = modell(p)
        except Exception: return np.full(len(K), 1.0)
        return cKDTree(M).query(K)[0]
    lo = [x0[0] - 0.5, 0.5 * x0[1], zb] + ([] if fam == "rund" else [0.1]); hi = [x0[0] + 0.5, 1.5 * x0[1], zb + 5] + ([] if fam == "rund" else [4.0])
    r = least_squares(res, np.clip(x0, lo, hi), loss="huber", f_scale=0.03, bounds=(lo, hi)); d = res(r.x)
    return dict(familie=fam, parameter=[float(v) for v in r.x], median_cm=float(np.median(d) * 100), p95_cm=float(np.percentile(d, 95) * 100))


def cmd_kontur(a):
    d = json.load(open(os.path.join(a.ortho, "ortho.json"))); fen = d["fenster"]; z = d["zelle"]; kand = json.load(open(a.kandidaten))["kandidaten"]
    wins = sorted(fenster_aus_kandidaten(kand), key=lambda w: w["u0"]); fotos = sorted(d["fotos"]); erg = dict(ortho=a.ortho, s=d["s"], bogen=[])
    ortho_cache = {nr: (cv2.imread(os.path.join(a.ortho, nr + ".png")), cv2.imread(os.path.join(a.ortho, nr + "_g.png"), 0) > 0) for nr in fotos}
    for bi, w in enumerate(wins):
        wd = w["u1"] - w["u0"]; mitte = ((w["u0"] + w["u1"]) / 2, w["z1"] - wd / 2); ko = {}
        for nr in fotos:
            orth, g = ortho_cache[nr]
            x0 = int((w["u0"] - 0.3 - fen[0]) / z); x1 = int((w["u1"] + 0.3 - fen[0]) / z); y0 = int((fen[3] - w["z1"] - 0.3) / z); y1 = int((fen[3] - 1.0) / z)
            x0, y0 = max(x0, 0), max(y0, 0)
            if g[y0:y1, x0:x1].mean() < a.min_sicht: continue                                  # Bogen nicht (voll) im Foto
            ko[nr] = kontur_foto(orth, g, fen, z, mitte, (0.5 * wd / 2, 1.5 * wd / 2 + 0.5))
        kl = list(ko.values()); D = None
        if a.ausrichten: kl, D = ausrichten(kl)
        fu = fusion(kl, min_n=min(5, len(ko))); K, tt, rr = kurve_spline(fu["theta"], fu["r"], mitte, a.glaettung)
        e = dict(index=bi, fenster=w, mitte=mitte, fotos=sorted(ko), n_fotos=len(ko), glaettung_m=a.glaettung, ausgerichtet=bool(a.ausrichten))
        if D is not None: e["verschiebung_je_foto_m"] = {nr: [round(float(x), 3) for x in d_] for nr, d_ in zip(ko, D)}; e["verschiebung_betrag_median_cm"] = float(np.median(np.hypot(D[:, 0], D[:, 1])) * 100)
        if K is None: e["ergebnis"] = "keine Kontur"; erg["bogen"].append(e); continue
        ok = fu["ok"]; e["streuung_foto_zu_foto_cm"] = dict(median=float(np.nanmedian(fu["streu"][ok]) * 100), p90=float(np.nanpercentile(fu["streu"][ok], 90) * 100), max=float(np.nanmax(fu["streu"][ok]) * 100))
        kr = ok & (np.degrees(fu["theta"]) >= 30) & (np.degrees(fu["theta"]) <= 150); e["streuung_krone_cm"] = dict(median=float(np.nanmedian(fu["streu"][kr]) * 100), n_winkel=int(kr.sum())) if kr.any() else None
        e["winkel_gueltig_anteil"] = float(ok.mean()); e["kurve_uz"] = K[::6].round(4).tolist()
        try: e["benennung"] = benennen(K)
        except Exception as ex: e["benennung"] = None; e["benennung_fehler"] = str(ex); erg["bogen"].append(e); print(f"Bogen {bi}: Benennung fehlgeschlagen: {ex}"); continue
        try: e["familien"] = [familien_fit(K, f) for f in ("rund", "stich", "spitz")]
        except Exception as ex: e["familien"] = str(ex)
        e["je_foto_kontur"] = {nr: dict(r=np.where(k["gueltig"], k["r"], np.nan).round(4).tolist()) for nr, k in zip(ko, kl)} if a.je_foto else "aus (--je-foto)"
        e["theta_grad"] = np.degrees(fu["theta"]).round(2).tolist() if a.je_foto else None
        erg["bogen"].append(e)
        print(f"Bogen {bi}: u {w['u0']:.2f}..{w['u1']:.2f}, {len(ko)} Fotos, Streuung Krone (30-150 Grad) {(e['streuung_krone_cm'] or {}).get('median', float('nan')):.1f} cm; gesamt Median {e['streuung_foto_zu_foto_cm']['median']:.1f} cm P90 {e['streuung_foto_zu_foto_cm']['p90']:.1f}, {json.dumps({k: round(v, 3) for k, v in e['benennung'].items()})}")
    json.dump(erg, open(os.path.join(a.ortho, "kontur.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def cmd_overlay(a):
    """Kontur (Spline, Fassadenebene um s) ueber das ORIGINALFOTO und das Ortho zeichnen -> Bilder zum Ansehen."""
    import fehlteile_finden as FF
    obj = json.load(open(a.objekt)); kj = json.load(open(os.path.join(a.ortho, "kontur.json"))); oj = json.load(open(os.path.join(a.ortho, "ortho.json"))); rahmen = oj["rahmen"]
    n = np.array(rahmen["n"] + [0.0]); dd = np.array(rahmen["d"] + [0.0]); o = np.array(rahmen["o"] + [0.0]); os.makedirs(a.aus, exist_ok=True)
    for nr in a.fotos.split(","):
        pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*")); K_ = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); im = cv2.imread(pf[0]); H, W = im.shape[:2]; cam = kamera_aus_k(K_, obj, nr, W, H)
        allx = []
        for e in kj["bogen"]:
            if "kurve_uz" not in e: continue
            P = np.array(e["kurve_uz"]); X = o[None] + P[:, :1] * dd[None] + oj["s"] * n[None]; X[:, 2] = P[:, 1]
            px, zc = projizieren(X + np.asarray(cam["tr"], float), cam["R"], cam["t"], cam["f"], cam["cx"], cam["cy"], cam["k1"])
            cv2.polylines(im, [np.round(px).astype(np.int32)], False, (255, 255, 0), max(2, W // 1500)); allx.append(px)
        if not allx: continue
        A = np.vstack(allx); x0, x1 = int(max(A[:, 0].min() - 150, 0)), int(min(A[:, 0].max() + 150, W)); y0, y1 = int(max(A[:, 1].min() - 150, 0)), int(min(A[:, 1].max() + 300, H))
        cr = im[y0:y1, x0:x1]; sc = 1800 / cr.shape[1]; cv2.imwrite(os.path.join(a.aus, f"overlay_foto_{nr}.jpg"), cv2.resize(cr, None, fx=sc, fy=sc), [cv2.IMWRITE_JPEG_QUALITY, 88])


def cmd_einbauen(a):
    """Gemessene Kontur (kontur.json) als Oeffnungsprofil in ein Netz (STL, Modell-mm, 1:Massstab) einbauen: Zwickelplatte + Prisma je Bogen, ueber element_einpassen.einbauen_einmal
    (gleicher Einbau wie der S9-Rundbogen -> fairer Vergleich). --modus rund: Vergleichsvariante aus S9-Elementen (Familie rund, freie Parameter aus --elemente)."""
    import element_einpassen as EE
    kj = json.load(open(os.path.join(a.ortho, "kontur.json"))); POLY = []
    orig_profil, orig_krone = EE.profil, EE.krone
    def profil(fam, p, zb, dz=0.01, nk=500): return POLY[int(p[3])] if fam == "kontur" else orig_profil(fam, p, zb, dz, nk)
    def krone(fam, p, n=400): return POLY[int(p[3])] if fam == "kontur" else orig_krone(fam, p, n)
    EE.profil, EE.krone = profil, krone
    els = []
    if a.modus == "mess":
        for e in kj["bogen"]:
            if "kurve_uz" not in e: continue
            K = np.array(e["kurve_uz"]); zb = a.zb
            P = np.vstack([K, [[K[-1, 0], zb], [K[0, 0], zb]]]); POLY.append(P); b = e["benennung"]
            els.append(dict(familie="kontur", p=[b["mitte_u"], b["breite"], b["kaempfer_z"], len(POLY) - 1], zb=zb, t_front=a.t_front, t_back=a.t_back, angenommen=True))
    elif a.modus == "stich":                                                   # Familien-Fit (Stichbogen) an die GEMESSENE Kontur als Fortsetzung bis zum Kaempfer (ANNAHME: Kontur unterhalb ~10 Grad ist nicht gemessen)
        for e in kj["bogen"]:
            f = [x for x in e.get("familien", []) if isinstance(x, dict) and x["familie"] == "stich"]
            if f: els.append(dict(familie="stich", p=f[0]["parameter"], zb=a.zb, t_front=a.t_front, t_back=a.t_back, angenommen=True))
    else:
        el = json.load(open(a.elemente))["elemente"]
        for e in el:
            els.append(dict(familie=e["familie"], p=e["p"], zb=a.zb, t_front=a.t_front, t_back=a.t_back, angenommen=True))
    rj = json.load(open(a.rahmen)); eb = EE.Ebene(rj["o"], rj["n"], rj["d"]); r = EE.einbauen(a.netz, a.aus, eb, els, massstab=a.massstab)
    print(json.dumps(r)); json.dump(dict(netz=a.netz, modus=a.modus, elemente=[dict(familie=e["familie"], p=e["p"]) for e in els], t_front=a.t_front, t_back=a.t_back, zb=a.zb, ergebnis=r), open(a.aus + ".json", "w"), indent=1, default=str)


def cmd_ortho(a):
    import fehlteile_finden as FF
    obj = json.load(open(a.objekt)); rahmen = json.load(open(a.rahmen)); fen = [float(x) for x in a.fenster.split(",")]
    os.makedirs(a.aus, exist_ok=True); fotos = a.fotos.split(",") if a.fotos else sorted(os.path.basename(k)[2:-5] for k in glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll", "K-*.json")) if json.load(open(k)).get("kamera", {}).get("buendel_tor", {}).get("ok"))
    info = {}
    for nr in fotos:
        pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if not pf: continue
        K = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); im = cv2.imread(pf[0]); H, W = im.shape[:2]
        if list(K["kamera"].get("bild", [W, H])) != [W, H]: print("Bildgroesse weicht von K ab, uebersprungen:", nr); continue
        cam = kamera_aus_k(K, obj, nr, W, H); orth, ok, mpp = ebene_ortho(im, cam, rahmen, fen, a.zelle, a.s)
        if ok.mean() < a.min_gueltig: continue
        cv2.imwrite(os.path.join(a.aus, nr + ".png"), orth); cv2.imwrite(os.path.join(a.aus, nr + "_g.png"), ok.astype(np.uint8) * 255)
        info[nr] = dict(gueltig=round(float(ok.mean()), 3), mpp_median=round(float(np.median(mpp[ok])), 4))
    json.dump(dict(rahmen=rahmen, fenster=fen, zelle=a.zelle, s=a.s, fotos=info), open(os.path.join(a.aus, "ortho.json"), "w"), indent=1); print(len(info), "Orthos")


def box_nms_vote(kasten_je_foto, iou_min=0.5, mind=2):
    """Boxen (u0,u1,z0,z1 in m) ueber Fotos abstimmen: Gruppen nach IoU, Gruppe gilt bei >= mind verschiedenen Fotos; Lage = Median je Kante."""
    def iou(a, b):
        iu = max(0, min(a[1], b[1]) - max(a[0], b[0])); iz = max(0, min(a[3], b[3]) - max(a[2], b[2])); I = iu * iz
        return I / ((a[1] - a[0]) * (a[3] - a[2]) + (b[1] - b[0]) * (b[3] - b[2]) - I + 1e-12)
    gr = []
    for nr, kk in kasten_je_foto.items():
        for k in kk:
            for g in gr:
                if iou(np.median([m[1] for m in g], 0), k) > iou_min: g.append((nr, k)); break
            else: gr.append([(nr, k)])
    out = []
    for g in gr:
        fo = {m[0] for m in g}
        if len(fo) >= mind: out.append(dict(box=np.median([m[1] for m in g], 0).round(3).tolist(), stimmen=len(fo)))
    return sorted(out, key=lambda e: e["box"][0])


def cmd_kandidaten(a):
    import torch
    from transformers import Owlv2Processor, Owlv2ForObjectDetection
    d = json.load(open(os.path.join(a.ortho, "ortho.json"))); fen = d["fenster"]; z = d["zelle"]
    fotos = sorted(d["fotos"], key=lambda k: -d["fotos"][k]["gueltig"] / d["fotos"][k]["mpp_median"])[:a.n]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pr = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble"); mo = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble").to(dev).eval()
    prompts = a.prompts.split("|"); res = {}
    for nr in fotos:
        im = cv2.imread(os.path.join(a.ortho, nr + ".png")); sc = a.skala; sm = cv2.resize(im, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(sm, cv2.COLOR_BGR2RGB); Hh, Ww = rgb.shape[:2]; S = max(Hh, Ww)
        inp = pr(text=[prompts], images=rgb, return_tensors="pt").to(dev)
        with torch.no_grad(): out = mo(**inp)
        r = pr.post_process_grounded_object_detection(out, threshold=a.schwelle, target_sizes=torch.tensor([[S, S]]).to(dev))[0]   # Owlv2 pad auf Quadrat
        kk = []
        for b, sco in zip(r["boxes"].cpu().numpy(), r["scores"].cpu().numpy()):
            x0, y0, x1, y1 = b / sc
            kk.append([float(v_) for v_ in (fen[0] + x0 * z, fen[0] + x1 * z, fen[3] - y1 * z, fen[3] - y0 * z)])
        res[nr] = kk
    erg = box_nms_vote(res, mind=a.mind_stimmen); json.dump(dict(prompts=prompts, schwelle=a.schwelle, skala=a.skala, fotos=fotos, je_foto=res, kandidaten=erg, hinweis="Schwelle NICHT optimiert (Standard fassade_parsing 0,15); Boxen nur Suchfenster"), open(os.path.join(a.ortho, "kandidaten.json"), "w"), indent=1)
    print(json.dumps(erg))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("ortho"); o.add_argument("objekt"); o.add_argument("--rahmen", required=True, help="JSON mit n,d,o (Fassadenrahmen, 2D im Modellrahmen)"); o.add_argument("--fenster", required=True, help="u0,u1,z0,z1 in m")
    o.add_argument("--aus", required=True); o.add_argument("--zelle", type=float, default=0.01); o.add_argument("--s", type=float, default=0.0); o.add_argument("--fotos"); o.add_argument("--min-gueltig", type=float, default=0.3)
    k = sp.add_parser("kandidaten"); k.add_argument("ortho"); k.add_argument("--n", type=int, default=8); k.add_argument("--prompts", default="an arch|an arcade arch"); k.add_argument("--schwelle", type=float, default=0.15)
    k.add_argument("--skala", type=float, default=0.5); k.add_argument("--mind-stimmen", type=int, default=3)
    q = sp.add_parser("kontur"); q.add_argument("ortho"); q.add_argument("--kandidaten", required=True); q.add_argument("--glaettung", type=float, default=0.01); q.add_argument("--min-sicht", type=float, default=0.9); q.add_argument("--je-foto", action="store_true"); q.add_argument("--ausrichten", action="store_true", help="je Foto eine Ebenenverschiebung (Kamerafehler) an den Median anpassen, dann fusionieren")
    v = sp.add_parser("overlay"); v.add_argument("objekt"); v.add_argument("ortho"); v.add_argument("--fotos", required=True); v.add_argument("--aus", required=True)
    e_ = sp.add_parser("einbauen"); e_.add_argument("ortho"); e_.add_argument("--netz", required=True); e_.add_argument("--aus", required=True); e_.add_argument("--rahmen", required=True); e_.add_argument("--modus", choices=["mess", "rund", "stich"], default="mess")
    e_.add_argument("--elemente", help="S9-Elemente-JSON (nur --modus rund)"); e_.add_argument("--t-front", type=float, required=True); e_.add_argument("--t-back", type=float, required=True); e_.add_argument("--zb", type=float, default=0.0); e_.add_argument("--massstab", type=float, default=87.0)
    a = ap.parse_args()
    {"einbauen": cmd_einbauen, "ortho": cmd_ortho, "kandidaten": cmd_kandidaten, "kontur": cmd_kontur, "overlay": cmd_overlay}[a.cmd](a)
