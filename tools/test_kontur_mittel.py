"""Beweistest (synthetisch): Mittelform aus verrauschten Kopien, Kreisbogen-RANSAC. Aufruf: python tools/test_kontur_mittel.py --synth"""
import sys, numpy as np; sys.path.insert(0, __file__.rsplit("/", 1)[0]); import kontur_mittel as K
def fenster():
    P = [(0, 0), (40, 0), (40, 70), (20, 90), (0, 70)]; return np.array(P, float)          # Rechteck mit Spitzbogen oben
def main():
    rng = np.random.default_rng(1); T = K.umtasten(fenster(), 48); ok = True
    inst = []
    for i in range(5):
        s = 1 + rng.normal(0, 0.03); sh = rng.normal(0, 200, 2); P = fenster() * s + sh + rng.normal(0, 1.5, fenster().shape); inst.append(np.roll(P, rng.integers(0, 5), axis=0))
    m = K.mittelform(inst); F = m["form"] * m["skala"]; Tn = (T - T.mean(0)); Tn = Tn / np.sqrt(abs(K.flaeche(K.ccw(fenster())))) * m["skala"]
    # Vergleich Mittelform gegen Wahrheit: Punkt-Abstand zur naechsten Wahrheits-Kante (translationsfrei, beide Schwerpunkt 0)
    from scipy.spatial import cKDTree
    dense = K.umtasten(fenster(), 2000); dense = dense - dense.mean(0); d = cKDTree(dense).query(F)[0]; print("Mittelform: mittlere Abweichung %.2f px, max %.2f px (Rauschen je Eckpunkt 1.5 px, Skala +-3 %%)" % (d.mean(), d.max())); ok &= d.mean() < 2.5
    print("Abweichung je Instanz (px):", [round(a, 1) for a in m["abweichung"]]); ok &= max(m["abweichung"]) < 6
    # Ausreisser: eine Instanz komplett falsch -> Median muss robust bleiben
    bad = inst + [np.array([(0, 0), (80, 0), (80, 30), (0, 30)], float) + 500]; m2 = K.mittelform(bad); d2 = cKDTree(dense).query(m2["form"] * m2["skala"])[0]; print("mit Ausreisser: mittlere Abweichung %.2f px" % d2.mean()); ok &= d2.mean() < 4
    # Boegen: zwei echte Boegen (Punkte mit Tangentenrichtung) in dichtem Zufalls-Kantenfeld (viele kurze Segmente in Zufallsrichtung): nur die echten duerfen gefunden werden
    pts, dirs = [], []
    for (cx, cy, r, a0, a1) in [(100, 200, 60, 3.4, 6.0), (300, 200, 80, 3.3, 6.1)]:
        a = rng.uniform(a0, a1, 300); pts.append(np.c_[cx + r * np.cos(a), cy + r * np.sin(a)] + rng.normal(0, 0.8, (300, 2))); dirs.append(np.c_[-np.sin(a), np.cos(a)])
    n = 6000; pts.append(rng.uniform(0, 400, (n, 2))); ang = rng.uniform(0, np.pi, n); dirs.append(np.c_[np.cos(ang), np.sin(ang)])
    B = K.boegen_finden(np.vstack(pts), 30, 150, D=np.vstack(dirs)); print("Boegen gefunden:", [(round(b['cx']), round(b['cy']), round(b['r'], 1), round(b['spann_grad'])) for b in B])
    ok &= len(B) == 2; rs = sorted(round(b["r"]) for b in B[:2]); sp = sorted(round(b['spann_grad']) for b in B[:2]); print('Radien', rs, 'Oeffnungswinkel (soll ca. 149 und 160):', sp)
    ok &= len(rs) == 2 and abs(rs[0] - 60) < 3 and abs(rs[1] - 80) < 3 and abs(sp[0] - 149) < 12 and abs(sp[1] - 160) < 12
    print("ALLE BEWEISE BESTANDEN" if ok else "FEHLGESCHLAGEN"); sys.exit(0 if ok else 1)
if "--synth" in sys.argv: main()
else: print(__doc__)
