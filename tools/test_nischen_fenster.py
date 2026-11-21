#!/usr/bin/env python3
"""test_nischen_fenster.py - fester synthetischer Test fuer tools/nischen_fenster.py (+ Bau in bauteile.fenster_aus_json), < 10 s, nur CPU.

Synthetische Wand (1 cm/px, glatter Putz mit Rauschen), Fall Schwabentor f00 nachgestellt, aber mit eigenen Massen:
  A: Rundbogennische 2,00 m (Sohle 23,00, Scheitel 25,40) mit Rundbogenfenster 0,60 m (Scheitel 24,80) - SCHWACHE Nischenkanten (Putz +-15 Grauwerte)
  B: Nische mit geradem Sturz 1,80 m (Sohle 23,10, Sturz 25,00) mit Rundbogenfenster 0,70 m, dazu eine helle SCHRAEGE Stoerlinie quer durch (Ortho-Naht/Mast)
  C: Erkennerpaar ohne irgendeine Kante im Bild -> darf kein Fenster werden
  D: grosser Sammelkasten ueber A und B (Erkenner 'bogen' ueber alles) -> keine Nische (enthaelt zwei Zonen)
Tiefe (Sweep-Raster 4 cm): Wand 0, Nische -0,15, Fenster -0,35 (also 0,20 hinter dem Nischengrund).
Erwartung: genau 2 Paare; Breiten/Sohle/Scheitel je +-4 cm; Formen A rund/rund, B gerade/rund; Nischentiefe 0,15 +-0,05, Fenstertiefe 0,20 +-0,05;
Bau: Koerper bleibt ein Stueck, Volumen sinkt um Nische + Fenster (+-15 %).
"""
import sys, os, json, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nischen_fenster as NF

U0, U1, Z0, Z1, C = -4.0, 4.0, 20.0, 28.0, 0.01
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def bild():
    rng = np.random.default_rng(7); H, W = int((Z1 - Z0) / C), int((U1 - U0) / C)
    g = np.full((H, W), 180.0) + rng.normal(0, 2.0, (H, W))
    uu = U0 + C * (np.arange(W) + 0.5); zz = Z1 - C * (np.arange(H) + 0.5); UU, ZZ = np.meshgrid(uu, zz)

    def innen(form, uL, uR, zs, zk, zt):
        a = (uR - uL) / 2; m = (uL + uR) / 2; seite = (UU >= uL) & (UU <= uR) & (ZZ >= zs)
        if form == "gerade": return seite & (ZZ <= zt)
        return seite & ((ZZ <= zk) | (((UU - m) / a) ** 2 + ((ZZ - zk) / (zt - zk)) ** 2 <= 1))
    g[innen("rund", -3.0, -1.0, 23.0, 24.4, 25.4)] = 165          # A: Nische, schwach
    g[innen("rund", -2.3, -1.7, 23.0, 24.5, 24.8)] = 60           # A: Fenster
    g[innen("gerade", 1.1, 2.9, 23.1, 25.0, 25.0)] = 196          # B: Nische, heller (Licht von der anderen Seite)
    g[innen("rund", 1.65, 2.35, 23.1, 24.55, 24.9)] = 70           # B: Fenster
    d = np.abs((UU - 1.0) * 5.0 - (ZZ - 21.5) * 1.2) / np.hypot(5.0, 1.2)   # B: schraege Stoerlinie (3 cm breit)
    g[d < 0.015] = 250
    return np.clip(g, 0, 255).astype(np.uint8)


def tiefe():
    c = 0.04; H, W = int((Z1 - Z0) / c), int((U1 - U0) / c)
    uu = U0 + c * (np.arange(W) + 0.5); zz = Z1 - c * (np.arange(H) + 0.5); UU, ZZ = np.meshgrid(uu, zz); w = np.zeros((H, W), np.float32)
    w[(UU > -3.0) & (UU < -1.0) & (ZZ > 23.0) & ((ZZ < 24.4) | ((UU + 2.0) ** 2 + (ZZ - 24.4) ** 2 < 1.0))] = -0.15
    w[(UU > -2.3) & (UU < -1.7) & (ZZ > 23.0) & ((ZZ < 24.5) | ((UU + 2.0) ** 2 + (ZZ - 24.5) ** 2 < 0.09))] = -0.35
    w[(UU > 1.1) & (UU < 2.9) & (ZZ > 23.1) & (ZZ < 25.0)] = -0.15
    w[(UU > 1.65) & (UU < 2.35) & (ZZ > 23.1) & ((ZZ < 24.55) | ((UU - 2.0) ** 2 + (ZZ - 24.55) ** 2 < 0.1225))] = -0.35
    return dict(w=w, gut=np.ones_like(w, bool), sicher=np.ones_like(w), u0=U0, z1=Z1, zelle=c)


def main():
    import cv2
    d = tempfile.mkdtemp(prefix="test_nischen_"); fo = os.path.join(d, "fassade"); ff = os.path.join(d, "fassade_fein"); au = os.path.join(d, "audit")
    for x in (fo, ff, au): os.makedirs(x)
    cv2.imwrite(os.path.join(ff, "ortho_f00.png"), bild()); np.savez(os.path.join(fo, "tiefe_f00.npz"), **tiefe())
    json.dump(dict(fassaden=[dict(id="f00", raster=dict(u0=U0, z1=Z1, nu=800, nz=800, zelle=C))]), open(os.path.join(ff, "fassaden.json"), "w"))
    el = [dict(klasse="fenster", u0=-3.12, u1=-0.92, z0=22.95, z1=25.50, stimmen=3), dict(klasse="fenster", u0=-2.28, u1=-1.66, z0=23.08, z1=24.75, stimmen=5),   # A (Kaesten +-5-12 cm daneben)
          dict(klasse="bogen", u0=1.18, u1=2.99, z0=23.02, z1=25.10, stimmen=3), dict(klasse="fenster", u0=1.70, u1=2.30, z0=23.15, z1=24.80, stimmen=3),       # B
          dict(klasse="fenster", u0=-3.5, u1=-1.5, z0=20.3, z1=22.0, stimmen=3), dict(klasse="fenster", u0=-2.8, u1=-2.2, z0=20.5, z1=21.6, stimmen=3),          # C: keine Kanten
          dict(klasse="bogen", u0=-3.3, u1=3.2, z0=22.8, z1=25.9, stimmen=4)]                                                                                    # D: Sammelkasten
    json.dump(dict(fassaden=dict(f00=dict(elemente=el))), open(os.path.join(fo, "elemente.json"), "w"))
    fa = os.path.join(au, "fenster_auto.json")
    json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fotos=[], fenster=[dict(u0=1.93, u1=2.52, z0=23.12, z1=24.81, teiler=[], kaempfer=None, scheiben=1, stimmen_min=3, sprossen=[])])), open(fa, "w"))
    sys.argv = ["nischen_fenster.py", fa, fo, ff]
    rc = NF.main(); pruef(rc == 0, f"rc {rc} (0 = Paare eingetragen)")
    J = json.load(open(fa))["f00"]["fenster"]; R = json.load(open(os.path.join(au, "nischen_fenster.json")))["f00"]
    pruef(len(J) == 2 and all(q.get("nische") for q in J), f"2 Fenster mit Nische (ist {len(J)}; altes Rechteck B ersetzt)")
    pruef(any(r["urteil"].startswith("kein Fenster") for r in R), "Zone C ohne Kanten -> kein Fenster: " + "; ".join(r["urteil"][:50] for r in R if r["zone_aussen"][2] < 21))
    J = sorted(J, key=lambda q: q["u0"])
    soll = [dict(n=(-3.0, -1.0, 23.0, 25.4, "rund"), f=(-2.3, -1.7, 24.8, "rund")), dict(n=(1.1, 2.9, 23.1, 25.0, "gerade"), f=(1.65, 2.35, 24.9, "rund"))]
    for q, s in zip(J, soll):
        N = q["nische"]; n_ = s["n"]; f_ = s["f"]
        pruef(max(abs(N["u0"] - n_[0]), abs(N["u1"] - n_[1]), abs(N["z0"] - n_[2]), abs(N["z1"] - n_[3])) <= 0.04 and N["bogen"]["form"] == n_[4],
              f"Nische {N['u0']:.2f}..{N['u1']:.2f} z {N['z0']:.2f}..{N['z1']:.2f} {N['bogen']['form']} (soll {n_})")
        pruef(max(abs(q["u0"] - f_[0]), abs(q["u1"] - f_[1]), abs(q["z1"] - f_[2]), abs(q["z0"] - n_[2])) <= 0.04 and q["bogen"]["form"] == f_[3],
              f"Fenster {q['u0']:.2f}..{q['u1']:.2f} z {q['z0']:.2f}..{q['z1']:.2f} {q['bogen']['form']} (soll {f_})")
        pruef(abs(N["tiefe"] - 0.15) <= 0.05 and abs(q["tiefe"] - 0.20) <= 0.05 and "ANNAHME" not in q["tiefe_quelle"], f"Tiefen Nische {N['tiefe']:.2f} (0,15) Fenster {q['tiefe']:.2f} (0,20)")
    # Bau (bauteile.fenster_aus_json): Nische flach + Fenster tiefer, Koerper bleibt ein Stueck
    from bauteile import fenster_aus_json, DURCH
    from manifold3d import Manifold as M
    k = M.cube((8.0, 3.0, 28.0)).translate((-4.0, 0.0, 0.0)); k2, bel = fenster_aus_json(k, fa)
    dv = k.volume() - k2.volume(); erw = sum(0.15 * NF_fl(q["nische"]) + 0.20 * NF_fl(q) for q in J)
    pruef(len(k2.decompose()) == 1 and abs(dv - erw) <= 0.15 * erw and len(bel) == 1, f"Bau: Abzug {dv:.3f} m3 (erwartet {erw:.3f}), {len(k2.decompose())} Stueck")
    import shutil; shutil.rmtree(d, ignore_errors=True)
    print(f"test_nischen_fenster: {F} Fehler"); return 1 if F else 0


def NF_fl(o):
    """Flaeche eines Umrisses (Polygon aus NF.umriss)."""
    b = o["bogen"]; P = NF.umriss(b["form"], o["u0"], o["u1"], o["z0"], b["kaempfer"], b["scheitel"], schritt=0.005)
    x, y = P[:, 0], P[:, 1]; return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


if __name__ == "__main__": sys.exit(main())
