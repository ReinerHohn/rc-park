#!/usr/bin/env python3
"""test_rund_eigenverdeckung.py - Verdeckungspruefung in tools/rund_aus_umriss.py ignoriert das VORMODELL des gemessenen Rundkoerpers (23.11.2026).
Befund Kettenlauf 1122p (Schwabentor Treppentuermchen r 2,09 statt ~1,56): das Modell-STL enthielt den Rundkoerper aus dem Vorlauf (zu dick, versetzt); die
Umrisspunkte des Startkreises lagen darin -> 60 % der Beobachtungen als 'verdeckt' verworfen, es blieben Blicke ueber die Hauptturmkante (zirkulaere Messung).
Synthetisch: Hauptkoerper (Quader) + angebauter Zylinder (Vormodell r 2,1, versetzt). Soll:
 1. Umrisspunkt des Startkreises IM Vormodell: ohne eigen verdeckt (alter Fehler), mit eigen NICHT verdeckt.
 2. Hauptkoerper zwischen Kamera und Umrisspunkt: bleibt verdeckt (auch mit eigen; die angrenzende Wand ist kein Eigenkoerper).
 3. Rot-Probe: Kamera hinter dem Hauptkoerper, Strahl streift ihn nur dicht neben dem Zylinder -> verdeckt.
 4. Kegeldach des Vormodells (ueber dem Profil) zaehlt ebenfalls als eigen."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trimesh, rund_aus_umriss as RU

haupt = trimesh.creation.box(extents=[10, 10, 30]); haupt.apply_translation([0, -5, 15])          # Hauptturm: x -5..5, y -10..0, z 0..30
zyl = trimesh.creation.cylinder(radius=2.1, height=12, sections=48); zyl.apply_translation([0.5, 1.2, 6])   # Vormodell Tuermchen (zu dick, versetzt), z 0..12
kegel = trimesh.creation.cone(radius=2.3, height=3.0, sections=48); kegel.apply_translation([0.5, 1.2, 12])
m = trimesh.util.concatenate([haupt, zyl, kegel]); inter = m.ray; nrm = np.asarray(m.face_normals)
H = dict(kasten=[-2, -1, 0.0, 3, 3.5, 12.0], kreis=dict(x=0.5, y=1.2, r=2.1), profil=[[z, 2.1, 9] for z in np.arange(0.25, 12, 0.5)],
         kreis_wolke=dict(x=0.0, y=1.5, r=1.6), profil_wolke=None)
eig = RU.eigenkoerper(H)
x0, y0, r0 = 0.0, 1.5, 1.6                                                       # Startkreis (Wolke, ~wahr)
fehler = []
# 1. Kamera im Norden: Umrisspunkt des Startkreises (+8 %) liegt im zu dicken Vormodell
C = np.array([0.0, 25.0, 2.0]); T, _, _ = RU.tangenten(np.array([[x0, y0]]), np.array([r0 * 1.08 + 0.05]), C[:2])
X = np.array([[T[s, 0, 0], T[s, 0, 1], 5.0] for s in (0, 1)])
alt = RU.verdeckt_strahlen(inter, nrm, C, X); neu = RU.verdeckt_strahlen(inter, nrm, C, X, eig)
if not alt.any(): fehler.append(f"Testaufbau: Vormodell verdeckt den Startumriss ohne eigen nicht ({alt})")
if neu.any(): fehler.append(f"1: Vormodell desselben Koerpers zaehlt noch als Verdecker ({neu})")
# 2. Kamera im Sueden hinter dem Hauptkoerper: Umrisspunkte hinter dem Quader
C2 = np.array([0.5, -30.0, 3.0]); T2, _, _ = RU.tangenten(np.array([[x0, y0]]), np.array([r0 * 1.08 + 0.05]), C2[:2])
X2 = np.array([[T2[s, 0, 0], T2[s, 0, 1], 5.0] for s in (0, 1)]); v2 = RU.verdeckt_strahlen(inter, nrm, C2, X2, eig)
if not v2.all(): fehler.append(f"2: Hauptkoerper vor dem Umriss nicht als Verdecker erkannt ({v2})")
# 3. Rot-Probe: schraeg von Suedost, Strahl schneidet die Hauptkoerper-Ecke knapp
C3 = np.array([12.0, -12.0, 3.0]); X3 = np.array([[4.0, 0.3, 5.0]]); v3 = RU.verdeckt_strahlen(inter, nrm, C3, X3, eig)
if not v3[0]: fehler.append("3: Strahl durch die Hauptkoerper-Ecke nicht verdeckt")
# 4. Kegeldach des Vormodells: Punkt hinter dem Kegel (von Norden, oben) wird nicht durch den eigenen Kegel verdeckt
C4 = np.array([20.0, 1.2, 13.0]); X4 = np.array([[-3.0, 1.2, 13.0]]); v4a = RU.verdeckt_strahlen(inter, nrm, C4, X4); v4 = RU.verdeckt_strahlen(inter, nrm, C4, X4, eig)
if not v4a[0] or v4[0]: fehler.append(f"4: Kegeldach des Vormodells (ohne eigen {v4a[0]}, mit eigen {v4[0]}; Soll True/False)")
# 4b. Innenkarte: Punkt im Hauptkoerper (dort fehlt dessen Wand im vereinigten STL nicht - hier Einzelkoerper) innen, Punkt nur im Vormodell und Punkt frei nicht innen
IK = RU.Innenkarte(inter, nrm, x0, y0, 3.5, [3.0, 5.0, 7.0], eig)
ik = IK.innen(np.array([[0.0, -0.6, 5.0], [0.0, 2.8, 5.0], [3.0, 2.0, 5.0], [-2.5, -0.5, 5.0]]))
if list(ik) != [True, False, False, True]: fehler.append(f"4b: Innenkarte {list(ik)} (Soll im Hauptkoerper True, im Vormodell False, frei False, Hauptkoerper seitlich True)")
# 5. Bildprobe wie Schwabentor 114101: weisser Zylinder r 1,5 an einen weiss verputzten Hauptkoerper angebaut; an dessen Ecke dunkle Eckquader (harte Kanten). Der wahre
#    Umriss vor der Wand ist kaum sichtbar (Putz vor Putz), Quaderkanten DAHINTER (synthetisch nicht stark genug, um ohne
#    Sperre falsch zu messen - Rot-Probe darum in 6 direkt). Mit Sperrkarte (STL = Hauptkoerper + zu dickes Vormodell, vereinigt) soll r stimmen.
import cv2, flaeche_ortho as FO
R5, X5, Y5, ZT5 = 1.5, 0.0, 0.0, 9.0
haus = trimesh.creation.box(extents=[7.2, 6.0, 16.0]); haus.apply_translation([-1.0, -4.0, 8.0])       # x -4,6..2,6 / y -7..-1 : Zylinder ragt nach Norden heraus
wahr = trimesh.creation.cylinder(radius=R5, height=ZT5, sections=96); wahr.apply_translation([X5, Y5, ZT5 / 2])
szene = trimesh.util.concatenate([haus, wahr]); nh = len(haus.faces); rs_ = szene.ray
vorm = trimesh.creation.cylinder(radius=2.0, height=ZT5, sections=48); vorm.apply_translation([0.3, 0.2, ZT5 / 2]); stl = haus.union(vorm)   # wie das Generator-STL: vereinigt, Hauptwand im Vormodell fehlt
W5, H5, F5 = 360, 480, 420.0; rng = np.random.default_rng(5); bilder = []
H5d = dict(kasten=[-2, -2, 0.0, 2.5, 2.5, ZT5], kreis=dict(x=0.3, y=0.2, r=2.0), profil=None, kreis_wolke=None)
eig5 = RU.eigenkoerper(H5d); IK5 = RU.Innenkarte(stl.ray, np.asarray(stl.face_normals), X5 + 0.25, Y5 + 0.2, 3.3, list(np.arange(0.75, ZT5, 0.5)), eig5)
for i, az in enumerate(np.radians(list(np.linspace(10, 80, 9)) + list(np.linspace(100, 170, 5)) + [-60, -30, 200])):
    d = 12 + 2 * (i % 3); C = np.array([X5 + d * math.cos(az), Y5 + d * math.sin(az), 1.6 + (i % 3)]); ziel = np.array([X5, Y5, 4.5]); zv = ziel - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv]); c = dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=(-Rm @ C).tolist(), f_px=F5, cx=W5 / 2, cy=H5 / 2, k1=0.0)
    u, v = np.meshgrid(np.arange(W5) + 0.5, np.arange(H5) + 0.5); dw = np.stack([(u - W5 / 2) / F5, (v - H5 / 2) / F5, np.ones_like(u)], -1).reshape(-1, 3) @ Rm
    dw /= np.linalg.norm(dw, axis=1)[:, None]; tri, ri, loc = rs_.intersects_id(np.broadcast_to(C, dw.shape), dw, multiple_hits=False, return_locations=True)
    img = (90 + 50 * (np.floor(u / 23) % 2) + 30 * np.sin(v / 17)).ravel()
    st = tri < nh; L = loc[st]; quader = (L[:, 0] > 1.9) & (((np.floor(L[:, 2] / 0.6)) % 2 == 0) | (L[:, 0] > 2.25))                  # Eckquader an der Ostecke
    img[ri[st]] = np.where(quader, 60, 222); img[ri[~st]] = 214 - 6 * ((np.floor(loc[~st][:, 2] / 0.5) % 2))                         # Putz vor Putz: Umriss schwach
    im = np.clip(img.reshape(H5, W5) + rng.normal(0, 5, (H5, W5)), 0, 255).astype(np.uint8)
    B = RU.Bild(c, im, (0, 0, W5, H5), FO.projektion); B.Cxy = C[:2]; B.C = C; B.sperre = RU.Sperrkarte(stl.ray, np.asarray(stl.face_normals), c, C, (0, 0, W5, H5), eig5); B.sperre.innen = IK5; B.hinter_nah = RU.HINTERGRUND_NAH * 1.8; bilder.append(B)
zs5 = list(np.round(np.arange(0.75, ZT5, 0.5), 2)); start5 = (X5 + 0.25, Y5 + 0.2, 1.8)
U5 = RU.vermessen(bilder, start5, zs5)
for B in bilder: B.sperre = None
U5o = RU.vermessen(bilder, start5, zs5)
# 6. Hintergrund-Sperre direkt: Umrisspunkt vor der Hauswand (1 m dahinter) = naher Hintergrund, vor dem Himmel nicht (Rot-Probe: nah 0 m sperrt nichts)
c6 = None
for B in bilder:
    if abs(math.degrees(math.atan2(B.Cxy[1], B.Cxy[0])) - 45) < 6: c6 = B
sk6 = RU.Sperrkarte(stl.ray, np.asarray(stl.face_normals), c6.c, c6.C, (0, 0, W5, H5), eig5)
Xw = np.array([[2.45, -0.5, 4.0]]); Nw = np.array([[1.0, 0.0, 0.0]]); Xs = np.array([[0.0, 0.0, 14.0]]); Ns = np.array([[0.0, 0.0, 1.0]])
hw, hs, h0 = sk6.hintergrund_nah(Xw, Nw, 3.6)[0], sk6.hintergrund_nah(Xs, Ns, 3.6)[0], sk6.hintergrund_nah(Xw, Nw, 0.0)[0]
if not (hw and not hs and not h0): fehler.append(f"6: Hintergrund-Sperre vor Wand {hw} (Soll True), vor Himmel {hs} (Soll False), nah=0 {h0} (Soll False)")
if not (U5 and abs(U5["r"] - R5) <= 0.05 and math.hypot(U5["x"] - X5, U5["y"] - Y5) <= 0.08):
    fehler.append(f"5: mit Sperrkarte r {U5 and U5['r']} Mitte {U5 and (U5['x'], U5['y'])} (Soll {R5}, {X5}/{Y5})")
print(f"  Bildprobe angebauter Zylinder: mit Sperrkarte r {U5['r']} Mitte {U5['x']}/{U5['y']}; ohne r {U5o['r']} Mitte {U5o['x']}/{U5o['y']} (Soll r {R5}, Mitte {X5}/{Y5})")
print(("OK" if not fehler else "FEHLER") + " rund_eigenverdeckung: Vormodell kein Verdecker, Hauptkoerper bleibt Verdecker" + ("" if not fehler else ": " + "; ".join(fehler)))
sys.exit(0 if not fehler else 1)
