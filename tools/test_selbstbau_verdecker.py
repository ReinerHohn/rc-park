#!/usr/bin/env python3
"""test_selbstbau_verdecker.py - MESSFEHLER 21.11.2026 (zirkulaere Messung): Messungen gegen das eigene Modell duerfen selbst gebaute Vorbauten nicht als Verdecker nutzen.

Befund: fassade_ortho rechnete uneinig_f00.png mit dem gebauten Vordach als vorderster Flaeche -> Profil flach -> vorbauten_bauplan fiel vom gemessenen
Wandanschluss 19,39 auf die ANNAHME 16,74 zurueck. Prueft (synthetisch, ohne Fotos):
  1. selbstbau_verdecker.ohne_selbstbau entfernt das Vordach (Dreiecke > 0,15 m vor der Wand im Vorbau-Raum), Wand und flaches Wandrelief bleiben.
  2. vorbauten_bauplan.anschluss_aus_uneinig misst die Stufe einer Karte (Dachflaeche uneinig bis z 19,4) und VERWIRFT eine Karte, deren fassaden.json
     verdecker_selbstbau.zustand = 'im_modell' meldet (sonst kaeme die ANNAHME still zurueck bzw. ein zirkulaerer Wert).
  3. fassade_ortho schreibt verdecker_selbstbau in fassaden.json und hat --mit-selbstbau (Quelltextprobe; der volle Lauf braucht Fotos).
"""
import os, sys, json, tempfile
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import trimesh, cv2
from selbstbau_verdecker import selbstbau_boxen, ohne_selbstbau
import vorbauten_bauplan as vb

F = 0
def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1

with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, "audit")); obj = os.path.join(td, "objekt.json"); json.dump(dict(stl_massstab=1000), open(obj, "w"))
    V = dict(fassaden=[dict(id="f00", o=[0, 0, 0], d=[0, 1, 0], n=[1, 0, 0], w_wand=0.0,
                            gruppen=[dict(u0=-3.9, u1=4.58, z0=9.14, z1=19.62, galerie=dict(vordach=dict(z_traufe=16.0, z_anschluss=17.5, u0=-3.9, u1=4.58)))])])
    json.dump(V, open(os.path.join(td, "audit", "vorbauten_auto.json"), "w"))
    wand = trimesh.creation.box(bounds=[[-5, -6, 0], [0, 6, 25]]); relief = trimesh.creation.box(bounds=[[0, -2, 12], [0.08, 2, 14]])       # Wandrelief 8 cm: bleibt
    dach = trimesh.convex.convex_hull(np.array([[x, y, z] for y in (-4.05, 4.73) for x, z in ((-0.1, 17.5), (-0.1, 17.35), (1.3, 16.15), (1.3, 16.0))]))
    m = trimesh.util.concatenate([wand, relief, dach]); B = selbstbau_boxen(obj)
    pruef(len(B) == 1 and B[0]["z1"] >= 17.5 and B[0]["u0"] <= -3.9, f"Vorbau-Raum aus vorbauten_auto.json ({len(B)} Gruppe, z bis {B[0]['z1'] if B else None})")
    m2, n = ohne_selbstbau(m, B); c = m2.triangles_center
    pruef(n > 0 and not ((c[:, 0] > 0.15) & (c[:, 2] > 15.9)).any(), f"Vordach als Verdecker entfernt ({n} Dreiecke)")
    pruef(len(m2.faces) >= len(wand.faces) + len(relief.faces) and (c[:, 0] > 0.05).sum() >= 2, "Wand und flaches Wandrelief bleiben Verdecker")
    fl = (np.abs(c[:, 0] + 0.01) < 1e-6) & (c[:, 2] > 15.9) & (c[:, 2] < 17.6)
    pruef(fl.sum() >= 2 and not ((np.abs(c[:, 0] + 0.01) < 1e-6) & (c[:, 2] < 15.5)).any(), f"Flicken in der gemessenen Wandebene nur hinter dem entfernten Vordach ({fl.sum()} Dreiecke; Generator schneidet die Wand dort weg)")
    pruef(ohne_selbstbau(m, [])[1] == 0 and selbstbau_boxen(os.path.join(td, "gibtsnicht", "objekt.json")) == [], "ohne vorbauten_auto.json unveraendert")
    # 2. Uneinigkeitskarte: Dachflaeche vor der Wand uneinig bis z 19,4
    fein = os.path.join(td, "fein"); os.makedirs(fein); R = dict(u0=-6.0, z1=25.0, nu=1200, nz=2500, zelle=0.01)
    un = np.full((R["nz"], R["nu"]), 5, np.uint8); un[int((25 - 19.4) / 0.01):int((25 - 16.0) / 0.01), :] = 100; cv2.imwrite(os.path.join(fein, "uneinig_f00.png"), un)
    ob = np.full((R["nz"], R["nu"], 3), 225, np.uint8); ob[int((25 - 19.4) / 0.01):int((25 - 16.0) / 0.01), :] = (60, 120, 70); cv2.imwrite(os.path.join(fein, "ortho_f00.png"), ob)   # 21.11.: Anschluss = Fotokante im Wandbild (anschluss_aus_uneinig)
    for zust, soll in (("entfernt", True), (None, True), ("im_modell", False)):
        fj = dict(fassaden=[dict(id="f00", raster=R)]); fj.update(dict(verdecker_selbstbau=dict(zustand=zust)) if zust else {}); json.dump(fj, open(os.path.join(fein, "fassaden.json"), "w"))
        z, q = vb.anschluss_aus_uneinig(fein, "f00", 16.0, -3.9, 4.58)
        pruef((z is not None and abs(z - 19.4) < 0.15) if soll else (z is None and "zirkulaer" in q), f"Anschluss aus Karte ({zust}): {z} - {q[:70]}")
src = open(os.path.join(HIER, "fassade_ortho.py")).read()
pruef("verdecker_selbstbau=VSB" in src and "--mit-selbstbau" in src and "ohne_selbstbau(m, _sb)" in src, "fassade_ortho: Verdecker ohne Selbstbau + Kennung in fassaden.json")
print("FEHLER: %d" % F if F else "alle Pruefungen bestanden"); sys.exit(1 if F else 0)
