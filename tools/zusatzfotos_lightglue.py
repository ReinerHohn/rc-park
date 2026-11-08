#!/usr/bin/env python3
"""zusatzfotos_lightglue.py - Zusatzfotos, die mit SIFT nicht registrierten, mit ALIKED+LightGlue nachmatchen und neu registrieren (2026-11-06, Register CY).

Baut auf tools/zusatzfotos_registrieren.py (PnP, feste Kamera je Format, Runden) und tools/lg_match.py (ALIKED/LightGlue: Apache-2.0 / BSD-3). Nichts Objektspezifisches.
Stufen (Ergebnis je Stufe im Zielordner ZIEL = Ordner der Stufe 'vorbereiten', Unterordner lg/):
  refnamen (venv-colmap) --ziel Z --ref-sparse REF   -> lg/refnamen.json
  paare   (venv-seg, GPU)  --ziel Z --ref-sparse REF --ref-bilder ORDNER [--k 12] [--grob 512] [--max-kp 4096]
        ALIKED fuer alle Zusatzfotos + registrierte Referenzbilder; Retrieval-Vorfilter: LightGlue mit nur --grob Merkmalen fuer ALLE Kandidatenpaare
        (Zusatz x Referenz, Zusatz x Zusatz), je Bild die --k besten Partner behalten (symmetrisch vereinigt); NUR diese Paare werden voll gematcht -> lg/lg.npz
  einlesen (venv-colmap, CPU) --ziel Z --ref-db DB --ref-sparse REF
        Kopie von Z/db.db -> Z/lg/db.db, ALIKED-Merkmale und -Matches ANGEHAENGT (SIFT bleibt), geometrische Verifikation der Paare;
        Referenzrekonstruktion mit Posen der Referenzbilder, Punkte neu trianguliert (SIFT+ALIKED) -> Z/lg/ref_tri/
  Danach: zusatzfotos_registrieren.py registrieren --sparse Z/lg/ref_tri --aus Z/lg  (Z/lg enthaelt vorbereitet.json, merkmale.json, db.db, bilder -> Link) und luecken.
Wasserzeichen (unten 5 %) ist in Z/bilder schon abgeschnitten (Stufe vorbereiten).
"""
import sys, os, json, argparse, sqlite3, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def paare(a):
    import torch, time
    from lightglue import LightGlue, ALIKED
    from lightglue.utils import load_image
    dev = "cuda"; Z = a.ziel; V = json.load(open(os.path.join(Z, "vorbereitet.json"))); lg = os.path.join(Z, "lg"); os.makedirs(lg, exist_ok=True)
    refn = json.load(open(os.path.join(lg, "refnamen.json")))        # Stufe refnamen (venv-colmap; pycolmap fehlt in venv-seg)
    pfad = {n: os.path.join(Z, "bilder", n) for n in V["bilder"]}; pfad.update({n: os.path.join(a.ref_bilder, n) for n in refn})
    namen = sorted(pfad); ext = ALIKED(max_num_keypoints=a.max_kp).eval().to(dev); mt = LightGlue(features="aliked").eval().to(dev)
    F = {}; t0 = time.time()
    for n in namen:
        with torch.no_grad(): F[n] = {k: v.cpu() for k, v in ext.extract(load_image(pfad[n]).to(dev), resize=2048).items()}
        torch.cuda.empty_cache()
    print(f"Merkmale {len(namen)} Bilder {time.time() - t0:.0f} s", flush=True)
    def gross(f, k): return {"keypoints": f["keypoints"][:, :k], "descriptors": f["descriptors"][:, :k], "keypoint_scores": f["keypoint_scores"][:, :k], "image_size": f["image_size"]}
    neu = sorted(V["bilder"]); kand = [(x, y) for x in neu for y in namen if y != x and (y not in V["bilder"] or x < y)]
    if getattr(a, "gps_radius", 0):                                  # GPS-Vorwahl (tools/paarvorwahl.py): entfaellt nur, wenn BEIDE Bilder GPS haben und weiter als Radius auseinander liegen
        import paarvorwahl
        gps = {n: g for n in namen for g in [paarvorwahl.gps_aus_exif(pfad[n])] if g}
        kand, st = paarvorwahl.gps_filter(kand, gps, a.gps_radius)
        print(f"GPS-Vorwahl {a.gps_radius} m: {st['vorher']} -> {st['nachher']} Paare, ohne GPS behalten: {st['ohne_gps']}, Bilder mit GPS: {len(gps)}/{len(namen)}", flush=True)
    G = {n: {k: v.to(dev) for k, v in gross(F[n], a.grob).items()} for n in namen}; sc = collections.defaultdict(dict); t0 = time.time()
    for i, (x, y) in enumerate(kand):
        with torch.no_grad(): m = mt({"image0": G[x], "image1": G[y]})
        k = int(m["matches"][0].shape[0]); sc[x][y] = k; sc[y][x] = k
        if i % 4000 == 0: print(f"  grob {i}/{len(kand)} {time.time() - t0:.0f} s", flush=True)
    sel = set()
    for x in neu:
        for y, k in sorted(sc[x].items(), key=lambda t: -t[1])[:a.k]:
            if k >= 8: sel.add(tuple(sorted((x, y))))
    print(f"Vorfilter: {len(kand)} Kandidatenpaare -> {len(sel)} gewaehlt", flush=True)
    out = {"namen": np.array(namen)}
    for n in namen: out["kp_" + n] = F[n]["keypoints"][0].cpu().numpy().astype(np.float32)
    npz = 0
    for x, y in sorted(sel):
        with torch.no_grad(): m = mt({"image0": {k: v.to(dev) for k, v in F[x].items()}, "image1": {k: v.to(dev) for k, v in F[y].items()}})
        idx = m["matches"][0].cpu().numpy().astype(np.int32)
        if len(idx) >= 15: out[f"m_{x}|{y}"] = idx; npz += 1
    np.savez_compressed(os.path.join(lg, "lg.npz"), **out)
    json.dump(dict(neu=len(neu), referenz=len(refn), kandidaten=len(kand), gewaehlt=len(sel), mit_matches=npz, k=a.k, grob=a.grob, max_kp=a.max_kp,
                   grob_matches={x: sorted(sc[x].values())[-a.k:] for x in neu}), open(os.path.join(lg, "paare.json"), "w"))
    print(f"voll gematcht: {npz} Paare mit >= 15 Matches", flush=True)


def refnamen(a):
    import pycolmap
    ref = pycolmap.Reconstruction(a.ref_sparse); lg = os.path.join(a.ziel, "lg"); os.makedirs(lg, exist_ok=True)
    json.dump(sorted(i.name for i in ref.images.values() if i.has_pose), open(os.path.join(lg, "refnamen.json"), "w")); print("Referenzbilder:", ref.num_reg_images())


def einlesen(a):
    import pycolmap, shutil
    Z = a.ziel; lg = os.path.join(Z, "lg"); db = os.path.join(lg, "db.db")
    if os.path.exists(db): os.remove(db)
    shutil.copy(os.path.join(Z, "db.db"), db)
    for f in ("vorbereitet.json", "merkmale.json"): shutil.copy(os.path.join(Z, f), os.path.join(lg, f))
    if not os.path.exists(os.path.join(lg, "bilder")): os.symlink(os.path.join(Z, "bilder"), os.path.join(lg, "bilder"))
    D = np.load(os.path.join(lg, "lg.npz"), allow_pickle=True); con = sqlite3.connect(db); cur = con.cursor()
    ids = {n: i for i, n in cur.execute("select image_id,name from images")}; typ = cur.execute("select sql from sqlite_master where name='descriptors'").fetchone()[0]; off = {}
    for name in [str(n) for n in D["namen"]]:
        iid = ids[name]; row = cur.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone(); n0, cols, data = row
        alt = np.frombuffer(data, np.float32).reshape(n0, cols); kp = D["kp_" + name].astype(np.float32); neu = np.zeros((kp.shape[0], cols), np.float32); neu[:, :2] = kp + 0.5   # COLMAP: Pixelmitte = +0.5
        if cols >= 6: neu[:, 2] = 1.0; neu[:, 5] = 1.0
        elif cols == 4: neu[:, 2] = 1.0
        allk = np.vstack([alt, neu]); off[name] = n0
        cur.execute("delete from keypoints where image_id=?", (iid,)); cur.execute("insert into keypoints (image_id, rows, cols, data) values (?,?,?,?)", (iid, allk.shape[0], cols, allk.tobytes()))
        d = cur.execute("select rows, cols, data from descriptors where image_id=?", (iid,)).fetchone(); dalt = np.frombuffer(d[2], np.uint8).reshape(d[0], d[1]) if d and d[0] else np.zeros((0, 128), np.uint8)
        dall = np.vstack([dalt, np.zeros((kp.shape[0], 128), np.uint8)]); cur.execute("delete from descriptors where image_id=?", (iid,))
        if "type" in typ: cur.execute("insert into descriptors (image_id, type, rows, cols, data) values (?,?,?,?,?)", (iid, 0, dall.shape[0], dall.shape[1], dall.tobytes()))
        else: cur.execute("insert into descriptors (image_id, rows, cols, data) values (?,?,?,?)", (iid, dall.shape[0], dall.shape[1], dall.tobytes()))
    pl = []
    for key in D.files:
        if not key.startswith("m_"): continue
        x, y = key[2:].split("|"); ia, ib = ids[x], ids[y]; m = D[key].astype(np.uint32) + np.array([off[x], off[y]], np.uint32)
        if ia > ib: ia, ib = ib, ia; m = m[:, ::-1].copy()
        pid = int(pycolmap.image_pair_to_pair_id(ia, ib)); alt = cur.execute("select rows, data from matches where pair_id=?", (pid,)).fetchone()
        if alt and alt[0]: m = np.vstack([np.frombuffer(alt[1], np.uint32).reshape(alt[0], 2), m])
        cur.execute("delete from matches where pair_id=?", (pid,)); cur.execute("delete from two_view_geometries where pair_id=?", (pid,))
        cur.execute("insert into matches (pair_id, rows, cols, data) values (?,?,?,?)", (pid, m.shape[0], 2, m.tobytes())); pl.append(f"{x} {y}")
    con.commit(); con.close(); pf = os.path.join(lg, "paare.txt"); open(pf, "w").write("\n".join(pl) + "\n")
    vo = pycolmap.TwoViewGeometryOptions(); vo.ransac.random_seed = 0
    pycolmap.verify_matches(db, pf, verification_options=vo) if False else pycolmap.verify_matches(db, pf)
    # Referenz: Posen behalten, Punkte NEU aus SIFT+ALIKED (alte Punkt-IDs haengen an den alten Merkmalsindizes - die Indizes sind gleich geblieben, ALIKED ist angehaengt)
    ref = pycolmap.Reconstruction(a.ref_sparse); td = os.path.join(lg, "ref_tri"); shutil.rmtree(td, ignore_errors=True); os.makedirs(td)
    rec = pycolmap.triangulate_points(ref, db, os.path.join(lg, "bilder"), td, clear_points=True)
    rec.write(td); print("Referenz neu trianguliert:", rec.num_points3D(), "Punkte (vorher", ref.num_points3D(), ")")


def teilmodell(a):
    """Teilrekonstruktion nur der Bilder der --serien (Namen h_<serie>_nn) aus Z/lg/db.db (COLMAP incremental, nur diese Bilder; Intrinsik fest),
    Sim3-Anbindung an das Netz ueber die gemeinsamen, bereits im Netz registrierten Bilder (Posen-Zentren, Umeyama, RANSAC-frei: Median-Residuum wird berichtet)."""
    import pycolmap
    lg = os.path.join(a.ziel, "lg"); V = json.load(open(os.path.join(a.ziel, "vorbereitet.json")))
    nm = sorted(n for n in V["bilder"] if n.split("_")[1] in a.serien); out = os.path.join(lg, "teil_" + "".join(a.serien)); import shutil; shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    o = pycolmap.IncrementalPipelineOptions(); o.image_names = nm; o.ba_refine_focal_length = False; o.ba_refine_extra_params = False; o.min_num_matches = 15
    rs = pycolmap.incremental_mapping(os.path.join(lg, "db.db"), os.path.join(lg, "bilder"), out, o)
    reg = json.load(open(os.path.join(lg, "registrierung.json")))["bilder"]; ber = dict(bilder_angefragt=len(nm), modelle=[])
    for k, r in rs.items():
        ims = {i.name: i for i in r.images.values() if i.has_pose}; gem = [n for n in ims if reg.get(n, {}).get("status") == "registriert"]
        m = dict(id=int(k), registriert=len(ims), punkte=r.num_points3D(), reproj_px=float(r.compute_mean_reprojection_error()) if r.num_points3D() else None, gemeinsam_im_netz=len(gem), namen=sorted(ims))
        if len(gem) >= 3:
            A = np.array([ims[n].projection_center() for n in gem]); B = np.array([reg[n]["zentrum"] for n in gem])
            sim = pycolmap.estimate_sim3d(A, B) if hasattr(pycolmap, "estimate_sim3d") else None
            if sim is not None:
                T = sim; Ap = np.array([T * x for x in A]); res = np.linalg.norm(Ap - B, axis=1); m.update(sim3_skala=float(T.scale), residuum_median_m=float(np.median(res)), residuum_max_m=float(res.max()))
                neu_ = {n: [float(v) for v in (T * ims[n].projection_center())] for n in ims if n not in gem}; m["neu_angebunden"] = neu_
                m["neu_angebunden_naechste_netzkamera_m"] = {n: float(np.linalg.norm(B - np.array(c), axis=1).min()) for n, c in neu_.items()}
        ber["modelle"].append(m)
    json.dump(ber, open(os.path.join(out, "teilmodell.json"), "w"), indent=1); print(json.dumps({k: v for k, v in ber.items()}, default=lambda x: None)[:1500])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("paare"); p.add_argument("--ziel", required=True); p.add_argument("--ref-sparse", required=True); p.add_argument("--ref-bilder", required=True)
    p.add_argument("--k", type=int, default=12); p.add_argument("--grob", type=int, default=512); p.add_argument("--max-kp", type=int, default=4096); p.add_argument("--gps-radius", type=float, default=0, help="Meter; 0 = aus (Standard). Paar entfaellt nur, wenn beide Bilder GPS haben")
    p = sp.add_parser("refnamen"); p.add_argument("--ziel", required=True); p.add_argument("--ref-sparse", required=True)
    p = sp.add_parser("einlesen"); p.add_argument("--ziel", required=True); p.add_argument("--ref-sparse", required=True)
    p = sp.add_parser("teilmodell"); p.add_argument("--ziel", required=True); p.add_argument("--serien", nargs="+", required=True)
    a = ap.parse_args(argv); {"paare": paare, "refnamen": refnamen, "teilmodell": teilmodell, "einlesen": einlesen}[a.cmd](a); return 0


if __name__ == "__main__": sys.exit(main())
