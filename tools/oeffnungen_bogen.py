#!/usr/bin/env python3
"""oeffnungen_bogen.py <ortho-ordner> --objekt <objekt.json> [--aus audit/oeffnungen_auto.json] - BOGENOEFFNUNGEN / TORDURCHFAHRTEN automatisch (17.11.2026, Kettenstufe 'fenster').

Anlass: das vollautomatische Schwabentor (schwab_auto) stand als geschlossener Klotz da. Ursache (gemessen): fassade_parsing.py (OWLv2) FINDET den Torbogen auf beiden Torseiten
mit 8 von 8 Stimmen (elemente.json, Klasse 'bogen') - aber fenster_aus_parsing.py liest nur die Klasse 'fenster'; die Klasse 'bogen' ging nirgends in den Generator.
Hier, ohne Handgriff, je Fassade:
  1. KANDIDATEN = Kaesten der Klasse 'bogen', die am Boden stehen (Unterkante <= --boden ueber dem Fassadenfuss), begehbar gross sind (>= --min_b breit, >= --min_h hoch)
     und genug Stimmen haben (>= --stimmen und >= 60 % der Fotos). Der Kasten ist NUR Suchfenster (Hoehen z0_roh/z1_roh: die Reihenbildung des Parsings zieht Kaesten ueber Geschosse zusammen).
  2. DURCHBLICK aus der Triangulation (KERNMETHODE: Tiefen-Sweep mit den SfM-Kameras): Ebenen-Sweep der Fassade (tools/fassade_tiefe.py, GPU, eigener Unterordner oeffnungen_tiefe/).
     Je Zelle: WAND = sichere Tiefe auf der OERTLICHEN Wandtiefe; OFFEN = Bildstruktur da, aber die Fotos werden in der Wandtiefe nicht deckungsgleich (dahinter liegt etwas anderes);
     LAIBUNG = zusammenhaengend knapp hinter der Wand (Fase, zurueckgesetztes Tuerblatt); sonst unbekannt (glatt, dunkel, kein Foto). Geschlossene Bogentuer, Blendbogen, Putzfeld -> kein OFFEN -> keine Oeffnung.
     Verworfen (zwei Fassungen, gleicher Tag): Helligkeits-Streuung der Fotos (Bruchstein streut genauso, Verhaeltnis innen/Wand 1,07) und Dichte der abgestimmten Canny-Kanten
     (Fotos vom gleichen Standort stimmen auch im Durchblick ueberein).
  3. FORM: die groesste Bogenform (rund / stich / spitz; Mitte, lichte Breite, Kaempfer, Pfeilhoehe frei), die den Durchblick einschliesst und keine Wandzellen (form_einpassen).
     Gegenpruefung: <= --wand_innen Wandzellen im Inneren, >= --rand_wand des Streifens aussen am Bogenrand ist Wand, Durchblick im Inneren >= --offen, Wand daneben deckungsgleich.
     Feinlage an Fotokanten auf der ECHTEN Wandebene (kanten_auf_ebene, 2 cm) nur, wenn sich die Kurve von verschobenen Kopien abhebt - in Bruchstein tut sie das nicht, dann gilt die Sweep-Lage (4 cm Zellen).
  4. DURCHFAHRT: (a) Gegenseite (Normale entgegengesetzt) hat selbst eine angenommene Oeffnung an gleicher Stelle -> jede Seite schneidet ihren Querschnitt bis zur Gebaeudemitte;
     (b) Gegenseite: Bogen erkannt und Durchblick an der durchprojizierten Form belegt, eigene Form aber nicht messbar (Baum, Vorbau) -> Querschnitt dieser Seite gerade durch das Gebaeude (ANNAHME);
     sonst Nische mit --nische m Tiefe (ANNAHME).
Ausgabe: je Fassade o, d, n und 'oeffnungen' (form, u, breite, kaempfer, scheitel, unten, tiefe_m, durchfahrt, gebaut, grund, annahmen) - fuer bauteile.oeffnungen_aus_json (nur gebaut = true).
Bilder im Ortho-Ordner ANSEHEN: oeffnungen_<id>.jpg (gruen = gebaut, rot = verworfen, gelb = Erkennerkasten), oeffnungen_<id>_maske.png (weiss = offen, grau = Wand).
Gemessen ist: Mitte, lichte Breite, Kaempfer, Scheitel (Sweep auf der echten Wandtiefe). ANNAHME ist: Tiefe, gleichbleibender Querschnitt, Kreisbogenform der Familie, Gewaende ohne Profil.
Wand ohne Bilddaten bekommt keine Oeffnung (kein Kandidat, kein Sweep); nichts wird gespiegelt.
Stand 17.11.2026: Schwabentor Nord gebaut (gegen Handmass schwab_v3: Mitte -0,13 m, Breite +0,35 m, Kaempfer -0,33 m, Scheitel +0,13 m), Sued Form nicht messbar (Baum/Strebepfeiler vor der linken Haelfte) -> Fall 4b;
Turmtuer f04 (geschlossenes Tuerblatt) richtig verworfen; ober_tvdr kein Kandidat; Kaufhaus-Arkaden f02 verworfen (Wand zwischen den Boegen nur schmale Pfeiler, Sweep dort nicht belastbar).
Grenzen: nur Boegen am Boden (Fensterboegen/Blendnischen in der Hoehe bleiben offen); Rechtecktore gar nicht; Arkadenreihen mit schmalen Pfeilern; Schwellen an EINEM Bauwerk eingestellt."""
import sys, os, json, argparse, numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


WAND_ANTEIL_MIN = 0.6     # 23.11.2026: eine Oeffnungszone muss zu >= 60 % IN der Wandflaeche (Fassadenpolygon polys_uz) liegen


def wand_anteil(F, kasten, zelle=0.05):
    """Anteil des Kastens [u0, u1, z0, z1], der im Fassadenpolygon (F['polys_uz'], LoD2-Wandflaeche) liegt; None = kein Polygon (kein Urteil).
    Anlass 1122o: der Erkenner meldete den Treppenturm VOR der Ostwand f03 (Zylinder + Kegeldach = 'Bogen'-Silhouette, 3,6 x 16 m) als Bogen - die Ostwand hat
    an der Stelle gar keine Flaeche (LoD2-Polygon dort ausgespart, der Turm ist ein eigener Koerper f04-f07). Ein Koerper vor der Wand ist keine Oeffnung in ihr."""
    P = F.get("polys_uz")
    if isinstance(P, str):
        try: P = json.loads(P)
        except Exception: return None
    if not P: return None
    u0, u1, z0, z1 = (float(x) for x in kasten[:4])
    if u1 - u0 <= 0 or z1 - z0 <= 0: return None
    nu, nz = max(2, int(np.ceil((u1 - u0) / zelle))), max(2, int(np.ceil((z1 - z0) / zelle)))
    m = np.zeros((nz, nu), np.uint8)
    for poly in P:
        q = np.array([[(u - u0) / zelle, (z1 - z) / zelle] for u, z in poly], np.float64)
        cv2.fillPoly(m, [np.round(q * 8).astype(np.int32)], 1, shift=3)
    return float(m.mean())


def sweep_laden(ordner, objekt, nr, fid, rois, py=sys.executable, log=print):
    """EBENEN-SWEEP der Fassade (tools/fassade_tiefe.py, GPU): je Wandzelle die Tiefe, in der die Fotos uebereinstimmen. Ergebnis in <ordner>/oeffnungen_tiefe/ (eigener Unterordner,
    die Dateien der Stufe 'seiten' bleiben unberuehrt). Liegt die Wandtiefe am Rand des Suchbereichs (LoD2-Wand steht falsch), einmal mit verschobenem Bereich wiederholen.
    Liefert dict(w, gut, u0, z1, zelle, w_wand) oder None."""
    import subprocess, shutil
    td = os.path.join(ordner, "oeffnungen_tiefe"); os.makedirs(td, exist_ok=True); fj = os.path.join(ordner, "fassaden.json"); nz_ = os.path.join(td, f"tiefe_f{nr:02d}.npz")
    def wand(Z):                                                          # Wandtiefe OERTLICH (um die Kandidaten): die haeufigste sichere Tiefe der ganzen Fassade ist bei Tuermen oft Unsinn (glatter Putz oben, Draehte: f00 Schwabentor +2,50 = Suchrand)
        w = Z["w"]; c = float(Z["zelle"]); H, W = w.shape; ys, xs = np.mgrid[0:H, 0:W]; U = float(Z["u0"]) + (xs + 0.5) * c; Zz = float(Z["z1"]) - (ys + 0.5) * c; m = np.zeros((H, W), bool)
        for u0, u1, z0, z1 in rois: m |= (U >= u0) & (U <= u1) & (Zz >= z0) & (Zz <= z1)
        g = Z["gut"] & m & (w > w.min() + 0.01) & (w < w.max() - 0.01)
        if g.sum() < 200: return None
        h, k = np.histogram(w[g], bins=np.arange(w.min() - 0.025, w.max() + 0.05, 0.05)); h = np.convolve(h, np.ones(3), "same"); return float(0.5 * (k[int(np.argmax(h))] + k[int(np.argmax(h)) + 1]))
    if not (os.path.exists(nz_) and os.path.getmtime(nz_) >= os.path.getmtime(fj)):
        if not objekt: return None
        shutil.copy(fj, os.path.join(td, "fassaden.json")); ber = (-0.8, 2.5)
        for runde in range(2):
            r_ = subprocess.run([py, "-W", "ignore", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fassade_tiefe.py"), objekt, td, str(nr), "--w", str(ber[0]), str(ber[1])], capture_output=True, text=True)
            if not os.path.exists(nz_) or r_.returncode not in (0, 4): log(f"  Ebenen-Sweep {fid}: rc {r_.returncode} {r_.stdout[-200:]} {r_.stderr[-300:]}"); return None
            ww = wand(np.load(nz_)); log(f"  Ebenen-Sweep {fid} w {ber[0]}..{ber[1]}: Wandtiefe um die Kandidaten {ww}")
            if ww is None or (ber[0] + 0.25 < ww < ber[1] - 0.25): break
            ber = (round(ww - 1.6, 2), round(ww + 1.6, 2))
    if not os.path.exists(nz_): return None
    Z = np.load(nz_); ww = wand(Z)
    if ww is None: return None
    return dict(w=Z["w"], gut=Z["gut"], u0=float(Z["u0"]), z1=float(Z["z1"]), zelle=float(Z["zelle"]), w_wand=ww, rand=bool(not (float(Z["w"].min()) + 0.25 < ww < float(Z["w"].max()) - 0.25)))


def sweep_masken(T, ortho_bgr, raster, tol=0.2):
    """Aus dem Ebenen-Sweep drei Klassen je Zelle (Sweep-Raster): WAND = sichere Tiefe auf der Wandtiefe; OFFEN = Bildstruktur vorhanden, aber die Fotos werden in der Wandtiefe
    nicht deckungsgleich (Durchblick: dahinter liegt etwas anderes oder weit Entferntes); UNBEKANNT = keine Struktur (glatter Putz, Tuerblatt, tiefer Schatten) oder kein Foto.
    Struktur = oertliche Grauwertstreuung des Fassadenbilds (0,6 m) > 6/255 (wie fassade_tiefe)."""
    from scipy import ndimage as ndi
    H, W = T["w"].shape; c = T["zelle"]; g = cv2.cvtColor(ortho_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32); zl = raster["zelle"]
    xs = ((T["u0"] + (np.arange(W) + 0.5) * c - raster["u0"]) / zl).astype(int); ys = ((raster["z1"] - (T["z1"] - (np.arange(H) + 0.5) * c)) / zl).astype(int)
    ok = (xs >= 0) & (xs < g.shape[1]); oky = (ys >= 0) & (ys < g.shape[0]); gg = np.zeros((H, W), np.float32); gg[np.ix_(oky, ok)] = g[np.ix_(ys[oky], xs[ok])]
    k = max(3, int(round(0.6 / c)) | 1); mu = cv2.blur(gg, (k, k)); sd = np.sqrt(np.maximum(cv2.blur(gg * gg, (k, k)) - mu * mu, 0)); gesehen = gg > 0
    wm = ndi.median_filter(T["w"], 5); wand = ndi.binary_opening(T["gut"] & (np.abs(wm - T["w_wand"]) <= tol) & gesehen, np.ones((5, 5)))      # Einzeltreffer (Zufallstiefe im Durchblick) sind keine Wand
    w2 = ndi.uniform_filter(T["w"] ** 2, 5) - ndi.uniform_filter(T["w"], 5) ** 2; unruhig = np.sqrt(np.maximum(w2, 0)) > 0.3
    offen = gesehen & (sd > 6.0) & ~wand & ((np.abs(wm - T["w_wand"]) > 0.5) | unruhig)      # zusammenhaengend knapp HINTER der Wand (Laibung, Fase, zurueckgesetztes Tuerblatt) ist kein Durchblick -> unbekannt
    offen = ndi.binary_opening(offen, np.ones((3, 3))); laibung = T["gut"] & ~wand & ~unruhig & (np.abs(wm - T["w_wand"]) <= 0.5)
    return wand, offen, gesehen & ~wand & ~laibung


def kanten_auf_ebene(objekt, F, fid, roi, s, td, zelle=0.02, k=12, log=print):
    """FOTOKANTEN AUF DER ECHTEN WANDEBENE: die k besten Fotos der Fassade einzeln auf die um s verschobene Ebene entzerren (bogen_kontur.ebene_ortho, Kameras K-<foto>.json),
    Canny je Foto, Abstimmung ueber die Fotos (element_einpassen.kantenpunkte). Noetig, weil die LoD2-Wand oft 0,2-0,8 m neben der echten Wand steht - im Fassadenbild der Kette
    sind die Kanten dann um die Parallaxe versetzt. Liefert (D, G, anzahl_fotos)."""
    import glob
    from bogen_kontur import ebene_ortho; from element_einpassen import kantenpunkte
    od = os.path.dirname(os.path.abspath(objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(objekt)); ed = os.path.join(td, f"ortho_{fid}_einzeln"); os.makedirs(ed, exist_ok=True)
    for f in glob.glob(os.path.join(ed, "*.png")): os.remove(f)
    u0, u1, z0, z1 = roi; nu = int(round((u1 - u0) / zelle)); nz = int(round((z1 - z0) / zelle)); n = 0
    for nm in sorted(F.get("fotos", {}), key=lambda q: -F["fotos"][q].get("zellen", 0)):
        kf = os.path.join(od, "messprotokoll", "K-" + nm + ".json"); ff = glob.glob(os.path.join(root, obj["fotos_dir"], nm + ".*"))
        if not os.path.exists(kf) or not ff: continue
        kk = json.load(open(kf))["kamera"]; im = cv2.imread(ff[0])
        if im is None or kk.get("tiefe_unsicher"): continue
        sk = im.shape[1] / float(kk["bild"][0]) if kk.get("bild") else 1.0
        cam = dict(R=cv2.Rodrigues(np.array(kk["rvec"], float))[0], t=np.array(kk["t"], float), f=kk["f_px"] * sk, cx=kk["cx"] * sk, cy=kk["cy"] * sk, k1=float(kk.get("k1") or 0.0), tr=kk.get("rahmen_verschiebung", [0, 0, 0]))
        o, ok, mpp = ebene_ortho(im, cam, dict(n=F["n"], d=F["d"], o=F["o"]), (u0, u1, z0, z1), zelle=zelle, s=s)
        if ok.mean() < 0.6 or float(np.median(mpp[ok])) > 2.5 * zelle: continue
        o[~ok] = 0; cv2.imwrite(os.path.join(ed, nm + ".png"), o); n += 1
        if n >= k: break
    if n < 3: return np.zeros((0, 2)), np.zeros((0, 2)), n
    D, G, _v, _n = kantenpunkte(td, fid, dict(u0=u0, z1=z1, zelle=zelle, nu=nu, nz=nz), min_stimmen=3, log=lambda *_: None)
    return D, G, n


def form_einpassen(U, Z, wand, offen, nichtwand, ka, zb, mu=3.0, nu_=0.3, la=0.5):
    """FORM AUS DEM SWEEP: die groesste Bogenform (rund / stich / spitz; Mitte, lichte Breite, Kaempfer, Pfeilhoehe frei), die den bewiesenen Durchblick einschliesst und KEINE Wandzellen.
    Wertung je Zelle im Inneren: offen +1, nicht Wand/nicht Laibung ohne Bildstruktur (dunkles Gewoelbe) +nu_, Wand -mu, Laibung/Fase (zusammenhaengend knapp hinter der Wand) -la: die LICHTE Oeffnung ist gesucht, nicht der Aussenrand der Fase. Zellen unter ~2,2 m zaehlen nicht (Passanten, Autos, Laternen
    stehen vor der Wand und sind im Sweep ebenfalls 'offen'). Die sicherste Klasse ist die WAND (sichere Tiefe auf der Wandtiefe) - sie begrenzt die Form; ein Baum vor einer Seite
    laesst die Form dort hoechstens bis zum Rand des Erkennerkastens (+0,2 m) wachsen. Familienwahl: beste Wertung, einfachere Familie bei < 1 % Unterschied.
    Gegenpruefung: 'rand_wand' = Anteil des Bogenrands (ueber 2,2 m), an dem direkt aussen (<= 0,3 m) Wand liegt; 'wand_innen' = Anteil Wandzellen im Inneren."""
    from element_einpassen import in_oeffnung, FAMILIEN
    from scipy.optimize import differential_evolution
    zf = zb + min(2.2, 0.45 * (ka["z1"] - zb)); g = (Z >= zf).astype(np.float32); wert = (offen * 1.0 + (nichtwand & ~offen) * nu_ - wand * mu - (~wand & ~nichtwand & ~offen) * la) * g; kc = 0.5 * (ka["u0"] + ka["u1"]); kw = ka["u1"] - ka["u0"]
    def aussen(p): return [p[0], p[1] + 0.6, p[2]] + ([p[3] + 0.3] if len(p) > 3 else [])
    def f(p, fam):
        w = p[1]; h = w / 2 if fam == "rund" else p[3]
        if (fam == "stich" and not (0.3 <= h < w / 2 - 1e-3)) or (fam == "spitz" and h <= w / 2 + 1e-3) or p[0] - w / 2 < ka["u0"] - 0.2 or p[0] + w / 2 > ka["u1"] + 0.2 or p[2] + h > ka["z1"] + 0.3: return 1e6
        return -float(wert[in_oeffnung(fam, p, zb, U, Z)].sum())
    erg = {}
    for fam in ("rund", "stich", "spitz"):
        b = [(kc - 0.8, kc + 0.8), (max(1.0, kw - 1.6), kw + 0.4), (zb + 0.8, ka["z1"])] + ([(0.3, 4.5)] if fam != "rund" else [])
        r = min((differential_evolution(f, b, args=(fam,), seed=sd_, maxiter=200, popsize=24, tol=0, atol=0, polish=False, init="sobol") for sd_ in (0, 17)), key=lambda q: q.fun); p = [float(x) for x in r.x]      # Stufenfunktion (Zellzahlen): zwei Starts, der bessere gilt
        inn = in_oeffnung(fam, p, zb, U, Z) & (Z >= zf); ring = in_oeffnung(fam, aussen(p), zb, U, Z) & ~in_oeffnung(fam, p, zb, U, Z) & (Z >= zf)
        erg[fam] = dict(p=[round(x, 4) for x in p], wertung=round(-float(r.fun), 1), wand_innen=round(float(wand[inn].mean()) if inn.any() else 1.0, 3), rand_wand=round(float(wand[ring].mean()) if ring.any() else 0.0, 3))
    wahl = max(erg, key=lambda q: erg[q]["wertung"])
    for fam in sorted(erg, key=lambda q: FAMILIEN[q]):
        if FAMILIEN[fam] < FAMILIEN[wahl] and erg[fam]["wertung"] >= 0.99 * erg[wahl]["wertung"]: wahl = fam; break
    return dict(familie=wahl, p=erg[wahl]["p"], rest=dict(wand_innen=erg[wahl]["wand_innen"], rand_wand=erg[wahl]["rand_wand"]), alle_familien=erg)


def durchblick(T, wand, offen, fam, p, zb, rand=0.2):
    """Durchblick-Probe an der gefitteten Oeffnung: Anteil OFFEN an den bekannten Zellen (OFFEN + WAND) im Inneren, dasselbe im Wandring 0,3-1,2 m ausserhalb (dort muss WAND ueberwiegen,
    sonst ist der Sweep an dieser Stelle nicht belastbar)."""
    from element_einpassen import in_oeffnung
    H, W = wand.shape; c = T["zelle"]; ys, xs = np.mgrid[0:H, 0:W]; U = T["u0"] + (xs + 0.5) * c; Z = T["z1"] - (ys + 0.5) * c
    def gr(q): return [p[0], p[1] + 2 * q, p[2]] + ([p[3] + q] if len(p) > 3 else [])
    innen = in_oeffnung(fam, p, zb, U, Z, rand=rand) & (Z > zb + 0.5); ring = in_oeffnung(fam, gr(1.2), zb, U, Z) & ~in_oeffnung(fam, gr(0.3), zb, U, Z) & (Z > zb + 0.5)
    def ant(m): o_, w_ = int((offen & m).sum()), int((wand & m).sum()); return (o_ / (o_ + w_) if o_ + w_ else None), (o_ + w_) / max(int(m.sum()), 1), o_ / max(int(m.sum()), 1)
    ai, bi, oi = ant(innen); sei = [ant(ring & m_)[0] for m_ in (U < p[0], U >= p[0])]; sei = [x for x in sei if x is not None]      # je Seite: vor EINER Seite darf ein Baum/Vorbau stehen, die andere muss Wand zeigen
    return dict(offen_innen=None if ai is None else round(ai, 3), offen_flaeche_innen=round(oi, 3), bekannt_innen=round(bi, 3), offen_wand=round(min(sei), 3) if sei else None, offen_wand_seiten=[round(x, 3) for x in sei], zellen_innen=int(innen.sum()))


def kanten_verfeinern(D, G, fam, p, zb, schritt=0.3):
    """Feinlage an den Fotokanten OHNE Polaritaetsannahme (helle Laibung in dunklem Stein kommt vor): Nelder-Mead um die Sweep-Lage, Grenzen +-schritt.
    Uebernommen wird nur, wenn danach mehr von der Kurve auf Kanten liegt UND sie sich von verschobenen Kopien abhebt. Liefert (p_neu, stuetze_vor, stuetze_nach, uebernommen, stuetze_verschoben)."""
    from element_einpassen import kosten_fn, profil
    from scipy.optimize import minimize; from scipy.spatial import cKDTree
    f = kosten_fn(D, G, fam, zb, False); p = np.array(p, float); t = cKDTree(D)
    def st(q, dp=(0.0, 0.0)): P = profil(fam, q, zb, 0.03); P = P[P[:, 1] >= q[2] - 1.2] + np.array(dp); return float(np.mean(t.query(P)[0] < 0.05))
    def g(q):
        if np.any(np.abs(q - p) > schritt) or (fam == "stich" and (q[3] >= q[1] / 2 - 1e-3 or q[3] < 0.3)) or (fam == "spitz" and q[3] <= q[1] / 2 + 1e-3): return 1e3
        return f(q)
    r = minimize(g, p, method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-9, maxiter=800, initial_simplex=np.vstack([p] + [p + np.eye(len(p))[i] * 0.06 for i in range(len(p))])))
    s0, s1 = st(p), st(r.x); neben = float(np.mean([st(r.x, (0.3 * np.cos(w_), 0.3 * np.sin(w_))) for w_ in np.linspace(0, 2 * np.pi, 8, endpoint=False)]))      # Bruchstein hat ueberall Kanten: die Kurve muss deutlich besser gestuetzt sein als ihre um 0,3 m verschobenen Kopien
    ja = bool(r.fun < g(p) and s1 >= max(0.5, s0 + 0.05) and s1 >= 1.5 * neben)
    return ([float(x) for x in r.x], round(s0, 3), round(s1, 3), ja, round(neben, 3))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ortho"); ap.add_argument("--objekt", help="objekt.json: noetig, um den Ebenen-Sweep (fassade_tiefe.py) zu rechnen; ohne ihn wird nur ein vorhandener Sweep gelesen"); ap.add_argument("--aus"); ap.add_argument("--stimmen", type=int, default=3)
    ap.add_argument("--boden", type=float, default=1.5, help="Kastenunterkante hoechstens so hoch ueber dem Fassadenfuss (m)"); ap.add_argument("--min_b", type=float, default=1.2); ap.add_argument("--min_h", type=float, default=2.2)
    ap.add_argument("--nische", type=float, default=0.6, help="ANNAHME: Tiefe einer Bogenoeffnung ohne Gegenstueck (m)"); ap.add_argument("--offen", type=float, default=0.6, help="Durchblick: Anteil OFFEN an den bekannten Zellen im Inneren")
    ap.add_argument("--offen_flaeche", type=float, default=0.3, help="... und OFFEN auf mindestens diesem Anteil der Innenflaeche"); ap.add_argument("--wand", type=float, default=0.35, help="im Wandring hoechstens dieser Anteil OFFEN (sonst Sweep dort nicht belastbar)")
    ap.add_argument("--wand_innen", type=float, default=0.05, help="Gegenpruefung: hoechstens dieser Anteil Wandzellen im Inneren der Form"); ap.add_argument("--rand_wand", type=float, default=0.4, help="... und mindestens dieser Anteil des Streifens 0,3 m ausserhalb des Bogenrands ist Wand"); a = ap.parse_args()
    from element_einpassen import krone
    from scipy import ndimage as ndi
    FL = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]; FA = {F.get("id"): (i, F) for i, F in enumerate(FL)}; EL = json.load(open(os.path.join(a.ortho, "elemente.json")))["fassaden"]; erg = {}; SW = {}
    for fid, X in EL.items():
        if fid not in FA: continue
        nr, F = FA[fid]; im = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png"))
        if im is None: continue
        r = F["raster"]; zb = float(F["z"][0]); K = []; aus = []
        for e in X["elemente"]:
            if e["klasse"] != "bogen": continue
            z0 = e.get("z0_roh", e["z0"]); z1 = e.get("z1_roh", e["z1"]); ges = e.get("gesehen", 0) or 0
            if e.get("stimmen", 0) < max(a.stimmen, int(np.ceil(0.6 * ges))) or z0 - zb > a.boden or e["u1"] - e["u0"] < a.min_b or z1 - zb < a.min_h: continue
            K.append(dict(u0=e["u0"], u1=e["u1"], z0=z0, z1=z1, stimmen=e.get("stimmen", 0), gesehen=ges, score=e.get("score")))
        K.sort(key=lambda k: -k["stimmen"]); K = [k for i, k in enumerate(K) if all(min(k["u1"], o["u1"]) - max(k["u0"], o["u0"]) < 0.5 * (k["u1"] - k["u0"]) for o in K[:i])]      # Doppelte (gleiche Stelle) weg
        T = sweep_laden(a.ortho, a.objekt, nr, fid, [(k["u0"] - 1.5, k["u1"] + 1.5, zb + 0.5, k["z1"] + 1.5) for k in K]) if K else None
        if K and T is None: aus = [dict(art="bogen", kasten=[round(k[q], 2) for q in ("u0", "u1", "z0", "z1")], stimmen=k["stimmen"], gebaut=False, grund="Durchblick nicht pruefbar: kein Ebenen-Sweep (zu wenige Fotos mit Kamera oder --objekt fehlt)") for k in K]; K = []
        if K: wand, offen, nichtwand = sweep_masken(T, im, r); cv2.imwrite(os.path.join(a.ortho, f"oeffnungen_{fid}_maske.png"), np.where(offen, 255, np.where(wand, 90, 0)).astype(np.uint8))
        for k in K:
            ka = dict(u0=k["u0"], u1=k["u1"], z0=k["z0"], z1=k["z1"]); o = dict(art="bogen", kasten=[round(k[q], 2) for q in ("u0", "u1", "z0", "z1")], stimmen=k["stimmen"], gesehen=k["gesehen"], unten=round(zb, 3), wand_tiefe_m=round(T["w_wand"], 2), gebaut=False)
            wa = wand_anteil(F, o["kasten"])
            if wa is not None and wa < WAND_ANTEIL_MIN:
                o.update(koerper_vor_wand=True, wand_anteil=round(wa, 2), grund=f"Zone liegt nur zu {wa * 100:.0f} % in der Wandflaeche (Fassadenpolygon) - Koerper vor der Wand (Rundbau/Turm/Vorbau), keine Oeffnung"); aus.append(o); continue
            c = T["zelle"]; H, W = offen.shape; ys, xs = np.mgrid[0:H, 0:W]; U = T["u0"] + (xs + 0.5) * c; Z = T["z1"] - (ys + 0.5) * c; feld = (U >= ka["u0"] - 0.8) & (U <= ka["u1"] + 0.8) & (Z <= ka["z1"] + 0.8)
            kern = (U >= ka["u0"]) & (U <= ka["u1"]) & (Z <= ka["z1"]) & (Z > zb + 0.5)
            if (kern & offen).sum() * c * c < 0.3 * a.min_b * a.min_h: o["grund"] = f"kein Durchblick im Kasten (offen {(kern & offen).sum() * c * c:.1f} m2) - geschlossenes Bogenfeld/Tuer/Blendbogen oder glatte Flaeche ohne Bildstruktur"; aus.append(o); continue
            A = form_einpassen(U[feld.any(1)][:, feld.any(0)], Z[feld.any(1)][:, feld.any(0)], wand[feld.any(1)][:, feld.any(0)], offen[feld.any(1)][:, feld.any(0)], nichtwand[feld.any(1)][:, feld.any(0)], ka, zb)
            fam = A["familie"]; p = [float(x) for x in A["p"]]; rest = A["rest"]; grund = []; o["lage_sweep"] = dict(form=fam, p=[round(x, 3) for x in p])
            if a.objekt:                                               # Feinlage: Fotokanten auf der ECHTEN Wandebene (Sweep-Tiefe), 2 cm
                D, G, nfo = kanten_auf_ebene(a.objekt, F, fid, (ka["u0"] - 1.0, ka["u1"] + 1.0, zb, ka["z1"] + 1.0), T["w_wand"], os.path.join(a.ortho, "oeffnungen_tiefe"))
                if len(D) >= 50:
                    o["kanten"] = dict(punkte=int(len(D)), fotos=nfo, ebene_w=round(T["w_wand"], 2), familien={})
                    for fam_ in A["alle_familien"]:                   # jede Familie von ihrer Sweep-Lage aus verfeinern; es gilt die, deren Kurve danach am besten auf Fotokanten liegt
                        q_, s0, s1, ja, nb_ = kanten_verfeinern(D, G, fam_, A["alle_familien"][fam_]["p"], zb); o["kanten"]["familien"][fam_] = dict(p=[round(x, 3) for x in q_], stuetze_vor=s0, stuetze_nach=s1, stuetze_verschoben=nb_, uebernommen=ja)
                    bf = max(o["kanten"]["familien"], key=lambda q: o["kanten"]["familien"][q]["stuetze_nach"] if o["kanten"]["familien"][q]["uebernommen"] else -1); kf_ = o["kanten"]["familien"][bf]
                    if kf_["uebernommen"]: fam, p = bf, [float(x) for x in kf_["p"]]; o["kanten"]["gewaehlt"] = bf
                else: o["kanten"] = dict(punkte=int(len(D)), fotos=nfo, hinweis="zu wenige Fotokanten auf der Wandebene - Lage aus dem Sweep")
            db = durchblick(T, wand, offen, fam, p, zb); uc, w, zs = p[:3]; h = w / 2 if fam == "rund" else p[3]
            if rest["wand_innen"] > a.wand_innen: grund.append(f"Wand im Inneren der Form ({rest['wand_innen'] * 100:.0f} %)")
            if rest["rand_wand"] < a.rand_wand: grund.append(f"Bogenrand nur zu {rest['rand_wand'] * 100:.0f} % von Wand begrenzt - Form nicht belegt")
            o["_nur_form"] = bool(grund); SW[fid] = (T, wand, offen, zb)
            if db["offen_innen"] is None or db["offen_innen"] < a.offen or db["offen_flaeche_innen"] < a.offen_flaeche: grund.append(f"kein Durchblick im Inneren (offen {db['offen_innen']}, Flaeche {db['offen_flaeche_innen']})")
            if db["offen_wand"] is None or db["offen_wand"] > a.wand: grund.append(f"Wand daneben nicht deckungsgleich (offen {db['offen_wand']}) - Sweep hier nicht belastbar")
            if T["rand"]: grund.append("Wandtiefe am Rand des Suchbereichs - Sweep nicht belastbar")
            if zs + h - zb < a.min_h or w < a.min_b: grund.append(f"zu klein fuer eine Bogenoeffnung am Boden ({w:.2f} x {zs + h - zb:.2f} m)")
            o.update(form=fam, u=round(uc, 3), breite=round(w, 3), kaempfer=round(zs, 3), scheitel=round(zs + h, 3), rest={q: round(v, 3) for q, v in rest.items()}, familien=A["alle_familien"],
                     durchblick=db, gebaut=not grund, grund="; ".join(grund), _p=p); o["_nur_form"] = o["_nur_form"] and len(grund) <= 2 and all(g_.startswith(("Wand im Inneren", "Bogenrand")) for g_ in grund); aus.append(o)
        erg[fid] = dict(o=F["o"], d=F["d"], n=F["n"], oeffnungen=aus, fotos=X.get("fotos", [])[:4])
    # Durchfahrt: Gegenstueck auf der Gegenseite (Normalen entgegengesetzt, Mitten liegen quer hoechstens eine halbe Breite auseinander)
    for fid, A in erg.items():
        oa, da, na = (np.array(A[q], float) for q in ("o", "d", "n"))
        for x in A["oeffnungen"]:
            if not x.get("gebaut"): continue
            x.update(durchfahrt=False, tiefe_m=a.nische, annahmen=[f"ANNAHME: Tiefe {a.nische} m (kein Gegenstueck auf der Gegenseite gefunden/gesehen)", "ANNAHME: Kreisbogen der Formfamilie, Gewaende ohne Profil"])
            for gid, B_ in erg.items():
                ob, db_, nb = (np.array(B_[q], float) for q in ("o", "d", "n"))
                if gid == fid or na @ nb > -0.9: continue
                dicke = float(-(ob - oa) @ na)
                if dicke <= 0.5: continue
                for y in B_["oeffnungen"]:
                    if y.get("gebaut"):                               # beide Seiten gemessen: jede schneidet ihren Querschnitt bis zur Mitte
                        quer = float((ob + y["u"] * db_ - oa) @ da - x["u"])
                        if abs(quer) <= 0.5 * max(x["breite"], y["breite"]):
                            x.update(durchfahrt=True, gegen=gid, versatz_quer_m=round(quer, 2), tiefe_m=round(dicke / 2 + 0.05, 3), annahmen=[f"ANNAHME: Durchfahrt - Querschnitt dieser Seite gilt bis zur Gebaeudemitte ({dicke / 2:.2f} m), Gegenseite {gid} schneidet ihren eigenen", "ANNAHME: Kreisbogen der Formfamilie, Gewaende ohne Profil, Gewoelbe nicht gemessen"])
                    elif y.get("_nur_form") and gid in SW and not x.get("durchfahrt"):      # Gegenseite: Bogen erkannt, Durchblick da, aber Form dort nicht messbar (Baum, Vorbau) -> Durchblick an der durchprojizierten Form pruefen
                        ug = float((oa + x["u"] * da - ob) @ db_); pg = [ug] + [float(q) for q in x["_p"][1:]]; k = y["kasten"]; dbg = durchblick(SW[gid][0], SW[gid][1], SW[gid][2], x["form"], pg, SW[gid][3])
                        deck = (min(ug + x["breite"] / 2, k[1]) - max(ug - x["breite"] / 2, k[0])) / x["breite"]
                        if deck >= 0.6 and dbg["offen_innen"] is not None and dbg["offen_innen"] >= a.offen and dbg["offen_flaeche_innen"] >= a.offen_flaeche:
                            x.update(durchfahrt=True, gegen=gid, tiefe_m=round(dicke + 0.6, 3), gegen_durchblick=dbg, gegen_deckung=round(deck, 2), annahmen=[f"ANNAHME: Durchfahrt mit DIESEM Querschnitt gerade durch das ganze Gebaeude ({dicke:.2f} m) - auf der Gegenseite {gid} ist der Bogen erkannt ({y['stimmen']} Stimmen) und der Durchblick belegt ({dbg['offen_innen'] * 100:.0f} %), die Bogenform dort aber nicht messbar ({y['grund']})", "ANNAHME: Kreisbogen der Formfamilie, Gewaende ohne Profil, Gewoelbe nicht gemessen"])
                            y["hinweis"] = f"Oeffnung entsteht durch die Durchfahrt von {fid} (eigene Form nicht messbar)"
    for fid, A in erg.items():                                              # Bild
        if not A["oeffnungen"]: print(f"{fid}: kein Bogenkandidat am Boden"); continue
        F = FA[fid][1]; r = F["raster"]; zl = r["zelle"]; im = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png")); f_ = max(1, int(round(3 * zl / 0.05))); im = cv2.resize(im, None, fx=f_, fy=f_, interpolation=cv2.INTER_NEAREST)
        def P(u, z): return int((u - r["u0"]) / zl * f_), int((r["z1"] - z) / zl * f_)
        for x in A["oeffnungen"]:
            k = x["kasten"]; cv2.rectangle(im, P(k[0], k[3]), P(k[1], k[2]), (0, 200, 255), 1)
            if "_p" not in x: cv2.putText(im, "verworfen", P(k[0], k[3] + 0.2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1); continue
            p = x.pop("_p"); x.pop("_nur_form", None); kr = krone(x["form"], p, 80); far = (0, 255, 0) if x["gebaut"] else (0, 0, 255)
            pts = [P(p[0] - p[1] / 2, x["unten"])] + [P(u, z) for u, z in kr] + [P(p[0] + p[1] / 2, x["unten"])]; cv2.polylines(im, [np.array(pts, np.int32)], False, far, 2)
            cv2.putText(im, f"{x['form']} b{x['breite']:.2f} s{x['scheitel']:.2f}" + (" DURCHFAHRT" if x.get("durchfahrt") else ""), P(p[0] - p[1] / 2, x["scheitel"] + 0.3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, far, 1)
        cv2.imwrite(os.path.join(a.ortho, f"oeffnungen_{fid}.jpg"), im)
        print(f"{fid}: {sum(1 for x in A['oeffnungen'] if x.get('gebaut'))} Bogenoeffnung(en) gebaut, {sum(1 for x in A['oeffnungen'] if not x.get('gebaut'))} verworfen")
        for x in A["oeffnungen"]:
            print(f"   {'GEBAUT   ' if x.get('gebaut') else 'VERWORFEN'} " + (f"{x['form']} u {x['u']:.2f} Breite {x['breite']:.2f} Kaempfer {x['kaempfer']:.2f} Scheitel {x['scheitel']:.2f} | Wand innen {x['rest']['wand_innen']} Rand an Wand {x['rest']['rand_wand']} | Durchblick innen {x['durchblick']['offen_innen']} (Flaeche {x['durchblick']['offen_flaeche_innen']}) Wand {x['durchblick']['offen_wand']} | Kanten {x.get('kanten')}"
                  + (f" | DURCHFAHRT mit {x['gegen']}, Tiefe {x['tiefe_m']} m" if x.get("durchfahrt") else "") if "form" in x else f"Kasten {x['kasten']}") + (f" | {x['grund']}" if x.get("grund") else "") + (f" | {x['hinweis']}" if x.get("hinweis") else ""))
    aus = a.aus or os.path.join(a.ortho, "oeffnungen.json"); json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False); print("->", aus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
