#!/usr/bin/env python3
"""lage_proben.py - UNABHAENGIGE Massstabs-/Lageproben als ENTSCHEIDER zwischen den LoD2-Loesungen der Ausrichtung (nicht mitteln; jede Probe sagt
'besteht' / 'faellt' / 'kein Urteil' mit Zahl und Grund).

WARUM (22.11.2026, schwabentor-1122): das Nah-GPS einer Sitzung ist systematisch verzerrt (tools/gps_unsicherheit.py) und legt Drehung/Massstab nur auf ~+-11 Grad /
+-20 % fest; der LoD2-Feinfit gegen den fast quadratischen Turm allein entscheidet das nicht (Lage 1122g: x0,80 zu klein, -9,3 Grad gedreht, Grundriss-Tor rot).
Belegt (Voragent, Kopien): Turmoberkante p99,9 1122g 37,4 m gegen DOM1 50,8 m (1120: 48,6 m); Handy-Kamerahoehe ueber dem Wolkenboden 1,28 m (1122g) gegen 1,55 m (1120);
freier LoD2-Wandfit MIT Nachbarn findet die 1120-Lage (-9,8 Grad, x1,19; 54 % Wandpunkte < 0,3 m statt 24,5 %).
PROBEN (alle auf einer Kandidatenlage im Modellrahmen von objekt.json, Meter, z = Hoehe ueber rahmen.gelaende):
  a) OBERKANTE: Hoehe der Wolke ueber dem Zielgrundriss (p99,9 ueber dem Wolkenboden ringsum) gegen DOM1-Hoehe des Zielgebaeudes (DOM1-Maximum im Grundriss ueber dem
     DGM1 ringsum). Nur urteilsfaehig, wenn die Fotos die Oberkante SEHEN: massstabsfrei an der Verjuengung gemessen (Breite der Wolke im obersten Band / Breite auf halber
     Hoehe muss wie im DOM1 schliessen). Zu hoch faellt immer; im Band besteht; zu niedrig ohne gesehenes Dach = kein Urteil (Wolke 1122d reichte nur bis 19-23 m).
  b) KAMERAHOEHE: Handfotos ueber dem EIGENEN Wolkenboden unter der Kamera (versatzfrei, nur Massstab); Median im Bereich KAMERAHOEHE_BEREICH.
  c) WANDFIT MIT NACHBARN: Wandband der Wolke gegen die LoD2-Grundrisskanten ALLER Gebaeude im Umkreis, die die Kameras wirklich sehen (vorn, im Bildwinkel, nahe genug,
     keine Brandwand); 2D-Suche Drehung x Massstab x Versatz (FFT) in einem Kasten um eine Bezugslage, Guete = Naehe x Abdeckung der gesehenen Kanten. Ein Kandidat besteht,
     wenn er beim Bestwert liegt (Toleranz); faellt, wenn der Bestwert eindeutig woanders liegt; kein Urteil bei Kastenrand oder zweitem Gipfel > EINDEUTIG_MAX.
  d) Grundriss-Tor A + Wanddicke-Tor bleiben die ABNAHME in tools/gesamtkette.py (tore), nicht hier.
ENTSCHEIDUNG (entscheiden): gewaehlt wird eine Lage, die ALLE urteilsfaehigen Proben besteht und mindestens eine besteht; bestehen keine oder mehrere unvereinbare
(> Toleranz voneinander) -> benannte Ursache, keine Lage. Ohne jedes Urteil -> 'kein Urteil' (nur GPS reicht nicht). MONOTON mit alt: die bisherige Wahl bleibt, solange
keine Probe sie verwirft ('bestaetigt'/'kein Urteil') - nur widerlegte Lagen werden ersetzt.
Verwendet von tools/sfm_lod2_ausrichten.py. Test: tools/test_lage_proben.py. Nur numpy/scipy (+ dom1_kachel, wolke_grundriss_pruefen fuer LoD2-Grundrisse)."""
import math
import numpy as np

# ---------- ANNAHMEN (je Zeile begruendet)
OBERKANTE_TOL_UNTEN = 0.12   # ANNAHME: duenne Spitzen/Laternen rekonstruiert die Wolke kaum; 1120 (gute Lage) 48,6/50,8 = 0,957
OBERKANTE_TOL_OBEN = 0.08    # ANNAHME: hoeher als DOM1 kann die Wolke nur mit Ausreissern sein (p99,9 robust), 1-m-Raster verpasst Spitzen
OBERKANTE_BAND = 0.03        # oberstes Band (Anteil der Hoehe) fuer die Verjuengung
DACH_SCHLIESST_MAX = 0.6     # ANNAHME: DOM1 oben / Mitte darunter = das Dach schliesst sichtbar (Turm, Giebel); sonst Flachdach -> zu niedrig = kein Urteil
DACH_GESEHEN_ZUSCHLAG = 0.25 # Wolke darf hoechstens so viel breiter schliessen als DOM1, um als 'Oberkante gesehen' zu gelten
KAMERAHOEHE_BEREICH = (1.35, 1.85)  # ANNAHME: Median der Handkamera ueber Boden. Augenhoehe stehender Erwachsener ~1,41 m (Frauen P5) .. ~1,76 m (Maenner P95)
                             # (Koerpermasse nach DIN 33402-2, Groessenordnung), Handy beim Fotografieren auf Augenhoehe oder bis ~10 cm darunter, +10 cm Reserve
                             # nach oben (Schuhe). Gemessen: 1120 1,55 m (gute Lage), 1122g 1,28 m (x0,80 zu klein).
KAMERAHOEHE_MIN_N = 20       # so viele Kameras mit Wolkenboden unter sich, sonst kein Urteil
KAMERA_BODEN_R = 1.5         # m, Umkreis fuer den Boden unter der Kamera
WAND_BAND = (1.0, 12.0)      # ANNAHME wie seiten_lod2_je_teil.Z_BAND: Wandband ueber DGM1 (Sockel/Fahrzeuge darunter, Erker/Daecher darueber)
SICHT_MAX_M = 40.0           # ANNAHME: weiter entfernte Fassaden traegt die Wolke kaum (Handyfotos in Gassen)
SICHT_MIN_KAMERAS = 2
ZELLE_GROB, ZELLE_FEIN = 0.2, 0.1
SIGMA_NAHE = 0.35            # wie seiten_lod2_je_teil
DREH_GROB, MASS_GROB = 1.0, 0.015
EINDEUTIG_MAX = 0.85         # wie sfm_lod2_ausrichten 'mehrdeutig'
TOL_DREH, TOL_MASS, TOL_M = 2.0, 0.035, 1.0   # ANNAHME: Kandidat 'beim Bestwert' (2 Grobschritte Drehung, ~2 Massstabsschritte, 1 m) - die 3D-Feinloesung darf so weit
                             # vom 2D-Bestwert liegen; enger als die Unterschiede der bisherigen Fehllagen (9-22 Grad, 10-25 %)
ANDERS_GRAD, ANDERS_MASS, ANDERS_M = 3.0, 0.05, 1.5
GIPFEL_MAX = 60
N_PUNKTE = 60000


# ---------- Rahmen / amtliche Daten
def _rahmen(obj):
    r = obj["rahmen"]; return np.array(r["mitte_utm"], float), np.array(r["xhat_utm"], float), np.array(r["yhat_utm"], float), float(r["gelaende"])


def utm(obj, xy):
    c0, xh, yh, _ = _rahmen(obj); xy = np.asarray(xy, float); return c0 + xy[:, :1] * xh + xy[:, 1:2] * yh


def raster(obj, xy, art):
    """DOM1/DGM1 (art 'dom1'/'dgm1') an Modell-xy -> Hoehe im Modellrahmen (z = absolut - gelaende), NaN ohne Kachel."""
    import dom1_kachel as DK
    U = utm(obj, xy); return DK.dom1_bilinear(U[:, 0], U[:, 1], art=art) - _rahmen(obj)[3]


def in_polygon(xy, poly):
    """Strahlprobe (vektorisiert): Punkte xy (n x 2) im Polygon (m x 2)?"""
    x, y = np.asarray(xy, float).T; P = np.asarray(poly, float); j = np.roll(np.arange(len(P)), 1); inn = np.zeros(len(x), bool)
    for i in range(len(P)):
        xi, yi, xj, yj = P[i, 0], P[i, 1], P[j[i], 0], P[j[i], 1]
        if yi == yj: continue
        c = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi) + xi); inn ^= c
    return inn


def grundrisse(obj, radius=60.0):
    """LoD2-Grundflaechen im Umkreis: [(id, polygon n x 2)], Modellrahmen."""
    import wolke_grundriss_pruefen as WG
    return [(b["id"], np.asarray(g, float)) for b in WG.grundrisse(obj, radius) for g in b["ground"] if len(g) >= 3]


def _abstand_zum_rand(xy, poly):
    P = np.asarray(poly, float); A = P; B = np.roll(P, -1, 0); e = B - A; L2 = np.maximum((e ** 2).sum(1), 1e-12); d = np.full(len(xy), np.inf)
    for i in range(len(P)):
        t = np.clip(((xy - A[i]) @ e[i]) / L2[i], 0, 1); d = np.minimum(d, np.linalg.norm(xy - (A[i] + t[:, None] * e[i]), axis=1))
    return d


def _ausdehnung(xy, c):
    return float(np.percentile(np.linalg.norm(xy - c, axis=1), 90)) if len(xy) >= 10 else float("nan")


# ---------- a) Oberkante
def probe_oberkante(P, obj, ziel_polys, ring=(1.0, 6.0), dom=None):
    """P = Wolke (Modellrahmen). ziel_polys = Grundflaechen des Zielgebaeudes. dom = (xy, z) zum Testen statt DOM1/DGM1 (dict mit 'dom', 'dgm' Funktionen) oder None."""
    erg = dict(probe="oberkante")
    if not ziel_polys: erg.update(urteil="kein Urteil", grund="kein LoD2-Grundriss des Zielgebaeudes"); return erg
    xy = P[:, :2]; inn = np.zeros(len(P), bool); d = np.full(len(P), np.inf)
    for g in ziel_polys: inn |= in_polygon(xy, g); d = np.minimum(d, _abstand_zum_rand(xy, g))
    aus = (~inn) & (d >= ring[0]) & (d <= ring[1])
    if inn.sum() < 500 or aus.sum() < 200: erg.update(urteil="kein Urteil", grund=f"zu wenig Wolke im Grundriss ({int(inn.sum())}) / ringsum ({int(aus.sum())})"); return erg
    boden_w = float(np.percentile(P[aus, 2], 2)); top_w = float(np.percentile(P[inn, 2], 99.9)); h_w = top_w - boden_w
    # amtlich: Raster 0,5 m im Grundriss (DOM1) und im Ring (DGM1)
    lo = np.min([g.min(0) for g in ziel_polys], 0) - ring[1]; hi = np.max([g.max(0) for g in ziel_polys], 0) + ring[1]
    gx, gy = np.meshgrid(np.arange(lo[0], hi[0], 0.5), np.arange(lo[1], hi[1], 0.5)); G = np.c_[gx.ravel(), gy.ravel()]
    gi = np.zeros(len(G), bool); gd = np.full(len(G), np.inf)
    for g in ziel_polys: gi |= in_polygon(G, g); gd = np.minimum(gd, _abstand_zum_rand(G, g))
    ga = (~gi) & (gd >= ring[0]) & (gd <= ring[1])
    fd = (dom or {}).get("dom") or (lambda q: raster(obj, q, "dom1")); fg = (dom or {}).get("dgm") or (lambda q: raster(obj, q, "dgm1"))
    zd = fd(G[gi]); zg = fg(G[ga])
    if not np.isfinite(zd).any() or not np.isfinite(zg).any(): erg.update(urteil="kein Urteil", grund="DOM1/DGM1-Kachel fehlt"); return erg
    boden_a = float(np.nanmedian(zg)); h_a = float(np.nanmax(zd)) - boden_a
    if h_a < 3: erg.update(urteil="kein Urteil", grund=f"DOM1-Hoehe {h_a:.1f} m zu klein fuer eine Massstabsprobe"); return erg
    q = h_w / h_a
    # Verjuengung (massstabsfrei): Breite oben / Breite auf halber Hoehe, Wolke und DOM1
    c = np.mean([g.mean(0) for g in ziel_polys], 0); zw = P[inn, 2] - boden_w
    vj_w = _ausdehnung(xy[inn][zw >= (1 - OBERKANTE_BAND) * h_w], c) / max(_ausdehnung(xy[inn][(zw > 0.4 * h_w) & (zw < 0.6 * h_w)], c), 1e-9)
    zdr = zd - boden_a; Gi = G[gi]
    vj_a = _ausdehnung(Gi[zdr >= (1 - OBERKANTE_BAND) * h_a], c) / max(_ausdehnung(Gi[zdr >= 0.5 * h_a], c), 1e-9)
    if not np.isfinite(vj_a): vj_a = 0.0                                                        # nur eine Rasterzelle ganz oben = Spitze
    dach_schliesst = vj_a <= DACH_SCHLIESST_MAX; gesehen = dach_schliesst and np.isfinite(vj_w) and vj_w <= vj_a + DACH_GESEHEN_ZUSCHLAG
    erg.update(wert=round(q, 3), hoehe_wolke_m=round(h_w, 2), hoehe_dom1_m=round(h_a, 2), verjuengung_wolke=round(float(vj_w), 3), verjuengung_dom1=round(float(vj_a), 3),
               oberkante_gesehen=bool(gesehen), grenzen=[1 - OBERKANTE_TOL_UNTEN, 1 + OBERKANTE_TOL_OBEN])
    if q > 1 + OBERKANTE_TOL_OBEN: erg.update(urteil="faellt", grund=f"Wolke {h_w:.1f} m hoeher als DOM1 {h_a:.1f} m (x{q:.2f}) - Modell zu gross")
    elif q >= 1 - OBERKANTE_TOL_UNTEN: erg.update(urteil="besteht", grund=f"Wolke {h_w:.1f} m / DOM1 {h_a:.1f} m = {q:.2f}")
    elif gesehen: erg.update(urteil="faellt", grund=f"Wolke {h_w:.1f} m statt DOM1 {h_a:.1f} m (x{q:.2f}), obwohl die Fotos die Oberkante sehen (Verjuengung {vj_w:.2f} wie DOM1 {vj_a:.2f}) - Modell zu klein")
    else: erg.update(urteil="kein Urteil", grund=f"Wolke {h_w:.1f} m < DOM1 {h_a:.1f} m, aber Oberkante nicht gesehen (Verjuengung Wolke {vj_w:.2f}, DOM1 {vj_a:.2f}) - Wolke endet vielleicht nur")
    return erg


# ---------- b) Kamerahoehe
def probe_kamerahoehe(P, C, r=KAMERA_BODEN_R):
    """P = Wolke, C = Kamerazentren (Modellrahmen). Boden je Kamera = 10-%-Hoehe der Wolkenpunkte im Umkreis r UNTER der Kamera."""
    from scipy.spatial import cKDTree
    # 22.11.2026 (1122j) SCHWACH: der Bereich 1,35-1,85 m laesst -13..+19 % Massstab zu und ist drehblind - im Lauf 1122j bestanden 4 von 5 FALSCHEN Loesungen
    # (1,54-1,67 m) die Kamerahoehe. Sie darf darum nur VERWERFEN, nie allein eine Lage bestaetigen (bestanden(): 'besteht' braucht eine starke Probe).
    erg = dict(probe="kamerahoehe", schwach=True); baum = cKDTree(P[:, :2]); h = []
    for c in np.asarray(C, float):
        ix = baum.query_ball_point(c[:2], r)
        if len(ix) < 10: continue
        z = P[ix, 2]; z = z[z < c[2]]
        if len(z) >= 10: h.append(c[2] - float(np.percentile(z, 10)))
    h = np.asarray(h)
    if len(h) < KAMERAHOEHE_MIN_N: erg.update(urteil="kein Urteil", grund=f"nur {len(h)} Kameras mit Wolkenboden darunter (noetig {KAMERAHOEHE_MIN_N})", n=len(h)); return erg
    m0 = float(np.median(h)); hand = h[(h > 0.25 * m0) & (h < 2.0 * m0)]                         # Drohne/Fenster/Turmblick (massstabsfreie Auswahl um den Median)
    if len(hand) < KAMERAHOEHE_MIN_N: erg.update(urteil="kein Urteil", grund=f"nur {len(hand)} Handkameras", n=len(hand)); return erg
    m = float(np.median(hand)); lo, hi = KAMERAHOEHE_BEREICH
    erg.update(wert=round(m, 3), n=int(len(hand)), p25_p75=np.round(np.percentile(hand, [25, 75]), 2).tolist(), grenzen=[lo, hi])
    if lo <= m <= hi: erg.update(urteil="besteht", grund=f"Handkameras {m:.2f} m ueber dem Wolkenboden ({len(hand)} Kameras)")
    else: erg.update(urteil="faellt", grund=f"Handkameras {m:.2f} m ueber dem Wolkenboden (Bereich {lo}-{hi} m, ANNAHME) - Massstab x{1.55 / m:.2f} daneben")
    return erg


# ---------- c) Wandfit mit Nachbarn
def wand_gesehen(S, N, C, V, halb_fov_grad, max_m=SICHT_MAX_M, min_kameras=SICHT_MIN_KAMERAS, block=2048):
    """DIE Sichtbarkeit einer Wandprobe (22.11.2026, eine Funktion fuer lage_proben.gesehene_kanten UND die Objektwand-Abdeckung der Ausrichtung):
    S = Wandproben (m x 2, waagerecht), N = Aussennormalen (m x 2), C = Kamerazentren (n x >=2), V = Blickrichtungen (n x >=2, waagerechter Anteil zaehlt),
    halb_fov_grad = halber waagerechter Bildwinkel je Kamera. Gesehen = mindestens min_kameras Kameras stehen VOR der Wand (Normale), <= max_m entfernt und haben
    die Probe im waagerechten Bildwinkel. -> bool (m).
    WARUM (Lage-Pruefstand 22.11.): die Abdeckung der Ausrichtung nahm 'zur Kamera gewandt' als Blick vom KAMERASCHWERPUNKT - stehen die Kameras rundum (vereinte
    Seiten, Tor mit Durchgang), liegt der Schwerpunkt IM Gebaeude, keine Wand zeigt zu ihm -> Abdeckung 0 % fuer jede Loesung. Je Kamera ist das richtig.
    ANNAHME wie gesehene_kanten: keine Verdeckungsrechnung."""
    S = np.asarray(S, float)[:, :2]; N = np.asarray(N, float)[:, :2]; N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    C = np.asarray(C, float)[:, :2]; V = np.asarray(V, float)[:, :2]; V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
    cf = np.cos(np.radians(np.broadcast_to(np.asarray(halb_fov_grad, float), (len(C),)))); out = np.zeros(len(S), bool)
    for a in range(0, len(S), block):
        D = C[None, :, :] - S[a:a + block, None, :]; dist = np.linalg.norm(D, axis=2); vorn = (D * N[a:a + block, None, :]).sum(2) > 0
        blick = (-(D / np.maximum(dist[..., None], 1e-9)) * V[None]).sum(2) >= cf[None]
        out[a:a + block] = ((dist <= max_m) & vorn & blick).sum(1) >= min_kameras
    return out


def gesehene_kanten(polys, C, V, halb_fov_grad, max_m=SICHT_MAX_M, schritt=0.5):
    """Grundrisskanten (alle Gebaeude), die die Kameras sehen: Kantenprobe vor der Wand (Aussennormale), Kamera <= max_m, im waagerechten Bildwinkel, nicht in einem
    anderen Grundriss (Brandwand). V = Blickrichtungen (n x 3), halb_fov_grad = halber waagerechter Bildwinkel je Kamera. -> Liste 2-Punkt-Segmente (je 2 x 2).
    ANNAHME: keine Verdeckungsrechnung (eine Fassade hinter einem Haus gilt als gesehen) - betrifft alle Kandidaten gleich."""
    C = np.asarray(C, float)[:, :2]; V = np.asarray(V, float)[:, :2]; V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9); cf = np.cos(np.radians(np.asarray(halb_fov_grad, float)))
    seg = []
    alle = [g for _, g in polys]
    for k, g in enumerate(alle):
        A = 0.5 * np.sum(g[:, 0] * np.roll(g[:, 1], -1) - np.roll(g[:, 0], -1) * g[:, 1]); vz = 1.0 if A > 0 else -1.0      # gegen den Uhrzeigersinn: Aussennormale (dy, -dx)
        for p0, p1 in zip(g, np.roll(g, -1, 0)):
            L = float(np.linalg.norm(p1 - p0))
            if L < 0.3: continue
            e = (p1 - p0) / L; n = vz * np.array([e[1], -e[0]]); m = max(2, int(L / schritt)); S = p0 + (np.arange(m) + 0.5)[:, None] / m * (p1 - p0)
            probe = S + 0.3 * n; brand = np.zeros(m, bool)
            for j, h in enumerate(alle):
                if j != k and np.all(h.min(0) - 1 <= probe.max(0)) and np.all(h.max(0) + 1 >= probe.min(0)): brand |= in_polygon(probe, h)
            ok = wand_gesehen(S, np.broadcast_to(n, S.shape), C, V, halb_fov_grad, max_m) & ~brand
            if ok.mean() >= 0.5: seg.append(np.array([p0, p1]))
    return seg


def _kanten_raster(seg, lo, n, zelle):
    W = np.zeros((n, n), bool)
    for p0, p1 in seg:
        m = int(np.linalg.norm(p1 - p0) / (zelle / 3)) + 2; L = p0 + np.linspace(0, 1, m)[:, None] * (p1 - p0); ij = np.floor((L - lo) / zelle).astype(int)
        ok = (ij >= 0).all(1) & (ij < n).all(1); W[ij[ok, 1], ij[ok, 0]] = True
    return W


def _wandproben(seg, d=0.2):
    return np.vstack([p0 + np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / d)))[:, None] * (p1 - p0) for p0, p1 in seg])


def wandfit_suche(xy, c, seg, kasten, zelle=ZELLE_GROB, dreh_schritt=DREH_GROB, mass_schritt=MASS_GROB, mitte=(0.0, 1.0, 0.0, 0.0)):
    """2D-Suche: q = Rz(d) (xy - c) / m + c + tau; mitte = (d0, m0, tx0, ty0): d in d0 +- kasten dreh_grad, log m in log m0 +- log(1 +- mass_rel), tau in (tx0, ty0) +- versatz_m.
    Guete = Naehe-Korrelation x Abdeckung der gesehenen Kanten. -> dict(best{dreh_grad, massstab, versatz, guete, naehe, abdeckung}, zweit{...}, verhaeltnis, rand[])."""
    from scipy.ndimage import distance_transform_edt, maximum_filter
    from scipy.spatial import cKDTree
    xy = np.asarray(xy, float); c = np.asarray(c, float)[:2]; d0, m0, tx0, ty0 = mitte[0], mitte[1], mitte[2], mitte[3]; v = kasten["versatz_m"]
    pk = np.vstack([s for s in seg]); lo = np.minimum(pk.min(0), c - 1) - v - 3.0; hi = np.maximum(pk.max(0), c + 1) + v + 3.0
    n = int(math.ceil(max(hi - lo) / zelle)); n += n % 2
    W = _kanten_raster(seg, lo, n, zelle); D = distance_transform_edt(~W) * zelle; FN = np.fft.rfft2(np.exp(-0.5 * (D / SIGMA_NAHE) ** 2))
    dreh = d0 + np.arange(-kasten["dreh_grad"], kasten["dreh_grad"] + 1e-9, dreh_schritt)
    lm = math.log(m0) + np.arange(math.log(1 - kasten["mass_rel"]), math.log(1 + kasten["mass_rel"]) + 1e-12, mass_schritt)
    k = int(math.floor(v / zelle)); sh = np.arange(-k, k + 1); kx0, ky0 = int(round(tx0 / zelle)), int(round(ty0 / zelle))
    karten = np.zeros((len(dreh), len(lm), len(sh), len(sh)), np.float32)
    for i, dd in enumerate(dreh):
        a = math.radians(dd); R2 = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        for j, l in enumerate(lm):
            q = (xy - c) @ R2.T / math.exp(l) + c; ij = np.floor((q - lo) / zelle).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
            H = np.bincount(ij[ok, 1] * n + ij[ok, 0], minlength=n * n).reshape(n, n).astype(float)
            K = np.fft.irfft2(FN * np.conj(np.fft.rfft2(H)), s=(n, n))                              # K[dy, dx] = sum H(p) N(p + d)
            karten[i, j] = K[np.ix_((sh + ky0) % n, (sh + kx0) % n)] / max(len(xy), 1)
    gip = karten >= maximum_filter(karten, size=(3, 3, 5, 5), mode="nearest")
    kand = np.argwhere(gip & (karten > 0)); kand = kand[np.argsort(-karten[tuple(kand.T)])][:GIPFEL_MAX]
    wand = _wandproben(seg); L_ = []
    for ix in kand:
        dd, l_, ty, tx = dreh[ix[0]], lm[ix[1]], (sh[ix[2]] + ky0) * zelle, (sh[ix[3]] + kx0) * zelle; a = math.radians(dd)
        q = (xy - c) @ np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]).T / math.exp(l_) + c + [tx, ty]
        ab = float((cKDTree(q).query(wand, distance_upper_bound=2 * SIGMA_NAHE)[0] < 2 * SIGMA_NAHE).mean())
        L_.append(dict(guete=float(karten[tuple(ix)]) * ab, naehe=float(karten[tuple(ix)]), abdeckung=ab, dreh_grad=float(dd), massstab=float(math.exp(l_)), versatz=[float(tx), float(ty)], ix=ix.tolist()))
    L_.sort(key=lambda r: -r["guete"])
    if not L_: return dict(best=None, zweit=None, verhaeltnis=1.0, rand=["keine Loesung"])
    b = L_[0]
    anders = [r for r in L_[1:] if abs(r["dreh_grad"] - b["dreh_grad"]) > ANDERS_GRAD or abs(math.log(r["massstab"] / b["massstab"])) > ANDERS_MASS
              or math.hypot(r["versatz"][0] - b["versatz"][0], r["versatz"][1] - b["versatz"][1]) > ANDERS_M]
    rand = []
    if b["ix"][0] in (0, len(dreh) - 1): rand.append("Drehung")
    if b["ix"][1] in (0, len(lm) - 1): rand.append("Massstab")
    if b["ix"][2] in (0, len(sh) - 1) or b["ix"][3] in (0, len(sh) - 1): rand.append("Versatz")
    return dict(best=b, zweit=(anders[0] if anders else None), verhaeltnis=(anders[0]["guete"] / b["guete"] if anders and b["guete"] > 0 else 0.0), rand=rand,
                raster=dict(dreh=len(dreh), massstab=len(lm), versatz=len(sh), zelle_m=zelle), kanten=len(seg))


def relativ_2d(Y_ref, Y_k, c):
    """2D-Aehnlichkeit Y_k ~ Rz(d) (Y_ref - c) / m + c + tau (Konvention von wandfit_suche) -> (d Grad, m, tau)."""
    a = np.asarray(Y_ref, float)[:, :2] - np.asarray(c, float)[:2]; b = np.asarray(Y_k, float)[:, :2] - np.asarray(c, float)[:2]
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb; U, S, Vt = np.linalg.svd(a0.T @ b0); dd = np.sign(np.linalg.det(Vt.T @ U.T)); Dm = np.diag([1, dd]); R = Vt.T @ Dm @ U.T
    s = (S * np.diag(Dm)).sum() / max((a0 ** 2).sum(), 1e-12); tau = mb - s * R @ ma
    return math.degrees(math.atan2(R[1, 0], R[0, 0])), 1.0 / s, tau


def boden_versatz(P, C, obj, r=KAMERA_BODEN_R, boden=None):
    """Hoehenversatz dz, der den Wolkenboden unter den Kameras auf DGM1 legt (Median ueber Kameras von DGM1 - 10-%-Hoehe der Wolke im Umkreis r unter der Kamera).
    22.11.2026 Probe teil0: die GPS-Bezugslage hat nur eine grobe Hoehe (Kameras 1,6 m, ANNAHME) - das Wandband (WAND_BAND ueber DGM1) griff dann Boden/Daecher und der
    Wandfit lief x0,87 zu klein; mit angeglichener Hoehe fand dieselbe Wolke die 1120-Lage (scratchpad gu/ev3.py). None ohne Boden unter >= 10 Kameras."""
    from scipy.spatial import cKDTree
    baum = cKDTree(np.asarray(P)[:, :2]); C = np.asarray(C, float); zg = (boden or (lambda q: raster(obj, q, "dgm1")))(C[:, :2]); d = []
    for c, g in zip(C, zg):
        if not np.isfinite(g): continue
        ix = baum.query_ball_point(c[:2], r)
        if len(ix) < 10: continue
        z = np.asarray(P)[ix, 2]; z = z[z < c[2]]
        if len(z) >= 10: d.append(g - float(np.percentile(z, 10)))
    return float(np.median(d)) if len(d) >= 10 else None


def wandband(P, obj, n=N_PUNKTE, boden=None, rng=None):
    """Wandband-Punkte (xy) der Wolke: WAND_BAND ueber DGM1 (boden(xy) zum Testen)."""
    rng = rng or np.random.default_rng(3); P = np.asarray(P, float)
    if len(P) > 4 * n: P = P[rng.choice(len(P), 4 * n, replace=False)]
    zb = (boden or (lambda q: raster(obj, q, "dgm1")))(P[:, :2]); zb = np.where(np.isfinite(zb), zb, 0.0); h = P[:, 2] - zb
    xy = P[(h > WAND_BAND[0]) & (h < WAND_BAND[1]), :2]
    if len(xy) > n: xy = xy[rng.choice(len(xy), n, replace=False)]
    return xy


def wandfit_bestwert(xy_ref, c, seg, kasten):
    """Grobsuche im Kasten + Feinsuche um den Grobbestwert (Bezugslage = Lage von xy_ref). -> Such-dict (best, fein, zweit, verhaeltnis, rand, kanten) oder None ohne Kanten."""
    if not seg: return None
    S = wandfit_suche(xy_ref, c, seg, kasten)
    if S.get("best") and not S["rand"]:
        b = S["best"]; F = wandfit_suche(xy_ref, c, seg, dict(dreh_grad=1.5, mass_rel=0.025, versatz_m=1.0), zelle=ZELLE_FEIN, dreh_schritt=0.25, mass_schritt=0.005,
                                         mitte=(b["dreh_grad"], b["massstab"], b["versatz"][0], b["versatz"][1]))
        if F.get("best"): S["fein"] = F["best"]
    S["kasten"] = dict(kasten); return S


def wandfit_urteil(S, Y_ref, Y_k, c):
    """Urteil fuer EINEN Kandidaten (Wolke Y_k derselben Punkte wie Y_ref): liegt er beim Bestwert der Wandsuche?"""
    e = dict(probe="wandfit")
    if S is None: e.update(urteil="kein Urteil", grund="keine gesehenen LoD2-Kanten"); return e
    b = S.get("fein") or S.get("best")
    if b is None: e.update(urteil="kein Urteil", grund="keine Loesung der Wandsuche"); return e
    d, m, tau = relativ_2d(Y_ref, Y_k, c); dd = d - b["dreh_grad"]; dm = math.log(m / b["massstab"]); dt = math.hypot(tau[0] - b["versatz"][0], tau[1] - b["versatz"][1])
    e.update(abstand=dict(dreh_grad=round(dd, 2), massstab_rel=round(dm, 4), versatz_m=round(dt, 2)), bestwert=dict(guete=round(b["guete"], 4), abdeckung=round(b["abdeckung"], 3)),
             verhaeltnis_zweit=round(S["verhaeltnis"], 3), kanten=S.get("kanten"))
    nahe = abs(dd) <= TOL_DREH and abs(dm) <= TOL_MASS and dt <= TOL_M
    if S["rand"]: e.update(urteil="kein Urteil", grund="Bestwert der Wandsuche am Kastenrand (" + ", ".join(S["rand"]) + ")")
    elif nahe: e.update(urteil="besteht", grund=f"beim Wandfit-Bestwert ({dd:+.1f} Grad, {100 * dm:+.1f} %, {dt:.1f} m; Abdeckung {100 * b['abdeckung']:.0f} %)")
    elif S["verhaeltnis"] > EINDEUTIG_MAX: e.update(urteil="kein Urteil", grund=f"Wandfit mehrdeutig (zweiter Gipfel {100 * S['verhaeltnis']:.0f} %)")
    else: e.update(urteil="faellt", grund=f"Wandfit mit Nachbarn liegt woanders ({dd:+.1f} Grad, {100 * dm:+.1f} %, {dt:.1f} m vom Bestwert; zweiter Gipfel {100 * S['verhaeltnis']:.0f} %)")
    return e


def wandfit_lage(S, c):
    """Bestwert der Wandsuche als Abbildung Bezugslage -> Wandfit-Lage: (Rz 3x3, m, tau3): Y_w = Rz (Y_ref - c) / m + c + tau."""
    b = S.get("fein") or S.get("best"); a = math.radians(b["dreh_grad"])
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]]); return Rz, float(b["massstab"]), np.array([b["versatz"][0], b["versatz"][1], 0.0])


def vertraeglich_2d(Y_i, Y_j, c):
    """Zwei Lagen derselben Punkte innerhalb der Toleranz (TOL_DREH, TOL_MASS, TOL_M)?"""
    d, m, tau = relativ_2d(Y_i, Y_j, c); return abs(d) <= TOL_DREH and abs(math.log(m)) <= TOL_MASS and math.hypot(*tau) <= TOL_M


def probe_wandfit_alle(Y_ref, kandidaten_Y, seg, c, kasten, xy_ref=None):
    """EINE Suche um die Bezugslage, dann je Kandidat ein Urteil. -> (suche, [probe-dict je Kandidat])."""
    S = wandfit_bestwert(xy_ref, c, seg, kasten); return S, [wandfit_urteil(S, Y_ref, Yk, c) for Yk in kandidaten_Y]


# ---------- Entscheidung
def bestanden(proben):
    """Ein Kandidat besteht, wenn keine Probe faellt und mindestens eine STARKE Probe besteht (schwach=True, z. B. Kamerahoehe, darf nur verwerfen;
    22.11.2026 1122j). -> 'besteht' / 'faellt' / 'kein Urteil'."""
    u = [p.get("urteil") for p in proben]
    if "faellt" in u: return "faellt"
    return "besteht" if any(p.get("urteil") == "besteht" and not p.get("schwach") for p in proben) else "kein Urteil"


def entscheiden(kand, vertraeglich, alt=None):
    """kand = Liste dict(name, guete, proben[list]); vertraeglich(i, j) -> bool (Lagen i, j innerhalb der Toleranz). -> dict(ergebnis, wahl (Index oder None), grund, je).
    alt = Index der bisherigen Wahl (beste Guete nach dem GPS-Veto) oder None. Mit alt gilt MONOTON (Kaufhaus/andere Objekte duerfen sich nicht aendern): besteht die
    bisherige Wahl alle urteilsfaehigen Proben oder urteilt keine Probe ueber sie, bleibt sie ('bestaetigt' / 'kein Urteil'); erst wenn eine unabhaengige Probe sie
    verwirft, wird unter den bestehenden gewaehlt (keine -> 'keine', unvereinbare -> 'mehrdeutig'). Belegt: Kaufhaus gk2 geschriebene Lage besteht Oberkante (1,01)
    und Kamerahoehe (1,75 m), Wandfit ohne Urteil (scratchpad gu/ev_kh.py, 22.11.)."""
    je = [bestanden(k["proben"]) for k in kand]
    ok = [i for i, u in enumerate(je) if u == "besteht"]
    if not any(p.get("urteil") in ("besteht", "faellt") for k in kand for p in k["proben"]):
        return dict(ergebnis="kein Urteil", wahl=None, je=je, grund="keine Probe urteilsfaehig (nur GPS/LoD2-Guete) - Lage NICHT unabhaengig belegt")
    if alt is not None and je[alt] != "faellt":
        return dict(ergebnis=("bestaetigt" if je[alt] == "besteht" else "kein Urteil"), wahl=(alt if je[alt] == "besteht" else None), je=je,
                    grund=f"bisherige Wahl {kand[alt]['name']} " + ("besteht alle urteilsfaehigen Proben" if je[alt] == "besteht" else "ohne Probenurteil - bleibt (nicht unabhaengig belegt)"))
    if not ok:
        return dict(ergebnis="keine", wahl=None, je=je, grund="keine Loesung besteht alle urteilsfaehigen Proben: " + "; ".join(
            f"{k['name']}: " + ", ".join(f"{p['probe']} {p['urteil']}" for p in k["proben"]) for k in kand[:6]))
    ok.sort(key=lambda i: -kand[i]["guete"])
    fremd = [j for j in ok[1:] if not vertraeglich(ok[0], j)]
    if fremd:
        return dict(ergebnis="mehrdeutig", wahl=None, je=je, grund=f"mehrere unvereinbare Lagen bestehen alle Proben: {kand[ok[0]]['name']} und {kand[fremd[0]]['name']}")
    return dict(ergebnis="belegt", wahl=ok[0], je=je, grund=f"{kand[ok[0]]['name']} besteht alle urteilsfaehigen Proben ({len(ok)} vertraegliche Loesung(en))")


# ---------- Tor-Regeln der Kette (22.11.2026, Lage-Pruefstand: EINE Funktion fuer tools/gesamtkette.py tore() und tools/lage_pruefstand.py)
def tor_rc(transformation):
    """Lageproben-Tor aus SFM-AUSRICHTUNG 'transformation.lage_proben': 0 = belegt/bestaetigt, 3 = keine/mehrdeutig (Lage nicht belegt, nicht modellieren),
    None = kein Urteil (oder keine Lageproben gelaufen). -> (rc, Hinweistext oder None)."""
    lp = (transformation or {}).get("lage_proben")
    if not lp: return None, None
    rc = 0 if lp.get("ergebnis") in ("belegt", "bestaetigt") else 3 if lp.get("ergebnis") in ("keine", "mehrdeutig") else None
    return rc, f"Lageproben: {lp.get('ergebnis')} - {str(lp.get('grund'))[:300]}"


def lage_bestanden(erg):
    """Lage-Urteil der Kette aus den rc der Tore (None = Tor lief nicht / kein Urteil): GPS, Seiten-Blick und Lageproben 0 oder None, Grundriss genau 0."""
    return erg.get("gps") in (0, None) and erg.get("grundriss") == 0 and erg.get("seiten_blick") in (0, None) and erg.get("lage_proben") in (0, None)
