#!/usr/bin/env python3
"""rund_aus_umriss.py - RUNDE KOERPER (Treppenturm, Rundturm, Saeule, Erkertuermchen) aus den FOTO-UMRISSEN vermessen (21.11.2026).

Warum: ein Zylinder hat keine festen Kanten - nur einen Umriss, der mit dem Blickwinkel wandert. Der Kanten-Sweep (tools/kantenstufe.py) trianguliert feste
Kanten und findet auf runden Teilen nichts (Schwabentor: 1823 Kantenpunkte nahe dem Treppenturm, alle 2,1-2,3 m von seiner Achse = Turmwand). Die dichte Wolke
misst runde Teile zu dick (Schwabentor Treppenturm Wolke r 1,73 m, Handstand per foto_mass 1,56 m). KERNMETHODE: Form aus Fotos, Wolke nur Lage.

Verfahren (Umriss-Tangenten, "visual hull" fuer einen Drehkoerper):
 1. Kandidat aus audit/koerper_auto.json (tools/wolke_rest.py, Form 'rund'): nur Ort und Hoehenbereich. Der Wolkenradius ist NUR Startwert der Suche.
 2. Je kalibriertem Foto (messprotokoll/K-*.json, flaeche_ortho.kameras_laden) und Hoehe z: fuer einen Kreis (cx, cy, r) liegen die beiden Umrisspunkte dort, wo der
    Sehstrahl den Kreis beruehrt. Dort wird der Bildgradient QUER zum Umriss gelesen (Richtung = Projektion der Kreisnormalen).
 3. Abstimmung: jede Beobachtung (Foto x Seite x Hoehe) wird auf ihr Maximum ueber alle Kandidaten normiert - jedes Foto zaehlt gleich, ein starker Fugen-
    oder Eckkantenzug in einem Foto kann nicht allein gewinnen; nur ein Kreis, der in VIELEN Fotos auf einer Kante liegt, gewinnt.
    Verdeckt (Strahl zum Umrisspunkt trifft vorher das Modell, z. B. Turmwand) -> Beobachtung entfaellt.
 4. Grob-fein: Mitte +-0,6 m, Radius 0,5..1,4 x Start; dann Feinraster. Danach je Hoehe nur noch r (Mitte fest) -> Drehprofil r(z).
 5. Oberkante: Umriss-Stuetze je Hoehe (mittlere Abstimmung am besten r), auch 3 m ueber der Wolke; Ende = letzte Hoehe mit >= 50 % der Median-Stuetze (ANNAHME).
Ausgabe: koerper_auto.json je Haufen 'umriss' (Masse, Stuetze, Fotos, Profil); mit --uebernehmen ersetzt das Fotomass 'kreis'/'profil' (Wolkenwerte bleiben als
'kreis_wolke'/'profil_wolke'); Bild audit/rund_umriss_<id>.jpg (Fotoausschnitte: gruen Foto-Umriss, rot Wolkenkreis; rechts Profil).
Aufruf: rund_aus_umriss.py <objekt.json> [--koerper audit/koerper_auto.json] [--stl STL] [--uebernehmen] [--max-fotos 120]
rc 0 = mindestens ein Rundkoerper vermessen, rc 3 = kein Kandidat, rc 4 = zu wenig Fotos/Stuetze (nichts uebernommen).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

# ---- Schwellen (Grund je Zeile; nicht an einem Bauwerk eingestellt) ---------------------------------------------------------------------------
MIN_R_PX = 12          # Radius im Foto mind. 12 px - darunter liegt der Umriss in 1-2 px Gradientenbreite, Radius nicht aufloesbar
STUFEN_R_PX = (25, 60)  # Bildpyramide: Radius in px fuer Grob- (Schritt 10 cm) und Mittelstufe (3 cm) - Kante etwa so breit wie der Schritt
MAX_R_PX = 150         # Feinstufe (Schritt 1 cm / 5 mm): volle Aufloesung bis 150 px Radius (1 px ~1 cm bei r 1,5 m); mehr Pixel zeigen nur Steinkoernung
MIN_FOTOS = 12        # mind. 12 Fotos mit Beobachtungen; Formfamilie aus >= 3 Fotos (CLAUDE.md), hier mehr, weil jede Seite einzeln verdeckt sein kann
MIN_SEITEN_FOTOS = 4   # je Seite (links/rechts vom Turm aus gesehen) mind. 4 Fotos, sonst ist der Radius nur einseitig bestimmt (Mitte und r gekoppelt)
STUETZE_ENDE = 0.5     # Oberkante: Stuetze faellt unter 50 % des Medians (ANNAHME)
SUCHE_MITTE = 0.6      # m: Wolkenmitte ist auf Dezimeter genau (Kreisausgleich Rest ~5 cm), 0,6 m laesst ihr deutlich Spielraum
FAECHER_GRAD = 15      # Richtungsfaecher fuer die Gewichtung der Beruehrlinien (24 Faecher rundum; feiner = zu wenige Beobachtungen je Faecher)
SUCHE_R = (0.5, 1.4)   # x Startradius: Wolke misst eher zu dick (Fasen, Rauschen), daher nach unten weiter offen


def lade(p):
    try: return json.load(open(p))
    except Exception: return None


def tangenten(c, r, Cxy):
    """Beruehrpunkte der Sehstrahlen vom Kamerastandort Cxy (2) an Kreise (c: K x 2, r: K) -> T (2, K, 2) [links, rechts], Normalen (2, K, 2), gueltig (K)."""
    v = Cxy[None, :] - c; D = np.linalg.norm(v, axis=1); ok = D > r * 1.05
    u = v / np.maximum(D, 1e-9)[:, None]; up = np.c_[-u[:, 1], u[:, 0]]
    ca = np.clip(r / np.maximum(D, 1e-9), -1, 1); sa = np.sqrt(1 - ca * ca)
    N = np.stack([ca[:, None] * u + sa[:, None] * up, ca[:, None] * u - sa[:, None] * up])
    return c[None] + r[None, :, None] * N, N, ok


class Bild:
    """Gradientenbild (Ausschnitt um den Kandidaten) eines Fotos + Projektion."""
    def __init__(self, c, img, box, proj, q=1.0):
        """q < 1: Ausschnitt verkleinert (21.11.2026: 120 nahe 12-MP-Fotos in voller Aufloesung = 11 GB, Lauf vom System beendet) - Radius bleibt >= MAX_R_PX/2 px."""
        import cv2
        self.c, self.proj = c, proj
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        W = c["cx"] * 2
        x0, y0, x1, y1 = [int(v) for v in box]; x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(g.shape[1], x1), min(g.shape[0], y1)
        a = g[y0:y1, x0:x1]
        if q < 1.0: a = cv2.resize(a, (max(4, int(a.shape[1] * q)), max(4, int(a.shape[0] * q))), interpolation=cv2.INTER_AREA)
        self.s = g.shape[1] / W * q; self.x0, self.y0 = x0 * q, y0 * q        # Pixel im Ausschnitt = (Bildpixel) * q - Versatz
        a = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 1.2)
        self.gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3).astype(np.float16); self.gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3).astype(np.float16)   # float16: halber Speicher, Gradient braucht keine 7 Stellen

    def pix(self, X):
        px, z, _ = self.proj(X, self.c); return px * self.s, z

    def quer(self, X, N3):
        """|Gradient . Bildrichtung der Normalen| an den 3D-Punkten X (n x 3) mit horizontaler Normalen N3 (n x 3)."""
        p, z = self.pix(X); q, _ = self.pix(X + 0.05 * N3); d = q - p; d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        x = p[:, 0] - self.x0; y = p[:, 1] - self.y0; h, w = self.gx.shape
        ok = (z > 0.5) & (x >= 1) & (y >= 1) & (x < w - 2) & (y < h - 2); xi = np.clip(x, 1, w - 2); yi = np.clip(y, 1, h - 2)
        x0 = np.floor(xi).astype(int); y0 = np.floor(yi).astype(int); fx = xi - x0; fy = yi - y0
        def bil(G): return (G[y0, x0] * (1 - fx) * (1 - fy) + G[y0, x0 + 1] * fx * (1 - fy) + G[y0 + 1, x0] * (1 - fx) * fy + G[y0 + 1, x0 + 1] * fx * fy)
        return np.where(ok, np.abs(bil(self.gx) * d[:, 0] + bil(self.gy) * d[:, 1]), np.nan)


def bewerten(bilder, obs, c, r, gew=None):
    """Summe der normierten Abstimmungen fuer Kreise (c: K x 2, r: K). obs: Liste (bildindex, seite, z). gew: Gewicht je Beobachtung. -> Punkte (K), Zahl Beob. (K), je Beob. Werte."""
    K = len(r); summe = np.zeros(K); n = np.zeros(K); roh = []
    for oi, (bi, seite, z) in enumerate(obs):
        B = bilder[bi]; T, N, ok = tangenten(c, r, B.Cxy)
        X = np.c_[T[seite], np.full(K, z)]; N3 = np.c_[N[seite], np.zeros(K)]
        s = B.quer(X, N3); s[~ok] = np.nan
        m = np.nanmax(s) if np.isfinite(s).any() else 0
        if m <= 0: roh.append(None); continue
        s = np.nan_to_num(s / m); w = 1.0 if gew is None else gew[oi]; summe += w * s; n += 1; roh.append(s)
    return summe, n, roh


def vermessen(bilder, start, z_ebenen, log=print, verdeckt=None):
    """Kern (ohne Dateien, fuer den Test): bilder = Liste Bild (mit .Cxy) ODER Liste von 3 Listen [grob, mittel, fein] (dieselben Fotos in 3 Aufloesungen);
    start = (x, y, r); z_ebenen = Hoehen. -> dict Masse.
    21.11.2026 Bildpyramide: bei hoher Aufloesung ist die Umrisskante (2-3 px) schmaler als der Rasterschritt der Grobsuche -> Guetegebirge aus Nadeln, Grobraster trifft
    Zufallsspitzen (Schwabentor: r sprang je Aufloesung 1,0 / 1,55 / 2,3 m). Jede Stufe sucht in der Aufloesung, die zu ihrem Schritt passt (Radius ~25 / ~60 / bis MAX_R_PX px)."""
    stufen = bilder if isinstance(bilder[0], (list, tuple)) else [bilder] * 3; bilder = stufen[0]; x0, y0, r0 = start
    obs = [(bi, s, z) for bi in range(len(bilder)) for s in (0, 1) for z in z_ebenen if not (verdeckt and verdeckt(bi, s, z))]
    if not obs: return None
    def raster(cx, cy, dm, sm, r_lo, r_hi, sr):
        g = np.arange(-dm, dm + 1e-9, sm); rr = np.arange(r_lo, r_hi + 1e-9, sr)
        A, B_, R = np.meshgrid(cx + g, cy + g, rr, indexing="ij"); return np.c_[A.ravel(), B_.ravel()], R.ravel()
    # 21.11.2026 (Schwabentor: 112 Fotos sehen den linken, 31 den rechten Umriss -> Mitte/Radius gekoppelt, Ergebnis sprang je Aufloesung zwischen r 1,0 und 1,55):
    # Gewicht je Beobachtung = 1 / Zahl der Beobachtungen mit aehnlicher Richtung der Beruehrlinie (Normale am Startkreis, Faecher 15 Grad) -> jede Blickrichtung zaehlt gleich.
    def gewichte(ol):
        az = []
        for bi, s_, z in ol:
            _, N, _ = tangenten(np.array([[x0, y0]]), np.array([r0]), bilder[bi].Cxy); az.append(int(np.degrees(np.arctan2(N[s_, 0, 1], N[s_, 0, 0])) // FAECHER_GRAD))
        az = np.array(az); u, cnt = np.unique(az, return_counts=True); m = dict(zip(u, cnt)); return np.array([1.0 / m[a] for a in az])
    zs = sorted(set(z for _, _, z in obs)); zg = zs[::max(1, len(zs) // 6)]           # Grobsuche auf ~6 Hoehen (Mitte/Radius gemeinsam, Profil spaeter)
    og = [o for o in obs if o[2] in zg]; wg = gewichte(og)
    c, r = raster(x0, y0, SUCHE_MITTE, 0.1, SUCHE_R[0] * r0, SUCHE_R[1] * r0, 0.05); P, n, _ = bewerten(stufen[0], og, c, r, wg); i = int(np.argmax(P))
    c, r = raster(c[i][0], c[i][1], 0.15, 0.03, r[i] - 0.1, r[i] + 0.1, 0.02); P, n, _ = bewerten(stufen[1], og, c, r, wg); i = int(np.argmax(P))
    c, r = raster(c[i][0], c[i][1], 0.05, 0.01, r[i] - 0.04, r[i] + 0.04, 0.005); P, n, _ = bewerten(stufen[2], og, c, r, wg); i = int(np.argmax(P))
    cx, cy, rg = float(c[i][0]), float(c[i][1]), float(r[i])
    # Stuetze und Seitenzahl am Gewinner
    _, _, roh = bewerten(stufen[1], obs, np.array([[cx, cy]]), np.array([rg]))
    fotos = {s: sorted(set(obs[k][0] for k, v in enumerate(roh) if v is not None and obs[k][1] == s)) for s in (0, 1)}
    # Profil r(z) bei fester Mitte
    rr = np.arange(SUCHE_R[0] * r0, SUCHE_R[1] * r0 + 1e-9, 0.02); prof = []
    for z in zs:
        oz = [o for o in obs if o[2] == z]
        if not oz: continue
        wz = gewichte(oz); P, n, _ = bewerten(stufen[1], oz, np.tile([cx, cy], (len(rr), 1)), rr, wz)
        if n.max() < 3: continue
        j = int(np.argmax(P)); rf = np.arange(rr[j] - 0.04, rr[j] + 0.04 + 1e-9, 0.005); Pf, nf, _ = bewerten(stufen[2], oz, np.tile([cx, cy], (len(rf), 1)), rf, wz); jf = int(np.argmax(Pf))
        prof.append([round(z, 2), round(float(rf[jf]), 3), int(n.max()), round(float(P[j] / wz.sum()), 3)])
    # Rest: Streuung der Einzelbeobachtungen um den Gewinner (je Beob. bestes r bei fester Mitte, Median-Abstand)
    _, _, ro = bewerten(stufen[1], obs, np.tile([cx, cy], (len(rr), 1)), rr)
    best = np.array([rr[int(np.argmax(v))] for v in ro if v is not None]); rest = float(np.median(np.abs(best - rg))) if len(best) else float("nan")
    return dict(x=round(cx, 3), y=round(cy, 3), r=round(rg, 3), rest_beob=round(rest, 3), beobachtungen=len(best), profil=prof,
                fotos_links=len(fotos[0]), fotos_rechts=len(fotos[1]), fotos=len(set(fotos[0]) | set(fotos[1])))


def glaetten(prof):
    """Median ueber 3 Hoehen: einzelne Hoehen, an denen die Mehrheit auf eine Fuge/Kante stimmt (Schwabentor 21.11.: 2,38 / 0,99 m zwischen 1,55-Werten), fallen weg."""
    r = [p[1] for p in prof]; g = [float(np.median(r[max(0, i - 1):i + 2])) for i in range(len(r))]
    return [[p[0], round(gi, 3), p[2], p[3]] for p, gi in zip(prof, g)]


def traufe(prof, schritt, ueber=1.08, anteil=0.85):
    """Traufe des Rundkoerpers aus dem geglaetteten Profil (ANNAHMEN, Schwabentor 21.11.: Schaft 1,57-1,62, Ueberstand 1,79-1,86 bei z 11,25-12,25, Kegeldach darueber):
    1. Dachueberstand: in der oberen Haelfte Hoehen mit r > ueber x Schaftmedian (8 % = deutlich ueber der Streuung 2-3 cm des Schafts) -> Traufe = Hoehe des groessten Radius.
    2. sonst Haube ohne Ueberstand: erste Hoehe, ab der r fuer >= 2 Hoehen unter anteil x Schaft faellt.  None = kein Uebergang gesehen."""
    if len(prof) < 4: return None
    h = max(2, len(prof) // 2); rs = float(np.median([p[1] for p in prof[:h]]))
    ob = [p for p in prof[h // 2:] if p[1] > ueber * rs]
    if ob: return max(ob, key=lambda p: (p[1], -p[0]))[0]
    for i in range(len(prof) - 1):
        if prof[i][1] < anteil * rs and prof[i + 1][1] < anteil * rs: return round(prof[i][0] - schritt / 2, 2)
    return None


def oberkante(prof):
    """Ende der Umriss-Stuetze: letzte Hoehe (von unten durchgehend) mit Stuetze >= STUETZE_ENDE x Median (ANNAHME)."""
    if not prof: return None
    med = float(np.median([p[3] for p in prof])); ende = None
    for p in prof:
        if p[3] >= STUETZE_ENDE * med: ende = p[0]
        elif ende is not None: break
    return ende


def main(argv=None):
    import cv2, flaeche_ortho as FO
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--koerper"); ap.add_argument("--stl"); ap.add_argument("--uebernehmen", action="store_true")
    ap.add_argument("--max-fotos", type=int, default=120); ap.add_argument("--schritt", type=float, default=0.5); ap.add_argument("--ueber", type=float, default=3.0)
    ap.add_argument("--max-r-px", type=float, default=MAX_R_PX); ap.add_argument("--nur-messen", action="store_true", help="koerper_auto.json nicht schreiben (Vergleichslaeufe)")
    a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); A = os.path.join(od, "audit"); kp = a.koerper or os.path.join(A, "koerper_auto.json"); KA = lade(kp)
    if not KA: print("keine", kp); return 3
    rund = [h for h in KA.get("haufen", []) if h.get("form") == "rund" and h.get("kreis") and h.get("angenommen") is not False]
    if not rund: print("kein Rundkandidat in", kp); return 3
    obj, cams = FO.kameras_laden(a.objekt)
    stlp = a.stl or os.path.join(FO.ROOT, obj["stl"]) if obj.get("stl") else a.stl; inter = None
    if stlp and os.path.exists(stlp):
        import trimesh; m = trimesh.load(stlp); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); inter = m.ray   # Embree, falls vorhanden (21.11.2026: ray_triangle in numpy auf 2,4 Mio. Dreiecken = 11 GB, Lauf beendet)
    rc = 4
    for H in rund:
        k = H.get("kreis_wolke") or H["kreis"]; x0, y0, r0 = k["x"], k["y"], k["r"]; kz = H["kasten"]; za, zb = max(kz[2], 0.3), kz[5]
        zs = list(np.round(np.arange(za + a.schritt / 2, zb + a.ueber, a.schritt), 2))
        Xa = np.array([[x0, y0, z] for z in (za, (za + zb) / 2, zb)])
        wahl = []
        for nr, (c, pf) in cams.items():
            px, z, C = FO.projektion(Xa, c); W, Hh = c["cx"] * 2, c["cy"] * 2
            if not ((z > 1).all() and (px[:, 0] > 0).all() and (px[:, 0] < W).all() and (px[:, 1] > -0.2 * Hh).all() and (px[:, 1] < 1.2 * Hh).all()): continue
            d = float(np.linalg.norm(C[:2] - Xa[0, :2])); rpx = r0 * c["f_px"] / max(d, 1e-6)
            if rpx >= MIN_R_PX: wahl.append((rpx, nr, c, pf, C))
        wahl.sort(key=lambda w: -w[0]); wahl = wahl[:a.max_fotos]
        print(f"{H.get('id')}: Start (Wolke) x {x0:.2f} y {y0:.2f} r {r0:.2f}, z {za:.1f}..{zb:.1f} (+{a.ueber} m darueber); {len(wahl)} Fotos mit r >= {MIN_R_PX} px")
        bilder = []; verd = {}; stufe = ([], [], [])
        for rpx, nr, c, pf, C in wahl:
            im = cv2.imread(pf, cv2.IMREAD_GRAYSCALE)
            if im is None: continue
            ring = np.array([[x0 + 1.6 * r0 * math.cos(t), y0 + 1.6 * r0 * math.sin(t), z] for t in np.linspace(0, 2 * math.pi, 16, endpoint=False) for z in (za, zs[-1])])
            p, zz, _ = FO.projektion(ring, c); p = p * (im.shape[1] / (c["cx"] * 2)); p = p[zz > 0.5]
            if len(p) < 4: continue
            box = (p[:, 0].min() - 10, p[:, 1].min() - 10, p[:, 0].max() + 10, p[:, 1].max() + 10)
            rpx_bild = rpx * im.shape[1] / (c["cx"] * 2); drei = []
            for ziel in (STUFEN_R_PX[0], STUFEN_R_PX[1], a.max_r_px):
                B = Bild(c, im, box, FO.projektion, min(1.0, ziel / max(rpx_bild, 1e-6))); B.Cxy = np.asarray(C[:2], float); B.C = np.asarray(C, float); B.nr = nr; B.pf = pf; drei.append(B)
            del im; bilder.append(drei[0]); stufe[0].append(drei[0]); stufe[1].append(drei[1]); stufe[2].append(drei[2])
        if inter is not None:                                                     # Verdeckung des Umrisspunkts (Startkreis + 8 %, ausserhalb des Wolken-Rundkoerpers)
            for bi, B in enumerate(bilder):
                T, N, ok = tangenten(np.array([[x0, y0]]), np.array([r0 * 1.08 + 0.05]), B.Cxy)
                for s in (0, 1):
                    X = np.array([[T[s, 0, 0], T[s, 0, 1], z] for z in zs]); v = X - B.C; dist = np.linalg.norm(v, axis=1)
                    _, ri, loc = inter.intersects_id(np.broadcast_to(B.C, X.shape), v / dist[:, None], multiple_hits=False, return_locations=True)
                    vor = np.full(len(X), np.inf); vor[ri] = np.linalg.norm(loc - B.C, axis=1)
                    for z, vz, dz in zip(zs, vor, dist): verd[(bi, s, z)] = bool(vz < dz - 0.15)
        nv = sum(verd.values()); print(f"  {len(bilder)} Fotos geladen; {nv} von {len(verd)} Umrissbeobachtungen verdeckt (Modell davor)")
        U = vermessen(list(stufe), (x0, y0, r0), zs, verdeckt=lambda bi, s, z: verd.get((bi, s, z), False))
        if not U: print("  keine Beobachtung"); continue
        U["profil_roh"] = U["profil"]; U["profil"] = glaetten(U["profil"])
        U["oberkante"] = oberkante([p for p in U["profil"] if p[0] >= za]); U["traufe"] = traufe([p for p in U["profil"] if p[0] >= za], a.schritt); U["start_wolke"] = dict(x=x0, y=y0, r=r0)
        sch = [p[1] for p in U["profil"][:max(2, len(U["profil"]) // 2)]]; U["r_schaft"] = round(float(np.median(sch)), 3) if sch else U["r"]
        U["quelle"] = "tools/rund_aus_umriss.py: Umriss-Tangenten in kalibrierten Fotos (messprotokoll/K-*.json), Abstimmung je Foto/Seite/Hoehe normiert"
        U["annahmen"] = ["ANNAHME: Traufe = groesster Radius > 108 % des Schafts in der oberen Haelfte (Dachueberstand), sonst Beginn der Verjuengung < 85 %", "Spitze ueber dem Ende der Umriss-Stuetze FEHLT (nicht gemessen, nicht erfunden)", f"ANNAHME: Oberkante = Ende der Umriss-Stuetze (< {STUETZE_ENDE:.0%} des Medians)", "ANNAHME: Querschnitt kreisrund, Achse lotrecht"]
        gut = U["fotos"] >= MIN_FOTOS and min(U["fotos_links"], U["fotos_rechts"]) >= MIN_SEITEN_FOTOS
        U["gueltig"] = gut; U["grund"] = None if gut else f"zu wenig Fotos ({U['fotos']}, links {U['fotos_links']}, rechts {U['fotos_rechts']})"
        H["umriss"] = U
        print(f"  FOTO-UMRISS: x {U['x']:.2f} y {U['y']:.2f} r {U['r']:.3f} m (Wolke r {r0:.2f}), Rest je Beobachtung {U['rest_beob']} m, {U['beobachtungen']} Beob., "
              f"Fotos {U['fotos']} (links {U['fotos_links']}, rechts {U['fotos_rechts']}), Schaft r {U['r_schaft']}, Traufe {U['traufe']}, Oberkante Umriss {U['oberkante']}  -> {'GUELTIG' if gut else 'UNGUELTIG: ' + U['grund']}")
        print("  Profil z:r(Stuetze) " + " ".join(f"{p[0]:g}:{p[1]:.2f}({p[3]:.2f})" for p in U["profil"]))
        if gut and a.uebernehmen:
            H.setdefault("kreis_wolke", H["kreis"]); H.setdefault("profil_wolke", H.get("profil"))
            ok_ = [p for p in U["profil"] if p[0] <= (U["oberkante"] or zb)]       # ganzes Foto-Profil (Schaft, Ueberstand, Dach) bis zum Ende der Umriss-Stuetze
            H["traufe"] = U["traufe"]
            H["kreis"] = dict(x=U["x"], y=U["y"], r=U["r"], rest=U["rest_beob"], quelle="foto_umriss"); H["profil"] = [[p[0], p[1], p[2]] for p in ok_]; H["mass_quelle"] = "foto_umriss"
        if gut: rc = 0
        try: bild(bilder, H, U, os.path.join(A, f"rund_umriss_{H.get('id', 'r')}.jpg"))
        except Exception as e: print("  Bild fehlgeschlagen:", e)
    if not a.nur_messen: json.dump(KA, open(kp, "w"), indent=1, ensure_ascii=False); print("->", kp)
    return rc


def bild(bilder, H, U, aus):
    """Pruefbild: 6 Fotos ueber den Blickwinkel verteilt, Ausschnitt mit Foto-Umriss (gruen) und Wolkenkreis (rot); rechts Profil r(z)."""
    import cv2
    if not bilder: return
    w0 = U["start_wolke"]; az = [math.atan2(B.Cxy[1] - U["y"], B.Cxy[0] - U["x"]) for B in bilder]; o = np.argsort(az); pick = [bilder[o[int(i)]] for i in np.linspace(0, len(o) - 1, min(6, len(o)))]
    zs = [p[0] for p in U["profil"]] or [0.0]; kacheln = []
    for B in pick:
        im = cv2.imread(B.pf); s = im.shape[1] / (B.c["cx"] * 2)
        for (x, y, r), col in (((w0["x"], w0["y"], w0["r"]), (0, 0, 255)), ((U["x"], U["y"], U["r"]), (0, 220, 0))):
            T, _, ok = tangenten(np.array([[x, y]]), np.array([r]), B.Cxy)
            for sd in (0, 1):
                X = np.array([[T[sd, 0, 0], T[sd, 0, 1], z] for z in np.linspace(min(zs), max(zs), 30)]); p, zz, _ = B.proj(X, B.c); p = (p * s).astype(int)
                cv2.polylines(im, [p.reshape(-1, 1, 2)], False, col, max(1, im.shape[1] // 600))
        X = np.array([[U["x"], U["y"], z] for z in (min(zs), max(zs))]); p, _, _ = B.proj(X, B.c); p = p * s; rpx = U["r"] * B.c["f_px"] * s / max(np.linalg.norm(B.Cxy - [U["x"], U["y"]]), 1)
        x0 = int(max(0, p[:, 0].min() - 3 * rpx)); x1 = int(min(im.shape[1], p[:, 0].max() + 3 * rpx)); y0 = int(max(0, p[:, 1].min() - rpx)); y1 = int(min(im.shape[0], p[:, 1].max() + rpx))
        k = im[y0:y1, x0:x1]
        if k.size == 0: continue
        k = cv2.resize(k, (int(k.shape[1] * 360 / k.shape[0]), 360)); cv2.putText(k, B.nr[-14:], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1); kacheln.append(k)
    pr = np.full((360, 260, 3), 255, np.uint8); P = U["profil"]
    if P:
        za, zb = min(p[0] for p in P), max(p[0] for p in P); rm = max(max(p[1] for p in P), w0["r"]) * 1.2
        Y = lambda z: int(340 - (z - za) / max(zb - za, 1e-6) * 320); Xr = lambda r: int(20 + r / rm * 220)
        cv2.line(pr, (Xr(w0["r"]), 10), (Xr(w0["r"]), 350), (0, 0, 255), 1)
        for p in P: cv2.circle(pr, (Xr(p[1]), Y(p[0])), 3, (0, 160, 0) if p[3] >= STUETZE_ENDE * np.median([q[3] for q in P]) else (160, 160, 160), -1)
        if U.get("oberkante") is not None: cv2.line(pr, (0, Y(U["oberkante"])), (259, Y(U["oberkante"])), (200, 0, 200), 1)
        cv2.putText(pr, f"r Foto {U['r']:.2f}  Wolke {w0['r']:.2f}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
    out = np.hstack(kacheln + [pr]); cv2.imwrite(aus, out, [cv2.IMWRITE_JPEG_QUALITY, 85]); print("  Bild:", aus)


if __name__ == "__main__": sys.exit(main())
