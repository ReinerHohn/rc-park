#!/usr/bin/env python3
"""handy_kalibrieren.py - Brennweite f (und k1) der Handykamera je Formatgruppe unabhaengig bestimmen, mit Unsicherheit (Register DB).

Hintergrund (Register DA): f fest 1413,6 px (SIFT) / 1421,9 px (LG) - ein f-Fehler von 2 % verschiebt die Kameras systematisch um ~0,6 m.
Drei voneinander unabhaengige Wege, KEIN Massstab aus dem Modell:
  exif     : EXIF-Brennweite (mm) der Originalfotos + Bildgroessen -> Pixel-f nur mit Sensorbreite; hier umgekehrt: aus f_px abgeleitete
             Sensorbreite muss zu einem plausiblen Sensor passen (Plausibilitaet, KEIN Messwert). Crop unten (5 %) -> Hauptpunkt cy.
  korr     : 2D-3D-Korrespondenzen Handybild -> Referenzpunkte (feste Referenzpunkte aus sparse_buendel/0) aus den verifizierten Matches der DB.
  mit_ref  : f, k1 (SIMPLE_RADIAL) gemeinsam fuer eine Bildgruppe, Referenzpunkte FEST, Posen frei (robuste kleinste Quadrate, Mehrfachstart in f).
             Bootstrap ueber Bilder; Streuung je Serie getrennt.
  ohne_ref : nur Handybilder untereinander (COLMAP-Mapper auf kleiner Teil-Datenbank, f/k1 frei), ohne Referenzpunkte/-posen.
Nur Lesen der Rekonstruktionen/DB; schreibt kleine JSON/NPZ. Reine Funktionen (modell_residuen, fit_gruppe) sind synthetisch testbar
(tools/test_handy_kalibrieren.py). Aufruf mit /media/oem/scan/venv-colmap/bin/python -I.
"""
import sys, os, json, argparse, glob, math
import numpy as np

HANDY = "/media/oem/scan/rc-park_null/kaufhaus_handy"
REF = "/media/oem/scan/rc-park_null/kaufhaus_null4/sfm/sparse_buendel/0"
CROP_UNTEN = 0.05          # vorbereiten: unten 5 % abgeschnitten (Wasserzeichen)


# ---------- reine Funktionen ----------
def rotmat(rv):
    """rv (M,3) Rotationsvektoren -> (M,3,3) (Rodrigues, vektorisiert)."""
    rv = np.atleast_2d(rv); th = np.linalg.norm(rv, axis=1)
    k = np.where(th[:, None] > 1e-12, rv / np.maximum(th[:, None], 1e-12), 0.0)
    K = np.zeros((len(rv), 3, 3)); K[:, 0, 1] = -k[:, 2]; K[:, 0, 2] = k[:, 1]; K[:, 1, 0] = k[:, 2]
    K[:, 1, 2] = -k[:, 0]; K[:, 2, 0] = -k[:, 1]; K[:, 2, 1] = k[:, 0]
    s = np.sin(th)[:, None, None]; c = np.cos(th)[:, None, None]
    return np.eye(3)[None] + s * K + (1 - c) * (K @ K)


def rotvec(R):
    from scipy.spatial.transform import Rotation
    return Rotation.from_matrix(R).as_rotvec()


def projiziere(f, k1, cx, cy, rv, t, idx, X, skala=None):
    """SIMPLE_RADIAL wie COLMAP; Pixel (n,2) + Tiefe. rv,t je Bild (M,3), idx: Bildindex je Beobachtung.
    cx, cy: Skalar oder je Bild (M,); skala (M,) optional: f_Bild = f * skala (gemeinsames f in Originalpixeln fuer Bilder verschiedener Verkleinerung)."""
    R = rotmat(rv)
    cx = np.asarray(cx, float); cy = np.asarray(cy, float)
    cx = cx[idx] if cx.ndim else cx; cy = cy[idx] if cy.ndim else cy
    if skala is not None:
        f = f * np.asarray(skala, float)[idx]
    Xc = np.einsum("nij,nj->ni", R[idx], X) + t[idx]
    z = Xc[:, 2]; x = Xc[:, 0] / z; y = Xc[:, 1] / z
    d = 1.0 + k1 * (x * x + y * y)
    return np.stack([f * x * d + cx, f * y * d + cy], 1), z


def fit_gruppe(uv, X, idx, M, cx, cy, rv0, t0, f0, k1_0=0.0, frei=("f", "k1"), cy_frei=False, f_scale=1.5, skala=None):
    """Gemeinsames f,k1 (+ optional cy) fuer M Bilder; Punkte X fest; Posen frei. Robust (soft_l1). Rueckgabe dict."""
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix
    n = len(X); ng = 3                       # globale Parameter: f, k1, cy-Versatz
    def unpack(p):
        return p[0], p[1], p[2], p[ng:ng + 3 * M].reshape(M, 3), p[ng + 3 * M:].reshape(M, 3)
    maske = np.array([("f" in frei), ("k1" in frei), bool(cy_frei)])
    p0 = np.concatenate([[f0, k1_0, 0.0], rv0.ravel(), t0.ravel()])
    def res(q):
        p = p0.copy(); p[:ng][maske] = q[:int(maske.sum())]; p[ng:] = q[int(maske.sum()):]
        f, k1, dcy, rv, t = unpack(p)
        u, z = projiziere(f, k1, cx, cy + dcy, rv, t, idx, X, skala)
        r = (u - uv); r[z <= 0.1] = 1e3
        return r.ravel()
    ngl = int(maske.sum()); q0 = np.concatenate([p0[:ng][maske], p0[ng:]])
    S = lil_matrix((2 * n, ngl + 6 * M), dtype=int)
    for j in range(ngl):
        S[:, j] = 1
    rows = np.arange(n)
    for i_ in range(3):
        S[2 * rows, ngl + 3 * idx + i_] = 1; S[2 * rows + 1, ngl + 3 * idx + i_] = 1
        S[2 * rows, ngl + 3 * M + 3 * idx + i_] = 1; S[2 * rows + 1, ngl + 3 * M + 3 * idx + i_] = 1
    # Skalierung: f ~1e3, k1 ~1e-1, cy ~1e1, Rotation ~1e-1, t ~1e0
    xs = np.concatenate([[1e3, 0.1, 10.0][i] * np.ones(1) for i in range(3) if maske[i]] + [0.1 * np.ones(3 * M), 1.0 * np.ones(3 * M)])
    sol = least_squares(res, q0, jac_sparsity=S, loss="soft_l1", f_scale=f_scale, x_scale=xs, method="trf", max_nfev=100, ftol=1e-8, xtol=1e-8, gtol=1e-8)
    q = sol.x; p = p0.copy(); p[:ng][maske] = q[:ngl]; p[ng:] = q[ngl:]
    f, k1, dcy, rv, t = unpack(p)
    u, z = projiziere(f, k1, cx, cy + dcy, rv, t, idx, X, skala)
    e = np.linalg.norm(u - uv, axis=1)
    return dict(f=float(f), k1=float(k1), dcy=float(dcy), rv=rv, t=t, fehler_px=e, kosten=float(sol.cost), tiefe=z, ok=bool(sol.success))


def inlier_wahl(e, schwelle):
    return e < schwelle


def zentren(rv, t):
    R = rotmat(rv)
    return -np.einsum("mji,mj->mi", R, t)


# ---------- EXIF ----------
def exif_info(ordner, vorb_json):
    from PIL import Image
    from PIL.ExifTags import TAGS
    V = json.load(open(vorb_json))["bilder"]
    gruppen = {}
    for n, v in V.items():
        gruppen.setdefault((tuple(v["orig"]), tuple(v["bild"]), round(v["skala"], 4)), []).append(n)
    fl = {}; model = set(); fo = set()
    for f in sorted(glob.glob(os.path.join(ordner, "*"))):
        try:
            im = Image.open(f); ex = im.getexif(); ei = ex.get_ifd(0x8769)
        except Exception:
            continue
        tags = {TAGS.get(k, k): v for k, v in list(ex.items()) + list(ei.items())}
        if "FocalLength" in tags:
            fl[os.path.basename(f)] = float(tags["FocalLength"])
        model.add((str(tags.get("Make")), str(tags.get("Model")))); fo.add(float(tags.get("FocalLengthIn35mmFilm", 0) or 0))
    return dict(gruppen={f"orig{k[0]}->bild{k[1]}@{k[2]}": len(v) for k, v in gruppen.items()}, brennweiten_mm=sorted(set(fl.values())),
                n_exif=len(fl), kamera=sorted(model), f35_in_exif=sorted(fo))


# ---------- Korrespondenzen (Handy -> feste Referenzpunkte) ----------
def korrespondenzen_sammeln(db_pfad, sparse_ref, bilder, min_ref_track=3, max_ref_err=1.5):
    """bilder: Namen. Je Bild alle 2D-3D aus verifizierten Matches (haeufigste Punkt-ID je Schluesselpunkt); nur Referenzpunkte mit
    mind. min_ref_track Beobachtern und kleinem Referenz-Reprojektionsfehler. Verwendet Matches der DB, NICHT die PnP-Inlier der Registrierung."""
    import pycolmap, sqlite3
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import zusatzfotos_registrieren as zr
    ref = pycolmap.Reconstruction(sparse_ref); db = pycolmap.Database.open(db_pfad)
    con = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True); name2id = {n: i for i, n in con.execute("select image_id,name from images")}; con.close()
    ok_pt = {pid for pid, p in ref.points3D.items() if p.track.length() >= min_ref_track and p.error <= max_ref_err}
    out = {}
    for n in bilder:
        if n not in name2id:
            continue
        idx, xy, pid, je = zr.korrespondenzen(db, ref, name2id, name2id[n])
        keep = [i for i, p in enumerate(pid) if p in ok_pt]
        if len(keep) < 30:
            continue
        out[n] = dict(uv=np.asarray(xy)[keep], X=np.array([ref.points3D[pid[i]].xyz for i in keep]), pid=np.array([pid[i] for i in keep]))
    db.close()
    return out


def gruppen_aus(korr, ausw):
    """Arrays fuer fit_gruppe aus dict{name:{uv,X}} und Namensliste."""
    uv = []; X = []; idx = []
    for i, n in enumerate(ausw):
        uv.append(korr[n]["uv"]); X.append(korr[n]["X"]); idx.append(np.full(len(korr[n]["uv"]), i))
    return np.concatenate(uv), np.concatenate(X), np.concatenate(idx)


def geo_von(V, namen, cy_modus="phys"):
    """Je Bild (W,H,skala,cx,cy). f wird in ORIGINALpixeln gefuehrt (f_Bild = f_orig * skala), damit Hoch- und Querformat dieselbe Linse teilen.
    cy_modus 'phys': Hauptpunkt = Mitte des Originalbilds (unten 5 % wurden abgeschnitten -> cy = H/(1-CROP)/2); 'mitte': H/2 (wie bisherige Registrierung)."""
    g = {}
    for n in namen:
        W, H = V[n]["bild"]; sk = V[n]["skala"]
        g[n] = (W, H, sk, W / 2.0, (H / (1 - CROP_UNTEN) / 2.0) if cy_modus == "phys" else H / 2.0)
    return g


def start_posen(uv, X, idx, M, fbild, geo_liste, schwelle=6.0):
    """Anfangsposen je Bild per RANSAC-PnP bei festem f (fbild je Bild)."""
    import pycolmap
    rv = np.zeros((M, 3)); t = np.zeros((M, 3)); nin = np.zeros(M, int); gut = np.zeros(M, bool)
    for i in range(M):
        m = idx == i; W, H, sk, cx, cy = geo_liste[i]
        cam = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, fbild[i], W, H); cam.params = [fbild[i], cx, cy, 0.0]
        eo = pycolmap.AbsolutePoseEstimationOptions(); eo.estimate_focal_length = False; eo.ransac.max_error = schwelle; eo.ransac.random_seed = 0
        r = pycolmap.estimate_and_refine_absolute_pose(uv[m], X[m], cam, eo)
        if r is None:
            continue
        cw = r["cam_from_world"]; rv[i] = rotvec(cw.rotation.matrix()); t[i] = np.array(cw.translation); nin[i] = r["num_inliers"]; gut[i] = nin[i] >= 30
    return rv, t, nin, gut


def kalibriere_gruppe(korr, namen, geo, f_starts=(2400, 2800, 3200, 3800), schwellen=(8.0, 4.0, 3.0), frei=("f", "k1"), cy_frei=False):
    """Gemeinsames f_orig (+k1) fuer die Bilder 'namen'. Mehrfachstart in f; je Start: PnP bei f0 -> Fit -> Inlier neu waehlen
    (kleiner werdende Schwelle) -> Fit. Beste = kleinster RMS der Inlier (Startvergleich bleibt sichtbar in 'laeufe')."""
    namen = [n for n in namen if n in korr]
    if len(namen) < 3:
        return None
    uv, X, idx = gruppen_aus(korr, namen); M = len(namen)
    gl = [geo[n] for n in namen]; sk = np.array([g[2] for g in gl]); cx = np.array([g[3] for g in gl]); cy = np.array([g[4] for g in gl])
    laeufe = []
    for f0 in f_starts:
        rv, t, nin, gut = start_posen(uv, X, idx, M, f0 * sk, gl)
        if gut.sum() < 3:
            laeufe.append(dict(f_start=f0, ok=False)); continue
        mk = gut[idx]; sel = mk.copy(); k1 = 0.0; f = f0
        try:
            for s_ in schwellen:
                r = fit_gruppe(uv[sel], X[sel], idx[sel], M, cx, cy, rv, t, f, k1, frei=frei, cy_frei=cy_frei, skala=sk)
                f, k1, dcy, rv, t = r["f"], r["k1"], r["dcy"], r["rv"], r["t"]
                u_all, z_all = projiziere(f, k1, cx, cy + dcy, rv, t, idx, X, sk)
                sel = mk & (np.linalg.norm(u_all - uv, axis=1) < s_) & (z_all > 0)
            r = fit_gruppe(uv[sel], X[sel], idx[sel], M, cx, cy, rv, t, f, k1, frei=frei, cy_frei=cy_frei, skala=sk)
        except Exception as ex:                                              # Fehlstart nicht verschweigen
            laeufe.append(dict(f_start=f0, ok=False, fehler=str(ex))); continue
        e = r["fehler_px"]
        laeufe.append(dict(f_start=f0, ok=True, f=r["f"], k1=r["k1"], dcy=r["dcy"], n_beob=int(sel.sum()), rms_px=float(np.sqrt(np.mean(e ** 2))),
                           median_px=float(np.median(e)), kosten=r["kosten"], rv=r["rv"], t=r["t"], sel=sel))
    gut_l = [l for l in laeufe if l.get("ok")]
    if not gut_l:
        return dict(namen=namen, laeufe=laeufe, best=None)
    # Gemeinsame Beobachtungsmenge (Schnitt aller Starts): RMS verschiedener Inliermengen ist nicht vergleichbar (weniger Inlier = kleinerer RMS).
    # Jeder Start wird mit der gemeinsamen Menge nachgefittet; 'best' = kleinste robuste Kosten dort. Reste der Startabhaengigkeit stehen in 'laeufe'.
    gem = np.logical_and.reduce([l["sel"] for l in gut_l])
    if gem.sum() >= 100:
        for l in gut_l:
            try:
                r = fit_gruppe(uv[gem], X[gem], idx[gem], M, cx, cy, l["rv"], l["t"], l["f"], l["k1"], frei=frei, cy_frei=cy_frei, skala=sk)
            except Exception:
                continue
            e = r["fehler_px"]
            l.update(f=r["f"], k1=r["k1"], dcy=r["dcy"], rv=r["rv"], t=r["t"], sel=gem.copy(), n_beob=int(gem.sum()), rms_px=float(np.sqrt(np.mean(e ** 2))), median_px=float(np.median(e)), kosten=r["kosten"])
    best = min(gut_l, key=lambda l: l["kosten"])
    return dict(namen=namen, laeufe=laeufe, best=best, uv=uv, X=X, idx=idx, cx=cx, cy=cy, skala=sk)


def bootstrap(res, n_boot=100, seed=0, frei=("f", "k1"), cy_frei=False):
    """Bildweises Bootstrap ab der besten Loesung (feste Inlierauswahl, Start = Optimum); Streuung von f_orig, k1."""
    b = res["best"]; M = len(res["namen"])
    uv, X, idx = res["uv"], res["X"], res["idx"]; sel = b["sel"]
    rng = np.random.default_rng(seed); fs = []; ks = []
    for _ in range(n_boot):
        ziehe = rng.integers(0, M, M)
        uvb = []; Xb = []; ib = []; rv0 = []; t0 = []
        for j, i in enumerate(ziehe):
            m = (idx == i) & sel
            uvb.append(uv[m]); Xb.append(X[m]); ib.append(np.full(m.sum(), j)); rv0.append(b["rv"][i]); t0.append(b["t"][i])
        try:
            r = fit_gruppe(np.concatenate(uvb), np.concatenate(Xb), np.concatenate(ib), M, res["cx"][ziehe], res["cy"][ziehe], np.array(rv0), np.array(t0), b["f"], b["k1"],
                           frei=frei, cy_frei=cy_frei, skala=res["skala"][ziehe])
        except Exception:
            continue
        fs.append(r["f"]); ks.append(r["k1"])
    fs = np.array(fs); ks = np.array(ks)
    return dict(n=int(len(fs)), f_mittel=float(fs.mean()), f_std=float(fs.std(ddof=1)), f_q05=float(np.quantile(fs, .05)), f_q95=float(np.quantile(fs, .95)),
                k1_mittel=float(ks.mean()), k1_std=float(ks.std(ddof=1)))


def kurz(res, boot=None):
    if res is None:
        return None
    if res.get("best") is None:
        return dict(ok=False, laeufe=[{k: v for k, v in l.items() if k in ("f_start", "ok", "fehler")} for l in res["laeufe"]])
    b = res["best"]
    d = dict(ok=True, n_bilder=len(res["namen"]), f_orig_px=b["f"], k1=b["k1"], rms_px=b["rms_px"], median_px=b["median_px"], n_beob=b["n_beob"],
             starts=[{k: (round(v, 5) if isinstance(v, float) else v) for k, v in l.items() if k in ("f_start", "ok", "f", "k1", "rms_px", "n_beob")} for l in res["laeufe"]])
    if boot:
        d["bootstrap"] = boot
    return d


# ---------- Weg ohne Referenz: Mapper auf Teil-Datenbank ----------
def teil_db_bauen(quell_db, ziel_db, namen, geo, f_start):
    """Kopiert nur Schluesselpunkte und verifizierte Geometrien der gewaehlten Handybilder in eine kleine neue Datenbank
    (je Bildgroesse eine Kamera SIMPLE_RADIAL, f ohne Prior). KEINE Referenzbilder, keine Referenzpunkte. Bild-IDs behalten die Ordnung der Quelle."""
    import pycolmap, sqlite3
    if os.path.exists(ziel_db):
        os.remove(ziel_db)
    q = pycolmap.Database.open(quell_db); z = pycolmap.Database.open(ziel_db)
    con = sqlite3.connect(f"file:{quell_db}?mode=ro", uri=True); name2id = {n: i for i, n in con.execute("select image_id,name from images")}; con.close()
    ns = sorted([n for n in namen if n in name2id], key=lambda n: name2id[n]); cam_je = {}; neu_id = {}
    for n in ns:
        W, H = geo[n][0], geo[n][1]
        if (W, H) not in cam_je:
            c = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, f_start * geo[n][2], W, H)
            c.params = [f_start * geo[n][2], W / 2.0, H / 2.0, 0.0]; c.has_prior_focal_length = False
            cam_je[(W, H)] = z.write_camera(c)
        im = pycolmap.Image(); im.name = n; im.camera_id = cam_je[(W, H)]
        neu_id[n] = z.write_image(im); z.write_keypoints(neu_id[n], q.read_keypoints(name2id[n]))
    npaare = 0
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            try:
                g = q.read_two_view_geometry(name2id[a], name2id[b])
            except Exception:
                continue
            if np.asarray(g.inlier_matches).shape[0] < 15:
                continue
            z.write_two_view_geometry(neu_id[a], neu_id[b], g); npaare += 1
    q.close(); z.close()
    return neu_id, npaare


def mapper_lauf(db_pfad, bild_ordner, out_ordner, namen, seed=0):
    import pycolmap
    os.makedirs(out_ordner, exist_ok=True)
    opt = pycolmap.IncrementalPipelineOptions()
    opt.image_names = list(namen)
    opt.ba_refine_focal_length = True; opt.ba_refine_extra_params = True; opt.ba_refine_principal_point = False
    opt.min_num_matches = 15; opt.num_threads = 8; opt.random_seed = seed
    recs = pycolmap.incremental_mapping(db_pfad, bild_ordner, out_ordner, opt)
    return recs


# ---------- CLI ----------
def gruppe_waehlen(pv, V, serien, klassen, hochformat):
    out = []
    for n, b in pv.items():
        if b["serie"] not in serien or b.get("klasse") not in klassen:
            continue
        W, H = V[n]["bild"]
        if hochformat is not None and (H > W) != hochformat:
            continue
        out.append(n)
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("exif"); p.add_argument("--originale", default="/media/oem/scan/rc-park_daten/kaufhaus/fotos_eingang/handy_2026-11-06")
    p = sp.add_parser("korr"); p.add_argument("--db", default=HANDY + "/db.db"); p.add_argument("--aus", required=True); p.add_argument("--serien", default="a,b")
    p.add_argument("--klassen", default="sicher")
    p = sp.add_parser("mit_ref"); p.add_argument("--aus", required=True); p.add_argument("--boot", type=int, default=60); p.add_argument("--zoom-json", help="zoom_verdacht.json (fuer Zoomgruppen)")
    p = sp.add_parser("ohne_ref"); p.add_argument("--aus", required=True); p.add_argument("--arbeit", required=True); p.add_argument("--lauf", default="SIFT", choices=["SIFT", "LG"])
    p.add_argument("--teil", type=int, default=20, help="Anzahl Teilmengen-Ziehungen (75 %% der Bilder, ohne Zuruecklegen)"); p.add_argument("--serien", default="a,b"); p.add_argument("--klassen", default="sicher")
    a = ap.parse_args(argv)
    V = json.load(open(HANDY + "/vorbereitet.json"))["bilder"]; pv = json.load(open(HANDY + "/pose_vertrauen.json"))["bilder"]
    if a.cmd == "exif":
        print(json.dumps(exif_info(a.originale, HANDY + "/vorbereitet.json"), indent=1)); return 0
    ser = getattr(a, "serien", "a,b").split(","); kl = getattr(a, "klassen", "sicher").split(",")
    if a.cmd == "korr":
        namen = gruppe_waehlen(pv, V, ser, kl, None)
        k = korrespondenzen_sammeln(a.db, REF, namen)
        np.savez_compressed(a.aus, **{f"{n}__uv": v["uv"] for n, v in k.items()}, **{f"{n}__X": v["X"] for n, v in k.items()})
        print(len(k), "Bilder,", sum(len(v["uv"]) for v in k.values()), "Korrespondenzen"); return 0
    if a.cmd == "mit_ref":
        return mit_ref_cli(a, V, pv)
    if a.cmd == "ohne_ref":
        return ohne_ref_cli(a, V, pv, ser, kl)
    return 0


def _job(j):
    tag, cym, sn, ns, geo, k, starts, nboot = j
    r = kalibriere_gruppe(k, ns, geo, f_starts=starts)
    if r is None:
        return (tag, cym, sn, None)
    return (tag, cym, sn, kurz(r, bootstrap(r, nboot) if r["best"] else None))


def mit_ref_cli(a, V, pv):
    """f_orig, k1 mit festen Referenzpunkten: Gruppen aus Serie/Format/Zoom, beide Laeufe (SIFT: sparse_buendel/0, LG: lg/ref_tri), Hauptpunkt phys/mitte."""
    from multiprocessing import Pool
    namen = sorted(V); K = {}
    for tag, db, ref in [("SIFT", HANDY + "/db.db", REF), ("LG", HANDY + "/lg/db.db", HANDY + "/lg/ref_tri")]:
        K[tag] = korrespondenzen_sammeln(db, ref, namen, 2, 2.0)
    zj = json.load(open(a.zoom_json))["bilder"] if a.zoom_json else {}
    hoch = lambda n: V[n]["bild"][1] > V[n]["bild"][0]
    sicher = lambda n: pv[n].get("klasse") == "sicher" and pv[n]["serie"] in ("a", "b")
    jobs = []
    for tag, k in K.items():
        for cym in ("phys", "mitte"):
            geo = geo_von(V, list(k), cym)
            sets = {"sicher_ab_quer+hoch": [n for n in k if sicher(n)], "sicher_ab_quer": [n for n in k if sicher(n) and not hoch(n)],
                    "sicher_ab_hoch": [n for n in k if sicher(n) and hoch(n)],
                    "serie_a_quer": [n for n in k if pv[n]["serie"] == "a" and sicher(n) and not hoch(n)],
                    "serie_b_quer": [n for n in k if pv[n]["serie"] == "b" and sicher(n) and not hoch(n)],
                    "serie_b_hoch": [n for n in k if pv[n]["serie"] == "b" and sicher(n) and hoch(n)]}
            sets["zoom_serie_j"] = [n for n in k if pv[n]["serie"] == "j" and zj.get(n, {}).get("klasse") == "gezoomt"]      # Einzelserien g,i,f: zu wenig Punkte, k1 entartet
            sets["zoom_alle"] = [n for n in k if zj.get(n, {}).get("klasse") == "gezoomt"]
            for sn, ns in sets.items():
                if len(ns) < 5:
                    continue
                if cym == "mitte" and not (sn.startswith("sicher") or sn in ("zoom_alle", "zoom_serie_j")):
                    continue
                st = (7500, 9000, 10500, 12000) if sn.startswith("zoom") else (2400, 2800, 3200, 3800)
                jobs.append((tag, cym, sn, ns, geo, k, st, a.boot))
    with Pool(10) as p:
        out = p.map(_job, jobs, chunksize=1)
    json.dump([dict(lauf=t, hauptpunkt=c, gruppe=g, ergebnis=d) for t, c, g, d in out], open(a.aus, "w"), indent=1, default=float)
    for t, c, g, d in out:
        if d and d.get("ok"):
            bb = d.get("bootstrap", {})
            print(t, c, g, "n=%d f_orig=%.0f k1=%.3f rms=%.2f boot f+-%.0f k1+-%.3f starts=%s" % (d["n_bilder"], d["f_orig_px"], d["k1"], d["rms_px"], bb.get("f_std", 0), bb.get("k1_std", 0), [round(x["f"]) for x in d["starts"] if x["ok"]]))
        else:
            print(t, c, g, "kein Ergebnis")
    return 0


def ohne_ref_cli(a, V, pv, ser, kl):
    """Mapper nur mit Handybildern (keine Referenz); Gesamtmenge + Teilmengen-Bootstrap; f je Format-Kamera in Originalpixeln."""
    import shutil
    dbq = {"SIFT": HANDY + "/db.db", "LG": HANDY + "/lg/db.db"}[a.lauf]
    namen = gruppe_waehlen(pv, V, ser, kl, None); geo = geo_von(V, list(V), "mitte"); rng = np.random.default_rng(0)
    os.makedirs(a.arbeit, exist_ok=True); lauf = []
    for j in range(a.teil + 1):
        ns = namen if j == 0 else sorted(rng.choice(namen, int(0.75 * len(namen)), replace=False).tolist())
        db = os.path.join(a.arbeit, "teil.db"); teil_db_bauen(dbq, db, ns, geo, 2800.)
        out = os.path.join(a.arbeit, "map"); shutil.rmtree(out, ignore_errors=True)
        recs = mapper_lauf(db, HANDY + "/bilder", out, ns)
        if not recs:
            continue
        rec = max(recs.values(), key=lambda r: r.num_reg_images()); je = {}
        for i in rec.images.values():
            if i.has_pose:
                c = rec.cameras[i.camera_id]; je.setdefault("hoch" if c.height > c.width else "quer", []).append((c.params[0] / V[i.name]["skala"], c.params[3]))
        lauf.append(dict(teil=j, n_bilder=len(ns), n_reg=rec.num_reg_images(), reproj=float(rec.compute_mean_reprojection_error()),
                         f_orig={k: v[0][0] for k, v in je.items()}, k1={k: v[0][1] for k, v in je.items()}, n={k: len(v) for k, v in je.items()}))
    shutil.rmtree(os.path.join(a.arbeit, "map"), ignore_errors=True)
    ges = lauf[0] if lauf and lauf[0]["teil"] == 0 else None; zus = {}
    for fm in ("quer", "hoch"):
        fs = np.array([l["f_orig"][fm] for l in lauf[1:] if fm in l["f_orig"]]); ks = np.array([l["k1"][fm] for l in lauf[1:] if fm in l["k1"]])
        if len(fs) > 2:
            zus[fm] = dict(n=len(fs), f_mittel=float(fs.mean()), f_std=float(fs.std(ddof=1)), f_median=float(np.median(fs)), k1_mittel=float(ks.mean()), k1_std=float(ks.std(ddof=1)))
    json.dump(dict(lauf=a.lauf, gesamt=ges, teilmengen=zus, einzel=lauf), open(a.aus, "w"), indent=1)
    print(json.dumps(dict(gesamt=ges, teilmengen=zus), indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
