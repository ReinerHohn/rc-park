"""Frontfassade als druckbarer Reliefkoerper: Hoehenkarte (Abstand zur Wandebene) aus dem zugeschnittenen Objektnetz (Painter-Rasterung in (u,z)), Rueckplatte, wasserdicht gebaut (Spalten, kein Fuellen/Glaetten).
Aufruf: python -I tools/fassade_relief_solid.py NETZ.npz OBJEKT.json OUT.stl [--u0 U --u1 U --z0 Z --z1 Z] [--zelle 0.02] [--dicke 0.25]
Annahme (gekennzeichnet): Rueckebene = Wandebene minus dicke; Unterschnitte (Balkonunterseite) gehen verloren."""
import argparse, json, numpy as np, cv2, trimesh
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("netz", "objekt", "aus")]; [ap.add_argument("--" + k, type=float, default=None) for k in ("u0", "u1", "z0", "z1")]; ap.add_argument("--zelle", type=float, default=0.02); ap.add_argument("--dicke", type=float, default=0.25); a = ap.parse_args()
z = np.load(a.netz); O = json.load(open(a.objekt)); n_ = np.array(O["fassade_n"]["wert"], float)[:2]; n_ /= np.linalg.norm(n_); U_ = np.array([n_[1], -n_[0]]); V = z["V"].astype(np.float64); F = z["F"]
Cm = np.mean([np.array(k["C"]) for k in json.load(open("/media/oem/scan/rc-park_daten/kaufhaus_alle/sfm/kam_lot2.json")).values()], 0); sg = 1.0 if (Cm[:2] - V[:, :2].mean(0)) @ n_ > 0 else -1.0
u = V[:, :2] @ U_; s = sg * (V[:, :2] @ n_); zz = V[:, 2]; u0 = a.u0 if a.u0 is not None else np.percentile(u, 1); u1 = a.u1 if a.u1 is not None else np.percentile(u, 99); z0 = a.z0 if a.z0 is not None else zz.min(); z1 = a.z1 if a.z1 is not None else np.percentile(zz, 99)
rb = a.zelle; W = int(np.ceil((u1 - u0) / rb)); H = int(np.ceil((z1 - z0) / rb)); print("Kachel", W, "x", H, "Zellen", flush=True)
cx = (u - u0) / rb; cy = (z1 - zz) / rb; tri = F; sm = s[tri].mean(1); tin = ((cx[tri] > -5) & (cx[tri] < W + 5) & (cy[tri] > -5) & (cy[tri] < H + 5)).any(1); idx = np.where(tin)[0]; idx = idx[np.argsort(sm[idx])]          # von hinten nach vorn
hf = np.full((H, W), np.nan, np.float32); depth = np.zeros((H, W), np.float32); cover = np.zeros((H, W), np.uint8)
for t in idx:
    P2 = np.c_[cx[tri[t]], cy[tri[t]]].astype(np.float32); m = np.zeros((H, W), np.uint8)
    bx0, bx1 = int(max(P2[:, 0].min(), 0)), int(min(P2[:, 0].max() + 2, W)); by0, by1 = int(max(P2[:, 1].min(), 0)), int(min(P2[:, 1].max() + 2, H))
    if bx1 <= bx0 or by1 <= by0: continue
    sub = np.zeros((by1 - by0, bx1 - bx0), np.uint8); cv2.fillConvexPoly(sub, (np.round(P2 - [bx0, by0])).astype(np.int32), 1); dm = sub > 0; hf[by0:by1, bx0:bx1][dm] = sm[t]; cover[by0:by1, bx0:bx1][dm] = 1
wall = float(np.nanmedian(hf)); print("Wandtiefe s=%.3f, Abdeckung %.0f %%" % (wall, 100 * cover.mean()), flush=True)
hfl = np.where(np.isnan(hf), wall, hf); hfl = cv2.medianBlur(hfl.astype(np.float32), 3); back = wall - a.dicke
# wasserdichter Spaltenkoerper: Oberflaeche s=hfl, Boden s=back, Seitenwaende am Rand
def vid(i, j, top): return (i * W + j) * 2 + (0 if top else 1)
ii, jj = np.mgrid[0:H, 0:W]; Vt = np.c_[(u0 + (jj + 0.5) * rb).ravel(), np.full(H * W, 0.0), (z1 - (ii + 0.5) * rb).ravel()]; top = np.c_[Vt[:, 0], hfl.ravel(), Vt[:, 2]]; bot = np.c_[Vt[:, 0], np.full(H * W, back), Vt[:, 2]]
verts = np.empty((H * W * 2, 3)); verts[0::2] = top; verts[1::2] = bot; a_ = np.arange(H * W).reshape(H, W); q = [a_[:-1, :-1].ravel(), a_[:-1, 1:].ravel(), a_[1:, :-1].ravel(), a_[1:, 1:].ravel()]
Ft = np.vstack([np.c_[q[0] * 2, q[2] * 2, q[1] * 2], np.c_[q[1] * 2, q[2] * 2, q[3] * 2]]); Fb = np.vstack([np.c_[q[0] * 2 + 1, q[1] * 2 + 1, q[2] * 2 + 1], np.c_[q[1] * 2 + 1, q[3] * 2 + 1, q[2] * 2 + 1]])
Fs = []
for r in (a_[0, :], a_[-1, :][::-1]):
    for k in range(len(r) - 1): Fs += [[r[k] * 2, r[k] * 2 + 1, r[k + 1] * 2], [r[k + 1] * 2, r[k] * 2 + 1, r[k + 1] * 2 + 1]]
for r in (a_[:, 0][::-1], a_[:, -1]):
    for k in range(len(r) - 1): Fs += [[r[k] * 2, r[k] * 2 + 1, r[k + 1] * 2], [r[k + 1] * 2, r[k] * 2 + 1, r[k + 1] * 2 + 1]]
Fall = np.vstack([Ft, Fb, np.array(Fs)]); Pw = np.zeros((len(verts), 3)); Pw[:, :2] = np.outer(verts[:, 0], U_) + np.outer(sg * verts[:, 1], n_); Pw[:, 2] = verts[:, 2]
m = trimesh.Trimesh(Pw, Fall, process=False); m.fix_normals(); print("wasserdicht:", m.is_watertight, "Volumen m3 %.3f" % abs(m.volume), "Dreiecke", len(m.faces)); m.export(a.aus)
np.savez_compressed(a.aus.replace(".stl", "_hf.npz"), hf=hfl, u0=u0, z1=z1, rb=rb, back=back, wall=wall)
