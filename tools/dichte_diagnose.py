#!/usr/bin/env python3
"""dichte_diagnose.py - WARUM ist die dichte Wolke an einer Stelle duenn? Foto-Bedarf oder Rechen-Bedarf? (Nutzer 26.11.2026, generisch fuer jedes Objekt)

  tools/py tools/dichte_diagnose.py modelle/<obj>/objekt.json <sparse_ordner> <dichte.npy> [--zelle 5] [--aus audit/dichte_diagnose.json]

Je Zelle (waagerechtes Raster, Modellmeter; Hoehe 0,5..--zmax) werden drei Messgroessen verglichen:
  S  = Sparse-Punkte mit Spur >= 3 (die SfM hat Geometrie dort belegt)         -> Geometrie vorhanden
  K  = verschiedene Bilder, die diese Sparse-Punkte sehen                      -> Kameras vorhanden (und in der Dichtrechnung?)
  D  = Dichtpunkte                                                              -> Ergebnis
Urteil je Zelle (Schwellen = ANNAHME, in der Ausgabe als 'schwellen' mitgeschrieben):
  FOTO   S < s_min und K < k_min : die SfM sieht dort kaum Geometrie und kaum Kameras -> Fotos fehlen (Kameras/Blickrichtung/Ueberlappung) -> foto_luecken_plan / Aufnahmeauftrag
  RECHEN S >= s_min, K >= k_min, D/S < d_min : Fotos reichen, Dichtrechnung duenn -> lokale Wiederholung (Bildwahl je Zelle, PatchMatch ROI), KEINE neuen Fotos
  BASIS  S >= s_min, K < k_min   : wenige Kameras -> gezielt wenige Fotos aus anderer Richtung
  OK     sonst.
Verwandt: tools/abdeckung_quellen.py (Kamerarichtungen je Quelle), tools/foto_luecken_plan.py (Ansichten je Wandfeld), tools/dicht_modell.py + tools/dicht_bildwahl.py (Dichtrechnung).
Vorlaeufer: keiner - die drei Messwerte Geometrie/Kameras/Dichtpunkte wurden nie je Zelle gegeneinander gelegt (Schwabentor 26.11.: Nordzelle 190 Kameras, 3290 Sparse-, 11 000 Dichtpunkte).
Grenzen: Verdeckung/Himmel nicht geprueft; Zelle nach der Ausrichtung in messprotokoll/SFM-AUSRICHTUNG-<name>.json (X_sfm = s R X_modell + t).
"""
import sys, os, json, argparse, numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("sparse"); ap.add_argument("dicht")
    ap.add_argument("--zelle", type=float, default=5.0); ap.add_argument("--zmax", type=float, default=20.0); ap.add_argument("--ausrichtung")
    ap.add_argument("--s_min", type=int, default=20); ap.add_argument("--k_min", type=int, default=8); ap.add_argument("--d_min", type=float, default=0.25, help="Dichtpunkte je Sparse-Punkt unter Median x dieser Zahl = duenn")
    ap.add_argument("--radius", type=float, default=40.0, help="nur Zellen im Umkreis der Objektmitte (Modell 0/0)"); ap.add_argument("--aus"); a = ap.parse_args()
    import cv2, pycolmap
    od = os.path.dirname(os.path.abspath(a.objekt)); name = json.load(open(a.objekt)).get("name", os.path.basename(od)).lower()
    af = a.ausrichtung or next((os.path.join(od, "messprotokoll", f) for f in sorted(os.listdir(os.path.join(od, "messprotokoll"))) if f.startswith("SFM-AUSRICHTUNG")), None)
    T = json.load(open(af))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
    rec = pycolmap.Reconstruction(a.sparse); XYZ = []; TR = []
    for p in rec.points3D.values():
        if p.track.length() >= 3: XYZ.append(p.xyz); TR.append([e.image_id for e in p.track.elements])
    M = (np.array(XYZ) - t) @ R / s
    D = np.load(a.dicht, mmap_mode="r"); D = np.asarray(D[::4]); w = 4
    z = (M[:, 2] > 0.5) & (M[:, 2] < a.zmax); M = M[z]; TR = [x for x, k in zip(TR, z) if k]
    lo = np.floor(M[:, :2].min(0) / a.zelle).astype(int); hi = np.ceil(M[:, :2].max(0) / a.zelle).astype(int)
    ci = lambda X: np.floor(X[:, :2] / a.zelle).astype(int) - lo
    n = hi - lo + 1; S = np.zeros(n, int); Dm = np.zeros(n, int); KS = {}
    for (i, j), tr in zip(ci(M), TR):
        S[i, j] += 1; KS.setdefault((i, j), set()).update(tr)
    dz = (D[:, 2] > 0.5) & (D[:, 2] < a.zmax); Dd = D[dz]; c = ci(Dd); ok = (c >= 0).all(1) & (c < n).all(1)
    np.add.at(Dm, (c[ok, 0], c[ok, 1]), w)
    rel = Dm / np.maximum(S, 1); med = np.median(rel[S >= a.s_min]) if (S >= a.s_min).any() else 1.0
    out = []; zaehl = {"FOTO": 0, "RECHEN": 0, "BASIS": 0, "OK": 0}
    for i in range(n[0]):
        for j in range(n[1]):
            if np.hypot((i + lo[0] + .5) * a.zelle, (j + lo[1] + .5) * a.zelle) > a.radius: continue
            if S[i, j] == 0 and Dm[i, j] < 1000: continue
            K = len(KS.get((i, j), ()))
            if S[i, j] < a.s_min: u = "RECHEN" if K >= a.k_min else "FOTO"
            elif K < a.k_min: u = "BASIS"
            elif rel[i, j] < a.d_min * med: u = "RECHEN"
            else: u = "OK"
            zaehl[u] += 1
            if u != "OK": out.append({"x0": float((i + lo[0]) * a.zelle), "y0": float((j + lo[1]) * a.zelle), "sparse": int(S[i, j]), "kameras": K, "dicht": int(Dm[i, j]), "urteil": u})
    erg = {"objekt": name, "zelle_m": a.zelle, "schwellen": {"s_min": a.s_min, "k_min": a.k_min, "d_min": a.d_min, "median_dicht_je_sparse": float(med)}, "zaehlung": zaehl, "zellen": sorted(out, key=lambda r: (r["urteil"], -r["sparse"]))}
    aus = a.aus or os.path.join(od, "audit", "dichte_diagnose.json"); json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False)
    print(f"Zellen {a.zelle:g} m: {zaehl} (Median Dichtpunkte je Sparse-Punkt {med:.0f})")
    for r in erg["zellen"][:12]: print(f"  {r['urteil']:6s} x {r['x0']:>5.0f} y {r['y0']:>5.0f}  sparse {r['sparse']:>5d}  kameras {r['kameras']:>3d}  dicht {r['dicht']:>8d}")
    stark = [r for r in out if r["urteil"] == "RECHEN" and r["sparse"] >= 100]
    erg["rechen_stark"] = len(stark); json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False)
    print(f"RECHEN-Zellen mit >= 100 Sparse-Punkten: {len(stark)} (Hinweis-Tor ab 5: Fotos reichen, Dichtrechnung duenn -> tools/kachelfusion.py + wolke_vereinigen.py)")
    print("->", aus); return 3 if len(stark) >= 5 else 0


if __name__ == "__main__":
    sys.exit(main())
