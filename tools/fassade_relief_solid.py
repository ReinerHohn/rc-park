"""Frontfassade als druckbarer Reliefkoerper: Hoehenkarte (Abstand zur Wandebene) aus dem zugeschnittenen Objektnetz (Painter-Rasterung in (u,z)), Rueckplatte, wasserdicht gebaut (Spalten, kein Fuellen/Glaetten).
Aufruf: python -I tools/fassade_relief_solid.py NETZ.npz OBJEKT.json OUT.stl [--u0 U --u1 U --z0 Z --z1 Z] [--zelle 0.02] [--dicke 0.25]
Annahme (gekennzeichnet): Rueckebene = Wandebene minus dicke; Unterschnitte (Balkonunterseite) gehen verloren."""
import argparse, json, numpy as np, cv2, trimesh
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("netz", "objekt", "aus")]; [ap.add_argument("--" + k, type=float, default=None) for k in ("u0", "u1", "z0", "z1")]; ap.add_argument("--zelle", type=float, default=0.02); ap.add_argument("--dicke", type=float, default=0.25); ap.add_argument("--faces", default=None, help="sam3d.json (SAM-Flaechen aus dem Foto: scharfer Umriss)"); ap.add_argument("--ebene", type=float, default=0.05); ap.add_argument("--nur_faces", action="store_true", help="Hoehe NUR je SAM-Flaeche (Ebene/Plateau, sonst Wandtiefe=ANNAHME), keine Wolkenhoehe dazwischen"); a = ap.parse_args()
z = np.load(a.netz); O = json.load(open(a.objekt)); n_ = np.array(O["fassade_n"]["wert"], float)[:2]; n_ /= np.linalg.norm(n_); U_ = np.array([n_[1], -n_[0]]); V = z["V"].astype(np.float64); F = z["F"]
Cm = np.mean([np.array(k["C"]) for k in json.load(open("/media/oem/scan/rc-park_daten/kaufhaus_alle/sfm/kam_lot2.json")).values()], 0); sg = 1.0 if (Cm[:2] - V[:, :2].mean(0)) @ n_ > 0 else -1.0
u = V[:, :2] @ U_; s = sg * (V[:, :2] @ n_); zz = V[:, 2]; u0 = a.u0 if a.u0 is not None else np.percentile(u, 1); u1 = a.u1 if a.u1 is not None else np.percentile(u, 99); z0 = a.z0 if a.z0 is not None else zz.min(); z1 = a.z1 if a.z1 is not None else np.percentile(zz, 99)
rb = a.zelle; W = int(np.ceil((u1 - u0) / rb)); H = int(np.ceil((z1 - z0) / rb)); print("Kachel", W, "x", H, "Zellen", flush=True)
cx = (u - u0) / rb; cy = (z1 - zz) / rb; tri = F; sm = s[tri].mean(1); tin = ((cx[tri] > -5) & (cx[tri] < W + 5) & (cy[tri] > -5) & (cy[tri] < H + 5)).any(1); idx = np.where(tin)[0]; idx = idx[np.argsort(sm[idx])]          # von hinten nach vorn
off = np.r_[0, np.cumsum(z["ntri"])]; tobj = np.zeros(len(F), np.int32)
for k in range(len(z["ids"])): tobj[off[k]:off[k + 1]] = k
lab = np.full((H, W), -1, np.int32); hf = np.full((H, W), np.nan, np.float32); depth = np.zeros((H, W), np.float32); cover = np.zeros((H, W), np.uint8)
for t in idx:
    P2 = np.c_[cx[tri[t]], cy[tri[t]]].astype(np.float32); m = np.zeros((H, W), np.uint8)
    bx0, bx1 = int(max(P2[:, 0].min(), 0)), int(min(P2[:, 0].max() + 2, W)); by0, by1 = int(max(P2[:, 1].min(), 0)), int(min(P2[:, 1].max() + 2, H))
    if bx1 <= bx0 or by1 <= by0: continue
    sub = np.zeros((by1 - by0, bx1 - bx0), np.uint8); cv2.fillConvexPoly(sub, (np.round(P2 - [bx0, by0])).astype(np.int32), 1); dm = sub > 0; hf[by0:by1, bx0:bx1][dm] = sm[t]; lab[by0:by1, bx0:bx1][dm] = tobj[t]; cover[by0:by1, bx0:bx1][dm] = 1
wall = float(np.nanmedian(hf)); print("Wandtiefe s=%.3f, Abdeckung %.0f %%" % (wall, 100 * cover.mean()), flush=True)
hfl = np.where(np.isnan(hf), wall, hf).astype(np.float32); back = wall - a.dicke
ok_ = ~np.isnan(hf); hm = cv2.medianBlur(hfl, 5); hfl = np.where(ok_, hm, hfl)                                          # Ausreisser
bl = hfl.copy()                                                                                                      # kantenerhaltend: Stufen (Baluster, Konsolen) bleiben, Flaechenrauschen verschwindet
for _ in range(4): bl = cv2.bilateralFilter(bl, 9, 0.025, 4.0)
hfl = bl
if a.faces:                                                                                                          # Umriss aus dem FOTO (SAM-Flaechen), Hoehe = robuste Ebene aus den Wolkenpunkten darin
    SJ = json.load(open(a.faces)); cnz = SJ["cn"]; z0f = SJ["z0"]; Fs = sorted(SJ["flaechen"], key=lambda f: -f["m2"]); lab2 = np.full((H, W), -1, np.int32); SH = 4
    def g(Q): Q = np.array(Q, float); return np.round(np.c_[(Q[:, 0] - u0) / rb, (z1 - (z0f + Q[:, 1] * cnz)) / rb] * (1 << SH)).astype(np.int32)
    for i, f in enumerate(Fs):
        mk_ = np.zeros((H, W), np.uint8); cv2.fillPoly(mk_, [g(f["poly"])], 1, shift=SH)
        for l in f["loecher"]: cv2.fillPoly(mk_, [g(l)], 0, shift=SH)
        lab2[mk_ > 0] = i
    uu_, zz_ = np.meshgrid(u0 + (np.arange(W) + 0.5) * rb, z1 - (np.arange(H) + 0.5) * rb); out_ = (np.full_like(hfl, wall) if a.nur_faces else hfl.copy()); ok2 = ~np.isnan(hf); npl = 0
    for i in np.unique(lab2[lab2 >= 0]):
        m = lab2 == i; vm = m & ok2
        if vm.sum() < 6: continue
        ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; mv = vm[y0:y1, x0:x1]; A = np.c_[uu_[y0:y1, x0:x1][mv], zz_[y0:y1, x0:x1][mv], np.ones(mv.sum())]; b_ = hf[y0:y1, x0:x1][mv].astype(np.float64); w_ = np.ones(len(b_))
        for _ in range(4):
            c_, *_ = np.linalg.lstsq(A * w_[:, None], b_ * w_, rcond=None); r_ = b_ - A @ c_; sg_ = max(1.4826 * np.median(np.abs(r_)), 0.004); w_ = (np.abs(r_) < 2.5 * sg_).astype(float)
            if w_.sum() < 8: break
        rms = float(np.sqrt(np.mean(r_[w_ > 0] ** 2))) if w_.sum() >= 8 else 9.0
        if rms > a.ebene and (a.nur_faces or int(m.sum()) < 2500) and mv.sum() >= 6: c_ = np.array([0.0, 0.0, float(np.median(b_))]); rms = 0.0                       # kleine Flaeche (< ~1 m2): flache Oberkante (Plateau)
        if rms <= a.ebene:
            sub = np.c_[uu_[y0:y1, x0:x1].ravel(), zz_[y0:y1, x0:x1].ravel(), np.ones((y1 - y0) * (x1 - x0))] @ c_; sub = sub.reshape(y1 - y0, x1 - x0); mm_ = m[y0:y1, x0:x1]; out_[y0:y1, x0:x1][mm_] = sub[mm_]; npl += 1
    print("Flaechen als Ebene:", npl, "von", len(Fs)); hfl = np.maximum(out_.astype(np.float32), back + 0.01); lab = np.where(lab2 >= 0, 1, lab)
nolab = (lab < 0)                                                                                                   # Zellen ohne Objekt: Wandtiefe (flach)
hfl = np.where(nolab & np.isnan(hf), wall, hfl).astype(np.float32)
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
