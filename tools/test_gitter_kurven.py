"""Beweistest gitter_kurven.py (synthetisch): Gerade, Kreisbogen (R 1,9 m, 150 Grad), kubische Bezier, Bogen in 2 Fragmenten (Luecke 33 cm) und Gerade in 2 Fragmenten (Luecke 20 cm) -> je EIN Verbund, je 5 'Referenzfotos' mit 1 cm Rauschen,
plus eine Gerade, die schon im Eingabegitter steht (muss ausgeschlossen werden). Erwartung: 1 Bogen (R +-3 cm, Zentrum +-3 cm), 1 Bezier, 1 Gerade (quelle 12),
nichts auf der Gittergeraden. Aufruf: test_gitter_kurven.py [ARBEITSORDNER]  -> Exit 0 bestanden, 1 durchgefallen."""
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner
ordner = sys.argv[1] if len(sys.argv) > 1 else temp_ordner("test_gitter_kurven_"); os.makedirs(ordner, exist_ok=True); rng = np.random.default_rng(1)
def streu(X, nref=5, sig=0.01):
    P = []; R = []
    for r in range(nref): P.append(X + rng.normal(0, sig, X.shape)); R.append(np.full(len(X), r))
    return np.vstack(P), np.concatenate(R)
n = 200
ger = np.stack([np.linspace(0, 4, n), np.full(n, 2.0), np.full(n, 5.0)], 1)                              # neue Gerade
th = np.linspace(np.radians(15), np.radians(165), n); C0 = np.array([10.0, 2.0, 8.0]); R0 = 1.9
bog = C0 + R0 * np.stack([np.cos(th), np.zeros(n), np.sin(th)], 1)                                      # Bogen in xz-Ebene
K = np.array([[20, 2, 5], [21, 2, 8], [23, 2, 3], [24, 2, 7.0]]); t = np.linspace(0, 1, n)[:, None]
bez = (1 - t) ** 3 * K[0] + 3 * (1 - t) ** 2 * t * K[1] + 3 * (1 - t) * t ** 2 * K[2] + t ** 3 * K[3]
alt = np.stack([np.linspace(0, 4, n), np.full(n, 2.0), np.full(n, 9.0)], 1)                              # Gerade schon im Gitter
C2 = np.array([30.0, 2.0, 8.0]); th2 = np.concatenate([np.linspace(np.radians(20), np.radians(80), 80), np.linspace(np.radians(90), np.radians(150), 80)])
bog2 = C2 + R0 * np.stack([np.cos(th2), np.zeros(len(th2)), np.sin(th2)], 1)                         # Bogen in 2 Fragmenten, Luecke 10 Grad = 33 cm
ger2 = np.stack([np.concatenate([np.linspace(0, 1.8, 90), np.linspace(2.0, 4, 100)]), np.full(190, 2.0), np.full(190, 3.0)], 1)   # Gerade in 2 Fragmenten, Luecke 20 cm
P, ref = zip(*[streu(X) for X in (ger, bog, bez, alt, bog2, ger2)]); P = np.vstack(P).astype(np.float32); ref = np.concatenate(ref)
np.savez(f"{ordner}/sweep.npz", P=P, s=np.full(len(P), 0.9, np.float32), ref=ref, fotos=np.array(["f%d" % i for i in range(5)]))
json.dump({"segmente": [[[0, 2, 9], [4, 2, 9], 0, 0.9], [[-2, -2, 0], [34, 6, 12], 0, 0.1]]}, open(f"{ordner}/gitter.json", "w"))   # 2. Segment = Quader aufspannen
r = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(__file__), "gitter_kurven.py"), f"{ordner}/sweep.npz", f"{ordner}/gitter.json", f"{ordner}/aus.json"], capture_output=True, text=True)
print(r.stdout); print(r.stderr[-2000:])
K_ = json.load(open(f"{ordner}/aus.json"))["kurven"]; typen = [k["typ"] for k in K_]; ok = True
def pruef(bed, text):
    global ok; print(("OK  " if bed else "FEHL") + " " + text); ok = ok and bed
bgn2 = [k for k in K_ if k["typ"] == "bogen" and k["zentrum"][0] > 20]; grs2 = [k for k in K_ if k["typ"] == "gerade" and abs(np.array(k["punkte"])[:, 2].mean() - 3.0) < 0.1]
pruef(len(bgn2) == 1 and bgn2[0].get("teile") == 2 and abs(bgn2[0]["winkel_grad"] - 130) < 4 and abs(bgn2[0]["radius"] - R0) < 0.03, "Bogen-Fragmente verbunden: %d Bogen, Teile %s, Winkel %s, R %s" % (len(bgn2), [k.get("teile") for k in bgn2], [round(k["winkel_grad"]) for k in bgn2], [round(k["radius"], 3) for k in bgn2]))
pruef(len(grs2) == 1 and grs2[0].get("teile") == 2 and abs(grs2[0]["laenge_m"] - 4.0) < 0.1, "Geraden-Fragmente verbunden: %d Gerade, Teile %s, Laenge %s" % (len(grs2), [k.get("teile") for k in grs2], [round(k["laenge_m"], 2) for k in grs2]))
bgn = [k for k in K_ if k["typ"] == "bogen" and k["zentrum"][0] < 20]; bzs = [k for k in K_ if k["typ"] == "bezier"]; grs = [k for k in K_ if k["typ"] == "gerade" and abs(np.array(k["punkte"])[:, 2].mean() - 5.0) < 0.1]
pruef(len(bgn) == 1, "genau 1 Bogen (%d)" % len(bgn))
if bgn: pruef(abs(bgn[0]["radius"] - R0) < 0.03 and np.linalg.norm(np.array(bgn[0]["zentrum"]) - C0) < 0.03, "Bogen R %.3f (Soll %.2f), Zentrumfehler %.3f m, Winkel %.0f" % (bgn[0]["radius"], R0, np.linalg.norm(np.array(bgn[0]["zentrum"]) - C0), bgn[0]["winkel_grad"]))
pruef(len(bzs) == 1, "genau 1 Bezier (%d)" % len(bzs))
if bzs:
    Z = np.array(bzs[0]["punkte"]); d = np.sqrt(((Z[:, None] - bez[None]) ** 2).sum(-1)).min(1); pruef(d.max() < 0.03, "Bezier-Abtastung max %.3f m von Sollkurve" % d.max())
pruef(len(grs) == 1, "genau 1 Gerade (%d)" % len(grs))
if grs: pruef(abs(np.array(grs[0]["punkte"])[:, 2].mean() - 5.0) < 0.03, "Gerade bei z=5 (neu), nicht z=9 (Gitter): z=%.2f" % np.array(grs[0]["punkte"])[:, 2].mean())
pruef(not any(np.array(k["punkte"])[:, 0].mean() < 5 and abs(np.array(k["punkte"])[:, 2].mean() - 9.0) < 0.5 for k in K_), "keine Kurve auf der Gittergeraden z=9 (x<5)")
print("BESTANDEN" if ok else "DURCHGEFALLEN"); sys.exit(0 if ok else 1)
