#!/usr/bin/env python3
"""zusatzfotos_registrieren.py - Zusatzfotos (Handy, feste Linse) gegen ein VORHANDENES SfM-Netz registrieren, OHNE das Netz zu veraendern (2026-11-06).

Warum eigenes Werkzeug: sfm_netz.py baut immer neu. Hier bleiben Referenz-Rekonstruktion (Modellrahmen, Meter) und Referenz-Datenbank unberuehrt (nur gelesen);
alles Neue entsteht in einem Zielordner (Kopie der Datenbank). Pose der neuen Bilder per PnP (2D-3D aus verifizierten Matches zu registrierten Referenzbildern),
EINE gemeinsame Kamera fuer alle Zusatzfotos (Intrinsik nicht je Bild frei).
Stufen (Ergebnis je Stufe als JSON im Zielordner):
  vorbereiten --fotos ORDNER... --aus ZIEL [--ausschluss liste.json] [--unten 0.05] [--breite 2000]
        Duplikate (MD5) und Ausschlussliste raus, unten Streifen (Hersteller-Wasserzeichen) abschneiden, auf --breite verkleinern -> ZIEL/bilder/*.jpg
  merkmale   --ref-db DB --sparse REFREKONSTRUKTION --aus ZIEL [--f-px F]      (GPU: SIFT + Matching der Paare neu x registriert + neu x neu)
  registrieren --sparse REF --aus ZIEL [--kalibrieren]                          (CPU: Brennweite je Bild (Kalibrierlauf) -> Median -> fest; PnP; Buendel nur der neuen Posen)
  luecken    --sparse REF --dicht-npy WOLKE.npy --aus ZIEL                      (Triangulation mit allen Posen; Anteil neuer Punkte ausserhalb der vorhandenen dichten Wolke)
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/zusatzfotos_registrieren.py <stufe> ...
Lizenz: nur pycolmap/COLMAP (BSD-3), OpenCV (Apache-2.0), numpy.
"""
import sys, os, json, glob, argparse, hashlib, shutil, sqlite3, itertools, collections
import numpy as np


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def name_aus_pfad(p):
    """eindeutiger Kurzname je Foto: z. B. .../handy_2026-11-06_c/handy_c_03.jpg -> h_c_03.jpg; .../handy_2026-11-06/handy_07.jpg -> h_a_07.jpg"""
    bn = os.path.splitext(os.path.basename(p))[0]; b = bn.split("_")
    if not bn.startswith("handy"): return bn + ".jpg"            # Videoframes u. a. (vid_IMG_6114_001.jpg): Name behalten, sonst Kollisionen (2026-11-09)
    return ("h_" + b[1] + "_" + b[2] + ".jpg") if len(b) == 3 else ("h_a_" + b[-1] + ".jpg")


def gruppe_von_bild(n, info, zoom=None):
    """Kameragruppe eines Bildes aus Format (Hoch/Quer nach Originalgroesse) UND Zoomklasse (zoom_verdacht.json, Feld bilder[n].klasse).
    Rueckgabe (gruppe, zoomstatus): zoomstatus = 'bewertet' | 'unbekannt' (nicht in zoom_verdacht.json: zuerst normal, MARKIERT) | 'ohne_zoomdatei'."""
    W, H = info["orig"]; fmt = "hoch" if H > W else "quer"
    if zoom is None: return fmt + "_normal", "ohne_zoomdatei"
    z = zoom.get("bilder", {}).get(n)
    if z is None: return fmt + "_normal", "unbekannt"
    return fmt + ("_zoom" if z.get("klasse") == "gezoomt" else "_normal"), "bewertet"


def kamera_gruppen(bilder, zoom, params):
    """bilder: vorbereitet.json['bilder']; params: JSON {'kameras': {gruppe: {f_orig, k1, cx_rel, cy_rel}}} (Zahlen aus Daten, nicht im Code).
    f in Bildpixeln = f_orig * skala; Hauptpunkt = rel * ORIGINALgroesse * skala (cy auf das UNGECROPPTE Original bezogen; Bild ist unten gecropped).
    Rueckgabe {gruppe: dict(namen, W, H, params=[f,cx,cy,k1], f_orig, skala)}, {name: (gruppe, zoomstatus)}."""
    out = {}; zuordnung = {}
    for n, info in bilder.items():
        g, zs = gruppe_von_bild(n, info, zoom); zuordnung[n] = (g, zs)
        if g not in params["kameras"]: raise KeyError(f"Kameragruppe {g} fehlt in den Kameraparametern")
        k = params["kameras"][g]; W0, H0 = info["orig"]; s = info["skala"]; Wb, Hb = info["bild"]
        P = [k["f_orig"] * s, k.get("cx_rel", 0.5) * W0 * s, k.get("cy_rel", 0.5) * H0 * s, k.get("k1", 0.0)]
        e = out.setdefault(g, dict(namen=[], W=Wb, H=Hb, params=P, f_orig=k["f_orig"], skala=s))
        if (e["W"], e["H"], round(e["skala"], 6)) != (Wb, Hb, round(s, 6)): raise ValueError(f"Gruppe {g}: uneinheitliche Bildgroesse/Skala bei {n}")
        e["namen"].append(n)
    return out, zuordnung


def db_kameras_schreiben(dbp, cams, GK, name2id):
    """Kameras je Gruppe in die (Ziel-)Datenbank schreiben, Bilder der Gruppe darauf umhaengen, trivialen Rig/Frame (rig_id = camera_id) anpassen.
    Grund: pycolmap.triangulate_points liest Rigs/Frames aus der DB; die Rekonstruktion legt fuer neue Kameras eigene Rigs an -> Rig-Konflikt."""
    con = sqlite3.connect(dbp)
    for g, c_ in cams.items():
        cid = int(c_.camera_id); blob = np.asarray(c_.params, dtype="<f8").tobytes()
        con.execute("insert or replace into cameras(camera_id,model,width,height,params,prior_focal_length) values (?,?,?,?,?,1)", (cid, 2, int(c_.width), int(c_.height), blob))
        con.execute("insert or replace into rigs(rig_id,ref_sensor_id,ref_sensor_type) values (?,?,0)", (cid, cid))
        for n in GK[g]["namen"]:
            iid = name2id[n]
            con.execute("update images set camera_id=? where image_id=?", (cid, iid))
            fr = [r[0] for r in con.execute("select frame_id from frame_data where data_id=? and sensor_type=0", (iid,))]
            for f_ in fr:
                con.execute("update frames set rig_id=? where frame_id=?", (cid, f_)); con.execute("update frame_data set sensor_id=? where frame_id=? and data_id=?", (cid, f_, iid))
    con.commit(); con.close()


def vorbereiten(a):
    import cv2
    ausschluss = set()
    if a.ausschluss:
        for k in json.load(open(a.ausschluss)).get("aussortiert", []): ausschluss.add(os.path.basename(k["datei"] if isinstance(k, dict) else k))
    fs = []
    for d in a.fotos: fs += sorted(glob.glob(os.path.join(d, "*.jpg")))
    seen = {}; liste = []; verworfen = []
    for f in fs:
        h = md5(f); b = os.path.basename(f)
        if h in seen: verworfen.append(dict(datei=f, grund="Dublette (MD5) von " + seen[h])); continue
        seen[h] = f
        if b in ausschluss: verworfen.append(dict(datei=f, grund="ausgeschlossen (Ausschlussliste, Sichtprobe)")); continue
        liste.append(f)
    bd = os.path.join(a.aus, "bilder"); os.makedirs(bd, exist_ok=True); info = {}
    for f in liste:
        im = cv2.imread(f)
        if im is None: verworfen.append(dict(datei=f, grund="nicht lesbar")); continue
        H, W = im.shape[:2]; h2 = int(round(H * (1 - a.unten))); im = im[:h2]; s = (a.breite / W) if a.breite > 0 else 1.0     # --breite 0 = keine Skalierung (gemischte Hoch/Quer-Frames, 2026-11-09)
        if a.breite > 0: im = cv2.resize(im, (a.breite, int(round(h2 * s))), interpolation=cv2.INTER_AREA)
        n = name_aus_pfad(f)
        cv2.imwrite(os.path.join(bd, n), im, [cv2.IMWRITE_JPEG_QUALITY, 95]); info[n] = dict(quelle=f, orig=[W, H], bild=[im.shape[1], im.shape[0]], skala=s)
    json.dump(dict(bilder=info, verworfen=verworfen, unten=a.unten, breite=a.breite), open(os.path.join(a.aus, "vorbereitet.json"), "w"), indent=1)
    print(f"vorbereitet: {len(info)} Bilder, verworfen {len(verworfen)}")


def merkmale(a):
    import pycolmap
    pycolmap.set_random_seed(0)
    V = json.load(open(os.path.join(a.aus, "vorbereitet.json"))); names = sorted(V["bilder"]); db = os.path.join(a.aus, "db.db")
    if not os.path.exists(db):
        src = sqlite3.connect(f"file:{a.ref_db}?mode=ro", uri=True); dst = sqlite3.connect(db); src.backup(dst); dst.close(); src.close()      # Kopie, Referenz bleibt unberuehrt
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from colmap_db_schema import kameras_alt      # 18.11.2026: Datenbank vom neuen globalen Mapper (Spalte 'source') -> pycolmap 4.2.1 oeffnet sie sonst nicht
    if kameras_alt(db): print("Datenbank-Kopie auf das pycolmap-4.2.1-Schema zurueckgefuehrt (Kameratabelle 'source' -> prior_focal_length)", flush=True)
    gr = collections.defaultdict(list)
    for n in names: gr[tuple(V["bilder"][n]["bild"])].append(n)         # Hoch-/Querformat = verschiedene Bildgroesse -> je Gruppe EINE Kamera (gleiche f, k1)
    for (W, H), nn in gr.items():
        ro = pycolmap.ImageReaderOptions(); ro.camera_model = "SIMPLE_RADIAL"; f0 = a.f_px; ro.camera_params = f"{f0},{W / 2},{H / 2},0"
        kw = {}
        if os.environ.get("RCPARK_SIFT_MAX"):                                  # opt-in: SiftGPU-VRAM begrenzen (3200 -> bis 7,4 GB, 1600 -> 2,1 GB; GPU_PARALLEL_UNTERSUCHUNG.md); ohne Variable Verhalten unveraendert
            eo = pycolmap.FeatureExtractionOptions(); eo.max_image_size = int(os.environ["RCPARK_SIFT_MAX"]); kw["extraction_options"] = eo
        pycolmap.extract_features(db, os.path.join(a.aus, "bilder"), image_names=nn, camera_mode=pycolmap.CameraMode.SINGLE, reader_options=ro, **kw)
    con = sqlite3.connect(db); ids = {n: i for i, n in con.execute("select image_id,name from images")}; con.close()
    ref = pycolmap.Reconstruction(a.sparse); reg = sorted(i.name for i in ref.images.values() if i.has_pose)
    mod_ = {str(c.model).split(".")[-1] for c in ref.cameras.values()}
    if mod_ <= {"PINHOLE"} and "dicht" in a.sparse:      # 18.11.2026 (Kaufhaus gk2i): Kette gab das ENTZERRTE Modell dicht/sparse - Keypoints der Datenbank gehoeren zu den Originalbildern; Absturz erst nach 90 min in triangulate_points (kPinhole vs kSimpleRadial)
        print(f"FEHLER: {a.sparse} ist ein entzerrtes Modell (nur PINHOLE) - passt nicht zur Merkmalsdatenbank der Originalbilder; das SfM-Modell (sfm/sparse/0) angeben", flush=True); sys.exit(2)
    paare = [(n, r) for n in names for r in reg] + list(itertools.combinations(names, 2))
    pf = os.path.join(a.aus, "paare.txt"); open(pf, "w").write("\n".join(f"{x} {y}" for x, y in paare) + "\n")
    mo = pycolmap.FeatureMatchingOptions(); vo = pycolmap.TwoViewGeometryOptions(); vo.ransac.random_seed = 0
    pycolmap.match_image_pairs(db, matching_options=mo, pairing_options=pycolmap.ImportedPairingOptions(match_list_path=pf), verification_options=vo)
    con = sqlite3.connect(db); nk = {n: con.execute("select rows from keypoints where image_id=?", (ids[n],)).fetchone()[0] for n in names}
    ver = con.execute("select count(*) from two_view_geometries where rows>0").fetchone()[0]; con.close()
    leer = [n for n, k in nk.items() if not k]
    if leer: raise SystemExit(f"FEHLER: {len(leer)} Bilder ohne Schluesselpunkte (SiftGPU scheitert bei VRAM-Mangel STILL mit rc 0): {leer[:5]} - VRAM pruefen (nvidia-smi), RCPARK_SIFT_MAX=1600")
    json.dump(dict(paare=len(paare), neu=len(names), referenz=len(reg), schluesselpunkte_mittel=float(np.mean(list(nk.values()))), verifizierte_paare_gesamt=ver, f_prior_px=f0), open(os.path.join(a.aus, "merkmale.json"), "w"), indent=1)
    print(f"merkmale: {len(names)} neu, {len(paare)} Paare gematcht, mittl. Schluesselpunkte {np.mean(list(nk.values())):.0f}")


def korrespondenzen(db, ref, name2id, n_id, mind=15):
    """2D-3D fuer neues Bild n_id: je Schluesselpunkt die haeufigste Punkt-ID aus den inlier-Matches zu registrierten Referenzbildern."""
    kp = db.read_keypoints(n_id)[:, :2]; stimmen = collections.defaultdict(collections.Counter); je_ref = {}
    for im in ref.images.values():
        if not im.has_pose: continue
        rid = name2id.get(im.name)
        if rid is None: continue
        try: g = db.read_two_view_geometry(n_id, rid) if n_id < rid else db.read_two_view_geometry(rid, n_id)
        except Exception: continue
        m = np.asarray(g.inlier_matches)
        if m.size == 0 or len(m) < mind: continue
        if n_id > rid: m = m[:, ::-1]
        p2 = im.points2D; k = 0
        for a_, b_ in m:
            p = p2[int(b_)]
            if p.has_point3D(): stimmen[int(a_)][p.point3D_id] += 1; k += 1
        je_ref[im.name] = k
    idx = sorted(stimmen); pid = [stimmen[i].most_common(1)[0][0] for i in idx]
    return idx, kp[idx], pid, je_ref


def _kalibrierlauf(a, pycolmap, names, C0, WH, f0, ref0):
    """Alter Weg (ohne --kameras): Brennweite je Bild frei, Median im +-30-%-Fenster um den Prior, ein Wert fuer ALLE Formate (Register DB: falsch fuer Hochformat/Zoom)."""
    fs = []; eo = pycolmap.AbsolutePoseEstimationOptions(); eo.estimate_focal_length = True; eo.ransac.max_error = a.max_fehler
    for n in names:
        idx, xy, pid, je = C0[n]
        if len(idx) < 60: continue
        W, H = WH(n); cam = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, f0, W, H); P3 = np.array([ref0.points3D[p].xyz for p in pid])
        r = pycolmap.estimate_and_refine_absolute_pose(xy, P3, cam, eo)
        if r is not None and r["num_inliers"] >= 40: fs.append(float(cam.params[0]))
    fin = [f for f in fs if 0.7 * f0 <= f <= 1.3 * f0]
    f_med = float(np.median(fin)) if len(fin) >= 8 else f0; f_streu = float(np.std(fin)) if fin else 0.0
    print(f"Kalibrierlauf: {len(fs)} Bilder, davon {len(fin)} im Fenster, f Median {f_med:.1f} px, Streuung {f_streu:.1f} (Prior {f0:.1f})", flush=True)
    json.dump(dict(f_median_px=f_med, f_std_px=f_streu, n_bilder_gesamt=len(fs), n_im_fenster=len(fin), f_je_bild=fs, prior_px=f0), open(os.path.join(a.aus, "kalibrierlauf.json"), "w"), indent=1)
    return f_med, f_streu


def registrieren(a):
    import pycolmap
    V = json.load(open(os.path.join(a.aus, "vorbereitet.json"))); names = sorted(V["bilder"]); dbp = os.path.join(a.aus, "db.db")
    ref0 = pycolmap.Reconstruction(a.sparse); db = pycolmap.Database.open(dbp)
    con = sqlite3.connect(dbp); name2id = {n: i for i, n in con.execute("select image_id,name from images")}; n2cam = {n: c for n, c in con.execute("select name,camera_id from images")}; con.close()
    f0 = json.load(open(os.path.join(a.aus, "merkmale.json")))["f_prior_px"]; WH = lambda n: tuple(V["bilder"][n]["bild"])
    C0 = {n: korrespondenzen(db, ref0, name2id, name2id[n]) for n in names}
    cams = {}; GK = None; zuord = {}; f_med = f0; f_streu = 0.0
    if a.kameras:
        # feste Kameras je Gruppe (Format x Zoomstufe) aus Parameter-JSON; KEIN Kalibrierlauf (der Median ueber alle Formate war der Fehler, Register DB)
        params = json.load(open(a.kameras)); zoom = json.load(open(a.zoom)) if a.zoom else None
        GK, zuord = kamera_gruppen(V["bilder"], zoom, params); con2 = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True); nxt = max(max(ref0.cameras), max(c[0] for c in con2.execute("select camera_id from cameras"))) + 1; con2.close()
        for k_, (g, e) in enumerate(sorted(GK.items())):
            c_ = pycolmap.Camera.create_from_model_id(nxt + k_, pycolmap.CameraModelId.SIMPLE_RADIAL, e["params"][0], e["W"], e["H"]); c_.params = list(e["params"]); cams[g] = c_
        db.close(); db_kameras_schreiben(dbp, cams, GK, name2id); db = pycolmap.Database.open(dbp)      # Datenbank-Rigs/Frames muessen zu den neuen Kameras passen (sonst Absturz in triangulate_points, Register DF)
        f_med = GK.get("quer_normal", next(iter(GK.values())))["params"][0]
        print("Kameragruppen:", {g: (len(e["namen"]), [round(x, 3) for x in e["params"]]) for g, e in GK.items()}, flush=True)
        camof = lambda n: cams[zuord[n][0]]
    elif a.je_bild:
        # 16.11.2026 (Stufe seiten, Webfotos fuer ungesehene Waende): jedes Bild EIGENE Kamera, Brennweite je Bild aus PnP mit freier Brennweite.
        # Grund: Webfotos haben gemischte Formate und Brennweiten; der gemeinsame Median registrierte 11 von 46 und triangulate_points brach ab (Kamerabreite 2000 vs. 1280).
        eo_f = pycolmap.AbsolutePoseEstimationOptions(); eo_f.estimate_focal_length = True; eo_f.ransac.max_error = a.max_fehler; GKb = {}
        con2 = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True); nxt = max(max(ref0.cameras), max(c[0] for c in con2.execute("select camera_id from cameras"))) + 1; con2.close(); f_bild = {}
        for k_, n in enumerate(names):
            W, H = WH(n); fs_ = 1.2 * max(W, H); idx, xy, pid, je = C0[n]; c_ = pycolmap.Camera.create_from_model_id(nxt + k_, pycolmap.CameraModelId.SIMPLE_RADIAL, fs_, W, H); f_ = fs_
            if len(idx) >= 20:
                r = pycolmap.estimate_and_refine_absolute_pose(xy, np.array([ref0.points3D[p].xyz for p in pid]), c_, eo_f)
                if r is not None and r["num_inliers"] >= 15 and 0.4 * max(W, H) < float(c_.params[0]) < 8.0 * max(W, H): f_ = float(c_.params[0])
            c_.params = [f_, W / 2, H / 2, 0.0]; cams[n] = c_; GKb[n] = dict(namen=[n]); f_bild[n] = round(f_, 1)
        db.close(); db_kameras_schreiben(dbp, cams, GKb, name2id); db = pycolmap.Database.open(dbp); json.dump(f_bild, open(os.path.join(a.aus, "brennweite_je_bild.json"), "w"), indent=1)
        print(f"je Bild eigene Kamera: {len(cams)} Kameras, Brennweite aus PnP bei {sum(1 for n in names if abs(f_bild[n] - 1.2 * max(WH(n))) > 1e-3)} Bildern", flush=True)
        camof = lambda n: cams[n]; f_med = f0
    else:
        f_med, f_streu = _kalibrierlauf(a, pycolmap, names, C0, WH, f0, ref0)
        for k_, (W, H) in enumerate(sorted({WH(n) for n in names})):
            c_ = pycolmap.Camera.create_from_model_id(n2cam[next(n for n in names if WH(n) == (W, H))], pycolmap.CameraModelId.SIMPLE_RADIAL, f_med, W, H); c_.params = [f_med, W / 2, H / 2, 0.0]; cams[(W, H)] = c_
        camof = lambda n: cams[WH(n)]
    eo2 = pycolmap.AbsolutePoseEstimationOptions(); eo2.estimate_focal_length = False; eo2.ransac.max_error = a.max_fehler
    rec = ref0
    for c_ in cams.values(): rec.add_camera_with_trivial_rig(c_)
    neu = {}; ergeb = {}; runde_von = {}; tri_dir = os.path.join(a.aus, "tri_runden")
    for runde in range(1, a.runden + 1):
        offen = [n for n in names if n not in neu]; neue_in_runde = 0
        for n in offen:
            idx, xy, pid, je = C0[n] if runde == 1 else korrespondenzen(db, rec, name2id, name2id[n])
            ergeb[n] = dict(status="zu wenige Korrespondenzen", n_korr=len(idx), referenzbilder=len(je))
            if GK: ergeb[n].update(kamera_gruppe=zuord[n][0], zoomstatus=zuord[n][1])
            if len(idx) < 12: continue
            P3 = np.array([rec.points3D[p].xyz for p in pid]); r = pycolmap.estimate_and_refine_absolute_pose(xy, P3, camof(n), eo2)
            if r is None or r["num_inliers"] < a.min_inlier:
                ergeb[n]["status"] = "PnP gescheitert/zu wenige Inlier"; ergeb[n]["inlier"] = 0 if r is None else int(r["num_inliers"]); continue
            mask = np.asarray(r["inlier_mask"], bool); inl = [int(i) for i in np.array(idx)[mask]]; kp = db.read_keypoints(name2id[n])[:, :2]; 
            im = pycolmap.Image(n, pycolmap.Point2DList([pycolmap.Point2D(p) for p in kp]), camof(n).camera_id, name2id[n])
            rec.add_image_with_trivial_frame(im, r["cam_from_world"]); neu[n] = name2id[n]; runde_von[n] = runde; neue_in_runde += 1
            pm = {i: p for i, p in zip(idx, pid)}
            for i in inl: rec.add_observation(pm[i], pycolmap.TrackElement(neu[n], i))
            ergeb[n].update(status="registriert", inlier=int(r["num_inliers"]), runde=runde, inlier_idx=inl)
            if GK: ergeb[n].update(kamera_gruppe=zuord[n][0], zoomstatus=zuord[n][1])
        print(f"Runde {runde}: +{neue_in_runde} (gesamt {len(neu)}/{len(names)})", flush=True)
        if neue_in_runde == 0 or runde == a.runden: break
        shutil.rmtree(tri_dir, ignore_errors=True); os.makedirs(tri_dir)                       # neue 3D-Punkte aus allen Posen (Referenz + neu), vorhandene bleiben
        db.close(); rec = pycolmap.triangulate_points(rec, dbp, os.path.join(a.aus, "bilder"), tri_dir, clear_points=False); db = pycolmap.Database.open(dbp)
        for c_ in cams.values():       # triangulate_points behaelt nur Kameras/Rigs mit registrierten Bildern: Gruppen ohne Bild bis jetzt (z.B. 1 Zoom-Bild) wieder anlegen (Register DG)
            if not rec.exists_camera(c_.camera_id): rec.add_camera_with_trivial_rig(c_)
    # Buendel: nur Posen der neuen Bilder variabel; Punkte und Referenzbilder fest
    cfg = pycolmap.BundleAdjustmentConfig()
    for n, iid in neu.items(): cfg.add_image(iid)
    pts = set()
    for n, iid in neu.items():
        for p in rec.images[iid].points2D:
            if p.has_point3D(): pts.add(p.point3D_id)
    for p in pts: cfg.add_constant_point(p)
    bo = pycolmap.BundleAdjustmentOptions(); bo.refine_focal_length = bool(a.kalibrieren); bo.refine_extra_params = bool(a.kalibrieren); bo.refine_principal_point = False; bo.refine_points3D = False
    if not a.kalibrieren:
        for c_ in cams.values(): cfg.set_constant_cam_intrinsics(c_.camera_id)
    if neu: pycolmap.create_default_bundle_adjuster(bo, cfg, rec).solve()
    fehler = []
    for n, iid in neu.items():
        im = rec.images[iid]; e = []
        for p in im.points2D:
            if not p.has_point3D(): continue
            q = im.project_point(rec.points3D[p.point3D_id].xyz)
            if q is not None: e.append(float(np.linalg.norm(np.asarray(q) - p.xy)))
        ergeb[n]["reproj_mittel_px"] = float(np.mean(e)) if e else None; ergeb[n]["n_beob"] = len(e); ergeb[n]["zentrum"] = [float(x) for x in im.projection_center()]; ergeb[n].pop("inlier_idx", None); fehler += e
    reg_c = np.array([i.projection_center() for i in ref0.images.values() if i.has_pose and i.name not in V["bilder"]]) if False else np.array([i.projection_center() for i in rec.images.values() if i.has_pose and i.name not in neu])
    for n in neu:
        c = np.array(ergeb[n]["zentrum"]); ergeb[n]["naechste_referenzkamera_m"] = float(np.linalg.norm(reg_c - c, axis=1).min())
    outd = os.path.join(a.aus, "sparse_handy", "0"); os.makedirs(outd, exist_ok=True); rec.write(outd)
    bericht = dict(registriert=len(neu), von=len(names), f_fest_px=f_med, f_streu_px=f_streu, runden=a.runden, kalibriert_im_buendel=bool(a.kalibrieren),
                   reproj_mittel_px=float(np.mean(fehler)) if fehler else None, reproj_median_px=float(np.median(fehler)) if fehler else None, n_beobachtungen=len(fehler),
                   kameras_json=a.kameras, zoom_json=a.zoom, kamera_gruppen=({g: dict(n=len(e["namen"]), f_px=e["params"][0], cx=e["params"][1], cy=e["params"][2], k1=e["params"][3], f_orig=e["f_orig"]) for g, e in GK.items()} if GK else None),
                   max_fehler_pnp_px=a.max_fehler, min_inlier=a.min_inlier, bilder=ergeb)
    json.dump(bericht, open(os.path.join(a.aus, "registrierung.json"), "w"), indent=1)
    print(f"registriert {len(neu)}/{len(names)}, Reproj mittel {bericht['reproj_mittel_px']:.2f} px, median {bericht['reproj_median_px']:.2f} px")


def luecken(a):
    """Neue Punkte = Punkte der erweiterten Rekonstruktion (sparse_handy/0), die es in der Referenz NICHT gab, Spur >= 3 Bilder, mindestens 1 neues Bild.
    Luecke = neuer Punkt weiter als --abstand von jedem Punkt der vorhandenen dichten Wolke (kd-Baum). Aufteilung je Serie (Bildname h_<serie>_nn)."""
    import pycolmap
    from scipy.spatial import cKDTree
    rec = pycolmap.Reconstruction(os.path.join(a.aus, "sparse_handy", "0")); ref = pycolmap.Reconstruction(a.sparse)
    V = json.load(open(os.path.join(a.aus, "vorbereitet.json"))); neu = {i.image_id: i.name for i in rec.images.values() if i.name in V["bilder"] and i.has_pose}
    alt = set(ref.points3D.keys()); P = []; ser = []
    for pid, p in rec.points3D.items():
        if pid in alt or p.track.length() < 3: continue
        ns = [neu[t.image_id] for t in p.track.elements if t.image_id in neu]
        if not ns: continue
        P.append(p.xyz); ser.append(collections.Counter(n.split("_")[1] for n in ns).most_common(1)[0][0])
    P = np.array(P); ser = np.array(ser); D = np.load(a.dicht_npy); D = D[:, :3] if D.ndim == 2 else D
    d, _ = cKDTree(D).query(P); L = d > a.abstand
    rot = dict(punkte_referenz=len(alt), punkte_gesamt_nach=len(rec.points3D), neue_punkte_ge3=int(len(P)), dichte_wolke=int(len(D)), schwelle_m=a.abstand, neu_ausserhalb_dicht=int(L.sum()), anteil_ausserhalb=float(L.mean()) if len(P) else None)
    rot["je_serie"] = {s: dict(neu=int((ser == s).sum()), ausserhalb=int(((ser == s) & L).sum())) for s in sorted(set(ser))}
    if L.any():
        g = P[L]; rot["bbox_luecke"] = [g.min(0).round(2).tolist(), g.max(0).round(2).tolist()]; rot["z_histogramm_2m"] = {str(int(k)): int(v) for k, v in zip(*np.unique(np.floor(g[:, 2] / 2) * 2, return_counts=True))}
    np.save(os.path.join(a.aus, "neu_punkte.npy"), P); np.save(os.path.join(a.aus, "neu_serie.npy"), ser); np.save(os.path.join(a.aus, "neu_luecke_maske.npy"), L)
    json.dump(rot, open(os.path.join(a.aus, "luecken.json"), "w"), indent=1); print(json.dumps(rot, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("vorbereiten"); p.add_argument("--fotos", nargs="+", required=True); p.add_argument("--aus", required=True); p.add_argument("--ausschluss"); p.add_argument("--unten", type=float, default=0.05, help="Anteil unten abschneiden (Wasserzeichen)"); p.add_argument("--breite", type=int, default=2000, help="Zielbreite; 0 = keine Skalierung")
    p = sp.add_parser("merkmale"); p.add_argument("--ref-db", required=True); p.add_argument("--sparse", required=True); p.add_argument("--aus", required=True); p.add_argument("--f-px", type=float, default=1444.0, help="ANNAHME: ~25 mm KB-Aequivalent bei 2000 px Breite (EXIF f=5,25 mm, Sensorbreite unbekannt); nur Startwert")
    p = sp.add_parser("registrieren"); p.add_argument("--sparse", required=True); p.add_argument("--aus", required=True); p.add_argument("--je-bild", action="store_true", help="jedes Bild eigene Kamera, Brennweite je Bild aus PnP (Webfotos gemischter Formate)"); p.add_argument("--kameras", help="JSON mit festen Kameras je Gruppe (Format x Zoom): f_orig, k1, cx_rel, cy_rel; ersetzt den Kalibrierlauf"); p.add_argument("--zoom", help="zoom_verdacht.json (Klasse gezoomt/normal je Bild)"); p.add_argument("--kalibrieren", action="store_true", help="f und k1 im Buendel der neuen Posen frei (gemeinsame Kamera)")
    p.add_argument("--max-fehler", type=float, default=4.0); p.add_argument("--runden", type=int, default=4, help="Registrierrunden; nach jeder Runde Triangulation der neuen Posen (neue 3D-Punkte fuer noch offene Bilder)"); p.add_argument("--min-inlier", type=int, default=30)
    p = sp.add_parser("luecken"); p.add_argument("--sparse", required=True); p.add_argument("--dicht-npy", required=True); p.add_argument("--aus", required=True); p.add_argument("--abstand", type=float, default=0.3)
    a = ap.parse_args(argv); {"vorbereiten": vorbereiten, "merkmale": merkmale, "registrieren": registrieren, "luecken": luecken}[a.cmd](a); return 0


if __name__ == "__main__": sys.exit(main())
