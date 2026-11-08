#!/usr/bin/env python3
"""teilmodell_sim3.py - Bildserie, die nicht ans Referenznetz anschliesst (Insel), als eigenes SfM-Teilmodell rekonstruieren und per Sim3 ins Referenzsystem legen (Register DK, 2026-11-06).

Ablauf (CPU, pycolmap, keine GPU):
  lauf --db LG_DB --vorb vorbereitet.json --ref ORDNER_REGISTRIERUNG (registrierung.json + sparse_handy/0) --serie l --nachbarn d k
       --kameras kamera_profil.json --zoom zoom_verdacht.json --hyp normal|zoom|frei --aus ZIEL
     1. Teil-Datenbank: Bilder der Serie + in der Referenz REGISTRIERTE Nachbarbilder (Anker); Matches/Geometrien nur dieser Bilder; Kameras je Gruppe fest
        (Hypothese 'normal'/'zoom' = Zoomklasse der Serie; 'frei' = Brennweite+Verzeichnung im Buendel frei, nur Serie ohne Anker = Diagnose)
     2. incremental_mapping (feste Intrinsiken), Modell mit den meisten Serienbildern
     3. Sim3 (robust, LMedS ohne feste Schwelle) von Teilmodell-Zentren auf Referenz-Zentren der Anker; Rotationen der Anker als Gegenprobe
     4. Kennzahlen: Reprojektionsfehler, Sim3-Restfehler in m (Leave-one-out), Punktabgleich (gleiche Keypoints Anker-Bild: Teilmodell-3D-Punkt vs Referenz-3D-Punkt)
Hinweis: Anker-Posen gelten (Referenz), das Teilmodell wird ihnen angepasst; Anker haben aber eigene Posenunsicherheit (Register DF).
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/teilmodell_sim3.py lauf ...
Lizenz: nur pycolmap/COLMAP (BSD-3), numpy.
"""
import sys, os, json, argparse, shutil, sqlite3, time
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PID = 2147483647


# ---------------------------------------------------------------- reine Mathematik (testbar)
def umeyama(A, B, mit_skala=True):
    """B ~ s R A + t (kleinste Quadrate, Umeyama 1991). A,B: (n,3). Rueckgabe s,R,t."""
    A = np.asarray(A, float); B = np.asarray(B, float)
    ma, mb = A.mean(0), B.mean(0); Ac, Bc = A - ma, B - mb
    U, S, Vt = np.linalg.svd(Bc.T @ Ac / len(A))
    d = np.ones(3); d[2] = np.sign(np.linalg.det(U) * np.linalg.det(Vt)) or 1.0
    R = U @ np.diag(d) @ Vt
    va = (Ac ** 2).sum() / len(A)
    s = float((S * d).sum() / va) if mit_skala and va > 0 else 1.0
    return s, R, mb - s * R @ ma


def anwenden(s, R, t, P):
    return s * (np.asarray(P, float) @ R.T) + t


def sim3_robust(A, B, versuche=3000, seed=0):
    """Robuste Sim3 ohne feste Schwelle: LMedS ueber zufaellige Tripel (Median der Rest-Quadrate), Ausreisser dann aus dem eigenen MAD-Mass
    (|r| < 2,5 * 1,4826 * (1+5/(n-3)) * sqrt(med r^2), Rousseeuw/Leroy), Nachrechnung mit allen Inliern. Rueckgabe dict(s,R,t,inlier,res,n)."""
    A = np.asarray(A, float); B = np.asarray(B, float); n = len(A)
    if n < 3: raise ValueError("mindestens 3 Punkte")
    rng = np.random.default_rng(seed); best = None
    tripel = [tuple(rng.choice(n, 3, replace=False)) for _ in range(min(versuche, 20000))] if n > 3 else [(0, 1, 2)]
    for tr in tripel:
        idx = list(tr)
        try: s, R, t = umeyama(A[idx], B[idx])
        except np.linalg.LinAlgError: continue
        if not np.isfinite(s) or s <= 0: continue
        r = np.linalg.norm(anwenden(s, R, t, A) - B, axis=1); m = float(np.median(r ** 2))
        if best is None or m < best[0]: best = (m, s, R, t)
    m, s, R, t = best
    s0 = 1.4826 * (1 + 5.0 / max(n - 3, 1)) * np.sqrt(m)
    r = np.linalg.norm(anwenden(s, R, t, A) - B, axis=1); inl = r <= 2.5 * s0 if s0 > 0 else r <= r.min() + 1e-12
    if inl.sum() >= 3:
        s, R, t = umeyama(A[inl], B[inl]); r = np.linalg.norm(anwenden(s, R, t, A) - B, axis=1)
    return dict(s=s, R=R, t=t, inlier=inl, res=r, n=n)


def rotation_mittel(Rs, Rr):
    """Welt-Rotation R (Referenz = s R Teil + t) aus Kamerarotationen: cam_from_world_ref = cam_from_world_teil * R^T  =>  R = Rr_i^T Rs_i (Chordal-Mittel). Rueckgabe R, Streuwinkel je Bild (Grad)."""
    M = [np.asarray(r).T @ np.asarray(s) for s, r in zip(Rs, Rr)]
    U, _, Vt = np.linalg.svd(sum(M)); d = np.sign(np.linalg.det(U @ Vt)) or 1.0
    R = U @ np.diag([1, 1, d]) @ Vt
    ang = [float(np.degrees(np.arccos(np.clip((np.trace(R.T @ m) - 1) / 2, -1, 1)))) for m in M]
    return R, ang


def winkel(R1, R2):
    return float(np.degrees(np.arccos(np.clip((np.trace(R1.T @ R2) - 1) / 2, -1, 1))))


def skala_aus_zentren(A, B, R):
    """s,t bei vorgegebenem R (kleinste Quadrate): B ~ s R A + t."""
    A = np.asarray(A, float); B = np.asarray(B, float); X = A @ R.T; xm, bm = X.mean(0), B.mean(0)
    Xc, Bc = X - xm, B - bm; s = float((Xc * Bc).sum() / (Xc ** 2).sum()); return s, bm - s * xm


def entartung(A):
    """Hauptachsen der Ankerzentren: Verhaeltnisse der Singulaerwerte (klein = nahezu linear/eben -> Rotation/Skala aus Zentren schwach bestimmt)."""
    S = np.linalg.svd(np.asarray(A, float) - np.mean(A, 0), compute_uv=False)
    return dict(sv=[float(x) for x in S], mittel_zu_gross=float(S[1] / S[0]) if S[0] > 0 else 0.0, klein_zu_gross=float(S[2] / S[0]) if S[0] > 0 else 0.0)


def rot_aus_quat_wxyz(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------- Teil-Datenbank
def teil_db(src, dst, behalte, gruppen_pro_bild, kam, neu_verifizieren=False):
    """Kopie von src nach dst, nur Bilder 'behalte' (Namen); Kameras je Gruppe (kam: {gruppe: dict(W,H,params)}) fest eingetragen."""
    from zusatzfotos_registrieren import db_kameras_schreiben
    shutil.copyfile(src, dst)
    con = sqlite3.connect(dst)
    name2id = {n: i for i, n in con.execute("select image_id,name from images")}
    keep = sorted(name2id[n] for n in behalte); kset = set(keep)
    con.execute("create temp table k(i integer primary key)"); con.executemany("insert into k values (?)", [(i,) for i in keep])
    for tab in ("keypoints", "descriptors"): con.execute(f"delete from {tab} where image_id not in (select i from k)")
    for tab in ("matches", "two_view_geometries"):
        con.execute(f"delete from {tab} where (pair_id/{PID}) not in (select i from k) or (pair_id%{PID}) not in (select i from k)")
    con.execute("delete from pose_priors")
    con.execute("delete from frame_data where data_id not in (select i from k)"); con.execute("delete from frames where frame_id not in (select frame_id from frame_data)")
    con.execute("delete from images where image_id not in (select i from k)")
    con.execute("update images set camera_id=-1"); con.execute("delete from rig_sensors"); con.execute("delete from rigs"); con.execute("delete from cameras")
    con.commit()
    cams = {}
    for k_, (g, e) in enumerate(sorted(kam.items()), start=1):
        cams[g] = SimpleNamespace(camera_id=k_, params=e["params"], width=e["W"], height=e["H"])
    # leere Rigs/Frames werden von db_kameras_schreiben angelegt bzw. angepasst
    for g, c_ in cams.items():
        con.execute("insert or replace into cameras(camera_id,model,width,height,params,prior_focal_length) values (?,?,?,?,?,1)", (c_.camera_id, 2, c_.width, c_.height, np.asarray(c_.params, "<f8").tobytes()))
        con.execute("insert or replace into rigs(rig_id,ref_sensor_id,ref_sensor_type) values (?,?,0)", (c_.camera_id, c_.camera_id))
    con.commit(); con.close()
    GK = {g: dict(namen=[n for n in behalte if gruppen_pro_bild[n] == g]) for g in cams}
    db_kameras_schreiben(dst, cams, GK, name2id)
    con = sqlite3.connect(dst); con.execute("vacuum"); con.close()
    if neu_verifizieren:
        import pycolmap
        # Geometrie-Verifikation der LightGlue-Rohmatches NEU mit den hier festen Kameras (die Altgeometrie ist mit Platzhalter-Intrinsiken berechnet -> E-Test unzuverlaessig, viele Paare 'uncalibrated')
        con = sqlite3.connect(dst); id2n = {i: n for n, i in name2id.items()}
        pairs = [(id2n[p // PID], id2n[p % PID]) for p, r in con.execute("select pair_id,rows from matches") if r > 0]
        con.execute("delete from two_view_geometries"); con.commit(); con.close()
        pf = dst + ".paare.txt"; open(pf, "w").write("\n".join(f"{x} {y}" for x, y in pairs) + "\n")
        o = pycolmap.TwoViewGeometryOptions(); o.compute_relative_pose = True; o.detect_watermark = False
        pycolmap.verify_matches(dst, pf, o)
    return name2id


# ---------------------------------------------------------------- Lauf
def lauf(a):
    import pycolmap
    from zusatzfotos_registrieren import kamera_gruppen
    t0 = time.time(); os.makedirs(a.aus, exist_ok=True)
    V = json.load(open(a.vorb))["bilder"]; R = json.load(open(os.path.join(a.ref, "registrierung.json")))
    serie = sorted(n for n in V if n.split("_")[1] == a.serie)
    anker = sorted(n for n, e in R["bilder"].items() if e.get("status") == "registriert" and n.split("_")[1] in a.nachbarn) if a.nachbarn else []
    params = json.load(open(a.kameras)); zoom = json.load(open(a.zoom)) if a.zoom else {"bilder": {}}
    zoom = {"bilder": dict(zoom.get("bilder", {}))}
    if a.hyp in ("normal", "zoom", "frei", "eigen"):
        for n in serie:
            zoom["bilder"][n] = {"klasse": "gezoomt" if a.hyp in ("zoom", "eigen") else "normal"}
    if a.hyp == "eigen":       # eigene Kamera der Serie: Gruppe 'hoch_zoom' nur fuer die Serie ueberschreiben (kein Anker darf darin liegen)
        import copy
        s_ = V[serie[0]]["skala"]; params = copy.deepcopy(params)
        assert not any(n.split("_")[1] != a.serie and zoom["bilder"].get(n, {}).get("klasse") == "gezoomt" for n in anker), "Anker in Zoomgruppe: eigene Kamera wuerde sie veraendern"
        for g in ("hoch_zoom", "quer_zoom"): params["kameras"][g] = dict(params["kameras"][g], f_orig=a.f_px / s_, k1=a.k1)
    namen = serie + anker; sub = {n: V[n] for n in namen}
    GK, zuord = kamera_gruppen(sub, zoom, params); gpb = {n: zuord[n][0] for n in namen}
    hd = os.path.join(a.aus, a.hyp + a.marke); shutil.rmtree(hd, ignore_errors=True); os.makedirs(hd)
    dbp = os.path.join(hd, "db.db")
    name2id = teil_db(a.db, dbp, namen, gpb, {g: dict(W=e["W"], H=e["H"], params=e["params"]) for g, e in GK.items()}, neu_verifizieren=a.neu_verifizieren)
    print(f"[{a.hyp}] Teil-DB: {len(serie)} Serienbilder + {len(anker)} Anker, Gruppen { {g: (len(e['namen']), [round(x, 3) for x in e['params']]) for g, e in GK.items()} }", flush=True)
    o = pycolmap.IncrementalPipelineOptions(); o.num_threads = a.threads; o.extract_colors = False; o.multiple_models = True; o.max_num_models = 10
    frei = a.hyp == "frei"
    o.ba_refine_focal_length = frei; o.ba_refine_extra_params = frei; o.ba_refine_principal_point = False
    o.mapper.abs_pose_refine_focal_length = frei; o.mapper.abs_pose_refine_extra_params = frei
    o.mapper.num_threads = a.threads; o.random_seed = a.seed
    o.min_model_size = a.min_modell
    if a.init_winkel is not None: o.mapper.init_min_tri_angle = a.init_winkel
    od = os.path.join(hd, "mapper"); os.makedirs(od)
    recs = pycolmap.incremental_mapping(dbp, os.path.join(a.ref, "bilder"), od, o)
    print(f"[{a.hyp}] Mapper fertig {time.time()-t0:.0f} s, Modelle: " + ", ".join(f"{k}:{r.num_reg_images()}" for k, r in recs.items()), flush=True)
    if not recs: json.dump(dict(hyp=a.hyp, ergebnis="kein Modell"), open(os.path.join(hd, "ergebnis.json"), "w"), indent=1); return
    id2name = {i: n for n, i in name2id.items()}; sset = set(serie)
    def n_serie(r): return sum(1 for i in r.images.values() if i.has_pose and i.name in sset)
    def auswerten(KK):
        k_best = KK; rec = recs[KK]
        reg_serie = sorted(i.name for i in rec.images.values() if i.has_pose and i.name in sset); reg_anker = sorted(i.name for i in rec.images.values() if i.has_pose and i.name not in sset)

        def fehler_je_bild(rec, namen_):
            out = {}
            for i in rec.images.values():
                if not i.has_pose or i.name not in namen_: continue
                e = []
                for p in i.points2D:
                    if p.has_point3D():
                        q = i.project_point(rec.points3D[p.point3D_id].xyz)
                        if q is not None: e.append(float(np.linalg.norm(np.asarray(q) - p.xy)))
                out[i.name] = dict(n=len(e), mittel=float(np.mean(e)) if e else None, median=float(np.median(e)) if e else None)
            return out
        fs = fehler_je_bild(rec, sset); alle = [v["median"] for v in fs.values() if v["median"] is not None]
        kam_out = {int(c): dict(f=float(cc.params[0]), k1=float(cc.params[3]) if len(cc.params) > 3 else None) for c, cc in rec.cameras.items()}
        erg = dict(hyp=a.hyp, modell=int(k_best), n_modelle=len(recs), registriert_serie=len(reg_serie), von_serie=len(serie), registriert_anker=len(reg_anker), von_anker=len(anker),
                   serien_namen_nicht_registriert=sorted(sset - set(reg_serie)), n_punkte=len(rec.points3D), reproj_mittel_modell_px=float(rec.compute_mean_reprojection_error()),
                   reproj_serie_median_der_bildmediane_px=float(np.median(alle)) if alle else None, reproj_serie_je_bild=fs, kameras_modell=kam_out, laufzeit_s=time.time() - t0)
        # --- Sim3 gegen Anker
        refrec = pycolmap.Reconstruction(os.path.join(a.ref, "sparse_handy", "0"))
        r_by = {i.name: i for i in refrec.images.values() if i.has_pose}
        gem = [n for n in reg_anker if n in r_by]
        erg["gemeinsame_anker"] = len(gem)
        if len(gem) >= 3:
            s_by = {i.name: i for i in rec.images.values() if i.has_pose}
            A = np.array([s_by[n].projection_center() for n in gem]); B = np.array([r_by[n].projection_center() for n in gem])
            Rs = [s_by[n].cam_from_world().rotation.matrix() for n in gem]; Rr = [r_by[n].cam_from_world().rotation.matrix() for n in gem]
            Rm, ang = rotation_mittel(Rs, Rr)
            sim = sim3_robust(A, B)
            sk, tk = skala_aus_zentren(A, B, Rm)
            res_rot = np.linalg.norm(anwenden(sk, Rm, tk, A) - B, axis=1)
            # Leave-one-out auf den Zentren (nur Inlier-Anker)
            loo = []; ii = np.where(sim["inlier"])[0]
            for j in ii:       # Leave-one-out nur fuer Inlier-Anker (Ausreisser-Anker sind schon als Fehlpose erkannt), Refit ohne j
                m = np.ones(len(gem), bool); m[j] = False
                if m.sum() >= 4:
                    r_ = sim3_robust(A[m], B[m], versuche=500); loo.append(float(np.linalg.norm(anwenden(r_["s"], r_["R"], r_["t"], A[j:j + 1]) - B[j])))
            # Punktabgleich: gleiche Keypoints der Anker-Bilder
            dp = []
            for n in gem:
                for p, q in zip(s_by[n].points2D, r_by[n].points2D):
                    if p.has_point3D() and q.has_point3D(): dp.append((rec.points3D[p.point3D_id].xyz, refrec.points3D[q.point3D_id].xyz))
            pk = {}
            if len(dp) >= 10:
                PA = np.array([x[0] for x in dp]); PB = np.array([x[1] for x in dp])
                pr = np.linalg.norm(anwenden(sim["s"], sim["R"], sim["t"], PA) - PB, axis=1)
                pk = dict(n=len(dp), median_m=float(np.median(pr)), q90_m=float(np.quantile(pr, 0.9)), mad_m=float(1.4826 * np.median(np.abs(pr - np.median(pr)))))
                sp = sim3_robust(PA, PB, versuche=1500); pk["unabhaengige_sim3_aus_punkten"] = dict(s=sp["s"], winkel_zu_zentren_sim3_grad=winkel(sp["R"], sim["R"]), restfehler_median_m=float(np.median(sp["res"])))
            erg["sim3"] = dict(s=float(sim["s"]), R=sim["R"].tolist(), t=sim["t"].tolist(), n_anker=len(gem), n_inlier=int(sim["inlier"].sum()), inlier_namen=[n for n, k in zip(gem, sim["inlier"]) if k],
                               rest_median_m=float(np.median(sim["res"])), rest_max_inlier_m=float(sim["res"][sim["inlier"]].max()), rest_je_anker_m={n: float(r) for n, r in zip(gem, sim["res"])},
                               loo_median_m=float(np.median(loo)) if loo else None, loo_max_m=float(max(loo)) if loo else None,
                               rotationsvariante=dict(s=sk, winkel_zu_zentren_sim3_grad=winkel(Rm, sim["R"]), rotationsstreuung_grad_median=float(np.median(ang)), rotationsstreuung_grad_q90=float(np.quantile(ang, 0.9)), rest_median_m=float(np.median(res_rot))),
                               entartung_ankerzentren=entartung(A), punktabgleich=pk, anker_ausdehnung_m=float(np.linalg.norm(B.max(0) - B.min(0))))
            # transformiertes Modell + Serienposen
            import copy
            rec2 = pycolmap.Reconstruction(rec); S = pycolmap.Sim3d(sim["s"], pycolmap.Rotation3d(sim["R"]), sim["t"]); rec2.transform(S)
            os.makedirs(os.path.join(hd, f"sparse_ref_m{KK}"), exist_ok=True); rec2.write(os.path.join(hd, f"sparse_ref_m{KK}"))
            poses = {}
            for i in rec2.images.values():
                if i.has_pose and i.name in sset:
                    c2w = i.cam_from_world(); poses[i.name] = dict(zentrum=[float(x) for x in i.projection_center()], cam_from_world_quat_xyzw=[float(x) for x in c2w.rotation.quat], cam_from_world_t=[float(x) for x in c2w.translation])
            erg["serie_posen_im_referenzsystem"] = poses
        json.dump(erg, open(os.path.join(hd, f"ergebnis_m{KK}.json"), "w"), indent=1)
        kurz = {k: erg.get(k) for k in ("hyp", "registriert_serie", "von_serie", "registriert_anker", "gemeinsame_anker", "n_punkte", "reproj_mittel_modell_px", "reproj_serie_median_der_bildmediane_px")}
        print(f"  Modell {KK}:", json.dumps(kurz), flush=True)
        if "sim3" in erg: print("sim3:", {k: erg["sim3"][k] for k in ("s", "n_anker", "n_inlier", "rest_median_m", "rest_max_inlier_m", "loo_median_m", "anker_ausdehnung_m")}, "entartung", erg["sim3"]["entartung_ankerzentren"], flush=True)

    for KK in sorted(recs, key=lambda k: -n_serie(recs[k])):
        auswerten(KK)
    best = sorted(recs, key=lambda k: -n_serie(recs[k]))[0]; shutil.copyfile(os.path.join(hd, f"ergebnis_m{best}.json"), os.path.join(hd, "ergebnis.json"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("lauf")
    for k in ("--db", "--vorb", "--ref", "--kameras", "--aus"): p.add_argument(k, required=True)
    p.add_argument("--zoom"); p.add_argument("--serie", required=True); p.add_argument("--nachbarn", nargs="*", default=[]); p.add_argument("--hyp", choices=["normal", "zoom", "frei", "eigen"], required=True); p.add_argument("--threads", type=int, default=28); p.add_argument("--init-winkel", type=float, help="Mapper init_min_tri_angle in Grad (Standard COLMAP 16); kleine Basis an ebener Fassade"); p.add_argument("--min-modell", type=int, default=3, help="kleinste Modellgroesse (Bilder); COLMAP-Standard 10 verwirft Teilgruppen der Insel"); p.add_argument("--f-px", type=float, help="hyp eigen: Brennweite der Serie in Bildpixeln (aus der freien Schaetzung)"); p.add_argument("--k1", type=float, default=0.0); p.add_argument("--seed", type=int, default=0); p.add_argument("--neu-verifizieren", action="store_true"); p.add_argument("--marke", default="", help="Zusatz im Ergebnisordner")
    a = ap.parse_args(argv)
    if a.cmd == "lauf": lauf(a)


if __name__ == "__main__":
    main()
