#!/usr/bin/env python3
"""test_feinsuche.py - SYNTHETISCHER BEWEIS fuer foto_feinsuche (modelle/SPEC_FEINSUCHE.md, Beweis 1).
Eine Testplatte mit aufgesetzten Rippen (bekannte Lage in Weltmetern) wird mit den ECHTEN Kameras von >= 4 kalibrierten Fotos (Blickwinkel >= 15 Grad auseinander) exakt
gerastert und undurchsichtig in die echten Fotos kopiert. Modell A = glatte Platte OHNE Rippen (Rippen fehlen), Modell B = Platte MIT Rippen (nichts fehlt).
Kette wie im echten Lauf: feinkanten_foto / feinkanten_modell / fein_gelb / flecken (teil_fotoform) -> beobachtungen -> GPU-Cluster -> Richtungstor (foto_feinsuche).
Erwartung: A -> Cluster in >= 3 Fotos, Zentrum liegt < 0,3 m von der naechsten Rippe, B -> kein Cluster.
Aufruf: python -I tools/test_feinsuche.py <objekt> --teil <Teilname als Ort der Platte> --teile_dir D --stl S [--aus DIR]"""
import sys, os, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK, foto_diff as FD, teil_fotoform as TF, foto_feinsuche as FS
import test_feinmass as TM
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _np(x): return x.cpu().numpy() if hasattr(x, "cpu") else np.asarray(x)


def platte(C, n, mit_rippen):
    """Platte 2,6 x 3,0 m in der Ebene durch C mit Normale n (horizontal), Rippen 0,08 m breit, 0,06 m vor der Platte (in Richtung n)."""
    u = np.array([-n[1], n[0], 0.0]); v = np.array([0, 0, 1.0]); M = np.eye(4); M[:3, :3] = np.column_stack([u, v, n]); M[:3, 3] = C
    teile = []
    b = trimesh.creation.box(extents=(2.6, 3.0, 0.05)); b.apply_translation((0, 0, -0.025)); b.apply_transform(M); teile.append(b)
    if mit_rippen:
        for l in TM.rippen(0.0):
            for a_, b_ in zip(l[:-1], l[1:]):
                a_, b_ = np.asarray(a_), np.asarray(b_); L = np.linalg.norm(b_ - a_) + 0.02; ang = np.arctan2(*(b_ - a_)[::-1])
                bx = trimesh.creation.box(extents=(L, 0.08, 0.06)); bx.apply_transform(trimesh.transformations.rotation_matrix(ang, (0, 0, 1)))
                mid = (a_ + b_) / 2; bx.apply_translation((mid[0], mid[1], 0.03)); bx.apply_transform(M); teile.append(bx)
    return trimesh.util.concatenate(teile)


def rippen_welt(C, n):
    u = np.array([-n[1], n[0], 0.0]); v = np.array([0, 0, 1.0]); pts = []
    for l in TM.rippen(0.0):
        for a_, b_ in zip(l[:-1], l[1:]):
            for s in np.linspace(0, 1, 12): p = (1 - s) * np.asarray(a_) + s * np.asarray(b_); pts.append(C + p[0] * u + p[1] * v + 0.06 * n)
    return np.array(pts)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teil", required=True); ap.add_argument("--teile_dir", required=True); ap.add_argument("--stl", required=True)
    ap.add_argument("--aus", default="/media/oem/scan/rc-park_tmp/feinsuche/synth"); ap.add_argument("--n_fotos", type=int, default=4); ap.add_argument("--fotos", help="a,b,c,d statt Auswahl")
    a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    alle = sorted(os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json")))
    m = trimesh.load(os.path.join(a.teile_dir, a.teil + ".stl"), force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    daten = {}
    for nr in alle:
        kp = FF.k_datei(objp, obj, R0, nr)
        if not kp: continue
        K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if bild: daten[nr] = (K, bild[0])
    K0 = next(iter(daten.values()))[0]; tr = TF.rahmen(a.stl, obj, K0["kamera"]); C0 = m.bounds.mean(0) + tr
    cams = FS.kameras(a.objekt, list(daten)); wahl = []; dirs = []
    from PIL import Image
    cand = []
    for nr, (K, bp) in daten.items():
        if nr not in cams: continue
        W, H = Image.open(bp).size; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); kk = K["kamera"]
        pc = R @ C0 + t
        if pc[2] < 8 or pc[2] > 45: continue
        uu, vv = f * pc[0] / pc[2] + float(kk.get("cx", W / 2)), f * pc[1] / pc[2] + float(kk.get("cy", H / 2))
        if 0.15 * W < uu < 0.85 * W and 0.15 * H < vv < 0.85 * H: cand.append((nr, abs(uu - W / 2) + abs(vv - H / 2)))
    for nr, _ in sorted(cand, key=lambda x: x[1]) if not a.fotos else [(x, 0) for x in a.fotos.split(",")]:
        d = cams[nr] - C0; d /= np.linalg.norm(d)
        if all(np.degrees(np.arccos(np.clip(d @ e, -1, 1))) >= 15 for e in dirs): wahl.append(nr); dirs.append(d)
        if len(wahl) >= a.n_fotos: break
    print("Fotos", wahl, "Ziel", np.round(C0, 2))
    nh = np.mean([(cams[n_] - C0) * np.array([1, 1, 0]) for n_ in wahl], 0); nh /= np.linalg.norm(nh); C = C0 + 1.5 * nh
    mA, mB = platte(C, nh, False), platte(C, nh, True); rw = rippen_welt(C, nh); res = {"A_ohne_rippen_modell": [], "B_mit_rippen_modell": []}
    obsA, obsB = [], []; kol = []
    for nr in wahl:
        K, bp = daten[nr]; im, K = FD.foto_skalieren(cv2.imread(bp), K); kk = K["kamera"]; H, W = im.shape[:2]; im, _ = FF.foto_entzerren(im, kk)
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        d, fid, _ = RK.dreiecke_rastern(mB, R, t, f, cx, cy, W, H); d = _np(d).astype(np.float32); fid = _np(fid); fin = np.isfinite(d)   # WAHRHEIT: Platte mit Rippen
        nz = np.asarray(mB.face_normals, np.float32)[np.clip(fid, 0, None)]; kn = (R @ nz.reshape(-1, 3).T).T.reshape(nz.shape)
        sh = np.clip(np.abs(kn @ np.array([-0.4, -0.5, 0.77])), 0, 1); foto = im.copy(); foto[fin] = np.dstack([(60 + 170 * sh).astype(np.uint8)] * 3)[fin]
        ms = cv2.dilate(fin.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        ff = TF.feinkanten_foto(cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY), ms) & ms
        zt = float(np.median(d[fin])); tolpx = TF.FEIN_TOL_M * f / zt
        for nm, mod, obs in (("A", mA, obsA), ("B", mB, obsB)):
            dm, fm, pos = RK.dreiecke_rastern(mod, R, t, f, cx, cy, W, H); dm = _np(dm).astype(np.float32); fm = _np(fm); pos = _np(pos)
            mf = TF.feinkanten_modell(dm, fm, np.asarray(mod.face_normals, np.float32)) & ms
            g = TF.fein_gelb(mf, ff, tolpx); fl = TF.flecken(g, pos, n=5, min_px=30)
            res["A_ohne_rippen_modell" if nm == "A" else "B_mit_rippen_modell"].append({"foto": nr, "fein_gelb_px": int(g.sum()), "flecken": len(fl)})
            for q in fl: obs.append((nr, q))
            if nm == "A":
                ov = (foto // 2).copy(); ov[ff] = (255, 160, 0); ov[mf] = (0, 220, 0); ov[g] = (0, 255, 255)
                ys, xs = np.nonzero(ms); kol.append(ov[max(ys.min() - 20, 0):ys.max() + 20, max(xs.min() - 20, 0):xs.max() + 20])
    def cluster(obs):
        te = {"synth_platte": {}}
        for nr, q in obs: te["synth_platte"].setdefault(nr, {"flecken_fein": []})["flecken_fein"].append(q)
        o = FS.beobachtungen({"teile": te}, 30); return FS.cluster_bilden(o, cams, 1.0, 3, 15.0)
    cA, cB = cluster(obsA), cluster(obsB); ok = True
    for c in cA:
        dist = float(np.min(np.linalg.norm(rw - np.array(c["ort"]), axis=1))); c["abstand_rippe_m"] = round(dist, 3)
        print("A Cluster", c["id"], "fotos", c["n_fotos"], "richtungen", c["n_richtungen"], "ort", c["ort"], "Abstand zur naechsten Rippe %.3f m" % dist, "defizit_px", c["defizit_px"])
    treffer = [c for c in cA if c["n_fotos"] >= 3 and c["abstand_rippe_m"] < 0.3]
    print("B (Modell MIT Rippen): Cluster", len(cB), [(c["ort"], c["n_fotos"]) for c in cB]); print(json.dumps(res, indent=0))
    ok = len(treffer) >= 1 and len(cB) == 0
    for i, k in enumerate(kol): cv2.imwrite(os.path.join(a.aus, "synth_A_%s.jpg" % wahl[i]), k, [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump({"fotos": wahl, "ziel": C0.tolist(), "platte": C.tolist(), "normale": nh.tolist(), "A": cA, "B": cB, "res": res, "bestanden": ok}, open(os.path.join(a.aus, "synth.json"), "w"), indent=1)
    print("BEWEIS Feinsuche synthetisch:", "BESTANDEN" if ok else "FEHLGESCHLAGEN", "(A: %d Cluster < 0,3 m von einer Rippe in >= 3 Fotos, B: %d Cluster)" % (len(treffer), len(cB)))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
