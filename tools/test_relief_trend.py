#!/usr/bin/env python3
"""test_relief_trend.py - Ausgleichsebene der Hoehenbilder nur aus der Wandflaeche, Angleich fein -> grob mit Neigung (21.11.2026).
Anlass: Schwabentor w01 - Feinrechnung (tools/tiefe_lokal.py) zeigte oben +5 / Mitte -8 / unten +15 cm, Hub 28,8 cm. Ursache: Kleinste-Quadrate-Ebene ueber
ALLE Zellen, ein echter Vorsprung (Sockelband unten +20..40 cm) kippte sie. Gebaut wird rel + Ebene (relief_einsatz.koerper trend=True), dort kam der
Keil nicht an - wohl aber eine Neigung fein - grob von ~1 cm/m (nur Median-Versatz abgezogen, 3,7 cm Abweichung zur dichten Wolke).
  1. robuste_ebene: Steinrelief + Neigung + Sockelband 25 % der Flaeche -> Neigung auf 0,2 cm/m; Kleinste Quadrate liegt daneben (Test trennscharf).
  2. Guard: zu wenig Zellen -> Rueckfall kleinste Quadrate mit Grund.
  3. relief_mischen: fein = grob + Steine + Keil 1,5 cm/m -> gebautes Relief folgt dem groben auf < 1 cm; Gesims (in beiden) und Sockel (nur fein) bleiben;
     rel ohne Trend (Zeilenmediane der Wand +-1 cm); Keil 8 cm/m -> Guard Rueckfall Median-Versatz.
"""
import os, sys, subprocess, tempfile, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from relief_trend import robuste_ebene
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


rng = np.random.default_rng(7)
def steine(H, W, px):                                                     # Quader 0,5 x 0,3 m mit Fugen 2 cm tief, Bosse +-1 cm
    ii, jj = np.mgrid[0:H, 0:W]; z = ii * px; u = jj * px + 0.25 * ((z // 0.3) % 2)
    fuge = ((u % 0.5) < 0.02) | ((z % 0.3) < 0.02); return np.where(fuge, -0.02, 0.0) + rng.normal(0, 0.006, (H, W))


# 1 robuste Ebene gegen Vorsprung
H, W, px = 640, 350, 0.01; ii, jj = np.mgrid[0:H, 0:W]
wand = steine(H, W, px) + 0.012 * jj * px - 0.015 * ii * px + 0.3; d = wand.copy(); sockel = ii >= int(0.75 * H); d[sockel] += 0.30
c, drin, info = robuste_ebene(jj.ravel(), ii.ravel(), d.ravel())
ok(info["robust"] and abs(c[0] / px - 0.012) < 0.002 and abs(c[1] / px + 0.015) < 0.002, f"robuste Ebene: Neigung {c[0]/px*100:.2f}/{c[1]/px*100:.2f} cm/m (Soll 1,2/-1,5) trotz Sockel 25 %")
ok(drin.reshape(H, W)[sockel].mean() < 0.05 and drin.reshape(H, W)[~sockel].mean() > 0.8, "Sockel faellt als Vorsprung heraus, Wandflaeche bleibt drin")
G = np.c_[jj.ravel(), ii.ravel(), np.ones(H * W)]; cl = np.linalg.lstsq(G, d.ravel(), rcond=None)[0]
ok(abs(cl[1] / px + 0.015) > 0.03, f"Gegenprobe: kleinste Quadrate kippt ({cl[1]/px*100:.1f} cm/m) - der Test erkennt den alten Fehler")

# 2 Guard
c2, _, i2 = robuste_ebene(np.arange(30.0), np.arange(30.0) % 5, np.arange(30.0) * 0.01)
ok(not i2["robust"] and i2["grund"] and abs(c2[0] - 0.01) < 1e-9, f"Guard: {i2['grund']} -> kleinste Quadrate (Wert stimmt trotzdem)")
_, _, i3 = robuste_ebene([0.0, 1.0], [0.0, 1.0], [0.0, 1.0]); ok(not i3["robust"], "Guard: zu wenig Zellen -> kein robuster Schluss")

# 3 relief_mischen Ende-zu-Ende (kleines synthetisches Feld)
def npz(p, rel, px, eb, tr, **k):
    np.savez_compressed(p, rel=rel.astype(np.float32), a=np.array([0.0, 0.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]), u0=0.1, z0=0.0, px=px, ebene_abstand_m=eb, trend_je_m=np.array(tr), **k)

def lauf(keil_z):
    td = tempfile.mkdtemp(prefix="relief_trend_")
    Hg, Wg, pg = 128, 70, 0.05; gi, gj = np.mgrid[0:Hg, 0:Wg]; zg = (Hg - 1 - gi + 0.5) * pg
    grob = 0.02 * gj * pg + np.where((zg > 4.0) & (zg < 4.3), 0.15, 0.0)          # leichte Wandneigung in u, Gesims z 4,0-4,3 (in beiden)
    npz(os.path.join(td, "g.npz"), np.where(grob == 0, 1e-4, grob), pg, 0.0, [0.0, 0.0], putz=np.zeros((Hg, Wg), bool), generiert=np.zeros((Hg, Wg), bool))
    Hf, Wf, pf = 640, 349, 0.01; fi, fj = np.mgrid[0:Hf, 0:Wf]; zf = (Hf - 1 - fi + 0.5) * pf; uf = (fj + 0.5) * pf
    fein = 0.02 * uf + np.where((zf > 4.0) & (zf < 4.3), 0.15, 0.0) + steine(Hf, Wf, pf) + np.where(zf < 1.2, 0.25, 0.0) + keil_z * zf - 0.03
    rel = fein.copy(); rel[rng.random((Hf, Wf)) < 0.2] = 0.0                       # 20 % Loecher
    npz(os.path.join(td, "f.npz"), rel, pf, 0.0, [0.0, 0.0])
    r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "relief_mischen.py"), os.path.join(td, "f.npz"), os.path.join(td, "g.npz"), os.path.join(td, "m.npz")], capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); ok(False, "relief_mischen lief nicht")
    Z = np.load(os.path.join(td, "m.npz")); rl = Z["rel"].astype(np.float64); H_, W_ = rl.shape; p_ = float(Z["px"]); mi, mj = np.mgrid[0:H_, 0:W_]; tu, tz = [float(v) for v in Z["trend_je_m"]]
    geb = rl + float(Z["ebene_abstand_m"]) + tu * (mj + 0.5) * p_ - tz * (mi + 0.5) * p_; zm = (H_ - 1 - mi + 0.5) * p_; um = 0.1 + (mj + 0.5) * p_
    return r.stdout, Z, rl, geb, zm, um

out, Z, rl, geb, zm, um = lauf(0.015)
wand = (zm > 1.5) & ((zm < 3.9) | (zm > 4.4)); soll = 0.02 * (um - 0.1)
rows = [np.median((geb - soll)[(zm > z) & (zm < z + 0.4) & wand]) for z in np.arange(1.6, 6.0, 0.4) if ((zm > z) & (zm < z + 0.4) & wand).any()]
ok(max(abs(np.array(rows) - np.median(rows))) < 0.01, f"gebautes Relief folgt dem groben: Zeilen +-{max(abs(np.array(rows) - np.median(rows)))*100:.1f} cm (Keil 1,5 cm/m abgezogen)")
ok("Ebene" in str(Z["fein_angleich_guard"]) and abs(float(Z["fein_angleich_je_m"][1]) - 0.015) < 0.004, f"Angleich-Neigung z {float(Z['fein_angleich_je_m'][1])*100:.2f} cm/m gemeldet (Soll 1,5)")
ges = np.median(geb[(zm > 4.05) & (zm < 4.25)]) - np.median(geb[(zm > 3.3) & (zm < 3.8)]); ok(abs(ges - 0.15) < 0.02, f"Gesims (in beiden) bleibt: {ges*100:.1f} cm (Soll 15)")
so = np.median(geb[(zm > 0.2) & (zm < 1.0)]) - np.median(geb[(zm > 1.6) & (zm < 2.4)]); ok(abs(so - 0.25) < 0.03, f"Sockel (nur fein) bleibt: {so*100:.1f} cm (Soll 25)")
zr = [np.median(rl[(zm > z) & (zm < z + 0.4) & wand]) for z in np.arange(1.6, 6.0, 0.4) if ((zm > z) & (zm < z + 0.4) & wand).any()]
ok(np.ptp(zr) < 0.02 and bool(Z["ebene_robust"]), f"rel ohne Trend: Zeilenmediane der Wand Spanne {np.ptp(zr)*100:.1f} cm (vorher Keil durch den Sockel)")
out, Z, rl, geb, zm, um = lauf(0.08)
ok("Rueckfall" in str(Z["fein_angleich_guard"]) and "Rueckfall" in out, "Keil 8 cm/m -> Guard: Rueckfall Median-Versatz mit Meldung")
print(f"test_relief_trend: {n_ok} ok")
