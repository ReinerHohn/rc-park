#!/usr/bin/env python3
"""malplan.py - Malplan je Wand aus dem entzerrten Wandbild (24.11.2026, Nutzer 23.11.: "das Malen ist fuer mich das Kritischste").

NUR AUSGABE: liest das Wandbild der Kette (tools/fassade_fein.py: <daten>/fassade_fein/ortho_fNN_fein.png + abdeckung_fNN_fein.png + relief_fNN.png,
Rueckfall <daten>/fassade/ortho_fNN.png) und schreibt einen Malplan. Aendert nichts am Modell.

Ablauf je Wand (alles aus den Daten, keine Koordinaten im Code):
  1. Gueltige Flaeche = Abdeckung > 0 und (falls vorhanden) Modellflaeche aus relief_fNN.png > 0.
  2. Arbeitsraster ~2 cm, Median-Vorglaettung auf ~1 mm H0 (Fugen verschwinden, Quaderflaeche bleibt eine Zone).
  3. Clusterung in CIE-Lab: k-means (k_max) auf einer Stichprobe, dann nahe Zentren (Delta-E76 < --de-merge) zusammenlegen, Kleinstcluster aufloesen.
  4. Zonen glaetten: Mehrheitsfilter (~1 mm H0), Zusammenhangsteile < Mindestflaeche (Standard (2 mm)^2 in H0) an den Nachbarn geben.
  5. Je Zone: mittlere Farbe (sRGB-Hex, aus dem UNgeglaetteten Bild), Material-Vorschlag aus Lab + Textur (ANNAHME, Farbregel),
     naechster Ton der Grundpalette (Bestand des Nutzers, Memory user-malmaterial-bestand) + beste Zweiermischung, Flaechenanteil,
     Malschritte Grundierung -> Grundton -> Lasur -> Trockenbuersten -> Mattlack nach Doku/projekt/bahn-anlage.md (Gestaltung/Malen).
  0. WEISSABGLEICH (24.11.2026, Koordinator): Durchgang 1 roh -> Putz-Zone (hellste grosse neutrale Zone) je Wand; von Kries im linearen sRGB: Putz -> neutral,
     Helligkeit aller Waende auf den hellsten Putz (Schattenseite wird nicht schwarz); Guard Verstaerkung <= --max-gain; Durchgang 2 auf dem abgeglichenen Bild.
  6. Gebaeude: EINE Malfarbe je Material (flaechengewichtetes Mittel ueber alle Waende) -> plan['gebaeude'].
Wandnamen: Seite aus objekt.json 'seiten_konvention' (Achse der Wandnormale, wie befundliste/seiten.jpg) + Wand-ID, z. B. malplan_Nord_f00.jpg; ohne Konvention nur ID.
Ausgabe (--aus): malplan.json, malplan_<Seite>_<fNN>.jpg (roh | abgeglichen | Zonenkarte mit Legende), malplan.md (kurze Anleitung).
rc 0 = mindestens eine Wand, rc 3 = keine Wandbilder gefunden.

Aufruf:  tools/py tools/malplan.py <daten>/fassade_fein --aus <ordner> [--nur f02 f03] [--massstab 87] [--min-mm 2]
Lizenz: numpy/scipy (BSD), OpenCV (Apache-2.0), Pillow (HPND) - verkaufstauglich (modelle/LIZENZ_WERKZEUGE.md).
"""
import argparse, glob, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                     # -I: Geschwister (pfade, abdeckung_quellen) importierbar

# Grundpalette = was der Nutzer hat (Memory user-malmaterial-bestand, 17.11.2026). ANNAHME: Hex-Werte sind Naeherungen der Herstellertoene (nicht gemessen).
# rolle: "deck" = Grundton/Trockenbuersten erlaubt, "lasur" = NUR stark verduennt als Lasur (OBI-Wandfarbe: dick/kreidig, verschmiert Details - Memory).
PALETTE = [
    ("Army Painter Matt Grey (Grundierung)", "#7d7f7d", "deck"),
    ("Warpaints Matt White", "#f4f4f2", "deck"),
    ("Warpaints Matt Black", "#1c1c1c", "deck"),
    ("Warpaints Ultramarine Blue", "#23408e", "deck"),
    ("Warpaints Daemonic Yellow", "#f0c419", "deck"),
    ("Liquitex Burnt Sienna", "#7a3b26", "deck"),   # ANNAHME: Kuenstler-Acryl, auch deckend nutzbar (Memory: Lasur fuer Stein/Ziegel)
    ("OBI Weiss 0095", "#f1efe8", "lasur"),
    ("OBI Anthrazit 7403", "#3a3f44", "lasur"),
    ("OBI Rehbraun 8674", "#8a6a4c", "lasur"),
    ("Liquitex Burnt Sienna (verduennt)", "#7a3b26", "lasur"),
]

# Malschritte je Material nach Doku/projekt/bahn-anlage.md "Gestaltung / Malen" (Nutzer 23.11.2026). Reihenfolge immer
# Grundierung -> Grundton -> Lasur -> Trockenbuersten -> Mattlack; fehlende Schritte = "-".
SCHRITTE = {
    "Putz": dict(grundton="gebrochenes Weiss / Hellocker duenn in Schichten", lasur="graubraune Lasur (Wash), stark verduennt",
                 trockenbuersten="-"),
    "Sandstein-Quader": dict(grundton="Rotbraun", lasur="dunkle Lasur in die Fugen", trockenbuersten="heller Ton (Relief aus der Kette traegt das)"),
    "Stein grau": dict(grundton="Grau (Grundierung kann stehen bleiben oder aufhellen)", lasur="dunkle Lasur in die Fugen", trockenbuersten="heller Grauton"),
    "Holz": dict(grundton="Dunkelbraun", lasur="-", trockenbuersten="laengs wenig helleres Braun (Maserung)"),
    "Dachziegel": dict(grundton="Ziegelrot (Burnt Sienna)", lasur="dunkle Lasur zwischen die Ziegel", trockenbuersten="heller Orangeton auf die Kanten"),
    "Gruen (Patina/glasiert)": dict(grundton="Gruen (Kupferpatina bzw. glasierte Ziegel; Mischung aus Blau + Gelb + Grau)", lasur="dunkle Lasur", trockenbuersten="heller Ton auf Kanten"),
    "Gold/Uhr": dict(grundton="Gelb/Ocker als Gold-Ersatz", lasur="braune Lasur", trockenbuersten="-"),
    "Fenster dunkel": dict(grundton="Scheiben dunkel (Anthrazit/Schwarz), Rahmen fein absetzen", lasur="-", trockenbuersten="-",
                           mattlack="Scheiben aussparen oder danach glaenzend absetzen"),
    "Schatten/dunkel": dict(grundton="Dunkelgrau/Anthrazit", lasur="-", trockenbuersten="-"),
    "Sonstiges": dict(grundton="mittlere Zonenfarbe", lasur="passende dunklere Lasur", trockenbuersten="-"),
}
NICHT_MALEN = {"Himmel/Fremd"}   # Himmel im Wandbild = Loch/Fremdflaeche, nicht Modell


# ------------------------------------------------------------------ Farbraum
def srgb_zu_linear(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_zu_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0, 1)
    return np.clip(np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0, 0, 255)


def rgb_zu_lab(rgb):
    """sRGB 0..255 (..., 3) -> CIE-Lab D65 (L 0..100)."""
    lin = srgb_zu_linear(rgb)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def hex_zu_rgb(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def rgb_zu_hex(c): return "#%02x%02x%02x" % tuple(int(round(v)) for v in np.clip(c, 0, 255))


def delta_e(a, b): return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


# ------------------------------------------------------------------ Material-Vorschlag (Farbregel, ANNAHME)
def material_aus_lab(L, a, b):
    """Farbregel -> Materialname (ANNAHME, Vorschlag fuer die Malanleitung, keine Bauteilerkennung). "dunkel" wird in dunkel_aufloesen entschieden."""
    C = math.hypot(a, b); h = math.degrees(math.atan2(b, a)) % 360
    if b < -8 and L > 35 and C > 8: return "Himmel/Fremd"
    if a < -4 and L > 30 and C > 6: return "Gruen (Patina/glasiert)"
    if b > 35 and L > 55 and 60 <= h <= 100: return "Gold/Uhr"
    if L < 28: return "dunkel"
    if C < 5: return "Putz" if L >= 50 else "Stein grau"
    if L >= 62 and C < 15: return "Putz"                                    # Hellocker-/Cremeputz
    if 15 <= h <= 60 and C >= 35 and L >= 40: return "Dachziegel"            # kraeftig orange-rot (Buntsandstein im Foto meist C 10-30)
    if h <= 60 or h >= 340: return "Sandstein-Quader"                         # rot-/graubraun (Freiburger Buntsandstein)
    if h <= 95: return "Holz" if L < 45 else "Putz"
    return "Sonstiges"


def dunkel_material(L, a, b):
    """Dunkle Zone, die KEINE Oeffnung ist: Farbton entscheidet (dunkler Stein/Fuge bzw. Schatten)."""
    C = math.hypot(a, b); h = math.degrees(math.atan2(b, a)) % 360
    return "Sandstein-Quader" if C >= 3 and (h <= 95 or h >= 340) else "Schatten/dunkel"


def _pal(rolle): return [(n, h) for n, h, r in PALETTE if r == rolle]


def palette_naechste(rgb, rolle="deck"):
    lab = rgb_zu_lab(rgb); best = min(_pal(rolle), key=lambda p: delta_e(rgb_zu_lab(hex_zu_rgb(p[1])), lab))
    return dict(name=best[0], hex=best[1], delta_e=round(delta_e(rgb_zu_lab(hex_zu_rgb(best[1])), lab), 1))


def palette_mischung(rgb, rolle="deck"):
    """Beste Zweiermischung (Anteile 1:3, 1:1, 3:1) aus Farben der Rolle - ANNAHME: Mischung linear im linearen sRGB (grobe Naeherung echter Pigmente).
    Nur Abtoenen/Abdunkeln (ein Partner unbunt: Weiss/Schwarz/Grau) - zwei Buntfarben mischen sich als Pigment subtraktiv (Blau+Gelb = Gruen), das kann das Modell nicht."""
    lab = rgb_zu_lab(rgb); best = None; P = _pal(rolle)
    unbunt = lambda h_: math.hypot(*rgb_zu_lab(hex_zu_rgb(h_))[1:]) < 5
    for i, (n1, h1) in enumerate(P):
        for n2, h2 in P[i + 1:]:
            if not (unbunt(h1) or unbunt(h2)): continue
            for w in (0.0, 0.25, 0.5, 0.75, 1.0):                           # 0/1 = Farbe pur
                m = linear_zu_srgb(w * srgb_zu_linear(hex_zu_rgb(h1)) + (1 - w) * srgb_zu_linear(hex_zu_rgb(h2)))
                d = delta_e(rgb_zu_lab(m), lab)
                if best is None or d < best[0] - 1e-9: best = (d, n1, n2, w, m)
    teil = lambda t: f"{t} Teil" if t == 1 else f"{t} Teile"
    d, n1, n2, w, m = best; t1 = int(round(w * 4))
    text = f"{n1} pur" if t1 == 4 else f"{n2} pur" if t1 == 0 else f"{teil(t1)} {n1} + {teil(4 - t1)} {n2}"
    return dict(text=text, hex=rgb_zu_hex(m), delta_e=round(d, 1))


# ------------------------------------------------------------------ Clusterung + Glaettung
def kmeans_lab(X, k, seed=0, iters=30):
    """Einfaches k-means++ (numpy), deterministisch. X (n,3)."""
    rng = np.random.default_rng(seed); n = len(X); k = max(1, min(k, n))
    C = [X[rng.integers(n)]]
    d2 = ((X - C[0]) ** 2).sum(1)
    for _ in range(1, k):
        if d2.sum() <= 0: break
        C.append(X[rng.choice(n, p=d2 / d2.sum())]); d2 = np.minimum(d2, ((X - C[-1]) ** 2).sum(1))
    C = np.array(C)
    for _ in range(iters):
        lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(2), 1)
        Cn = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(len(C))])
        if np.allclose(Cn, C, atol=0.05): C = Cn; break
        C = Cn
    return C


def zentren_vereinen(X, C, de_merge, min_anteil):
    """Nahe Zentren (Delta-E < de_merge) und Kleinstcluster (< min_anteil der Stichprobe) zusammenlegen."""
    C = [c for c in C]
    while len(C) > 1:
        lab = np.argmin(((X[:, None, :] - np.array(C)[None]) ** 2).sum(2), 1); n = np.bincount(lab, minlength=len(C))
        C = [X[lab == j].mean(0) if n[j] else C[j] for j in range(len(C))]
        D = np.array([[delta_e(a, b) if i != j else 1e9 for j, b in enumerate(C)] for i, a in enumerate(C)])
        i, j = np.unravel_index(np.argmin(D), D.shape); klein = int(np.argmin(n))
        if D[i, j] < de_merge: pass
        elif n[klein] < min_anteil * len(X):
            i = klein; D[i, i] = 1e9; j = int(np.argmin(D[i]))
        else: break
        w = n[i] + n[j]; C[i] = (C[i] * n[i] + C[j] * n[j]) / max(w, 1); del C[j]
    return np.array(C)


def mehrheitsfilter(lbl, gueltig, k, fenster):
    if fenster < 2: return lbl
    best = np.full(lbl.shape, -1.0); out = lbl.copy()
    for j in range(k):
        s = ndi.uniform_filter(((lbl == j) & gueltig).astype(np.float32), fenster, mode="constant")
        m = s > best; best[m] = s[m]; out[m] = j
    out[~gueltig] = -1; return out


def kleine_zonen_aufloesen(lbl, gueltig, min_px):
    """Zusammenhangsteile < min_px bekommen das Label des naechsten Pixels einer grossen Zone."""
    lbl = lbl.copy()
    for _ in range(3):
        weg = np.zeros(lbl.shape, bool)
        for j in np.unique(lbl[lbl >= 0]):
            cc, n = ndi.label(lbl == j)
            if n == 0: continue
            gr = np.bincount(cc.ravel())[1:]; klein = np.where(gr < min_px)[0] + 1
            if len(klein): weg |= np.isin(cc, klein)
        if not weg.any(): break
        behalt = gueltig & ~weg & (lbl >= 0)
        if not behalt.any(): break
        _, idx = ndi.distance_transform_edt(~behalt, return_indices=True)
        lbl[weg] = lbl[idx[0][weg], idx[1][weg]]
    lbl[~gueltig] = -1; return lbl


# ------------------------------------------------------------------ Eingabe
def seiten_konvention(objekt_json):
    """{'+x': 'Nord', ...} aus objekt.json 'seiten_konvention' (wie tools/abdeckung_quellen.seiten_aus_konvention). Fehlt sie -> {}: dann KEIN Seitenname und
    keine eigene Kompassrechnung - sonst hiesse dieselbe Wand im Malplan anders als in seiten.jpg/neben-Bildern (Koordinator 24.11.2026)."""
    if not objekt_json or not os.path.exists(objekt_json): return {}
    try:
        from abdeckung_quellen import seiten_aus_konvention
        return seiten_aus_konvention(json.load(open(objekt_json)))
    except Exception as e: print(f"  Warnung: seiten_konvention aus {objekt_json} nicht lesbar ({type(e).__name__})"); return {}


def seite_name(n, konv):
    """Achse mit groesstem Skalarprodukt zur Wandnormale (Objektkoordinaten) -> Seitenname der Konvention (wie tools/befundliste.seite_name)."""
    if not konv or n is None: return ""
    ach = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
    return konv.get(max(ach, key=lambda k: ach[k][0] * n[0] + ach[k][1] * n[1]), "")


def waende_finden(ordner, objekt_json=None):
    """-> (Liste dict(id, seite, bild, abdeckung, relief, zelle_m), objekt.json mit Konvention oder None). Seitenkonvention aus objekt.json
    (Standard: 'objekt' in fassaden.json, ueber tools/pfade.repo_pfad aufgeloest)."""
    meta = {}; obj_rel = None
    fj = os.path.join(ordner, "fassaden.json")
    if os.path.exists(fj):
        try:
            fd = json.load(open(fj)); obj_rel = fd.get("objekt")
            for f in fd.get("fassaden") or []: meta[f["id"]] = f
        except Exception as e: print(f"  Warnung: {fj} nicht lesbar ({type(e).__name__}) - Wandnamen ohne Seite")
    if not objekt_json and obj_rel:
        try:
            from pfade import repo_pfad; objekt_json = repo_pfad(obj_rel)
        except Exception: objekt_json = obj_rel
    konv = seiten_konvention(objekt_json)
    ids = sorted({os.path.basename(p).split("_")[1] for p in glob.glob(os.path.join(ordner, "ortho_f*.png"))})
    out = []
    for i in ids:
        bild = next((p for p in (os.path.join(ordner, f"ortho_{i}_fein.png"), os.path.join(ordner, f"ortho_{i}.png")) if os.path.exists(p)), None)
        if not bild: continue
        ab = next((p for p in (os.path.join(ordner, f"abdeckung_{i}_fein.png"), os.path.join(ordner, f"abdeckung_{i}.png")) if os.path.exists(p)), None)
        rel = os.path.join(ordner, f"relief_{i}.png"); m = meta.get(i, {})
        zelle = float((m.get("raster") or {}).get("zelle") or 0) or None
        out.append(dict(id=i, seite=seite_name(m.get("n"), konv), bild=bild, abdeckung=ab, relief=rel if os.path.exists(rel) else None, zelle_m=zelle))
    return out, (objekt_json if konv else None)


# ------------------------------------------------------------------ Weissabgleich (von Kries im linearen sRGB, Bezug Putz)
def luminanz(lin): return float(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])


def putz_bezug(zonen, voll, rgb, min_anteil):
    """Hellste grosse neutrale Zone = Putz (Material 'Putz', Anteil >= min_anteil; bei mehreren die hellste) -> mittleres lineares RGB oder None."""
    k = [z for z in zonen if z["material"] == "Putz" and z["anteil"] >= min_anteil]; art = "Putz"
    if not k:      # Putz im Farbstich (Schattenseite mit Himmelslicht) faellt roh unter 'Himmel/Fremd': hellste grosse, nur maessig bunte Zone (C* < 25)
        k = [z for z in zonen if z["anteil"] >= min_anteil and math.hypot(*z["lab"][1:]) < 25 and z["lab"][0] > 25]; art = "hellste grosse Zone (Putz im Farbstich, ANNAHME)"
    if not k: return None
    z = max(k, key=lambda z_: z_["lab"][0]); m = voll == z["label"]
    return (srgb_zu_linear(rgb[m]).mean(0), art) if m.any() else None


def abgleichen(rgb, gain):
    """von Kries: je Kanal im linearen sRGB verstaerken (gain = Ziel-Y / Putz je Kanal -> Putz neutral und auf gemeinsamer Helligkeit)."""
    return linear_zu_srgb(srgb_zu_linear(rgb) * np.asarray(gain, float)[None, None, :]).round().astype(np.uint8)


def gebaeude_farben(waende):
    """Eine Malfarbe je Material fuer das ganze Gebaeude: flaechengewichtetes Mittel (linear) der abgeglichenen Zonenfarben aller Waende."""
    acc = {}
    for w in waende:
        for z in w["zonen"]:
            if z["nicht_malen"]: continue
            e = acc.setdefault(z["material"], dict(s=np.zeros(3), d=np.zeros(3), h=np.zeros(3), a=0.0, waende=[]))
            f = z["flaeche_m2"]; e["a"] += f; e["waende"].append(w["wand"])
            for k_, q_ in (("s", "hex"), ("d", "ton_dunkel"), ("h", "ton_hell")): e[k_] += f * srgb_zu_linear(hex_zu_rgb(z[q_]))
    out = {}
    for m, e in sorted(acc.items(), key=lambda kv: -kv[1]["a"]):
        if e["a"] <= 0: continue
        c = linear_zu_srgb(e["s"] / e["a"])
        z = dict(material=m, hex=rgb_zu_hex(c), ton_dunkel=rgb_zu_hex(linear_zu_srgb(e["d"] / e["a"])), ton_hell=rgb_zu_hex(linear_zu_srgb(e["h"] / e["a"])))
        z["palette"] = palette_naechste(c); z["mischung"] = palette_mischung(c); z["schritte"] = malschritte(z)
        out[m] = dict(hex=z["hex"], flaeche_m2=round(e["a"], 2), waende=sorted(set(e["waende"])), ton_dunkel=z["ton_dunkel"], ton_hell=z["ton_hell"],
                      palette=z["palette"], mischung=z["mischung"], schritte=z["schritte"])
    return out


# ------------------------------------------------------------------ Kern
def malplan_wand(rgb, gueltig, zelle_m, massstab=87, min_mm=2.0, arbeit_m=0.02, k_max=8, de_merge=12.0, seed=0, fenster_kontrast=20.0, fenster_textur=6.0, glatt_mm=0.5):
    """rgb (H, W, 3) uint8, gueltig (H, W) bool, zelle_m = Meter je Pixel. -> (zonen-Liste, Labelbild in Originalgroesse, Info)."""
    H, W = gueltig.shape
    f = max(1, int(round(arbeit_m / zelle_m)))                                     # Arbeitsraster
    hs, ws = H // f * f, W // f * f
    if hs == 0 or ws == 0: f = 1; hs, ws = H, W
    rs = rgb[:hs, :ws].reshape(hs // f, f, ws // f, f, 3).astype(np.float32)
    gs = gueltig[:hs, :ws].reshape(hs // f, f, ws // f, f)
    gw = gs.mean((1, 3)) > 0.5
    cnt = np.maximum(gs.sum((1, 3)), 1)[..., None]
    rw = (rs * gs[..., None]).sum((1, 3)) / cnt
    zw = zelle_m * f                                                                  # Meter je Arbeitspixel
    mm_px = (massstab / 1000.0) / zw                                                  # Arbeitspixel je 1 mm H0 (1 mm H0 = massstab mm echt)
    lab = rgb_zu_lab(rw).astype(np.float32)
    # Vorglaettung (~1 mm H0): Median je Kanal, nur gueltige Nachbarn zaehlen (ungueltig = Mittelwert, damit Raender nicht verschmieren)
    fen = max(1, int(round(glatt_mm * mm_px)) | 1)
    labg = lab.copy()
    if gw.any() and fen > 1:
        mittel = lab[gw].mean(0)
        for c in range(3):
            ch = np.where(gw, lab[..., c], mittel[c]); labg[..., c] = ndi.median_filter(ch, size=fen, mode="nearest")
    X = labg[gw]
    if len(X) < 10: return [], np.full((H, W), -1, np.int16), dict(fehler="zu wenig gueltige Flaeche")
    rng = np.random.default_rng(seed); S = X[rng.choice(len(X), min(len(X), 40000), replace=False)].astype(np.float64)
    C = kmeans_lab(S, k_max, seed=seed)
    C = zentren_vereinen(S, C, de_merge, min_anteil=0.005)
    lbl = np.full(gw.shape, -1, np.int32)
    C32 = C.astype(np.float32); zu = np.empty(len(X), np.int32)
    for i0 in range(0, len(X), 200000): zu[i0:i0 + 200000] = np.argmin(((X[i0:i0 + 200000, None, :] - C32[None]) ** 2).sum(2), 1)
    lbl[gw] = zu
    lbl = mehrheitsfilter(lbl, gw, len(C), fen)
    min_px = int(math.ceil((min_mm * mm_px) ** 2))
    lbl = kleine_zonen_aufloesen(lbl, gw, max(1, min_px))
    # Material je Cluster; dunkle Cluster je Zusammenhangsteil: Oeffnung (Fenster/Scharte) nur wenn deutlich dunkler als der Ring drumherum UND
    # innen gleichmaessig (Fugen/Steinstruktur = Textur) - sonst dunkler Stein/Schatten nach Farbton. Schwellen = Parameter, keine Koordinaten.
    Lroh = rgb_zu_lab(rw)[..., 0]
    tex = np.sqrt(np.maximum(ndi.uniform_filter(Lroh ** 2, fen) - ndi.uniform_filter(Lroh, fen) ** 2, 0))
    lab_c = [rgb_zu_lab(linear_zu_srgb(srgb_zu_linear(rw[lbl == j]).mean(0))) if (lbl == j).any() else C[j] for j in range(len(C))]
    mat_c = [material_aus_lab(*l_) for l_ in lab_c]
    MATS = list(dict.fromkeys(REIHENFOLGE_MAT + sorted(NICHT_MALEN))); mid = np.full(lbl.shape, -1, np.int32); dunkel_teile = []
    for j in range(len(C)):
        m = lbl == j
        if not m.any(): continue
        if mat_c[j] != "dunkel": mid[m] = MATS.index(mat_c[j]); continue
        cc, n = ndi.label(m)
        for t in range(1, n + 1):
            k_ = cc == t; ring = ndi.binary_dilation(k_, iterations=max(1, fen)) & ~k_ & gw
            kontrast = float(np.median(Lroh[ring]) - np.median(Lroh[k_])) if ring.any() else 0.0
            tx = float(np.median(tex[k_])); L_, a_, b_ = rgb_zu_lab(linear_zu_srgb(srgb_zu_linear(rw[k_]).mean(0)))
            ring_voll = ndi.binary_dilation(k_, iterations=max(1, fen)) & ~k_
            umschlossen = float(ring.sum() / max(ring_voll.sum(), 1))           # Oeffnung liegt IN der Wand; dunkle Eckquader/Randstreifen beruehren den Wandrand
            oeff = kontrast >= fenster_kontrast and tx <= fenster_textur and umschlossen >= 0.9
            if oeff: ma = "Fenster dunkel"
            else:                                                                # dunkler Stein/Fuge/Schatten gehoert zum Material ringsum (nicht-dunkle Nachbarcluster)
                rm = [mat_c[q] for q in lbl[ring] if q >= 0 and mat_c[q] not in ("dunkel",) and mat_c[q] not in NICHT_MALEN]
                ma = max(set(rm), key=rm.count) if rm else dunkel_material(L_, a_, b_)
                if ma == "Putz": ma = dunkel_material(L_, a_, b_)            # dunkel neben Putz ist kein Putzton: eigener Farbton entscheidet (dunkler Sandstein bzw. Schatten)
            mid[k_] = MATS.index(ma)
            dunkel_teile.append(dict(px=int(k_.sum()), kontrast_L=round(kontrast, 1), textur_L=round(tx, 1), umschlossen=round(umschlossen, 2), material=ma))
    mid = kleine_zonen_aufloesen(mid, gw, max(1, min_px))
    gesamt = int(gw.sum()); zonen = []
    for mi, ma in enumerate(MATS):
        m = mid == mi
        if not m.any(): continue
        farbe = linear_zu_srgb(srgb_zu_linear(rw[m]).mean(0))                     # Mittel im linearen Licht, aus dem ungeglaetteten Bild
        L_, a_, b_ = rgb_zu_lab(farbe)
        toene = []
        for j in range(len(C)):
            mj = m & (lbl == j)
            if mj.sum() >= 0.03 * m.sum(): toene.append(dict(hex=rgb_zu_hex(linear_zu_srgb(srgb_zu_linear(rw[mj]).mean(0))), L=round(float(rgb_zu_lab(linear_zu_srgb(srgb_zu_linear(rw[mj]).mean(0)))[0]), 1), anteil_in_zone=round(float(mj.sum() / m.sum()), 3)))
        toene.sort(key=lambda t_: t_["L"])
        zonen.append(dict(label=mi, material=ma, hex=rgb_zu_hex(farbe), lab=[round(float(L_), 1), round(float(a_), 1), round(float(b_), 1)],
                          textur_L=round(float(np.median(tex[m])), 1), anteil=round(m.sum() / max(gesamt, 1), 4), flaeche_m2=round(float(m.sum()) * zw * zw, 2),
                          flaeche_h0_cm2=round(float(m.sum()) * zw * zw / massstab ** 2 * 1e4, 2), teile=int(ndi.label(m)[1]), toene=toene,
                          ton_dunkel=toene[0]["hex"] if toene else rgb_zu_hex(farbe), ton_hell=toene[-1]["hex"] if toene else rgb_zu_hex(farbe)))
    lbl = mid
    # Labelbild zurueck auf Originalgroesse (naechster Nachbar)
    voll = np.full((H, W), -1, np.int16)
    up = np.repeat(np.repeat(lbl, f, 0), f, 1).astype(np.int16); voll[:up.shape[0], :up.shape[1]] = up
    voll[~gueltig] = -1
    info = dict(arbeit_zelle_m=round(zw, 4), fenster_px=fen, min_zone_px=min_px, min_zone_mm=min_mm, cluster=len(C), gueltig_m2=round(gesamt * zw * zw, 1), dunkle_teile=dunkel_teile)
    return zonen, voll, info


def malschritte(z):
    s = SCHRITTE.get(z["material"], SCHRITTE["Sonstiges"]); pal, mix = z["palette"], z["mischung"]
    las = palette_naechste(hex_zu_rgb(z["ton_dunkel"]), "lasur"); tb = palette_mischung(hex_zu_rgb(z["ton_hell"]))
    return [dict(schritt="Grundierung", was="Army Painter Matt Grey, duenn mit Pinsel, 2 Schichten"),
            dict(schritt="Grundton", was=f"{s['grundton']} - Ziel {z['hex']}; naechster Ton {pal['name']} (dE {pal['delta_e']}), Mischung {mix['text']} (dE {mix['delta_e']})"),
            dict(schritt="Lasur", was="-" if s["lasur"] == "-" else f"{s['lasur']} - dunkler Ton {z['ton_dunkel']}: {las['name']} stark verduennt"),
            dict(schritt="Trockenbuersten", was="-" if s["trockenbuersten"] == "-" else f"{s['trockenbuersten']} - heller Ton {z['ton_hell']}: {tb['text']}"),
            dict(schritt="Mattlack", was=s.get("mattlack", "Homy Arty Mattlack (Spray), duenn"))]


REIHENFOLGE_MAT = ["Putz", "Stein grau", "Sandstein-Quader", "Dachziegel", "Holz", "Gruen (Patina/glasiert)", "Gold/Uhr", "Schatten/dunkel", "Fenster dunkel", "Sonstiges"]


def zonen_anreichern(zonen):
    """Palette, Mischung, Schritte, Reihenfolge (grosse Grundflaechen zuerst, Details/Fenster zuletzt)."""
    for z in zonen:
        z["nicht_malen"] = z["material"] in NICHT_MALEN
        z.setdefault("ton_dunkel", z["hex"]); z.setdefault("ton_hell", z["hex"])
        rgb = hex_zu_rgb(z["hex"]); z["palette"] = palette_naechste(rgb); z["mischung"] = palette_mischung(rgb)
        z["schritte"] = [] if z["nicht_malen"] else malschritte(z)
    mal = sorted([z for z in zonen if not z["nicht_malen"]], key=lambda z: (REIHENFOLGE_MAT.index(z["material"]) if z["material"] in REIHENFOLGE_MAT else 99, -z["anteil"]))
    for i, z in enumerate(mal): z["reihenfolge"] = i + 1
    return sorted(zonen, key=lambda z: z.get("reihenfolge", 999))


# ------------------------------------------------------------------ Bild
def schrift(gr):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if os.path.exists(p): return ImageFont.truetype(p, gr)
    try: return ImageFont.load_default(size=gr)
    except TypeError: return ImageFont.load_default()


def bild_schreiben(pfad, rgb, gueltig, voll, zonen, titel, max_h=1400, rgb_k=None):
    H, W = gueltig.shape; s = min(1.0, max_h / H); h, w = max(1, int(H * s)), max(1, int(W * s))
    links = Image.fromarray(rgb).resize((w, h), Image.BILINEAR)
    if rgb_k is not None:                                                         # roh | abgeglichen nebeneinander im linken Feld
        lk = Image.new("RGB", (2 * w + 6, h), (255, 255, 255)); lk.paste(links, (0, 0)); lk.paste(Image.fromarray(rgb_k).resize((w, h), Image.BILINEAR), (w + 6, 0))
        links = lk
    karte = np.zeros((H, W, 3), np.uint8); karte[...] = (40, 40, 40)
    for z in zonen:
        m = voll == z["label"]; c = hex_zu_rgb(z["hex"]).astype(np.uint8)
        if z["nicht_malen"]: c = np.array([90, 90, 140], np.uint8)
        karte[m] = c
    # Zonengrenzen schwarz, damit gleich helle Zonen trennbar bleiben
    rand = (voll != np.roll(voll, 1, 0)) | (voll != np.roll(voll, 1, 1)); rand &= voll >= 0
    rand = ndi.binary_dilation(rand, iterations=max(1, int(round(1.5 / s))))
    karte[rand] = (0, 0, 0)
    rechts = Image.fromarray(karte).resize((w, h), Image.NEAREST)
    leg_w = 640; zeile = 30; f = schrift(17); fk = schrift(14)
    lw = links.width
    out = Image.new("RGB", (lw + w + 30 + leg_w, max(h, 60 + zeile * 2 * len(zonen) + 40)), (255, 255, 255))
    out.paste(links, (0, 0)); out.paste(rechts, (lw + 10, 0))
    d = ImageDraw.Draw(out); x0 = lw + w + 30; d.text((x0, 8), titel, fill=(0, 0, 0), font=f)
    d.text((x0, 32), ("Wandbild roh | weissabgeglichen (Putz) | Zonen" if rgb_k is not None else "links Wandbild | rechts Zonen") + " (Zonenfarbe = Mittelfarbe)", fill=(80, 80, 80), font=fk)
    y = 60
    for z in zonen:
        c = tuple(int(v) for v in hex_zu_rgb(z["hex"])); d.rectangle([x0, y, x0 + 40, y + 2 * zeile - 8], fill=c, outline=(0, 0, 0))
        pc = tuple(int(v) for v in hex_zu_rgb(z["palette"]["hex"])); d.rectangle([x0 + 44, y, x0 + 58, y + 2 * zeile - 8], fill=pc, outline=(0, 0, 0))
        nr = f"{z['reihenfolge']}." if z.get("reihenfolge") else "--"
        d.text((x0 + 66, y), f"{nr} {z['material']}  {z['hex']}  {z['anteil'] * 100:.0f} %" + ("  (NICHT MALEN)" if z["nicht_malen"] else ""), fill=(0, 0, 0), font=f)
        d.text((x0 + 66, y + zeile - 6), f"Palette: {z['palette']['name']} (dE {z['palette']['delta_e']})", fill=(60, 60, 60), font=fk)
        y += 2 * zeile
    out.save(pfad, quality=88)


# ------------------------------------------------------------------ Anleitung
def md_schreiben(pfad, plan):
    z = [f"# Malplan {plan.get('objekt') or ''}".rstrip(), "",
         f"Automatisch aus den Wandbildern ({plan['quelle']}), Massstab 1:{plan['massstab']}, Mindestzone {plan['min_mm']} mm in H0. "
         "Material = Vorschlag aus Farbe/Textur (ANNAHME), vor dem Malen am Foto pruefen. Palette-Hex = Naeherung der Herstellertoene (ANNAHME). "
         "Zonenfarben sind fotografiert; je Wand weissabgeglichen (Putz -> neutral, Helligkeit auf den hellsten Putz aller Waende). ANNAHME: Putz ist neutral hell; "
         "Restfehler (Streulicht, Wetter) moeglich - Ton am Original pruefen. "
         "OBI-Wandfarben nur stark verduennt als Lasur, nie als Grundton.", "",
         "Grundablauf (Doku/projekt/bahn-anlage.md): Grundierung -> Grundton -> Lasur -> Trockenbuersten -> Mattlack. "
         "Erst an Fehldrucken/Probewaenden ueben (2-3 Stueck). Grosse Grundflaechen zuerst, Fenster/Details zuletzt.", "",
         "## Eine Malfarbe je Material (ganzes Gebaeude, flaechengewichtet ueber alle Waende)"]
    for m, g in (plan.get("gebaeude") or {}).items():
        z.append(f"- {m} {g['hex']} ({g['flaeche_m2']} m2; {', '.join(g['waende'])}): Grundton {g['mischung']['text']} (dE {g['mischung']['delta_e']}); "
                 f"Lasur: {g['schritte'][2]['was']}; Trockenbuersten: {g['schritte'][3]['was']}")
    z.append("")
    for w in plan["waende"]:
        z.append(f"## Wand {w['wand']} (Bild {os.path.basename(w['bild_ausgabe'])})")
        for zo in w["zonen"]:
            if zo["nicht_malen"]: z.append(f"- (nicht malen) {zo['material']} {zo['hex']}, {zo['anteil'] * 100:.0f} % - Himmel/Fremdflaeche im Wandbild"); continue
            z.append(f"- {zo['reihenfolge']}. {zo['material']} {zo['hex']}, {zo['anteil'] * 100:.0f} % (~{zo['flaeche_h0_cm2']} cm2 in H0): "
                     f"Grundton {zo['mischung']['text']} (oder {zo['palette']['name']}); Lasur: {zo['schritte'][2]['was']}; Trockenbuersten: {zo['schritte'][3]['was']}")
        z.append("")
    open(pfad, "w").write("\n".join(z) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ordner", help="<daten>/fassade_fein (oder <daten>/fassade); ist es der Datenordner, wird fassade_fein bzw. fassade darunter genommen")
    ap.add_argument("--aus", required=True); ap.add_argument("--nur", nargs="*", default=[])
    ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--min-mm", type=float, default=2.0)
    ap.add_argument("--arbeit-m", type=float, default=0.02, help="Arbeitsraster in Metern (Standard 2 cm)")
    ap.add_argument("--k-max", type=int, default=8); ap.add_argument("--de-merge", type=float, default=12.0)
    ap.add_argument("--fenster-kontrast", type=float, default=20.0, help="dunkle Zone = Oeffnung, wenn L* des Rings um mindestens so viel heller ist ...")
    ap.add_argument("--fenster-textur", type=float, default=6.0, help="... und die L*-Streuung innen hoechstens so gross ist (Fugen/Steinstruktur = Textur)")
    ap.add_argument("--glatt-mm", type=float, default=0.5, help="Fenster fuer Median-Vorglaettung und Mehrheitsfilter in mm H0 (0,5 mm = 4 cm echt: Fugen weg, Scharten bleiben)")
    ap.add_argument("--objekt", default="")
    ap.add_argument("--objekt-json", default="", help="objekt.json fuer seiten_konvention; Standard: 'objekt' aus fassaden.json")
    ap.add_argument("--ohne-weissabgleich", dest="weissabgleich", action="store_false", help="Farben roh aus dem Wandbild (kein Abgleich auf den Putz)")
    ap.add_argument("--putz-min-anteil", type=float, default=0.10, help="Putz-Zone zaehlt als Weissbezug ab diesem Wandanteil")
    ap.add_argument("--max-gain", type=float, default=4.0, help="Guard: hoechste Verstaerkung je Kanal beim Abgleich")
    a = ap.parse_args(argv)
    ordner = a.ordner
    if not glob.glob(os.path.join(ordner, "ortho_f*.png")):
        for u in ("fassade_fein", "fassade"):
            if glob.glob(os.path.join(ordner, u, "ortho_f*.png")): ordner = os.path.join(ordner, u); break
    waende, obj_json = waende_finden(ordner, a.objekt_json or None)
    waende = [w for w in waende if not a.nur or w["id"] in a.nur]
    if not waende: print(f"malplan: keine Wandbilder ortho_fNN*.png in {ordner}"); return 3
    if not obj_json: print("  Hinweis: keine seiten_konvention (objekt.json) - Waende nur mit ID benannt")
    os.makedirs(a.aus, exist_ok=True)
    plan = dict(objekt=a.objekt, objekt_json=obj_json, quelle=os.path.abspath(ordner), massstab=a.massstab, min_mm=a.min_mm, weissabgleich=a.weissabgleich,
                palette=[dict(name=n, hex=h, rolle=r) for n, h, r in PALETTE],
                hinweis="nur Ausgabe, aendert nichts am Modell; Material/Palette = ANNAHME (Farbregel bzw. Naeherung); Farben nach Weissabgleich auf den Putz", waende=[])
    kw = dict(massstab=a.massstab, min_mm=a.min_mm, arbeit_m=a.arbeit_m, k_max=a.k_max, de_merge=a.de_merge, fenster_kontrast=a.fenster_kontrast, fenster_textur=a.fenster_textur, glatt_mm=a.glatt_mm)
    roh = []
    for w in waende:
        rgb = np.array(Image.open(w["bild"]).convert("RGB")); H, W_ = rgb.shape[:2]
        g = np.ones((H, W_), bool)
        if w["abdeckung"]:
            ab = np.array(Image.open(w["abdeckung"]).convert("L"))
            if ab.shape == g.shape: g &= ab > 0
        if w["relief"]:
            r = np.array(Image.open(w["relief"]))
            if r.shape == g.shape: g &= r > 0
        g &= rgb.max(2) > 3                                                        # schwarze Loecher im Wandbild
        zelle = w["zelle_m"] or 0.01
        if not w["zelle_m"]: print(f"  {w['id']}: ANNAHME Zelle 1 cm (kein raster.zelle in fassaden.json)")
        # Durchgang 1 (roh): Putz-Bezug dieser Wand
        putz = None
        if a.weissabgleich:
            z0, v0, _ = malplan_wand(rgb, g, zelle, **kw); putz = putz_bezug(z0, v0, rgb, a.putz_min_anteil)
        roh.append(dict(w=w, rgb=rgb, g=g, zelle=zelle, putz=putz[0] if putz else None, putz_art=putz[1] if putz else None))
    # Gemeinsames Ziel: Helligkeit des hellsten Putzes aller Waende (Sonnenseite am naechsten am Material); Guard: Verstaerkung je Kanal <= --max-gain
    bez = [r_["putz"] for r_ in roh if r_["putz"] is not None]; Y_ziel = max(luminanz(p_) for p_ in bez) if bez else None; gains_ok = []
    for r_ in roh:
        r_["gain"] = None
        if r_["putz"] is not None:
            gn = Y_ziel / np.maximum(r_["putz"], 1e-4); r_["quelle"] = f"{r_['putz_art']} dieser Wand"
            if gn.max() > a.max_gain: gn = gn * (a.max_gain / gn.max()); r_["quelle"] += f" (Guard: auf x{a.max_gain} begrenzt)"
            r_["gain"] = gn; gains_ok.append(gn)
    for r_ in roh:
        if r_["gain"] is None:
            r_["gain"] = np.median(gains_ok, 0) if gains_ok else np.ones(3)
            r_["quelle"] = (f"ANNAHME: Median der anderen Waende (kein Putz >= {100 * a.putz_min_anteil:.0f} %)" if gains_ok else "kein Abgleich (kein Putz)") if a.weissabgleich else "aus"
    # Durchgang 2: auf dem abgeglichenen Wandbild
    for r_ in roh:
        w, rgb, g, zelle = r_["w"], r_["rgb"], r_["g"], r_["zelle"]
        rgb_k = abgleichen(rgb, r_["gain"]) if a.weissabgleich else rgb
        zonen, voll, info = malplan_wand(rgb_k, g, zelle, **kw)
        zonen = zonen_anreichern(zonen)
        name = (f"{w['seite']}_" if w["seite"] else "") + w["id"]                # Seite (objekt.json seiten_konvention) + Wand-ID der Kette
        bp = os.path.join(a.aus, f"malplan_{name}.jpg")
        if zonen: bild_schreiben(bp, rgb, g, voll, zonen, f"Malplan {name} ({a.objekt})" if a.objekt else f"Malplan {name}", rgb_k=rgb_k if a.weissabgleich else None)
        wb = dict(gain=[round(float(x), 3) for x in r_["gain"]], quelle=r_["quelle"], putz_roh=rgb_zu_hex(linear_zu_srgb(r_["putz"])) if r_["putz"] is not None else None)
        plan["waende"].append(dict(wand=name, id=w["id"], seite=w["seite"], bild=w["bild"], bild_ausgabe=bp if zonen else "", zelle_m=zelle, weissabgleich=wb, **info, zonen=zonen))
        for t_ in sorted(info.get("dunkle_teile") or [], key=lambda t_: -t_["px"])[:8]: print(f"    dunkel {t_['px']} px: Kontrast {t_['kontrast_L']}, Textur {t_['textur_L']}, umschlossen {t_['umschlossen']} -> {t_['material']}")
        print(f"  {name}: Abgleich x{'/'.join(f'{x:.2f}' for x in r_['gain'])} ({r_['quelle']}); {len(zonen)} Zonen, " + ", ".join(f"{z['material']} {z['hex']} {z['anteil'] * 100:.0f}%" for z in zonen))
    plan["gebaeude"] = gebaeude_farben(plan["waende"])
    for m_, v_ in plan["gebaeude"].items(): print(f"  GEBAEUDE {m_}: {v_['hex']} ({v_['flaeche_m2']} m2, {len(v_['waende'])} Waende) -> {v_['mischung']['text']} (dE {v_['mischung']['delta_e']})")
    json.dump(plan, open(os.path.join(a.aus, "malplan.json"), "w"), indent=1, ensure_ascii=False)
    md_schreiben(os.path.join(a.aus, "malplan.md"), plan)
    print(f"malplan: {len(plan['waende'])} Waende -> {a.aus}/malplan.json, malplan.md, malplan_<wand>.jpg")
    return 0 if any(w["zonen"] for w in plan["waende"]) else 3


if __name__ == "__main__":
    sys.exit(main())
