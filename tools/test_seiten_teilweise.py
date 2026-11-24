#!/usr/bin/env python3
"""test_seiten_teilweise.py - TEILWEISE UNGESEHENE WAND loest das Nachholen aus (24.11.2026, Kette schwabentor-null-1122x: Ostwand f02 44 % gesehen, 239 m2 ohne
Bilddaten oberhalb des Nachbardachs; tools/seiten_luecken.py meldete 'keine Wand ganz ungesehen; ABER f02 239 m2' mit rc 0 - kein Nachholen, keine Wiederholung).
Prueft mit kleinen vorgespielten Daten (Sekunden, keine GPU, kein echtes Nachholen):
  (1) teilweise_ungesehen: beide Schwellen (Anteil der FOTOGRAFIERBAREN Wand UND m2), ganz ungesehene / kleine / fast ganz gesehene Waende nicht;
  (2) zone_ohne_daten: Hoehenzone der groessten Luecke; nachbar_verdeckt: Wandteil hinter einem angebauten Nachbarhaus (Quader-Netz) zaehlt nicht als Luecke;
  (3) seiten_luecken.py ohne --holen: Wand mit 56 m2 (56 %) ohne Bilddaten -> rc 3, Bericht 'teilweise' + Zone; 40 m2 (unter der Schwelle) -> rc 0 wie bisher;
  (4) --holen: teilweise ungesehen startet das Nachhol-Skript (Log geschrieben); Kandidaten-Marke versucht_kand_* vorhanden -> UEBERSPRUNGEN in Sekunden, rc 3,
      kein zweiter Versuch ohne neues Foto (versucht_kandidaten.json; Kosten: Nachholen ~48 min + Teillauf ~1,7 h je Versuch, 1122w), neues Foto -> wieder Versuch;
  (5) seiten_wiederholung.kandidaten nimmt teilweise ungesehene Waende mit; gesamtkette ruft seiten_wiederholen auch bei 'teilweise'.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_seiten_teilweise.py   Exit 0 = alles bestanden."""
import os, sys, json, struct, subprocess, time
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2
from pfade import temp_ordner
import seiten_luecken as SL, seiten_wiederholung as SW

F = 0
def pruef(ok, text):
    global F
    print(("ok   " if ok else "FEHLER ") + text, flush=True); F += 0 if ok else 1


def wand(fid):
    """Wand 10 x 10 m, Raster 0,1 m mit 0,5 m Rand (wie fassade_ortho)."""
    return dict(id=fid, n=[1.0, 0.0], d=[0.0, 1.0], o=[0.0, 0.0], flaeche_m2=100.0, polys_uz=[[[-5, 0], [5, 0], [5, 10], [-5, 10]]], raster=dict(u0=-5.5, z1=10.5, nu=110, nz=110, zelle=0.1), fotos={})


def ortho(ordner, fid, oben_leer_m):
    """ortho_<id>.png: Bilddaten nur unterhalb von z = 10 - <oben_leer_m> (Zeile 5 = z 10 m)."""
    im = np.zeros((110, 110, 3), np.uint8); im[5 + int(round(oben_leer_m * 10)):105, 5:105] = 120; cv2.imwrite(os.path.join(ordner, f"ortho_{fid}.png"), im)


def stl_binaer(p, n):
    open(p, "wb").write(b"kopf".ljust(80, b"\0") + struct.pack("<I", n) + b"".join(struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0) for _ in range(n)))


# (1) Schwellen
pruef(SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.442, ohne_daten_m2=238.9)), "1122x f02: 44 % gesehen, 239 m2 ohne Bilddaten -> teilweise ungesehen (Nachholen)")
pruef(not SL.teilweise_ungesehen(dict(ungesehen=True, abdeckung=0.05, ohne_daten_m2=380.0)), "ganz ungesehen ist nicht 'teilweise' (eigener Weg)")
pruef(SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.442, flaeche_m2=428.3, ohne_daten_m2=238.9, verdeckt_nachbar_m2=190.0, ohne_daten_frei_m2=57.0)), "1122x f02 mit Nachbarhaus: 57 m2 = 24 % der fotografierbaren Wand -> Nachholen")
pruef(not SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.3, flaeche_m2=400.0, ohne_daten_m2=280.0, verdeckt_nachbar_m2=260.0, ohne_daten_frei_m2=20.0)), "Luecke fast ganz am angebauten Nachbarhaus (fotografierbar 20 m2) -> kein Nachholen")
pruef(not SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.94, ohne_daten_m2=60.0, flaeche_m2=1000.0)), "1000-m2-Wand, 6 % verstreute Luecke (60 m2) -> unter der Anteil-Schwelle, nur Meldung")
pruef(not SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.4, ohne_daten_m2=36.0)), "kleine Wand 60 m2, 60 % Luecke = 36 m2 -> unter der m2-Schwelle")
pruef(not SL.teilweise_ungesehen(dict(ungesehen=False, abdeckung=0.996, ohne_daten_m2=1.8)), "gesehene Wand (Randrest 1,8 m2) -> nichts")
pruef(SL.TEIL_MIN_ANTEIL >= 2 * SW.MIN_GEWINN - 1e-9 and SL.TEIL_MIN_M2 / 1000.0 >= SW.MIN_GEWINN - 1e-9, f"Schwellen {SL.TEIL_MIN_ANTEIL}/{SL.TEIL_MIN_M2} m2 lassen dem Gewinn-Tor {SW.MIN_GEWINN} Raum (Waende bis 1000 m2)")

# (2) Zone
Fw = wand("f00"); m = np.zeros((110, 110), np.uint8); m[5:105, 5:105] = 1; dat = np.zeros((110, 110), bool); dat[55:105, 5:105] = True
z = SL.zone_ohne_daten(dat, m, Fw["raster"])
pruef(z is not None and abs(z["z_von"] - 5.0) < 0.11 and abs(z["z_bis"] - 10.0) < 0.11 and abs(z["m2"] - 50.0) < 1.0, f"Zone ohne Bilddaten: obere 5 m -> z 5-10 m, 50 m2 ({z})")
pruef(SL.zone_ohne_daten(np.ones((110, 110), bool), m, Fw["raster"]) is None, "voll gesehen -> keine Zone")
import trimesh
nb = trimesh.creation.box(extents=[8.0, 10.0, 6.0]); nb.apply_translation([4.0, 0.0, 3.0])      # angebautes Nachbarhaus vor der Wand (n = +x, Wand bei x = 0): 6 m hoch, 10 m breit
ver = SL.nachbar_verdeckt(nb, Fw, m)
zr = np.where(ver.any(1))[0]; z_hoch = Fw["raster"]["z1"] - zr.min() * Fw["raster"]["zelle"] if len(zr) else None
pruef(len(zr) and abs(z_hoch - 6.0) < 0.6 and 0.5 < ver.sum() / m.sum() < 0.7, f"nachbar_verdeckt: Wand bis 6 m hinter dem Nachbarhaus (bis z {z_hoch}, Anteil {ver.sum() / m.sum():.2f})")
nb2 = nb.copy(); nb2.apply_translation([20.0, 0, 0])
pruef(not SL.nachbar_verdeckt(nb2, Fw, m).any(), "nachbar_verdeckt: Haus gegenueber (20 m entfernt, nicht angebaut) verdeckt nichts")

# (3)/(4) Ende zu Ende
d = temp_ordner("test_seiten_teilweise_")
root = os.path.join(d, "r"); od = os.path.join(root, "modelle", "xtest"); mp = os.path.join(od, "messprotokoll"); fd = os.path.join(root, "fotos"); fo = os.path.join(root, "fassade"); sp = os.path.join(root, "sparse")
for q in (mp, fd, fo, sp): os.makedirs(q)
os.symlink(T, os.path.join(root, "tools"))
oj = os.path.join(od, "objekt.json"); json.dump(dict(fotos_dir="fotos", name="Test", stl="modelle/xtest/m.stl"), open(oj, "w")); stl_binaer(os.path.join(od, "m.stl"), 3)
json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[0, 0, 5])), open(os.path.join(mp, "K-ref.json"), "w"))      # Referenzkamera: belegbar() ok, sonst Frueh-Abbruch vor der Marke
json.dump(dict(fassaden=[wand("f00"), wand("f01")]), open(os.path.join(fo, "fassaden.json"), "w"))
ortho(fo, "f00", 0.0); ortho(fo, "f01", 5.6)                                                                    # f01: obere 5,6 m ohne Bilddaten = 56 m2 = 56 %
open(os.path.join(sp, "images.bin"), "wb").write(struct.pack("<Q", 0))
for n in ("neu_a", "neu_b"): cv2.imwrite(os.path.join(fd, n + ".jpg"), np.full((32, 32, 3), 99, np.uint8))
daten = os.path.join(d, "daten"); env = dict(os.environ, SEITEN_LUECKEN_DATEN=daten); env.pop("SEITEN_NEU", None)
for k_ in ("RCPARK_TEIL_MIN_ANTEIL", "RCPARK_TEIL_MIN_M2"): env.pop(k_, None)
aufruf = [sys.executable, "-I", os.path.join(T, "seiten_luecken.py"), oj, fo, "--sparse", sp, "--ref-db", os.path.join(d, "gibtsnicht.db")]
sj = os.path.join(od, "audit", "seiten_luecken.json"); Z = os.path.join(daten, "xtest", "seiten_nachholen")

r = subprocess.run(aufruf, capture_output=True, text=True, env=env); S = json.load(open(sj)) if os.path.exists(sj) else {}
w1 = (S.get("waende") or [{}, {}])[1]
pruef(r.returncode == 3 and S.get("ungesehen") == [] and S.get("teilweise") == [1], f"56 m2 (56 %) ohne Bilddaten -> rc 3, Bericht teilweise [1] (rc {r.returncode}, {S.get('ungesehen')}/{S.get('teilweise')}; {r.stdout.strip().splitlines()[-1][:120] if r.stdout.strip() else r.stderr[-200:]})")
zo = w1.get("zone_ohne_daten") or {}
pruef(abs((zo.get("z_von") or 0) - 4.4) < 0.11 and abs((zo.get("z_bis") or 0) - 10.0) < 0.11, f"Bericht: Hoehenzone der Luecke z 4,4-10 m ({zo})")
pruef("TEILWEISE UNGESEHEN" in r.stdout and os.path.exists(os.path.join(od, "audit", "seiten_luecken_kandidaten.jpg")), "Meldung + Kontaktbogen der Kandidaten auch fuer teilweise ungesehene Wand")

ortho(fo, "f01", 4.0)                                                                                          # 40 m2 = unter der m2-Schwelle 50
r = subprocess.run(aufruf, capture_output=True, text=True, env=env)
pruef(r.returncode == 0 and "unter der Nachhol-Schwelle" in r.stdout, f"40 m2 ohne Bilddaten -> rc 0, nur Meldung/Fotoauftrag ({r.stdout.strip().splitlines()[-1][:120] if r.stdout.strip() else ''})")

ortho(fo, "f01", 5.6)
t0 = time.time(); r = subprocess.run(aufruf + ["--holen"], capture_output=True, text=True, env=env, timeout=600); dt = time.time() - t0
pruef(os.path.exists(os.path.join(Z, "nachholen_letzter_lauf.log")), f"--holen: teilweise ungesehen STARTET das Nachhol-Skript (rc {r.returncode} in {dt:.0f} s; hier scheitert die Vorpruefung an der fehlenden DB)")
sk = open(os.path.join(od, "audit", "seiten_luecken_holen.sh")).read(); kand = [os.path.join(fd, n + ".jpg") for n in ("neu_a", "neu_b")]
pruef(not SL.kandidaten_versucht(Z, kand)[0], "kandidaten_versucht: ohne Liste -> nein")
SL.kandidaten_merken(Z, kand, ["f01"])
os.remove(os.path.join(Z, "nachholen_letzter_lauf.log"))
t0 = time.time(); r = subprocess.run(aufruf + ["--holen"], capture_output=True, text=True, env=env, timeout=120); dt = time.time() - t0
pruef(r.returncode == 3 and "UEBERSPRUNGEN (teilweise ungesehen)" in r.stdout and "FOTOAUFTRAG" in r.stdout and not os.path.exists(os.path.join(Z, "nachholen_letzter_lauf.log")) and dt < 60,
      f"Kandidaten schon nachgeholt -> kein zweiter Versuch, rc 3 in {dt:.1f} s, Fotoauftrag ({r.stdout.strip().splitlines()[-1][:140] if r.stdout.strip() else r.stderr[-200:]})")
cv2.imwrite(os.path.join(fd, "neu_c.jpg"), np.full((32, 32, 3), 50, np.uint8)); kand3 = kand + [os.path.join(fd, "neu_c.jpg")]
ok3, t3 = SL.kandidaten_versucht(Z, kand3); ok1, _ = SL.kandidaten_versucht(Z, kand[:1])
pruef(not ok3 and "neu_c" in t3 and ok1, f"neues Foto -> wieder ein Versuch ({t3}); Teilmenge schon versuchter Kandidaten (anderes SfM) -> kein Versuch")
os.remove(os.path.join(fd, "neu_c.jpg"))

# (5) Entscheidung der Kette
tj = os.path.join(d, "tor.json"); json.dump(dict(belegt=["x"], neu=1, waende=[dict(nr=1, id="f01", neu_sicht=3)]), open(tj, "w"))
k, g = SW.kandidaten(tj, sj); S = json.load(open(sj))
pruef([w["id"] for w in k] == ["f01"], f"seiten_wiederholung.kandidaten: teilweise ungesehene f01 mit belegter neuer Kamera ({k} {g})")
src = open(os.path.join(T, "gesamtkette.py")).read()
pruef('or teil) and not TEILLAUF and seiten_wiederholen(' in src and 'get("teilweise")' in src, "gesamtkette: seiten_wiederholen auch bei teilweise ungesehener Wand (hoechstens einmal, nicht im Teillauf)")

print("ALLE BESTANDEN" if not F else f"{F} FEHLER"); sys.exit(1 if F else 0)
