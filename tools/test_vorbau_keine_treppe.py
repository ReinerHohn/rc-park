#!/usr/bin/env python3
"""Test (24.11.2026, RUECKFALL Treppenkloetze Kette 1122z/zb/zc Schwabentor; Verwandt: test_vorbau_pfosten.py, test_vorbau_beleg.py; Vorlaeufer: Sackgasse 21.11.
"Hoehenfeld als Gestalt treppig", Doku/projekt/bauteile-kreis/generator.md).
Ursache: ebenen_masse fand bei duennen Fotokanten keinen Kasten -> bauteile.vorbauten_aus_json baute STILL das Hoehenfeld je 0,2-m-Zelle = gestufte Bloecke.
  1. Ohne kanten_mass, mit Galerie-Messung: Ersatz-Kasten, Treppen-Anteil (bauteile.treppen_anteil) < 0,02, Beleg nennt 'Ersatzmessung'.
  2. ROTE PROBE: MIT_HOEHENFELD=1 (alter Weg) -> Treppen-Anteil > 0,10 (das Mass erkennt die Treppe).
  3. GUARD: Galerie und Grobkoerper ungueltig -> nichts gebaut, Beleg 'NICHT gebaut'.
  4. ebenen_masse.duenne_linien: luechige Holm-/Unterkante mit Galerie-Band -> 2 Linien; ohne Galerie-Messung -> keine (Phantom-Schutz); Einzelfleck (geringe Spanne) -> keine."""
import os, sys, json, shutil
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from manifold3d import Manifold as M
import trimesh
import bauteile as B
import ebenen_masse as EM
from pfade import temp_ordner

FEHLER = []
def pruef(ok, text):
    print(("    ok " if ok else "    FEHLER ") + text)
    if not ok: FEHLER.append(text)

def als_trimesh(m):
    t = m.to_mesh(); return trimesh.Trimesh(np.asarray(t.vert_properties)[:, :3], np.asarray(t.tri_verts), process=False)

rng = np.random.default_rng(7)
Z1, R = 16.0, 0.2
W = np.zeros((30, 42))                                          # Hoehenfeld wie der Ebenen-Sweep: Tiefe je 0,2-m-Zelle mit Messrauschen (3x3-Median, auf 5 cm gerundet = Laeufe)
W[6:26] = 1.1 + rng.normal(0.0, 0.1, (20, 42))
GAL = dict(u0=-4.0, u1=4.4, z_boden=11.0, z_holm=12.6, z_dach=14.6, w=1.1, w_wand=0.0, pfosten=[-3.8, 4.2], streben_u=[-3.5, -2.0, -0.5, 1.0, 2.5, 4.0], z_fuss=9.4)
def gruppe(**k):
    g = dict(u0=-4.2, u1=4.2, z0=Z1 - 30 * R, z1=Z1, raster=R, w=W.tolist(), koerper=dict(u0=-4.2, u1=4.2, z0=10.0, z1=15.0, w_median=1.0), galerie=dict(GAL))
    g.update(k); return g

td = temp_ordner("test_vorbau_keine_treppe_")
try:
    wand = M.cube((6, 14, 20)).translate((-6, -7, 0))
    def bau(g, env=None):
        f = os.path.join(td, "vorbauten_auto.json"); json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], w_wand=0.0, gruppen=[g])]), open(f, "w"))
        alt = {k_: os.environ.get(k_) for k_ in (env or {})}; os.environ.update(env or {})
        try: return B.vorbauten_aus_json(wand, f)
        finally:
            for k_, v_ in alt.items():
                if v_ is None: os.environ.pop(k_, None)
                else: os.environ[k_] = v_
    zone = ([0.0, 0.0], [0.0, 1.0], [1.0, 0.0], -4.2, 4.2, 10.0, 15.8)
    k1, b1 = bau(gruppe())
    a1, p1 = B.treppen_anteil(als_trimesh(k1), *zone)
    pruef(p1 > 200 and a1 < 0.02, f"1. Ersatz-Kasten statt Hoehenfeld: Treppen-Anteil {a1:.3f} ({p1} Paare), Soll < 0,02")
    pruef("Ersatzmessung" in json.dumps(b1, ensure_ascii=False), "1. Beleg nennt die Ersatzmessung")
    k2, b2 = bau(gruppe(), env={"MIT_HOEHENFELD": "1"})
    a2, p2 = B.treppen_anteil(als_trimesh(k2), *zone)
    pruef(a2 > 0.10, f"2. ROTE PROBE Hoehenfeld (MIT_HOEHENFELD=1): Treppen-Anteil {a2:.3f} ({p2} Paare), Soll > 0,10")
    k3, b3 = bau(gruppe(galerie=dict(GAL, w=0.0), koerper=dict(u0=0.0, u1=0.1, z0=10.0, z1=15.0, w_median=1.0)))
    pruef(abs(k3.volume() - wand.volume()) < 1e-6 and "NICHT gebaut" in json.dumps(b3, ensure_ascii=False), "3. Guard: ungueltige Ersatzmessung -> nichts gebaut, Beleg")
    lin = [dict(z=10.73, belegt_m=3.2, stuecke=[[-3.72, -3.57], [-1.52, -0.72], [3.38, 4.13]]), dict(z=11.95, belegt_m=1.6, stuecke=[[-3.77, -3.62], [0.43, 0.83], [3.83, 4.13]]),
           dict(z=11.45, belegt_m=0.1, stuecke=[[0.1, 0.2]])]
    v = EM.duenne_linien(lin, 3.2, 8.92, dict(z_boden=10.42, z_holm=12.82))
    pruef([l_["z"] for l_ in v] == [10.73, 11.95], f"4. duenne Linien mit Galerie-Band: {[l_['z'] for l_ in v]}")
    pruef(EM.duenne_linien(lin, 3.2, 8.92, None) == [], "4. ohne Galerie-Messung keine Stufe 2 (Phantom-Schutz)")
    fl = [dict(z=10.73, belegt_m=3.2, stuecke=[[0.0, 3.2]]), dict(z=11.95, belegt_m=1.6, stuecke=[[0.5, 2.1]])]
    pruef(EM.duenne_linien(fl, 3.2, 8.92, dict(z_boden=10.42, z_holm=12.82)) == [], "4. Einzelfleck (Spanne < 0,6 x Zone) -> keine")
finally:
    shutil.rmtree(td, ignore_errors=True)
if FEHLER: print("FEHLER test_vorbau_keine_treppe:", len(FEHLER)); sys.exit(1)
print("    ok test_vorbau_keine_treppe")
