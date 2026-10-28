#!/usr/bin/env python3
"""foto_fassade_vermessen.py — GENERISCH: Fassade aus einem Foto vermessen.

Vermesser-Kette (Bildverarbeitungs-Standard):
  1. LSD-Liniensegmente (jede Kante)
  2. Fluchtpunkte: vertikaler VP + Fassaden-Horizontal-VP (RANSAC über Liniengruppen)
  3. Fassade entzerren (Homographie aus den 2 VPs → fronto-parallel)
  4. horizontale Kanten → Geschoss-/Balkon-/Trauf-/First-Bänder (Cluster)
     vertikale Kanten → Fensterachsen (Cluster)
  5. Maßstab über bekannte Referenzhöhe (--ref-height, z.B. LOD2-Gesamthöhe)
     → alle Abstände in Metern

Nicht bauwerksspezifisch. Ausgabe: Overlay + entzerrtes Bild mit Maßen + JSON.

  python3 tools/foto_fassade_vermessen.py --img foto.jpg --ref-height 17.6 \
      --out-dir daten/x --tag hofgut
"""
import argparse, json, os
import numpy as np
import cv2


def lsd_lines(gray, min_len=25):
    lsd = cv2.createLineSegmentDetector()
    segs = lsd.detect(gray)[0]
    if segs is None:
        return np.empty((0, 4))
    S = segs.reshape(-1, 4)
    L = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1])
    return S[L >= min_len]


def group(segs):
    """in nahe-vertikal / nahe-horizontal / schräg nach Winkel."""
    ang = np.degrees(np.arctan2(segs[:, 3] - segs[:, 1], segs[:, 2] - segs[:, 0]))
    a = np.abs(((ang + 90) % 180) - 90)       # 0=horiz, 90=vert
    vert = segs[a > 75]; horiz = segs[a < 15]; obl = segs[(a >= 15) & (a <= 75)]
    return vert, horiz, obl


def vanishing_point(segs, iters=600, thr=2.0):
    """RANSAC-Fluchtpunkt (homogen) aus Liniensegmenten."""
    if len(segs) < 2:
        return None
    def line(s):
        p1 = np.array([s[0], s[1], 1.0]); p2 = np.array([s[2], s[3], 1.0])
        l = np.cross(p1, p2); return l / (np.linalg.norm(l[:2]) + 1e-9)
    Ls = np.array([line(s) for s in segs])
    best, bestn = None, -1
    rng = np.random.default_rng(0)
    for _ in range(iters):
        i, j = rng.choice(len(Ls), 2, replace=False)
        v = np.cross(Ls[i], Ls[j])
        if abs(v[2]) < 1e-9:
            continue
        v = v / v[2]
        # Abstand Punkt↔Linie: |l·v|
        d = np.abs(Ls @ v)
        inl = d < thr
        if inl.sum() > bestn:
            bestn, best = inl.sum(), v
    return best


def rectify(img, vp_vert, vp_horiz, bbox):
    """Homographie aus 2 VPs: Fassaden-bbox → fronto-parallel-Rechteck."""
    x0, y0, x1, y1 = bbox
    src = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    # Entzerren durch Abbildung der VP-Richtungen auf Bildachsen:
    # baue Homographie, die vp_horiz→(∞ in x) und vp_vert→(∞ in y) schickt.
    H_line = np.cross(vp_vert, vp_horiz)             # Fluchtlinie
    Hp = np.array([[1, 0, 0], [0, 1, 0], H_line / (H_line[2] + 1e-9)])  # projektiv entzerren
    # danach affine Normalisierung auf bbox
    pts = cv2.perspectiveTransform(src.reshape(-1, 1, 2), Hp).reshape(-1, 2)
    w = int(np.hypot(*(pts[1] - pts[0]))); h = int(np.hypot(*(pts[2] - pts[1])))
    w = max(200, min(w, 2000)); h = max(200, min(h, 2000))
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    Hfull = cv2.getPerspectiveTransform(cv2.perspectiveTransform(src.reshape(-1, 1, 2), Hp).reshape(-1, 2).astype(np.float32), dst)
    M = Hfull @ Hp
    return cv2.warpPerspective(img, M, (w, h)), M, (w, h)


def cluster_1d(vals, n_expect=None, min_gap=8):
    vals = np.sort(vals)
    if len(vals) == 0:
        return []
    groups = [[vals[0]]]
    for v in vals[1:]:
        (groups[-1] if v - groups[-1][-1] < min_gap else groups.append([v]) or groups[-1]).append(v)
    return [float(np.mean(g)) for g in groups if len(g) >= 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--ref-height", type=float, default=0.0, help="bekannte Gesamthöhe (m) für Maßstab")
    ap.add_argument("--scale-up", type=float, default=2.0)
    ap.add_argument("--out-dir", default="/tmp"); ap.add_argument("--tag", default="fassade")
    a = ap.parse_args()

    img = cv2.imread(a.img)
    if img is None:
        raise SystemExit("Bild fehlt")
    img = cv2.resize(img, None, fx=a.scale_up, fy=a.scale_up, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    segs = lsd_lines(gray)
    vert, horiz, obl = group(segs)
    print(f"Segmente {len(segs)}: vertikal {len(vert)}, horizontal {len(horiz)}, schräg {len(obl)}")

    vp_v = vanishing_point(vert)
    vp_h = vanishing_point(np.vstack([horiz, obl]) if len(obl) else horiz)
    print(f"VP vertikal {None if vp_v is None else vp_v[:2].round(0)}  "
          f"VP horizontal {None if vp_h is None else vp_h[:2].round(0)}")

    # Fassaden-bbox grob = Hülle aller langen Segmente
    allp = segs.reshape(-1, 2)
    bbox = [allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max()]

    os.makedirs(a.out_dir, exist_ok=True)
    result = {"img": a.img, "n_segments": int(len(segs))}

    rect = None
    if vp_v is not None and vp_h is not None:
        try:
            rect, M, (w, h) = rectify(img, vp_v, vp_h, bbox)
            rg = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)
            rsegs = lsd_lines(rg, min_len=max(20, w // 15))
            rv, rh, _ = group(rsegs)
            ybands = cluster_1d(((rh[:, 1] + rh[:, 3]) / 2), min_gap=h * 0.03)
            xaxes = cluster_1d(((rv[:, 0] + rv[:, 2]) / 2), min_gap=w * 0.025)
            print(f"entzerrt {w}x{h}: {len(ybands)} horizontale Bänder, {len(xaxes)} vertikale Achsen")
            # Maßstab: Referenzhöhe auf die Spanne der Bänder
            vis = rect.copy()
            for y in ybands:
                cv2.line(vis, (0, int(y)), (w, int(y)), (0, 0, 255), 2)
            for x in xaxes:
                cv2.line(vis, (int(x), 0), (int(x), h), (0, 200, 0), 1)
            if a.ref_height and len(ybands) >= 2:
                span_px = max(ybands) - min(ybands)
                mpp = a.ref_height / span_px if span_px else 0
                bands_m = [round((max(ybands) - y) * mpp, 2) for y in ybands]  # Höhe ü. unterstem Band
                result["baender_m_ueber_unten"] = sorted(bands_m)
                # Abstände zwischen benachbarten Bändern
                ys = sorted(ybands)
                result["geschoss_abstaende_m"] = [round((ys[i+1]-ys[i])*mpp, 2) for i in range(len(ys)-1)]
                result["achsabstand_median_m"] = round(float(np.median(np.diff(sorted(xaxes)))) * mpp, 2) if len(xaxes) > 2 else None
                cv2.putText(vis, f"ref {a.ref_height}m -> {mpp*100:.1f} cm/px", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                print("Geschoss-Abstände (m):", result["geschoss_abstaende_m"])
                print("Achsabstand median (m):", result["achsabstand_median_m"])
            cv2.imwrite(f"{a.out_dir}/{a.tag}_entzerrt.png", vis)
            result["entzerrt"] = f"{a.out_dir}/{a.tag}_entzerrt.png"
        except Exception as e:
            print("Rektifizierung fehlgeschlagen:", e)

    # Overlay Originalkanten
    ov = img.copy()
    for s in vert: cv2.line(ov, (int(s[0]), int(s[1])), (int(s[2]), int(s[3])), (0, 255, 0), 1)
    for s in horiz: cv2.line(ov, (int(s[0]), int(s[1])), (int(s[2]), int(s[3])), (0, 0, 255), 1)
    for s in obl: cv2.line(ov, (int(s[0]), int(s[1])), (int(s[2]), int(s[3])), (180, 160, 0), 1)
    cv2.imwrite(f"{a.out_dir}/{a.tag}_kanten.png", ov)
    json.dump(result, open(f"{a.out_dir}/{a.tag}_messung.json", "w"), indent=2, ensure_ascii=False)
    print(f"-> {a.out_dir}/{a.tag}_kanten.png + _entzerrt.png + _messung.json")


if __name__ == "__main__":
    main()
