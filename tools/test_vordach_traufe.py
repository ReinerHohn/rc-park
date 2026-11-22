#!/usr/bin/env python3
"""test_vordach_traufe.py - fester synthetischer Test (22.11.2026, Befund Lauf 1122a schwabentor-1120 Stadtseite, Bild audit/neben_eigen__IMG_20261106_113231.jpg):
Vordach im Foto weit ueber die Holzgalerie auskragend und geschweift, Kette mass Traufe nur 0,10 m vor der Galerie, seitlich 0,05 m, c +1,0.
Ursache: tools/vordach_profil.Foto.bewerte blendete alles unter der Traufe aus -> die Traufkante selbst war keine Fotokante, die Traufe rutschte auf die
Unterkante des dunklen Raehms; der zu tiefe/innere Eckpunkt zog die Grate gerade.
Szene: Wand hell, Wandgemaelde mittel, Raehm dunkel 0,25 m tief unter der Galeriefront, Traufschatten (Untersicht) dunkel, Dachkoerper (Front + Walmseiten)
mit Ziegelreihen (Streifen = falsche Kanten). Wahre Traufe 0,55 m vor der Galeriefront, seitlich 0,35 m, c 1,5. Sweep-Startwerte absichtlich daneben
(Traufband 0,15 m zu tief) - die Kette muss Traufe und Krummheit aus den Fotos finden. 4 Kameras aus verschiedenen Hoehen/Abstaenden (Traufhoehe <-> Ausladung).
Laeuft in ~30 s, keine echten Daten. rc 0 = alles gut, sonst FEHLER-Zeilen.
"""
import sys, os, tempfile, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import cv2
import vordach_profil as VP
FEHLER = []
def pruefe(b, txt):
    print(("ok     " if b else "FEHLER ") + txt)
    if not b: FEHLER.append(txt)


def kamera(C, ziel, f=1600.0, W=1500, H=2000):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); r = np.cross(fw, [0, 0, 1.0]); r /= np.linalg.norm(r); dn = np.cross(fw, r)
    R = np.stack([r, dn, fw]); return dict(Rn=R.tolist(), tn=(-R @ C).tolist(), C=C.tolist(), f=f, cx=W / 2, cy=H / 2, W=W, H=H, params=[f, W / 2, H / 2, 0.0])


WF = 1.2                                                                   # Galeriefront (w vor der Wand) = kanten_mass.ausladung
KB = dict(u0=-4.0, u1=4.0)                                                 # Kasten der Galerie
WAHR = dict(u0=KB["u0"] - 0.35, u1=KB["u1"] + 0.35, w_a=0.0, w_t=WF + 0.55, z_t=16.1, z_a=19.9, c=1.5, As=1.4)
welt = lambda P: np.stack([P[:, 2], P[:, 0], P[:, 1]], 1)                 # o = 0, d = +y, n = +x: (u, z, w) -> (x = w, y = u, z)


def szene(td):
    rng = np.random.default_rng(7); KA = {}
    for i, (w_, u_, z_) in enumerate(((22.0, -8.0, 1.6), (36.0, 0.0, 1.6), (15.0, 6.0, 1.6), (48.0, -3.0, 6.0))):
        nm = f"traufe_{i}.png"; K = kamera((w_, u_, z_), (0.8, 0.0, 17.5)); KA[nm] = K
        class _F(VP.Foto):
            def __init__(s): s.K = K; s.welt = welt; s.sj = 1.0; s.x0 = 0; s.y0 = 0; s.f = 1.0
        f_ = _F()
        def fuell(P, wert):
            x, y = f_.px(np.asarray(P, float)); cv2.fillPoly(im, [np.stack([x, y], 1).round().astype(np.int32)], int(wert))
        im = np.full((K["H"], K["W"]), 210, np.uint8)                                                     # Putz hell
        zt = WAHR["z_t"]; zr = zt - 0.6
        fuell([(KB["u0"], zr, 0.0), (KB["u1"], zr, 0.0), (KB["u1"], 11.0, 0.0), (KB["u0"], 11.0, 0.0)], 150)  # Wandgemaelde
        fuell([(KB["u0"], zr, WF), (KB["u1"], zr, WF), (KB["u1"], zt, WF), (KB["u0"], zt, WF)], 40)          # Raehm-Front (unter der Galeriefront)
        fuell([(WAHR["u0"], zt, 0.0), (WAHR["u1"], zt, 0.0), (WAHR["u1"], zt, WAHR["w_t"]), (WAHR["u0"], zt, WAHR["w_t"])], 50)   # Untersicht / Traufschatten
        for j, q_ in enumerate(VP.flaechen(WAHR, n=30)):                                                    # Dachkoerper, Ziegelreihen als Streifen
            fuell(q_, 105 if (j // 3) % 2 else 125)
        im = np.clip(im.astype(np.float32) + rng.normal(0, 6, im.shape), 0, 255).astype(np.uint8); cv2.imwrite(os.path.join(td, nm), im)
    F = dict(id="f00", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], w_wand=0.0)
    g = dict(koerper=dict(w_median=WF), kanten_mass=dict(ausladung=WF, kasten=dict(KB)), galerie=dict(vordach=dict(z_traufe=WAHR["z_t"] - 0.15, z_anschluss=WAHR["z_a"])))
    return F, g, KA


td = tempfile.mkdtemp(prefix="test_vordach_traufe_")
F, g, KA = szene(td)
r = VP.messen(F, g, KA, td, max_fotos=4, min_fotos=3, log=lambda *a: None)
pruefe(isinstance(r, tuple), "Messung liefert ein Ergebnis")
if isinstance(r, tuple):
    e = r[0]
    print(f"       gemessen: w_t {e['w_t']:.2f} (wahr {WAHR['w_t']:.2f}), Ueberstand {e['ueberstand_front']:.2f} (wahr 0.55), seitlich {e['ueberstand_seitlich']:.2f} (wahr 0.35), "
          f"z_t {e['z_t']:.2f} (wahr {WAHR['z_t']}), c {e['c']:+.1f} (wahr {WAHR['c']}), As {e['As']:.2f} (wahr {WAHR['As']}), Traufkante {e['guete_traufe']:.2f}, {e['familie']} {e['fotos_familie']}/4")
    pruefe(abs(e["w_t"] - WAHR["w_t"]) <= 0.15 and e["ueberstand_front"] >= 0.40, f"Traufe weit vor der Galeriefront ({e['ueberstand_front']:.2f} m, wahr 0,55; Fehler des Laufs 1122a: 0,10 m)")
    pruefe(abs(e["ueberstand_seitlich"] - 0.35) <= 0.15, f"seitlicher Ueberstand {e['ueberstand_seitlich']:.2f} ~ 0,35 m (1122a: 0,05 m)")
    pruefe(abs(e["z_t"] - WAHR["z_t"]) <= 0.15, f"Traufhoehe {e['z_t']:.2f} ~ {WAHR['z_t']} trotz 0,15 m zu tiefem Sweep-Startwert")
    pruefe(e["familie"] == "geschweift" and e["belegt"] and abs(e["c"] - WAHR["c"]) <= 0.75, f"geschweift mit c {e['c']:+.1f} ~ {WAHR['c']} (>= 3 Fotos)")
    pruefe(e["guete_traufe"] > 0.2, f"Traufkante sitzt auf einer Fotokante (Band oben - unten {e['guete_traufe']:.2f} > 0,2)")
    pruefe(not e.get("am_suchrand"), f"kein Wert am Suchrand ({e.get('am_suchrand')})")
print("FEHLER: %d" % len(FEHLER) if FEHLER else "alle Pruefungen bestanden")
sys.exit(1 if FEHLER else 0)
