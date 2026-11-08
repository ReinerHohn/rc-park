#!/usr/bin/env python3
"""saeulen_schliessen.py - GENERISCH: schwebende Saeulen/Pfeiler/Stuetzen eines Netzes bis zum Boden verlaengern (Nutzerfund 6.11.: Saeulen abgeschnitten).
Regel (Statik, kein Objektwissen): Ein Querschnitt, unter dem im naechsten tieferen Horizontalschnitt NICHTS liegt, schwebt -> senkrechtes Prisma bis zum Boden darunter.
Wand ueber einem Bogen schwebt NICHT (darunter liegen die Pfeiler); ein abgeschnittener Pfeiler schon.
Alle Masse aus den Daten: Schichtabstand = Netzhoehe/--schichten, Rauschfilter = 1 Schichtabstand (Oeffnen der Polygone, entfernt Fahnen/Keile), Boden = Anker 'boden' (DGM1) aus --anker, sonst
Perzentile aus Netz+Wolke. Netz-STL in mm (Massstab --massstab, Standard 87).
  venv-o3d/bin/python tools/saeulen_schliessen.py --stl in.stl --aus out.stl [--wolke dicht_alle_modell.npy] [--schichten 80]
Kein Sollwert wird gelockert; Pruefung: foto_diff (kosten_lr) darf nicht schlechter werden, Schnittbild ansehen."""
import argparse, numpy as np, trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
ap = argparse.ArgumentParser(); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--wolke"); ap.add_argument("--anker", help="anker3d.json: Boden = Mittel der z-Werte aller Anker mit 'boden' im Namen (DGM1, amtlich)")
ap.add_argument("--schichten", type=int, default=80); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--lauf", type=int, default=2, help="Stuetzbeweis: so viele Schichten lueckenlos unter dem Schnitt muessen Wolkenpunkte im Umriss (+1 Schicht) haben"); ap.add_argument("--nah", type=float, default=0.0, help="Keil-Filter (VERSUCH, standardmaessig aus: entfernt auch echte duenne Flaechen wie Bogenlaibungen): Umkreis um verlaengerte Saeulen (m)"); ap.add_argument("--profil", default="eigen", choices=["eigen", "median"], help="median: alle Pfeiler gleiches Profil"); ap.add_argument("--breiten", help="Breite je Saeule in m (nach x sortiert, kommagetrennt) statt Median; bei --profil median"); ap.add_argument("--info", help="JSON: Mitte/Drehung/Profil je Saeule"); ap.add_argument("--frei", type=int, default=3); ap.add_argument("--ueberlapp", type=float, default=0.1)
a = ap.parse_args(); k = a.massstab / 1000.0
m = trimesh.load(a.stl); m.apply_scale(k); zlo, zhi = m.bounds[0][2], m.bounds[1][2]; dz = (zhi - zlo) / a.schichten
X = np.load(a.wolke)[:, :3] if a.wolke else None
from scipy.spatial import cKDTree
def polys(z):
    sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None: return [], None
    p2, T = sec.to_2D(); out = []; from shapely.affinity import translate
    for p in p2.polygons_full:
        p = translate(p, T[0, 3], T[1, 3])                      # gemeinsamer Weltrahmen (to_2D verschiebt je Schicht)
        q = p.buffer(-dz / 2).buffer(dz / 2)                    # Rauschfilter: Fahnen/Keile < 1 Schichtabstand verschwinden
        out += [g for g in (q.geoms if hasattr(q, "geoms") else [q]) if g.area > dz * dz]
    return out, T
ref = np.vstack([m.vertices] + ([X] if X is not None else [])); baum = cKDTree(ref[:, :2]) if True else None
rad = 0.2 * float(np.ptp(m.vertices[:, :2], axis=0).max())      # Boden = flache Flaeche unter dem Gebaeude: niedrige Perzentile in 20 % der Gebaeudebreite (Daten, kein Festwert)
import json
GZ = None
if a.anker:
    _z = [(v['xyz'] if isinstance(v, dict) else v)[2] for kk, v in json.load(open(a.anker))['anker'].items() if 'boden' in kk]; GZ = float(np.mean(_z)) if _z else None
def boden(g, T):
    if GZ is not None: return GZ
    idx = baum.query_ball_point(np.array(g.centroid.coords[0]), r=rad)
    return float(np.percentile(ref[idx, 2], 3)) if len(idx) > 50 else zlo
teile = [m]; n = 0; z_prev = None; spuren = []; spalten = []
for i in range(1, a.schichten):
    z = zlo + i * dz; P, T = polys(z)
    if i == 1 or not P: z_prev = None if not P else (P, T); continue
    if z_prev is None: z_prev = (P, T); continue
    Pu, Tu = polys(z - dz)                                       # Schicht darunter im selben 2D-Rahmen? -> beide Rahmen gleich (Ebenen parallel, to_2D ohne Rotation)
    U = unary_union(Pu) if Pu else None
    for g in P:
        if U is not None and g.intersection(U).area > a.ueberlapp * g.area: continue
        zg = min(boden(g, T), z - dz)
        if X is not None:                                            # Wolke muss die Saeule unter dem Schnitt stuetzen (sonst Gewoelbe/Erker/Vordach = darf schweben)
            gb = g.buffer(dz); lauf = 0; xs = X[(X[:, 0] > gb.bounds[0]) & (X[:, 0] < gb.bounds[2]) & (X[:, 1] > gb.bounds[1]) & (X[:, 1] < gb.bounds[3])]
            from shapely import contains_xy
            xs = xs[contains_xy(gb, xs[:, 0], xs[:, 1])]
            for j in range(1, int((z - zg) / dz)):
                if ((xs[:, 2] > z - (j + 1) * dz) & (xs[:, 2] <= z - j * dz)).sum() >= 3: lauf += 1
                else: break
            # Freistand-Beweis: Saeule steht frei, wenn in >= --frei von 8 Sektoren rund um sie (Ring 0,3..0,9 m) in der Hoehe der Stuetzschichten KEINE Wolke liegt (Wand ringsum = eingebettet, kein Pfeiler)
            cx, cy = g.centroid.coords[0]; rr = np.sqrt(g.area / np.pi); sel = (xs[:, 2] < z) & (xs[:, 2] > z - max(lauf, 1) * dz)
            Xr = X[(np.abs(X[:, 0] - cx) < rr + 1) & (np.abs(X[:, 1] - cy) < rr + 1) & (X[:, 2] < z) & (X[:, 2] > z - max(lauf, 1) * dz)]
            rho = np.hypot(Xr[:, 0] - cx, Xr[:, 1] - cy); ring = (rho > rr + 0.3) & (rho < rr + 0.9); sek = np.floor((np.arctan2(Xr[ring, 1] - cy, Xr[ring, 0] - cx) + np.pi) / (np.pi / 4)).astype(int) % 8
            frei = 8 - len({q for q in sek if (sek == q).sum() >= 3})
            if lauf >= a.lauf and frei < a.frei: print("  (eingebettet, %d/8 Sektoren frei: Flaeche %.2f m2 Mitte %s Unterkante %.2f -> kein Pfeiler)" % (frei, g.area, np.round(g.centroid.coords[0], 1), z)); continue
            if lauf < a.lauf: print("  (kein Stuetzbeweis in der Wolke: Flaeche %.2f m2 Mitte %s Unterkante %.2f -> bleibt schwebend)" % (g.area, np.round(g.centroid.coords[0], 1), z)); continue
        if z - zg < 2 * dz: continue
        spalten.append((g, z, zg)); n += 1; spuren.append((g, z))
        print("schwebende Saeule: Flaeche %.2f m2, Mitte %s, Unterkante %.2f -> Boden %.2f" % (g.area, np.round(g.centroid.coords[0], 2), z, zg))
# Pfeilerprofil: alle verlaengerten Saeulen bekommen DASSELBE Profil (Mediane der Mindest-Drehrechtecke aller Saeulen), Mitte und Drehung je Saeule (Nutzerfund: Balken ungleich dick)
def rechteck(g):
    r = g.minimum_rotated_rectangle; c = np.array(r.exterior.coords)[:4]; e1 = c[1] - c[0]; e2 = c[2] - c[1]
    if np.linalg.norm(e1) < np.linalg.norm(e2): e1, e2 = e2, e1
    return np.linalg.norm(e1), np.linalg.norm(e2), np.arctan2(e1[1], e1[0]), np.array(g.centroid.coords[0])
if spalten:
    ab = [rechteck(g) for g, _, _ in spalten]; W = float(np.median([x[0] for x in ab])); D = float(np.median([x[1] for x in ab]))
    print("Profil (Median): %.2f x %.2f m; Streuung vorher Breite %.2f..%.2f" % (W, D, min(x[0] for x in ab), max(x[0] for x in ab)))
    if a.profil == "median":      # Ausreisser (Breite > 1,8 x Median) sind keine Pfeiler der Reihe (z.B. Wandstueck) -> verwerfen
        gut = [i for i, x in enumerate(ab) if x[0] <= 1.8 * W]; print("verworfen als Ausreisser:", [(round(ab[i][3][0], 1), round(ab[i][3][1], 1), round(ab[i][0], 2)) for i in range(len(ab)) if i not in gut]); spalten = [spalten[i] for i in gut]; ab = [ab[i] for i in gut]
if spalten:
    order = sorted(range(len(spalten)), key=lambda i: ab[i][3][0]); spalten = [spalten[i] for i in order]; ab = [ab[i] for i in order]
    if a.info: json.dump([dict(x=float(c[0]), y=float(c[1]), ang=float(ang), w=float(w), d=float(d), z_schnitt=float(z), z_boden=float(zg)) for (g, z, zg), (w, d, ang, c) in zip(spalten, ab)], open(a.info, "w"), indent=1)
BR = [float(x) for x in a.breiten.split(",")] if a.breiten else None
for ii, ((g, z, zg), (w, d, ang, c)) in enumerate(zip(spalten, ab if spalten else [])):
    if a.profil == "median":
        Wi = BR[ii] if BR else W
        from shapely.geometry import box; from shapely.affinity import rotate, translate
        g = translate(rotate(box(-Wi / 2, -D / 2, Wi / 2, D / 2), ang, origin=(0, 0), use_radians=True), c[0], c[1])
    pr = trimesh.creation.extrude_polygon(g, z - zg + dz); pr.apply_translation([0, 0, zg]); teile.append(pr)
# Keile/Fahnen am Fuss: Dreiecke unter der Schnitthoehe einer verlaengerten Saeule und nahe ihr (< --nah m), die in ihrer Schicht ausserhalb aller GEOEFFNETEN Querschnitte liegen (duenner als 1 Schicht), entfernen
if spuren and a.nah > 0:
    zc = max(zz for _, zz in spuren); nahzone = unary_union([g.buffer(a.nah) for g, _ in spuren]); Fc = m.vertices[m.faces].mean(1); weg = np.zeros(len(Fc), bool)
    from shapely import contains_xy
    for i in range(0, int((zc - zlo) / dz) + 1):
        zl = zlo + i * dz; kz = (Fc[:, 2] >= zl) & (Fc[:, 2] < zl + dz) & (Fc[:, 2] < zc)
        kz &= contains_xy(nahzone, Fc[:, 0], Fc[:, 1])
        if not kz.any(): continue
        Pz, _ = polys(zl + dz / 2); U = unary_union([q.buffer(dz) for q in Pz]) if Pz else None
        weg[kz] = True if U is None else ~contains_xy(U, Fc[kz, 0], Fc[kz, 1])
    print("Keil-Dreiecke entfernt:", int(weg.sum()), "von", len(Fc)); teile[0] = trimesh.Trimesh(m.vertices, m.faces[~weg], process=False)
r = trimesh.util.concatenate(teile); r.apply_scale(1 / k); r.export(a.aus); print("Prismen:", n)
