#!/usr/bin/env python3
"""foto_luecken.py - WO MUSS ICH VOR ORT NOCH FOTOS MACHEN? (Nutzerwunsch 10.11.: "Ich stehe am Gebaeude und will sehen, wo ich noch Fotos machen muss.")

Ablauf (alles GPU, generisch fuer jedes Objekt):
  1. Flaeche  (--flaeche stl|netz|lod2|auto):
       stl  = Modell-STL des Objekts (objekt.json "stl", "stl_massstab").
       netz = grobes Fotonetz (--netz DATEI.stl, Rahmen der Kameras) PLUS LoD2-Huelle: LoD2-Dreiecke, die weiter als NETZ_TOL (0,5 m) vom Netz
              entfernt sind, bleiben als Flaeche drin (Falle: ein Netz aus denselben Fotos hat dort, wo kein Foto hinsah, gar keine Flaeche - die Luecke
              wuerde unsichtbar; gpu_knn).
       lod2 = nur die LoD2-Huelle des Objekts (objekt.json "lod2"); Normalfall VOR dem ersten Termin (Online-Fotos -> SfM -> Wolke -> hier).
              Zusatzmerkmal "Wolke duenn" (--wolke): Punkte der Fotowolke innerhalb 0,5 m je m2 LoD2-Flaeche (gpu_knn).
       auto = stl, wenn objekt.json "stl" existiert, sonst netz (falls --netz), sonst lod2.
  2. Kameras: ALLE kalibrierten Fotos (kam*.json-Dateien der SfM des Objekts, Format je Bild Rn,tn,C,f,cx,cy,W,H; Online-/Video-Frames mit;
     dazu messprotokoll/K-*.json). Fast gleiche Posen (< 0,25 m und < 2 Grad) zaehlen als EINE Ansicht.
  3. Sicht je Kamera: render_kern.dreiecke_rastern (GPU, exakt) auf 1/4 Aufloesung, Mittelpunkt-Tiefentest je Dreieck. Nachbargebaeude (LoD2) verdecken.
     Bewertung je 1-m-Fleck (Lage x Normalenrichtung): gut / mittel / fehlt (Schwellen unten, ANNAHME wo ohne Quelle).
  4. Standpunkte: Kandidaten am Boden (Augenhoehe), Sicht per Voxel-Strahl (GPU), Greedy-Ueberdeckung inkl. Triangulationswinkel zu vorhandenen Kameras.
  5. Georeferenz SfM-Rahmen -> UTM32 -> WGS84 (Grundriss-Anpassung an LoD2; Beweis: IoU und Eckabstand) und Ausgabe.

Aufruf (venv-seg, GPU; lange Laeufe ueber tools/job_start.sh mit JOB_GPU_MB):
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_luecken.py <objekt> [--flaeche auto] [--aus DIR] [--daten DIR] [--kameras a.json,b.json]
        [--wolke W.npy] [--netz N.stl] [--georef G.json] [--teile_dir D] [--max_standpunkte 25]
Ausgabe: <aus>/foto_luecken.json, standpunkt_<n>.jpg, luecken_3d.json, georef.json (Standard <aus> = /media/oem/scan/rc-park_daten/<objekt>/foto_luecken/).
"""
import sys, os, json, glob, argparse, time, math
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # mehrere Jobs teilen 8 GB VRAM
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as RK

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Schwellen (Nutzervorgabe 10.11. = Quelle "Nutzer"; sonst ANNAHME) ------------------------------------------------------------------------
GUT_MIN_ANSICHTEN = 3        # Nutzer: gut = >= 3 Ansichten ...
GUT_MAX_EINFALL = 60.0       # ... mit Einfallswinkel < 60 Grad (Nutzer)
GUT_MIN_TRI = 15.0           # ... groesster Triangulationswinkel zwischen zwei solchen Ansichten >= 15 Grad (Nutzer)
GUT_MAX_RES = 0.01           # ... beste Bodenaufloesung <= 0,01 m/px = Tiefe/f (Nutzer)
MAX_EINFALL_SICHT = 80.0     # ANNAHME: ab 80 Grad Streifwinkel zaehlt die Flaeche nicht mehr als gesehen (Texturverzerrung, kein Bildwert)
MIN_FLECK_SICHT = 0.25       # ANNAHME: Kamera "sieht" einen Fleck, wenn >= 25 % seiner Flaeche sichtbar sind; "gut gesehen" ab 50 %
GUT_ANTEIL = 0.5
POSE_DEDUP_M, POSE_DEDUP_GRAD = 0.25, 2.0   # ANNAHME: fast gleiche Pose = dieselbe Ansicht (Video-Frames)
RASTER_SKALE = 0.25          # Raster auf 1/4 Aufloesung: Sicht grob genug, Mittelpunkt-Test
TIEFE_TOL = (0.08, 0.01)     # ANNAHME: Tiefentest-Toleranz 0,08 m + 1 % der Tiefe
FLECK_RASTER = 1.0           # Nutzer: ~1 m Raster
UNTERTEILUNG = 2.0           # Dreiecke werden auf <= 2 m Kantenlaenge unterteilt (grosse Waende teilweise verdeckt)
AUGEN = 1.6                  # Nutzer: Augenhoehe Gelaende + 1,6 m
STAND_D = (5.0, 30.0)        # Nutzer: Abstand 5-30 m
STAND_NORMALE = 40.0         # Nutzer: entlang Normale +-40 Grad (Kandidat im Kegel der Normalen der Flecke)
KAND_RASTER = 2.5            # ANNAHME: Kandidatenabstand am Boden
FREI_PUFFER = 0.8            # ANNAHME: Mindestabstand zur Wand/zum Grundriss
ZIEL_ABDECKUNG, MAX_STAND = 0.90, 25   # Nutzer
F_LANG_1X = 0.77 * 4032      # Handy 1x (26 mm KB): f = 3111 px bei 4032 px lange Seite (Messung K-6120, SfM 3111 px)
PX_LANG, PX_KURZ = 4032, 3024
ZOOMS = (1.0, 2.0, 3.0)      # Handy 1x / 2x / 3x
NETZ_TOL = 0.5               # Netz-LoD2-Abstand (Nutzer)
WOLKE_R, WOLKE_DUENN = 0.5, 5.0   # Punkte im Radius 0,5 m; < 5 Punkte/m2 = duenn (ANNAHME)
FAECHER_WINKEL = 15.0        # 3 Fotos je Standpunkt mit seitlichem Versatz b: Basiswinkel 2 atan(b/d) = 15 Grad, b in [1,4] m (Nutzer: 1-2 m; bei 25-30 m Abstand sind fuer 15 Grad 3-4 m noetig)
MIN_GEWINN_M2 = 3.0          # ANNAHME: ein Standpunkt, der weniger als 3 m2 neu abdeckt, lohnt den Weg nicht -> Greedy bricht ab (6 m2 verlor die Erker-/Balkon-Unterseiten)
NAH_D, NAH_RASTER = (2.0, 25.0), 1.0   # ANNAHME: 2. Durchgang fuer Gassen/Nahbereich: ab 2 m Abstand, Kandidaten alle 1 m
GRUENDE = ("vom Boden erreichbar", "Dach: nur Drohne/erhoehter Standort", "kein Standpunkt 2-30 m mit Einfall < 60 Grad (zu steil/zu hoch/Unterseite)", "verdeckt durch Nachbargebaeude/Eigenbau oder Gasse zu eng", "Aufloesung/Triangulation/Bildausschnitt reichen nicht (Zoom/Drohne)")
KLASSEN = ("gut", "mittel", "fehlt")


# ====================================================================================================================================================
# Georeferenz
# ====================================================================================================================================================
def utm32(lat, lon):
    """Transverse Mercator Zone 32 (GRS80/WGS84), Formel wie tools/objekt_daten.py utm32 (Snyder)."""
    a = 6378137.0; f = 1 / 298.257222101; e2 = f * (2 - f); ep2 = e2 / (1 - e2); k0 = 0.9996; lon0 = math.radians(9.0)
    la = math.radians(lat); lo = math.radians(lon); N = a / math.sqrt(1 - e2 * math.sin(la) ** 2); T = math.tan(la) ** 2; C = ep2 * math.cos(la) ** 2; A = math.cos(la) * (lo - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * la - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * la) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * la) - (35 * e2 ** 3 / 3072) * math.sin(6 * la))
    return 500000 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120), k0 * (M + N * math.tan(la) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))


def utm32_zurueck(E, N, lat0=48.0, lon0=7.85):
    """Umkehrung per Newton auf utm32 (exakt bis < 1e-9 m)."""
    lat, lon = lat0, lon0
    for _ in range(12):
        e, n = utm32(lat, lon); h = 1e-6
        e1, n1 = utm32(lat + h, lon); e2, n2 = utm32(lat, lon + h)
        J = np.array([[(e1 - e) / h, (e2 - e) / h], [(n1 - n) / h, (n2 - n) / h]]); d = np.linalg.solve(J, [E - e, N - n])
        lat += d[0]; lon += d[1]
        if abs(d).max() < 1e-12: break
    return float(lat), float(lon)


class Georef:
    """SfM-/Modellrahmen -> UTM32. p_L = Rz(theta) p_xy + t (LoD2-Rahmen des Objekts: Ursprung c0, Achsen xh,yh), UTM = c0 + x xh + y yh. z_sfm - z_boden = z ueber Gelaende."""
    def __init__(self, d):
        self.d = d; th = math.radians(d["theta_grad"]); self.Rz = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]]); self.t = np.array(d["t"], float)
        self.c0 = np.array(d["mitte_utm"], float); self.xh = np.array(d["xhat_utm"], float); self.yh = np.array(d["yhat_utm"], float)
    def sfm_nach_L(self, P): P = np.atleast_2d(np.asarray(P, float)); return np.c_[P[..., :2] @ self.Rz.T + self.t, P[..., 2] - self.d["z_boden"]]
    def L_nach_sfm(self, P): P = np.atleast_2d(np.asarray(P, float)); return np.c_[(P[..., :2] - self.t) @ self.Rz, P[..., 2] + self.d["z_boden"]]
    def L_nach_utm(self, P): P = np.atleast_2d(np.asarray(P, float)); return self.c0 + P[..., :1] * self.xh + P[..., 1:2] * self.yh
    def utm_nach_L(self, E, z=0.0): E = np.asarray(E, float) - self.c0; return np.c_[E @ self.xh, E @ self.yh, np.full(len(E), z)]
    def sfm_nach_utm(self, P): return self.L_nach_utm(self.sfm_nach_L(P))
    def sfm_nach_wgs(self, P): return [utm32_zurueck(*e) for e in np.atleast_2d(self.sfm_nach_utm(P))]
    def richtung_nach_kompass(self, v):
        """Richtungsvektor (SfM, xy) -> Kompasspeilung in Grad (0 = Nord, 90 = Ost)."""
        v = np.asarray(v, float)[:2] @ self.Rz.T; e = v[0] * self.xh + v[1] * self.yh; return float(math.degrees(math.atan2(e[0], e[1])) % 360)


def wand_gier_hist(normalen, flaechen, glaett=2.0):
    """Flaechengewichtetes Histogramm der Wand-Gierwinkel (Grad, 1-Grad-Klassen, gaussglatt) aus Normalen nahezu senkrechter Flaechen (|nz| < 0,2)."""
    n = np.asarray(normalen); mk = np.abs(n[:, 2]) < 0.2; ang = np.degrees(np.arctan2(n[mk, 1], n[mk, 0])) % 360
    h = np.bincount(np.round(ang).astype(int) % 360, weights=np.asarray(flaechen)[mk], minlength=360).astype(float)
    k = np.exp(-0.5 * (np.arange(-6, 7) / glaett) ** 2); h = np.sum([np.roll(h, i) * k[i + 6] for i in range(-6, 7)], 0)
    return h / max(np.linalg.norm(h), 1e-9)


def fit_grundriss(poly_modell, poly_ziel, theta_schritt=3.0, h_modell=None, h_ziel=None, kam_xy=None, sperre=None, w_wand=0.5, w_kam=1.0):
    """2D-Starrkoerper (theta, t) so, dass poly_modell auf poly_ziel liegt. Ziel = IoU + w_wand * Korrelation der Wand-Gierwinkel (h_modell/h_ziel)
    - w_kam * Anteil bodennaher Kameras (kam_xy, Modellrahmen) in Gebaeuden (sperre = LoD2-Gebaeudeflaeche). Die Wandwinkel und Kameras loesen die
    180-Grad-/90-Grad-Mehrdeutigkeit eines fast rechteckigen Grundrisses (Befund Kaufhaus: IoU allein 172 Grad - dann liegen 86 % der Kameras IN Gebaeuden).
    Rueckgabe theta_grad, t, iou, dict(wandkorr, kam_in_geb)."""
    from shapely import affinity
    from shapely.geometry import Point
    from scipy.optimize import minimize
    cz = np.array(poly_ziel.centroid.coords[0])
    def teil(th, t):
        q = affinity.translate(affinity.rotate(poly_modell, th, origin=(0, 0)), *t); u = q.union(poly_ziel).area; io = q.intersection(poly_ziel).area / u if u > 0 else 0.0
        wk = 0.0
        if h_modell is not None:                                           # sum_k hm[k] * hl[k + theta] (lineare Interpolation)
            i0 = int(math.floor(th)); fr = th - i0; wk = float((1 - fr) * np.dot(h_modell, np.roll(h_ziel, -i0)) + fr * np.dot(h_modell, np.roll(h_ziel, -i0 - 1)))
        kf = 0.0
        if kam_xy is not None and sperre is not None:
            r = math.radians(th); Rz = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]]); L = kam_xy @ Rz.T + np.asarray(t)
            from shapely import contains_xy
            kf = float(contains_xy(sperre, L[:, 0], L[:, 1]).mean())
        return io, wk, kf
    def ziel(p): io, wk, kf = teil(p[0], p[1:]); return -(io + w_wand * wk - w_kam * kf)
    def start(th): r = np.array(affinity.rotate(poly_modell, th, origin=(0, 0)).centroid.coords[0]); return [th, *(cz - r)]
    cand = sorted(((-ziel(start(th)), th) for th in np.arange(0, 360, theta_schritt)), reverse=True)[:6]
    best = None
    for _, th in cand:
        s0 = start(th)
        r = minimize(ziel, s0, method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-7, maxiter=500, initial_simplex=np.array([s0, [th + 2, s0[1], s0[2]], [th, s0[1] + 1, s0[2]], [th, s0[1], s0[2] + 1]])))
        if best is None or -r.fun > best[0]: best = (-r.fun, r.x)
    _, (th, tx, ty) = best; io, wk, kf = teil(th, [tx, ty])
    return float(th % 360), [float(tx), float(ty)], float(io), dict(wandkorr=round(float(wk), 3), kamera_in_gebaeude=round(kf, 4))


def lod2_laden(obj, radius=70.0):
    """LoD2 des Objekts (LGL-gml, objekt.json "lod2") -> (ziel_polys, nachbar_polys) in UTM. polys = Liste (Typ, Nx3)."""
    import lod2_gebaeude as LG
    lo = obj["lod2"]; rh = obj["rahmen"]; picked = LG.extract(lo["gml"], center=tuple(rh["mitte_utm"]), radius=radius)
    ziel = [pk for pk in picked if pk[0].get("id") == lo.get("id")]
    if not ziel: raise SystemExit("LoD2-Gebaeude %s nicht im gml" % lo.get("id"))
    return ziel[0][1], [pk[1] for pk in picked if pk[0].get("id") != lo.get("id")]


def lod2_mesh_L(polys_liste, geo):
    """LoD2-Polygone (UTM) -> trimesh im L-Rahmen (z ueber Gelaende des Zielgebaeudes: geo.d['z_lod2_boden'])."""
    import lod2_gebaeude as LG
    V, F = [], []
    for polys in polys_liste:
        for typ, P in polys:
            Pl = np.c_[geo.utm_nach_L(P[:, :2])[:, :2], P[:, 2] - geo.d["z_lod2_boden"]]; b = len(V); V.extend(Pl.tolist())
            for tri in LG.planar_triangulate(Pl): F.append((b + tri[0], b + tri[1], b + tri[2]))
    return trimesh.Trimesh(np.array(V), np.array(F), process=False)


def schnitt_polygon(mesh, z):
    """Horizontalschnitt des Netzes in Hoehe z -> shapely-Vereinigung der gefuellten Schleifen (leer = None)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None: return None
    ps = [Polygon(l[:, :2]).buffer(0) for l in s.discrete if len(l) > 3]
    ps = [p for p in ps if p.area > 0.05]
    return unary_union(ps) if ps else None


def georef_bestimmen(obj, mesh_sfm, zg, aus=None, cams=None):
    """Beweis der Transformation: Grundriss-Schnitt des Modells (3 m ueber Boden) auf den LoD2-Grundriss legen (IoU + Wandwinkel + Kameras nicht in Gebaeuden);
    Bericht: IoU, Eckabstaende, Anteil des Modellumrisses nahe der LoD2-Kante, Wand-Gierwinkel-Rest."""
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    from shapely import affinity
    rh = obj["rahmen"]; ziel_polys, nachbar = lod2_laden(obj)
    c0 = np.array(rh["mitte_utm"]); xh = np.array(rh["xhat_utm"]); yh = np.array(rh["yhat_utm"])
    gml_z = float(np.vstack([P for t, P in ziel_polys if t == "GroundSurface"])[:, 2].min())
    d0 = dict(mitte_utm=c0.tolist(), xhat_utm=xh.tolist(), yhat_utm=yh.tolist(), theta_grad=0.0, t=[0, 0], z_boden=float(zg), z_lod2_boden=gml_z)
    g0 = Georef(d0)
    flaeche = lambda polys: unary_union([q for q in (Polygon(g0.utm_nach_L(P[:, :2])[:, :2]).buffer(0) for t, P in polys if t == "GroundSurface" and len(P) > 2) if q.area > 0.05])
    gr = flaeche(ziel_polys); alle = unary_union([gr] + [flaeche(p) for p in nachbar if p])
    mod = schnitt_polygon(mesh_sfm, zg + 3.0)
    if mod is None: raise SystemExit("Modellschnitt leer")
    # LoD2-Wandnormalen im L-Rahmen
    nl, al = [], []
    for t, P in ziel_polys:
        if t == "WallSurface" and len(P) >= 3:
            n = np.cross(P[1] - P[0], P[2] - P[0]); nn = np.linalg.norm(n)
            if nn < 1e-6: continue
            v = np.array([n[0] * xh[0] + n[1] * xh[1], n[0] * yh[0] + n[1] * yh[1], n[2]]); nl.append(v / nn); al.append(0.5 * nn)
    h_l = wand_gier_hist(np.array(nl), al); h_m = wand_gier_hist(mesh_sfm.face_normals, mesh_sfm.area_faces)
    kam_xy = None
    if cams: C = np.array([c["C"] for c in cams]); kam_xy = C[C[:, 2] < zg + 4][:, :2]
    th, t, iouw, extra = fit_grundriss(mod, gr, h_modell=h_m, h_ziel=h_l, kam_xy=kam_xy, sperre=alle)
    d0["theta_grad"] = th; d0["t"] = t; g = Georef(d0)
    mq = affinity.translate(affinity.rotate(mod, th, origin=(0, 0)), *t)
    ecken = []
    for p in (gr.geoms if hasattr(gr, "geoms") else [gr]): ecken += list(p.exterior.coords)[:-1]
    ab = np.array([mq.boundary.distance(Point(e)) for e in ecken])
    mq_h = max(mq.geoms, key=lambda q: q.area) if hasattr(mq, "geoms") else mq      # Hauptkoerper ohne Arkadenpfeiler (freistehende Kreise)
    bp = np.array([mq_h.boundary.interpolate(x).coords[0] for x in np.linspace(0, mq_h.boundary.length, 400, endpoint=False)]); from shapely import points as _pts
    from shapely import distance as _dist
    db = _dist(_pts(bp[:, 0], bp[:, 1]), gr.boundary)
    front = {}
    if kam_xy is not None and len(kam_xy):
        L = (kam_xy @ np.array([[math.cos(math.radians(th)), math.sin(math.radians(th))], [-math.sin(math.radians(th)), math.cos(math.radians(th))]])) + np.array(t)   # Rz p + t
        cb = np.array(mq_h.centroid.coords[0]); u = L.mean(0) - cb; u /= np.linalg.norm(u); pr = (bp - cb) @ u; sel = pr > 0.6 * pr.max()
        front = dict(n=int(sel.sum()), median=round(float(np.median(db[sel])), 3), p90=round(float(np.percentile(db[sel], 90)), 3), max=round(float(db[sel].max()), 3),
                     hinweis="nur der den Kameras zugewandte Umriss (Frontwand) - dort misst die Aufnahme")
    d0["beweis"] = dict(iou=round(iouw, 4), lod2_flaeche_m2=round(gr.area, 1), modell_schnitt_m2=round(mq.area, 1), lod2_ohne_modell_m2=round(gr.difference(mq).area, 1),
                        modell_ohne_lod2_m2=round(mq.difference(gr).area, 1), wandwinkelkorrelation=extra["wandkorr"], kameras_in_gebaeuden_anteil=extra["kamera_in_gebaeude"],
                        eckabstand_m=dict(n=len(ab), mittel=round(float(ab.mean()), 3), median=round(float(np.median(ab)), 3), p90=round(float(np.percentile(ab, 90)), 3), max=round(float(ab.max()), 3)),
                        modellumriss_zu_lod2_kante_m=dict(median=round(float(np.median(db)), 3), anteil_unter_0_5=round(float((db < 0.5).mean()), 3), anteil_unter_1_0=round(float((db < 1.0).mean()), 3), anteil_unter_2_0=round(float((db < 2.0).mean()), 3)),
                        frontwand_abstand_m=front,
                        quelle="Grundriss-Anpassung (shapely, Nelder-Mead; IoU + Wandwinkel-Korrelation + Kameras nicht in Gebaeuden): Schnitt des Modells 3 m ueber Boden gegen LoD2 GroundSurface/WallSurface %s und Nachbarn" % obj["lod2"].get("id"),
                        hinweis="Rahmen-Annahme: SfM-/Modellrahmen ist lotrecht (z oben), Massstab 1:1 Meter; nur 2D-Drehung+Verschiebung. Restabweichung = Form Modell vs LoD2 (Arkaden/Fluegel), nicht nur Transformation")
    return g, d0, ziel_polys, nachbar


def geo_pruefen_lage(obj):
    """Gegenprobe objekt.json "lage" (lat, lon <-> utm32) mit der eigenen Vorwaerts-/Rueckwaertsformel; Abweichung in m."""
    lg = obj["lage"]; e, n = utm32(lg["lat"], lg["lon"]); la, lo = utm32_zurueck(*lg["utm32"])
    return dict(vorwaerts_abw_m=round(float(math.hypot(e - lg["utm32"][0], n - lg["utm32"][1])), 3), rueck_lat_lon=[round(la, 6), round(lo, 6)], objekt_lat_lon=[lg["lat"], lg["lon"]])


# ====================================================================================================================================================
# Kameras
# ====================================================================================================================================================
def kameras_laden(pfade, obj, objp, stl_verschiebung=None, dedup=True):
    """Liste von Kameras (dict name,R,t,C,f,cx,cy,W,H). pfade: kam*.json (Rn,tn,C,f,cx,cy,W,H je Bild) und messprotokoll/K-*.json. Reihenfolge = Vorrang bei Namensgleichheit."""
    cams, namen = [], set()
    for p in pfade:
        try: k = json.load(open(p))
        except Exception: continue
        if not isinstance(k, dict): continue
        for n, v in k.items():
            if not isinstance(v, dict) or "Rn" not in v or n in namen: continue
            namen.add(n); R = np.array(v["Rn"], float); t = np.array(v["tn"], float)
            cams.append(dict(name=n, R=R, t=t, C=-R.T @ t, f=float(v["f"]), cx=float(v["cx"]), cy=float(v["cy"]), W=int(v["W"]), H=int(v["H"]), quelle=os.path.basename(p)))
    for p in sorted(glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json"))):
        try: K = json.load(open(p)); kk = K["kamera"]
        except Exception: continue
        n = K.get("datei", os.path.basename(p))
        if n in namen: continue
        namen.add(n); R, _ = cv2.Rodrigues(np.array(kk["rvec"])); t = np.array(kk["t"], float)
        sv = np.array(kk.get("rahmen_verschiebung", stl_verschiebung if stl_verschiebung is not None else [0, 0, 0]), float)
        t = t + R @ sv; W, H = kk["bild"]
        cams.append(dict(name=n, R=R, t=t, C=-R.T @ t, f=float(kk["f_px"]), cx=float(kk.get("cx", W / 2)), cy=float(kk.get("cy", H / 2)), W=int(W), H=int(H), quelle=os.path.basename(p)))
    n0 = len(cams)
    if dedup and cams:
        keep = []
        for c in cams:
            ok = True
            for k in keep:
                if np.linalg.norm(c["C"] - k["C"]) < POSE_DEDUP_M and math.degrees(math.acos(np.clip((np.trace(c["R"] @ k["R"].T) - 1) / 2, -1, 1))) < POSE_DEDUP_GRAD: ok = False; break
            if ok: keep.append(c)
        cams = keep
    return cams, n0


# ====================================================================================================================================================
# Flaeche
# ====================================================================================================================================================
def unterteilen(mesh, kante=UNTERTEILUNG):
    v, f, idx = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, max_edge=kante, max_iter=12, return_index=True)
    return np.asarray(v, float), np.asarray(f), np.asarray(idx)


def netz_mit_lod2(netz, lod2, tol=NETZ_TOL):
    """Fotonetz + die LoD2-Dreiecke (auf 1 m unterteilt), die weiter als tol vom Netz entfernt sind (gpu_knn). Rueckgabe Mesh, quelle je Dreieck (0 Netz, 1 LoD2-Ergaenzung)."""
    from gpu_knn import min_abstand
    P = netz.sample(int(max(20000, netz.area * 40)))
    v, f, _ = unterteilen(lod2, 1.0); L = trimesh.Trimesh(v, f, process=False)
    d = min_abstand(L.triangles_center, P); keep = d > tol
    Lk = trimesh.Trimesh(L.vertices, L.faces[keep], process=False)
    m = trimesh.util.concatenate([netz, Lk]); q = np.r_[np.zeros(len(netz.faces), np.int8), np.ones(len(Lk.faces), np.int8)]
    return m, q


# ====================================================================================================================================================
# Kern
# ====================================================================================================================================================
def ohne_bodenflaeche(mesh, zg, quelle=None):
    """Bodenflaeche des Modells (Normale nach unten direkt am Gelaende) ist keine Oberflaeche -> nicht bewerten (Erker-Unterseiten liegen hoeher und bleiben)."""
    tc = mesh.triangles; n = mesh.face_normals; bod = (n[:, 2] < -0.9) & (tc[:, :, 2].max(1) < zg + 0.3)
    m = trimesh.Trimesh(mesh.vertices, mesh.faces[~bod], process=False)
    return m, (None if quelle is None else np.asarray(quelle)[~bod]), int(bod.sum())


def oom_wiederholen(fn, log=print, tries=120, warte=20):
    """CUDA-OOM (VRAM wird von bis zu 8 anderen Jobs geteilt): warten und wiederholen, nicht abbrechen (Auftrag)."""
    for i in range(tries):
        try: return fn()
        except Exception as e:
            if "out of memory" not in str(e).lower(): raise
            import torch, gc; gc.collect(); torch.cuda.empty_cache(); log(f"  CUDA OOM - warte {warte} s (Versuch {i + 1})"); time.sleep(warte)
    raise RuntimeError("CUDA OOM: VRAM blieb belegt")


def _torch():
    import torch; return torch


def flecke_bilden(V, F, fnorm_az_bins=8):
    """Flaeche -> Flecke: Zellschluessel (floor(x/1 m), y, z) + Normalenklasse (oben, unten, 8 Himmelsrichtungen). Rueckgabe patch_id je Dreieck, Anzahl, Schluessel."""
    tri = V[F]; c = tri.mean(1); n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); a = 0.5 * np.linalg.norm(n, axis=1); n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    nk = np.where(n[:, 2] > 0.7, 8, np.where(n[:, 2] < -0.7, 9, (np.floor(((np.degrees(np.arctan2(n[:, 0], n[:, 1])) % 360) + 22.5) / 45.0).astype(int)) % fnorm_az_bins))
    cell = np.floor(c / FLECK_RASTER).astype(np.int64)
    key = np.c_[cell, nk]; u, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.ravel(), len(u), u, c, n, a


def analysiere(V, F, quelle_dreieck, occ_mesh, cams, zg, geo=None, wolke=None, teil_label=None, teil_namen=None, optionen=None, aus=None, log=print, freie_flaechen=None):
    """Kernfunktion (auch fuer den synthetischen Test). V,F: Flaeche im Kamerarahmen (Meter); occ_mesh: zusaetzliche Verdecker (Nachbarn) oder None;
    cams: Kameraliste; zg: Bodenhoehe; freie_flaechen: (shapely-Sperrflaeche) fuer Kandidaten; teil_label: Bauteilindex je Dreieck (oder None)."""
    import torch
    opt = dict(max_stand=MAX_STAND, ziel=ZIEL_ABDECKUNG, d=STAND_D, vorschau=True); opt.update(optionen or {})
    t0 = time.time(); dev = "cuda"
    mesh0 = trimesh.Trimesh(V, F, process=False)
    v2, f2, orig = unterteilen(mesh0)
    nF = len(f2)
    # ---- Flecke
    pid, nP, pkey, fc, fn, fa = flecke_bilden(v2, f2)
    pid_t = torch.as_tensor(pid, device=dev, dtype=torch.long); fa_t = torch.as_tensor(fa, device=dev, dtype=torch.float32)
    fc_t = torch.as_tensor(fc, device=dev, dtype=torch.float32); fn_t = torch.as_tensor(fn, device=dev, dtype=torch.float32)
    PA = torch.zeros(nP, device=dev).index_add_(0, pid_t, fa_t)
    PC = torch.zeros(nP, 3, device=dev).index_add_(0, pid_t, fc_t * fa_t[:, None]) / PA[:, None]
    PN = torch.zeros(nP, 3, device=dev).index_add_(0, pid_t, fn_t * fa_t[:, None]); PN = PN / PN.norm(dim=1, keepdim=True).clamp(min=1e-9)
    log(f"Flaeche: {len(F)} Dreiecke -> {nF} (<= {UNTERTEILUNG} m), {nP} Flecke, {float(PA.sum()):.0f} m2")
    # ---- Szene fuer das Rastern (Flaeche + Verdecker)
    # Tiefenbild: Originalflaeche (nicht die unterteilte - gleiche Tiefe, 4x schneller) + Verdecker
    vo, fo = np.asarray(V, float), np.asarray(F)
    if occ_mesh is not None and len(occ_mesh.faces): sv = np.vstack([vo, occ_mesh.vertices]); sf = np.vstack([fo, occ_mesh.faces + len(vo)])
    else: sv, sf = vo, fo
    scene = trimesh.Trimesh(sv, sf, process=False)
    N = len(cams); FV = torch.zeros(nP, N, dtype=torch.float16, device=dev); FG = torch.zeros(nP, N, dtype=torch.float16, device=dev)
    Ccam = torch.as_tensor(np.array([c["C"] for c in cams]), device=dev, dtype=torch.float32)
    fz_cos = math.cos(math.radians(MAX_EINFALL_SICHT)); gz_cos = math.cos(math.radians(GUT_MAX_EINFALL))
    ts = time.time(); ck = None; cache_ok = False
    if opt.get("cache"):
        import hashlib
        hh = hashlib.sha1(); hh.update(np.ascontiguousarray(V, np.float64).tobytes()); hh.update(np.ascontiguousarray(F).tobytes())
        if occ_mesh is not None: hh.update(np.ascontiguousarray(occ_mesh.vertices, np.float64).tobytes())
        for c in cams: hh.update(np.concatenate([c["R"].ravel(), c["t"], [c["f"], c["cx"], c["cy"], c["W"], c["H"]]]).astype(np.float64).tobytes())
        ck = (opt["cache"], hh.hexdigest())
        if os.path.exists(ck[0]):
            z_ = np.load(ck[0])
            if str(z_["key"]) == ck[1]: FV = torch.as_tensor(z_["FV"], device=dev); FG = torch.as_tensor(z_["FG"], device=dev); cache_ok = True; log("Sicht-Cache geladen", ck[0])
    def kamera_schritt(ci, c):
            s = RASTER_SKALE; W, H = max(8, int(c["W"] * s)), max(8, int(c["H"] * s))
            d_img, _, _ = RK.dreiecke_rastern(scene, c["R"], c["t"], c["f"] * s, c["cx"] * s, c["cy"] * s, W, H, als_torch=True)
            D = torch.as_tensor(d_img, device=dev)
            R = torch.as_tensor(c["R"], device=dev, dtype=torch.float32); t = torch.as_tensor(c["t"], device=dev, dtype=torch.float32)
            X = fc_t @ R.T + t; z = X[:, 2]; zs = z.clamp(min=1e-6)
            u = c["f"] * X[:, 0] / zs + c["cx"]; v = c["f"] * X[:, 1] / zs + c["cy"]
            ui = torch.round(u * s).long(); vi = torch.round(v * s).long()
            inside = (z > 1.0) & (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
            dz = torch.full_like(z, float("inf")); dz[inside] = D[vi[inside], ui[inside]].float()
            tol = TIEFE_TOL[0] + TIEFE_TOL[1] * z
            w = Ccam[ci] - fc_t; dist = w.norm(dim=1).clamp(min=1e-6); cosw = (fn_t * w).sum(1) / dist
            sicht = inside & (z <= dz + tol) & (cosw > fz_cos)
            gut = sicht & (cosw > gz_cos)
            FV[:, ci] = (torch.zeros(nP, device=dev).index_add_(0, pid_t, fa_t * sicht.float()) / PA).half()
            FG[:, ci] = (torch.zeros(nP, device=dev).index_add_(0, pid_t, fa_t * gut.float()) / PA).half()
            del D, d_img

    for ci, c in enumerate(cams if not cache_ok else []):
        oom_wiederholen(lambda: kamera_schritt(ci, c), log)
        if ci % 100 == 0: log(f"  Kamera {ci}/{N}  {time.time() - ts:.0f} s  VRAM max {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB")
    torch.cuda.empty_cache()
    if ck and not cache_ok: np.savez(ck[0], key=ck[1], FV=FV.cpu().numpy(), FG=FG.cpu().numpy())
    log(f"Sicht je Kamera fertig: {N} Kameras {time.time() - ts:.0f} s")
    # ---- Fleck-Bewertung (vorhandene Kameras)
    Wp = PC[:, None, :] - Ccam[None]                      # (P,N,3) Fleck - Kamera
    dpc = Wp.norm(dim=2).clamp(min=1e-6)                  # Entfernung
    fcam = torch.as_tensor(np.array([c["f"] for c in cams]), device=dev, dtype=torch.float32)
    gutv = (FG.float() >= GUT_ANTEIL)                     # gut gesehen
    sicht_p = FV.float() >= MIN_FLECK_SICHT
    res = dpc / fcam[None]
    n_gut = gutv.sum(1)
    res_best = torch.where(gutv, res, torch.full_like(res, 9.0)).min(1).values
    dirs = (Ccam[None] - PC[:, None, :]); dirs = dirs / dirs.norm(dim=2, keepdim=True).clamp(min=1e-9)   # (P,N,3) Fleck -> Kamera
    ang = torch.zeros(nP, device=dev)
    for a0 in range(0, nP, 64):
        dd = dirs[a0:a0 + 64]; m = gutv[a0:a0 + 64]; cs = torch.einsum("pnk,pmk->pnm", dd, dd)
        mm = m[:, :, None] & m[:, None, :]; cs = torch.where(mm, cs, torch.ones_like(cs)); ang[a0:a0 + 64] = torch.rad2deg(torch.acos(cs.amin((1, 2)).clamp(-1, 1)))
    gut_p = (n_gut >= GUT_MIN_ANSICHTEN) & (ang >= GUT_MIN_TRI) & (res_best <= GUT_MAX_RES)
    sicht_n = sicht_p.sum(1)
    klasse = torch.where(gut_p, 0, torch.where(sicht_n > 0, 1, 2))      # 0 gut, 1 mittel, 2 fehlt
    log(f"Flecken: gut {int((klasse == 0).sum())}, mittel {int((klasse == 1).sum())}, fehlt {int((klasse == 2).sum())} (Flaeche m2: "
        + ", ".join("%s %.0f" % (KLASSEN[k], float(PA[klasse == k].sum())) for k in range(3)) + ")")
    # ---- Wolkendichte (Zusatzmerkmal)
    wolke_duenn = None
    if wolke is not None and len(wolke):
        from gpu_knn import ball_anzahl
        n_pts = ball_anzahl(fc, wolke, WOLKE_R, kmax=64).astype(np.float32); dichte = n_pts / (math.pi * WOLKE_R ** 2)
        dt = torch.as_tensor(dichte < WOLKE_DUENN, device=dev, dtype=torch.float32)
        wolke_duenn = (torch.zeros(nP, device=dev).index_add_(0, pid_t, fa_t * dt) / PA)
        log(f"Wolke duenn (< {WOLKE_DUENN} Pkt/m2 im {WOLKE_R} m): {float((PA * wolke_duenn).sum()):.0f} m2 von {float(PA.sum()):.0f}")
    # ---- Kandidaten, Sicht (Voxel), Greedy
    arg = (cams, zg, geo, scene, v2, f2, orig, nP, PA, PC, PN, klasse, n_gut, ang, res_best, gutv, dirs, Ccam, freie_flaechen, log)
    log("Durchgang 1: Standard (Abstand %.0f-%.0f m, Kandidatenraster %.1f m)" % (opt["d"][0], opt["d"][1], KAND_RASTER))
    r1 = oom_wiederholen(lambda: standpunkte(dict(opt), *arg), log)
    res_stand = r1
    if opt.get("durchgang2", True) and len(r1["standpunkte"]) < opt["max_stand"]:
        log("Durchgang 2: Nahbereich/Gassen (Abstand %.0f-%.0f m, Raster %.1f m) fuer das, was Durchgang 1 nicht abdeckt" % (NAH_D[0], NAH_D[1], NAH_RASTER))
        o2 = dict(opt, d=NAH_D, kand_raster=NAH_RASTER, nah=True, skip=r1["abgedeckt"], max_stand=opt["max_stand"] - len(r1["standpunkte"]))
        r2 = oom_wiederholen(lambda: standpunkte(o2, *arg), log)
        cov = np.asarray(r1["coverable"]) | np.asarray(r2["coverable"]); abg = np.asarray(r1["abgedeckt"]) | np.asarray(r2["abgedeckt"]); ng_all = (klasse > 0).cpu().numpy(); PAn = PA.cpu().numpy()
        gr = np.where(cov, 0, r1.get("grund", np.zeros(nP, np.int8)))
        res_stand = dict(grund=gr, standpunkte=r1["standpunkte"] + r2["standpunkte"], coverable=cov, abgedeckt=abg, coverable_m2=float(PAn[ng_all & cov].sum()), nongut_m2=float(PAn[ng_all].sum()),
                         unerreichbar_m2=float(PAn[ng_all & ~cov].sum()), kandidaten=r1["kandidaten"] + r2["kandidaten"], durchgang1_m2=r1.get("coverable_m2"), durchgang2_zusatz_m2=float(PAn[ng_all & cov].sum() - r1.get("coverable_m2", 0)))
    # ---- Ausgabe-Rohdaten
    opid = np.zeros(len(F), np.int64); od = np.argsort(fa); opid[orig[od]] = pid[od]       # Fleck je Originaldreieck (groesstes Teildreieck gewinnt)
    return dict(opid=opid, v2=v2, f2=f2, orig=orig, pid=pid, nP=nP, PA=PA.cpu().numpy(), PC=PC.cpu().numpy(), PN=PN.cpu().numpy(), klasse=klasse.cpu().numpy(), n_gut=n_gut.cpu().numpy(),
                ang=ang.cpu().numpy(), res_best=res_best.cpu().numpy(), sicht_n=sicht_n.cpu().numpy(), wolke_duenn=None if wolke_duenn is None else wolke_duenn.cpu().numpy(),
                stand=res_stand, scene=scene, fa=fa, fn=fn, fc=fc, pkey=pkey, laufzeit_s=time.time() - t0)


def voxel_szene(scene_mesh, lo, hi, vs=0.25, dichte=100.0):
    """Besetzt-Gitter (GPU) der Szene: Oberflaechenpunkte (>= 100 / m2) -> Voxel."""
    import torch
    dev = "cuda"; T = torch.as_tensor(scene_mesh.triangles, device=dev, dtype=torch.float32)
    A = 0.5 * torch.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0], dim=1).norm(dim=1)
    cnt = (A * dichte).ceil().clamp(min=1).long(); cnt = torch.minimum(cnt, torch.full_like(cnt, 4000))
    tri_i = torch.repeat_interleave(torch.arange(len(T), device=dev), cnt)
    r1 = torch.rand(len(tri_i), device=dev).sqrt(); r2 = torch.rand(len(tri_i), device=dev)
    Tt = T[tri_i]; P = (1 - r1)[:, None] * Tt[:, 0] + (r1 * (1 - r2))[:, None] * Tt[:, 1] + (r1 * r2)[:, None] * Tt[:, 2]
    dims = np.ceil((hi - lo) / vs).astype(int); occ = torch.zeros(tuple(dims), dtype=torch.bool, device=dev)
    idx = ((P - torch.as_tensor(lo, device=dev, dtype=torch.float32)) / vs).floor().long()
    ok = (idx >= 0).all(1) & (idx < torch.as_tensor(dims, device=dev)).all(1); idx = idx[ok]; occ[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    return occ, lo, vs


def strahl_frei(occ, lo, vs, A, B, schritt=0.1, vor_ende=0.35, start=0.25, blk=6_000_000):
    """True, wenn die Strecke A->B (Tensoren (M,3), GPU) kein besetztes Voxel schneidet (Ende vor_ende m vor B)."""
    import torch
    M = len(A); out = torch.ones(M, dtype=torch.bool, device=A.device); lo_t = torch.as_tensor(lo, device=A.device, dtype=torch.float32)
    dims = torch.as_tensor(occ.shape, device=A.device)
    d = (B - A).norm(dim=1); nmax = int(torch.ceil((d.max() - vor_ende - start) / schritt).clamp(min=1)) if M else 1
    ts = start + torch.arange(nmax, device=A.device, dtype=torch.float32) * schritt
    per = max(1, blk // nmax)
    for a0 in range(0, M, per):
        a, b, dd = A[a0:a0 + per], B[a0:a0 + per], d[a0:a0 + per]
        dirv = (b - a) / dd.clamp(min=1e-6)[:, None]
        P = a[:, None, :] + dirv[:, None, :] * ts[None, :, None]                 # (m,nmax,3)
        gueltig = ts[None, :] < (dd[:, None] - vor_ende)
        idx = ((P - lo_t) / vs).floor().long()
        im = (idx >= 0).all(2) & (idx < dims).all(2)
        idc = torch.where(im[..., None], idx, torch.zeros_like(idx))
        hit = occ[idc[..., 0], idc[..., 1], idc[..., 2]] & im & gueltig
        out[a0:a0 + per] = ~hit.any(1)
    return out


def standpunkte(opt, cams, zg, geo, scene, v2, f2, orig, nP, PA, PC, PN, klasse, n_gut, ang_ex, res_ex, gutv, dirs, Ccam, sperre, log):
    import torch
    dev = "cuda"; t0 = time.time()
    nongut = (klasse == 0) if opt.get("kontrolle") else (klasse > 0)      # Kontrolle: Sichtmethode an den schon GUT fotografierten Flecken pruefen (muessen weitgehend sichtbar sein)
    if opt.get("skip") is not None: nongut = nongut & ~torch.as_tensor(opt["skip"], device=dev)
    w0 = torch.where(nongut, PA, torch.zeros_like(PA))
    if float(w0.sum()) <= 0: return dict(standpunkte=[], coverable=np.zeros(nP, bool), abgedeckt=np.zeros(nP, bool), coverable_m2=0.0, nongut_m2=0.0, unerreichbar_m2=0.0, kandidaten=0)
    # ---- Gitter
    allp = np.vstack([scene.vertices, np.array([c["C"] for c in cams])])
    pad = opt["d"][1] + 5; lo = np.array([allp[:, 0].min() - pad, allp[:, 1].min() - pad, zg - 1.0]) ; hi = np.array([allp[:, 0].max() + pad, allp[:, 1].max() + pad, scene.vertices[:, 2].max() + 3.0])
    vs = 0.25 if np.prod((hi - lo) / 0.25) < 8e7 else 0.4
    occ, lo, vs = voxel_szene(scene, lo, hi, vs)
    # ---- Kandidaten am Boden: Abstand 5-30 m zu den Nicht-gut-Flecken, nicht in Sperrflaeche
    pc = PC.cpu().numpy(); ng = nongut.cpu().numpy(); ng_w = ng & (PN.cpu().numpy()[:, 2] < 0.3) if opt.get("nah") else ng; xy = pc[ng_w, :2]     # Nahpass: Dachflaechen erzeugen keine Kandidaten
    gx = np.arange(lo[0] + 1, hi[0] - 1, opt.get("kand_raster", KAND_RASTER)); gy = np.arange(lo[1] + 1, hi[1] - 1, opt.get("kand_raster", KAND_RASTER)); G = np.array([(x, y) for x in gx for y in gy])
    from scipy.spatial import cKDTree      # nur Kandidatenvorauswahl (kleine Mengen, CPU), keine grosse Abstandssuche
    dmin = cKDTree(xy).query(G)[0]; G = G[(dmin >= opt["d"][0] * 0.6) & (dmin <= opt["d"][1])]
    if sperre is not None:
        from shapely.geometry import Point
        from shapely.prepared import prep
        sp = prep(sperre.buffer(FREI_PUFFER)); G = G[[not sp.contains(Point(p)) for p in G]]
    if len(G) == 0: return dict(standpunkte=[], coverable=np.zeros(nP, bool), abgedeckt=np.zeros(nP, bool), coverable_m2=0.0, nongut_m2=float(w0.sum()), unerreichbar_m2=float(w0.sum()), kandidaten=0)
    Cz = np.c_[G, np.full(len(G), zg + AUGEN)]; nC = len(Cz); log(f"Kandidaten: {nC}")
    Ct = torch.as_tensor(Cz, device=dev, dtype=torch.float32)
    nidx = torch.nonzero(nongut).squeeze(1)
    Pn, Nn, An = PC[nidx], PN[nidx], PA[nidx]; nPn = len(nidx)
    vec = Ct[:, None, :] - Pn[None]                       # (C,P,3) Fleck -> Kandidat
    dd = vec.norm(dim=2).clamp(min=1e-6); cosN = (vec * Nn[None]).sum(2) / dd
    geo_ok = (dd >= opt["d"][0]) & (dd <= opt["d"][1]) & (cosN >= math.cos(math.radians(GUT_MAX_EINFALL)))   # Einfall < 60 Grad (Nutzerwunsch +-40 Grad entlang der Normalen ist Zielbereich, hier die harte Gut-Grenze)
    ci, pi = torch.nonzero(geo_ok, as_tuple=True)
    _roof = (Nn[:, 2] > 0.3)
    log(f"Gate Geometrie (Abstand {opt['d'][0]}-{opt['d'][1]} m, Einfall < {GUT_MAX_EINFALL}): Flecke mit >= 1 Kandidat: Wand/unten {int(geo_ok.any(0)[~_roof].sum())} von {int((~_roof).sum())}, Dach {int(geo_ok.any(0)[_roof].sum())} von {int(_roof.sum())}")
    log(f"Sichtstrahlen: {len(ci)}")
    A_ = Ct[ci]; B_ = Pn[pi] + Nn[pi] * 0.3
    frei = strahl_frei(occ, lo, vs, A_, B_)
    vis = torch.zeros(nC, nPn, dtype=torch.bool, device=dev); vis[ci[frei], pi[frei]] = True
    del A_, B_, frei, ci, pi, occ; torch.cuda.empty_cache()
    log(f"Gate freie Sicht (Voxel): Flecke mit >= 1 sichtbarem Kandidat: Wand/unten {int(vis.any(0)[~_roof].sum())}, Dach {int(vis.any(0)[_roof].sum())}")
    geo_any_ = geo_ok.any(0); vis_any_ = vis.any(0)
    azcp = torch.rad2deg(torch.atan2(-vec[..., 0], -vec[..., 1])) % 360        # Peilung Kandidat -> Fleck (ab +y, im Uhrzeigersinn)
    elcp = torch.rad2deg(torch.atan2(-vec[..., 2], torch.hypot(vec[..., 0], vec[..., 1])))
    # ---- Winkel Kandidat zu vorhandenen guten Kameras
    dirc = vec / dd[..., None]                            # (C,P,3) Fleck -> Kandidat
    ang_ce = torch.zeros(nC, nPn, device=dev)
    dex = dirs[nidx]; gm = gutv[nidx]
    for a0 in range(0, nPn, 8):
        cs = torch.einsum("cpk,pnk->cpn", dirc[:, a0:a0 + 8], dex[a0:a0 + 8]); cs = torch.where(gm[a0:a0 + 8][None], cs, torch.full_like(cs, 1.0))
        ang_ce[:, a0:a0 + 8] = torch.rad2deg(torch.acos(cs.amin(2).clamp(-1, 1))) * (gm[a0:a0 + 8].any(1)[None].float())
    del dirc, dex
    ang_ex_n = ang_ex[nidx]; res_ex_n = res_ex[nidx]
    b = (0.5 * dd * math.tan(math.radians(FAECHER_WINKEL / 2)) * 2).clamp(1.0, 3.0)
    ang_fan = torch.rad2deg(2 * torch.atan(b / dd))
    tri_ok = (torch.maximum(torch.maximum(ang_fan, ang_ce), ang_ex_n[None]) >= GUT_MIN_TRI)
    # ---- Ansichten: Azimut x Neigung x Zoom x Format
    views = []
    for z in ZOOMS:
        f = F_LANG_1X * z
        for fm, (hl, hk) in (("quer", (PX_LANG, PX_KURZ)), ("hoch", (PX_KURZ, PX_LANG))):
            hh = math.degrees(math.atan(hl / 2 / f)); hv = math.degrees(math.atan(hk / 2 / f))
            for az in range(0, 360, 20):
                for el in (0, 25, 50, 75):
                    views.append((z, fm, az, el, hh, hv, f))
    log(f"Ansichten je Kandidat: {len(views)}")
    def abdeck(vw, w):
        z, fm, az, el, hh, hv, f = vw
        daz = ((azcp - az + 180) % 360) - 180
        cone = (daz.abs() <= hh) & ((elcp - el).abs() <= hv)
        res_ok = (dd / f <= GUT_MAX_RES) | (res_ex_n[None] <= GUT_MAX_RES)
        return vis & cone & res_ok & tri_ok
    # coverable: irgendeine Ansicht deckt den Fleck
    cov_any = torch.zeros(nPn, dtype=torch.bool, device=dev)
    for vw in views: cov_any |= abdeck(vw, None).any(0)
    log(f"Gate Ansicht/Aufloesung/Triangulation: abdeckbar Wand/unten {int(cov_any[~_roof].sum())} von {int((~_roof).sum())}, Dach {int(cov_any[_roof].sum())} von {int(_roof.sum())}")
    wn = An.clone(); coverable_area = float(wn[cov_any].sum()); log(f"coverable {coverable_area:.0f} m2 von Luecken {float(wn.sum()):.0f} m2; nicht vom Boden erreichbar: {float(wn[~cov_any].sum()):.0f} m2")
    if opt.get("kontrolle"):
        log(f"KONTROLLE Sichtmethode an gut fotografierten Flecken: >= 1 sichtbarer Kandidat Wand {int(vis_any_[~_roof].sum())} von {int((~_roof).sum())} ({100 * float(vis_any_[~_roof].float().mean()):.0f} %)"); return dict(standpunkte=[], coverable=np.zeros(nP, bool), abgedeckt=np.zeros(nP, bool), coverable_m2=0.0, nongut_m2=0.0, unerreichbar_m2=0.0, kandidaten=int(nC))
    rest = torch.where(cov_any, wn, torch.zeros_like(wn)); gewaehlt = []; abgedeckt = torch.zeros(nPn, dtype=torch.bool, device=dev)
    for it in range(opt["max_stand"]):
        if coverable_area <= 0 or float(rest.sum()) <= (1 - opt["ziel"]) * coverable_area: break
        best = (0.0, None, None)
        for vi, vw in enumerate(views):
            cov = abdeck(vw, None)                       # (C,P)
            g = (cov.float() * rest[None]).sum(1) * (1 - 0.03 * (vw[0] - 1))
            gm_, ix = g.max(0)
            if float(gm_) > best[0]: best = (float(gm_), vi, int(ix))
        if best[1] is None or best[0] < MIN_GEWINN_M2: break
        vi, c = best[1], best[2]; vw = views[vi]; cov = abdeck(vw, None)[c]
        neu = cov & (rest > 0)
        gewaehlt.append(dict(nah=bool(opt.get("nah")), kand=c, view=vw, patches=nidx[neu].cpu().numpy(), flaeche=float(rest[neu].sum()), pos=Cz[c]))
        abgedeckt |= neu; rest = torch.where(neu, torch.zeros_like(rest), rest)
        log(f"  Standpunkt {it + 1}: {float(gewaehlt[-1]['flaeche']):.0f} m2, Rest {float(rest.sum()):.0f}")
    for g in gewaehlt:   # Peilung/Neigung aus den gedeckten Flecken verfeinern
        c = g["kand"]; pm = torch.as_tensor(g["patches"], device=dev); loc = torch.searchsorted(nidx, pm)
        a_ = azcp[c, loc]; e_ = elcp[c, loc]; ww = PA[pm]
        sa = float((torch.sin(torch.deg2rad(a_)) * ww).sum()); ca = float((torch.cos(torch.deg2rad(a_)) * ww).sum())
        g["az"] = math.degrees(math.atan2(sa, ca)) % 360; g["el"] = float((e_ * ww).sum() / ww.sum()); g["d_mittel"] = float((dd[c, loc] * ww).sum() / ww.sum())
        g["az_breite"] = float((((a_ - g["az"] + 180) % 360) - 180).abs().max()) * 2; g["el_breite"] = float((e_ - g["el"]).abs().max()) * 2
    coverable_full = torch.zeros(nP, dtype=torch.bool, device=dev); coverable_full[nidx[cov_any]] = True
    grund = torch.zeros(nP, dtype=torch.int8, device=dev)      # 0 erreichbar, 1 Dach, 2 Abstand/Einfall, 3 verdeckt (Nachbarn/Eigenbau), 4 Ansicht/Aufloesung/Triangulation
    gg = geo_any_; gv = vis_any_; rg = torch.where(cov_any, 0, torch.where(~gg, torch.where(Nn[:, 2] > 0.3, 1, 2), torch.where(~gv, 3, 4))); grund[nidx] = rg.to(torch.int8)
    abg_full = torch.zeros(nP, dtype=torch.bool, device=dev); abg_full[nidx[abgedeckt]] = True
    log(f"Standpunkte: {len(gewaehlt)}, abgedeckt {float(An[abgedeckt].sum()):.0f} von {coverable_area:.0f} m2  ({time.time() - t0:.0f} s)")
    return dict(standpunkte=gewaehlt, coverable=coverable_full.cpu().numpy(), abgedeckt=abg_full.cpu().numpy(), grund=grund.cpu().numpy(), coverable_m2=coverable_area, nongut_m2=float(An.sum()), unerreichbar_m2=float(An[~cov_any].sum()),
                kandidaten=int(nC))


# ====================================================================================================================================================
# Ausgabe
# ====================================================================================================================================================
def kamera_blick(pos, az_grad, el_grad, f, W, H):
    """Weltkamera: Position, Peilung (0 = +y, im Uhrzeigersinn), Neigung nach oben -> R,t."""
    az, el = math.radians(az_grad), math.radians(el_grad)
    fw = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
    x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x)    # y nach unten im Bild
    R = np.vstack([x, y, fw]); return R, -R @ np.asarray(pos, float)


def vorschau_bild(erg, g, nr, pfad, zusatz=""):
    scene = erg["scene"]; nF = len(erg["opid"]); z, fm, *_ = g["view"]
    W, H = (720, 540) if fm == "quer" else (540, 720)
    f = F_LANG_1X * g["view"][0] * max(W, H) / PX_LANG
    R, t = kamera_blick(g["pos"], g["az"], g["el"], f, W, H)
    d, fid, _ = RK.dreiecke_rastern(scene, R, t, f, W / 2, H / 2, W, H, als_torch=True)
    fid = fid.cpu().numpy(); n = scene.face_normals; img = np.full((H, W, 3), 235, np.uint8)
    tr = fid >= 0
    shade = np.zeros((H, W), np.float32)
    if tr.any():
        nn = n[fid[tr]]; cosv = np.abs(nn @ R[2]); shade[tr] = 0.35 + 0.55 * cosv
    base = np.repeat((shade * 255)[..., None], 3, 2).astype(np.uint8); img[tr] = base[tr]
    pid = erg["opid"]; fpid = np.where((fid >= 0) & (fid < nF), pid[np.clip(fid, 0, nF - 1)], -1); fpid[~tr] = -1
    farbe = np.zeros(erg["nP"], np.int8)   # 0 neutral, 1 gut (gruen), 2 neu abgedeckt (rot), 3 offen (gelb/orange)
    farbe[erg["klasse"] == 0] = 1; farbe[(erg["klasse"] > 0)] = 3; farbe[g["patches"]] = 2
    for k, col in ((1, (60, 170, 60)), (2, (40, 40, 230)), (3, (30, 170, 240))):
        m = (fpid >= 0) & (farbe[np.clip(fpid, 0, None)] == k)
        if m.any(): img[m] = (0.45 * img[m] + 0.55 * np.array(col, np.float32)).astype(np.uint8)
    txt = [f"Standpunkt {nr}  Blick {g['az']:.0f} Grad (Modell)  Neigung {g['el']:+.0f}  {z:.0f}x {fm}  3 Fotos", f"ROT = zu erfassen ({g['flaeche']:.0f} m2)  GRUEN = schon gut  ORANGE = noch offen", zusatz]
    ov = img.copy(); cv2.rectangle(ov, (0, 0), (W, 22 * sum(1 for t_ in txt if t_) + 6), (0, 0, 0), -1); img = cv2.addWeighted(ov, 0.6, img, 0.4, 0)
    for i, s_ in enumerate([t_ for t_ in txt if t_]): cv2.putText(img, s_, (6, 20 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    # Lageplan-Ausschnitt (Draufsicht): Fleckmitten, Standpunkt, Blickkeil
    M = 150; ox, oy = W - M - 6, H - M - 6; PCx = erg["PC"][:, :2]; lo_ = PCx.min(0) - 12; hi_ = PCx.max(0) + 12; sc = M / float(max(hi_ - lo_)); cv2.rectangle(img, (ox, oy), (ox + M, oy + M), (255, 255, 255), -1); cv2.rectangle(img, (ox, oy), (ox + M, oy + M), (0, 0, 0), 1)
    pt = lambda xy: (int(ox + (xy[0] - lo_[0]) * sc), int(oy + M - (xy[1] - lo_[1]) * sc))
    for i in range(0, len(PCx), max(1, len(PCx) // 1500)): cv2.circle(img, pt(PCx[i]), 1, (170, 170, 170) if erg["klasse"][i] == 0 else (30, 170, 240), -1)
    for i in g["patches"][::2]: cv2.circle(img, pt(PCx[i]), 1, (40, 40, 230), -1)
    for g2 in erg["stand"]["standpunkte"]: cv2.circle(img, pt(g2["pos"]), 2, (160, 100, 0), -1)
    p0 = np.array(pt(g["pos"])); az = math.radians(g["az"]); hw = math.radians(33)
    for da in (-hw, hw): cv2.line(img, tuple(p0), (int(p0[0] + 40 * math.sin(az + da)), int(p0[1] - 40 * math.cos(az + da))), (255, 0, 0), 1)
    cv2.circle(img, tuple(p0), 4, (255, 0, 0), -1); cv2.putText(img, "Plan (oben = +y Modell)", (ox + 3, oy + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 0, 0), 1)
    cv2.imwrite(pfad, img, [cv2.IMWRITE_JPEG_QUALITY, 88])


def flecken_liste(erg, teil_label, teil_namen, nur_erhoeht):
    """Zusammenhaengende Nicht-gut-Flecke (Nachbarzellen gleicher Normalenklasse und Klasse) -> Liste."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nP = erg["nP"]; kl = erg["klasse"]; key = erg["pkey"]; idx = {tuple(k): i for i, k in enumerate(key)}
    ids = [i for i in range(nP) if kl[i] > 0]; r, c = [], []
    for i in ids:
        cx, cy, cz, nk = key[i]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    j = idx.get((cx + dx, cy + dy, cz + dz, nk))
                    if j is not None and j != i and kl[j] == kl[i]: r.append(i); c.append(j)
    ncomp, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(nP, nP)), directed=False)
    pid = erg["pid"]
    out = []
    for cidx in np.unique(lab[ids]):
        mem = [i for i in ids if lab[i] == cidx]; a = erg["PA"][mem]; A = float(a.sum())
        if A < 0.5: continue
        pc = (erg["PC"][mem] * a[:, None]).sum(0) / A; nn = (erg["PN"][mem] * a[:, None]).sum(0); nn /= max(np.linalg.norm(nn), 1e-9)
        d = dict(id=int(cidx), klasse=KLASSEN[int(kl[mem[0]])], flaeche_m2=round(A, 1), schwerpunkt=np.round(pc, 2).tolist(), normale=np.round(nn, 2).tolist(),
                 z_von_bis=[round(float(erg["PC"][mem, 2].min()), 1), round(float(erg["PC"][mem, 2].max()), 1)], n_flecke=len(mem), patches=mem,
                 nur_erhoeht=bool(nur_erhoeht[mem].mean() > 0.5), dach=bool(nn[2] > 0.3))
        gc = erg["stand"].get("grund")
        if gc is not None:
            cnt = {int(k): float(erg["PA"][[i for i in mem if gc[i] == k]].sum()) for k in np.unique(gc[mem])}; k = max(cnt, key=cnt.get); d["grund"] = GRUENDE[k]
        if erg["wolke_duenn"] is not None: d["wolke_duenn_anteil"] = round(float((erg["wolke_duenn"][mem] * a).sum() / A), 2)
        if teil_label is not None:
            fm = np.isin(pid, mem); lab_f = teil_label[erg["orig"][fm]]; wts = erg["fa"][fm]; v = {}
            for l, w in zip(lab_f, wts): v[int(l)] = v.get(int(l), 0) + w
            d["bauteil"] = teil_namen[max(v, key=v.get)] if v else None
        out.append(d)
    return sorted(out, key=lambda d: -d["flaeche_m2"])


def teile_zuordnen(m_orig_centers, teile_dir, skala, verschiebung):
    """Dreieck -> naechstes Teil (gpu_knn auf Oberflaechenpunkten der Teil-STLs). Rueckgabe label, namen."""
    from gpu_knn import naechster
    namen, P, L = [], [], []
    for i, p in enumerate(sorted(glob.glob(os.path.join(teile_dir, "*.stl")))):
        m = trimesh.load(p, force="mesh")
        if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0: continue
        m.apply_scale(skala); m.apply_translation(verschiebung); s = m.sample(int(max(500, m.area * 40))); P.append(s); L.append(np.full(len(s), len(namen))); namen.append(os.path.basename(p)[:-4])
    if not P: return None, []
    d, ix = naechster(m_orig_centers, np.vstack(P)); lab = np.concatenate(L)[ix]; lab = np.where(d < 1.5, lab, -1)
    return lab, namen


def schreibe(erg, aus, geo, cams_info, args_info, teil_label=None, teil_namen=None, mesh_orig=None, quelle_tri=None, stand_namen=None, log=print):
    os.makedirs(aus, exist_ok=True)
    st = erg["stand"]; coverable = st.get("coverable", np.zeros(erg["nP"], bool)); nur = ~np.asarray(coverable, bool)
    fl = flecken_liste(erg, teil_label, teil_namen, nur)
    stand_out = []
    for i, g in enumerate(st.get("standpunkte", []), 1):
        pos = g["pos"]; teile = {}
        pa = erg["PA"][g["patches"]]
        sp = dict(nr=i, position_sfm=np.round(pos, 2).tolist(), blick_azimut_modell_grad=round(g["az"], 1), neigung_grad=round(g["el"], 1), zoom=f"{g['view'][0]:.0f}x", brennweite_kb_mm=round(26 * g["view"][0]),
                  format=g["view"][1], fotos=3, versatz_seitlich_m=round(float(np.clip(g["d_mittel"] * 0.135, 1, 4)), 1), abstand_mittel_m=round(g["d_mittel"], 1),
                  art=("Nahbereich/Gasse (2-25 m)" if g.get("nah") else "Standard (5-30 m)"), erfasst_m2=round(g["flaeche"], 1), bildwinkel_noetig_grad=[round(g["az_breite"], 0), round(g["el_breite"], 0)])
        if geo is not None:
            lat, lon = geo.sfm_nach_wgs(pos)[0]; sp["lat"] = round(lat, 7); sp["lon"] = round(lon, 7); sp["utm32"] = np.round(geo.sfm_nach_utm(pos)[0], 2).tolist()
            sp["blick_kompass_grad"] = round(geo.richtung_nach_kompass([math.sin(math.radians(g["az"])), math.cos(math.radians(g["az"]))]), 1)
        if teil_label is not None:
            fm = np.isin(erg["pid"], g["patches"]); v = {}
            for l, w in zip(teil_label[erg["orig"][fm]], erg["fa"][fm]): v[teil_namen[int(l)] if l >= 0 else "(ohne Teil)"] = v.get(teil_namen[int(l)] if l >= 0 else "(ohne Teil)", 0) + float(w)
            sp["erfasst_bauteile_m2"] = {k: round(x, 1) for k, x in sorted(v.items(), key=lambda kv: -kv[1])[:8]}
        gp = set(int(x) for x in g["patches"]); sp["flecken_ids"] = [f["id"] for f in fl if gp & set(f["patches"])][:20]
        stand_out.append(sp)
        if args_info.get("vorschau", True): vorschau_bild(erg, g, i, os.path.join(aus, f"standpunkt_{i}.jpg"), zusatz=(f"lat {sp['lat']:.6f} lon {sp['lon']:.6f}" if geo is not None else ""))
    kl = erg["klasse"]; PA = erg["PA"]
    summ = {KLASSEN[k]: round(float(PA[kl == k].sum()), 1) for k in range(3)}
    erst = dict(summe_m2=summ, flaeche_gesamt_m2=round(float(PA.sum()), 1), erreichbar_vom_boden_m2=round(st.get("coverable_m2", 0.0), 1), nur_erhoeht_m2=round(float(PA[(kl > 0) & nur].sum()), 1))
    out = dict(objekt=args_info.get("objekt"), erzeugt=time.strftime("%Y-%m-%d %H:%M:%S"), flaeche_quelle=args_info.get("flaeche"), schwellen=dict(
        gut=f">= {GUT_MIN_ANSICHTEN} Ansichten Einfall < {GUT_MAX_EINFALL} Grad, Triangulationswinkel >= {GUT_MIN_TRI}, beste Aufloesung <= {GUT_MAX_RES} m/px (Nutzer 10.11.)",
        sichtbar_bis_einfall=MAX_EINFALL_SICHT, fleck_raster_m=FLECK_RASTER, augenhoehe_m=AUGEN, stand_abstand_m=list(STAND_D)), kameras=cams_info, zusammenfassung=erst,
        standpunkte=stand_out, flecken=fl, georef=(geo.d if geo is not None else None), laufzeit_s=round(erg["laufzeit_s"], 1), hinweise=args_info.get("hinweise", []))
    json.dump(out, open(os.path.join(aus, "foto_luecken.json"), "w"), indent=1, ensure_ascii=False)
    # --- 3D-Uebersicht: Originaldreiecke, Klasse = schlechteste Klasse mit >= 30 % Flaeche
    o = erg["orig"]; pk = kl[erg["pid"]]; nO = len(mesh_orig.faces); tot = np.bincount(o, weights=erg["fa"], minlength=nO); score = np.zeros(nO, np.int8)
    for k in (2, 1):
        a = np.bincount(o, weights=erg["fa"] * (pk == k), minlength=nO); score[(a >= 0.3 * np.maximum(tot, 1e-9)) & (score == 0)] = k
    mo = mesh_orig; step = 1
    j3 = dict(einheit="m (SfM-Rahmen)", klassen=list(KLASSEN), farben=["#2e9e44", "#e8a317", "#d62828"], v=np.round(mo.vertices, 2).ravel().tolist(), f=mo.faces.ravel().tolist(), klasse=score.tolist(),
              standpunkte=[s["position_sfm"] for s in stand_out], kameras=np.round(np.array([c["C"] for c in args_info["cams"]]), 2).tolist())
    json.dump(j3, open(os.path.join(aus, "luecken_3d.json"), "w"), separators=(",", ":"))
    return out


# ====================================================================================================================================================
# Hauptprogramm
# ====================================================================================================================================================
def kamera_pfade(a, objp, obj):
    if a.kameras: return a.kameras.split(",")
    out = []
    daten = a.daten or os.path.join("/media/oem/scan/rc-park_daten", a.objekt)
    for d in (os.path.join(daten, "sfm"), os.path.join(os.path.dirname(objp), "sfm")):
        if d and os.path.isdir(d):
            fs = sorted(glob.glob(os.path.join(d, "kam_*.json"))); fs.sort(key=lambda p: (os.path.basename(p) != "kam_lot2.json", p)); out += fs
    return out


def wolke_laden(pfad, maxn=3_000_000):
    P = np.load(pfad, allow_pickle=True)
    if hasattr(P, "files"): P = P[[k for k in ("P", "xyz", "pts", "punkte") if k in P.files][0]]
    P = np.asarray(P, np.float32)[:, :3]
    if len(P) > maxn: P = P[np.random.default_rng(0).choice(len(P), maxn, replace=False)]
    return P


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--flaeche", default="auto", choices=["auto", "stl", "netz", "lod2"])
    ap.add_argument("--aus"); ap.add_argument("--daten"); ap.add_argument("--kameras"); ap.add_argument("--wolke"); ap.add_argument("--netz"); ap.add_argument("--georef")
    ap.add_argument("--teile_dir"); ap.add_argument("--max_standpunkte", type=int, default=MAX_STAND); ap.add_argument("--keine_vorschau", action="store_true")
    ap.add_argument("--kontrolle", action="store_true", help="nur Sichtmethode an gut fotografierten Flecken pruefen")
    ap.add_argument("--max_kameras", type=int, default=0, help="nur zum Testen")
    a = ap.parse_args(argv)
    import gpu_slot; gpu_slot.belegen("foto_luecken")      # gemeinsame GPU-Schlange (3 Plaetze), haelt den Platz bis Prozessende
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    aus = a.aus or os.path.join("/media/oem/scan/rc-park_daten", a.objekt, "foto_luecken"); os.makedirs(aus, exist_ok=True)
    logf = open(os.path.join(aus, "lauf.log"), "a")
    def log(*x):
        s = time.strftime("%H:%M:%S ") + " ".join(str(i) for i in x); print(s, flush=True); logf.write(s + "\n"); logf.flush()
    t0 = time.time(); hinweise = []
    stl_pfad = os.path.join(R0, obj["stl"]) if obj.get("stl") else None
    hat_stl = bool(stl_pfad and os.path.exists(stl_pfad))
    flaeche = a.flaeche
    if flaeche == "auto": flaeche = "stl" if hat_stl else ("netz" if a.netz else "lod2")
    log(f"Objekt {a.objekt}  Flaeche {flaeche}")
    skala = obj.get("stl_massstab", 87) / 1000.0
    stl_m = None
    if hat_stl:
        stl_m = trimesh.load(stl_pfad, force="mesh"); stl_m.apply_scale(skala)
    zeile_zg = float(stl_m.bounds[0, 2]) if stl_m is not None else None
    # ---- Kameras
    cams, n0 = kameras_laden(kamera_pfade(a, objp, obj), obj, objp)
    if a.max_kameras: cams = cams[:a.max_kameras]
    log(f"Kameras: {n0} geladen, {len(cams)} nach Posen-Dedup")
    if not cams: raise SystemExit("keine Kameras")
    if zeile_zg is None: zeile_zg = float(np.percentile([c["C"][2] for c in cams], 5) - AUGEN); hinweise.append("ANNAHME: Boden = 5. Perzentil der Kamerahoehen - 1,6 m")
    zg = zeile_zg
    # ---- Georeferenz
    geo, ziel_polys, nachbar = None, None, []
    lod2_da = bool(obj.get("lod2", {}).get("gml") and os.path.exists(obj["lod2"]["gml"]) and obj.get("rahmen"))
    if a.georef: geo = Georef(json.load(open(a.georef)))
    if lod2_da:
        if geo is None and stl_m is not None:
            geo, gd, ziel_polys, nachbar = georef_bestimmen(obj, stl_m, zg, cams=cams)
            json.dump(gd, open(os.path.join(aus, "georef.json"), "w"), indent=1)
            log("Georef:", json.dumps(gd["beweis"], ensure_ascii=False))
        else:
            ziel_polys, nachbar = lod2_laden(obj)
            if geo is None:
                rh = obj["rahmen"]; gz = float(np.vstack([P for t, P in ziel_polys if t == "GroundSurface"])[:, 2].min())
                geo = Georef(dict(mitte_utm=rh["mitte_utm"], xhat_utm=rh["xhat_utm"], yhat_utm=rh["yhat_utm"], theta_grad=0.0, t=[0, 0], z_boden=zg, z_lod2_boden=gz))
                hinweise.append("ANNAHME: Kameras liegen im LoD2-Rahmen des Objekts (objekt.json rahmen) - keine Anpassung moeglich ohne STL/--georef")
            else:
                geo.d.setdefault("z_lod2_boden", float(np.vstack([P for t, P in ziel_polys if t == "GroundSurface"])[:, 2].min()))
    else: hinweise.append("keine LoD2/Georeferenz -> keine lat/lon, keine Nachbarverdeckung")
    # ---- Flaeche
    quelle_tri = None; lod2_hull = None
    if geo is not None and ziel_polys is not None:
        mL = lod2_mesh_L([ziel_polys], geo); lod2_hull = trimesh.Trimesh(geo.L_nach_sfm(mL.vertices), mL.faces, process=False)
    if flaeche == "stl":
        if stl_m is None: raise SystemExit("kein STL")
        mesh = stl_m
    elif flaeche == "netz":
        if not a.netz or lod2_hull is None: raise SystemExit("--flaeche netz braucht --netz und LoD2/Georef")
        nm = trimesh.load(a.netz, force="mesh"); mesh, quelle_tri = netz_mit_lod2(nm, lod2_hull)
    else:
        if lod2_hull is None: raise SystemExit("--flaeche lod2 braucht LoD2")
        mesh = lod2_hull; hinweise.append("LoD2-Huelle: keine Aufbauten/Erker/Arkaden - Luecken dort unsichtbar")
    mesh, quelle_tri, nb_ = ohne_bodenflaeche(mesh, zg, quelle_tri); log(f"Bodenflaeche ausgenommen: {nb_} Dreiecke")
    occ = None
    if geo is not None and nachbar:
        mn = lod2_mesh_L(nachbar, geo); occ = trimesh.Trimesh(geo.L_nach_sfm(mn.vertices), mn.faces, process=False); log(f"Nachbarn (Verdecker): {len(occ.faces)} Dreiecke")
    # ---- Sperrflaeche (Grundriss + Nachbarn)
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    sp = []
    s0 = schnitt_polygon(mesh, zg + 1.5)
    if s0 is not None: sp.append(s0)
    if geo is not None:
        for polys in ([ziel_polys] if ziel_polys else []) + list(nachbar):
            for t, P in polys:
                if t == "GroundSurface":
                    q = Polygon(geo.L_nach_sfm(geo.utm_nach_L(P[:, :2]))[:, :2]).buffer(0)
                    if q.area > 0.05: sp.append(q)
    sperre = unary_union(sp) if sp else None
    wolke = wolke_laden(a.wolke) if a.wolke else None
    teil_label = teil_namen = None
    td = a.teile_dir            # Export der Bauteile (BAUTEILE_AUS-Ordner des Generators, mm, gleicher Rahmen wie das STL); ohne: keine Bauteilnamen
    if td and os.path.isdir(td) and flaeche == "stl":
        # Teile liegen im selben Rahmen wie die Flaeche (STL mm * skala); Dreiecksmitten der Originalflaeche
        teil_label, teil_namen = teile_zuordnen(mesh.triangles_center, td, skala, np.zeros(3))
    cams_info = dict(n_geladen=n0, n_verwendet=len(cams), quellen=sorted({c["quelle"] for c in cams}))
    erg = analysiere(np.asarray(mesh.vertices), np.asarray(mesh.faces), quelle_tri, occ, cams, zg, geo, wolke, optionen=dict(kontrolle=a.kontrolle, durchgang2=not a.kontrolle, max_stand=a.max_standpunkte, cache=os.path.join(aus, "cache_sicht.npz")), aus=aus, log=log, freie_flaechen=sperre)
    out = schreibe(erg, aus, geo, cams_info, dict(objekt=a.objekt, flaeche=flaeche, hinweise=hinweise, vorschau=not a.keine_vorschau, cams=cams), teil_label, teil_namen, mesh, quelle_tri, log=log)
    import torch
    log(f"FERTIG {time.time() - t0:.0f} s, VRAM max {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB; {len(out['flecken'])} Flecken, {len(out['standpunkte'])} Standpunkte; {aus}")
    return out


if __name__ == "__main__":
    main()
