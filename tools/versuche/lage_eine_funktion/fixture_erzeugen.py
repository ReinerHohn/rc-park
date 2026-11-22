#!/usr/bin/env python3
"""Erzeugt tools/test_lage_eine_funktion_fixture.json (22.11.2026, nur lesend): Kamerazentren der 174 GPS-Kameras von schwabentor-1120 im Netzsystem der Ausrichtung
VOR dem LoD2-Feinfit - einmal mit dem Lot der Kameraebene (alte Regel), einmal mit dem Bild-x-Lot (seiten_gps_vereinen.lot_info) - waagerecht (x, y, SfM-Einheiten),
dazu Foto-GPS und EXIF-Zeiten aus test_gps_eine_quelle_fixture.json. Zeigt den Befund 'Ausrichtung +-11,2 Grad ohne Fernfoto, Tor +-1,7 Grad mit 10 Fernfotos'.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/versuche/lage_eine_funktion/fixture_erzeugen.py [kameras.json]"""
import json, os, sys, math
import numpy as np
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import seiten_gps_vereinen as SG
kj = sys.argv[1] if len(sys.argv) > 1 else "/media/oem/scan/rc-park_daten/schwabentor-1120/pipe/kameras.json"
F = json.load(open(os.path.join(T, "test_gps_eine_quelle_fixture.json")))["schwabentor-1120"]
KJ = json.load(open(kj)); nm = [os.path.splitext(b["name"])[0] for b in KJ["bilder"]]
C = np.array([b["C"] for b in KJ["bilder"]], float); Rs = np.array([b["R"] for b in KJ["bilder"]], float); ix = {n: i for i, n in enumerate(nm)}; sel = np.array([ix[n] for n in F["namen"]])
dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); cm = C[nah].mean(0); eb = np.linalg.svd(C[nah] - cm)[2][2]
ach = np.asarray(SG.lot_info(Rs)["oben"], float); eb = eb if eb @ ach > 0 else -eb
def rahmen(u):
    e1 = np.cross(u, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1); return ((C - cm) @ np.vstack([e1, e2, u]).T)[sel, :2].round(4).tolist()
out = dict(quelle="tools/versuche/lage_eine_funktion/fixture_erzeugen.py, " + kj + " + test_gps_eine_quelle_fixture.json[schwabentor-1120] (22.11.2026)",
           namen=F["namen"], gps_modell=F["gps_modell"], zeiten=F["zeiten"], kamera_ebene=rahmen(eb), kamera_bildachsen=rahmen(ach),
           winkel_ebene_bildachsen_grad=round(math.degrees(math.acos(min(1.0, abs(float(eb @ ach))))), 3))
json.dump(out, open(os.path.join(T, "test_lage_eine_funktion_fixture.json"), "w"))
print("geschrieben", len(out["namen"]), "Kameras, Winkel", out["winkel_ebene_bildachsen_grad"])
