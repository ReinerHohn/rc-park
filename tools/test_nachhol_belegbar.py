#!/usr/bin/env python3
"""test_nachhol_belegbar.py - FRUEH-ABBRUCH der Kettenstufe seiten_luecken (24.11.2026, Kette schwabentor-null-1122u: 3737 s fuer '264 nachgetragen, 0 BELEGT, 264 gesperrt').
Ursache 1122u: Modell-STL leer -> tools/kamera_verfeinern.py stuerzte beim Laden ab (trimesh-Szene, KeyError 'world'), '|| true' im Nachhol-Skript schluckte das,
jede neue Kamera wurde 'unbelegt' und die Erfolgsmarke 'versucht' liess den naechsten Lauf ueberspringen. Prueft (Sekunden, keine echten Daten, keine GPU):
(1) seiten_luecken.stl_dreiecke: binaer/ASCII/leer/kaputt;
(2) seiten_luecken.belegbar: STL mit Dreiecken + Referenzkamera im gueltigen Rahmen -> ok; leeres/fehlendes STL, keine oder nur veraltete Referenzkameras -> nicht ok;
(3) seiten_luecken.py --holen mit leerem STL: rc 5 in Sekunden, Bericht seiten_luecken.json geschrieben, Nachhol-Skript NICHT gelaufen, keine Fehlschlag-/Erfolgsmarke;
(4) Nachhol-Skriptzeile kamera_verfeinern: rc 3 (keine Kamera bestimmt) laeuft weiter, Absturz (rc 1) bricht ab (set -e).
  /media/oem/scan/venv-seg/bin/python -I tools/test_nachhol_belegbar.py   Exit 0 = alles bestanden."""
import os, sys, json, struct, subprocess, time
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2
from pfade import temp_ordner
import seiten_luecken as SL, kamera_rahmen as KR

F = 0
def pruef(ok, text):
    global F
    print(("ok   " if ok else "FEHLER ") + text, flush=True); F += 0 if ok else 1


def stl_binaer(p, n):
    open(p, "wb").write(b"solid kopf".ljust(80, b"\0") + struct.pack("<I", n) + b"".join(struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0) for _ in range(n)))


d = temp_ordner("test_nachhol_belegbar_")
# (1) STL lesen
p = os.path.join(d, "a.stl"); stl_binaer(p, 2); pruef(SL.stl_dreiecke(p) == 2, "binaeres STL mit 2 Dreiecken (Kopf beginnt mit 'solid')")
stl_binaer(p, 0); pruef(SL.stl_dreiecke(p) == 0, "leeres binaeres STL (84 Byte, 1122u-Fall) -> 0 Dreiecke")
open(p, "w").write("solid x\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 0\n   vertex 1 0 0\n   vertex 0 1 0\n  endloop\n endfacet\nendsolid x\n"); pruef(SL.stl_dreiecke(p) == 1, "ASCII-STL mit 1 Dreieck")
open(p, "wb").write(b"\x01" * 100); pruef(SL.stl_dreiecke(p) is None, "kaputte Datei -> None")

# (2) belegbar
root = os.path.join(d, "r"); od = os.path.join(root, "modelle", "xtest"); mp = os.path.join(od, "messprotokoll"); os.makedirs(mp)
oj = os.path.join(od, "objekt.json"); json.dump(dict(fotos_dir="fotos", name="Test", stl="modelle/xtest/m.stl"), open(oj, "w")); sp_ = os.path.join(od, "m.stl")
stl_binaer(sp_, 3); json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[0, 0, 5])), open(os.path.join(mp, "K-ref.json"), "w"))
ok, g = SL.belegbar(oj); pruef(ok, f"STL 3 Dreiecke + 1 Referenzkamera -> belegbar ({g})")
stl_binaer(sp_, 0); ok, g = SL.belegbar(oj); pruef(not ok and "LEER" in g, f"leeres STL -> nicht belegbar ({g[:90]})")
os.remove(sp_); ok, g = SL.belegbar(oj); pruef(not ok and "fehlt" in g, "STL fehlt -> nicht belegbar")
stl_binaer(sp_, 3); os.remove(os.path.join(mp, "K-ref.json")); json.dump(dict(punkte=[1]), open(os.path.join(mp, "K-ohne.json"), "w"))
ok, g = SL.belegbar(oj); pruef(not ok and "Referenzkamera" in g, "K-Datei ohne 'kamera' zaehlt nicht -> nicht belegbar")
KR.setzen(mp, dict(id="neu", zeit=time.time())); json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[0, 0, 5], rahmen="alt")), open(os.path.join(mp, "K-alt.json"), "w"))
ok, g = SL.belegbar(oj); pruef(not ok, "Referenzkamera nur im ALTEN Rahmen (kamera_rahmen.veraltet, wie kamera_verfeinern) -> nicht belegbar")
json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[0, 0, 5], rahmen="neu")), open(os.path.join(mp, "K-neu.json"), "w")); ok, g = SL.belegbar(oj); pruef(ok, "Referenzkamera im aktuellen Rahmen -> belegbar")
json.dump(dict(fotos_dir="fotos"), open(oj, "w")); ok, g = SL.belegbar(oj); pruef(not ok and "'stl'" in g, "objekt.json ohne 'stl' -> nicht belegbar")

# (3) Ende zu Ende: --holen mit leerem STL bricht in Sekunden ab, ohne das Nachhol-Skript
json.dump(dict(fotos_dir="fotos", name="Test", stl="modelle/xtest/m.stl"), open(oj, "w")); stl_binaer(sp_, 0)
fd = os.path.join(root, "fotos"); fo = os.path.join(root, "fassade"); sp = os.path.join(root, "sparse")
for q in (fd, fo, sp): os.makedirs(q)
os.symlink(T, os.path.join(root, "tools"))
json.dump(dict(fassaden=[dict(id="f00", flaeche_m2=80.0, n=[1.0, 0.0], o=[0.0, 0.0], raster=dict(nu=40, nz=30, u0=0.0, z1=3.0, zelle=0.1), polys_uz=[[[0, 0], [4, 0], [4, 3], [0, 3]]], fotos={})]),
          open(os.path.join(fo, "fassaden.json"), "w")); cv2.imwrite(os.path.join(fo, "ortho_f00.png"), np.zeros((30, 40, 3), np.uint8))      # Wand ohne Bilddaten = ungesehen
open(os.path.join(sp, "images.bin"), "wb").write(struct.pack("<Q", 0))      # leeres SfM-Modell: jedes Foto ist Kandidat
for n in ("neu_a", "neu_b"): cv2.imwrite(os.path.join(fd, n + ".jpg"), np.full((32, 32, 3), 99, np.uint8))
daten = os.path.join(d, "daten"); env = dict(os.environ, SEITEN_LUECKEN_DATEN=daten); env.pop("SEITEN_NEU", None)
t0 = time.time(); r = subprocess.run([sys.executable, "-I", os.path.join(T, "seiten_luecken.py"), oj, fo, "--sparse", sp, "--ref-db", os.path.join(d, "gibtsnicht.db"), "--holen"],
                                     capture_output=True, text=True, env=env); dt = time.time() - t0; out = r.stdout + r.stderr
Z = os.path.join(daten, "xtest", "seiten_nachholen"); marken = [f for f in os.listdir(Z) if f.startswith(("fehlschlag_", "versucht_"))] if os.path.isdir(Z) else []
pruef(r.returncode == 5 and "Frueh-Abbruch" in out and "LEER" in out and dt < 60, f"--holen mit leerem STL: rc 5 in {dt:.1f} s (rc {r.returncode}; {out.strip().splitlines()[-1][:110] if out.strip() else ''})")
pruef(not os.path.exists(os.path.join(Z, "nachholen_letzter_lauf.log")) and not marken, f"Nachhol-Skript nicht gelaufen, keine Marke ({marken})")
sj = os.path.join(od, "audit", "seiten_luecken.json"); B = json.load(open(sj)) if os.path.exists(sj) else {}
pruef(B.get("ungesehen") == [0] and len(B.get("nicht_registriert", [])) == 2, f"Bericht seiten_luecken.json trotzdem geschrieben (ungesehen {B.get('ungesehen')})")

# (4) Skriptzeile kamera_verfeinern: rc 3 weiter, Absturz Abbruch
au = os.path.join(d, "audit4"); Z4 = os.path.join(d, "Z4"); os.makedirs(au); os.makedirs(Z4)
json.dump(dict(neu=[dict(foto="a")]), open(os.path.join(au, "kameras_nachtragen.json"), "w"))
for rc_, soll in ((3, True), (0, True), (1, False)):
    z = SL.kamera_verfeinern_zeile(f"sh -c 'exit {rc_}' x", "/T", "/o/objekt.json", "/o/fassaden.json", au, Z4)
    r = subprocess.run(["bash", "-c", "set -e\n" + z + "\necho ENDE"], capture_output=True, text=True)
    pruef(("ENDE" in r.stdout) == soll and (r.returncode == 0) == soll, f"kamera_verfeinern rc {rc_} -> " + ("weiter" if soll else "Skript bricht ab (kein stilles 'alles unbelegt')"))

print("ALLE BESTANDEN" if not F else f"{F} FEHLER"); sys.exit(1 if F else 0)
