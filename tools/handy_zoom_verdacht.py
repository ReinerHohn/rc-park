#!/usr/bin/env python3
"""handy_zoom_verdacht.py - je Handybild f frei schaetzen (Profil ueber f, PnP bei festem f, robuste Kosten) und Bilder mit f deutlich ausserhalb
des Hauptclusters als 'gezoomt' kennzeichnen (EXIF zeigt Digital-/Tele-Zoom NICHT: bei allen 5,25 mm, 4000x3000).
f wird in Originalpixeln (f_orig = f_Bild / skala) gefuehrt, damit Quer-/Hochformat vergleichbar sind. Referenzpunkte aus sparse_buendel/0 (SIFT-DB)
und lg/ref_tri (LG-DB), Korrespondenzen aus verifizierten Matches (NICHT aus den PnP-Inliern der Registrierung).
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/handy_zoom_verdacht.py --aus JSON [--schwelle 0.05]
Grenze: Einzelbild-f ist bei ebenen Szenen mit f/Abstand gekoppelt und streut auch ohne Zoom um ca. +-8 %; deshalb Klassen nach Streuung der
ungezoomten Serien (a,b), nicht nach festem Prozentwert allein. Test: tools/test_handy_kalibrieren.py (reine Funktionen)."""
import sys, os, json, argparse, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handy_kalibrieren as hk


def f_profil(uv, X, W, H, cx, cy, grid):
    import pycolmap
    prof = []
    for f in grid:
        cam = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, f, W, H); cam.params = [f, cx, cy, 0.0]
        eo = pycolmap.AbsolutePoseEstimationOptions(); eo.estimate_focal_length = False; eo.ransac.max_error = 4.0; eo.ransac.random_seed = 0
        r = pycolmap.estimate_and_refine_absolute_pose(uv, X, cam, eo)
        if r is None:
            prof.append((f, np.inf, 0)); continue
        cw = r["cam_from_world"]; R = cw.rotation.matrix(); t = np.array(cw.translation)
        Xc = X @ R.T + t; z = Xc[:, 2]; u = f * Xc[:, :2] / z[:, None] + [cx, cy]
        e = np.linalg.norm(u - uv, axis=1); e[z <= 0] = 99
        prof.append((f, float(np.sum(np.minimum(e ** 2, 16))), int(r["num_inliers"])))
    return np.array(prof)


def klassifiziere(z_med, streu, schwelle, zoom_z=1.5):
    """z = f_orig / f_Haupt. Einzelbild-f streut ohne Zoom um 'streu' (log, aus Serien a,b gemessen).
    'normal': |z-1| <= max(schwelle, 2*streu); 'gezoomt': z >= zoom_z (oder <= 1/zoom_z) - klar ausserhalb der Streuung;
    dazwischen 'abweichend' (>5 %, aber im Rauschbereich des Einzelbild-f: NICHT als Zoom behaupten)."""
    d = abs(z_med - 1.0)
    if z_med >= zoom_z or z_med <= 1.0 / zoom_z:
        return "gezoomt"
    return "normal" if d <= max(schwelle, 2 * streu) else "abweichend"


def haupt_f(werte):
    """Hauptcluster: Median der Werte, die innerhalb +-25 % des Gesamtmedians der Werte < 1,6 x Minimum-Cluster liegen (iterativ, 2 Schritte)."""
    w = np.asarray(werte, float); m = np.median(w[w < 1.6 * np.quantile(w, .25)])
    for _ in range(2):
        m = np.median(w[(w > .75 * m) & (w < 1.25 * m)])
    return float(m)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--aus", required=True); ap.add_argument("--schwelle", type=float, default=0.05)
    ap.add_argument("--korr-pkl", help="Zwischenspeicher der Korrespondenzen (optional)")
    a = ap.parse_args(argv)
    V = json.load(open(hk.HANDY + "/vorbereitet.json"))["bilder"]; pv = json.load(open(hk.HANDY + "/pose_vertrauen.json"))["bilder"]
    namen = sorted(V); grid = np.exp(np.linspace(np.log(1800), np.log(24000), 80))     # f_orig
    je = {}
    for tag, db, ref in [("SIFT", hk.HANDY + "/db.db", hk.REF), ("LG", hk.HANDY + "/lg/db.db", hk.HANDY + "/lg/ref_tri")]:
        k = hk.korrespondenzen_sammeln(db, ref, namen, 2, 2.0)
        for n, v in k.items():
            W, H = V[n]["bild"]; sk = V[n]["skala"]; cx = W / 2; cy = H / (1 - hk.CROP_UNTEN) / 2
            P = f_profil(v["uv"], v["X"], W, H, cx, cy, grid * sk)
            c = P[:, 1]; i = int(np.argmin(c)); ok = c <= c[i] + 4 * 1.3 ** 2
            je.setdefault(n, {})[tag] = dict(f_orig=float(P[i, 0] / sk), f_lo=float(P[ok, 0].min() / sk), f_hi=float(P[ok, 0].max() / sk), n_korr=len(v["uv"]), inlier=int(P[i, 2]))
    fmed = {n: float(np.exp(np.mean([np.log(d["f_orig"]) for d in t.values()]))) for n, t in je.items()}
    f_haupt = haupt_f(list(fmed.values()))
    ref_streu = float(np.std([np.log(fmed[n] / f_haupt) for n in fmed if pv[n]["serie"] in ("a", "b") and abs(fmed[n] / f_haupt - 1) < 0.3]))
    out = dict(f_haupt_orig_px=f_haupt, streu_log_ungezoomt_ab=ref_streu, schwelle=a.schwelle, bilder={}, je_serie={}, hinweis="Einzelbild-f nur Hinweis; Gruppen-f siehe handy_kalibrieren.py mit_ref")
    for n, t in sorted(je.items()):
        z = fmed[n] / f_haupt; s = pv[n]["serie"]
        out["bilder"][n] = dict(serie=s, hochformat=V[n]["bild"][1] > V[n]["bild"][0], f_orig_SIFT=t.get("SIFT", {}).get("f_orig"), f_orig_LG=t.get("LG", {}).get("f_orig"),
                                z=z, klasse=klassifiziere(z, ref_streu, a.schwelle), inlier=max(d["inlier"] for d in t.values()), n_laeufe=len(t))
    for s in sorted({b["serie"] for b in out["bilder"].values()}):
        bb = [b for b in out["bilder"].values() if b["serie"] == s]
        out["je_serie"][s] = dict(n_bewertet=len(bb), n_im_foto_gesamt=sum(1 for n in V if pv[n]["serie"] == s), normal=sum(b["klasse"] == "normal" for b in bb),
                                  abweichend=sum(b["klasse"] == "abweichend" for b in bb), gezoomt=sum(b["klasse"] == "gezoomt" for b in bb),
                                  z_hist=np.histogram([b["z"] for b in bb], bins=[0, .8, .95, 1.05, 1.25, 1.5, 2, 3, 3.8, 5, 99])[0].tolist(), z_median=float(np.median([b["z"] for b in bb])))
    out["z_hist_bins"] = [0, .8, .95, 1.05, 1.25, 1.5, 2, 3, 3.8, 5, 99]
    out["nicht_bewertet"] = sorted(n for n in V if n not in je)
    json.dump(out, open(a.aus, "w"), indent=1)
    print(json.dumps(out["je_serie"], indent=0)); print("f_haupt", f_haupt, "streu", ref_streu, "nicht bewertet", len(out["nicht_bewertet"]))


# ---------------------------------------------------------------------------------------------------------------------------------
# v2 (Register DG): alle Bilder der Neuregistrierungen (Laeufe a_m, npq), zwei unabhaengige Schaetzer, Schwellen aus den Daten.
#  E1 = PnP-Profil ueber f (wie oben) gegen die Referenz-3D-Punkte.
#  E2 = Fundamentalmatrix-Selbstkalibrierung: je Bildpaar (neu x Referenzbild, Referenzkamera bekannt) F aus den verifizierten Matches (ohne 3D-Punkte, ohne
#       Posen), E(f) = F diag(f,f,1); f minimiert den Singulaerwert-Unterschied (s1-s2)/(s1+s2) (Hartley). Median ueber Partner. Schwach bei kleiner Basis.
#  Klassengrenzen: Zoomgrenze = geometrische Mitte der beiden Cluster (2-Means in log z), nur wenn Clusterabstand > Summe der Streuungen, sonst keine Zoomklasse;
#  'normal' = |log z| <= 2 * Streuung der Serien a,b; Bild ohne genug Korrespondenzen oder mit f-Intervall, das beide Cluster umfasst -> 'unbekannt'.
def zwei_means_log(lz):
    """2-Means in 1D (log z). Rueckgabe (c_lo, c_hi, s_lo, s_hi, n_lo, n_hi) oder None."""
    x = np.sort(np.asarray(lz, float))
    if len(x) < 6: return None
    best = None
    for k in range(2, len(x) - 1):
        a, b = x[:k], x[k:]; c = a.var() * len(a) + b.var() * len(b)
        if best is None or c < best[0]: best = (c, k)
    k = best[1]; a, b = x[:k], x[k:]
    return float(a.mean()), float(b.mean()), float(a.std()), float(b.std()), len(a), len(b)


def f_fmatrix(db, rec, name2id, nid, grid, cx, cy, f0, neu_partner=None, max_partner=14, min_inlier=60):
    """E2 (Bildpixel des NEUEN Bildes; grid in Bildpixeln). Partner: registrierte Referenzbilder (Kamera bekannt) und, falls neu_partner
    {Name: (f_bild, cx, cy)} gegeben, neue Bilder mit E1-Brennweite (dann abhaengig von deren E1-Schaetzung, als solche gezaehlt).
    F in mit f0 normierten Koordinaten (RANSAC-Schwelle 3 px / f0), E(f) = F diag(f/f0, f/f0, 1), Kriterium (s1-s2)/(s1+s2). Rueckgabe (fs, n_inlier, art)."""
    import cv2
    kp_n = db.read_keypoints(nid)[:, :2].astype(float); kand = []
    for im in rec.images.values():
        if not im.has_pose: continue
        rid = name2id.get(im.name)
        if rid is None: continue
        kand.append((rid, im, None))
    for nm_, (fb, cx_, cy_) in (neu_partner or {}).items():
        rid = name2id.get(nm_)
        if rid is not None and rid != nid: kand.append((rid, None, (fb, cx_, cy_)))
    liste = []
    for rid, im, par in kand:
        try: g = db.read_two_view_geometry(nid, rid) if nid < rid else db.read_two_view_geometry(rid, nid)
        except Exception: continue
        m = np.asarray(g.inlier_matches)
        if len(m) >= min_inlier: liste.append((len(m), rid, im, par, m if nid < rid else m[:, ::-1]))
    liste.sort(key=lambda x: -x[0]); fs = []; ni = []; art = []
    for nm, rid, im, par, m in liste[:max_partner]:
        kr = db.read_keypoints(rid)[:, :2].astype(float)
        if im is not None:
            cam = rec.cameras[im.camera_id]; u1 = np.array([cam.cam_from_img(p) for p in kr[m[:, 1]]], float); fr = float(cam.params[0])
        else:
            fb, cx_, cy_ = par; u1 = (kr[m[:, 1]] - [cx_, cy_]) / fb; fr = fb
        u2 = (kp_n[m[:, 0]] - [cx, cy]) / f0; ok = np.isfinite(u1).all(1)
        if ok.sum() < min_inlier: continue
        F, mask = cv2.findFundamentalMat(u2[ok], u1[ok], cv2.FM_RANSAC, 3.0 / fr, 0.999)
        if F is None or F.shape != (3, 3) or mask.sum() < min_inlier: continue
        cost = np.array([(lambda sv: (sv[0] - sv[1]) / (sv[0] + sv[1]))(np.linalg.svd(F @ np.diag([f / f0, f / f0, 1.0]), compute_uv=False)) for f in grid])
        i = int(np.argmin(cost))
        if i in (0, len(grid) - 1): continue
        fs.append(float(grid[i])); ni.append(int(mask.sum())); art.append("ref" if im is not None else "neu")
    return fs, ni, art


class DbLeser:
    """Schreibgeschuetzter SQLite-Leser (immutable, keine Sperre): gleiche Schnittstelle wie pycolmap.Database fuer read_keypoints /
    read_two_view_geometry(...).inlier_matches. Grund: 20 pycolmap-Datenbankobjekte auf derselben Datei -> 'database is locked' / SIGBUS."""
    def __init__(self, pfad):
        import sqlite3
        self.con = sqlite3.connect(f"file:{pfad}?mode=ro&immutable=1", uri=True)
    def read_keypoints(self, iid):
        r = self.con.execute("select rows,cols,data from keypoints where image_id=?", (iid,)).fetchone()
        return np.frombuffer(r[2], np.float32).reshape(r[0], r[1]) if r and r[0] else np.zeros((0, 2), np.float32)
    def read_two_view_geometry(self, a, b):
        r = self.con.execute("select rows,cols,data from two_view_geometries where pair_id=?", (a * 2147483647 + b,)).fetchone()
        class G: pass
        g = G(); g.inlier_matches = np.frombuffer(r[2], np.uint32).reshape(r[0], r[1]) if r and r[0] else np.zeros((0, 2), np.uint32)
        return g
    def close(self): self.con.close()


_G = {}
def _init(db_pfad, ref_pfad, vorb, sperre=None):
    import pycolmap, sqlite3
    _G["rec"] = pycolmap.Reconstruction(ref_pfad); _G["V"] = vorb; _G["db"] = DbLeser(db_pfad)
    con = sqlite3.connect(f"file:{db_pfad}?mode=ro&immutable=1", uri=True); _G["n2id"] = {n: i for i, n in con.execute("select image_id,name from images")}; con.close()
    _G["db_pfad"] = db_pfad; _G["ref_pfad"] = ref_pfad


def _e1(args):
    n, grid = args; V = _G["V"]; W, H = V[n]["bild"]; sk = V[n]["skala"]; cx = W / 2; cy = H / (1 - hk.CROP_UNTEN) / 2
    import zusatzfotos_registrieren as zr       # gleiche Auswahl wie hk.korrespondenzen_sammeln (Referenzpunkte: Track >= 2, Fehler <= 2 px, >= 30 Korrespondenzen)
    rec = _G["rec"]; k = {}
    if n in _G["n2id"]:
        idx, xy, pid, je = zr.korrespondenzen(_G["db"], rec, _G["n2id"], _G["n2id"][n])
        keep = [i for i, p in enumerate(pid) if rec.points3D[p].track.length() >= 2 and rec.points3D[p].error <= 2.0]
        if len(keep) >= 30: k[n] = dict(uv=np.asarray(xy)[keep], X=np.array([rec.points3D[pid[i]].xyz for i in keep]))
    r = dict(n_korr=0, f1=None, f1_lo=None, f1_hi=None, inlier=0)
    if n in k:
        P = f_profil(k[n]["uv"], k[n]["X"], W, H, cx, cy, grid * sk); c = P[:, 1]; i = int(np.argmin(c)); ok = c <= c[i] + 4 * 1.3 ** 2
        r.update(n_korr=int(len(k[n]["uv"])), f1=float(P[i, 0] / sk), f1_lo=float(P[ok, 0].min() / sk), f1_hi=float(P[ok, 0].max() / sk), inlier=int(P[i, 2]))
    return n, r


def _e2(args):
    n, grid, f0, neu_partner = args; V = _G["V"]; W, H = V[n]["bild"]; sk = V[n]["skala"]; cx = W / 2; cy = H / (1 - hk.CROP_UNTEN) / 2
    if n not in _G["n2id"]: return n, {}
    try:
        fs, ni, art = f_fmatrix(_G["db"], _G["rec"], _G["n2id"], _G["n2id"][n], grid * sk, cx, cy, f0 * sk, neu_partner)
    except Exception as e:
        return n, dict(f2_fehler=repr(e)[:120])
    if not fs: return n, {}
    fr = [f / sk for f, a_ in zip(fs, art) if a_ == "ref"]; fn = [f / sk for f, a_ in zip(fs, art) if a_ == "neu"]
    sel = fr if fr else fn      # Referenzpartner (Kamera bekannt) haben Vorrang; neue Partner nur wenn keine Referenz
    return n, dict(f2=float(np.median(sel)), f2_n_partner=len(sel), f2_partner_art="ref" if fr else "neu", f2_streu_log=float(np.std(np.log(sel))) if len(sel) > 1 else None,
                   f2_inlier_median=float(np.median(ni)), f2_alle_partner_median=float(np.median(fr + fn)))


def v2_lauf(name, ordner, db_pfad, ref_pfad, grid_orig, procs):
    import multiprocessing as mp
    V = json.load(open(os.path.join(ordner, "vorbereitet.json")))["bilder"]; namen = sorted(V); ctx = mp.get_context("fork")
    with ctx.Pool(procs, initializer=_init, initargs=(db_pfad, ref_pfad, V, ctx.Lock())) as pool:
        e1 = dict(pool.map(_e1, [(n, grid_orig) for n in namen], chunksize=1))
        res = {n: dict(lauf=name, serie=n.split("_")[1], hochformat=V[n]["bild"][1] > V[n]["bild"][0], f2=None, f2_n_partner=0, f2_streu_log=None, **e1[n]) for n in namen}
        bew = [v["f1"] for v in res.values() if v["f1"] and v["n_korr"] >= 30]
        f0 = haupt_f(bew) if len(bew) >= 8 else 2800.0
        neu_p = {}
        for n, v in res.items():
            if v["f1"] and v["n_korr"] >= 30 and v["inlier"] >= 30:
                sk = V[n]["skala"]; W, H = V[n]["bild"]; neu_p[n] = (v["f1"] * sk, W / 2, H / (1 - hk.CROP_UNTEN) / 2)
        for n, r in pool.map(_e2, [(n, grid_orig, f0, neu_p) for n in namen], chunksize=1): res[n].update(r)
    return res


def main_v2(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--v2", action="store_true"); ap.add_argument("--lauf", action="append", required=True, help="NAME=ORDNER(vorbereitet.json)=DB=REFSPARSE")
    ap.add_argument("--procs", type=int, default=os.cpu_count()); ap.add_argument("--aus", required=True); ap.add_argument("--alt", help="zoom_verdacht.json (Vergleich)"); a = ap.parse_args(argv)
    grid = np.exp(np.linspace(np.log(1800), np.log(24000), 100)); alle = {}
    for l in a.lauf:
        nm, o, d, r = l.split("="); alle.update({f"{nm}/{n}": v for n, v in v2_lauf(nm, o, d, r, grid, a.procs).items()}); print("fertig", nm, len(alle), flush=True)
    bew = [v for v in alle.values() if v["f1"] and v["n_korr"] >= 30]
    f_haupt = haupt_f([v["f1"] for v in bew]); streu = float(np.std([np.log(v["f1"] / f_haupt) for v in bew if v["serie"] in ("a", "b") and abs(v["f1"] / f_haupt - 1) < 0.3]))
    cl = zwei_means_log([np.log(v["f1"] / f_haupt) for v in bew]); zoom_grenze = None; c_lo = c_hi = None
    if cl and (cl[1] - cl[0]) > cl[2] + cl[3] and cl[5] >= 3:
        c_lo, c_hi = cl[0], cl[1]; zoom_grenze = (c_lo + c_hi) / 2
    out = dict(f_haupt_orig_px=f_haupt, streu_log_ungezoomt_ab=streu, cluster_log=dict(normal=c_lo, zoom=c_hi, zoom_grenze_log=zoom_grenze, zwei_means=cl),
               hinweis="Einzelbild-f nur Hinweis; E1 PnP-Profil, E2 Fundamentalmatrix; Grenzen aus Daten (2-Means, Serien-a/b-Streuung); 'unbekannt' NICHT in bilder", bilder={}, alle={})
    for key, v in sorted(alle.items()):
        n = key.split("/", 1)[1]; z = None; kl = "unbekannt"; grund = None
        if v["f1"] and v["n_korr"] >= 30:
            z = v["f1"] / f_haupt; lz = np.log(z)
            lo, hi = np.log(v["f1_lo"] / f_haupt), np.log(v["f1_hi"] / f_haupt)
            if zoom_grenze is not None and lo <= (c_lo + 2 * streu) and hi >= (c_hi - 2 * streu): kl = "unbekannt"; grund = "f-Intervall umfasst Normal- und Zoomcluster"
            elif zoom_grenze is not None and lz >= zoom_grenze: kl = "gezoomt"
            elif abs(lz) <= 2 * streu: kl = "normal"
            else: kl = "abweichend"
        else: grund = "zu wenige Korrespondenzen (<30 Referenzpunkte)"
        z2 = (v["f2"] / f_haupt) if v["f2"] else None
        kl2 = None
        if z2 is not None and zoom_grenze is not None: kl2 = "gezoomt" if np.log(z2) >= zoom_grenze else ("normal" if abs(np.log(z2)) <= 2 * streu else "abweichend")
        # Endklasse: E1 wenn vorhanden; sonst E2 (nur Fundamentalmatrix, >= 2 Partner) und nur 'normal'/'gezoomt' ('abweichend' aus E2 allein bleibt unbekannt)
        kf, qu = kl, ("E1" if kl != "unbekannt" else None)
        if kl == "unbekannt" and kl2 in ("normal", "gezoomt") and v.get("f2_n_partner", 0) >= 2: kf, qu = kl2, "E2"
        e = dict(v, z=z, klasse=kl, grund_unbekannt=grund, z_E2=z2, klasse_E2=kl2, klasse_final=kf, klasse_quelle=qu); out["alle"][key] = e
        if kf != "unbekannt": out["bilder"][n] = dict(serie=v["serie"], hochformat=v["hochformat"], f_orig_SIFT=None, f_orig_LG=v["f1"], z=(z if qu == "E1" else z2), klasse=kf, klasse_quelle=qu, inlier=v["inlier"], n_laeufe=1, lauf=v["lauf"])
    ser = {}
    for key, e in out["alle"].items():
        s = e["serie"]; d = ser.setdefault(s, dict(n=0, normal=0, abweichend=0, gezoomt=0, unbekannt=0, E2_vorhanden=0, E1E2_gleich=0, E1E2_verschieden=0)); d["n"] += 1; d[e["klasse"]] += 1
        if e["klasse_E2"]:
            d["E2_vorhanden"] += 1
            if e["klasse"] != "unbekannt": d["E1E2_gleich" if e["klasse"] == e["klasse_E2"] else "E1E2_verschieden"] += 1
    out["je_serie"] = ser; out["zaehlung"] = {k_: sum(1 for e in out["alle"].values() if e["klasse"] == k_) for k_ in ("normal", "abweichend", "gezoomt", "unbekannt")}
    out["zaehlung_final"] = {k_: sum(1 for e in out["alle"].values() if e["klasse_final"] == k_) for k_ in ("normal", "abweichend", "gezoomt", "unbekannt")}
    out["zaehlung_final"]["davon_nur_E2"] = sum(1 for e in out["alle"].values() if e["klasse_quelle"] == "E2")
    if a.alt:
        alt = json.load(open(a.alt))["bilder"]; vg = collections.Counter()
        for n, b in alt.items():
            keys = [k_ for k_ in out["alle"] if k_.endswith("/" + n)]
            if keys: vg[(b["klasse"], out["alle"][keys[0]]["klasse"])] += 1
        out["vergleich_alt_neu"] = {f"{x}->{y}": c for (x, y), c in sorted(vg.items())}
    json.dump(out, open(a.aus, "w"), indent=1, default=float)
    print(json.dumps(out["zaehlung"]), json.dumps(out["zaehlung_final"]), json.dumps(out["je_serie"]), out.get("vergleich_alt_neu"), "f_haupt", f_haupt, "streu", streu, "cluster", out["cluster_log"])


if __name__ == "__main__":
    if "--v2" in sys.argv: sys.exit(main_v2())
    sys.exit(main())
