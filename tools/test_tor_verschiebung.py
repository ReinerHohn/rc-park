#!/usr/bin/env python3
"""test_tor_verschiebung.py - BEWEIS fuer tools/tor_verschiebung.py (Nullkontrolle des Foto-Tors) auf synthetischer Wahrheit.

Das "Foto" ist ein Render der WAHREN Geometrie (test_foto_diff.foto_rendern, Lambert + Rauschen); gemessen wird mit der ECHTEN Kette
(tor_verschiebung -> teil_fotoform -> foto_diff), nicht mit einem Ersatzmass. Ein Wegwerf-Objekt modelle/_synth_tvs wird angelegt und am Ende entfernt.
Szene (Meter): Wand 14 x 0,6 x 9, Kamera 16 m davor. Zwei Faelle fuer das Ziel-Teil:
  A  VORBAU: eine einzelner Vorbau (Kasten mit Aufsatz) (eindeutige Lage).        Erwartung: echte Lage belegt (marge >= Schwelle),
     dieselbe Plakette 0,3 m daneben im Modell (falsch gesetzt)               Erwartung: NICHT belegt (eine Verschiebung zurueck ist besser).
  B  RIPPEN: 12 senkrechte Rippen (0,25 breit, 1,0 tief) im Abstand 0,5 m (viele, gleiche Kanten).  Erwartungen:
     B1 Dichte taeuscht das einfache Tor: falsch gesetzte Rippen (0,3 m verschoben = 0,05 m Restversatz der Kanten, innerhalb der Toleranz 0,14 m) schlagen die rippenlose Platte (F1 nachher > vorher -> einfaches Tor wuerde annehmen);
     B2 die Kontrolle erklaert dieses falsche Rippenfeld NICHT fuer lage_belegt.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_tor_verschiebung.py   (oder tor_verschiebung.py --synth)
Exit 0 = alle Behauptungen erfuellt.
"""
import sys, os, json, shutil, time, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tor_verschiebung as TV, test_foto_diff as TF

R0 = TV.R0; OBJ = "_synth_tvs"; OD = os.path.join(R0, "modelle", OBJ)
ARB = os.path.join(TV.TMP, "synth"); W0, H0, F = 3200, 2400, 3000.0
C = np.array([7.0, -15.0, 4.5])


def box(ext, ctr):
    b = trimesh.creation.box(extents=ext); b.apply_translation(ctr); return b


def wand(): return box([14, 0.6, 9], [0, 0.3, 4.5])


def plakette(dx=0.0):       # EINZELNER Vorbau (eindeutige Lage): Kasten 2,0 x 1,2 x 3,0 mit Aufsatz 1,0 x 0,6 x 1,0 (flaches Relief < ~0,5 m erzeugt in foto_diff KEINE Modellkante, rippen_diag/BERICHT.md)
    return trimesh.util.concatenate([box([2.0, 1.2, 3.0], [dx, -0.6, 4.0]), box([1.0, 0.6, 1.0], [-0.3 + dx, -1.5, 5.0])])


def rippen(dx=0.0, n=12, pitch=0.5):
    return trimesh.util.concatenate([box([0.25, 1.0, 2.5], [-3.0 + i * pitch + dx, -0.5, 4.0]) for i in range(n)])


def platte(): return box([6.0, 0.05, 2.5], [-3.0 + 5.5 * 0.5, -0.025, 4.0])


def kamera():
    z = np.array([0.0, -0.5, 4.0]) - C; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x)   # Blick auf die Mitte des Zielbereichs
    Rm = np.vstack([x, y, z]); rv, _ = cv2.Rodrigues(Rm); return Rm, -Rm @ C, rv.ravel()


def aufbau():
    shutil.rmtree(OD, ignore_errors=True); os.makedirs(os.path.join(OD, "messprotokoll")); os.makedirs(ARB, exist_ok=True)
    json.dump({"name": "synthetisch (test_tor_verschiebung)", "stl": "x.stl", "stl_massstab": 1000, "zentrierung": "achse", "masstabelle": f"modelle/{OBJ}/masstabelle.json",
               "fotos_dir": ARB, "generator": ""}, open(os.path.join(OD, "objekt.json"), "w"))
    Rm, t, rv = kamera()
    for nr in ("sa", "sb"):
        json.dump({"foto": nr, "kamera": {"rvec": rv.tolist(), "t": t.tolist(), "f_px": F, "cx": W0 / 2, "cy": H0 / 2, "bild": [W0, H0], "k1": 0.0, "modell": "SIMPLE_RADIAL",
                   "rahmen_verschiebung": [0.0, 0.0, 0.0]}}, open(os.path.join(OD, "messprotokoll", f"K-{nr}.json"), "w"))


def foto(nr, teile):
    Rm, t, _ = kamera(); m = trimesh.util.concatenate(teile)
    im = TF.foto_rendern(m, Rm, t, F, W0 / 2, H0 / 2, W0, H0, np.random.default_rng(3)); cv2.imwrite(os.path.join(ARB, f"{nr}_synth.png"), im)


def stl_dir(name, wand_m, ziel_m):
    d = os.path.join(ARB, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    wand_m.export(os.path.join(d, "wand.stl")); ziel_m.export(os.path.join(d, "ziel.stl")); return d


def main(argv=None):
    os.makedirs(ARB, exist_ok=True); aufbau(); ok = True; t0 = time.time(); erg = {}
    def pruefe(name, bed, info=""):
        nonlocal ok
        print(f"  [{'OK ' if bed else 'FEHLER'}] {name} {info}", flush=True); ok &= bool(bed); erg[name] = bool(bed)
    try:
        W = wand()
        foto("sa", [W, plakette()]); foto("sb", [W, rippen()])
        kw = dict(skala=0.5, wolke="aus", massstab=1000.0, verbose=True)
        print("== A Plakette, richtig gesetzt"); dA = stl_dir("A_richtig", W, plakette())
        eA = TV.kontrolle(OBJ, dA, "ziel", ["sa"], 0.3, arbeit=os.path.join(ARB, "kA"), **kw)
        pruefe("A richtig: lage_belegt", eA["lage_belegt"], f"f1 {eA['f1_echt']} Versatz max {eA['f1_versatz_max']} marge {eA['marge']} marge_min {eA['marge_min']} {eA['marge_achse']}")
        print("== A' Plakette 0,3 m falsch gesetzt"); dA2 = stl_dir("A_falsch", W, plakette(0.3))
        eA2 = TV.kontrolle(OBJ, dA2, "ziel", ["sa"], 0.3, arbeit=os.path.join(ARB, "kA2"), **kw)
        pruefe("A falsch gesetzt: NICHT lage_belegt", eA2["lage_belegt"] is False, f"f1 {eA2['f1_echt']} Versatz max {eA2['f1_versatz_max']} marge {eA2['marge']} marge_min {eA2['marge_min']}")
        pruefe("A: richtige Lage hat hoehere F1 als falsche", eA["f1_echt"] > eA2["f1_echt"], f"{eA['f1_echt']} > {eA2['f1_echt']}")
        print("== B Rippenfeld"); dB0 = stl_dir("B_platte", W, platte()); dBr = stl_dir("B_richtig", W, rippen()); dBf = stl_dir("B_falsch", W, rippen(0.3))
        hue = os.path.join(ARB, "B_huelle"); os.makedirs(hue, exist_ok=True); trimesh.util.concatenate([rippen(), rippen(0.3), platte()]).export(os.path.join(hue, "ziel.stl"))
        def f1_(d, zm):
            voll = os.path.join(d, "voll.stl"); trimesh.util.concatenate([W, zm]).export(voll)
            return TV.f1_messen(OBJ, d, voll, "ziel", ["sb"], os.path.join(d, "ff.json"), hue, 0.5, "aus")
        fP, fR, fF = f1_(dB0, platte()), f1_(dBr, rippen()), f1_(dBf, rippen(0.3))
        print(f"  platte {fP}\n  richtig {fR}\n  falsch(0,3) {fF}")
        # Rippenlose Platte hat keine Modellkanten im Bereich (mk_px < min_px) -> F1 nicht messbar (None): fuer das Tor 'vorher' ist das ein Phantom ohne Kanten.
        pruefe("B1 Dichte: falsch gesetzte Rippen (0,3 m daneben) erreichen praktisch die F1 der richtigen (Abstand <= 0,02) -> einfaches Tor kann sie nicht unterscheiden",
               fF and fR and fF["f1"] >= fR["f1"] - 0.02, f"richtig {fR and fR['f1']} falsch {fF and fF['f1']}")
        eB = TV.kontrolle(OBJ, dBf, "ziel", ["sb"], 0.3, arbeit=os.path.join(ARB, "kB"), **kw)
        pruefe("B2 Kontrolle: falsche Rippen NICHT lage_belegt", eB["lage_belegt"] is False, f"f1 {eB['f1_echt']} Versatz max {eB['f1_versatz_max']} marge {eB['marge']} marge_min {eB['marge_min']} {eB['marge_achse']}")
        erg["zahlen"] = {"A": eA, "A_falsch": eA2, "B_platte": fP, "B_richtig": fR, "B_falsch": fF, "B_kontrolle_falsch": eB}
    finally:
        shutil.rmtree(OD, ignore_errors=True)
    json.dump(erg, open(os.path.join(ARB, "ergebnis.json"), "w"), indent=1, default=str)
    print(f"{'ALLE BEHAUPTUNGEN ERFUELLT' if ok else 'FEHLGESCHLAGEN'} ({time.time() - t0:.0f} s)"); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
