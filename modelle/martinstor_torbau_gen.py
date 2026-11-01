#!/usr/bin/env python3
"""martinstor_torbau_gen.py - Nordfront des 1901er Torbaus (McDonald's) westlich des Martinstors, parametrisch (manifold3d).

Masse als DATEN: modelle/martinstor/torbau/torbau_masse.json (Quelle je Mass: dichte Fotowolke Nord, Fotos 003/089, LoD2).
Was dieses Modell ist: der giebelstaendige FRONTBLOCK (Arkade, zwei Fensterreihen, Staffelgiebel) im Modellsystem des Turms;
der restliche Baukoerper bleibt das LoD2-Massenmodell (torbau_lod2_modell.stl). Was es NICHT ist: ein vermessenes Fassadenmodell -
Fensterzahl, Staffelstufen und Bogenbreite sind ANNAHMEN aus Fotosichtung (so im JSON markiert), Hoehen/Tiefen aus der Wolke.
  SCALE=87 ~/.venvs/rcpark/bin/python modelle/martinstor_torbau_gen.py
Schreibt modelle/martinstor/torbau/torbau_front_modell.stl (m) und modelle/stl/martinstor_torbau_front_1-<SCALE>.stl (mm) + elemente.json.
"""
import os, sys, json, math, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from manifold3d import Manifold as M, OpType
from bauteile import box, lade_masse

HERE = os.path.dirname(os.path.abspath(__file__)); TD = os.path.join(HERE, "martinstor", "torbau")
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
_M = lade_masse(os.path.join(TD, "torbau_masse.json"))
YW, YO, XF, T = _M["FRONT_Y_WEST"], _M["FRONT_Y_OST"], _M["FRONT_X"], _M["TIEFE"]; XR = XF + T
EGX, EGH, SCH = _M["EG_RUECKSPRUNG_X"], _M["EG_HOEHE"], _M["ARKADE_SCHEITEL"]
ZF, YFIRST, ZT, NST = _M["GIEBEL_FIRST"], _M["GIEBEL_FIRST_Y"], _M["TRAUFE"], int(_M["GIEBEL_STUFEN"])
ELEMENTE = []
def beleg(element, quelle, **masse): ELEMENTE.append(dict(seite="-x", element=element, quelle=quelle, **masse))

adds, cuts = [], []
# Erdgeschoss: Arkadenzone zurueckgesetzt (Pfeilerfront EGX), darueber vorkragende Obergeschosse ab EGH bis zur Traufe
adds.append(box(EGX, XR, YW, YO, 0.0, EGH))
beleg("Arkadengeschoss (Pfeilerfront zurueckgesetzt)", "Wolke z 5-9,5: Front bei x -5,2..-5,6, Obergeschosse ab 9,8 m bei -6,3", front_x=EGX, hoehe=EGH)
adds.append(box(XF, XR, YW, YO, EGH - 0.3, ZT))
beleg("Obergeschosse, vorkragend", "Wolke z 10-19: Front -6,1..-6,5", front_x=XF, traufe=ZT)
# Arkadenbogen (McDonald's-Bogen): Durchgang quer durch das Erdgeschoss, Rundbogen
bw = min(2.6, (YO - YW) - 1.0); yc = (YW + YO) / 2; r = bw / 2; zk = SCH - r
cuts.append(box(EGX - 0.5, EGX + 3.5, yc - r, yc + r, -0.1, zk))
cuts.append(M.cylinder(4.0, r, r, 48).rotate((0, 90, 0)).translate((EGX - 0.5, yc, zk)))
beleg("Arkadenbogen (Durchgang)", "Foto 089/003: Korbbogen unter dem Schriftzug; Scheitel ~8,6 m ANNAHME aus Wolke (Oeffnung bis 9,5)", breite=bw, scheitel=SCH, anzahl=1)
# Fensterreihen (je 2, Breite 0,9, Hoehe 1,7, 0,3 m tief)
for z0 in (_M["FENSTER_Z1"], _M["FENSTER_Z2"]):
    for ycw in (yc - 0.85, yc + 0.85):
        cuts.append(box(XF - 0.1, XF + 0.3, ycw - 0.45, ycw + 0.45, z0, z0 + 1.7))
beleg("Fenster 2 Reihen x 2", "Foto 003 (Zahl ANNAHME); Reihenhoehen Wolke/Foto", reihen=2, je_reihe=2)
# Staffelgiebel: Stufen von der Traufe zur Spitze bei YFIRST, Giebelwand 0,5 m dick vorn, dahinter Satteldach (Firstlinie in x)
dz = (ZF - ZT) / NST; wl = (YFIRST - YW); wr = (YO - YFIRST)
for i in range(NST):
    zl, zh = ZT + i * dz, ZT + (i + 1) * dz
    y0 = YW + wl * i / NST; y1 = YO - wr * i / NST
    adds.append(box(XF, XF + 0.5, y0, y1, zl - 0.02, zh))
beleg("Staffelgiebel", "Giebelspitze 20,7 m bei y -8,3 (Wolke); Staffeln je Seite ANNAHME aus Foto 003", first=ZF, traufe=ZT, stufen=NST)
# Satteldach hinter dem Giebel (Firstlinie laeuft nach Sueden bis XR)
pts = [(XF + 0.4, YW, ZT), (XF + 0.4, YO, ZT), (XF + 0.4, YFIRST, ZF - 0.3), (XR, YW, ZT), (XR, YO, ZT), (XR, YFIRST, ZF - 0.3)]
adds.append(M.hull_points(pts))
beleg("Satteldach giebelstaendig", "LoD2 Vorderteil 19,6 m; Firstlinie ANNAHME senkrecht zur Front", first=ZF - 0.3)
# Giebelfenster
cuts.append(box(XF - 0.1, XF + 0.3, YFIRST - 0.3, YFIRST + 0.3, _M["GIEBEL_FENSTER_Z"], _M["GIEBEL_FENSTER_Z"] + 1.0))

body = M.batch_boolean(adds, OpType.Add); model = M.batch_boolean([body] + cuts, OpType.Subtract)
mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64); F = np.asarray(mesh.tri_verts)
def stl_schreiben(pfad, V, F):
    """Binaer-STL ohne Abhaengigkeiten (Normalen aus den Dreiecken)."""
    tri = V[F]; n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"] = n; rec["v"] = tri
    with open(pfad, "wb") as f: f.write(b"rc-park torbau".ljust(80, b"\0")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
stl_schreiben(os.path.join(TD, "torbau_front_modell.stl"), V, F)
stl_schreiben(os.path.join(HERE, "stl", f"martinstor_torbau_front_1-{SCALE:.0f}.stl"), V * K, F)
json.dump(dict(elemente=ELEMENTE, masse=_M), open(os.path.join(TD, "torbau_elemente.json"), "w"), indent=1, ensure_ascii=False)
b = np.c_[V.min(0), V.max(0)]; print(f"Torbau-Front: {len(F)} Dreiecke, Genus {model.genus()}, x {b[0,0]:.1f}..{b[0,1]:.1f} y {b[1,0]:.1f}..{b[1,1]:.1f} z {b[2,0]:.1f}..{b[2,1]:.1f} m; {len(ELEMENTE)} Elemente mit Beleg")
