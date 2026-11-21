#!/usr/bin/env python3
"""test_anschluss_stufe.py - Vordach-Wandanschluss als Niveauwechsel (vorbauten_bauplan.anschluss_aus_uneinig / stufe_je_spalte / stufenkante), 21.11.2026.

Befund Schwabentor-1120 f00: Anschluss stand als ANNAHME 16,74 statt gemessen. Ursache: alte Regel 'letzte Stufe ueber 40 % der Spitze' im u-gemittelten
Uneinigkeitsprofil; die echte Karte hat Dachflaeche UND Wand bei 25-36, nur die Anschlusslinie ist ein heller Balken (43-45), dazu ein senkrechter
Fremdbalken (255) -> nie unter 40 % -> 'keine Stufe'. Synthetisch (ohne Fotos) geprueft:
  1. Dach (gruen, geschweifte Seiten) unter Putz (hell) + Leitungsschatten + Stange + Bildluecke, Uneinigkeit = Balken an der Linie, Flaeche/Wand gleich
     -> Anschluss auf 0,05 m; geschweifte Seiten nicht im Lauf.
  2. Wand ohne Dach (Fenster, Leitungen, Schattengrenze) -> None (keine erfundene Stufe).
  3. Fotokante nur ueber 30 % der Breite (Fenstersturz) -> None.
  4. Fotokante ohne Gegenprobe in der Uneinigkeitskarte (flach) -> None.
  5. zirkulaere Karte (verdecker_selbstbau.zustand = im_modell) -> None.
"""
import os, sys, json, tempfile
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import cv2
import vorbauten_bauplan as vb

F = 0
def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1

R = dict(u0=-6.0, z1=25.0, nu=1200, nz=1500, zelle=0.01)
py = lambda z: int((R["z1"] - z) / R["zelle"]); px = lambda u: int((u - R["u0"]) / R["zelle"])
ZT, ZA, U0, U1 = 16.0, 19.5, -3.9, 4.6
rng = np.random.default_rng(3)


def wand():
    b = np.full((R["nz"], R["nu"], 3), 220, np.uint8); b[:] = np.clip(b + rng.normal(0, 6, b.shape), 0, 255).astype(np.uint8)
    for k in range(4):                                     # Leitungsschatten: schraege duenne dunkle Linien
        cv2.line(b, (px(-4 + 2 * k), py(24)), (px(-1 + 2 * k), py(17)), (90, 90, 90), 3)
    return b


def schreibe(d, ortho, un, zust=None):
    os.makedirs(d, exist_ok=True); fj = dict(fassaden=[dict(id="f00", raster=R)])
    if zust: fj["verdecker_selbstbau"] = dict(zustand=zust)
    json.dump(fj, open(os.path.join(d, "fassaden.json"), "w")); cv2.imwrite(os.path.join(d, "ortho_f00.png"), ortho); cv2.imwrite(os.path.join(d, "uneinig_f00.png"), un)


def un_karte(balken_z=None):
    un = np.clip(rng.normal(30, 4, (R["nz"] // 20, R["nu"] // 20)), 0, 255).astype(np.uint8)     # grobe Bloecke wie fassade_ortho, Dach = Wand
    un = cv2.resize(un, (R["nu"], R["nz"]), interpolation=cv2.INTER_NEAREST)
    un[:, px(3.6):px(3.9)] = 255                                                                 # senkrechter Fremdbalken (Stange)
    if balken_z is not None: un[py(balken_z + 0.3):py(balken_z - 0.1), px(U0):px(U1)] = 44          # Anschlusslinie
    return un


with tempfile.TemporaryDirectory() as td:
    # 1. Dach vor der Wand
    o = wand(); dach_farbe = (70, 125, 80)
    for u in np.arange(U0, U1, 0.01):
        r = min(u - U0, U1 - u); z_top = ZA if r > 1.0 else ZT + 0.6 + (ZA - ZT - 0.6) * (r / 1.0) ** 2   # geschweifte Seiten
        o[py(z_top):py(ZT), px(u)] = dach_farbe
    o[py(ZT):py(ZT - 0.6), px(U0):px(U1)] = (40, 40, 45)                                           # Traufschatten
    o[:, px(0.3):px(0.33)] = 0                                                                      # Bildluecke (Naht)
    o[:, px(3.6):px(3.9)] = (30, 30, 30)                                                            # Stange
    d1 = os.path.join(td, "dach"); schreibe(d1, o, un_karte(ZA)); b = {}
    z, q = vb.anschluss_aus_uneinig(d1, "f00", ZT, U0, U1, bild=b)
    pruef(z is not None and abs(z - ZA) <= 0.05, f"Anschluss gemessen {z} (soll {ZA}) - {q[:90]}")
    if b.get("lauf"):
        us = b["u_spalten"]; j0, j1 = b["lauf"]
        pruef(us[j0] > U0 + 0.6 and us[j1] < U1 - 0.6, f"geschweifte Seiten nicht im Lauf (u {us[j0]:.2f}..{us[j1]:.2f})")
    # 1b. alte Annahme: Dachflaeche uneinig, Wand einig (Niveauwechsel statt Balken) -> ebenfalls gemessen
    un2 = un_karte(); un2[py(ZA):py(ZT), px(U0):px(U1)] = 80
    d1b = os.path.join(td, "dach_b"); schreibe(d1b, o, un2); z, q = vb.anschluss_aus_uneinig(d1b, "f00", ZT, U0, U1)
    pruef(z is not None and abs(z - ZA) <= 0.05, f"Uneinigkeit als Niveauwechsel: {z} - {q[:80]}")
    # 2. Wand ohne Dach: Fenster, Leitungen, weiche Schattengrenze
    w = wand()
    for u in (-3.0, 0.0, 3.0): w[py(19.0):py(17.0), px(u):px(u + 0.6)] = (40, 40, 40)
    w[py(18.4):, :] = np.clip(w[py(18.4):, :].astype(int) - 12, 0, 255).astype(np.uint8)             # Schatten/Lichtgrenze ueber die ganze Breite (schwach)
    d2 = os.path.join(td, "wand"); schreibe(d2, w, un_karte()); z, q = vb.anschluss_aus_uneinig(d2, "f00", ZT, U0, U1)
    pruef(z is None, f"Wand ohne Dach: keine Stufe erfunden ({z}; {q[:80]})")
    # 3. Kante nur ueber 30 % der Breite (Sturz/Vorsprung)
    t = wand(); t[py(19.0):py(16.6), px(-1.0):px(1.6)] = dach_farbe
    d3 = os.path.join(td, "teil"); schreibe(d3, t, un_karte(19.0)); z, q = vb.anschluss_aus_uneinig(d3, "f00", ZT, U0, U1)
    pruef(z is None, f"Teilkante 30 % der Breite verworfen ({z}; {q[:60]})")
    # 4. Fotokante ohne Gegenprobe
    d4 = os.path.join(td, "flach"); schreibe(d4, o, un_karte()); z, q = vb.anschluss_aus_uneinig(d4, "f00", ZT, U0, U1)
    pruef(z is None and "Gegenprobe" in q, f"ohne Gegenprobe Uneinigkeit -> ANNAHME ({z}; {q[:70]})")
    # 5. zirkulaer
    d5 = os.path.join(td, "zirk"); schreibe(d5, o, un_karte(ZA), "im_modell"); z, q = vb.anschluss_aus_uneinig(d5, "f00", ZT, U0, U1)
    pruef(z is None and "zirkulaer" in q, "zirkulaere Karte verworfen")
# Guard-Einheit: Luecken (nan) unterbrechen den Lauf nicht, Ausreisser schon
z_, a_, l_ = vb.stufenkante([19.6, 19.7, np.nan, 19.65, 20.0, 17.0, 16.8], [0.8] * 7, [100] * 7)
pruef(l_ == (0, 4) and abs(z_ - 19.675) < 0.01, f"stufenkante: Lauf {l_}, z {z_}")
print("FEHLER: %d" % F if F else "alle Pruefungen bestanden"); sys.exit(1 if F else 0)
