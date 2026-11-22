#!/usr/bin/env python3
"""test_laibung_aus_fotos.py - fester synthetischer Test fuer tools/laibung_aus_fotos.py (21.11.2026 spaet), < 10 s, nur CPU.

Wand u = x, aussen -y (w = -y). Fenster A 0,60 m breit, Laden 0,80 m hinter der Wand; Fenster B 0,70 m, Laden 0,45 m hinter der Wand und in einer 0,10-m-Nische;
Modellflaeche (relief) im Fenster A bei s = -0,30 (wie ein schon geschnittenes Modell), sonst 0. Sechs Kameras links und rechts vor der Wand, eine direkt davor
(keine Stimme), eine mit verdeckter Laibung (Bild leer). Einzelfoto-Orthos werden aus der Strahlgeometrie gerechnet (Laden dunkel, Laibung hell).
Erwartung: T(A) = 0,80 +-0,04, T(B) = 0,45 +-0,04; tiefe B = 0,35 ab Nischengrund; Fenster C ohne Fotos bleibt unveraendert (rc 0, C ohne 'laibung').
"""
import sys, os, json, tempfile, shutil, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner   # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
H = os.path.dirname(os.path.abspath(__file__))
U0, U1, Z0, Z1, C = -3.0, 3.0, 9.0, 13.0, 0.01
WIN = [dict(u0=-2.0, u1=-1.4, z0=10.0, z1=11.8, T=0.80, b=(-2.0, -1.4), s=-0.30),
       dict(u0=1.0, u1=1.7, z0=10.0, z1=11.8, T=0.45, b=(1.0, 1.7), s=0.0)]
KAM = [(-12.0, 30.0), (-8.0, 15.0), (-6.0, 8.0), (9.0, 20.0), (7.0, 9.0), (5.0, 6.0), (-0.2, 25.0), (-9.0, 12.0)]


def ortho(Cu, Cw, leer=False):
    rng = np.random.default_rng(int(abs(Cu * 10 + Cw))); H_, W_ = int((Z1 - Z0) / C), int((U1 - U0) / C)
    g = np.full((H_, W_), 200.0) + rng.normal(0, 2, (H_, W_)); rel = np.full((H_, W_), 10000, np.uint16)
    uu = U0 + C * (np.arange(W_) + 0.5); zz = Z1 - C * (np.arange(H_) + 0.5)
    if leer: return np.zeros((H_, W_), np.uint8), rel
    for w in WIN:
        j = (uu >= w["u0"]) & (uu <= w["u1"]); i = (zz >= w["z0"]) & (zz <= w["z1"]); s = w["s"]
        lam = (Cw + w["T"]) / (Cw - s); ub = Cu + lam * (uu - Cu)          # Strahl durch die Modellflaeche (u, s) bis zur Ladenebene w = -T
        hell = np.where((ub >= w["b"][0]) & (ub <= w["b"][1]), 60.0, 235.0)
        g[np.ix_(i, j)] = hell[j][None, :]; rel[np.ix_(i, j)] = int(round((s + 10) * 1000))
    return np.clip(g, 1, 255).astype(np.uint8), rel


def main():
    import cv2
    d = temp_ordner("test_laib_"); ff = os.path.join(d, "fassade_fein"); ez = os.path.join(ff, "ortho_f00_einzeln"); mp = os.path.join(d, "messprotokoll"); au = os.path.join(d, "audit")
    for x in (ez, mp, au): os.makedirs(x)
    for n_, (Cu, Cw) in enumerate(KAM):
        g, r_ = ortho(Cu, Cw, leer=(n_ == len(KAM) - 1)); cv2.imwrite(os.path.join(ez, f"k{n_}.png"), g)
        if n_ == 0: rel = r_
        json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[-Cu, Cw, -1.5], f_px=1000, cx=0, cy=0)), open(os.path.join(mp, f"K-k{n_}.json"), "w"))   # R = I: Zentrum = -t = (Cu, -Cw)
    cv2.imwrite(os.path.join(ff, "relief_f00.png"), rel)
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[1, 0], n=[0, -1], raster=dict(u0=U0, z1=Z1, zelle=C))]), open(os.path.join(ff, "fassaden.json"), "w"))
    ob = os.path.join(d, "objekt.json"); json.dump({}, open(ob, "w"))
    fe = [dict(u0=-2.0, u1=-1.4, z0=10.0, z1=11.8, bogen=dict(form="rund", kaempfer=11.5, scheitel=11.8), tiefe=0.12, tiefe_quelle="ANNAHME"),
          dict(u0=1.0, u1=1.7, z0=10.0, z1=11.8, tiefe=0.12, tiefe_quelle="ANNAHME", nische=dict(u0=0.6, u1=2.1, z0=10.0, z1=12.5, tiefe=0.10)),
          dict(u0=2.2, u1=2.8, z0=5.0, z1=6.0, tiefe=0.12, tiefe_quelle="ANNAHME")]          # C: ausserhalb der Orthos
    fa = os.path.join(au, "fenster_auto.json"); json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=fe)), open(fa, "w"))
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(H, "laibung_aus_fotos.py"), fa, ff, ob], capture_output=True, text=True)
    F = 0
    def pruef(ok, t):
        nonlocal F; print(("  ok     " if ok else "  FEHLER ") + t); F += not ok
    pruef(r.returncode == 0, f"rc {r.returncode} {r.stdout.strip()[-300:]} {r.stderr[-300:]}")
    J = json.load(open(fa))["f00"]["fenster"]
    for q, w in zip(J[:2], WIN):
        L = q.get("laibung") or {}
        pruef(abs(L.get("tiefe_ab_wand", -9) - w["T"]) <= 0.04 and L.get("fotos", 0) >= 3, f"Fenster u {q['u0']}: Laibung {L.get('tiefe_ab_wand')} m (soll {w['T']}), {L.get('fotos')} Fotos, Seite {L.get('seite')}")
    pruef(abs(J[1].get("tiefe", 0) - 0.35) <= 0.04 and "Fotos" in J[1].get("tiefe_quelle", ""), f"B: Tiefe ab Nischengrund {J[1].get('tiefe')} (0,35), Quelle '{J[1].get('tiefe_quelle', '')[:40]}'")
    pruef("laibung" not in J[2] and J[2]["tiefe_quelle"] == "ANNAHME", "C ohne Fotos unveraendert")
    if F and os.environ.get("TEST_DEBUG"):
        for e in json.load(open(os.path.join(au, "laibung_aus_fotos.json")))["f00"][:1]:
            for p in e.get("punkte", []): print("   ", p)
    shutil.rmtree(d, ignore_errors=True)
    print(f"test_laibung_aus_fotos: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
