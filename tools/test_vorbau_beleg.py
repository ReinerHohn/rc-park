#!/usr/bin/env python3
"""test_vorbau_beleg.py - synthetisch, CPU, < 5 s (23.11.2026, Befund Kette 1122t: 'Vorbau f03' West war ein Phantom).

URSACHE 1122t: der Ebenen-Sweep fand auf f03 eine 'Front' bei +2,05 m (z 17,5-25,4), ein Viertel der Zellen klebte an der Suchgrenze (+2,4..2,45 von 2,6 m),
die Vorbau-Ebene f03_vb0 bekam 0 Kantenpunkte - im Foto ist dort nichts. Das Fototor meldete BELEGT (Praezision 0,52 >= 0,5).
Geprueft (tools/vorbau_fototor.py beleg / beleg_anwenden / urteil):
  1. Phantom (Randtreffer + 0 Kantenpunkte) -> verworfen, beide Gruende genannt.
  2. Echter Erker (dichte Kanten, Front weit vor der Grenze, wenige Dachzellen am Rand) -> bleibt, nichts knapp.
  3. Nur (a) oder nur (b) reicht zum Verwerfen; fehlende Daten urteilen nicht.
  4. Regel (c): Praezision schwach + Beleg knapp -> NICHT BELEGT; ohne Beleg wie bisher (0,52 = BELEGT); starke Praezision + knapp -> BELEGT.
  5. beleg_anwenden auf Dateien (vorbauten_auto + vorbauten_fNN + ebenen.json): Phantom bekommt 'verworfen', Erker nicht; kein Wand-Id im Code.
  6. bauteile.vorbauten_aus_json baut eine verworfene Gruppe nicht (Generator-Umgebung, sonst Hinweis).
"""
import os, sys, json, subprocess, tempfile
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import vorbau_fototor as VF

F = []
def pruef(b, t):
    print(("ok     " if b else "FEHLER ") + t)
    if not b: F.append(t)


def feld(nz, nu, front, rand_n=0, rand_w=None):
    """Hoehenfeld nz x nu: Front 'front', die ersten rand_n Zellen (zeilenweise) auf rand_w."""
    w = [[front] * nu for _ in range(nz)]; k = 0
    for r in range(nz):
        for s in range(nu):
            if k < rand_n: w[r][s] = rand_w; k += 1
    return w


# Synthetische Fassaden nach Muster 1122t (Werte gerundet, keine Objektdaten im Werkzeug)
GRENZE_A, GRENZE_B = 2.5, 2.6
wand = dict(punkte=60000, zone=[-6.0, 6.0, 0.0, 37.0])                       # ~135 Punkte/m2
erker = dict(w=feld(40, 40, 1.1, rand_n=80, rand_w=2.25), raster=0.2)          # 5 % am Rand (Dach), Rest Front 1,1 m
ebene_erker = dict(punkte=22000, zone=[-4.3, 5.0, 8.2, 20.8])                 # ~190 Punkte/m2 = 1,4 x Wand
phantom = dict(w=feld(40, 13, 2.05, rand_n=150, rand_w=2.45), raster=0.2)      # 29 % am Rand
ebene_leer = dict(punkte=0, zone=[2.5, 6.3, 15.9, 26.4], fehler="ValueError: need at least one array to concatenate")

# 1. Phantom
b = VF.beleg(phantom, GRENZE_B, ebene_leer, wand)
pruef(b["verwerfen"] and len(b["gruende"]) == 2 and b["kanten_punkte"] == 0 and b["rand_anteil"] > VF.RAND_ANTEIL_MAX,
      f"Phantom (Randtreffer {b['rand_anteil']} + 0 Kantenpunkte) verworfen: {b['gruende']}")
# 2. echter Erker
b = VF.beleg(erker, GRENZE_A, ebene_erker, wand)
pruef(not b["verwerfen"] and not b["knapp"] and b["kanten_dichte_rel"] > 1.0 and b["rand_anteil"] < VF.RAND_ANTEIL_MAX / VF.KNAPP,
      f"echter Erker bleibt (Dichte {b['kanten_dichte_rel']} x Wand, Randanteil {b['rand_anteil']}, knapp {b['knapp']})")
# 3. einzelne Gruende, fehlende Daten
b = VF.beleg(phantom, GRENZE_B, ebene_erker, wand)
pruef(b["verwerfen"] and b["gruende"][0].startswith("(b)"), "nur Randtreffer (Kanten vorhanden) -> verworfen")
b = VF.beleg(erker, GRENZE_A, ebene_leer, wand)
pruef(b["verwerfen"] and b["gruende"][0].startswith("(a)"), "nur fehlende Fotokanten (Tiefe in Ordnung) -> verworfen")
b = VF.beleg(erker, GRENZE_A, dict(punkte=900, zone=ebene_erker["zone"]), wand)
pruef(b["verwerfen"] and "Dichte" in b["gruende"][0], f"duenne Kanten (Dichte {b['kanten_dichte_rel']} x Wand < {VF.KANTEN_DICHTE_REL_MIN}) -> verworfen")
b = VF.beleg(phantom, None, None, None)
pruef(not b["verwerfen"] and b["rand_anteil"] is None and b["kanten_punkte"] is None, "ohne Grenze/Ebene kein Urteil (nicht verworfen)")
# 4. Regel (c)
schwach = {"_gesamt": dict(praez=0.52, recall=0.8, f1=0.63, fotos=8)}; stark = {"_gesamt": dict(praez=0.62, recall=0.88, f1=0.72, fotos=8)}
knapp = VF.beleg(dict(w=feld(40, 13, 1.5, rand_n=40, rand_w=2.45)), GRENZE_B, dict(punkte=7000, zone=ebene_erker["zone"]), wand)   # Rand ~8 %, Dichte ~0,4
pruef(not knapp["verwerfen"] and knapp["knapp"], f"Beleg knapp, aber nicht verworfen ({knapp['knapp']})")
pruef(VF.urteil(schwach, beleg_=knapp)[0] == "NICHT BELEGT", "(c) Praezision 0,52 + Beleg knapp -> NICHT BELEGT")
pruef(VF.urteil(schwach)[0] == "BELEGT" and VF.urteil(schwach, beleg_=VF.beleg(erker, GRENZE_A, ebene_erker, wand))[0] == "BELEGT", "ohne/mit sauberem Beleg wie bisher: 0,52 = BELEGT")
pruef(VF.urteil(stark, beleg_=knapp)[0] == "BELEGT", "starke Praezision 0,62 + Beleg knapp -> BELEGT")

# 5. beleg_anwenden auf Dateien
with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as T:
    fo = os.path.join(T, "fassade"); os.makedirs(fo)
    json.dump(dict(w_bereich=[-0.88, 2.42], wand_versatz_m=-0.08, belastbar=True), open(os.path.join(fo, "vorbauten_f00.json"), "w"))
    json.dump(dict(w_bereich=[-0.8, 2.5], wand_versatz_m=-0.1, belastbar=True), open(os.path.join(fo, "vorbauten_f03.json"), "w"))
    eb = os.path.join(T, "ebenen.json")
    json.dump(dict(ebenen=[dict(wand, id="f00_wand"), dict(wand, id="f03_wand", punkte=106000), dict(ebene_erker, id="f00_vb0"), dict(ebene_leer, id="f03_vb0")]), open(eb, "w"))
    vj = os.path.join(T, "vorbauten_auto.json"); g0 = dict(u0=-3.7, u1=4.4, z0=9.8, z1=19.8, koerper=dict(w_median=1.05)); g3 = dict(u0=3.1, u1=5.7, z0=17.5, z1=25.4, koerper=dict(w_median=2.05))
    json.dump(dict(fassaden=[dict(id="f00", nr=0, gruppen=[dict(g0, **erker)]), dict(id="f03", nr=3, gruppen=[dict(g3, **phantom)])]), open(vj, "w"))
    r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "vorbau_fototor.py"), "--beleg", vj, fo, eb], capture_output=True, text=True)
    J = json.load(open(vj)); G0, G3 = J["fassaden"][0]["gruppen"][0], J["fassaden"][1]["gruppen"][0]
    pruef(r.returncode == 2 and "verworfen" in G3 and "verworfen" not in G0 and "beleg" in G0, f"--beleg: Phantom f03 verworfen, Erker f00 bleibt (rc {r.returncode}) {r.stdout.strip()[-300:]}")
    pruef(abs(G3["beleg"]["w_grenze"] - 2.6) < 1e-6 and abs(G0["beleg"]["w_grenze"] - 2.5) < 1e-6, "Suchgrenze je Fassade aus vorbauten_fNN.json (w_bereich - Wandversatz)")

    # 6. Generator baut verworfene Gruppe nicht
    GEN = os.path.expanduser("~/.venvs/rcpark/bin/python")
    if os.path.exists(GEN):
        gb = dict(u0=-1.0, u1=1.0, z0=5.0, z1=6.0, raster=0.5, w=[[1.0] * 4, [1.0] * 4], koerper=dict(w_median=1.0), dach=None)
        vj2 = os.path.join(T, "vb2.json"); json.dump(dict(fassaden=[dict(id="f00", nr=0, o=[0, 0], d=[0, 1], n=[1, 0], w_wand=0.0, gruppen=[dict(gb, verworfen="Test"), dict(gb, u0=3.0, u1=4.0, koerper=dict(u0=3.0, u1=4.0, z0=5.0, z1=6.0, w_median=1.0))])]), open(vj2, "w"))
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from manifold3d import Manifold as M; from bauteile import vorbauten_aus_json as V; k, b = V(M(), sys.argv[2]); "
                "import numpy as np; m = k.to_mesh(); v = np.asarray(m.vert_properties)[:, :3]; print(len(b), round(float(v[:, 1].min()), 2) if len(v) else 'leer')")
        r = subprocess.run([GEN, "-I", "-c", code, HIER, vj2], capture_output=True, text=True); o_ = r.stdout.split()
        pruef(r.returncode == 0 and o_[:2] == ["1", "3.0"], f"bauteile.vorbauten_aus_json: verworfene Gruppe nicht gebaut, zweite schon (Belege/u-min {o_}) {r.stderr[-200:]}")
    else:
        print("hinweis: Generator-Umgebung fehlt - Bau nicht geprueft")

print("FEHLER: %d" % len(F) if F else "alle Pruefungen bestanden"); sys.exit(1 if F else 0)
