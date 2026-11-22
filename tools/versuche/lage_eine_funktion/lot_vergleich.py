"""Welches Lot stimmt? Kameraebene / Bild-x-Achsen (Median- und Mittel-Vorzeichen) gegen die Hochachse der geschriebenen Ausrichtung (LoD2+DGM1-Feinfit, Kippung frei)."""
import json, numpy as np, math, sys, os
from scipy.spatial.transform import Rotation as Rot
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import seiten_gps_vereinen as SG
W = "/home/oem/git/rc-park"; D = "/media/oem/scan/rc-park_daten"
def ang(u, v): u = np.asarray(u, float); v = np.asarray(v, float); return math.degrees(math.acos(min(1.0, abs(u @ v) / np.linalg.norm(u) / np.linalg.norm(v))))
for ziel in sys.argv[1:]:
    kj = f"{D}/{ziel}/pipe/kameras.json"; au = f"{W}/modelle/{ziel}/messprotokoll/SFM-AUSRICHTUNG-{ziel}.json"
    if not (os.path.isfile(kj) and os.path.isfile(au)): print(ziel, "fehlt", os.path.isfile(kj), os.path.isfile(au)); continue
    KJ = json.load(open(kj)); C = np.array([b["C"] for b in KJ["bilder"]], float); Rs = np.array([b["R"] for b in KJ["bilder"]], float)
    AU = json.load(open(au)); t = AU["transformation"]; Rm = Rot.from_rotvec(t["rvec"]).as_matrix(); z_r = Rm[:, 2]
    nm = [os.path.splitext(b["name"])[0] for b in KJ["bilder"]]; st = AU["kameras"]; gem = [i for i, n in enumerate(nm) if n in st and st[n].get("standort") is not None]
    A = np.array([st[nm[i]]["standort"] for i in gem], float); B = C[gem]          # B ~ s R A + t
    ma, mb = A.mean(0), B.mean(0); U, S, Vt = np.linalg.svd((B - mb).T @ (A - ma)); E = np.eye(3); E[2, 2] = np.sign(np.linalg.det(U @ Vt)); Rk = U @ E @ Vt; z_m = Rk[:, 2]
    print(f"   {ziel}: gemeinsame Kameras {len(gem)}, Hochachse rvec vs Korrespondenz {ang(z_r, z_m):.2f} Grad")
    dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); cm = C[nah].mean(0); _, sv, vt = np.linalg.svd(C[nah] - cm); eb = vt[2]
    ach = np.asarray(SG.lot_aus_bild_achsen(Rs), float)
    # Wechselwirkung Vorzeichen: Median statt Mittel
    print(f"{ziel}: n {len(C)}, flach {sv[2] / sv[0]:.2f} | Ebene vs Feinfit {ang(eb, z_m):.2f} Grad | Bildachsen vs Feinfit {ang(ach, z_m):.2f} | Ebene vs Bildachsen {ang(eb, ach):.2f}"
          f" | Vorzeichen Bildachsen richtig: {bool(ach @ z_m > 0)} | loesung {t.get('loesung_nr')}")
