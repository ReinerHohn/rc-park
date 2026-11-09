#!/usr/bin/env python3
"""teile_sichtpruefung.py - JEDES aktive Bauteil gegen VIELE Fotos pruefen (nicht nur das Nahfoto, an dem man gerade arbeitet).

Anlass (Runde 5 Kaufhaus, 2026-11-09): auf dem Nahfoto 6120 passte alles, auf dem Uebersichtsfoto 6261 ragte links ein Umriss ueber das Nachbarhaus, beide Erker trafen
nur teilweise, ein Tor fehlte, ein EG-Fenster sass daneben. Ein Bauteil gilt erst als 'trifft', wenn es in MEHREREN Fotos aus VERSCHIEDENEN Richtungen besteht.

Ablauf (generisch, kein Objektname im Code; Pfade aus objekt.json["teile_sicht"] oder der Kommandozeile):
 1. Bauteile = aktive Eintraege objekt.json["bauteile"]. Je Bauteil ein eigenes Teil-STL: derselbe Generatoraufruf wie objekt.json["generator"], aber mit NUR_BAUTEIL=<typ>
    (Generator baut nur dieses Bauteil). Ohne Koerper (nur Schnitte) -> UNGEPRUEFT.
 2. Auswahl: ALLE kalibrierten Kameras (kameras-Datei) werden grob gerastert (GPU, Teile zusammen); je Bauteil zaehlt die UNVERDECKTE, NICHT STREIFENDE Pixelflaeche
    (Z-Puffer gegen das ganze Modell, |cos(Blickstrahl, Normale)| > 0,3). Die besten --fotos Fotos mit verschiedenen Blickrichtungen (>= 15 Grad) werden genommen;
    --pflicht erzwingt zusaetzlich bestimmte Fotos (z. B. das Uebersichtsfoto, das der Pruefer uebersehen hat).
 3. Je Bauteil und Foto (alles in der ENTZERRTEN Lochkamera, k1 der Kamera):
      hit    Anteil der sichtbaren Modellkanten (Umriss + Knick + Tiefensprung aus dem exakten GPU-Raster) mit Fotokante (Stabilitaetskarte) innerhalb
             tol = max(tol_min_px, tol_m * f / z) Pixeln,
      lift   hit minus mittlerer hit bei 8 um ~1 m verschobenen Kantenbildern (Zufallstreffer in dichter Fassade), also der Beleg, dass die LAGE zaehlt,
      himmel Anteil der Bauteilflaeche (2 px erodiert) auf Himmelspixeln (= Modell ragt ins Leere),
      recall Gegenrichtung: Anteil der Fotokanten im 0,7-m-Umfeld des Teils, die irgendeine Modellkante erklaert; sil_recall dasselbe fuer die Himmelssilhouette
             (zu schmales Teil, z. B. Kegel statt geschweiftem Helm: Nadel trifft, die breite Glocke fehlt),
      wolke  Anteil der Bauteilflaeche, an der die Wolke (Z-Puffer) HINTER dem Modell liegt (> tol_wolke_m): Modell steht vor einer tieferen Flaeche (Nachbarhaus),
             'wolke_vorn' (Wolke davor, auch Passanten/Baeume) wird nur gemeldet, nicht gewertet.
 4. Urteil je Bauteil: GRUEN = mindestens --min-fotos auswertbare Fotos, davon hoechstens rot_anteil schlecht; ROT = Anteil schlechter Fotos >= rot_anteil oder
    ein Foto mit hartem Befund (Himmel > hart_himmel); UNGEPRUEFT = zu wenig auswertbare Fotos (ein einziges Foto reicht NIE fuer GRUEN).
    Dazu die Zeile 'GANZ' (Gesamtmodell gegen dieselben Pflichtfotos) - findet 'ragt in fremde Flaeche' auch dort, wo ein Teil nicht trennbar ist.
 5. Ausgabe in --out: teile_sicht.json, je Bauteil teil_<nr>_<name>.jpg (bestes | schlechtestes Foto, Modellkanten gruen = Fotokante da, rot = keine), uebersicht.jpg,
    ungeprueft.txt. Rueckgabecode 1, wenn ein Bauteil ROT ist (Gate), sonst 0.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teile_sichtpruefung.py <objekt> [--fotos 6] [--out modelle/<objekt>/audit/teile_sicht] [--pflicht a.jpg,b.jpg]
Schwellen sind Parameter (Standardwerte an dem SYNTHETISCHEN Fall tools/test_teile_sichtpruefung.py kalibriert, nicht am Kaufhaus-Ergebnis).
GPU: Raster (render_kern.dreiecke_rastern), Wolken-Z-Puffer und Verschiebe-Treffer auf der GPU; JOB_GPU_MB ~1500 reicht (gemessen im Log)."""
import os, sys, json, argparse, subprocess, shlex, time, math, concurrent.futures as cf
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import render_kern as RK

SCHWELLEN = dict(tol_m=0.10, tol_min_px=2.5, thr_hit=0.50, thr_lift=-1.0, thr_himmel=0.06, hart_himmel=0.20, thr_wolke=0.30, tol_wolke_m=1.0,
                 versatz_m=1.8, thr_gewinn=0.03, thr_prom=0.03, ring_m=(0.4, 0.8), thr_versatz=0.35, thr_rand=0.0, recall_m=0.7, recall_rel=0.0, thr_recall=0.45, thr_sil=0.55, min_sil=25, min_px=500, min_px_er=120, min_kanten=40, rot_anteil=0.5, wolke_verdeckt=0, min_fotos=2, min_richtungen=2, richtung_grad=25.0, kos_min=0.3, decoy_m=1.0,
                 # --- Runde 2 (2026-11-09), Begruendung je Wert im Log (LOG_TEILE_SICHT_2026-11-09.md, Abschnitt Runde 2)
                 min_z=5.0, min_beob=150, rms_schlecht_px=2.0, recall_max_ext=3.0, thr_ende=0.0, thr_ende_lift=-9.0, min_el=4, min_el_px=60, thr_grad=1.1, grad_dec_m=0.35, min_grad_px=60, frei_min=0.5, lift_gut=0.12, himmel_n=2, nah_m=0.25, fern_m=0.5, tie_marge=0.015, glatt_innen=0.2, glatt_rund=0.85,
                 kam_korr_max_m=0.5, kam_korr_gewinn=0.04, kam_korr_min_px=1.5, sicht_kand=14, fremd_m=0.5)
LANG = 1008                                                                                           # lange Bildseite der Arbeitsaufloesung (Pixel)
FARBE = {"GRUEN": (60, 190, 60), "ROT": (50, 50, 230), "UNGEPRUEFT": (150, 150, 150)}

# ------------------------------------------------------------------ Geometrie / Ansicht
class Ansicht:
    """Ein Foto in der entzerrten Lochkamera (Arbeitsaufloesung). Alle Felder numpy (H,W)."""
    def __init__(s, name, R, t, f, cx, cy, W, H, Dg, FK, sky=None, cz=None, bild=None, Eg=None):
        s.name, s.R, s.t, s.f, s.cx, s.cy, s.W, s.H, s.Dg, s.FK, s.sky, s.cz, s.bild = name, np.asarray(R, float), np.asarray(t, float).ravel(), f, cx, cy, W, H, Dg, FK, sky, cz, bild
        s.dF = cv2.distanceTransform((~FK).astype(np.uint8), cv2.DIST_L2, 5)
        s.Eg = Eg; s.dEg = cv2.distanceTransform((~Eg).astype(np.uint8), cv2.DIST_L2, 5) if Eg is not None else None      # Kanten des GANZEN Modells (fuer Recall: erklaert irgendein Teil die Fotokante?)
        s.kam_korr = (0.0, 0.0); s.kam_gewinn = None; s.kam_unsicher = False; s._g = None            # Runde 2: Kamera-Restversatz (Pixel), siehe kamera_versatz()

    def grau_grad(s):
        """(gx, gy) des geglaetteten Grauwertbildes (Arbeitsaufloesung); None ohne Bild. Fuer das Silhouetten-Kriterium glatter Koerper."""
        if s._g is None and s.bild is not None:
            g = cv2.GaussianBlur(cv2.cvtColor(s.bild, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0, (0, 0), 1.2); s._g = (cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3) / 8.0, cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3) / 8.0)
        return s._g

    def verschieben(s, dx, dy):
        """Fotoseite (Kantenkarte, Himmel, Wolke, Bild) so schieben, dass Foto(p + d) auf Modell(p) liegt (Kamera-Restversatz d in Pixeln); dF neu."""
        M = np.float32([[1, 0, -dx], [0, 1, -dy]]); sz = (s.W, s.H)
        s.FK = cv2.warpAffine(s.FK.astype(np.uint8), M, sz, flags=cv2.INTER_NEAREST).astype(bool); s.dF = cv2.distanceTransform((~s.FK).astype(np.uint8), cv2.DIST_L2, 5)
        if s.sky is not None: s.sky = cv2.warpAffine(s.sky.astype(np.uint8), M, sz, flags=cv2.INTER_NEAREST).astype(bool)
        if s.cz is not None: s.cz = cv2.warpAffine(np.where(np.isfinite(s.cz), s.cz, 1e9).astype(np.float32), M, sz, flags=cv2.INTER_NEAREST, borderValue=1e9); s.cz[s.cz > 1e8] = np.inf
        if s.bild is not None: s.bild = cv2.warpAffine(s.bild, M, sz, flags=cv2.INTER_LINEAR)
        s._g = None; s.kam_korr = (float(dx), float(dy))

def kamera_skaliert(k, lang=LANG):
    s = lang / float(max(k["W"], k["H"])); W = int(round(k["W"] * s)); H = int(round(k["H"] * s))
    return dict(R=np.array(k["Rn"], float), t=np.array(k["tn"], float).ravel(), f=float(k["f"]) * s, cx=float(k["cx"]) * s, cy=float(k["cy"]) * s, W=W, H=H, s=s, k1=float(k["params"][3]) if "params" in k and len(k["params"]) > 3 else 0.0,
                C=-np.array(k["Rn"], float).T @ np.array(k["tn"], float).ravel(), W0=k["W"], H0=k["H"], f0=float(k["f"]), cx0=float(k["cx"]), cy0=float(k["cy"]))

def entzerren(src, kc, interp=cv2.INTER_LINEAR):
    """Bild in Originalverzerrung (SIMPLE_RADIAL: d = x*(1+k*r^2), Lochkoordinaten x) -> Lochkamera der Arbeitsaufloesung."""
    hs, ws = src.shape[:2]; u, v = np.meshgrid(np.arange(kc["W"], dtype=np.float32), np.arange(kc["H"], dtype=np.float32))
    x = (u - kc["cx"]) / kc["f"]; y = (v - kc["cy"]) / kc["f"]; fac = 1 + kc["k1"] * (x * x + y * y)
    mu = (kc["f0"] * x * fac + kc["cx0"]) * (ws / kc["W0"]); mv = (kc["f0"] * y * fac + kc["cy0"]) * (hs / kc["H0"])
    return cv2.remap(src, mu.astype(np.float32), mv.astype(np.float32), interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

def kamera_versatz(A, kc, sw=SCHWELLEN):
    """Gemeinsamer Bildversatz des GANZEN Modells gegen die Fotokanten (Kamera-Restfehler, wirkt auf ALLE Teile gleich). Rueckgabe (dx, dy, gewinn, am_rand).
    Modellkante bei p trifft Fotokante bei p + d. Grobes Raster +-kam_korr_max_m, dann Verfeinerung auf 1 px. Ein Teilfehler (ein falsches Teil) verschiebt das Ganze kaum;
    ein Kamerafehler verschiebt alles - das ist die Trennung 'Kamera schlecht' / 'Teil falsch'."""
    ys, xs = np.nonzero(A.Eg) if A.Eg is not None else (np.zeros(0, int), np.zeros(0, int))
    if len(ys) < 300: return 0, 0, 0.0, False
    rng = np.random.default_rng(1); sel = rng.permutation(len(ys))[:6000]; ys, xs = ys[sel], xs[sel]; z = np.maximum(A.Dg[ys, xs], 1.0); tol = np.maximum(sw["tol_min_px"], sw["tol_m"] * kc["f"] / z)
    zm = float(np.median(z)); ppm = kc["f"] / zm; rr = max(3, int(math.ceil(sw["kam_korr_max_m"] * ppm))); st = max(1, rr // 16); H, W = A.dF.shape; hA = np.arange(len(ys)) % 2 == 0; hB = ~hA
    def h(dx, dy, m): return float((A.dF[np.clip(ys[m] + dy, 0, H - 1), np.clip(xs[m] + dx, 0, W - 1)] <= tol[m]).mean())
    best = (h(0, 0, hA), 0, 0)                                                                            # Schaetzung auf der Haelfte A ...
    for dy in range(-rr, rr + 1, st):
        for dx in range(-rr, rr + 1, st):
            v = h(dx, dy, hA)
            if v > best[0] + 1e-9: best = (v, dx, dy)
    b0 = best
    for dy in range(b0[2] - st, b0[2] + st + 1):
        for dx in range(b0[1] - st, b0[1] + st + 1):
            v = h(dx, dy, hA)
            if v > best[0] + 1e-9: best = (v, dx, dy)
    gew = h(best[1], best[2], hB) - h(0, 0, hB)                                                           # ... Gewinn auf der ZURUECKGEHALTENEN Haelfte B (kein Rauschmaximum ueber ~1000 Versaetze)
    return best[1], best[2], gew, (abs(best[1]) >= rr - st or abs(best[2]) >= rr - st)

def raster(mesh, kc):
    """Exaktes GPU-Raster -> depth (H,W; inf leer), fid (-1 leer), pos (Weltpunkt je Pixel)."""
    if mesh is None or len(mesh.faces) == 0: return np.full((kc["H"], kc["W"]), np.inf, np.float32), np.full((kc["H"], kc["W"]), -1, np.int64), np.zeros((kc["H"], kc["W"], 3), np.float32)
    return RK.dreiecke_rastern(mesh, kc["R"], kc["t"], kc["f"], kc["cx"], kc["cy"], kc["W"], kc["H"])

def kantenpixel(D, fid, vis, mesh, winkel=25.0, sprung_rel=0.02, sprung_abs=0.12):
    """Modellkanten aus dem Raster: Umriss der sichtbaren Flaeche, Normalenknick > winkel, Tiefensprung. Nur Pixel von vis.
    Tiefensprung = ZWEITE Differenz (|D(x+1)-2D(x)+D(x-1)|): eine streifend gesehene ebene Flaeche hat steile, aber lineare Tiefe -> keine Kante
    (die erste Differenz gab Strahlenbuendel aus Scheinkanten, Sichtblatt Runde 5 GANZ)."""
    n = np.zeros(D.shape + (3,), np.float32); g = fid >= 0; n[g] = mesh.face_normals[fid[g]]
    E = np.zeros(D.shape, bool); c = np.cos(np.radians(winkel)); Dz = np.where(np.isfinite(D), D, 0.0)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        vn = np.roll(vis, (-dy, -dx), (0, 1)); nn = np.roll(n, (-dy, -dx), (0, 1)); vm = np.roll(vis, (dy, dx), (0, 1))
        d2 = np.abs(np.roll(Dz, (-dy, -dx), (0, 1)) - 2 * Dz + np.roll(Dz, (dy, dx), (0, 1)))
        E |= vis & (~vn | ((n * nn).sum(2) < c) | (vn & vm & (d2 > sprung_abs + sprung_rel * Dz)))
    E[0, :] = E[-1, :] = False; E[:, 0] = E[:, -1] = False
    return E & vis

def ganz_raster(mesh, kc):
    """Tiefe + Kantenpixel des ganzen Modells (Verdeckung und 'erklaerte Fotokanten')."""
    D, fid, _ = raster(mesh, kc); fin = np.isfinite(D); return D, (kantenpixel(D, fid, fin, mesh) if fin.any() else np.zeros(D.shape, bool))

def wolke_zpuffer(P, kc, dil=3):
    """Z-Puffer (kleinste Tiefe je Pixel) der Wolke in der Lochkamera; 3x3 aufgeweitet, damit duenne Wolken Pixel decken; inf = unbekannt. GPU."""
    import torch
    Pg = P if torch.is_tensor(P) else torch.as_tensor(np.asarray(P, np.float32), device="cuda")
    Rg = torch.as_tensor(kc["R"], dtype=torch.float32, device="cuda"); tg = torch.as_tensor(kc["t"], dtype=torch.float32, device="cuda")
    X = Pg @ Rg.T + tg; z = X[:, 2]; ok = z > 1; u = torch.round(kc["f"] * X[:, 0] / z.clamp(min=1e-3) + kc["cx"]).long(); v = torch.round(kc["f"] * X[:, 1] / z.clamp(min=1e-3) + kc["cy"]).long()
    ok &= (u >= 0) & (u < kc["W"]) & (v >= 0) & (v < kc["H"]); zb = torch.full((kc["H"] * kc["W"],), 1e9, device="cuda"); zb.scatter_reduce_(0, v[ok] * kc["W"] + u[ok], z[ok], reduce="amin")
    zb = zb.view(kc["H"], kc["W"]); zb = -torch.nn.functional.max_pool2d(-zb[None, None], dil, 1, dil // 2)[0, 0]; out = zb.cpu().numpy(); out[out > 1e8] = np.inf; return out

# ------------------------------------------------------------------ Mass je (Teil, Foto)
def reihe_ende(vis, E, A, D, kc, sw):
    """Periodische Teile (Fensterreihe, Baluster): Kantentreffer ueber die ganze Reihe sind blind (der um eine Periode verschobene Satz trifft die Nachbarkante).
    Das ERSTE und LETZTE Element der Reihe tragen die Identitaet: ein verschobener Satz liegt dort neben der Reihe (Wand ohne Fensterkante) bzw. auf dem Nachbarfenster
    ausserhalb. Je Endelement: hit (Anteil Modellkanten mit Fotokante) und lift (hit minus mittlerer hit bei 4 um 0,5 m verschobenen Kantenbildern).
    Rueckgabe None (keine Reihe: < min_el aehnliche Elemente) oder dict(ende_hit, ende_lift, n_el)."""
    m = cv2.morphologyEx(vis.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)); n, lab, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    idx = [i for i in range(1, n) if st[i, 4] >= sw["min_el_px"]]
    if len(idx) < sw["min_el"]: return None
    ar = np.array([st[i, 4] for i in idx], float); med = float(np.median(ar)); idx = [i for i, a_ in zip(idx, ar) if 0.4 * med <= a_ <= 2.5 * med]
    if len(idx) < sw["min_el"]: return None
    c = cen[idx]; u_, s_, vt = np.linalg.svd(c - c.mean(0)); pos = (c - c.mean(0)) @ vt[0]; o = np.argsort(pos); H, W = A.dF.shape; hs = []; ls = []
    for i in (idx[o[0]], idx[o[-1]]):
        ys, xs = np.nonzero(E & cv2.dilate((lab == i).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))
        if len(ys) < 15: continue
        z = np.maximum(D[ys, xs], 1.0); tol = np.maximum(sw["tol_min_px"], sw["tol_m"] * kc["f"] / z); dm = int(round(0.5 * kc["f"] / float(np.median(z))))
        def hh(dx, dy): return float((A.dF[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)] <= tol).mean())
        h0 = hh(0, 0); dec = np.mean([hh(dx, dy) for dx, dy in ((dm, 0), (-dm, 0), (0, dm), (0, -dm))]); hs.append(h0); ls.append(h0 - dec)
    if len(hs) < 2: return None
    return dict(ende_hit=round(min(hs), 3), ende_lift=round(min(ls), 3), n_el=len(idx))

def silhouette_maske(vis, D, A):
    """Umrisspixel der Teilflaeche, hinter denen etwas Tieferes/Leeres liegt (echte Silhouette), und Anteil 'frei' = Silhouette / gesamter Rand. Eingebettete Teile (Tuer in der Wand) haben frei ~ 0."""
    v8 = vis.astype(np.uint8); Bd = vis & ~cv2.erode(v8, np.ones((3, 3), np.uint8)).astype(bool)
    Dv = np.where(vis, D, 0).astype(np.float32); Dn = cv2.dilate(Dv, np.ones((3, 3), np.uint8)); ring = cv2.dilate(v8, np.ones((3, 3), np.uint8)).astype(bool) & ~vis
    far = ring & (~np.isfinite(A.Dg) | (A.Dg > Dn + np.maximum(0.3, 0.05 * Dn))); sil = Bd & cv2.dilate(far.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return sil, float(sil.sum() / max(1, Bd.sum()))

def silhouette_grad(vis, D, A, kc, z_med, sw):
    """Glatte Koerper (Saeule, Zylinder): kaum Innenkanten, Stabilitaetskarte leer. Statt Kantenpraesenz: Farbgradient QUER zur projizierten Umrisslinie.
    Umrisspixel = Rand der Teilflaeche, an dem dahinter etwas Tieferes/Leeres liegt. Je Pixel max |Gradient . Aussennormale| im Fenster +-tol (Median ueber den Umriss) gegen
    dieselbe Messung mit 4 um grad_dec_m verschobenen Umrissen. Rueckgabe (verhaeltnis, n_pixel) oder (None, n)."""
    gg = A.grau_grad()
    if gg is None: return None, 0
    gx, gy = gg; H, W = vis.shape; v8 = vis.astype(np.uint8); sil, _ = silhouette_maske(vis, D, A)
    ys, xs = np.nonzero(sil)
    if len(ys) < sw["min_grad_px"]: return None, int(len(ys))
    bl = cv2.GaussianBlur(v8.astype(np.float32), (0, 0), 2.0); nx = -cv2.Sobel(bl, cv2.CV_32F, 1, 0, ksize=3)[ys, xs]; ny = -cv2.Sobel(bl, cv2.CV_32F, 0, 1, ksize=3)[ys, xs]; nn = np.hypot(nx, ny) + 1e-9; nx, ny = nx / nn, ny / nn
    tol = max(sw["tol_min_px"], sw["tol_m"] * kc["f"] / max(z_med, 1.0)); ds = np.linspace(-tol, tol, 2 * int(math.ceil(tol)) + 1)
    def staerke(oy, ox):
        best = np.zeros(len(ys), np.float32)
        for d in ds:
            yy = np.clip(np.round(ys + ny * d + oy).astype(int), 0, H - 1); xx = np.clip(np.round(xs + nx * d + ox).astype(int), 0, W - 1); best = np.maximum(best, np.abs(gx[yy, xx] * nx + gy[yy, xx] * ny))
        return float(np.median(best))
    s0 = staerke(0, 0); dm = int(round(sw["grad_dec_m"] * kc["f"] / max(z_med, 1.0))); dec = [staerke(oy, ox) for oy, ox in ((dm, 0), (-dm, 0), (0, dm), (0, -dm))]
    return round(s0 / (float(np.mean(dec)) + 1e-6), 3), int(len(ys))

def teil_messen(teil, A, kc, sw=SCHWELLEN, mit_bild=False):
    """Mass fuer ein Teil-Netz (m, Weltrahmen) gegen eine Ansicht A. Rueckgabe dict (nur Zahlen/None) und bei mit_bild die Pixelfelder fuer das Overlay."""
    D, fid, pos = raster(teil, kc); fin = np.isfinite(D); Dg = A.Dg
    tolz = np.maximum(0.08, 0.01 * np.where(fin, D, 0))
    vis = fin & np.isfinite(Dg) & (np.abs(D - Dg) <= tolz)                                              # das Teil IST die vorderste Flaeche des ganzen Modells (verdeckt/ausgeschnitten -> nein)
    if sw.get("wolke_verdeckt") and A.cz is not None: vis &= ~(np.isfinite(A.cz) & (A.cz < D - np.maximum(1.0, 0.04 * D)))       # Formfit-Modus: kein Modellkoerper als Verdecker -> Wolke verdeckt (Decke, Passanten)
    C = kc["C"]; ray = pos - C; cosw = np.zeros(D.shape, np.float32)
    g = fid >= 0
    if g.any(): rl = np.linalg.norm(ray[g], axis=1) + 1e-9; cosw[g] = np.abs((teil.face_normals[fid[g]] * ray[g]).sum(1)) / rl
    nutz = vis & (cosw > 0.3)                                                                          # nicht streifend
    r = dict(kam_korr_px=[round(A.kam_korr[0], 1), round(A.kam_korr[1], 1)], kam_gewinn=A.kam_gewinn, flaeche_px=int(nutz.sum()), sichtbar_px=int(vis.sum()), hit=None, lift=None, himmel=None, wolke=None, wolke_vorn=None, n_kanten=0, z_med=None, auswertbar=False)
    if vis.sum() == 0: return (r, None) if mit_bild else r
    r["z_med"] = float(np.median(D[vis])); v_ = kc["C"] - teil.centroid; r["blick"] = [round(float(x), 3) for x in v_ / (np.linalg.norm(v_) + 1e-9)]
    E = kantenpixel(D, fid, vis, teil); r["n_kanten"] = int(E.sum())
    er = cv2.erode(vis.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(bool); ner = int(er.sum())
    ok_flaeche = r["flaeche_px"] >= sw["min_px"] and r["n_kanten"] >= sw["min_kanten"]
    if r["z_med"] < sw["min_z"]: ok_flaeche = False; r["grund_nein"] = f"zu nah ({r['z_med']:.1f} m < {sw['min_z']} m: Strahlenbuendel/Kamerafehler, Nahfoto nicht urteilsfaehig)"
    if A.kam_unsicher: ok_flaeche = False; r["grund_nein"] = "Kamera-Restversatz nicht bestimmbar/zu gross (Pose unbelegt)"
    if r.get("n_kanten", 0) > 0:                                                                          # glatt: kaum Innenkanten (nur Umriss) -> Kantenpraesenz nicht aussagefaehig
        bd = vis & ~cv2.erode(vis.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool); nv = teil.face_normals[fid[vis & (fid >= 0)]]
        rund = bool(len(nv) and np.linalg.norm(nv.mean(0)) < sw["glatt_rund"])                           # Resultierende der Normalen: Ebene 1,0; halber Zylinder 0,64 -> nur GEKRUEMMTE Koerper (Quader/Wand haben keinen Silhouetten-Kontrast zu erwarten)
        r["rund"] = rund; r["glatt"] = bool(rund and (E & ~bd).sum() < sw["glatt_innen"] * max(1, E.sum()))
    else: r["glatt"] = r["rund"] = False
    r["frei"] = round(silhouette_maske(vis, D, A)[1], 3)
    r["ende_hit"] = r["ende_lift"] = r["grad"] = None; r["n_el"] = 0
    rn = reihe_ende(vis, E, A, D, kc, sw) if r["n_kanten"] >= sw["min_kanten"] else None
    if rn: r.update(rn)
    r["grad"], r["n_grad"] = silhouette_grad(vis, D, A, kc, r["z_med"], sw) if r["glatt"] else (None, 0)
    r["rand_hit"] = None                                                                                 # AUSSENKONTUR der Teilflaeche (bricht die Periodizitaet von Fensterreihen/Balustern: Reihenende hat keine Nachbarkante)
    cn, _ = cv2.findContours(cv2.morphologyEx(vis.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if cn:
        ctr = np.zeros(vis.shape, np.uint8); cv2.drawContours(ctr, cn, -1, 1, 1); ctr = ctr.astype(bool) & (E | cv2.dilate(E.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))
        cy_, cx_ = np.nonzero(ctr)
        if len(cy_) >= sw["min_kanten"] // 2:
            tc = np.maximum(sw["tol_min_px"], sw["tol_m"] * kc["f"] / np.maximum(D[cy_, cx_], 1.0)); r["rand_hit"] = round(float((A.dF[cy_, cx_] <= tc).mean()), 3); r["n_rand"] = int(len(cy_))
    if r["n_kanten"] >= 5:
        ys, xs = np.nonzero(E); z = D[ys, xs]; tol = np.maximum(sw["tol_min_px"], sw["tol_m"] * kc["f"] / np.maximum(z, 1.0))
        H, W = A.dF.shape
        def treffer(dx, dy):
            return float((A.dF[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)] <= tol).mean())
        h0 = treffer(0, 0); dm = max(sw["decoy_m"] * kc["f"] / max(r["z_med"], 1.0), 4 * float(np.median(tol))); dec = []
        for a_ in range(8): dec.append(treffer(int(round(dm * math.cos(a_ * math.pi / 4))), int(round(dm * math.sin(a_ * math.pi / 4)))))
        r["hit"] = round(h0, 3); r["lift"] = round(h0 - float(np.mean(dec)), 3); r["hit_decoy"] = round(float(np.mean(dec)), 3)
        # Lagesuche als PROFIL (Runde 2): Kantentreffer als Funktion des Bildversatzes (+-versatz_m, beide Achsen, Schritt ~0,1 m), 3x3 geglaettet. Lage des Maximums auf der Haelfte A der Modellkanten,
        # Gewinn (Maximum gegen Versatz 0) auf der ZURUECKGEHALTENEN Haelfte B: kein Rauschmaximum ueber ~600 Versaetze. Bei periodischen Teilen liegt das Maximum bei +-Periode, wenn die Lage falsch ist.
        rng = np.random.default_rng(0); sel = rng.permutation(len(ys))[:8000]; ysx, xsx, tl_ = ys[sel], xs[sel], tol[sel]; ppm = kc["f"] / max(r["z_med"], 1.0); hA = np.arange(len(sel)) % 2 == 0
        rr = int(math.ceil(sw["versatz_m"] * ppm)); st = max(1, int(round(0.1 * ppm))); offs = list(range(-(rr // st) * st, (rr // st) * st + 1, st)); n_ = len(offs); PA = np.zeros((n_, n_), np.float32); PB = np.zeros((n_, n_), np.float32)
        for iy, dy in enumerate(offs):
            for ix, dx in enumerate(offs):
                tr = A.dF[np.clip(ysx + dy, 0, H - 1), np.clip(xsx + dx, 0, W - 1)] <= tl_; PA[iy, ix] = tr[hA].mean(); PB[iy, ix] = tr[~hA].mean()
        PA = cv2.blur(PA, (3, 3)); PB = cv2.blur(PB, (3, 3)); c0 = n_ // 2; gy_, gx_ = np.meshgrid(offs, offs, indexing="ij"); dist = np.hypot(gx_, gy_) / ppm; nah = dist <= sw["nah_m"]; fern = dist >= sw["fern_m"]
        iy, ix = np.unravel_index(int(np.argmax(PA)), PA.shape); ny_, nx_ = np.unravel_index(int(np.argmax(np.where(nah, PA, -1))), PA.shape)                  # globales Maximum / bestes Maximum im Nahbereich (|s| <= nah_m: Kamerarest, Pixelraster)
        ring = (np.hypot(gx_ - gx_[iy, ix], gy_ - gy_[iy, ix]) / ppm >= sw["ring_m"][0]) & (np.hypot(gx_ - gx_[iy, ix], gy_ - gy_[iy, ix]) / ppm <= sw["ring_m"][1])
        prom = float(PA[iy, ix] - PA[ring].mean()) if ring.any() else 0.0; r["profil_prominenz"] = round(prom, 3)                  # echtes Maximum hebt sich von seinem Umfeld ab; ein Dichtegefaelle im Foto (Maximum am Rand) nicht
        r["gewinn"] = round(float(PB[iy, ix] - PB[ny_, nx_]) if (not nah[iy, ix] and prom >= sw["thr_prom"]) else 0.0, 3); r["versatz_m"] = round(float(dist[iy, ix]), 2); r["versatz_px"] = [int(offs[ix]), int(offs[iy])]; r["ppm"] = round(float(ppm), 1); r["profil_kontrast"] = round(float(PA[ny_, nx_] - np.median(PA)), 3)
        r["profil_tie"] = bool(fern.any() and PA[fern].max() >= PA[ny_, nx_] - sw["tie_marge"])                # ein Nebenmaximum >= nah_m weit weg gleich hoch: Lage nicht eindeutig (periodisch/dichte Fassade)
    if ner >= sw["min_px_er"]:
        if A.sky is not None:
            ske = cv2.erode(A.sky.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool); r["himmel"] = round(float((er & ske).sum() / ner), 3)
        if A.cz is not None:
            kn = er & np.isfinite(A.cz)
            if kn.sum() >= sw["min_px_er"] // 2:
                tw = np.maximum(sw["tol_wolke_m"], 0.04 * D); r["wolke"] = round(float((kn & (A.cz > D + tw)).sum() / kn.sum()), 3); r["wolke_vorn"] = round(float((kn & (A.cz < D - tw)).sum() / kn.sum()), 3)
    r["recall"] = None; r["sil_recall"] = None
    ext = float(np.max(teil.bounds[1][:2] - teil.bounds[0][:2])); kompakt = bool(sw.get("recall_rel")) or ext <= sw["recall_max_ext"]   # Recall nur fuer kompakte Teile (Helm, Saeule, Erker): grosse Flaechenteile haben nicht modellierte Details im Umfeld (Fehlerliste 1)
    if A.dEg is not None and ner >= sw["min_px_er"] and kompakt and (r["rund"] or sw.get("recall_rel")) and r["frei"] >= sw["frei_min"]:                                       # Gegenrichtung: Fotokanten/-silhouette UM das Teil ohne Modellkante (zu kleines/falsch geformtes Teil)
        rm = max(0.2, sw["recall_rel"] * ext) if sw.get("recall_rel") else sw["recall_m"]     # Formfit-Modus: Umfeld ~ halbe Teilbreite (Saeule 0,44 m, Helm ~0,8 m), nicht die ganze Arkade
        rp = max(3, int(round(rm * kc["f"] / max(r["z_med"], 1.0)))); reg = cv2.dilate(vis.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rp + 1, 2 * rp + 1))).astype(bool)
        tolr = max(sw["tol_min_px"], sw["tol_m"] * kc["f"] / max(r["z_med"], 1.0)); fk = A.FK & reg
        if fk.sum() >= sw["min_kanten"]: r["recall"] = round(float((A.dEg[fk] <= tolr).mean()), 3)
        if A.sky is not None:
            sg = A.sky & ~cv2.erode(A.sky.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool); sg &= reg
            if sg.sum() >= sw["min_sil"]: r["sil_recall"] = round(float((A.dEg[sg] <= tolr).mean()), 3); r["n_sil"] = int(sg.sum())
    if r.get("profil_tie") and r.get("n_el", 0) >= sw["min_el"] and not r.get("glatt"): ok_flaeche = False; r["grund_nein"] = "periodisch: Nebenmaximum der Lagesuche gleich hoch (Lage nicht eindeutig, Kantenpraesenz blind)"
    r["auswertbar"] = bool(ok_flaeche and (r["hit"] is not None or r["grad"] is not None))
    return (r, dict(E=E, vis=vis, D=D)) if mit_bild else r

def foto_urteil(r, sw=SCHWELLEN):
    """(schlecht?, hart?, Gruende) fuer ein Foto-Mass. Glatte Koerper (kaum Innenkanten): Silhouetten-Gradient statt Kantenpraesenz/Lagesuche.
    Periodische Reihen: zusaetzlich Endelemente (erstes/letztes) - die Kantenpraesenz der Reihe ist periodisch blind."""
    g = []; glatt = bool(r.get("glatt"))
    if not glatt:
        if r["hit"] is not None and r["hit"] < sw["thr_hit"]: g.append(f"hit {r['hit']:.2f}<{sw['thr_hit']}")
        if r["lift"] is not None and r["lift"] < sw["thr_lift"]: g.append(f"lift {r['lift']:.2f}<{sw['thr_lift']}")
        if r.get("gewinn") is not None and r["gewinn"] >= sw["thr_gewinn"] and r["versatz_m"] >= sw["thr_versatz"] and not (r["lift"] is not None and r["lift"] >= sw["lift_gut"]): g.append(f"versatz {r['versatz_m']} m gewinn {r['gewinn']:.2f}")
        if r.get("ende_hit") is not None and (r["ende_hit"] < sw["thr_ende"] or r["ende_lift"] < sw["thr_ende_lift"]): g.append(f"reihenende hit {r['ende_hit']:.2f} lift {r['ende_lift']:.2f}")
    elif r.get("grad") is not None and r["grad"] < sw["thr_grad"]: g.append(f"silhouetten-gradient {r['grad']:.2f}<{sw['thr_grad']}")
    if r["himmel"] is not None and r["himmel"] > sw["thr_himmel"]: g.append(f"himmel {r['himmel']:.2f}>{sw['thr_himmel']}")
    if r["wolke"] is not None and r["wolke"] > sw["thr_wolke"]: g.append(f"wolke_hinten {r['wolke']:.2f}>{sw['thr_wolke']}")
    if r.get("rand_hit") is not None and r["rand_hit"] < sw["thr_rand"]: g.append(f"aussenkontur {r['rand_hit']:.2f}<{sw['thr_rand']}")
    if r.get("recall") is not None and r["recall"] < sw["thr_recall"]: g.append(f"recall {r['recall']:.2f}<{sw['thr_recall']}")
    if r.get("sil_recall") is not None and r["sil_recall"] < sw["thr_sil"]: g.append(f"silhouette {r['sil_recall']:.2f}<{sw['thr_sil']}")
    hart = r["himmel"] is not None and r["himmel"] > sw["hart_himmel"]
    return bool(g), hart, g

def teil_urteil(messungen, sw=SCHWELLEN):
    """messungen: Liste (foto, r) mit r['auswertbar']. -> (Urteil, Grund)."""
    ausw = [(f, r) for f, r in messungen if r["auswertbar"]]
    if len(ausw) < sw["min_fotos"]: return "UNGEPRUEFT", f"nur {len(ausw)} auswertbare Fotos (< {sw['min_fotos']}; Fläche/Kanten zu klein oder verdeckt)"
    dirs = []
    for f, r in ausw:
        b = np.array(r.get("blick") or [0, 0, 0])
        if all(math.degrees(math.acos(np.clip(b @ x, -1, 1))) >= sw["richtung_grad"] for x in dirs): dirs.append(b)
    if len(dirs) < sw["min_richtungen"]: return "UNGEPRUEFT", f"{len(ausw)} auswertbare Fotos, aber nur {len(dirs)} Blickrichtung(en) (>= {sw['min_richtungen']} verlangt)"
    bad = []; hart = []
    for f, r in ausw:
        s, h, g = foto_urteil(r, sw)
        if s: bad.append((f, g))
        if h: hart.append(f)
    anteil = len(bad) / len(ausw)
    hm = [(f, r) for f, r in ausw if r["himmel"] is not None and r["himmel"] > sw["thr_himmel"]]; hdirs = []                  # Himmelsbefund in >= himmel_n Fotos aus >= 2 Richtungen = hartes Kriterium (Koordinator-Hypothese, Beleg am Synth: korrekte Teile 0 Fotos)
    for f, r in hm:
        b = np.array(r.get("blick") or [0, 0, 0])
        if all(math.degrees(math.acos(np.clip(b @ x, -1, 1))) >= sw["richtung_grad"] for x in hdirs): hdirs.append(b)
    if len(hm) >= sw["himmel_n"] and len(hdirs) >= 2: hart = hart + [f for f, _ in hm] if hart else [f for f, _ in hm]
    if hart or anteil >= sw["rot_anteil"]:
        return "ROT", f"{len(bad)}/{len(ausw)} Fotos schlecht" + (f", harter Himmelsbefund in {len(hart)}" if hart else "") + ": " + "; ".join(f"{f[:22]} ({', '.join(g)})" for f, g in bad[:3])
    return "GRUEN", f"{len(ausw) - len(bad)}/{len(ausw)} Fotos tragen" + (f" ({len(bad)} schlecht unter Schwelle {sw['rot_anteil']:.2f})" if bad else "")

def wolkenbeleg_je_teil(meshes, wolke_pfad, nah=1.0, beleg=0.15, n=60000):
    """Zweitquelle ohne Fotos: je Teil Anteil der Oberflaeche mit Wolkenpunkt < nah m und davon < beleg m (gleiche Definition wie tools/konvergenz_bericht.py 'wolkenbeleg_teile', GPU-knn).
    Niedrig = Teil steht neben echten Daten, trifft sie aber nicht. Rueckseiten ohne Daten zaehlen nicht (anteil_mit_daten)."""
    from gpu_knn import min_abstand
    W = np.load(wolke_pfad, mmap_mode="r"); Wv = np.asarray(W[:, :3], np.float32); zw = float(Wv[:, 2].max()); out = {}
    for t, m in meshes.items():
        Pt = m.sample(n).astype(np.float32); dt = min_abstand(Pt, Wv); dt = np.asarray(dt.cpu() if hasattr(dt, "cpu") else dt); nh = dt < nah
        out[t] = dict(beleg=round(float((dt[nh] < beleg).mean()), 3) if nh.any() else None, anteil_mit_daten=round(float(nh.mean()), 3), ueber_wolke_z=round(float((Pt[:, 2] > zw).mean()), 3))
    return out

# ------------------------------------------------------------------ Daten laden
def cfg_laden(a):
    root = os.path.abspath(a.root); op = a.objekt if a.objekt.endswith(".json") else os.path.join(root, "modelle", a.objekt, "objekt.json")
    obj = json.load(open(op)); name = os.path.basename(os.path.dirname(op)); ts = obj.get("teile_sicht", {})
    def wahl(k, fl, d=None):
        v = getattr(a, fl) or ts.get(k) or d
        return v if v is None or os.path.isabs(v) else os.path.join(root, v)
    return obj, name, root, os.path.dirname(op), dict(kameras=wahl("kameras", "kameras"), bilder=wahl("bilder", "bilder"), stabil=wahl("stabil", "stabil"), wolke=wahl("wolke", "wolke"), stl=wahl("stl", "stl", obj.get("stl")))

def teile_bauen(obj, name, root, out, massstab, neu=False, parallel=4):
    """Je aktivem Bauteil ein STL (m) ueber den Generatoraufruf aus objekt.json["generator"] mit NUR_BAUTEIL. Rueckgabe Liste (typ, gruppe, Pfad|None)."""
    toks = shlex.split(obj["generator"]); env = dict(os.environ); i = 0
    while i < len(toks) and "=" in toks[i] and not toks[i].startswith("/"): k, v = toks[i].split("=", 1); env[k] = os.path.expanduser(v); i += 1
    cmd = [os.path.expanduser(toks[i])] + toks[i + 1:]; sd = os.path.join(out, "teile_stl"); os.makedirs(sd, exist_ok=True)
    ref = max(os.path.getmtime(os.path.join(root, "tools", "baukasten_gen.py")), os.path.getmtime(os.path.join(root, "modelle", name, "objekt.json")))
    liste = [(b["typ"], b.get("gruppe") or b["typ"]) for b in obj["bauteile"] if b.get("aktiv", True) is not False]
    def eins(j_t):
        j, (typ, gr) = j_t; sn = f"_teilsicht_{os.getpid()}_{j}.stl"; ziel = os.path.join(sd, f"{j:02d}_" + typ.replace(":", "_").replace("/", "_") + ".stl")
        if os.path.exists(ziel) and not neu and os.path.getmtime(ziel) > ref: return typ, gr, ziel
        e = dict(env, NUR_BAUTEIL=typ, STL_NAME=sn, ELEMENTE_AUS="/dev/null"); p = subprocess.run(cmd, cwd=root, env=e, capture_output=True, text=True)
        gen = os.path.join(root, "modelle", "stl", sn)
        if p.returncode != 0 or not os.path.exists(gen): return typ, gr, None
        os.replace(gen, ziel); return typ, gr, ziel
    with cf.ThreadPoolExecutor(parallel) as ex: return list(ex.map(eins, enumerate(liste)))

def stl_m(pfad, massstab):
    m = trimesh.load(pfad, process=False)
    if not isinstance(m, trimesh.Trimesh): m = m.dump(concatenate=True)
    m.apply_scale(massstab / 1000.0); return m

# ------------------------------------------------------------------ Formfit-Ergebnisse (zweiter Einsatzort)
def _rohr(p0, p1, r=0.04):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float); L = np.linalg.norm(p1 - p0)
    if L < 1e-6: return None
    c = trimesh.creation.cylinder(radius=r, height=L, sections=6); z = np.array([0, 0, 1.0]); d = (p1 - p0) / L
    T = trimesh.geometry.align_vectors(z, d); T[:3, 3] = (p0 + p1) / 2; c.apply_transform(T); return c

def formteile_laden(pfad, adapter="auto"):
    """Formteile aus einer Datei -> [(name, trimesh in m)]. Eingabeformate (Weltrahmen = Rahmen der Kameras):
      {"teile": [{"name": "..", "netz": "x.stl"}, {"name": "..", "segmente": [[[x,y,z],[x,y,z]], ..]}]}   (allgemein: Dreiecksnetz oder Kantensatz plus Name; Segmente -> duenne Rohre)
      {"helme": [{cx, cy, z_spitze, z_fuss, r_fuss, ..}]}     helm_fit.py (formen/helme.json): je Helm ein 16-seitiger Kegel (so wie das Modell ihn bauen wuerde)
      {"saeulen": [{cx, cy, R, z_fuss, z_kopf, ..}]}           saeulen_fit.py (g3_formen.json): je Saeule ein Zylinder
    adapter auto = nach vorhandenem Schluessel."""
    d = json.load(open(pfad)); out = []; ad = adapter if adapter != "auto" else next((k for k in ("teile", "helme", "saeulen") if k in d), None)
    if ad == "teile":
        for t in d["teile"]:
            if t.get("netz"): m = trimesh.load(t["netz"], process=False); m.apply_scale(t.get("massstab", 1.0)); out.append((t["name"], m))
            else:
                R = [r for r in (_rohr(a, b) for a, b, *_ in t["segmente"]) if r is not None]
                if R: out.append((t["name"], trimesh.util.concatenate(R)))
    elif ad == "helme":
        for i, h in enumerate(d["helme"]): c = trimesh.creation.cone(radius=h["r_fuss"], height=h["z_spitze"] - h["z_fuss"], sections=16); c.apply_translation([h["cx"], h["cy"], h["z_fuss"]]); out.append((f"helm_{i}", c))
    elif ad == "saeulen":
        for i, h in enumerate(d["saeulen"]): c = trimesh.creation.cylinder(radius=h["R"], height=h["z_kopf"] - h["z_fuss"], sections=24); c.apply_translation([h["cx"], h["cy"], (h["z_kopf"] + h["z_fuss"]) / 2]); out.append((f"saeule_{i}", c))
    else: sys.exit("Formteile: Format nicht erkannt (teile|helme|saeulen)")
    return out

# ------------------------------------------------------------------ Foto laden (Ansicht)
def ansicht_laden(name, k, cfg, P_gpu, Dg_mesh, cache_dir, farbe=False, sw=None, pflicht=False, korrigieren=True):
    kc = kamera_skaliert(k); stem = os.path.splitext(name)[0]
    sp = os.path.join(cfg["stabil"], stem + ".png"); st = cv2.imread(sp, cv2.IMREAD_GRAYSCALE)
    if st is None: return None, None
    FK = entzerren(st, kc) >= 70
    FK = cv2.dilate(FK.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    sky = None; bild = None; im = cv2.imread(os.path.join(cfg["bilder"], name), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if im is not None:
        small = cv2.resize(im, (im.shape[1] // 4, im.shape[0] // 4), interpolation=cv2.INTER_AREA); cp = os.path.join(cache_dir, "himmel_" + stem + ".png")
        try:
            if os.path.exists(cp): sm = cv2.imread(cp, 0) > 127
            else:
                import foto_pick as FP; sm = FP.himmel(small); cv2.imwrite(cp, (sm * 255).astype(np.uint8))
            sky = entzerren(sm.astype(np.uint8), kc, cv2.INTER_NEAREST).astype(bool)
        except (Exception, SystemExit) as ex: print(f"   (Himmelsmaske {name}: {str(ex)[:60]})")
        if farbe: bild = entzerren(cv2.resize(im, (im.shape[1] // 2, im.shape[0] // 2), interpolation=cv2.INTER_AREA), kc)
    cz = wolke_zpuffer(P_gpu, kc) if P_gpu is not None else None
    D, Eg = ganz_raster(Dg_mesh, kc)
    A = Ansicht(name, kc["R"], kc["t"], kc["f"], kc["cx"], kc["cy"], kc["W"], kc["H"], D, FK, sky, cz, bild, Eg)
    if korrigieren and Eg is not None:                                                                    # Kamera-Restfehler ABZIEHEN (wirkt auf alle Teile gleich), Pose am Fensterrand = unsicher
        sw = sw or SCHWELLEN; dx, dy, gew, rand = kamera_versatz(A, kc, sw); A.kam_gewinn = round(float(gew), 3)
        if gew >= sw["kam_korr_gewinn"] and math.hypot(dx, dy) >= sw["kam_korr_min_px"]: A.verschieben(dx, dy)
        A.kam_unsicher = bool(rand and gew >= sw["kam_korr_gewinn"] and not pflicht)
    return A, kc

# ------------------------------------------------------------------ Auswahl der Fotos
def guete_laden(kam_pfad, sw, guete_pfad=None, od=None):
    """Kamera-Guete je Foto. Vorrang: Gueterating der SfM-Pose (audit/kamera_guete_<kameradatei>.json, Leave-one-out-Fehler in m; klasse gut/grob/unbrauchbar). 'unbrauchbar' wird ausgeschlossen,
    'grob' nur zugelassen, wenn fehler_m_bei_abstand < tol_m. Ersatz: Reprojektion/Beobachtungen aus der SfM (tools/kamera_sfm_guete.py, blind fuer Lagefehler). Rueckgabe name -> {klasse: gut|grob|schlecht, ...}."""
    stem = os.path.splitext(os.path.basename(kam_pfad))[0]
    for gp in ([guete_pfad] if guete_pfad else []) + ([os.path.join(od, "audit", f"kamera_guete_{stem}.json"), os.path.join(od, "audit", f"kamera_guete_{stem[4:] if stem.startswith('kam_') else stem}.json")] if od else []):
        if gp and os.path.exists(gp):
            G = json.load(open(gp)); out = {}
            for n, v in G.items():
                k = v.get("klasse"); sch = k == "unbrauchbar" or (k == "grob" and (v.get("fehler_m_bei_abstand") is None or v["fehler_m_bei_abstand"] >= sw["tol_m"]))
                out[n] = dict(klasse="schlecht" if sch else k, quelle="kamera_guete", fehler_m=v.get("fehler_m_bei_abstand"))
            return out
    gp = kam_pfad + ".guete.json"; sp = os.path.join(os.path.dirname(kam_pfad), "sparse", "0")
    if not os.path.exists(gp):
        if not os.path.exists(os.path.join(sp, "images.bin")): return {}
        import kamera_sfm_guete as KG
        try: json.dump(KG.guete(sp, sw["min_beob"], sw["rms_schlecht_px"]), open(gp, "w"))
        except OSError: return KG.guete(sp, sw["min_beob"], sw["rms_schlecht_px"])
    return json.load(open(gp))

def vorwahl(kam, namen, concat, bereiche, teile, Pg=None, sw=SCHWELLEN, lang=360, cache_pfad=None, pflicht=()):
    """Fotowahl je Teil, EINHEITLICH mit tools/bauteil_sichtliste.py: Wert = sichtbare nicht streifende Pixel * Sichtanteil (sichtbar/ohne Verdeckung projiziert) * Bildanteil
    (Teilecken im Bild) * (1 - Fremdverdeckung)^2; Fremdverdeckung = Anteil der Teilpixel, vor denen die WOLKE > fremd_m liegt (Gewoelbe/Passanten/Baeume; Kameras UNTER der Arkade
    'sehen' Giebel durch das nicht modellierte Gewoelbe). Zusaetzlich mittlere Tiefe je Teil/Foto (Nahfotos < min_z werden nicht gewaehlt).
    Rueckgabe fl[teil][foto] = dict(wert, px, z, fremd, ant, im_bild). Zwischenspeicher (cache_pfad) nach Hash von Netz+Kameras+Wolke."""
    import hashlib, pickle
    P = len(bereiche) - 1; fn = concat.face_normals; cum = np.array(bereiche)
    hs = hashlib.sha1(); hs.update(np.round(np.asarray(concat.vertices), 3).tobytes()); hs.update(np.asarray(concat.faces).tobytes()); hs.update(repr((lang, sw["fremd_m"], len(namen), cum.tolist(), Pg is not None, sorted(pflicht), [round(float(kam[n]["f"]), 2) for n in namen[:40]], [round(float(x), 3) for n in namen[:40] for x in kam[n]["tn"]])).encode())
    key = hs.hexdigest()[:16]
    if cache_pfad and os.path.exists(cache_pfad):
        try:
            c = pickle.load(open(cache_pfad, "rb"))
            if c.get("key") == key: print("  Vorwahl aus Zwischenspeicher", flush=True); return c["fl"]
        except Exception: pass
    px = np.zeros((P, len(namen))); zs = np.zeros((P, len(namen))); fr = np.zeros((P, len(namen))); ib = np.zeros((P, len(namen)))
    verts = [np.asarray(m.vertices)[::max(1, len(m.vertices) // 1500)] for m in teile]
    for j, n in enumerate(namen):
        kc = kamera_skaliert(kam[n], lang); D, fid, pos = raster(concat, kc); g = fid >= 0
        for p_, V in enumerate(verts):
            X = V @ kc["R"].T + kc["t"]; z = np.maximum(X[:, 2], 1e-3); u = kc["f"] * X[:, 0] / z + kc["cx"]; v = kc["f"] * X[:, 1] / z + kc["cy"]; ib[p_, j] = float(((X[:, 2] > 1) & (u >= 0) & (u < kc["W"]) & (v >= 0) & (v < kc["H"])).mean())
        if not g.any(): continue
        ray = pos[g] - kc["C"]; cosw = np.abs((fn[fid[g]] * ray).sum(1)) / (np.linalg.norm(ray, axis=1) + 1e-9); tid = np.searchsorted(cum, fid[g], "right") - 1; ok = cosw > 0.3; Dg_ = D[g]
        c = np.bincount(tid[ok], minlength=P); px[:, j] = c * (LANG / lang) ** 2; zs[:, j] = np.bincount(tid[ok], weights=Dg_[ok], minlength=P) / np.maximum(c, 1)
        if Pg is not None:
            cz = wolke_zpuffer(Pg, kc)[g]; fr[:, j] = np.bincount(tid[ok & (cz < Dg_ - sw["fremd_m"])], minlength=P) / np.maximum(c, 1)
    fl = {p_: {} for p_ in range(P)}; K = sw["sicht_kand"]
    for p_ in range(P):
        roh = px[p_] * (1 - fr[p_]) ** 2 * ib[p_]
        for j in list(np.argsort(-roh)[:K]) + [namen.index(q) for q in pflicht if q in namen]:
            if px[p_, j] <= 0: continue
            n = namen[j]; kc = kamera_skaliert(kam[n], lang); D, fid, _ = raster(teile[p_], kc); allein = float((fid >= 0).sum()) * (LANG / lang) ** 2
            ant = float(min(1.0, px[p_, j] / max(allein, 1.0))); fl[p_][n] = dict(wert=float(px[p_, j] * ant * ib[p_, j] * (1 - fr[p_, j]) ** 2), px=float(px[p_, j]), z=float(zs[p_, j]), fremd=round(float(fr[p_, j]), 3), ant=round(ant, 3), im_bild=round(float(ib[p_, j]), 3))
    if cache_pfad:
        try: pickle.dump(dict(key=key, fl=fl), open(cache_pfad, "wb"))
        except OSError: pass
    return fl

def waehlen(fl, kam, schwerpunkt, K, pflicht, winkel=15.0, guete=None, sw=SCHWELLEN):
    """Beste K Fotos nach Wert (siehe vorwahl) mit verschiedenen Blickrichtungen (>= winkel). Ausgeschlossen: Nahfotos (mittlere Tiefe < min_z), SfM-Pose 'schlecht' (kamera_sfm_guete). Pflichtfotos zusaetzlich."""
    cand = sorted(fl.items(), key=lambda kv: -kv[1]["wert"]); gew = []; dirs = []; skip = []
    def d_(n): v = np.array(kam[n]["C"], float) - schwerpunkt; return v / (np.linalg.norm(v) + 1e-9)
    for n, e in cand:
        if len(gew) >= 3 * K: break
        if e["z"] < sw["min_z"]: skip.append((n, "nah")); continue
        if guete and guete.get(n, {}).get("klasse") == "schlecht": skip.append((n, "pose")); continue
        d = d_(n)
        if all(math.degrees(math.acos(np.clip(d @ x, -1, 1))) >= winkel for x in dirs): gew.append(n); dirs.append(d)
    return gew, [p for p in pflicht if p in fl and p not in gew]

# ------------------------------------------------------------------ Overlay
def overlay(A, kc, teil, r, extra, rand=0.25, lang=520):
    E, vis = extra["E"], extra["vis"]; ys, xs = np.nonzero(vis)
    if len(ys) == 0: return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); w = x1 - x0 + 1; h = y1 - y0 + 1; m = int(max(w, h) * rand) + 12
    x0, y0, x1, y1 = max(0, x0 - m), max(0, y0 - m), min(A.W, x1 + m + 1), min(A.H, y1 + m + 1)
    im = A.bild.copy() if A.bild is not None else np.full((A.H, A.W, 3), 90, np.uint8)
    if im.shape[:2] != (A.H, A.W): im = cv2.resize(im, (A.W, A.H))
    im[A.FK] = (0.55 * im[A.FK] + 0.45 * np.array([255, 220, 0])).astype(np.uint8)                     # Fotokanten (Stabilitaetskarte) hellblau/gelb
    tol = np.maximum(SCHWELLEN["tol_min_px"], SCHWELLEN["tol_m"] * kc["f"] / np.maximum(extra["D"], 1.0)); hit = E & (A.dF <= tol)
    sc = min(4.0, lang / max(x1 - x0, y1 - y0)); sz = (int((x1 - x0) * sc), int((y1 - y0) * sc)); crop = cv2.resize(im[y0:y1, x0:x1], sz, interpolation=cv2.INTER_CUBIC)
    for msk, col in ((E & ~hit, (40, 40, 255)), (hit, (60, 220, 60))):
        mm = cv2.resize(cv2.dilate(msk[y0:y1, x0:x1].astype(np.uint8), np.ones((2, 2), np.uint8)), sz, interpolation=cv2.INTER_NEAREST).astype(bool); crop[mm] = col
    tx = f"{A.name[:30]} hit {r['hit']} lift {r['lift']} himm {r['himmel']} wolke {r['wolke']}"
    cv2.rectangle(crop, (0, 0), (crop.shape[1], 18), (0, 0, 0), -1); cv2.putText(crop, tx, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    return crop

def nebeneinander(bilder, h=520):
    bs = [cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h)) for b in bilder if b is not None]
    return np.hstack(bs) if bs else np.full((60, 200, 3), 60, np.uint8)

# ------------------------------------------------------------------ Hauptlauf
def pruefen(ap_args):
    a = ap_args; t0 = time.time(); obj, name, root, od, cfg = cfg_laden(a); sw = dict(SCHWELLEN)
    if a.formen: sw["wolke_verdeckt"] = 1; sw["min_fotos"] = 3; sw["recall_rel"] = 0.5
    for k in sw:
        v = getattr(a, k, None)
        if v is not None: sw[k] = v
    out = a.out or os.path.join(od, "audit", "teile_sicht"); out = out if os.path.isabs(out) else os.path.join(root, out); os.makedirs(out, exist_ok=True); cd = os.path.join(out, "cache"); os.makedirs(cd, exist_ok=True)
    for k in ("kameras", "bilder", "stabil") + (() if a.formen else ("stl",)):
        if not cfg.get(k): sys.exit(f"--{k} fehlt (und objekt.json teile_sicht.{k} nicht gesetzt)")
    massstab = float(obj.get("stl_massstab", 87)); print(f"[{time.time() - t0:5.1f}s] Teile bauen ...", flush=True)
    if a.formen: teile = []; formteile = formteile_laden(a.formen, a.adapter)                         # Einsatzort 2: Formfit-Ergebnisse der Kantenkette statt Generator-STL
    else: teile = teile_bauen(obj, name, root, out, massstab, a.neu); formteile = []
    meshes = {}; ohne = []
    for typ, m in formteile: meshes[typ] = ("Formteil", m)
    for typ, gr, p in teile:
        m = stl_m(p, massstab) if p else None
        if m is None or len(m.faces) < 4: ohne.append((typ, gr, "kein Koerper (Generator lieferte kein Netz; nur Schnitt/Rohdreiecke?)" if p else "Generator lieferte allein kein Netz (nur Schnitt, oder haengt von einem Vorgaenger-Bauteil ab, z. B. Gauben von Dach): nicht trennbar -> ungeprueft")); continue
        meshes[typ] = (gr, m)
    print(f"  {len(meshes)} Bauteile mit Koerper, {len(ohne)} ohne", flush=True)
    ganz = trimesh.util.concatenate([m for _, (_, m) in meshes.items()]) if a.formen else stl_m(cfg["stl"], massstab); kam = json.load(open(cfg["kameras"])); namen = [n for n in sorted(kam) if os.path.exists(os.path.join(cfg["stabil"], os.path.splitext(n)[0] + ".png")) and os.path.exists(os.path.join(cfg["bilder"], n))]
    print(f"[{time.time() - t0:5.1f}s] Vorwahl: {len(namen)} Kameras ...", flush=True)
    tl = list(meshes); concat = trimesh.util.concatenate([meshes[t][1] for t in tl]); cum = np.r_[0, np.cumsum([len(meshes[t][1].faces) for t in tl])]
    P = None
    if cfg.get("wolke"):
        w = np.load(cfg["wolke"]); w = w["P"] if hasattr(w, "files") else w; P = w[:, :3].astype(np.float32)
    import torch; Pg = torch.as_tensor(P, device="cuda") if P is not None else None
    guete = guete_laden(cfg["kameras"], sw, a.guete, od); print(f"  Kamera-Guete: {len(guete)} Fotos ({sum(v.get('klasse') == 'schlecht' for v in guete.values())} schlecht)" if guete else "  Kamera-Guete: keine SfM neben der Kameradatei -> keine Pose-Filterung", flush=True)
    fl = vorwahl(kam, namen, concat, cum, [meshes[t][1] for t in tl], Pg, sw, cache_pfad=os.path.join(cd, "vorwahl.pkl"), pflicht=[p for p in (a.pflicht.split(',') if a.pflicht else []) if p in kam])
    print(f"[{time.time() - t0:5.1f}s] Vorwahl fertig", flush=True)
    pflicht = [p for p in (a.pflicht.split(",") if a.pflicht else []) if p in kam]
    cache = {}
    def ansicht(n, farbe=False):
        if n not in cache or (farbe and cache[n][0].bild is None):
            cache[n] = ansicht_laden(n, kam[n], cfg, Pg, ganz, cd, farbe, sw, pflicht=n in pflicht, korrigieren=bool(a.kamera_korrektur) and not a.formen)
            if len(cache) > 40: cache.pop(next(iter(cache)))
        return cache[n]
    wb = wolkenbeleg_je_teil({t: meshes[t][1] for t in tl}, a.wolke_voll) if a.wolke_voll and not a.formen else {}
    ergebnis = []; bilder = {}
    teile_aus = [(t, meshes[t][0], meshes[t][1]) for t in tl]
    for j, (typ, gr, m) in enumerate(teile_aus):
        gew, zus = waehlen(fl[j], kam, m.centroid, a.fotos, pflicht, guete=guete, sw=sw); mess = []; nutz = 0; extras = {}
        for n in gew + zus:
            if n in gew and nutz >= a.fotos and n not in zus: continue
            A, kc = ansicht(n, True)
            if A is None: continue
            r, ex = teil_messen(m, A, kc, sw, mit_bild=True); r["pflicht"] = n in zus; mess.append((n, r)); extras[n] = (ex, A, kc)
            if r["auswertbar"] and n not in zus: nutz += 1
        urteil, grund = teil_urteil(mess, sw)
        ergebnis.append(dict(typ=typ, gruppe=gr, urteil=urteil, grund=grund, dreiecke=len(m.faces), wolkenbeleg=wb.get(typ), fotos=[dict(foto=n, **r) for n, r in mess]))
        aus = [(n, r) for n, r in mess if r["auswertbar"]]
        if aus:
            bestes = max(aus, key=lambda x: x[1]["flaeche_px"]); schl = min(aus, key=lambda x: (x[1]["hit"] or 0) - 2 * (x[1]["himmel"] or 0) - (x[1]["wolke"] or 0)); ims = []
            for n, r in ([bestes] if schl[0] == bestes[0] else [bestes, schl]):
                ex, A, kc = extras[n]; ims.append(overlay(A, kc, m, r, ex))
            bl = nebeneinander(ims); bilder[typ] = (bl, urteil, gr)
            cv2.imwrite(os.path.join(out, f"teil_{j:02d}_" + typ.replace(":", "_") + ".jpg"), bl)
        print(f"  [{time.time() - t0:5.1f}s] {urteil:10s} {typ:28s} {grund[:110]}", flush=True)
    # Gesamtmodell gegen die Pflichtfotos und die haeufigst gewaehlten Fotos
    zaehl = {}
    for e in ergebnis:
        for f in e["fotos"]:
            if f["auswertbar"] and not f["pflicht"]: zaehl[f["foto"]] = zaehl.get(f["foto"], 0) + 1
    gfotos = list(dict.fromkeys(pflicht + [n for n, _ in sorted(zaehl.items(), key=lambda kv: -kv[1])][:max(0, a.fotos - len(pflicht))])); gm = []; gex = {}
    for n in gfotos:
        A, kc = ansicht(n, True)
        if A is None: continue
        r, ex = teil_messen(ganz, A, kc, sw, mit_bild=True); r["pflicht"] = n in pflicht; gm.append((n, r)); gex[n] = (ex, A, kc)
    gu, gg = teil_urteil(gm, sw); ergebnis.append(dict(typ="GANZ", gruppe="Gesamtmodell", urteil=gu, grund=gg, dreiecke=len(ganz.faces), fotos=[dict(foto=n, **r) for n, r in gm]))
    ga = [(n, r) for n, r in gm if r["auswertbar"]]
    if ga:
        sch = min(ga, key=lambda x: (x[1]["hit"] or 0) - 2 * (x[1]["himmel"] or 0) - (x[1]["wolke"] or 0)); ex, A, kc = gex[sch[0]]; bl = overlay(A, kc, ganz, sch[1], ex, rand=0.05); bilder["GANZ"] = (bl, gu, "Gesamtmodell"); cv2.imwrite(os.path.join(out, "teil_GANZ.jpg"), bl)
    print(f"  GANZ {gu}: {gg[:150]}")
    for typ, gr, grund in ohne: ergebnis.append(dict(typ=typ, gruppe=gr, urteil="UNGEPRUEFT", grund=grund, dreiecke=0, fotos=[]))
    # Uebersichtsblatt
    kach = []
    for e in ergebnis:
        b = bilder.get(e["typ"])
        t = np.full((300, 380, 3), 45, np.uint8)
        if b is not None:
            im = b[0]; s = min(380 / im.shape[1], 270 / im.shape[0]); im = cv2.resize(im, None, fx=s, fy=s); t[30:30 + im.shape[0], :im.shape[1]] = im[:, :380]
        col = FARBE[e["urteil"]]; cv2.rectangle(t, (0, 0), (379, 299), col, 5); cv2.rectangle(t, (0, 0), (379, 28), col, -1)
        cv2.putText(t, f"{e['urteil']} {e['typ'][:30]}", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA); kach.append(t)
    sp = 4
    while len(kach) % sp: kach.append(np.full((300, 380, 3), 20, np.uint8))
    cv2.imwrite(os.path.join(out, "uebersicht.jpg"), np.vstack([np.hstack(kach[i:i + sp]) for i in range(0, len(kach), sp)]))
    ung = [e for e in ergebnis if e["urteil"] == "UNGEPRUEFT"]; open(os.path.join(out, "ungeprueft.txt"), "w").write("".join(f"{e['typ']}\t{e['grund']}\n" for e in ung))
    rot = [e["typ"] for e in ergebnis if e["urteil"] == "ROT"]; lauf = round(time.time() - t0, 1)
    json.dump(dict(objekt=name, schwellen=sw, fotos_je_teil=a.fotos, pflicht=pflicht, laufzeit_s=lauf, rot=rot, ungeprueft=[e["typ"] for e in ung], teile=ergebnis), open(os.path.join(out, "teile_sicht.json"), "w"), indent=1, ensure_ascii=False)
    z = {u: sum(e["urteil"] == u for e in ergebnis) for u in FARBE}
    print(f"TEILE-SICHT {name}: GRUEN {z['GRUEN']}  ROT {z['ROT']}  UNGEPRUEFT {z['UNGEPRUEFT']}   ({lauf} s)  -> {out}")
    if rot: print("ROT:", ", ".join(rot))
    return 1 if rot else 0

def argumente(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("objekt"); ap.add_argument("--fotos", type=int, default=6, help="auswertbare Fotos je Bauteil (Standard 6)")
    ap.add_argument("--out"); ap.add_argument("--root", default=REPO, help="Wurzel mit tools/ und modelle/ (Standard: dieses Repo; Beweis: Scratch-Kopie eines alten Stands)")
    for k in ("kameras", "bilder", "stabil", "wolke", "stl"): ap.add_argument("--" + k)
    ap.add_argument("--formen", help="Formfit-Datei (siehe formteile_laden) statt Generator-Bauteilen: Kettenstufe 'formen'"); ap.add_argument("--adapter", default="auto", choices=["auto", "teile", "helme", "saeulen"])
    ap.add_argument("--pflicht", help="Fotodateien, die IMMER ausgewertet werden (Komma)"); ap.add_argument("--neu", action="store_true", help="Teil-STL neu bauen"); ap.add_argument("--wolke-voll", help="VOLLE Wolke (npy, Modellrahmen) fuer den modellfremden Wolkenbeleg je Teil (Zweitquelle; nicht die _crop, die bei z 26 abgeschnitten ist)"); ap.add_argument("--kamera-korrektur", action="store_true", help="Gemeinsamen Bildversatz des Ganzmodells je Foto abziehen (Standard AUS: SfM-Posen sind mm-genau, ein Versatz waere Modell-/Rahmenfehler und wuerde ihn verstecken)"); ap.add_argument("--guete", help="Kamera-Gueterating JSON (Standard modelle/<objekt>/audit/kamera_guete_<kameradatei>.json)")
    for k, v in SCHWELLEN.items(): ap.add_argument("--" + k.replace("_", "-"), dest=k, type=type(v), default=None)
    return ap.parse_args(argv)

if __name__ == "__main__":
    sys.exit(pruefen(argumente()))
