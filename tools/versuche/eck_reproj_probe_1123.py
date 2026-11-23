"""Probe 23.11.2026: Eckstufe Kopplungsweg REPROJ (align_reconstructions_via_reprojections) gegen den Punkt-Weg (sim3_meter) und die COLMAP-Geschwister
via_points / via_proj_centers - jeweils mit DENSELBEN Toren (kopplung_pruefen, bei COLMAP-Wegen M_fest). Nur vorhandene Eckmodelle (kein Mapper, CPU, Sekunden).
Aufruf: tools/py tools/versuche/eck_reproj_probe_1123.py <ordner mit teil0/teil1/r_teil0/r_teil1/stufe_*/zwischen0*_s20/<m>> [aus.json]"""
import sys, os, json, time, glob, numpy as np, pycolmap
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import seiten_eck_koppeln as EK
D = sys.argv[1]; aus = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "probe.json"); erg = []
for ts in ("teil", "r_teil"):
    R = {t: pycolmap.Reconstruction(f"{D}/{ts}{t}") for t in (0, 1)}; at = {t: EK.ausdehnung([p.xyz for p in R[t].points3D.values()]) for t in R}
    for t in R: EK.NAMEN[t] = {im.name for im in R[t].images.values() if im.has_pose}
    print(ts, {t: len(EK.NAMEN[t]) for t in R}, "gemeinsam", len(EK.NAMEN[0] & EK.NAMEN[1]))
    for m in sorted(glob.glob(f"{D}/stufe_*/zwischen0*_s*/*/images.bin")):
        m = os.path.dirname(m); rE = pycolmap.Reconstruction(m); ausd = EK.ausdehnung([p.xyz for p in rE.points3D.values()])
        for t in (0, 1):
            X, Y, ns, td = EK.punkte(rE, R[t], mit_tiefe=True)
            if len(ns) < EK.MIN_BILDER_TEIL: continue
            kam = EK.kamerazentren(rE, R[t], ns)
            for weg in ("punkte", "reproj", "via_points", "proj_centers"):
                t0 = time.time(); Mf = None; info = {}
                if weg == "reproj": Mf, info = EK.reproj_sim3(rE, R[t])
                elif weg == "via_points":
                    try: s = pycolmap.align_reconstructions_via_points(rE, R[t])
                    except Exception as ex: s = None; info = dict(grund=f"via_points: {type(ex).__name__} {str(ex)[:80]}")   # Eck-Bilder ausserhalb des Teils -> IndexError
                    Mf = None if s is None else np.r_[np.asarray(s.matrix()), [[0, 0, 0, 1]]]
                elif weg == "proj_centers":                                          # Schwelle 2 % der Median-Tiefe im Teilrahmen (wie SCHWELLE_REL) - ANNAHME fuer die Probe
                    sg = EK.sim3_meter(kam[0], kam[1], schwelle_m=float("inf"), min_anteil=0.0); s_ = float(np.cbrt(np.linalg.det(sg["M"][:3, :3]))) if sg else 1.0
                    s = pycolmap.align_reconstructions_via_proj_centers(rE, R[t], max_proj_center_error=EK.SCHWELLE_REL * s_ * float(np.median(td)))
                    Mf = None if s is None else np.r_[np.asarray(s.matrix()), [[0, 0, 0, 1]]]
                if weg != "punkte" and Mf is None: pr, ok, g = dict(), False, info.get("grund", "keine Sim3")
                else: _, pr, ok, g = EK.kopplung_pruefen(X, Y, ausd, at[t], tiefe=td, kameras=kam, M_fest=Mf)
                dt = time.time() - t0
                if weg == "reproj" and Mf is not None: pr["reproj"] = dict(info, **EK.reproj_beobachtungen(Mf, rE, R[t], ns))
                z = dict(teile=ts, eck=os.path.relpath(m, D), teil=t, weg=weg, ok=ok, grund=g, laufzeit_s=round(dt, 3), bilder=len(ns), **pr); erg.append(z)
                print(f"  {os.path.relpath(m, D):34s} T{t} {weg:12s} ok={int(ok)} ant={pr.get('anteil')} rest={pr.get('rest_rel')} hael={pr.get('massstab_haelften_rel')}"
                      f" kam={pr.get('kameras_rel')} heb={pr.get('hebel')} n={len(ns)} {dt:.2f}s {(pr.get('reproj') or {}).get('beobachtungen_stimmig', '')} {g[:60]}")
json.dump(erg, open(aus, "w"), indent=1, default=str); print("->", aus)
# Verdrahtung wie in zwischenmodell(): Varianten sift / teilkameras (Punkt-Weg) + reproj_* auf den passenden Paaren (Eckmodell mit den Kameras genau dieser Teile)
for ts, st in (("r_teil", "stufe_r"), ("teil", "stufe_neu")):
    R = {t: pycolmap.Reconstruction(f"{D}/{ts}{t}") for t in (0, 1)}; at = {t: EK.ausdehnung([p.xyz for p in R[t].points3D.values()]) for t in R}
    for t in R: EK.NAMEN[t] = {im.name for im in R[t].images.values() if im.has_pose}
    vs = {}
    for v, ordner in (("sift", "zwischen0_s20"), ("teilkameras", "zwischen0tk_s20")):
        m = f"{D}/{st}/{ordner}/1"; _, gut, alle = EK.koppeln(m, [0, 1], R, None, at); vs[v] = dict(modell=m, teile=[0, 1], _gut=gut, kopplungen=alle)
        sm = f"{D}/{st}/{ordner.replace('_s20', '_s15')}/1"
        if os.path.isdir(sm): vs[v]["sensitivitaet"] = dict(schwelle=15, modell=sm)
    for b in list(vs): vs["reproj_" + b] = EK.reproj_variante(vs[b], dict(teile=[0, 1]), R, at, b)
    gj = {v: z["_gut"] for v, z in vs.items()}; w = EK.variante_waehlen(gj)
    print(ts, st, "GEWAEHLT", w, "|", EK.wahl_grund(gj, w))
    for v, z in vs.items(): print("  ", v, {t: k.get("grund")[:50] for t, k in z["kopplungen"].items()}, "sens", (z.get("sensitivitaet") or {}).get("vergleich"), z.get("laufzeit_s"))
