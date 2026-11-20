import sys, json, numpy as np, cv2
sys.path.insert(0, "/home/oem/git/rc-park/tools"); import seiten_vereinen as V
W = "/media/oem/rcdaten/tmp/mt_seiten"; F = W + "/fein_vgl"
tr = json.load(open("/home/oem/git/rc-park/modelle/martinstor_gk3/messprotokoll/SFM-AUSRICHTUNG-martinstor_gk3_nord.json"))["transformation"]
s = tr["s"]; R = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; t = np.array(tr["t"], float); T = np.array(json.load(open(W + "/vereinen3/vereinen.json"))["B_nach_A"])
M = lambda X: (((X @ T[:3, :3].T + T[:3, 3]) - t) / s) @ R
ax = np.array([-0.86, -0.2]); bilder = {}
P = "/media/oem/rcdaten/tmp/pm_ab"
for nm, p in (("ohne_PR", P + "/ohne/fused.ply"), ("mit_PR5041", P + "/mit/fused.ply")):
    X = M(V.ply_punkte(p, 6000000)); k = (np.abs(X[:, 1] - ax[1]) < 4.5) & (X[:, 2] > 3) & (X[:, 2] < 35)
    xs = X[k, 0]; h, e = np.histogram(xs[(xs > -8) & (xs < -3)], bins=np.arange(-8, -3, 0.02)); w0 = e[np.argmax(h)] + 0.01
    nah = k & (np.abs(X[:, 0] - w0) < 0.25); innen = k & (X[:, 0] > w0 + 0.6) & (X[:, 0] < 3.5); aussen = k & (X[:, 0] < w0 - 0.6) & (X[:, 0] > w0 - 4)
    d = X[nah, 0] - w0; dicke = np.percentile(np.abs(d), 75) * 2
    Z = X[nah]; gy = ((Z[:, 1] - ax[1] + 4.5) / 0.1).astype(int); gz = ((Z[:, 2] - 3) / 0.1).astype(int);
    G = np.zeros((320, 90), bool); G[gz.clip(0, 319), gy.clip(0, 89)] = True; bilder[nm] = G
    print(f"{nm}: Punkte {len(X)/1e6:.2f} Mio | Rueckwand x {w0:.2f} | an der Wand {nah.sum()} | Wand belegt (10 cm) {100*G.mean():.0f} % | Fehlpunkte im Turm {100*innen.sum()/max(1,nah.sum()):.1f} %, vor der Wand {100*aussen.sum()/max(1,nah.sum()):.1f} % | Wanddicke {100*dicke:.1f} cm")
im = np.hstack([np.where(bilder[n][::-1, :, None], np.array([90, 220, 255], np.uint8), np.uint8(18)) for n in ("ohne_PR", "mit_PR5041")]).repeat(3, 0).repeat(3, 1)
cv2.imwrite(P + "/belegung.png", im)
