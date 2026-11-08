#!/usr/bin/env python3
"""s8_kaufhaus.py - Beweislauf SPEC S8 am Kaufhaus: Ebenen-Modell (voll + Holdout), STL 1:87, Pruefstand, foto_diff auf 6 Holdout-Fotos gegen Generator C und Carving (Holdout).
Aufruf: venv-seg/bin/python -W ignore -I tools/s8_kaufhaus.py   (Ausgabe /media/oem/scan/rc-park_null/kanten_vektor/kh_beweis.json)"""
import os, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ebenen_modell as EM, wolke_solid as WS, beweis_ansatz as BA
B = "/media/oem/scan/rc-park_null/kanten_vektor"; DICHT = "/media/oem/scan/rc-park_null/kaufhaus_null5/sfm/dicht_alle"; AUSR = os.path.join(ROOT, "modelle/kaufhaus_null5/messprotokoll/SFM-AUSRICHTUNG-buendel.json")
OBJ = os.path.join(ROOT, "modelle/kaufhaus_null5/objekt.json"); HO = ["001", "024", "054", "083", "211", "234"]; erg = {}
os.environ.setdefault("MINFL", "1.0")
def bauen(name, mat, ohne):
    m, e = EM.lauf(DICHT, AUSR, mat, os.path.join(B, name), ohne, solid=0.8, leer=0.2, min_flaeche_m2=1.0)
    p = os.path.join(B, name, "ebenen_modell_1-87.stl"); m2, gr, ok, dv = WS.stl_dicht(m, 87.0, p); erg[name] = dict(stl=p, wasserdicht_nach_laden=bool(ok), raster_m=gr, koerper=e["koerper"], zellen=e["zellen"], ebenen=len(e["ebenen"])); return p
stl_voll = bauen("kh_eb_voll", "/media/oem/scan/rc-park_null/wolke_solid/carv_kh3/material.npz", ())
stl_ho = bauen("kh_eb_ho", os.path.join(B, "ho_carv/material.npz"), tuple(HO))
r = subprocess.run([BA.PYSEG, "-W", "ignore", "-I", os.path.join(HERE, "pruefstand.py"), OBJ, "--stl", stl_voll], cwd=ROOT, capture_output=True, text=True); erg["pruefstand_voll"] = (r.stdout + r.stderr)[-2500:]
C = "/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6/modell_s3_v9.stl"; CARV = os.path.join(B, "ho_carv/wolke_carving_1-87.stl"); k = dict(fd_objp=OBJ)
for n, s in (("C_generator", C), ("carving_holdout", CARV), ("ebenen_holdout", stl_ho)):
    erg["fd_" + n] = BA.foto_diff_lauf(k, HO, s, os.path.join(B, "fd_" + n), False)
    json.dump(erg, open(os.path.join(B, "kh_beweis.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in erg.items() if k.startswith("fd_")}, indent=1)[:4000])
