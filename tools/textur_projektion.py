#!/usr/bin/env python3
"""textur_projektion.py - Fotofarbe auf die Modelloberflaeche projizieren und AUTOMATISCH messen, wie viel Prozent je Seite/Hoehenband wirklich Farbe haben.

Je Dreieck (Modell auf <= --kante m unterteilt, automatisch vergroebert bis <= --max-dreiecke) wird aus den kalibrierten Fotos (messprotokoll/K-<foto>.json mit
'kamera') die BESTE Kamera gewaehlt: sichtbar (Strahlentest gegen Modell + Verdecker), Blickwinkel zur Flaechennormale, Aufloesung (m/px), Kameragueterating.
Pipeline der Farbe:
  1. HIMMEL: Pixel, die die Himmelsmaske des Fotos (foto_pick.himmel_cached, Cache modelle/<objekt>/himmelsmaske/<foto>.png) trifft (+ --himmel-rand-px Rand), liefern keine
     Farbe. Ursache des Himmelblaus auf Helm/Tuermchen: Kamerafehler legt Himmelspixel auf das Dach (Strang C, 2026-11-03).
  2. ANGLEICH (Belichtung/Weissabgleich): je Quelle (Foto, Drohne) ein multiplikativer Gain je Kanal (RGB, Annahme: reine Verstaerkung im sRGB-Raum). Er wird aus den
     UEBERLAPPEN geschaetzt: in Dreiecken, die zwei Quellen sehen, gilt g_i + log c_i = g_j + log c_j; Median ueber die Dreiecke je Paar, Ausgleich nach kleinsten Quadraten
     ueber den Quellgraphen (Bezug = Foto mit der groessten Flaeche; unverbundene Quellen bleiben bei 1; Gain auf [1/gmax, gmax] begrenzt). Die Drohne ist die Bruecke
     zwischen Fotos, die sich nicht ueberlappen (Nord/Sued) - ihre eigene Farbtreue ist NICHT belegt.
  3. KONSISTENZ (Verdeckung/Laub): sehen >= 3 Fotos ein Dreieck, gilt der Median der Farben (CIELAB); Fotos mit Delta-E > --konsistenz-de gelten als Ausreisser
     (Baumlaub, Fussgaenger, Leitung) und werden verworfen. Bei 2 Fotos entscheidet die Drohnenfarbe, sonst die beste Aufloesung (als 'strittig' gezaehlt). Zusaetzlich
     LAUBFILTER: Farben mit Hue --laub-hue (Grad, Blattgruen; Kupferpatina ~150-190 Grad bleibt) und Saettigung > --laub-sat werden durch ein anderes Foto/Drohne ersetzt, sonst 'keine'.
  4. LIZENZ: jedes Dreieck bekommt die Lizenzklasse seines Fotos aus tools/lizenz_register.py (foto_klassen); Drohne = 'unfrei' (YouTube). produkt(klasse) liefert ja | bedingt | nein.
     --produkt faerbt NUR 'ja' (frei, frei_namensnennung); 'bedingt' (frei_sharealike) wird NICHT stillschweigend mitgezaehlt, sondern im Bericht als eigene Gruppe ausgewiesen
     (Flaechenanteil je Klasse, gesamt und je Seite/Hoehenband); --produkt-mit-bedingt faerbt sie ausdruecklich mit. Alles uebrige (nc, unfrei, unklar) wird grau.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/textur_projektion.py modelle/<objekt>/objekt.json [--ausgabe PFAD/praefix] [--bild sheet.jpg] [--produkt [--produkt-mit-bedingt]]
        [--drohne-ordner DIR | --ohne-drohne] [--ohne-himmel] [--ohne-angleich] [--ohne-konsistenz] [--ohne-laubfilter]
Ausgabe: <objekt>/audit/textur_abdeckung.json (Anteile Foto/Drohne/keine und Lizenzklassen je Seite x Hoehenband, Verwendbarkeit/Gain je Foto, Zaehler der Filter),
4-Seiten-Ansicht (--bild, Standard audit/textur_ansicht.jpg). Mit --ausgabe PRAEFIX zusaetzlich PRAEFIX.ply, PRAEFIX.glb (glTF-binaer) und PRAEFIX.obj (Vertexfarben).
Die Netze werden NICHT mehr nach audit/ geschrieben (35-100 MB); ohne --ausgabe entsteht keines.
ANNAHMEN (alle als Argument, keine versteckten Konstanten; Vorgaben sind Voreinstellungen, keine Messwerte):
  --rms-max-proz 3.0     Kameras mit RMS > 3 % der Bildhoehe werden NICHT benutzt (K-040: 2,6 % ist schon grob)
  --rms-gut-proz 0.5     Gewicht = 1/(1+(rms%/0,5)^2): schlechtere Kameras verlieren gegen bessere
  --kante 0.35 --max-dreiecke 1000000   Unterteilung <= 35 cm; wird bei Ueberschreitung der Dreieckszahl um 20 % je Schritt vergroebert
  --cos-min 0.25         Flaechen steiler als ~75 Grad zum Blick bekommen keine Farbe
  --himmel-rand-px 6     Rand um die Himmelsmaske (Mischpixel am Silhouettenrand)
  --gain-max 1.6 --angleich-min 200   Gain je Kanal in [1/1,6; 1,6]; Paare mit < 200 gemeinsamen Dreiecken zaehlen nicht
  --konsistenz-de 25     Delta-E (CIELAB) ab dem ein Foto als Ausreisser gilt
  --laub-hue 55,125 --laub-sat 0.25   Blattgruen (Grad / HSV-Saettigung 0-1)
GRENZEN (ehrlich):
  * Kamerafehler (RMS 50-150 px) werden zu FARBVERSATZ: Fugen/Kanten sitzen dann bis zu mehreren Dezimetern falsch (in Mauerwerk nicht sichtbar, an Uhr/Fenstern schon).
  * Verdecker sind nur Modell + Torbau-LoD2: Baeume/Leitungen werden nur ueber Konsistenz (>= 3 Fotos) bzw. Laubfilter erwischt, nicht geometrisch.
  * Der Gain gleicht Belichtung/Weissabgleich an, nicht Schatten, Tonwertkurven oder Verzeichnung; ohne Ueberlapp (und ohne Drohne) bleibt er 1.
  * 'Sichtbar' heisst nicht 'scharf': Aufloesung (m/px) je Foto steht im Bericht.
  * Lizenzklassen sind eine Einordnung nach dem Lizenztext (lizenz_register.py), keine Rechtsberatung; Auflagen (Urheber nennen, ShareAlike) stehen je Klasse im Bericht.
"""
import sys, os, re, json, glob, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lizenz_register as LR        # zentrale Lizenzklassen (frei | frei_namensnennung | frei_sharealike | nc | unfrei | unklar); gehoert nicht diesem Werkzeug

def seiten_aus_konvention(obj):
    """{'+x': 'Sued', ...} aus objekt.json seiten_konvention (erstes Wort)."""
    out = {}
    for k, v in (obj.get("seiten_konvention") or {}).items():
        m = re.match(r"\s*([A-Za-z]+)", str(v))
        if k in ("+x", "-x", "+y", "-y") and m: out[k] = m.group(1)
    return out

def modell_laden(obj, root, stl=None):
    """Wie tools/fehlteile_finden.py: Massstab, Zentrierung (huelle|achse -> nur auf z=0 setzen)."""
    import trimesh
    m = trimesh.load(stl or os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3); T_ = np.array([-c[0], -c[1], -m.bounds[0, 2]]); m.apply_translation(T_)
    m.merge_vertices(); m.metadata["verschiebung"] = T_; return m

def verdecker_laden(obj, root):
    """Nebengebaeude-Massenmodelle (objekt.json 'nebengebaeude' -> 'stl_m', im Modellrahmen, LoD2). ANNAHME: Georeferenz = Modellrahmen (bbox grenzt an die Fassade)."""
    import trimesh; L = []
    for name, e in (obj.get("nebengebaeude") or {}).items():
        p = e.get("stl_m")
        if p and os.path.exists(os.path.join(root, p)) and "front" not in name:     # 'front' ist eine feinere Fassade desselben Gebaeudes (Doppelzaehlung vermeiden)
            L.append((name, trimesh.load(os.path.join(root, p))))
    return L

def verdecker_lod2(obj, od, radius, T_):
    """GENERISCH (2026-11-04, Kaufhaus): LoD2-NACHBARGEBAEUDE als Verdecker. Ohne sie projizierte jedes Foto die angebauten Nachbarhaeuser auf die
    Brandwaende des Modells. Alle LoD2-Gebaeude im Radius ausser dem eigenen (objekt.json lod2.id, ergaenzt per objekt_rahmen.py), Polygone als Faecher."""
    import trimesh, lod2_gebaeude as LG, objekt_rahmen as OR
    obj = OR.ergaenzen(dict(obj), od)
    if not obj.get("lod2") or not obj.get("rahmen"): return []
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    V, F = [], []
    for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=radius):
        if meta.get("id") == obj["lod2"].get("id"): continue
        for _, P in polys:
            Q = np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - R["gelaende"]] + T_; b = sum(len(v) for v in V)
            V.append(Q); F += [[b, b + i, b + i + 1] for i in range(1, len(Q) - 1)]
    if not F: return []
    return [("lod2_nachbarn", trimesh.Trimesh(np.vstack(V), np.array(F), process=False))]


def bilinear(im, u, v):
    """Bilineare Farbabtastung (u,v in Pixelmitten-Koordinaten); eigene Implementierung, weil cv2.remap an 32767 Punkten scheitert."""
    H, W = im.shape[:2]; u = np.clip(u - 0.5, 0, W - 1.001); v = np.clip(v - 0.5, 0, H - 1.001); x0 = np.floor(u).astype(int); y0 = np.floor(v).astype(int); fx = (u - x0)[:, None]; fy = (v - y0)[:, None]
    a = im[y0, x0].astype(np.float32); b = im[y0, x0 + 1].astype(np.float32); c = im[y0 + 1, x0].astype(np.float32); d = im[y0 + 1, x0 + 1].astype(np.float32)
    return np.rint(a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy).astype(np.uint8)

def kameras_pruefen(obj, root, od, a):
    """Liest alle K-*.json, bewertet Verwendbarkeit. Rueckgabe: (benutzbar[dict], bericht[list])."""
    import cv2; from PIL import Image
    ben, ber = {}, []
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]; K = json.load(open(kp)); k = K.get("kamera"); e = dict(foto=nr)
        fp = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
        if not k: e.update(benutzt=False, grund="keine geloeste Kamera in K-%s.json" % nr); ber.append(e); continue
        if not fp: e.update(benutzt=False, grund="Fotodatei fehlt"); ber.append(e); continue
        W, H = Image.open(fp[0]).size; rms_p = 100.0 * k["rms_px"] / H; e.update(rms_px=round(k["rms_px"], 1), rms_proz_bildhoehe=round(rms_p, 2), f_px=round(k["f_px"], 1), bild=[W, H])
        R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float); C = -R.T @ t; dist0 = float(np.hypot(C[0], C[1]))
        grund = None
        if list(k.get("bild", [W, H])) != [W, H]: grund = "Bildgroesse K %s != Datei %s" % (k.get("bild"), [W, H])
        elif not (a.min_abstand <= dist0 <= a.max_abstand) or k["f_px"] > a.max_f_rel * max(W, H): grund = "unphysikalisch (Standort %.0f m, f %.0f px): Kamera nicht belastbar" % (dist0, k["f_px"])
        elif k.get("plausibel_strassenfoto") is False and not a.auch_unplausible: grund = "als nicht plausibel markiert (plausibel_strassenfoto=false)"
        elif rms_p > a.rms_max_proz: grund = "RMS %.1f %% der Bildhoehe > Grenze %.1f %%" % (rms_p, a.rms_max_proz)
        if grund: e.update(benutzt=False, grund=grund); ber.append(e); continue
        import messung_pruefen as MP; lo, hi = MP.kamera_zone(k)
        ben[nr] = dict(R=R, t=t, C=C, f=float(k["f_px"]), cx=float(k["cx"]), cy=float(k["cy"]), W=W, H=H, w=1.0 / (1.0 + (rms_p / a.rms_gut_proz) ** 2), zone=(lo, hi), pfad=fp[0], rms_p=rms_p)
        e.update(benutzt=True, gewicht=round(ben[nr]["w"], 3), ankerzone_z=[lo, hi], grob=bool(rms_p > a.rms_gut_proz)); ber.append(e)
    return ben, ber

def kameras_sfm(pfad, od, T_):
    """GENERISCH (2026-11-04): Kameras aus einer Buendel-/SfM-Ausrichtung (messprotokoll/SFM-AUSRICHTUNG-<name>.json von sfm_lod2_buendel.py) statt handkalibrierter
    K-*.json. Kamera im Modellrahmen (X_modell), Werkzeug arbeitet im verschobenen Rahmen X_w = X_modell + T_ (modell_laden) -> t' = t - R T_. f/cx/cy/k1 in den
    Pixeln der SfM-Bilder (sparse_<name>_bilder). Ohne Ankerzone (das Buendel haelt alle Hoehen ueber LoD2/DGM1), Gewicht 1."""
    from PIL import Image
    A = json.load(open(pfad if os.path.isabs(pfad) else os.path.join(od, pfad))); sp = A["sparse"].rstrip("/")
    bdir = (os.path.dirname(sp) if os.path.basename(sp).isdigit() else sp) + "_bilder"; ben, ber = {}, []
    for nr, k in A["kameras"].items():
        fp = sorted(glob.glob(os.path.join(bdir, nr + ".*")))
        if not fp: ber.append(dict(foto=nr, benutzt=False, grund="Bild fehlt in " + bdir)); continue
        W, H = Image.open(fp[0]).size; R = np.array(k["R"], float); t = np.array(k["t"], float) - R @ T_
        if [W, H] != [k.get("bild_b", W), k.get("bild_h", H)]: ber.append(dict(foto=nr, benutzt=False, grund=f"Bildgroesse {W}x{H} != Kamera")); continue
        ben[nr] = dict(R=R, t=t, C=-R.T @ t, f=float(k["f_px_original"]), cx=float(k["cx"]), cy=float(k["cy"]), k1=float((k.get("k") or [0.0])[0]), W=W, H=H, w=1.0, zone=(None, None), pfad=fp[0], rms_p=0.0)
        ber.append(dict(foto=nr, benutzt=True, rms_proz_bildhoehe=0.0, gewicht=1.0, quelle="sfm"))
    return ben, ber


def rgb2lab(rgb):
    """uint8/float (N,3) RGB -> float32 CIELAB (L 0..100), in Stuecken (cv2-Groessengrenze)."""
    import cv2; rgb = np.asarray(rgb, np.float32) / 255.0; out = np.empty_like(rgb)
    for a in range(0, len(rgb), 400000): out[a:a + 400000] = cv2.cvtColor(rgb[a:a + 400000].reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    return out

def laub_maske(rgb, hue_lo, hue_hi, sat_min):
    """Blattgruen-aehnlich? HSV mit Hue in Grad (cv2: 0..179 = Grad/2), Saettigung 0..1, Helligkeit > 0,15. Kupferpatina (Hue ~150-190 Grad) liegt ausserhalb der Vorgabe."""
    import cv2; hsv = cv2.cvtColor(np.asarray(rgb, np.uint8).reshape(-1, 1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(np.float32)
    h = hsv[:, 0] * 2.0; return (h >= hue_lo) & (h <= hue_hi) & (hsv[:, 1] / 255.0 >= sat_min) & (hsv[:, 2] / 255.0 >= 0.15)

def gains_schaetzen(knoten, kanten, ref, gmax, lam=1.0):
    """Gain je Knoten und Kanal. kanten: [(i, j, d_rgb[3], n)] mit d = log c_j - log c_i = g_i - g_j. Kleinste Quadrate mit Gewicht sqrt(min(n,2500)),
    schwacher Anker lam auf g=0, harter Anker am Bezugsknoten; Ergebnis auf [-log gmax, log gmax] begrenzt."""
    K = len(knoten); idx = {k: a for a, k in enumerate(knoten)}; g = np.zeros((K, 3))
    if not kanten: return g
    A = []; B = []
    for (i, j, d, n) in kanten:
        w = np.sqrt(min(n, 2500.0)); r = np.zeros(K); r[idx[i]] = w; r[idx[j]] = -w; A.append(r); B.append(w * np.asarray(d, float))
    for a in range(K):
        r = np.zeros(K); r[a] = lam * (100.0 if knoten[a] == ref else 1.0); A.append(r); B.append(np.zeros(3))
    sol = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)[0]; return np.clip(sol, -np.log(gmax), np.log(gmax))

def netz_exportieren(prefix, fine, farbe):
    """PLY, GLB und OBJ mit Vertexfarben (je Dreieck eigene Eckpunkte, weil die Farbe je Dreieck gilt)."""
    import trimesh; n = len(fine.faces); T3 = fine.vertices[fine.faces].reshape(-1, 3)
    vc = np.repeat(np.c_[farbe, np.full(n, 255, np.uint8)], 3, axis=0); tm = trimesh.Trimesh(T3, np.arange(len(T3)).reshape(-1, 3), vertex_colors=vc, process=False); aus = []
    for ext in ("ply", "glb"):
        try: tm.export(prefix + "." + ext); aus.append(prefix + "." + ext)
        except Exception as e: print(f"WARNUNG: {ext}-Export fehlgeschlagen: {e}")
    try:
        with open(prefix + ".obj", "w") as f:
            f.write("# textur_projektion.py: Vertexfarben (v x y z r g b)\n"); c = vc[:, :3] / 255.0
            for (x, y, z), (r, g, b) in zip(T3, c): f.write("v %.4f %.4f %.4f %.3f %.3f %.3f\n" % (x, y, z, r, g, b))
            F = (np.arange(len(T3)).reshape(-1, 3) + 1)
            for a, b, c3 in F: f.write("f %d %d %d\n" % (a, b, c3))
        aus.append(prefix + ".obj")
    except Exception as e: print(f"WARNUNG: obj-Export fehlgeschlagen: {e}")
    return aus

def atlas_backen(m, fine, wahl, farbe, ben, gain, texel, kante_grob, prefix, max_texel=16e6):
    """TEXTURATLAS (2026-11-04, Nutzer: 'viel zu grob'): statt EINER Farbe je 25-cm-Dreieck echte Fotopixel. Traeger = Modell auf <= kante_grob unterteilt;
    je Dreieck eine Rechteckzelle (Regalpackung) mit 1 Texel Rand, Texelmitte -> 3D-Punkt (baryzentrisch, ausserhalb des Dreiecks in der Ebene fortgesetzt =
    Rand gegen Filterbluten). Fotowahl je Texel = Wahl des naechsten feinen Dreiecks gleicher Orientierung (Sicht-/Himmel-/Tiefen-/Konsistenzentscheid bleibt
    der von main()); Farbe = bilineare Abtastung dieses Fotos am TEXELPUNKT (SIMPLE_RADIAL) x Gain. Ohne Foto: Dreiecksfarbe (grau/Drohne).
    Ausgabe: PREFIX_atlas.jpg, PREFIX_atlas.npz (V je Dreiecksecke, UV in [0,1], v nach oben), PREFIX_atlas.glb. Rueckgabe Bericht."""
    import cv2, trimesh; from scipy.spatial import cKDTree
    V0 = np.asarray(m.vertices); F0 = np.asarray(m.faces)
    while True:
        Vg, Fg = trimesh.remesh.subdivide_to_size(V0, F0, max_edge=kante_grob); T = Vg[Fg]
        L = np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2); e0 = np.argmax(L, axis=1)            # laengste Kante als Grundlinie: Ecken so drehen, dass P0->P1 die laengste ist
        T = np.stack([T[np.arange(len(T)), (e0 + k) % 3] for k in (2, 0, 1)], axis=1)              # Kante (e0-1 -> e0) ist laengste: P0 = Ecke e0-1, P1 = e0
        a_ = T[:, 1] - T[:, 0]; la = np.linalg.norm(a_, axis=1); ua = a_ / np.maximum(la, 1e-9)[:, None]; b_ = T[:, 2] - T[:, 0]
        bx = (b_ * ua).sum(1); hb = np.linalg.norm(b_ - bx[:, None] * ua, axis=1)
        sw = np.ceil(la / texel).astype(int) + 2; sh = np.ceil(hb / texel).astype(int) + 2       # Zelle: Breite = Grundlinie, Hoehe = Dreieckshoehe (+ 2 Texel Rand)
        if (sw * sh).sum() <= max_texel: break
        texel *= 1.15
    n = len(T); order = np.argsort(-sh); Wat = int(min(16384, max(1024, np.sqrt((sw * sh).sum() * 1.1))))
    ox = np.zeros(n, int); oy = np.zeros(n, int); x = y = hrow = 0
    for i in order:                                                                                  # Regalpackung
        if x + sw[i] > Wat: x = 0; y += hrow; hrow = 0
        ox[i], oy[i] = x, y; x += sw[i]; hrow = max(hrow, sh[i])
    Hat = y + hrow; atlas = np.full((Hat, Wat, 3), 200, np.uint8)
    # Texel -> (Dreieck, s, t) in Dreiecksbasis: P = P0 + s*ua*la... direkt metrisch: P = P0 + xs*ua + ys*nb (nb = Hoehenrichtung)
    nb = b_ - bx[:, None] * ua; nb /= np.maximum(np.linalg.norm(nb, axis=1), 1e-9)[:, None]
    tri = np.repeat(np.arange(n), sw * sh); k_ = np.arange(len(tri)) - np.repeat(np.cumsum(sw * sh) - sw * sh, sw * sh)
    ix = k_ % sw[tri]; iy = k_ // sw[tri]
    xs = ((ix + 0.5 - 1.0) * texel).astype(np.float32); ys = ((iy + 0.5 - 1.0) * texel).astype(np.float32)
    P = T[tri, 0] + xs[:, None] * ua[tri] + ys[:, None] * nb[tri]
    # Fotowahl vom naechsten feinen Dreieck mit passender Normale
    fn = fine.face_normals; kd = cKDTree(fine.triangles_center); nG = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nG /= np.maximum(np.linalg.norm(nG, axis=1), 1e-12)[:, None]
    jf = np.zeros(len(P), np.int64)
    for a0 in range(0, len(P), 1500000):                                                             # in Bloecken (Speicher)
        sl = slice(a0, a0 + 1500000); _, j_ = kd.query(P[sl], k=4, workers=-1); dots = np.einsum("ikj,ij->ik", fn[j_], nG[tri[sl]]); gut = dots > 0.7
        erst = np.where(gut.any(1), np.argmax(gut, 1), 0); jf[sl] = j_[np.arange(len(j_)), erst]
    col = farbe[jf].astype(np.float32); w_ = wahl[jf].astype(object); quellen = {}
    # LOECHER (Sprenkel): feine Dreiecke ohne Foto (Tiefenkarte lueckig) mitten in fotografierten Flaechen -> haeufigstes Foto des Traegerdreiecks, wenn dort
    # >= fuell_min der Texel ein Foto haben (sonst bleibt grau: echte Luecke, Himmel/Verdecker-Entscheid nicht ueberstimmen).
    fuell_min = 0.5; hatf = w_ != ""; nf = 0
    if hatf.any():
        codes, inv = np.unique(w_[hatf], return_inverse=True); M = np.zeros((n, len(codes)), np.int32); np.add.at(M, (tri[hatf], inv), 1)
        cnt = np.bincount(tri, minlength=n); best = np.argmax(M, 1); ant = M.sum(1) / np.maximum(cnt, 1)
        leer = ~hatf & (ant[tri] >= fuell_min) & (M[tri, best[tri]] > 0); w_[leer] = codes[best[tri[leer]]]; nf = int(leer.sum())
    for nr in sorted(set(w_) - {""}):
        if nr not in ben: continue
        c = ben[nr]; s = np.nonzero(w_ == nr)[0]; Xc = P[s] @ c["R"].T + c["t"]; z = Xc[:, 2]; xn, yn = Xc[:, 0] / z, Xc[:, 1] / z; dk = 1 + c.get("k1", 0.0) * (xn ** 2 + yn ** 2)
        u = c["f"] * dk * xn + c["cx"]; v = c["f"] * dk * yn + c["cy"]; ok = (z > 0.5) & (u >= 1) & (u < c["W"] - 1) & (v >= 1) & (v < c["H"] - 1); s, u, v = s[ok], u[ok], v[ok]
        im = cv2.imread(c["pfad"]); col[s] = np.clip(bilinear(im, u, v)[:, ::-1].astype(np.float32) * gain.get(nr, np.ones(3)), 0, 255); quellen[nr] = int(len(s))
    atlas[oy[tri] + iy, ox[tri] + ix] = np.rint(col).astype(np.uint8)
    # UV der Ecken: P0 bei Texel (1,1), P1 bei (1 + la/texel, 1), P2 bei (1 + bx/texel, 1 + hb/texel)
    U = np.stack([ox + 1.0, ox + 1.0 + la / texel, ox + 1.0 + bx / texel], 1); Vv = np.stack([oy + 1.0, oy + 1.0, oy + 1.0 + hb / texel], 1)
    UV = np.stack([U / Wat, 1.0 - Vv / Hat], 2).reshape(-1, 2).astype(np.float32); VV = T.reshape(-1, 3).astype(np.float32)
    cv2.imwrite(prefix + "_atlas.jpg", atlas[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 88]); np.savez_compressed(prefix + "_atlas.npz", V=VV, UV=UV, texel=texel)
    try:
        from PIL import Image
        tm = trimesh.Trimesh(VV, np.arange(len(VV)).reshape(-1, 3), process=False, visual=trimesh.visual.TextureVisuals(uv=UV, image=Image.fromarray(atlas)))
        tm.export(prefix + "_atlas.glb")
    except Exception as e: print("WARNUNG: glb-Atlas fehlgeschlagen:", e)
    ber = dict(texel_m=round(float(texel), 4), traeger_kante_m=kante_grob, dreiecke=int(n), atlas_px=[int(Wat), int(Hat)], texel_gesamt=int(len(tri)), texel_je_foto=quellen,
               texel_foto_proz=round(100.0 * sum(quellen.values()) / len(tri), 1), texel_gefuellt=nf, fuell_min=fuell_min)
    print(f"Atlas: {n} Dreiecke (<= {kante_grob} m), Texel {texel * 100:.1f} cm, {Wat}x{Hat} px, Fotopixel {ber['texel_foto_proz']} % -> {prefix}_atlas.jpg/.npz/.glb", flush=True)
    return ber


def main():
    ap = argparse.ArgumentParser(description="Fotofarbe auf die Modelloberflaeche projizieren (siehe Modul-Doku)")
    ap.add_argument("--atlas", type=float, default=0.0, help="Texturatlas mit dieser Texelgroesse (m, z. B. 0.025) zusaetzlich zu den Eckenfarben (braucht --ausgabe)")
    ap.add_argument("--atlas-kante", type=float, default=1.0, help="Traegernetz des Atlas: Modell auf <= so viele m unterteilt")
    ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--ausgabe", help="Praefix fuer .ply/.glb/.obj (ohne: keine Netze)"); ap.add_argument("--bild")
    ap.add_argument("--tiefen", help="Dichte-Arbeitsordner (sfm_dicht.py) mit kameras_unverzerrt.json (tiefen_kameras.py): Tiefentest gegen Himmel/Verdecker")
    ap.add_argument("--tiefen-tol", type=float, default=0.05); ap.add_argument("--tiefen-tol-m", type=float, default=0.5); ap.add_argument("--tiefen-fenster", type=int, default=3); ap.add_argument("--tiefen-rand", type=int, default=1, help="Tiefenmaske um so viele px schrumpfen (Silhouettenbluten)")
    ap.add_argument("--verdecker-lod2", type=float, default=0.0, help="LoD2-Nachbargebaeude im Radius (m) als Verdecker (0 = aus)"); ap.add_argument("--kameras-sfm", help="Kameras aus messprotokoll/SFM-AUSRICHTUNG-<name>.json (Buendel) statt K-*.json"); ap.add_argument("--kante", type=float, default=0.35); ap.add_argument("--max-dreiecke", type=int, default=1000000); ap.add_argument("--cos-min", type=float, default=0.25)
    ap.add_argument("--rms-max-proz", type=float, default=3.0); ap.add_argument("--rms-gut-proz", type=float, default=0.5); ap.add_argument("--auch-unplausible", action="store_true")
    ap.add_argument("--min-abstand", type=float, default=3.0, help="Kamera mind. so weit (m, horizontal) vom Koordinatenursprung")
    ap.add_argument("--max-abstand", type=float, default=2000.0, help="Kamera hoechstens so weit; Luftbilder 321-376 m Hoehe sind dann moeglich, 15 Mio. m nicht")
    ap.add_argument("--max-f-rel", type=float, default=50.0, help="f_px hoechstens das X-fache der langen Bildseite (sonst unphysikalisch)")
    ap.add_argument("--rand-px", type=float, default=8.0); ap.add_argument("--versatz-m", type=float, default=0.02, help="Strahlenstart ueber der Flaeche (m)")
    ap.add_argument("--drohne-ordner"); ap.add_argument("--ohne-drohne", action="store_true"); ap.add_argument("--drohne-dist", type=float, default=0.5)
    ap.add_argument("--ohne-verdecker", action="store_true"); ap.add_argument("--baender", default="0,15,30,45,60,70", help="Hoehenbaender in m (Komma)")
    ap.add_argument("--ohne-himmel", action="store_true"); ap.add_argument("--himmel-rand-px", type=int, default=6)
    ap.add_argument("--ohne-angleich", action="store_true"); ap.add_argument("--gain-max", type=float, default=1.6); ap.add_argument("--angleich-min", type=int, default=200)
    ap.add_argument("--ohne-konsistenz", action="store_true"); ap.add_argument("--konsistenz-de", type=float, default=25.0)
    ap.add_argument("--ohne-laubfilter", action="store_true"); ap.add_argument("--laub-hue", default="55,125"); ap.add_argument("--laub-sat", type=float, default=0.25)
    ap.add_argument("--produkt", action="store_true", help="nur Klassen mit produkt()==ja faerben (Drohne/nc/unfrei/unklar/bedingt grau)"); ap.add_argument("--produkt-mit-bedingt", action="store_true", help="mit --produkt: auch 'bedingt' (frei_sharealike) faerben")
    a = ap.parse_args()
    import cv2, trimesh; from scipy.spatial import cKDTree; import foto_pick as FP
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od)); audit = os.path.join(od, "audit"); os.makedirs(audit, exist_ok=True)
    konv = seiten_aus_konvention(obj); seiten = sorted(set(konv.values())) + ["Dach/oben"]
    m = modell_laden(obj, root, a.stl); V = np.asarray(m.vertices); F = np.asarray(m.faces); kante = a.kante
    while True:
        V2, F2 = trimesh.remesh.subdivide_to_size(V, F, max_edge=kante)
        if len(F2) <= a.max_dreiecke or kante > 3.0: break
        kante *= 1.2
    fine = trimesh.Trimesh(V2, F2, process=False); cen = fine.triangles_center; nrm = fine.face_normals; area = fine.area_faces; n = len(F2)
    print(f"Modell: {len(F)} Dreiecke -> {n} (Kante <= {kante:.2f} m, Vorgabe {a.kante}, Obergrenze {a.max_dreiecke}), Flaeche {area.sum():.0f} m2")
    occ = [("modell", m)]; vd = [] if a.ohne_verdecker else verdecker_laden(obj, root); occ += vd
    if a.verdecker_lod2 > 0: occ += verdecker_lod2(obj, od, a.verdecker_lod2, m.metadata["verschiebung"])
    occ_mesh = trimesh.util.concatenate([x[1] for x in occ]); print("Verdecker:", [x[0] for x in occ])
    ben, kber = kameras_sfm(a.kameras_sfm, od, m.metadata["verschiebung"]) if a.kameras_sfm else kameras_pruefen(obj, root, od, a)
    for e in kber: print("  K-%s: %s" % (e["foto"], ("BENUTZT RMS %.1f %% w=%.2f" % (e["rms_proz_bildhoehe"], e["gewicht"])) if e.get("benutzt") else "nicht benutzt: " + e["grund"]))
    tk = None
    if a.tiefen:
        import tiefen_kameras as TK; tk = json.load(open(os.path.join(a.tiefen, "kameras_unverzerrt.json")))
    liz = LR.foto_klassen(objp); hlo, hhi = [float(x) for x in a.laub_hue.split(",")]
    # ---- Durchgang 1: je Foto alle sichtbaren Dreiecke mit Farbe, Score, Aufloesung ----
    sicht = {}; zaehler = dict(himmel_verworfen=0, konsistenz_verworfen=0, strittig=0, laub_ersetzt=0, laub_keine=0)
    for nr, c in ben.items():
        d = c["C"][None] - cen; dist = np.linalg.norm(d, axis=1); d /= dist[:, None]; cs = (nrm * d).sum(1)
        ok = cs >= a.cos_min; idx = np.nonzero(ok)[0]
        Xc = cen[idx] @ c["R"].T + c["t"]; z = Xc[:, 2]; xn, yn = Xc[:, 0] / z, Xc[:, 1] / z; dk = 1 + c.get("k1", 0.0) * (xn ** 2 + yn ** 2)   # SIMPLE_RADIAL (SfM-Kameras), K-Kameras k1=0
        u = c["f"] * dk * xn + c["cx"]; v = c["f"] * dk * yn + c["cy"]
        ins = (z > 1) & (u >= a.rand_px) & (u < c["W"] - a.rand_px) & (v >= a.rand_px) & (v < c["H"] - a.rand_px)
        lo, hi = c["zone"]
        if lo is not None: ins &= (cen[idx, 2] >= lo) & (cen[idx, 2] <= hi)            # nur wo die Anker tragen (sonst extrapoliert die Kamera)
        idx, u, v = idx[ins], u[ins], v[ins]
        if not len(idx): print(f"  {nr}: kein Dreieck im Bild/in der Ankerzone"); continue
        org = cen[idx] + nrm[idx] * a.versatz_m; verd = occ_mesh.ray.intersects_any(org, d[idx]); keep = ~verd; idx, u, v = idx[keep], u[keep], v[keep]; n_sicht = len(idx)
        im = cv2.imread(c["pfad"])
        if not a.ohne_himmel:
            try:
                sk = FP.himmel_cached(im, os.path.join(od, "himmelsmaske", nr + ".png")); r_ = a.himmel_rand_px
                if r_ > 0: sk = cv2.dilate(sk.astype(np.uint8), np.ones((2 * r_ + 1, 2 * r_ + 1), np.uint8)) > 0
                im_h = sk[np.clip(np.rint(v).astype(int), 0, c["H"] - 1), np.clip(np.rint(u).astype(int), 0, c["W"] - 1)]
                zaehler["himmel_verworfen"] += int(im_h.sum()); idx, u, v = idx[~im_h], u[~im_h], v[~im_h]; c["himmel"] = True
            except SystemExit as e: print(f"  {nr}: keine Himmelsmaske ({str(e)[:90]}) - nicht maskiert"); c["himmel"] = False
        if tk is not None and nr in tk:
            # TIEFENTEST (2026-11-04, Kaufhaus: Himmel auf dem Dach, Masken unplausibel): Tiefenkarte der dichten Rekonstruktion (entzerrte PINHOLE-Kamera).
            # Verworfen: (a) Karte zeigt etwas deutlich NAEHER als das Modell (Verdecker, den das Modell nicht kennt: Baum, Mensch, Schild);
            # (b) im Fenster (--tiefen-fenster px) gar keine Tiefe (Himmel, Leere). Grau ist ehrlicher als Himmel auf dem Dach.
            q = tk[nr]; Ru = np.array(q["R"]); tu = np.array(q["t"]) - Ru @ m.metadata["verschiebung"]
            Xu = cen[idx] @ Ru.T + tu; zu = Xu[:, 2]; iu = np.rint(q["fx"] * Xu[:, 0] / zu + q["cx"] - 0.5).astype(int); iv = np.rint(q["fy"] * Xu[:, 1] / zu + q["cy"] - 0.5).astype(int)
            pd = os.path.join(a.tiefen, "stereo", "depth_maps", q["bild"] + ".geometric.bin")
            if os.path.exists(pd):
                from scipy.ndimage import maximum_filter, minimum_filter
                Dm = TK.lies_tiefe(pd); Hh, Ww = Dm.shape; inn = (iu >= 0) & (iu < Ww) & (iv >= 0) & (iv < Hh); iu_, iv_ = np.clip(iu, 0, Ww - 1), np.clip(iv, 0, Hh - 1)
                # Rand: PatchMatch blutet an Silhouetten einige Pixel Tiefe in den Himmel (Kaufhaus: hellblaue Dachkante) -> Tiefenmaske erst um --tiefen-rand px schrumpfen
                gueltig = minimum_filter(Dm > 0, size=a.tiefen_rand) if a.tiefen_rand > 1 else Dm > 0
                irgend = maximum_filter(gueltig, size=a.tiefen_fenster)[iv_, iu_]; dv = Dm[iv_, iu_]
                naeher = (dv > 0) & (dv < zu - np.maximum(a.tiefen_tol_m, a.tiefen_tol * zu)); leer = ~irgend
                weg = inn & (naeher | leer); zaehler["tiefe_verdeckt"] = zaehler.get("tiefe_verdeckt", 0) + int((inn & naeher).sum()); zaehler["tiefe_leer"] = zaehler.get("tiefe_leer", 0) + int((inn & leer & ~naeher).sum())
                idx, u, v = idx[~weg], u[~weg], v[~weg]
        px = dist[idx] / (c["f"] * cs[idx]); col = bilinear(im, u, v)[:, ::-1].astype(np.float32)
        sicht[nr] = dict(idx=idx, col=col, score=c["w"] / px, px=px); print(f"  {nr}: sichtbar {n_sicht} von {ok.sum()} Dreiecken im Blickwinkel, nach Himmelsmaske {len(idx)}")
    # ---- Drohne: Farbe je Dreieck (nearest neighbour), nur dort, wo ein Foto sieht oder die Luecke liegt ----
    P_d = None; drohne_info = None; dcol = np.full((n, 3), np.nan, np.float32); dhas = np.zeros(n, bool)
    if not a.ohne_drohne and not a.produkt:
        od_ = a.drohne_ordner or (os.path.join(obj.get("video_stufe", {}).get("ordner", ""), "d1_cv"))
        pm, pc = os.path.join(od_, "dicht_modell.npy"), os.path.join(od_, "dicht_farben.npy")
        if os.path.exists(pm) and os.path.exists(pc):
            P_d = np.load(pm).astype(np.float64); C_d = np.load(pc); dd, ii = cKDTree(P_d).query(cen, distance_upper_bound=a.drohne_dist); dhas = np.isfinite(dd)
            dcol[dhas] = C_d[ii[dhas]]; drohne_info = dict(ordner=od_, punkte=int(len(P_d)), dreiecke_mit_drohne=int(dhas.sum())); print(f"Drohne {od_}: {len(P_d)} Punkte, {dhas.sum()} Dreiecke <= {a.drohne_dist} m")
        else: print("Drohnenwolke nicht gefunden:", od_)
    # ---- Durchgang 2: Angleich (Gain je Quelle aus den Ueberlappen) ----
    gain = {k: np.ones(3) for k in list(sicht) + ["drohne"]}; angleich = dict(kanten=[], verworfen=[], de_vorher=None, de_nachher=None)
    if not a.ohne_angleich and sicht:
        def log_(x): return np.log(np.clip(x, 0, 255) + 8.0)
        def mitte(col): g = col.mean(1); return (g > 30) & (g < 225)
        def paar(ci, cj):                                      # Dreiecke im Mittelton beider Farben
            ok_ = mitte(ci) & mitte(cj); return ok_
        nr_list = list(sicht); kanten = []; ueber = {}
        for ia in range(len(nr_list)):
            for ib in range(ia + 1, len(nr_list)):
                A_, B_ = sicht[nr_list[ia]], sicht[nr_list[ib]]; _, ja, jb = np.intersect1d(A_["idx"], B_["idx"], return_indices=True)
                if len(ja) < a.angleich_min: continue
                ca, cb = A_["col"][ja], B_["col"][jb]; ok_ = paar(ca, cb)
                if ok_.sum() < a.angleich_min: continue
                kanten.append((nr_list[ia], nr_list[ib], np.median(log_(cb[ok_]) - log_(ca[ok_]), axis=0), int(ok_.sum()))); ueber[(nr_list[ia], nr_list[ib])] = (ja[ok_], jb[ok_])
        flaeche_foto = {nr: float(area[sicht[nr]["idx"]].sum()) for nr in nr_list}; ref = max(flaeche_foto, key=flaeche_foto.get)
        G = gains_schaetzen(nr_list, kanten, ref, a.gain_max)                                  # Fotos NUR aus direkten Foto-Ueberlappen (Drohne ist keine Bruecke: widerspruechlich, Register 3.11.)
        for k, gg in zip(nr_list, G): gain[k] = np.exp(gg)
        dkanten = []
        if P_d is not None:                                                                    # Drohnen-Gain: gewichteter Median der Foto-Drohne-Verhaeltnisse (nach Fotogain), wirkt nur auf Drohnenfarbe
            ds = []; ws = []
            for nr in nr_list:
                A_ = sicht[nr]; h = np.nonzero(dhas[A_["idx"]])[0]
                if len(h) < a.angleich_min: continue
                ca, cd = A_["col"][h] * gain[nr], dcol[A_["idx"][h]]; ok_ = paar(ca, cd)
                if ok_.sum() < a.angleich_min: continue
                ds.append(np.median(log_(ca[ok_]) - log_(cd[ok_]), axis=0)); ws.append(float(ok_.sum())); dkanten.append((nr, h[ok_], int(ok_.sum())))
            if ds:
                ds = np.array(ds); ws = np.array(ws); o = np.argsort(ds, axis=0); gd = np.zeros(3)
                for ch in range(3): cw = np.cumsum(ws[o[:, ch]]); gd[ch] = ds[o[:, ch], ch][np.searchsorted(cw, cw[-1] / 2.0)]
                gain["drohne"] = np.exp(np.clip(gd, -np.log(a.gain_max), np.log(a.gain_max)))
        def de_kante(ci, cj, gi, gj):
            sub = np.random.default_rng(0).choice(len(ci), min(len(ci), 20000), replace=False)
            return float(np.median(np.linalg.norm(rgb2lab(np.clip(ci[sub] * gi, 0, 255)) - rgb2lab(np.clip(cj[sub] * gj, 0, 255)), axis=1)))
        def alle_kanten(g):
            out = []
            for (i, j), (ja, jb) in ueber.items(): out.append((i, j, de_kante(sicht[i]["col"][ja], sicht[j]["col"][jb], g[i], g[j])))
            for (nr, h, nn) in dkanten: out.append((nr, "drohne", de_kante(sicht[nr]["col"][h], dcol[sicht[nr]["idx"][h]], g[nr], g["drohne"])))
            return out
        eins = {k: np.ones(3) for k in gain}; v0 = alle_kanten(eins); v1 = alle_kanten(gain)
        for k in list(gain):                                                                   # Pruefung je Quelle: verschlechtert der Gain ihre Kanten im Mittel, wird er verworfen
            m0 = [x[2] for x in v0 if k in x[:2]]; m1 = [x[2] for x in v1 if k in x[:2]]
            if m0 and np.mean(m1) > np.mean(m0): angleich["verworfen"].append(dict(quelle=k, de_vorher=round(float(np.mean(m0)), 1), de_nachher=round(float(np.mean(m1)), 1))); gain[k] = np.ones(3)
        v1 = alle_kanten(gain)
        angleich["kanten"] = [dict(von=a_[0], nach=a_[1], delta_e_median_vorher=round(a_[2], 1), delta_e_median_nachher=round(b_[2], 1)) for a_, b_ in zip(v0, v1)]
        angleich.update(bezug=ref, gain={k: [round(float(x), 3) for x in v] for k, v in gain.items()}, de_vorher=round(float(np.mean([x[2] for x in v0])), 1) if v0 else None, de_nachher=round(float(np.mean([x[2] for x in v1])), 1) if v1 else None)
        print("Angleich Bezug", ref, "| Gains:", {k: [round(float(x), 2) for x in v] for k, v in gain.items()}, "| verworfen:", [x["quelle"] for x in angleich["verworfen"]], "| Delta-E Kanten vorher/nachher:", angleich["de_vorher"], angleich["de_nachher"])
        for k in sicht: sicht[k]["col"] = np.clip(sicht[k]["col"] * gain[k], 0, 255)
        if P_d is not None: dcol[dhas] = np.clip(dcol[dhas] * gain["drohne"], 0, 255)
    # ---- Durchgang 3: Auswahl mit Konsistenz, Laubfilter, Drohnen-Luecken ----
    nr_list = list(sicht); Pn = len(nr_list)
    S = np.full((max(Pn, 1), n), -np.inf, np.float32); Cc = np.zeros((max(Pn, 1), n, 3), np.float32); PX = np.full((max(Pn, 1), n), np.nan, np.float32)
    for p_, nr in enumerate(nr_list): S[p_, sicht[nr]["idx"]] = sicht[nr]["score"]; Cc[p_, sicht[nr]["idx"]] = sicht[nr]["col"]; PX[p_, sicht[nr]["idx"]] = sicht[nr]["px"]
    valid = np.isfinite(S) if Pn else np.zeros((1, n), bool); cnt = valid.sum(0)
    if Pn and not a.ohne_konsistenz:
        tri = np.nonzero(cnt >= 2)[0]; lab = np.zeros((Pn, len(tri), 3), np.float32)
        for p_ in range(Pn): lab[p_] = rgb2lab(Cc[p_, tri])
        v_t = valid[:, tri]
        for k3 in np.unique(cnt[tri]):                         # Gruppen gleicher Foto-Anzahl: >= 3 Median, 2 Drohne/Aufloesung
            sel = np.nonzero(cnt[tri] == k3)[0]
            if k3 >= 3:
                L_ = np.where(v_t[:, sel, None], lab[:, sel], np.nan); med = np.nanmedian(L_, axis=0); de = np.linalg.norm(lab[:, sel] - med[None], axis=2)
                out = v_t[:, sel] & (de > a.konsistenz_de); zaehler["konsistenz_verworfen"] += int(out.sum()); valid[:, tri[sel]] &= ~out
            else:
                two = tri[sel]; w2 = [np.nonzero(valid[:, t])[0] for t in two]; pa = np.array([x[0] for x in w2]); pb = np.array([x[1] for x in w2])
                la, lb = lab[pa, sel], lab[pb, sel]; strittig = np.linalg.norm(la - lb, axis=1) > a.konsistenz_de; zaehler["strittig"] += int(strittig.sum())
                has_d = dhas[two] & strittig
                if has_d.any():
                    ld = rgb2lab(dcol[two[has_d]]); da = np.linalg.norm(la[has_d] - ld, axis=1); db = np.linalg.norm(lb[has_d] - ld, axis=1); verw = np.where(da <= db, pb[has_d], pa[has_d])
                    valid[verw, two[has_d]] = False; zaehler["konsistenz_verworfen"] += int(has_d.sum())
    Sg = np.where(valid, S, -np.inf); wahl_i = np.argmax(Sg, axis=0) if Pn else np.zeros(n, int); hat = np.isfinite(Sg.max(0)) if Pn else np.zeros(n, bool)
    farbe = np.full((n, 3), 200, np.uint8); quelle = np.full(n, "keine", object); wahl = np.full(n, "", object); aufl = np.full(n, np.nan)
    ii_ = np.nonzero(hat)[0]
    if len(ii_):
        farbe[ii_] = np.rint(Cc[wahl_i[ii_], ii_]).astype(np.uint8); wahl[ii_] = np.array(nr_list, object)[wahl_i[ii_]]; quelle[ii_] = np.array(["foto:" + x for x in nr_list], object)[wahl_i[ii_]]; aufl[ii_] = PX[wahl_i[ii_], ii_]
    if Pn and not a.ohne_laubfilter and len(ii_):
        lb = laub_maske(farbe[ii_], hlo, hhi, a.laub_sat); bad = ii_[lb]
        for t in bad:                                                              # anderes Foto ohne Laubfarbe, sonst Drohne, sonst keine
            alt = [p_ for p_ in np.nonzero(valid[:, t])[0] if p_ != wahl_i[t] and not laub_maske(np.rint(Cc[p_, t])[None].astype(np.uint8), hlo, hhi, a.laub_sat)[0]]
            if alt: p_ = max(alt, key=lambda q: S[q, t]); farbe[t] = np.rint(Cc[p_, t]).astype(np.uint8); wahl[t] = nr_list[p_]; quelle[t] = "foto:" + nr_list[p_]; aufl[t] = PX[p_, t]; zaehler["laub_ersetzt"] += 1
            elif dhas[t] and not laub_maske(np.rint(dcol[t])[None].astype(np.uint8), hlo, hhi, a.laub_sat)[0]: farbe[t] = np.rint(dcol[t]).astype(np.uint8); quelle[t] = "drohne"; wahl[t] = ""; aufl[t] = np.nan; zaehler["laub_ersetzt"] += 1
            else: farbe[t] = 200; quelle[t] = "keine"; wahl[t] = ""; aufl[t] = np.nan; zaehler["laub_keine"] += 1
    luecke = np.nonzero(quelle == "keine")[0]; l2 = luecke[dhas[luecke]]
    if len(l2) and not a.produkt:
        ok_d = ~laub_maske(np.rint(dcol[l2]).astype(np.uint8), hlo, hhi, a.laub_sat) if not a.ohne_laubfilter else np.ones(len(l2), bool); l2 = l2[ok_d]
        farbe[l2] = np.rint(dcol[l2]).astype(np.uint8); quelle[l2] = "drohne"
        if drohne_info: drohne_info["gefuellt_dreiecke"] = int(len(l2))
    # ---- Lizenzklasse je Dreieck; --produkt: nur 'frei' ----
    lk = np.full(n, "", object)
    for nr in nr_list: lk[wahl == nr] = liz.get(nr, "unklar")
    lk[quelle == "drohne"] = "unfrei"
    erlaubt = {"ja"} | ({"bedingt"} if a.produkt_mit_bedingt else set())
    if a.produkt:
        nicht = (quelle != "keine") & np.array([LR.produkt(k)[0] not in erlaubt for k in lk]); farbe[nicht] = 200; zaehler["produkt_entfaerbt"] = int(nicht.sum()); quelle[nicht] = "keine"; lk[nicht] = ""
    # ---- Bericht je Seite x Hoehenband ----
    bd = [float(x) for x in a.baender.split(",")]; bands = list(zip(bd[:-1], bd[1:]))
    horiz = np.abs(nrm[:, 2]) < 0.5; schl = np.where(np.abs(nrm[:, 0]) >= np.abs(nrm[:, 1]), np.where(nrm[:, 0] > 0, "+x", "-x"), np.where(nrm[:, 1] > 0, "+y", "-y"))
    seite = np.where(horiz, np.array([konv.get(s, s) for s in schl]), "Dach/oben"); tab = {}; qs = quelle.astype(str)
    for s in seiten:
        for (lo, hi) in bands:
            sel = (seite == s) & (cen[:, 2] >= lo) & (cen[:, 2] < hi); A = area[sel].sum()
            if A <= 0: continue
            q = qs[sel]; tab.setdefault(s, {})[f"z{lo:.0f}-{hi:.0f}"] = dict(flaeche_m2=round(float(A), 1), foto_proz=round(100 * area[sel][np.char.startswith(q, "foto")].sum() / A, 1),
                                                                         drohne_proz=round(100 * area[sel][q == "drohne"].sum() / A, 1), keine_proz=round(100 * area[sel][q == "keine"].sum() / A, 1),
                                                                         lizenz_proz={k: round(float(100 * area[sel][lk[sel] == k].sum() / A), 1) for k in LR.REIHENFOLGE if (lk[sel] == k).any()})
    gesamt = {k: round(100 * float(area[(np.char.startswith(qs, "foto") if k == "foto" else qs == k)].sum() / area.sum()), 1) for k in ("foto", "drohne", "keine")}
    lizenz_gesamt = {k: round(float(100 * area[lk == k].sum() / area.sum()), 1) for k in LR.REIHENFOLGE if (lk == k).any()}
    pj = {"ja": 0.0, "bedingt": 0.0, "nein": 0.0}
    for k, v in lizenz_gesamt.items(): pj[LR.produkt(k)[0]] += v
    gesamt["produkt_ja"] = round(pj["ja"], 1); gesamt["produkt_bedingt"] = round(pj["bedingt"], 1)
    je_seite = {}
    for s in seiten:
        sel = seite == s; A = area[sel].sum()
        if A > 0: je_seite[s] = dict(flaeche_m2=round(float(A), 1), foto_proz=round(100 * area[sel][np.char.startswith(qs[sel], "foto")].sum() / A, 1), drohne_proz=round(100 * area[sel][qs[sel] == "drohne"].sum() / A, 1),
                                     keine_proz=round(100 * area[sel][qs[sel] == "keine"].sum() / A, 1),
                                     lizenz_proz={k: round(float(100 * area[sel][lk[sel] == k].sum() / A), 1) for k in LR.REIHENFOLGE if (lk[sel] == k).any()})
    for e in kber:
        if e.get("benutzt"):
            sel = wahl == e["foto"]; e["flaeche_m2"] = round(float(area[sel].sum()), 1); e["aufl_median_cm_je_px"] = round(float(np.nanmedian(aufl[sel]) * 100), 2) if sel.any() else None
            kl = liz.get(e["foto"], "unklar"); e["lizenz"] = dict(klasse=kl, produkt=LR.produkt(kl)[0], auflage=LR.produkt(kl)[1]); e["gain_rgb"] = [round(float(x), 3) for x in gain.get(e["foto"], np.ones(3))]; e["himmel_maskiert"] = bool(ben[e["foto"]].get("himmel"))
    asp = np.asarray(fine.area_faces) / np.maximum(1e-9, np.max(np.linalg.norm(fine.vertices[fine.faces] - np.roll(fine.vertices[fine.faces], 1, axis=1), axis=2), axis=1) ** 2)
    bericht = dict(objekt=obj.get("name"), stl=a.stl or obj["stl"], kante_m=round(kante, 3), dreiecke=int(n), flaeche_m2=round(float(area.sum()), 1), gesamt_proz=gesamt, je_seite=je_seite, lizenz_flaeche_proz_gesamt=lizenz_gesamt, lizenz_produkt_gruppen=dict(ja=gesamt['produkt_ja'], bedingt=gesamt['produkt_bedingt'], hinweis='bedingt = frei_sharealike: nicht stillschweigend als produktfaehig gezaehlt'), je_seite_und_band=tab, fotos=kber,
                   drohne=drohne_info, verdecker=[x[0] for x in vd], filter=zaehler, angleich=angleich, produktmodus=bool(a.produkt), dreiecksform_flaeche_zu_laengste_kante2_p5_median=[round(float(np.percentile(asp, 5)), 3), round(float(np.median(asp)), 3)],
                   annahmen=dict(rms_max_proz=a.rms_max_proz, rms_gut_proz=a.rms_gut_proz, cos_min=a.cos_min, kante_m=a.kante, max_dreiecke=a.max_dreiecke, drohne_dist_m=a.drohne_dist, rand_px=a.rand_px, himmel_rand_px=a.himmel_rand_px,
                                 gain_max=a.gain_max, angleich_min=a.angleich_min, konsistenz_de=a.konsistenz_de, laub_hue=a.laub_hue, laub_sat=a.laub_sat,
                                 schalter=dict(ohne_himmel=a.ohne_himmel, ohne_angleich=a.ohne_angleich, ohne_konsistenz=a.ohne_konsistenz, ohne_laubfilter=a.ohne_laubfilter, ohne_drohne=a.ohne_drohne)),
                   lizenz="Lizenzklassen aus tools/lizenz_register.py (Fotos nach Manifest, Drohne = unfrei, YouTube). --produkt faerbt nur produkt()==ja; 'bedingt' (frei_sharealike) nur mit --produkt-mit-bedingt. Mapillary = nc. Einordnung nach Lizenztext, keine Rechtsberatung.",
                   grenzen="Kamerafehler (RMS) = Farbversatz; Verdecker nur Modell+Torbau-LoD2, Laub/Leitungen nur ueber Konsistenz (>= 3 Fotos) bzw. Laubfilter; Gain gleicht nur Belichtung/Weissabgleich an; Drohne ist Angleich-Bruecke ohne Farbtreue-Beleg.")
    json.dump(bericht, open(os.path.join(audit, "textur_abdeckung.json"), "w"), indent=1, ensure_ascii=False)
    aus = netz_exportieren(a.ausgabe, fine, farbe) if a.ausgabe else []
    if a.atlas > 0 and a.ausgabe:
        bericht["atlas"] = atlas_backen(m, fine, wahl, farbe, ben, gain, a.atlas, a.atlas_kante, a.ausgabe); json.dump(bericht, open(os.path.join(audit, "textur_abdeckung.json"), "w"), indent=1, ensure_ascii=False)
    # 4-Seiten-Ansicht (orthografisch, Z-Puffer, Dreiecksmitten als Quadrate)
    px_m = 0.05; zmax = float(cen[:, 2].max()) + 1; Hh = int(zmax / px_m); tiles = []
    for s, (fw, nm) in {"Sued": ((-1, 0, 0), "Sued(+x)"), "Nord": ((1, 0, 0), "Nord(-x)"), "Ost": ((0, -1, 0), "Ost(+y)"), "West": ((0, 1, 0), "West(-y)")}.items():
        fw = np.array(fw, float); up = np.array([0, 0, 1.0]); rt = np.cross(fw, up); depth = cen @ fw; uu = cen @ rt; face = (nrm @ -fw) > 0.1
        u0 = uu.min() - 1; Wd = int((uu.max() - u0 + 1) / px_m); img = np.full((Hh, Wd, 3), 235, np.uint8); r = max(1, int(round(kante / 2 / px_m)))
        ids = np.nonzero(face)[0]; ids = ids[np.argsort(-depth[ids])]                                  # fern zuerst, nah zuletzt: der letzte Schreiber gewinnt (Z-Puffer)
        xs = ((uu[ids] - u0) / px_m).astype(int); ys = Hh - 1 - (cen[ids, 2] / px_m).astype(int)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                yy = np.clip(ys + dy, 0, Hh - 1); xx = np.clip(xs + dx, 0, Wd - 1); img[yy, xx] = farbe[ids][:, ::-1]
        cv2.putText(img, nm, (10, 40), 0, 1.2, (0, 0, 200), 3); tiles.append(img)
    hh = max(t.shape[0] for t in tiles); sheet = np.hstack([np.pad(t, ((0, hh - t.shape[0]), (0, 8), (0, 0)), constant_values=255) for t in tiles])
    bild = a.bild or os.path.join(audit, "textur_ansicht.jpg"); cv2.imwrite(bild, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("\nFilter:", zaehler)
    print("GESAMT Foto %.1f %%, Drohne %.1f %%, keine %.1f %% (Flaeche %.0f m2) | Produkt ja %.1f %%, bedingt %.1f %% | Lizenz je Klasse %s" % (gesamt["foto"], gesamt["drohne"], gesamt["keine"], area.sum(), gesamt["produkt_ja"], gesamt["produkt_bedingt"], lizenz_gesamt))
    for s, v in je_seite.items(): print("  %-10s Foto %5.1f  Drohne %5.1f  keine %5.1f  (%.0f m2)  Lizenz %s" % (s, v["foto_proz"], v["drohne_proz"], v["keine_proz"], v["flaeche_m2"], v["lizenz_proz"]))
    print("->", os.path.join(audit, "textur_abdeckung.json"), "|", bild, "|", aus)

if __name__ == "__main__": main()
