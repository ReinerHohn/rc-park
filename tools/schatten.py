#!/usr/bin/env python3
"""schatten.py - Schlagschatten des Modells (+ Nachbarn) fuer ein kalibriertes Foto vorhersagen (2026-11-05, Nutzer-Sichtbeobachtung Foto 018:
Gaubenschatten auf dem Dach erzeugen Fotokanten ohne Bauteilkante -> "riesige Buggefahr" fuer den Kantenvergleich).

Verfahren (Schattenkarte, Standard der Echtzeitgrafik): Netz aus Sonnenrichtung s (ferne Lochkamera ~ orthografisch) exakt rastern (render_kern.dreiecke_rastern);
jeder sichtbare Weltpunkt des Fotos (pos aus dem Fotoraster) wird in die Sonnenkamera projiziert; Schatten, wenn er weiter von der Sonne entfernt ist als die
dort naechste Flaeche (+ Toleranz). Schattengrenzen = Kanten der Schattenmaske innerhalb der Silhouette, ohne Stellen, die schon Geometriekanten sind.
Sonnenrichtung: aus Aufnahmezeit (EXIF) + Ort (NOAA-Naeherung, Genauigkeit ~0,5 Grad) ODER Suche ueber (Azimut, Hoehe) gegen die Fotokanten
(EXIF-Zeiten sind oft falsch/ohne Zeitzone: Kaufhaus 59 von 249 Fotos mit Zeit, meist ohne Zeitzone). Bewoelkt -> keine Richtung erklaert die Kanten -> keine Schatten.
"""
import math, numpy as np


def sonnenstand(utc, lat, lon):
    """NOAA-Naeherung: (Azimut von Nord im Uhrzeigersinn, Hoehe) in Grad fuer datetime in UTC."""
    import datetime as _dt
    doy = utc.timetuple().tm_yday; h = utc.hour + utc.minute / 60 + utc.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (h - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dek = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    tst = h * 60 + eqt + 4 * lon; ha = math.radians(tst / 4 - 180); la = math.radians(lat)
    cz = math.sin(la) * math.sin(dek) + math.cos(la) * math.cos(dek) * math.cos(ha); zen = math.acos(max(-1, min(1, cz)))
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(dek) * math.cos(la))) + 180
    return az % 360, 90 - math.degrees(zen)


def richtung(az, el, nord_drehung=0.0):
    """Einheitsvektor ZUR Sonne im Modellrahmen (x Ost, y Nord, z hoch; nord_drehung = Winkel Gitternord->Modell-y, Grad)."""
    a = math.radians(az - nord_drehung); e = math.radians(el)
    return np.array([math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)])


def sonnenkamera(mm, s, N=2048, abstand=5000.0):
    """Ferne Lochkamera in Sonnenrichtung, Bild N x N deckt die Netzhuelle."""
    V = np.asarray(mm.vertices); c = 0.5 * (V.min(0) + V.max(0)); r = 0.5 * np.linalg.norm(V.max(0) - V.min(0)) * 1.05
    C = c + s * abstand; fw = -s; up = np.array([0, 0, 1.0]) if abs(fw[2]) < 0.99 else np.array([0, 1.0, 0])
    rt = np.cross(fw, up); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R = np.vstack([rt, dn, fw]); t = -R @ C
    f = (N / 2) * abstand / r
    return R, t, f, N / 2, N / 2, N


def schattenmaske(mm, pos, gueltig, s, N=2048, tol=0.25, normalen=None, eigen_cos=0.1, steil=1.0):
    """pos (H,W,3) Weltpunkte des Fotorasters (numpy oder torch), gueltig (H,W) bool. Rueckgabe bool (H,W): Punkt liegt im Schatten.
    normalen (H,W,3, nach aussen): Eigenschatten = Flaeche von der Sonne abgewandt (n.s < eigen_cos); Toleranz waechst mit dem Streifwinkel
    (tol + steil * tan(Winkel zwischen n und s), Standard 'slope-scaled bias' gegen Schattenakne auf flach beschienenen Flaechen)."""
    import torch
    import render_kern as RK
    if s[2] <= 0.02: return np.zeros(gueltig.shape, bool)                                             # Sonne unter dem Horizont: alles Schatten = keine Schattenkante
    R, t, f, cx, cy, N = sonnenkamera(mm, s, N)
    ds, _, _ = RK.dreiecke_rastern(mm, R, t, f, cx, cy, N, N)
    ds_t = torch.as_tensor(ds, device="cuda"); ds_t = torch.where(torch.isfinite(ds_t), ds_t, torch.full_like(ds_t, 1e12))
    ds_t = -torch.nn.functional.max_pool2d(-ds_t[None, None], 3, 1, 1)[0, 0]                           # naechste Flaeche im 3x3-Fenster: Rasterfehler an Kanten nicht als Schatten werten
    P = torch.as_tensor(pos, device="cuda", dtype=torch.float64) if not torch.is_tensor(pos) else pos.double()
    X = P @ torch.as_tensor(R, device="cuda", dtype=torch.float64).T + torch.as_tensor(t, device="cuda", dtype=torch.float64)
    u = (f * X[..., 0] / X[..., 2] + cx).round().long().clamp(0, N - 1); v = (f * X[..., 1] / X[..., 2] + cy).round().long().clamp(0, N - 1)
    g = torch.as_tensor(gueltig, device="cuda") if not torch.is_tensor(gueltig) else gueltig
    if normalen is not None:
        Nn = torch.as_tensor(normalen, device="cuda", dtype=torch.float64) if not torch.is_tensor(normalen) else normalen.double()
        c = (Nn @ torch.as_tensor(s, device="cuda", dtype=torch.float64)).clamp(-1, 1); tn = torch.sqrt((1 - c * c).clamp(min=0)) / c.clamp(min=0.05)
        m = (X[..., 2] > ds_t[v, u].double() + tol + steil * tn.clamp(max=20)) | (c < eigen_cos)
    else: m = (X[..., 2] > ds_t[v, u].double() + tol)
    return (m & g).cpu().numpy()


def schattenkanten(maske, silhouette, geo_kanten=None, abstand_px=2):
    """Grenzen der Schattenmaske innerhalb der Silhouette (duenn), ohne Pixel nahe vorhandener Geometriekanten."""
    import cv2
    m8 = maske.astype(np.uint8); k = cv2.morphologyEx(m8, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    k &= cv2.erode(silhouette.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    if geo_kanten is not None: k &= cv2.dilate(geo_kanten.astype(np.uint8), np.ones((2 * abstand_px + 1,) * 2, np.uint8)) == 0
    return k


def sonne_suchen(mm, pos, gueltig, normalen, grau, schritt=5.0, N=1024, prior=None):
    """Sonnenrichtung aus dem Foto: je (Azimut, Hoehe) Licht/Schatten-Maske vorhersagen und mit der Helligkeit vergleichen (punktbiseriale Korrelation
    der Foto-Luminanz mit 'beschienen'; Material-Unterschiede mitteln sich ueber die Flaechen heraus). Ergebnis: beste Richtung, Korrelation, Gitter.
    Richtungen hier im MODELLRAHMEN (Azimut von Modell-+y im Uhrzeigersinn). Bewoelkt: Korrelation bleibt klein fuer alle Richtungen."""
    import torch
    g = np.asarray(grau, np.float64); ok = np.asarray(gueltig if not torch.is_tensor(gueltig) else gueltig.cpu().numpy(), bool)
    L = (g[ok] - g[ok].mean()) / (g[ok].std() + 1e-9); erg = []
    for el in np.arange(5.0, 76.0, schritt):
        for az in np.arange(0.0, 360.0, schritt):
            s = np.array([math.sin(math.radians(az)) * math.cos(math.radians(el)), math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))])
            lit = ~schattenmaske(mm, pos, gueltig, s, N=N, normalen=normalen)[ok]; p = lit.mean()
            r = 0.0 if p < 0.02 or p > 0.98 else float(L[lit].mean() - L[~lit].mean()) * math.sqrt(p * (1 - p))
            erg.append((r, float(az), float(el)))
    erg.sort(reverse=True); return erg


def richtung_modell(az, el, obj):
    """Wahrer Azimut/Hoehe -> Einheitsvektor zur Sonne im Modellrahmen (Meridiankonvergenz UTM 32 + rahmen.xhat/yhat aus objekt.json)."""
    la, lo = obj["lage"]["lat"], obj["lage"]["lon"]; gam = (lo - 9.0) * math.sin(math.radians(la)); xh, yh = obj["rahmen"]["xhat_utm"], obj["rahmen"]["yhat_utm"]
    ag = math.radians(az - gam); e_ = math.cos(math.radians(el)); ve, vn = math.sin(ag) * e_, math.cos(ag) * e_
    return np.array([ve * xh[0] + vn * xh[1], ve * yh[0] + vn * yh[1], math.sin(math.radians(el))])


def zeit_suchen(mm, pos, gueltig, normalen, grau, utc, obj, spanne_h=3.0, schritt_min=10, N=1024):
    """Uhrzeitfehler der Kamera suchen (Datum aus EXIF gilt): je Versatz Sonnenstand -> Licht/Schatten -> Korrelation mit der Helligkeit.
    Nur physikalisch moegliche Sonnenstaende (Spiegelloesungen wie 'Sonne aus Norden' fallen weg). Rueckgabe sortiert [(r, versatz_min, az, el)]."""
    import datetime as dt, torch
    g = np.asarray(grau, np.float64); ok = np.asarray(gueltig if not torch.is_tensor(gueltig) else gueltig.cpu().numpy(), bool)
    L = (g[ok] - g[ok].mean()) / (g[ok].std() + 1e-9); erg = []
    for vm in range(-int(spanne_h * 60), int(spanne_h * 60) + 1, schritt_min):
        az, el = sonnenstand(utc + dt.timedelta(minutes=vm), obj["lage"]["lat"], obj["lage"]["lon"])
        if el < 3: continue
        lit = ~schattenmaske(mm, pos, gueltig, richtung_modell(az, el, obj), N=N, normalen=normalen)[ok]; p = lit.mean()
        r = 0.0 if p < 0.02 or p > 0.98 else float(L[lit].mean() - L[~lit].mean()) * math.sqrt(p * (1 - p))
        erg.append((r, vm, round(az, 1), round(el, 1)))
    erg.sort(reverse=True); return erg


def kanten_treffer(schatten_k, foto_k, tol_px=2):
    """Anteil vorhergesagter Schattenkantenpixel mit Fotokante im Abstand <= tol_px, minus Zufallserwartung (Fotokantendichte im erweiterten Band)."""
    import cv2
    n = int(schatten_k.sum())
    if n < 30: return 0.0, n
    d = cv2.dilate(foto_k.astype(np.uint8), np.ones((2 * tol_px + 1,) * 2, np.uint8)) > 0
    zufall = d[cv2.dilate(schatten_k.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0].mean()
    return float(d[schatten_k].mean() - zufall), n


def zeit_suchen_kanten(mm, pos, gueltig, normalen, foto_k, geo_k, utc, obj, spanne_h=3.0, schritt_min=10, N=1024):
    """Wie zeit_suchen, Kriterium = Schattenkanten (ohne Geometriekanten) treffen Fotokanten besser als Zufall. Rueckgabe [(guete, versatz_min, az, el, n_px)]."""
    import datetime as dt, torch
    sil = np.asarray(gueltig if not torch.is_tensor(gueltig) else gueltig.cpu().numpy(), bool); erg = []
    for vm in range(-int(spanne_h * 60), int(spanne_h * 60) + 1, schritt_min):
        az, el = sonnenstand(utc + dt.timedelta(minutes=vm), obj["lage"]["lat"], obj["lage"]["lon"])
        if el < 3: continue
        sm = schattenmaske(mm, pos, gueltig, richtung_modell(az, el, obj), N=N, normalen=normalen, eigen_cos=-2.0)   # nur SCHLAGschatten (Eigenschatten-Grenzen = Geometriekanten)
        k = schattenkanten(sm, sil, geo_k); q, n = kanten_treffer(k, foto_k)
        erg.append((round(q, 4), vm, round(az, 1), round(el, 1), n))
    erg.sort(reverse=True); return erg
