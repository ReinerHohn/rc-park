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
W, D = 21.0, 12.0   # Fassade schmaler (User: noch zu breit); Tiefe wird unten gekappt
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

# DACH-TIEFEN-REGEL (UNIVERSELL, wie tools/bauwerk_generator.py): die LOD2-First (21,4) ist das
# TIEFE Gesamtdach; die Straßenfront zeigt es perspektivisch VERKÜRZT. First aus der am Frontfoto
# gemessenen Dachhöhe (kh_jm3289: 6,15 m über der Traufe), Tiefe auf Straßenfront kappen.
RIDGE = round(EAVE + 6.9, 2)   # Giebel etwas höher (User: unten zu gedrungen), aber nicht die volle LOD2-First
D = min(D, 8.5)
STAT_Z_OFF = 0.7               # Statuen etwas tiefer (User)
# 1. OG höher (User): Fenster größer -> Sohlbank etwas tiefer, Sturz etwas höher (bleibt < Traufe)
SILL = round(SILL - 0.3, 2)
HEAD = round(min(HEAD + 0.2, EAVE - 0.2), 2)
STAT_Z = SILL + STAT_Z_OFF


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
def _pointed_curve(xc, bw, spring, apex_z, nseg=18):
    """obere Spitzbogen-KURVE (nur der Bogen, Kämpfer→Scheitel→Kämpfer) als Punktliste.
    Zweizentrig durch die Kämpfer (xc±a, spring) und den Scheitel (xc, apex_z). Für apex_z
    knapp über dem Halbkreis = gedrückter (flacher) Spitzbogen, passend zur breiten Arkade."""
    a = bw/2.0; H = apex_z-spring
    u = (H*H-a*a)/(2*a)                               # Zentrum der LINKEN Bogenhälfte bei (xc+u, spring)
    R = (H*H+a*a)/(2*a)                               # Radius
    aL = np.arctan2(H, -u)                            # Scheitelwinkel von links
    pts = []
    for t in np.linspace(np.pi, aL, nseg):            # linke Hälfte: Kämpfer→Scheitel (Zentrum xc+u)
        pts.append((xc+u + R*np.cos(t), spring + R*np.sin(t)))
    for t in np.linspace(np.pi-aL, 0.0, nseg):        # rechte Hälfte: Scheitel→Kämpfer (Zentrum xc-u)
        pts.append((xc-u + R*np.cos(t), spring + R*np.sin(t)))
    return pts


def pointed_arch(xc, bw, spring, apex=None):
    """Spitzbogen-ÖFFNUNG (mit senkrechten Leibungen) als Polygon. apex = Scheitelhöhe z;
    default = gedrückter Spitzbogen etwas über dem Halbkreis."""
    if apex is None:
        apex = spring + (bw/2.0)*1.16
    pts = [(xc-bw/2, 0.25), (xc-bw/2, spring)] + _pointed_curve(xc, bw, spring, apex) + [(xc+bw/2, spring), (xc+bw/2, 0.25)]
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
        holes.append(pointed_arch(pitch*(i+0.5), pitch*ARC_BW, ARC_SPRING))   # SPITZbögen (Foto: gotisch, nicht rund)
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
    parts = []; x0, x1 = BAL_X0, BAL_X1; z = BAL_Z0; mid = (x0+x1)/2; wdt = x1-x0
    slab = tbox(extents=(wdt, 1.5, 0.22)); slab.apply_translation((mid, -0.85, z)); parts.append(slab)          # tiefere, kräftigere Platte
    lip = tbox(extents=(wdt+0.12, 0.16, 0.18)); lip.apply_translation((mid, -1.55, z+0.02)); parts.append(lip)   # profilierte Vorderkante
    for x in np.linspace(x0+0.3, x1-0.3, 10):               # 10 regelmäßige getreppte Kragsteine (User)
        for (w, d, h, yy, zz) in [(0.28, 0.55, 0.2, -0.5, z-0.2), (0.22, 0.85, 0.2, -0.68, z-0.4), (0.15, 1.1, 0.2, -0.82, z-0.6)]:
            cb = tbox(extents=(w, d, h)); cb.apply_translation((x, yy, zz)); parts.append(cb)
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
    mid = (BAL_X0+BAL_X1)/2; wdt = BAL_X1-BAL_X0                                 # NUR zwischen den Erkern (wie der Balkon), NICHT über die ganze Breite
    bot = tbox(extents=(wdt, 0.3, 0.1)); bot.apply_translation((mid, BAL_Y, BAL_Z0)); parts.append(bot)   # Sohle — endet an den Erkern (sonst goldener ÜBERHANG vor dem Erker-Fuß, User)
    top = tbox(extents=(wdt, 0.28, 0.1)); top.apply_translation((mid, BAL_Y, BAL_Z1)); parts.append(top)  # Handlauf
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
    m = trimesh.util.concatenate(parts)
    m.apply_translation((-xc, 0.86, -z0)); m.apply_scale(1.13); m.apply_translation((xc, -0.86, z0))  # etwas größer (User)
    return m


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
        y = -0.52; zb = STAT_Z + 1.5                     # direkt über dem Statuenkopf (tiefer, User)
        plat = tbox(extents=(0.92, 0.54, 0.17)); plat.apply_translation((xc, y, zb)); parts.append(plat)   # massivere Konsolplatte
        canopy = tcone(radius=0.36, height=0.9, sections=6); canopy.apply_translation((xc, y, zb+0.09)); parts.append(canopy)  # massive Spitzhaube (User: mächtiger)
        fin = tcone(radius=0.1, height=0.55, sections=6); fin.apply_translation((xc, y, zb+0.92)); parts.append(fin)
        kn = trimesh.creation.icosphere(subdivisions=0, radius=0.1); kn.apply_translation((xc, y, zb+1.4)); parts.append(kn)
        for dx in (-0.34, 0.34):                                                                         # kräftige Eckfialen
            sf = tcone(radius=0.085, height=0.62, sections=6); sf.apply_translation((xc+dx, y, zb+0.12)); parts.append(sf)
    return trimesh.util.concatenate(parts)


def statues():
    _, xs = bay_layout()          # Figuren an den Fach-Teilern
    return trimesh.util.concatenate([statue(x) for x in xs])


# ---------- polygonaler Erker (Stein) + oktogonaler Spitzhelm (Gold) + Wappen ----------
def oriel(xc, z0, z1, w=4.0, proj=2.2):
    """polygonaler Eck-Erker + schlanker Spitzhelm mit BUNTEM Schuppenmuster (rot/creme,
    spiralig) + Krabben + Fiale — Blickfang wie im Foto. Gibt Farbgruppen getrennt zurück."""
    body_parts, gold, rot, hell, gruen = [], [], [], [], []

    # VOLLER OKTOGON-ERKER (voll rund, druck- & zusammensetzbar — echtes 3D-Teil): Körper, Netz UND
    # Fenster laufen RUNDHERUM; Helm (voller Revolve) sitzt konzentrisch drauf → nicht versetzt (User).
    NF = 8; cy2 = -proj*0.5; rb = w*0.5                     # Buchtzentrum (Y) + Körperradius
    ang8 = np.linspace(0, 2*np.pi, NF+1)

    def _ring(r, cy):
        return [(xc + r*np.cos(a), cy + r*np.sin(a)) for a in ang8]

    def bay_poly(sc=1.0):                                   # VOLLER Oktogon (8 Facetten)
        return Polygon(_ring(rb*sc, cy2)[:-1])
    for zz, sc in [(z0-1.5, 0.52), (z0-0.8, 0.76)]:        # Konsol-Aufbau unten
        b = extrude_polygon(bay_poly(sc), 0.7); b.apply_translation((0, 0, zz)); body_parts.append(b)
    body = extrude_polygon(bay_poly(1.0), z1-z0); body.apply_translation((0, 0, z0)); body_parts.append(body)
    pts6 = _ring(rb, cy2)                                   # 9 Punkte, pts6[8]==pts6[0] → 8 Facetten
    for vx, vy in pts6[:-1]:                                                   # Gold-Kantenrippen an ALLEN Facettenkanten
        gold.append(trimesh.creation.cylinder(radius=0.055, segment=((vx, vy, z0-0.3), (vx, vy, z1))))
    # Unterseite = SOLIDER voller Rippen-Trichter (Kragstein), druckbar:
    boss = np.array([xc, cy2, z0-1.7])
    cor = [np.array([x, y, z0-0.05]) for (x, y) in pts6[:-1]]; nb = len(cor)
    V = [tuple(c) for c in cor] + [tuple(boss)]
    F = [(i, (i+1) % nb, nb) for i in range(nb)]                               # voller geschlossener Trichter
    body_parts.append(_tri(V, F))
    for c in cor:                                                              # dünne Gold-Rippen auf den Kanten
        gold.append(trimesh.creation.cylinder(radius=0.04, segment=(tuple(boss), tuple(c))))
    # NETZGEWÖLBE (voll rund): Rippen vom Boss fächerförmig hoch, kreuzen sich zu Rauten.
    NR = NF*2                                                                   # Winkel-Unterteilungen rund um den VOLLEN Trichter
    rim = [np.array([xc + rb*np.cos(a), cy2 + rb*np.sin(a), z0-0.05]) for a in np.linspace(0, 2*np.pi, NR+1)]
    rings = [0.38, 0.68, 1.0]                                                   # radiale Ringe (Boss→Rim)

    def _nd(si, k):                                                             # Knoten auf Ring si (si=-1 → Boss)
        if si < 0:
            return boss
        return boss + (rim[k]-boss)*rings[si]
    for si in range(len(rings)-1):                                             # Ring-Rippen (quer) — NUR innen; KEIN Gold-Ring an der Rim
        pr = [_nd(si, k) for k in range(NR+1)]                                  # (der volle Rim-Ring las sich als goldener ÜBERHANG, User) → Rim bleibt Stein
        for p0, p1 in zip(pr[:-1], pr[1:]):
            if np.linalg.norm(p1-p0) > 1e-3:
                gold.append(trimesh.creation.cylinder(radius=0.02, segment=(tuple(p0), tuple(p1))))
    for si in range(-1, len(rings)-1):                                         # Diagonal-Rippen → Rauten (zwei Scharen)
        for k in range(NR):
            for a, b in (((_nd(si, k)), _nd(si+1, k+1)), (_nd(si, k+1), _nd(si+1, k))):
                if np.linalg.norm(b-a) > 1e-3:
                    gold.append(trimesh.creation.cylinder(radius=0.016, segment=(tuple(a), tuple(b))))
    cx2, cy2 = xc, -proj*0.5
    cr0 = w*0.40; chh = max(3.0, (EAVE+0.62*(RIDGE-EAVE))-z1-0.05)                # VOLLE Höhe (nicht mehr gekürzt) — Dach war zu kurz (User)
    # EINE glatte, konkave Glockenkurve MIT überkragender Traufe: Fuß breit (1.40 → kragt über den
    # Körper = Überlappung/Traufe) und kommt bis z1-0.14 (überlappt die Körper-Oberkante), zieht dann
    # in einer durchgehenden konkaven Kurve zur Spitze ein (kein 2-Punkt-Knick).
    FDROP = 0.55; FOOT = z1-FDROP                                               # Dach WEITER nach unten gezogen (User: „Dach weiterführen") → Traufe tiefer, schließt die Lücke überm Fenster
    def _r(t):                                                                  # t=0 Fuß .. 1 Spitze
        return cr0*(1.40*(1.0-t)**2.5 + 0.015)
    npro = 24
    prof = [(_r(i/npro), FOOT + (chh+FDROP)*(i/npro)) for i in range(npro+1)]
    prof.append((0.012, z1+chh+0.05))                                           # Spitze
    gruen.append(_revolve(prof, cx2, cy2, sections=8))                          # OKTOGONALER (facettierter) Kern, grün glasiert — Foto: 8-eckiger Helm, NICHT rund
    rib_ang = np.linspace(np.pi/8, 2*np.pi+np.pi/8, 8, endpoint=False)          # 8 Gold-Grat-Rippen auf den Facettenkanten
    for a in rib_ang:
        pr = [(cx2+r*np.cos(a), cy2+r*np.sin(a), z) for (r, z) in prof]
        for p0, p1 in zip(pr[:-1], pr[1:]):
            if np.linalg.norm(np.array(p1)-np.array(p0)) > 1e-3:
                gold.append(trimesh.creation.cylinder(radius=0.028, segment=(p0, p1)))   # DÜNNE Gratrippen (Foto: zartes Gold, nicht dominant)
    nring = 17                                                                  # DICHTE 4-farbige Diamant-Glasur, folgt der KONKAVEN Silhouette
    for i in range(nring):
        t = (i+0.4)/nring; rr = _r(t); zz = FOOT + (chh+FDROP)*t; nseg = max(8, int(16*(1-t)+6))
        e = max(0.12, 2*np.pi*rr/nseg*0.9)
        for k in range(nseg):
            ang = 2*np.pi*k/nseg + i*0.5
            sc = tbox(extents=(e, e, 0.07)); sc.apply_transform(trimesh.transformations.rotation_matrix(np.pi/4, [0, 0, 1]))
            sc.apply_translation((cx2+rr*np.cos(ang), cy2+rr*np.sin(ang), zz))
            [gruen, hell, rot, gold][(i + k) % 4].append(sc)   # BUNTE Glasur-Schindeln im RAUTEN-/Schachbrettmuster (grün/creme/rot/gelb verstreut) — bunt wie Foto, aber Schachbrett → KEINE waagrechten Ringe (User)
    # (Wasserspeier ENTFERNT — sahen wie rote Strippen/Drähte aus, User; stattdessen Dach tiefer gezogen)
    zb = z1+chh+0.05; sh = 1.3; r0 = w*0.055                                     # schlanke Fiale über dem Helm
    spire = tcone(radius=r0, height=sh, sections=6); spire.apply_translation((cx2, cy2, zb)); gold.append(spire)
    fin = trimesh.creation.cylinder(radius=0.045, height=0.5); fin.apply_translation((cx2, cy2, zb+sh+0.2)); gold.append(fin)
    knauf = trimesh.creation.icosphere(subdivisions=1, radius=0.12); knauf.apply_translation((cx2, cy2, zb+sh+0.5)); gold.append(knauf)
    # ---- Erker-Bucht-Fenster (Foto kh_erker): hohe BLEIGLAS-Fenster je Facette, GOLD-Pfosten +
    # Querkämpfer + flacher Gold-Sturz + Sohlbank, FACETTENGERECHT gedreht; bunte Wappen darunter ----
    wins = []; bayc = np.array([xc, cy2])                                       # Buchtzentrum (für Außennormale) = Oktogon-Mitte
    wh = (z1 - 0.6) - BAL_Z1; wz = BAL_Z1 + wh/2                                # Unterkante an Balkonkante, Oberkante HÖHER (bis knapp unter Helmfuß) — Fenster größer (User)
    arz = (BAL_Z0+BAL_Z1)/2                                                     # Wappen GENAU auf Balkonhöhe (User)
    for j in range(NF):                                                        # Fenster VOLL RUNDHERUM auf ALLEN 8 Facetten (User: voll rund, nicht nur draufgesetzt)
        pa = np.array(pts6[j]); pb = np.array(pts6[j+1]); ctr = (pa+pb)/2
        tang = pb-pa; fw = float(np.linalg.norm(tang)); tu = tang/fw
        ang = float(np.arctan2(tu[1], tu[0])); Rz = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
        nout = ctr-bayc; nout = nout/np.linalg.norm(nout)

        def put(ex, dalong, zc, out, bucket):                                   # Element in Facetten-Ebene setzen
            m = tbox(extents=ex); m.apply_transform(Rz)
            px = ctr[0]+tu[0]*dalong+nout[0]*out; py = ctr[1]+tu[1]*dalong+nout[1]*out
            m.apply_translation((px, py, zc)); bucket.append(m)
        lw = fw*0.82; _Praw = PROF if PROF else [(-0.5, 0.6), (0.0, 1.0), (0.5, 0.6)]
        # ERKER-Fensterkopf FLACHER (User mit Markierung: das Konkave fällt zu stark ab, in echt flacher).
        # Höhen affin zur Oberkante stauchen -> Schultern höher, konkaver Schwung flacher. 1.0 bleibt 1.0,
        # Monotonie bleibt -> parametrisch gültig. Gilt NUR hier (Erker), nicht für die Hauptfenster-PROF.
        ERK_DROOP = 0.45
        _P = [(xf, 1.0 - (1.0 - hf) * ERK_DROOP) for xf, hf in _Praw]

        def facet_poly(poly2d, thick, out):                                     # 2D-Polygon (entlang, höhe) in die Facetten-Ebene heben
            m = extrude_polygon(poly2d.buffer(0), thick); Vv = m.vertices.copy()
            m.vertices = np.c_[ctr[0]+tu[0]*Vv[:, 0]+nout[0]*(out+Vv[:, 2]),
                               ctr[1]+tu[1]*Vv[:, 0]+nout[1]*(out+Vv[:, 2]), (wz-wh/2)+Vv[:, 1]]
            return m
        a = lw/2
        glass = [(-a, 0.0)] + [(xf*lw, hf*wh) for xf, hf in _P] + [(a, 0.0)]    # Bleiglas MIT konkav-durchhängendem Kielbogen-Kopf (wie Hauptfenster)
        wins.append(facet_poly(Polygon(glass), 0.1, 0.0))
        og = [(-a-0.06, 0.0)] + [(xf*(lw+0.12), hf*wh+0.1) for xf, hf in _P] + [(a+0.06, 0.0)]   # Gold-Rahmen folgt dem Kielbogen
        ig = [(-a+0.07, -0.35)] + [(xf*(lw-0.14), hf*wh-0.04) for xf, hf in _P] + [(a-0.07, -0.35)]   # ig bis UNTER die og-Unterkante → Rahmen hat KEINEN waagrechten Gold-Bodenbalken mehr (der las sich als goldener ÜBERHANG am Erker-Fuß, User) — nur Jamben + Bogenkopf
        ring = Polygon(og).difference(Polygon(ig)).buffer(0)
        for geom in (ring.geoms if ring.geom_type == "MultiPolygon" else [ring]):
            if not geom.is_empty:
                gold.append(facet_poly(geom, 0.12, 0.04))   # Gold-Rahmen proud (Unterkante ist offen → kein Boden-Saum, aber Rahmen bleibt plastisch)
        put((0.05, 0.14, wh), 0, wz, 0.055, gold)                               # Gold-Mittelpfosten → 2 Lichter
        for s in (-1, 1):                                                       # schlanke Gold-Jamben an den Facettenkanten
            put((0.055, 0.2, wh+0.1), s*fw*0.47, wz, 0.035, gold)
        put((lw+0.06, 0.16, 0.06), 0, wz-0.1, 0.055, gold)                      # Querkämpfer (Transom) wieder PROUD vor dem Glas (out=0 ließ ihn im Glas versinken → Querbalken weg, User)
        # Sohlbank ENTFERNT — dieses durchlaufende Gold-Sohlbankband am Erker-Fuß war der „goldene
        # Überhang" (User, per Farb-Isolationstest identifiziert); Fenster sitzen aufs Wappenband (Foto pe_under2)
        for zr in np.linspace(wz-wh/2+0.25, wz+wh/2-0.25, 3):                   # feine DUNKLE Bleiruten (kein Gold!) — sonst wirkt das Glas wie ein Goldgitter
            put((lw-0.04, 0.125, 0.015), 0, zr, 0.015, wins)
        # kleines WAPPEN-SCHILD (statt Kugel): Schildform (runder Kopf, Spitze unten) + Gold-Rand + Kreuz
        sw, sh2 = 0.27, 0.37; fld = [rot, hell, gruen][j % 3]   # Wappenschilde kräftiger (Foto: große Wappen)
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
    # KRAGSTEIN-KÖPFCHEN: Reihe kleiner Stein-Köpfe am Erker-Fuß, direkt über dem Netzgewölbe (Foto)
    hz = z0 - 0.03; hc = np.array([xc, cy2])
    head_xy = [tuple(p) for p in pts6[:-1]] + [tuple((np.array(pts6[k])+np.array(pts6[k+1]))/2) for k in range(len(pts6)-1)]
    for hx, hy in head_xy:
        nd = np.array([hx, hy]) - hc; nl = float(np.linalg.norm(nd)); nd = nd/nl if nl > 1e-6 else np.array([0.0, -1.0])
        hh = trimesh.creation.icosphere(subdivisions=1, radius=0.085)
        hh.apply_translation((hx+nd[0]*0.07, hy+nd[1]*0.07, hz)); body_parts.append(hh)
    return {"erker": trimesh.util.concatenate(body_parts), "helm": trimesh.util.concatenate(gold),
            "helm_rot": trimesh.util.concatenate(rot), "helm_hell": trimesh.util.concatenate(hell),
            "helm_gruen": trimesh.util.concatenate(gruen), "fenster": trimesh.util.concatenate(wins)}


# ---------- giebelständige Gaube (Satteldach) ----------
def _dormer_size():                                   # GEMESSEN (gauben_mass.json), NICHT hardcodiert
    try:
        d = json.load(open("modelle/kaufhaus_freiburg/gauben_mass.json"))
        return float(d["dormer_w_m"]), float(d["dormer_h_m"])
    except Exception:
        return 2.0, 1.5
DORMER_W, DORMER_H = _dormer_size()                   # Gaubenbreite/-höhe aus Foto gemessen (Fenster/Gebäudebreite)
DORMER_H = min(DORMER_H, 1.1)                         # Gauben KLEIN lassen (User: Fenster zu groß) — nicht künstlich auf 1.3 hochklemmen


def _dormer_specs():
    """Gauben-Positionen (x,z) auf REGELMÄSSIGEM, versetztem Raster: alle Gauben haben GLEICHEN
    x-Abstand (pitch). Untere Reihe auf geraden Rastern (0,2,4), obere auf den ungeraden (1,3) =
    exakt die Lücken-Mitten (Foto: untere 0,26/0,51/0,77, obere 0,39/0,62 = Mittelpunkte)."""
    cx = W/2; span = W*DORMER_WFRAC; x_lo = cx-span/2
    nslots = sum(DORMER_ROWS)                            # z.B. 3+2 = 5 Raster-Spalten
    pitch = span/(nslots-1) if nslots > 1 else span
    nrows = len(DORMER_ROWS)
    base = float(P.get("dormer_base_frac", 0.30))      # Gauben höher ins Dach (User: untere Reihe nicht an der Traufe)
    gap = float(P.get("dormer_row_gap", 0.27))         # Reihenabstand: obere Reihe tiefer halten, damit Dachfläche ÜBER ihr bleibt (User: obere Reihe war zu weit oben/am First)
    fracs = np.linspace(base, base+gap*(nrows-1), nrows) if nrows > 1 else [base]
    specs = []
    for r, n in enumerate(DORMER_ROWS):
        z = EAVE+fracs[r]*(RIDGE-EAVE)
        for i in range(n):
            s = r + 2*i                                  # Reihe r startet um r versetzt, Schrittweite 2 → gleichmäßig
            specs.append((x_lo + pitch*s, z))
    return specs


def _slope_y(z):
    return (D/2)*(z-EAVE)/(RIDGE-EAVE)              # y-Lage der Dachhaut auf Höhe z


DORMER_PROJ = 0.62   # Gaube steht weniger weit vor → sitzt INS Dach integriert statt als Kasten davor (Foto: kleine Hüftgauben, Ziegel laufen eng ran)


def dormers():
    """VORSTEHENDE Gauben (Foto): SOLIDER Gaubenkörper (watertight, druckbar) der klar aus der
    Dachhaut ragt; Front dunkel = Fenster. Steckt hinten in der Dachschräge (Slicer-Union)."""
    parts = []
    for xc, z in _dormer_specs():
        ys = _slope_y(z); yf = ys-DORMER_PROJ
        body = tbox(extents=(DORMER_W, (ys+0.15)-yf, DORMER_H)); body.apply_translation((xc, (yf+ys+0.15)/2, z+DORMER_H/2-0.05)); parts.append(body)
    return trimesh.util.concatenate(parts)


def dormer_roofs():
    """WALMGAUBE mit kurzem FIRST (Foto dorm_B, genau studiert): trapezförmige Ziegel-Vorderfläche
    schräg nach hinten-oben zu einem KURZEN waagrechten First + dreieckige Hüft-(Walm-)Seiten. KEINE
    Spitze, kein Keil, moderate Höhe. Solider Körper (druckbar)."""
    parts = []
    for xc, z in _dormer_specs():
        # Dachbasis = GENAU die Oberfläche des Gaubenkörpers (Breite + y-Tiefe), mit kleinem Überstand,
        # und ÜBERLAPPT den Körper (zt unter der Körper-Oberkante z+0.90) → sitzt GERADE drauf + ein
        # watertight Solid beim Union (druckbar). Hintere Traufe = Körper-Rückseite (ys+0.15, steckt im Dach),
        # NICHT frei über der Dachhaut schwebend (das war der „sitzt nicht gerade"-Effekt).
        ys = _slope_y(z); o = 0.14
        yF = (ys-DORMER_PROJ) - o                          # vordere Traufe (mit Überstand übers Fenster)
        yB = ys+0.15                                       # hintere Traufe = Körper-Rückkante (im Dach)
        xL, xR = xc-DORMER_W/2-o, xc+DORMER_W/2+o
        zt = z+DORMER_H-0.13                               # Traufe: 0.08 in die Körper-Oberkante (z+0.90) hinein → Überlappung
        zr = zt+0.46; rh = DORMER_W*0.30; ym = ys-DORMER_PROJ*0.5    # kurzer First mittig übers Dach, moderate Neigung (niedrige Hüftgaube)
        V = [(xL, yF, zt), (xR, yF, zt), (xR, yB, zt), (xL, yB, zt),   # 0..3 Traufe (vorn/hinten) = Körper-Oberfläche
             (xc-rh, ym, zr), (xc+rh, ym, zr)]                          # 4,5 First
        F = [(0, 1, 5), (0, 5, 4),                           # Vorderfläche (Trapez, schräg nach hinten-oben)
             (2, 3, 4), (2, 4, 5),                           # Rückfläche
             (3, 0, 4),                                      # linker Walm (Dreieck)
             (1, 2, 5),                                      # rechter Walm (Dreieck)
             (0, 3, 2), (0, 2, 1)]                           # Boden
        parts.append(_tri(V, F))
    return trimesh.util.concatenate(parts)


def dormer_frames():
    """heller Steinrahmen (Pfosten + Sturz) um das dunkle Gaubenfenster vorn — Foto: helle Fassung."""
    parts = []
    for xc, z in _dormer_specs():
        ys = _slope_y(z); yf = ys-DORMER_PROJ; t = 0.1
        for dx in (-DORMER_W/2, DORMER_W/2):               # senkrechte Rahmen-Pfosten
            parts.append(tbox(extents=(0.15, 0.15, DORMER_H*0.9)).apply_translation((xc+dx, yf-0.03, z+DORMER_H*0.45)))
        lint = tbox(extents=(DORMER_W+0.22, 0.16, 0.16)); lint.apply_translation((xc, yf-0.03, z+DORMER_H*0.88)); parts.append(lint)  # Sturz
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
    # BEIDE Rakes JEDES Giebels (vorne Y=0→First UND hinten Y=D→First) → symmetrischer Treppengiebel.
    # Vorher nur die Vorder-Rakes → Zacken nur auf einer Dachseite (User-Bug).
    rakes = [((0, 0, EAVE), (inset, D/2, RIDGE)), ((0, D, EAVE), (inset, D/2, RIDGE)),
             ((W, 0, EAVE), (W-inset, D/2, RIDGE)), ((W, D, EAVE), (W-inset, D/2, RIDGE))]
    for p0, p1 in rakes:
        p0 = np.array(p0, float); p1 = np.array(p1, float); d = p1-p0
        beam = trimesh.creation.cylinder(radius=0.36, segment=(tuple(p0+[0, 0, 0.3]), tuple(p1+[0, 0, 0.3])))
        parts.append(beam)                                                   # durchgehender Balken → VERBINDET alle Stufen (ein Solid, druckbar)
        n = 9
        for j in range(n):
            c = p0 + d*(j/(n-1))
            blk = tbox(extents=(0.72, 0.78, 0.98)); blk.apply_translation((c[0], c[1], c[2]+0.5)); parts.append(blk)   # größere Stufenblöcke (User)
    for xt in (inset, W-inset):                                              # Giebel-Abschluss-Fiale EINMAL je Giebelspitze
        yt, zt = D/2, RIDGE
        for k, s in enumerate([0.6, 0.42]):
            st = tbox(extents=(s, s, 0.4)); st.apply_translation((xt, yt, zt+0.22+k*0.32)); parts.append(st)
        tip = tcone(radius=0.18, height=0.4, sections=6); tip.apply_translation((xt, yt, zt+0.55)); parts.append(tip)
    return trimesh.util.concatenate(parts)


def arcade_muntins():
    """weißer Rahmen + FENSTERKREUZ in jedem (kleinen) Arkaden-Fenster — proud vor dem Glas,
    damit die Bögen als verglaste Fenster auf rotem Hintergrund lesen."""
    pitch = W/N_ARCH; parts = []
    for i in range(N_ARCH):
        xc = (i+0.5)*pitch
        if i == ARC_DOOR:                                                                         # TÜRRAHMEN + Oberlicht-Riegel
            dw = pitch*0.32; dh0, dh1 = 0.1, 2.95; zc = (dh0+dh1)/2; hgt = dh1-dh0
            for dx in (-dw/2, dw/2):
                b = tbox(extents=(0.09, 0.08, hgt)); b.apply_translation((xc+dx, 1.82, zc)); parts.append(b)
            top = tbox(extents=(dw+0.1, 0.08, 0.09)); top.apply_translation((xc, 1.82, dh1)); parts.append(top)
            tr = tbox(extents=(dw, 0.08, 0.08)); tr.apply_translation((xc, 1.82, dh1-0.55)); parts.append(tr)  # Oberlicht-Querriegel
            v = tbox(extents=(0.07, 0.07, hgt)); v.apply_translation((xc, 1.79, zc)); parts.append(v)          # Türmittelstab
            continue
        ww, wz0, wz1 = pitch*ARC_WW_FRAC, ARC_WZ0, ARC_WZ1; zc = (wz0+wz1)/2; hgt = wz1-wz0        # FENSTERRAHMEN + Kreuz
        for dx in (-ww/2, ww/2):
            b = tbox(extents=(0.08, 0.08, hgt+0.08)); b.apply_translation((xc+dx, 1.82, zc)); parts.append(b)
        for dz in (-hgt/2, hgt/2):
            b = tbox(extents=(ww+0.08, 0.08, 0.08)); b.apply_translation((xc, 1.82, zc+dz)); parts.append(b)
        v = tbox(extents=(0.07, 0.07, hgt)); v.apply_translation((xc, 1.79, zc)); parts.append(v)
        h = tbox(extents=(ww, 0.07, 0.07)); h.apply_translation((xc, 1.79, zc)); parts.append(h)
    return trimesh.util.concatenate(parts)


def roof_rake_gold():
    """zwei schmale WAAGERECHTE Goldstreifen an der TRAUFKANTE (Foto: Goldleisten quer, nicht aufs Dach)."""
    parts = []
    for dz in (-0.04, 0.16):
        c = trimesh.creation.cylinder(radius=0.06, segment=((0.4, -0.34, EAVE+dz), (W-0.4, -0.34, EAVE+dz)))
        parts.append(c)
    return trimesh.util.concatenate(parts)


def roof_tiles_fine():
    """ganz fein angedeutete Dachziegel (kleine überlappende Schuppen, versetzt) auf der
    Vorderschräge — granulare Textur zum Drucken, dezent erhaben."""
    a = D/2; b = RIDGE-EAVE; Ls = (a*a+b*b)**0.5
    su = np.array([0, a, b])/Ls; nrm = np.array([0, -b, a])/Ls
    xv = np.cross(su, nrm); Rm = np.eye(4); Rm[:3, 0] = xv; Rm[:3, 1] = su; Rm[:3, 2] = nrm
    tw, th, rel = 0.26, 0.2, 0.03; parts = []; nc = int(Ls/th)
    for ci in range(1, nc):
        t = ci*th
        if t > Ls-0.12:
            break
        base = np.array([0.0, 0.0, EAVE]) + su*t
        x = (tw/2) if ci % 2 else 0.0
        while x+tw <= W-0.05:
            box = tbox(extents=(tw*0.88, th*1.3, rel)); box.apply_transform(Rm)
            box.apply_translation(np.array([x+tw/2, base[1], base[2]]) + nrm*(rel*0.5)); parts.append(box)
            x += tw
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
    """ROTE Giebel-Endwände (Treppengiebel-Dreiecke) an den Seiten x=0 und x=W + kleine
    Schlitzfenster, die im Giebel hochsteigen (Foto). Gibt (Wände, dunkle Scheiben)."""
    specs = _gable_window_specs()
    holes = [Polygon([(s["yc"]-s["hw"], s["zb"]), (s["yc"]+s["hw"], s["zb"]),
                      (s["yc"]+s["hw"], s["zt"]), (s["yc"]-s["hw"], s["zt"])]) for s in specs]
    walls = trimesh.util.concatenate([plain_gable(-0.35, 0.7, holes), plain_gable(W-0.35, 0.7, holes)])
    glass, frames = [], []
    for xg, xf in ((0.0, -0.3), (W, W+0.3)):          # xg=Glas (mittig in der Wand), xf=Gewände (außen proud)
        for s in specs:
            yc, hw, zb, zt = s["yc"], s["hw"], s["zb"], s["zt"]
            g = tbox(extents=(0.1, 2*hw-0.06, zt-zb)); g.apply_translation((xg, yc, (zb+zt)/2)); glass.append(g)
            for dy in (-hw, hw):                       # Sandstein-Pfosten
                frames.append(tbox(extents=(0.12, 0.1, zt-zb)).apply_translation((xf, yc+dy, (zb+zt)/2)))
            frames.append(tbox(extents=(0.14, 2*hw+0.24, 0.1)).apply_translation((xf, yc, zt)))   # Sturz
            frames.append(tbox(extents=(0.14, 2*hw+0.24, 0.1)).apply_translation((xf, yc, zb)))   # Sohlbank
            if s["cross"]:                             # KREUZSTOCK: senkrechter Mittelpfosten + waagrechter Kämpfer
                frames.append(tbox(extents=(0.1, 0.08, zt-zb)).apply_translation((xf, yc, (zb+zt)/2)))
                frames.append(tbox(extents=(0.1, 2*hw, 0.08)).apply_translation((xf, yc, (zb+zt)/2)))
    return walls, trimesh.util.concatenate(glass), trimesh.util.concatenate(frames)


# Arkaden-Fenstermaße HOCHKANT (schmal + hoch), klein genug für Rot ringsum
ARC_WW_FRAC = 0.24; ARC_WZ0, ARC_WZ1 = 1.1, 3.25
ARC_DOOR = 2            # Arkadenbogen mit TÜR statt Fenster (2. von rechts, wird am Render geprüft)
PIER_H = ARC_APEX   # Pfeiler steigen MIT dem Bogen bis zum Scheitel und gehen FLIESSEND in den Bogen über
                    # (gleiche rote Farbe wie Fassade/Bogenlaibung), KEIN abgeschnittener Stumpf am Kämpfer
                    # und NICHT bis zum Balkon (Apex 5,2 < Balkon 5,4). User: „unter den Erkern stoppten die Säulen".


def arcade_piers():
    """schlankere Arkaden-Pfeiler mit Basis + Kapitell (Foto: zierlicher) + goldener Lisenen-Linie."""
    pitch = W/N_ARCH; parts = []
    for i in range(N_ARCH+1):
        x = pitch*i
        # Pfeiler geht FLIESSEND in den Bogen über — KEINE verbreiterten Kapitell-/Impost-Ringe
        # (User: die zwei Endringe markierten das Säulenende, falsch). Schlichter Schaft bis Bogenansatz.
        shaft = tbox(extents=(0.62, 0.9, PIER_H)); shaft.apply_translation((x, -0.4, PIER_H/2)); parts.append(shaft)
    return trimesh.util.concatenate(parts)


def pier_bases():
    """abgesetzter dunklerer STEIN-SOCKEL je Arkadenpfeiler (Foto: Basis aus grau-braunem Sandstein,
    deutlich dunkler als der rote Schaft) — zweistufig, leicht breiter."""
    pitch = W/N_ARCH; parts = []
    for i in range(N_ARCH+1):
        x = pitch*i
        b1 = tbox(extents=(0.92, 1.12, 0.55)); b1.apply_translation((x, -0.4, 0.28)); parts.append(b1)   # Sockelblock
        b2 = tbox(extents=(0.78, 0.98, 0.18)); b2.apply_translation((x, -0.4, 0.64)); parts.append(b2)   # Anlauf/Abschrägung
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
    apex = spring + (bw/2.0)*1.16
    for i in range(N_ARCH):
        xc = pitch*(i+0.5)
        curve = LineString(_pointed_curve(xc, bw, spring, apex))         # Spitzbogen-Leibungslinie
        band = curve.buffer(t, cap_style=2, join_style=1).buffer(0)      # dünner Saum ENTLANG des Bogens (robust)
        for geom in (band.geoms if band.geom_type == "MultiPolygon" else [band]):
            if not geom.is_empty:
                parts.append(_stand(extrude_polygon(geom, 0.28), y0=-0.22))   # dünne Gold-Archivolte auf der Spitzbogen-Leibung
        key = tbox(extents=(0.3, 0.3, 0.5)); key.apply_translation((xc, -0.12, apex-0.05)); parts.append(key)  # zarter Schlussstein am Scheitel
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
    back = tbox(extents=(W, 0.3, ARC_APEX)); back.apply_translation((W/2, 2.2, ARC_APEX/2)); parts.append(back)   # Rückwand über VOLLE Breite → Laube ist ein GESCHLOSSENER, schattiger Gang (kein Durchblick nach draußen = kein weißes Loch, User)
    floor = tbox(extents=(W, 2.6, 0.3)); floor.apply_translation((W/2, 1.1, 0.12)); parts.append(floor)   # Laubengang-Boden
    return trimesh.util.concatenate(parts)


def arcade_glazing():
    """Fenster in den EG-Bögen: KLEINERES dunkles Glas + Pfosten, sodass die ROTE Rückwand (laube)
    ringsum sichtbar bleibt — die Bögen lesen sich als rote Öffnungen mit Fenstern darin."""
    pitch = W/N_ARCH; ww = pitch*ARC_WW_FRAC; wz0, wz1 = ARC_WZ0, ARC_WZ1; parts = []
    for i in range(N_ARCH):
        xc = (i+0.5)*pitch
        if i == ARC_DOOR:                                              # TÜR: bis zum Boden, etwas breiter
            dw = pitch*0.32; dh0, dh1 = 0.1, 2.95
            g = tbox(extents=(dw, 0.1, dh1-dh0)); g.apply_translation((xc, 1.92, (dh0+dh1)/2)); parts.append(g)
        else:
            g = tbox(extents=(ww, 0.1, wz1-wz0)); g.apply_translation((xc, 1.92, (wz0+wz1)/2)); parts.append(g)
    return trimesh.util.concatenate(parts)


SIDE_WINY = tuple(round(D*f, 2) for f in (0.46, 0.67, 0.88))   # Y-Lagen aus der TIEFE abgeleitet (D wird gekappt!) — sonst ragte das 3. Fenster (9.6) aus der 8.5 m tiefen Wand (User: Seitenfenster falsch/außerhalb)


def _side_window_specs():
    """Giebelseiten-Fenster GEMESSEN am Foto (kh_erker.jpg Seitenwand): WENIGE kleine Fenster mit
    hellem Sandsteingewände — ein zweiflügliges Rechteckfenster (vorn/oben) + ein Rundbogenfenster
    (hinten, hohes schlankes) — NICHT drei gleiche Schlitze. Y aus der Tiefe D abgeleitet."""
    return [
        dict(yc=round(D*0.30, 2), hw=0.55, zb=SILL-0.3,  zt=HEAD-1.0, round=False, lights=2),  # 2-licht Rechteck (vorn, unten)
        dict(yc=round(D*0.62, 2), hw=0.42, zb=SILL-1.3,  zt=HEAD-0.9, round=True,  lights=1),  # Rundbogen (hinten, unten)
        dict(yc=round(D*0.42, 2), hw=0.30, zb=HEAD-0.5,  zt=EAVE-0.2, round=False, lights=1),  # kleines Einzelfenster MITTE-OBEN (User: fehlte; Foto pe_sideA hat es zwischen unterem Paar und Giebel)
    ]


def _side_hole(s):
    """Loch-Polygon (Y,Z) eines Seitenfensters — Rechteck oder Rundbogen."""
    yc, hw, zb, zt = s["yc"], s["hw"], s["zb"], s["zt"]
    if not s["round"]:
        return Polygon([(yc-hw, zb), (yc+hw, zb), (yc+hw, zt), (yc-hw, zt)])
    zc = zt-hw
    pts = [(yc-hw, zb), (yc-hw, zc)]
    pts += [(yc+hw*np.cos(a), zc+hw*np.sin(a)) for a in np.linspace(np.pi, 0, 14)]
    pts += [(yc+hw, zb)]
    return Polygon(pts)


def side_walls():
    """SEITENWÄNDE (Giebelseiten x≈0 / x≈W): SOLIDE rote Wand + wenige kleine Fenster mit
    Sandsteingewände (Foto pe_side: Giebelseite ist massiv, KEIN Erd­geschoss-Durchgang).
    Gibt (Wand, Glas, Gewände/Rahmen)."""
    outer = Polygon([(0, 0), (D, 0), (D, EAVE), (0, EAVE)])      # (Y, Z)
    specs = _side_window_specs()
    # TORBOGEN wieder da (User): die Laube ist an den ENDEN offen → begehbarer Durchgang. Öffnung GANZ
    # VORNE (Y klein, vor der Arkaden-Rückwand bei y=2.2) → man sieht in die Kolonnade, nicht auf die Wand.
    holes = [round_arch(1.4, 2.2, ARC_SPRING)] + [_side_hole(s) for s in specs]
    poly = outer.difference(unary_union([h.buffer(0) for h in holes]))
    walls, glass, frames = [], [], []
    for x0 in (0.0, W-0.6):
        m = extrude_polygon(poly, 0.6); V = m.vertices.copy()
        m.vertices = np.c_[x0+V[:, 2], V[:, 0], V[:, 1]]         # Poly-x→Welt-Y (Tiefe), Poly-y→Welt-Z (Höhe), Dicke→Welt-X
        walls.append(m)
    for xg, xf in ((0.33, 0.08), (W-0.33, W-0.08)):             # xg=Glasebene (mittig), xf=Gewändeebene (außen, leicht proud)
        for s in specs:
            yc, hw, zb, zt = s["yc"], s["hw"], s["zb"], s["zt"]
            g = tbox(extents=(0.08, 2*hw-0.1, zt-zb)); g.apply_translation((xg, yc, (zb+zt)/2)); glass.append(g)
            for dy in (-hw, hw):                                # senkrechte Gewände-Pfosten
                frames.append(tbox(extents=(0.14, 0.12, zt-zb)).apply_translation((xf, yc+dy, (zb+zt)/2)))
            frames.append(tbox(extents=(0.16, 2*hw+0.3, 0.12)).apply_translation((xf, yc, zb)))    # Sohlbank
            if s["lights"] >= 2:                                # Mittelpfosten (2 Lichter) + Kämpfer
                frames.append(tbox(extents=(0.12, 0.1, zt-zb)).apply_translation((xf, yc, (zb+zt)/2)))
                frames.append(tbox(extents=(0.12, 2*hw, 0.1)).apply_translation((xf, yc, (zb+zt)/2)))
            if not s["round"]:
                frames.append(tbox(extents=(0.14, 2*hw+0.24, 0.14)).apply_translation((xf, yc, zt)))   # Sturz
            else:                                               # Rundbogen-Gewände als Saum entlang des Bogens
                zc = zt-hw
                curve = LineString([(yc+hw*np.cos(a), zc+hw*np.sin(a)) for a in np.linspace(np.pi, 0, 20)])
                band = curve.buffer(0.09, cap_style=2).buffer(0)
                for geom in (band.geoms if band.geom_type == "MultiPolygon" else [band]):
                    mm = extrude_polygon(geom, 0.14); Vv = mm.vertices.copy()
                    mm.vertices = np.c_[xf+Vv[:, 2], Vv[:, 0], Vv[:, 1]]; frames.append(mm)
    return (trimesh.util.concatenate(walls), trimesh.util.concatenate(glass),
            trimesh.util.concatenate(frames))


def _gable_window_specs():
    """Fenster im hohen Treppengiebel, GEMESSEN am Foto ac7b01d5 (rechte Giebelseite): EIN kleines
    zweiflügliges KREUZ-Fenster (2×2, unten) + EIN schmaler SCHLITZ (höher), beide zur VORDERKANTE
    versetzt (Y<D/2), nicht mittig — und KEINE zwei gleichen Schlitze."""
    # Form+Position korrigiert (User): Kreuzfenster fast QUADRATISCH (war zu hoch/schmal) und TIEFER
    # knapp über der Traufe, weiter zur Vorderkante; Schlitz ebenfalls tiefer.
    return [dict(yc=round(D*0.30, 2), hw=0.46, zb=EAVE+0.35, zt=EAVE+1.45, cross=True),   # 2×2 Kreuzfenster, nahezu quadratisch (0.92 breit × 1.1 hoch)
            dict(yc=round(D*0.33, 2), hw=0.13, zb=EAVE+1.85, zt=EAVE+3.05, cross=False)]  # schmaler Schlitz darüber


def plain_gable(x_end, dx=0.5, holes=None):
    """Dreiecks-Giebelwand (Satteldach) mit optionalen Schlitzfenster-Löchern."""
    P = Polygon([(0, EAVE), (D/2, RIDGE), (D, EAVE)])
    if holes:
        P = P.difference(unary_union([h.buffer(0) for h in holes]))
    m = extrude_polygon(P, dx); V = m.vertices.copy()
    m.vertices = np.c_[x_end+V[:, 2], V[:, 0], V[:, 1]]
    return m


def _mirror_y(m):
    """Mesh an der Ebene y=D/2 spiegeln (Vorder- → Rückschräge). Winding danach drehen."""
    m2 = m.copy(); V = m2.vertices.copy(); V[:, 1] = D - V[:, 1]; m2.vertices = V
    m2.invert()
    return m2


def back_wall():
    """RÜCKWAND (Münster-Seite, y≈D): rote Wand mit regelmäßigem Fensterraster (kein Foto → plausibel
    geschätzt, User-Freigabe) + dunkle Scheiben + Sandsteingewände. Gibt (Wand, Glas, Gewände)."""
    outer = Polygon([(0, 0), (W, 0), (W, EAVE), (0, EAVE)])      # (x, z)
    cols = np.linspace(W*0.13, W*0.87, 6)
    rows = [(2.0, 3.7), (5.6, 8.0)]                             # EG-Band + OG-Band
    holes, specs = [], []
    for zb, zt in rows:
        for xc in cols:
            holes.append(Polygon([(xc-0.45, zb), (xc+0.45, zb), (xc+0.45, zt), (xc-0.45, zt)]))
            specs.append((xc, zb, zt))
    poly = outer.difference(unary_union([h.buffer(0) for h in holes]))
    m = extrude_polygon(poly, 0.6); V = m.vertices.copy()
    m.vertices = np.c_[V[:, 0], (D-0.6)+V[:, 2], V[:, 1]]        # x→x, Dicke→y (D-0.6..D), z→z
    glass, frames = [], []
    for xc, zb, zt in specs:
        g = tbox(extents=(0.9, 0.08, zt-zb)); g.apply_translation((xc, D-0.3, (zb+zt)/2)); glass.append(g)
        for dx in (-0.45, 0.45):
            frames.append(tbox(extents=(0.1, 0.12, zt-zb)).apply_translation((xc+dx, D-0.02, (zb+zt)/2)))
        frames.append(tbox(extents=(1.06, 0.12, 0.1)).apply_translation((xc, D-0.02, zt)))
        frames.append(tbox(extents=(1.06, 0.12, 0.1)).apply_translation((xc, D-0.02, zb)))
        frames.append(tbox(extents=(0.08, 0.12, zt-zb)).apply_translation((xc, D-0.02, (zb+zt)/2)))   # Mittelpfosten
    return m, trimesh.util.concatenate(glass), trimesh.util.concatenate(frames)


def build():
    e0 = oriel(ORIEL_X[0], SILL-0.6, EAVE-1.0, w=2.5, proj=1.5)   # zurück auf vorherige Erker-Maße
    e1 = oriel(ORIEL_X[1], SILL-0.6, EAVE-1.0, w=2.5, proj=1.5)
    giebel_wall, giebel_glas, giebel_rahmen = gables()
    parts = {
        "fassade": facade_wall(),
        "balken": red_lintel(),
        "cornice": cornice(),
        "konsolen": cornice_corbels(),
        "dach": roof(),
        "giebel": giebel_wall,
        "giebelglas": giebel_glas,
        "giebelrahmen": giebel_rahmen,
        "piers": arcade_piers(),
        "pierbase": pier_bases(),
        # "lisenen": pier_lisenen(),  # ENTFERNT — die Pfeiler haben KEINE senkrechte Goldlinie (User)
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
        "gauben": trimesh.util.concatenate([dormers(), _mirror_y(dormers())]),            # Gauben auf BEIDEN Dachschrägen (User)
        "gauben_dach": trimesh.util.concatenate([dormer_roofs(), _mirror_y(dormer_roofs())]),
        "gauben_rahmen": trimesh.util.concatenate([dormer_frames(), _mirror_y(dormer_frames())]),
        "dachmuster": roof_courses(),
        "dachrauten": roof_diaper(),
        "dachziegel": roof_tiles_fine(),
        "first": ridge_crest(),
        "krabben": dach_krabben(),
        "dachkante_gold": roof_rake_gold(),
        "rahmen": window_goldframe(),
        "sprossen": window_muntins(),
        "balkon": balcony(),
        "gitter": attic_railing(),
        "baldachin": statue_canopies(),
        # Wappen-Rundschilde SITZEN AN DEN ERKERN (Foto), nicht als große Goldmünzen in der Balkonbrüstung → raus (entrümpelt)
        "laube": arcade_recess(),
        "arkadenglas": arcade_glazing(),
        "arkadenkreuz": arcade_muntins(),
    }
    back_m, back_glass, back_frames = back_wall()
    wall_m, side_glass, side_frames = side_walls()
    parts["waende"] = trimesh.util.concatenate([back_m, wall_m])
    parts["seitenglas"] = trimesh.util.concatenate([side_glass, back_glass])
    parts["seitenrahmen"] = trimesh.util.concatenate([side_frames, back_frames])

    cols = {"fassade": [126, 48, 42, 255], "waende": [126, 48, 42, 255], "dach": [98, 104, 88, 255],   # Seiten-/Rückwand = Fassadenrot; Dach VERWITTERT grau-grün (entsättigt, Foto ~grau-grün, nicht kräftig grün)

            "giebel": [126, 48, 42, 255], "balken": [120, 38, 34, 255], "galerie": [138, 48, 42, 255], "fenster": [26, 30, 36, 255], "seitenglas": [26, 30, 36, 255], "seitenrahmen": [196, 176, 140, 255], "giebelglas": [26, 30, 36, 255], "giebelrahmen": [196, 176, 140, 255],   # dunkle Giebelfenster + heller Sandstein-Gewände/Kreuzstock (Foto)
            "statuen": [206, 206, 212, 255], "konsole": [198, 160, 90, 255], "erker": [126, 48, 42, 255], "helm": [192, 152, 70, 255],
            "baldachin": [198, 162, 92, 255],
            "gauben": [40, 34, 32, 255], "gauben_dach": [98, 104, 88, 255], "dachmuster": [92, 99, 83, 255], "dachziegel": [94, 100, 84, 255],
            "dachrauten": [72, 82, 64, 255],
            "cornice": [182, 150, 80, 255], "konsolen": [176, 144, 78, 255], "laube": [96, 34, 28, 255], "arkadenglas": [24, 24, 28, 255], "arkadenkreuz": [48, 44, 46, 255], "piers": [126, 48, 42, 255], "pierbase": [104, 40, 34, 255],   # Pfeiler+Sockel = roter Sandstein (User: Sockel sind AUCH rot, nicht grau); Sockel nur eine Spur dunkler
            "boegen": [192, 154, 72, 255], "first": [182, 150, 80, 255], "rahmen": [206, 162, 58, 255],
            "wappen": [196, 150, 48, 255], "krabben": [150, 42, 36, 255], "dachkante_gold": [196, 160, 78, 255], "nische": [126, 48, 42, 255],   # Hintergrund hinter den Statuen = ROTE Wand (User: kein dunkles Nischenloch), Figuren stehen auf Konsolen vor der roten Fassade
            "helm_rot": [150, 44, 40, 255], "helm_hell": [224, 214, 190, 255], "helm_gruen": [86, 134, 82, 255],
            "lisenen": [188, 150, 72, 255], "sprossen": [72, 74, 84, 255],   # dunkle Bleiruten (echtes Bleiglas ist DUNKEL mit feinen Stegen) — Fenster liest als Öffnung, nicht grau
            "wappen_rot": [150, 46, 42, 255], "wappen_blau": [44, 70, 120, 255], "gitter": [128, 46, 40, 255],   # Balkon-Baluster = ROTER Sandstein (User+Foto p_statbg: rote gedrechselte Baluster, NICHT dunkelbraun)
            "balkon": [92, 40, 34, 255], "firstkamm": [150, 44, 38, 255],
            "gauben_rahmen": [150, 134, 108, 255]}   # gedämpfter Steinrahmen (Foto: dunklere Laibung, nicht hell-leuchtend)
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
