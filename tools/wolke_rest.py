#!/usr/bin/env python3
"""wolke_rest.py - WAS FEHLT DEM MODELL ALS KOERPER? Rest der dichten Wolke, der nicht an der Modellflaeche liegt, als Haufen mit Ort und Grobform (21.11.2026).

Anlass (Nutzer 21.11.: "von null ... der Handstand darf keine Rolle spielen ... vielleicht braucht man die dichte Wolke doch"): die Ebenen-Schleife sieht nur, was an einer
Wandebene liegt. Ganze Koerper (Treppenturm, Laterne, Dachueberstand, Anbau) liegen auf keiner Wandebene -> kein Kandidat. Im Handstand kamen genau diese Koerper aus der
dichten Wolke (Treppenturm = Kreisausgleich der Wolke, Dach = Traufecken) - hier dasselbe ohne Vorwissen:
  1. Modellflaeche abtasten, Wolkenpunkte weiter als --fern (0,35 m) davon = REST.
  2. Restpunkte in drei KLASSEN trennen, BEVOR Haufen gebildet werden (sonst verklebt das Nachbarhaus ueber die Durchfahrt mit dem Bau):
       innen  = vom Modell umschlossen (Flaechenzellen in 4 waagrechten Richtungen oder 3 + oben; s. umschlossen)    -> Form 'hohl' (Durchfahrt/Nische/Loggia fehlt im Modell oder Lagefehler), nur Meldung
       fremd  = ueber einer FREMDEN LoD2-Grundflaeche, nicht ueber der eigenen, nicht hoeher als deren Dach + 1 m -> Form 'nachbar', nie Bauteil-Kandidat
       aussen = alles andere                                                                                  -> Grobform, Bauteil-Kandidat
     Grundflaechen: LoD2 des Objekts (objekt.json lod2.gml/id + rahmen; Modell x/y = (UTM - mitte_utm) . xhat/yhat, z = Hoehe - gelaende) oder --grundflaechen <json> im Modellrahmen.
     Ohne LoD2 UND zusaetzlich fuer Bauten, die LoD2 nicht kennt, die geometrische Ersatzregel (ANNAHME): Haufen reicht bis zum Boden, ist >= 3 m hoch und wird von der Suchgrenze
     --weit abgeschnitten (>= 3 % seiner Punkte im letzten Zellenband) = eigenes Gebaeude/Umgebung, das ueber den betrachteten Raum hinausreicht -> 'nachbar'.
     Abgeschnitten OHNE Bodenkontakt -> 'umgebung' (Leitung, Baum, Streupunkte): nicht vollstaendig gemessen, kein Kandidat.
  3. Je Klasse in --zelle-Wuerfel (0,4 m), zusammenhaengende Haufen; nur Haufen, die das Modell beruehren (naechster Punkt <= --anschluss).
  4. GROBFORM je Aussen-Haufen, jede mit messbarem Kriterium, Restfehler und den Massen fuer einen generischen Koerper (h['mass'], Pruefwerte aller Formen in h['pruef']):
       'rund'   Kreisausgleich im Grundriss, Rest <= 8 cm, r 0,4-4 m, Hoehe >= 1,5 m, Bogen >= 90 Grad belegt            -> Achse + Drehprofil r(z)
       'stab'   schlank und hoch: Hoehe >= 1 m, Dicke <= 0,8 m, Hoehe/Dicke >= 4, Hauptachse <= 20 Grad vom Lot        -> Achse, z0..z1, Radiusprofil
       'ring'   umlaufend auf einer Hoehe: >= 50 % der 24 Sektoren um die Modellmitte belegt, flach (Hoehe <= halbe
                kleinste Grundrissausdehnung), Ausladung je Sektor einheitlich (Streuung <= 0,25 m)                     -> z0..z1, Ausladung, belegte Sektoren
       'band'   wie Ring, aber nur an einer Seite belegt: Laenge >= 2 m und >= 3 x Hoehe und Ausladung (nach 'kasten' geprueft) -> wie Ring + Grundriss-Rechteck des Haufens
       'kasten' Quader an einer Wand: Punkte liegen an den AUSSENFLAECHEN eines wandparallelen Quaders (Median-Abstand
                zur naechsten Flaeche <= 10 cm und <= 6 % der kleinsten Kante), Frontebene belegt und <= 15 Grad zur Wand -> Wandrahmen o/d/n, u0..u1, w0..w1, z0..z1, belegte Flaechen
       'platte' duennste Hauptachse <= 0,25 m (nur Meldung), sonst 'koerper' (unbenannt, nur Meldung).
     Alle Schwellen sind ANNAHMEN (Schwabentor + synthetische Tests), an einem zweiten Bauwerk pruefen.
Kernmethode: die Wolke nennt nur WO und GROB WAS; die Masse kommen danach aus Fotokanten auf den Ebenen dieses Haufens.
Je Haufen und je Kandidat aus audit/koerper_auto.json zusaetzlich 'am_modell': Wolkenpunkte naeher als --nah (0,15 m) an der Modellflaeche im Kasten des Haufens (+ 0,5 m) - Grundlage der Annahmeregel
in tools/koerper_schleife.py (vorher/nachher je Kandidat statt nur der Gesamtzahl).
Aufruf: wolke_rest.py <objekt.json> <wolke.npy> [--stl S] [--bild audit/wolke_rest.jpg] [--uebernehmen] [--grundflaechen G.json]   Ausgabe: audit/wolke_rest.json
"""
import sys, os, json, argparse, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)
BAUBAR = ("rund", "kasten", "ring", "band", "stab")          # dafuer gibt es einen generischen Koerper in tools/bauteile.py (wolkenrest_koerper)
# Schwellen der Grobformen - alle ANNAHMEN (eingestellt am Schwabentor und an synthetischen Koerpern, tools/test_wolke_rest_formen.py)
SW = dict(rund_rest=0.08, rund_bogen=90.0, stab_hoehe=1.0, stab_dicke=0.8, stab_schlank=4.0, stab_steil=0.94, stab_rest=0.08, ring_abdeckung=0.5, ring_flach=0.5, ring_rest=0.25, ring_sektoren=24, band_laenge=2.0, band_schlank=3.0,
          kasten_min=0.4, kasten_rest=0.10, kasten_rel=0.06, kasten_winkel=15.0, kasten_front=0.10, nachbar_hoehe=3.0, nachbar_schnitt=0.03, dach_tol=1.0, eigen_anteil=0.2, rand=0.5)


def kreis(xy):
    A = np.c_[2 * xy, np.ones(len(xy))]; b = (xy ** 2).sum(1); s = np.linalg.lstsq(A, b, rcond=None)[0]; r = float(np.sqrt(max(s[2] + s[0] ** 2 + s[1] ** 2, 0)))
    return float(s[0]), float(s[1]), r, float(np.median(np.abs(np.hypot(xy[:, 0] - s[0], xy[:, 1] - s[1]) - r)))


def in_polygon(xy, poly):
    """Punkt-in-Vieleck (Strahl nach +x, gerade/ungerade), ohne Fremdbibliothek."""
    x = np.asarray(xy[:, 0], float); y = np.asarray(xy[:, 1], float); p = np.asarray(poly, float)[:, :2]; inn = np.zeros(len(x), bool)
    for (x0, y0), (x1, y1) in zip(p, np.roll(p, -1, 0)):
        if y0 != y1: inn ^= ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / (y1 - y0) + x0)
    return inn


def grundflaechen_laden(obj, datei, mitte_xy, radius):
    """Grundflaechen im MODELLRAHMEN: (eigen [Nx2], fremd [(name, Nx2, Dachhoehe)], Quelle) oder (None, None, Grund). Rahmen: x/y = (UTM - mitte_utm) . xhat_utm/yhat_utm, z = Hoehe - gelaende
    (geprueft an schwabentor-1120: LoD2-Grundflaeche PLcp -> x -8,2..3,9 / y 8,9..21,4 = objekt.json rahmen_wand; Modell x -9,9..5,2 / y 7,9..24,7 mit Dachueberstand und Treppenturm)."""
    if datei:
        G = json.load(open(datei)); return [np.array(p, float) for p in G.get("eigen", [])], [(f.get("name", f"fremd{i}"), np.array(f["umriss"], float), float(f.get("hoehe", 1e9))) for i, f in enumerate(G.get("fremd", []))], os.path.basename(datei)
    L, R = obj.get("lod2"), obj.get("rahmen")
    if not isinstance(L, dict) or not isinstance(R, dict) or not os.path.exists(str(L.get("gml", ""))) or not all(k in R for k in ("mitte_utm", "xhat_utm", "yhat_utm")): return None, None, "kein LoD2 (objekt.json lod2.gml / rahmen fehlt)"
    sys.path.insert(0, HIER); import lod2_gebaeude as LG
    m0 = np.array(R["mitte_utm"], float); xh = np.array(R["xhat_utm"], float); yh = np.array(R["yhat_utm"], float); g = R.get("gelaende"); eigen, fremd = [], []
    try: liste = LG.extract(L["gml"], center=tuple(m0 + mitte_xy[0] * xh + mitte_xy[1] * yh), radius=radius)
    except Exception as e: return None, None, f"LoD2 nicht lesbar ({e})"
    for meta, polys in liste:
        gr = [np.c_[(np.asarray(P)[:, :2] - m0) @ xh, (np.asarray(P)[:, :2] - m0) @ yh] for t, P in polys if t == "GroundSurface"]
        if not gr: continue
        if meta.get("id") == L.get("id"): eigen += gr
        else: zd = (max(float(np.asarray(P)[:, 2].max()) for t, P in polys) - float(g)) if g is not None else 1e9; fremd += [(str(meta.get("id")), p, zd) for p in gr]      # ohne Gelaendehoehe keine Dachgrenze (ANNAHME: jede Hoehe)
    return eigen, fremd, f"LoD2 {os.path.basename(L['gml'])} ({len(eigen)} eigene, {len(fremd)} fremde Grundflaechen)"


def umschlossen(S, R, zelle=0.2):
    """Liegt ein Restpunkt IM Modell? Das Druckmodell ist eine hohle Schale mit Fensterloechern - Normalen-Vorzeichen (1. Fassung: Punkte neben einer Kante galten als innen) und
    Flutung von aussen taugen nicht. Regel: Flaechenzellen (0,2 m < fern, die eigene Zelle ist leer) in allen 4 waagrechten Achsrichtungen, oder in 3 davon und darueber
    (Fenster/Tor oeffnen eine Richtung). Punkt vor einer Wand = 1 Richtung, in einer Innenecke unter einem Vorbau = 2 + oben -> nicht innen."""
    lo = S.min(0) - zelle; I = ((S - lo) / zelle).astype(int); G = np.zeros(I.max(0) + 2, bool); G[tuple(I.T)] = True
    def ab(ax, rueck):
        A = np.flip(G, ax) if rueck else G; C = np.maximum.accumulate(A, ax); return np.flip(C, ax) if rueck else C
    J = np.floor((R - lo) / zelle).astype(int); ok = np.all((J >= 0) & (J < np.array(G.shape)), 1); j = tuple(J[ok].T); n = sum(ab(ax, r)[j].astype(int) for ax in (0, 1) for r in (False, True))
    inn = np.zeros(len(R), bool); inn[ok] = (n == 4) | ((n == 3) & ab(2, True)[j]); return inn


def haufen_bilden(R, zelle, min_p):
    """zusammenhaengende Haufen (26er-Nachbarschaft belegter Zellen mit >= 3 Punkten) -> Liste von Indexfeldern."""
    from scipy import ndimage
    if len(R) < min_p: return []
    I = ((R - R.min(0)) / zelle).astype(int); G = np.zeros(I.max(0) + 1, np.int32); np.add.at(G, tuple(I.T), 1); L, n = ndimage.label(G >= 3, structure=np.ones((3, 3, 3))); lab = L[tuple(I.T)]
    anz = np.bincount(lab, minlength=n + 1); return [np.flatnonzero(lab == k) for k in range(1, n + 1) if anz[k] >= min_p]


def form_stab(P):
    """Schlank und hoch: Gerade x(z), y(z) durch den Haufen, Radius = mittlerer Abstand der Punkte von dieser Achse (Wolkenpunkte liegen auf der Oberflaeche)."""
    z = P[:, 2]; z0, z1 = np.percentile(z, [1, 99]); hz = float(z1 - z0); c = P - P.mean(0); w, V = np.linalg.eigh(np.cov(c.T)); steil = float(abs(V[2, 2]))
    A = np.c_[z - z.mean(), np.ones(len(z))]; kx = np.linalg.lstsq(A, P[:, 0], rcond=None)[0]; ky = np.linalg.lstsq(A, P[:, 1], rcond=None)[0]; rr = np.hypot(P[:, 0] - A @ kx, P[:, 1] - A @ ky)
    r = float(np.median(rr)); dicke = float(2 * np.percentile(rr, 98)); rest = float(np.median(np.abs(rr - r)))
    ok = hz >= SW["stab_hoehe"] and dicke <= SW["stab_dicke"] and hz / max(dicke, 1e-6) >= SW["stab_schlank"] and steil >= SW["stab_steil"] and rest <= SW["stab_rest"]
    prof = []
    for za in np.arange(z0, z1, 0.25):
        q = rr[(z >= za) & (z < za + 0.25)]
        if len(q) >= 8: prof.append([round(float(za + 0.125), 2), round(float(np.median(q)), 3), int(len(q))])
    mass = dict(x=round(float(kx[1]), 3), y=round(float(ky[1]), 3), z0=round(float(z0), 2), z1=round(float(z1), 2), r=round(r, 3), profil=prof, neigung_grad=round(float(np.degrees(np.arccos(min(steil, 1.0)))), 1), rest=round(rest, 3))
    return ok and len(prof) >= 2, mass, dict(ok=bool(ok and len(prof) >= 2), hoehe=round(hz, 2), dicke=round(dicke, 2), steil=round(steil, 3), rest=round(rest, 3))


def form_ring(P, S, fern):
    """Umlaufend auf einer Hoehe: Sektoren um die Mitte des Modellquerschnitts im Hoehenband des Haufens; Ausladung = waagrechter Abstand der aeusseren Punkte vom Modell je Sektor."""
    from scipy.spatial import cKDTree
    z0, z1 = np.percentile(P[:, 2], [2, 98]); B = S[(S[:, 2] >= z0 - 0.25) & (S[:, 2] <= z1 + 0.25)][:, :2].astype(float); ns = SW["ring_sektoren"]
    if len(B) < 200: return None, None, dict(ok=False, grund="kein Modellquerschnitt in der Hoehe des Haufens")
    c = (np.percentile(B, 2, 0) + np.percentile(B, 98, 0)) / 2; q = P[:, :2] - c; sek = (np.floor((np.arctan2(q[:, 1], q[:, 0]) + np.pi) / (2 * np.pi) * ns).astype(int)) % ns; anz = np.bincount(sek, minlength=ns)
    beleg = anz >= 3; abd = float(beleg.mean()); dh, _ = cKDTree(B).query(P[:, :2]); aus_s = np.array([np.percentile(dh[sek == s], 90) for s in range(ns) if beleg[s]]); aus = float(np.median(aus_s)); rest = float(np.median(np.abs(aus_s - aus)))
    ext = P[:, :2].max(0) - P[:, :2].min(0); flach = float((z1 - z0) / max(ext.min(), 1e-6)); um = bool(np.all(P[:, :2].min(0) < c) and np.all(P[:, :2].max(0) > c))
    ok = abd >= SW["ring_abdeckung"] and flach <= SW["ring_flach"] and rest <= SW["ring_rest"] and um
    # EINSEITIG ('band': Gesims/Ueberstand, den die Wolke nur an einer Seite zeigt): lang gegen Hoehe und Ausladung statt umlaufend; gebaut wird nur im Grundriss-Rechteck des Haufens
    laenge = float(ext.max()); band = (not ok) and laenge >= SW["band_laenge"] and laenge >= SW["band_schlank"] * max(float(z1 - z0), aus) and rest <= SW["ring_rest"] and aus >= fern and int(beleg.sum()) >= 2
    g = np.r_[np.percentile(P[:, :2], 1, 0), np.percentile(P[:, :2], 99, 0)]
    mass = dict(c=[round(float(c[0]), 3), round(float(c[1]), 3)], z0=round(float(z0), 2), z1=round(float(z1), 2), ausladung=round(aus, 3), abdeckung=round(abd, 2), sektoren=[int(b) for b in beleg], grenzen=[round(float(x), 2) for x in g], umlaufend=bool(ok), rest=round(rest, 3))
    return ("ring" if ok and aus >= fern else "band" if band else None), mass, dict(ok=bool(ok and aus >= fern), band=bool(band), abdeckung=round(abd, 2), flach=round(flach, 2), laenge=round(laenge, 2), ausladung=round(aus, 2), rest=round(rest, 3), umschliesst=um)


def form_kasten(P, Sn, Nn, z_boden):
    """Quader an einer Wand: Wandnormale n = mittlere waagrechte Normale der naechsten Modellflaeche, Rahmen u (entlang), w (vor der Wand), z. Flaechen = Raender der Punkte (2/98 %),
    je Flaeche nachgestellt auf den Median der Punkte an ihr (Ebenen-Fit bei fester Richtung); Restfehler = Median-Abstand ALLER Punkte zur naechsten Aussenflaeche (ein gefuellter
    Klumpen haette ~10 % der Kantenlaenge, eine gesehene Huelle wenige cm). Frontebene zusaetzlich frei ausgeglichen (Winkel zur Wandnormale)."""
    nh = Nn[np.abs(Nn[:, 2]) < 0.5][:, :2]
    if len(nh) < 10: return False, None, dict(ok=False, grund="naechste Modellflaeche ist keine Wand")
    n = nh.mean(0); ln = float(np.hypot(*n))
    if ln < 0.3: return False, None, dict(ok=False, grund="keine einheitliche Wandrichtung (Ecke)")
    n = n / ln; d = np.array([-n[1], n[0]]); o = Sn[:, :2].mean(0); u = (P[:, :2] - o) @ d; w = (P[:, :2] - o) @ n; z = P[:, 2]; an_wand = (Nn[:, :2] @ n) > 0.7
    w_wand = float(np.median((Sn[an_wand][:, :2] - o) @ n)) if an_wand.sum() >= 10 else float(np.percentile((Sn[:, :2] - o) @ n, 50))
    u0, u1 = np.percentile(u, [2, 98]); z0, z1 = np.percentile(z, [2, 98]); w1 = float(np.percentile(w, 98)); bis_boden = bool(z0 <= z_boden + 0.3)
    def abst(): return np.c_[np.abs(u - u0), np.abs(u - u1), np.abs(w - w1), np.abs(z - z1)] if bis_boden else np.c_[np.abs(u - u0), np.abs(u - u1), np.abs(w - w1), np.abs(z - z1), np.abs(z - z0)]
    for _ in range(2):                                                                      # Flaechen auf den Median der Punkte an ihnen nachstellen
        D = abst(); j = D.argmin(1); nah = D.min(1) < 0.15
        if (nah & (j == 0)).sum() >= 10: u0 = float(np.median(u[nah & (j == 0)]))
        if (nah & (j == 1)).sum() >= 10: u1 = float(np.median(u[nah & (j == 1)]))
        if (nah & (j == 2)).sum() >= 10: w1 = float(np.median(w[nah & (j == 2)]))
        if (nah & (j == 3)).sum() >= 10: z1 = float(np.median(z[nah & (j == 3)]))
        if not bis_boden and (nah & (j == 4)).sum() >= 10: z0 = float(np.median(z[nah & (j == 4)]))
    D = abst(); j = D.argmin(1); rest = float(np.median(D.min(1))); nah = D.min(1) < 0.15; namen = ["links", "rechts", "front", "oben", "unten"]; fl = {namen[i]: round(float((nah & (j == i)).mean()), 3) for i in range(D.shape[1])}
    kanten = [float(u1 - u0), float(w1 - w_wand), float(z1 - (0.0 if bis_boden else z0))]; fr = P[nah & (j == 2)]; winkel = 90.0
    if len(fr) >= 30:
        ev, V = np.linalg.eigh(np.cov((fr - fr.mean(0)).T)); nf = V[:, 0]; winkel = float(np.degrees(np.arccos(min(abs(float(nf[:2] @ n)), 1.0))))
    ok = min(kanten) >= SW["kasten_min"] and rest <= SW["kasten_rest"] and rest / max(min(kanten), 1e-6) <= SW["kasten_rel"] and fl["front"] >= SW["kasten_front"] and winkel <= SW["kasten_winkel"]
    mass = dict(o=[round(float(o[0]), 3), round(float(o[1]), 3)], d=[round(float(d[0]), 4), round(float(d[1]), 4)], n=[round(float(n[0]), 4), round(float(n[1]), 4)], u0=round(float(u0), 3), u1=round(float(u1), 3), w0=round(w_wand, 3), w1=round(float(w1), 3),
                z0=round(float(z0), 2), z1=round(float(z1), 2), bis_boden=bis_boden, flaechen=fl, winkel_front=round(winkel, 1), rest=round(rest, 3))
    return ok, mass, dict(ok=bool(ok), kanten=[round(k, 2) for k in kanten], rest=round(rest, 3), rest_rel=round(rest / max(min(kanten), 1e-6), 3), front=fl["front"], winkel=round(winkel, 1))


def gleich(h, k):
    """derselbe Koerper wie ein schon eingetragener Kandidat (auch ein verworfener: wird nicht wieder vorgeschlagen)."""
    if h.get("form") != k.get("form"): return False
    if h["form"] == "rund": return bool(np.hypot(k["kreis"]["x"] - h["kreis"]["x"], k["kreis"]["y"] - h["kreis"]["y"]) < 1.0)
    a, b = np.array(h["kasten"], float), np.array(k["kasten"], float); return bool(np.linalg.norm((a[:3] + a[3:]) / 2 - (b[:3] + b[3:]) / 2) < 1.0)


def uebernehmen(H, K):
    """Kandidaten (baubare Form, kein Nachbar/Hohlraum) DAUERHAFT in die Liste K (audit/koerper_auto.json): angenommen = None bis tools/koerper_schleife.py nachgemessen hat. -> neue Eintraege"""
    neu = []
    for h in H:
        if not h.get("kandidat") or any(gleich(h, k) for k in K): continue
        if h["form"] == "rund" and not (h.get("profil") and len(h["profil"]) >= 4): continue
        K.append(dict(h, id=f"{h['form']}{sum(1 for k in K if k.get('form') == h['form'])}", haufen_id=h.get("id"), angenommen=None, am_modell_vorher=h.get("am_modell"))); neu.append(K[-1])
    return neu


def messen(S, N, W, a, eigen=None, fremd=None, kandidaten=()):
    """Kern: Modellabtastung S (+ Normalen N), Wolke W -> (Haufenliste, Kennzahlen, Restpunkte, Kandidatenmessung). Ohne Dateizugriff (Tests)."""
    from scipy.spatial import cKDTree
    lo, hi = S.min(0), S.max(0); W = W[np.all((W > lo - a.weit) & (W < hi + a.weit), 1) & (W[:, 2] > lo[2] + a.boden)]; d, ix = cKDTree(S).query(W, workers=-1); an = d <= a.fern; nah_m = d <= a.nah
    rm = (d > a.fern) & (d < a.weit); R = W[rm].astype(float); dR = d[rm]; iR = ix[rm]; kl = np.zeros(len(R), int); fr_i = np.full(len(R), -1)
    if fremd:                                                                                # Klasse 2: ueber fremder Grundflaeche (nicht ueber eigener), bis Dachhoehe + Toleranz
        eig = np.zeros(len(R), bool)
        for p in eigen or []: eig |= in_polygon(R, p)
        for i, (nm, p, zd) in enumerate(fremd):
            k = in_polygon(R, p) & ~eig & (R[:, 2] <= zd + SW["dach_tol"]) & (kl == 0); kl[k] = 2; fr_i[k] = i
    kl[umschlossen(S, R)] = 1                                                                # Klasse 1: vom Modell umschlossen (Vollkoerper oder hohle Druckschale)
    def im_kasten(k, rand=SW["rand"]): return np.all((W > np.array(k[:3]) - rand) & (W < np.array(k[3:]) + rand), 1)
    H = []
    for klasse, name in ((0, "aussen"), (1, "innen"), (2, "fremd")):
        sub = np.flatnonzero(kl == klasse)
        for idx in haufen_bilden(R[sub], a.zelle, a.min_p):
            s = sub[idx]; P = R[s]; dk = dR[s]
            if dk.min() > a.anschluss and name != "innen": continue                           # beruehrt das Modell nicht -> Umgebung (Punkte IM Modell gehoeren immer dazu)
            c = P - P.mean(0); ev = np.sqrt(np.maximum(np.linalg.eigvalsh(np.cov(c.T)), 0)); hoehe = float(P[:, 2].max() - P[:, 2].min()); kasten = [round(float(x), 2) for x in np.r_[P.min(0), P.max(0)]]
            h = dict(klasse=name, punkte=int(len(s)), kasten=kasten, abstand_max=round(float(np.percentile(dk, 95)), 2), abstand_median=round(float(np.median(dk)), 2), staerke=[round(float(x), 2) for x in ev], profil=None, kreis=None, mass=None, pruef={})
            h["am_modell"] = int((nah_m & im_kasten(kasten)).sum()); schnitt = float((dk >= a.weit - a.zelle).mean()); h["abgeschnitten"] = round(schnitt, 3)
            if eigen: h["ueber_eigen"] = round(float(np.any([in_polygon(P, p) for p in eigen], 0).mean()), 2)
            if name == "fremd":
                nm = fremd[int(np.bincount(fr_i[s]).argmax())][0]; h.update(form="nachbar", nachbar=dict(quelle="Grundflaeche", name=nm), kandidat=False, grund="liegt ueber fremder Grundflaeche " + nm)
            elif name == "innen": h.update(form="hohl", kandidat=False, grund="Wolke im Vollkoerper des Modells: Durchfahrt/Nische/Innenraum fehlt im Modell oder Lagefehler")
            elif P[:, 2].min() <= lo[2] + a.boden + 1.0 and hoehe >= SW["nachbar_hoehe"] and schnitt >= SW["nachbar_schnitt"] and h.get("ueber_eigen", 0.0) < 0.5:
                h.update(form="nachbar", nachbar=dict(quelle="ANNAHME geometrisch"), kandidat=False, grund=f"ANNAHME (kein Grundflaechenbeleg): reicht bis zum Boden, {hoehe:.1f} m hoch, {schnitt * 100:.0f} % an der Suchgrenze {a.weit} m abgeschnitten = eigenes Gebaeude/Umgebung")
            elif schnitt >= SW["nachbar_schnitt"] and not form_stab(P)[0]:                    # ein lotrechter Stab darf oben ueber die Suchgrenze hinausreichen (Helmstange), er bleibt 'stab'
                h.update(form="umgebung", kandidat=False, grund=f"{schnitt * 100:.0f} % an der Suchgrenze {a.weit} m abgeschnitten, kein Bodenkontakt: reicht ueber den betrachteten Raum hinaus (Leitung, Baum, Streupunkte entlang Sehstrahlen, fremdes Dach) - kein vollstaendig gemessener Koerper")
            else:
                cx, cy, r, res = kreis(P[:, :2]); bogen = 10.0 * int((np.bincount(((np.degrees(np.arctan2(P[:, 1] - cy, P[:, 0] - cx)) + 180.0) / 10.0).astype(int) % 36, minlength=36) >= 2).sum())
                h["pruef"]["rund"] = dict(ok=bool(res <= SW["rund_rest"] and 0.4 <= r <= 4.0 and hoehe >= 1.5 and bogen >= SW["rund_bogen"]), r=round(r, 2), rest=round(res, 3), bogen_grad=bogen, hoehe=round(hoehe, 2))
                ok_s, m_s, h["pruef"]["stab"] = form_stab(P); f_r, m_r, h["pruef"]["ring"] = form_ring(P, S, a.fern); ok_k, m_k, h["pruef"]["kasten"] = form_kasten(P, S[iR[s]], N[iR[s]], lo[2] + a.boden)
                if h["pruef"]["rund"]["ok"]:
                    h["form"] = "rund"; h["kreis"] = dict(x=round(cx, 2), y=round(cy, 2), r=round(r, 2), rest=round(res, 3), bogen_grad=bogen)
                    # DREHPROFIL r(z) aus der Wolke um die gefundene Achse: Schaft, Gesims, Haube ohne Musterteil
                    rr = np.hypot(W[:, 0] - cx, W[:, 1] - cy); nah = (rr < r + 0.9) & (d > 0.15) & (W[:, 2] < P[:, 2].max() + 6.0); zz = W[nah, 2]; rq = rr[nah]; prof = []
                    for z0 in np.arange(float(P[:, 2].min()), float(zz.max()) if nah.any() else 0.0, 0.25):
                        q = rq[(zz >= z0) & (zz < z0 + 0.25)]
                        if len(q) < 25:
                            if prof and z0 > P[:, 2].max(): break
                            continue
                        hh, kk = np.histogram(q, bins=np.arange(0.0, r + 0.95, 0.05)); j = int(np.argmax(hh * kk[1:]))      # dichteste Schale (flaechengewichtet), nicht der Median: Innenpunkte/Nachbarwand stoeren
                        prof.append([round(float(z0 + 0.125), 2), round(float(np.median(q[(q >= kk[j] - 0.05) & (q < kk[j + 1] + 0.05)])), 3), int(len(q))])
                    h["profil"] = prof
                elif ok_s: h["form"] = "stab"; h["mass"] = dict(m_s, oben_abgeschnitten=bool(schnitt >= SW["nachbar_schnitt"]))
                elif f_r == "ring": h["form"] = "ring"; h["mass"] = m_r
                elif ok_k: h["form"] = "kasten"; h["mass"] = m_k
                elif f_r == "band": h["form"] = "band"; h["mass"] = m_r
                else: h["form"] = "platte" if ev[0] <= 0.25 and ev[1] >= 0.6 else "koerper"
                h["kandidat"] = h["form"] in BAUBAR
            H.append(h)
    H.sort(key=lambda h: -h["punkte"])
    for i, h in enumerate(H): h["id"] = f"r{i:02d}"
    kenn = dict(im_kasten=int(len(W)), an_flaeche=round(float(an.mean()), 3) if len(W) else 0.0, an_flaeche_punkte=int(an.sum()), rest=int(len(R)), rest_innen=int((kl == 1).sum()), rest_fremd=int((kl == 2).sum()))
    return H, kenn, (R, kl), {k["id"]: int((nah_m & im_kasten(k["kasten"])).sum()) for k in kandidaten if k.get("id") and k.get("kasten")}


def text(h):
    k = h["kasten"]; z = ""
    if h["form"] == "rund": z = f" (Kreis r {h['kreis']['r']} m, Rest {h['kreis']['rest']} m, Bogen {h['kreis']['bogen_grad']:.0f} Grad)"
    elif h["form"] == "stab": z = f" (r {h['mass']['r']} m, z {h['mass']['z0']}..{h['mass']['z1']}, Rest {h['mass']['rest']} m)"
    elif h["form"] in ("ring", "band"): z = f" (z {h['mass']['z0']}..{h['mass']['z1']}, Ausladung {h['mass']['ausladung']} m, Abdeckung {h['mass']['abdeckung'] * 100:.0f} %, Rest {h['mass']['rest']} m)"
    elif h["form"] == "kasten": m = h["mass"]; z = f" (breit {m['u1'] - m['u0']:.2f}, tief {m['w1'] - m['w0']:.2f}, z {m['z0']}..{m['z1']}, Rest {m['rest']} m)"
    elif h["form"] == "nachbar": z = f" ({h['nachbar'].get('name') or h['nachbar']['quelle']})"
    return (f"{h['id']}: {h['punkte']:6d} Punkte  x {k[0]:.1f}..{k[3]:.1f}  y {k[1]:.1f}..{k[4]:.1f}  z {k[2]:.1f}..{k[5]:.1f}  Abstand Median {h['abstand_median']} / 95 % {h['abstand_max']} m  Form: {h['form']}{z}"
            + ("  KANDIDAT" if h.get("kandidat") else ""))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("wolke"); ap.add_argument("--stl"); ap.add_argument("--fern", type=float, default=0.35); ap.add_argument("--zelle", type=float, default=0.4)
    ap.add_argument("--anschluss", type=float, default=0.8); ap.add_argument("--weit", type=float, default=4.0, help="Punkte weiter weg vom Modell = Umgebung, nicht betrachtet"); ap.add_argument("--min_p", type=int, default=150)
    ap.add_argument("--jeder", type=int, default=6); ap.add_argument("--boden", type=float, default=1.0); ap.add_argument("--bild", default=""); ap.add_argument("--uebernehmen", action="store_true", help="baubare Haufen als Kandidaten nach audit/koerper_auto.json (Eingang bauteile.wolkenrest_koerper)")
    ap.add_argument("--grundflaechen", default="", help="JSON {eigen: [[[x,y],..]], fremd: [{name, umriss, hoehe}]} im Modellrahmen statt LoD2"); ap.add_argument("--proben", type=int, default=1500000); ap.add_argument("--nah", type=float, default=0.15, help="Grenze fuer 'am_modell' je Haufen/Kandidat (Annahmeregel koerper_schleife)"); a = ap.parse_args()
    import trimesh
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); stl = a.stl or os.path.join(ROOT, obj["stl"]); m = trimesh.load(stl); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    S, fi = trimesh.sample.sample_surface(m, a.proben, seed=0); S = np.asarray(S, np.float32); N = np.asarray(m.face_normals[fi], np.float32); lo, hi = S.min(0), S.max(0)      # fester Keim: Wiederholung zaehlt gleich (Annahmeregel vergleicht Zaehlungen)
    W = np.asarray(np.load(a.wolke, mmap_mode="r")[::a.jeder, :3], np.float32); eigen, fremd, gq = grundflaechen_laden(obj, a.grundflaechen, (lo[:2] + hi[:2]) / 2, float(np.linalg.norm(hi[:2] - lo[:2]) / 2 + a.weit + 30.0))
    if fremd:                                                                                # Gueltigkeits-Guard: eine 'fremde' Grundflaeche, auf der das Modell selbst steht, ist die eigene (falsche/fehlende LoD2-Kennung)
        q = S[::50, :2]; eigen = list(eigen or []) + [p for nm, p, zd in fremd if in_polygon(q, p).mean() >= SW["eigen_anteil"]]; fremd = [(nm, p, zd) for nm, p, zd in fremd if in_polygon(q, p).mean() < SW["eigen_anteil"]]
    A = os.path.join(od, "audit"); os.makedirs(A, exist_ok=True); kp = os.path.join(A, "koerper_auto.json"); K = json.load(open(kp)).get("haufen", []) if os.path.exists(kp) else []
    H, kenn, (R, kl), kmess = messen(S, N, W, a, eigen, fremd, K)
    print(f"Wolke im Kasten: {kenn['im_kasten']} Punkte, an der Modellflaeche (<= {a.fern} m): {kenn['an_flaeche_punkte']} = {kenn['an_flaeche'] * 100:.1f} % (Vergleich zwischen Bauten ueber die ANZAHL: der Kasten waechst mit dem Modell), Rest bis {a.weit} m: {kenn['rest']}"
          f" (davon im Vollkoerper {kenn['rest_innen']}, ueber fremder Grundflaeche {kenn['rest_fremd']})\nGrundflaechen: {gq}" + ("" if fremd is not None else " -> Nachbarn nur ueber die geometrische Ersatzregel (ANNAHME)"))
    for h in H: print(text(h))
    json.dump(dict(quelle="tools/wolke_rest.py", stl=os.path.relpath(stl, ROOT), wolke=a.wolke, fern=a.fern, grundflaechen=gq, schwellen=SW, **{k: kenn[k] for k in ("an_flaeche", "an_flaeche_punkte", "rest", "rest_innen", "rest_fremd")}, kandidaten=kmess, haufen=H),
              open(os.path.join(A, "wolke_rest.json"), "w"), indent=1)
    if a.uebernehmen:                                                                         # gefundene Koerper DAUERHAFT ablegen: nach dem Bau liegt der Haufen am Modell und verschwindet aus dem Rest
        for k in uebernehmen(H, K): print(f"uebernommen als Kandidat: {k['id']} ({k['haufen_id']}, {k['punkte']} Punkte)")
        json.dump(dict(quelle="tools/wolke_rest.py --uebernehmen", haufen=K), open(kp, "w"), indent=1)
    if a.bild:
        import cv2
        px = 0.05; B = []; farbe = dict(nachbar=(150, 150, 150), umgebung=(150, 150, 150), hohl=(60, 160, 60)); pf = np.array([(150, 170, 255), (170, 220, 170), (215, 215, 215)], np.uint8)[kl]      # Rest: aussen rot, innen gruen, fremd grau
        for (i, j, nm) in ((0, 2, "von Sueden/Norden (x-z)"), (1, 2, "von Osten/Westen (y-z)"), (0, 1, "Grundriss (x-y)")):
            a0 = min(lo[i], R[:, i].min()) - 0.5; b0 = min(lo[j], R[:, j].min()) - 0.5; w_ = int((max(hi[i], R[:, i].max()) + 0.5 - a0) / px); h_ = int((max(hi[j], R[:, j].max()) + 0.5 - b0) / px); im = np.full((h_, w_, 3), 255, np.uint8)
            q = S[::6]; im[np.clip(h_ - 1 - ((q[:, j] - b0) / px).astype(int), 0, h_ - 1), np.clip(((q[:, i] - a0) / px).astype(int), 0, w_ - 1)] = (120, 120, 120)
            im[np.clip(h_ - 1 - ((R[:, j] - b0) / px).astype(int), 0, h_ - 1), np.clip(((R[:, i] - a0) / px).astype(int), 0, w_ - 1)] = pf
            for h in H[:24]:
                k = h["kasten"]; p0 = (int((k[i] - a0) / px), h_ - 1 - int((k[j + 3] - b0) / px)); p1 = (int((k[i + 3] - a0) / px), h_ - 1 - int((k[j] - b0) / px)); f = farbe.get(h["form"], (0, 0, 200) if h.get("kandidat") else (200, 100, 0))
                cv2.rectangle(im, p0, p1, f, 2 if h.get("kandidat") else 1); cv2.putText(im, f"{h['id']} {h['form']}", (p0[0] + 3, p0[1] + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, f, 1 + int(bool(h.get("kandidat"))))
            cv2.putText(im, nm, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2); B.append(im)
        hh = max(b.shape[0] for b in B); B = [cv2.copyMakeBorder(b, hh - b.shape[0], 0, 0, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for b in B]; cv2.imwrite(a.bild, np.hstack(B), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"-> {os.path.join(A, 'wolke_rest.json')}: {len(H)} Haufen am Modell, {sum(1 for h in H if h.get('kandidat'))} Kandidaten, {sum(1 for h in H if h['form'] == 'nachbar')} Nachbarn, {sum(1 for h in H if h['form'] == 'hohl')} Hohlraeume"); return 0


if __name__ == "__main__": sys.exit(main())
