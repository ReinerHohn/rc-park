#!/usr/bin/env python3
"""foto_diff.py - Modell gegen Foto: KONTUR-Abweichungen automatisch MERKEN (falscher Torbogen, falsche Bogenzahl, fehlende/erfundene Kanten).

Anders als fehlteile_finden.py (Kantendichte je 1-m-Zelle, Ankerzone-Filter) vergleicht dieses Werkzeug die KANTENLINIEN selbst:
  Modellkanten (Tiefensprung/Normalenknick aus dem Render mit der kalibrierten Kamera) <-> Fotokanten (Canny nach ~7 cm Glaettung).
  Seit 2026-11-04: Modellkanten auf DERSELBEN Arbeitsaufloesung und Glaettung wie die Fotokanten (--kanten normalen); dazu globale Versatzschaetzung
  (gekappter Kantenabstand ueber +-1 m verschoben, 'versatz' im Bericht) - der Anteil allein bemerkt in dichten Fassaden keinen 0,6-m-Versatz.
  Je Modellkantenpixel Abstand zur naechsten Fotokante in METERN (Distanztransformation, Tiefe -> m/px); umgekehrt je Fotokantenpixel.
  Abstand > --tol (Standard 0,35 m) UND zusammenhaengend > --laenge (0,8 m) => Treffer:
    FALSCH/ERFUNDEN : Modellkante ohne Fotokante in der Naehe (z.B. Zwischensaeule, falsche Bogenform/-lage)
    FEHLT           : Fotokante ohne Modellkante in der Naehe
Ausgabe: audit/foto_diff_<foto>.jpg (Foto + gruene = passende, ROTE = falsche/erfundene Modellkanten, GELBE = fehlende; Treffer nummeriert)
         + audit/foto_diff_<foto>_roi.jpg (je Treffer: Foto | Modell-Render nebeneinander) + .json; Beobachtungen automatisch in der Masstabelle.
Exit 0 immer (Bericht); mit --streng Exit 1, wenn Treffer in der Ankerzone liegen. Grenzen: Kamerafehler > tol erzeugt Doppelkanten (Versatz-Hinweis im Bericht);
Verdeckung (Baeume, Leitungen) erzeugt Scheintreffer -> ROI-Blatt ansehen; Treffer ausserhalb der Ankerzone sind als 'unsicher' markiert.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_diff.py modelle/<objekt>/objekt.json <foto> [--tol 0.35] [--laenge 0.8] [--top 10] [--streng]
"""
import sys, os, json, glob, numpy as np, cv2, trimesh, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK

def netzkanten(m, R, t, f, cx, cy, W, H, winkel=25.0, schritt_px=1.5):
    """EXAKTE Modellkanten (2026-11-04): Knickkanten (Flaechenwinkel > winkel), Umrisskanten (eine Nachbarflaeche zur Kamera, eine abgewandt) und Randkanten
    aus dem Netz, abgetastet alle ~schritt_px Bildpixel, Sichtbarkeit per Strahl (Embree) gegen das Netz. Vorher aus dem Punkt-Tiefenbild per Kruemmungsschwelle:
    uebersah beim detailreichen Martinstor Traufen/Fenster/Uhr (Beweis test_foto_diff, T1 53 %)."""
    R = np.asarray(R, float); t = np.asarray(t, float); C = -R.T @ t
    fn = m.face_normals; vor = ((C - m.triangles_center) * fn).sum(1) > 0; fa = m.face_adjacency
    sel = (m.face_adjacency_angles > np.radians(winkel)) | (vor[fa[:, 0]] != vor[fa[:, 1]])
    sel &= vor[fa[:, 0]] | vor[fa[:, 1]]                                                            # Kante zwischen zwei abgewandten Flaechen ist unsichtbar
    E = m.face_adjacency_edges[sel]
    rand = m.edges_sorted[trimesh.grouping.group_rows(m.edges_sorted, require_count=1)]
    if len(rand): E = np.vstack([E, rand])
    A, B = m.vertices[E[:, 0]], m.vertices[E[:, 1]]
    def proj(X):
        Xc = X @ R.T + t; z = Xc[:, 2]; return np.c_[f * Xc[:, 0] / np.maximum(z, 1e-6) + cx, f * Xc[:, 1] / np.maximum(z, 1e-6) + cy], z
    ua, za = proj(A); ub, zb = proj(B); vorn = (za > 0.5) & (zb > 0.5)
    L = np.where(vorn, np.linalg.norm(ua - ub, axis=1), 0); n = np.clip(np.ceil(L / schritt_px).astype(int), 0, 4000); n[~vorn] = 0
    ii = np.repeat(np.arange(len(E)), n + 1 * (n > 0)); tt = np.concatenate([np.linspace(0, 1, k + 1) for k in n if k > 0]) if n.sum() else np.zeros(0)
    P = A[ii] + (B[ii] - A[ii]) * tt[:, None]
    uv, z = proj(P); im_bild = (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H); P, uv = P[im_bild], uv[im_bild]
    if not len(P): return np.zeros((H, W), bool)
    d = P - C; Ld = np.linalg.norm(d, axis=1); d /= Ld[:, None]
    loc, ri, _ = m.ray.intersects_location(np.repeat(C[None], len(P), 0), d, multiple_hits=False)
    sicht = np.ones(len(P), bool)
    if len(ri): sicht[ri] = np.linalg.norm(loc - C, axis=1) >= Ld[ri] - (0.05 + 0.003 * Ld[ri])
    mk = np.zeros((H, W), bool); q = np.round(uv[sicht]).astype(int); q[:, 0] = np.clip(q[:, 0], 0, W - 1); q[:, 1] = np.clip(q[:, 1], 0, H - 1); mk[q[:, 1], q[:, 0]] = True
    return mk


def versatz_schaetzen(mk, fk, inner, ppm, mpp_med, weite_m=1.0, schritt_m=0.05, kappe_m=0.35, n_max=20000):
    """Globaler Bildversatz Modell -> Foto (2026-11-04): gekappter Kantenabstand (Chamfer, beide Richtungen) ueber ein Raster von +-weite_m verschoben.
    Ein Anteil 'Modellkanten ohne Foto' bleibt in dichten Fassaden fast gleich, wenn alles 0,6 m versetzt ist (jede Kante findet IRGENDEINE in tol; Martinstor T1 23 % / T2 25 %);
    die Lage des Minimums dagegen zeigt den Versatz direkt. Rueckgabe dict(versatz_px, versatz_m, gewinn) mit gewinn = 1 - Kosten(best)/Kosten(0)."""
    H, W = mk.shape; kap = max(1.0, kappe_m * ppm); rng = np.random.default_rng(0)
    dFp = np.minimum(cv2.distanceTransform((~fk).astype(np.uint8), cv2.DIST_L2, 5), kap)
    dMp = np.minimum(cv2.distanceTransform((~mk).astype(np.uint8), cv2.DIST_L2, 5), kap)
    ym, xm = np.nonzero(mk); yf, xf = np.nonzero(fk & inner)
    if len(ym) < 50 or len(yf) < 50: return dict(versatz_px=None, versatz_m=None, gewinn=None, deutlich=False)
    if len(ym) > n_max: i = rng.choice(len(ym), n_max, replace=False); ym, xm = ym[i], xm[i]
    if len(yf) > n_max: i = rng.choice(len(yf), n_max, replace=False); yf, xf = yf[i], xf[i]
    r = int(np.ceil(weite_m * ppm)); st = max(1, int(round(schritt_m * ppm))); sh = range(-r, r + 1, st); best = (np.inf, 0, 0); k0 = None
    def kosten(dx, dy):
        a = dFp[np.clip(ym + dy, 0, H - 1), np.clip(xm + dx, 0, W - 1)].mean()                          # Modellkante verschoben -> naechste Fotokante
        b = dMp[np.clip(yf - dy, 0, H - 1), np.clip(xf - dx, 0, W - 1)].mean()                          # Fotokante zurueck -> naechste Modellkante
        return a + b
    for dy in sh:
        for dx in sh:
            k = kosten(dx, dy); best = min(best, (k, dx, dy))
    k0 = kosten(0, 0); _, bx, by = best
    for dy in range(by - st, by + st + 1):                                                          # Feinsuche 1 px
        for dx in range(bx - st, bx + st + 1):
            k = kosten(dx, dy); best = min(best, (k, dx, dy))
    kb, bx, by = best
    g = float(1 - kb / max(k0, 1e-9))
    return dict(versatz_px=[int(bx), int(by)], versatz_m=round(float(np.hypot(bx, by)) * mpp_med, 3), gewinn=round(g, 4), kosten0=round(float(k0 / kap), 5), kosten_best=round(float(kb / kap), 5),   # Kosten / Kappe: 0 = deckungsgleich, 2 = nichts passt (param_suche.py)
                deutlich=bool(g >= 0.08))     # ANNAHME 0,08: synthetisch 0,6 m -> Gewinn 0,12-0,34, ohne Versatz <= 0,003; echte Fotos 0,02-0,06 (Kaufhaus 004: Kantenarten uneins -> kein Befund)


def verdecker_maske(tdir, nr, f, cx, cy, W, H, dmodell, tol_m=0.5, tol_rel=0.05, rand=5, kk=None, abstand=None, trennbar=False):
    """Verdecker aus der Tiefenkarte der dichten Rekonstruktion (sfm_dicht.py, tiefen_kameras.py): Pixel, an denen das Foto etwas DEUTLICH NAEHER zeigt als das Modell
    (Strassenbahn, Baum, Mensch, Schild) - dort kann weder eine Foto- noch eine Modellkante etwas ueber das Modell sagen (2026-11-04; Regel wie textur_projektion --tiefen).
    Abbildung ueber normierte Koordinaten (gleiche Drehung und metrischer Rahmen geprueft: Kaufhaus 004/023/064 Drehung 0,0000 Grad, Zentren nur um rahmen_verschiebung versetzt).
    Rueckgabe (Maske HxW bool oder None, Quelle)."""
    import tiefen_kameras as TK
    kp = os.path.join(tdir, "kameras_unverzerrt.json")
    if not os.path.exists(kp): return None, f"keine {kp}"
    q = json.load(open(kp)).get(nr)
    if not q: return None, f"Foto {nr} nicht in {kp}"
    if kk is not None and "rvec" in kk:                                                              # TOR: Tiefenkarte nur, wenn ihre Kamera DIESELBE ist (gleiche Ausrichtung). Martinstor 014: dicht_nord aus Netz 'nord',
        Rk, _ = cv2.Rodrigues(np.array(kk["rvec"], float)); Ru = np.array(q["R"], float)             # K aus 'buendel' -> 1,8 Grad / 7,6 m daneben, 73 %% des Turms faelschlich 'verdeckt' (2026-11-04)
        dw = float(np.degrees(np.arccos(np.clip((np.trace(Rk.T @ Ru) - 1) / 2, -1, 1))))
        dC = float(np.linalg.norm((-Rk.T @ np.asarray(kk["t"], float)) - (-Ru.T @ np.asarray(q["t"], float)) - np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)))
        grenze = 0.1 + 0.002 * float(abstand or 0.0)
        if dw > 0.1 or dC > grenze: return None, f"Tiefenkamera passt nicht zu K-{nr} (Drehung {dw:.2f} Grad, Zentrum {dC:.2f} m > {grenze:.2f} m): {kp} nicht benutzt"
    pd = os.path.join(tdir, "stereo", "depth_maps", q["bild"] + ".geometric.bin")
    if not os.path.exists(pd): return None, f"keine Tiefenkarte {pd}"
    D = TK.lies_tiefe(pd).astype(np.float32); D[cv2.erode((D > 0).astype(np.uint8), np.ones((rand, rand), np.uint8)) == 0] = 0     # PatchMatch blutet an Silhouetten in den Himmel
    if trennbar:                                                                                   # GPU-Fassung (RAM): Spalte haengt nur von u, Zeile nur von v ab -> zwei Indexreihen statt vier Vollbildkarten (0,3 GB)
        mu = (q["fx"] * (np.arange(W, dtype=np.float32) - cx) / f + q["cx"] - 0.5).astype(np.float32); mv = (q["fy"] * (np.arange(H, dtype=np.float32) - cy) / f + q["cy"] - 0.5).astype(np.float32)
        iu = np.rint(mu).astype(np.int64); iv = np.rint(mv).astype(np.int64); gu = (iu >= 0) & (iu < D.shape[1]); gv = (iv >= 0) & (iv < D.shape[0])
        Ds = D[np.clip(iv, 0, D.shape[0] - 1)][:, np.clip(iu, 0, D.shape[1] - 1)]; Ds[~gv] = 0; Ds[:, ~gu] = 0
    else:
        u, v = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        mu = (q["fx"] * (u - cx) / f + q["cx"] - 0.5).astype(np.float32); mv = (q["fy"] * (v - cy) / f + q["cy"] - 0.5).astype(np.float32)
        Ds = cv2.remap(D, mu, mv, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0); del u, v, mu, mv
    dm = np.nan_to_num(dmodell, nan=np.inf)
    occ = (Ds > 0) & np.isfinite(dm) & (Ds < dm - np.maximum(tol_m, tol_rel * dm))
    if os.environ.get("FD_DEBUG"):
        b = (Ds > 0) & np.isfinite(dm); print("DEBUG verdecker D>0", int((D > 0).sum()), "von", D.size, "Ds>0", int((Ds > 0).sum()), "beide", int(b.sum()), "Ds med", float(np.median(Ds[b])) if b.any() else None, "dm med", float(np.median(dm[b])) if b.any() else None, "occ roh", int(occ.sum()))
    k = max(3, int(round(0.004 * max(W, H))) | 1); occ = cv2.morphologyEx(occ.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8))   # Einzelpixel (Rauschen) weg
    occ = cv2.dilate(occ, np.ones((2 * k + 1, 2 * k + 1), np.uint8)) > 0                                                           # Kante des Verdeckers mitnehmen
    return occ, pd


def kantenrichtung(k, r=3):
    """Richtung (0-180 Grad) duenner Kantenlinien aus dem Strukturtensor des Kantenbildes (fuer Modell- und Fotokanten gleich gerechnet)."""
    g = cv2.GaussianBlur(k.astype(np.float32), (0, 0), 1.0); gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    jxx, jyy, jxy = (cv2.GaussianBlur(x, (0, 0), r) for x in (gx * gx, gy * gy, gx * gy))
    return (np.degrees(0.5 * np.arctan2(2 * jxy, jxx - jyy)) + 90.0) % 180.0                     # Gradientrichtung + 90 = Linienrichtung


def normalenkanten(nrm, depth, r_, W, H, winkel=25.0, sprung_m=0.25, pos=None, C=None, dsauber=None, weit=True, glatt=0.0):
    """Modellkanten auf DERSELBEN Arbeitsaufloesung wie die Fotokanten (2026-11-04, Uebergabe Aufgabe 1): Normalen/Tiefe des Renders flaechengemittelt auf r_,
    KNICK = Normalenwinkel ueber 2 Arbeitspixel > winkel, SPRUNG = |zweite Tiefendifferenz| > sprung_m (schraege Ebenen: 0; vorher |Gradient| > 0,2 m/px markierte
    angeschnittene Seitenflaechen ganz, Martinstor links). Details unter der Fotoglaettung mitteln sich weg (vorher Netzkanten: Ziffern/Ziegel)."""
    w, h = max(8, int(round(W * r_))), max(8, int(round(H * r_)))
    if dsauber is not None:                                                                        # Punktrender: in Loechern gewinnt ein Rueckseitenpunkt (Meter-Spruenge) -> bereinigte Tiefe, Normale nur von der Vorderflaeche
        v = (np.isfinite(depth) & np.isfinite(dsauber) & (np.abs(np.nan_to_num(depth, posinf=1e6) - np.nan_to_num(dsauber, nan=-1e6)) < 0.3)).astype(np.float32); depth = dsauber
    else: v = np.isfinite(depth).astype(np.float32)
    if pos is not None:                                                                            # Netznormalen sind nicht einheitlich orientiert: zur Kamera drehen, sonst heben sich gemittelte Normalen auf
        sg = np.sign(((C[None, None, :] - pos) * nrm).sum(2)); sg[sg == 0] = 1; nrm = nrm * sg[..., None]
    c = cv2.resize(v, (w, h), interpolation=cv2.INTER_AREA); ok = c > 0.05; cc = np.maximum(c, 1e-6)   # Mittel ist abdeckungsgewichtet; > 0,5 liess beim Kaufhaus (3840 px, loechriger Punktrender) nur 990 Arbeitspixel cc = np.maximum(c, 1e-6)
    n = np.dstack([cv2.resize((np.nan_to_num(nrm[..., i]) * v).astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) / cc for i in range(3)])
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    vd = np.isfinite(depth).astype(np.float32); cd = cv2.resize(vd, (w, h), interpolation=cv2.INTER_AREA); ok &= cd > 0.05
    d = cv2.resize((np.nan_to_num(depth, posinf=0.0, nan=0.0) * vd).astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) / np.maximum(cd, 1e-6)
    if glatt > 0:                                                                                  # DIESELBE Glaettung wie die Fotokanten (sigma glaett_px auf der Arbeitsaufloesung): Reliefs/Zickzack unter der Glaettung (Eckquader, Keilsteine, Ziffern) verschwinden wie im Foto
        wt = cv2.GaussianBlur(ok.astype(np.float32), (0, 0), glatt); wt_ = np.maximum(wt, 1e-6)
        n = np.dstack([cv2.GaussianBlur((n[..., i] * ok).astype(np.float32), (0, 0), glatt) / wt_ for i in range(3)]); n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
        d = cv2.GaussianBlur((d * ok).astype(np.float32), (0, 0), glatt) / wt_
    cosw = np.cos(np.radians(winkel)); k = np.zeros((h, w), bool)
    for sl_a, sl_m, sl_b in (((slice(None), slice(0, -2)), (slice(None), slice(1, -1)), (slice(None), slice(2, None))),
                             ((slice(0, -2), slice(None)), (slice(1, -1), slice(None)), (slice(2, None), slice(None)))):
        alle = ok[sl_a] & ok[sl_m] & ok[sl_b]
        knick = (n[sl_a] * n[sl_b]).sum(2) < cosw
        if weit:                                                                                   # ... und auch in +-2 Arbeitspixeln verschieden: flaches Relief (Ziffern, Fensterkreuze) hat davor und dahinter dieselbe Normale -> unter der Fotoaufloesung
            n2 = np.pad(n, ((2, 2), (2, 2), (0, 0)), mode="edge"); o2 = np.pad(ok, 2)
            if sl_m[0] == slice(None): na, nb, oa, ob = n2[2:-2, 1:-3], n2[2:-2, 3:-1], o2[2:-2, 1:-3], o2[2:-2, 3:-1]
            else: na, nb, oa, ob = n2[1:-3, 2:-2], n2[3:-1, 2:-2], o2[1:-3, 2:-2], o2[3:-1, 2:-2]
            knick &= (((na * nb).sum(2) < cosw) | ~oa | ~ob)[sl_m]
        sprung = np.abs(d[sl_b] - 2 * d[sl_m] + d[sl_a]) > sprung_m
        k[sl_m] |= alle & (knick | sprung)
        if os.environ.get("FD_DEBUG"): print("DEBUG normalenkanten knick", int((alle & knick).sum()), "sprung", int((alle & sprung).sum()), "von", int(alle.sum()))
    mk = cv2.resize(k.astype(np.uint8) * 255, (W, H), interpolation=cv2.INTER_NEAREST)
    return cv2.ximgproc.thinning(mk) > 0 if hasattr(cv2, "ximgproc") else mk > 0


def normalenkanten_gpu(nrm, depth, r_, W, H, winkel=25.0, sprung_m=0.25, pos=None, C=None, dsauber=None, weit=True, glatt=0.0):
    """normalenkanten auf der GPU (2026-11-04, Schritt 2): nrm/pos bleiben als torch-Tensoren im GPU-Speicher, zurueck kommt nur die Kantenmaske.
    INTER_AREA -> adaptive Flaechenmittelung (F.interpolate 'area'), GaussianBlur -> separabler Gauss (Rand reflect101), Rest gleich. Nicht bitgleich -> Beweis."""
    import torch, torch.nn.functional as Fn
    dev = nrm.device; w, h = max(8, int(round(W * r_))), max(8, int(round(H * r_)))
    dg = torch.as_tensor(np.asarray(depth, np.float32), device=dev)
    if dsauber is not None:
        ds = torch.as_tensor(np.asarray(dsauber, np.float32), device=dev)
        v = (torch.isfinite(dg) & torch.isfinite(ds) & ((torch.nan_to_num(dg, posinf=1e6) - torch.nan_to_num(ds, nan=-1e6)).abs() < 0.3)).float(); dg = ds
    else: v = torch.isfinite(dg).float()
    if pos is not None:
        Cg = torch.as_tensor(np.asarray(C, np.float32), device=dev); sg = torch.sign(((Cg - pos) * nrm).sum(2)); sg[sg == 0] = 1; nrm = nrm * sg[..., None]
    area = lambda x: Fn.interpolate(x[None, None] if x.dim() == 2 else x.permute(2, 0, 1)[None], size=(h, w), mode="area")[0]
    def gauss(x, s_):                                                                              # x (C,h,w); Kernel wie OpenCV (ksize = round(8 sigma + 1) | 1)
        k = int(round(s_ * 8 + 1)) | 1; r = k // 2; t = torch.arange(-r, r + 1, device=dev, dtype=torch.float32); g = torch.exp(-t * t / (2 * s_ * s_)); g = g / g.sum()
        x = Fn.pad(x[None], (r, r, 0, 0), mode="reflect"); x = Fn.conv2d(x, g.view(1, 1, 1, -1).expand(x.shape[1], 1, 1, -1), groups=x.shape[1])
        x = Fn.pad(x, (0, 0, r, r), mode="reflect"); return Fn.conv2d(x, g.view(1, 1, -1, 1).expand(x.shape[1], 1, -1, 1), groups=x.shape[1])[0]
    c = area(v)[0]; ok = c > 0.05; cc = c.clamp(min=1e-6)
    n = area(torch.nan_to_num(nrm) * v[..., None]) / cc; n = n / n.norm(dim=0, keepdim=True).clamp(min=1e-6)       # (3,h,w)
    vd = torch.isfinite(dg).float(); cd = area(vd)[0]; ok &= cd > 0.05
    d = area(torch.nan_to_num(dg, posinf=0.0, nan=0.0) * vd)[0] / cd.clamp(min=1e-6)
    if glatt > 0:
        wt = gauss(ok.float()[None], glatt)[0].clamp(min=1e-6); n = gauss(n * ok, glatt) / wt; n = n / n.norm(dim=0, keepdim=True).clamp(min=1e-6); d = gauss((d * ok)[None], glatt)[0] / wt
    cosw = float(np.cos(np.radians(winkel))); k = torch.zeros((h, w), dtype=torch.bool, device=dev)
    n2 = Fn.pad(n[None], (2, 2, 2, 2), mode="replicate")[0]; o2 = Fn.pad(ok[None, None].float(), (2, 2, 2, 2))[0, 0] > 0
    for ax in (1, 0):                                                                              # 1 = waagerecht (Spalten), 0 = senkrecht (Zeilen)
        if ax == 1: A, M, B = (slice(None), slice(0, -2)), (slice(None), slice(1, -1)), (slice(None), slice(2, None))
        else: A, M, B = (slice(0, -2), slice(None)), (slice(1, -1), slice(None)), (slice(2, None), slice(None))
        alle = ok[A] & ok[M] & ok[B]; knick = (n[(slice(None),) + A] * n[(slice(None),) + B]).sum(0) < cosw
        if weit:
            if ax == 1: na, nb, oa, ob = n2[:, 2:-2, 1:-3], n2[:, 2:-2, 3:-1], o2[2:-2, 1:-3], o2[2:-2, 3:-1]
            else: na, nb, oa, ob = n2[:, 1:-3, 2:-2], n2[:, 3:-1, 2:-2], o2[1:-3, 2:-2], o2[3:-1, 2:-2]
            knick &= (((na * nb).sum(0) < cosw) | ~oa | ~ob)[M]
        sprung = (d[B] - 2 * d[M] + d[A]).abs() > sprung_m
        k[M] |= alle & (knick | sprung)
    mk = (Fn.interpolate(k[None, None].float(), size=(H, W), mode="nearest")[0, 0] > 0).to(torch.uint8).mul_(255).cpu().numpy()
    return cv2.ximgproc.thinning(mk) > 0 if hasattr(cv2, "ximgproc") else mk > 0


_NETZ = {}


def _netz(pfad, obj, kk):
    """Netz laden, skalieren, in den Kamerarahmen schieben, Oberflaeche abtasten (8 M Punkte, seed 0) - je (Datei, Stand, Massstab, Rahmen) EINMAL
    pro Prozess (Mehrfoto-Aufruf aus param_suche: vorher je Foto neu; Ergebnis identisch, da gleiche Rechnung in gleicher Reihenfolge)."""
    s = os.stat(pfad); m = trimesh.load(pfad); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    tr = np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)   # Kamera traegt ihren Rahmen (Buendel); sonst aus der STL (Handkameras wie bisher)
    saat = int(os.environ.get("FD_SAAT", "0"))                                                  # Saat der Abtastung (test_gpu_gleichwertig: Stichproben-Rauschen der Methode); 0 = bisher
    key = (os.path.abspath(pfad), s.st_mtime_ns, s.st_size, obj.get("stl_massstab", 87), obj.get("zentrierung", "huelle"), tuple(tr.tolist())) + ((saat,) if saat else ())
    if key not in _NETZ:
        if _NETZ: _NETZ.clear()                                                                   # Speicher: 8 M Punkte ~ 0,4 GB; nur das aktuelle Netz halten (parallele Arbeiter, RAM-begrenzt)
        m.apply_translation(tr); gd = os.environ.get("FD_PUNKTE_DIR")
        if gd:                                                                                    # param_suche-Arbeiter: Abtastung je STL nur EINMAL (Spitze 1,4 GB/Prozess) und geteilt per Speicherabbild
            import hashlib, fcntl                                                                 # (/dev/shm; gleiche Zahlen -> bitgleich, geprueft 2026-11-04)
            os.makedirs(gd, exist_ok=True); fn = os.path.join(gd, os.path.basename(pfad) + "_" + hashlib.sha1(repr(key).encode()).hexdigest()[:16])
            with open(fn + ".lock", "w") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                if not os.path.exists(fn + "_N.npy"):
                    P, fi = trimesh.sample.sample_surface(m, 8000000, seed=saat); np.save(fn + "_P.tmp.npy", np.asarray(P)); np.save(fn + "_N.tmp.npy", m.face_normals[fi]); del P, fi
                    os.replace(fn + "_P.tmp.npy", fn + "_P.npy"); os.replace(fn + "_N.tmp.npy", fn + "_N.npy")
            _NETZ[key] = (m, np.load(fn + "_P.npy", mmap_mode="r"), np.load(fn + "_N.npy", mmap_mode="r"))
        else:
            P, fi = trimesh.sample.sample_surface(m, 8000000, seed=saat); P = np.asarray(P); _NETZ[key] = (m, P, m.face_normals[fi])
    return _NETZ[key]


def _cuda():
    try:
        import torch; return torch.cuda.is_available()
    except Exception: return False


def _nanmedian(x, f64=False):
    """np.nanmedian auf der GPU (sort; gerade Anzahl: Mittel der zwei Mittelelemente in der Dtype des Eingangs) - bitgleich, 12-MP-Bild 0,2 s -> 0,03 s (11.11.)."""
    try:
        import torch
        if not (_cuda() and x.dtype in (np.float32, np.float64)): return np.nanmedian(x)
        g = torch.as_tensor(np.ascontiguousarray(x), device="cuda").reshape(-1); g = g[~torch.isnan(g)]; n = g.numel(); g = g.double() if f64 else g
        if n == 0: return np.nanmedian(x.astype(np.float64) if f64 else x)
        g, _ = torch.sort(g); k = (n - 1) // 2                                                      # Sortieren auf der GPU ist 10x schneller als kthvalue (gemessen 14/26 ms gegen 127/226 ms)
        r = g[k] if n % 2 else (g[k] + g[k + 1]) / 2
        return r.cpu().numpy()[()]
    except (RuntimeError, ImportError): return np.nanmedian(x.astype(np.float64) if f64 else x)


_NETZ_R = {}
def _sonne_dreh(s, grad):
    """Gegenprobe: Sonnenvektor um die Hochachse drehen (falsche Sonne muss schlechter abschneiden als die richtige)."""
    c, s_ = np.cos(np.radians(grad)), np.sin(np.radians(grad)); return np.array([c * s[0] - s_ * s[1], s_ * s[0] + c * s[1], s[2]])


_RUECK = None   # Schnellweg fuer teil_fotoform (Nutzer 10.11. abends "massiv beschleunigen"): dict -> Raster + Kostenkarte im Speicher zurueck statt
                # zweitem Raster/npz; "nur_kosten" -> nach der Kostenkarte aufhoeren (Bericht/Bilder ungenutzt). None = altes Verhalten (alle anderen Aufrufer).
def _netz_raster(pfad, obj, kk):
    """Netz fuer --raster: laden, skalieren, in den Kamerarahmen schieben (wie _netz), KEINE Abtastung. Einmal je Prozess und Netzstand."""
    s = os.stat(pfad); key = (os.path.abspath(pfad), s.st_mtime_ns, s.st_size, obj.get("stl_massstab", 87), obj.get("zentrierung", "huelle"), json.dumps(kk.get("rahmen_verschiebung")))
    if key not in _NETZ_R:
        m = trimesh.load(pfad); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
        c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
        m.apply_translation(np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)); _NETZ_R.clear(); _NETZ_R[key] = m
    return _NETZ_R[key]


_NETZ_G = {}


def _netz_gpu(pfad, obj, kk, n=8000000):
    """GPU-Fassung (2026-11-04, Nutzerauftrag 'GPU nutzen'): Oberflaeche flaechengewichtet auf der GPU abtasten (torch, Saat 0), Punkte bleiben im GPU-Speicher.
    NICHT bitgleich zu trimesh.sample_surface (andere Zufallsfolge) -> eigener Beweis (test_foto_diff/test_param_suche mit FD_GPU=1)."""
    import torch
    s = os.stat(pfad); m = trimesh.load(pfad); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    tr = np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)
    key = (os.path.abspath(pfad), s.st_mtime_ns, s.st_size, obj.get("stl_massstab", 87), obj.get("zentrierung", "huelle"), tuple(tr.tolist()), n, int(os.environ.get("FD_SAAT", "0")))
    if key not in _NETZ_G:
        _NETZ_G.clear(); torch.cuda.empty_cache(); m.apply_translation(tr)
        V = torch.as_tensor(np.asarray(m.vertices), dtype=torch.float64, device="cuda"); F = torch.as_tensor(np.asarray(m.faces), dtype=torch.long, device="cuda"); T_ = V[F]
        e1, e2 = T_[:, 1] - T_[:, 0], T_[:, 2] - T_[:, 0]; fl = torch.linalg.cross(e1, e2).norm(dim=1)
        g = torch.Generator(device="cuda"); g.manual_seed(key[-1]); cdf = torch.cumsum(fl, 0); cdf = cdf / cdf[-1]
        fi = torch.searchsorted(cdf, torch.rand(n, generator=g, device="cuda", dtype=torch.float64)).clamp_(max=len(F) - 1)
        u = torch.rand(n, 2, generator=g, device="cuda", dtype=torch.float64); ub = u.sum(1) > 1; u[ub] = 1 - u[ub]          # gleichverteilt im Dreieck (Spiegelung)
        P = (T_[fi, 0] + u[:, :1] * e1[fi] + u[:, 1:] * e2[fi]).float(); N = torch.as_tensor(np.asarray(m.face_normals), dtype=torch.float32, device="cuda")[fi]
        del V, F, T_, e1, e2, fl, cdf, fi, u, ub; _NETZ_G[key] = (m, P, N)
    return _NETZ_G[key]


def _render_gpu(P, N, R, t, f, W, H, cx, cy):
    """Z-Puffer auf der GPU wie render_kern (Rundung, amin, isclose), Gleichstand deterministisch: hoechste Punktnummer gewinnt. Rueckgabe numpy float32 (RAM)."""
    import torch
    Rg = torch.as_tensor(np.asarray(R, np.float32), device="cuda"); tg = torch.as_tensor(np.asarray(t, np.float32).ravel(), device="cuda")
    X = P @ Rg.T + tg; z = X[:, 2]; u = torch.round(f * X[:, 0] / z + cx).long(); v = torch.round(f * X[:, 1] / z + cy).long()
    ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H); ids = torch.nonzero(ok, as_tuple=True)[0]; flat = v[ok] * W + u[ok]; zz = z[ok]; del X, u, v, ok
    d = torch.full((H * W,), float("inf"), device="cuda"); d.scatter_reduce_(0, flat, zz, reduce="amin")
    gw = torch.isclose(d[flat], zz); idx = torch.full((H * W,), -1, dtype=torch.long, device="cuda"); idx.scatter_reduce_(0, flat[gw], ids[gw], reduce="amax")
    tr_ = idx >= 0; nrm = torch.zeros((H * W, 3), device="cuda"); pos = torch.zeros((H * W, 3), device="cuda"); nrm[tr_] = N[idx[tr_]]; pos[tr_] = P[idx[tr_]]
    return d.reshape(H, W).cpu().numpy(), nrm.reshape(H, W, 3), pos.reshape(H, W, 3)                 # nrm/pos bleiben auf der GPU (Schritt 2: 0,4 GB RAM je Arbeiter)


def _versatz_gpu(mk, fk, inner, ppm, mpp_med, weite_m=1.0, schritt_m=0.05, kappe_m=0.35, n_max=20000):
    """versatz_schaetzen mit allen Verschiebungen in EINEM GPU-Schritt (vorher 1770 Python-Schleifen). Gleiche Abstandskarten und Stichprobe (cv2, rng 0);
    Mittelwerte in float64 auf der GPU -> bis auf Summationsreihenfolge gleich."""
    import torch
    H, W = mk.shape; kap = max(1.0, kappe_m * ppm); rng = np.random.default_rng(0)
    dFp = np.minimum(cv2.distanceTransform((~fk).astype(np.uint8), cv2.DIST_L2, 5), kap); dMp = np.minimum(cv2.distanceTransform((~mk).astype(np.uint8), cv2.DIST_L2, 5), kap)
    ym, xm = np.nonzero(mk); yf, xf = np.nonzero(fk & inner)
    if len(ym) < 50 or len(yf) < 50: return dict(versatz_px=None, versatz_m=None, gewinn=None, deutlich=False)
    if len(ym) > n_max: i = rng.choice(len(ym), n_max, replace=False); ym, xm = ym[i], xm[i]
    if len(yf) > n_max: i = rng.choice(len(yf), n_max, replace=False); yf, xf = yf[i], xf[i]
    G = lambda a_, dt=torch.long: torch.as_tensor(np.asarray(a_), dtype=dt, device="cuda")
    dF_, dM_ = G(dFp, torch.float64), G(dMp, torch.float64); ym, xm, yf, xf = G(ym), G(xm), G(yf), G(xf)
    def kosten(dxs, dys):                                                                          # dxs, dys: (S,) Verschiebungen -> (S,) Kosten
        a_ = dF_[(ym[None] + dys[:, None]).clamp(0, H - 1), (xm[None] + dxs[:, None]).clamp(0, W - 1)].mean(1)
        b_ = dM_[(yf[None] - dys[:, None]).clamp(0, H - 1), (xf[None] - dxs[:, None]).clamp(0, W - 1)].mean(1)
        return a_ + b_
    r = int(np.ceil(weite_m * ppm)); st = max(1, int(round(schritt_m * ppm))); sh = torch.arange(-r, r + 1, st, device="cuda")
    dy_, dx_ = torch.meshgrid(sh, sh, indexing="ij"); dy_, dx_ = dy_.ravel(), dx_.ravel()
    k = torch.cat([kosten(dx_[i:i + 256], dy_[i:i + 256]) for i in range(0, len(dx_), 256)]); j = int(torch.argmin(k)); bx, by = int(dx_[j]), int(dy_[j]); kb = float(k[j])
    k0 = float(kosten(torch.zeros(1, dtype=torch.long, device="cuda"), torch.zeros(1, dtype=torch.long, device="cuda"))[0])
    fy, fx = torch.meshgrid(torch.arange(by - st, by + st + 1, device="cuda"), torch.arange(bx - st, bx + st + 1, device="cuda"), indexing="ij")
    kf = kosten(fx.ravel(), fy.ravel()); jf = int(torch.argmin(kf))
    if float(kf[jf]) < kb: kb, bx, by = float(kf[jf]), int(fx.ravel()[jf]), int(fy.ravel()[jf])
    g = float(1 - kb / max(k0, 1e-9))
    return dict(versatz_px=[int(bx), int(by)], versatz_m=round(float(np.hypot(bx, by)) * mpp_med, 3), gewinn=round(g, 4), kosten0=round(float(k0 / kap), 5), kosten_best=round(float(kb / kap), 5), deutlich=bool(g >= 0.08))


def _render(P, N, R, t, f, W, H, cx, cy):
    """wie fehlteile_finden.render (gemeinsamer Renderkern), aber mit vorab abgetasteten Punkten."""
    import render_kern as RK
    depth, idx = RK.tiefenbild(P, R, t, f, cx, cy, W, H)
    if hasattr(depth, "cpu"): depth = depth.cpu().numpy(); idx = idx.cpu().numpy()
    nrm = np.zeros((H, W, 3)); pos = np.zeros((H, W, 3)); tr = idx >= 0
    nrm[tr] = N[idx[tr]]; pos[tr] = P[idx[tr]]
    return depth, nrm, pos



def fotokanten_mehrstufig(gray, ppm, glatt_max_m, glatt_min_m, W, H, stimmen=2, debug=None, kette=False):
    """Fotokanten aus Skalen x Belichtungen (Nutzer 5.11.: 'bis 1 cm runter, Helligkeit/Kontrast variieren, alle Strukturen mergen';
    Fenster im 2. Bogen links 004 lag im Dunkeln). Skalen: Glaettung glatt_min_m .. glatt_max_m (Faktor 2), je Skala Arbeitsaufloesung mit 2 px Glaettung.
    Belichtungen: Gamma 0,4 / 1 / 2,2 + CLAHE (lokaler Kontrast, Schatten unter Boegen). Merge: Pixel zaehlt, wenn er in >= stimmen Varianten
    (Belichtung x benachbarte Skala) innerhalb 1 Arbeitspixel bestaetigt ist (Rauschen/Textur einzelner Varianten faellt raus). Ergebnis duenn, volle Aufloesung."""
    g0 = gray.astype(np.float32) / 255.0
    bel = {"g1": gray, "g04": (np.power(g0, 0.4) * 255).astype(np.uint8), "g22": (np.power(g0, 2.2) * 255).astype(np.uint8),
           "clahe": cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16, 16)).apply(gray)}
    skalen = []; s_ = glatt_max_m
    while s_ >= glatt_min_m * 0.99: skalen.append(s_); s_ /= 2.0
    if skalen[-1] > glatt_min_m * 1.01: skalen.append(glatt_min_m)
    ges = np.zeros((H, W), bool); vor = None; vor_r = 0                                             # Skalen grob -> fein; feine Kante nur, wenn die naechstgroebere Skala
    for s_ in skalen:                                                                                 # innerhalb 1 Sigma (der groben) eine Kante hat (Persistenz; reine Vereinigung = Pflaster/Textur)
        sig = max(1.0, s_ * ppm); r_ = min(1.0, 2.0 / sig); w, h = max(8, int(W * r_)), max(8, int(H * r_))
        st = np.zeros((h, w), np.uint8); e_all = np.zeros((h, w), bool)
        for b in bel.values():
            gs = cv2.GaussianBlur(cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA), (0, 0), max(1.0, sig * r_))
            e = cv2.Canny(gs, 12, 36) > 0; st += cv2.dilate(e.astype(np.uint8), np.ones((3, 3), np.uint8)); e_all |= e
        e_ms = e_all & (st >= stimmen)
        up = cv2.resize(e_ms.astype(np.uint8) * 255, (W, H), interpolation=cv2.INTER_NEAREST)
        if vor is not None:
            k_ = 2 * vor_r + 1; up[cv2.dilate(vor, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_, k_))) == 0] = 0
        if debug: cv2.imwrite(f"{debug}_{s_:.3f}.png", up)
        ges = (up > 0) if kette else (ges | (up > 0)); vor = up; vor_r = max(1, int(round(s_ * ppm)))   # kette: nur Kanten, die ALLE Skalen ueberleben (UND ueber Skalen), sonst ODER
    fk = ges.astype(np.uint8) * 255
    return cv2.ximgproc.thinning(fk) > 0 if hasattr(cv2, "ximgproc") else ges


def lr_mischung(dz, pz, dmax, nf):
    """'a contrario'-Kosten mit geschaetzter Passgenauigkeit: Modellkanten-Abstaende ~ w*Halbnormal(sigma) + (1-w)*p_zufall. Rueckgabe (kosten, sigma_px, w);
    kosten = -max_{w,sigma} sum log(w*r + 1 - w) / nf, r = Halbnormal/p_zufall. Zufallskanten: Erwartung <= 0 (Jensen) -> Kosten steigen; fehlende Kanten: Summe kleiner."""
    c = np.bincount(dz, minlength=dmax + 1).astype(float); N = c.sum(); x = np.arange(dmax + 1); best = (0.0, None, 0.0)
    if N == 0: return 0.0, None, 0.0
    for sig in np.geomspace(1.0, max(1.5, dmax / 1.5), 12):
        hn = np.exp(-0.5 * (x / sig) ** 2); hn /= hn.sum(); r = hn / pz; w = 0.5
        for _ in range(60): w = float((c * (w * r / (w * r + 1 - w))).sum() / N)
        ll = float((c * np.log(w * r + 1 - w)).sum())
        if ll > best[0]: best = (ll, float(sig), w)
    return round(-best[0] / nf, 5), (round(best[1], 2) if best[1] else None), round(best[2], 4)

def _verschieben(mask, dx, dy):
    """Maske um (dx, dy) Pixel verschieben (Bild-x nach rechts, y nach unten); wie die Verschiebung in versatz_schaetzen (Modellpunkt -> Foto)."""
    H, W = mask.shape; ys, xs = np.nonzero(mask); ys = ys + int(dy); xs = xs + int(dx); g = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
    out = np.zeros_like(mask); out[ys[g], xs[g]] = True; return out


def _kosten_param_lr(mkp, fkp, M_, kap_):
    """kosten_param und kosten_lr wie in main (gleiche Formeln, Kopie fuer die versatzkompensierten Felder). (None, None) bei < 50 Kantenpixeln."""
    if mkp.sum() < 50 or fkp.sum() < 50: return None, None
    dFp_ = np.minimum(cv2.distanceTransform((~fkp).astype(np.uint8), cv2.DIST_L2, 5), kap_); dMp_ = np.minimum(cv2.distanceTransform((~mkp).astype(np.uint8), cv2.DIST_L2, 5), kap_)
    kp = round(float((dFp_[mkp].mean() + dMp_[fkp].mean()) / kap_), 5)
    dmax = max(3, int(kap_)); dz = np.minimum(dFp_[M_], dmax).astype(int); pz = np.bincount(dz, minlength=dmax + 1).astype(float) + 1.0; pz /= pz.sum()
    return kp, lr_mischung(np.minimum(dFp_[mkp], dmax).astype(int), pz, dmax, float(fkp.sum()))[0]


def foto_skalieren(im, K):
    """RCPARK_FOTO_SKALA=s (Versuch 10.11. abends, Nutzer 'massiv beschleunigen'): Foto um s verkleinern, Brennweite/Hauptpunkt mit (k1 ist normiert, bleibt).
    NICHT bitgleich zur Vollaufloesung -> Gegenprobe (F1 Tuer/Helm O, Positivtest Verschiebung) Pflicht; Standard 1 = unveraendert."""
    s = float(os.environ.get("RCPARK_FOTO_SKALA") or 1.0)
    if s == 1.0 or im is None: return im, K
    im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    K = json.loads(json.dumps(K)); k = K.get("kamera")
    if k:
        for q in ("f_px", "cx", "cy"):
            if k.get(q) is not None: k[q] = float(k[q]) * s
    return im, K

def _tiefe_vorbereiten(depth, gpu):
    """Silhouette, aufgefuellte Tiefe und Medianabstand dmed aus dem Tiefenbild (frueher inline in main; gleiche Rechnung, bitgleich)."""
    sil = np.isfinite(depth)
    sil_f = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    dfill = depth.copy(); dfill[~sil] = 1e6; dfill = cv2.erode(dfill, np.ones((9, 9), np.uint8))               # Punktrender hat Loecher: naechster Punkt gewinnt
    dfill[(sil_f == 0) | (dfill >= 1e6)] = np.nan
    dm = float(_nanmedian(dfill))
    if gpu and dfill.dtype == np.float32 and _cuda():                                                 # Schnellfassung (11.11., bitgleich): float32 bleibt float32 (float64-Umweg war ein verlustfreier Rundweg), Median auf der GPU in float64
        x_ = dfill.copy(); np.copyto(x_, np.float32(dm), where=np.isnan(x_)); dfill = cv2.medianBlur(x_, 5); dfill[sil_f == 0] = np.nan   # Ausreisser (Restloecher) weg
        dmed = float(_nanmedian(dfill, f64=True))
    else:
        dfill = cv2.medianBlur(np.nan_to_num(dfill, nan=dm).astype(np.float32), 5).astype(np.float64); dfill[sil_f == 0] = np.nan   # Ausreisser (Restloecher) weg
        dmed = float(_nanmedian(dfill))
        if gpu: dfill = dfill.astype(np.float32)                                                     # GPU-Fassung: Tiefe/Meter-je-Pixel/Abstaende in 32 Bit (RAM; Fehler << 1 mm)
    return sil, sil_f, dfill, dmed


def _dmed_fest(cfg, nr, K, W, H, obj, kk, R, t, f, cx0, cy0, gpu, dmed_aktuell):
    """Fester dmed je Foto (Metrik v3_sigma_fest, 11.11.). Ursache (Befund Kreis 11.11.): sigma = glaettung*ppm, ppm = f/dmed, dmed = Median der Modelltiefe in der Silhouette des GANZEN Modells
    -> eine Aenderung am Westhelm veraenderte die Fotokanten (Canny-Glaettung) und damit fk_px/praez eines unveraenderten Teils (Baldachine 0,614 -> 0,499).
    Jetzt: dmed aus dem Referenz-STL cfg['ref'] (eingefroren, bleibt fuer alle Messungen gleich), je Foto einmal berechnet und in cfg['dir'] gespeichert.
    Schluessel = Kamera + Aufloesung + Referenz-STL-Hash + Massstab/Zentrierung/Rahmen + Version. Gleiche Rechnung wie fuer das aktuelle Modell (_tiefe_vorbereiten)."""
    import hashlib
    refp = cfg["ref"]; sha = cfg.get("ref_sha") or hashlib.sha256(open(refp, "rb").read()).hexdigest()[:16]
    key = hashlib.sha1(json.dumps(["v1", sha, nr, W, H, float(f), cx0, cy0, np.asarray(R, float).round(9).tolist(), np.asarray(t, float).round(9).tolist(), obj.get("stl_massstab", 87), obj.get("zentrierung", "huelle"),
                                   kk.get("rahmen_verschiebung"), bool(gpu), os.environ.get("RCPARK_FOTO_SKALA") or "1"], sort_keys=True).encode()).hexdigest()[:24]
    fp = os.path.join(cfg["dir"], f"dmed_{nr}_{key}.json")
    if os.path.exists(fp):
        try: return float(json.load(open(fp))["dmed"])
        except Exception: pass
    m = trimesh.load(refp); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation(np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float))
    depth = RK.dreiecke_rastern(m, R, t, f, cx0, cy0, W, H, nur_tiefe=True)[0]
    dmed = float(_tiefe_vorbereiten(depth, gpu)[3]); del depth
    os.makedirs(cfg["dir"], exist_ok=True); tmpf = fp + f".{os.getpid()}.tmp"
    json.dump({"dmed": dmed, "foto": nr, "ref_sha": sha, "version": "v1", "dmed_aktuell_bei_anlage": dmed_aktuell}, open(tmpf, "w")); os.replace(tmpf, fp)
    return dmed


def main(argv=None):
    """argv: Liste wie auf der Kommandozeile (Mehrfoto-Aufruf im selben Prozess, param_suche.py); Rueckgabe Ergebnis-dict."""
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--tol", type=float, default=0.35)
    ap.add_argument("--laenge", type=float, default=0.8); ap.add_argument("--top", type=int, default=10); ap.add_argument("--streng", action="store_true")
    ap.add_argument("--glaettung", type=float, default=0.18); ap.add_argument("--stl"); ap.add_argument("--eintragen", action="store_true"); ap.add_argument("--bild", help="Foto-Datei statt fotos_dir/<foto>_* (synthetischer Beweis test_foto_diff.py)"); ap.add_argument("--aus", help="Ausgabeordner statt audit/ (Beweislaeufe schreiben nicht ins Objekt)"); ap.add_argument("--kanten", default="normalen", choices=["netz", "tiefenbild", "normalen"], help="normalen (Standard seit 2026-11-04: Knick/Sprung aus Render-Normalen auf der Arbeitsaufloesung der Fotokanten; Beweis test_foto_diff Kaufhaus 004 + Martinstor 014 bestanden) | tiefenbild (alt, Martinstor T1 33 %%, Versatz verzerrt) | netz = exakte Netzkanten mit Strahl-Sichtbarkeit (Entwurf: erfasst Martinstor-Details, aber T1 Kaufhaus 18 %%)"); ap.add_argument("--dichte-max", type=float, default=0.0, help="0 = aus (Standard); >0: Modellkantenpixel im Fenster 2x Glaettung > so viel x Fensterbreite = feiner als aufloesbar, nicht beurteilbar (Entwurf, Martinstor ungeloest)"); ap.add_argument("--tiefen", default="auto", help="Verdecker aus Tiefenkarte: auto (sfm/dicht_*/ des Objekts) | aus | <Dichte-Arbeitsordner mit kameras_unverzerrt.json>"); ap.add_argument("--keine-entzerrung", action="store_true", help="Foto NICHT um k1 entzerren (nur Gegenprobe T5 in test_foto_diff; vorher Standard, Ecken 44-71 px falsch)"); ap.add_argument("--modell-glatt", type=float, default=1.0, help="nur --kanten normalen: Gaussglaettung der Modellnormalen/-tiefe in Arbeitspixeln (Standard 1; 0 -> Martinstor T1 44 %%, 2 -> Modellkanten verschwinden, Fotokanten ohne Modell 79 %%)"); ap.add_argument("--sprung-m", type=float, default=0.25, help="Tiefensprung-Schwelle (2. Differenz, m) der Normalenkanten; 0,25 = bisher. 2026-11-05: frontale 0,25-m-Fensternischen geben im Raster KEINE Modellkante (Pruefung offen, test_foto_diff)"); ap.add_argument("--raster", action="store_true", help="(Standard) Modell EXAKT gerastert (render_kern.dreiecke_rastern, GPU) statt 8 M Punkte: keine Loecher/Pfeffer, kein Zufall"); ap.add_argument("--punkte", action="store_true", help="alte Fassung: Modell aus 8 M Zufallspunkten (auch FD_RASTER=0; CPU-Vergleiche, test_gpu_gleichwertig)"); ap.add_argument("--gpu", action="store_true", help="GPU-Fassung (Abtastung, Z-Puffer, Versatzsuche auf der GPU; auch FD_GPU=1). Nicht bitgleich zur CPU-Fassung, eigener Beweis"); ap.add_argument("--kostenkarte", help="Diagnose: Kostenanteile je Pixel (Modellkante->Foto dF, Fotokante->Modell dM, /Kappe) als .npz"); ap.add_argument("--maske-aus", help="param_suche: Bewertungsbereich (Silhouette + --maske-rand) als PNG schreiben"); ap.add_argument("--maske-rand", type=float, default=1.5, help="Rand der Bewertungsmaske in m (ANNAHME 1,5 m > Rasterweite der Suche)"); ap.add_argument("--bewertung-maske", help="param_suche: feste Maske je Foto -> kosten_param (Umriss eingeschlossen, Bereich unabhaengig vom Parameter)"); ap.add_argument("--region", default="aus", choices=["aus", "himmel", "quader"], help="Bildregion der Bewertung (UND mit --bewertung-maske): himmel = Band um die Himmelsgrenze (Dach/First/Giebel), Fassade zaehlt nicht; quader = Bildhuelle eines Quaders (--region-box) im Modellrahmen, Fussabdruck eines Bauteils")
    ap.add_argument("--region-box", help="x0,y0,z0,x1,y1,z1 in Metern im Rahmen des geladenen Modells (nur --region quader); Foto ohne sichtbaren Quader = nicht beurteilbar"); ap.add_argument("--region-rand", type=float, default=2.0, help="Halbbreite des Himmelsbandes in m (ANNAHME 2 m)"); ap.add_argument("--richtung", type=float, default=0.0, help="0 = aus; >0: Klassenbreite in Grad fuer richtungsgebundenen Abgleich (Entwurf 45)"); ap.add_argument("--schatten-dreh", type=float, default=0.0, help="Gegenprobe: Sonne um so viele Grad um die Hochachse drehen"); ap.add_argument("--schatten", default="aus", choices=["aus", "sonne", "immer"], help="Schlagschatten des Modells + LoD2-Nachbarn als Modellkanten (sonne.json aus sonne_fotos.py): sonne = nur Fotos mit DWD-Sonnenschein; ANNAHME EXIF-Uhr richtig"); ap.add_argument("--glaett-px", type=float, default=2.0, help="Fotokanten auf der Arbeitsaufloesung, in der die Glaettung (--glaettung m) so viele px misst; vorher volle Aufloesung mit 10-28 px Glaettung -> Canny-Gradient unter der Schwelle, 97 Fotokantenpixel in der Silhouette (Beweis test_foto_diff 2026-11-04)"); ap.add_argument("--mehrstufig", action="store_true", help="Fotokanten aus mehreren Skalen (--glaettung bis --mehrstufig-min) x Belichtungen (Gamma/CLAHE) gemergt (Nutzer 5.11.; Entwurf, nicht Standard)"); ap.add_argument("--mehrstufig-min", type=float, default=0.01, help="feinste Glaettung in m (1 cm)"); ap.add_argument("--mehrstufig-stimmen", type=int, default=2, help="Mindestzahl bestaetigender Belichtungsvarianten je Skala"); ap.add_argument("--versatz-max", type=float, default=1.5, help="S2 (2026-11-05): Deckel in m fuer die versatzkompensierten Felder rot_versatz/gelb_versatz/kosten_*_versatz (nur wenn versatz.deutlich und |versatz_m| <= Deckel, sonst gleich rot/gelb/kosten); aendert KEIN bisheriges Feld"); a = ap.parse_args(argv); nr = a.foto
    obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kp = FF.k_datei(a.objekt, obj, root, nr); K = json.load(open(kp)) if os.path.exists(kp) else {}
    im = cv2.imread(a.bild or glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0])
    im, K = foto_skalieren(im, K); H, W = im.shape[:2]
    k1_ent = 0.0
    if not a.keine_entzerrung: im, k1_ent = FF.foto_entzerren(im, K.get("kamera", {}))              # Renderer sind Lochkameras: Foto vorher entzerren (k1 aus K)
    R, t, f, quelle, (zlo, zhi) = FF.kamera_laden(K, obj, nr, root, W, H)
    kk = K.get("kamera", {}); gpu = a.gpu or os.environ.get("FD_GPU") == "1"
    # Raster = STANDARD seit 2026-11-04 (Nutzerentscheid "laenger, aber viel geiler -> machen wir"): Beweise test_foto_diff Martinstor 014 + Kaufhaus 004, test_param_suche.
    # Alte Punktfassung: --punkte oder FD_RASTER=0. Ohne CUDA automatisch Punkte (CPU).
    raster = (a.raster or not (a.punkte or os.environ.get("FD_RASTER") == "0")) and _cuda(); gpu = gpu or raster   # Rasterer laeuft auf der GPU, Folgeschritte nehmen die GPU-Fassung
    cx0, cy0 = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))          # Hauptpunkt aus K (Buendelkameras, kameras_aus_buendel.py), sonst Bildmitte
    if raster:
        import torch
        m = _netz_raster(a.stl or os.path.join(root, obj["stl"]), obj, kk); depth, fid_, pos = RK.dreiecke_rastern(m, R, t, f, cx0, cy0, W, H, als_torch=True)
        if _RUECK is not None: _RUECK["depth"] = depth.copy(); _RUECK["pos"] = pos.clone()
        Nf_ = torch.as_tensor(np.asarray(m.face_normals), dtype=torch.float32, device="cuda"); nrm = torch.zeros((H, W, 3), device="cuda"); ok_ = fid_ >= 0; nrm[ok_] = Nf_[fid_[ok_]]; del fid_, ok_
    else:
        m, P_, N_ = (_netz_gpu if gpu else _netz)(a.stl or os.path.join(root, obj["stl"]), obj, kk)
        depth, nrm, pos = (_render_gpu if gpu else _render)(P_, N_, R, t, f, W, H, cx0, cy0)
    sil, sil_f, dfill, dmed = _tiefe_vorbereiten(depth, gpu)
    dmed_aktuell = dmed
    if _RUECK is not None and _RUECK.get("sigma_fest"):                                           # Metrik v3 (11.11.): dmed (damit sigma, Kappe, Randabstand) je Foto aus dem FESTEN Referenz-STL, nicht aus dem aktuellen Gesamtmodell
        dmed = _dmed_fest(_RUECK["sigma_fest"], nr, K, W, H, obj, kk, R, t, f, cx0, cy0, gpu, dmed_aktuell); _RUECK["dmed_info"] = dict(dmed_fest=dmed, dmed_aktuell=dmed_aktuell)
    ppm = f / dmed
    if a.kanten == "tiefenbild":                                                                 # alte Tiefenbild-Kanten (Gradienten auf voller Aufloesung, ~0,6 GB): in normalen/netz ungenutzt und gleich ueberschrieben -> nur hier rechnen (2026-11-04, bitgleich)
        dsm = cv2.GaussianBlur(np.nan_to_num(dfill, nan=0.0), (0, 0), 3.0)
        gx = cv2.Sobel(dsm, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gy = cv2.Sobel(dsm, cv2.CV_64F, 0, 1, ksize=3) / 8.0
        gxx = cv2.Sobel(gx, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gyy = cv2.Sobel(gy, cv2.CV_64F, 0, 1, ksize=3) / 8.0; gxy = cv2.Sobel(gx, cv2.CV_64F, 0, 1, ksize=3) / 8.0
        mk = (((np.hypot(gx, gy) > 0.2) | ((np.abs(gxx) + np.abs(gyy) + np.abs(gxy)) * ppm > 1.0)) & (sil_f > 0))
        mk = cv2.ximgproc.thinning((mk * 255).astype(np.uint8)) > 0 if hasattr(cv2, "ximgproc") else mk
    else: mk = None
    if a.kanten == "netz": mk = netzkanten(m, R, t, f, cx0, cy0, W, H)
    sigma = max(1.0, a.glaettung * ppm); r_ = min(1.0, a.glaett_px / sigma)
    if a.kanten == "normalen": mk = (normalenkanten_gpu if gpu else normalenkanten)(nrm, depth, r_, W, H, pos=pos, C=-np.asarray(R).T @ np.asarray(t, float), dsauber=dfill, glatt=a.modell_glatt, sprung_m=a.sprung_m) & (sil_f > 0)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if r_ < 1.0:                                                                                   # Arbeitsaufloesung: Glaettung = --glaett-px (vorher 0,18 m x 155 px/m = 28 px -> Canny fand fast nichts, Kaufhaus 004: 100 % 'falsch')
        gs = cv2.GaussianBlur(cv2.resize(gray, None, fx=r_, fy=r_, interpolation=cv2.INTER_AREA), (0, 0), max(1.0, sigma * r_))
        fk = cv2.resize((cv2.Canny(gs, 12, 36) > 0).astype(np.uint8) * 255, (W, H), interpolation=cv2.INTER_NEAREST)
        fk = cv2.ximgproc.thinning(fk) > 0 if hasattr(cv2, "ximgproc") else fk > 0
    else:
        g = cv2.GaussianBlur(gray, (0, 0), sigma); fk = cv2.Canny(g, 12, 36) > 0
    if a.mehrstufig:                                                                                # Nutzer 5.11.: Aufloesung bis 1 cm, Helligkeit/Kontrast durchvariieren, alle Strukturen mergen
        fk = fotokanten_mehrstufig(gray, ppm, a.glaettung, a.mehrstufig_min, W, H, a.mehrstufig_stimmen, os.environ.get("FD_MS_DEBUG"))
    nur_k = _RUECK is not None and bool(_RUECK.get("nur_kosten"))                                  # teil_fotoform-Schnellweg: nach der Kostenkarte Schluss -> mpp/lr-Kosten werden nie gelesen (11.11., bitgleich)
    if not nur_k: sm = np.clip(np.nan_to_num(dfill, nan=dmed), 0.5, 500.0); mpp = sm / f                                   # Meter je Pixel am jeweiligen Punkt
    if a.schatten != "aus" and raster:                                                              # Schlagschatten-Kanten als MODELLkanten (2026-11-05, Nutzerfund Gaubenschatten Foto 018; tools/schatten.py)
        sj = os.path.join(od, "sonne.json"); Sd = (json.load(open(sj))["fotos"].get(nr) if os.path.exists(sj) else None)
        if Sd and (Sd["urteil"] == "Sonne" or a.schatten == "immer") and Sd["hoehe"] > 3:
            import schatten as SC
            from fassade_ortho import nachbarn_netz
            nb, _ = nachbarn_netz(obj)
            if nb is not None: nb = nb.copy(); nb.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
            ms_ = trimesh.util.concatenate([m, nb]) if nb is not None else m
            smk = SC.schattenmaske(ms_, pos, torch.as_tensor(sil, device="cuda"), _sonne_dreh(np.asarray(Sd["sonne_modell"], float), a.schatten_dreh), N=4096, normalen=nrm, eigen_cos=-2.0)   # nur Schlagschatten; Grenzen von Eigenschatten = Geometriekanten
            sk_ = SC.schattenkanten(smk, sil > 0, None)
            if r_ < 1.0:                                                                            # auf die Arbeitsaufloesung der Modellkanten (duenn wie mk)
                sk_ = cv2.resize(cv2.resize(sk_.astype(np.uint8) * 255, None, fx=r_, fy=r_, interpolation=cv2.INTER_AREA), (W, H), interpolation=cv2.INTER_NEAREST) > 0
                sk_ = cv2.ximgproc.thinning(sk_.astype(np.uint8) * 255) > 0 if hasattr(cv2, "ximgproc") else sk_
            mk = mk | (sk_ & (sil_f > 0)); schatten_info = dict(sonne=[Sd["azimut"], Sd["hoehe"]], utc=Sd["utc"], zeitzone=Sd["zeitzone"], dwd_min=Sd["dwd_sonne_min"], kantenpixel=int(sk_.sum()))
            print(f"  Schatten: Sonne Az {Sd['azimut']} / H {Sd['hoehe']} ({Sd['utc']} UTC, DWD {Sd['dwd_sonne_min']} min), {int(sk_.sum())} Schattenkantenpixel", flush=True)
    mk_roh = mk.copy()                                                                             # vor 'nur innen': fuer kosten_param (Umriss zaehlt)
    inner = cv2.erode(sil_f, np.ones((int(0.25 * ppm) | 1,) * 2, np.uint8)) > 0; fk_i = fk & inner
    if a.kanten != "netz": mk &= inner                                                              # Netzkanten: Umriss bleibt (zeigt z. B. zu hohes Dach); Fotokanten zaehlen weiter nur innen
    occ, occ_q = np.zeros((H, W), bool), "aus"
    if a.tiefen != "aus":
        tds = [a.tiefen] if a.tiefen != "auto" else sorted(d for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "sfm", "dicht_*")) if os.path.isdir(d))
        gruende = []
        for td in tds:
            o_, q_ = verdecker_maske(td, nr, f, cx0, cy0, W, H, dfill, kk=kk, abstand=dmed, trennbar=gpu)   # Tor auch fuer ausdrueckliche Ordner (Beweis T6/T6b)
            if o_ is not None: occ, occ_q = o_ & (sil_f > 0), q_; break
            gruende.append(q_)
        else: occ_q = "keine passende Tiefenkarte: " + ("; ".join(gruende) if gruende else "kein sfm/dicht_*")
    mk_vor_occ = int(mk.sum()); mk = mk & ~occ; fk = fk & ~occ; fk_i = fk_i & ~occ
    kp_param = None; kp_lr = None; kp_chamfer = None; kp_state = None
    if a.maske_aus:                                                                                # Bewertungsbereich fuer param_suche: Silhouette + Rand (param_suche vereinigt die Rasterextreme)
        cv2.imwrite(a.maske_aus, (cv2.dilate(sil_f, np.ones((int(2 * a.maske_rand * ppm) | 1,) * 2, np.uint8)) > 0).astype(np.uint8) * 255)
    if a.bewertung_maske:                                                                          # kosten_param (2026-11-04): FESTER Bereich je Foto, Umriss eingeschlossen. kosten0 zaehlt Fotokanten nur in der
        M_ = cv2.imread(a.bewertung_maske, cv2.IMREAD_GRAYSCALE) > 0                               # Modellsilhouette -> niedrigerer First 'versteckt' seine Kante (Beweis Kaufhaus: Wahrheit -0,8 -> gefunden -1,11)
        if a.region == "himmel":                                                                   # Stufe 1 (Nutzer 6.11.): nur Dach-/Giebelkontur gegen den Himmel bewerten, nicht die Fassade (Erker/Arkaden fehlen im Modell und wuerden Dach/First verbiegen)
            try:
                import foto_pick as FP
                sk_ = FP.himmel_cached(im, os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "himmelsmaske", nr + ".png")).astype(np.uint8)
                grenze_ = (cv2.dilate(sk_, np.ones((3, 3), np.uint8)) > 0) & ~(cv2.erode(sk_, np.ones((3, 3), np.uint8)) > 0)
                band_ = cv2.dilate(grenze_.astype(np.uint8), np.ones((int(2 * a.region_rand * ppm) | 1,) * 2, np.uint8)) > 0
                M_ = M_ & band_
            except BaseException as ex_:                                                               # auch SystemExit der Himmelspruefung (Foto ohne plausiblen Himmel, z. B. 001): Foto nur nicht beurteilbar, Lauf laeuft weiter
                print(f"  Region himmel: Himmelsmaske nicht verfuegbar ({str(ex_)[:80]}) -> Foto nicht beurteilbar"); M_ = np.zeros_like(M_)
        if a.region == "quader":                                                                   # Region je Bauteil (Nutzer 6.11. "einzelne Bereiche, nicht mitteln"): Bildhuelle der 8 Quaderecken mit der Kamera dieses Fotos
            try:
                b_ = [float(x) for x in a.region_box.split(",")]; ecken = np.array([[x, y, z] for x in (b_[0], b_[3]) for y in (b_[1], b_[4]) for z in (b_[2], b_[5])])
                Xc_ = ecken @ R.T + t; vorn_ = Xc_[:, 2] > 0.5
                if vorn_.sum() < 8: raise ValueError("Quader nicht komplett vor der Kamera")
                uv_ = np.c_[f * Xc_[:, 0] / Xc_[:, 2] + cx0, f * Xc_[:, 1] / Xc_[:, 2] + cy0]; hull_ = cv2.convexHull(uv_.astype(np.float32)).astype(np.int32)
                q_ = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(q_, hull_, 1); M_ = M_ & (q_ > 0)
            except BaseException as ex_:
                print(f"  Region quader: {str(ex_)[:80]} -> Foto nicht beurteilbar"); M_ = np.zeros_like(M_)
        rand_ = (sil_f > 0) & ~(cv2.erode(sil_f, np.ones((3, 3), np.uint8)) > 0)
        mkp = (mk_roh | rand_) & ~occ & M_; fkp = fk & M_; kap_ = max(1.0, a.tol * ppm)
        if mkp.sum() >= 50 and fkp.sum() >= 50 and nur_k and a.kostenkarte:                        # Schnellweg (11.11.): beide Abstandstransformationen in 2 Threads (cv2 gibt die GIL frei), keine kosten_param/lr-Rechnung, keine Kopien; Karten bitgleich
            from concurrent.futures import ThreadPoolExecutor
            def _dt_(x): d_ = np.minimum(cv2.distanceTransform((~x).astype(np.uint8), cv2.DIST_L2, 5), kap_); return d_, (d_ / kap_).astype(np.float16)
            with ThreadPoolExecutor(2) as ex_: fa_, fb_ = ex_.submit(_dt_, fkp), ex_.submit(_dt_, mkp); (dFp_, dF16_), (dMp_, dM16_) = fa_.result(), fb_.result()
            _RUECK["kosten"] = dict(mkp=mkp, fkp=fkp, dF=dF16_, dM=dM16_, dFp=dFp_)   # dFp = Abstand zur Fotokante, auf kap_ gekappt (teil_fotoform: Kappe ohne zweite Transformation)
        elif mkp.sum() >= 50 and fkp.sum() >= 50:
            dFp_ = np.minimum(cv2.distanceTransform((~fkp).astype(np.uint8), cv2.DIST_L2, 5), kap_); dMp_ = np.minimum(cv2.distanceTransform((~mkp).astype(np.uint8), cv2.DIST_L2, 5), kap_)
            kp_param = round(float((dFp_[mkp].mean() + dMp_[fkp].mean()) / kap_), 5)
            # kosten_lr (2026-11-05, 'a contrario'): Gegenprobe zeigte, dass kosten_param ZUFALLSKANTEN belohnt (+10 % Zufallslinien: -0,3..-0,57; Schatten mit
            # falscher Sonne so gut wie mit richtiger). Je Modellkantenpixel log p_wahr(d)/p_zufall(d), d = Abstand zur Fotokante; p_zufall = Abstaende ALLER Pixel der
            # Bewertungsmaske (Fotokanten-Dichte dieses Fotos), p_wahr = Halbnormal(sigma = Kappe/3) + 5 % gleichverteilt. Summe statt Mittel, / Fotokantenzahl (fest je Foto).
            # Erwartung fuer Zufallskanten <= 0 (= -KL), also kosten_lr steigt; Beweis Kaufhaus 061/088/114/018/044/000: +10 % Zufall +0,02..+0,05.
            dmax = max(3, int(kap_)); dz = np.minimum(dFp_[M_], dmax).astype(int); pz = np.bincount(dz, minlength=dmax + 1).astype(float) + 1.0; pz /= pz.sum()
            xx = np.arange(dmax + 1); pw = np.exp(-0.5 * (xx / max(2.0, kap_ / 3.0)) ** 2); pw = 0.95 * pw / pw.sum() + 0.05 / (dmax + 1)
            lr_tab = np.log(pw / pz); kp_lr_alt = round(float(-lr_tab[np.minimum(dFp_[mkp], dmax).astype(int)].sum() / fkp.sum()), 5)
            # 2026-11-05 Korrektur: festes sigma = Kappe/3 war bei Kameraversatz 0,35-1,3 m zu eng -> fast jede Modellkante 'schlechter als Zufall', HAELFTE DER KANTEN
            # LOESCHEN senkte die Kosten (-0,19..-1,26; null5: Fenster/Boegen verworfen, Giebelparameter am Unterrand). Jetzt Mischung w*Halbnormal(sigma) + (1-w)*p_zufall,
            # w und sigma per ML je Foto und Modell (EM auf sigma-Raster); Kosten = -max log-Verhaeltnis / Fotokantenzahl (<= 0). Beweis (6 Fotos): Haelfte weg +0,006..+0,083,
            # +10 % Zufall +0,001..+0,011, Versatz 1 Kappe +0,008..+0,147 - alle schlechter (test_foto_diff T_LR).
            kp_lr, lr_sig, lr_w = lr_mischung(np.minimum(dFp_[mkp], dmax).astype(int), pz, dmax, float(fkp.sum()))
            kp_state = (mkp, fkp, M_, kap_, occ)                                                      # S2: fuer kosten_*_versatz (nach der Versatzschaetzung)
            if os.environ.get("FD_MASS") == "lr": kp_chamfer, kp_param = kp_param, kp_lr                # qualitaetsstufen Plan "mass": "lr" -> Entscheidungen auf dem fairen Mass
            if a.kostenkarte and _RUECK is not None: _RUECK["kosten"] = dict(mkp=mkp.copy(), fkp=fkp.copy(), dF=(dFp_ / kap_).astype(np.float16), dM=(dMp_ / kap_).astype(np.float16))
            elif a.kostenkarte: np.savez_compressed(a.kostenkarte, mkp=mkp, fkp=fkp, dF=(dFp_ / kap_).astype(np.float16), dM=(dMp_ / kap_).astype(np.float16))   # Diagnose: wo entstehen die Kosten
    if _RUECK is not None and _RUECK.get("nur_kosten"): return None
    dF = cv2.distanceTransform((~fk).astype(np.uint8), cv2.DIST_L2, 5) * mpp
    if a.richtung > 0:                                                                             # richtungsgebunden: Modellkante nur durch Fotokante aehnlicher Richtung bestaetigt (dichte Fassade: sonst findet jede Kante IRGENDEINE in tol; Martinstor T2 0,6 m Versatz = T1)
        nb_ = int(round(180.0 / a.richtung)); rm_, rf_ = kantenrichtung(mk), kantenrichtung(fk); bm, bf = np.floor(rm_ / a.richtung).astype(int) % nb_, np.floor(rf_ / a.richtung).astype(int) % nb_
        dFr = np.full(dF.shape, np.inf, np.float32); dMr = np.full(dF.shape, np.inf, np.float32)
        for b in range(nb_):
            nachbar = lambda B: (B == b) | (B == (b + 1) % nb_) | (B == (b - 1) % nb_)                # eigene + Nachbarklasse (Rand der Klassen)
            db_ = cv2.distanceTransform((~(fk & nachbar(bf))).astype(np.uint8), cv2.DIST_L2, 5); dFr[bm == b] = db_[bm == b]
            dm_ = cv2.distanceTransform((~((mk & nachbar(bm)) | ~inner)).astype(np.uint8), cv2.DIST_L2, 5); dMr[bf == b] = dm_[bf == b]
        dF = np.where(mk, dFr * mpp, dF)                              # Abstand Modellpunkt -> naechste Fotokante [m]
    dM = cv2.distanceTransform((~(mk | ~inner)).astype(np.uint8), cv2.DIST_L2, 5) * mpp
    if a.richtung > 0: dM = np.where(fk, dMr * mpp, dM)                    # Abstand Fotopunkt -> naechste Modellkante [m]
    rr = max(2, int(round(2 * a.glaettung * ppm))); dichte = cv2.boxFilter(mk.astype(np.float32), -1, (2 * rr + 1,) * 2, normalize=False)
    fein = mk & (dichte > a.dichte_max * (2 * rr + 1)) if a.dichte_max > 0 else np.zeros_like(mk)                                             # Modelldetail feiner als die Fotoglaettung: kein Foto kann es auf dieser Skala bestaetigen -> nicht beurteilbar
    mk_alle = mk; mk = mk & ~fein
    falsch = mk & (dF > a.tol); fehlt = fk_i & (dM > a.tol)
    falsch &= ~occ; fehlt &= ~occ                                                                    # verdeckt: weder Bestaetigung noch Widerspruch
    vs = (_versatz_gpu if gpu else versatz_schaetzen)(mk, fk, inner, ppm, float(np.median(mpp[mk])) if mk.any() else 1.0 / ppm, kappe_m=a.tol)
    if os.environ.get("FD_DEBUG"): print("DEBUG ppm", round(ppm,1), "sigma", round(sigma,1), "r_", round(r_,3), "fk", int(fk.sum()), "fk_i", int(fk_i.sum()), "mk", int(mk.sum()), "dF@mk median m", float(np.median(dF[mk])) if mk.any() else None, "mpp median", float(np.median(mpp[mk])) if mk.any() else None, "dfill med", dmed, "f", f)
    def cluster(mask, art):
        mm = cv2.dilate(mask.astype(np.uint8), np.ones((int(0.25 * ppm) | 1,) * 2, np.uint8)); n, lab, st, _ = cv2.connectedComponentsWithStats(mm)
        out = []
        for i in range(1, n):
            x_, y_, w_, h_ = (int(v) for v in st[i, :4]); sl = (slice(y_, y_ + h_), slice(x_, x_ + w_))          # nur der Label-Ausschnitt (vorher Vollbild je Label: 5 s/Foto; gleiche Pixel in gleicher Reihenfolge -> bitgleich)
            sel = (lab[sl] == i) & mask[sl]; npx = int(sel.sum())
            if npx == 0: continue
            lm = npx * float(np.median(mpp[sl][sel]))                                                            # Kantenlaenge ~ Pixel x m/px
            if lm < a.laenge: continue
            ys, xs = np.nonzero(sel); ys = ys + y_; xs = xs + x_; ps_ = pos[sl]; ps_ = ps_.cpu().numpy() if hasattr(ps_, "cpu") else ps_; pz = ps_[sel & np.isfinite(depth[sl])]; P3 = pz.mean(0) if len(pz) else np.array([np.nan] * 3)
            out.append(dict(art=art, laenge_m=round(lm, 2), box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], xyz=[round(float(v), 2) for v in P3],
                            in_ankerzone=bool(zlo is None or (np.isfinite(P3[2]) and zlo <= P3[2] <= zhi))))
        return out
    tr = cluster(falsch, "FALSCH/ERFUNDEN (Modellkante ohne Fotokante)") + cluster(fehlt, "FEHLT (Fotokante ohne Modellkante)")
    tr.sort(key=lambda d: -d["laenge_m"]); tr = tr[:a.top]
    ok = mk & ~falsch; o = im.copy(); o = (o * 0.6).astype(np.uint8)
    if occ.any(): o[occ] = (0.5 * o[occ] + 0.5 * np.array([160, 80, 0])).astype(np.uint8)            # verdeckt (Tiefenkarte naeher als Modell): blau getoent, nicht bewertet
    o[cv2.dilate((fehlt).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 230, 255)
    o[cv2.dilate(ok.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 200, 0)
    o[cv2.dilate(falsch.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 0, 255)
    for k, d in enumerate(tr, 1):
        x0, y0, x1, y1 = d["box"]; col = (0, 0, 255) if d["art"].startswith("FALSCH") else (0, 230, 255)
        cv2.rectangle(o, (x0 - 12, y0 - 12), (x1 + 12, y1 + 12), (255, 255, 255), 3); cv2.putText(o, str(k), (x0, max(30, y0 - 18)), 0, 1.4, col, 4)
    out = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); out = a.aus or out; os.makedirs(out, exist_ok=True)
    cv2.imwrite(os.path.join(out, f"foto_diff_{nr}.jpg"), o, [cv2.IMWRITE_JPEG_QUALITY, 88])
    # ROI-Blatt: je Treffer Foto | Modell-Schattierung (Normalen) mit Kantenlage
    shade = (np.clip(128 + 110 * np.nan_to_num(nrm[..., 1] * 0.5 + nrm[..., 0] * 0.3 + nrm[..., 2] * 0.6), 0, 255).astype(np.uint8) if not hasattr(nrm, "cpu") else
             (128 + 110 * (nrm[..., 1] * 0.5 + nrm[..., 0] * 0.3 + nrm[..., 2] * 0.6).nan_to_num()).clamp(0, 255).to(__import__('torch').uint8).cpu().numpy()); shade[~sil_f.astype(bool)] = 40
    shade = cv2.cvtColor(shade, cv2.COLOR_GRAY2BGR); shade[cv2.dilate(mk.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 200, 0)
    rows = []
    for k, d in enumerate(tr, 1):
        x0, y0, x1, y1 = d["box"]; p = int(0.8 * ppm); x0, y0, x1, y1 = max(0, x0 - p), max(0, y0 - p), min(W, x1 + p), min(H, y1 + p)
        sc = 420.0 / max(1, max(x1 - x0, y1 - y0)); sc = min(sc, 2.0); a1 = cv2.resize(im[y0:y1, x0:x1], None, fx=sc, fy=sc); b1 = cv2.resize(shade[y0:y1, x0:x1], None, fx=sc, fy=sc)
        row = np.hstack([a1, np.full((a1.shape[0], 6, 3), 255, np.uint8), b1]); cv2.putText(row, f"{k} {d['art'][:6]} {d['laenge_m']} m z={d['xyz'][2]}", (6, 24), 0, 0.7, (0, 255, 255), 2); rows.append(row)
    if rows:
        wmax = max(r.shape[1] for r in rows); cv2.imwrite(os.path.join(out, f"foto_diff_{nr}_roi.jpg"), np.vstack([np.pad(r, ((0, 8), (0, wmax - r.shape[1]), (0, 0))) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    erg = dict(foto=nr, kamera=quelle, kamera_datei=os.path.abspath(kp), entzerrt_k1=k1_ent, verdecker=dict(quelle=occ_q, anteil_silhouette=round(float(occ.sum() / max(1, (sil_f > 0).sum())), 4)), f_px=float(f), cx=cx0, cy=cy0, tol_m=a.tol, laenge_m=a.laenge, anteil_modellkanten_ohne_foto=round(float(falsch.sum() / max(1, mk.sum())), 4),
                   anteil_fotokanten_ohne_modell=round(float(fehlt.sum() / max(1, fk_i.sum())), 4), anteil_modellkanten_nicht_beurteilbar=round(float(fein.sum() / max(1, mk_alle.sum())), 4), versatz=vs, treffer=tr, ankerzone=[zlo, zhi])
    if a.bewertung_maske: erg["kosten_param"] = kp_param; erg["kosten_lr"] = kp_lr; erg["kosten_lr_alt"] = kp_lr_alt if kp_lr is not None else None; erg["lr_sigma_px"] = lr_sig if kp_lr is not None else None; erg["lr_w"] = lr_w if kp_lr is not None else None; erg["kosten_chamfer"] = kp_chamfer if kp_chamfer is not None else kp_param
    # S2 (2026-11-05) versatzkompensierte Kennzahlen, NUR ZUSAETZLICH (kein bisheriges Feld geaendert): Modellkanten um den geschaetzten Versatz verschoben, dann rot/gelb/Kosten neu.
    # Nur wenn der Versatz DEUTLICH ist (Gewinn >= 0,08) und |versatz_m| <= --versatz-max; sonst gleich den unkompensierten Werten. Der Versatz ist ein Stoerparameter je Foto-Modell-Paar.
    anw = bool(vs.get("deutlich") and vs.get("versatz_px") is not None and vs.get("versatz_m") is not None and abs(vs["versatz_m"]) <= a.versatz_max)
    erg["modellkanten_px"] = int(mk.sum()); erg["fotokanten_px"] = int(fk_i.sum()); erg["versatz_angewandt"] = anw; erg["versatz_max_m"] = a.versatz_max
    if anw:
        vdx, vdy = vs["versatz_px"]; mk_s = _verschieben(mk, vdx, vdy) & ~occ
        if a.kanten != "netz": mk_s &= inner
        dF_s = cv2.distanceTransform((~fk).astype(np.uint8), cv2.DIST_L2, 5) * mpp; dM_s = cv2.distanceTransform((~(mk_s | ~inner)).astype(np.uint8), cv2.DIST_L2, 5) * mpp
        erg["rot_versatz"] = round(float((mk_s & (dF_s > a.tol) & ~occ).sum() / max(1, mk_s.sum())), 4); erg["gelb_versatz"] = round(float((fk_i & (dM_s > a.tol) & ~occ).sum() / max(1, fk_i.sum())), 4)
        del dF_s, dM_s
    else: erg["rot_versatz"] = erg["anteil_modellkanten_ohne_foto"]; erg["gelb_versatz"] = erg["anteil_fotokanten_ohne_modell"]
    if a.bewertung_maske:
        if anw and kp_state is not None:
            mkp_, fkp_, M2_, kap2_, occ_ = kp_state; kpv, klv = _kosten_param_lr(_verschieben(mkp_, vdx, vdy) & M2_ & ~occ_, fkp_, M2_, kap2_)
            if os.environ.get("FD_MASS") == "lr": kpv = klv
            erg["kosten_param_versatz"] = kpv; erg["kosten_lr_versatz"] = klv
        else: erg["kosten_param_versatz"] = erg.get("kosten_param"); erg["kosten_lr_versatz"] = erg.get("kosten_lr")
    if gpu: erg["gpu"] = True
    if raster: erg["raster"] = True
    json.dump(erg, open(os.path.join(out, f"foto_diff_{nr}.json"), "w"), indent=1, ensure_ascii=False)
    print(f"foto_diff {nr} ({quelle}): Modellkanten ohne Foto {100 * falsch.sum() / max(1, mk.sum()):.1f} %, Fotokanten ohne Modell {100 * fehlt.sum() / max(1, fk_i.sum()):.1f} %, Versatz {vs['versatz_m']} m {vs['versatz_px']} px (Gewinn {vs['gewinn']}{', DEUTLICH: Kamera oder Modell global versetzt' if vs['deutlich'] else ', nicht deutlich'}) -> {out}/foto_diff_{nr}.jpg")
    for k, d in enumerate(tr, 1): print(f"  {k:2d}. {d['art']:46s} {d['laenge_m']:5.1f} m  bei x={d['xyz'][0]} y={d['xyz'][1]} z={d['xyz'][2]}{'' if d['in_ankerzone'] else '  (ausserhalb Ankerzone: unsicher)'}")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from masstabelle_io import aendern, auto_ersetzen
    def _e(tab):
        auto_ersetzen(tab, f"fotodiff-{nr}-"); neu = 0
        for k, d in enumerate(tr, 1):
            if not d["art"].startswith("FALSCH") or not d["in_ankerzone"]: continue
            tab.setdefault("beobachtungen_offen", []).append(dict(datum="auto", wer=f"foto_diff (Foto {nr}, Treffer {k})", auto_id=f"fotodiff-{nr}-{k}", art="kontur_abweichung", foto=nr, xyz=d["xyz"],
                z_von=d["xyz"][2], z_bis=d["xyz"][2], abweichung=d["laenge_m"], text=f"Modellkante ({d['laenge_m']} m) ohne Fotokante in {a.tol} m bei x={d['xyz'][0]} y={d['xyz'][1]} z={d['xyz'][2]}",
                naechster_schritt=f"audit/foto_diff_{nr}_roi.jpg Treffer {k} ansehen; Element am Foto zaehlen/messen (Z-/M-Protokoll), dann Generator")); neu += 1
        return neu
    if a.eintragen and not a.stl: print(f"  -> {aendern(os.path.join(root, obj['masstabelle']), _e)} Beobachtung(en) eingetragen")
    if gpu:                                                                                        # GPU-Zwischenspeicher freigeben: param_suche-Arbeiter laufen viele Aufrufe, torch hielt je Prozess 2,5-3,4 GB -> Ueberlauf (2026-11-04)
        import torch; del nrm, pos; torch.cuda.empty_cache()
    if a.streng and any(not d["art"].startswith("FEHLT") and d["in_ankerzone"] for d in tr): sys.exit(1)
    return erg

if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("foto_diff")   # gemeinsame GPU-Schlange (10.11.: >2-3 gleichzeitige GPU-Pruefungen = Einbruch)
    main()
