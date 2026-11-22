#!/usr/bin/env python3
"""teil_fotoform.py - FORMPRUEFUNG JE BAUTEIL GEGEN DIE EINZELFOTOS (Regel 9d b, L-KR24).

Warum (Nutzer-Sichtfunde 10.11.): Gauben (Dachueberstand, fehlende Wangenfenster) und Balkon (laeuft bis an Erker 2, in echt Ende + Ruecksprung)
waren falsch, ohne dass der Kreis es merkte: das Kantengitter hat an den Gauben 0 Punkte -> Guete = nur Wolkenbeleg; die Wolke sieht steile
Wangen nicht; Fehlteile kommen nur aus dem Gitter. Hier dagegen direkt am Foto, je Teil:

  1. foto_diff.py (Raster, GPU) je kalibriertem Foto mit Bewertungsmaske = ganzes Bild -> Kostenkarte: Modellkanten mkp, Fotokanten fkp und je Pixel
     der Abstand zur jeweils anderen Kantenart (dF, dM; Einheit = Kappe tol 0,35 m).
  2. Jedes Teil allein EXAKT gerastert (render_kern, GPU) und mit der Tiefe des ganzen Modells verglichen -> sichtbare Pixel des Teils (verdeckt = nicht).
  3. Im sichtbaren Teilbereich: Praezision = Anteil Modellkantenpixel mit Fotokante naeher als --schwelle x Kappe (rot = erfundene Form),
     Recall = Anteil Fotokantenpixel mit Modellkante naeher als --schwelle x Kappe (gelb = fehlende Form, z. B. Fenster in einer Wange).
  4. Brennpunkte: zusammenhaengende rote/gelbe Flecken im Teilbereich, mit Weltpunkt (Rasterposition) -> wo genau.

Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py <objekt> [--teile_dir D] [--fotos 6120,6161] [--aus bericht.json] [--bilder]
Ohne --teile_dir werden die Teile mit dem Generator (BAUTEILE_AUS) in einen Zeitordner exportiert.
Oder `tools/py tools/teil_fotoform.py ...` (torch/cv2/trimesh -> venv-seg). Weitere Optionen: --nur <teile>, --stl, --schwelle 0.4, --bilder_dir, --wolke.
Ausgaben: --aus <bericht.json> (Praezision/Recall/F1 je Teil und Foto), mit --bilder Ausschnitte nach modelle/<objekt>/audit/teil_fotoform/.
Belegt die gemeinsame GPU-Schlange (gpu_slot). Exit 0 = gelaufen (Bericht, kein Urteil; das Tor ist der Vergleich vorher/nachher).
"""
import sys, os, json, glob, argparse, tempfile, subprocess, time, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# METRIK-VERSION (Cache-Schluessel!): bei JEDER Aenderung der Bewertung hochzaehlen. bauteil_kreis.py liest die Zeile per Regex (^METRIK = "...").
# v2 = Verdeckung zusaetzlich gegen die Fotowolke (wolke_verdeckung.py); "festbereich" = --bereich_von (ROI vorher/nachher gleich) moeglich.
METRIK = "v2_wolkenverdeckung_festbereich"
# v3 (11.11., fertig gebaut, noch NICHT eingeschaltet): dmed/sigma/Kappe je Foto aus einem FESTEN Referenz-STL (foto_diff._dmed_fest) - vorher aenderte ein Umbau am Westhelm die Fotokanten
# und damit fk_px/praez UNVERAENDERTER Teile (Baldachine 0,614 -> 0,499). EINSCHALTEN (Kreis-Umstellung, durch main): Standard --sigma_fest/RCPARK_SIGMA_FEST auf "an" und METRIK = METRIK_V3 setzen.
METRIK_V3 = "v3_sigma_fest_wolkenverdeckung_festbereich"


def rahmen(stl, obj, kk):
    """Gleiche Verschiebung wie foto_diff._netz_raster (aus dem GANZEN Modell), damit Teile im Kamerarahmen liegen."""
    m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    return np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)


def waagerecht(maske, winkel=30.0):
    """Kantenpixel, deren Kantenrichtung im Bild hoechstens `winkel` Grad von waagerecht abweicht (Strukturtensor der geglaetteten Kantenmaske).
    HOEHEN-WERT (Nutzer 10.11. abends, Positivtest Helm O: 0,3 m nach oben -> Foto-F1 nur -0,010, seitlich -0,093): steile Kanten gleiten bei
    Hoehenfehlern an sich selbst entlang und bleiben 'Treffer'; nur waagerechte Kanten verraten die Hoehe - getrennt zaehlen, sonst gehen sie unter.
    ANNAHME: Bild-waagerecht ~ Welt-waagerecht (Fotos kaum gerollt, Rahmen lot2)."""
    m = cv2.GaussianBlur(maske.astype(np.float32), (0, 0), 2)
    gx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # Gradientenrichtung; waagerechte Kante = senkrechter Gradient
    return maske & (np.abs(np.cos(th)) < np.sin(np.radians(winkel)))


def senkrecht(maske, winkel=30.0):
    """Gegenstueck zu waagerecht(): Kantenpixel hoechstens `winkel` Grad von senkrecht. SEITEN-WERT (11.11., Verschiebungskontrolle Laubensockel O /
    Gauben: Seitenversatz 0,3 m aendert F1 um <= 0,002, weil waagerechte Kanten langer Teile an sich selbst entlanggleiten); nur senkrechte Kanten verraten die Seitenlage."""
    m = cv2.GaussianBlur(maske.astype(np.float32), (0, 0), 2)
    gx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # senkrechte Kante = waagerechter Gradient
    return maske & (np.abs(np.sin(th)) < np.sin(np.radians(winkel)))


def richtungen(maske, winkel=30.0):
    """(waagerecht, senkrecht) in EINEM Durchgang: der Strukturtensor th ist fuer beide gleich (vorher zweimal gerechnet) -> Ergebnis bitgleich zu waagerecht()/senkrecht()."""
    m = cv2.GaussianBlur(maske.astype(np.float32), (0, 0), 2)
    gx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy); sw = np.sin(np.radians(winkel))
    return maske & (np.abs(np.cos(th)) < sw), maske & (np.abs(np.sin(th)) < sw)


# FEINMASS (11.11., modelle/archiv/SPEC_ORNAMENT_FEINMASS.md): Nebenzahl f1_fein, Hauptzahl F1 unveraendert (eigenes Etikett METRIK_FEIN, METRIK bleibt -> Kreis-Caches bleiben gueltig).
# Grund: die Hauptzahl glaettet Kanten auf 0,18 m und ist blind fuer Rippen/Sprossen/Masswerk (Erker-Varianten: F1 0,574/0,570/0,574 bei klar verschiedenen Renderbildern).
METRIK_FEIN = "fein_v1"
FEIN_TOL_M = 0.03      # Toleranz in Metern (Kamera -> Pixel ueber die Teiltiefe)
FEIN_TIEFE_M = 0.025   # Modellkante: Tiefensprung zwischen Nachbarpixeln > max(FEIN_TIEFE_M, 1 % der Tiefe)
FEIN_NORMAL_GRAD = 25.0  # Modellkante: Normalensprung > 25 Grad (Rippe/Sprosse auf einer Flaeche)


def feinkanten_modell(d, fid, fnorm):
    """Modellkanten des Teilrasters in voller Aufloesung: Tiefensprung (inkl. Silhouette zum Hintergrund) ODER Normalensprung zwischen 4-Nachbarn.
    d: Tiefe (inf = leer), fid: Dreiecksnummer (-1 leer), fnorm: Flaechennormalen. Gibt bool-Karte (1 px breit) zurueck."""
    fin = np.isfinite(d); dd = np.where(fin, d, 0.0).astype(np.float32); K = np.zeros(d.shape, bool)
    nz = fnorm[np.clip(fid, 0, None)]   # (H,W,3)
    for sl_a, sl_b in (((slice(None), slice(0, -1)), (slice(None), slice(1, None))), ((slice(0, -1), slice(None)), (slice(1, None), slice(None)))):
        fa, fb = fin[sl_a], fin[sl_b]; da, db = dd[sl_a], dd[sl_b]
        sprung = (fa != fb) | (fa & fb & (np.abs(da - db) > np.maximum(FEIN_TIEFE_M, 0.01 * np.maximum(da, db))))
        cosw = (nz[sl_a] * nz[sl_b]).sum(-1); knick = fa & fb & (fid[sl_a] != fid[sl_b]) & (cosw < np.cos(np.radians(FEIN_NORMAL_GRAD)))
        e = sprung | knick; K[sl_a] |= e; K[sl_b] |= e
    return K


def fein_bewerten(mfm, ff, tolpx):
    """(Praezision, Recall): Anteil Modellkantenpixel mit Fotokante und Anteil Fotokantenpixel mit Modellkante innerhalb tolpx (Pixel)."""
    dtf = cv2.distanceTransform((~ff).astype(np.uint8), cv2.DIST_L2, 5); dtm = cv2.distanceTransform((~mfm).astype(np.uint8), cv2.DIST_L2, 5)
    return float((dtf[mfm] <= tolpx).mean()), float((dtm[ff] <= tolpx).mean())


def fein_gelb(mfm, ff, tolpx):
    """FEIN-GELB (SPEC_FEINSUCHE): Fotokantenpixel (voll aufgeloest) ohne Modell-Feinkante innerhalb tolpx. Nur Zusatzfeld, F1/f1_fein unberuehrt."""
    dtm = cv2.distanceTransform((~mfm).astype(np.uint8), cv2.DIST_L2, 5)
    return ff & (dtm > tolpx)


_POS_NAHE = {}


def pos_nahe(pos):
    """Weltpunkt-Karte (H,W,3) mit Luecken (nan) aufgefuellt durch den naechsten Modelltreffer (cv2.distanceTransformWithLabels); je Foto einmal (Cache nach id)."""
    k = id(pos)
    if k in _POS_NAHE: return _POS_NAHE[k][1]
    fin = np.isfinite(pos).all(2) & (np.abs(np.nan_to_num(pos)).sum(2) > 0)  # Raster ohne Treffer steht als 0,0,0
    lab = cv2.distanceTransformWithLabels((~fin).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)[1]
    ys, xs = np.nonzero(fin); lut = np.zeros((lab.max() + 1, 2), np.int64)
    zl = lab[ys, xs]; lut[zl, 0] = ys; lut[zl, 1] = xs; out = pos[lut[lab, 0], lut[lab, 1]]
    _POS_NAHE.clear(); _POS_NAHE[k] = (pos, out); return out


def feinkanten_foto(gray, roi):
    """Fotokanten in VOLLER Aufloesung ohne 0,18-m-Glaettung: Canny auf leicht geglaettetem Grau (sigma 1), Schwellen adaptiv im ROI
    (hoch = 80. Perzentil des Gradientenbetrags im ROI, tief = 0,5 x hoch). roi = bool-Karte."""
    g = cv2.GaussianBlur(gray, (0, 0), 1.0); gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)[roi]
    if mag.size < 100: return np.zeros(gray.shape, bool)
    hi = float(np.percentile(mag, 80)); hi = max(hi, 8.0)
    # Schwellen in Sobel-3x3-Einheiten (L2), dieselbe Skala wie mag
    return cv2.Canny(cv2.convertScaleAbs(g), 0.5 * hi, hi, L2gradient=True) > 0


def flecken(maske, pos, n=3, min_px=40):
    """Groesste zusammenhaengende Flecken (nach 5-px-Schliessen) mit Pixelzahl und Weltpunkt (Median der Rasterpositionen)."""
    if maske.sum() < min_px: return []
    mm = cv2.dilate(maske.astype(np.uint8), np.ones((5, 5), np.uint8))
    k, lab, st, _ = cv2.connectedComponentsWithStats(mm, 8)
    out = []
    for i in np.argsort(-st[1:, cv2.CC_STAT_AREA])[:n] + 1:
        sel = (lab == i) & maske
        if sel.sum() < min_px: continue
        p = pos[sel]; p = p[np.isfinite(p).all(1)]
        out.append({"px": int(sel.sum()), "xyz": np.round(np.median(p, 0), 2).tolist() if len(p) else None,
                    "bbox_px": [int(st[i, 0]), int(st[i, 1]), int(st[i, 2]), int(st[i, 3])]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir"); ap.add_argument("--fotos")
    ap.add_argument("--stl"); ap.add_argument("--schwelle", type=float, default=0.4, help="Anteil der Kappe (0,35 m): 0,4 = 0,14 m")
    ap.add_argument("--min_px", type=int, default=150, help="Mindestzahl Kantenpixel je Teil und Foto, sonst nicht beurteilbar")
    ap.add_argument("--sigma_fest", choices=["an", "aus"], default=os.environ.get("RCPARK_SIGMA_FEST", "aus"), help="dmed/sigma je Foto aus Referenz-STL (Metrik v3, Standard) statt aus dem aktuellen Modell (v2)")
    ap.add_argument("--sigma_dir", default=os.environ.get("RCPARK_SIGMA_DIR"), help="Ordner mit ref.stl und dmed_*.json (Standard /media/oem/scan/rc-park_tmp/fotoform_cache/sigma_<objekt>)")
    ap.add_argument("--stoermaske", choices=["an", "aus"], default=os.environ.get("RCPARK_STOERMASKE", "aus"),
                    help="Stoermaske (tools/foto_stoermaske.py: Menschen/Fahrzeuge/Schilder/Moebel/Pflanzen/Fahnen): Foto- UND Modellkantenpixel in der Maske zaehlen nicht. Standard aus = bitgleich zum Ist. Auch RCPARK_STOERMASKE=an")
    ap.add_argument("--stoermaske_dir", default=os.environ.get("RCPARK_STOERMASKE_DIR"), help="Maskenordner (Standard /media/oem/scan/rc-park_tmp/stoermaske); Dateien <dir>/<objekt>/<foto>.png")
    ap.add_argument("--fein", choices=["an", "aus"], default=os.environ.get("RCPARK_FEIN", "an"), help="Nebenzahl f1_fein (voll aufgeloeste Kanten, Hauptzahl F1 unveraendert); auch RCPARK_FEIN=aus")
    ap.add_argument("--fein_n", type=int, default=5, help="SPEC_FEINSUCHE: Zahl der groessten Fein-Fehlflecken je Teil und Foto (Standard 5 war an 32/36 Fotos ausgeschoepft: kleinste Fleck ~1000 px)"); ap.add_argument("--fein_min_px", type=int, default=30)
    ap.add_argument("--fein_rand_m", type=float, default=0.0, help="SPEC_FEINSUCHE: > 0 = Zusatzfeld flecken_fein_rand (Feinkanten bis diesen Abstand in METERN ausserhalb der Modellsilhouette, z. B. Drachen vor Himmel; Weltpunkt = naechster Modelltreffer); 0 = aus, Hauptzahlen unberuehrt")
    ap.add_argument("--aus"); ap.add_argument("--bilder", action="store_true", help="je Teil+Foto Ausschnitt mit gruen/rot/gelb nach audit/teil_fotoform/")
    ap.add_argument("--nur", help="nur diese Teile (Komma), z. B. das Kreis-Ziel"); ap.add_argument("--etikett", default="", help="Zusatz im Bildnamen (vorher/nachher)")
    ap.add_argument("--bilder_dir", help="Bilder hierhin statt modelle/<objekt>/audit/teil_fotoform (Kreis: Datenplatte, nicht ins Repo)")
    ap.add_argument("--wolke_verdeckung", choices=["an", "aus"], default=os.environ.get("RCPARK_WOLKE_VERDECKUNG", "an"),
                    help="Fotowolken-Verdeckung (tools/wolke_verdeckung.py, Metrik v2): Teilpixel hinter gestuetzter Wolke gelten als verdeckt. Auch RCPARK_WOLKE_VERDECKUNG=aus")
    ap.add_argument("--wolke", help="Fotowolke (npy, Rahmen = Kamerarahmen); Standard objekt.json kreis.wolke, sonst lot2-Wolke")
    ap.add_argument("--wolke_abs", type=float, default=0.5, help="Verdeckung ab Tiefenunterschied > max(abs, rel x Teiltiefe) [m]"); ap.add_argument("--wolke_rel", type=float, default=0.05)
    ap.add_argument("--wolke_schliess", type=int, default=int(os.environ.get("RCPARK_WOLKE_SCHLIESS", "10")), help="Schliessradius in Zellen (Luecken zwischen verdeckenden Wolkenpunkten fuellen)")
    ap.add_argument("--bereich_von", help="Teile-Verzeichnis VORHER (STLs gleichen Namens): Teilbereich (ROI) = Vereinigung aus vorher- und nachher-Teil, Recall zaehlt Fotokanten in der Vereinigung "
                    "(Schrumpf-Falle: gekuerztes Teil -> weniger Fotokanten im Bereich -> F1 steigt trivial). Verdeckung des Vorher-Teils gegen das NACHHER-Modell (ANNAHME: Verdecker unveraendert)")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    stl = a.stl or os.path.join(R0, obj["stl"])
    td = a.teile_dir
    if not td:
        td = tempfile.mkdtemp(prefix="tff_")
        subprocess.run(obj["generator"], shell=True, cwd=R0, env=dict(os.environ, BAUTEILE_AUS=td), check=True, capture_output=True)
    teile = sorted(glob.glob(os.path.join(td, "*.stl")))
    if a.nur: teile = [p for p in teile if os.path.basename(p)[:-4] in a.nur.split(",")]   # Kreis-Tor: nur das Ziel-Teil (Verdeckung trotzdem gegen das ganze Modell)
    # PHANTOM (11.11., Foto-Tor fuer NEUE Teile): ein --nur-Teil, das es im Vorher-Stand nicht gibt, aber in --bereich_von (Nachher-Teile), wird im
    # Bildbereich gemessen, den es NACHHER einnaehme (sichtbar vor dem Vorher-Modell); Modellkanten = Vorher-Modell. Bestehende Teile unveraendert.
    phantom = []
    if a.nur and a.bereich_von:
        da = {os.path.basename(p)[:-4] for p in teile}
        for nm in a.nur.split(","):
            pb = os.path.join(a.bereich_von, nm + ".stl")
            if nm not in da and os.path.exists(pb): teile.append(pb); phantom.append(nm)
    fotos = a.fotos.split(",") if a.fotos else sorted(os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json")))
    bd = a.bilder_dir or os.path.join(os.path.dirname(objp), "audit", "teil_fotoform"); os.makedirs(bd, exist_ok=True)
    import hashlib, time
    erg = {"objekt": a.objekt, "stl_sha": hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16], "bilder_dir": bd, "schwelle_m": round(a.schwelle * 0.35, 3), "fotos": {}, "teile": {}}
    # METRIK-VERSION (Cache-Schluessel!): Formlisten verschiedener Metrik duerfen NIE verglichen werden (bauteil_kreis/fotoform_auffrischen pruefen 'metrik').
    VERD = None
    if a.wolke_verdeckung == "an":
        import wolke_verdeckung as WV
        wp = a.wolke or obj.get("kreis", {}).get("wolke") or "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy"
        if os.path.exists(wp): VERD = WV.Verdecker(np.load(wp, mmap_mode="r")); erg["wolke"] = wp
        else: print("WARNUNG: Wolke fehlt, Verdeckung aus:", wp, flush=True)
    SIG = None
    if a.sigma_fest == "an":
        if os.environ.get("TFF_LANGSAM") == "1": raise SystemExit("TFF_LANGSAM=1 geht nur mit --sigma_fest aus")
        sd = a.sigma_dir or os.path.join("/media/oem/scan/rc-park_tmp/fotoform_cache" if os.path.isdir("/media/oem/scan") else tempfile.gettempdir(), "sigma_" + a.objekt); os.makedirs(sd, exist_ok=True)
        rp = os.path.join(sd, "ref.stl")
        if not os.path.exists(rp):   # erster Lauf friert das aktuelle Haupt-STL ein (atomar; wer zuerst kommt, gewinnt - danach nie wieder aendern)
            tp_ = rp + f".{os.getpid()}.tmp"; _sh0 = __import__("shutil"); _sh0.copyfile(stl, tp_)
            try: os.link(tp_, rp)
            except FileExistsError: pass
            os.remove(tp_)
        SIG = dict(dir=sd, ref=rp, ref_sha=hashlib.sha256(open(rp, "rb").read()).hexdigest()[:16]); erg["sigma_fest"] = SIG["ref_sha"]
    erg["metrik"] = METRIK_V3 if SIG else METRIK; erg["wolke_verdeckung"] = "an" if VERD is not None else "aus"   # aus = Vergleichslauf, nie mit "an"-Listen mischen
    FEIN = a.fein == "an"
    if FEIN: erg["metrik_fein"] = METRIK_FEIN
    SM_ON = a.stoermaske == "an"
    if SM_ON:
        import foto_stoermaske as FS
        erg["metrik"] += "_stoermaske"; erg["stoermaske"] = a.stoermaske_dir or FS.CACHE; erg["stoermaske_fehlt"] = []   # eigene Metrik-Version: nie mit Listen ohne Maske mischen
    if phantom: erg["phantom"] = phantom   # nur Bereich des Nachher-Teils, Vorher-Modell ohne dieses Teil
    if a.bereich_von: erg["bereich_von"] = a.bereich_von   # F1 in Vereinigungsbereich: NICHT mit Listen ohne dieses Feld vergleichen/mischen (nur vorher/nachher-Paar eines Tors)
    _td = "/media/oem/scan/rc-park_tmp" if os.path.isdir("/media/oem/scan") else None   # nie Root-Platte (10.11.: 76 Reste = 4,1 GB in /tmp, Root 5 GB)
    if _td: os.makedirs(_td, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="tff_k_", dir=_td)
    import atexit, shutil as _sh; atexit.register(_sh.rmtree, tmp, True)   # auch bei Abbruch per Ausnahme aufraeumen
    TM = {}; TV = {}
    def foto_bewerten(nr):
            kp = FF.k_datei(objp, obj, R0, nr)
            if not kp: return
            K = json.load(open(kp)); kk = K["kamera"]
            bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*")) or glob.glob(os.path.join(R0, obj["fotos_dir"], nr + ".*"))   # 22.11.2026: Kettenobjekte heissen <foto>.jpg (K-<foto>.json), nicht <nr>_<name> - sonst still 0 Teile beurteilt
            if not bild: erg["fotos"][nr] = "Foto nicht gefunden"; return
            im0, K = FD.foto_skalieren(cv2.imread(bild[0]), K); kk = K["kamera"]; H, W = im0.shape[:2]; im0_voll = im0   # RCPARK_FOTO_SKALA (Standard 1 = unveraendert)
            voll = os.path.join(tmp, f"voll_{W}x{H}.png"); cv2.imwrite(voll, np.full((H, W), 255, np.uint8)) if not os.path.exists(voll) else None
            npz = os.path.join(tmp, f"k_{nr}.npz")
            # SCHNELLWEG (10.11. abends, bitgleich geprueft - TFF_LANGSAM=1 = alter Weg, TFF_PRUEF=1 = beide Wege vergleichen): foto_diff gibt Raster und
            # Kostenkarte im Speicher zurueck und hoert nach der Kostenkarte auf (Bericht/Bilder/zweites Vollraster/npz entfallen).
            schnell = os.environ.get("TFF_LANGSAM") != "1"
            FD._RUECK = ({"nur_kosten": os.environ.get("TFF_PRUEF") != "1", **({"sigma_fest": SIG} if SIG else {})}) if schnell else None
            try:
                FD.main([objp, nr, "--stl", stl, "--bewertung-maske", voll, "--kostenkarte", npz, "--aus", tmp])
            except BaseException as ex:
                if 'out of memory' in str(ex).lower(): raise
                erg["fotos"][nr] = f"foto_diff fehlgeschlagen: {str(ex)[:120]}"; return
            finally:
                rueck, FD._RUECK = FD._RUECK, None
            if schnell and rueck and "kosten" in rueck:
                Z = rueck["kosten"]
            elif os.path.exists(npz): Z = np.load(npz)
            else: erg["fotos"][nr] = "keine Kostenkarte (zu wenig Kanten)"; return
            mkp, fkp, dF16, dM16 = Z["mkp"], Z["fkp"], Z["dF"], Z["dM"]
            # Hoehen-Wert: Abstaende nur zwischen WAAGERECHTEN Kanten, gleiche Einheit wie dF (Kappe in Pixeln aus dF zurueckgerechnet; Median ueber das GANZE Bild -> nicht beschneidbar)
            _dtF = Z["dFp"] if (hasattr(Z, "keys") and "dFp" in Z) else cv2.distanceTransform((~fkp).astype(np.uint8), cv2.DIST_L2, 5); _dF = dF16.astype(np.float32); _s = (_dF > 0.05) & (_dF < 0.95) & mkp
            kap = float(np.median(_dtF[_s] / _dF[_s])) if _s.sum() > 20 else None
            del _dtF, _dF, _s
            R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
            tr = rahmen(stl, obj, kk)
            zc = None
            if VERD is not None and "rahmen_verschiebung" in kk:   # Wolke nur im Kamerarahmen (K-Datei traegt ihren Rahmen), sonst wie bisher
                ZL = max(2, int(round(12 * float(os.environ.get("RCPARK_FOTO_SKALA") or 1.0)))); zc = VERD.zkarte(R, t, f, cx, cy, W, H, zelle=ZL)
            if schnell and rueck and "depth" in rueck and os.environ.get("TFF_PRUEF") != "1":
                dv, pos = rueck["depth"], rueck["pos"]   # Vollraster aus foto_diff (gleiches Netz, gleiche Kamera) statt zweitem Raster; pos bleibt auf der GPU, nur der Ausschnitt geht zur CPU
            else:
                mv = trimesh.load(stl, force="mesh"); mv.apply_scale(obj.get("stl_massstab", 87) / 1000.0); mv.apply_translation(tr)
                dv, _, pos = RK.dreiecke_rastern(mv, R, t, f, cx, cy, W, H)
                if schnell and rueck and "depth" in rueck:   # TFF_PRUEF: Schnellweg muss bitgleich sein
                    print(f"PRUEF {nr}: depth gleich {np.array_equal(dv, rueck['depth'], equal_nan=True)}, pos gleich {np.array_equal(pos, rueck['pos'].cpu().numpy(), equal_nan=True)}", flush=True)
            erg["fotos"][nr] = {"mk_px": int(mkp.sum()), "fk_px": int(fkp.sum()), **({k: round(v, 9) for k, v in rueck["dmed_info"].items()} if (rueck and rueck.get("dmed_info")) else {})}
            # ---- Durchlauf 1: sichtbare Pixel je Teil (nur im Rasterausschnitt des Teils gespeichert) ----
            sichtbar = {}; ymin = xmin = 1 << 30; ymax = xmax = -1
            for tp in teile:
                name = os.path.basename(tp)[:-4]
                if name not in TM:
                    m = trimesh.load(tp, force="mesh")
                    if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0: TM[name] = None; continue
                    m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); TM[name] = m
                if TM[name] is None: continue
                m = TM[name].copy(); m.apply_translation(tr)
                dp = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H, nur_tiefe=True)[0]
                fin = np.isfinite(dp); vis = fin & (dp <= dv * 1.003 + 0.03)
                vw = 0; vd = None
                if zc is not None:
                    vd = VERD.verdeckt(zc, dp, ZL, a.wolke_abs, a.wolke_rel, a.wolke_schliess) & vis; vw = int(vd.sum()); vis &= ~vd   # Fotowolke vor dem Teil = verdeckt
                finu = fin
                if a.bereich_von:   # Vereinigung mit dem sichtbaren Bereich des Vorher-Teils (gleicher Bildbereich vorher/nachher)
                    if name not in TV:
                        pv = os.path.join(a.bereich_von, name + ".stl"); mv_ = trimesh.load(pv, force="mesh") if os.path.exists(pv) else None
                        if isinstance(mv_, trimesh.Trimesh) and len(mv_.faces): mv_.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
                        else: mv_ = None
                        TV[name] = mv_
                    if TV[name] is not None:
                        mv2 = TV[name].copy(); mv2.apply_translation(tr); dpv = RK.dreiecke_rastern(mv2, R, t, f, cx, cy, W, H, nur_tiefe=True)[0]
                        finv = np.isfinite(dpv); visv = finv & (dpv <= dv * 1.003 + 0.03)
                        if zc is not None: visv &= ~VERD.verdeckt(zc, dpv, ZL, a.wolke_abs, a.wolke_rel, a.wolke_schliess)
                        vis = vis | visv; finu = fin | finv
                if vis.sum() < 200: continue
                ry, rx = np.flatnonzero(finu.any(1)), np.flatnonzero(finu.any(0)); by0, by1, bx0, bx1 = int(ry[0]), int(ry[-1]) + 1, int(rx[0]), int(rx[-1]) + 1   # Rasterausschnitt des Teils (vis liegt darin)
                mf = None
                if FEIN:   # Feinkanten des Teils (eigener Voll-Raster mit Dreiecksnummern; Tiefe bitgleich zum nur_tiefe-Raster)
                    d2, fid2, _ = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H)
                    fn = np.asarray(TM[name].face_normals, np.float32)
                    mf = feinkanten_modell(d2[by0:by1, bx0:bx1], fid2[by0:by1, bx0:bx1], fn); del d2, fid2
                    zt = float(np.median(dp[by0:by1, bx0:bx1][vis[by0:by1, bx0:bx1]])); mf = (mf, FEIN_TOL_M * f / max(zt, 1e-3))
                sichtbar[name] = dict(mf=mf, vis=vis[by0:by1, bx0:bx1].copy(), vd=vd[by0:by1, bx0:bx1].copy() if (a.bilder and zc is not None) else None, vw=vw, box=(by0, by1, bx0, bx1))
                ymin, ymax, xmin, xmax = min(ymin, by0), max(ymax, by1), min(xmin, bx0), max(xmax, bx1)
            if not sichtbar: return
            # ---- gemeinsamer Ausschnitt C: alle Teile + Rand (Dilatation 3, Richtungsfilter ~22, Abstandskappe kap, Bildrand 40) ----
            pad = max(int((kap or 0) * 1.1) + 4, 60) + 30
            cy0, cy1, cx0, cx1 = max(0, ymin - pad), min(H, ymax + pad), max(0, xmin - pad), min(W, xmax + pad)
            C = (slice(cy0, cy1), slice(cx0, cx1))
            SMC = None
            if SM_ON:
                _sm = FS.maske_laden(a.objekt, nr, W, H, a.stoermaske_dir or FS.CACHE)
                if _sm is None: erg["stoermaske_fehlt"].append(nr); print(f"WARNUNG: keine Stoermaske fuer {nr} (Foto unmaskiert gemessen)", flush=True)
                else: SMC = _sm[C]
            gray_c = cv2.cvtColor(FF.foto_entzerren(im0_voll, kk)[0][C], cv2.COLOR_BGR2GRAY) if FEIN else None   # Fotokanten wie foto_diff aus dem ENTZERRTEN Foto (Renderer = Lochkamera)
            mkp, fkp = mkp[C], fkp[C]; dF, dM = dF16[C].astype(np.float32), dM16[C].astype(np.float32); im0 = im0[C]
            pos = pos[cy0:cy1, cx0:cx1]; pos = pos.cpu().numpy() if hasattr(pos, "cpu") else np.ascontiguousarray(pos)
            if kap:
                mkh, mkv = richtungen(mkp); fkh, fkv = richtungen(fkp)
                dFh = np.minimum(cv2.distanceTransform((~fkh).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
                dMh = np.minimum(cv2.distanceTransform((~mkh).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
                dFv = np.minimum(cv2.distanceTransform((~fkv).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
                dMv = np.minimum(cv2.distanceTransform((~mkv).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
            Hc, Wc = mkp.shape
            for name, sv in sichtbar.items():
                by0, by1, bx0, bx1 = sv["box"]; vis = np.zeros((Hc, Wc), bool); vis[by0 - cy0:by1 - cy0, bx0 - cx0:bx1 - cx0] = sv["vis"]; vw = sv["vw"]
                ms = cv2.dilate(vis.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
                if SMC is not None: ms &= ~SMC   # Stoermaske: Pixel in der Maske zaehlen weder als Foto- noch als Modellkante
                mk_t, fk_t = mkp & ms, fkp & ms
                # FEHLENDES TEIL IM FESTBEREICH (11.11., Dienste a030758: vorher nur 2 von 9 Fotos beurteilt, weil vor glatter Wand kaum Modellkanten):
                # mit --bereich_von zaehlt ein Foto mit genug FOTOkanten auch ohne Modellkanten - Recall ~0 senkt F1, Praezision traegt mit Gewicht mk_px (0) nichts bei.
                if fk_t.sum() < a.min_px or (mk_t.sum() < a.min_px and not a.bereich_von): continue
                ok_m, ok_f = dF[mk_t] < a.schwelle, dM[fk_t] < a.schwelle
                rot = mk_t & (dF >= a.schwelle); gelb = fk_t & (dM >= a.schwelle)
                if kap:
                    mh_t, fh_t = mkh & ms, fkh & ms
                    hw = {"praez_h": round(float((dFh[mh_t] < a.schwelle).mean()), 3), "recall_h": round(float((dMh[fh_t] < a.schwelle).mean()), 3),
                          "mkh_px": int(mh_t.sum()), "fkh_px": int(fh_t.sum())} if (mh_t.sum() >= 50 and fh_t.sum() >= 50) else {}
                    mv_t, fv_t = mkv & ms, fkv & ms
                    if mv_t.sum() >= 50 and fv_t.sum() >= 50:
                        hw.update({"praez_v": round(float((dFv[mv_t] < a.schwelle).mean()), 3), "recall_v": round(float((dMv[fv_t] < a.schwelle).mean()), 3),
                                   "mkv_px": int(mv_t.sum()), "fkv_px": int(fv_t.sum())})
                else: hw = {}
                fl_r, fl_g = flecken(rot, pos), flecken(gelb, pos)
                for fl_ in fl_r + fl_g: fl_["bbox_px"][0] += cx0; fl_["bbox_px"][1] += cy0   # zurueck in Bildkoordinaten des ganzen Fotos
                e = {**hw, "praez": round(float(ok_m.mean()), 3) if ok_m.size else 0.0, "recall": round(float(ok_f.mean()), 3), "mk_px": int(mk_t.sum()), "fk_px": int(fk_t.sum()), "sicht_px": int(vis.sum()), "wolke_verd_px": vw,
                     "rot": fl_r, "gelb": fl_g}
                if FEIN and sv["mf"] is not None:
                    mfb, tolpx = sv["mf"]; mfm = np.zeros((Hc, Wc), bool); mfm[by0 - cy0:by1 - cy0, bx0 - cx0:bx1 - cx0] = mfb
                    mfm &= ms; ff = feinkanten_foto(gray_c, ms) & ms
                    if SMC is not None: mfm &= ~SMC; ff &= ~SMC
                    if mfm.sum() >= 50 and ff.sum() >= 50:
                        pf, rf = fein_bewerten(mfm, ff, tolpx)
                        e.update({"praez_f": round(pf, 3), "recall_f": round(rf, 3), "f1_f": round(2 * pf * rf / (pf + rf), 3) if pf + rf else 0.0,
                                  "mkf_px": int(mfm.sum()), "fkf_px": int(ff.sum()), "tol_px": round(tolpx, 2)})
                        fl_fg = flecken(fein_gelb(mfm, ff, tolpx), pos, n=a.fein_n, min_px=a.fein_min_px)   # groesste Feinkanten-Fehlstellen mit Weltpunkt auf der Modellflaeche
                        for fl_ in fl_fg: fl_["bbox_px"][0] += cx0; fl_["bbox_px"][1] += cy0
                        e["flecken_fein"] = fl_fg
                        if a.fein_rand_m > 0:   # Randfleck: Feinkanten auch ausserhalb der 3-px-Silhouettenzone (Metergroesse aus Kamera: Rand = fein_rand_m * f / Teiltiefe)
                            rpx = max(3, int(round(a.fein_rand_m * tolpx / FEIN_TOL_M))); ms2 = cv2.dilate(vis.astype(np.uint8), np.ones((2 * rpx + 1, 2 * rpx + 1), np.uint8)) > 0
                            if SMC is not None: ms2 &= ~SMC
                            ff2 = feinkanten_foto(gray_c, ms2) & ms2
                            if SMC is not None: ff2 &= ~SMC
                            g2 = fein_gelb(mfm, ff2, tolpx) & ~ms   # nur der NEUE Randstreifen ausserhalb von ms (innen gilt flecken_fein)
                            fl2 = flecken(g2, pos_nahe(pos), n=max(8, a.fein_n // 2), min_px=a.fein_min_px)
                            for fl_ in fl2: fl_["bbox_px"][0] += cx0; fl_["bbox_px"][1] += cy0
                            e["flecken_fein_rand"] = fl2
                        if a.bilder:
                            fo = (im0 // 2).copy(); fo[ff] = (255, 160, 0); fo[mfm] = (0, 220, 0); fo[mfm & ff] = (255, 255, 255)
                            ys, xs = np.where(ms); fy0, fy1, fx0, fx1 = max(0, ys.min() - 20), min(Hc, ys.max() + 20), max(0, xs.min() - 20), min(Wc, xs.max() + 20)
                            cv2.imwrite(os.path.join(bd, f"{name}_{nr}{('_' + a.etikett) if a.etikett else ''}_fein.jpg"), fo[fy0:fy1, fx0:fx1], [cv2.IMWRITE_JPEG_QUALITY, 85])
                erg["teile"].setdefault(name, {})[nr] = e
                if a.bilder:
                    ys, xs = np.where(ms); y0, y1, x0, x1 = max(0, ys.min() - 40), min(Hc, ys.max() + 40), max(0, xs.min() - 40), min(Wc, xs.max() + 40)
                    ov = (im0 // 2).copy(); ov[ms & ~(mk_t | fk_t)] = (ov[ms & ~(mk_t | fk_t)] * 1.6).clip(0, 255).astype(np.uint8)
                    ov[mk_t & ~rot] = (0, 200, 0); ov[fk_t & ~gelb & ~mk_t] = (200, 120, 0); ov[rot] = (0, 0, 255); ov[gelb] = (0, 255, 255)
                    if zc is not None:
                        vd2 = np.zeros((Hc, Wc), bool); vd2[by0 - cy0:by1 - cy0, bx0 - cx0:bx1 - cx0] = sv["vd"]   # violett = durch Fotowolke verdeckt (nicht bewertet); = vd aus Durchlauf 1 (gleiche Formel wie vorher vd2)
                        ov[vd2] = (0.5 * ov[vd2] + 0.5 * np.array((255, 0, 160))).astype(np.uint8)
                        ys, xs = np.where(ms | vd2); y0, y1, x0, x1 = max(0, ys.min() - 40), min(Hc, ys.max() + 40), max(0, xs.min() - 40), min(Wc, xs.max() + 40)
                    cv2.imwrite(os.path.join(bd, f"{name}_{nr}{('_' + a.etikett) if a.etikett else ''}.jpg"), ov[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 85])
    TEIL = (a.aus + ".teil") if a.aus else None
    if TEIL and os.path.exists(TEIL):   # Wiederaufnahme: abgebrochener Lauf zum selben STL
        try:
            alt = json.load(open(TEIL))
            if alt.get("stl_sha") == erg["stl_sha"] and alt.get("metrik") == erg["metrik"] and alt.get("metrik_fein") == erg.get("metrik_fein"): erg["fotos"], erg["teile"] = alt["fotos"], alt["teile"]; print("Wiederaufnahme:", sum(isinstance(v, dict) for v in alt["fotos"].values()), "Fotos fertig", flush=True)
        except Exception: pass
    import torch
    for nr in fotos:
        if isinstance(erg["fotos"].get(nr), dict): continue
        for versuch in range(12):   # 10.11.: GPU-Speicher voll durch 8 Kreis-Spuren -> Abbruch nach 38 min; jetzt warten und Foto wiederholen
            try: foto_bewerten(nr); break
            except (torch.OutOfMemoryError, RuntimeError) as ex:
                if "out of memory" not in str(ex).lower(): raise
                for v in erg["teile"].values(): v.pop(nr, None)
                erg["fotos"].pop(nr, None); torch.cuda.empty_cache(); print(f"Foto {nr}: GPU-Speicher voll, Versuch {versuch + 1}, warte 60 s", flush=True); time.sleep(60)
        else: erg["fotos"][nr] = "GPU-Speicher dauerhaft voll"
        print(f"Foto {nr}: {sum(1 for v in erg['teile'].values() if nr in v)} Teile beurteilt", flush=True)
        if TEIL: json.dump(erg, open(TEIL, "w"), ensure_ascii=False)   # Zwischenstand je Foto (11:56 brach ein 38-min-Lauf am Ende ab, alles verloren)
    for name, je in erg["teile"].items():   # Mittel ueber Fotos, gewichtet mit Pixelzahl
        je = {k: v for k, v in je.items() if isinstance(v, dict) and "mk_px" in v}; erg["teile"][name] = je
        mk = sum(v["mk_px"] for v in je.values()); fk = sum(v["fk_px"] for v in je.values())
        if not mk or not fk: continue
        p = sum(v["praez"] * v["mk_px"] for v in je.values()) / mk; r = sum(v["recall"] * v["fk_px"] for v in je.values()) / fk
        je["_gesamt"] = {"praez": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "fotos": len(je)}
        ff_ = [v for v in je.values() if isinstance(v, dict) and "mkf_px" in v]   # Feinmass (Nebenzahl), gleiche Gewichtung
        mfp = sum(v["mkf_px"] for v in ff_); ffp = sum(v["fkf_px"] for v in ff_)
        if mfp and ffp:
            pfe = sum(v["praez_f"] * v["mkf_px"] for v in ff_) / mfp; rfe = sum(v["recall_f"] * v["fkf_px"] for v in ff_) / ffp
            je["_gesamt"].update({"praez_f": round(pfe, 3), "recall_f": round(rfe, 3), "f1_fein": round(2 * pfe * rfe / (pfe + rfe), 3) if pfe + rfe else 0.0, "fotos_fein": len(ff_)})
        hh = [v for v in je.values() if isinstance(v, dict) and "mkh_px" in v]   # Hoehen-Wert (waagerechte Kanten), gleiche Gewichtung
        mh = sum(v["mkh_px"] for v in hh); fh = sum(v["fkh_px"] for v in hh)
        if mh and fh:
            ph = sum(v["praez_h"] * v["mkh_px"] for v in hh) / mh; rh = sum(v["recall_h"] * v["fkh_px"] for v in hh) / fh
            je["_gesamt"].update({"praez_h": round(ph, 3), "recall_h": round(rh, 3), "f1_h": round(2 * ph * rh / (ph + rh), 3) if ph + rh else 0.0, "fotos_h": len(hh)})
        vv = [v for v in je.values() if isinstance(v, dict) and "mkv_px" in v]   # Seiten-Wert (senkrechte Kanten), gleiche Gewichtung
        mv_ = sum(v["mkv_px"] for v in vv); fv_ = sum(v["fkv_px"] for v in vv)
        if mv_ and fv_:
            pv = sum(v["praez_v"] * v["mkv_px"] for v in vv) / mv_; rv = sum(v["recall_v"] * v["fkv_px"] for v in vv) / fv_
            je["_gesamt"].update({"praez_v": round(pv, 3), "recall_v": round(rv, 3), "f1_v": round(2 * pv * rv / (pv + rv), 3) if pv + rv else 0.0, "fotos_v": len(vv)})
    if a.aus: json.dump(erg, open(a.aus, "w"), ensure_ascii=False, indent=1)
    print(f"{'Teil':30s} {'Fotos':>5s} {'Praez':>6s} {'Recall':>6s} {'F1':>6s}")
    for name, je in sorted(((k, v) for k, v in erg["teile"].items() if "_gesamt" in v), key=lambda kv: kv[1]["_gesamt"]["f1"]):
        g = je["_gesamt"]; print(f"{name:30s} {g['fotos']:5d} {g['praez']:6.3f} {g['recall']:6.3f} {g['f1']:6.3f}")
    return erg


if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("teil_fotoform")   # gemeinsame GPU-Schlange (10.11.: >2-3 gleichzeitige GPU-Pruefungen = Einbruch)
    main()
