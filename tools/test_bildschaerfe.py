#!/usr/bin/env python3
"""Tests fuer tools/bildschaerfe.py und tools/zusatzfotos_registrieren.py (vorbereiten: Dubletten, Ausschlussliste, Wasserzeichenstreifen, Namen).
  /media/oem/scan/venv-seg/bin/python -I tools/test_bildschaerfe.py"""
import os, sys, json, tempfile, shutil, subprocess
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bildschaerfe as B, zusatzfotos_registrieren as Z

def szene(seed=0):
    r = np.random.RandomState(seed); g = np.full((1500, 2000, 3), (90, 90, 190), np.uint8)             # glatte rote Flaeche
    for _ in range(60): cv2.rectangle(g, (int(r.randint(0, 1900)), int(r.randint(0, 1400))), (int(r.randint(0, 2000)), int(r.randint(0, 1500))), tuple(int(x) for x in r.randint(0, 255, 3)), 2)
    return g
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m); return bool(c)
res = []
s = szene(); sc = B.schaerfe(s)
k = np.zeros((1, 41), np.float32); k[0, :] = 1 / 41; M = np.eye(41, dtype=np.float32)[20][None]; Mk = cv2.warpAffine(np.ones((41, 41), np.float32), cv2.getRotationMatrix2D((20, 20), 30, 1), (41, 41)); Mk /= Mk.sum()
bl = cv2.filter2D(s, -1, Mk)
bm = B.schaerfe(bl)
res.append(ok(sc["kachel_q"] > 5 * bm["kachel_q"], f"Bewegungsunschaerfe senkt kachel_q stark ({sc['kachel_q']:.0f} -> {bm['kachel_q']:.0f})"))
res.append(ok(B.urteil(sc) == "scharf" and B.urteil(bm) != "scharf", f"Urteil scharf/{B.urteil(bm)}"))
glatt = np.full((1500, 2000, 3), (90, 90, 190), np.uint8); cv2.line(glatt, (0, 700), (2000, 760), (0, 0, 0), 3)       # fast nur glatte Flaeche, EINE scharfe Kante: Ganzbild-Laplace ~ 0
res.append(ok(B.urteil(B.schaerfe(glatt)) == "scharf" and B.schaerfe(glatt)["global_lap"] < 150, f"glatte Flaeche mit scharfer Kante bleibt scharf (global_lap {B.schaerfe(glatt)['global_lap']:.0f} wuerde verwerfen)"))
glatt_u = cv2.GaussianBlur(glatt, (0, 0), 6)
res.append(ok(B.urteil(B.schaerfe(glatt_u)) != "scharf", "dieselbe Kante verwischt -> nicht scharf"))
# vorbereiten
t = tempfile.mkdtemp(); a = os.path.join(t, "handy_2026-11-06"); c = os.path.join(t, "handy_2026-11-06_c"); os.makedirs(a); os.makedirs(c)
cv2.imwrite(os.path.join(a, "handy_01.jpg"), cv2.resize(s, (400, 300))); shutil.copy(os.path.join(a, "handy_01.jpg"), os.path.join(c, "handy_c_01.jpg"))
cv2.imwrite(os.path.join(a, "handy_02.jpg"), cv2.resize(bl, (400, 300))); cv2.imwrite(os.path.join(c, "handy_c_02.jpg"), cv2.resize(szene(3), (400, 300)))
aus = os.path.join(t, "z"); os.makedirs(aus); json.dump(dict(aussortiert=[dict(datei="handy_2026-11-06/handy_02.jpg", grund="test")]), open(os.path.join(t, "aus.json"), "w"))
class A: pass
q = A(); q.fotos = [a, c]; q.aus = aus; q.ausschluss = os.path.join(t, "aus.json"); q.unten = 0.1; q.breite = 200; Z.vorbereiten(q)
v = json.load(open(os.path.join(aus, "vorbereitet.json")))
res.append(ok(sorted(v["bilder"]) == ["h_a_01.jpg", "h_c_02.jpg"], f"Dublette (MD5) und Ausschluss entfernt: {sorted(v['bilder'])}"))
im = cv2.imread(os.path.join(aus, "bilder", "h_a_01.jpg")); res.append(ok(im.shape[:2] == (135, 200), f"unten 10 % abgeschnitten, Breite 200: {im.shape[:2]}"))
res.append(ok(any("Dublette" in x["grund"] for x in v["verworfen"]) and any("ausgeschlossen" in x["grund"] for x in v["verworfen"]), "Verwurf mit Begruendung protokolliert (nichts geloescht)"))
res.append(ok(os.path.exists(os.path.join(c, "handy_c_01.jpg")), "Originale unberuehrt")); shutil.rmtree(t)
print("alle bestanden" if all(res) else "FEHLER"); sys.exit(0 if all(res) else 1)
