#!/usr/bin/env python3
"""test_vordach_vorbau.py - fester synthetischer Test (21.11.2026, schwabentor-1120 Stadtseite, Nutzerbild neben_eigen__IMG_20261106_113231) fuer
  (1) tools/vordach_profil.messen: Walm-Vordach in 3 synthetischen Fotos (bekannte Kameras) - geschweiftes Dach -> Familie 'geschweift' (c, Walm-Ruecksprung, Traufe
      wiedergefunden), gerades Dach -> 'gerade'. Bewertung = Silhouettenkontrast; Ziegelstruktur im Dach darf nicht taeuschen.
  (2) bauteile.vordach_walm: geschlossener Koerper, Oberkante = Anschluss, geschweift hat weniger Volumen als gerade (Flaeche unter der Sehne), Walm schmaler oben.
  (3) putz_wandbild.relief_vorbau_flach: Reliefblase hinter dem Vorbau ohne Tiefensprung in den Fotokanten -> Wandniveau; Block mit Kanten vor der Wand bleibt;
      Blase ausserhalb der Vorbauzone bleibt (andere Regeln zustaendig).
Laeuft in Sekunden, keine echten Daten. rc 0 = alles gut, sonst FEHLER-Zeilen.
"""
import sys, os, tempfile, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import cv2
import vordach_profil as VP
FEHLER = []
def pruefe(b, txt):
    print(("ok     " if b else "FEHLER ") + txt)
    if not b: FEHLER.append(txt)


def kamera(C, ziel, f=2000.0, W=2000, H=3000):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); r = np.cross(fw, [0, 0, 1.0]); r /= np.linalg.norm(r); dn = np.cross(fw, r)
    R = np.stack([r, dn, fw]); return dict(Rn=R.tolist(), tn=(-R @ C).tolist(), C=C.tolist(), f=f, cx=W / 2, cy=H / 2, W=W, H=H, params=[f, W / 2, H / 2, 0.0])


def szene(td, wahr, name):
    """3 Fotos eines Walm-Vordachs (Wand x = 0, aussen +x): Wand hell, Dach dunkel mit Ziegelpunkten, Traufkasten dunkel darunter."""
    rng = np.random.default_rng(1); KA = {}
    welt = lambda P: np.stack([P[:, 2], P[:, 0], P[:, 1]], 1)            # o = 0, d = +y, n = +x: (u, z, w) -> (w, u, z)
    for i, y in enumerate((-9.0, 0.0, 9.0)):
        nm = f"{name}_{i}.png"; K = kamera((26.0, y, 1.6), (0.7, 0.0, 17.6)); KA[nm] = K
        im = np.full((K["H"], K["W"]), 205, np.uint8)
        class _F(VP.Foto):
            def __init__(s): s.K = K; s.welt = welt; s.sj = 1.0; s.x0 = 0; s.y0 = 0; s.f = 1.0
        f_ = _F()
        for q_ in VP.flaechen(dict(wahr, w_a=0.0), n=60):            # 22.11.2026: ganzer Dachkoerper (Front + Walmseiten) statt nur Grat-Polygon - so sieht ihn eine schraege Kamera
            x, y_ = f_.px(q_); cv2.fillPoly(im, [np.stack([x, y_], 1).round().astype(np.int32)], 70)
        fx, fy = f_.px(np.array([[wahr["u0"], wahr["z_t"], wahr["w_t"]], [wahr["u1"], wahr["z_t"], wahr["w_t"]], [wahr["u1"], wahr["z_t"] - 0.5, wahr["w_t"] - 0.1], [wahr["u0"], wahr["z_t"] - 0.5, wahr["w_t"] - 0.1]]))
        cv2.fillPoly(im, [np.stack([fx, fy], 1).round().astype(np.int32)], 50)
        dach = im == 70; pk = rng.random(im.shape) < 0.01; im[dach & pk] = 150             # Ziegelpunkte (helle Glasur-Flecken)
        im = np.clip(im.astype(np.float32) + rng.normal(0, 6, im.shape), 0, 255).astype(np.uint8); cv2.imwrite(os.path.join(td, nm), im)
    F = dict(id="f00", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], w_wand=0.0)
    g = dict(koerper=dict(w_median=1.2), kanten_mass=dict(ausladung=1.2, kasten=dict(u0=-4.0, u1=4.0)), galerie=dict(vordach=dict(z_traufe=16.0, z_anschluss=19.8)))
    return F, g, KA


print("(1) vordach_profil.messen an synthetischen Fotos")
td = temp_ordner("test_vordach_")
for name, wahr, fam in (("schweif", dict(u0=-4.1, u1=4.1, w_t=1.4, z_t=16.1, z_a=19.9, c=2.0, As=1.25), "geschweift"),
                        ("gerade", dict(u0=-4.1, u1=4.1, w_t=1.4, z_t=16.1, z_a=19.9, c=0.0, As=1.25), "gerade")):
    F, g, KA = szene(td, wahr, name)
    r = VP.messen(F, g, KA, td, max_fotos=3, min_fotos=3, log=lambda *a: None)
    pruefe(isinstance(r, tuple), f"{name}: Messung liefert ein Ergebnis")
    if not isinstance(r, tuple): continue
    e = r[0]
    print(f"       {name}: familie {e['familie']} c {e['c']:+.1f} As {e['As']:.2f} w_t {e['w_t']:.2f} z_t {e['z_t']:.2f} z_a {e['z_a']:.2f} ({e['fotos_familie']}/3 Fotos)")
    pruefe(e["familie"] == fam and e["belegt"] == (fam != "gerade" or e["belegt"]), f"{name}: Formfamilie {fam} erkannt")
    pruefe(abs(e["As"] - wahr["As"]) <= 0.3, f"{name}: Walm-Ruecksprung {e['As']:.2f} ~ {wahr['As']}")
    pruefe(abs(e["z_a"] - wahr["z_a"]) <= 0.15 and abs(e["z_t"] - wahr["z_t"]) <= 0.15, f"{name}: Anschluss/Traufe auf 15 cm")
    if fam == "geschweift": pruefe(abs(e["c"] - wahr["c"]) <= 1.0, f"{name}: Krummheit c {e['c']} ~ {wahr['c']}")

print("(2) bauteile.vordach_walm")
from bauteile import Wand, vordach_walm
W = Wand((0.0, 0.0), (0.0, 1.0), aussen=(1.0, 0.0))
k1 = vordach_walm(W, -4, 4, 0.0, 1.4, 16.0, 19.8, c=2.0, As=1.2); k0 = vordach_walm(W, -4, 4, 0.0, 1.4, 16.0, 19.8, c=0.0, As=1.2)
bb = k1.bounding_box()
pruefe(not k1.is_empty() and k1.volume() > 0, "geschweiftes Vordach ist ein Koerper")
pruefe(abs(bb[5] - 19.8) < 0.02 and abs(bb[2] - 15.85) < 0.02, f"Oberkante Anschluss 19,8 / Unterseite Traufe - 0,15 (z {bb[2]:.2f}..{bb[5]:.2f})")
pruefe(k1.volume() < 0.85 * k0.volume(), f"geschweift weniger Volumen als gerade ({k1.volume():.2f} < {k0.volume():.2f} m3)")
sl = k1.slice(19.5).to_polygons(); ys = np.concatenate([np.asarray(p)[:, 1] for p in sl]) if sl else np.zeros(1)
pruefe(ys.max() - ys.min() < 8.0 - 1.5, f"Walm: oben schmaler als die Traufe ({ys.max() - ys.min():.2f} m bei z 19,5)")

print("(3) putz_wandbild.relief_vorbau_flach")
import putz_wandbild as PW
px = 0.05; H, Wd = 300, 300; rel = np.full((H, Wd), 0.10, np.float32)            # 15 x 15 m, z0 = 0, u0 = 0
jj, ii = np.meshgrid(np.arange(Wd), np.arange(H)); uu = (jj + 0.5) * px; zz = (H - 1 - ii + 0.5) * px
blase = (uu - 5) ** 2 + (zz - 9) ** 2 < 0.8 ** 2; block = (np.abs(uu - 8) < 0.6) & (np.abs(zz - 9) < 0.6); aussen_ = (uu - 12.5) ** 2 + (zz - 4) ** 2 < 0.8 ** 2
rel[blase] += 0.15; rel[block] += 0.15; rel[aussen_] += 0.15
Z = dict(rel=rel, px=px, u0=0.0, z0=0.0, a=np.array([0.0, 0.0, 0.0]), t=np.array([0.0, 1.0, 0.0]), n=np.array([1.0, 0.0, 0.0]), oeffnung=np.zeros((H, Wd), bool))
f_in = os.path.join(td, "w_voll.npz"); np.savez_compressed(f_in, **Z)
rng = np.random.default_rng(3); K = []
for _ in range(1500): K.append((rng.uniform(3, 10), rng.uniform(7, 11), rng.normal(0.0, 0.01)))            # gemalte Kanten auf der Wandebene (auch ueber der Blase)
for _ in range(200):
    s_ = rng.uniform(-0.6, 0.6); K.append((8 + rng.choice([-0.6, 0.6]), 9 + s_, 0.15 + rng.normal(0, 0.01))); K.append((8 + s_, 9 + rng.choice([-0.6, 0.6]), 0.15 + rng.normal(0, 0.01)))
inf = PW.relief_vorbau_flach(f_in, os.path.join(td, "w_vorbau.npz"), [(3.0, 10.0, 7.0, 11.0)], np.array(K))
N = np.load(os.path.join(td, "w_vorbau.npz"))["rel"]; print("      ", inf)
pruefe(np.abs(N[blase] - 0.10).max() < 0.02, "Blase ohne Tiefensprung in den Kanten -> Wandniveau")
pruefe(np.median(N[block]) > 0.22, "Block mit Kanten 0,15 m vor der Wand bleibt (Rand-Kanten belegen ihn)")
pruefe(np.abs(N[aussen_] - rel[aussen_]).max() < 1e-6, "Blase ausserhalb der Vorbauzone unveraendert")
inf0 = PW.relief_vorbau_flach(f_in, os.path.join(td, "w_vorbau0.npz"), [(3.0, 10.0, 7.0, 11.0)], None)
pruefe(abs(np.load(os.path.join(td, "w_vorbau0.npz"))["rel"][blase] - 0.10).max() < 0.02, "ohne Kanten (kein Mehrfoto-Beleg) -> Wandniveau")

print("FEHLER: %d" % len(FEHLER) if FEHLER else "alle Pruefungen bestanden")
sys.exit(1 if FEHLER else 0)
