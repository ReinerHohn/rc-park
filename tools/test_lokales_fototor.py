#!/usr/bin/env python3
"""Synthetischer Beweis des lokalen Foto-Tors (modelle/archiv/SPEC_LOKALES_FOTOTOR.md, Punkte 1-3), am echten Modell (Teile-Ordner eines Kreislaufs):
 1. erfundenes Detail (Kasten 0,4 m an der Bruestung) -> lokaler F1 darf nicht um >= 0,05 steigen
 2. echtes Detail (Teil entfernt = vorher, vorhanden = nachher) -> lokal >= +0,05
 3. dasselbe Teil 0,3 m versetzt (nachher) gegen richtig liegend (vorher) -> lokal muss FALLEN
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_lokales_fototor.py [basis_teile_dir] [teil_erfunden] [teil_echt] [teil_versatz]"""
import sys, os, json, shutil, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_lokal as FL
BASIS = sys.argv[1] if len(sys.argv) > 1 else "/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_091923a091923/teile_r2_nachher"
T_ERF = sys.argv[2] if len(sys.argv) > 2 else "bruestung__balkon"
T_ECHT = sys.argv[3] if len(sys.argv) > 3 else "quader__laube_sockel_o"
T_VERS = sys.argv[4] if len(sys.argv) > 4 else "bruestung__balkon"   # gut sitzendes Teil (lokal-F1 0,9); sockel_o sitzt schlecht (F1 0,35, Versatz verbessert ihn)
FOTOS = "i08,6120,p03,6119,6132,d11,j05,h13,q11,6127"
W = "/media/oem/scan/rc-park_tmp/foto_lokal/synth"; os.makedirs(W, exist_ok=True)
EINHEIT_M = 0.087   # STL-Einheit -> m (stl_massstab 87/1000)

def kopie(name, aendern):
    """neuer Teile-Ordner = BASIS (Symlinks) mit aendern(dict dateiname->Trimesh|None, liste)"""
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    liste = json.load(open(os.path.join(BASIS, "liste.json")))
    for f in os.listdir(BASIS):
        if f.endswith(".stl"): os.symlink(os.path.join(BASIS, f), os.path.join(d, f))
    aendern(d, liste); json.dump(liste, open(os.path.join(d, "liste.json"), "w"))
    return d

def messen(v, n, teil, tag):
    e = FL.main(["kaufhaus_grob3", "--vorher", v, "--nachher", n, "--fotos", FOTOS, "--nur", teil, "--aus", os.path.join(W, tag + ".json"), "--bilder", os.path.join(W, "bilder_" + tag)])
    g = e["teile"][teil]["_gesamt"]; return g

def ersetzen(d, fn, mesh):
    os.remove(os.path.join(d, fn)); mesh.export(os.path.join(d, fn))

# 1. erfundener Kasten 0,4 m auf der Oberkante, an drei Stellen (Mitte, beide Enden der Teil-Box); jede muss unter +0,05 bleiben
NUR3 = os.environ.get("TEST_NUR3") == "1"   # nur Test 3 (Wiederholung)
m0 = trimesh.load(os.path.join(BASIS, T_ERF + ".stl"), force="mesh"); k = 0.4 / EINHEIT_M
box = trimesh.creation.box((k, k, k)); lo, hi = m0.bounds; erf = {}
for nm, f in ((() if NUR3 else (("mitte", 0.5), ("ende1", 0.1), ("ende2", 0.9)))):
    bx = box.copy(); bx.apply_translation([lo[0] + f * (hi[0] - lo[0]), lo[1] + f * (hi[1] - lo[1]), hi[2] + k / 2])
    def a1(d, l, bx=bx): ersetzen(d, T_ERF + ".stl", trimesh.util.concatenate([m0, bx]))
    erf[nm] = messen(BASIS, kopie("erfunden_" + nm, a1), T_ERF, "t1_erfunden_" + nm)
# 2. echtes Detail: vorher ohne das Teil, nachher mit Teil
def a2(d, l): os.remove(os.path.join(d, T_ECHT + ".stl")); l.pop(next(kk for kk, vv in l.items() if vv["datei"] == T_ECHT + ".stl"))
v2 = kopie("ohne_teil", a2)
g2 = {"lokal_nicht_messbar": True} if NUR3 else messen(v2, BASIS, T_ECHT, "t2_echt")
# 3. Versatz 0,3 m: nachher = Teil versetzt (Richtung: lokale +x), vorher = richtig
m3 = trimesh.load(os.path.join(BASIS, T_VERS + ".stl"), force="mesh")
verschoben = {}
for ri, vec in ((a_, v_) for a_, v_ in (("x", [0.3 / EINHEIT_M, 0, 0]), ("y", [0, 0.3 / EINHEIT_M, 0]), ("z", [0, 0, 0.3 / EINHEIT_M])) if a_ in os.environ.get("TEST_ACHSEN", "xyz")):
    mm = m3.copy(); mm.apply_translation(vec)
    def a3(d, l, mm=mm): ersetzen(d, T_VERS + ".stl", mm)
    n3 = kopie("versetzt_" + ri, a3); verschoben[ri] = messen(BASIS, n3, T_VERS, "t3_versatz_" + ri)
def lok(g): return None if g.get("lokal_nicht_messbar") else round(g["f1_lokal_nach"] - g["f1_lokal_vor"], 3)
r1 = {k_: lok(g) for k_, g in erf.items()}; r2 = lok(g2); r3 = {k: lok(g) for k, g in verschoben.items()}
ok1 = NUR3 or all(v is not None and v < 0.05 for v in r1.values()); ok2 = NUR3 or r2 is not None and r2 >= 0.05; ok3 = all(v is not None and v < 0 for v in r3.values())
print(json.dumps({"1_erfunden_lokal_delta": r1, "bestanden": ok1, "g": erf, "2_echt_lokal_delta": r2, "bestanden2": ok2, "g2": g2, "3_versatz_lokal_delta": r3, "bestanden3": ok3, "g3": verschoben}, indent=1))
sys.exit(0 if (ok1 and ok2 and ok3) else 1)
