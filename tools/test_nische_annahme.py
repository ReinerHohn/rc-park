#!/usr/bin/env python3
"""test_nische_annahme.py - fester synthetischer Test (24.11.2026, WEG_HAND_ZU_KETTE Punkt 2: Blendnischen der Nordfenster fehlten), < 60 s (unter Last mehr), nur CPU.
Verwandt: tools/test_nischen_fenster.py (Paare/Form/Sweep), tools/test_laibung_aus_fotos.py (Fensterlaibung), tools/test_sohlbank.py (gemessene Sohlbank).
Vorlaeufer: keiner - die Faelle hier verwarf die Kette bisher ('Nischentiefe nicht messbar', 'Auskragung aus keiner Messung plausibel').

Nutzerplan 'belegte Form -> typisiert bauen, unsicheres Mass als ANNAHME, nie verwerfen' + Nutzer 24.11. 'Alle Masse muessen aus Fotos kommen':
  1 nischen_fenster: Nischenform aus 3 Einzelfotos belegt, Sweep im Wandring ohne sichere Zellen (glatter Putz) -> Nische GEBAUT, Tiefe = Platzhalter
    Druckmindestmass mit 'ANNAHME'. ROTE PROBE: der alte Stand verwarf sie ('Fenster ohne Nische').
  2 naher Wandring unsicher, weiter Ring (0,1-1,0 m) sicher -> Tiefe 0,15 aus dem Sweep (Quelle 'weiter Wandring', keine ANNAHME).
  3 Geschwister: A nur Platzhalter, B mit Sweep-Mass -> A uebernimmt B als 'ANNAHME Geschwister'.
  4 Form NICHT aus >= 3 Fotos belegt + Sweep unmessbar -> weiter keine Nische (nichts erfinden).
  5 laibung_aus_fotos: Nischenlaibung in 10 Schraegfotos (Nischengrund 0,15 hinter der Wand) -> Nischentiefe 0,15 +-0,03 ersetzt die ANNAHME.
  6 sohlbank_aus_fotos.annahme_bank: Band in 5 Fotos, Steigung unbestimmt -> Sohlbank mit Auskragung = gemessene Stirnhoehe (ANNAHME benannt).
  7 bauteile.nische_tiefe_guard: Wand 0,20 m massiv, Nische 0,15 + Oeffnung 0,12 -> zusammen <= 0,20 - Druckmindestmass; Mindestmass 0,07.
"""
import sys, os, json, shutil, subprocess, argparse, numpy as np
H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)
from pfade import temp_ordner
import nischen_fenster as NF

U0, U1, Z0, Z1, C = -4.0, 4.0, 20.0, 28.0, 0.01
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text); F += not ok


def innen(UU, ZZ, form, uL, uR, zs, zk, zt):
    a = (uR - uL) / 2; m = (uL + uR) / 2; s = (UU >= uL) & (UU <= uR) & (ZZ >= zs)
    return s & ((ZZ <= zk) | (((UU - m) / a) ** 2 + ((ZZ - zk) / max(zt - zk, 1e-6)) ** 2 <= 1))


def wandbild(seed):
    rng = np.random.default_rng(seed); Hh, W = int((Z1 - Z0) / C), int((U1 - U0) / C)
    g = np.full((Hh, W), 180.0) + rng.normal(0, 2.0, (Hh, W))
    uu = U0 + C * (np.arange(W) + 0.5); zz = Z1 - C * (np.arange(Hh) + 0.5); UU, ZZ = np.meshgrid(uu, zz)
    for (nu0, nu1), (fu0, fu1) in (((-3.0, -1.0), (-2.3, -1.7)), ((1.0, 3.0), (1.7, 2.3))):      # zwei gleiche Rundbogennischen mit Rundbogenfenster
        g[innen(UU, ZZ, "rund", nu0, nu1, 23.0, 24.4, 25.4)] = 150
        g[innen(UU, ZZ, "rund", fu0, fu1, 23.0, 24.5, 24.8)] = 60
    return np.clip(g, 1, 255).astype(np.uint8)


def sweep(gut_fn):
    c = 0.04; Hh, W = int((Z1 - Z0) / c), int((U1 - U0) / c)
    uu = U0 + c * (np.arange(W) + 0.5); zz = Z1 - c * (np.arange(Hh) + 0.5); UU, ZZ = np.meshgrid(uu, zz); w = np.zeros((Hh, W), np.float32)
    for (nu0, nu1), (fu0, fu1) in (((-3.0, -1.0), (-2.3, -1.7)), ((1.0, 3.0), (1.7, 2.3))):
        w[innen(UU, ZZ, "rund", nu0, nu1, 23.0, 24.4, 25.4)] = -0.15; w[innen(UU, ZZ, "rund", fu0, fu1, 23.0, 24.5, 24.8)] = -0.35
    return dict(w=w, gut=gut_fn(UU, ZZ), sicher=np.ones_like(w), u0=U0, z1=Z1, zelle=c)


def nah_unsicher(UU, ZZ, nur_links=False, weit_auch=False):
    """Zellen 0,02-0,45 m um die Nischen unsicher (glatter Putz); weit_auch: die ganze Wand ausserhalb der Nischen unsicher."""
    g = np.ones(UU.shape, bool)
    for nu0, nu1 in ((-3.0, -1.0),) + (() if nur_links else ((1.0, 3.0),)):
        zone = (UU > nu0 - 0.45) & (UU < nu1 + 0.45) & (ZZ > 22.55) & (ZZ < 25.85); kern = (UU > nu0 + 0.02) & (UU < nu1 - 0.02) & (ZZ > 23.02) & (ZZ < 25.38)
        g &= ~(zone & ~kern)
    if weit_auch: g &= (UU > -3.0) & (UU < -1.0) & (ZZ > 23.0) & (ZZ < 25.4) | (UU > 1.0) & (UU < 3.0) & (ZZ > 23.0) & (ZZ < 25.4)
    return g


def args():
    return argparse.Namespace(kante=4.0, anteil_min=0.5, nische_min=0.05, flaeche_max_anteil=0.5, fenster_tiefe=0.12)


KAESTEN = [(-3.08, -0.94, 22.96, 25.47, 3), (-2.27, -1.68, 23.06, 24.76, 5), (0.95, 3.06, 22.95, 25.48, 3), (1.72, 2.33, 23.04, 24.79, 4)]


_BILDER = {}
_fak = NF.form_aus_kanten; _CACHE = {}


def _form_cache(B, kasten, innen=None, **kw):
    """Formsuche je (Bild, Zone) nur einmal (Laufzeit: form_aus_kanten ~1-4 s; die Faelle 1-4 unterscheiden sich nur im Sweep)."""
    k = (id(B), tuple(round(float(x), 4) for x in kasten), None if innen is None else tuple(round(float(x), 4) for x in innen), tuple(sorted(kw.items())))
    if k not in _CACHE: _CACHE[k] = _fak(B, kasten, innen=innen, **kw)
    import copy; return copy.deepcopy(_CACHE[k])                             # Kopie: form_bestaetigen aendert in place


def fall_nischen(gut_fn, mit_fotos=True):
    if not _BILDER: _BILDER["B"] = NF.Bild(wandbild(1), U0, Z1, C); _BILDER["fotos"] = [(f"e{i}", NF.Bild(wandbild(10 + i), U0, Z1, C)) for i in range(NF.MIN_FOTOS)]
    NF.form_aus_kanten = _form_cache
    B = _BILDER["B"]; fotos = _BILDER["fotos"] if mit_fotos else []
    E, br = NF.fassade_auswerten(B, KAESTEN, sweep(gut_fn), args(), (), fotos, [])
    return sorted(E, key=lambda q: q["u0"]), br


def teste_nischen():
    dm = NF.druck_min() if hasattr(NF, "druck_min") else 0.0696          # rote Probe gegen den alten Stand: dort fehlt druck_min
    E, br = fall_nischen(lambda U, Z: nah_unsicher(U, Z, weit_auch=True))
    pruef(len(E) == 2 and all(q.get("nische") for q in E), "1 belegte Form, Sweep unmessbar -> beide Nischen gebaut (rote Probe: alter Stand 'Fenster ohne Nische'): "
          + "; ".join(r["urteil"][:70] for r in br))
    if len(E) == 2 and all(q.get("nische") for q in E):
        pruef(all(abs(q["nische"]["tiefe"] - dm) < 1e-6 and "ANNAHME" in q["nische"]["tiefe_quelle"] for q in E), f"1 Tiefe = Platzhalter Druckmindestmass {dm} mit ANNAHME")
    E, br = fall_nischen(lambda U, Z: nah_unsicher(U, Z))
    ok = len(E) == 2 and all(q.get("nische") for q in E)
    pruef(ok and all(abs(q["nische"]["tiefe"] - 0.15) <= 0.03 and "weiter Wandring" in q["nische"]["tiefe_quelle"] and "ANNAHME" not in q["nische"]["tiefe_quelle"] for q in E),
          "2 weiter Wandring misst 0,15: " + "; ".join(f"{q['nische']['tiefe']} {q['nische']['tiefe_quelle'][:45]}" for q in E if q.get("nische")))
    E, br = fall_nischen(lambda U, Z: nah_unsicher(U, Z, nur_links=True, weit_auch=False) & ~((U < 0) & ~((U > -3.0) & (U < -1.0) & (Z > 23.0) & (Z < 25.4))))
    ok = len(E) == 2 and all(q.get("nische") for q in E)
    pruef(ok and "Geschwister" in E[0]["nische"]["tiefe_quelle"] and abs(E[0]["nische"]["tiefe"] - E[1]["nische"]["tiefe"]) < 1e-6 and abs(E[1]["nische"]["tiefe"] - 0.15) <= 0.03,
          "3 Geschwister: " + "; ".join(f"{q['nische']['tiefe']} {q['nische']['tiefe_quelle'][:50]}" for q in E if q.get("nische")))
    E, br = fall_nischen(lambda U, Z: nah_unsicher(U, Z, weit_auch=True), mit_fotos=False)
    pruef(not any(q.get("nische") for q in E), "4 Form nicht aus Fotos belegt + Sweep unmessbar -> keine Nische: " + "; ".join(r["urteil"][:60] for r in br))


# ---------------------------------------------------------------- 5 Nischenlaibung aus Schraegfotos
LU0, LU1, LZ0, LZ1 = -3.0, 3.0, 9.0, 13.0
NI = dict(u0=-1.0, u1=1.0, z0=10.0, z1=12.4, T=0.15); FE = dict(u0=-0.3, u1=0.3, z0=10.0, z1=11.8)
KAM = [(-12.0, 30.0), (-8.0, 15.0), (-6.0, 8.0), (-10.0, 22.0), (-4.0, 10.0), (9.0, 20.0), (7.0, 9.0), (5.0, 6.0), (8.0, 14.0), (4.0, 12.0), (-0.1, 25.0)]


def ortho_nische(Cu, Cw):
    rng = np.random.default_rng(int(abs(Cu * 10 + Cw))); Hh, W = int((LZ1 - LZ0) / C), int((LU1 - LU0) / C)
    g = np.full((Hh, W), 200.0) + rng.normal(0, 2, (Hh, W)); uu = LU0 + C * (np.arange(W) + 0.5); zz = LZ1 - C * (np.arange(Hh) + 0.5)
    j = (uu >= NI["u0"]) & (uu <= NI["u1"]); i = (zz >= NI["z0"]) & (zz <= NI["z1"])
    ub = Cu + (Cw + NI["T"]) / Cw * (uu - Cu)                                 # Strahl durch die Wandebene bis zum Nischengrund w = -T
    wert = np.where((ub >= NI["u0"]) & (ub <= NI["u1"]), 170.0, 235.0)       # Grund mittelgrau, Laibung hell
    g[np.ix_(i, j)] = wert[j][None, :]
    jf = (uu >= FE["u0"]) & (uu <= FE["u1"]); i_f = (zz >= FE["z0"]) & (zz <= FE["z1"]); g[np.ix_(i_f, jf)] = 60.0
    return np.clip(g, 1, 255).astype(np.uint8)


def teste_laibung():
    import cv2
    d = temp_ordner("test_nische_laib_"); ff = os.path.join(d, "fassade_fein"); ez = os.path.join(ff, "ortho_f00_einzeln"); mp = os.path.join(d, "messprotokoll"); au = os.path.join(d, "audit")
    try:
        for x in (ez, mp, au): os.makedirs(x)
        for n_, (Cu, Cw) in enumerate(KAM):
            cv2.imwrite(os.path.join(ez, f"k{n_}.png"), ortho_nische(Cu, Cw))
            json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[-Cu, Cw, -1.5], f_px=1000, cx=0, cy=0)), open(os.path.join(mp, f"K-k{n_}.json"), "w"))
        json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[1, 0], n=[0, -1], raster=dict(u0=LU0, z1=LZ1, zelle=C))]), open(os.path.join(ff, "fassaden.json"), "w"))
        ob = os.path.join(d, "objekt.json"); json.dump({}, open(ob, "w"))
        rb = dict(form="rund", kaempfer=11.4, scheitel=12.4)
        fe = [dict(FE, bogen=dict(form="rund", kaempfer=11.5, scheitel=11.8), tiefe=0.12, tiefe_quelle="ANNAHME 0.12",
                   nische=dict(u0=NI["u0"], u1=NI["u1"], z0=NI["z0"], z1=NI["z1"], bogen=rb, tiefe=NF.druck_min(), tiefe_quelle=NF.ANNAHME_PLATZHALTER))]
        fa = os.path.join(au, "fenster_auto.json"); json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=fe)), open(fa, "w"))
        r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(H_, "laibung_aus_fotos.py"), fa, ff, ob], capture_output=True, text=True)
        N = json.load(open(fa))["f00"]["fenster"][0]["nische"]
        pruef(abs(N["tiefe"] - NI["T"]) <= 0.03 and N["tiefe_quelle"].startswith("Fotos: Nischenlaibung"),
              f"5 Nischenlaibung aus Fotos: {N['tiefe']} (soll {NI['T']}), '{N['tiefe_quelle'][:60]}' rc {r.returncode} {r.stdout.strip()[-200:]} {r.stderr[-200:]}")
    finally: shutil.rmtree(d, ignore_errors=True)


def teste_sohlbank():
    import sohlbank_aus_fotos as SB
    a = argparse.Namespace(min_fotos=3, k_spanne=0.1, kontrast_rel=0.4, max_auskragung=0.5)
    kam = {f"k{i}": (cu, cw, 1.5) for i, (cu, cw) in enumerate(((-6.0, 9.0), (-3.0, 12.0), (0.0, 15.0), (3.0, 20.0), (6.0, 26.0)))}
    P = []
    for i, (nm, (cu, cw, cz)) in enumerate(kam.items()):
        ka = (23.0 - cz) / cw; H = 0.06 + 0.004 * ka + 0.015 * (-1) ** i      # Steigung klein + Streuung gross = Auskragung nicht bestimmbar, Stirn ~0,06
        P.append(dict(foto=nm, s=0.0, kappa=ka, H=H, Y_unten=22.94 + 0.003 * i, Y_oben=22.94 + H, u_links=-2.12 - 0.01 * i, u_rechts=-0.88 + 0.01 * i))
    A = SB.auskragung([P], a)
    pruef("fehler" in A, "6 Vorbedingung: Auskragung aus der Blickschraege unbestimmt (" + str(A.get("fehler", ""))[:60] + ")")
    e = SB.annahme_bank(P, kam, (-2.1, -0.9, 23.0, -1.8, -1.2), A, 0, a, dict(A, geschwister=1))
    ok = "fehler" not in e and abs(e["auskragung"] - 0.06) <= 0.01 and "ANNAHME" in e.get("auskragung_quelle", "") and abs(e["z0"] - 22.946) <= 0.01 and e["u1"] - e["u0"] > 1.0
    pruef(ok, f"6 Sohlbank ANNAHME: Auskragung {e.get('auskragung')} (Stirnhoehe 0,06 <= Bandhoehe), z0 {e.get('z0')}, u {e.get('u0')}..{e.get('u1')}, '{str(e.get('auskragung_quelle'))[:70]}'")
    A2 = dict(A, auskragung_bandhoehe=dict(A["auskragung_bandhoehe"] or {}, achsabschnitt=[0.41]))          # Stirn hoeher als das gesehene Band (Kopie 1122 f04)
    e2 = SB.annahme_bank(P, kam, (-2.1, -0.9, 23.0, -1.8, -1.2), A2, 0, a, dict(A2, geschwister=1))
    P3 = [dict(p, u_links=None) for p in P]                                    # linkes Ende in keinem Foto frei (Schatten/verdeckt)
    e3 = SB.annahme_bank(P3, kam, (-2.1, -0.9, 23.0, -1.8, -1.2), A, 0, a, dict(A, geschwister=1))
    A4 = dict(A, auskragung_bandhoehe=dict(A["auskragung_bandhoehe"] or {}, d=-0.025, streuung=0.01, achsabschnitt=[0.06]))   # Fotos messen sicher ~0 (Schwabentor f00 zb)
    e4 = SB.annahme_bank(P, kam, (-2.1, -0.9, 23.0, -1.8, -1.2), A4, 0, a, dict(A4, geschwister=1))
    pruef("fehler" in e4 and "KEINE Auskragung" in e4["fehler"], f"6 Fotos messen sicher keine Auskragung -> keine ANNAHME-Bank ({str(e4.get('fehler'))[-60:]})")
    pruef("fehler" in e2 and "fehler" in e3, f"6 keine ANNAHME-Bank bei Stirn > Band ({str(e2.get('fehler'))[-50:]}) oder ohne freie Enden ({str(e3.get('fehler'))[-45:]})")


def teste_guard():
    from manifold3d import Manifold as M
    import bauteile as BT
    W = BT.Wand(np.array([0.0, 0.0]), np.array([1.0, 0.0]), aussen=np.array([0.0, -1.0]))      # u = x ab o (wie fenster_aus_json: Wand(o, o + d, o + n))
    k = M.cube((8.0, 0.20, 28.0)).translate((-4.0, 0.0, 0.0))             # Wand 0,20 m dick, Aussenflaeche y = 0 (aussen -y)
    dm = 0.0696; N = dict(u0=-1.0, u1=1.0, z0=23.0, z1=25.4)
    d_ = BT.wand_dicke(k, W, 0.0, 23.6, w_max=1.0)
    pruef(abs(d_ - 0.20) <= 0.015, f"7 Wanddicke gemessen {d_:.3f} (0,20)")
    t0, tf, v = BT.nische_tiefe_guard(k, W, N, 0.15, 0.12, dm)
    pruef(t0 + tf <= 0.20 - dm + 0.015 and t0 > 0.03 and tf >= dm - 1e-9 and v, f"7 Guard: Nische {t0:.3f} + Oeffnung {tf:.3f} <= {0.20 - dm:.3f}; {v}")
    t0, tf, v = BT.nische_tiefe_guard(M.cube((8.0, 2.0, 28.0)).translate((-4.0, 0.0, 0.0)), W, N, 0.03, 0.12, dm)
    pruef(abs(t0 - dm) < 1e-9 and abs(tf - 0.12) < 1e-9, f"7 dicke Wand: Nische 0,03 -> Druckmindestmass {t0:.3f}, Oeffnung bleibt {tf:.3f}")


def main():
    teste_nischen(); teste_laibung(); teste_sohlbank(); teste_guard()
    print(f"test_nische_annahme: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
