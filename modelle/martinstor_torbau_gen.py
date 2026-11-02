#!/usr/bin/env python3
"""martinstor_torbau_gen.py - Nordfront des 1901er Torbaus (McDonald's) westlich des Martinstors, parametrisch (manifold3d).

Masse als DATEN: modelle/martinstor/torbau/torbau_masse.json (Quelle je Mass: dichte Fotowolke Nord, Fotos 003/089, LoD2).
Was dieses Modell ist: der FRONTBLOCK (Durchgangsbogen, drei Fensterreihen, Schweifgiebel; Messprotokolle M-089-001..007) im Modellsystem des Turms;
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
YW, YO, XF, T = _M["FRONT_Y_WEST"], _M["FRONT_Y_OST"], _M["FRONT_X"], _M["TIEFE"]; XR = XF + T          # YW = Erdgeschoss-Westkante (aeusserer Bogenpfeiler)
YWO = _M["FRONT_Y_WEST_OG"]; EGX, EGH = _M["EG_RUECKSPRUNG_X"], _M["EG_HOEHE"]
BYM, BB, BSCH, BK = _M["BOGEN_Y_MITTE"], _M["BOGEN_BREITE"], _M["BOGEN_SCHEITEL"], _M["BOGEN_KAEMPFER"]
XW, EY0, EY1, EZ0, EZ1 = _M["FRONT_X_WAND"], _M["ERKER_Y0"], _M["ERKER_Y1"], _M["ERKER_Z0"], _M["ERKER_Z1"]
ZF, YFIRST, ZT, GH = _M["GIEBEL_FIRST"], _M["GIEBEL_FIRST_Y"], _M["TRAUFE"], _M["GIEBEL_HALB_FUSS"]
ELEMENTE = []
def beleg(element, quelle, **masse): ELEMENTE.append(dict(seite="-x", element=element, quelle=quelle, **masse))

adds, cuts = [], []
# Erdgeschoss: Arkadenzone zurueckgesetzt (Pfeilerfront EGX) bis zum aeusseren Bogenpfeiler YW; Obergeschosse kragen ab EGH vor und enden bei YWO
adds.append(box(EGX, XR, YW, YO, 0.0, EGH))
beleg("Arkadengeschoss (Pfeilerfront zurueckgesetzt)", "Wolke z 5-9,5: Front bei x -5,2..-5,6; Breite y -5,6..-14,7 aus Foto 089 (Bogen 8,0 m aussen, M-089-001)", front_x=EGX, hoehe=EGH, y_west=YW)
adds.append(box(XW, XR, YWO, YO, EGH - 0.02, ZT))
beleg("Obergeschosse (glatte Wand, auf Kragplatte)", "Wolke: Front bei x -5,8 neben dem Erker; Breite 7,06 m aus Foto 089 (M-089-007)", front_x=XW, traufe=ZT, y_west=YWO)
adds.append(box(XF, XR, EY0, EY1, EZ0, EZ1))
beleg("Erker (2 Geschosse, vorkragend)", "Wolke z 10-19: vorderste Front -6,2..-6,4 bei y -10..-7,5; Foto 089 Zoom: Erker 3,2 m breit, z 10,2..17,8", front_x=XF, y0=EY0, y1=EY1, z0=EZ0, z1=EZ1)
# Durchgangsbogen (McDonald's): ELLIPTISCHER Bogen, Spannweite BB, Kaempfer BK, Scheitel BSCH (Foto 089: M-089-002/004/005)
a_y = BB / 2.0; a_z = BSCH - BK
cuts.append(box(EGX - 0.5, EGX + 3.5, BYM - a_y, BYM + a_y, -0.1, BK))
cuts.append(M.cylinder(4.0, 1.0, 1.0, 96).rotate((0, 90, 0)).scale((1.0, a_y, a_z)).translate((EGX - 0.5, BYM, BK)))
beleg("Durchgangsbogen (McDonald's-Bogen, elliptisch)", "Foto 089 Zoom: Spannweite 7,25 m (M-089-002), Scheitel 6,2 m (M-089-004), Kaempfer 3,0 m (M-089-005); rechtes Bogenende verdeckt: ANNAHME symmetrisch", breite=BB, scheitel=BSCH, kaempfer=BK, anzahl=1)
# Fensterreihen: 1./2. OG je 4 (y-Mitten aus Foto 089, Turmkante als Ursprung), Giebelgeschoss 2 symmetrisch zur Giebelachse
def fenster(yc, z0, h, b=0.9, xw=None):
    xw = XF if xw is None else xw; cuts.append(box(xw - 0.1, xw + 0.3, yc - b / 2, yc + b / 2, z0, z0 + h))
for yc in (-7.65, -8.75, -11.25, -12.25): fenster(yc, _M["FENSTER_Z1"], _M["FENSTER_H1"], xw=EGX)      # 1. OG liegt in der zurueckgesetzten Erdgeschosswand (unter der Kragplatte)
beleg("Fenster 1. Obergeschoss (4)", "Foto 089 Zoom: 2+2 Fenster beidseits des Erkers; Hoehe M-089-006 (1,87 m); Breite 0,9 m aus 70 px", reihen=1, je_reihe=4, z=_M["FENSTER_Z1"])
for yc, xw in ((-9.2, XF), (-10.35, XF), (-11.8, XW)): fenster(yc, _M["FENSTER_Z2"], _M["FENSTER_H2"], xw=xw)
beleg("Fenster 2. Obergeschoss (3: 2 im Erker, 1 in der Wand)", "Foto 089 Zoom; Hoehe ANNAHME wie 1. OG", reihen=1, je_reihe=3, z=_M["FENSTER_Z2"])
for dy in (-0.55, 0.55): fenster(YFIRST + dy, _M["FENSTER_Z3"], _M["FENSTER_H3"], b=0.8)
beleg("Fenster Giebelgeschoss (2)", "Foto 089: zwei Fenster unter dem Schweifgiebel, symmetrisch zur Giebelachse (Abstand 1,1 m aus 85 px)", je_reihe=2, z=_M["FENSTER_Z3"])
# Schweifgiebel (Renaissance, Voluten): Profil Halbbreite ueber Hoehe (Foto 089 Zoom: Fuss 5,6 m bei z 17, Hals ~3,3 m bei z 18,7, Kappe ~1,9 m bei z 20), in duennen Scheiben gestuft
prof = [(0.0, GH), (0.4, GH), (1.4, GH - 0.7), (2.2, GH - 1.5), (2.9, 1.35), (3.5, 1.0), (3.9, 0.55), (ZF - ZT, 0.0)]
hz = np.array([ZT + p[0] for p in prof]); hw = np.array([p[1] for p in prof]); N = 24; dz = (ZF - ZT) / N
for i in range(N):
    zl = ZT + i * dz; w = float(np.interp(zl + dz / 2, hz, hw))
    adds.append(box(XF, XF + 0.5, YFIRST - w, YFIRST + w, zl - 0.02, zl + dz))
beleg("Schweifgiebel (Voluten)", "Foto 089/006: Renaissance-Schweifgiebel, Fuss 5,6 m, Hals ~3,3 m, Kappe ~1,9 m; Firsthoehe Wolke 20,7 / Drohne 21,5; Achse y -8,3 aus Wolke (Foto 089 ergaebe -9,2: offener Widerspruch, nicht gemittelt)", first=ZF, traufe=ZT, achse_y=YFIRST)
# Satteldach hinter dem Giebel (Firstlinie laeuft nach Sueden bis XR), Grundbreite = Giebelfuss
pts = [(XF + 0.4, YFIRST - GH, ZT), (XF + 0.4, YFIRST + GH, ZT), (XF + 0.4, YFIRST, ZF - 0.3), (XR, YFIRST - GH, ZT), (XR, YFIRST + GH, ZT), (XR, YFIRST, ZF - 0.3)]
adds.append(M.hull_points(pts))
beleg("Satteldach giebelstaendig", "LoD2 Vorderteil 19,6 m; Firstlinie ANNAHME senkrecht zur Front; Grundbreite = Giebelfuss", first=ZF - 0.3)

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
json.dump([dict(e, seite_name="Nord") for e in ELEMENTE], open(os.path.join(HERE, "martinstor_torbau", "elemente.json"), "w"), indent=1, ensure_ascii=False)
b = np.c_[V.min(0), V.max(0)]; print(f"Torbau-Front: {len(F)} Dreiecke, Genus {model.genus()}, x {b[0,0]:.1f}..{b[0,1]:.1f} y {b[1,0]:.1f}..{b[1,1]:.1f} z {b[2,0]:.1f}..{b[2,1]:.1f} m; {len(ELEMENTE)} Elemente mit Beleg")
