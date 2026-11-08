#!/usr/bin/env python3
"""video_merge.py - obere Turmhaelfte aus der dichten Videowolke (video_dicht.py) in die Nordwolke einfuegen (Register BQ).

Nur Punkte der Videowolke mit z >= --zmin (Standard 38 m, dort ist die Strassenwolke duenn) und |x|,|y| <= --rand innerhalb der Turmgrundflaeche (+Rand);
statistisch gefiltert (Nachbarn im Voxel), auf die Dichte der Nordwolke gedeckelt (--max-anteil). Schreibt sfm/dicht_<seite>_entzerrt.npy neu; die Ausgangswolke bleibt als *_ohnevideo.npy
(idempotent: Marker sfm/video_merge.json). KEIN Massstab-Beweis: Skala/Lage stammen aus der Ausrichtung am Nordnetz (Bodenanker).
  /media/oem/scan/venv-colmap/bin/python -I tools/video_merge.py modelle/<objekt>/objekt.json <video_sfm_ordner> [--seite nord] [--zmin 38]
"""
import os, sys, json, argparse, shutil, struct, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from video_netz import netz_info
BER = None                                                                                    # (xmin, xmax, ymin, ymax) Modellrahmen; None = Altverhalten +-Rand um den Ursprung (Martinstor-Turm)

def inbox(X, hw):
    """Punkte innerhalb des Objektbereichs: video_stufe.bereich / --bereich, sonst +-hw um den Ursprung (Altverhalten)."""
    if BER: return (X[:, 0] >= BER[0]) & (X[:, 0] <= BER[1]) & (X[:, 1] >= BER[2]) & (X[:, 1] <= BER[3])
    return (np.abs(X[:, 0]) < hw) & (np.abs(X[:, 1]) < hw)

def ply_lesen_roh(fp):
    with open(fp, "rb") as f:
        h = []
        while True:
            l = f.readline().decode("ascii").strip(); h.append(l)
            if l == "end_header": break
        n = int([x for x in h if x.startswith("element vertex")][0].split()[-1]); return h, n, f.read()

def fused_vereinigen(basis_dir, aus_dir, Vsfm, Cv):
    """Basis-fused.ply + Videopunkte (SfM-Rahmen des Basisnetzes, Normalen 0) -> aus_dir/fused.ply; .vis: Basiseintraege unveraendert, Videopunkte mit 0 Sichtbildern."""
    h, n, roh = ply_lesen_roh(os.path.join(basis_dir, "fused.ply")); assert len(roh) == 27 * n, "unerwartetes fused.ply-Format (erwartet x y z nx ny nz r g b)"
    rec = np.zeros(len(Vsfm), dtype=np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)])); rec["p"] = Vsfm.astype(np.float32); rec["c"] = Cv
    h2 = [("element vertex %d" % (n + len(Vsfm))) if x.startswith("element vertex") else x for x in h]
    with open(os.path.join(aus_dir, "fused.ply"), "wb") as f: f.write(("\n".join(h2) + "\n").encode("ascii")); f.write(roh); f.write(rec.tobytes())
    vb = open(os.path.join(basis_dir, "fused.ply.vis"), "rb").read()
    with open(os.path.join(aus_dir, "fused.ply.vis"), "wb") as f: f.write(struct.pack("<Q", n + len(Vsfm))); f.write(vb[8:]); f.write(np.zeros(len(Vsfm), "<u4").tobytes())
    return n

def verfeinern(P, V, zb=(14, 48), seite=9.0, it=30, trim=0.7):
    """Starre Verschiebung der Videowolke auf die Strassenwolke (getrimmter ICP, nur Translation) im Ueberlappungsbereich z 14-48 m.
    Messung 2026-11-03 (Register BR): Sim3 aus Punktkorrespondenzen liess 0,65 m Versatz in x (alle Hoehenbaender gleich, y/z ~0) - der Nutzer sah das Dach 'schweben'."""
    from scipy.spatial import cKDTree
    a = P[(P[:, 2] >= zb[0]) & (P[:, 2] < zb[1]) & inbox(P, seite)]
    b = V[(V[:, 2] >= zb[0]) & (V[:, 2] < zb[1]) & inbox(V, seite)]
    if len(a) < 500 or len(b) < 500: return np.zeros(3), None, None
    b = b[np.random.default_rng(0).choice(len(b), min(len(b), 30000), replace=False)]; tr = cKDTree(a); t = np.zeros(3)
    d0 = float(np.median(tr.query(b)[0]))
    for _ in range(it):
        d, i = tr.query(b + t); k = d < np.quantile(d, trim); t += (a[i[k]] - (b[k] + t)).mean(0)
    return t, d0, float(np.median(tr.query(b + t)[0]))

def video_ausgabe(a, NI, P, C0, V, Cv, t, d0, d1, n_roh, clipinfo, vdir, mk, od):
    """Neuer Standard (Register CR): vereinigte Wolke nach sfm/dicht_<netz>_video/, Basis bleibt. fused.ply im SfM-Rahmen des Basisnetzes (wie freiraum.dicht), dicht_modell.npy im Modellrahmen."""
    import pycolmap
    os.makedirs(vdir, exist_ok=True); S = json.load(open(NI["ausr"]))["transformation"]; Rm = pycolmap.Rotation3d(np.array(S["rvec"])).matrix(); tm = np.array(S["t"])
    Vsfm = S["s"] * (V @ Rm.T) + tm                                                              # Modellrahmen -> SfM-Rahmen (Umkehr von Xm = ((Y - tm) @ Rm) / s)
    n_basis_ply = fused_vereinigen(NI["basis_fused"], vdir, Vsfm, Cv) if os.path.exists(os.path.join(NI["basis_fused"], "fused.ply")) and os.path.exists(os.path.join(NI["basis_fused"], "fused.ply.vis")) else None
    np.save(os.path.join(vdir, "dicht_modell.npy"), np.vstack([P, V]).astype(np.float32)); np.save(os.path.join(vdir, "dicht_farben.npy"), np.vstack([C0, Cv])); np.save(os.path.join(vdir, "video_punkte_modell.npy"), V.astype(np.float32)); np.save(os.path.join(vdir, "video_punkte_farben.npy"), Cv)
    shutil.copy(NI["ausr"], os.path.join(vdir, "ausrichtung.json"))
    ku = os.path.join(NI["basis_fused"], "kameras_unverzerrt.json")
    if os.path.exists(ku): shutil.copy(ku, vdir)
    erg = dict(dicht_mtime=os.path.getmtime(os.path.join(a.video, "dicht_modell.npy")), n_basis=len(P), n_video=int(len(V)), n_video_roh=n_roh, n_nach=len(P) + int(len(V)), zmin=a.zmin, video=a.video, basis=NI["basis_npy"], basis_fused=NI["basis_fused"], basis_ply_punkte=n_basis_ply, verschiebung=t.tolist(), nn_vor=d0, nn_nach=d1, clips=clipinfo,
               hinweis="Basiswolke unveraendert (Register BT: Kette nie auf verschmolzener Wolke); nur fuer wolke_solid/Viewer; Videopunkte haben 0 Sichtbilder im .vis")
    json.dump(erg, open(mk, "w"), indent=1); json.dump(dict(verschiebung_m=t.tolist(), nn_median_vor_m=d0, nn_median_nach_m=d1, clips=clipinfo, schwelle_m=a.max_nn, ok=(d1 is None or d1 <= a.max_nn)), open(os.path.join(od, "audit", "video_versatz.json") if os.path.isdir(os.path.join(od, "audit")) else os.path.join(vdir, "video_versatz.json"), "w"), indent=1)
    op = os.path.abspath(a.objekt); o = json.load(open(op)); fr = o.get("freiraum") or {}
    o["freiraum_video"] = dict(dicht=vdir, ausrichtung=fr.get("ausrichtung") or os.path.relpath(NI["ausr"], od), hinweis="vereinigte Wolke (Basis + Video) nur fuer wolke_solid/Viewer; freiraum bleibt auf der Basis (Register CR/BT)", n_video=int(len(V)), n_basis=len(P))
    json.dump(o, open(op, "w"), indent=1, ensure_ascii=False)
    print(f"Video vereinigt: {len(V)} Videopunkte (roh {n_roh}, z >= {a.zmin} m) + {len(P)} Basispunkte -> {vdir} (Basis unveraendert); objekt.json freiraum_video gesetzt")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("video"); ap.add_argument("--seite", default=None, help="Netzname (Standard: aus objekt.json, video_netz.py)"); ap.add_argument("--inplace", action="store_true", help="ALTVERHALTEN: Basiswolke sfm/dicht_<netz>_entzerrt.npy ueberschreiben (Register BQ/BT: Kette danach nicht mehr auf dieser Wolke). Standard: Ausgabe nach sfm/dicht_<netz>_video/, Basis bleibt (Register CR)"); ap.add_argument("--bereich", nargs=4, type=float, help="xmin xmax ymin ymax im Modellrahmen (Standard video_stufe.bereich, sonst +-rand um den Ursprung)"); ap.add_argument("--icp-z", nargs=2, type=float, help="Hoehenband der starren Verfeinerung (Standard video_stufe.icp_z, sonst 14 48)"); ap.add_argument("--pruef-z-unten", type=float, help="Clips, die nirgends gegen die Basis pruefbar sind, werden ueber dieser Hoehe verworfen (Standard video_stufe.pruef_z_unten, sonst 30)"); ap.add_argument("--zmin", type=float, default=38.0)
    ap.add_argument("--rand", type=float, default=8.0); ap.add_argument("--voxel", type=float, default=0.15); ap.add_argument("--min-voxel", type=int, default=3); ap.add_argument("--max-anteil", type=float, default=1.0); ap.add_argument("--zurueck", action="store_true"); ap.add_argument("--ohne-verfeinern", action="store_true"); ap.add_argument("--ohne-clippruefung", action="store_true"); ap.add_argument("--passen", type=int, default=2, help="Durchgaenge der Clip-Bandkorrektur"); ap.add_argument("--max-clipversatz", type=float, default=0.5, help="Clip-Hoehenband wird verworfen, wenn Restversatz (x,y) zur Strassenwolke darueber liegt (m)"); ap.add_argument("--max-nn", type=float, default=0.3, help="Pruefung: NN-Median nach Verfeinerung (m); darueber wird NICHT eingefuegt")
    a = ap.parse_args(); NI = netz_info(a.objekt); od = NI["od"]; sd = NI["sd"]; a.seite = a.seite or NI["netz"]; cfg = NI["cfg"]; global BER
    BER = tuple(a.bereich or cfg.get("bereich") or ()) or None; ICPZ = tuple(a.icp_z or cfg.get("icp_z") or (14, 48)); PZU = a.pruef_z_unten if a.pruef_z_unten is not None else cfg.get("pruef_z_unten", 30)
    f = os.path.join(sd, f"dicht_{a.seite}_entzerrt.npy") if a.inplace else NI["basis_npy"]; fc = f.replace("_entzerrt.npy", "_farben.npy").replace("_modell.npy", "_farben.npy"); f0 = f.replace(".npy", "_ohnevideo.npy"); vdir = NI["video_dir"]
    mk = os.path.join(sd, "video_merge.json") if a.inplace else os.path.join(vdir, "video_merge.json")
    if a.zurueck and not a.inplace:
        shutil.rmtree(vdir, ignore_errors=True); print(f"zurueck: {vdir} entfernt (Basiswolke war unveraendert)"); return
    if a.zurueck:
        if os.path.exists(f0):
            os.replace(f0, f); c0 = f0.replace("_entzerrt", "_farben")
            if os.path.exists(c0): os.replace(c0, fc)                                              # Farben mit zuruecksetzen (sonst Laengenfehler)
            print("zurueck: Wolke ohne Video"); os.path.exists(mk) and os.remove(mk)
        return
    P = np.load(f).astype(np.float64); n0 = len(P)
    if a.inplace and os.path.exists(mk) and json.load(open(mk)).get("n_nach") == n0: print("bereits eingefuegt (Marker passt) - nichts zu tun"); return
    if not a.inplace and os.path.exists(mk) and json.load(open(mk)).get("video") == a.video and json.load(open(mk)).get("n_basis") == n0 and json.load(open(mk)).get("zmin") == a.zmin and json.load(open(mk)).get("dicht_mtime") == os.path.getmtime(os.path.join(a.video, "dicht_modell.npy")) and not os.environ.get("VIDEO_MERGE_NEU"): print("bereits vereinigt (Marker passt) - nichts zu tun"); return
    V = np.load(os.path.join(a.video, "dicht_modell.npy")).astype(np.float64); Cv = np.load(os.path.join(a.video, "dicht_farben.npy"))
    # (1) Hoehenabhaengige Tiefenkorrektur wie bei der Strassenwolke (wolke_vs_modell --entzerren): die Videowolke liegt im UNentzerrten Rahmen des Rohnetzes.
    #     Beleg 2026-11-03: Spitze z>=55 roh x=-1,5 m, entzerrt +0,06 m, Laser-DOM1-Spitzenzellen x -0,26..0,01 (Register BR). Nur Nordseite (Tiefenachse x).
    dj = os.path.join(od, "audit", f"wolke_vs_modell_{a.seite}.json"); drift = json.load(open(dj)).get("drift") if os.path.exists(dj) else None
    if drift and a.seite == "nord": V[:, 0] += drift[0] * V[:, 2] + drift[1]; print(f"Drift-Korrektur der Videowolke: x += {drift[0] * 1000:.1f} mm/m * z {drift[1]:+.2f} m")
    else: print("WARNUNG: keine Drift-Korrektur der Videowolke (nur Nordseite mit wolke_vs_modell-Drift implementiert)")
    # (2) Clip-Konsistenz: Punkte nach dominantem Clip (>= 80 % der Bildsichten) und Hoehenband gegen die Strassenwolke pruefen; abweichende Clip-Baender werden NICHT eingefuegt
    #     (Beobachtung Nutzer: 'zwei parallele Daecher'; Ursache: Clip RBC7Co kippt im Gesamt-SfM, +0,9 m bei z 32-48, +2,1 m darueber).
    clipinfo = []; pc = os.path.join(a.video, "punkt_clips.npy"); loes = np.zeros(len(V), bool); V_roh = V.copy()
    if os.path.exists(pc) and not a.ohne_clippruefung:
        from scipy.spatial import cKDTree
        A_ = np.load(pc).astype(float)
        if len(A_) != len(V): sys.exit("punkt_clips.npy passt nicht zur Videowolke - video_dicht.py neu laufen lassen")
        fr = A_ / np.maximum(A_.sum(1, keepdims=True), 1); dom = fr.argmax(1); rein = fr.max(1) >= 0.8; cn = json.load(open(os.path.join(a.video, "punkt_clips.json")))
        BAENDER = [tuple(b) for b in (cfg.get('baender_z') or [(14, 20), (20, 26), (26, 32), (32, 38), (38, 44), (44, 50), (50, 56)])]; ZM = np.array([(lo + hi) / 2 for lo, hi in BAENDER]); Pt = {}
        def icp3(aa, bs):
            tr = cKDTree(aa); tt = np.zeros(3)
            for _ in range(25): dd, ii = tr.query(bs + tt); kk = dd < np.quantile(dd, 0.7); tt += (aa[ii[kk]] - (bs[kk] + tt)).mean(0)
            return tt
        def band_t(Vx, ci, lo, hi):                                                                  # Versatz Clip-Band gegen die Strassenwolke (None: zu wenig Punkte)
            b = Vx[(dom == ci) & rein & (Vx[:, 2] >= lo) & (Vx[:, 2] < hi) & inbox(Vx, 9)]
            aa = P[(P[:, 2] >= lo) & (P[:, 2] < hi) & inbox(P, 9)]
            if len(b) < 500 or len(aa) < 300: return None, len(b)
            return icp3(aa, b[np.random.default_rng(0).choice(len(b), min(len(b), 15000), replace=False)]), len(b)
        # Kippen eines Clips (Register BR): Versatz je Clip UND Hoehenband messen, stueckweise linear ueber z interpolieren und abziehen (statt zu verwerfen). Kreuzprobe 2026-11-03:
        # RBC7Co gegen Strasse +1,93 (z 46-54) = gegen Referenzclip +2,11 abzueglich Referenz gegen Strasse -0,19 -> bandweise Korrektur ist in sich stimmig. Ueber dem letzten Band fehlt jede Referenz: Fremdclips dort verworfen.
        shifts = np.zeros((len(V), 3)); obergrenze = BAENDER[-1][1]; V = V_roh.copy()
        for passe in range(a.passen):                                                                # zweiter Durchgang auf den schon korrigierten Punkten (Rest ~0,25 m nach dem ersten, Nutzer-Sicht 2026-11-03)
            sp = np.zeros((len(V), 3)); Pt = {}
            for ci in range(A_.shape[1]):
                ts = [band_t(V, ci, lo, hi) for lo, hi in BAENDER]; ok_b = [i for i, (t, n) in enumerate(ts) if t is not None]
                if not ok_b: continue
                zc = ZM[ok_b]; T = np.array([ts[i][0] for i in ok_b]); Pt[ci] = (zc, T)
                for j in range(3): sp[:, j] += fr[:, ci] * np.interp(V[:, 2], zc, T[:, j])           # Mischpunkte: gewichtet nach Bildsichten je Clip; ausserhalb der Baender konstant
            V = V + sp; shifts += sp
        for ci in range(A_.shape[1]):                                                                 # Nachpruefung je Clip/Band mit korrigierten Punkten
            for (lo, hi) in BAENDER:
                t, n = band_t(V, ci, lo, hi)
                if t is None: continue
                ok = float(abs(t[0])) <= a.max_clipversatz; vor = band_t(V_roh, ci, lo, hi)[0]
                clipinfo.append(dict(clip=cn[ci], z=[lo, hi], n=int(n), versatz_vorher_m=vor.round(2).tolist(), rest_nach_korrektur_m=t.round(2).tolist(), ok=bool(ok)))
                print(f"  Clip {cn[ci][:8]} z {lo}-{hi}: n={n} Versatz {vor.round(2)} -> nach Korrektur {t.round(2)} -> {'ok' if ok else 'VERWORFEN'}")
                if not ok: loes |= (dom == ci) & rein & (V[:, 2] >= lo) & (V[:, 2] < hi)
        # Fremdclips ueber dem Referenzbereich: ohne Strassenwolke keine Pruefung -> nur Clips behalten, deren letzte Korrektur klein war (|dx| <= max)
        for ci, (zc, T) in Pt.items():
            if abs(T[-1, 0]) > a.max_clipversatz: loes |= (dom == ci) & rein & (V[:, 2] >= obergrenze); print(f"  Clip {cn[ci][:8]}: ueber {obergrenze} m verworfen (letzter Bandversatz {T[-1, 0]:+.2f} m, keine Referenz darueber)")
        for ci in range(A_.shape[1]):
            if ci not in Pt: loes |= (dom == ci) & rein & (V[:, 2] >= PZU); print(f"  Clip {cn[ci][:8]}: nirgends gegen die Strasse pruefbar -> ueber {PZU} m verworfen")
        np.save(os.path.join(a.video, "dicht_korrigiert.npy"), V.astype(np.float32)); np.save(os.path.join(a.video, "dicht_verworfen.npy"), loes)

    k = (V[:, 2] >= a.zmin) & inbox(V, a.rand + 1e-9) & ~loes; V, Cv = V[k], Cv[k]; n_roh = len(V)
    vox = np.floor(V / a.voxel).astype(np.int64); _, inv, cnt = np.unique(vox, axis=0, return_inverse=True, return_counts=True); keep = cnt[inv.ravel()] >= a.min_voxel; V, Cv = V[keep], Cv[keep]
    print(f"Videopunkte nach Zuschnitt/Clip-Pruefung: {len(V)} ({int(loes.sum())} Punkte aus inkonsistenten Clip-Baendern verworfen)")
    t, d0, d1 = (np.zeros(3), None, None) if a.ohne_verfeinern else verfeinern(P, V, zb=ICPZ, seite=9.0)
    if d0 is not None:
        print(f"Verfeinerung: Verschiebung {t.round(2)} m, NN-Median {d0:.2f} -> {d1:.2f} m")
        if d1 > a.max_nn: sys.exit(f"Videowolke passt nach Verfeinerung nicht zur Strassenwolke (NN-Median {d1:.2f} m > {a.max_nn} m) - nicht eingefuegt (Pruefung)")
        V = V + t
    nmax = int(a.max_anteil * n0)
    if len(V) > nmax: sel = np.random.default_rng(1).choice(len(V), nmax, replace=False); V, Cv = V[sel], Cv[sel]
    C0 = np.load(fc)
    if len(C0) != n0: sys.exit(f"Farbdatei ({len(C0)}) passt nicht zur Wolke ({n0}) - Abbruch")
    if a.inplace: np.save(f0, P.astype(np.float32)); np.save(f0.replace("_entzerrt", "_farben"), C0); np.save(f, np.vstack([P, V]).astype(np.float32)); np.save(fc, np.vstack([C0, Cv]))          # Altverhalten: Sicherung IMMER aus der aktuellen (unvermischten) Wolke
    else: video_ausgabe(a, NI, P, C0, V, Cv, t, d0, d1, n_roh, clipinfo, vdir, mk, od)
    if not a.inplace: return
    json.dump(dict(n_vor=n0, n_video=int(len(V)), n_video_roh=n_roh, zmin=a.zmin, n_nach=n0 + int(len(V)), video=a.video, verschiebung=t.tolist(), nn_vor=d0, nn_nach=d1, clips=clipinfo), open(mk, "w"))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(verschiebung_m=t.tolist(), nn_median_vor_m=d0, nn_median_nach_m=d1, clips=clipinfo, schwelle_m=a.max_nn, ok=(d1 is None or d1 <= a.max_nn), baender_z=[14, 48],
                   hinweis="starre Verschiebung Video->Strassenwolke (getrimmter ICP); vor 2026-11-03 fehlte sie: 0,65 m Versatz in x (Register BR)"), open(os.path.join(od, "audit", "video_versatz.json"), "w"), indent=1)
    print(f"Video eingefuegt: {len(V)} Punkte (roh {n_roh}, z >= {a.zmin} m) zu {n0} Nordpunkten; ohne Video gesichert: {os.path.basename(f0)}")

if __name__ == "__main__":
    main()
