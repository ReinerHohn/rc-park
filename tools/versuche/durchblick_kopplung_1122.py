#!/usr/bin/env python3
"""durchblick_kopplung_1122.py - Teilmodelle ueber ein starres Eckmodell koppeln (22.11.2026, schwabentor-1122).
Je Paar (Eckmodell -> Teilmodell) ueber die GEMEINSAMEN Kameras: Drehung aus den Kamera-Orientierungen (Mittel der R_teil^T R_eck, robust), Massstab/Versatz aus den
Kamerazentren bei fester Drehung (Median). Kameras eines Eckmodells liegen eng beisammen - die Zentren allein legen die Drehung schlecht fest, die Orientierungen gut.
Kette: Teil B -> Ecke -> Teil A (Ausrichtung). Ausgabe: Lage von Teil B im Ausrichtungsrahmen (Sim3 B -> Ausrichtung), Abweichung der Einzel-Drehungen.
python -I durchblick_kopplung_1122.py --ecke E --a TEIL0 --b TEIL1 --ausrichtung AU --aus DIR"""
import os, sys, json, argparse, numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
from sim3_robust import sim3_meter, matrix, anwenden


def lade(p):
    import pycolmap; r = pycolmap.Reconstruction(p); return r, {im.name: im for im in r.images.values() if im.has_pose}


def mittel_dreh(Rs):
    U, _, Vt = np.linalg.svd(sum(Rs)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); return U @ D @ Vt


def winkel(R): return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def kopplung(E, Z, min_kam=3):
    """Sim3 Eckmodell-Welt -> Zielmodell-Welt ueber gemeinsame Kameras. -> (M, info) oder (None, info)."""
    ns = sorted(set(E) & set(Z))
    if len(ns) < min_kam: return None, dict(gemeinsam=len(ns))
    Rs = [Z[n].cam_from_world().rotation.matrix().T @ E[n].cam_from_world().rotation.matrix() for n in ns]   # X_z = s R X_e + t  ->  R = R_z^T R_e
    R = mittel_dreh(Rs)
    for _ in range(2):                                                                                       # Ausreisser-Drehungen (> 3 Grad) weg, neu mitteln
        ok = [x for x in Rs if winkel(x @ R.T) < 3.0]
        if len(ok) >= min_kam: R = mittel_dreh(ok)
    abw = [winkel(x @ R.T) for x in Rs]
    Ce = np.array([E[n].projection_center() for n in ns]); Cz = np.array([Z[n].projection_center() for n in ns])
    a = Ce @ R.T; ac, zc = a - np.median(a, 0), Cz - np.median(Cz, 0); s = float(np.median(np.linalg.norm(zc, axis=1)) / max(np.median(np.linalg.norm(ac, axis=1)), 1e-12))
    t = np.median(Cz - s * a, 0); M = matrix(s, R, t); rest = np.linalg.norm(anwenden(M, Ce) - Cz, axis=1)
    return M, dict(gemeinsam=len(ns), dreh_abw_median=round(float(np.median(abw)), 2), dreh_abw_max=round(float(max(abw)), 2), massstab=s,
                   zentren_rest_rel=round(float(np.median(rest) / max(np.median(np.linalg.norm(zc, axis=1)), 1e-9)), 3))


def punkte(rE, E, rZ, Z):
    """Gemeinsame 3D-Punkte ueber gleiche Bildpunkte (Bildname + Keypoint-Index) gemeinsamer Kameras -> (X_eck, X_ziel)."""
    pe, pz = [], []; gesehen = set()
    for n in set(E) & set(Z):
        a_, b_ = E[n].points2D, Z[n].points2D
        for k in range(min(len(a_), len(b_))):
            if a_[k].has_point3D() and b_[k].has_point3D() and (a_[k].point3D_id, b_[k].point3D_id) not in gesehen:
                gesehen.add((a_[k].point3D_id, b_[k].point3D_id)); pe.append(rE.points3D[a_[k].point3D_id].xyz); pz.append(rZ.points3D[b_[k].point3D_id].xyz)
    return np.array(pe), np.array(pz)


def main(argv=None):
    ap = argparse.ArgumentParser(); [ap.add_argument(f"--{k}", required=True) for k in ("ecke", "a", "b", "ausrichtung", "aus")]
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    rE, E = lade(a.ecke); rA, A = lade(a.a); rb, B = lade(a.b)
    au = json.load(open(a.ausrichtung)); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
    na = [n for n in A if os.path.splitext(n)[0] in st]; f = sim3_meter(np.array([A[n].projection_center() for n in na]), np.array([st[os.path.splitext(n)[0]] for n in na]))
    print(f"A -> Ausrichtung: {f['n_inlier']}/{f['n']} stimmig, Rest {f['rest_median_m']:.3f} m")
    # Punkt-Kopplung (viele gemeinsame 3D-Punkte statt weniger Kameras): Ecke -> Ausrichtung (Meter) ueber A, B -> Ecke
    Xe, Xa = punkte(rE, E, rA, A); fa = sim3_meter(Xe, anwenden(f["M"], Xa), schwelle_m=0.3) if len(Xe) >= 3 else None
    Ye, Yb = punkte(rE, E, rb, B)
    if fa is None or len(Ye) < 3: print("KEINE KOPPLUNG", len(Xe), len(Ye)); return 2
    m_je = float(np.linalg.norm(fa["M"][:3, :3], axis=0).mean())                   # Meter je Eck-Einheit
    fb = sim3_meter(Yb, Ye, schwelle_m=0.3 / m_je)                                   # B -> Ecke, Schwelle 0,3 m in Eck-Einheiten
    if fb is None: print("KEINE KOPPLUNG B -> Ecke"); return 2
    ia = dict(gemeinsame_kameras=len(set(E) & set(A)), punkte=len(Xe), stimmig=fa["n_inlier"], rest_m=round(fa["rest_median_m"], 3))
    ib = dict(gemeinsame_kameras=len(set(E) & set(B)), punkte=len(Ye), stimmig=fb["n_inlier"], rest_m=round(fb["rest_median_m"] * m_je, 3))
    print("Ecke -> A (Meter):", ia); print("B -> Ecke:", ib)
    M_b = fa["M"] @ fb["M"]                                                          # B -> Ecke -> Ausrichtung
    out = dict(ecke_a=ia, ecke_b=ib, a_ausrichtung=dict(n=f["n"], stimmig=f["n_inlier"], rest_m=f["rest_median_m"]), M_b_nach_ausrichtung=M_b.tolist(), M_a_nach_ausrichtung=f["M"].tolist())
    nb = [n for n in B if os.path.splitext(n)[0] in st]
    if nb:
        d = np.linalg.norm(anwenden(M_b, np.array([B[n].projection_center() for n in nb])) - np.array([st[os.path.splitext(n)[0]] for n in nb]), axis=1)
        out["b_gegen_kette_ausrichtung_m"] = dict(n=len(nb), median=round(float(np.median(d)), 2)); print("B-Kameras gegen Ketten-Ausrichtung:", out["b_gegen_kette_ausrichtung_m"])
    json.dump(out, open(os.path.join(a.aus, "kopplung.json"), "w"), indent=1); print("->", os.path.join(a.aus, "kopplung.json")); return 0


if __name__ == "__main__": sys.exit(main())
