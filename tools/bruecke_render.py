#!/usr/bin/env python3
"""bruecke_render.py - RENDER-ABGLEICH fuer die Kettenstufe BRUECKE (27.11.2026, Analyse durch Synthese; loest die Profilspitzen-Deutung in bruecke_messen.messen ab).

Warum: die Profilspitzen-Messung (bruecke_messen.messen) musste jede Spitze im Hoehenprofil einem Bauteil ZUORDNEN (unterste = Unterkante, oberste = Traufe ...).
Kanten anderer Ebenen (Geisterkanten der Gegenseite, Dach, Strasse) erschienen als zusaetzliche Spitzen -> falsche Zuordnung (Synthetik: Traufe 10,56 statt 8,60,
Tauschtest instabil). Hier ordnet das MODELL zu: der Baustein bauteile.ueberdachter_gang (derselbe wie im Bau) wird je Kamera mit eigener Verdeckung gerastert
(render_kern.dreiecke_rastern, GPU), seine sichtbaren scharfen Kanten werden mit den Fotokanten verglichen, die Parameter werden so gewaehlt, dass die Guete maximal ist.

Guete je Foto (Pixel des halben Bildes): BELEGT = Fotokantenpixel, an denen eine sichtbare Modellkante gleicher Richtung naeher als TAU liegt (jedes Fotopixel EINMAL,
weich gewichtet) minus STRAFE x Bildlaenge sichtbarer Modellkanten ohne Fotokante. Gesamt = Mittel ueber die Fotos.
VERSUCHT 27.11. (Synthetik, Wahrheit bekannt): F1 mit Recall im Modellbereich -> schmales kurzes Modell schlug die Wahrheit (0,54 gegen 0,51); Summe ueber Modellpunkte
minus Zufallsrate -> zwei Modellkanten an einer Fotokante doppelt belohnt (duenne Wand + dickes Dach 141 gegen 113); STRAFE 0,5 -> Flachdach schlug das echte
(kantenarme Modelle gewinnen, wo gleich helle Flaechen keine Fotokante haben); 0,25 -> Wahrheit vor allen Gegenmodellen. CMA-ES ueber alle 15 Parameter und reine
Koordinatensuche ab Zonenmitte -> lokale Optima (geschlossener schmaler Gang) -> verworfen.

Suche: (1) KANDIDATEN aus dem Linien-Sweep (bruecke_messen.messen: Wandebenen, Pfostenabstand, Enden, ALLE Hoehenspitzen - ohne Zuordnung); (2) ZUORDNUNG
Spitzen -> Unterkante/Holm/Riegel/Traufe und Wandpaar per Render-Guete nur auf Laengskanten der Waende (unabhaengig von Dach und Pfosten); (3) DACH gemeinsam
(Traufe, Neigung, Ueberstand, Dicke; beste 8 Rasterpunkte lokal verfeinert); (4) PFOSTEN gemeinsam (Zahl x Breite); (5) Koordinatenrunden ueber alle Parameter;
(2)-(5) wiederholt, bis sich nichts aendert; (6) Feinrunden. Die Zone ist nur Suchraum/Start; Tauschtest (+-30 %) muss dieselben Werte liefern.
Beleg je Parameter: in der letzten Feinabtastung hat jedes Foto eine eigene Guetekurve; ein Foto STIMMT ZU, wenn sein eigenes Maximum (mit Kontrast) beim
gemeinsamen Bestwert liegt. < 3 zustimmende Fotos -> 'fehlt' (nicht belegt), nie ein Ersatzwert.

Aufruf (tools/py waehlt venv-seg wegen torch):
  tools/py tools/bruecke_render.py KAMWAHL.json LAGE.json AUSDIR [--wolke PLY] [--zone_skala 1.0] [--ohne_tausch] [--teiler 2] [--max_kam 40]
rc 0 = Massliste geschrieben (einzelne Masse duerfen 'fehlt'/'instabil' sein -> Bau-Tor ROT), 2 = keine Fotokanten / kein Modell.
"""
import sys, os, json, math, time, copy
import numpy as np, cv2, trimesh
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import bauteile as BT
import bruecke_messen as BM

NB = 8            # Richtungsklassen der Linien (180/8 = 22,5 Grad)
DQ = 8.0          # Abstandsfeld uint8 in 1/8 px, gekappt bei 255/8 ~ 32 px
TAU = 3.0         # Kappe in Pixeln (verkleinertes Bild): Kante zaehlt voll bei 0 px, gar nicht ab TAU
STRAFE = 0.25     # Guete je Foto = belegte Fotokante (px, jedes Pixel einmal) - STRAFE x Modellkante ohne Fotokante (px)
SCHRITT = 0.02    # Abtastschritt der Modellkanten (m) -> Guete in Metern


def _klasse(theta):
    """Linienrichtung (rad, Bild) -> Klasse 0..NB-1 (mod pi)."""
    return (np.floor((np.mod(theta, np.pi) / np.pi) * NB + 0.5).astype(int)) % NB


class FotoKanten:
    """Fotokanten EINES Fotos im verkleinerten Raster (teiler): Abstandsfeld je Richtungsklasse + Kantenpixel je Klasse + Umgebungsverdeckung."""
    def __init__(self, c, grau, teiler=2, min_len=12, verdeckt=None):
        self.c = c; self.T = teiler; H, W = grau.shape[0] // teiler, grau.shape[1] // teiler; self.W, self.H = W, H
        # LSD im VOLLEN Bild (27.11.: im halben Bild fehlten kontrastarme Pfostenkanten -> Pfostenzahl ohne Einfluss), Segmente in das Raster 1/teiler
        seg = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(cv2.GaussianBlur(grau, (0, 0), 0.8))[0]
        if seg is not None: seg = (seg.reshape(-1, 4) + 0.5) / teiler - 0.5
        M = np.zeros((NB, H, W), np.uint8)
        if seg is not None:
            seg = seg.reshape(-1, 4); L = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]); seg = seg[L >= min_len]
            kl = _klasse(np.arctan2(seg[:, 3] - seg[:, 1], seg[:, 2] - seg[:, 0]))
            for (x1, y1, x2, y2), k in zip(seg, kl):
                cv2.line(M[k], (int(round(x1)), int(round(y1))), (int(round(x2)), int(round(y2))), 1, 1)
        self.n_seg = 0 if seg is None else len(seg)
        self.dt = np.empty((NB, H, W), np.uint8)
        for b in range(NB):
            u = M[b] | M[(b - 1) % NB] | M[(b + 1) % NB]
            self.dt[b] = np.minimum(cv2.distanceTransform((1 - u).astype(np.uint8), cv2.DIST_L2, 3) * DQ, 255).astype(np.uint8) if u.any() else 255
        self.pix = [np.nonzero(M[b]) for b in range(NB)]                    # (ys, xs) je Klasse
        self.verdeckt = verdeckt


def kanten_modell(t, winkel=25.0, schritt=SCHRITT):
    """Scharfe Kanten eines Netzes -> Abtastpunkte X (N,3), Kantennummer eid (N,), Endpunkte A, B (E,3)."""
    ang = t.face_adjacency_angles; e = t.face_adjacency_edges[ang > math.radians(winkel)]
    A = t.vertices[e[:, 0]]; B = t.vertices[e[:, 1]]; L = np.linalg.norm(B - A, axis=1); n = np.maximum(2, np.ceil(L / schritt).astype(int) + 1)
    eid = np.repeat(np.arange(len(e)), n); off = np.cumsum(n) - n; k = np.arange(n.sum()) - np.repeat(off, n); s = k / (np.repeat(n, n) - 1.0)
    X = A[eid] + (B - A)[eid] * s[:, None]
    return X, eid, A, B


def foto_guete(t, X, eid, A, B, fk, tau=TAU):
    """Kantenabgleich EINES Fotos fuer das Modell t (sichtbare Modellkanten gegen Fotokanten). Liefert (belegt, unbelegt, p_sum, p_n):
    belegt = Fotokantenpixel mit sichtbarer Modellkante gleicher Richtung naeher als tau (jedes Pixel einmal, weich gewichtet), unbelegt = Bildlaenge (px)
    sichtbarer Modellkanten ohne Fotokante, p_sum/p_n = Trefferguete-Summe/Zahl der sichtbaren Modellpunkte (Diagnose, Praezision = p_sum/p_n)."""
    import render_kern as RK
    c = fk.c; T = fk.T; W, H = fk.W, fk.H; Rn = np.asarray(c["Rn"], float); tn = np.asarray(c["tn"], float)
    f2 = c["f"] / T; cx2 = (c["cx"] + 0.5) / T - 0.5; cy2 = (c["cy"] + 0.5) / T - 0.5
    depth = RK.dreiecke_rastern(t, Rn, tn, f2, cx2, cy2, W, H, nur_tiefe=True)[0]
    Xc = X @ Rn.T + tn; z = Xc[:, 2]; zz = np.maximum(z, 1e-3)
    up = np.round(f2 * Xc[:, 0] / zz + cx2).astype(int); vp = np.round(f2 * Xc[:, 1] / zz + cy2).astype(int)
    ok = (z > 0.5) & (up >= 0) & (up < W) & (vp >= 0) & (vp < H)
    uvf, _ = BM.projizieren(c, X); ud = np.round((uvf[:, 0] + 0.5) / T - 0.5).astype(int); vd = np.round((uvf[:, 1] + 0.5) / T - 0.5).astype(int)
    ok &= (ud >= 0) & (ud < W) & (vd >= 0) & (vd < H)
    dp = np.full(len(X), np.inf); dp[ok] = depth[vp[ok], up[ok]]
    vis = ok & ~(dp < z - (0.05 + 0.004 * z))                                # Selbstverdeckung
    if fk.verdeckt is not None and vis.any(): vis[vis] = ~fk.verdeckt(uvf[vis], z[vis], rand=1.5)
    # Bildrichtung und Bildlaenge je Abtastpunkt aus dem NACHBARPUNKT derselben Kante (27.11. echte Fotos: Kantenenden hinter der Kamera gaben aus den
    # Endpunkten riesige Bildlaengen -> Guete -4e10); Punkte, deren Nachbar nicht vor der Kamera liegt, und Bildschritte > 8 px fallen weg
    nb = np.r_[np.arange(1, len(X)), len(X) - 1]; letzt = np.r_[eid[1:] != eid[:-1], True]; nb[letzt] = np.arange(len(X))[letzt] - 1
    du = (uvf[nb] - uvf) / T; du[letzt] *= -1; w = np.hypot(du[:, 0], du[:, 1])
    vis &= (z[nb] > 0.5) & (w > 1e-6) & (w <= 8.0)
    if not vis.any(): return 0.0, 0.0, 0.0, 0
    kl = _klasse(np.arctan2(du[vis, 1], du[vis, 0])); u_, v_ = ud[vis], vd[vis]; w = w[vis]                  # Bildlaenge (px) je Abtastpunkt
    d = fk.dt[kl, v_, u_].astype(np.float32) / DQ; p = np.clip(1 - d / tau, 0, 1)
    unbelegt = float(((1 - p) * w).sum())                                                       # Modellkante ohne Fotokante (px)
    # Belegte Fotokante (px): jedes Fotokantenpixel zaehlt EINMAL, wenn eine sichtbare Modellkante gleicher Richtung naeher als tau liegt
    # (27.11.: Summe ueber Modellpunkte belohnte zwei Modellkanten an EINER Fotokante doppelt -> duenne Wand, dickes Dach, Wahrheit 112,6 gegen falsch 141,4)
    m = int(math.ceil(tau)) + 1; y0, y1 = max(0, v_.min() - m), min(H, v_.max() + m + 1); x0, x1 = max(0, u_.min() - m), min(W, u_.max() + m + 1)
    Mm = np.zeros((NB, y1 - y0, x1 - x0), np.uint8); Mm[kl, v_ - y0, u_ - x0] = 1
    belegt = 0.0
    for b_ in range(NB):
        py, px = fk.pix[b_]; s = (py >= y0) & (py < y1) & (px >= x0) & (px < x1)
        if not s.any(): continue
        u = Mm[b_] | Mm[(b_ - 1) % NB] | Mm[(b_ + 1) % NB]
        if not u.any(): continue
        ys_, xs_ = py[s] - y0, px[s] - x0
        dm = cv2.distanceTransform((1 - u).astype(np.uint8), cv2.DIST_L2, 3)[ys_, xs_]; belegt += float(np.clip(1 - dm / tau, 0, 1).sum())
    return belegt, unbelegt, float(p.sum()), int(len(p))


# ---------------------------------------------------------------- Parameter <-> Baustein

SCHLUESSEL = ("s_a", "s_b", "ql", "qr", "gier", "zu", "zb", "zh", "zr", "zt", "neigung", "ueberstand", "pfosten_breite", "pfosten", "wand_dicke", "dach_dicke")


def baustein_param(x, zone, dmin):
    """Suchvektor (absolute Hoehen, Enden im Rahmen) -> Parameter-dict fuer bauteile.ueberdachter_gang."""
    R = zone["rahmen"].gedreht(x["gier"]); qc = 0.5 * (x["ql"] + x["qr"]); a = R.welt(x["s_a"], qc, 0.0)[:2]; b = R.welt(x["s_b"], qc, 0.0)[:2]
    return dict(achse=dict(a=a.tolist(), b=b.tolist()), breite=x["qr"] - x["ql"], z_boden=x["zb"], hoehe=x["zt"] - x["zb"], boden_dicke=x["zb"] - x["zu"],
                wand_dicke=max(dmin, x.get("wand_dicke", dmin)), einbinden=0.0,
                dach=dict(form="sattel", neigung_grad=x["neigung"], ueberstand=x["ueberstand"], dicke=max(dmin, x.get("dach_dicke", dmin))),
                seiten=dict(art="offen", pfosten=int(x["pfosten"]), pfosten_breite=x["pfosten_breite"], bruestung=x["zh"] - x["zb"], riegel=x["zt"] - x["zr"]),
                quelle="bruecke_render (Render-Abgleich gegen Fotokanten)")


class Abgleich:
    def __init__(self, fks, zone, massstab=87.0, min_mm=0.8, threads=8, log=print):
        self.tau = TAU; self.filter = None; self.fks = fks; self.zone = zone; self.dmin = min_mm * massstab / 1000.0; self.cache = {}; self.n_eval = 0; self.log = log; self.threads = threads
        from concurrent.futures import ThreadPoolExecutor
        self.ex = ThreadPoolExecutor(threads); self.aussen = ThreadPoolExecutor(4)

    def guete(self, x):
        """Gesamtguete (Mittel ueber die Fotos) + Guete je Foto. Ungueltige Parameter (Baustein baut nicht / Ersatzform) -> -1e9."""
        key = tuple(round(float(x[k]), 4) for k in SCHLUESSEL) + (self.tau, self.filter)
        if key in self.cache: return self.cache[key]
        self.n_eval += 1
        g, _, ms = BT.ueberdachter_gang(baustein_param(x, self.zone, self.dmin))
        if g is None or ms.get("art") in ("nicht gebaut", "massiver Steg") or any(r["bauteil"] in ("dach", "seiten", "gang") for r in ms.get("rot", [])):
            r = (-1e9, np.full(len(self.fks), -1e9)); self.cache[key] = r; return r
        t = BT.als_trimesh(g); X, eid, A, B = kanten_modell(t)
        # Raster am unterteilten Netz: render_kern verwirft Dreiecke mit einer Ecke < 1 m vor der Kamera; lange Deck-/Dachflaechen ueber einer Kamera unter
        # der Bruecke fielen sonst ganz weg (keine Verdeckung) (27.11.)
        v_, f_ = trimesh.remesh.subdivide_to_size(t.vertices, t.faces, max_edge=1.0); tr = trimesh.Trimesh(v_, f_, process=False)
        if self.filter == "laengs_wand":
            # nur LAENGSkanten der Wandebenen unter der Traufe zaehlen (Verdeckung rechnet weiter das ganze Modell): Hoehenzuordnung unabhaengig von
            # Dachneigung und Pfostenzahl, die zu dem Zeitpunkt noch nicht gemessen sind (27.11.: gekoppelte Stufen blieben eine Spitze zu hoch haengen)
            Rg = self.zone["rahmen"].gedreht(x["gier"]); dv = B - A; dv /= np.maximum(np.linalg.norm(dv, axis=1), 1e-9)[:, None]
            qa = Rg.lokal(A)[:, 1]; qb = Rg.lokal(B)[:, 1]; qc = 0.5 * (x["ql"] + x["qr"]); hb = 0.5 * (x["qr"] - x["ql"]) + 0.02
            ok_e = (np.abs(dv[:, :2] @ Rg.d) > 0.95) & (np.maximum(A[:, 2], B[:, 2]) <= x["zt"] + 0.02) & (np.abs(qa - qc) <= hb) & (np.abs(qb - qc) <= hb)
            m = ok_e[eid]; X, eid = X[m], eid[m]
            if not len(X): r = (-1e9, np.full(len(self.fks), -1e9)); self.cache[key] = r; return r
        res = list(self.ex.map(lambda fk: foto_guete(tr, X, eid, A, B, fk, self.tau), self.fks))
        # Guete je Foto = belegte Fotokante (px) - STRAFE x Modellkante ohne Fotokante (px); kein Bereich, der vom Modell abhaengt (siehe Kopf: VERSUCHT)
        F = np.array([bel - STRAFE * unb for bel, unb, _, _ in res])
        r = (float(F.mean()), F); self.cache[key] = r; return r

    def grenzen(self, x, k, lo, hi):
        """Reihenfolge der Hoehen erzwingen (Unterkante < Laufebene < Holm < Riegel < Traufe), Mindestabstand = Druck-Mindestmass."""
        d = self.dmin + 0.01
        if k == "zu": hi = min(hi, x["zb"] - d)
        if k == "zb": lo = max(lo, x["zu"] + d); hi = min(hi, x["zh"] - d)
        if k == "zh": lo = max(lo, x["zb"] + d); hi = min(hi, x["zr"] - d)
        if k == "zr": lo = max(lo, x["zh"] + d); hi = min(hi, x["zt"] - d)
        if k == "zt": lo = max(lo, x["zr"] + d)
        if k == "s_a": hi = min(hi, x["s_b"] - 2.0)
        if k == "s_b": lo = max(lo, x["s_a"] + 2.0)
        if k == "ql": hi = min(hi, x["qr"] - 0.6)
        if k == "qr": lo = max(lo, x["ql"] + 0.6)
        return lo, hi

    def abtasten(self, x, k, lo, hi, schritt, kurven=None):
        lo, hi = self.grenzen(x, k, lo, hi)
        if hi < lo: return x
        if k == "pfosten": werte = np.arange(int(math.ceil(lo)), int(math.floor(hi)) + 1)
        else: werte = np.unique(np.r_[np.arange(lo, hi + 1e-9, schritt), np.clip(x[k], lo, hi)])
        best = (self.guete(x)[0], x[k]); kurve = []
        xs = [dict(x, **{k: float(v)}) for v in werte]
        for v, (g, F) in zip(werte, self.aussen.map(self.guete, xs)):
            kurve.append((float(v), g, F))
            if g > best[0] + 1e-9: best = (g, float(v))
        if kurven is not None: kurven[k] = kurve
        x = dict(x); x[k] = best[1]; return x


def suchraum(zone, ext=0.5):
    """Grenzen je Parameter aus der Zone (je Seite um ext x Ausdehnung erweitert). NUR Suchraum."""
    L = zone["s1"] - zone["s0"]; Hz = zone["z1"] - zone["z0"]; q = zone["qmax"]
    zlo, zhi = zone["z0"] - ext * Hz, zone["z1"] + ext * Hz
    return dict(s_a=(zone["s0"] - ext * L, 0.0), s_b=(0.0, zone["s1"] + ext * L), ql=(-q * (1 + ext), q * (1 + ext)), qr=(-q * (1 + ext), q * (1 + ext)), gier=(-4.0, 4.0),
                zu=(zlo, zhi), zb=(zlo, zhi), zh=(zlo, zhi), zr=(zlo, zhi), zt=(zlo, zhi), neigung=(5.0, 60.0), ueberstand=(0.0, 1.2),
                pfosten_breite=(0.06, 0.4), wand_dicke=(0.07, 0.4), dach_dicke=(0.07, 0.4), pfosten=(2, max(3, int(L * (1 + 2 * ext) / 0.8))))


GROB = dict(s_a=0.3, s_b=0.3, ql=0.1, qr=0.1, gier=0.5, zu=0.15, zb=0.15, zh=0.15, zr=0.15, zt=0.15, neigung=2.5, ueberstand=0.1, pfosten_breite=0.04, pfosten=1, wand_dicke=0.04, dach_dicke=0.04)
FEIN = dict(s_a=(0.1, 1.0), s_b=(0.1, 1.0), ql=(0.03, 0.3), qr=(0.03, 0.3), gier=(0.2, 1.0), zu=(0.03, 0.3), zb=(0.03, 0.3), zh=(0.03, 0.3), zr=(0.03, 0.3),
            zt=(0.03, 0.3), neigung=(1.0, 5.0), ueberstand=(0.05, 0.3), pfosten_breite=(0.02, 0.1), pfosten=(1, 3), wand_dicke=(0.02, 0.1), dach_dicke=(0.02, 0.1))
REIHE = ("ql", "qr", "zt", "zb", "zu", "s_a", "s_b", "zh", "zr", "neigung", "ueberstand", "pfosten", "pfosten_breite", "wand_dicke", "dach_dicke", "gier")


def start_aus_zone(zone):
    """Startwerte = Zonenmitte (generisch, gleiche Anteile fuer jede Zone; keine Objektwerte)."""
    z0, z1 = zone["z0"], zone["z1"]; h = z1 - z0; L = zone["s1"] - zone["s0"]
    return dict(s_a=zone["s0"] * 0.9, s_b=zone["s1"] * 0.9, ql=-0.5 * zone["qmax"], qr=0.5 * zone["qmax"], gier=0.0, zu=z0 + 0.25 * h, zb=z0 + 0.33 * h, zh=z0 + 0.45 * h,
                zr=z0 + 0.58 * h, zt=z0 + 0.62 * h, neigung=30.0, ueberstand=0.3, pfosten_breite=0.15, pfosten=max(3, int(round(L / 3.0)) + 1), wand_dicke=0.1, dach_dicke=0.1)


TAU_GROB = (8.0, 5.0)   # grobe Runden mit weicher Kappe (breites Einzugsgebiet), feine mit TAU


def lichtraum_unterkante(Xall, zone, kern=0.6, bin_m=0.1, anteil=0.1):
    """LAGE-VETO aus der Wolke (nur Veto, nie Form): unter einer Bruecke ist der Raum zwischen Strasse und Deck fast leer (Strasse, Autos, Menschen
    geben nur duenne Punkte), das Deck ist die UNTERSTE DICHTE Schicht. Im Kern des Grundrisses (|q| < kern x qmax, mittlere kern-Anteile der Laenge)
    z-Histogramm der Wolke; erste Klasse von unten mit >= anteil x der vollsten Klasse = Deck-Unterseite laut Wolke. Rueckgabe dict oder None (zu wenig Punkte).
    27.11.: Hoehenkandidaten 1,78/1,98/2,16 (Strassenkanten) wurden sonst als Unterkante zugeordnet. Echte Wolke: 0-4,5 m je 0,5 m 30-120 Punkte,
    4,5-5,0 m 2165, 5,0-5,5 m 24332 (leere Luecke gibt es nicht - Strassenpunkte streuen bis 4 m; deshalb Dichte statt Leerstelle)."""
    if Xall is None or not len(Xall): return None
    l = zone["rahmen"].lokal(Xall); L = zone["s1"] - zone["s0"]; m = 0.5 * (zone["s0"] + zone["s1"])
    sel = (np.abs(l[:, 1]) < kern * zone["qmax"]) & (np.abs(l[:, 0] - m) < 0.5 * kern * L) & (l[:, 2] < zone["z1"])
    z = l[sel, 2]
    if len(z) < 500: return None
    bins = np.arange(np.percentile(z, 0.5), zone["z1"] + bin_m, bin_m); h = np.histogram(z, bins)[0]
    i = int(np.argmax(h >= anteil * h.max()))
    return dict(deck_unten=round(float(bins[i]), 2), punkte=int(len(z)), voll=int(h.max()))


def kandidaten_aus_sweep(kams, bilder, zone, raster=0.04, reserve=0.6, max_hoehen=10, log=print, lichtraum=None):
    """KANDIDATEN aus dem Linien-Sweep (bruecke_messen.messen): Wandebenen, Pfostenabstand, Enden und ALLE Hoehenspitzen der Wandprofile - ohne Zuordnung.
    Welche Spitze Unterkante/Holm/Riegel/Traufe ist, entscheidet danach der Render-Abgleich (Modell mit Verdeckung), nicht eine Reihenfolgeregel."""
    t0 = time.time(); kbs = [BM.kantenbild(b) for b in bilder]
    ml, diag = BM.messen(kams, kbs, zone, raster=raster, reserve=reserve, log=lambda *_: None)
    K = dict(waende=[], hoehen=[], abstand=None, s_a=ml.get("s_a"), s_b=ml.get("s_b"))
    if ml.get("status") != "gemessen": log(f"  Sweep-Kandidaten: keine ({ml.get('grund')})"); return K
    zm = 0.5 * (zone["z0"] + zone["z1"]); hz = 0.5 * (zone["z1"] - zone["z0"]) * (1 + reserve); zs = np.arange(zm - hz, zm + hz + 1e-9, raster / 2)
    sp = []
    for k, P in diag.items():
        if k.startswith("hoehen_q") and len(P) == len(zs): sp += BM.profil_spitzen(np.asarray(P), zs, None, rel=0.1, k_mad=0.5)
    sp.sort(key=lambda s: -s["v"]); H = []
    for s in sp:
        if all(abs(s["x"] - h) > 0.1 for h in H): H.append(s["x"])
        if len(H) >= max_hoehen: break
    if lichtraum:     # Kanten unter der Deck-Unterseite laut Wolke (Strasse, Autos) koennen nicht zur Bruecke gehoeren; 0,3 m Spiel fuer Wolkenrauschen
        weg = [h for h in H if h < lichtraum["deck_unten"] - 0.3]
        if weg: log(f"  Lichtraum-Veto (Wolke: unterste dichte Schicht ab {lichtraum['deck_unten']} m): Hoehen {', '.join(f'{h:.2f}' for h in sorted(weg))} verworfen")
        H = [h for h in H if h >= lichtraum["deck_unten"] - 0.3]
    K["hoehen"] = sorted(H); K["lichtraum"] = lichtraum
    P_ = ml["parameter"]
    if P_.get("breite", {}).get("wert") is not None: b = P_["breite"]["wert"]; K["waende"].append((ml["qc"] - b / 2, ml["qc"] + b / 2))
    r = diag.get("r"); qm = zone["qmax"] * (1 + reserve); qs = np.arange(-qm, qm + 1e-9, raster)
    if r is not None and len(r) == len(qs):
        # je Seite der Zonenmitte die 3 staerksten lokalen Maxima (27.11. echte Fotos: die 6 staerksten lagen alle auf der fotoreichen Seite -> kein Paar)
        lok = sorted([i for i in range(1, len(r) - 1) if r[i] >= r[i - 1] and r[i] >= r[i + 1]], key=lambda i: -r[i])
        neg = [i for i in lok if qs[i] < -0.3][:3]; pos = [i for i in lok if qs[i] > 0.3][:3]
        for i in neg:
            for j in pos:
                if qs[j] - qs[i] >= 0.8 and (qs[i], qs[j]) not in K["waende"]: K["waende"].append((float(qs[i]), float(qs[j])))
    K["waende"] = K["waende"][:6]
    K["abstand"] = P_.get("pfosten", {}).get("abstand_m")
    log(f"  Sweep-Kandidaten [{time.time() - t0:.0f} s]: Hoehen {', '.join(f'{h:.2f}' for h in K['hoehen'])}; Waende {', '.join(f'{a:+.2f}/{b:+.2f}' for a, b in K['waende'])}; "
        f"Pfostenabstand {K['abstand']}; Enden {K['s_a']}..{K['s_b']}")
    return K


def zuordnung_suchen(ab, x, K, log=print):
    """Alle Zuordnungen Hoehenspitzen -> (Unterkante, Holm, Riegel, Traufe) und Wandpaare per Render-Guete pruefen; Laufebene vorlaeufig zwischen Unterkante und Holm."""
    import itertools
    best = (ab.guete(x)[0], x); kand = []
    for ql, qr in (K["waende"] or [(x["ql"], x["qr"])]):
        for zu, zh, zr, zt in itertools.combinations(K["hoehen"], 4):
            if zh - zu < 0.3 or zt - zr < ab.dmin: continue
            xx = dict(x, ql=ql, qr=qr, zu=zu, zh=zh, zr=zr, zt=zt, zb=zu + min(0.6, 0.5 * (zh - zu))); kand.append(xx)
    ab.filter = "laengs_wand"; best = (ab.guete(x)[0], x)
    for xx, (g, _) in zip(kand, ab.aussen.map(ab.guete, kand)):
        if g > best[0]: best = (g, xx)
    ab.filter = None
    log(f"  Zuordnung (nur Laengskanten der Waende): {len(kand)} Kombinationen geprueft, beste Guete {best[0]:.1f}: " + ", ".join(f"{k} {best[1][k]:.2f}" for k in ("ql", "qr", "zu", "zh", "zr", "zt")))
    return best[1]


def dach_suchen(ab, x, K, log=print):
    """Dach gemeinsam (Traufe, Neigung, Ueberstand sind gekoppelt: einzeln verschoben bricht die Dachkante weg; 27.11. flaches Ersatzdach 12 Grad mit
    Traufe 9,19 statt 40 Grad / 8,6). Traufe aus den Sweep-Hoehen ueber dem Riegel + aktueller Wert, Neigung 5..60 Grad, Ueberstand 0..0,8 m."""
    zts = sorted({round(h, 3) for h in (K.get("hoehen") or []) if h > x["zr"] + ab.dmin} | {round(x["zt"], 3)})
    kand = [dict(x, zt=zt, neigung=float(n), ueberstand=u, dach_dicke=dd) for zt in zts for n in np.arange(5.0, 60.1, 5.0) for u in (0.0, 0.15, 0.3, 0.5, 0.8)
            for dd in (0.08, 0.15, 0.25)]
    kand.append(dict(x)); G = [g for g, _ in ab.aussen.map(ab.guete, kand)]
    # Die Guete ist um die richtige Dachform sehr schmal (Synthetik: 2 cm Traufe kosten 5 %), das Raster trifft sie nicht genau: die besten
    # Rasterpunkte je Neigungsband kurz lokal verfeinern, dann entscheiden (27.11.: Raster allein waehlte Flachdach 5 Grad)
    # je Neigungsband (10 Grad) der beste Rasterpunkt + der bisherige Stand: sonst fuellen flache Varianten mit verschiedener Traufe alle Plaetze (27.11.)
    o = np.argsort(G)[::-1]; top = [kand[-1]]; baender = set()
    for i in o[:]:
        b = int(kand[i]["neigung"] // 10)
        if b not in baender: baender.add(b); top.append(kand[i])
    best = (-np.inf, x); tau0 = ab.tau; ab.tau = TAU
    for t_ in top:
        y = verfeinern(ab, t_, (("zt", 0.02, 0.1), ("neigung", 1.0, 4.0), ("ueberstand", 0.05, 0.15), ("dach_dicke", 0.02, 0.06), ("wand_dicke", 0.01, 0.04),
                                ("zr", 0.02, 0.12), ("ql", 0.02, 0.06), ("qr", 0.02, 0.06)))      # Riegel/Waende tragen das Dach: mit verfeinern (27.11.)
        g = ab.guete(y)[0]
        if g > best[0]: best = (g, y)
    ab.tau = tau0
    log(f"  Dach: {len(kand)} Kombinationen, {len(top)} verfeinert, beste Guete {best[0]:.1f}: Traufe {best[1]['zt']:.2f}, Neigung {best[1]['neigung']:.0f}, Ueberstand {best[1]['ueberstand']:.2f}")
    return best[1]


def verfeinern(ab, x, plan, runden=2):
    """Kurze lokale Koordinatensuche: plan = ((schluessel, schritt, halbe Breite), ...)."""
    S = None
    for _ in range(runden):
        for k, st, w in plan: x = ab.abtasten(x, k, x[k] - w, x[k] + w, st)
    return x


def suchen(ab, zone, grob_runden=2, fein_runden=2, log=print, K=None):
    S = suchraum(zone); x = start_aus_zone(zone); t0 = time.time()
    if K:
        if K.get("s_a") is not None and K["s_b"] - K["s_a"] >= 4.0: x["s_a"], x["s_b"] = K["s_a"], K["s_b"]     # sonst Zonenstart (Sweep-Enden unbrauchbar)
        if K.get("abstand"): x["pfosten"] = max(2, int(round((x["s_b"] - x["s_a"]) / K["abstand"])) + 1)
    for r in range(grob_runden):
        x_vor = dict(x)
        ab.tau = TAU_GROB[min(r, len(TAU_GROB) - 1)] if not K else TAU_GROB[-1]
        # Zuordnung je Runde neu: in der ersten Runde stehen Enden/Pfosten noch auf den Sweep-Werten (27.11.: Zuordnung bei falschen Enden waehlte die
        # Geisterspitze 9,22 als Traufe; nach den Enden-Scans erneut zugeordnet)
        if K and K.get("hoehen") and len(K["hoehen"]) >= 4:
            x = zuordnung_suchen(ab, x, K, log); x = dach_suchen(ab, x, K, log)
            S_p = suchraum(zone)["pfosten"]; kand = [dict(x, pfosten=n, pfosten_breite=pb) for n in range(S_p[0], S_p[1] + 1) for pb in (0.1, 0.16, 0.25)]
            G = [g for g, _ in ab.aussen.map(ab.guete, kand)]; i = int(np.argmax(G))
            if G[i] > ab.guete(x)[0]: x = kand[i]
            log(f"  Pfosten: {len(kand)} Kombinationen, beste Guete {max(G):.1f}: {x['pfosten']} Pfosten, Breite {x['pfosten_breite']:.2f}")
        for k in REIHE: x = ab.abtasten(x, k, *S[k], GROB[k])
        if r and all(abs(x[k] - x_vor[k]) < 1e-9 for k in SCHLUESSEL):
            log(f"  grob {r + 1}: unveraendert -> Grobsuche beendet"); break
        log(f"  grob {r + 1}: Guete {ab.guete(x)[0]:.4f} ({ab.n_eval} Auswertungen, {time.time() - t0:.0f} s) " + ", ".join(f"{k} {x[k]:.2f}" for k in REIHE))
    kurven = {}; ab.tau = TAU
    if K and K.get("hoehen"):
        # Dach ZULETZT noch einmal bei feiner Kappe, wenn Waende/Hoehen/Pfosten stehen (27.11. Synthetik: in den Grobrunden lag das echte 40-Grad-Dach
        # wegen 2-8 cm Restfehlern an Riegel/Wand unter einem Flachdach mit dicker Platte; mit den Endwerten gewinnt es)
        x = dach_suchen(ab, x, K, log); ab.tau = TAU
    for r in range(fein_runden):
        for k in REIHE:
            st, w = FEIN[k]; lo, hi = S[k]; x = ab.abtasten(x, k, max(lo, x[k] - w), min(hi, x[k] + w), st, kurven if r == fein_runden - 1 else None)
        log(f"  fein {r + 1}: Guete {ab.guete(x)[0]:.4f} ({ab.n_eval} Auswertungen, {time.time() - t0:.0f} s) " + ", ".join(f"{k} {x[k]:.2f}" for k in REIHE))
    return x, kurven


def beleg_je_parameter(kurven, x, min_kontrast=0.1):
    """Je Parameter: Fotos, deren eigene Guetekurve beim gemeinsamen Bestwert ihr Maximum hat (innerhalb 2 Schritten) und Kontrast zeigt -> n_fotos, Streuung."""
    out = {}
    for k, kv in kurven.items():
        v = np.array([a for a, _, _ in kv]); Fm = np.stack([F for _, _, F in kv], 0)         # (werte, fotos)
        if len(v) < 3: out[k] = dict(n_fotos=0, streuung=None, fotos=[]); continue
        st = np.median(np.diff(np.sort(v))) if len(v) > 1 else 0.0
        kon = Fm.max(0) - Fm.min(0); arg = v[np.argmax(Fm, 0)]
        ja = (kon >= min_kontrast) & (np.abs(arg - x[k]) <= 2 * st + 1e-9)
        mit = arg[kon >= min_kontrast]
        sd = float(1.4826 * np.median(np.abs(mit - x[k]))) if len(mit) else None
        out[k] = dict(n_fotos=int(ja.sum()), streuung=sd, fotos=[int(j) for j in np.nonzero(ja)[0]], fotos_mit_kontrast=int((kon >= min_kontrast).sum()))
    return out


# Messgroessen (Schluessel wie bruecke_messen.massliste) aus dem Suchvektor; je Messgroesse die Suchparameter, die sie belegen
MESS = dict(spannweite=("s_a", "s_b"), breite=("ql", "qr"), unterkante=("zu",), laufebene=("zb",), holm=("zh",), riegel=("zr",), traufe=("zt",),
            first=("neigung", "zt", "breite"), ueberstand=("ueberstand",), pfosten=("pfosten",), pfosten_breite=("pfosten_breite",), wand_dicke=("wand_dicke",), dach_dicke=("dach_dicke",), ende_a=("s_a",), ende_b=("s_b",))


def massliste(x, ab, beleg, zone, min_fotos=3, namen=None):
    g, _, ms = BT.ueberdachter_gang(baustein_param(x, zone, ab.dmin)); t = BT.als_trimesh(g)
    werte = dict(spannweite=x["s_b"] - x["s_a"], breite=x["qr"] - x["ql"], unterkante=x["zu"], laufebene=x["zb"], holm=x["zh"], riegel=x["zr"], traufe=x["zt"],
                 first=float(t.bounds[1][2]), ueberstand=x["ueberstand"], pfosten=int(x["pfosten"]), pfosten_breite=x["pfosten_breite"], wand_dicke=x["wand_dicke"], dach_dicke=x["dach_dicke"], ende_a=x["s_a"], ende_b=x["s_b"])
    P = {}
    for k, w in werte.items():
        bl = [beleg.get(p, dict(n_fotos=0)) for p in MESS[k]]; n = min(b["n_fotos"] for b in bl)
        sd = [b.get("streuung") for b in bl if b.get("streuung") is not None]
        e = dict(wert=w, quelle="Render-Abgleich (Modell mit Selbst- und Umgebungsverdeckung gegen LSD-Fotokanten, Kandidaten aus dem Linien-Sweep, Suche nach maximaler belegter Fotokante)", n_fotos=n,
                 streuung=max(sd) if sd else None, suchparameter=list(MESS[k]))
        if namen is not None: e["fotos"] = sorted({namen[j] for b in bl for j in b.get("fotos", [])})[:60]
        if n < min_fotos: e.update(status="fehlt", grund=f"nicht belegt: nur {n} Fotos stimmen dem Wert zu (< {min_fotos})")
        else: e["status"] = "gemessen"
        P[k] = e
    return P


def abgleich(kams, bilder, zone, teiler=2, wolke=None, log=print, threads=8, grob_runden=3, fein_runden=2, namen=None, sweep=True, wolke_alle=None):
    """Kern: Kameras + Grauwertbilder + Zone -> Massliste (dict wie bruecke_messen.messen, methode 'render_abgleich')."""
    t0 = time.time(); R = zone["rahmen"]; kams_alle, bilder_alle = list(kams), list(bilder)
    # Kameras IN der Zone (Fotos auf dem Steg) nicht verwenden: die Kamera steckt im Modell, Nahebene des Rasterers (1 m) -> Sicht nicht rechenbar.
    # ANNAHME/Luecke: Laufebene und Deck innen bleiben so ohne Beleg (wie Abdeckung abd-steg: Deck innen duenn).
    innen = []
    for j, c in enumerate(kams):
        Cc = np.asarray(c.get("C", (-np.asarray(c["Rn"]).T @ np.asarray(c["tn"])).tolist()), float); l = R.lokal(Cc[None])[0]
        if zone["s0"] - 1 <= l[0] <= zone["s1"] + 1 and abs(l[1]) <= zone["qmax"] and zone["z0"] <= l[2] <= zone["z1"]: innen.append(j)
    if innen:
        log(f"  {len(innen)} Kameras in der Zone (auf dem Steg) ausgelassen")
        kams = [c for j, c in enumerate(kams) if j not in innen]; bilder = [b for j, b in enumerate(bilder) if j not in innen]
        if namen is not None: namen = [n for j, n in enumerate(namen) if j not in innen]
    fks = [FotoKanten(c, im, teiler, verdeckt=BM.tiefenpuffer(c, wolke) if wolke is not None and len(wolke) else None) for c, im in zip(kams, bilder)]
    nseg = sum(f.n_seg for f in fks); log(f"  Fotokanten: {len(fks)} Fotos, {nseg} LSD-Segmente  [{time.time() - t0:.0f} s]")
    if nseg < 10 * len(fks): return dict(status="nicht belegt", grund=f"zu wenige Fotokanten ({nseg})", methode="render_abgleich")
    ab = Abgleich(fks, zone, threads=threads, log=log)
    K = kandidaten_aus_sweep(kams_alle, bilder_alle, zone, log=log, lichtraum=lichtraum_unterkante(wolke_alle, zone)) if sweep else None     # Sweep braucht keine Rasterung: alle Kameras, auch die auf dem Steg
    x, kurven = suchen(ab, zone, grob_runden, fein_runden, log, K=K)
    g, F = ab.guete(x)
    if g <= -1e8 or g <= 0: return dict(status="nicht belegt", grund=f"kein gueltiges oder kein belegtes Modell (Guete {g:.3f} m)", methode="render_abgleich")
    beleg = beleg_je_parameter(kurven, x)
    P = massliste(x, ab, beleg, zone, namen=namen)
    ml = dict(status="gemessen", methode="render_abgleich", parameter=P, suchvektor=x, guete=g, guete_je_foto=[round(float(v), 4) for v in F],
              rahmen=dict(mitte=R.gedreht(x["gier"]).m.tolist(), achse=R.gedreht(x["gier"]).d.tolist(), neigung_grad=math.degrees(math.atan(R.tg))),
              qc=0.5 * (x["ql"] + x["qr"]), s_a=x["s_a"], s_b=x["s_b"], auswertungen=ab.n_eval, dauer_s=round(time.time() - t0, 1), beleg=beleg, sweep_kandidaten=K)
    ml["gang"] = baustein_param(x, zone, ab.dmin)
    return ml


def gang_mit_fehlt(ml):
    """Baustein-Parameter + fehlt-Liste (status fehlt/instabil -> ROT im Bau; NIE Ersatzwert: der Wert bleibt, das Tor wird rot)."""
    fehlt = [dict(bauteil=k, grund=v.get("grund", v.get("status"))) for k, v in ml["parameter"].items() if v.get("status") in ("fehlt", "instabil")]
    P = copy.deepcopy(ml["gang"]); P["fehlt"] = fehlt; return P, fehlt


def lauf(kamwahl, lage, ausdir, wolke=None, skala=1.0, tausch=True, teiler=2, max_kam=40, threads=8):
    from concurrent.futures import ThreadPoolExecutor
    Wj = json.load(open(kamwahl)); L = json.load(open(lage)); os.makedirs(ausdir, exist_ok=True)
    names = list(Wj["kameras"])[:max_kam]; kams = [Wj["kameras"][n] for n in names]
    with ThreadPoolExecutor(16) as ex: bilder = list(ex.map(lambda nc: BM.bild_laden(Wj["bilddir"], nc[0], nc[1]), zip(names, kams)))
    zone = BM.zone_aus_lage(L, skala); X = None
    Xall = None
    if wolke: Xall = BM.ply_lesen(wolke, nmax=2_000_000); X = BM.ausser_zone(Xall, BM.zone_aus_lage(L, 1.6)); print(f"  Wolke (ausserhalb der Zone x1,6): {len(X)} Punkte")
    lg = lambda *a: print(*a, flush=True)
    lg(f"Render-Abgleich Zone x{skala}"); ml = abgleich(kams, bilder, zone, teiler, X, threads=threads, namen=names, log=lg, wolke_alle=Xall)
    if tausch and ml["status"] == "gemessen":
        andere = []
        for f in (0.7, 1.3):
            lg(f"Tauschtest Zone x{skala * f:.2f}"); andere.append(abgleich(kams, bilder, BM.zone_aus_lage(L, skala * f), teiler, X, threads=threads, namen=names, log=lg, wolke_alle=Xall))
        BM.tausch_pruefen(ml, andere); ml["tausch"] = [dict(skala=round(skala * f, 2), werte={k: v.get("wert") for k, v in a.get("parameter", {}).items()}) for f, a in zip((0.7, 1.3), andere)]
        print("  Tauschtest:", ", ".join(f"{k} {v['tausch_werte']}" for k, v in ml["parameter"].items() if v.get("status") == "instabil") or "stabil")
    ml.update(kameras=names, zone_skala=skala, lage=os.path.abspath(lage), wolke=wolke)
    if ml["status"] == "gemessen": ml["gang"], ml["fehlt"] = gang_mit_fehlt(ml)
    json.dump(ml, open(os.path.join(ausdir, "massliste_bruecke.json"), "w"), indent=1, ensure_ascii=False, default=float)
    print("Massliste ->", os.path.join(ausdir, "massliste_bruecke.json"), "| fehlt/instabil:", ", ".join(f["bauteil"] for f in ml.get("fehlt", [])) or "nichts")
    return 0 if ml["status"] == "gemessen" else 2


def main():
    if len(sys.argv) < 4: print(__doc__); sys.exit(2)
    def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
    sys.exit(lauf(sys.argv[1], sys.argv[2], sys.argv[3], wolke=opt("--wolke", None, str), skala=opt("--zone_skala", 1.0), tausch="--ohne_tausch" not in sys.argv,
                  teiler=opt("--teiler", 2, int), max_kam=opt("--max_kam", 40, int), threads=opt("--threads", 8, int)))


if __name__ == "__main__":
    main()
