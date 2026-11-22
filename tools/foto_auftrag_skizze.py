#!/usr/bin/env python3
"""foto_auftrag_skizze.py - FOTOAUFTRAG FRUEH, GENAU UND ALS BILD (22.11.2026, schwabentor-1122).

WARUM: Die Kette wusste schon nach der SfM, welche Seite nicht angebunden ist (pipe/sfm/seiten_modelle.json 'fotoluecken': Teil 1, 127 Bilder,
"Suedostseite", Azimut 141 Grad; Wolke Wandpunkte 2-15 m: Nord 2,1 Mio., West 832 000, Ost 411 000, Sued 12 000). Der Nutzer erfuhr es erst auf Nachfrage und
nur als Text. Zehn gezielte Fotos vor Ort ersetzen Stunden Rechnen. Dieses Werkzeug macht daraus OHNE Handeintrag eine Skizze mit Standpunkten.

AUS DEN KETTENDATEN (nichts fest eingetragen, jedes Objekt):
  LoD2 (objekt.json lod2.gml + Nachbarkacheln, tools/lod2_gebaeude.extract) -> Grundriss Ziel + Nachbarn im Modellrahmen; Waende = freie Kanten des Zielgebaeudes
    (Kanten, vor denen ein anderer Grundriss liegt, sind 'angebaut' und brauchen kein Foto), Kanten mit Knick < KNICK_GRAD zusammengefasst.
  Wolke (modelle/<obj>/sfm/punkte_modell_<obj>.npy, mmap + Unterabtastung auf <= MAX_PUNKTE) -> Wandbelegung je Wand = Punkte je m2 im Band +-BAND_M um die
    Wandlinie, Hoehe Z0_M .. Traufe (LoD2); Klasse relativ zur bestbelegten freien Wand derselben Wolke: gruen >= GRUEN_REL, gelb >= GELB_REL, sonst rot.
  Kameras: SFM-AUSRICHTUNG 'kameras' (Teil A, Modellrahmen); nicht vereinte Seitenteile ueber das EXIF-GPS ihrer Fotos (seiten_modelle/teilN.txt) - Farbe je Teil.
  seiten_modelle.json 'fotoluecken' -> die freie Wand, deren Aussennormale dem Azimut der Luecke am naechsten liegt (<= LUECKE_MAX_GRAD), gilt als 'nicht angebunden'
    (rot, ausser die Wolke belegt sie schon gruen -> gelb). Begruendung je Luecke in einem Satz aus 'grund'.
  Bildwinkel der Kamera: Median der eigenen Fotos (f_px_original, bild_b/bild_h der Ausrichtung), sonst ANNAHME HFOV_ANNAHME.
STANDPUNKTE (nummeriert, je mit Blickrichtung, Entfernung, Hoch-/Querformat, GPS an, WGS84 je Foto):
  (a) UEBERECK-BOGEN an jeder Ecke zwischen einer belegten (gruen/gelb) und einer roten Wand: Kreisbogen um die Ecke von der Normalen der einen zur Normalen der
      anderen Wand, Blick auf die Ecke. Radius: beide Waende (bis zur kuerzeren Wandlaenge) passen bei Blick ueber Eck ins Bild (Hoch-/Querformat nach Hoehe/Breite).
      Schrittwinkel = (1 - UEBERLAPP_BRUECKE) x Bildbreite / Radius, hoechstens MAX_SCHRITT_GRAD (Blickwinkelaenderung, die SIFT/LightGlue noch zuordnet) ->
      Anzahl und Seitenschritt folgen aus Wandlaenge und Ueberlappung.
  (b) FRONTALREIHE vor jeder roten Wand: Abstand = ganze Wandbreite im Bild, begrenzt durch den freien Raum vor der Wand (Strahl gegen LoD2-Nachbarn);
      Schritt = (1 - UEBERLAPP_REIHE) x Bildbreite.
  (c) FERNSTANDORTE: Abstand >= GPS-Rest (gps_anker.rest_m) / tan(MAX_DREH_SD/2) (Drehfehler halb so gross wie die Grenze des GPS-Tors, seiten_gps_vereinen) und
      <= Gebaeudehoehe x f_px / MIN_PIXEL_HOEHE; Richtung zwischen den Normalen der beiden Waende einer Ecke (beide Seiten im Bild); nur Orte ausserhalb jedes
      LoD2-Grundrisses mit freier Sicht (3D: Sichtlinie Auge AUGE_M -> Ecke auf halber Traufhoehe ueber jedem Nachbargebaeude, Gelaende eben = ANNAHME).
Strassennamen: nur wenn lokale Geodaten sie liefern - im Bestand (_geo: LoD2/DGM/DOM/DOP) gibt es keine, also weggelassen (nichts erfunden).
AUSGABE: <aus>/foto_auftrag.png (Nahplan | Uebersicht | Liste), foto_auftrag.json, foto_auftrag.md. Rueckgabe 0 = Skizze geschrieben, 2 = keine Daten (kein LoD2/Rahmen).
FOTO PRUEFEN (Skill foto-vor-ort): --pruefen <foto_auftrag.json> <foto...> -> je Foto naechster Standpunkt aus EXIF-GPS, Abstand, Verschiebung links/rechts/vor/zurueck
  relativ zur Soll-Blickrichtung, Kompass (EXIF GPSImgDirection) gegen Soll-Blick; Urteil 'erfuellt Standpunkt N' / 'bitte X m ...'.
AUFRUF: tools/py seg tools/foto_auftrag_skizze.py modelle/<obj>/objekt.json [--wolke npy] [--ausrichtung json] [--seiten-modelle json] [--fotos ordner] [--aus ordner]
  (Kette: tools/gesamtkette.py nach der SfM und am Laufende; Schalter RCPARK_FOTOAUFTRAG_SKIZZE=0). Nur CPU, < 1 GB RAM.
Test: tools/test_foto_auftrag_skizze.py (synthetisch: Rechteck, eine Seite leer -> Uebereck an den zwei richtigen Ecken, kein Standpunkt in einem Nachbarhaus).
"""
import os, sys, json, math, glob, re, argparse, time
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)

KNICK_GRAD = 25.0          # ANNAHME: Kanten mit kleinerem Knick bilden eine Wand (Rundanbau wird in wenige Stuecke geteilt)
FREI_PROBE_M = 0.4         # Probe vor der Kante: liegt dort ein anderer Grundriss, ist die Kante angebaut
BAND_M = 1.0               # ANNAHME: Wandband +-1 m (Lagefehler der Ausrichtung ~0,4-0,9 m + Relief)
Z0_M = 2.0                 # ANNAHME: unter 2 m Passanten/Autos/Schilder
MAX_PUNKTE = 2_000_000     # Unterabtastung der Wolke (Speicher)
GRUEN_REL, GELB_REL = 0.25, 0.05   # ANNAHME: Anteil an der bestbelegten freien Wand derselben Wolke (1122: Sued 0,6 %, Ost 20 %)
LUECKE_MAX_GRAD = 60.0     # wie foto_auftrag.seiten_bedarf
MIN_WAND_REL = 0.2         # ANNAHME: Waende kuerzer als 20 % der laengsten freien Wand bekommen keine eigenen Standpunkte (werden mitfotografiert)
UEBERLAPP_BRUECKE = 0.8    # ANNAHME: Brueckenfotos ueber Eck 80 % Ueberlappung
UEBERLAPP_REIHE = 0.7      # ANNAHME: Frontalreihe 70 %
MAX_SCHRITT_GRAD = 15.0    # ANNAHME: Blickwinkelaenderung je Schritt, die Merkmalszuordnung noch traegt
HFOV_ANNAHME = (66.0, 52.0)   # ANNAHME Handy-Hauptkamera (lange/kurze Bildseite), nur wenn keine eigenen Fotos in der Ausrichtung
GPS_REST_ANNAHME = 5.0     # ANNAHME Telefon-GPS (m), nur wenn die Ausrichtung keinen GPS-Rest hat
MIN_PIXEL_HOEHE = 500      # ANNAHME: Gebaeude mind. 500 px hoch im Fernfoto (Merkmale fuer die Zuordnung)
AUGE_M = 1.6
FERN_JE_ECKE = 2
VERBINDUNG_MAX_M = 60.0   # ANNAHME: hoechstens 60 m Verbindungsreihe entlang roter Nachbarfassaden bis zur Bruecken-Ecke
FARBE = dict(gruen="#2e8b3e", gelb="#e0a800", rot="#d0281c")
TEIL_FARBEN = ["#1f5fbf", "#8a2be2", "#e07b00", "#009e9e", "#b0306f", "#6b8e23"]


# ---------------------------------------------------------------- Geometrie
class Rahmen:
    def __init__(self, obj):
        r = obj["rahmen"]; self.m0 = np.array(r["mitte_utm"], float); self.xh = np.array(r["xhat_utm"], float); self.yh = np.array(r["yhat_utm"], float)
        self.gelaende = float(r.get("gelaende", 0.0))
    def utm(self, xy): xy = np.asarray(xy, float); return self.m0 + xy[..., :1] * self.xh + xy[..., 1:2] * self.yh
    def lokal(self, xy):
        """Modellrahmen -> (Ost, Nord) in m relativ zur Rahmenmitte (Zeichnung: Norden oben)."""
        return self.utm(xy) - self.m0
    def modell(self, utm): d = np.asarray(utm, float) - self.m0; return np.stack([d @ self.xh, d @ self.yh], -1)
    def azimut(self, v):
        vv = v[0] * self.xh + v[1] * self.yh; return float(math.degrees(math.atan2(vv[0], vv[1])) % 360.0)
    def richtung(self, az):
        """Kompass-Azimut -> Einheitsvektor im Modellrahmen."""
        e = np.array([math.sin(math.radians(az)), math.cos(math.radians(az))]); return np.array([e @ self.xh, e @ self.yh])
    def geo(self, xy):
        from seiten_luecken import utm32_nach_geo
        u = self.utm(xy); return utm32_nach_geo(float(u[0]), float(u[1]))


def seite_name(az):
    return ["Nordseite", "Nordostseite", "Ostseite", "Südostseite", "Südseite", "Südwestseite", "Westseite", "Nordwestseite"][int(((az % 360) + 22.5) // 45) % 8]


def kompass(az): return ["Norden", "Nordosten", "Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten"][int(((az % 360) + 22.5) // 45) % 8]


def flaeche(p): x, y = p[:, 0], p[:, 1]; return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def ring_sauber(p):
    p = np.asarray(p, float)[:, :2]
    if len(p) > 1 and np.linalg.norm(p[0] - p[-1]) < 1e-6: p = p[:-1]
    keep = [0] + [i for i in range(1, len(p)) if np.linalg.norm(p[i] - p[i - 1]) > 0.05]; p = p[keep]
    return p[::-1].copy() if flaeche(p) < 0 else p          # gegen den Uhrzeigersinn -> Aussennormale (d_y, -d_x)


def innen(pt, ringe):
    """Punkt(e) in irgendeinem Ring? (matplotlib.path, gerade/ungerade Regel je Ring)."""
    from matplotlib.path import Path
    pt = np.atleast_2d(pt); hit = np.zeros(len(pt), bool)
    for r in ringe:
        lo, hi = r.min(0), r.max(0); m = (pt[:, 0] >= lo[0]) & (pt[:, 0] <= hi[0]) & (pt[:, 1] >= lo[1]) & (pt[:, 1] <= hi[1])
        if m.any(): hit[m] |= Path(r).contains_points(pt[m])
    return hit


def schnitt_t(p0, p1, ring):
    """Kleinster Parameter t in [0,1] des Schnitts der Strecke p0->p1 mit dem Ring (oder None)."""
    q0 = ring; q1 = np.roll(ring, -1, 0); d = p1 - p0; e = q1 - q0; w = q0 - p0
    den = d[0] * e[:, 1] - d[1] * e[:, 0]; ok = np.abs(den) > 1e-12
    t = np.where(ok, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / np.where(ok, den, 1), -1); u = np.where(ok, (w[:, 0] * d[1] - w[:, 1] * d[0]) / np.where(ok, den, 1), -1)
    m = ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
    if innen(p0, [ring])[0]: return 0.0
    return float(t[m].min()) if m.any() else None


def sicht_frei(p0, z0, p1, z1, geb, ausser=()):
    """3D-Sichtlinie (p0, z0) -> (p1, z1) ueber alle LoD2-Gebaeude ausser 'ausser' (ids): an jedem Eintritt in einen Grundriss muss die Linie ueber dessen Dach liegen."""
    lo, hi = np.minimum(p0, p1), np.maximum(p0, p1)
    for g in geb:
        if g["id"] in ausser: continue
        for r in g["ringe"]:
            if (r[:, 0].max() < lo[0]) or (r[:, 0].min() > hi[0]) or (r[:, 1].max() < lo[1]) or (r[:, 1].min() > hi[1]): continue
            t = schnitt_t(p0, p1, r)
            if t is not None and z0 + t * (z1 - z0) < g["oben"]: return False, g["id"]
    return True, None


# ---------------------------------------------------------------- Daten
def gebaeude(obj, rahmen, radius):
    """LoD2-Grundrisse im Umkreis (alle Kacheln neben objekt.json lod2.gml) -> [dict(id, ziel, ringe[], oben (m ueber Rahmen-Gelaende), traufe)]."""
    import lod2_gebaeude as LG
    gml = (obj.get("lod2") or {}).get("gml"); zid = (obj.get("lod2") or {}).get("id")
    if not gml or not os.path.exists(gml):
        hit = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/LoD2_32_{int(rahmen.m0[0] // 1000)}_{int(rahmen.m0[1] // 1000)}_1_BW.gml", recursive=True)
        if not hit: return [], zid
        gml = hit[0]
    kacheln = []
    for g in sorted(glob.glob(os.path.join(os.path.dirname(gml), "LoD2_32_*_*_1_BW.gml"))):
        m = re.search(r"LoD2_32_(\d+)_(\d+)_1_BW", os.path.basename(g))
        if not m: continue
        e0, n0 = int(m.group(1)) * 1000, int(m.group(2)) * 1000
        dx = max(e0 - rahmen.m0[0], 0, rahmen.m0[0] - e0 - 1000); dy = max(n0 - rahmen.m0[1], 0, rahmen.m0[1] - n0 - 1000)
        if math.hypot(dx, dy) <= radius: kacheln.append(g)
    if gml not in kacheln: kacheln.insert(0, gml)
    aus, ids = [], set()
    for k in kacheln:
        for meta, polys in LG.extract(k, center=tuple(rahmen.m0), radius=radius):
            if meta.get("id") in ids: continue
            gr = [ring_sauber(rahmen.modell(P[:, :2])) for t, P in polys if t == "GroundSurface"]; gr = [r for r in gr if len(r) >= 3 and abs(flaeche(r)) > 0.5]
            if not gr: continue
            ids.add(meta.get("id")); boden = float(meta.get("ground_z", rahmen.gelaende)) - rahmen.gelaende
            allz = np.vstack([P for _, P in polys])[:, 2]; oben = float(allz.max()) - rahmen.gelaende
            aus.append(dict(id=meta.get("id"), ziel=meta.get("id") == zid, ringe=gr, oben=oben, boden=boden, traufe=float(meta.get("eave_m") or (oben - boden)), first=float(meta.get("ridge_m") or (oben - boden))))
    return aus, zid


def _kanten(r, fremd, hoehe, eigen_id=None):
    """Kanten eines Rings (gegen den Uhrzeigersinn) mit Frei-Probe: vor der Kante (FREI_PROBE_M) ein fremder Grundriss = angebaut; ueberragt das Ziel diesen um
    >= 3 m (ANNAHME: ein Geschoss), ist die Wand oberhalb des Nachbardachs frei (ab = Nachbarhoehe)."""
    K = []
    for i in range(len(r)):
        a, b = r[i], r[(i + 1) % len(r)]; L = float(np.linalg.norm(b - a))
        if L < 1e-3: continue
        d = (b - a) / L; n = np.array([d[1], -d[0]]); k = max(3, int(L / 0.5))
        q = a + np.outer(np.linspace(0.1, 0.9, k), b - a) + n * FREI_PROBE_M
        belegt_ = np.zeros(k, bool); ab = 0.0; wer = set()
        for gg, rr in fremd:
            h = innen(q, [rr])
            if h.any(): belegt_ |= h; ab = max(ab, hoehe + 99 if gg["ziel"] else gg["oben"]); wer.add(gg["id"])     # eigener Gebaeudeteil: ganz innen
        frei = float(1 - belegt_.mean()) >= 0.5
        # 22.11.2026 (schwabentor-1122): der Turm ueberragt das angebaute Nachbarhaus - die Wand OBERHALB des Nachbardachs ist frei
        if not frei and ab < hoehe - 3.0: frei, ab_m = True, round(ab, 1)
        else: ab_m = 0.0
        K.append(dict(a=a, b=b, L=L, d=d, frei=frei, ab=ab_m, an=sorted(wer) if not frei or ab_m else [], besitzer=eigen_id))
    return K


def _gruppen(K, rahmen, ring, knick=KNICK_GRAD):
    """Kanten mit kleinem Knick (und gleichem Frei-Zustand/Besitzer) zu Waenden zusammenfassen."""
    if not K: return []
    ang = lambda u, v: math.degrees(math.acos(max(-1.0, min(1.0, float(u @ v)))))
    sch = lambda e: (e["frei"], e["ab"], e["besitzer"])
    st = next((i for i in range(len(K)) if sch(K[i]) != sch(K[i - 1]) or ang(K[i]["d"], K[i - 1]["d"]) > knick), 0)
    K = K[st:] + K[:st]; grp = [[K[0]]]
    for e in K[1:]:
        if sch(e) == sch(grp[-1][0]) and ang(e["d"], grp[-1][0]["d"]) <= knick and ang(e["d"], grp[-1][-1]["d"]) <= knick: grp[-1].append(e)
        else: grp.append([e])
    W = []
    for gr in grp:
        a, b = gr[0]["a"], gr[-1]["b"]; L = float(np.linalg.norm(b - a)) or sum(e["L"] for e in gr)
        d = (b - a) / max(np.linalg.norm(b - a), 1e-9); n = np.array([d[1], -d[0]]); az = rahmen.azimut(n)
        W.append(dict(a=a, b=b, L=round(L, 2), d=d, n=n, frei=gr[0]["frei"], ab=gr[0]["ab"], an=sorted({x for e in gr for x in e["an"]}), besitzer=gr[0]["besitzer"], ring=ring, az=round(az, 1),
                      seite=seite_name(az), polylinie=np.vstack([e["a"] for e in gr] + [b])))
    return W


def waende(geb, rahmen, knick=KNICK_GRAD):
    """Waende des Zielgebaeudes. Ist das Ziel an Nachbarhaeuser angebaut, laeuft der Umriss ueber den BLOCK (Ziel + direkt angebaute Nachbarn, Vereinigung der
    Grundrisse): Brueckenfotos muessen dann um den Block herum (schwabentor-1122: Suedwand endet im Osten am angebauten Haus Tvdv, dessen Nordfassade belegt ist).
    Kanten des Ziels zu einem niedrigeren Nachbarn kommen als eigene Waende 'frei ab <Nachbarhoehe>' dazu (ring 'ueber_nachbar', ohne Ecken).
    -> Liste dict(a, b, L, d, n, frei, ab, besitzer (LoD2-id), nachbar (bool), ring, az, seite, polylinie, nr)."""
    ziel = [g for g in geb if g["ziel"]]
    if not ziel: return []
    zid = ziel[0]["id"]; hoehe = max(g["first"] for g in ziel)
    alle = [(g, ri, r) for g in geb for ri, r in enumerate(g["ringe"])]
    zk, an = [], set()
    for g in ziel:
        for ri, r in enumerate(g["ringe"]):
            K = _kanten(r, [(gg, rr) for gg, rj, rr in alle if not (gg is g and rj == ri)], hoehe, zid); zk.append((ri, K))
            for e in K:
                if not e["frei"] or e["ab"]: an |= {x for x in e["an"] if x != zid}
    if not an:                                                                  # frei stehend: je Ring
        W = [w for ri, K in zk for w in _gruppen(K, rahmen, (zid, ri), knick)]
    else:
        Polygon = __import__("shapely.geometry", fromlist=["Polygon"]).Polygon; unary_union = __import__("shapely.ops", fromlist=["unary_union"]).unary_union   # shapely nur in venv-seg (tools/py waehlt sonst rcpark ohne shapely)
        block = [g for g in geb if g["ziel"] or g["id"] in an]
        U = unary_union([Polygon(r).buffer(0.15, join_style=2) for g in block for r in g["ringe"]]).buffer(-0.15, join_style=2)
        polys = list(U.geoms) if hasattr(U, "geoms") else [U]
        zmitte = np.vstack([r for g in ziel for r in g["ringe"]]).mean(0)
        P = max(polys, key=lambda p: (p.distance(__import__("shapely.geometry", fromlist=["Point"]).Point(*zmitte)) < 0.5, p.area))
        ring = ring_sauber(np.asarray(P.simplify(0.05).exterior.coords))
        ecken_b = np.vstack([r for g in block for r in g["ringe"]]); neu_ = []          # Umriss an jeder Gebaeudegrenze teilen (sonst laeuft eine Kante ueber Ziel UND Nachbar)
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]; v = b - a; L = float(np.linalg.norm(v)); neu_.append(a)
            if L < 0.6: continue
            t = (ecken_b - a) @ v / L ** 2; dd = np.linalg.norm(a + np.outer(t, v) - ecken_b, axis=1); m = (dd < 0.25) & (t * L > 0.3) & (t * L < L - 0.3)
            for tt in sorted(set(np.round(t[m], 3))): neu_.append(a + tt * v)
        ring = np.array(neu_)
        fremd = [(gg, rr) for gg, rj, rr in alle if not (gg["ziel"] or gg["id"] in an)]
        K = _kanten(ring, fremd, hoehe)
        for e in K:                                                             # Besitzer: Ziel, wenn die Kante auf einem Zielgrundriss liegt
            m = 0.5 * (e["a"] + e["b"]); best = None
            for g in block:
                for r in g["ringe"]:
                    dd = _abstand_rand(m, [r])
                    if best is None or dd < best[0] - 1e-6 or (abs(dd - best[0]) < 1e-6 and g["ziel"]): best = (dd, g["id"])
            e["besitzer"] = best[1] if best and best[0] < 0.6 else None
        W = _gruppen(K, rahmen, ("block", 0), knick)
        for ri, K in zk:                                                        # Zielwand ueber dem Nachbardach
            W += [w for w in _gruppen(K, rahmen, (zid, ri), knick) if w["ab"]]
            for w in W:
                if w["ring"] == (zid, ri): w["ring"] = ("ueber_nachbar", ri)
    for i, w in enumerate(W): w["nr"] = i + 1; w["nachbar"] = w["besitzer"] not in (zid, None)
    return W


def belegung(W, wolke, z0, z1, max_n=MAX_PUNKTE):
    """Punkte je m2 im Wandband (Wolke mit mmap + Unterabtastung) -> w['punkte'], w['dichte']."""
    if not wolke or not os.path.isfile(wolke): return None
    A = np.load(wolke, mmap_mode="r"); st = max(1, int(math.ceil(len(A) / max_n))); P = np.asarray(A[::st, :3], np.float32)
    P = P[(P[:, 2] >= z0) & (P[:, 2] <= z1)]
    for w in W:
        za = max(z0, w.get("ab") or 0.0)                                   # Wand ueber einem angebauten Nachbardach: nur der freie Teil zaehlt
        rel = P[:, :2] - w["a"].astype(np.float32); t = rel @ w["d"].astype(np.float32); s = rel @ w["n"].astype(np.float32)
        r_ = BAND_M if w["L"] > 4 * BAND_M else 0.0                         # Wandenden um die Bandbreite kuerzen: sonst zaehlen die Punkte der Nachbarwand an der Ecke mit
        n = int(np.count_nonzero((t >= r_) & (t <= w["L"] - r_) & (np.abs(s) <= BAND_M) & (P[:, 2] >= za))) * st
        w["punkte"] = n; w["dichte"] = round(n / max((w["L"] - 2 * r_) * max(z1 - za, 1.0), 1e-6), 1)
    return dict(datei=wolke, punkte=len(A), unterabtastung=st, z=[z0, round(z1, 1)])


def kameras_teil_a(au, rahmen):
    """SFM-AUSRICHTUNG 'kameras' -> (Positionen Modellrahmen, Namen, Bildwinkel (lange, kurze Seite) Grad, f_px Median, GPS-Rest m)."""
    if not au or not os.path.isfile(au): return np.zeros((0, 3)), [], None, None, None
    d = json.load(open(au)); K = d.get("kameras") or {}; C, N, hl, hk, fl = [], [], [], [], []
    for n, k in K.items():
        if not isinstance(k, dict) or "standort" not in k: continue
        C.append(k["standort"]); N.append(n)
        f, b, h = k.get("f_px_original") or k.get("f_px"), k.get("bild_b"), k.get("bild_h")
        if f and b and h and n.startswith("eigen"):                         # eigene Fotos = Kamera des Nutzers
            lang, kurz = max(b, h), min(b, h); hl.append(2 * math.degrees(math.atan(lang / 2 / f))); hk.append(2 * math.degrees(math.atan(kurz / 2 / f))); fl.append(f * 1.0)
    hf = (round(float(np.median(hl)), 1), round(float(np.median(hk)), 1)) if len(hl) >= 5 else None
    g = ((d.get("transformation") or {}).get("gps_anker") or {}).get("rest_m")
    return np.asarray(C, float).reshape(-1, 3), N, hf, (float(np.median(fl)) if fl else None), (float(g) if g else None)


def kameras_teile_gps(smj, fotos, rahmen):
    """Nicht vereinte Seitenteile: Kamerastandorte aus dem EXIF-GPS ihrer Fotos (teilN.txt) -> {teil: (n x 2) Modellrahmen}."""
    aus = {}
    if not smj or not os.path.isfile(smj) or not fotos or not os.path.isdir(fotos): return aus
    S = json.load(open(smj)); arb = S.get("arbeit") or os.path.join(os.path.dirname(smj), "seiten_modelle")
    try:
        from seiten_gps_vereinen import gps_roh
        from bilder_holen import wgs84_zu_utm
    except Exception as e: print("GPS der Seitenteile nicht lesbar:", e); return aus
    for t in S.get("nicht_vereint") or []:
        tx = os.path.join(arb, f"teil{t}.txt")
        if not os.path.isfile(tx): continue
        namen = [z.strip() for z in open(tx) if z.strip()]
        roh = gps_roh(fotos, namen)
        if roh:
            P = rahmen.modell(np.array([wgs84_zu_utm(la, lo) for la, lo in roh.values()]))
            aus[int(t)] = P[np.linalg.norm(P, axis=1) < 400]
    return aus


def satz_aus_grund(L):
    """Ein Satz je Fotoluecke aus 'grund' (nur die nicht bestandenen Proben, gekuerzt)."""
    g = str(L.get("grund") or ""); teile = [s.strip() for s in g.split(" - ", 1)[-1].split(";") if "NICHT" in s]
    kurz = []
    for s in teile:
        m = re.match(r"(\w+): NICHT bestanden \((.*)\)?$", s)
        kurz.append((m.group(1).replace("_", " ") + ": " + m.group(2)[:110]) if m else s[:120])
    return (f"Seitenteil {L.get('teil')} ({L.get('bilder')} Bilder, {L.get('seite')}) liess sich nicht unabhaengig an das Hauptmodell binden"
            + (" - " + "; ".join(kurz) if kurz else "") + ".")


# ---------------------------------------------------------------- Standpunkte
def _abstand_rand(p, ringe):
    """kleinster Abstand Punkt -> Grundriss-Kanten."""
    best = 1e9
    for r in ringe:
        q0, q1 = r, np.roll(r, -1, 0); e = q1 - q0; t = np.clip(((p - q0) * e).sum(1) / np.maximum((e * e).sum(1), 1e-12), 0, 1); best = min(best, float(np.min(np.linalg.norm(q0 + e * t[:, None] - p, axis=1))))
    return best


def ort_ok(p, geb, rand=0.5):
    rr = [r for g in geb for r in g["ringe"]]
    return (not innen(p, rr)[0]) and _abstand_rand(p, rr) >= rand


def sicht_2d(p, ziel, geb, zid):
    """Sicht am Boden von p zur Zielecke: kein fremder Grundriss dazwischen (Ziel selbst ausgenommen, Strecke 0,3 m vor dem Ziel beendet)."""
    v = ziel - p; L = np.linalg.norm(v); q = p + v * max(0.0, (L - 0.3) / max(L, 1e-9))
    for g in geb:
        if g["id"] == zid: continue
        for r in g["ringe"]:
            if schnitt_t(p, q, r) is not None: return False
    return True


def format_wahl(breite_grad, hoehe_grad): return "Hochformat" if hoehe_grad > breite_grad else "Querformat"


def uebereck(w1, w2, K, hoehe, hfov, geb, zid, rahmen):
    """Bogen um die Ecke K von der Normalen von w1 zur Normalen von w2. w1 belegt, w2 rot (Reihenfolge egal fuer die Geometrie)."""
    Lv = min(w1["L"], w2["L"]); a1 = math.atan2(w1["n"][1], w1["n"][0]); a2 = math.atan2(w2["n"][1], w2["n"][0]); da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    if abs(da) < math.radians(10): return None                              # keine echte Ecke
    # Richtungen von K entlang der Waende (weg von der Ecke)
    u1 = w1["d"] * (-1 if np.linalg.norm(w1["b"] - K) < np.linalg.norm(w1["a"] - K) else 1); u2 = w2["d"] * (-1 if np.linalg.norm(w2["b"] - K) < np.linalg.norm(w2["a"] - K) else 1)
    hoch = hoehe > Lv; hf = math.radians(hfov[1] if hoch else hfov[0])
    am = a1 + da / 2; vb = np.array([math.cos(am), math.sin(am)]); r = None
    for rr in np.arange(2.0, 80.0, 0.5):                                     # kleinster Radius, bei dem beide Wandstuecke (Laenge Lv) ins Bild passen
        C = K + vb * rr; ok = True
        for u in (u1, u2):
            q = K + u * Lv - C; ang = abs(math.atan2(q @ np.array([-vb[1], vb[0]]), q @ -vb))
            if ang > 0.85 * hf / 2: ok = False
        if ok: r = rr; break
    if r is None: r = 80.0
    breite = 2 * math.degrees(math.atan(Lv / r)); hoehe_g = math.degrees(math.atan(hoehe / r)); fmt = format_wahl(breite, hoehe_g); hf = math.radians(hfov[1] if fmt == "Hochformat" else hfov[0])
    s = (1 - UEBERLAPP_BRUECKE) * 2 * r * math.tan(hf / 2); dth = min(s / r, math.radians(MAX_SCHRITT_GRAD)); n = int(math.ceil(abs(da) / dth)) + 1
    fotos, verworfen = [], 0
    for i in range(n):
        a = a1 + da * i / (n - 1); v = np.array([math.cos(a), math.sin(a)]); p = None
        for f in (1.0, 0.85, 0.7, 0.55):                                    # Hindernis (Nachbarhaus): naeher an die Ecke
            q = K + v * r * f
            if ort_ok(q, geb) and sicht_2d(q, K, geb, zid): p = q; break
        if p is None: verworfen += 1; continue
        fotos.append(p)
    if len(fotos) < 3: return dict(ok=False, grund=f"nur {len(fotos)} freie Orte auf dem Bogen (Nachbarhaeuser)", radius_m=round(r, 1))
    schritt = float(np.median(np.linalg.norm(np.diff(np.array(fotos), axis=0), axis=1))) if len(fotos) > 1 else 0.0
    return dict(ok=True, fotos=fotos, ziel=K, radius_m=round(r, 1), schritt_m=round(schritt, 1), format=fmt, schritt_grad=round(math.degrees(dth), 1), verworfen=verworfen, bogen_grad=round(abs(math.degrees(da)), 0))


def frontal(w, hoehe, hfov, geb, zid):
    """Reihe vor der Wand: Abstand fuer ganze Wandbreite, begrenzt durch den freien Raum (Strahl gegen Nachbarn)."""
    m = 0.5 * (w["a"] + w["b"]); hf_q = math.radians(hfov[0]); d0 = (w["L"] / 2) / math.tan(0.85 * hf_q / 2)
    frei = 2 * d0; andere = [r for g in geb if g["id"] != zid for r in g["ringe"]]
    for r in andere:
        t = schnitt_t(m + w["n"] * 0.3, m + w["n"] * (2 * d0 + 0.3), r)
        if t is not None: frei = min(frei, t * 2 * d0)
    d = min(d0, frei - 1.0)
    if d < 2.0: return dict(ok=False, grund=f"vor der Wand nur {frei:.1f} m frei (Nachbarhaus) - nur schraeg von den Ecken", frei_m=round(frei, 1))
    fmt = format_wahl(2 * math.degrees(math.atan(w["L"] / 2 / d)), math.degrees(math.atan(hoehe / d))); hf = math.radians(hfov[1] if fmt == "Hochformat" else hfov[0])
    s = (1 - UEBERLAPP_REIHE) * 2 * d * math.tan(hf / 2); n = max(3, int(math.ceil(w["L"] / max(s, 0.3))) + 1)
    fuss = [w["a"] + w["d"] * w["L"] * i / (n - 1) for i in range(n)]; paar = [(f + w["n"] * d, f) for f in fuss if ort_ok(f + w["n"] * d, geb, 0.3)]
    if len(paar) < 2: return dict(ok=False, grund="Orte vor der Wand liegen in Gebaeuden")
    return dict(ok=True, fotos=[p for p, _ in paar], ziele=[f for _, f in paar], ziel=m, abstand_m=round(d, 1), schritt_m=round(w["L"] / (n - 1), 1), format=fmt, frei_m=round(frei, 1))


def fern(w1, w2, K, z_ziel, d_min, d_max, geb, zid, rahmen, n_max=FERN_JE_ECKE):
    """Fernstandorte zwischen den Normalen der beiden Waende einer Ecke, frei (nicht in Gebaeuden), Sicht 3D frei."""
    a1, a2 = rahmen.azimut(w1["n"]), rahmen.azimut(w2["n"]); da = (a2 - a1 + 180) % 360 - 180; mitte = (a1 + da / 2) % 360
    kand = []
    for f in np.linspace(0.12, 0.88, 14):
        az = (a1 + da * f) % 360; v = rahmen.richtung(az)
        for d in np.arange(d_min, d_max + 1e-6, max(5.0, (d_max - d_min) / 20)):
            p = K + v * d
            if not ort_ok(p, geb, 1.0): continue
            ok, _ = sicht_frei(p, AUGE_M, K, z_ziel, geb, ausser=(zid,))
            if ok: kand.append((abs((az - mitte + 180) % 360 - 180) / 45.0 + abs(d - 1.25 * d_min) / max(d_min, 1.0), az, float(d), p))
    kand.sort(key=lambda k: k[0]); wahl = []
    for k in kand:
        if all(abs((k[1] - w[1] + 180) % 360 - 180) >= 12 for w in wahl): wahl.append(k)
        if len(wahl) >= n_max: break
    return [dict(ok=True, fotos=[k[3]], ziel=K, abstand_m=round(k[2], 0), azimut_vom_ziel=round(k[1], 0)) for k in wahl], len(kand)


# ---------------------------------------------------------------- Hauptablauf
def erzeugen(objekt_json, wolke=None, ausrichtung=None, seiten_modelle=None, fotos=None, aus=".", radius=None, zeichnen=True, obj=None, geb=None, kam=None):
    """Alles in einem Aufruf (auch fuer Tests: obj/geb/kam direkt uebergeben). -> Ergebnis-dict (auch als JSON geschrieben)."""
    obj = obj or json.load(open(objekt_json)); rahmen = Rahmen(obj); os.makedirs(aus, exist_ok=True)
    C_a, N_a, hfov, f_px, gps_rest = kam if kam is not None else kameras_teil_a(ausrichtung, rahmen)
    hfov_q = "Median der eigenen Fotos (Ausrichtung)" if hfov else f"ANNAHME {HFOV_ANNAHME} Grad (keine eigenen Fotos)"; hfov = hfov or HFOV_ANNAHME
    gps_rest_q = "gps_anker.rest_m der Ausrichtung" if gps_rest else f"ANNAHME {GPS_REST_ANNAHME} m"; gps_rest = gps_rest or GPS_REST_ANNAHME
    try:
        from seiten_gps_vereinen import MAX_DREH_SD
    except Exception: MAX_DREH_SD = 6.0
    d_min = gps_rest / math.tan(math.radians(MAX_DREH_SD / 2))
    if geb is None:
        geb, zid = gebaeude(obj, rahmen, radius or 340.0)
    else: zid = (obj.get("lod2") or {}).get("id")
    ziel = [g for g in geb if g["ziel"]]
    if not ziel: print("FEHLER foto_auftrag_skizze: Zielgebaeude (lod2.id) nicht im LoD2 - keine Skizze"); return None
    traufe = max(g["first"] for g in ziel); first = traufe              # Wandhoehe = LoD2-Gebaeudehoehe (eave_m ist die tiefste Dachkante, oft ein Anbau)
    f_ph = f_px or (0.5 * 4000 / math.tan(math.radians(HFOV_ANNAHME[0] / 2)))
    d_max = max(first * f_ph / MIN_PIXEL_HOEHE, 1.5 * d_min); d_max = min(d_max, (radius or 340.0) - 20)
    W = waende(geb, rahmen); WF = [w for w in W if w["frei"]]; WZ = [w for w in WF if not w["nachbar"]]     # WZ: Waende des Zielgebaeudes
    bel = belegung(WF, wolke, Z0_M, max(traufe, Z0_M + 3))
    for w in WF:
        m = 0.5 * (w["a"] + w["b"]); v = C_a[:, :2] - m if len(C_a) else np.zeros((0, 2)); dist = np.linalg.norm(v, axis=1)
        w["kameras"] = int(np.count_nonzero((v @ w["n"] > 1.0) & (dist < d_max) & ((v @ w["n"]) / np.maximum(dist, 1e-9) > math.cos(math.radians(70))))) if len(v) else 0
    Lmax = max([w["L"] for w in WZ] or [1.0]); Lmin = MIN_WAND_REL * Lmax; dmax_ = max([w.get("dichte", 0) for w in WZ if w["L"] >= Lmin] or [0])
    for w in WF:
        if bel is None: w["rel"] = None; w["klasse"] = "gruen" if w["kameras"] >= 10 else ("gelb" if w["kameras"] >= 3 else "rot"); continue   # ohne Wolke: nur Kameras (ANNAHME 10/3)
        w["rel"] = round(w["dichte"] / dmax_, 4) if dmax_ > 0 else 0.0; w["klasse"] = "gruen" if w["rel"] >= GRUEN_REL else ("gelb" if w["rel"] >= GELB_REL else "rot")
    # Fotoluecken der Seitenmodelle
    luecken, meldungen = [], []
    S = json.load(open(seiten_modelle)) if seiten_modelle and os.path.isfile(seiten_modelle) else {}
    for L in S.get("fotoluecken") or []:
        az = L.get("azimut_grad"); satz = satz_aus_grund(L)
        if az is None: meldungen.append(f"Fotoluecke Teil {L.get('teil')}: Richtung unbekannt - keine Wand zugeordnet"); luecken.append(dict(teil=L.get("teil"), wand=None, satz=satz)); continue
        kand = sorted([(abs((w["az"] - az + 180) % 360 - 180), w) for w in WZ if w["L"] >= Lmin], key=lambda k: k[0])
        kand = [k for k in kand if k[0] <= LUECKE_MAX_GRAD]
        if not kand: meldungen.append(f"Fotoluecke Teil {L.get('teil')}: keine freie Wand innerhalb {LUECKE_MAX_GRAD:.0f} Grad von {az} Grad"); luecken.append(dict(teil=L.get("teil"), wand=None, satz=satz)); continue
        w = kand[0][1]; w["luecke"] = dict(teil=L.get("teil"), bilder=L.get("bilder"), azimut=az, abweichung_grad=round(kand[0][0], 0))
        w["klasse"] = "gelb" if w["klasse"] == "gruen" else "rot"
        neben = [k[1]["seite"] for k in kand[1:] if k[0] <= LUECKE_MAX_GRAD]
        luecken.append(dict(teil=L.get("teil"), wand=w["nr"], seite=w["seite"], satz=satz, auch_moeglich=neben, azimut=az))
    for w in WZ:
        if w["klasse"] == "rot" and not w.get("luecke") and w["L"] >= Lmin:
            luecken.append(dict(teil=None, wand=w["nr"], seite=w["seite"] + (f" (über {w['ab']:.0f} m)" if w.get("ab") else ""),
                                satz=(f"Die Wolke belegt die {w['seite']}" + (f" oberhalb des Nachbardachs ({w['ab']:.0f} m)" if w.get("ab") else "") + f" nur mit {w.get('dichte', 0):.0f} Punkten je m2 = "
                                      f"{100 * (w['rel'] or 0):.1f} % der bestbelegten Wand (Grenze {100 * GELB_REL:.0f} %), {w['kameras']} Kameras blicken auf sie.") if w.get("rel") is not None else f"Nur {w['kameras']} Kameras blicken auf die {w['seite']}."))
    # Standpunkte: von jeder roten Zielwand im Umriss nach beiden Seiten gehen - rote Waende (auch Nachbarhaus im Block) brauchen eine Verbindungsreihe,
    # an der ersten belegten Wand entsteht die Bruecken-Ecke. Angebaute Kante (Block-Ende) oder > VERBINDUNG_MAX_M Weg: keine Ecke auf dieser Seite.
    SP = []; ecken = []; verbindung = []
    def schritt(w, vor):
        ring = [x for x in W if x["ring"] == w["ring"]]; i = next(j for j, x in enumerate(ring) if x is w); k = len(ring); weg = []
        for s in range(1, k):
            x = ring[(i + s) % k] if vor else ring[(i - s) % k]
            if not x["frei"]: return None, weg
            if x["L"] < Lmin: continue
            if x is w: return None, weg
            if x["klasse"] != "rot": return x, weg
            weg.append(x)
            if sum(y["L"] for y in weg) > VERBINDUNG_MAX_M: return None, weg
        return None, weg
    for w in WZ:
        if w["klasse"] != "rot" or w["L"] < Lmin or w["ring"][0] == "ueber_nachbar": continue
        for vor in (True, False):
            x, weg = schritt(w, vor)
            if x is None: continue
            letzte = weg[-1] if weg else w
            K = 0.5 * ((letzte["b"] if vor else letzte["a"]) + (x["a"] if vor else x["b"]))
            if any(np.linalg.norm(K - e[2]) < 0.5 for e in ecken): continue
            ecken.append((x, letzte, K)); verbindung += [y for y in weg if y["nachbar"] and all(y is not v for v in verbindung)]
    for (wb, wr, K) in ecken:
        u = uebereck(wb, wr, K, traufe, hfov, geb, zid, rahmen)
        name = f"Ecke {wr['seite'].replace('seite', '')}/{wb['seite'].replace('seite', '')}" + (" (am Nachbarhaus)" if wb["nachbar"] or wr["nachbar"] else "")
        if u is None: meldungen.append(f"{name}: kein Knick - die Frontalreihe laeuft ueber die Wandgrenze weiter"); continue
        if not u["ok"]: meldungen.append(f"{name}: Uebereck-Bogen nicht moeglich ({u['grund']})"); continue
        SP.append(dict(art="uebereck", titel=f"Übereck-Bogen {name}", waende=[wb["nr"], wr["nr"]], **u))
    for w in [w for w in WZ if w["klasse"] == "rot" and w["L"] >= Lmin] + verbindung:
        if w.get("ab"): meldungen.append(f"{w['seite']}: erst oberhalb des angebauten Nachbardachs ({w['ab']:.0f} m) frei - keine Frontalreihe, nur Fernfotos"); continue
        f = frontal(w, traufe, hfov, geb, zid)
        tit = f"Verbindungsreihe {w['seite']} Nachbarhaus" if w["nachbar"] else f"Frontalreihe {w['seite']}"
        if not f["ok"]: meldungen.append(f"{tit}: nicht moeglich ({f['grund']})"); continue
        SP.append(dict(art="frontal", titel=tit, waende=[w["nr"]], **f))
    n_fern_kand = 0
    for (wb, wr, K) in ecken:
        fl, nk = fern(wb, wr, K, 0.5 * traufe, d_min, d_max, geb, zid, rahmen); n_fern_kand += nk
        if not fl: meldungen.append(f"Fern {wr['seite']}/{wb['seite']}: kein freier Fernstandort {d_min:.0f}-{d_max:.0f} m (LoD2-Sichtlinie)")
        for f in fl: f["hinweis"] = "Gebaeude bildfuellend (Zoom), 2-3 Aufnahmen vom selben Ort"; SP.append(dict(art="fern", titel=f"Fernfoto {wr['seite'].replace('seite', '')}/{wb['seite'].replace('seite', '')} aus {f['abstand_m']:.0f} m", waende=[wb["nr"], wr["nr"]],
                                    format="Hochformat" if first > 0.6 * max(wb["L"], wr["L"]) else "Querformat", **f))
    # Reihenfolge = Wichtigkeit: 1 Bruecke direkt am Ziel (Uebereck an der Zielwand, Frontalreihe der Luecke), 2 Fernfotos (Drehung/Massstab), 3 Umweg ueber Nachbarfassaden
    for s in SP: s["prio"] = 3 if (s["art"] == "frontal" and "Nachbarhaus" in s["titel"]) or (s["art"] == "uebereck" and "Nachbarhaus" in s["titel"]) else (2 if s["art"] == "fern" else 1)
    SP.sort(key=lambda s: s["prio"])
    # Ausgabe je Standpunkt: Blick, Entfernung, GPS
    for i, s in enumerate(SP, 1):
        s["nr"] = i; z = s["ziel"]; s["ziel_xy"] = [round(float(z[0]), 2), round(float(z[1]), 2)]; s["ziel_geo"] = [round(v, 6) for v in rahmen.geo(z)]
        fl = []
        zl = s.pop("ziele", None)                                           # Frontalreihe: jedes Foto senkrecht auf die Wand
        for j, p in enumerate(s["fotos"], 1):
            zj = zl[j - 1] if zl else z; la, lo = rahmen.geo(p); bl = rahmen.azimut(zj - p); fl.append(dict(i=j, x=round(float(p[0]), 2), y=round(float(p[1]), 2), lat=round(la, 6), lon=round(lo, 6), blick_grad=round(bl), entfernung_m=round(float(np.linalg.norm(zj - p)), 1)))
        s["fotos"] = fl; s["anzahl"] = len(fl); s["gps_an"] = True; s["entfernung_m"] = round(float(np.median([f["entfernung_m"] for f in fl])), 0)
        s["blick"] = kompass(float(np.median([f["blick_grad"] for f in fl]))) if s["art"] != "uebereck" else f"auf die Ecke ({kompass(fl[0]['blick_grad'])} bis {kompass(fl[-1]['blick_grad'])})"
        s.pop("ziel", None)
    erg = dict(objekt=obj.get("name"), zeit=time.strftime("%Y-%m-%d %H:%M"), quellen=dict(wolke=wolke, ausrichtung=ausrichtung, seiten_modelle=seiten_modelle, fotos=fotos),
               rahmen=dict(mitte_utm=rahmen.m0.tolist(), xhat_utm=rahmen.xh.tolist(), yhat_utm=rahmen.yh.tolist()), wolke=bel,
               kamera=dict(hfov_lang_grad=hfov[0], hfov_kurz_grad=hfov[1], quelle=hfov_q, f_px=round(f_ph), gps_rest_m=round(gps_rest, 1), gps_rest_quelle=gps_rest_q),
               fern=dict(d_min_m=round(d_min), d_max_m=round(d_max), herleitung=f"d_min = GPS-Rest {gps_rest:.1f} m / tan(MAX_DREH_SD {MAX_DREH_SD} / 2); d_max = First {first:.0f} m x f {f_ph:.0f} px / {MIN_PIXEL_HOEHE} px", kandidaten=n_fern_kand),
               annahmen=dict(band_m=BAND_M, z0_m=Z0_M, gruen_rel=GRUEN_REL, gelb_rel=GELB_REL, ueberlapp_bruecke=UEBERLAPP_BRUECKE, ueberlapp_reihe=UEBERLAPP_REIHE, max_schritt_grad=MAX_SCHRITT_GRAD,
                             gelaende="eben (Sichtlinie ohne DGM)", strassennamen="keine lokalen Geodaten - weggelassen"),
               traufe_m=round(traufe, 1), first_m=round(first, 1),
               waende=[dict(nr=w["nr"], seite=w["seite"], azimut_normale=w["az"], laenge_m=w["L"], frei=w["frei"], frei_ab_m=w.get("ab") or 0.0, punkte_m2=w.get("dichte"), rel=w.get("rel"), kameras=w.get("kameras"), klasse=w.get("klasse", "angebaut"),
                            luecke=w.get("luecke"), von=[round(float(v), 2) for v in w["a"]], bis=[round(float(v), 2) for v in w["b"]]) for w in W],
               luecken=luecken, standpunkte=SP, meldungen=meldungen)
    erg["teile_gps"] = {}
    tg = kameras_teile_gps(seiten_modelle, fotos, rahmen) if kam is None else {}
    for t, P in tg.items(): erg["teile_gps"][str(t)] = len(P)
    pfad = os.path.join(aus, "foto_auftrag"); erg["bild"] = pfad + ".png"; erg["text"] = pfad + ".md"
    json.dump(erg, open(pfad + ".json", "w"), indent=1, ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    open(pfad + ".md", "w").write(text(erg))
    if zeichnen: zeichne(erg, geb, W, C_a, tg, rahmen, pfad + ".png")
    return erg


def text(e):
    z = [f"# Fotoauftrag {e['objekt']} ({e['zeit']})", ""]
    if not e["luecken"]: z.append("Keine Lücke: alle freien Wände sind belegt.")
    for L in e["luecken"]: z.append(f"- LÜCKE {L.get('seite') or '?'}: {L['satz']}" + (f" (Zuordnung über Azimut {L['azimut']} Grad; auch möglich: {', '.join(L['auch_moeglich'])})" if L.get("auch_moeglich") else ""))
    z += ["", f"Kamera: Bildwinkel {e['kamera']['hfov_lang_grad']}/{e['kamera']['hfov_kurz_grad']} Grad ({e['kamera']['quelle']}). Bei JEDEM Foto: GPS (Standort) in der Kamera-App an.", ""]
    for s in e["standpunkte"]:
        f0, fm, f1 = s["fotos"][0], s["fotos"][len(s["fotos"]) // 2], s["fotos"][-1]
        z.append(f"{s['nr']}. [{['', 'zuerst', 'dann', 'nur wenn Zeit'][s['prio']]}] {s['titel']}: {s['anzahl']} Foto(s), {s.get('format', '')}, Blick {s['blick']}, Entfernung ~{s['entfernung_m']:.0f} m"
                 + (f", Seitenschritt ~{s['schritt_m']} m" if s.get("schritt_m") else "") + (f" ({s['hinweis']})" if s.get("hinweis") else "") + ".")
        z.append(f"   Start {f0['lat']:.6f}, {f0['lon']:.6f}" + (f" | Mitte {fm['lat']:.6f}, {fm['lon']:.6f} | Ende {f1['lat']:.6f}, {f1['lon']:.6f}" if s["anzahl"] > 1 else "")
                 + f" | https://www.google.com/maps/search/?api=1&query={fm['lat']},{fm['lon']}")
    for m in e["meldungen"]: z.append(f"- HINWEIS: {m}")
    z += ["", "Wände: " + "; ".join(f"{w['nr']} {w['seite']} {w['laenge_m']:.0f} m {w['klasse']}" + (f" ({w['punkte_m2']:.0f}/m2, {w['kameras']} Kam.)" if w.get("punkte_m2") is not None else "") for w in e["waende"] if w["frei"])]
    return "\n".join(z) + "\n"


def zeichne(e, geb, W, C_a, tg, rahmen, png):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as Poly, FancyArrowPatch
    fig = plt.figure(figsize=(16, 11.5), dpi=100); gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1], height_ratios=[1, 0.36], hspace=0.12, wspace=0.08)
    axn, axu, axt = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
    L = rahmen.lokal; SP = e["standpunkte"]
    zpts = np.vstack([L(r) for g in geb if g["ziel"] for r in g["ringe"]]); zm = zpts.mean(0)
    nah_p = [zpts] + [L(np.array([[f["x"], f["y"]] for f in s["fotos"]])) for s in SP if s["art"] != "fern"]
    nah = np.vstack(nah_p); lo, hi = nah.min(0) - 12, nah.max(0) + 12; c = 0.5 * (lo + hi); h = 0.5 * max(hi - lo); nah_box = (c - h, c + h)
    alle = np.vstack([nah] + [L(np.array([[f["x"], f["y"]] for f in s["fotos"]])) for s in SP]); lo2, hi2 = alle.min(0) - 30, alle.max(0) + 30; c2 = 0.5 * (lo2 + hi2); h2 = max(0.5 * max(hi2 - lo2), 60); ueb_box = (c2 - h2, c2 + h2)
    for ax, (b0, b1), ist_nah in ((axn, nah_box, True), (axu, ueb_box, False)):
        for g in geb:
            for r in g["ringe"]:
                q = L(r)
                if q[:, 0].max() < b0[0] or q[:, 0].min() > b1[0] or q[:, 1].max() < b0[1] or q[:, 1].min() > b1[1]: continue
                ax.add_patch(Poly(q, closed=True, fc="#9aa39d" if g["ziel"] else "#d9dcd6", ec="#55605a" if g["ziel"] else "#b5bab3", lw=1.2 if g["ziel"] else 0.5, zorder=1))
        for w in W:
            q = L(w["polylinie"])
            if not w["frei"]: ax.plot(q[:, 0], q[:, 1], color="#777", lw=1, ls=":", zorder=2); continue
            ax.plot(q[:, 0], q[:, 1], color=FARBE[w["klasse"]], lw=(4 if w.get("ab") else 7) if ist_nah else 4, ls="--" if w.get("ab") else "-", solid_capstyle="butt", zorder=3)
            if ist_nah and w["L"] >= 2:
                m = L(0.5 * (w["a"] + w["b"]) + w["n"] * 2.2); ax.text(m[0], m[1], (f"{w['seite'].replace('seite', '')}\n{w.get('dichte') or 0:.0f}/m²" if w.get("dichte") is not None else w["seite"]) + (f"\nab {w['ab']:.0f} m" if w.get("ab") else ""), ha="center", va="center", fontsize=8, color=FARBE[w["klasse"]], weight="bold", zorder=6, clip_on=True)
            if w.get("luecke") and ist_nah:
                m = L(0.5 * (w["a"] + w["b"]) + w["n"] * 5.0); ax.text(m[0], m[1], f"nicht angebunden\n(Teil {w['luecke']['teil']}, {w['luecke']['bilder']} Bilder)", ha="center", va="center", fontsize=8, color=FARBE["rot"], zorder=6, clip_on=True, bbox=dict(fc="white", ec=FARBE["rot"], lw=0.8, alpha=0.9))
        if len(C_a): q = L(C_a[:, :2]); ax.scatter(q[:, 0], q[:, 1], s=6 if ist_nah else 4, c=TEIL_FARBEN[0], alpha=0.55, lw=0, zorder=2, label=f"Kameras Teil A ({len(C_a)})")
        for k, (t, P) in enumerate(sorted(tg.items())):
            if len(P): q = L(P); ax.scatter(q[:, 0], q[:, 1], s=14 if ist_nah else 8, marker="x", c=TEIL_FARBEN[1 + k % 5], alpha=0.8, lw=1, zorder=2, label=f"Teil {t} nicht angebunden ({len(P)}, nur GPS)")
        for s in SP:
            if ist_nah and s["art"] == "fern": continue
            P = L(np.array([[f["x"], f["y"]] for f in s["fotos"]])); Z = L(np.array(s["ziel_xy"]))
            col = {"uebereck": "#c2185b", "frontal": "#1565c0", "fern": "#6a1b9a"}[s["art"]]
            ax.plot(P[:, 0], P[:, 1], "-", color=col, lw=1, alpha=0.6, zorder=4); ax.scatter(P[:, 0], P[:, 1], s=16 if ist_nah else 22, color=col, zorder=5, ec="white", lw=0.5)
            if ist_nah or s["art"] == "fern":
                for k_ in (range(0, len(P), max(1, len(P) // 4)) if len(P) > 4 else range(len(P))):
                    p = P[k_]; f_ = s["fotos"][k_]; ln = f_["entfernung_m"]; az_ = math.radians(f_["blick_grad"])         # Blickpfeil je Foto (lokal Ost/Nord)
                    v = np.array([math.sin(az_), math.cos(az_)]) * min(ln * 0.45, 4.5 if ist_nah else ln * 0.5)
                    ax.add_patch(FancyArrowPatch(tuple(p), tuple(p + v), arrowstyle="-|>", mutation_scale=9, color=col, lw=1, zorder=5))
            pm = P[len(P) // 2]; off = (pm - Z) / max(np.linalg.norm(pm - Z), 1e-9) * (2.6 if ist_nah else 0.03 * (b1[0] - b0[0]))
            ax.text(*(pm + off), str(s["nr"]), ha="center", va="center", fontsize=10 if ist_nah else 9, color="white", weight="bold", zorder=7, bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="white", lw=1))
        ax.set_xlim(b0[0], b1[0]); ax.set_ylim(b0[1], b1[1]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        sp = b1[0] - b0[0]; bl = [v for v in (5, 10, 20, 50, 100, 200) if v <= sp / 4][-1]; x0, y0 = b0[0] + 0.04 * sp, b0[1] + 0.04 * sp
        ax.plot([x0, x0 + bl], [y0, y0], color="k", lw=4, zorder=8); ax.text(x0 + bl / 2, y0 + 0.015 * sp, f"{bl} m", ha="center", fontsize=9, zorder=8)
        ax.annotate("", xy=(b1[0] - 0.05 * sp, b1[1] - 0.04 * sp), xytext=(b1[0] - 0.05 * sp, b1[1] - 0.13 * sp), arrowprops=dict(arrowstyle="-|>", color="k", lw=2), zorder=8)
        ax.text(b1[0] - 0.05 * sp, b1[1] - 0.16 * sp, "N", ha="center", fontsize=12, weight="bold", zorder=8)
        if not ist_nah:
            r_ = ueb_box[1][0] - ueb_box[0][0]
            for d in (e["fern"]["d_min_m"], e["fern"]["d_max_m"]):
                if d < r_: ax.add_patch(matplotlib.patches.Circle(tuple(zm), d, fill=False, ls="--", ec="#6a1b9a", lw=0.7, alpha=0.6, zorder=2))
    axn.set_title(f"Fotoauftrag {e['objekt']} - Nahplan (Norden oben)", fontsize=13, loc="left"); axu.set_title(f"Übersicht mit Fernstandorten ({e['fern']['d_min_m']}-{e['fern']['d_max_m']} m)", fontsize=11, loc="left")
    from matplotlib.lines import Line2D
    hl = [Line2D([], [], color=FARBE["gruen"], lw=6, label=f"Wand belegt (>= {100 * GRUEN_REL:.0f} % der besten)"), Line2D([], [], color=FARBE["gelb"], lw=6, label="Wand schwach"), Line2D([], [], color=FARBE["rot"], lw=6, label=f"Wand fehlt / nicht angebunden (< {100 * GELB_REL:.0f} %)"),
          Line2D([], [], color="#777", ls=":", label="angebaut (kein Foto nötig)"), Line2D([], [], color="#555", ls="--", lw=3, label="frei erst über dem Nachbardach"), Line2D([], [], marker="o", ls="-", color="#c2185b", label="Übereck-Bogen"), Line2D([], [], marker="o", ls="-", color="#1565c0", label="Frontalreihe"), Line2D([], [], marker="o", ls="", color="#6a1b9a", label="Fernstandort")]
    h_, l_ = axn.get_legend_handles_labels(); axu.legend(handles=hl + h_, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8, framealpha=0.9, borderaxespad=0)
    import textwrap
    axt.axis("off"); zeilen = []
    for L_ in e["luecken"]: zeilen += textwrap.wrap(f"LÜCKE {L_.get('seite') or '?'}: {L_['satz']}", 175, subsequent_indent="    ")
    for s in SP:
        fm = s["fotos"][len(s["fotos"]) // 2]
        zeilen.append(f"{s['nr']:>2}. [{['', 'zuerst', 'dann', 'nur wenn Zeit'][s['prio']]}] {s['titel']}: {s['anzahl']} Fotos, {s.get('format', '')}, Blick {s['blick']}, ~{s['entfernung_m']:.0f} m" + (f", Schritt {s['schritt_m']} m" if s.get("schritt_m") else "") + f", GPS an  |  {fm['lat']:.6f}, {fm['lon']:.6f}")
    for m in e["meldungen"][:4]: zeilen.append("Hinweis: " + m[:200])
    if not SP: zeilen.append("Keine Standpunkte nötig." if not e["luecken"] else "Keine Standpunkte gefunden (siehe Hinweise).")
    axt.text(0.0, 1.0, "\n".join(zeilen[:16]), va="top", ha="left", fontsize=9, family="monospace", transform=axt.transAxes)
    fig.savefig(png, dpi=100, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------- Foto gegen Auftrag
def exif_gps(foto):
    """-> (lat, lon, kompass_grad oder None) aus EXIF, oder None."""
    from PIL import Image
    try: g = Image.open(foto).getexif().get_ifd(0x8825)
    except Exception: return None
    if not g or 2 not in g or 4 not in g: return None
    gr = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    la = gr(g[2]) * (-1 if g.get(1) == "S" else 1); lo = gr(g[4]) * (-1 if g.get(3) == "W" else 1); k = g.get(17)
    return la, lo, (float(k) if k is not None else None)


def pruefen(auftrag, foto, gps=None):
    """Foto gegen den Auftrag: naechster Soll-Standort, Abstand, Verschiebung relativ zur Soll-Blickrichtung, Kompass. -> dict(urteil, text, ...)."""
    from bilder_holen import wgs84_zu_utm
    A = json.load(open(auftrag)) if isinstance(auftrag, str) else auftrag
    g = gps or exif_gps(foto)
    if g is None: return dict(urteil="ohne_gps", text=f"{os.path.basename(str(foto))}: kein GPS im Foto - bitte in der Kamera-App 'Standort speichern' einschalten und neu aufnehmen.")
    r = A["rahmen"]; m0, xh, yh = np.array(r["mitte_utm"]), np.array(r["xhat_utm"]), np.array(r["yhat_utm"]); u = np.array(wgs84_zu_utm(g[0], g[1])) - m0; p = np.array([u @ xh, u @ yh])
    best = None
    for s in A["standpunkte"]:
        for f in s["fotos"]:
            d = float(np.hypot(f["x"] - p[0], f["y"] - p[1]))
            if best is None or d < best[0]: best = (d, s, f)
    if best is None: return dict(urteil="kein_auftrag", text="Auftrag ohne Standpunkte.")
    d, s, f = best; tol = max(float(A["kamera"].get("gps_rest_m") or GPS_REST_ANNAHME), 0.5 * float(s.get("schritt_m") or 0), 0.05 * float(f["entfernung_m"]))
    bl = math.radians(f["blick_grad"]); vor = np.array([math.sin(bl), math.cos(bl)]); rechts = np.array([vor[1], -vor[0]])     # Ost/Nord
    soll = m0 + f["x"] * xh + f["y"] * yh; delta = soll - (m0 + p[0] * xh + p[1] * yh); dr, dv = float(delta @ rechts), float(delta @ vor)
    teile = []
    if d > tol:
        if abs(dr) > tol / 2: teile.append(f"{abs(dr):.0f} m nach {'rechts' if dr > 0 else 'links'}")
        if abs(dv) > tol / 2: teile.append(f"{abs(dv):.0f} m {'näher heran' if dv > 0 else 'zurück'}")
    blick_ok, dreh = None, ""
    hf = float(A["kamera"].get("hfov_kurz_grad") or HFOV_ANNAHME[1])
    if g[2] is not None:
        dw = (f["blick_grad"] - g[2] + 180) % 360 - 180; blick_ok = abs(dw) <= hf / 2
        if not blick_ok: dreh = f"um {abs(dw):.0f} Grad nach {'rechts' if dw > 0 else 'links'} drehen (Soll-Blick {kompass(f['blick_grad'])})"
    ort_ok = d <= tol; ok = ort_ok and blick_ok is not False
    if ok: t = f"ERFÜLLT Standpunkt {s['nr']} (Foto {f['i']} von {s['anzahl']}, {s['titel']}), {d:.1f} m vom Soll" + ("" if blick_ok else ", Blickrichtung ohne Kompass nicht geprüft")
    else: t = f"PASST NICHT: nächster ist Standpunkt {s['nr']} Foto {f['i']} ({s['titel']}), {d:.0f} m daneben - bitte " + " und ".join([x for x in [", ".join(teile), dreh] if x] or ["Blickrichtung prüfen"])
    return dict(urteil="erfuellt" if ok else "nicht", standpunkt=s["nr"], foto=f["i"], abstand_m=round(d, 1), toleranz_m=round(tol, 1), rechts_m=round(dr, 1), vor_m=round(dv, 1), blick_ok=blick_ok, text=t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("objekt", nargs="?"); ap.add_argument("--wolke"); ap.add_argument("--ausrichtung"); ap.add_argument("--seiten-modelle"); ap.add_argument("--fotos")
    ap.add_argument("--aus"); ap.add_argument("--radius", type=float, default=340.0); ap.add_argument("--pruefen", nargs="+", metavar=("AUFTRAG_JSON", "FOTO"), help="Foto(s) gegen foto_auftrag.json pruefen")
    a = ap.parse_args(argv)
    if a.pruefen:
        if len(a.pruefen) < 2: ap.error("--pruefen <foto_auftrag.json> <foto> [foto ...]")
        A = json.load(open(a.pruefen[0])); er = [pruefen(A, f) for f in a.pruefen[1:]]
        for r in er: print(r["text"])
        n = {}
        for r in er:
            if r["urteil"] == "erfuellt": n.setdefault(r["standpunkt"], set()).add(r["foto"])
        for s in A["standpunkte"]:
            if s["nr"] in n: print(f"Standpunkt {s['nr']}: {len(n[s['nr']])} von {s['anzahl']} Fotos erfuellt")
        return 0 if all(r["urteil"] == "erfuellt" for r in er) else 1
    if not a.objekt: ap.error("objekt.json fehlt")
    oj = os.path.abspath(a.objekt); Z = os.path.dirname(oj); nm = os.path.basename(Z); D = f"/media/oem/scan/rc-park_daten/{nm}"
    w = a.wolke or os.path.join(Z, "sfm", f"punkte_modell_{nm}.npy"); au = a.ausrichtung or os.path.join(Z, "messprotokoll", f"SFM-AUSRICHTUNG-{nm}.json")
    sm = a.seiten_modelle or os.path.join(D, "pipe", "sfm", "seiten_modelle.json"); fo = a.fotos or os.path.join(D, "fotos"); aus = a.aus or os.path.join(Z, "audit")
    obj = json.load(open(oj))
    if "rahmen" not in obj: print("FEHLER: objekt.json ohne 'rahmen' - keine Skizze"); return 2
    e = erzeugen(oj, w if os.path.isfile(w) else None, au if os.path.isfile(au) else None, sm if os.path.isfile(sm) else None, fo if os.path.isdir(fo) else None, aus, a.radius, obj=obj)
    if e is None: return 2
    for m in e["meldungen"]: print("  HINWEIS " + m)
    for L in e["luecken"]: print(f"  LUECKE {L.get('seite')}: {L['satz'][:200]}")
    for s in e["standpunkte"]: print(f"  {s['nr']:2d} {s['titel']}: {s['anzahl']} Fotos, {s.get('format', '')}, Blick {s['blick']}, ~{s['entfernung_m']:.0f} m")
    print(f"FOTOAUFTRAG-SKIZZE {e['bild']}: {len(e['luecken'])} Luecke(n), {len(e['standpunkte'])} Standpunkte ({sum(s['anzahl'] for s in e['standpunkte'])} Fotos)")      # letzte Zeile (Kettenbericht 'ende')
    return 0


if __name__ == "__main__":
    sys.exit(main())
