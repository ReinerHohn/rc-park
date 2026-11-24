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
    23.11.2026 (Kettenlauf 1122p, Treppentuermchen r 2,09 statt ~1,6, Umriss auf der Hauptturmkante): (a) das VORMODELL desselben Koerpers im STL ist kein Verdecker
    (eigenkoerper/ist_eigen - sonst misst die Stufe ihr eigenes Vormodell), (b) Verdeckung JE KANDIDAT (Sperrkarte: Strahlenraster je Foto, Kante eines Koerpers davor
    sperrt die Nachbarschaft; Innenkarte: Umrisspunkt im Nachbarkoerper), (c) nur Umrisse vor FERNEM Hintergrund stimmen ab (hintergrund_nah: Wand < 2 Radien dahinter
    -> deren Textur, z. B. Eckquader, ist vom Umriss nicht zu trennen), (d) fehlende Beobachtungen je Kandidat auf volle Abdeckung hochgerechnet (ABDECKUNG_MIN).
 4. Grob-fein: Mitte +-0,6 m, Radius 0,5..1,4 x Start; dann Feinraster. Danach je Hoehe nur noch r (Mitte fest) -> Drehprofil r(z).
 5. Oberkante: Umriss-Stuetze je Hoehe (mittlere Abstimmung am besten r), auch 3 m ueber der Wolke; Ende = letzte Hoehe mit >= 50 % der Median-Stuetze (ANNAHME).
 6. KEGELDACH (23.11.2026, kegeldach()): ueber der Traufe/Oberkante Traufradius und Spitze aus den beiden geraden Umriss-Mantellinien je Foto (exakte Kegelsilhouette,
    Kantenrichtung mit Vorzeichen), Guard: >= 6 Fotos, >= 3 einig, Bestwert nicht am Suchrand -> Block 'dach' (bauteile.kegeldach_teile baut Traufbrett + Kegel).
 7. KRANZ (24.11.2026, kranz_messen; Befund Hoehen-Angleich 1122: Silhouetten-Traufe 12,75, Kranz 0,75 m dick, Fotokanten/Wolke 0,75-0,84 m tiefer = Rezept L31):
    Hoehen des auskragenden Rings an der Traufe aus Quellen OHNE Auskragungs-Falle - Ober-/Unterkante je einzeln: triangulierte Fotokanten (--kanten, Ringspitze), sonst
    Wolken-Flaechenmitte (--wolke), sonst Silhouette mit L31-Rueckrechnung; Silhouette nur Radius. Traufe = Kranz-Oberkante (Kegeldach-Traufhoehe dann fest).
    Guard (Dicke 0,1-1,5 m, Oberkante im Fenster) sonst alter Weg; Audit 'umriss.kranz' (Quellen, Spitzen, Wolkenband, Grund/fallback). --ohne-kranz = alter Weg.
Ausgabe: koerper_auto.json je Haufen 'umriss' (Masse, Stuetze, Fotos, Profil); mit --uebernehmen ersetzt das Fotomass 'kreis'/'profil' (Wolkenwerte bleiben als
'kreis_wolke'/'profil_wolke'); Bild audit/rund_umriss_<id>.jpg (Fotoausschnitte: gruen Foto-Umriss, rot Wolkenkreis; rechts Profil).
Aufruf: rund_aus_umriss.py <objekt.json> [--koerper audit/koerper_auto.json] [--stl STL] [--uebernehmen] [--max-fotos 120] [--kanten kanten/sweep.npz] [--wolke npy] [--ohne-kranz]
Verwandt: tools/hoehen_angleich.py (gleiche Quellen am fertigen Modell), tools/rund_aus_huelle.py, tools/test_rund_kranz.py.
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
SUCHRAND_FANG = 0.045  # m: Profil-Feinsuche +-0,04 m (Schritt 5 mm) um den besten 2-cm-Rasterwert -> ein Radius so nahe am Suchrand hatte kein Maximum IM Bereich


def am_suchrand(r, r0):
    """True, wenn ein Profilradius r am Rand des Suchbereichs SUCHE_R x Startradius r0 liegt: die Guete stieg bis zum Rand, der Umriss lag nicht im Bereich -> kein Messwert.
    24.11.2026 (Kettenlauf 1122zb, Schwabentor-Treppenturm): z 11,25/11,75 r 0,835/0,855 bei Untergrenze 0,875 (0,5 x Wolke 1,75) -> 0,7 m tiefe Kerbe im glatten Putz-Schaft."""
    return r <= SUCHE_R[0] * r0 + SUCHRAND_FANG or r >= SUCHE_R[1] * r0 - SUCHRAND_FANG


def profil_bereinigen(P, r0):
    """Drehprofil P = [[z, r, ...], ...] (z steigend) ohne Suchrand-Werte. -> (P_neu, weg = z der verworfenen Hoehen).
    Regeln (24.11.2026, Befund 1122zb f04: glatter weisser Putz im Foto, im Modell Kerbe z 10,5-12,2 m): (1) Hoehen am Suchrand (am_suchrand) sind keine Messung und fallen weg.
    (2) Die gemessenen Nachbarn einer Luecke bekommen den Median aus 3 der verbleibenden Hoehen (ein Uebergangswert, dessen Scheibe halb in der Luecke liegt - 10,75: 1,215 zwischen
    1,595 und 2,255 - faellt so weg). (3) Die Luecke traegt den Radius der naechsten gemessenen Hoehe DARUNTER (Schaft laeuft weiter, bis eine Messung etwas anderes zeigt;
    keine Interpolation ueber ungemessene Hoehen); liegt sie ganz unten, den der naechsten darueber. Ohne Suchrand-Werte bleibt P unveraendert (idempotent)."""
    P = [list(p) for p in P]
    if not r0 or not P: return P, []
    rand = [am_suchrand(float(p[1]), float(r0)) for p in P]
    if not any(rand): return P, []
    ki = [i for i, w in enumerate(rand) if not w]
    if not ki: return P, [p[0] for p in P]
    rk = [float(P[i][1]) for i in ki]; neu = list(rk)
    for j, i in enumerate(ki):
        an_luecke = (j > 0 and ki[j - 1] != i - 1) or (j + 1 < len(ki) and ki[j + 1] != i + 1) or (j == 0 and i > 0) or (j == len(ki) - 1 and i < len(P) - 1)
        if an_luecke: neu[j] = float(np.median(rk[max(0, j - 1):j + 2]))
    for j, i in enumerate(ki): P[i][1] = round(neu[j], 3)
    for i, w in enumerate(rand):
        if not w: continue
        unter = [k for k in ki if k < i]; ueber = [k for k in ki if k > i]
        P[i][1] = P[unter[-1]][1] if unter else P[ueber[0]][1]
    return P, [P[i][0] for i, w in enumerate(rand) if w]


EIGEN_BAND = 0.25      # m: Flaeche des VORMODELLS desselben Rundkoerpers liegt +-25 cm um dessen gebauten Radius (Fasen, Segmentierung 48-Eck, Profilrundung 5 mm)
EIGEN_RADIAL = 0.6     # |Normale . radial| >= 0,6 (Abweichung < 53 Grad): Mantelflaeche zeigt nach aussen; angrenzende Hauptturmwand hat dort tangentiale Normale
VERDECKT_VOR = 0.15    # m: Treffer erst 15 cm vor dem Umrisspunkt zaehlt als Verdeckung (Netzrauschen am Punkt selbst)
SPERR_ZELLEN = 60      # Strahlenraster je Foto: ~60 Zellen ueber die Ausschnittbreite (3,2 x Startradius -> Zelle ~ 9 cm); feiner kostet Strahlen ohne Nutzen (Netz ~5 cm genau)
SPERR_RAND = 1         # +-1 Zelle um den Umrisspunkt: Kante eines Koerpers DAVOR sperrt auch die Nachbarschaft (Lage-/Kalibrierfehler ~ 1 Zelle)
INNEN_SCHRITT = 0.05   # m: Raster der Innen-Pruefung (Lage des Umrisspunkts im Nachbarkoerper) - halbe Wandfuge, feiner als die Mittelstufe (3 cm Kreis / 5 cm Ort)
SPERR_AUSSEN = 0.10    # m: Hintergrund-Probe 10 cm ausserhalb des Umrisspunkts (gut 1 Rasterzelle, sicher nicht mehr auf dem Koerper)
HINTERGRUND_NAH = 2.0  # x Startradius: fremde Flaeche weniger als 2 Radien hinter dem Umriss = "naher Hintergrund" (Parallaxe der Wandtextur zum Umriss < ~10 %)
ABDECKUNG_MIN = 0.6    # Kandidat mit weniger als 60 % der besten gueltigen Beobachtungsgewichte wird nur bis dahin hochgerechnet (Strafe fuer "versteckt")


def lade(p):
    try: return json.load(open(p))
    except Exception: return None


def eigenkoerper(H):
    """23.11.2026 (Kettenlauf 1122p, Treppentuermchen r 2,09 statt ~1,56): die Verdeckungspruefung lief gegen das Modell-STL, das den Rundkoerper aus dem
    VORLAUF schon enthaelt (r 2,1, Mitte 0,55 m versetzt). Die Umrisspunkte des Startkreises lagen IN diesem Vormodell -> 3770 von 6240 Beobachtungen als
    'verdeckt' verworfen, es blieben v. a. Blicke ueber die Hauptturmkante = zirkulaere Messung (die Stufe misst ihr eigenes Vormodell).
    -> Liste der moeglichen Vormodelle dieses Haufens (Foto-Mass 'kreis'/'profil' und Wolken-Mass 'kreis_wolke'/'profil_wolke'): (x, y, zs, rs, z_lo, z_hi)."""
    kz = H.get("kasten") or [0, 0, 0, 0, 0, 1e9]; aus = []
    for kk, pk in (("kreis", "profil"), ("kreis_wolke", "profil_wolke")):
        k = H.get(kk); P = [p for p in (H.get(pk) or []) if len(p) >= 2]
        if not k: continue
        if P: zs = np.array([p[0] for p in P], float); rs = np.array([p[1] for p in P], float); z_hi = max(float(zs.max()), kz[5])
        else: zs = np.array([kz[2], kz[5]], float); rs = np.array([k["r"], k["r"]], float); z_hi = kz[5]
        o = np.argsort(zs); aus.append((float(k["x"]), float(k["y"]), zs[o], rs[o], kz[2] - 0.3, z_hi))
    return aus


def ist_eigen(loc, nrm, eigen):
    """Treffer (loc n x 3, Flaechennormale nrm n x 3) auf dem Vormodell eines der eigen-Koerper? Mantel: Abstand zur Achse = Profilradius +- EIGEN_BAND, Normale radial
    nach aussen; Dach (ueber dem Profil bis 3,5 x r hoch, Kegel/Haube): innerhalb 1,5 x Profilradius, Normale nach aussen-oben. Angrenzende Waende anderer Koerper
    (Normale tangential oder nach innen) bleiben Verdecker."""
    e = np.zeros(len(loc), bool)
    for x, y, zs, rs, z_lo, z_hi in eigen:
        v = loc[:, :2] - [x, y]; d = np.linalg.norm(v, axis=1); rad = v / np.maximum(d, 1e-9)[:, None]; nr = (nrm[:, :2] * rad).sum(1)
        rz = np.interp(loc[:, 2], zs, rs); rt = float(rs[-1])
        mantel = (loc[:, 2] >= z_lo) & (loc[:, 2] <= z_hi + 0.3) & (np.abs(d - rz) <= EIGEN_BAND) & (nr >= EIGEN_RADIAL)
        dach = (loc[:, 2] > z_hi - 0.3) & (loc[:, 2] <= z_hi + 3.5 * rt) & (d <= 1.5 * rt) & (nr >= 0) & (nrm[:, 2] > 0.2)
        e |= mantel | dach
    return e


def verdeckt_strahlen(inter, normalen, C, X, eigen=()):
    """Je Zielpunkt X (n x 3): liegt zwischen Kamera C und X eine Modellflaeche (mehr als VERDECKT_VOR vor X), die NICHT zum Vormodell des gemessenen Koerpers gehoert?"""
    v = X - C; dist = np.linalg.norm(v, axis=1); vor = np.full(len(X), np.inf)
    tri, ri, loc = inter.intersects_id(np.broadcast_to(C, X.shape), v / dist[:, None], multiple_hits=True, return_locations=True)
    if len(ri):
        t = np.linalg.norm(loc - C, axis=1); fremd = ~ist_eigen(loc, normalen[tri], eigen) if eigen else np.ones(len(ri), bool)
        np.minimum.at(vor, ri[fremd], t[fremd])
    return vor < dist - VERDECKT_VOR


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
        if getattr(self, "sperre", None) is not None:                                      # 23.11.2026: Kandidaten-Umrisspunkt verdeckt, an fremder Verdeckerkante oder vor nahem Hintergrund
            ok &= ~self.sperre.gesperrt(X)
            if getattr(self, "hinter_nah", 0) > 0: ok &= ~self.sperre.hintergrund_nah(X, N3, self.hinter_nah)
        return np.where(ok, np.abs(bil(self.gx) * d[:, 0] + bil(self.gy) * d[:, 1]), np.nan)


class Sperrkarte:
    """23.11.2026 (Kettenlauf 1122p: Treppentuermchen r 2,09/1,86 statt ~1,56, gruene Umrisslinie auf der Hauptturmkante): Verdeckung JE KANDIDAT statt nur am Startkreis.
    Je Foto ein grobes Strahlenraster ueber den Ausschnitt (Schritt SPERR_PX Kalibrierpixel): Abstand zur ersten Modellflaeche, die NICHT zum Vormodell des gemessenen
    Koerpers gehoert (ist_eigen). Ein Kandidaten-Umrisspunkt X ist gesperrt, wenn in der Rasterzelle ODER einer Nachbarzelle (+-SPERR_RAND) eine Flaeche mehr als
    VERDECKT_VOR vor X liegt: verdeckt, oder direkt an der Silhouette eines Koerpers DAVOR - dessen Kante (Stein gegen Himmel/Putz) ist der staerkste Gradient im
    Ausschnitt und zog die Abstimmung auf einen Kreis, der die Hauptturmkante beruehrt. Nur Umrisse mit Hintergrund (nichts davor) stimmen ab."""
    def __init__(self, inter, normalen, c, C, box, eigen=(), schritt=None):
        import cv2
        u0, v0, u1, v1 = box; sp = schritt or max(4.0, (u1 - u0) / SPERR_ZELLEN)
        us = np.arange(u0, u1 + sp, sp); vs = np.arange(v0, v1 + sp, sp); U_, V_ = np.meshgrid(us, vs)
        xd = (U_.ravel() - c["cx"]) / c["f_px"]; yd = (V_.ravel() - c["cy"]) / c["f_px"]; xn, yn = xd.copy(), yd.copy(); k1 = float(c.get("k1") or 0.0)
        for _ in range(5): s_ = 1 + k1 * (xn * xn + yn * yn); xn, yn = xd / s_, yd / s_                 # radiale Verzeichnung umkehren (Fixpunkt)
        R = cv2.Rodrigues(np.asarray(c["rvec"], float))[0]; dw = np.c_[xn, yn, np.ones_like(xn)] @ R; dw /= np.linalg.norm(dw, axis=1)[:, None]
        vor = np.full(len(dw), np.inf); C = np.asarray(C, float)
        tri, ri, loc = inter.intersects_id(np.broadcast_to(C, dw.shape), dw, multiple_hits=True, return_locations=True)
        if len(ri):
            t = np.linalg.norm(loc - C, axis=1); fremd = ~ist_eigen(loc, normalen[tri], eigen) if eigen else np.ones(len(ri), bool); np.minimum.at(vor, ri[fremd], t[fremd])
            ri_f, t_f, nd = ri[fremd], t[fremd], (normalen[tri[fremd]] * dw[ri[fremd]]).sum(1); erst = np.isclose(t_f, vor[ri_f])
            rueck = np.zeros(len(dw), bool); rueck[ri_f[erst & (nd > 0.1)]] = True    # erste fremde Flaeche von INNEN getroffen: Strahl lief durch das ausgenommene Vormodell in einen Koerper
        else: rueck = np.zeros(len(dw), bool)
        self.tief = np.where(rueck, -np.inf, vor).reshape(U_.shape)                    # roher Abstand zum Hintergrund (-inf = im Koerper) fuer hintergrund_nah
        V = vor.reshape(U_.shape); k = SPERR_RAND; P = np.pad(V, k, constant_values=np.inf)
        self.vor = np.min([P[k + i:k + i + V.shape[0], k + j:k + j + V.shape[1]] for i in range(-k, k + 1) for j in range(-k, k + 1)], axis=0)   # naechster Verdecker in der Nachbarschaft
        self.u0, self.v0, self.sp, self.c, self.C = float(us[0]), float(vs[0]), sp, c, C

    def gesperrt(self, X):
        import flaeche_ortho as FO
        p, z, _ = FO.projektion(np.asarray(X, float), self.c); j = np.round((p[:, 0] - self.u0) / self.sp).astype(int); i = np.round((p[:, 1] - self.v0) / self.sp).astype(int)
        h, w = self.vor.shape; inn = (i >= 0) & (j >= 0) & (i < h) & (j < w); d = np.linalg.norm(np.asarray(X, float) - self.C, axis=1)
        v = np.where(inn, self.vor[np.clip(i, 0, h - 1), np.clip(j, 0, w - 1)], np.inf); g = v < d - VERDECKT_VOR
        return g | self.innen.innen(X) if getattr(self, "innen", None) is not None else g

    def hintergrund_nah(self, X, N3, nah):
        """23.11.2026 (Bild 114101: wahrer Umriss weiss vor weisser Hauptturmwand kaum sichtbar, die Eckquader-Kante der Wand DAHINTER ist der staerkste Gradient und
        zog den Kreis auf r 2,0): liegt hinter dem Umrisspunkt (Strahl knapp ausserhalb, X + SPERR_AUSSEN x Normale) eine fremde Flaeche naeher als 'nah' m? Dann ist die
        Bildkante dort nicht vom Umriss zu trennen (Textur der Wand dahinter, kaum Parallaxe) -> Beobachtung zaehlt fuer diesen Kandidaten nicht. Nur Umrisse vor
        fernem Hintergrund (Himmel, Strasse, Nachbarhaeuser) stimmen ab."""
        import flaeche_ortho as FO
        Y = np.asarray(X, float) + SPERR_AUSSEN * np.asarray(N3, float); p, z, _ = FO.projektion(Y, self.c)
        j = np.round((p[:, 0] - self.u0) / self.sp).astype(int); i = np.round((p[:, 1] - self.v0) / self.sp).astype(int); h, w = self.tief.shape
        inn = (i >= 0) & (j >= 0) & (i < h) & (j < w); t = np.where(inn, self.tief[np.clip(i, 0, h - 1), np.clip(j, 0, w - 1)], np.inf)
        return t < np.linalg.norm(Y - self.C, axis=1) + nah


class Innenkarte:
    """23.11.2026: Umrisspunkt eines Kandidaten liegt IM Nachbarkoerper (Hauptturm), an den der Rundkoerper angebaut ist? Das Modell-STL ist eine Vereinigung: die
    Hauptturmwand innerhalb des Vormodells fehlt, ein Strahl durch das (ausgenommene) Vormodell trifft dort nichts -> Sperrkarte allein sieht den Punkt als frei.
    Test je Rasterpunkt (Schritt INNEN_SCHRITT, waagrecht um die Achse, je Hoehe): Strahl von der Achse radial nach aussen durch den Punkt; trifft er zuerst (ohne
    Vormodell-Flaechen) eine fremde Flaeche VON INNEN (Normale in Strahlrichtung), liegt der Punkt in einem festen Koerper. Ein Umriss im Inneren ist kein Umriss
    (die Kante dort ist die Anschlusslinie an die Wand, nicht die Beruehrlinie)."""
    def __init__(self, inter, normalen, x, y, halb, zs, eigen=()):
        g = np.arange(-halb, halb + 1e-9, INNEN_SCHRITT); self.x, self.y, self.g0, self.n = x, y, -halb, len(g); self.zs = np.asarray(sorted(zs), float)
        A, B_ = np.meshgrid(g, g, indexing="ij"); a, b = A.ravel(), B_.ravel(); rl = np.hypot(a, b); ok = rl > 0.05
        dxy = np.c_[a[ok], b[ok]] / rl[ok, None]; self.m = np.zeros((len(self.zs), self.n, self.n), bool)
        for k, z in enumerate(self.zs):
            O = np.c_[np.full(ok.sum(), x), np.full(ok.sum(), y), np.full(ok.sum(), z)]; D = np.c_[dxy, np.zeros(ok.sum())]
            tri, ri, loc = inter.intersects_id(O, D, multiple_hits=True, return_locations=True); erst = np.full(ok.sum(), np.inf); dot = np.zeros(ok.sum())
            if len(ri):
                t = np.linalg.norm(loc[:, :2] - [x, y], axis=1); rp = rl[ok][ri]; jenseits = t > rp + 1e-3    # erste fremde Flaeche JENSEITS des Punkts
                fremd = (~ist_eigen(loc, normalen[tri], eigen) if eigen else np.ones(len(ri), bool)) & jenseits
                o = np.lexsort((t[fremd], ri[fremd])); rf, tf, nf = ri[fremd][o], t[fremd][o], (normalen[tri[fremd]][o][:, :2] * D[ri[fremd][o], :2]).sum(1)
                _, first = np.unique(rf, return_index=True); erst[rf[first]] = tf[first]; dot[rf[first]] = nf[first]
            mm = np.zeros(len(a), bool); mm[np.where(ok)[0]] = np.isfinite(erst) & (dot > 0.1); self.m[k] = mm.reshape(self.n, self.n)

    def innen(self, X):
        X = np.asarray(X, float); i = np.round((X[:, 0] - self.x - self.g0) / INNEN_SCHRITT).astype(int); j = np.round((X[:, 1] - self.y - self.g0) / INNEN_SCHRITT).astype(int)
        k = np.clip(np.searchsorted(self.zs, X[:, 2]), 0, len(self.zs) - 1); inn = (i >= 0) & (j >= 0) & (i < self.n) & (j < self.n)
        return inn & self.m[k, np.clip(i, 0, self.n - 1), np.clip(j, 0, self.n - 1)]


def bewerten(bilder, obs, c, r, gew=None):
    """Summe der normierten Abstimmungen fuer Kreise (c: K x 2, r: K). obs: Liste (bildindex, seite, z). gew: Gewicht je Beobachtung. -> Punkte (K), Zahl Beob. (K), je Beob. Werte."""
    K = len(r); summe = np.zeros(K); n = np.zeros(K); roh = []; wv = np.zeros(K)
    for oi, (bi, seite, z) in enumerate(obs):
        B = bilder[bi]; T, N, ok = tangenten(c, r, B.Cxy)
        X = np.c_[T[seite], np.full(K, z)]; N3 = np.c_[N[seite], np.zeros(K)]
        s = B.quer(X, N3); s[~ok] = np.nan
        m = np.nanmax(s) if np.isfinite(s).any() else 0
        if m <= 0: roh.append(None); continue
        w = 1.0 if gew is None else gew[oi]; wv += w * np.isfinite(s); s = np.nan_to_num(s / m); summe += w * s; n += 1; roh.append(s)
    # 23.11.2026: Beobachtungen, deren Umrisspunkt fuer einen Kandidaten verdeckt/gesperrt ist, fehlen nur DIESEM Kandidaten -> Summe auf volle Abdeckung hochrechnen
    # (Mittel ueber die gueltigen), aber hoechstens bis ABDECKUNG_MIN der besten Abdeckung: ein Kandidat, der sich hinter Verdeckern versteckt, gewinnt nicht.
    if K and wv.max() > 0: summe = summe * wv.max() / np.maximum(wv, ABDECKUNG_MIN * wv.max())
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


# ---- 23.11.2026 KEGEL-/ZELTDACH auf dem Rundkoerper aus den Umriss-Geraden (Kettenlauf 1122o: Treppentuermchen als nackter Zylinder, oben offen, Kegeldach fehlte) ----
# Ein Kegel (Spitze S auf der Achse, Traufkreis r_e in z_t) zeigt im Foto zwei gerade Umrisslinien: die Mantellinien, deren Tangentialebene durch die Kamera C geht.
# Ihre Fusspunkte sind die Beruehrpunkte der Tangenten vom Punkt C' an den Traufkreis, C' = Schnitt der Geraden S-C mit der Traufebene (exakt, keine Naeherung).
# z_t und r_e sind entlang einer Mantellinie gekoppelt (dieselbe Gerade) - z_t kommt darum aus dem Profil (Traufe/Oberkante), gesucht werden r_e und z_spitze.
KEGEL_R = (0.80, 1.40)     # Traufradius als Vielfaches des Schaftradius (Dachueberstand bis 40 %, auch eingezogen bis 80 %)
KEGEL_H = (0.25, 3.5)      # Dachhoehe als Vielfaches des Schaftradius: Neigung ~14..74 Grad (flacher = kein Kegel, steiler = Nadelhelm, eigene Stufe)
KEGEL_ANTEILE = np.linspace(0.15, 0.85, 8)   # Abtastung der Mantellinie (ohne Traufrand und Spitze: dort stoeren Traufbrett und Knauf)
KEGEL_MIN_FOTOS = 6        # Beobachtungen aus mind. 6 Fotos (je Seite einzeln verdeckbar), davon
KEGEL_EINIG = 3            # mind. 3 Fotos, deren Einzelbestwert dieselbe Spitze zeigt (Formfamilie aus >= 3 Fotos, CLAUDE.md)


def kegel_fuesse(Cxyz, x, y, z_t, r_e, z_s):
    """Fusspunkte der beiden Umriss-Mantellinien fuer Kegel (Achse x, y; Traufe z_t, Radius r_e (K); Spitze z_s (K)) von der Kamera Cxyz -> F (2, K, 2), ok (K)."""
    r_e = np.asarray(r_e, float); z_s = np.asarray(z_s, float); C = np.asarray(Cxyz, float)
    den = C[2] - z_s; ok = den < -0.05                                                 # Kamera unter der Spitze (sonst sieht sie den Traufkreis als Umriss)
    t = (z_t - z_s) / np.where(ok, den, -1.0)
    cp = np.c_[x + t * (C[0] - x), y + t * (C[1] - y)]; v = cp - np.array([x, y]); D = np.linalg.norm(v, axis=1); ok &= D > r_e * 1.02   # C' im Traufkreis: Untersicht, kein Mantelumriss
    u = v / np.maximum(D, 1e-9)[:, None]; up = np.c_[-u[:, 1], u[:, 0]]; ca = np.clip(r_e / np.maximum(D, 1e-9), -1, 1); sa = np.sqrt(1 - ca * ca)
    N = np.stack([ca[:, None] * u + sa[:, None] * up, ca[:, None] * u - sa[:, None] * up])
    return np.array([x, y])[None, None] + r_e[None, :, None] * N, ok


def kegel_quer(B, x, y, z_t, r_e, z_s, seite):
    """Mittlerer |Gradient quer zur projizierten Mantellinie| ueber KEGEL_ANTEILE fuer alle Kandidaten (K) - nan, wo nicht beurteilbar."""
    W_, ok = mantel_werte(B, x, y, z_t, r_e, z_s, seite, KEGEL_ANTEILE); n_ok = np.isfinite(W_).sum(0)
    m = np.where(n_ok >= len(KEGEL_ANTEILE) // 2 + 1, np.abs(np.nanmean(np.where(n_ok > 0, W_, 0.0), 0)), np.nan)
    return np.where(ok, m, np.nan)


def mantel_werte(B, x, y, z_t, r_e, z_s, seite, anteile):
    """Gradient quer zur projizierten Mantellinie (MIT Vorzeichen) an den Anteilen 'anteile' (Fuss 0 .. Spitze 1) fuer alle Kandidaten (K) -> (len(anteile), K), ok (K).
    Ein Kegelstumpf (Segment eines geschweiften Dachs) ist der untere Teil des Kegels mit seiner GEDACHTEN Spitze z_s; sein Umriss ist das Stueck der Mantellinie bis zum Anteil
    (r_unten - r_oben) / r_unten (23.11.2026, profil_quer)."""
    r_e = np.asarray(r_e, float); z_s = np.asarray(z_s, float); z_t = np.broadcast_to(np.asarray(z_t, float), r_e.shape)
    F, ok = kegel_fuesse(B.C, x, y, z_t, r_e, z_s); K = len(r_e); Fs = F[seite]; anteile = np.asarray(anteile, float)
    if anteile.ndim == 1: anteile = np.broadcast_to(anteile[:, None], (len(anteile), K))
    pF, zF = B.pix(np.c_[Fs, z_t]); pS, zS = B.pix(np.c_[np.full(K, x), np.full(K, y), z_s])
    d = pS - pF; L = np.linalg.norm(d, axis=1); nrm = np.c_[-d[:, 1], d[:, 0]] / np.maximum(L, 1e-9)[:, None]; ok &= (L * (anteile[-1] - anteile[0]) > 4) & (zF > 0.5) & (zS > 0.5)
    h, w = B.gx.shape; werte = []
    A_ = np.c_[np.full(K, x), np.full(K, y)]
    for f in anteile:
        Xm = np.c_[Fs + f[:, None] * (A_ - Fs), z_t + f * (z_s - z_t)]; p, zp = B.pix(Xm)          # Punkt auf der 3D-Mantellinie projiziert (exakt, auch fuer kurze Segmente)
        xx = p[:, 0] - B.x0; yy = p[:, 1] - B.y0; inn = (xx >= 1) & (yy >= 1) & (xx < w - 2) & (yy < h - 2) & (zp > 0.5)
        xi = np.clip(xx, 1, w - 2); yi = np.clip(yy, 1, h - 2); x0 = np.floor(xi).astype(int); y0 = np.floor(yi).astype(int); fx = xi - x0; fy = yi - y0
        def bil(G): return (G[y0, x0] * (1 - fx) * (1 - fy) + G[y0, x0 + 1] * fx * (1 - fy) + G[y0 + 1, x0] * (1 - fx) * fy + G[y0 + 1, x0 + 1] * fx * fy).astype(np.float32)
        if getattr(B, "sperre", None) is not None:                                       # 23.11.2026: verdeckte Mantelpunkte / Kante eines Koerpers davor zaehlen nicht
            inn &= ~B.sperre.gesperrt(Xm)
            if getattr(B, "hinter_nah", 0) > 0:
                nh_ = Xm[:, :2] - [x, y]; nh_ /= np.maximum(np.linalg.norm(nh_, axis=1), 1e-9)[:, None]; inn &= ~B.sperre.hintergrund_nah(Xm, np.c_[nh_, np.zeros(K)], B.hinter_nah)
        werte.append(np.where(inn, bil(B.gx) * nrm[:, 0] + bil(B.gy) * nrm[:, 1], np.nan))    # VORZEICHEN behalten: eine Umrisskante hat innen/aussen ueberall dieselbe Richtung, Streifen/Fugen quer dazu wechseln
    return np.array(werte), ok


def profil_knick(z_t, R, Z, A, Q):
    """Dachprofil mit einem Knick (23.11.2026): Traufe (z_t, R), Spitze Z; Knick auf Anteil A der Dachhoehe mit Radius Q x (Radius der Geraden Traufe-Spitze dort).
    Q = 1 gerader Kegel, Q < 1 geschweift (unten flach ausgestellt, oben steil), Q > 1 gebaucht. -> z_k, r_k (Arrays)."""
    A = np.asarray(A, float); Q = np.asarray(Q, float); R = np.asarray(R, float); Z = np.asarray(Z, float)
    return z_t + A * (Z - z_t), R * (1 - A) * Q


def profil_quer(B, x, y, z_t, R, Z, A, Q, seite):
    """Umriss-Abstimmung fuer Dachprofile aus ZWEI Kegelstuempfen (Traufe -> Knick -> Spitze), K Kandidaten. Jeder Stumpf ist Teil eines Kegels mit eigener (gedachter)
    Spitze; sein Umriss ist das Stueck seiner Mantellinie (exakte Silhouette je Stumpf). Je Stueck Mittel MIT Vorzeichen; Wert = harmonisches Mittel der Betraege (0, wenn die Vorzeichen verschieden sind).
    nan, wo ein Stueck nicht beurteilbar ist (verdeckt, Kamera ueber der gedachten Spitze, zu kurz im Bild)."""
    R = np.asarray(R, float); Z = np.asarray(Z, float); z_k, r_k = profil_knick(z_t, R, Z, A, Q)
    fr1 = (R - r_k) / R; za1 = z_t + (z_k - z_t) / np.maximum(fr1, 1e-6)
    W1, ok1 = mantel_werte(B, x, y, z_t, R, za1, seite, fr1[None, :] * PROFIL_ANTEILE_UNTEN[:, None])
    W2, ok2 = mantel_werte(B, x, y, z_k, r_k, Z, seite, PROFIL_ANTEILE_OBEN)
    n1 = np.isfinite(W1).sum(0); n2 = np.isfinite(W2).sum(0)
    m1 = np.nansum(W1, 0) / np.maximum(n1, 1); m2 = np.nansum(W2, 0) / np.maximum(n2, 1)
    ok = ok1 & ok2 & (n1 >= len(PROFIL_ANTEILE_UNTEN) // 2 + 1) & (n2 >= len(PROFIL_ANTEILE_OBEN) // 2 + 1)
    gleich = np.sign(m1) == np.sign(m2)                                                  # beide Stuecke derselbe Umriss: gleiche Kantenrichtung
    hm = 2 * np.abs(m1) * np.abs(m2) / np.maximum(np.abs(m1) + np.abs(m2), 1e-9)          # harmonisches Mittel: BEIDE Stuecke muessen auf der Kante liegen (ein kurzes, flaches
    return np.where(ok, np.where(gleich, hm, 0.0), np.nan)                               # unteres Stueck ging im Laengenmittel unter - Traufradius lief auf den Schaft, Test D 23.11.)


PROFIL_ANTEILE_UNTEN = np.linspace(0.12, 0.92, 5)   # unterer Stumpf ohne Traufbrett (Anteil seiner Laenge)
PROFIL_ANTEILE_OBEN = np.linspace(0.08, 0.85, 6)    # oberer Stumpf ohne Knauf
PROFIL_A = np.round(np.arange(0.15, 0.651, 0.1), 2)  # Knickhoehe als Anteil der Dachhoehe
PROFIL_Q = np.round(np.arange(0.4, 1.201, 0.1), 2)   # Knickradius / Radius der Geraden (1 = gerade, < 1 geschweift, > 1 gebaucht)
PROFIL_VORZUG = 0.05      # Beobachtung "bevorzugt" eine Formfamilie, wenn ihr normierter Wert um >= 5 % hoeher liegt (ANNAHME, Rauschen der Abstimmung ~2-3 %)
TRAUFE_SPIEL = 0.12       # Traufradius mind. Profilradius - 0,12 m (Streuung des Drehprofils 2-3 cm, Traufbrett/Untersicht; ANNAHME)
TRAUFE_DZ = np.array([-1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25])   # Traufhoehe frei um die Profil-Traufe: von unten gesehen liegt der Dachumriss im Bild HOEHER als
                          # der Dachpunkt, die waagrechten Tangenten (vermessen) setzen die Traufe darum zu hoch (schwabentor-1122: Profil-Traufe 13,75, Foto ~13; ANNAHME Spiel)
PROFIL_GEWINN = 1.02      # geknickte Familie nur, wenn die Gesamtabstimmung >= 2 % ueber der Geraden liegt (sonst gerade: einfachere Form)


def kegeldach(bilder, x, y, z_t, r_s, verdeckt=None, log=print, r_traufe=None):
    """Kegeldach ueber dem Rundkoerper (Achse x, y, Schaftradius r_s, Traufe z_t) aus den Umriss-Mantellinien aller Fotos. bilder: Liste Bild (.C, .Cxy).
    Abstimmung wie vermessen(): jede Beobachtung (Foto x Seite) auf ihr Maximum normiert, Gewicht 1 / Fotos im selben 15-Grad-Faecher. -> dict (gueltig, grund, Masse).
    23.11.2026 (schwabentor-1122, Treppentuermchen: Dach GESCHWEIFT, unten flach ausgestellt, oben steil - eine Gerade passte nur oben, Traufradius lief an den Suchrand):
    Profil aus zwei Kegelstuempfen (profil_quer), gesucht Traufradius, Spitze, Knickhoehe A und Knickradius Q. Formfamilie (gerade Q=1 / geschweift Q<1 / gebaucht Q>1)
    nach dem Rest: geknickt nur, wenn >= KEGEL_EINIG Fotos sie einzeln bevorzugen, mehr Fotos dafuer als dagegen und Gesamtabstimmung >= PROFIL_GEWINN x gerade.
    r_traufe: groesster Radius des Umriss-Drehprofils oben (vermessen(), waagrechte Tangenten). Ein Dach, das sich nach oben verjuengt, hat an der Traufe mind. diesen Radius:
    Traufradius >= r_traufe - TRAUFE_SPIEL (ohne diese Schranke zog die Kante Schaft/Untersicht das kurze, flache untere Stueck auf den Schaftradius, Test D 23.11.).
    Traufhoehe: frei in z_t + TRAUFE_DZ (die Profil-Traufe liegt von unten gesehen zu hoch)."""
    obs = [(bi, s) for bi in range(len(bilder)) for s in (0, 1) if not (verdeckt and verdeckt(bi, s))]
    erg = dict(z_traufe=round(float(z_t), 2), r_schaft=round(float(r_s), 3), quelle="tools/rund_aus_umriss.kegeldach: Umriss-Mantellinien (exakte Silhouette je Kegelstumpf) in kalibrierten Fotos")
    if not obs: return dict(erg, gueltig=False, grund="keine Beobachtung")
    az = np.array([int(np.degrees(math.atan2(bilder[bi].Cxy[1] - y, bilder[bi].Cxy[0] - x)) // FAECHER_GRAD) for bi, _ in obs]); u_, c_ = np.unique(az, return_counts=True); cnt = dict(zip(u_, c_))
    gw = np.array([1.0 / cnt[a] for a in az])
    def punkte(R, T, Z, A, Q, norm=None):
        S = np.zeros(len(R)); roh = []; mx = []
        for k_, ((bi, s), w) in enumerate(zip(obs, gw)):
            v = profil_quer(bilder[bi], x, y, T, R, Z, A, Q, s); m = (norm[k_] if norm is not None else (np.nanmax(v) if np.isfinite(v).any() else 0.0))
            mx.append(m)
            if not m or m <= 0: roh.append(None); continue
            v = np.minimum(np.nan_to_num(v / m), 1.0); S += w * v; roh.append(v)
        return S, roh, mx
    z_t0 = float(z_t); r_lo, r_hi = KEGEL_R[0] * r_s, KEGEL_R[1] * r_s; h_lo, h_hi = KEGEL_H[0] * r_s, KEGEL_H[1] * r_s
    dz_ = np.array([0.0])                                                                  # ohne Profil-Traufe (nur Oberkante): Traufhoehe fest (Rot-Probe flacher Zylinder)
    if r_traufe and r_lo < r_traufe < r_hi: r_lo = max(r_lo, r_traufe - TRAUFE_SPIEL); dz_ = TRAUFE_DZ; erg["r_traufe_profil"] = round(float(r_traufe), 3)
    g = np.meshgrid(np.arange(r_lo, r_hi + 1e-9, 0.04), z_t0 + dz_, np.arange(h_lo, h_hi + 1e-9, 0.12), PROFIL_A, PROFIL_Q, indexing="ij"); R, T, H_, A, Q = (v.ravel() for v in g)
    _, r_k = profil_knick(T, R, T + H_, A, Q); gut_ = (r_k < 0.97 * R) & (r_k > 0.03)
    R, T, H_, A, Q = R[gut_], T[gut_], H_[gut_], A[gut_], Q[gut_]; Z = T + H_
    S, roh, norm = punkte(R, T, Z, A, Q)
    def fein(i, nur_gerade):
        r0, t0, z0, a0, q0 = R[i], T[i], Z[i], A[i], Q[i]
        da = [-0.05, 0.0, 0.05]; dq = [0.0] if nur_gerade else [-0.05, 0.0, 0.05]      # gerade: Teilung A frei (gleiche Abtastung wie die geknickten), Q bleibt 1
        gg = np.meshgrid(np.arange(r0 - 0.06, r0 + 0.06 + 1e-9, 0.02), t0 + (np.array([-0.1, 0.0, 0.1]) if len(dz_) > 1 else np.zeros(1)), np.arange(z0 - 0.12, z0 + 0.12 + 1e-9, 0.04), a0 + np.array(da), q0 + np.array(dq), indexing="ij")
        R2, T2, Z2, A2, Q2 = (v.ravel() for v in gg); _, rk2 = profil_knick(T2, R2, Z2, A2, Q2)
        ok = (rk2 < 0.97 * R2) & (rk2 > 0.03) & (A2 > 0.05) & (A2 < 0.95) & (R2 >= r_lo - 1e-9) & (R2 <= r_hi + 1e-9) & (Z2 > T2 + 0.2)
        R2, T2, Z2, A2, Q2 = R2[ok], T2[ok], Z2[ok], A2[ok], Q2[ok]; S2, _, _ = punkte(R2, T2, Z2, A2, Q2, norm); j = int(np.argmax(S2))
        return float(R2[j]), float(T2[j]), float(Z2[j]), float(A2[j]), float(Q2[j]), float(S2[j])
    ig = np.where(Q == 1.0)[0]; i_s = int(ig[np.argmax(S[ig])]); i_b = int(np.argmax(S))
    gerade = fein(i_s, True); best = fein(i_b, False) if Q[i_b] != 1.0 else gerade
    # Formfamilie nach dem Rest: Beobachtungen am feinen Bestwert der Geraden und der geknickten Form vergleichen
    S_v, roh_v, _ = punkte(*[np.array([gerade[k], best[k]]) for k in range(5)], norm)
    fuer, gegen = set(), set()
    for (bi, s), v in zip(obs, roh_v):
        if v is None: continue
        if v[1] - v[0] >= PROFIL_VORZUG: fuer.add(bi)
        elif v[0] - v[1] >= PROFIL_VORZUG: gegen.add(bi)
    gegen -= fuer
    knick = best is not gerade and abs(best[4] - 1.0) >= 0.08 and len(fuer) >= KEGEL_EINIG and len(fuer) > len(gegen) and S_v[1] >= PROFIL_GEWINN * S_v[0]
    r_e, z_t, z_s, a_, q_, s_ = best if knick else gerade; h = z_s - z_t; erg["z_traufe"] = round(z_t, 2); erg["z_traufe_profil"] = round(z_t0, 2)
    familie = ("geschweift" if q_ < 1 else "gebaucht") if knick else "kegel"
    # Einigkeit: Einzelbestwert je Beobachtung im Grobraster; ein Foto ist einig, wenn eine seiner Seiten die Spitze auf max(0,25 m, 12 % der Dachhoehe) trifft
    tol = max(0.25, 0.12 * h); einig = set(); fotos = set()
    for (bi, s), v in zip(obs, roh):
        if v is None: continue
        fotos.add(bi); k = int(np.argmax(v))
        if abs(Z[k] - z_s) <= tol and abs(R[k] - r_e) <= max(0.15, 0.1 * r_e) and abs(T[k] - z_t) <= 0.3: einig.add(bi)
    rand = (h <= h_lo + 0.1 or h >= h_hi - 0.1 or r_e <= r_lo + 0.03 or r_e >= r_hi - 0.03)
    rand = rand or (len(dz_) > 1 and z_t <= z_t0 + dz_[0] + 0.01)
    if knick: rand = rand or q_ <= PROFIL_Q[0] + 0.01 or q_ >= PROFIL_Q[-1] - 0.01
    z_k, r_k = (float(v) for v in profil_knick(z_t, r_e, z_s, a_, q_))
    erg.update(r_traufe=round(r_e, 3), z_spitze=round(z_s, 2), hoehe=round(h, 2), neigung_grad=round(math.degrees(math.atan2(h, r_e)), 1), fotos=len(fotos), einig=len(einig),
               beobachtungen=sum(v is not None for v in roh), stuetze=round(float(s_ / max(gw.sum(), 1e-9)), 3),
               formwahl=dict(stuetze_gerade=round(float(S_v[0] / max(gw.sum(), 1e-9)), 3), stuetze_knick=round(float(S_v[1] / max(gw.sum(), 1e-9)), 3), q_knick=round(best[4], 2),
                             fotos_fuer_knick=len(fuer), fotos_gegen_knick=len(gegen), gerade=dict(r_traufe=round(gerade[0], 3), z_traufe=round(gerade[1], 2), z_spitze=round(gerade[2], 2))))
    if knick:
        erg.update(knick=dict(z=round(z_k, 2), r=round(r_k, 3)), profil=[[round(float(z_t), 2), round(r_e, 3)], [round(z_k, 2), round(r_k, 3)], [round(z_s, 2), 0.0]],
                   neigung_unten_grad=round(math.degrees(math.atan2(z_k - z_t, r_e - r_k)), 1), neigung_oben_grad=round(math.degrees(math.atan2(z_s - z_k, r_k)), 1))
    grund = None
    if len(fotos) < KEGEL_MIN_FOTOS: grund = f"nur {len(fotos)} Fotos sehen den Dachumriss (verlangt {KEGEL_MIN_FOTOS})"
    elif len(einig) < KEGEL_EINIG: grund = f"nur {len(einig)} Fotos einig ueber die Spitze (verlangt {KEGEL_EINIG}) - keine Formfamilie Kegel"
    elif rand: grund = (f"Bestwert am Suchrand (h {h:.2f} m in {h_lo:.2f}..{h_hi:.2f}, r {r_e:.2f} in {r_lo:.2f}..{r_hi:.2f}" + (f", Knick q {q_:.2f}" if knick else "")
                        + ") - kein Kegel (flach/offen) oder ausserhalb der Formfamilie")
    erg.update(gueltig=grund is None, grund=grund, familie=familie if grund is None else None, familie_bestwert=familie)
    log(f"  KEGELDACH ({familie}): Traufe z {z_t:.2f} r {r_e:.2f} (Schaft {r_s:.2f}), " + (f"Knick z {z_k:.2f} r {r_k:.2f}, " if knick else "")
        + f"Spitze z {z_s:.2f} (h {h:.2f}, {erg['neigung_grad']} Grad), Fotos {len(fotos)}, einig {len(einig)}, Formwahl {erg['formwahl']} -> "
        + ("GUELTIG" if grund is None else "UNGUELTIG: " + grund))
    return erg


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


# ---- 24.11.2026 KRANZ / TRAUFE aus triangulierten Fotokanten bzw. Wolken-Flaechenmitte (Befund Hoehen-Angleich 1122, modelle/FEATURE_FORMSITZ.md:110) ----------
# Die waagrechten Tangenten (vermessen) lesen einen AUSKRAGENDEN Ring (Kranz, Traufe) falsch in z (Rezept L31): der vordere Rand liegt um die Tiefe delta vor der Ebene
# durch die Achse und erscheint um delta x tan(Blickhoehe) hoeher (Kamera darunter), der hintere Rand der Untersicht um ebensoviel tiefer. Die Silhouette sieht darum
# ueber der wahren Oberkante (und unter der Unterkante) einen "Geister-Kranz" mit r(z) = sqrt(R^2 - (dz / tan)^2) - Schwabentor 1122: Silhouetten-Traufe 12,75, Kranz im
# Modell 0,75 m dick; Fotokanten-Oberkante 0,84 m, Wolke 0,75 m tiefer, Wolke Kranz ~0,4 m dick. Hier: HOEHEN aus Quellen ohne diese Falle, Silhouette nur fuer den Radius.
KRANZ_UEBER = 1.08        # Ueberstands-Zone: Profilradius > 108 % des Schafts (gleiche Schwelle wie traufe(): deutlich ueber der Schaftstreuung 2-3 cm)
KRANZ_SUCHE_UNTEN = 1.5   # m: Suchfenster bis 1,5 m unter die Silhouetten-Zone (die Silhouette liest die Unterkante um tan x Tiefe zu tief, die Oberkante zu hoch;
KRANZ_SUCHE_OBEN = 0.25   #    die wahre Oberkante liegt darum nicht ueber der Zone, + 0,25 m = halber Profilschritt Spiel)
KRANZ_DICKE = (0.10, 1.5)  # m: Kranzdicke plausibel 0,1..1,5 m (duenner = eine Kante, dicker = Geschoss, kein Kranz)
KRANZ_BAND_MIN = 0.10     # m: Ringband der Kranz-Aussenseite beginnt mind. 0,1 m (bzw. KRANZ_BAND_ANTEIL des Ueberstands) ausserhalb des Schafts (Schaftfugen bleiben draussen)
KRANZ_BAND_ANTEIL = 0.3   # 30 % des Silhouetten-Ueberstands: Kehle/Profil am Kranzfuss zaehlt zum Kranz, Schaftrauschen (Wolke +-5 cm) nicht
KRANZ_BAND_AUS = 0.30     # m: und endet 0,3 m ausserhalb des Silhouetten-Radius (Kantenlage +-5 cm, Profil der Kranzkante)
KRANZ_SEKTOREN = 3        # ein Ring ist rund: Spitze nur, wenn >= 3 von 12 Richtungs-Sektoren (30 Grad) beitragen (Wandfuge/Gesims am Nachbarbau = 1 Sektor)
KRANZ_BIN = 0.05          # m: Hoehenraster Kanten-Histogramm und Wolkenscheiben
KANT_MIN_N = 20           # Kantenspitze: >= 20 Punkte in +-0,1 m (wie hoehen_angleich KANT_MIN)
KANT_PROM_K = 2.0         # und >= 2 x Untergrund (Median des Fensters, wie hoehen_angleich KANT_PROM)
WOLKE_MIN_N = 20          # Wolkenscheibe zaehlt nur mit >= 20 Punkten
WOLKE_PROM = 2.0          # Wolken-Kranz: Bandanteil der besten Scheibe >= 2 x Median des Fensters
WOLKE_HALB = 0.5          # Flaechenmitte: Kranz = zusammenhaengende Scheiben mit Bandanteil >= 50 % der besten (Halbwertsbreite)
KRANZ_UNEINIG = 0.3       # m: Kanten- und Wolken-Oberkante weiter auseinander = 'uneinig' im Audit (Kanten gelten, KERNMETHODE; nicht gemittelt)
KRANZ_FUGE = 0.02         # m: Uebergang Schaft -> Kranz im Profil (2 cm, nahezu waagrechte Untersicht, nicht entartet)


def kranz_zone(prof, r_s, z_traufe, schritt):
    """Silhouetten-Ueberstandszone um die Traufhoehe: zusammenhaengende Profilhoehen mit r > KRANZ_UEBER x r_s, die z_traufe enthalten -> (z_lo, z_hi, R, Hoehen) | None.
    Grenzen = halber Profilschritt ausserhalb der aeussersten Zonenhoehe; R = Median der Zonenradien (Silhouette misst den Radius in der Ebene durch die Achse richtig)."""
    if z_traufe is None or not prof or not r_s: return None
    zs = [float(p[0]) for p in prof]; i0 = int(np.argmin([abs(z - z_traufe) for z in zs]))
    if abs(zs[i0] - z_traufe) > 1e-6 or prof[i0][1] <= KRANZ_UEBER * r_s: return None
    a = b = i0
    while a > 0 and prof[a - 1][1] > KRANZ_UEBER * r_s: a -= 1
    while b + 1 < len(prof) and prof[b + 1][1] > KRANZ_UEBER * r_s: b += 1             # nach oben auch Geister-Kranz und Dachfuss (bleibt ueber der gemessenen Oberkante weg)
    return zs[a] - schritt / 2, zs[b] + schritt / 2, float(np.median([prof[k][1] for k in range(a, b + 1)])), zs[a:b + 1]


def _ring(P, x, y, r_in, r_aus, z_lo, z_hi):
    d = np.hypot(P[:, 0] - x, P[:, 1] - y); m = (d >= r_in) & (d <= r_aus) & (P[:, 2] >= z_lo) & (P[:, 2] <= z_hi)
    return P[m], d[m], (np.degrees(np.arctan2(P[m, 1] - y, P[m, 0] - x)) % 360 // 30).astype(int)


def kanten_spitzen(KP, x, y, r_in, r_aus, z_lo, z_hi):
    """Waagrechte Ringkanten in den triangulierten Fotokanten (tools/kantenstufe.py -> kanten/sweep.npz): Hoehen-Histogramm der Punkte im Ringband r_in..r_aus.
    Senkrechte Kanten verteilen sich ueber z, eine waagrechte Kante ist eine Spitze. -> Liste dict(z, n, sektoren, r_median) der gueltigen Spitzen (z fallend)."""
    Q, d, sek = _ring(np.asarray(KP, float), x, y, r_in, r_aus, z_lo, z_hi)
    if len(Q) < KANT_MIN_N: return [], dict(n=int(len(Q)))
    e = np.arange(z_lo, z_hi + KRANZ_BIN, KRANZ_BIN); h, _ = np.histogram(Q[:, 2], bins=e); zc = 0.5 * (e[1:] + e[:-1])
    hs = np.convolve(np.pad(h.astype(float), 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid"); bg = max(1.0, float(np.median(hs)))
    out = []
    for i in range(len(hs)):
        if hs[i] < KANT_PROM_K * bg or hs[i] < hs[max(0, i - 1)] or hs[i] < hs[min(len(hs) - 1, i + 1)] or (i > 0 and hs[i] == hs[i - 1]): continue
        nb = np.arange(max(0, i - 2), min(len(hs), i + 3)); zp = float(np.average(zc[nb], weights=np.maximum(hs[nb] - bg, 1e-6)))
        m = np.abs(Q[:, 2] - zp) <= 2 * KRANZ_BIN; n = int(m.sum())
        if n < KANT_MIN_N: continue
        sc = np.bincount(sek[m], minlength=12); ns = int((sc >= max(2, 0.05 * n)).sum())
        if ns < KRANZ_SEKTOREN: continue
        if out and abs(out[-1]["z"] - zp) < 3 * KRANZ_BIN:
            if n <= out[-1]["n"]: continue
            out.pop()
        out.append(dict(z=round(zp, 3), n=n, sektoren=ns, r_median=round(float(np.median(d[m])), 3)))
    return sorted(out, key=lambda s: -s["z"]), dict(n=int(len(Q)), untergrund=round(bg, 1))


def wolke_kranz(W, x, y, r_s, R, z_lo, z_hi, z_schaft=None):
    """Kranz in der dichten Wolke als FLAECHE (nicht Silhouette): je 5-cm-Scheibe Anteil der Punkte im Ringband der Kranz-Aussenseite; Kranz = zusammenhaengende
    Scheiben um die beste mit Anteil >= WOLKE_HALB x bester (Halbwertsbreite), Ring in >= KRANZ_SEKTOREN Sektoren. Wolke misst runde Teile dicker (Fasen, Rauschen):
    Band relativ zum WOLKEN-Schaft (25-%-Quantil der Scheiben-Mediane). -> dict(z_unterkante, z_oberkante, ...) | dict(grund)."""
    W = np.asarray(W, float); d = np.hypot(W[:, 0] - x, W[:, 1] - y); m = (d <= R + 1.0) & (W[:, 2] >= z_lo) & (W[:, 2] <= z_hi); W, d = W[m], d[m]
    if len(W) < 10 * WOLKE_MIN_N: return dict(grund=f"Wolke im Fenster fast leer ({len(W)} Punkte)")
    sek = (np.degrees(np.arctan2(W[:, 1] - y, W[:, 0] - x)) % 360 // 30).astype(int); e = np.arange(z_lo, z_hi + KRANZ_BIN, KRANZ_BIN); k = np.clip(np.digitize(W[:, 2], e) - 1, 0, len(e) - 2)
    med = np.array([np.median(d[k == i]) if (k == i).sum() >= WOLKE_MIN_N else np.nan for i in range(len(e) - 1)])
    if not np.isfinite(med).any(): return dict(grund="keine Wolkenscheibe mit genug Punkten")
    ms = med[(e[:-1] < z_schaft)] if z_schaft is not None else med                       # Wolken-Schaft nur UNTER der Silhouetten-Zone (darueber Dach/Nachbarwand)
    r_sw = float(np.nanpercentile(ms if np.isfinite(ms).any() else med, 25)); dick = float(np.clip(r_sw - r_s, 0.0, 0.3))
    b_in = r_sw + max(KRANZ_BAND_MIN, KRANZ_BAND_ANTEIL * (R - r_s)); b_aus = R + dick + KRANZ_BAND_AUS
    fr = np.zeros(len(e) - 1); gut = np.zeros(len(e) - 1, bool)
    for i in range(len(e) - 1):
        s = k == i; n = int(s.sum())
        if n < WOLKE_MIN_N: continue
        b = s & (d >= b_in) & (d <= b_aus); nb = int(b.sum()); fr[i] = nb / n
        gut[i] = nb >= WOLKE_MIN_N and int((np.bincount(sek[b], minlength=12) >= max(2, 0.03 * nb)).sum()) >= KRANZ_SEKTOREN
    nn = np.bincount(k, minlength=len(e) - 1)[:len(e) - 1] >= WOLKE_MIN_N; bg = float(np.median(fr[nn])) if nn.any() else 0.0   # alle Scheiben mit Punkten (auch Anteil 0)
    if not gut.any(): return dict(grund="kein ringfoermiges Band in der Wolke", band=[round(b_in, 3), round(b_aus, 3)])
    i = int(np.argmax(np.where(gut, fr, -1))); pk = float(fr[i])
    erg = dict(band=[round(b_in, 3), round(b_aus, 3)], r_schaft_wolke=round(r_sw, 3), anteil_best=round(pk, 3), anteil_untergrund=round(bg, 3))
    if pk < WOLKE_PROM * bg: return dict(erg, grund=f"Bandanteil {pk:.2f} < {WOLKE_PROM:g} x Untergrund {bg:.2f} - kein Kranz in der Wolke")
    a = b_ = i
    while a > 0 and gut[a - 1] and fr[a - 1] >= WOLKE_HALB * pk: a -= 1
    while b_ + 1 < len(fr) and gut[b_ + 1] and fr[b_ + 1] >= WOLKE_HALB * pk: b_ += 1
    return dict(erg, z_unterkante=round(float(e[a]), 3), z_oberkante=round(float(e[b_ + 1]), 3), scheiben=int(b_ - a + 1))


def kranz_messen(prof, r_s, x, y, schritt, z_traufe, KP=None, W=None, tan_blick=None, log=print):
    """KRANZ (auskragender Ring an der Traufe) eines Rundkoerpers: Ober- und Unterkante aus Quellen OHNE Auskragungs-Falle, Radius aus der Silhouette.
    Reihenfolge je Kante (nicht gemittelt): 1. triangulierte Fotokanten (KERNMETHODE), 2. Wolken-Flaechenmitte (wolke_kranz), 3. Silhouette mit L31-Rueckrechnung
    (Oberkante = Zonenende - c, c = tan(Blickhoehe) x sqrt(R^2 - (KRANZ_UEBER x r_s)^2): so weit reicht der Geister-Kranz ueber die wahre Kante; hoechstens halber Profilschritt
    ueber der Hoehe des groessten Radius; Unterkante bleibt Silhouette - ANNAHMEN, im Audit).
    Guard: Dicke in KRANZ_DICKE, Oberkante im Suchfenster, sonst gueltig=False -> alter Weg (Silhouetten-Traufe, Profil unveraendert), Grund im Audit."""
    Z = kranz_zone(prof, r_s, z_traufe, schritt)
    if Z is None: return dict(gueltig=False, grund="keine Ueberstands-Zone an der Traufe (kein Kranz)", fallback="alter Weg")
    z_lo, z_hi, R, zz = Z; w_lo, w_hi = z_lo - KRANZ_SUCHE_UNTEN, z_hi + KRANZ_SUCHE_OBEN
    erg = dict(silhouette=dict(z_unten=round(z_lo, 3), z_oben=round(z_hi, 3), r=round(R, 3), hoehen=zz, z_traufe=z_traufe), r=round(R, 3), fenster=[round(w_lo, 3), round(w_hi, 3)],
               quelle_radius="Silhouette (Umriss-Tangenten in der Ebene durch die Achse)")
    ob, un = {}, {}
    if KP is not None and len(KP):
        sp, info = kanten_spitzen(KP, x, y, r_s + max(KRANZ_BAND_MIN, KRANZ_BAND_ANTEIL * (R - r_s)), R + KRANZ_BAND_AUS, w_lo, w_hi); erg["kanten"] = dict(info, spitzen=sp[:6])
        if sp:
            ob["kanten"] = sp[0]["z"]
            u_ = [s for s in sp[1:] if KRANZ_DICKE[0] <= sp[0]["z"] - s["z"] <= KRANZ_DICKE[1]]
            if u_: un["kanten"] = max(u_, key=lambda s: s["n"])["z"]
    else: erg["kanten"] = dict(grund="keine Kantenpunkte (kanten/sweep.npz fehlt)")
    if W is not None and len(W):
        wk = wolke_kranz(W, x, y, r_s, R, w_lo, w_hi, z_schaft=z_lo); erg["wolke"] = wk
        if "z_oberkante" in wk: ob["wolke"] = wk["z_oberkante"]; un["wolke"] = wk["z_unterkante"]
    else: erg["wolke"] = dict(grund="keine Wolke")
    if tan_blick is not None and tan_blick > 0:
        c = float(tan_blick) * math.sqrt(max(R * R - (KRANZ_UEBER * r_s) ** 2, 0.0)); erg["l31"] = dict(tan_blick=round(float(tan_blick), 3), korrektur=round(c, 3))
        # Oberkante: Zonenende - c, hoechstens halber Schritt ueber der Hoehe des groessten Radius (traufe(); die Zone reicht oft bis in den Dachfuss: 1122 z 12,0..14,0)
        ob["silhouette_l31"] = round(min(z_hi - c, z_traufe + schritt / 2), 3); un["silhouette_l31"] = round(z_lo, 3)   # Unterkante: Silhouette (am 1122-Befund nicht zu tief)
    if "kanten" in ob and "wolke" in ob:
        dd = ob["kanten"] - ob["wolke"]; erg["oberkante_kanten_minus_wolke"] = round(dd, 3); erg["einig"] = abs(dd) <= KRANZ_UNEINIG
    grund = None; z_o = q_o = z_u = q_u = None
    for q in ("kanten", "wolke", "silhouette_l31"):
        if q in ob and w_lo <= ob[q] <= w_hi: z_o, q_o = ob[q], q; break
    if z_o is None: grund = "keine Oberkante aus Fotokanten/Wolke/Silhouette (L31) im Fenster"
    else:
        for q in ("kanten", "wolke", "silhouette_l31"):
            if q in un and KRANZ_DICKE[0] <= z_o - un[q] <= KRANZ_DICKE[1]: z_u, q_u = un[q], q; break
        if z_u is None: grund = f"keine Unterkante {KRANZ_DICKE[0]}..{KRANZ_DICKE[1]} m unter der Oberkante {z_o:.2f} ({q_o})"
    if grund is None and R <= KRANZ_UEBER * r_s: grund = f"Kranzradius {R:.2f} nicht ueber dem Schaft {r_s:.2f}"
    erg.update(oberkanten={k: round(v, 3) for k, v in ob.items()}, unterkanten={k: round(v, 3) for k, v in un.items()}, gueltig=grund is None, grund=grund)
    if grund is None:
        erg.update(z_oberkante=round(z_o, 3), z_unterkante=round(z_u, 3), dicke=round(z_o - z_u, 3), quelle_oberkante=q_o, quelle_unterkante=q_u,
                   dicke_silhouette=round(z_hi - z_lo, 3), traufe_alt=z_traufe)
        if "silhouette_l31" in (q_o, q_u): erg["annahmen"] = ["ANNAHME: L31-Rueckrechnung nur an der Oberkante (Geister-Kranz bis tan x sqrt(R^2 - Schwelle^2) darueber), Unterkante = Silhouette, tan = Median der Fotos"]
    else: erg["fallback"] = "alter Weg: Traufe und Kranz aus der Silhouette (Auskragungs-Falle L31 moeglich)"
    log(f"  KRANZ: Silhouette z {z_lo:.2f}..{z_hi:.2f} r {R:.2f}; Oberkanten {erg['oberkanten']}, Unterkanten {erg['unterkanten']} -> "
        + (f"Kranz z {z_u:.2f}..{z_o:.2f} (Dicke {z_o - z_u:.2f}, oben {q_o}, unten {q_u})" if grund is None else "ALTER WEG: " + grund))
    return erg


def kranz_einbauen(prof, K):
    """Drehprofil mit gemessenem Kranz: die Silhouetten-Zone (Geister-Kranz) und alle Hoehen zwischen Unter- und Oberkante fallen weg; darunter Schaft bis
    Unterkante - KRANZ_FUGE, dann Kranzradius von der Unter- bis zur Oberkante, bei Oberkante + KRANZ_FUGE der Radius der naechsten Hoehe darueber. Hoehen ueber der
    Oberkante ausserhalb der Zone bleiben. Ungueltig -> Profil unveraendert."""
    if not K or not K.get("gueltig"): return prof
    zo, zu, R = K["z_oberkante"], K["z_unterkante"], K["r"]; zone = set(K["silhouette"]["hoehen"])
    unten = [list(p) for p in prof if p[0] < zu - KRANZ_FUGE - 1e-6 and p[0] not in zone]; oben = [list(p) for p in prof if p[0] > zo + KRANZ_FUGE and p[0] not in zone]
    if not unten: return prof
    rest = list(unten[-1][2:]); r_u = unten[-1][1]
    deckel = [[round(zo + KRANZ_FUGE, 3), oben[0][1]] + rest] if oben else []           # Kranz-Oberseite waagrecht (sonst lofted der Generator schraeg zur naechsten Hoehe)
    return unten + [[round(zu - KRANZ_FUGE, 3), r_u] + rest, [round(zu, 3), R] + rest, [round(zo, 3), R] + rest] + deckel + oben


def tan_blickhoehe(bilder, x, y, z):
    """Median |tan(Blickhoehe)| der Fotos zum Punkt (x, y, z) - Mass der Auskragungs-Falle (L31) fuer die Silhouetten-Rueckrechnung."""
    t = [abs(z - float(B.C[2])) / max(math.hypot(float(B.C[0]) - x, float(B.C[1]) - y), 1.0) for B in bilder]
    return float(np.median(t)) if t else None


def wolke_ausschnitt(pfad, tr, x, y, rad, z_lo, z_hi, block=2_000_000):
    """Dichte Wolke (npy N x >=3, KAMERARAHMEN) blockweise (mmap, RAM) im Zylinder um die Achse -> Punkte im STL-Rahmen (Kamerarahmen - rahmen_verschiebung tr)."""
    A = np.load(pfad, mmap_mode="r"); tr = np.asarray(tr, float); out = []
    for i in range(0, len(A), block):
        B = np.asarray(A[i:i + block, :3], np.float64) - tr; m = (np.abs(B[:, 0] - x) <= rad) & (np.abs(B[:, 1] - y) <= rad) & (B[:, 2] >= z_lo) & (B[:, 2] <= z_hi)
        if m.any(): out.append(B[m].astype(np.float32))
    return np.vstack(out) if out else np.zeros((0, 3), np.float32)


def main(argv=None):
    import cv2, flaeche_ortho as FO
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--koerper"); ap.add_argument("--stl"); ap.add_argument("--uebernehmen", action="store_true")
    ap.add_argument("--max-fotos", type=int, default=120); ap.add_argument("--schritt", type=float, default=0.5); ap.add_argument("--ueber", type=float, default=3.0)
    ap.add_argument("--max-r-px", type=float, default=MAX_R_PX); ap.add_argument("--nur-messen", action="store_true", help="koerper_auto.json nicht schreiben (Vergleichslaeufe)")
    ap.add_argument("--kanten", help="triangulierte Fotokanten der Kantenstufe (kanten/sweep.npz, STL-Rahmen); Standard <DATEN>/<objekt>/kanten/sweep.npz")
    ap.add_argument("--wolke", help="dichte Wolke (npy, Kamerarahmen); Standard konvergenz_wolke.wolke_pfad"); ap.add_argument("--ohne-kranz", action="store_true", help="alter Weg (Traufe aus der Silhouette)")
    a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); A = os.path.join(od, "audit"); kp = a.koerper or os.path.join(A, "koerper_auto.json"); KA = lade(kp)
    if not KA: print("keine", kp); return 3
    rund = [h for h in KA.get("haufen", []) if h.get("form") == "rund" and h.get("kreis") and h.get("angenommen") is not False]
    if not rund: print("kein Rundkandidat in", kp); return 3
    obj, cams = FO.kameras_laden(a.objekt)
    # 24.11.2026 Kranz/Traufe: zweite und dritte Hoehenquelle ohne Auskragungs-Falle (kranz_messen); fehlen beide, rechnet die Silhouette nach L31 zurueck
    KP = wp = None; tr = np.zeros(3)
    if not a.ohne_kranz:
        kpf = a.kanten
        if not kpf:
            try: import pfade; kpf = os.path.join(pfade.DATEN, os.path.basename(od), "kanten", "sweep.npz")
            except Exception: kpf = None
        if kpf and os.path.exists(kpf):
            try: KP = np.load(kpf)["P"].astype(np.float32); print(f"Kranz: {len(KP)} Fotokanten-Punkte aus {kpf} (STL-Rahmen, ANNAHME wie hoehen_angleich)")
            except Exception as e: print("Kranz: Kantenpunkte nicht lesbar:", e)
        else: print(f"Kranz: keine Fotokanten ({kpf})")
        wp = a.wolke
        if not wp:
            try: import konvergenz_wolke as KW; wp = KW.wolke_pfad(obj, od)
            except Exception: wp = None
        if not (wp and os.path.exists(wp)): print(f"Kranz: keine dichte Wolke ({wp})"); wp = None
        trs = [c.get("rahmen_verschiebung") for c, _ in cams.values() if c.get("rahmen_verschiebung") is not None]
        if trs: tr = np.median(np.asarray(trs, float), axis=0)                       # Kamerarahmen = STL + rahmen_verschiebung (flaeche_ortho.projektion)
    stlp = a.stl or os.path.join(FO.ROOT, obj["stl"]) if obj.get("stl") else a.stl; inter = None
    if stlp and os.path.exists(stlp):
        import trimesh; m = trimesh.load(stlp); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); inter = m.ray; normalen = np.asarray(m.face_normals)  # Embree, falls vorhanden (21.11.2026: ray_triangle in numpy auf 2,4 Mio. Dreiecken = 11 GB, Lauf beendet)
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
        bilder = []; verd = {}; stufe = ([], [], []); eigen = eigenkoerper(H); innen = None    # 23.11.2026: Vormodell DIESES Koerpers im STL ist kein Verdecker (zirkulaer, s. eigenkoerper)
        for rpx, nr, c, pf, C in wahl:
            im = cv2.imread(pf, cv2.IMREAD_GRAYSCALE)
            if im is None: continue
            z_box = zs[-1] + KEGEL_H[1] * KEGEL_R[1] * r0 * 0.75                      # 23.11.2026: Ausschnitt bis ueber die hoechste gesuchte Kegelspitze (kegeldach)
            ring = np.array([[x0 + 1.6 * r0 * math.cos(t), y0 + 1.6 * r0 * math.sin(t), z] for t in np.linspace(0, 2 * math.pi, 16, endpoint=False) for z in (za, z_box)])
            p, zz, _ = FO.projektion(ring, c); p = p * (im.shape[1] / (c["cx"] * 2)); p = p[zz > 0.5]
            if len(p) < 4: continue
            box = (p[:, 0].min() - 10, p[:, 1].min() - 10, p[:, 0].max() + 10, p[:, 1].max() + 10)
            rpx_bild = rpx * im.shape[1] / (c["cx"] * 2); drei = []
            for ziel in (STUFEN_R_PX[0], STUFEN_R_PX[1], a.max_r_px):
                B = Bild(c, im, box, FO.projektion, min(1.0, ziel / max(rpx_bild, 1e-6))); B.Cxy = np.asarray(C[:2], float); B.C = np.asarray(C, float); B.nr = nr; B.pf = pf; drei.append(B)
            if inter is not None:                                                 # 23.11.2026: Verdeckung je Kandidat (Sperrkarte), Vormodell dieses Koerpers ausgenommen
                sk = Sperrkarte(inter, normalen, c, C, [v / (im.shape[1] / (c["cx"] * 2)) for v in box], eigen)
                if innen is None: innen = Innenkarte(inter, normalen, x0, y0, SUCHE_R[1] * r0 + SUCHE_MITTE + 0.3, list(zs) + [z_box], eigen)
                sk.innen = innen
                for B in drei: B.sperre = sk; B.hinter_nah = HINTERGRUND_NAH * r0
            del im; bilder.append(drei[0]); stufe[0].append(drei[0]); stufe[1].append(drei[1]); stufe[2].append(drei[2])
        if inter is not None:                                                     # Verdeckung des Umrisspunkts (Startkreis + 8 %, ausserhalb des Wolken-Rundkoerpers)
            for bi, B in enumerate(bilder):
                T, N, ok = tangenten(np.array([[x0, y0]]), np.array([r0 * 1.08 + 0.05]), B.Cxy)
                for s in (0, 1):
                    X = np.array([[T[s, 0, 0], T[s, 0, 1], z] for z in zs])
                    for z, vd in zip(zs, verdeckt_strahlen(inter, normalen, B.C, X, eigen)): verd[(bi, s, z)] = bool(vd)
        nv = sum(verd.values()); print(f"  {len(bilder)} Fotos geladen; {nv} von {len(verd)} Umrissbeobachtungen verdeckt (Modell davor)")
        U = vermessen(list(stufe), (x0, y0, r0), zs, verdeckt=lambda bi, s, z: verd.get((bi, s, z), False))
        if not U: print("  keine Beobachtung"); continue
        U["profil_roh"] = U["profil"]; P_, weg = profil_bereinigen(U["profil"], r0); U["profil"] = glaetten(P_)   # 24.11.2026: Suchrand-Werte sind keine Messung (profil_bereinigen)
        if weg: U["profil_suchrand"] = weg; print(f"  Profil: {len(weg)} Hoehen am Suchrand verworfen (z {weg}) - Radius der Hoehe darunter")
        U["oberkante"] = oberkante([p for p in U["profil"] if p[0] >= za]); U["traufe"] = traufe([p for p in U["profil"] if p[0] >= za], a.schritt); U["start_wolke"] = dict(x=x0, y=y0, r=r0)
        sch = [p[1] for p in U["profil"][:max(2, len(U["profil"]) // 2)]]; U["r_schaft"] = round(float(np.median(sch)), 3) if sch else U["r"]
        kranz_gut = False
        if not a.ohne_kranz and U["traufe"] is not None:                          # 24.11.2026: Kranz-Hoehen aus Fotokanten/Wolke, Silhouette nur Radius (kranz_messen)
            Zk = kranz_zone(U["profil"], U["r_schaft"], U["traufe"], a.schritt); Wk = None
            if Zk and wp:
                try: Wk = wolke_ausschnitt(wp, tr, U["x"], U["y"], Zk[2] + 1.5, Zk[0] - KRANZ_SUCHE_UNTEN - 0.5, Zk[1] + KRANZ_SUCHE_OBEN + 0.5)
                except Exception as e: print("  Kranz: Wolke nicht lesbar:", e)
            tb = tan_blickhoehe(stufe[1], U["x"], U["y"], 0.5 * (Zk[0] + Zk[1])) if Zk else None
            K_ = kranz_messen(U["profil"], U["r_schaft"], U["x"], U["y"], a.schritt, U["traufe"], KP=KP, W=Wk, tan_blick=tb); U["kranz"] = K_
            if K_.get("gueltig"):
                U["traufe_silhouette"] = U["traufe"]; U["profil_silhouette"] = U["profil"]; U["profil"] = kranz_einbauen(U["profil"], K_); U["traufe"] = K_["z_oberkante"]; kranz_gut = True
                U["annahmen_kranz"] = [f"Traufe = Kranz-Oberkante {K_['z_oberkante']} ({K_['quelle_oberkante']}), Kranz-Unterkante {K_['z_unterkante']} ({K_['quelle_unterkante']}); Radius {K_['r']} aus der Silhouette"] + K_.get("annahmen", [])
        elif a.ohne_kranz: U["kranz"] = dict(gueltig=False, grund="--ohne-kranz", fallback="alter Weg")
        U["quelle"] = "tools/rund_aus_umriss.py: Umriss-Tangenten in kalibrierten Fotos (messprotokoll/K-*.json), Abstimmung je Foto/Seite/Hoehe normiert"
        U["annahmen"] = ["ANNAHME: Traufe = groesster Radius > 108 % des Schafts in der oberen Haelfte (Dachueberstand), sonst Beginn der Verjuengung < 85 %", "Spitze ueber dem Ende der Umriss-Stuetze FEHLT (nicht gemessen, nicht erfunden)", f"ANNAHME: Oberkante = Ende der Umriss-Stuetze (< {STUETZE_ENDE:.0%} des Medians)", "ANNAHME: Querschnitt kreisrund, Achse lotrecht"]
        gut = U["fotos"] >= MIN_FOTOS and min(U["fotos_links"], U["fotos_rechts"]) >= MIN_SEITEN_FOTOS
        U["gueltig"] = gut; U["grund"] = None if gut else f"zu wenig Fotos ({U['fotos']}, links {U['fotos_links']}, rechts {U['fotos_rechts']})"
        # 23.11.2026 Kegeldach ueber der Traufe (bzw. Oberkante) aus den Umriss-Mantellinien; Verdeckung am Startkegel (r 1,1 x Schaft, h 1 x Schaft) wie oben
        z_t = U["traufe"] if U["traufe"] is not None else U["oberkante"]
        if gut and z_t is not None:
            vk = {}
            if inter is not None:
                for bi, B in enumerate(stufe[1]):
                    F_, okf = kegel_fuesse(B.C, U["x"], U["y"], z_t, [1.1 * U["r_schaft"]], [z_t + U["r_schaft"]])
                    for s in (0, 1):
                        if not okf[0]: continue
                        X = np.array([[*(0.5 * (F_[s, 0] + [U["x"], U["y"]])), z_t + 0.5 * U["r_schaft"]]])
                        vk[(bi, s)] = bool(verdeckt_strahlen(inter, normalen, B.C, X, eigen)[0])
            r_tr = next((p[1] for p in U["profil"] if abs(p[0] - z_t) < 1e-6), None) if U["traufe"] is not None else None   # Traufradius aus dem Drehprofil (nur bei erkannter Traufe)
            if kranz_gut: r_tr = None    # 24.11.2026: Traufe = gemessene Kranz-Oberkante (keine Auskragungs-Falle) -> Traufhoehe FEST, Dach-Traufradius frei (Kranz != Dachrand)
            U["dach"] = kegeldach(stufe[1], U["x"], U["y"], z_t, U["r_schaft"], verdeckt=lambda bi, s: vk.get((bi, s), False), r_traufe=r_tr)
            try: dach_bild(stufe[1], U["x"], U["y"], U["dach"], os.path.join(A, f"rund_dach_{H.get('id', 'r')}.jpg"), verdeckt=lambda bi, s: vk.get((bi, s), False))
            except Exception as e: print("  Dachbild fehlgeschlagen:", e)
        H["umriss"] = U
        print(f"  FOTO-UMRISS: x {U['x']:.2f} y {U['y']:.2f} r {U['r']:.3f} m (Wolke r {r0:.2f}), Rest je Beobachtung {U['rest_beob']} m, {U['beobachtungen']} Beob., "
              f"Fotos {U['fotos']} (links {U['fotos_links']}, rechts {U['fotos_rechts']}), Schaft r {U['r_schaft']}, Traufe {U['traufe']}, Oberkante Umriss {U['oberkante']}  -> {'GUELTIG' if gut else 'UNGUELTIG: ' + U['grund']}")
        print("  Profil z:r(Stuetze) " + " ".join(f"{p[0]:g}:{p[1]:.2f}({p[3]:.2f})" for p in U["profil"]))
        if gut and a.uebernehmen:
            H.setdefault("kreis_wolke", H["kreis"]); H.setdefault("profil_wolke", H.get("profil"))
            ok_ = [p for p in U["profil"] if p[0] <= (U["oberkante"] or zb)]       # ganzes Foto-Profil (Schaft, Ueberstand, Dach) bis zum Ende der Umriss-Stuetze
            H["traufe"] = U["traufe"]
            H["kreis"] = dict(x=U["x"], y=U["y"], r=U["r"], rest=U["rest_beob"], quelle="foto_umriss"); H["profil"] = [[p[0], p[1], p[2]] for p in ok_]; H["mass_quelle"] = "foto_umriss"
            H["dach"] = U.get("dach")                                                  # bauteile.drehkoerper_aus_wolkenrest baut den Kegel nur, wenn gueltig
        if gut: rc = 0
        try: bild(bilder, H, U, os.path.join(A, f"rund_umriss_{H.get('id', 'r')}.jpg"), verd)
        except Exception as e: print("  Bild fehlgeschlagen:", e)
    if not a.nur_messen: json.dump(KA, open(kp, "w"), indent=1, ensure_ascii=False); print("->", kp)
    return rc


def dach_bild(bilder, x, y, KD, aus, verdeckt=None, n=6):
    """Pruefbild Dach (23.11.2026): 6 Fotos ueber den Blickwinkel verteilt (nur unverdeckte Dachumrisse), darauf die Umriss-Mantellinien des gemessenen Dachprofils
    (gruen; geknickt: je Stumpf), der besten Geraden (rot) und der Traufkreis (blau). Bild schlaegt Zahl: passt gruen auf die Dachkante, rot nur oben, ist die Formwahl richtig."""
    import cv2
    if not KD or KD.get("r_traufe") is None: return
    z_t = KD["z_traufe"]; pro = {(0, 200, 0): KD.get("profil") or [[z_t, KD["r_traufe"]], [KD["z_spitze"], 0.0]]}
    G = (KD.get("formwahl") or {}).get("gerade")
    if G and KD.get("profil"): pro[(0, 0, 255)] = [[G.get("z_traufe", z_t), G["r_traufe"]], [G["z_spitze"], 0.0]]
    kand = [bi for bi in range(len(bilder)) if not (verdeckt and verdeckt(bi, 0) and verdeckt(bi, 1))]
    if not kand: return
    az = np.array([math.atan2(bilder[bi].Cxy[1] - y, bilder[bi].Cxy[0] - x) for bi in kand]); o = np.argsort(az); pick = [kand[o[int(i)]] for i in np.linspace(0, len(o) - 1, min(n, len(o)))]
    kacheln = []
    for bi in pick:
        B = bilder[bi]; im = cv2.imread(B.pf)
        if im is None: continue
        s = im.shape[1] / (B.c["cx"] * 2); lw = max(1, im.shape[1] // 700); pts = []
        for col, P in pro.items():
            for (z0, r0), (z1, r1) in zip(P[:-1], P[1:]):
                za = z0 + (z1 - z0) * r0 / max(r0 - r1, 1e-6); F, ok = kegel_fuesse(B.C, x, y, z0, np.array([r0]), np.array([za]))
                if not ok[0]: continue
                fr = (r0 - r1) / r0
                for sd in (0, 1):
                    X = np.array([[*(F[sd, 0] + f * (np.array([x, y]) - F[sd, 0])), z0 + f * (za - z0)] for f in np.linspace(0, fr, 12)]); p, zz, _ = B.proj(X, B.c)
                    if (zz > 0.5).all(): p = (p * s).astype(int); pts.append(p); cv2.polylines(im, [p.reshape(-1, 1, 2)], False, col, lw)
        zt_, re_ = pro[(0, 200, 0)][0]; zs_ = pro[(0, 200, 0)][-1][0]
        Xk = np.array([[x + re_ * math.cos(t), y + re_ * math.sin(t), zt_] for t in np.linspace(0, 2 * math.pi, 40)]); pk, zk_, _ = B.proj(Xk, B.c)
        if (zk_ > 0.5).all(): pk = (pk * s).astype(int); cv2.polylines(im, [pk.reshape(-1, 1, 2)], True, (255, 160, 0), lw); pts.append(pk)    # Traufkreis (blau)
        ps_, zz_, _ = B.proj(np.array([[x, y, zs_]]), B.c)
        if zz_[0] > 0.5: pts.append((ps_ * s).astype(int))
        if not pts: continue
        Q = np.vstack(pts); w_ = max(Q[:, 0].max() - Q[:, 0].min(), 20); x0 = int(max(0, Q[:, 0].min() - 0.6 * w_)); x1 = int(min(im.shape[1], Q[:, 0].max() + 0.6 * w_))
        y0 = int(max(0, Q[:, 1].min() - 0.5 * w_)); y1 = int(min(im.shape[0], Q[:, 1].max() + 0.5 * w_)); k = im[y0:y1, x0:x1]
        if k.size == 0: continue
        k = cv2.resize(k, (max(1, int(k.shape[1] * 360 / k.shape[0])), 360)); cv2.putText(k, B.nr[-14:], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1); kacheln.append(k)
    if not kacheln: return
    out = np.hstack(kacheln); cv2.putText(out, f"gruen: {KD.get('familie_bestwert') or KD.get('familie')} {KD.get('profil') or ''}  rot: beste Gerade  gueltig {KD.get('gueltig')}", (4, 352), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    cv2.imwrite(aus, out, [cv2.IMWRITE_JPEG_QUALITY, 85]); print("  Dachbild:", aus)


def bild(bilder, H, U, aus, verd=None):
    """Pruefbild: 6 Fotos ueber den Blickwinkel verteilt, Ausschnitt mit Foto-Umriss (gruen) und Wolkenkreis (rot); rechts Profil r(z).
    23.11.2026: Hoehen, an denen die Umrissbeobachtung als VERDECKT verworfen wurde, als graue Punkte neben dem gruenen Umriss (zaehlt dort nicht)."""
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
                if verd and col == (0, 220, 0):
                    bi = next((i for i, b in enumerate(bilder) if b is B), None); zv = [z for (b_, s_, z), v in verd.items() if v and b_ == bi and s_ == sd]
                    if zv:
                        Xv = np.array([[T[sd, 0, 0], T[sd, 0, 1], z] for z in zv]); pv, _, _ = B.proj(Xv, B.c)
                        for q in (pv * s).astype(int): cv2.circle(im, (int(q[0]) + 3 * max(1, im.shape[1] // 600), int(q[1])), 2 * max(1, im.shape[1] // 600), (150, 150, 150), -1)
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
