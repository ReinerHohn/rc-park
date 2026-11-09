#!/usr/bin/env python3
"""Slicer-Vorcheck fuer ein Generator-STL (generisch, nichts Objektspezifisches; Vorbild koerper_v11.pruefen).

Aufruf:  python tools/druck_vorcheck.py <objekt> [--stl PFAD] [--n 60000] [--grenze_mm 0.4] [--winkel 60]
Liest modelle/<objekt>/objekt.json (Massstab 'massstab' bzw. SCALE 87, Fassadenachse = erstes 'achse_n' der Bauteile),
STL standardmaessig modelle/stl/<objekt>_1-<SCALE>.stl (mm im Druckmassstab). Ausgabe modelle/<objekt>/audit/druck_vorcheck.json:
  - netz: wasserdicht, Teilnetze, Volumen
  - ueberhang: Flaechen, deren Normale steiler als <winkel> Grad von der Senkrechten nach unten zeigt (ohne Bodenflaeche),
    je 1-m-Hoehenband Flaeche/Ausdehnung entlang/normal (Fassadenrahmen u = entlang, n = Normale)
  - duenn: Wandstaerke per Strahl entlang der Innennormalen (GPU, torch Moeller-Trumbore), Quantile und Haufen der Stichproben
    unter grenze_mm (im Druck) mit Lage (u, n, z in Modellmetern)
Nur Bericht (Exit 0); Sollwerte stehen in der Masstabelle (Merkmal druck)."""
import argparse, json, math, os, sys
import numpy as np, trimesh, torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def strahl_dicke(m, n, seed=0):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    P, fi = trimesh.sample.sample_surface(m, n, seed=seed); Nn = m.face_normals[fi]
    T = torch.tensor(m.triangles, dtype=torch.float32, device=dev); v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    O = torch.tensor(P - Nn * 1e-4, dtype=torch.float32, device=dev); D = torch.tensor(-Nn, dtype=torch.float32, device=dev)
    t_best = torch.full((len(P),), float("inf"), device=dev)
    for i in range(0, len(P), 512):
        o, d = O[i:i + 512, None, :], D[i:i + 512, None, :]
        pv = torch.cross(d.expand(-1, len(T), -1), e2[None].expand(len(o), -1, -1), dim=2); det = (e1[None] * pv).sum(2)
        inv = 1.0 / torch.where(det.abs() < 1e-12, torch.full_like(det, 1e-12), det); tv = o - v0[None]
        uu = (tv * pv).sum(2) * inv; qv = torch.cross(tv, e1[None].expand(len(o), -1, -1), dim=2); vv = (d * qv).sum(2) * inv; tt = (e2[None] * qv).sum(2) * inv
        ok = (det.abs() > 1e-12) & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (tt > 1e-5)
        t_best[i:i + 512] = torch.where(ok, tt, torch.full_like(tt, float("inf"))).min(1).values
    return P, t_best.cpu().numpy(), dev


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--grenze_mm", type=float, default=0.4); ap.add_argument("--winkel", type=float, default=60.0); a = ap.parse_args()
    od = os.path.join(ROOT, "modelle", a.objekt); O = json.load(open(os.path.join(od, "objekt.json")))
    sc = float(O.get("massstab") or os.environ.get("SCALE", 87)); K = 1000.0 / sc
    stl = a.stl or os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_1-{int(sc)}.stl")
    an = next((b["achse_n"] for b in O.get("bauteile", []) if b.get("achse_n") and b.get("aktiv", True) is not False), [0.0, 1.0])
    n_ = np.array(an, float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    m = trimesh.load(stl, process=False); m.merge_vertices(); m.apply_scale(1.0 / K)                   # mm im Druck -> Modellmeter
    erg = {"stl": os.path.relpath(stl, ROOT), "massstab": sc, "achse_n": n_.tolist(),
           "netz": {"wasserdicht": bool(m.is_watertight), "teilnetze": len(m.split(only_watertight=False)), "volumen_m3": float(abs(m.volume)), "dreiecke": len(m.faces)}}
    N = m.face_normals; A_ = m.area_faces; C = m.triangles_center; zb = m.bounds[0, 2]
    ov = (N[:, 2] < -math.cos(math.radians(90 - a.winkel))) & (C[:, 2] > zb + 0.05)
    Cu, Cn = C[:, :2] @ u_, C[:, :2] @ n_; baender = []
    if ov.any():
        for z0 in np.arange(math.floor(C[ov, 2].min()), math.ceil(C[ov, 2].max()) + 1e-9, 1.0):
            mm = ov & (C[:, 2] >= z0) & (C[:, 2] < z0 + 1)
            if mm.any(): baender.append({"z": [float(z0), float(z0 + 1)], "flaeche_m2": round(float(A_[mm].sum()), 3), "dreiecke": int(mm.sum()),
                                         "u": [round(float(Cu[mm].min()), 2), round(float(Cu[mm].max()), 2)], "n": [round(float(Cn[mm].min()), 2), round(float(Cn[mm].max()), 2)]})
    erg["ueberhang"] = {"winkel_grad": a.winkel, "flaeche_m2": round(float(A_[ov].sum()), 3), "anteil": round(float(A_[ov].sum() / A_.sum()), 4),
                        "hinweis": "Flaechen nach unten ohne Stuetze: Bogenscheitel/Erkerunterseite/Gesimsunterseite/Balkonplatte - Stuetzen im Slicer oder Druck kopfueber/geteilt",
                        "baender": baender}
    P, t, dev = strahl_dicke(m, a.n); fin = np.isfinite(t); gm = a.grenze_mm / K
    unter = fin & (t < gm); Pu = P[unter]; haufen = []
    if len(Pu):
        key = np.c_[np.round(Pu[:, :2] @ u_), np.round(Pu[:, :2] @ n_, 1), np.round(Pu[:, 2] * 2) / 2]   # 1 m entlang, 0,1 m normal, 0,5 m Hoehe
        ks, cnt = np.unique(key, axis=0, return_counts=True)
        for k_, c_ in sorted(zip(ks.tolist(), cnt.tolist()), key=lambda x: -x[1])[:25]: haufen.append({"u": k_[0], "n": k_[1], "z": k_[2], "stichproben": int(c_)})
    q = lambda p: round(float(np.percentile(t[fin], p)), 4) if fin.any() else None
    erg["duenn"] = {"geraet": dev, "stichproben": int(a.n), "grenze_mm_druck": a.grenze_mm, "grenze_m_modell": round(gm, 4), "ohne_treffer": round(float(1 - fin.mean()), 4),
                    "dicke_m_p0_1": q(0.1), "dicke_m_p1": q(1), "dicke_m_p5": q(5), "anteil_unter": round(float(unter.sum() / max(fin.sum(), 1)), 5), "haufen_unter_grenze": haufen,
                    "hinweis": "Kegelspitzen/Grate liefern lokal kleine Dicken (Quantil statt Minimum)"}
    out = os.path.join(od, "audit", "druck_vorcheck.json"); os.makedirs(os.path.dirname(out), exist_ok=True); json.dump(erg, open(out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in erg.items() if k != "ueberhang"}, indent=1, ensure_ascii=False)[:3000])
    print("Ueberhang >", a.winkel, "Grad:", erg["ueberhang"]["flaeche_m2"], "m2, Anteil", erg["ueberhang"]["anteil"])
    for b in baender: print("  z", b["z"], "m2", b["flaeche_m2"], "u", b["u"], "n", b["n"])
    print("->", out)


if __name__ == "__main__":
    main()
