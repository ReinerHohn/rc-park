#!/usr/bin/env python3
"""fassade_diagnose.py <objekt.json> --stl <modell.stl> [--aus diagnose.json] [--schritt 0.2] [--max-winkel 70] [--max-mpp 0.06] [--tol 0.10] - WARUM hat eine Fassade keine Bilddaten?

17.11.2026 (kaufhaus_gk: "nur 30 % der Fassadenflaeche haben Bilddaten"). Die Zahl "Abdeckung" von fassade_ortho.py sagt nicht, WO die Zellen verloren gehen.
Dieses Werkzeug rechnet dieselbe Kaskade wie fassade_ortho.py (gleiche Fassaden aus den LoD2-Waenden, gleiche Kameraregel, gleiche Schwellen) auf einem groben Raster
(--schritt) und zaehlt je Fassade, wie weit die Zellen kommen:
  wand      Zellen im Fassadenpolygon (LoD2-WallSurface) mit Modellflaeche
  angebaut  davon: ein NACHBARGEBAEUDE (LoD2) steht < --angebaut m vor der Zelle = Brandwand, kann nie fotografiert werden -> gehoert nicht in den Nenner
  frei      = wand - angebaut  (die Flaeche, die ueberhaupt ein Fassadenbild haben kann)
  je freier Zelle die WEITESTE Stufe, die irgendeine Messkamera erreicht:
    kein_foto   keine Kamera hat die Zelle von vorn im Bild
    winkel      im Bild, aber nur flacher als --max-winkel
    aufloesung  Winkel gut, aber nur groeber als --max-mpp
    eigen       Aufloesung gut, aber das EIGENE Modell steht davor (Vorbau, Dach, anderer Fluegel; oder Wandebene des Modells liegt falsch)
    nachbar     nur noch ein Nachbargebaeude (LoD2) steht davor
    gesehen     mindestens eine Kamera besteht alles
Dazu je Fassade die Kamerazahl je Stufe (Kamera zaehlt, wenn sie >= 2 % der freien Zellen so weit bringt) und die Kameraguete (sfm_guete) der sehenden Kameras.
Ausgabe: Tabelle + JSON. Kein Bild wird geladen (nur K-Dateien + Strahlen), Laufzeit Sekunden.
Lesart: viel 'kein_foto' = es gibt wirklich keine Fotos (Stufe seiten / Fotoauftrag); viel 'winkel'/'aufloesung' = Fotos da, Filter pruefen; viel 'eigen' = Modell/Wandebene pruefen;
viel 'angebaut'/'nachbar' = Flaeche ist keine freie Fassade (Abdeckung auf 'frei' beziehen).
"""
import os, sys, json, glob, math, argparse
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)
import fassade_ortho as FO

STUFEN = ("kein_foto", "winkel", "aufloesung", "eigen", "nachbar", "gesehen")


def diagnose(objekt, stl, schritt=0.2, max_winkel=70.0, max_mpp=0.06, tol=0.10, angebaut=1.0, nur_gute=False):
    obj = json.load(open(objekt)); od = os.path.dirname(os.path.abspath(objekt)); waende, mitte = FO.lod2_waende(obj); fas = FO.fassaden_gruppieren(waende, mitte)
    m = trimesh.load(stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); nb, n_nb = FO.nachbarn_netz(obj); alle = trimesh.util.concatenate([m, nb]) if nb is not None else m
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector
    ray_m = RI(m); ray_a = RI(alle); ray_n = RI(nb) if nb is not None else None; FN = np.asarray(alle.face_normals, float); P0 = np.asarray(alle.triangles[:, 0], float); n_eigen = len(m.faces)
    kam = {}
    for kf in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        c = json.load(open(kf)).get("kamera"); nm = os.path.basename(kf)[2:-5]
        if isinstance(c, dict) and "rvec" in c and "cx" in c: kam[nm] = c
    mit_tor = any("buendel_tor" in c for c in kam.values())
    def ok(nm, c):                                                       # dieselbe Regel wie fassade_ortho.py
        if nm.startswith(("dl_", "neu__")): return bool(c.get("vertrauen"))
        if c.get("buendel_tor", {}).get("ok"): return True
        return (not mit_tor) and not nm.startswith("video")
    mess = {nm: c for nm, c in kam.items() if ok(nm, c) and (not nur_gute or (c.get("sfm_guete") or {}).get("klasse") != "schlecht")}
    erg = dict(objekt=objekt, kameras=len(kam), messkameras=len(mess), nachbarn_lod2=n_nb, schritt_m=schritt, max_winkel=max_winkel, max_mpp=max_mpp, fassaden=[])
    cgr = math.cos(math.radians(max_winkel))
    for i, F in enumerate(fas):
        n3 = np.array(F["n"] + [0.0]); d = np.array(F["d"]); o = np.array(F["o"]); uu = np.arange(F["u"][0] + schritt / 2, F["u"][1], schritt); zz = np.arange(F["z"][0] + schritt / 2, F["z"][1], schritt)
        U, Zg = np.meshgrid(uu, zz); inn = np.zeros(U.shape, np.uint8)
        for poly in F["polys_uz"]: cv2.fillPoly(inn, [np.array([[(u_ - F["u"][0]) / schritt, (z_ - F["z"][0]) / schritt] for u_, z_ in poly], np.int32)], 1)
        X = np.c_[o[0] + U.ravel() * d[0], o[1] + U.ravel() * d[1], Zg.ravel()][inn.ravel() > 0]
        if not len(X): continue
        ur = X + n3 * 3.0; ti, ri = FO.erster_treffer(ray_m, ur, -n3)                               # vorderste Modellflaeche wie fassade_ortho.relief
        loc, gut = trimesh.intersections.planes_lines(plane_origins=np.asarray(m.triangles[:, 0])[ti], plane_normals=np.asarray(m.face_normals)[ti], line_origins=ur[ri], line_directions=np.broadcast_to(-n3, (len(ri), 3)))
        rel = np.full(len(X), np.nan); rel[ri[gut]] = 3.0 - np.linalg.norm(loc - ur[ri[gut]], axis=1); rel[rel < -6.0] = np.nan
        S = X[np.isfinite(rel)] + n3 * rel[np.isfinite(rel)][:, None]; n_wand = len(S)
        if not n_wand: continue
        ang = np.zeros(n_wand, bool)
        if ray_n is not None:                                            # Brandwand: Nachbar-LoD2 direkt vor der Zelle
            S0 = S - n3 * 0.3; ti, ri = FO.erster_treffer(ray_n, S0, n3)      # Start 0,3 m HINTER der Flaeche: die Nachbarwand liegt oft genau in der eigenen Wandebene (gemeinsame Brandwand)
            if len(ri):
                nn = np.asarray(nb.face_normals)[ti]; nen = nn @ n3; t_ = np.einsum("ij,ij->i", np.asarray(nb.triangles[:, 0])[ti] - S0[ri], nn) / np.where(np.abs(nen) < 1e-12, 1e-12, nen); ang[ri[(t_ >= 0) & (t_ < angebaut + 0.3)]] = True
        Sf = S[~ang]; n_frei = len(Sf); stufe = np.zeros(n_frei, np.int8); kz = {s_: 0 for s_ in STUFEN[1:]}; guete = {}; sehende = []
        for nm, c in mess.items():
            if not n_frei: break
            R = cv2.Rodrigues(np.asarray(c["rvec"], float))[0]; t = np.asarray(c["t"], float); tr = np.asarray(c.get("rahmen_verschiebung", [0, 0, 0]), float); Cw = -R.T @ t - tr
            v = Cw - Sf; dist = np.linalg.norm(v, axis=1)
            if not np.isfinite(dist).all() or dist.max() > 2000 or dist.min() < 0.5: continue
            cosw = (v @ n3) / dist; pc = (Sf + tr) @ R.T + t; z = np.maximum(pc[:, 2], 1e-6); xn = pc[:, 0] / z; yn = pc[:, 1] / z; s_ = 1 + float(c.get("k1") or 0.0) * (xn * xn + yn * yn)
            W_, H_ = (c.get("bild") or [2 * c["cx"], 2 * c["cy"]])[:2]; pu = c["f_px"] * xn * s_ + c["cx"]; pv = c["f_px"] * yn * s_ + c["cy"]
            g1 = (cosw > 0.02) & (pc[:, 2] > 1) & (pu >= 0) & (pu < W_ - 1) & (pv >= 0) & (pv < H_ - 1); g2 = g1 & (cosw > cgr); g3 = g2 & (dist / (c["f_px"] * np.maximum(cosw, 1e-3)) < max_mpp)
            st = np.zeros(n_frei, np.int8); st[g1] = 1; st[g2] = 2; st[g3] = 3
            j = np.where(g3)[0]
            if len(j):
                dirs = -v[j] / dist[j, None]; q = FO.erster_treffer(ray_a, Cw, dirs, roh=True); tr_ = q >= 0; qq = np.clip(q, 0, None); nen = np.einsum("ij,ij->i", dirs, FN[qq]); e = np.where(tr_, np.einsum("ij,ij->i", P0[qq] - Cw, FN[qq]) / np.where(np.abs(nen) < 1e-12, 1e-12, nen), np.inf)
                sicht = np.abs(e - dist[j]) < tol + 0.002 * dist[j]; davor = ~sicht & (e < dist[j]); st[j[sicht]] = 5; st[j[davor & (q >= n_eigen)]] = 4      # 4 = nur Nachbar davor; eigenes Modell davor bleibt 3
                st[j[~sicht & ~davor]] = 3
            stufe = np.maximum(stufe, st)
            for k_, s_ in enumerate(STUFEN[1:], 1):
                if (st >= k_).sum() >= max(3, 0.02 * n_frei): kz[s_] += 1
            if (st == 5).sum() >= max(3, 0.02 * n_frei): kl = (c.get("sfm_guete") or {}).get("klasse", "ohne"); guete[kl] = guete.get(kl, 0) + 1; sehende.append(((st == 5).mean(), nm))
        ant = {s_: round(float((stufe == k_).mean()), 3) if n_frei else 0.0 for k_, s_ in enumerate(STUFEN)}
        erg["fassaden"].append(dict(id=f"f{i:02d}", n=F["n"], flaeche_m2=F["flaeche_m2"], wand_m2=round(n_wand * schritt ** 2, 1), angebaut_m2=round(float(ang.sum()) * schritt ** 2, 1), frei_m2=round(n_frei * schritt ** 2, 1),
                                    anteil_frei=ant, kameras_bis=kz, guete_sehende=guete, beste=[(round(a_, 2), b_) for a_, b_ in sorted(sehende, reverse=True)[:5]]))
    return erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--aus"); ap.add_argument("--schritt", type=float, default=0.2); ap.add_argument("--max-winkel", type=float, default=70.0); ap.add_argument("--max-mpp", type=float, default=0.06)
    ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--angebaut", type=float, default=1.0, help="Nachbar-LoD2 naeher als dies (m) vor der Zelle = Brandwand"); ap.add_argument("--nur-gute", action="store_true", help="Kameras der Klasse 'schlecht' (sfm_guete) weglassen - zeigt, was die Kameraguete kostet"); a = ap.parse_args()
    E = diagnose(a.objekt, a.stl, a.schritt, a.max_winkel, a.max_mpp, a.tol, a.angebaut, a.nur_gute)
    print(f"{E['messkameras']} Messkameras von {E['kameras']} K-Dateien, {E['nachbarn_lod2']} Nachbargebaeude (LoD2); Anteile in % der FREIEN Wandflaeche")
    print("  id   LoD2 m2  angebaut   frei m2 | kein_foto winkel aufloes. eigen nachbar GESEHEN | Kameras: im Bild/Winkel/Aufl./frei/sehen | Guete der sehenden")
    gf = gs = gw = 0.0
    for F in E["fassaden"]:
        p = F["anteil_frei"]; k = F["kameras_bis"]; gf += F["frei_m2"]; gs += F["frei_m2"] * p["gesehen"]; gw += F["wand_m2"]
        print(f"  {F['id']} {F['wand_m2']:8.1f} {F['angebaut_m2']:9.1f} {F['frei_m2']:9.1f} | {p['kein_foto'] * 100:8.0f} {p['winkel'] * 100:6.0f} {p['aufloesung'] * 100:7.0f} {p['eigen'] * 100:6.0f} {p['nachbar'] * 100:6.0f} {p['gesehen'] * 100:7.0f} | {k['winkel']:3d}/{k['aufloesung']:3d}/{k['eigen']:3d}/{k['nachbar']:3d}/{k['gesehen']:3d} | {F['guete_sehende']}")
    E["summe"] = dict(wand_m2=round(gw, 1), frei_m2=round(gf, 1), gesehen_m2=round(gs, 1), gesehen_von_frei=round(gs / max(gf, 1e-9), 3), gesehen_von_wand=round(gs / max(gw, 1e-9), 3))
    print(f"SUMME: Wand {gw:.0f} m2, davon frei {gf:.0f} m2; gesehen {gs:.0f} m2 = {100 * gs / max(gf, 1e-9):.0f} % der freien, {100 * gs / max(gw, 1e-9):.0f} % der ganzen LoD2-Wandflaeche")
    if a.aus: json.dump(E, open(a.aus, "w"), indent=1); print("->", a.aus)


if __name__ == "__main__":
    sys.exit(main())
