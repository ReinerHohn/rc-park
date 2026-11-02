#!/usr/bin/env python3
"""video_merge.py - obere Turmhaelfte aus der dichten Videowolke (video_dicht.py) in die Nordwolke einfuegen (Register BQ).

Nur Punkte der Videowolke mit z >= --zmin (Standard 38 m, dort ist die Strassenwolke duenn) und |x|,|y| <= --rand innerhalb der Turmgrundflaeche (+Rand);
statistisch gefiltert (Nachbarn im Voxel), auf die Dichte der Nordwolke gedeckelt (--max-anteil). Schreibt sfm/dicht_<seite>_entzerrt.npy neu; die Ausgangswolke bleibt als *_ohnevideo.npy
(idempotent: Marker sfm/video_merge.json). KEIN Massstab-Beweis: Skala/Lage stammen aus der Ausrichtung am Nordnetz (Bodenanker).
  /media/oem/scan/venv-colmap/bin/python -I tools/video_merge.py modelle/<objekt>/objekt.json <video_sfm_ordner> [--seite nord] [--zmin 38]
"""
import os, sys, json, argparse, numpy as np

def verfeinern(P, V, zb=(14, 48), seite=9.0, it=30, trim=0.7):
    """Starre Verschiebung der Videowolke auf die Strassenwolke (getrimmter ICP, nur Translation) im Ueberlappungsbereich z 14-48 m.
    Messung 2026-11-03 (Register BR): Sim3 aus Punktkorrespondenzen liess 0,65 m Versatz in x (alle Hoehenbaender gleich, y/z ~0) - der Nutzer sah das Dach 'schweben'."""
    from scipy.spatial import cKDTree
    a = P[(P[:, 2] >= zb[0]) & (P[:, 2] < zb[1]) & (np.abs(P[:, 0]) < seite) & (np.abs(P[:, 1]) < seite)]
    b = V[(V[:, 2] >= zb[0]) & (V[:, 2] < zb[1]) & (np.abs(V[:, 0]) < seite) & (np.abs(V[:, 1]) < seite)]
    if len(a) < 500 or len(b) < 500: return np.zeros(3), None, None
    b = b[np.random.default_rng(0).choice(len(b), min(len(b), 30000), replace=False)]; tr = cKDTree(a); t = np.zeros(3)
    d0 = float(np.median(tr.query(b)[0]))
    for _ in range(it):
        d, i = tr.query(b + t); k = d < np.quantile(d, trim); t += (a[i[k]] - (b[k] + t)).mean(0)
    return t, d0, float(np.median(tr.query(b + t)[0]))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("video"); ap.add_argument("--seite", default="nord"); ap.add_argument("--zmin", type=float, default=38.0)
    ap.add_argument("--rand", type=float, default=8.0); ap.add_argument("--voxel", type=float, default=0.15); ap.add_argument("--min-voxel", type=int, default=3); ap.add_argument("--max-anteil", type=float, default=1.0); ap.add_argument("--zurueck", action="store_true"); ap.add_argument("--ohne-verfeinern", action="store_true"); ap.add_argument("--ohne-clippruefung", action="store_true"); ap.add_argument("--max-clipversatz", type=float, default=0.5, help="Clip-Hoehenband wird verworfen, wenn Restversatz (x,y) zur Strassenwolke darueber liegt (m)"); ap.add_argument("--max-nn", type=float, default=0.3, help="Pruefung: NN-Median nach Verfeinerung (m); darueber wird NICHT eingefuegt")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); sd = os.path.join(od, "sfm"); f = os.path.join(sd, f"dicht_{a.seite}_entzerrt.npy"); fc = f.replace("_entzerrt.npy", "_farben.npy"); f0 = f.replace(".npy", "_ohnevideo.npy"); mk = os.path.join(sd, "video_merge.json")
    if a.zurueck:
        if os.path.exists(f0):
            os.replace(f0, f); c0 = f0.replace("_entzerrt", "_farben")
            if os.path.exists(c0): os.replace(c0, fc)                                              # Farben mit zuruecksetzen (sonst Laengenfehler)
            print("zurueck: Wolke ohne Video"); os.path.exists(mk) and os.remove(mk)
        return
    P = np.load(f).astype(np.float64); n0 = len(P)
    if os.path.exists(mk) and json.load(open(mk)).get("n_nach") == n0: print("bereits eingefuegt (Marker passt) - nichts zu tun"); return
    V = np.load(os.path.join(a.video, "dicht_modell.npy")).astype(np.float64); Cv = np.load(os.path.join(a.video, "dicht_farben.npy"))
    # (1) Hoehenabhaengige Tiefenkorrektur wie bei der Strassenwolke (wolke_vs_modell --entzerren): die Videowolke liegt im UNentzerrten Rahmen des Rohnetzes.
    #     Beleg 2026-11-03: Spitze z>=55 roh x=-1,5 m, entzerrt +0,06 m, Laser-DOM1-Spitzenzellen x -0,26..0,01 (Register BR). Nur Nordseite (Tiefenachse x).
    dj = os.path.join(od, "audit", f"wolke_vs_modell_{a.seite}.json"); drift = json.load(open(dj)).get("drift") if os.path.exists(dj) else None
    if drift and a.seite == "nord": V[:, 0] += drift[0] * V[:, 2] + drift[1]; print(f"Drift-Korrektur der Videowolke: x += {drift[0] * 1000:.1f} mm/m * z {drift[1]:+.2f} m")
    else: print("WARNUNG: keine Drift-Korrektur der Videowolke (nur Nordseite mit wolke_vs_modell-Drift implementiert)")
    # (2) Clip-Konsistenz: Punkte nach dominantem Clip (>= 80 % der Bildsichten) und Hoehenband gegen die Strassenwolke pruefen; abweichende Clip-Baender werden NICHT eingefuegt
    #     (Beobachtung Nutzer: 'zwei parallele Daecher'; Ursache: Clip RBC7Co kippt im Gesamt-SfM, +0,9 m bei z 32-48, +2,1 m darueber).
    clipinfo = []; pc = os.path.join(a.video, "punkt_clips.npy"); loes = np.zeros(len(V), bool)
    if os.path.exists(pc) and not a.ohne_clippruefung:
        from scipy.spatial import cKDTree
        A_ = np.load(pc).astype(float)
        if len(A_) != len(V): sys.exit("punkt_clips.npy passt nicht zur Videowolke - video_dicht.py neu laufen lassen")
        fr = A_ / np.maximum(A_.sum(1, keepdims=True), 1); dom = fr.argmax(1); rein = fr.max(1) >= 0.8; cn = json.load(open(os.path.join(a.video, "punkt_clips.json")))
        for ci in range(A_.shape[1]):
            for lo, hi in [(14, 32), (32, 48), (48, 70)]:
                sel = (dom == ci) & rein & (V[:, 2] >= lo) & (V[:, 2] < hi); b = V[sel & (np.abs(V[:, 0]) < 9) & (np.abs(V[:, 1]) < 9)]
                if len(b) < 500: continue
                bs = b[np.random.default_rng(0).choice(len(b), min(len(b), 15000), replace=False)]
                aa = P[(P[:, 2] >= lo) & (P[:, 2] < hi) & (np.abs(P[:, 0]) < 9) & (np.abs(P[:, 1]) < 9)]
                if len(aa) < 300: continue
                tr = cKDTree(aa); tt = np.zeros(3)
                for _ in range(25): dd, ii = tr.query(bs + tt); kk = dd < np.quantile(dd, 0.7); tt += (aa[ii[kk]] - (bs[kk] + tt)).mean(0)
                ok = float(abs(tt[0])) <= a.max_clipversatz                                  # Tiefenachse x (Nordseite); y/z sind Seiten-/Hoehenlage
                clipinfo.append(dict(clip=cn[ci], z=[lo, hi], n=int(len(b)), verschiebung_m=tt.round(2).tolist(), ok=bool(ok)))
                print(f"  Clip {cn[ci][:8]} z {lo}-{hi}: n={len(b)} Rest-Versatz {tt.round(2)} -> {'ok' if ok else 'VERWORFEN (inkonsistent)'}")
                if not ok: loes |= sel
    k = (V[:, 2] >= a.zmin) & (np.abs(V[:, 0]) <= a.rand) & (np.abs(V[:, 1]) <= a.rand) & ~loes; V, Cv = V[k], Cv[k]; n_roh = len(V)
    vox = np.floor(V / a.voxel).astype(np.int64); _, inv, cnt = np.unique(vox, axis=0, return_inverse=True, return_counts=True); keep = cnt[inv.ravel()] >= a.min_voxel; V, Cv = V[keep], Cv[keep]
    print(f"Videopunkte nach Zuschnitt/Clip-Pruefung: {len(V)} ({int(loes.sum())} Punkte aus inkonsistenten Clip-Baendern verworfen)")
    t, d0, d1 = (np.zeros(3), None, None) if a.ohne_verfeinern else verfeinern(P, V)
    if d0 is not None:
        print(f"Verfeinerung: Verschiebung {t.round(2)} m, NN-Median {d0:.2f} -> {d1:.2f} m")
        if d1 > a.max_nn: sys.exit(f"Videowolke passt nach Verfeinerung nicht zur Strassenwolke (NN-Median {d1:.2f} m > {a.max_nn} m) - nicht eingefuegt (Pruefung)")
        V = V + t
    nmax = int(a.max_anteil * n0)
    if len(V) > nmax: sel = np.random.default_rng(1).choice(len(V), nmax, replace=False); V, Cv = V[sel], Cv[sel]
    C0 = np.load(fc)
    if len(C0) != n0: sys.exit(f"Farbdatei ({len(C0)}) passt nicht zur Wolke ({n0}) - Abbruch")
    np.save(f0, P.astype(np.float32)); np.save(f0.replace("_entzerrt", "_farben"), C0)          # Sicherung IMMER aus der aktuellen (unvermischten) Wolke
    np.save(f, np.vstack([P, V]).astype(np.float32)); np.save(fc, np.vstack([C0, Cv]))
    json.dump(dict(n_vor=n0, n_video=int(len(V)), n_video_roh=n_roh, zmin=a.zmin, n_nach=n0 + int(len(V)), video=a.video, verschiebung=t.tolist(), nn_vor=d0, nn_nach=d1, clips=clipinfo), open(mk, "w"))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(verschiebung_m=t.tolist(), nn_median_vor_m=d0, nn_median_nach_m=d1, clips=clipinfo, schwelle_m=a.max_nn, ok=(d1 is None or d1 <= a.max_nn), baender_z=[14, 48],
                   hinweis="starre Verschiebung Video->Strassenwolke (getrimmter ICP); vor 2026-11-03 fehlte sie: 0,65 m Versatz in x (Register BR)"), open(os.path.join(od, "audit", "video_versatz.json"), "w"), indent=1)
    print(f"Video eingefuegt: {len(V)} Punkte (roh {n_roh}, z >= {a.zmin} m) zu {n0} Nordpunkten; ohne Video gesichert: {os.path.basename(f0)}")

if __name__ == "__main__":
    main()
