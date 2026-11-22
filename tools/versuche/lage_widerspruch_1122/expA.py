import sys, time; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import lod2fit as LF
sys.path.insert(0, S + "wt/tools")
import wand_dicke_tor as WD
gp = set(json.load(open(S + "obj22/audit/kamera_plausibel.json"))["ausschliessen"])
ZIEL = LF.L["ziel"]


def obs_fehler(rec):
    return rec.compute_mean_reprojection_error(), rec.compute_num_observations()


def ba(rec, frei):
    o = pycolmap.BundleAdjustmentOptions(); o.refine_focal_length = frei; o.refine_extra_params = frei; o.refine_principal_point = False
    o.print_summary = False
    try: o.ceres.solver_options.max_num_iterations = 100; o.ceres.solver_options.num_threads = 8
    except Exception as ex: print("ceres-opt", ex)
    pycolmap.bundle_adjustment(rec, o)


def entfernen(rec, namen):
    k = 0
    for im in list(rec.images.values()):
        if stamm(im.name) in namen and im.has_pose: rec.deregister_frame(im.frame_id); k += 1
    return k


def punkte_obj(rec, abb):
    P = np.array([abb(p.xyz) for p in rec.points3D.values() if p.track.length() >= 3 and p.error < 2.0]); return P


def messen(name, rec, ref_z, abb_ref):
    """rec im eigenen Rahmen; Sim3 auf die Referenz-Kamerazentren (urspruengliches Teilmodell) -> dann Abbildung in den 1122-Objektrahmen."""
    Z = zentren(rec); nm = [n for n in Z if n in ref_z and n not in gp]
    a = np.array([Z[n] for n in nm]); b = np.array([ref_z[n] for n in nm])
    s, R, t, _ = robust_sim3(a, b, q=90); res = np.linalg.norm(a @ R.T * s + t - b, axis=1)
    abb = lambda X: abb_ref(np.asarray(X) @ R.T * s + t)
    C = {n: abb(Z[n]) for n in Z}
    ref_obj = {n: abb_ref(ref_z[n]) for n in nm}
    verf = np.array([np.linalg.norm(C[n] - ref_obj[n]) for n in nm])
    g = gps_fit({n: C[n] for n in C if n not in gp})
    P = punkte_obj(rec, abb); w = (P[:, 2] > 1.5) & (P[:, 2] < 9) & (np.hypot(P[:, 0] - LF.C[0], P[:, 1] - LF.C[1]) < 40); Q = P[w, :2]
    b_ = LF.suche(Q, dreh=np.arange(-16, 16.1, 1.0), mass=np.arange(0.84, 1.40, 0.02)); th, sc, tt = LF.fein(Q, b_[0][1], b_[0][2], b_[0][3])
    kan = [k for gg in ZIEL for k in WD.kanten_messen(gg, {"t": P}, min_punkte=50)]
    wd = "; ".join(f"{k['laenge_m']:.0f}m:" + (f"Lage {k['teile']['t'].get('lage_m')} Dicke {k['teile']['t'].get('dicke_m')}" if 'lage_m' in k['teile']['t'] else "k.U.") for k in kan)
    me, no = obs_fehler(rec)
    print(f"  [{name}] Bilder {rec.num_reg_images()} Beob {no} Reproj {me:.3f} px | Verformung gg. Original (Kameras, m): median {np.median(verf):.3f} p90 {np.percentile(verf,90):.3f} max {verf.max():.2f}")
    print(f"     GPS: {kurz(g)}")
    print(f"     LoD2 frei: Drehung {th:+.1f} Massstab x{sc:.3f} Anteil<0.3 {LF.anteil(LF.trafo(Q, th, sc, tt)):.3f} (jetzt {LF.anteil(Q):.3f})"
          + (f" | Widerspruch GPS-LoD2: {g['dreh']-th:+.1f} Grad, x{g['s']/sc:.3f}" if 'dreh' in g else ""))
    print(f"     Wanddicke (Sparse, je Kante): {wd}")
    return dict(reproj=me, verf_med=float(np.median(verf)), gps=({k: v for k, v in g.items() if not k.startswith('_') and k != 'namen'}), lod2=(th, sc), wd=kan)


ERG = {}
for teil, pfad, abb0 in [("teil0", B22 + "seiten_modelle/teil0_b/0", sfm_zu_obj),
                         ("teil1", B22 + "seiten_modelle/teil1_b/0", lambda X: sfm_zu_obj(np.asarray(X) @ M1[:3, :3].T + M1[:3, 3]))]:
    print("=====", teil); t0 = time.time()
    orig = pycolmap.Reconstruction(pfad); ref_z = zentren(orig)
    schlecht = {n for n in ref_z if n in gp}; print("  tiefe Kameras im Teil:", len(schlecht), "von", len(ref_z))
    ERG[teil] = {"original": messen("original", orig, ref_z, abb0)}
    for var, rem, frei in [("BA fest, alle (Kontrolle)", False, False), ("BA fest, ohne tiefe", True, False), ("BA frei, ohne tiefe", True, True)]:
        r = pycolmap.Reconstruction(pfad)
        if rem: print("  entfernt", entfernen(r, schlecht))
        ba(r, frei); ERG[teil][var] = messen(var, r, ref_z, abb0); print(f"     ({time.time()-t0:.0f} s)")
json.dump(ERG, open(S + "e/expA.json", "w"), default=str, indent=1)
