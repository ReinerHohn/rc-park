#!/usr/bin/env python3
"""vordach_profil.py - DACHPROFIL eines Vordachs aus Fotokanten (21.11.2026, Kettenstufe 'bauplan', nach tools/ebenen_masse.py).

Anlass (Nutzer 21.11., audit/neben_eigen__IMG_20261106_113231.jpg Schwabentor Stadtseite): Vordach ueber dem Wandgemaelde ist im Foto ein GESCHWEIFTES Walmdach
(gruen glasierte Ziegel, konkav, nach unten ausschwingende Traufe, geschweifte Seitenflaechen), im Modell eine ebene Platte. Anschluss (19,81) und Traufe (16,02)
misst schon vorbauten_bauplan; die Dachflaeche selbst gibt der Kanten-Sweep nicht her (Ziegel = keine stabilen Kanten, METHODE_EBENEN_BAUPLAN 'Nicht: Dachflaeche').
MESSUNG (KERNMETHODE: Form aus Fotokanten, SfM liefert die Kameras): die Gratlinien (Walmkanten) und die Traufe sind in jedem Foto von vorn/schraeg harte Kanten
(Firstziegel, Umriss vor der Wand). Hypothesen eines Walm-Vordachs
    Front:  z = z_t + (z_a - z_t) * g(a / A)      a = Abstand hinter der Traufe, A = w_t - w_a (Traufe bis Wand)
    Seiten: z = z_t + (z_a - z_t) * g(b / As)     b = Abstand innerhalb der Seitentraufe, As = Ruecksprung des Walms an der Wand (As = 0: senkrechte Giebelseite)
    g(s) = (exp(c s) - 1) / (exp(c) - 1)          c = 0 gerade, c > 0 GESCHWEIFT (flach an der Traufe, steil an der Wand), c < 0 gewoelbt (konvex)
werden in jedes Foto projiziert (SfM-Kameras kanten/kam.json, k1-Verzeichnung) und gegen die Bildkanten (Canny, Abstandskarte) bewertet: Stufe 1 Traufe
(w_t, seitlicher Ueberstand), Stufe 2 Grate + Wandanschlusslinie (c, As). Formfamilie gilt nur, wenn >= --min_fotos Fotos einzeln dieselbe Familie waehlen;
sonst bleibt die Familie 'gerade' (ANNAHME im Ergebnis). Keine Werte aus dem Handstand.
22.11.2026 (Befund 1122a, Vordach zu flach/kaum Ueberstand): Guete = Silhouette des GANZEN Dachkoerpers (Front + Walmseiten, flaechen()) + TRAUFKANTE als Fotokante
(Foto.traufe: Dachhaut ueber der Traufe heller als der Traufschatten darunter). Ohne Traufterm war die Traufe frei (Ring unter der Traufe ausgeblendet) und lag auf der
Raehm-Unterkante: Traufterm 0,09 statt 0,57, Ueberstand 0,20 statt ~0,40 m, seitlich 0,05 statt ~0,20 m; der zu tiefe/innere Eckpunkt zog die Grate gerade (c 1,0 statt 1,5).
Ausgabe: audit/vordach_profil.json {fassaden: [{id, gruppe, u0, u1, w_wand, w_t, z_t, z_a, c, As, familie, profil [[w, z]...], fotos, je_foto, belegt}]} -> bauteile.vorbauten_aus_json
(baut bauteile.vordach_walm) + Kontrollbild audit/vordach_profil.jpg (bestes Profil rot in den Fotos).
Aufruf: vordach_profil.py <objekt.json> <kanten-ordner> [--fotos <ordner>] [--aus audit/vordach_profil.json] [--max_fotos 16] [--min_fotos 3]
rc 0 = mindestens ein Vordach gemessen, rc 3 = kein Vordach in vorbauten_auto.json / keine Fotos.
"""
import sys, os, json, argparse, numpy as np

C_GITTER = np.round(np.arange(-3.0, 6.01, 0.5), 2)          # Krummheit c (0 = gerade)


def g_profil(s, c):
    """Profilfunktion 0..1 (s = 0 Traufe, s = 1 Wand); c = 0 gerade, > 0 geschweift (konkav), < 0 konvex."""
    s = np.asarray(s, float)
    return s if abs(c) < 1e-6 else (np.exp(c * s) - 1.0) / (np.exp(c) - 1.0)


def familie(c, schwelle=0.75):
    return "gerade" if abs(c) < schwelle else ("geschweift" if c > 0 else "gewoelbt")


def walm_kurven(u0, u1, w_a, w_t, z_t, z_a, c, As, n=24):
    """3D-Kanten des Walm-Vordachs in Wandkoordinaten (u, z, w): zwei Grate (Traufecke -> Wand), Wandanschluss zwischen den Graten. Liste von (n, 3)-Arrays."""
    t = np.linspace(0.0, 1.0, n); A = w_t - w_a; z = z_t + (z_a - z_t) * g_profil(t, c); w = w_t - t * A
    links = np.stack([u0 + t * As, z, w], 1); rechts = np.stack([u1 - t * As, z, w], 1)
    ua, ub = u0 + As, u1 - As; oben = np.stack([np.linspace(ua, ub, n), np.full(n, z_a), np.full(n, w_a)], 1) if ub > ua + 0.2 else np.zeros((0, 3))
    return [links, rechts, oben]


def traufe_kurven(u0, u1, w_t, z_t, n=40):
    """Traufkante vorn (u0..u1 bei w_t, z_t) und die zwei Seitentraufen bis 0,4 m zurueck (Ecken)."""
    return [np.stack([np.linspace(u0, u1, n), np.full(n, z_t), np.full(n, w_t)], 1)]


def flaechen(p, n=16):
    """Alle Dachflaechen der Hypothese p als 3D-Vierecke (Wandkoordinaten u, z, w): je Profilstufe ein Frontstreifen und zwei Walmseiten-Streifen
    (Seite = vom Grat bis an die Wand w_a, wie bauteile.vordach_walm baut). Ihre Vereinigung im Foto ist die Silhouette des Dachkoerpers."""
    t = np.linspace(0.0, 1.0, n + 1); A = p["w_t"] - p["w_a"]; z = p["z_t"] + (p["z_a"] - p["z_t"]) * g_profil(t, p["c"]); Q = []
    for i in range(n):
        a, b = t[i], t[i + 1]; wa, wb = p["w_t"] - a * A, p["w_t"] - b * A
        la, ra, lb, rb = p["u0"] + a * p["As"], p["u1"] - a * p["As"], p["u0"] + b * p["As"], p["u1"] - b * p["As"]
        Q.append(np.array([(la, z[i], wa), (ra, z[i], wa), (rb, z[i + 1], wb), (lb, z[i + 1], wb)]))
        for ua, ub in ((la, lb), (ra, rb)): Q.append(np.array([(ua, z[i], wa), (ua, z[i], p["w_a"]), (ub, z[i + 1], p["w_a"]), (ub, z[i + 1], wb)]))
    return Q


class Foto:
    """Eine Kamera (kam.json-Eintrag) + Kantenabstandskarte im Ausschnitt um das Vordach (skaliert auf ~breite px)."""
    def __init__(s, name, K, pfad, welt, box_uzw, breite=700):
        import cv2
        s.name = name; s.K = K; s.welt = welt; s.ok = False
        x, y, d = s.proj_roh(welt(box_uzw))
        if (d <= 1.0).any(): return
        im = cv2.imread(pfad, cv2.IMREAD_GRAYSCALE)
        if im is None: return
        s.sj = im.shape[1] / float(K["W"]); x = x * s.sj; y = y * s.sj
        x0, x1, y0, y1 = int(x.min()) - 30, int(x.max()) + 30, int(y.min()) - 30, int(y.max()) + 30
        if x0 < 0 or y0 < 0 or x1 > im.shape[1] or y1 > im.shape[0]: return
        s.f = breite / float(x1 - x0); s.x0, s.y0 = x0, y0
        cr = cv2.resize(im[y0:y1, x0:x1], (breite, max(8, int((y1 - y0) * s.f))), interpolation=cv2.INTER_AREA)
        s.bild = cv2.GaussianBlur(cr, (0, 0), 1.5).astype(np.float32); s.streu = float(s.bild.std()) + 1.0; s.ok = s.streu > 8.0

    def proj_roh(s, X):
        K = s.K; R = np.array(K["Rn"]); t = np.array(K["tn"]); Xc = X @ R.T + t; d = Xc[:, 2]
        x = Xc[:, 0] / np.maximum(d, 0.3); y = Xc[:, 1] / np.maximum(d, 0.3); f = 1 + K["params"][3] * (x * x + y * y)
        return K["f"] * x * f + K["cx"], K["f"] * y * f + K["cy"], d

    def px(s, uzw):
        x, y, d = s.proj_roh(s.welt(uzw)); return (x * s.sj - s.x0) * s.f, (y * s.sj - s.y0) * s.f

    def bewerte(s, p, ring=4):
        """SILHOUETTEN-KONTRAST einer Hypothese p (dict u0, u1, w_a, w_t, z_t, z_a, c, As): Umriss des ganzen Dachkoerpers (Front + beide Walmseiten, tools/vordach_profil.flaechen)
        ins Foto projiziert; Guete = (Helligkeit im Saum ausserhalb - im Saum innerhalb, je ring px) / Streuung des Ausschnitts. Der Ring unter der Traufe zaehlt nicht (dort Traufkasten/Galerie).
        21.11.2026: Kantenabstand allein las die Ziegelreihen als Kanten (jede Hypothese auf dem Dach 'traf') -> Flaechenkontrast Dach (dunkel) gegen Wand/Himmel.
        22.11.2026: Umriss = Vereinigung aller Dachflaechen statt nur Grat-Polygon - bei schraegen Kameras ist auf der nahen Seite die Walmseite (Wandanschluss/Seitentraufe) der Umriss, nicht der Grat."""
        import cv2
        H, W = s.bild.shape; inn = np.zeros((H, W), np.uint8)
        Q = np.array(flaechen(p)); x, y = s.px(Q.reshape(-1, 3))                       # alle Ecken in einem Zug projizieren
        if x.min() < -5 or y.min() < -5 or x.max() > W + 5 or y.max() > H + 5: return -1.0
        for P_ in np.stack([x, y], 1).round().astype(np.int32).reshape(len(Q), 4, 2): cv2.fillPoly(inn, [P_], 1)
        k_ = np.ones((2 * ring + 1, 2 * ring + 1), np.uint8); aus = cv2.dilate(inn, k_) & (1 - inn); inn = inn & (1 - cv2.erode(inn, k_))   # nur der Saum beidseits des Umrisses
        ex, ey = s.px(np.array([[p["u0"], p["z_t"], p["w_t"]], [p["u1"], p["z_t"], p["w_t"]]]))
        if getattr(s, "_yx", None) is None or s._yx[0].shape != (H, W): s._yx = np.mgrid[0:H, 0:W]
        yy, xx = s._yx
        if abs(ex[1] - ex[0]) < 5: return -1.0
        ye = ey[0] + (xx - ex[0]) * (ey[1] - ey[0]) / (ex[1] - ex[0]); aus[yy > ye - 3] = 0      # nicht unter der Traufe
        inn[yy > ye - 3] = 0
        if inn.sum() < 50 or aus.sum() < 50: return -1.0
        return float((s.bild[aus > 0].mean() - s.bild[inn > 0].mean()) / s.streu)

    def traufe(s, p, a=3, b=12, n=60, ausserhalb=0.0):
        """TRAUFKANTE ALS FOTOKANTE (22.11.2026): mittlere Helligkeit im Band a..b px UEBER der projizierten Traufe (Dachhaut, vom Himmel beleuchtet) minus im Band darunter
        (Traufschatten / Traufkasten / Raehm), je Streuung. Vorher zaehlte unter der Traufe gar nichts -> die Traufe war frei und rutschte auf die Unterkante des Raehms
        (Schwabentor 1122a: 0,10 m vor der Galerie statt ~0,4 m). Bandbreite > Ziegelreihe, damit einzelne Ziegelkanten nicht gewinnen; vorzeichenrichtig, damit
        die Unterkante des dunklen Raehms vor hellerer Wand (umgekehrtes Vorzeichen) nicht gewinnt."""
        u = np.linspace(p["u0"] + 0.1, p["u1"] - 0.1, n); x, y = s.px(np.stack([u, np.full(n, p["z_t"]), np.full(n, p["w_t"])], 1))
        dx, dy = np.gradient(x), np.gradient(y); nn = np.hypot(dx, dy) + 1e-9; nx, ny = dy / nn, -dx / nn
        if ny.mean() > 0: nx, ny = -nx, -ny                                               # Normale nach oben im Bild
        H, W = s.bild.shape; ob, un = [], []
        if x.min() < 0 or y.min() < 0 or x.max() >= W or y.max() >= H: return ausserhalb
        for o_ in range(a, b + 1):
            for sg, L_ in ((1, ob), (-1, un)):
                xx = np.clip((x + sg * o_ * nx).round().astype(int), 0, W - 1); yy = np.clip((y + sg * o_ * ny).round().astype(int), 0, H - 1); L_.append(s.bild[yy, xx])
        return float((np.mean(ob) - np.mean(un)) / s.streu)

    def guete(s, p, ring=4):
        """Silhouette + Traufkante (beide je Streuung des Ausschnitts); ring > 4 = breiter Saum/Band fuer die Grobsuche (glatteres Guetegebirge)."""
        b_ = s.bewerte(p, ring=ring)
        return b_ if b_ <= -1.0 else b_ + s.traufe(p, a=3, b=max(12, 2 * ring))


def traufenden(FO, hyp, q, Kb, weit=1.2, schritt=0.05, h=0.15, anteil=0.5):
    """SEITLICHE ENDEN DER TRAUFKANTE aus den Fotos (22.11.2026): Traufkanten-Kontrast (Foto.traufe) je kurzem Abschnitt (u +- h) entlang der gemessenen Traufe
    von Kastenkante - weit bis Kastenkante + weit, Median ueber alle Fotos; Kantenhoehe = Median ueber den Kasten. Die Kante gilt, solange sie >= anteil * Hoehe
    ist (zusammenhaengend von der Kastenmitte aus). dict(links, rechts = Ueberstand neben dem Kasten in m, s = Mittel beider Seiten oder None, hoehe, profil)."""
    us = np.round(np.arange(Kb["u0"] - weit, Kb["u1"] + weit + 1e-6, schritt), 3); p = hyp(q)
    M = np.array([[f_.traufe(dict(p, u0=u - h - 0.1, u1=u + h + 0.1), n=7, ausserhalb=np.nan) for u in us] for f_ in FO])
    med = np.array([np.nanmedian(M[:, i]) if np.isfinite(M[:, i]).sum() >= 3 else np.nan for i in range(len(us))])
    innen = (us > Kb["u0"] + 0.3) & (us < Kb["u1"] - 0.3); hoehe = float(np.nanmedian(med[innen])) if np.isfinite(med[innen]).any() else 0.0
    erg = dict(links=None, rechts=None, s=None, hoehe=hoehe, profil=[[float(u), (None if not np.isfinite(m) else round(float(m), 3))] for u, m in zip(us, med)])
    if hoehe < 0.15: return erg
    gut = np.nan_to_num(med, nan=-1.0) >= anteil * hoehe; i0 = int(np.argmin(np.abs(us - 0.5 * (Kb["u0"] + Kb["u1"]))))
    if not gut[i0]: return erg
    il = i0
    while il > 0 and gut[il - 1]: il -= 1
    ir = i0
    while ir < len(us) - 1 and gut[ir + 1]: ir += 1
    if il == 0 or ir == len(us) - 1: return erg                                     # Kante laeuft bis an den Suchrand: Ende nicht gesehen
    links = round(float(Kb["u0"] - (us[il] - schritt / 2)), 3); rechts = round(float((us[ir] + schritt / 2) - Kb["u1"]), 3)
    erg.update(links=links, rechts=rechts, s=round(float(np.clip(0.5 * (links + rechts), 0.0, weit)), 3)); return erg


def fotos_waehlen(KA, welt, box_uzw, aussen, w_min, max_fotos, fdir, mindestabstand=1.5):
    """Kameras vor der Fassade (w_C >= w_min), Vordach ganz im Bild, Blick nicht steiler als 55 Grad von unten; je Standort (mindestabstand m) nur ein Foto, groesste Abbildung zuerst."""
    kand = []
    for nm, K in KA.items():
        if not os.path.exists(os.path.join(fdir, nm)): continue
        C = np.array(K["C"], float); wC = aussen(C)
        if wC < w_min: continue
        R = np.array(K["Rn"]); t = np.array(K["tn"]); X = welt(box_uzw); Xc = X @ R.T + t
        if (Xc[:, 2] <= 1.0).any(): continue
        x = K["f"] * Xc[:, 0] / Xc[:, 2] + K["cx"]; y = K["f"] * Xc[:, 1] / Xc[:, 2] + K["cy"]
        if x.min() < 0 or y.min() < 0 or x.max() > K["W"] or y.max() > K["H"]: continue
        hoch = np.degrees(np.arctan2(X[:, 2].mean() - C[2], max(wC, 0.1)))
        if hoch > 55: continue
        kand.append((float(x.max() - x.min()), nm, C))
    kand.sort(key=lambda k: -k[0]); gew = []
    for b, nm, C in kand:
        if b < 250: break
        if any(np.linalg.norm(C - C2) < mindestabstand for _, _, C2 in gew): continue
        gew.append((b, nm, C))
        if len(gew) >= max_fotos: break
    return [nm for _, nm, _ in gew]


def kasten_oder_ersatz(g):
    """Seitliche Grenzen (u0, u1) des Vorbaus, an denen das Vordach haengt. 24.11.2026 (Nutzer: 'wir hatten schon mal einen viel besseren Stand' = Handstand schwab_v3
    mit geneigtem, geschweiftem Vordach; Kette 1122w-zc: vordach_profil.json 'fassaden: []'): messen() verlangte kanten_mass.kasten - bei duennen Vorbau-Kanten
    (ebenen_masse: keine zwei 'vollen' Linien) gab es keinen Kasten, das Profil wurde NIE gemessen und der Generator baute eine ebene Platte bzw. Hoehenfeld-Stufen.
    Ersatz (Guard): die Galerie-Breite aus dem Ebenen-Sweep (vorbauten_bauplan.galerie_messen, ebenfalls aus den Fotos) - die Grenzen sind nur Startwerte,
    Ueberstand/Grate/Profil misst die Foto-Silhouette. Ohne Galerie-Band mit Vordach: None (kein Vordach, wie bisher)."""
    Kb = (g.get("kanten_mass") or {}).get("kasten")
    if Kb: return dict(Kb, quelle="kanten_mass.kasten (Fotokanten)")
    G = g.get("galerie") or {}
    if not G.get("vordach") or G.get("u0") is None or G.get("u1") is None: return None
    u0, u1 = float(G["u0"]), float(G["u1"])
    if not (np.isfinite(u0) and np.isfinite(u1)) or u1 - u0 < 1.0: return None          # degeneriert: kein Ersatz
    return dict(u0=u0, u1=u1, breite=round(u1 - u0, 3), quelle="Ersatz: Galerie-Band des Ebenen-Sweeps (kein Kanten-Kasten)")


def messen(F, g, KA, fdir, max_fotos=16, min_fotos=3, log=print):
    """Ein Vordach (Gruppe g der Fassade F aus vorbauten_auto.json mit kanten_mass.kasten und galerie.vordach) messen. dict oder None."""
    KM = g.get("kanten_mass") or {}; G = g.get("galerie") or {}; V = G.get("vordach"); Kb = kasten_oder_ersatz(g)
    if not (V and Kb): return None
    o = np.array(F["o"], float); d = np.array(F["d"], float); n = np.array(F["n"], float)
    # 22.11.2026 (Schwabentor-1122: Wand im Kamerarahmen geneigt, fassade_tiefe 'wand_ebene'): gemessen wird im Kamerarahmen an der OERTLICHEN Wand (Versatz kipp_),
    # ausgegeben im Baurahmen (w_wand der Fassade) - sonst saesse das Vordach um Neigung x Hoehe versetzt.
    NE_ = F.get("wand_ebene"); kipp_ = float(NE_["b_u"] * (0.5 * (Kb["u0"] + Kb["u1"]) - NE_["u_ref"]) + NE_["c_z"] * (float(V["z_traufe"]) - NE_["z_ref"])) if NE_ else 0.0
    ww = float(F.get("w_wand", 0.0)) + kipp_
    welt = lambda P: np.stack([o[0] + P[:, 0] * d[0] + P[:, 2] * n[0], o[1] + P[:, 0] * d[1] + P[:, 2] * n[1], P[:, 1]], 1)
    aussen = lambda C: float((C[:2] - o) @ n)
    wf = ww + float(KM.get("ausladung", g["koerper"]["w_median"])); z_t, z_a = float(V["z_traufe"]), float(V["z_anschluss"])
    box = np.array([[u, z, w] for u in (Kb["u0"] - 1.0, Kb["u1"] + 1.0) for z in (z_t - 0.6, z_a + 0.8) for w in (ww, wf + 1.0)])
    nm_ = fotos_waehlen(KA, welt, box, aussen, wf + 3.0, max_fotos, fdir)
    FO = [f_ for f_ in (Foto(nm, KA[nm], os.path.join(fdir, nm), welt, box) for nm in nm_) if f_.ok]
    log(f"  Fotos gewaehlt {len(nm_)}, mit Kanten {len(FO)}: {', '.join(f_.name[-20:] for f_ in FO)}")
    if len(FO) < min_fotos: return dict(belegt=False, grund=f"nur {len(FO)} Fotos", fotos=[f_.name for f_ in FO])
    # Koordinatenabstieg ueber alle Groessen (Startwerte = Sweep/Kanten: Traufe, Anschluss, Front); Guete = Summe Silhouettenkontrast ueber alle Fotos
    # 22.11.2026: Traufe bis 1,5 m vor die Galeriefront / 1,2 m seitlich (vorher 0,8 m: Schranke knapp ueber dem Befund), Traufhoehe +-0,6 m um das Sweep-Band
    B = dict(w_t=np.round(np.arange(wf, wf + 1.51, 0.05), 3), z_t=np.round(np.arange(z_t - 0.6, z_t + 0.61, 0.05), 3), s=np.round(np.arange(0.0, 1.21, 0.05), 3),
             z_a=np.round(np.arange(z_a - 0.4, z_a + 0.61, 0.05), 3), c=C_GITTER, k=np.round(np.arange(-0.5, min(2.5, 0.45 * (Kb["u1"] - Kb["u0"])) + 1e-6, 0.125), 3))
    # 22.11.2026: gesucht wird k = Gratkopf-Einrueckung gegen die Kastenkante (As = k + s) statt As: so verschiebt der seitliche Ueberstand s nur den Gratfuss
    # (Traufecke), der im Foto gut sichtbare Gratkopf an der Wand bleibt stehen. Mit As als Groesse hingen s und As fest aneinander (Nebenoptimum seitlich 0,20 statt 0,35).
    q = dict(w_t=wf + 0.25, z_t=z_t, s=0.15, z_a=z_a, c=0.0, k=0.45)
    def hyp(q_): return dict(u0=Kb["u0"] - q_["s"], u1=Kb["u1"] + q_["s"], w_a=ww, w_t=q_["w_t"], z_t=q_["z_t"], z_a=q_["z_a"], c=q_["c"], As=q_["k"] + q_["s"])
    RING = [4]
    def ges(q_): return -9.0 if q_["k"] + q_["s"] < 0 else float(np.mean([f_.guete(hyp(q_), ring=RING[0]) for f_ in FO]))
    # 22.11.2026 STARTSUCHE statt fester Startwerte: grobes Gitter ueber Traufausladung, seitlichen Ueberstand, Gratkopf und Krummheit (gekoppelt - Traufecke,
    # Grat und Schweifung zeichnen dieselbe Umrisslinie); Traufhoehe je Ausladung aus der Traufkante allein (schnell, ohne Silhouette). Der Abstieg von festen
    # Startwerten (Traufe 0,25 m vor der Front, c 0) blieb synthetisch bei gerade/seitlich 0,05 haengen, obwohl die wahre Form im Foto besser passte.
    def zt_zu(w_):
        zz = [(float(np.mean([f_.traufe(hyp(dict(q, w_t=w_, z_t=z_))) for f_ in FO])), float(z_)) for z_ in B["z_t"]]; return max(zz)[1]
    kand = []; RING[0] = 10
    for w_ in B["w_t"][::6]:
        z_ = zt_zu(float(w_))
        for s_ in B["s"][::4]:
            for k_ in B["k"][::4]:
                for c_ in C_GITTER[3::3]:
                    q2 = dict(q, w_t=float(w_), z_t=z_, s=float(s_), k=float(k_), c=float(c_)); kand.append((ges(q2), q2))
    kand.sort(key=lambda e: -e[0]); q = kand[0][1]
    log(f"  Startsuche {len(kand)} Hypothesen: beste Traufe w {q['w_t']:.2f} z {q['z_t']:.2f}, seitlich {q['s']:.2f}, Gratkopf {q['k']:.2f}, c {q['c']:+.1f} (Guete {kand[0][0]:.3f})")
    def abstieg(q, ringe, frei):
        """Koordinatenabstieg ueber die Groessen in 'frei' (+ gekoppelte Paare), je Saumbreite in 'ringe' (grob -> fein). (q, Guete, Runden)"""
        for RING[0] in ringe:
            g_b = ges(q)
            for runde in range(5):
                alt = dict(q)
                for k_ in [k_ for k_ in ("s", "w_t", "z_t", "z_a", "k", "c") if k_ in frei]:
                    for v_ in B[k_]:
                        q2 = dict(q); q2[k_] = float(v_); g2 = ges(q2)
                        if g2 > g_b + 1e-9: g_b, q = g2, q2
                # 22.11.2026: gekoppelte Paare gemeinsam (grob, jeder 2. Gitterwert): Traufhoehe <-> Traufausladung (von unten gesehen fast dieselbe Bildlage),
                # Krummheit <-> Gratkopf, seitlicher Ueberstand <-> Gratkopf. Einzeln blieb der Abstieg im Nebenoptimum haengen (synthetisch: seitlich 0,40 statt 0,10, Traufe 10 cm zu tief).
                for k1, k2 in [pp for pp in (("z_t", "w_t"), ("c", "k"), ("s", "k")) if pp[0] in frei and pp[1] in frei]:
                    for v1 in B[k1][::2]:
                        for v2 in B[k2][::2]:
                            q2 = dict(q); q2[k1] = float(v1); q2[k2] = float(v2); g2 = ges(q2)
                            if g2 > g_b + 1e-9: g_b, q = g2, q2
                if q == alt: break
        return q, g_b, runde
    # 22.11.2026: dann Abstieg grob -> fein: erst breiter Saum (10 px, glattes Guetegebirge), dann der scharfe Saum (4 px).
    q, g_b, runde = abstieg(q, (10, 4), ("s", "w_t", "z_t", "z_a", "k", "c"))
    # 22.11.2026 TRAUFENDEN ALS FOTOKANTE: seitlicher Ueberstand = wo die Traufkante (Dachhaut oben hell, Schatten unten dunkel) links/rechts aufhoert
    # (Median ueber alle Fotos je 0,1-m-Abschnitt, Ende = Abfall unter die halbe Hoehe der Kante ueber dem Kasten). Die Silhouette allein sieht die duennen Ecken
    # kaum (Sandstein-Ecklisenen dahinter sind so dunkel wie das Dach) - Schwabentor 1122a: seitlich 0,05 m gemessen, Traufkante endet aber ~0,4 m neben dem Kasten.
    TE = traufenden(FO, hyp, q, Kb)
    log(f"  Traufenden im Foto: links {TE['links']} rechts {TE['rechts']} m neben dem Kasten (Kantenhoehe {TE['hoehe']:.2f})")
    if TE["s"] is not None:
        q = dict(q, s=float(TE["s"])); q, g_b, runde = abstieg(q, (4,), ("w_t", "z_t", "z_a", "k", "c"))
    for c_ in C_GITTER:                                                     # Abschluss: c und Gratkopf gemeinsam (gekoppelt: krummer Grat <-> Ruecksprung)
        for a_ in B["k"]:
            q2 = dict(q, c=float(c_), k=float(a_)); g2 = ges(q2)
            if g2 > g_b + 1e-9: g_b, q = g2, q2
    log(f"  Silhouette (Runde {runde + 1}): Traufe w {q['w_t']:.2f} z {q['z_t']:.2f} (Front {wf:.2f}), seitlich {q['s']:.2f}, Anschluss z {q['z_a']:.2f}, c {q['c']:+.1f}, As {q['k'] + q['s']:.2f}, Kontrast {g_b:.3f}")
    # Familie je Foto: bestes (c, As) bei sonst gemeinsamen Werten
    je = []
    for f_ in FO:
        Sg = np.array([[(f_.guete(hyp(dict(q, c=float(c_), k=float(a_)))) if a_ + q["s"] >= 0 else -9.0) for a_ in B["k"]] for c_ in C_GITTER]); i_, j_ = np.unravel_index(np.argmax(Sg), Sg.shape)
        je.append(dict(foto=f_.name, c=float(C_GITTER[i_]), As=round(float(B["k"][j_] + q["s"]), 3), familie=familie(C_GITTER[i_]), guete=round(float(Sg[i_, j_]), 3),
                       guete_gerade=round(float(Sg[int(np.argmin(np.abs(C_GITTER))), j_]), 3)))
    am_rand = [k_ for k_ in ("s", "w_t", "z_t", "z_a") if q[k_] in (float(B[k_][0]), float(B[k_][-1])) and not (k_ == "s" and q[k_] == 0.0)]
    g_tr = float(np.mean([f_.traufe(hyp(q)) for f_ in FO]))
    log(f"  Traufkante im Foto (Band oben - unten) {g_tr:.3f}, Ueberstand vor der Galeriefront {q['w_t'] - wf:.2f} m, seitlich {q['s']:.2f} m" + (f"; AM SUCHRAND: {', '.join(am_rand)}" if am_rand else ""))
    c_b = q["c"]; fam = familie(c_b); n_fam = sum(1 for e in je if e["familie"] == fam); gerade = ges(dict(q, c=0.0)); belegt = n_fam >= min_fotos
    log(f"  Profil: {fam} ({n_fam}/{len(FO)} Fotos einzeln gleich), Kontrast {g_b:.3f} gegen gerade {gerade:.3f}")
    if not belegt: c_b = 0.0
    w_t, z_t, z_a, As_b, s_ = q["w_t"], q["z_t"], q["z_a"], round(q["k"] + q["s"], 3), q["s"]; u0, u1 = Kb["u0"] - s_, Kb["u1"] + s_; A = w_t - ww
    ww, w_t, wf = ww - kipp_, w_t - kipp_, wf - kipp_      # zurueck in den Baurahmen (A und Hoehen unveraendert)
    t = np.linspace(0, 1, 13); prof = [[round(float(w_t - x * A), 3), round(float(z_t + (z_a - z_t) * g_profil(x, c_b)), 3)] for x in t]
    return dict(id=F.get("id"), u0=round(u0, 3), u1=round(u1, 3), w_wand=ww, w_t=round(float(w_t), 3), z_t=round(z_t, 3), z_a=round(z_a, 3), c=c_b, As=As_b, familie=fam if belegt else "gerade",
                familie_gemessen=fam, fotos_familie=n_fam, fotos=[f_.name for f_ in FO], guete=round(g_b, 3), guete_gerade=round(gerade, 3),
                je_foto=je, profil=prof, belegt=belegt, ueberstand_seitlich=s_, kasten_quelle=Kb.get("quelle"), front=round(wf, 3), ueberstand_front=round(float(w_t - wf), 3), guete_traufe=round(g_tr, 3), am_suchrand=am_rand,
                traufenden=dict(links=TE["links"], rechts=TE["rechts"], hoehe=round(TE["hoehe"], 3), quelle="Traufkante je 0,1 m, Median ueber die Fotos; s = Mittel links/rechts (Vordach symmetrisch gebaut)"), sweep=dict(z_traufe=float(V["z_traufe"]), z_anschluss=float(V["z_anschluss"])),
                annahme=("" if belegt else f"Familie nicht von >= {min_fotos} Fotos belegt -> gerade; ") + "Seitenflaechen mit demselben Profil wie die Front (auf As skaliert); Ziegel glatt (Reihen < 0,8 mm im Druck); Eckzier (Spitzen) nicht gebaut"), FO


def kontrollbild(pfad, erg, FO, n=5):
    import cv2
    teile = []
    for f_ in FO[:n]:
        b = cv2.cvtColor(f_.bild.astype(np.uint8), cv2.COLOR_GRAY2BGR)
        for fa, c, col in (("gerade", 0.0, (255, 160, 0)), ("mess", erg["c"], (0, 0, 255))):
            for k in walm_kurven(erg["u0"], erg["u1"], erg["w_wand"], erg["w_t"], erg["z_t"], erg["z_a"], c, erg["As"]) + traufe_kurven(erg["u0"], erg["u1"], erg["w_t"], erg["z_t"]):
                if len(k): x, y = f_.px(k); cv2.polylines(b, [np.stack([x, y], 1).astype(np.int32)], False, col, 1)
        cv2.putText(b, f_.name[-22:], (4, 16), 0, 0.45, (255, 0, 255), 1); h = 420; teile.append(cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h)))
    if teile: cv2.imwrite(pfad, np.hstack(teile))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("kanten"); ap.add_argument("--fotos"); ap.add_argument("--aus")
    ap.add_argument("--max_fotos", type=int, default=16); ap.add_argument("--min_fotos", type=int, default=3); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); vj = os.path.join(od, "audit", "vorbauten_auto.json")
    if not os.path.exists(vj): print("keine audit/vorbauten_auto.json"); return 3
    KA = json.load(open(os.path.join(a.kanten, "kam.json"))); fdir = a.fotos or next((q_ for q_ in (os.path.join(a.kanten, "zusatz", "bilder"), os.path.join(os.path.dirname(os.path.abspath(a.kanten)), "fotos")) if os.path.isdir(q_)), "")      # 28.11.2026: Zusatzfotos (gesamtkette.kanten_mit_zusatz)
    aus = a.aus or os.path.join(od, "audit", "vordach_profil.json"); E = []
    for F in json.load(open(vj)).get("fassaden", []):
        for gi, g in enumerate(F.get("gruppen", [])):
            print(f"Fassade {F.get('id')} Gruppe {gi}:"); r = messen(F, g, KA, fdir, a.max_fotos, a.min_fotos)
            if r is None: print("  kein Vordach (galerie.vordach oder Kasten/Galerie-Breite fehlen)"); continue
            if isinstance(r, dict): E.append(dict(id=F.get("id"), gruppe=gi, **r)); continue
            erg, FO = r; erg["gruppe"] = gi; E.append(erg); kontrollbild(aus[:-5] + ".jpg", erg, FO)
    json.dump(dict(quelle="tools/vordach_profil.py (Grate/Traufe aus Fotokanten, SfM-Kameras kanten/kam.json)", fassaden=E), open(aus, "w"), indent=1)
    print("->", aus); return 0 if any(e.get("profil") for e in E) else 3


if __name__ == "__main__":
    sys.exit(main())
