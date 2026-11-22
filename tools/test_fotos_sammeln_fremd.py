#!/usr/bin/env python3
"""Test fotos_sammeln (22.11.2026): Fremdbilder in einem --eigen-Ordner (alter Sammelordner) bekommen ihre echte Quelle und laufen ueber die Vorpruefung."""
import os, sys, json, tempfile, subprocess, numpy as np, cv2
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import fotos_sammeln as FS
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR")); O = os.path.join(tmp, "rc-park_daten", "objx"); rng = np.random.default_rng(3)
def bild(p):
    os.makedirs(os.path.dirname(p), exist_ok=True); cv2.imwrite(p, (rng.random((240, 320, 3)) * 255).astype(np.uint8)); return p
eig = bild(f"{O}/fotos_eigen/IMG_1.jpg"); vf = bild(f"{O}/video_frames/clipA/vf_001.jpg"); vf2 = bild(f"{O}/video_frames/clipB/vf_001.jpg"); co = bild(f"{O}/commons/orig/c1.jpg")
S = f"{O}/alt_sammlung/fotos"; os.makedirs(S)
os.symlink(eig, f"{S}/eigen__IMG_1.jpg"); os.symlink(vf, f"{S}/video_frames_clipA__vf_001.jpg"); os.symlink(vf2, f"{S}/vf_001.jpg"); os.symlink(co, f"{S}/c1.jpg")
h = {r: (f, g) for r, f, g in FS.herkunft(S)}
pruef(h[os.path.realpath(eig)][0] is False, "eigenes Foto bleibt eigen")
pruef(h[os.path.realpath(co)][0] and sum(1 for _, (f, _) in h.items() if f) == 3, f"3 Fremdbilder erkannt (Sammelname, Fremdquellordner): {h}")
pruef(FS.fremde_ordner([S]) == sorted({os.path.dirname(x) for x in (vf, vf2, co)}), "fremde_ordner liefert die echten Quellordner")
def lauf(*arg):
    r = subprocess.run([sys.executable, "-I", os.path.join(T, "fotos_sammeln.py"), *arg], capture_output=True, text=True); return r.returncode, r.stdout
Z = os.path.join(tmp, "ziel"); rc, out = lauf(Z, "--eigen", S, "--trocken")
pruef(rc == 0 and not os.path.exists(Z) and "3 von 4 'eigenen' Bildern sind Fremdquellen" in out, "Trockenlauf meldet 3 von 4, Ziel unberuehrt")
vp = os.path.join(tmp, "vp.json"); json.dump(dict(bilder={vf: dict(inlier=100), vf2: dict(inlier=10)}), open(vp, "w"))
rc, out = lauf(Z, "--eigen", S, "--geprueft", vp); n = sorted(os.listdir(Z))
pruef(rc == 0 and "eigen__IMG_1.jpg" in n and "video_frames_clipA__vf_001.jpg" in n, f"mit Vorpruefung: eigenes + stimmiges Videobild mit echter Quelle ({n})")
pruef(not any("clipB" in x or "c1" in x for x in n), "unter min-inlier bzw. nicht vorgeprueft -> weg")
sj = json.load(open(os.path.join(Z, "sammlung.json")))["fremd_in_eigen"]
pruef(sj["gesamt"] == 3 and sj["nicht_vorgeprueft"] == 1 and sj["unter_min_inlier"] == 1, f"Bilanz in sammlung.json {sj}")
rc, out = lauf(Z, "--eigen", S); n = sorted(os.listdir(Z))
pruef(rc == 0 and "commons_orig__c1.jpg" in n and "video_frames_clipB__vf_001.jpg" in n, f"ohne Vorpruefung: Fremdbilder behalten, aber mit echter Quelle ({n})")
src = open(os.path.join(T, "gesamtkette.py")).read()
pruef("from fotos_sammeln import fremde_ordner" in src and "fremd += fie" in src, "gesamtkette gibt die Fremdordner an die Vorpruefung")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
