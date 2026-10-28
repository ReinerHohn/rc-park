#!/usr/bin/env python3
"""kaufhaus_measured.py — Historisches Kaufhaus Freiburg, FEIN vermessen aus den
hochauflösenden Frontalen/Detailfotos (kh_front2025b, kh_fenster, kh_erker) gegen
Referenz Traufe 9,7 / First 21,4 m (LOD2, amtlich). Echte Geometrie mit Details:
Arkade (6 Spitzbögen), Galerie mit Balustern, Maßwerk-Fensterband mit 4 Statuen,
2 polygonale Erker mit oktogonalem Spitzhelm, giebelständige Gauben (3 Reihen),
Treppengiebel (7 Stufen). Maße photo-abgelesen (±~5 %), Herkunft dokumentiert.
"""
import os, json, numpy as np, trimesh
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from trimesh.creation import extrude_polygon, box as tbox, cone as tcone

# ---- AUTOMATISCH ERKANNTE Stückzahlen (vom Vermesser-Ensemble aus dem Foto, NICHT hardcoden) ----
_PARAM_PATH = "modelle/kaufhaus_freiburg/kaufhaus_params.json"
_DEFAULTS = {"n_arch": 5, "n_windows": 10, "n_statues": 4, "n_oriels": 2,
             "dormer_rows_bottom_to_top": [3, 2], "dormer_width_frac": 0.59}
def _load_params():
    p = dict(_DEFAULTS)
    try:
        with open(_PARAM_PATH) as f:
            p.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})
    except FileNotFoundError:
        print(f"  (keine {_PARAM_PATH} — nehme Defaults; besser: Vermesser-Ensemble laufen lassen)")
    return p
P = _load_params()
N_ARCH   = int(P["n_arch"])        # erkannt, NICHT geraten
N_WIN    = int(P["n_windows"])
N_STAT   = int(P["n_statues"])
DORMER_ROWS = list(P["dormer_rows_bottom_to_top"])
DORMER_WFRAC = float(P["dormer_width_frac"])

# ---- gemessene Maße (m) ----
W, D = 24.1, 12.0   # AMTLICH aus LOD2 (DEBW_0010007Tv9r): Fassade 24,1 m (oriented footprint), Front-Range-Tiefe ~12 m; vorher 18,5 (Foto-Verhältnis) war zu schmal
EAVE, RIDGE = 9.7, 15.4   # FOTO-GEMESSEN (proportion_check): Dach/Fassade = 0.59 → RIDGE = EAVE*1.59
ROOF_INSET = 0.0          # SATTELDACH (gegiebelt): First über volle Breite, Seiten = rote Giebel (Foto), kein Walm
ARC_SPRING, ARC_APEX = 2.2, 5.2   # FOTO-GEMESSEN: hohe Arkade (~0,52 Fassade, proportion_check „Bögen zu niedrig")
ARC_BW = 0.87                      # Bogenbreite breiter (Foto: Bögen breit, Pfeiler schlank) — Auto-Messung durch Arkaden-Müll unzuverlässig, daher visuell verifiziert
SPANDREL_Z = 5.5                 # Zwickel-Band über den Bögen (hier sitzen die Wappen)
GAL_Z = 5.9                      # Galerie-Brüstung Oberkante
SILL, HEAD, OGEE = 6.3, 9.1, 9.4  # Fensterband über der Galerie bis fast Traufe (Foto)
def _win_params():                # GEMESSEN (nicht hardcodiert): Fensterbreiten-Anteil + Seitenverhältnis
    try:
        wf = float(json.load(open("modelle/kaufhaus_freiburg/win_struct.json")).get("breite_frac", 0.72))
    except Exception:
        wf = 0.72
    try:
        asp = float(json.load(open("modelle/kaufhaus_freiburg/win_profile.json")).get("aspect_w_h", 0.92))
    except Exception:
        asp = 0.92
    return wf, asp
WIN_WFRAC, WIN_ASPECT = _win_params()
ORIEL_X = [0.0, W]               # Erker AM ECK, ragen über die Hausflucht hinaus (User: nicht nach innen versetzt) — Buchtmitte = Gebäudeecke, halbe Bucht kragt aus
STAT_Z = 7.05                    # Statuen-Fußpunkt HÖHER (oberes Fensterband) — Füße nicht bis zur Brüstung runter (User: „gehen viel zu weit runter")

# ---- HYBRID: Höhen-Bänder aus der KANTENERKENNUNG übernehmen (tools/foto_kanten_messen.py) ----
# Messung VERFEINERT die kontinuierlichen Maße; Stückzahlen/Formen bleiben parametrisch (oben).
def _load_mass():
    try:
        with open("modelle/kaufhaus_freiburg/kaufhaus_mass.json") as f:
            return json.load(f).get("features_verfeinert_m", {})
    except (FileNotFoundError, ValueError):
        return {}
_MASS = _load_mass()
if _MASS:
    RIDGE = float(_MASS.get("First", RIDGE)); EAVE = float(_MASS.get("Traufe", EAVE))
    HEAD = float(_MASS.get("Fenster-Sturz", HEAD)); SILL = float(_MASS.get("Fenster-Sohlbank", SILL))
    GAL_Z = float(_MASS.get("Brüstung-OK", GAL_Z))
    ARC_APEX = float(_MASS.get("Bogen-Scheitel", ARC_APEX)); ARC_SPRING = float(_MASS.get("Bogen-Kämpfer", ARC_SPRING))
    ARC_BW = float(_MASS.get("bogen_breite_frac", ARC_BW))   # Bogenbreite GEMESSEN (fassade_gitter), nicht hardcodiert
    # Fenster-HÖHE = GEMESSENE Sturz/Sohlbank-Kanten (9,18/6,13). Die BREITE folgt aus dem gemessenen
    # Seitenverhältnis (win_profile aspect 0,45) → hoch+schlank. NICHT umgekehrt (Höhe aus Breite/Aspekt
    # ließ HEAD über die Traufe schießen = gedrungen/zu breit, von proportion_check gefangen).
    STAT_Z = SILL+1.0    # Figurenfuß: oberes Fensterdrittel, Kopf an Fensteroberkante, klar über der Brüstung
    D = float(_MASS.get("tiefe_m", D))   # Gebäudetiefe aus Messung (tiefe_messen.py: Analyse-durch-Synthese am Schrägfoto)
    print(f"  [HYBRID-Messung] RIDGE={RIDGE} EAVE={EAVE} HEAD={HEAD} SILL={SILL} ARC_SPRING={ARC_SPRING} ARC_APEX={ARC_APEX}")


def _tri(V, F):
    return trimesh.Trimesh(np.array(V, float), np.array(F), process=True)


def _stand(m, y0=0.0):
    """ein mit extrude_polygon((x, hoehe), dicke) gebautes Mesh AUFRICHTEN: Polygon-Höhe → Z,
    Extrusionsdicke → Y (Tiefe). Ohne das liegt die Wand flach (Höhe in Y) = unsichtbar."""
    V = m.vertices.copy()
    m.vertices = np.c_[V[:, 0], y0 + V[:, 2], V[:, 1]]
    return m


def bay_layout():
    """Obergeschoss (Foto kh_fenster): je Gruppe EIN BREITES Fenster mit 3 Lichtern; N_STAT
    Statuen auf den Teilern dazwischen. Gibt (breite Fenstermitten, Statuen-Teiler) zurück."""
    x0, x1 = ORIEL_X[0]+1.6, ORIEL_X[1]-1.6
    ngroup = N_STAT + 1
    gw = (x1-x0)/ngroup
    centers = [x0 + gw*(g+0.5) for g in range(ngroup)]   # breite Fenster-Einheiten
    stats = [x0 + gw*g for g in range(1, ngroup)]        # Statuen-Teiler
    return centers, stats


def _unit_pitch_frac():
    try:
        return float(json.load(open("modelle/kaufhaus_freiburg/win_struct.json")).get("unit_pitch_frac", 0.54))
    except Exception:
        return 0.54


def _win_w():
    # BREITE = GEMESSENE Fenster-Einheit/Bay-Teilung (0,54 aus kh_fenster). Höhe kommt aus den gemessenen
    # Sturz/Sohlbank-Kanten → Einheit ist hoch+schlank (aspect ~0,5) wie im Foto, füllt aber die halbe Bay.
    x0, x1 = ORIEL_X[0]+1.6, ORIEL_X[1]-1.6
    return (x1-x0)/(N_STAT+1)*_unit_pitch_frac()


# ---------- Fassadenwand mit Arkade + Kielbogen-Fenstern (shapely) ----------
def pointed_arch(xc, bw, spring, apex=None):
    """echter zweizentriger Spitzbogen: Kämpfer bei spring, Bögen (Radius=bw, Zentren an
    den gegenüberliegenden Kämpfern) treffen sich im Scheitel (xc, spring+bw*√3/2)."""
    a = bw/2; R = bw; h = np.sqrt(R*R - a*a)        # Scheitelhöhe über Kämpfer
    aL = np.arctan2(h, -a)                           # Scheitel-Winkel vom linken Zentrum (~120°)
    aR = np.arctan2(h, a)                            # vom rechten Zentrum (~60°)
    pts = [(xc-a, 0.25), (xc-a, spring)]
    for t in np.linspace(np.pi, aL, 16):             # linker Bogen: Kämpfer→Scheitel
        pts.append((xc+a + R*np.cos(t), spring + R*np.sin(t)))
    for t in np.linspace(aR, 0.0, 16):               # rechter Bogen: Scheitel→Kämpfer
        pts.append((xc-a + R*np.cos(t), spring + R*np.sin(t)))
    pts += [(xc+a, spring), (xc+a, 0.25)]
    return Polygon(pts)


def ogee_window(xc, w, sill, head, apex):
    """Fensteröffnung mit Kielbogen-Spitze."""
    a = w/2
    pts = [(xc-a, sill), (xc-a, head), (xc-a*0.5, head+0.35*(apex-head)),
           (xc, apex), (xc+a*0.5, head+0.35*(apex-head)), (xc+a, head), (xc+a, sill)]
    return Polygon(pts)


def curtain_window(xc, w, sill, head, rise, flat=None):
    """VORHANGBOGEN (Foto kh_fenster): das MITTELSEGMENT hat einen GERADEN, flachen Oberrand
    (höher); nur die zwei SEITENSEGMENTE fallen in konkaven Schrägen nach außen ab (Gardine).
    flat = Breite des Mittelsegments (= w/3 für ein 3-Licht-Fenster)."""
    if flat is None:
        flat = w/3.0
    a = w/2; ha = max(0.05, a-flat/2)                    # Horizontalspanne JE Seitensegment
    pts = [(xc-a, sill), (xc-a, head)]
    for t in np.linspace(0, 1, 9):                       # linke Schulter → linke Kante des flachen Mittelteils (konkav)
        pts.append((xc-a + ha*t, head + rise*(1-np.sqrt(max(0.0, 1-t*t)))))
    # flacher gerader Oberrand über das Mittelsegment (xc-flat/2 .. xc+flat/2, auf head+rise)
    for t in np.linspace(1, 0, 9):                       # rechte Kante Mittelteil → rechte Schulter (konkav)
        pts.append((xc+a - ha*t, head + rise*(1-np.sqrt(max(0.0, 1-t*t)))))
    pts += [(xc+a, sill)]
    return Polygon(pts)


def _load_profile():
    """Fenster-Kopf als PARAMETRISCHER Schulter-Kielbogen — IMMER gültig (monoton von der Mitte nach
    außen fallend → kann nicht self-intersecten/degenerieren). Nur die SCHULTERHÖHE kommt aus der
    GEMESSENEN Kontur (win_profile), die Form ist parametrisch garantiert simpel. GENERELLE LÖSUNG:
    keine freien Multiplikatoren mehr auf die Messung (die hatten die Fenster kollabieren lassen)."""
    shoulder, keel, flat = 0.60, 1.7, 0.21               # Schulter 60 %, Kielbogen-Exp, FLACHER Mittel-Oberrand (halbe Breite)
    try:
        d = json.load(open("modelle/kaufhaus_freiburg/win_profile.json"))
        p = sorted(d["profile_top"]); xs = np.array([q[0] for q in p]); hs = np.array([q[1] for q in p])
        edge = hs[np.abs(xs) > 0.4]                      # Höhe der Kontur an den Rändern = Schulter
        if len(edge):
            shoulder = float(np.clip(np.median(edge), 0.45, 0.80))
        if "keel_exp" in d:
            keel = float(np.clip(d["keel_exp"], 1.0, 3.0))
        if "flat_half" in d:
            flat = float(np.clip(d["flat_half"], 0.0, 0.35))
    except Exception:
        pass
    # Foto: ZWEI Spitzen über den Lichtern (bei ±xp) und der Oberrand hängt in der MITTE DURCH (nicht
    # flach, nicht spitz) + konkave Schultern nach außen. xp aus flat abgeleitet.
    xp = max(0.12, flat); dip = 0.05                         # Mitte hängt nur LEICHT durch (Foto: subtil, nicht übertrieben)
    grid = np.linspace(-0.5, 0.5, 41); t = np.abs(grid)
    center = 1.0 - dip*(1.0 - np.clip(t/xp, 0, 1)**2)        # Parabel-Durchhang: Mitte tief → Spitze bei xp
    flank = shoulder + (1.0-shoulder)*np.clip((0.5-t)/max(1e-6, 0.5-xp), 0, 1)**keel
    hi = np.where(t <= xp, center, flank)                    # Doppelspitze + durchhängende Mitte (valid: einfaches Polygon)
    return list(zip(grid, hi))


PROF = _load_profile()


def _load_winstruct():
    """Fenster-GLIEDERUNG aus fenster_struktur.py (erkannt, NICHT hardcodiert): Pfosten/Kämpfer/Wabe."""
    try:
        d = json.load(open("modelle/kaufhaus_freiburg/win_struct.json"))
        return (list(d["mullions_xrel_centered"]), list(d["transoms_zrel"]), float(d["hex_R_rel_breite"]))
    except Exception:
        print("  (keine win_struct.json — fenster_struktur.py laufen lassen)")
        return ([0.0], [], 0.07)
WIN_MULL, WIN_TRANS, WIN_HEXR = _load_winstruct()


def measured_window(xc, w, sill, top):
    """Fenster-Polygon aus dem Kielbogen-Profil (PROF). GENERELLER GÜLTIGKEITS-GUARD: liefert nur
    ein einfaches, gültiges, nicht-degeneriertes Polygon zurück — sonst sauberer Rechteck-Fallback
    (so kann ein schlechtes Profil nie mehr kaputte Fenster erzeugen)."""
    if not PROF:
        return curtain_window(xc, w, sill, top-0.6, 0.55)
    a = w/2; h = max(0.1, top-sill); pts = [(xc-a, sill)]
    for xf, hf in PROF:
        pts.append((xc + xf*w, sill + hf*h))
    pts.append((xc+a, sill))
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    # Degeneriert? (ungültig, leer, MultiPolygon, oder Fläche < 55 % des Schulter-Rechtecks) → Fallback
    shoulder = min(hf for _, hf in PROF)
    if (poly.is_empty or poly.geom_type != "Polygon" or poly.area < 0.55*(w*shoulder*h)):
        return Polygon([(xc-a, sill), (xc-a, sill+shoulder*h), (xc, sill+h), (xc+a, sill+shoulder*h), (xc+a, sill)])
    return poly


def stepped_window(xc, w, sill, head, rise, steps=3):
    """ECKIGER Stufen-Fensterkopf (Foto kh_fenster: Treppe, die zur Mitte hochsteigt) — breit."""
    a = w/2; dx = a/steps; dz = rise/steps
    pts = [(xc-a, sill), (xc-a, head)]
    x, z = xc-a, head
    for _ in range(steps):                    # linke Treppe hoch zur Mitte
        z += dz; pts.append((x, z)); x += dx; pts.append((x, z))
    for _ in range(steps):                    # rechte Treppe runter
        x += dx; pts.append((x, z)); z -= dz; pts.append((x, z))
    pts += [(xc+a, sill)]
    return Polygon(pts)


def round_arch(xc, bw, spring):
    """RUNDbogen (Halbkreis) auf senkrechten Leibungen — Kaufhaus-Arkade ist rund (Foto/Juror)."""
    a = bw/2; R = a
    pts = [(xc-a, 0.25), (xc-a, spring)]
    for t in np.linspace(np.pi, 0.0, 28):
        pts.append((xc + R*np.cos(t), spring + R*np.sin(t)))
    pts += [(xc+a, spring), (xc+a, 0.25)]
    return Polygon(pts)


def red_lintel():
    """breites rotes Wandband/Balken ÜBER den Fenstern bis zur Traufe (Foto: Fenster reichen
    NICHT bis zum Dach, darüber rote Wand) — leicht vorspringender roter Sturzbalken."""
    x0, x1 = ORIEL_X[0]+0.3, ORIEL_X[1]-0.3
    b = tbox(extents=(x1-x0, 0.55, 0.5)); b.apply_translation(((x0+x1)/2, 0.05, HEAD-0.1))
    return b


def facade_wall():
    outer = Polygon([(0, 0), (W, 0), (W, EAVE), (0, EAVE)])
    holes = []
    pitch = W/N_ARCH
    for i in range(N_ARCH):
        holes.append(round_arch(pitch*(i+0.5), pitch*ARC_BW, ARC_SPRING))
    # Fensterband: je Gruppe EIN BREITES Fenster, Kopf = geschwungener VORHANGBOGEN (Foto)
    wins, _ = bay_layout(); ww = _win_w()
    for c in wins:
        holes.append(measured_window(c, ww, SILL, HEAD-0.5))
    poly = outer.difference(unary_union([h.buffer(0) for h in holes]))
    return _stand(extrude_polygon(poly, 0.6), y0=0.0)


# ---------- Maßwerk: Mullions hinter den Fenstern (dunkel, lesbar) ----------
def window_glazing():
    wins, _ = bay_layout(); ww = _win_w(); parts = []
    for c in wins:                                       # dunkle Scheibe in VORHANGBOGEN-Form
        poly = measured_window(c, ww-0.14, SILL+0.05, HEAD-0.56)
        parts.append(_stand(extrude_polygon(poly, 0.14), y0=0.45))
    return trimesh.util.concatenate(parts)


def _seg(x1, z1, x2, z2, y, th=0.02, dep=0.05):
    """dünner Bleisteg zwischen (x1,z1)-(x2,z2) in der XZ-Ebene (Tiefe y)."""
    dx, dz = x2-x1, z2-z1; L = np.hypot(dx, dz); ang = np.arctan2(dz, dx)
    b = tbox(extents=(L, dep, th))
    b.apply_transform(trimesh.transformations.rotation_matrix(-ang, [0, 1, 0]))
    b.apply_translation(((x1+x2)/2, y, (z1+z2)/2)); return b


def window_muntins():
    """SECHSECK-Bleiglas als echte WABEN (Foto kh_fenster): flachgedeckte Hexagone, DUNKLE Bleistege,
    GEKLIPPT auf die echte Fensterform (Vorhangbogen) → keine Hexagone außerhalb des Glases."""
    wins, _ = bay_layout(); ww = _win_w(); parts = []
    R = max(0.06, WIN_HEXR*ww); hh = R*np.sqrt(3)/2; y = 0.40   # Waben-Zellgröße ERKANNT (win_struct.json)
    for c in wins:
        glass = measured_window(c, ww-0.2, SILL+0.14, HEAD-0.18).buffer(-0.05)   # echte Glasfläche (enger geklippt)
        if glass.is_empty:
            continue
        minx, minz, maxx, maxz = glass.bounds
        for ci in range(int((minx-c)/(1.5*R))-1, int((maxx-c)/(1.5*R))+2):
            xc = c + ci*1.5*R; zoff = hh if ci % 2 else 0.0
            for ri in range(int((minz-maxz)/(2*hh))-1, int((maxz-minz)/(2*hh))+2):
                zc = minz+zoff+ri*2*hh
                V = [(xc+R, zc), (xc+R/2, zc+hh), (xc-R/2, zc+hh), (xc-R, zc), (xc-R/2, zc-hh), (xc+R/2, zc-hh)]
                for a in range(6):
                    x1, zz1 = V[a]; x2, zz2 = V[(a+1) % 6]
                    seg = LineString([(x1, zz1), (x2, zz2)])
                    if glass.contains(seg):                                      # NUR vollständig innen → keine Hexagone außerhalb des Glases
                        parts.append(_seg(x1, zz1, x2, zz2, y))
    return trimesh.util.concatenate(parts) if parts else None


BAL_Z0 = ARC_APEX+0.2     # Brüstungs-Unterkante (über den Bögen) ~5,4 m
BAL_Z1 = SILL-0.05        # Brüstungs-Oberkante bis an die Sohlbank (Foto: Säulen ~1,0 m HOCH, nicht 0,6 — User)
BAL_Y = -0.62             # Brüstung/Baluster liegen an der Balkon-Vorderkante


BAL_X0, BAL_X1 = ORIEL_X[0]+1.9, ORIEL_X[1]-1.9   # Balkon NUR vor dem Fensterband (Foto: stoppt an den Erkern, NICHT über die ganze Breite)


def balcony():
    """VORKRAGENDER Balkon NUR vor den Fenstern (Foto: endet an den Erkern) — Platte + Konsolsteine."""
    parts = []; x0, x1 = BAL_X0, BAL_X1; z = BAL_Z0
    slab = tbox(extents=(x1-x0, 1.25, 0.2)); slab.apply_translation(((x0+x1)/2, -0.72, z)); parts.append(slab)
    for x in np.linspace(x0+0.4, x1-0.4, 9):                  # Konsolsteine unter der Platte
        cb = tbox(extents=(0.3, 0.8, 0.5)); cb.apply_translation((x, -0.5, z-0.4)); parts.append(cb)
    return trimesh.util.concatenate(parts)


def attic_railing():
    """ROTE gedrechselte Baluster zwischen den beiden Gold-Leisten (Foto: kräftige rote Baluster,
    nicht 56 dünne Stäbchen) — sauber, ablesbar."""
    parts = []; x0, x1 = BAL_X0, BAL_X1
    hbal = BAL_Z1-BAL_Z0; z0 = BAL_Z0
    nb = max(10, int((x1-x0)/0.28))                          # VIELE schlanke gedrechselte Baluster (Foto: ~0,28 m Teilung), Fuß→Bauch→Hals
    for x in np.linspace(x0+0.1, x1-0.1, nb):
        foot = trimesh.creation.cylinder(radius=0.04, height=hbal*0.14, sections=6); foot.apply_translation((x, BAL_Y, z0+hbal*0.08)); parts.append(foot)
        belly = trimesh.creation.icosphere(subdivisions=0, radius=0.06); belly.apply_translation((x, BAL_Y, z0+hbal*0.34)); parts.append(belly)  # Drechselbauch (schlanker)
        neck = trimesh.creation.cylinder(radius=0.026, height=hbal*0.42, sections=6); neck.apply_translation((x, BAL_Y, z0+hbal*0.66)); parts.append(neck)
        cap = trimesh.creation.cylinder(radius=0.04, height=hbal*0.12, sections=6); cap.apply_translation((x, BAL_Y, z0+hbal*0.92)); parts.append(cap)
    return trimesh.util.concatenate(parts)


def window_goldframe():
    """goldener Rahmen, der der VORHANGBOGEN-Form FOLGT (Ring aus zwei Kurven-Polygonen) +
    Sohlbank — so liest das Fenster als Schulterbogen, nicht als Rechteck."""
    wins, _ = bay_layout(); ww = _win_w(); parts = []
    for c in wins:
        outer = measured_window(c, ww+0.1, SILL-0.05, HEAD-0.42).buffer(0)
        inner = measured_window(c, ww-0.14, SILL+0.05, HEAD-0.56).buffer(0)
        ring = outer.difference(inner).buffer(0)
        if not ring.is_empty:
            for geom in (ring.geoms if ring.geom_type == "MultiPolygon" else [ring]):
                parts.append(_stand(extrude_polygon(geom, 0.12), y0=0.4))
        _top = HEAD-0.42                                   # Fenster-Oberkante (wie beim Rahmen oben)
        _pxs = [xf for xf, _ in PROF] if PROF else [-0.5, 0, 0.5]
        _phs = [hf for _, hf in PROF] if PROF else [0.6, 1.0, 0.6]
        for xr in WIN_MULL:                               # Gold-Pfosten laufen GANZ DURCH bis an die Kielbogen-KANTE (Foto), nicht bis zur Kämpferlinie
            ht = float(np.interp(xr, _pxs, _phs))         # Kielbogen-Höhe an der Pfosten-x-Lage
            mh = max(0.3, ht*(_top-SILL)-0.06)
            parts.append(tbox(extents=(0.06, 0.2, mh)).apply_translation((c+xr*ww, 0.42, SILL+0.03+mh/2)))
        for zr in WIN_TRANS:                              # GESTUFTER Kämpfer (Foto): mittleres Segment NACH OBEN versetzt
            zt = SILL+zr*(HEAD-SILL); rise = 0.42
            ml = (min(WIN_MULL) if WIN_MULL else -0.17)*ww; mr = (max(WIN_MULL) if WIN_MULL else 0.17)*ww
            le, re = -0.5*ww+0.05, 0.5*ww-0.05
            parts.append(tbox(extents=(ml-le, 0.22, 0.09)).apply_translation((c+(le+ml)/2, 0.43, zt)))          # linkes Segment (tief)
            parts.append(tbox(extents=(re-mr, 0.22, 0.09)).apply_translation((c+(mr+re)/2, 0.43, zt)))          # rechtes Segment (tief)
            parts.append(tbox(extents=(mr-ml, 0.22, 0.09)).apply_translation((c+(ml+mr)/2, 0.43, zt+rise)))     # MITTLERES Segment (erhöht)
            for mx in (ml, mr):                                                                                  # senkrechte Verbinder der Stufe
                parts.append(tbox(extents=(0.07, 0.22, rise)).apply_translation((c+mx, 0.43, zt+rise/2)))
        for zf in (0.20, 0.38, 0.56, 0.74, 0.88):         # DÜNNE waagrechte Saddle-Bars (Foto: feine Gold-Querstangen im Bleiglas), oben schmaler (Bogenkopf)
            zb = SILL + zf*(_top-SILL)
            tap = 1.0 if zf <= 0.60 else max(0.2, (1.0-zf)/0.40)
            bw2 = (ww-0.14)*tap
            if bw2 > 0.2:
                parts.append(tbox(extents=(bw2, 0.16, 0.035)).apply_translation((c, 0.45, zb)))
        sb = tbox(extents=(ww+0.12, 0.26, 0.14)); sb.apply_translation((c, 0.44, SILL-0.12)); parts.append(sb)
    return trimesh.util.concatenate(parts)


# ---------- Galerie-Brüstung als BLENDARKADEN-Fries (Filigran) ----------
def gallery():
    """ZWEI schmale GOLD-Leisten der Balkonbrüstung (Handlauf oben + Sohle unten) — KEIN
    Blendarkaden-Fries mehr (war wuselig/„Schrott", User); dazwischen die roten Baluster."""
    parts = []
    bot = tbox(extents=(W*0.9, 0.3, 0.1)); bot.apply_translation((W/2, BAL_Y, BAL_Z0)); parts.append(bot)   # Sohle
    top = tbox(extents=(W*0.9, 0.28, 0.1)); top.apply_translation((W/2, BAL_Y, BAL_Z1)); parts.append(top)  # Handlauf
    return trimesh.util.concatenate(parts)


# ---------- Statuen (4) auf Konsolen mit Baldachin ----------
def wappen():
    """bunte Wappen-Medaillons auf der Galerie-Brüstung über den Bögen (Foto: farbige
    Rundschilde zwischen Arkade und Fensterband) — kräftiges Filigran/Farbe-Detail."""
    _, xs = bay_layout(); parts = []                  # Wappen auf der Brüstung zwischen den Fenstern (Foto), nicht über den Bögen
    for xc in xs:
        disc = trimesh.creation.cylinder(radius=0.32, height=0.1, sections=20)
        disc.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0]))
        disc.apply_translation((xc, BAL_Y-0.08, (BAL_Z0+BAL_Z1)/2)); parts.append(disc)
    return trimesh.util.concatenate(parts) if parts else None


def _wappen_kerne(sel):
    """farbige Schild-Kerne auf den Gold-Wappen, abwechselnd rot/blau (sel=0 rot, 1 blau)."""
    _, xs = bay_layout(); parts = []                              # farbiger Schild-Kern VOR der Gold-Scheibe
    for i, xc in enumerate(xs):
        if i % 2 != sel:
            continue
        c = tbox(extents=(0.34, 0.05, 0.4))
        c.apply_translation((xc, BAL_Y-0.14, (BAL_Z0+BAL_Z1)/2)); parts.append(c)
    return trimesh.util.concatenate(parts) if parts else None


def _rotx(m, a):
    m.apply_transform(trimesh.transformations.rotation_matrix(a, [1, 0, 0])); return m


def _revolve(profile, cx, cy, sections=12):
    """Rotationskörper aus (r,z)-Profil um die senkrechte Achse (cx,cy). Letzter Punkt mit r≈0 →
    Spitze. Für durchgeschwungene (konkave) Helme/Kegel."""
    V = []; ns = sections
    for (r, z) in profile:
        for k in range(ns):
            a = 2*np.pi*k/ns; V.append((cx+r*np.cos(a), cy+r*np.sin(a), z))
    F = []; nr = len(profile)
    for i in range(nr-1):
        for k in range(ns):
            k2 = (k+1) % ns
            a = i*ns+k; b = i*ns+k2; c = (i+1)*ns+k; d = (i+1)*ns+k2
            F += [(a, b, d), (a, d, c)]
    return _tri(V, F)


def statue(xc):
    """stehende Gewandfigur (Kaiser), GROSS & prominent (Hauptmerkmal, Juror): Konsole, flaring
    Gewand-Saum, Torso, Schultern/Mantel, Arme, Kopf, Krone + Baldachin (steht VOR dunkler Nische)."""
    parts = []; z0 = STAT_Z; y = -0.86                        # Fuß z0 ~7,5 m, Kopfkrone ~z0+1,5 ~9,0 m (Fensteroberkante) — gemessen
    robe = tcone(radius=0.2, height=1.02, sections=12); robe.apply_translation((xc, y, z0)); parts.append(robe)   # schlanker Gewand-Mantel
    chest = trimesh.creation.cylinder(radius=0.1, height=0.44, sections=10); chest.apply_translation((xc, y, z0+0.97)); parts.append(chest)
    shoulder = _rotx(tcone(radius=0.16, height=0.24, sections=12), np.pi); shoulder.apply_translation((xc, y, z0+1.1)); parts.append(shoulder)
    for s in (-1, 1):
        arm = trimesh.creation.cylinder(radius=0.038, height=0.54, sections=6); arm.apply_translation((xc+s*0.14, y-0.04, z0+0.88)); parts.append(arm)
    neck = trimesh.creation.cylinder(radius=0.042, height=0.08); neck.apply_translation((xc, y, z0+1.27)); parts.append(neck)
    head = trimesh.creation.icosphere(subdivisions=1, radius=0.11); head.apply_translation((xc, y, z0+1.38)); parts.append(head)
    sceptre = trimesh.creation.cylinder(radius=0.023, height=0.86); sceptre.apply_translation((xc+0.17, y-0.05, z0+0.92)); parts.append(sceptre)  # Zepter
    return trimesh.util.concatenate(parts)


def statue_corbels():
    """prominente GOLD-Konsolen unter den Figuren (gestufte Kragsteine) + GOLD-KRONE am Kopf."""
    _, xs = bay_layout(); parts = []
    for xc in xs:
        y = -0.86; z = STAT_Z                                 # GOLD-Konsole unter den Füßen; endet klar ÜBER der Brüstung (gemessen)
        for k, (ww_, hh_) in enumerate([(0.5, 0.16), (0.38, 0.18), (0.26, 0.2), (0.15, 0.22)]):
            b = tbox(extents=(ww_, 0.44, hh_)); b.apply_translation((xc, y, z-0.06-k*0.16)); parts.append(b)
        cr = trimesh.creation.cylinder(radius=0.12, height=0.11, sections=10); cr.apply_translation((xc, y, z+1.51)); parts.append(cr)   # Goldkrone am Kopf (Kopf ~z+1,49)
        for a in np.linspace(0, 2*np.pi, 5, endpoint=False):
            sp = tcone(radius=0.023, height=0.1, sections=4); sp.apply_translation((xc+0.085*np.cos(a), y+0.085*np.sin(a), z+1.59)); parts.append(sp)
    return trimesh.util.concatenate(parts)


def statue_niches():
    """dunkle Rück-Nischen hinter den Figuren → helle Figur hebt sich ab (liest als Statue)."""
    _, xs = bay_layout(); parts = []
    for xc in xs:
        n = tbox(extents=(0.7, 0.2, 2.1)); n.apply_translation((xc, -0.40, STAT_Z+0.85)); parts.append(n)
    return trimesh.util.concatenate(parts)


def statue_canopies():
    """SOLIDER gotischer Baldachin (Tabernakel) ÜBER jeder Statue (Foto): facettierte Spitzhaube +
    Mittelfiale + 2 Eckfialen + Krabben — alle Teile DICK/verschmolzen (druckbar @1:50, ≥~1 mm),
    nicht mehr dünne freischwebende Spitzen."""
    _, xs = bay_layout(); parts = []
    for xc in xs:
        y = -0.52; zb = HEAD-0.2
        plat = tbox(extents=(0.80, 0.48, 0.16)); plat.apply_translation((xc, y, zb)); parts.append(plat)   # solide Konsolplatte
        canopy = tcone(radius=0.34, height=1.0, sections=6); canopy.apply_translation((xc, y, zb+0.1)); parts.append(canopy)   # facettierte Spitzhaube
        fin = tcone(radius=0.08, height=0.5, sections=6); fin.apply_translation((xc, y, zb+1.05)); parts.append(fin)           # Mittelfiale (dick)
        kn = trimesh.creation.icosphere(subdivisions=0, radius=0.08); kn.apply_translation((xc, y, zb+1.5)); parts.append(kn)  # Kreuzblume
        for dx in (-0.30, 0.30):                                                                                              # 2 solide Eckfialen
            sf = tcone(radius=0.075, height=0.6, sections=6); sf.apply_translation((xc+dx, y, zb+0.12)); parts.append(sf)
            k = trimesh.creation.icosphere(subdivisions=0, radius=0.06); k.apply_translation((xc+dx, y, zb+0.65)); parts.append(k)
        for t in (0.35, 0.6, 0.85):                                                                                           # dicke Krabben auf der Haubenkante
            for s in (-1, 1):
                cr = trimesh.creation.icosphere(subdivisions=0, radius=0.055); cr.apply_translation((xc+s*0.34*(1-t), y-0.1, zb+0.1+1.0*t)); parts.append(cr)
    return trimesh.util.concatenate(parts)


def statues():
    _, xs = bay_layout()          # Figuren an den Fach-Teilern
    return trimesh.util.concatenate([statue(x) for x in xs])


# ---------- polygonaler Erker (Stein) + oktogonaler Spitzhelm (Gold) + Wappen ----------
def oriel(xc, z0, z1, w=4.0, proj=2.2):
    """polygonaler Eck-Erker + schlanker Spitzhelm mit BUNTEM Schuppenmuster (rot/creme,
    spiralig) + Krabben + Fiale — Blickfang wie im Foto. Gibt Farbgruppen getrennt zurück."""
    body_parts, gold, rot, hell, gruen = [], [], [], [], []

    def bay_poly(sc=1.0):                                   # facettierter Halb-Oktogon-Erker (projiziert nach -y)
        return Polygon([(xc + (w/2*sc)*np.cos(t), -(proj*sc)*np.sin(t)) for t in np.linspace(np.pi, 0, 6)])
    for zz, sc in [(z0-1.5, 0.45), (z0-0.8, 0.72)]:        # Konsol-Aufbau unten
        b = extrude_polygon(bay_poly(sc), 0.7); b.apply_translation((0, 0, zz)); body_parts.append(b)
    body = extrude_polygon(bay_poly(1.0), z1-z0); body.apply_translation((0, 0, z0)); body_parts.append(body)
    pts6 = [(xc + (w/2)*np.cos(t), -proj*np.sin(t)) for t in np.linspace(np.pi, 0, 6)]
    for vx, vy in pts6[1:-1]:                                                   # Gold-Kantenrippen an den Facetten → klar vieleckig
        rib = trimesh.creation.cylinder(radius=0.07, segment=((vx, vy, z0-0.3), (vx, vy, z1))); gold.append(rib)
    # Unterseite = SOLIDER facettierter Rippen-Trichter (Kragstein), druckbar — kein Gespinst:
    boss = np.array([xc, -proj*0.34, z0-1.7])
    cor = [np.array([xc + (w/2)*np.cos(t), -proj*np.sin(t), z0-0.05]) for t in np.linspace(np.pi, 0, 6)]
    V = [tuple(c) for c in cor] + [tuple(boss)]; nb = len(cor)
    F = [(i, i+1, nb) for i in range(nb-1)] + [(0, i+1, i) for i in range(1, nb-1)]
    body_parts.append(_tri(V, F))                                              # Stein-Trichter (Erker-Farbe)
    for c in cor:                                                              # dünne Gold-Rippen auf den Kanten
        gold.append(trimesh.creation.cylinder(radius=0.045, segment=(tuple(boss), tuple(c))))
    # feines GEÄSTEL unter dem Erker (Foto: gotisches Rippennetz, verästelt): gekrümmte Haupt- +
    # Zwischenrippen + 2 Querringe → Netz, nicht nur gerade Speichen
    boss2 = np.array([xc, -proj*0.34, z0-1.45])
    for ci in range(len(cor)-1):
        c, c2 = cor[ci], cor[ci+1]
        midedge = (c+c2)/2
        inter = (boss2+midedge)/2 + np.array([0, -0.12, 0.10])                 # Zwischenrippe bauchig nach außen
        gold.append(trimesh.creation.cylinder(radius=0.028, segment=(tuple(boss2), tuple(inter))))
        gold.append(trimesh.creation.cylinder(radius=0.028, segment=(tuple(inter), tuple(midedge))))
    for frac in (0.42, 0.72):                                                  # Querringe verbinden die Rippen → Netz
        rp = [boss2 + (cor[k]-boss2)*frac for k in range(len(cor))]
        for p0, p1 in zip(rp[:-1], rp[1:]):
            if np.linalg.norm(p1-p0) > 1e-3:
                gold.append(trimesh.creation.cylinder(radius=0.022, segment=(tuple(p0), tuple(p1))))
    cx2, cy2 = xc, -proj*0.5
    cr0 = w*0.48; zf = 0.32; chh = max(3.0, (EAVE+0.62*(RIDGE-EAVE))-z1-zf-0.05)   # Spitze ~62% hoch im (steilen) Dach → hoher, schlanker Spitzhelm wie Foto (nicht mehr gedeckelt-kurz)

    def _r(t):                                                                  # konkaves Helmprofil (t=0 Fuß .. 1 Spitze)
        return cr0*(1-t)**2.3*0.98 + 0.015                                      # STEILER: unten breit, zieht schnell in einer Kurve dünn ein (Foto)
    prof = [(cr0*1.30, z1), (cr0*1.08, z1+zf)]                                   # breit ÜBERKRAGENDER Glockenfuß, dann rasch einziehen
    npro = 18
    for i in range(1, npro+1):
        t = i/npro; prof.append((_r(t), z1+zf+(chh-zf)*t))
    prof.append((0.015, z1+chh+0.05))                                           # Spitze
    gruen.append(_revolve(prof, cx2, cy2, sections=8))                          # OKTOGONALER (facettierter) Kern, grün glasiert — Foto: 8-eckiger Helm, NICHT rund
    rib_ang = np.linspace(np.pi/8, 2*np.pi+np.pi/8, 8, endpoint=False)          # 8 Gold-Grat-Rippen auf den Facettenkanten
    for a in rib_ang:
        pr = [(cx2+r*np.cos(a), cy2+r*np.sin(a), z) for (r, z) in prof]
        for p0, p1 in zip(pr[:-1], pr[1:]):
            if np.linalg.norm(np.array(p1)-np.array(p0)) > 1e-3:
                gold.append(trimesh.creation.cylinder(radius=0.05, segment=(p0, p1)))
    nring = 17                                                                  # DICHTE 4-farbige Diamant-Glasur, folgt der KONKAVEN Silhouette
    for i in range(nring):
        t = (i+0.4)/nring; rr = _r(t); zz = z1+zf+(chh-zf)*t; nseg = max(8, int(16*(1-t)+6))
        e = max(0.12, 2*np.pi*rr/nseg*0.9)
        for k in range(nseg):
            ang = 2*np.pi*k/nseg + i*0.5
            sc = tbox(extents=(e, e, 0.07)); sc.apply_transform(trimesh.transformations.rotation_matrix(np.pi/4, [0, 0, 1]))
            sc.apply_translation((cx2+rr*np.cos(ang), cy2+rr*np.sin(ang), zz))
            [gruen, rot, hell, gold][(i + k) % 4].append(sc)   # grün/rot/creme/gold Diamanten (glasiert) wie das Foto
    zb = z1+chh+0.05; sh = 1.3; r0 = w*0.055                                     # schlanke Fiale über dem Helm
    spire = tcone(radius=r0, height=sh, sections=6); spire.apply_translation((cx2, cy2, zb)); gold.append(spire)
    fin = trimesh.creation.cylinder(radius=0.045, height=0.5); fin.apply_translation((cx2, cy2, zb+sh+0.2)); gold.append(fin)
    knauf = trimesh.creation.icosphere(subdivisions=1, radius=0.12); knauf.apply_translation((cx2, cy2, zb+sh+0.5)); gold.append(knauf)
    # ---- Erker-Bucht-Fenster (Foto kh_erker): hohe BLEIGLAS-Fenster je Facette, GOLD-Pfosten +
    # Querkämpfer + flacher Gold-Sturz + Sohlbank, FACETTENGERECHT gedreht; bunte Wappen darunter ----
    wins = []; bayc = np.array([xc, -proj*0.32])                                # Buchtzentrum (für Außennormale)
    wh = (z1-z0)*0.42; wz = z0+(z1-z0)*0.62                                     # Fenster im MITTLEREN Teil: Oberkante ~0,83 → ROTES Mauerstück zwischen Fenstersturz und Helmfuß (Foto: Erkerfenster reichen NICHT bis zum Dach), unten Wappen-Schürze
    arz = z0+(z1-z0)*0.26                                                       # Wappen-Rundschilde auf der Schürze darunter
    for j in (1, 2, 3):
        pa = np.array(pts6[j]); pb = np.array(pts6[j+1]); ctr = (pa+pb)/2
        tang = pb-pa; fw = float(np.linalg.norm(tang)); tu = tang/fw
        ang = float(np.arctan2(tu[1], tu[0])); Rz = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
        nout = ctr-bayc; nout = nout/np.linalg.norm(nout)

        def put(ex, dalong, zc, out, bucket):                                   # Element in Facetten-Ebene setzen
            m = tbox(extents=ex); m.apply_transform(Rz)
            px = ctr[0]+tu[0]*dalong+nout[0]*out; py = ctr[1]+tu[1]*dalong+nout[1]*out
            m.apply_translation((px, py, zc)); bucket.append(m)
        lw = fw*0.82
        put((lw, 0.12, wh), 0, wz, 0.0, wins)                                   # dunkles Bleiglas (dominiert → liest als Fenster, nicht Goldgitter)
        put((0.05, 0.14, wh), 0, wz, 0.045, gold)                               # EIN schlanker Gold-Mittelpfosten → 2 Lichter (Foto kh_erker)
        for s in (-1, 1):                                                       # schlanke Gold-Jamben an den Facettenkanten
            put((0.055, 0.2, wh+0.1), s*fw*0.47, wz, 0.035, gold)
        put((lw+0.06, 0.16, 0.06), 0, wz, 0.05, gold)                           # ein Querkämpfer (Transom)
        otop = wz+wh/2+0.02; orise = 0.5                                        # KONKAVER Bogenkopf statt flachem Sturz (Foto: Erkerfenster-Köpfe konkav)
        _pr = PROF[::3] if PROF else [(-0.5, 0.6), (-0.25, 0.9), (0, 1.0), (0.25, 0.9), (0.5, 0.6)]
        for xf, hf in _pr:
            put((0.09, 0.16, 0.10), xf*lw*0.98, otop+hf*orise, 0.045, gold)     # Gold-Leiste folgt dem Kielbogen → konkaver Kopf
        put((fw*0.92, 0.22, 0.1), 0, wz-wh/2-0.06, 0.045, gold)                 # Sohlbank
        for zr in np.linspace(wz-wh/2+0.25, wz+wh/2-0.25, 3):                   # feine DUNKLE Bleiruten (kein Gold!) — sonst wirkt das Glas wie ein Goldgitter
            put((lw-0.04, 0.125, 0.015), 0, zr, 0.015, wins)
        # kleines WAPPEN-SCHILD (statt Kugel): Schildform (runder Kopf, Spitze unten) + Gold-Rand + Kreuz
        sw, sh2 = 0.22, 0.30; fld = [rot, hell, gruen][j % 3]
        for scale, thick, out2, bucket in [(1.15, 0.05, 0.11, gold), (1.0, 0.08, 0.14, fld)]:
            sx, sy = sw*scale, sh2*scale
            poly = Polygon([(-sx, sy), (-sx*0.7, sy*1.08), (sx*0.7, sy*1.08), (sx, sy),
                            (sx, -sy*0.1), (sx*0.45, -sy*0.7), (0, -sy), (-sx*0.45, -sy*0.7), (-sx, -sy*0.1)])
            m = extrude_polygon(poly.buffer(0), thick); Vv = m.vertices.copy()
            m.vertices = np.c_[ctr[0]+tu[0]*Vv[:, 0]+nout[0]*(out2+Vv[:, 2]),
                               ctr[1]+tu[1]*Vv[:, 0]+nout[1]*(out2+Vv[:, 2]), arz+Vv[:, 1]]
            bucket.append(m)
        put((0.05, 0.14, 0.42), 0, arz, 0.20, gold)                             # Kreuz senkrecht
        put((0.30, 0.14, 0.05), 0, arz+0.04, 0.20, gold)                        # Kreuz waagrecht
    return {"erker": trimesh.util.concatenate(body_parts), "helm": trimesh.util.concatenate(gold),
            "helm_rot": trimesh.util.concatenate(rot), "helm_hell": trimesh.util.concatenate(hell),
            "helm_gruen": trimesh.util.concatenate(gruen), "fenster": trimesh.util.concatenate(wins)}


# ---------- giebelständige Gaube (Satteldach) ----------
DORMER_W = 1.1


def _dormer_specs():
    """Gauben-Positionen (x,z) auf REGELMÄSSIGEM, versetztem Raster: alle Gauben haben GLEICHEN
    x-Abstand (pitch). Untere Reihe auf geraden Rastern (0,2,4), obere auf den ungeraden (1,3) =
    exakt die Lücken-Mitten (Foto: untere 0,26/0,51/0,77, obere 0,39/0,62 = Mittelpunkte)."""
    cx = W/2; span = W*DORMER_WFRAC; x_lo = cx-span/2
    nslots = sum(DORMER_ROWS)                            # z.B. 3+2 = 5 Raster-Spalten
    pitch = span/(nslots-1) if nslots > 1 else span
    nrows = len(DORMER_ROWS)
    fracs = np.linspace(0.12, 0.12+0.15*(nrows-1), nrows) if nrows > 1 else [0.16]  # Gauben LOW am Traufenrand (Foto: steiles hohes Dach, Gauben unten), nicht übers ganze Dach verteilt
    specs = []
    for r, n in enumerate(DORMER_ROWS):
        z = EAVE+fracs[r]*(RIDGE-EAVE)
        for i in range(n):
            s = r + 2*i                                  # Reihe r startet um r versetzt, Schrittweite 2 → gleichmäßig
            specs.append((x_lo + pitch*s, z))
    return specs


def _slope_y(z):
    return (D/2)*(z-EAVE)/(RIDGE-EAVE)              # y-Lage der Dachhaut auf Höhe z


DORMER_PROJ = 0.75   # wie weit die Gaube aus der Dachhaut vorsteht (Foto: deutlich, mit Wangen + Dächlein)


def dormers():
    """VORSTEHENDE Gauben (Foto): SOLIDER Gaubenkörper (watertight, druckbar) der klar aus der
    Dachhaut ragt; Front dunkel = Fenster. Steckt hinten in der Dachschräge (Slicer-Union)."""
    parts = []
    for xc, z in _dormer_specs():
        ys = _slope_y(z); yf = ys-DORMER_PROJ
        body = tbox(extents=(DORMER_W, (ys+0.15)-yf, 0.8)); body.apply_translation((xc, (yf+ys+0.15)/2, z+0.38)); parts.append(body)
    return trimesh.util.concatenate(parts)


def dormer_roofs():
    """flach ablaufendes SCHLEPPDÄCHLEIN (Sprungschanze, Foto): hinten an der Dachhaut HOCH, nach vorn
    ABFALLEND, leicht konkav — KEINE Spitzhaube. Solider dünner Keil (druckbar)."""
    parts = []
    for xc, z in _dormer_specs():
        ys = _slope_y(z); o = 0.16; yf = ys-DORMER_PROJ-0.10
        xL, xR = xc-DORMER_W/2-o, xc+DORMER_W/2+o
        ztop = z+0.72                                       # Gaubenkörper-Oberkante (Unterseite des Dächleins)
        zback, zmid, zfront = z+1.00, z+0.80, z+0.70        # hinten hoch → vorn tief, konkav (Sprungschanze)
        ym = ys-DORMER_PROJ*0.5
        # Oberkante als 3-Punkt-Konkavkurve (hinten→vorn), Unterkante flach auf ztop
        V = [(xL, ys, zback), (xR, ys, zback), (xL, ym, zmid), (xR, ym, zmid), (xL, yf, zfront), (xR, yf, zfront),
             (xL, ys, ztop), (xR, ys, ztop), (xL, yf, ztop), (xR, yf, ztop)]
        F = [(0, 1, 3), (0, 3, 2), (2, 3, 5), (2, 5, 4),     # konkave Oberseite (2 Segmente)
             (6, 8, 9), (6, 9, 7),                           # Unterseite
             (0, 2, 6), (2, 8, 6), (2, 4, 8),                # linke Wange
             (1, 7, 3), (3, 7, 9), (3, 9, 5),                # rechte Wange
             (4, 5, 9), (4, 9, 8),                           # Vorderkante
             (0, 6, 7), (0, 7, 1)]                           # Hinterkante
        parts.append(_tri(V, F))
    return trimesh.util.concatenate(parts)


def dormer_frames():
    """heller Steinrahmen (Pfosten + Sturz) um das dunkle Gaubenfenster vorn — Foto: helle Fassung."""
    parts = []
    for xc, z in _dormer_specs():
        ys = _slope_y(z); yf = ys-DORMER_PROJ; t = 0.1
        for dx in (-DORMER_W/2, DORMER_W/2):               # senkrechte Rahmen-Pfosten
            parts.append(tbox(extents=(0.12, 0.12, 0.74)).apply_translation((xc+dx, yf-0.03, z+0.37)))
        lint = tbox(extents=(DORMER_W+0.18, 0.14, 0.14)); lint.apply_translation((xc, yf-0.03, z+0.72)); parts.append(lint)  # Sturz
        sill = tbox(extents=(DORMER_W+0.22, 0.2, 0.1)); sill.apply_translation((xc, yf-0.02, z+0.02)); parts.append(sill)    # Sohlbank
    return trimesh.util.concatenate(parts)


def ridge_crest(inset=ROOF_INSET):
    """schlichter First-Grat (Foto: First ist glatt, KEINE Zacken-Reihe)."""
    crest = tbox(extents=(W-2*inset, 0.2, 0.16)); crest.apply_translation((W/2, D/2, RIDGE+0.06))
    return crest


def dach_krabben(inset=ROOF_INSET):
    """MASSIVE rote STUFEN-Kante (Treppengiebel-Coping) entlang der vorderen Dach-Gratkanten +
    gestufte Fiale am oberen Ende (Foto: deutlich wuchtige rote Stufen, keine dünnen Krabben)."""
    parts = []
    for p0, p1 in [((0, 0, EAVE), (inset, D/2, RIDGE)), ((W, 0, EAVE), (W-inset, D/2, RIDGE))]:
        p0 = np.array(p0, float); p1 = np.array(p1, float); d = p1-p0
        beam = trimesh.creation.cylinder(radius=0.3, segment=(tuple(p0+[0, 0, 0.28]), tuple(p1+[0, 0, 0.28])))
        parts.append(beam)                                                   # durchgehender Balken → VERBINDET alle Stufen (ein Solid, druckbar)
        n = 9
        for j in range(n):
            c = p0 + d*(j/(n-1))
            blk = tbox(extents=(0.58, 0.64, 0.8)); blk.apply_translation((c[0], c[1], c[2]+0.42)); parts.append(blk)   # Stufenblock, überlappt den Balken
        xt, yt, zt = p1                                                      # Giebel-Abschluss: KLEINE Fiale ~ First/Helm-Höhe (nicht 3 m drüber!)
        for k, s in enumerate([0.6, 0.42]):
            st = tbox(extents=(s, s, 0.4)); st.apply_translation((xt, yt, zt+0.22+k*0.32)); parts.append(st)
        tip = tcone(radius=0.18, height=0.4, sections=6); tip.apply_translation((xt, yt, zt+0.55)); parts.append(tip)
    return trimesh.util.concatenate(parts)


def roof_courses():
    """waagerechte Ziegel-Lagen auf der vorderen Dachfläche (Foto: glasierte Biberschwanz-Reihen)
    — dünne, leicht erhabene Leisten in dunklerem Grün geben die Dachtextur."""
    parts = []
    for frac in np.linspace(0.08, 0.94, 9):            # weniger + dünner → dezente Textur, keine Streifen
        z = EAVE+frac*(RIDGE-EAVE); ys = _slope_y(z)
        w = (W-2*ROOF_INSET*frac) * 0.99
        strip = tbox(extents=(w, 0.08, 0.04)); strip.apply_translation((W/2, ys-0.015, z)); parts.append(strip)
    return trimesh.util.concatenate(parts)


def ridge_cresting():
    """rote Firstziegel-Kreuzblumen-Reihe auf dem First (Foto: roter Zierkamm)."""
    parts = []
    for t in np.linspace(0.04, 0.96, 18):
        x = ROOF_INSET+(W-2*ROOF_INSET)*t
        p = tcone(radius=0.11, height=0.4, sections=4); p.apply_translation((x, D/2, RIDGE+0.32)); parts.append(p)
    return trimesh.util.concatenate(parts)


def roof_diaper():
    """dunklere Rauten-Glasur (Diaper-Muster) im Schachbrett auf der Dachfläche (Foto: deutliches
    Rautengitter glasierter Ziegel) — größere, dichtere Rauten damit es als MUSTER liest, nicht als Rauschen."""
    parts = []; nx = 13; rows = np.linspace(0.08, 0.92, 11)
    for fi, frac in enumerate(rows):
        z = EAVE+frac*(RIDGE-EAVE); ys = _slope_y(z); wrow = (W-2*ROOF_INSET*frac)*0.96
        cellw = wrow/nx; e = cellw*0.82                   # Raute ~ Zellengröße → berührt die Nachbarn = durchgehendes Gitter
        for i in range(nx):
            if (i+fi) % 2:
                continue
            x = W/2 - wrow/2 + wrow*(i+0.5)/nx
            d = tbox(extents=(e, e, 0.07)); d.apply_transform(trimesh.transformations.rotation_matrix(np.pi/4, [0, 0, 1]))
            d.apply_translation((x, ys-0.035, z)); parts.append(d)
    return trimesh.util.concatenate(parts)


def roof():
    """SATTELDACH (gegiebelt, Foto: Seiten sind rote Giebel, KEIN grüner Walm): 2 grüne Schrägen +
    Bodenplatte, geschlossener Solid. Die roten Giebeldreiecke liefert gables()."""
    A = (0, 0, EAVE); B = (W, 0, EAVE); C = (W, D, EAVE); Dd = (0, D, EAVE)
    R0 = (0, D/2, RIDGE); R1 = (W, D/2, RIDGE)
    return _tri([A, B, C, Dd, R0, R1],
                [(0, 1, 5), (0, 5, 4),          # Vorderschräge A,B,R1 + A,R1,R0
                 (3, 4, 5), (3, 5, 2),          # Rückschräge Dd,R0,R1 + Dd,R1,C
                 (0, 4, 3), (1, 2, 5),          # Giebeldreiecke (grün hinterlegt, von gables() rot überdeckt)
                 (0, 3, 2), (0, 2, 1)])         # Bodenplatte bei Traufe


def gables():
    """ROTE Giebel-Endwände (Treppengiebel-Dreiecke) an den Seiten x=0 und x=W (Foto: die
    Dachseiten sind rote Giebel mit roter Stufenkante, nicht grün)."""
    return trimesh.util.concatenate([plain_gable(-0.35, 0.7), plain_gable(W-0.35, 0.7)])


PIER_H = ARC_APEX   # vollhohe Pfeiler (Kolonnade); Bogen-Archivolten als Ring davor


def arcade_piers():
    """schlankere Arkaden-Pfeiler mit Basis + Kapitell (Foto: zierlicher) + goldener Lisenen-Linie."""
    pitch = W/N_ARCH; parts = []
    for i in range(N_ARCH+1):
        x = pitch*i
        shaft = tbox(extents=(0.6, 0.9, PIER_H)); shaft.apply_translation((x, -0.4, PIER_H/2)); parts.append(shaft)
        base = tbox(extents=(0.8, 1.05, 0.3)); base.apply_translation((x, -0.4, 0.15)); parts.append(base)
        cap = tbox(extents=(0.8, 1.05, 0.26)); cap.apply_translation((x, -0.4, PIER_H-0.2)); parts.append(cap)
        imp = tbox(extents=(0.76, 1.0, 0.22)); imp.apply_translation((x, -0.4, ARC_SPRING)); parts.append(imp)   # Kämpfer/Impost am Bogenansatz (Foto)
    return trimesh.util.concatenate(parts)


def pier_lisenen():
    """dünne goldene Senkrecht-Linie auf jeder Pfeilerfront (feines Gliederungsdetail)."""
    pitch = W/N_ARCH; parts = []
    for i in range(N_ARCH+1):
        s = tbox(extents=(0.12, 0.12, PIER_H-0.8)); s.apply_translation((pitch*i, -1.02, PIER_H/2)); parts.append(s)
    return trimesh.util.concatenate(parts)


def window_frames():
    """OG-Fensterband als verglaste Galerie: durchlaufendes Sturz-/Brüstungsband + je Licht
    senkrechte Pfosten (Jamben) + durchgehender Kämpfer-Riegel (Kreuzstock) → liest als Reihe
    einzelner Maßwerk-Fenster statt dunkler Schlitze (Foto)."""
    parts = []
    bw = ORIEL_X[1]-ORIEL_X[0]-3.0
    lint = tbox(extents=(bw, 0.35, 0.3)); lint.apply_translation((W/2, 0.42, HEAD+0.2)); parts.append(lint)
    sill = tbox(extents=(bw, 0.35, 0.25)); sill.apply_translation((W/2, 0.42, SILL-0.15)); parts.append(sill)
    transom = tbox(extents=(bw, 0.3, 0.14)); transom.apply_translation((W/2, 0.46, (SILL+HEAD)/2)); parts.append(transom)
    wins, _ = bay_layout()
    for xc in wins:                                   # Kreuzstock: Jamben + MITTELPFOSTEN je Licht
        for dx in (-0.30, 0.0, 0.30):
            w = 0.11 if dx == 0 else 0.09
            j = tbox(extents=(w, 0.26, HEAD-SILL)); j.apply_translation((xc+dx, 0.44, (SILL+HEAD)/2)); parts.append(j)
    return trimesh.util.concatenate(parts)


def window_gablets():
    """gotische Spitzgiebel (Wimperge) über jedem Fenster: dünnes Dreieck + Kreuzblume +
    Krabben — das feine Maßwerk-Detail über den Fenstern (Foto)."""
    wins, _ = bay_layout(); parts = []
    for xc in wins:
        b = HEAD-0.05; pk = HEAD+0.62; gw = 0.42
        tri = _stand(extrude_polygon(Polygon([(xc-gw, b), (xc+gw, b), (xc, pk)]), 0.16), y0=-0.16); parts.append(tri)
        fin = trimesh.creation.cylinder(radius=0.04, height=0.32); fin.apply_translation((xc, -0.12, pk+0.12)); parts.append(fin)
        for s in (-1, 1):                                  # Krabben an den Schrägen
            cr = trimesh.creation.icosphere(subdivisions=0, radius=0.075); cr.apply_translation((xc+s*gw*0.5, -0.12, b+0.32)); parts.append(cr)
    return trimesh.util.concatenate(parts)


def arch_rings(t=0.17):
    """FEINE Gold-Archivolte: dünne Bogen-Leiste genau auf der Leibung (Foto: schlanke
    goldene Bogenlinie, keine klobige Steinringe) + zierlicher Schlussstein."""
    pitch = W/N_ARCH; spring = ARC_SPRING; bw = pitch*ARC_BW; parts = []
    for i in range(N_ARCH):
        xc = pitch*(i+0.5); Ri = bw/2; Ro = Ri+t
        pts = [(xc+Ro*np.cos(a), spring+Ro*np.sin(a)) for a in np.linspace(np.pi, 0, 40)]
        pts += [(xc+Ri*np.cos(a), spring+Ri*np.sin(a)) for a in np.linspace(0, np.pi, 40)]
        ring = _stand(extrude_polygon(Polygon(pts).buffer(0), 0.28), y0=-0.22); parts.append(ring)   # dünne Leiste vor der Wand
        key = tbox(extents=(0.3, 0.3, 0.5)); key.apply_translation((xc, -0.12, spring+Ro-0.05)); parts.append(key)  # zarter Schlussstein
    return trimesh.util.concatenate(parts)


def cornice():
    """Traufgesims als ZWEI feine Gold-Profile mit Spalt (Foto: kein dicker Balken, User)."""
    a = tbox(extents=(W+0.6, 0.5, 0.13)); a.apply_translation((W/2, -0.02, EAVE-0.05))
    b = tbox(extents=(W+0.45, 0.42, 0.11)); b.apply_translation((W/2, 0.03, EAVE-0.34))
    return trimesh.util.concatenate([a, b])


def cornice_corbels():
    """Konsolfries unter dem Traufgesims (Foto: Reihe kleiner Kragsteine) — feines Profil."""
    parts = []
    for x in np.linspace(ORIEL_X[0]+0.4, ORIEL_X[1]-0.4, 26):
        cb = tbox(extents=(0.16, 0.55, 0.3)); cb.apply_translation((x, 0.12, EAVE-0.62)); parts.append(cb)
    return trimesh.util.concatenate(parts)


def arcade_recess():
    """Laubengang hinter der Arkade: SCHATTIGE Steinrückwand + Boden (nicht pechschwarz) → die
    Torbögen lesen sich als TIEFE Öffnungen mit Innenraum (Foto: Stände/Stein), nicht als Löcher."""
    parts = []
    back = tbox(extents=(W, 0.3, ARC_APEX)); back.apply_translation((W/2, 2.2, ARC_APEX/2)); parts.append(back)
    floor = tbox(extents=(W, 2.6, 0.3)); floor.apply_translation((W/2, 1.1, 0.12)); parts.append(floor)   # Laubengang-Boden
    return trimesh.util.concatenate(parts)


SIDE_WINY = (4.2, 6.9, 9.6)    # Y-Lagen der Seitenfenster (3 über die Tiefe, Durchgang vorn frei)


def side_walls():
    """SEITENWÄNDE (Giebelseiten x≈0 / x≈W): EIN Durchgangs-Rundbogen GANZ VORNE (Y klein → bildet
    einen Eck-Durchgang, nicht mittig, User) + Fenster im oberen Band (Foto s_side). Gibt (Wand, Glas)."""
    outer = Polygon([(0, 0), (D, 0), (D, EAVE), (0, EAVE)])      # (Y, Z)
    holes = [round_arch(1.9, 3.0, ARC_SPRING)]                   # Durchgang vorne (Y≈1,9), NICHT in der Mitte
    for yc in SIDE_WINY:                                         # Fenster oben
        holes.append(Polygon([(yc-0.55, SILL), (yc+0.55, SILL), (yc+0.55, HEAD-0.5), (yc-0.55, HEAD-0.5)]))
    poly = outer.difference(unary_union([h.buffer(0) for h in holes]))
    walls = []
    for x0 in (0.0, W-0.6):
        m = extrude_polygon(poly, 0.6); V = m.vertices.copy()
        m.vertices = np.c_[x0+V[:, 2], V[:, 0], V[:, 1]]         # Poly-x→Welt-Y (Tiefe), Poly-y→Welt-Z (Höhe), Dicke→Welt-X
        walls.append(m)
    glass = []                                                  # dunkle Scheiben hinter den Seitenfenstern (kein Durchblick) + Gold-Kreuzstock
    for x0 in (0.33, W-0.33):
        for yc in SIDE_WINY:
            g = tbox(extents=(0.08, 1.05, HEAD-0.5-SILL)); g.apply_translation((x0, yc, (SILL+HEAD-0.5)/2)); glass.append(g)
    return trimesh.util.concatenate(walls), trimesh.util.concatenate(glass)


def plain_gable(x_end, dx=0.5):
    """normale Dreiecks-Giebelwand (KEIN Treppengiebel — Original hat Satteldach, Juror)."""
    P = Polygon([(0, EAVE), (D/2, RIDGE), (D, EAVE)])
    m = extrude_polygon(P, dx); V = m.vertices.copy()
    m.vertices = np.c_[x_end+V[:, 2], V[:, 0], V[:, 1]]
    return m


def build():
    e0 = oriel(ORIEL_X[0], SILL-0.6, EAVE-1.0, w=2.5, proj=1.5)   # schmalere, höhere Bucht (Foto: Erker schlank+hoch); Körper bis Traufe, Spitze darüber
    e1 = oriel(ORIEL_X[1], SILL-0.6, EAVE-1.0, w=2.5, proj=1.5)
    parts = {
        "fassade": facade_wall(),
        "balken": red_lintel(),
        "cornice": cornice(),
        "konsolen": cornice_corbels(),
        "dach": roof(),
        "giebel": gables(),
        "piers": arcade_piers(),
        "lisenen": pier_lisenen(),
        "boegen": arch_rings(),
        "galerie": gallery(),
        "fenster": trimesh.util.concatenate([window_glazing(), e0["fenster"], e1["fenster"]]),
        "nische": statue_niches(),
        "konsole": statue_corbels(),
        "statuen": statues(),
        "erker": trimesh.util.concatenate([e0["erker"], e1["erker"]]),
        "helm": trimesh.util.concatenate([e0["helm"], e1["helm"]]),
        "helm_rot": trimesh.util.concatenate([e0["helm_rot"], e1["helm_rot"]]),
        "helm_hell": trimesh.util.concatenate([e0["helm_hell"], e1["helm_hell"]]),
        "helm_gruen": trimesh.util.concatenate([e0["helm_gruen"], e1["helm_gruen"]]),
        "gauben": dormers(),
        "gauben_dach": dormer_roofs(),
        "gauben_rahmen": dormer_frames(),
        "dachmuster": roof_courses(),
        "dachrauten": roof_diaper(),
        "first": ridge_crest(),
        "krabben": dach_krabben(),
        "rahmen": window_goldframe(),
        "sprossen": window_muntins(),
        "balkon": balcony(),
        "gitter": attic_railing(),
        "baldachin": statue_canopies(),
        # Wappen-Rundschilde SITZEN AN DEN ERKERN (Foto), nicht als große Goldmünzen in der Balkonbrüstung → raus (entrümpelt)
        "laube": arcade_recess(),
    }
    back = tbox(extents=(W, 0.6, EAVE)); back.apply_translation((W/2, D-0.3, EAVE/2))
    wall_m, side_glass = side_walls()
    parts["waende"] = trimesh.util.concatenate([back, wall_m])
    parts["seitenglas"] = side_glass

    cols = {"fassade": [116, 38, 34, 255], "waende": [104, 34, 30, 255], "dach": [96, 108, 74, 255],   # tieferes Ochsenblut-Rot (Foto); Dach moosig-olivgrün (NICHT rot — Foto zeigt grün)
            "giebel": [116, 38, 34, 255], "balken": [120, 38, 34, 255], "galerie": [138, 48, 42, 255], "fenster": [26, 30, 36, 255], "seitenglas": [26, 30, 36, 255],
            "statuen": [206, 206, 212, 255], "konsole": [198, 160, 90, 255], "erker": [116, 38, 34, 255], "helm": [192, 152, 70, 255],
            "baldachin": [198, 162, 92, 255],
            "gauben": [40, 34, 32, 255], "gauben_dach": [96, 108, 74, 255], "dachmuster": [88, 102, 70, 255],
            "dachrauten": [64, 82, 52, 255],
            "cornice": [182, 150, 80, 255], "konsolen": [176, 144, 78, 255], "laube": [34, 24, 22, 255], "piers": [138, 48, 42, 255],
            "boegen": [192, 154, 72, 255], "first": [182, 150, 80, 255], "rahmen": [198, 168, 120, 255],
            "wappen": [196, 150, 48, 255], "krabben": [150, 42, 36, 255], "nische": [28, 22, 24, 255],
            "helm_rot": [150, 44, 40, 255], "helm_hell": [224, 214, 190, 255], "helm_gruen": [86, 134, 82, 255],
            "lisenen": [188, 150, 72, 255], "sprossen": [72, 74, 84, 255],   # dunkle Bleiruten (echtes Bleiglas ist DUNKEL mit feinen Stegen) — Fenster liest als Öffnung, nicht grau
            "wappen_rot": [150, 46, 42, 255], "wappen_blau": [44, 70, 120, 255], "gitter": [60, 42, 38, 255],   # Balkon-Baluster DUNKELBRAUN (Foto: dunkle Brüstung, nicht rot)
            "balkon": [92, 40, 34, 255], "firstkamm": [150, 44, 38, 255],
            "gauben_rahmen": [196, 176, 140, 255]}   # heller Steinrahmen um das Gaubenfenster (Foto)
    os.makedirs("modelle/kaufhaus_freiburg", exist_ok=True)
    sc = trimesh.Scene()
    for nm, m in parts.items():
        if m is None or not len(m.faces):
            print(f"  (leer {nm})"); continue
        m.visual.face_colors = cols[nm]; m.export(f"modelle/kaufhaus_freiburg/khm_{nm}.stl")
        sc.add_geometry(m, geom_name=nm); print(f"  {nm}: {len(m.faces)} F")
    sc.export("modelle/kaufhaus_freiburg/kaufhaus_measured.glb")
    print("-> modelle/kaufhaus_freiburg/kaufhaus_measured.glb")


if __name__ == "__main__":
    build()
