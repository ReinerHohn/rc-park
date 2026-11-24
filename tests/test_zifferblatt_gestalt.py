#!/usr/bin/env python3
"""test_zifferblatt_gestalt.py - fester synthetischer Test (24.11.2026, Nutzer: "so wirklich gut ist es noch nicht, wir hatten schon mal einen viel besseren Stand";
Kette baute die Schwabentor-Uhr nur als verwaschenes Relief, Handstand schwab_v3 hatte lesbare Ziffern) fuer tools/uhren_wandbild.zifferblatt_aus_fotos, < 30 s, CPU.
Verwandt: tools/test_putz_uhr.py (4)/(5), tests/test_uhr_einzelfotos.py (5). Vorlaeufer: gold_maske + druckbar (Aufweiten um d_min/2 je Seite).

Befund (audit/uhr_f00_0.jpg der Kette): gold_maske (Farbton gelb, Saettigung >= 70) traf nur die SAEUME der blass-hellen Ziffern, Zeigerschaefte gar nicht;
druckbar weitete jeden duennen Saum um 3,5 cm je Seite auf -> die Luecken zwischen den Ziffernstrichen (5-8 cm) liefen zu, VIII/XII wurden Kleckse.
Teile:
  1 ZIFFERN  blass-helle (Saettigung ~50) 'III'-Ziffern: drei Striche 5 cm breit, Luecken 6 cm, auf dunklem Ring -> jeder Strich erhaben, jede Luecke offen.
  2 DRUCKBAR jeder erhabene Strich mindestens 0,8 mm H0 breit (7 cm), Relief-Raster = Mindestmass / 3.
  3 ZEIGER   blasser 3-cm-Zeiger im blauen Feld aus dem schaerfsten Foto erhaben; Oberleitung (dunkel, je Foto anders) nicht.
  4 WULST    Randwulst an den gemessenen Kreisen (aussen, innen) erhaben.
  5 ROT-PROBE (a) leere Scheibe ohne Zeichen -> im Ring zwischen den Wuelsten nichts erhaben; (b) altes Verfahren (gold_maske) auf denselben Fotos verfehlt die
             blassen Striche bzw. schliesst die Luecken -> Teil 1 schlaegt dort fehl (der Test unterscheidet alt/neu).
Werte sind Testgeometrie, kein Objektmass."""
import sys, os, json, numpy as np, cv2
HIER = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.join(os.path.dirname(HIER), "tools"); sys.path.insert(0, TOOLS)
from pfade import temp_ordner
import uhren_wandbild as UW

F = 0
def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text); F += 0 if ok else 1

c = 0.01; R = dict(u0=0.0, z1=5.0, nu=500, nz=500, zelle=c)
uu = R["u0"] + (np.arange(R["nu"]) + 0.5) * c; zz = R["z1"] - (np.arange(R["nz"]) + 0.5) * c; UU, ZZ = np.meshgrid(uu, zz)
UC, ZC, RA, RI = 2.5, 2.5, 1.5, 1.0; RM = 0.5 * (RA + RI); DM = 0.8 * 87 / 1000.0
BLASS = (185, 222, 236)                                                    # BGR, Saettigung ~55: unter der alten Goldschwelle (70)
TAN = (-0.11, 0.0, 0.11)                                                   # Strichmitten tangential (m): 5 cm Strich, 6 cm Luecke


def bild(seed, dx=0.0, dz=0.0, zeiger=0.5, zeichen=True, draht=None):
    rng = np.random.default_rng(seed); B = np.zeros((R["nz"], R["nu"], 3), np.float32); B[:] = (225, 228, 230); B += rng.normal(0, 2, B.shape)
    u_, z_ = UC + dx, ZC + dz; rr = np.hypot(UU - u_, ZZ - z_); ph = np.arctan2(UU - u_, ZZ - z_)
    B[rr <= RA] = (40, 36, 34); B[rr <= RI] = (160, 115, 70)                # Ring dunkel, Feld blau
    if zeichen:
        for n_ in range(12):
            a_ = np.radians(30 * n_); t_ = np.sin(ph - a_) * rr; r_ = np.cos(ph - a_) * rr
            for o_ in TAN: B[(np.abs(t_ - o_) < 0.025) & (r_ > RI + 0.08) & (r_ < RA - 0.10)] = BLASS
        B[(np.abs(np.sin(ph - zeiger)) * rr < 0.015) & (rr < 0.85 * RI) & (np.cos(ph - zeiger) > 0)] = BLASS
    if draht is not None: B[np.abs((ZZ - ZC) - draht * (UU - UC) - 0.3) < 0.012] = (25, 25, 25)
    B += rng.normal(0, 3, B.shape)
    return cv2.GaussianBlur(B.clip(0, 255).astype(np.uint8), (0, 0), 0.6 if seed == 0 else 1.2)   # Foto 0 = schaerfstes


def anlegen(T, zeichen=True):
    FF = os.path.join(T, "fassade_fein"); os.makedirs(os.path.join(FF, "ortho_f00_einzeln"), exist_ok=True)
    json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=R)]), open(os.path.join(FF, "fassaden.json"), "w"))
    for k, v in enumerate([dict(), dict(dx=0.06, dz=0.03, zeiger=0.7, draht=0.4), dict(dx=-0.05, dz=-0.04, zeiger=0.9, draht=-0.3), dict(dx=0.03, dz=0.06, zeiger=1.1)]):
        cv2.imwrite(os.path.join(FF, "ortho_f00_einzeln", f"foto{k}.png"), bild(k, zeichen=zeichen, **v))
    return FF


def raster(E):
    p = float(E["px"]); N = E["rel"].shape[0]; g_ = (np.arange(N) + 0.5) * p - 0.5 * N * p; X, Y = np.meshgrid(g_, -g_); return p, X, Y


def hoch_bei(E, r, a_, t):
    """Relief bei Radius r, Uhrwinkel a_ (rad, ab 12 im Uhrzeigersinn - im Fassaden-u = +X), tangential versetzt t (m)."""
    p, X, Y = raster(E); x = r * np.sin(a_) + t * np.cos(a_); y = r * np.cos(a_) - t * np.sin(a_)
    j = int((x + 0.5 * E["rel"].shape[0] * p) / p); i = int((0.5 * E["rel"].shape[0] * p - y) / p); return float(E["rel"][i, j])


def ziffern_pruefen(E, wer):
    rel = E["rel"]; hz = 0.10 + 0.07 - 0.01; n_str = n_lu = 0; tot = 0
    for n_ in range(12):
        a_ = np.radians(30 * n_)
        for rf in (-0.10, 0.0, 0.10):                                     # Strichmitte +- 10 cm (Strichenden liegen 2-3 cm neben den Wuelsten)
            n_str += sum(hoch_bei(E, RM + rf, a_, o_) >= hz for o_ in TAN); lu_ = [hoch_bei(E, RM + rf, a_, o_) < hz for o_ in (-0.055, 0.055)]; n_lu += sum(lu_); tot += 1
            if os.environ.get("ZB_DEBUG") and not all(lu_): print(f"    {wer}: Luecke zu bei {n_ * 30} Grad, r {RM + rf:.2f}: {lu_}")
    return n_str / (3 * tot), n_lu / (2 * tot)


T = temp_ordner("test_zifferblatt_gestalt_"); U = dict(u=UC, z=ZC, d_aussen=2 * RA, d_innen=2 * RI)
FF = anlegen(os.path.join(T, "a")); E = UW.zifferblatt_aus_fotos(FF, "f00", R, U, os.path.join(T, "a", "uhr.npz"))
pruef(E is not None, "Zifferblatt aus 4 Einzelfotos gerechnet")
if E is not None:
    s_, l_ = ziffern_pruefen(E, "neu")
    pruef(s_ >= 0.95, f"1 ZIFFERN: blasse Striche erhaben ({s_ * 100:.0f} % der Strichmitten, Soll >= 95)")
    pruef(l_ >= 0.90, f"1 ZIFFERN: Luecken zwischen den Strichen offen ({l_ * 100:.0f} %, Soll >= 90)")
    pruef(abs(float(E["px"]) - DM / 3) < 1e-6, f"2 DRUCKBAR: Relief-Raster {float(E['px']) * 100:.2f} cm = Mindestmass/3")
    p, X, Y = raster(E); g = E["rel"] >= 0.15; rr = np.hypot(X, Y)
    # Breite je erhabener Zeile quer zum Strich: Strich 12 Uhr (vertikal) - Zeilen bei Y = RM, Laufstuecke in X
    i = int((0.5 * g.shape[0] * p - RM) / p); lauf = np.diff(np.r_[0, g[i].astype(int), 0]); st = np.flatnonzero(lauf == 1); en = np.flatnonzero(lauf == -1)
    br = [(e_ - s0) * p for s0, e_ in zip(st, en) if abs((s0 + e_) / 2 * p - 0.5 * g.shape[0] * p) < 0.2]
    pruef(len(br) == 3 and min(br) >= DM - 1e-6, f"2 DRUCKBAR: Ziffer XII = 3 Striche je >= {DM * 100:.1f} cm ({[round(b * 100, 1) for b in br]} cm)")
    zh = [hoch_bei(E, r_, 0.5, 0.0) for r_ in (0.3, 0.5, 0.7)]
    pruef(min(zh) >= 0.06 + 0.07 - 0.01, f"3 ZEIGER: blasser Zeiger aus dem schaerfsten Foto erhaben ({[round(h, 3) for h in zh]})")
    dr = [hoch_bei(E, r_, a_, 0.0) for r_, a_ in ((RM, np.radians(105)), (RM, np.radians(255)))]           # Oberleitung kreuzt den Ring zwischen den Ziffern
    pruef(max(dr) < 0.15, f"3 ZEIGER: Oberleitung (1 Foto je Lage) nicht erhaben ({[round(h, 3) for h in dr]})")
    wa = float(np.median(E["rel"][(rr > RA - DM + p) & (rr < RA - p)])); wi = float(np.median(E["rel"][np.abs(rr - RI) < 0.5 * DM - p]))
    pruef(wa >= 0.16 and wi >= 0.12, f"4 WULST: Randwulst aussen {wa:.3f} / innen {wi:.3f} m erhaben")
FF = anlegen(os.path.join(T, "b"), zeichen=False); E0 = UW.zifferblatt_aus_fotos(FF, "f00", R, U, os.path.join(T, "b", "uhr.npz"))
if E0 is not None:
    p, X, Y = raster(E0); rr = np.hypot(X, Y); zw = (rr > RI + DM) & (rr < RA - DM - 2 * p)
    pruef(float((E0["rel"][zw] > 0.15).mean()) < 0.01, f"5a ROT-PROBE: leere Scheibe -> Ring ohne Zeichen ({(E0['rel'][zw] > 0.15).mean() * 100:.1f} % erhaben)")
else: pruef(False, "5a ROT-PROBE: leere Scheibe lieferte kein Relief (Wulst erwartet)")
alt = UW.zeichen_maske; UW.zeichen_maske = lambda b, *a, **k: UW.gold_maske(b)                     # altes Verfahren (Goldfarbe) auf denselben Fotos
try:
    Ea = UW.zifferblatt_aus_fotos(os.path.join(T, "a", "fassade_fein"), "f00", R, U, os.path.join(T, "a", "alt.npz"))
finally: UW.zeichen_maske = alt
sa, la = ziffern_pruefen(Ea, "alt") if Ea is not None else (0.0, 0.0)
pruef(sa < 0.95 or la < 0.90, f"5b ROT-PROBE: Goldfarb-Maske besteht Teil 1 NICHT (Striche {sa * 100:.0f} %, Luecken {la * 100:.0f} %)")
print("FEHLER: %d" % F if F else "ALLE BESTANDEN (Zifferblatt-Gestalt: blasse Ziffern, Luecken offen, druckbar, Zeiger, Wulst, Rot-Proben)")
sys.exit(1 if F else 0)
