#!/usr/bin/env python3
"""selbstbau_verdecker.py - Verdecker-Modell fuer MESSUNGEN ohne selbst erzeugte Bauteile (21.11.2026, MESSFEHLER zirkulaere Messung).

Befund Schwabentor-1120 (21.11.): tools/fassade_ortho.py rechnete die Uneinigkeitskarte uneinig_f00.png mit dem schon GEBAUTEN Modell als Verdecker/Flaeche.
Das Vordach (selbst gebaut aus audit/vorbauten_auto.json) lag als vorderste Flaeche vor der Wand: die Fotos sahen dort dieselbe Dachflaeche, die Karte wurde
flach und tools/vorbauten_bauplan.py fiel vom gemessenen Wandanschluss 19,39 auf die ANNAHME 16,74 zurueck. Das Modell loescht seinen eigenen Beleg.

Regel: Messungen, die das eigene Modell als Verdecker oder Messflaeche nutzen, rechnen gegen das Modell OHNE die Bauteile, die aus genau solchen Messungen
erzeugt wurden (Vorbauten/Galerie/Vordach/Streben aus audit/vorbauten_auto.json). Entfernt werden Dreiecke, deren Schwerpunkt im Raum einer Vorbau-Gruppe
liegt (u-Bereich +-0,3 m, z vom tiefsten Fuss bis Anschluss/Dach +0,3 m) UND mehr als --w_min m vor der vorderen von gemessener Wand und LoD2-Ebene steht.
Wand und Wandrelief bleiben: Messung Schwabentor f00 (w_wand -0,15): Modell OHNE Vorbauten hat im Vorbau-Raum 50 m2 Relief bis 0,15 m vor der LoD2-Ebene und nur 1,5 m2 davor;
ab LoD2 + 0,15 m entfernt die Regel 129 m2 Vorbau/Vordach (Modell mit) - eine Schwelle ab der gemessenen Wand (0,15) haette 50 m2 echtes Wandrelief mit entfernt.

Aufruf (Geschwister-Stufen, die eine STL-Datei erwarten):
  tools/py tools/selbstbau_verdecker.py <objekt.json> <modell.stl> <aus.stl> [--w_min 0.15]
Bibliothek: boxen = selbstbau_boxen(objekt_json); mesh2, n = ohne_selbstbau(mesh_in_metern, boxen)
"""
import os, sys, json, argparse
import numpy as np


def selbstbau_boxen(objekt, rand_u=0.3, rand_z=0.3):
    """Raumkaesten der selbst gebauten Vorbauten (audit/vorbauten_auto.json neben objekt.json), Modellrahmen in Metern. [] ohne Datei."""
    p = os.path.join(os.path.dirname(os.path.abspath(objekt)), "audit", "vorbauten_auto.json")
    if not os.path.exists(p): return []
    J = json.load(open(p)); B = []
    for F in J.get("fassaden", []):
        o, d, n = (np.array(F[k], float)[:2] for k in ("o", "d", "n")); ww = float(F.get("w_wand", 0.0))
        for g in F.get("gruppen", []):
            G = g.get("galerie") or {}; V = G.get("vordach") or {}; KM = g.get("kanten_mass") or {}
            zu = [g.get("z0"), G.get("z_fuss"), (KM.get("streben") or {}).get("z_fuss"), (KM.get("kasten") or {}).get("z_unten"), (KM.get("konsolen") or {}).get("z_unten")]
            zo = [g.get("z1"), V.get("z_anschluss"), G.get("z_dach"), (KM.get("kasten") or {}).get("z_oben")]
            uu = [g.get("u0"), g.get("u1"), V.get("u0"), V.get("u1"), (KM.get("kasten") or {}).get("u0"), (KM.get("kasten") or {}).get("u1")]
            zu, zo, uu = [float(x) for x in zu if x is not None], [float(x) for x in zo if x is not None], [float(x) for x in uu if x is not None]
            if not (zu and zo and uu): continue
            B.append(dict(fassade=F.get("id"), o=o, d=d, n=n, w_wand=ww, u0=min(uu) - rand_u, u1=max(uu) + rand_u, z0=min(zu) - rand_z, z1=max(zo) + rand_z))
    return B


def ohne_selbstbau(mesh, boxen, w_min=0.15, w_max=6.0, flicken=0.1):
    """mesh (trimesh, Meter, Modellrahmen) ohne die Dreiecke selbst gebauter Vorbauten. Liefert (neues mesh, Zahl entfernter Dreiecke).
    Die Vereinigung im Generator hat die Wand HINTER dem Vorbau weggeschnitten; ohne Flicken saehe die Messung dort in den Hohlraum (Probe Schwabentor f00:
    Relief -0,60 m bei z 18-19). Darum wird jede 'flicken'-Zelle, die ein entferntes Dreieck bedeckt, als Flaeche in der GEMESSENEN Wandebene (w_wand) geschlossen;
    wo die echte Wandflaeche noch steht, liegt sie davor und bleibt die vorderste."""
    if not boxen or len(mesh.faces) == 0: return mesh, 0
    import trimesh, cv2
    c = np.asarray(mesh.triangles_center, float); weg = np.zeros(len(c), bool); T = np.asarray(mesh.triangles, float); fl = []
    for b in boxen:
        r = c[:, :2] - b["o"]; u = r @ b["d"]; w = r @ b["n"] - max(b["w_wand"], 0.0)      # ab der VORDEREN von gemessener Wand und LoD2-Ebene
        wb = (u >= b["u0"]) & (u <= b["u1"]) & (c[:, 2] >= b["z0"]) & (c[:, 2] <= b["z1"]) & (w > w_min) & (w < w_max); weg |= wb
        if not wb.any() or not flicken: continue
        nu, nz = int(np.ceil((b["u1"] - b["u0"]) / flicken)), int(np.ceil((b["z1"] - b["z0"]) / flicken)); M_ = np.zeros((nz, nu), np.uint8)
        for t in T[wb]:
            uz = np.c_[((t[:, :2] - b["o"]) @ b["d"] - b["u0"]) / flicken, (b["z1"] - t[:, 2]) / flicken]
            cv2.fillPoly(M_, [np.round(uz).astype(np.int32)], 1)
        ww = b["w_wand"] - 0.01; o3 = np.r_[b["o"], 0.0]; d3 = np.r_[b["d"], 0.0]; n3 = np.r_[b["n"], 0.0]
        for i in range(nz):
            j = 0
            while j < nu:
                if not M_[i, j]: j += 1; continue
                e = j
                while e + 1 < nu and M_[i, e + 1]: e += 1
                ua, ub = b["u0"] + j * flicken, b["u0"] + (e + 1) * flicken; zo, zu = b["z1"] - i * flicken, b["z1"] - (i + 1) * flicken
                P = [o3 + u_ * d3 + ww * n3 + np.r_[0, 0, z_] for u_, z_ in ((ua, zu), (ub, zu), (ub, zo), (ua, zo))]
                fl.append(trimesh.Trimesh(vertices=np.array(P), faces=[[0, 1, 2], [0, 2, 3]], process=False)); j = e + 1
    if not weg.any(): return mesh, 0
    m2 = mesh.copy(); m2.update_faces(~weg); m2.remove_unreferenced_vertices()
    if fl: m2 = trimesh.util.concatenate([m2] + fl)
    return m2, int(weg.sum())


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("stl"); ap.add_argument("aus"); ap.add_argument("--w_min", type=float, default=0.15)
    a = ap.parse_args(argv)
    import trimesh
    obj = json.load(open(a.objekt)); sk = float(obj.get("stl_massstab", 87)) / 1000.0
    m = trimesh.load(a.stl); m.apply_scale(sk); B = selbstbau_boxen(a.objekt); m2, n = ohne_selbstbau(m, B, a.w_min); m2.apply_scale(1.0 / sk); m2.export(a.aus)
    print(f"{len(B)} Vorbau-Gruppen, {n} Dreiecke entfernt -> {a.aus}"); return 0


if __name__ == "__main__":
    sys.exit(main())
