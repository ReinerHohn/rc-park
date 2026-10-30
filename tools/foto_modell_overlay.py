#!/usr/bin/env python3
"""foto_modell_overlay.py — das ECHTE 3D-Modell halbtransparent & perspektivisch ins Foto.

Pipeline (robust, Ziel: aus JEDER Perspektive sichtbar passend):
  1. Intrinsics K aus EXIF (Brennweite/Sensor) → echte Kamera, nicht nur flache Homographie.
  2. solvePnP (IPPE, planare Fassaden-Punkte y=0) aus wenigen Hand-Korrespondenzen → Kamera-Pose.
  3. EDGE-SNAP-Refine: projizierte Bogen-Leibungen aufs echte Kanten-Gradientenbild schnappen,
     Pose per solvePnP nachziehen (ICP-artig) → unempfindlich gegen Pick-Rauschen.
  4. Das STL wird aus der Pose projiziert, tiefensortiert (Maler) und HALBTRANSPARENT
     übers Foto gelegt → Tunnel/Hinterkanten/Tiefe sitzen korrekt.

Config (JSON): foto, stl, f_mm, sensor_mm, corr=[[mx,my,mz,u,v],...] (u,v in work_w-Raum).
"""
import argparse, json, numpy as np, cv2, trimesh

L, N, PP, R, ZS = 224.0, 9, 224.0/9, 10.0, 36*0.61
def xc(k): return -L/2 + (k+0.5)*PP


def intrinsics(cfg, work_w, h):
    f = cfg["f_mm"] / cfg["sensor_mm"] * work_w
    return np.array([[f, 0, work_w/2.0], [0, f, h/2.0], [0, 0, 1]], float)


def solve(obj_xyz, img_uv, K):
    """IPPE (planare y=0-Punkte). obj_xyz echte Modellkoords (x,y,z); Plane-Map (x,z,y=0)."""
    obj = np.column_stack([obj_xyz[:, 0], obj_xyz[:, 2], obj_xyz[:, 1]]).astype(np.float32)
    n, rvs, tvs, _ = cv2.solvePnPGeneric(obj, img_uv.astype(np.float32), K, None,
                                         flags=cv2.SOLVEPNP_IPPE)
    best = None
    for i in range(n):
        p, _ = cv2.projectPoints(obj, rvs[i], tvs[i], K, None)
        rms = np.sqrt(((p.reshape(-1, 2) - img_uv) ** 2).sum(1).mean())
        if best is None or rms < best[0]:
            best = (rms, rvs[i], tvs[i])
    return best            # (rms, rvec, tvec)


def project(pts_xyz, rv, tv, K):
    q = np.column_stack([pts_xyz[:, 0], pts_xyz[:, 2], pts_xyz[:, 1]]).astype(np.float32)
    p, _ = cv2.projectPoints(q, rv, tv, K, None)
    return p.reshape(-1, 2)


def refine_edges(gray, rv, tv, K, iters=4, win=7):
    """ICP-artig, robust: für jeden projizierten Intrados-Punkt entlang der INWÄRTS-Normale
    die STEIN→DUNKEL-Kante suchen (Bogenring hell außen, Öffnung dunkel innen = Leibung).
    Snap = stärkster NEGATIVER Richtungsgradient (nicht nur |grad| → fängt keine Baum-Kante).
    Re-Solve per IPPE mit Ausreißer-Abwurf (robuster Verlust)."""
    g = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 1.5)
    Hh, Wg = gray.shape
    for _ in range(iters):
        O, I = [], []
        for k in range(N):
            angs = np.linspace(np.deg2rad(18), np.deg2rad(162), 18)
            arc = np.array([[xc(k)+R*np.cos(a), 0, ZS+R*np.sin(a)] for a in angs])
            uv = project(arc, rv, tv, K)
            cen = project(np.array([[xc(k), 0, ZS]]), rv, tv, K)[0]
            for a, p in zip(angs, uv):
                d = p - cen; nmag = np.linalg.norm(d)
                if nmag < 1e-3: continue
                d /= nmag                                 # Einwärts = Richtung Öffnungsmitte
                prof = []
                for s in range(-win, win+1):
                    q = p + d*s; xi, yi = int(round(q[0])), int(round(q[1]))
                    prof.append(g[yi, xi] if (0 <= xi < Wg and 0 <= yi < Hh) else np.nan)
                prof = np.array(prof)
                if np.isnan(prof).any(): continue
                deriv = np.gradient(prof)                 # einwärts: hell->dunkel = negativ
                j = int(np.argmin(deriv))
                if deriv[j] < -6 and prof[:win].mean() > prof[win:].mean()+8:  # außen heller
                    s = j - win
                    O.append([xc(k)+R*np.cos(a), 0, ZS+R*np.sin(a)]); I.append((p + d*s).tolist())
        if len(O) < 10: break
        O, I = np.array(O), np.array(I)
        # robuster Re-Solve: IPPE, dann Ausreißer (>2·Median-Residuum) abwerfen, nochmal
        for _r in range(2):
            rms, rv, tv = solve(O, I, K)
            pr = project(O, rv, tv, K); res = np.linalg.norm(pr - I, axis=1)
            keep = res < max(6.0, 2.0*np.median(res))
            if keep.all() or keep.sum() < 10: break
            O, I = O[keep], I[keep]
    return rv, tv


def render(cfg_path, out, alpha=0.5, work_w=1400, do_refine=True):
    cfg = json.load(open(cfg_path))
    work_w = int(cfg.get("emb_w", work_w))          # Picker liefert Klick-Raum-Breite
    img0 = cv2.imread(cfg["foto"]); Hf, Wf = img0.shape[:2]
    img = cv2.resize(img0, (work_w, int(Hf*work_w/Wf))); h = img.shape[0]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    K = intrinsics(cfg, work_w, h)
    corr = np.array(cfg["corr"], float)
    obj_xyz, img_uv = corr[:, :3], corr[:, 3:5]
    rms, rv, tv = solve(obj_xyz, img_uv, K)
    print(f"{cfg['foto'].split('/')[-1]}: IPPE-RMS {rms:.1f}px  t={tv.ravel().round(1)}m")
    if do_refine:
        rv, tv = refine_edges(gray, rv, tv, K)
        p = project(obj_xyz, rv, tv, K)
        print(f"  nach Edge-Snap: Korr-RMS {np.sqrt(((p-img_uv)**2).sum(1).mean()):.1f}px")

    m = trimesh.load(cfg["stl"], force="mesh")
    V = m.vertices.view(np.ndarray)
    uv = project(V, rv, tv, K)
    # Tiefe je Vertex (Kameraabstand) für Maler-Sortierung
    q = np.column_stack([V[:, 0], V[:, 2], V[:, 1]]).astype(np.float32)
    Rm, _ = cv2.Rodrigues(rv); zc = (q @ Rm.T + tv.ravel())[:, 2]
    tri = m.faces; tz = zc[tri].mean(1); order = np.argsort(-tz)
    nrm = m.face_normals; shade = 0.45 + 0.45*np.clip(nrm[:, 1]*0.5+0.6, 0, 1)
    layer = img.copy()
    for f in order:
        pts = uv[tri[f]].astype(np.int32)
        if (pts < -2*work_w).any() or (pts > 3*work_w).any(): continue
        s = shade[f]; cv2.fillConvexPoly(layer, pts, (int(70*s), int(210*s), int(90*s)), cv2.LINE_AA)
    vis = cv2.addWeighted(layer, alpha, img, 1-alpha, 0)
    # scharfe Vorderkanten der Bögen
    for k in range(N):
        arc = np.array([[xc(k)+R*np.cos(a), 0, ZS+R*np.sin(a)] for a in np.linspace(np.pi, 0, 40)])
        cv2.polylines(vis, [project(arc, rv, tv, K).astype(np.int32)], False, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(out.replace(".png", "_full.png"), vis)
    cv2.imwrite(out, cv2.resize(vis, (560, int(h*560/work_w))))
    print("->", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--alpha", type=float, default=0.5); ap.add_argument("--no-refine", action="store_true")
    a = ap.parse_args()
    render(a.cfg, a.out, a.alpha, do_refine=not a.no_refine)
