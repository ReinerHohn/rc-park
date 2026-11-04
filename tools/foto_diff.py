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
import fehlteile_finden as FF

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
    return dict(versatz_px=[int(bx), int(by)], versatz_m=round(float(np.hypot(bx, by)) * mpp_med, 3), gewinn=round(g, 4),
                deutlich=bool(g >= 0.08))     # ANNAHME 0,08: synthetisch 0,6 m -> Gewinn 0,12-0,34, ohne Versatz <= 0,003; echte Fotos 0,02-0,06 (Kaufhaus 004: Kantenarten uneins -> kein Befund)


def verdecker_maske(tdir, nr, f, cx, cy, W, H, dmodell, tol_m=0.5, tol_rel=0.05, rand=5, kk=None, abstand=None):
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
    u, v = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    mu = (q["fx"] * (u - cx) / f + q["cx"] - 0.5).astype(np.float32); mv = (q["fy"] * (v - cy) / f + q["cy"] - 0.5).astype(np.float32)
    Ds = cv2.remap(D, mu, mv, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--tol", type=float, default=0.35)
    ap.add_argument("--laenge", type=float, default=0.8); ap.add_argument("--top", type=int, default=10); ap.add_argument("--streng", action="store_true")
    ap.add_argument("--glaettung", type=float, default=0.18); ap.add_argument("--stl"); ap.add_argument("--eintragen", action="store_true"); ap.add_argument("--bild", help="Foto-Datei statt fotos_dir/<foto>_* (synthetischer Beweis test_foto_diff.py)"); ap.add_argument("--aus", help="Ausgabeordner statt audit/ (Beweislaeufe schreiben nicht ins Objekt)"); ap.add_argument("--kanten", default="normalen", choices=["netz", "tiefenbild", "normalen"], help="normalen (Standard seit 2026-11-04: Knick/Sprung aus Render-Normalen auf der Arbeitsaufloesung der Fotokanten; Beweis test_foto_diff Kaufhaus 004 + Martinstor 014 bestanden) | tiefenbild (alt, Martinstor T1 33 %%, Versatz verzerrt) | netz = exakte Netzkanten mit Strahl-Sichtbarkeit (Entwurf: erfasst Martinstor-Details, aber T1 Kaufhaus 18 %%)"); ap.add_argument("--dichte-max", type=float, default=0.0, help="0 = aus (Standard); >0: Modellkantenpixel im Fenster 2x Glaettung > so viel x Fensterbreite = feiner als aufloesbar, nicht beurteilbar (Entwurf, Martinstor ungeloest)"); ap.add_argument("--tiefen", default="auto", help="Verdecker aus Tiefenkarte: auto (sfm/dicht_*/ des Objekts) | aus | <Dichte-Arbeitsordner mit kameras_unverzerrt.json>"); ap.add_argument("--keine-entzerrung", action="store_true", help="Foto NICHT um k1 entzerren (nur Gegenprobe T5 in test_foto_diff; vorher Standard, Ecken 44-71 px falsch)"); ap.add_argument("--modell-glatt", type=float, default=1.0, help="nur --kanten normalen: Gaussglaettung der Modellnormalen/-tiefe in Arbeitspixeln (Standard 1; 0 -> Martinstor T1 44 %%, 2 -> Modellkanten verschwinden, Fotokanten ohne Modell 79 %%)"); ap.add_argument("--richtung", type=float, default=0.0, help="0 = aus; >0: Klassenbreite in Grad fuer richtungsgebundenen Abgleich (Entwurf 45)"); ap.add_argument("--glaett-px", type=float, default=2.0, help="Fotokanten auf der Arbeitsaufloesung, in der die Glaettung (--glaettung m) so viele px misst; vorher volle Aufloesung mit 10-28 px Glaettung -> Canny-Gradient unter der Schwelle, 97 Fotokantenpixel in der Silhouette (Beweis test_foto_diff 2026-11-04)"); a = ap.parse_args(); nr = a.foto
    obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kp = FF.k_datei(a.objekt, obj, root, nr); K = json.load(open(kp)) if os.path.exists(kp) else {}
    im = cv2.imread(a.bild or glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]
    k1_ent = 0.0
    if not a.keine_entzerrung: im, k1_ent = FF.foto_entzerren(im, K.get("kamera", {}))              # Renderer sind Lochkameras: Foto vorher entzerren (k1 aus K)
    R, t, f, quelle, (zlo, zhi) = FF.kamera_laden(K, obj, nr, root, W, H)
    m = trimesh.load(a.stl or os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    kk = K.get("kamera", {}); c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]])   # Kamera traegt ihren Rahmen (Buendel); sonst aus der STL (Handkameras wie bisher)
    cx0, cy0 = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))          # Hauptpunkt aus K (Buendelkameras, kameras_aus_buendel.py), sonst Bildmitte
    depth, nrm, pos = FF.render(m, R, t, f, W, H, cx0, cy0, n=8000000); sil = np.isfinite(depth)
    sil_f = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    dfill = depth.copy(); dfill[~sil] = 1e6; dfill = cv2.erode(dfill, np.ones((9, 9), np.uint8))               # Punktrender hat Loecher: naechster Punkt gewinnt
    dfill[(sil_f == 0) | (dfill >= 1e6)] = np.nan
    dm = float(np.nanmedian(dfill)); dfill = cv2.medianBlur(np.nan_to_num(dfill, nan=dm).astype(np.float32), 5).astype(np.float64); dfill[sil_f == 0] = np.nan   # Ausreisser (Restloecher) weg
    dsm = cv2.GaussianBlur(np.nan_to_num(dfill, nan=0.0), (0, 0), 3.0)
    gx = cv2.Sobel(dsm, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gy = cv2.Sobel(dsm, cv2.CV_64F, 0, 1, ksize=3) / 8.0
    dmed = float(np.nanmedian(dfill)); ppm = f / dmed
    gxx = cv2.Sobel(gx, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gyy = cv2.Sobel(gy, cv2.CV_64F, 0, 1, ksize=3) / 8.0; gxy = cv2.Sobel(gx, cv2.CV_64F, 0, 1, ksize=3) / 8.0
    mk = (((np.hypot(gx, gy) > 0.2) | ((np.abs(gxx) + np.abs(gyy) + np.abs(gxy)) * ppm > 1.0)) & (sil_f > 0))
    mk = cv2.ximgproc.thinning((mk * 255).astype(np.uint8)) > 0 if hasattr(cv2, "ximgproc") else mk
    if a.kanten == "netz": mk = netzkanten(m, R, t, f, cx0, cy0, W, H)
    sigma = max(1.0, a.glaettung * ppm); r_ = min(1.0, a.glaett_px / sigma)
    if a.kanten == "normalen": mk = normalenkanten(nrm, depth, r_, W, H, pos=pos, C=-np.asarray(R).T @ np.asarray(t, float), dsauber=dfill, glatt=a.modell_glatt) & (sil_f > 0)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if r_ < 1.0:                                                                                   # Arbeitsaufloesung: Glaettung = --glaett-px (vorher 0,18 m x 155 px/m = 28 px -> Canny fand fast nichts, Kaufhaus 004: 100 % 'falsch')
        gs = cv2.GaussianBlur(cv2.resize(gray, None, fx=r_, fy=r_, interpolation=cv2.INTER_AREA), (0, 0), max(1.0, sigma * r_))
        fk = cv2.resize((cv2.Canny(gs, 12, 36) > 0).astype(np.uint8) * 255, (W, H), interpolation=cv2.INTER_NEAREST)
        fk = cv2.ximgproc.thinning(fk) > 0 if hasattr(cv2, "ximgproc") else fk > 0
    else:
        g = cv2.GaussianBlur(gray, (0, 0), sigma); fk = cv2.Canny(g, 12, 36) > 0
    sm = np.clip(np.nan_to_num(dfill, nan=dmed), 0.5, 500.0); mpp = sm / f                                   # Meter je Pixel am jeweiligen Punkt
    inner = cv2.erode(sil_f, np.ones((int(0.25 * ppm) | 1,) * 2, np.uint8)) > 0; fk_i = fk & inner
    if a.kanten != "netz": mk &= inner                                                              # Netzkanten: Umriss bleibt (zeigt z. B. zu hohes Dach); Fotokanten zaehlen weiter nur innen
    occ, occ_q = np.zeros((H, W), bool), "aus"
    if a.tiefen != "aus":
        tds = [a.tiefen] if a.tiefen != "auto" else sorted(d for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "sfm", "dicht_*")) if os.path.isdir(d))
        gruende = []
        for td in tds:
            o_, q_ = verdecker_maske(td, nr, f, cx0, cy0, W, H, dfill, kk=kk, abstand=dmed)   # Tor auch fuer ausdrueckliche Ordner (Beweis T6/T6b)
            if o_ is not None: occ, occ_q = o_ & (sil_f > 0), q_; break
            gruende.append(q_)
        else: occ_q = "keine passende Tiefenkarte: " + ("; ".join(gruende) if gruende else "kein sfm/dicht_*")
    mk_vor_occ = int(mk.sum()); mk = mk & ~occ; fk = fk & ~occ; fk_i = fk_i & ~occ
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
    vs = versatz_schaetzen(mk, fk, inner, ppm, float(np.median(mpp[mk])) if mk.any() else 1.0 / ppm, kappe_m=a.tol)
    if os.environ.get("FD_DEBUG"): print("DEBUG ppm", round(ppm,1), "sigma", round(sigma,1), "r_", round(r_,3), "fk", int(fk.sum()), "fk_i", int(fk_i.sum()), "mk", int(mk.sum()), "dF@mk median m", float(np.median(dF[mk])) if mk.any() else None, "mpp median", float(np.median(mpp[mk])) if mk.any() else None, "dfill med", dmed, "f", f)
    def cluster(mask, art):
        mm = cv2.dilate(mask.astype(np.uint8), np.ones((int(0.25 * ppm) | 1,) * 2, np.uint8)); n, lab, st, _ = cv2.connectedComponentsWithStats(mm)
        out = []
        for i in range(1, n):
            sel = (lab == i) & mask; npx = int(sel.sum())
            if npx == 0: continue
            lm = npx * float(np.median(mpp[sel]))                                                                # Kantenlaenge ~ Pixel x m/px
            if lm < a.laenge: continue
            ys, xs = np.nonzero(sel); pz = pos[sel & np.isfinite(depth)]; P3 = pz.mean(0) if len(pz) else np.array([np.nan] * 3)
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
    shade = np.clip(128 + 110 * np.nan_to_num(nrm[..., 1] * 0.5 + nrm[..., 0] * 0.3 + nrm[..., 2] * 0.6), 0, 255).astype(np.uint8); shade[~sil_f.astype(bool)] = 40
    shade = cv2.cvtColor(shade, cv2.COLOR_GRAY2BGR); shade[cv2.dilate(mk.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 200, 0)
    rows = []
    for k, d in enumerate(tr, 1):
        x0, y0, x1, y1 = d["box"]; p = int(0.8 * ppm); x0, y0, x1, y1 = max(0, x0 - p), max(0, y0 - p), min(W, x1 + p), min(H, y1 + p)
        sc = 420.0 / max(1, max(x1 - x0, y1 - y0)); sc = min(sc, 2.0); a1 = cv2.resize(im[y0:y1, x0:x1], None, fx=sc, fy=sc); b1 = cv2.resize(shade[y0:y1, x0:x1], None, fx=sc, fy=sc)
        row = np.hstack([a1, np.full((a1.shape[0], 6, 3), 255, np.uint8), b1]); cv2.putText(row, f"{k} {d['art'][:6]} {d['laenge_m']} m z={d['xyz'][2]}", (6, 24), 0, 0.7, (0, 255, 255), 2); rows.append(row)
    if rows:
        wmax = max(r.shape[1] for r in rows); cv2.imwrite(os.path.join(out, f"foto_diff_{nr}_roi.jpg"), np.vstack([np.pad(r, ((0, 8), (0, wmax - r.shape[1]), (0, 0))) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(dict(foto=nr, kamera=quelle, kamera_datei=os.path.abspath(kp), entzerrt_k1=k1_ent, verdecker=dict(quelle=occ_q, anteil_silhouette=round(float(occ.sum() / max(1, (sil_f > 0).sum())), 4)), f_px=float(f), cx=cx0, cy=cy0, tol_m=a.tol, laenge_m=a.laenge, anteil_modellkanten_ohne_foto=round(float(falsch.sum() / max(1, mk.sum())), 4),
                   anteil_fotokanten_ohne_modell=round(float(fehlt.sum() / max(1, fk_i.sum())), 4), anteil_modellkanten_nicht_beurteilbar=round(float(fein.sum() / max(1, mk_alle.sum())), 4), versatz=vs, treffer=tr, ankerzone=[zlo, zhi]), open(os.path.join(out, f"foto_diff_{nr}.json"), "w"), indent=1, ensure_ascii=False)
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
    if a.streng and any(not d["art"].startswith("FEHLT") and d["in_ankerzone"] for d in tr): sys.exit(1)

if __name__ == "__main__":
    main()
