#!/usr/bin/env python3
"""sfm_lod2_ausrichten.py - GENERISCH: SfM-Netz OHNE Handpicks an die amtliche Umgebung ausrichten (LoD2-Gebaeude + DGM1-Gelaende).

Kaltstart-Ersatz fuer sfm_ausrichten.py (das braucht gepickte LoD2-Eckkanten in K-*.json; ein neues Objekt hat keine; Plan B7).
Gesucht: Aehnlichkeit X_sfm = s * R @ X_modell + t (7 Parameter), Modellsystem = anker3d.json/objekt.json rahmen.
  1. Lot: Strassenfotos liegen fast in einer Ebene (Kamerazentren) -> Normale = Lot; Vorzeichen: die Mehrzahl der Punkte liegt UEBER den Kameras.
  2. Grob (2D): Netzpunkte waagrecht projizieren; Ziel = Wandlinien ALLER LoD2-Gebaeude im Umkreis (die Wolke enthaelt die Nachbarfassaden -
     die machen die Loesung eindeutig). Gittersuche Drehung x Massstab, Verschiebung je Paar per FFT-Korrelation.
  3. Fein (3D): Punkt-zu-Flaeche-Ausgleich (7 Parameter, getrimmt) gegen abgetastete LoD2-Waende/-Daecher und DGM1-Boden.
  4. Guete: Massstab-Sigma aus Teilstichproben (Bootstrap), Inlier-Anteil, Abstands-RMS, Kamerahoehen (Strassenfotos ~1,5-2 m: nur Pruefung).
Quellen-Blindheit: LoD2 kennt keine Aufbauten/Erker/Arkadentiefe -> Punkte dort sind Ausreisser (Trimmung), nicht Fehler der Ausrichtung.
Schreibt dasselbe Format wie sfm_ausrichten.py: messprotokoll/SFM-AUSRICHTUNG-<name>.json, sfm/sparse_modell_<name>, sfm/punkte_modell_<name>.npy.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_lod2_ausrichten.py modelle/<objekt>/objekt.json --sparse <pfad> --name <name> [--schreiben] [--radius 80]
"""
import sys, os, json, glob, math, argparse, numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import pycolmap
except ImportError:  # GPU-Umgebung: Kameras kommen aus --kameras
    pycolmap = None


def lod2_ziel(obj, radius, dichte=0.35):
    """LoD2-Flaechen (alle Gebaeude im Umkreis) im Modellsystem, abgetastet: Punkte, Normalen, Typ (0 Wand, 1 Dach)."""
    import lod2_gebaeude as LG
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"]); gel = R["gelaende"]
    gml = obj["lod2"]["gml"]
    # Cache: das Einlesen des amtlichen GML ist reines Textparsen (~2 min). Schluessel: Datei (Groesse, Zeit), Mitte, Radius.
    import pickle, hashlib
    st = os.stat(gml); schl = hashlib.sha1(f"{gml}|{st.st_size}|{int(st.st_mtime)}|{c0.tolist()}|{radius}".encode()).hexdigest()[:16]
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modelle", ".cache_lod2"); os.makedirs(cache_dir, exist_ok=True)
    cpfad = os.path.join(cache_dir, f"lod2_{schl}.pkl")
    if os.path.exists(cpfad):
        picked = pickle.load(open(cpfad, "rb")); print("LOD2: aus Cache", os.path.basename(cpfad), flush=True)
    else:
        picked = LG.extract(gml, center=tuple(c0), radius=radius)
        pickle.dump(picked, open(cpfad, "wb")); print("LOD2: eingelesen und gecacht", os.path.basename(cpfad), flush=True)
    lok = lambda P: np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - gel]
    pts, nrm, typ, wand2d, grund2d, eigen = [], [], [], [], [], []
    rng = np.random.default_rng(0)
    if os.environ.get("AUSR_NUR_ZIEL") == "1":   # nur das Torgebaeude als Ziel (keine Nachbarn)
        picked = [(m, pl) for m, pl in picked if m.get("id") == obj["lod2"].get("id")]
        print(f"AUSR_NUR_ZIEL: {len(picked)} Gebaeude (nur {obj['lod2'].get('id')})", flush=True)
    for meta, polys in picked:
        for t, P in polys:
            if t == "GroundSurface": grund2d.append(lok(P)[:, :2])
            if t not in ("WallSurface", "RoofSurface"): continue
            Q = lok(P); n = np.cross(Q[1] - Q[0], Q[2] - Q[0])
            for i in range(2, len(Q) - 1): n = n if np.linalg.norm(n) > 1e-6 else np.cross(Q[i] - Q[0], Q[i + 1] - Q[0])
            if np.linalg.norm(n) < 1e-9: continue
            n = n / np.linalg.norm(n)
            for i in range(1, len(Q) - 1):                                                    # Faecher-Dreiecke, flaechentreu abgetastet
                a, b, c = Q[0], Q[i], Q[i + 1]; A = 0.5 * np.linalg.norm(np.cross(b - a, c - a)); k = max(1, int(A / dichte ** 2))
                u = rng.random((k, 2)); f = u.sum(1) > 1; u[f] = 1 - u[f]
                pts.append(a + u[:, :1] * (b - a) + u[:, 1:] * (c - a)); nrm.append(np.repeat(n[None], k, 0)); typ.append(np.full(k, 0 if t == "WallSurface" else 1))
                eigen.append(np.full(k, meta.get("id") == obj["lod2"].get("id")))
            if t == "WallSurface": wand2d.append(Q[:, :2])
    return np.vstack(pts), np.vstack(nrm), np.concatenate(typ), wand2d, grund2d, len(picked), np.concatenate(eigen)


def dgm_ziel(obj, halb):
    """DGM1-Boden im Modellsystem (Punkte, Normale nach oben); fehlt die Kachel: Ebene z = 0 (ANNAHME)."""
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    ek, nk = int(c0[0] // 1000), int(c0[1] // 1000)
    f = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/dgm1_32_{ek}_{nk}_1_bw_*.xyz", recursive=True)
    if f:
        g = np.loadtxt(f[0]); L = np.c_[(g[:, :2] - c0) @ xh, (g[:, :2] - c0) @ yh, g[:, 2] - R["gelaende"]]
        L = L[(np.abs(L[:, 0]) < halb) & (np.abs(L[:, 1]) < halb)]; quelle = os.path.basename(f[0])
    else:
        xx, yy = np.meshgrid(np.arange(-halb, halb, 1.0), np.arange(-halb, halb, 1.0)); L = np.c_[xx.ravel(), yy.ravel(), np.zeros(xx.size)]; quelle = "ANNAHME Ebene z=0 (keine DGM1-Kachel)"
    return L, np.repeat([[0, 0, 1.0]], len(L), 0), quelle


GPS_KAM = []   # (Kameraindex, UTM) aus gps_massstab - fuer den GPS-Startkandidaten


def gps_massstab(ims, C, obj, od, fotos=""):
    """Massstab SfM-Einheiten je m aus Foto-GPS (EXIF): Median der Verhaeltnisse Kameraabstand SfM / GPS fuer Paare > 15 m GPS-Abstand.
    Unabhaengig von LoD2 und von weit entfernten Wolkenteilen. None bei < 15 Kameras mit GPS."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gps_ausrichtung import gps_exif; from bilder_holen import wgs84_zu_utm
    except Exception as e: print("GPS-Massstab: Hilfsmodule fehlen:", type(e).__name__); return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ds = [d for d in (fotos, obj.get("fotos_dir", "")) if d]; ds = [d if os.path.isabs(d) else os.path.join(root, d) for d in ds]
    U, X = [], []; GPS_KAM.clear()
    for _i, (im, c) in enumerate(zip(ims, C)):
        nm = os.path.splitext(os.path.basename(im.name))[0]; kand = [nm] + ([nm.split("__", 1)[1]] if "__" in nm else [])
        hit = [p for d in ds for n_ in kand for p in glob.glob(os.path.join(d, glob.escape(n_) + ".*")) if p.lower().endswith((".jpg", ".jpeg"))]
        g = gps_exif(hit[0]) if hit else None
        if g:
            u_ = np.asarray(wgs84_zu_utm(*g), float)
            if not np.isfinite(u_).all(): continue                                  # Kaufhaus 15.11.: einzelne EXIF-GPS ergeben NaN -> vergifteten Median/Fit (Rest 'nan', 0 Kameras)
            U.append(u_); X.append(c); GPS_KAM.append((_i, u_))
    if len(U) < 8: print(f"GPS-Massstab: nur {len(U)} Kameras mit GPS - Startmassstab aus Wolkenausdehnung"); return None   # 8: Kaufhaus hatte 10 (Chat-Kopien ohne EXIF)
    U = np.array(U, float); X = np.array(X, float); i, j = np.triu_indices(len(U), 1); dg = np.hypot(*(U[i] - U[j]).T); dx = np.linalg.norm(X[i] - X[j], axis=1); m = dg > 15
    if m.sum() < 15: return None
    q = dx[m] / dg[m]; q25, q50, q75 = np.percentile(q, [25, 50, 75]); streu = q75 / max(q25, 1e-12)
    print(f"GPS-Massstab: {len(U)} Kameras, {int(m.sum())} Paare > 15 m, Verhaeltnis-Streuung q75/q25 {streu:.2f}")
    if streu > 2.0:                                                            # Martinstor 15.11.: Commons-Geotags = Objektstandort statt Kamerastandort -> Massstab 10x falsch, keine Loesung
        print("GPS-Massstab VERWORFEN: Paarverhaeltnisse streuen zu stark (Geotags sind keine Kamerastandorte?) - Startmassstab aus Wolkenausdehnung"); GPS_KAM.clear(); return None
    return float(q50)


def loesung_index(loesung, n, schreiben):
    """Welche der n unterscheidbaren Loesungen wird geschrieben, und mit welchem rc endet der Lauf? -> (Index oder None, rc).
    17.11.2026 (Durchsicht): der Korrekturkreislauf der Kette ruft --loesung 1, 2, ... --schreiben, bis die Lage-Tore bestehen. Fiel auch die letzte durch, blieb SIE liegen
    (Ausrichtung, Wolke) - nicht die beste (Loesung 0); ein spaeterer Einstieg '--ab tore' pruefte dann die durchgefallene als Ausgangslage und Loesung 0 nie wieder.
    Jetzt: gibt es Loesung K nicht mehr (rc 5 = alle probiert), wird vor dem Ende Loesung 0 zurueckgeschrieben. OFFEN bleibt der Fall 'mehr Loesungen als --max-loesung der Kette':
    dort endet der Kreislauf ohne rc 5 - die Kette muesste dann selbst noch einmal --loesung 0 --schreiben rufen (in der Datei steht transformation.loesung_nr)."""
    if loesung < n: return loesung, 0
    return (0 if (schreiben and loesung > 0 and n > 0) else None), 5


def ergebnis_schreiben(od, sfx, usfx, out, Pm, FARBEN):
    """Ausrichtung + Wolke + Farben als EIN Stand: erst alles vollstaendig neben das Ziel schreiben, dann umbenennen (Wolke, Farben, zuletzt die JSON als Marke).
    17.11.2026 (Durchsicht): vorher JSON zuerst (`json.dump(out, open(pth, "w"))` - ein nicht schreibbarer Wert liess eine abgeschnittene Ausrichtung zurueck), dann die Wolke:
    ein Abbruch dazwischen (volle Platte, Zeitlimit der Kette) hinterliess die NEUE Ausrichtung mit der ALTEN Wolke - das Grundriss-Tor pruefte dann die alte Lage.
    Verknuepfungen (grosse Daten liegen auf der Datenplatte) bleiben erhalten: geschrieben wird neben das wirkliche Ziel."""
    text = json.dumps(out, indent=1, ensure_ascii=False); json.loads(text)                     # erst wandeln: scheitert das, ist noch nichts angefasst
    os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); os.makedirs(os.path.join(od, "sfm"), exist_ok=True)   # 15.11.: neues Objekt der Gesamtkette hat keinen sfm-Ordner
    wirklich = lambda q: os.path.realpath(q) if os.path.islink(q) else q
    pth = wirklich(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG{sfx}.json")); pw = wirklich(os.path.join(od, "sfm", f"punkte_modell{usfx}.npy")); pf = wirklich(os.path.join(od, "sfm", f"punkte_farben{usfx}.npy"))
    neu = lambda q: f"{q}.neu{os.getpid()}"; fertig = []
    try:
        for q, feld in ((pw, Pm), (pf, FARBEN)):
            with open(neu(q), "wb") as f: np.save(f, feld); f.flush(); os.fsync(f.fileno())
            fertig.append(q)
        with open(neu(pth), "w") as f: f.write(text); f.flush(); os.fsync(f.fileno())
        fertig.append(pth)
        for q in (pw, pf, pth): os.replace(neu(q), q)
    except BaseException:
        for q in (pw, pf, pth):
            if os.path.exists(neu(q)): os.remove(neu(q))
        raise
    return pth


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sparse", default=None); ap.add_argument("--name", default=""); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--fit_punkte", type=int, default=600000, help="dichte Wolke: Zufallsauswahl fuer die Anpassung (7 Parameter)")
    ap.add_argument("--fotos", default="", help="Fotoordner fuer GPS-Startmassstab (Standard objekt.json fotos_dir; Quellpraefix eigen__ wird abgestreift)")
    ap.add_argument("--loesung", type=int, default=0, help="K-te unterscheidbare Loesung (>10 Grad oder >3 m) statt der besten - Korrekturkreislauf tools/gesamtkette.py")
    ap.add_argument("--radius", type=float, default=80.0, help="LoD2-Gebaeude in diesem Umkreis um die Objektmitte (m)"); ap.add_argument("--zelle", type=float, default=0.25, help="Rasterweite Grobsuche (m)")
    ap.add_argument("--mitte-max", type=float, default=20.0, help="Wolkenmitte hoechstens so weit von der Objektmitte (m): die Bilder sind um das Objekt ausgewaehlt")
    ap.add_argument("--kamerahoehe", nargs=2, type=float, default=[1.6, 1.0], metavar=("H0", "SIGMA"), help="ANNAHME Strassenfotos: Kamerahoehe ueber Boden (robust gewichtet)")
    ap.add_argument("--kamera-gewicht", type=float, default=0.3, help="Gewicht der Kamerahoehen gegen die Punkte (0 = aus)")
    ap.add_argument("--wand", help="ignoriert (Kompatibilitaet zu sfm_ausrichten.py-Aufrufen)")
    ap.add_argument("--kameras", default=None, help="kamera_export.py-JSON: Kameras ohne pycolmap (GPU-Umgebung)")
    ap.add_argument("--fein-punkte", type=int, default=40000, help="Punkte im Feinfit (feste Zufallsauswahl)")
    ap.add_argument("--dicht", default=None, help="dichte Wolke (binary PLY, COLMAP fusion): Punkte kommen daraus, Kameras weiter aus --sparse"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od)
    rec = None; CAMS = {}
    if a.kameras:  # Kameras aus JSON (keine pycolmap-Abhaengigkeit)
        KJ = json.load(open(a.kameras))
        class _Rot:
            def __init__(s_, M): s_._M = np.asarray(M)
            def matrix(s_): return s_._M
        class _CW:
            def __init__(s_, R_, t_): s_.rotation = _Rot(R_); s_.translation = np.asarray(t_)
        class _Im:
            def __init__(s_, d): s_.name = d["name"]; s_.camera_id = d["cam"]; s_._cw = _CW(d["R"], d["t"]); s_._c = np.asarray(d["C"])
            def cam_from_world(s_): return s_._cw
            def projection_center(s_): return s_._c
        class _Mod:
            def __init__(s_, n): s_.name = n
        class _Cam:
            def __init__(s_, d): s_.params = d["params"]; s_.model = _Mod(d["model"]); s_.width = d["width"]; s_.height = d["height"]
        ims = [_Im(d) for d in KJ["bilder"]]; C = np.array([im._c for im in ims])
        CAMS = {int(k): _Cam(v) for k, v in KJ["kameras"].items()}
    elif not a.dicht:
        rec = pycolmap.Reconstruction(a.sparse); CAMS = rec.cameras
    if rec is not None:
        ids = list(rec.points3D.keys()); P = np.array([rec.points3D[i].xyz for i in ids]); err = np.array([rec.points3D[i].error for i in ids]); tl = np.array([rec.points3D[i].track.length() for i in ids])
        FARBEN = np.array([rec.points3D[i].color for i in ids], dtype=np.uint8)
    if a.dicht:  # dichte Wolke: Punkte und Farben aus dem PLY, Spur/Fehler entfallen (alle gelten)
        dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
        raw = open(a.dicht, "rb").read(); kopf_ende = raw.index(b"end_header\n") + len(b"end_header\n")
        n = int([l for l in raw[:kopf_ende].decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
        V = np.frombuffer(raw, dtype=dt, count=n, offset=kopf_ende)
        P = np.c_[V["x"], V["y"], V["z"]].astype(float); FARBEN = np.c_[V["r"], V["g"], V["b"]].astype(np.uint8)
        err = np.zeros(len(P)); tl = np.full(len(P), 3); ids = list(range(len(P)))
        print(f"dichte Wolke: {len(P)} Punkte aus {a.dicht}", flush=True)
    gut = np.ones(len(P), bool) if a.dicht else ((tl >= 3) & (err < np.percentile(err, 90))); Pg = P[gut]
    if a.dicht and len(Pg) > a.fit_punkte: Pg = Pg[np.random.default_rng(3).choice(len(Pg), a.fit_punkte, replace=False)]; print(f"Fit auf {len(Pg)} Zufallspunkten der dichten Wolke (Ausgabe: alle)")   # 15.11.: 4,4 Mio Punkte = 2,5 min je Startwert, 85 min je Lauf
    if rec is not None:
        ims = list(rec.images.values()); C = np.array([im.projection_center() for im in ims])
    print(f"SfM: {len(ims)} Kameras, {len(P)} Punkte ({gut.sum()} mit Spur >= 3)")
    # 1. Lot aus der Kameraebene
    _cmed = np.median(C, 0); _dc = np.linalg.norm(C - _cmed, axis=1); _nah = _dc <= np.percentile(_dc, 70)   # 15.11.: ferne Kameras (Schlossberg, Commons, Drohne) kippten Lot und Mitte (v2)
    cm = C[_nah].mean(0); _, sv, vt = np.linalg.svd(C[_nah] - cm); up = vt[2]
    if np.median((Pg - cm) @ up) < 0: up = -up
    flach = sv[2] / sv[0]
    print(f"Lot aus Kameraebene: Streuung {sv.round(2).tolist()} (Dicke/Laenge {flach:.2f}; < 0,25 = Strassenfotos in einer Ebene)")
    # Basis: e3 = up, e1/e2 beliebig senkrecht
    e1 = np.cross(up, [1, 0, 0]); e1 = e1 if np.linalg.norm(e1) > 0.1 else np.cross(up, [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    B0 = np.vstack([e1, e2, up])                                                              # Zeilen: SfM -> lotrechtes Netzsystem
    Q = (Pg - cm) @ B0.T; Cq = (C - cm) @ B0.T
    # Ziel
    T, Tn, Tt, wand2d, grund2d, nb, Te = lod2_ziel(obj, a.radius)
    Wo = T[Te & (Tt == 0)]; Wn = Tn[Te & (Tt == 0)]                                             # Waende des Objekts selbst (Abdeckungsmass)
    print(f"Objekt-Waende (LoD2 {obj['lod2'].get('id')}): {len(Wo)} Abtastpunkte"); G, Gn, gq = dgm_ziel(obj, a.radius)
    print(f"Ziel: {nb} LoD2-Gebaeude im Umkreis {a.radius:.0f} m ({len(T)} Flaechenpunkte), Boden {gq} ({len(G)} Punkte)")
    # 2. Grobsuche 2D: Wandlinien-Raster (Naehe) gegen Punktdichte
    from scipy.ndimage import distance_transform_edt
    z = a.zelle; H = a.radius * 1.25; n = int(2 * H / z); W = np.zeros((n, n), bool)
    for Pw in wand2d:
        for i in range(len(Pw)):
            p0, p1 = Pw[i], Pw[(i + 1) % len(Pw)]; m = int(np.linalg.norm(p1 - p0) / (z / 2)) + 2
            s_ = np.linspace(0, 1, m)[:, None]; L = p0 + s_ * (p1 - p0); ij = ((L + H) / z).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1); W[ij[ok, 1], ij[ok, 0]] = True
    Dw = distance_transform_edt(~W) * z; Nahe = np.exp(-0.5 * (Dw / 0.5) ** 2)
    import cv2
    innb = np.zeros((n, n), np.uint8)
    for Pg_ in grund2d: cv2.fillPoly(innb, [np.round((Pg_ + H) / z - 0.5).astype(np.int32)], 1)
    inn = innb.astype(bool); Tief = (distance_transform_edt(inn) * z > 1.0).astype(float)    # mehr als 1 m im Gebaeude: dort kann kein Fassadenpunkt liegen
    FT = np.fft.rfft2(Tief); zc_q = np.median(Cq[:, 2])
    GPU_FFT = False
    try:
        import torch
        if os.environ.get("ALIGN_CPU") == "1": raise ImportError("CPU erzwungen (ALIGN_CPU=1, Vergleich)")
        if torch.cuda.is_available():
            GPU_FFT = True; FTt = torch.fft.rfft2(torch.as_tensor(Tief, dtype=torch.float32, device="cuda"))
            print("Grobsuche-FFT: GPU (torch)", flush=True)
    except Exception as e:
        print("Grobsuche-FFT: CPU (numpy), GPU nicht verfuegbar:", type(e).__name__, flush=True)
    print(f"Grobsuche: Fassadenpunkte (1-7 m ueber Boden beim Probemassstab) muessen an LoD2-Waenden liegen (Naehe, Sigma 0,5 m) und nicht > 1 m im Gebaeude (Strafe x2)")
    ext = np.percentile(np.hypot(Q[:, 0], Q[:, 1]), 80); ziel_ext = 0.8 * a.radius * 0.5
    s0 = ext / ziel_ext                                                                       # grober Startmassstab (SfM-Einheiten je m), Suche ueber Faktor 6 in beide Richtungen
    s_gps = gps_massstab(ims, C, obj, od, a.fotos)                                            # 15.11.: v2 (Video/Commons weit weg) -> Wolkenausdehnung 70x falsch, Suchband verfehlte den Massstab
    if s_gps:
        print(f"Startmassstab aus Foto-GPS: {s_gps:.4f} SfM-Einheiten/m (Wolkenausdehnung haette {s0:.4f} gegeben)"); s0 = s_gps
    best = []
    print(f"Startmassstab s0 = {s0:.4f} SfM-Einheiten/m (Wolkenausdehnung), Suche s0/4 .. 4 s0; Toleranz 0,75 m * s0/s (konstant in SfM-Einheiten)")
    _band = 1.5 if s_gps else 4.0                                                             # 15.11.: mit GPS-Massstab nur +-50 % suchen (GPS lag 6-8 % neben LoD2; Kaufhaus: ohne Grenze gewann ein 2,6-fach geschrumpftes Modell, Wolke 9 m hoch)
    if s_gps: print(f"Massstabssuche auf GPS-Band begrenzt: {s0 / _band:.4f} .. {s0 * _band:.4f}")
    for ls in np.linspace(math.log(s0 / _band), math.log(s0 * _band), 17 if s_gps else 33):
        s = math.exp(ls); hq = (Q[:, 2] - zc_q) / s + 1.6; fs = (hq > 1.0) & (hq < 7.0)
        if fs.sum() < 50: continue
        sig_m = max(z, 0.75 * s0 / s)                                                          # Toleranz in SfM-EINHEITEN konstant (massstabsneutral; in Metern bevorzugt jede Toleranz das geschrumpfte Modell)
        FN = np.fft.rfft2(np.exp(-0.5 * (Dw / sig_m) ** 2))
        if GPU_FFT: FNt = torch.fft.rfft2(torch.as_tensor(np.exp(-0.5 * (Dw / sig_m) ** 2), dtype=torch.float32, device="cuda"))
        if GPU_FFT:  # gesamter Winkel-Durchlauf auf der GPU (Drehung, Raster, FFT, Maximum)
            Qf = torch.as_tensor(Q[fs, :2], dtype=torch.float64, device="cuda"); sh_t = np.fft.fftfreq(n, 1.0 / n) * z
            for th in np.radians(np.arange(0, 360, 3)):
                c, si = math.cos(th), math.sin(th)
                Rt = torch.tensor([[c, -si], [si, c]], dtype=torch.float64, device="cuda")
                xyt = (Qf @ Rt.T) / s
                ijf = torch.floor((xyt + H) / z).long(); okt = (ijf >= 0).all(1) & (ijf < n).all(1)
                if int(okt.sum()) < 0.3 * len(xyt): continue
                Dt = torch.zeros((n, n), dtype=torch.float32, device="cuda")
                Dt.index_put_((ijf[okt, 1], ijf[okt, 0]), torch.ones(int(okt.sum()), dtype=torch.float32, device="cuda"), accumulate=True)
                K = torch.fft.irfft2((FNt - 2.0 * FTt) * torch.conj(torch.fft.rfft2(Dt))).double()
                m0 = torch.median(xyt, 0).values.cpu().numpy()
                fern = np.hypot(m0[0] + sh_t[None, :], m0[1] + sh_t[:, None]) > a.mitte_max
                K = K.masked_fill(torch.as_tensor(fern, device="cuda"), float("-inf"))
                kf = int(torch.argmax(K)); ky, kx = divmod(kf, n); kval = float(K[ky, kx])
                dy, dx = [(v if v < n // 2 else v - n) * z for v in (ky, kx)]
                best.append((kval / len(Q), s, th, dx, dy))
            continue
        for th in np.radians(np.arange(0, 360, 3)):
            c, si = math.cos(th), math.sin(th); xy = (Q[fs, :2] @ np.array([[c, -si], [si, c]]).T) / s
            ij = ((xy + H) / z).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
            if ok.sum() < 0.3 * len(xy): continue
            if GPU_FFT:  # GPU: Raster per scatter-add, FFT per torch (gleiche Mathematik wie numpy)
                ijt = torch.as_tensor(np.c_[ij[ok, 1], ij[ok, 0]], dtype=torch.long, device="cuda")
                Dt = torch.zeros((n, n), dtype=torch.float32, device="cuda"); Dt.index_put_((ijt[:, 0], ijt[:, 1]), torch.ones(len(ijt), dtype=torch.float32, device="cuda"), accumulate=True)
                FDt = torch.conj(torch.fft.rfft2(Dt)); K = torch.fft.irfft2((FNt - 2.0 * FTt) * FDt, s=(n, n)).double().cpu().numpy()
            else:
                D = np.zeros((n, n)); np.add.at(D, (ij[ok, 1], ij[ok, 0]), 1.0)
                FD = np.conj(np.fft.rfft2(D)); K = np.fft.irfft2((FN - 2.0 * FT) * FD, s=(n, n))   # K[dy,dx] = sum D(p) * (Nahe - 2 Tief)(p + d)
            m0 = np.median(xy, 0); sh = np.fft.fftfreq(n, 1.0 / n) * z                          # Verschiebung je Rasterindex (m)
            fern = np.hypot(m0[0] + sh[None, :], m0[1] + sh[:, None]) > a.mitte_max                 # Fotos sind um das Objekt ausgewaehlt: Wolkenmitte (Median) <= mitte_max vom Objekt
            K[fern] = -np.inf
            k = np.unravel_index(np.argmax(K), K.shape); dy, dx = [(v if v < n // 2 else v - n) * z for v in k]
            best.append((K[k] / len(Q), s, th, dx, dy))                                       # durch ALLE Punkte teilen: wenige Punkte im Band (zu kleines Modell) gewinnen nicht
    best.sort(key=lambda b: -b[0]); top = []
    for b in best:                                                                            # je Massstabsband die beste Loesung (die Grobsumme allein bevorzugt kleine Modelle)
        if not any(abs(math.log(b[1] / t[1])) < 0.15 for t in top): top.append(b)
        # KEINE Obergrenze (Martinstor 2026-11-04): mit 'top 12' fiel das richtige Band (s = 0,071, alte Pick-Kette) heraus, weil die Grobsumme kleine
        # Modelle bevorzugt -> Turm 0,66-fach. Jedes Massstabsband (Abstand 0,15 in log s, ~19 Baender) bekommt eine Feinloesung; entschieden wird dort.
    GPS_PRUEF = None
    if sum(_nah[i] for i, _ in GPS_KAM) >= 15:                                               # 15.11.: GPS-Startkandidat (v2: LoD2-Grobsuche verfehlte Lage; 190 Kameras mit GPS)
        R_ = obj["rahmen"]; c0_ = np.array(R_["mitte_utm"], float); xh_, yh_ = np.array(R_["xhat_utm"], float), np.array(R_["yhat_utm"], float)
        _gk = [(i, u) for i, u in GPS_KAM if _nah[i]]                                         # nur Kamerakern: globaler Mapper setzt einzelne Kameras tausende Einheiten weit weg
        Mxy = np.array([[(u - c0_) @ xh_, (u - c0_) @ yh_] for _, u in _gk]); Cxy = Cq[[i for i, _ in _gk], :2]
        w_ = np.isfinite(Mxy).all(1) & np.isfinite(Cxy).all(1) & (np.linalg.norm(Mxy, axis=1) < 5000)   # Kaufhaus: einzelne Fotos mit unsinnigem EXIF-GPS (NaN/fern) -> SVD-Absturz
        def _gpsfit(Cxy_, w0):
            w = w0.copy(); Rg_ = np.eye(2); res_ = np.full(len(Mxy), np.inf); k = 1.0; tg_ = np.zeros(2)
            for _ in range(5):
                if w.sum() < 8: break
                try:
                    mc, cc = Mxy[w].mean(0), Cxy_[w].mean(0); Uu, Ss, Vv = np.linalg.svd((Mxy[w] - mc).T @ (Cxy_[w] - cc))
                except np.linalg.LinAlgError: w[:] = False; break
                Rg_ = Uu @ np.diag([1, np.sign(np.linalg.det(Uu @ Vv))]) @ Vv; k = Ss.sum() / ((Cxy_[w] - cc) ** 2).sum(); tg_ = mc - k * Rg_ @ cc
                res_ = np.linalg.norm(k * Cxy_ @ Rg_.T + tg_ - Mxy, axis=1); w = res_ < max(2.5 * np.median(res_), 8)
            return Rg_, k, tg_, res_, w
        Rg, k_, tg, res, w1 = _gpsfit(Cxy, w_); Rs, ks, ts, ress, ws = _gpsfit(Cxy * [1, -1], w_)
        if ws.sum() >= 8 and np.median(ress) < 8 and np.median(ress) < 0.5 * np.median(res):     # 15.11. Kaufhaus: GPS passt nur GESPIEGELT -> Lot zeigt nach unten (Kameras/Wolke standen kopf)
            print(f"LOT UMGEDREHT: GPS-Fit gespiegelt Rest {np.median(ress):.1f} m gegen {np.median(res):.1f} m - Hochachse war falsch herum; Grobsuche verworfen, nur GPS-Startlagen")
            B0[1:] *= -1; Q[:, 1:] *= -1; Cq[:, 1:] *= -1; Cxy = Cxy * [1, -1]; Rg, k_, tg, res, w1 = Rs, ks, ts, ress, ws; top.clear()
        w_ = w1
        if np.linalg.det(Rg) > 0 and w_.sum() >= 8 and np.median(res) < 12:                  # nur ein brauchbarer GPS-Fit wird Startkandidat
            thg = math.atan2(Rg[1, 0], Rg[0, 0])
            for _dx, _dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (0, 0)): top.insert(0, (-1.0, 1.0 / k_, thg, float(tg[0]) + _dx, float(tg[1]) + _dy))   # GPS-Lage +-4 m (Handy-GPS in der Gasse), Fangbereich Feinfit ~3 m
            print(f"GPS-Startkandidat: Massstab {1 / k_:.4f} SfM-Einheiten/m, Drehung {math.degrees(thg):.0f} Grad, Rest Median {np.median(res):.1f} m ({int(w_.sum())} von {len(w_)} Kameras)")
        else: print(f"GPS-Startkandidat nicht benutzt: Rest Median {np.median(res):.1f} m, {int(w_.sum())} Kameras")
        if np.linalg.det(Rg) > 0 and np.median(res) < 8 and int(w_.sum()) >= 15: GPS_PRUEF = (np.array([i for i, _ in _gk]), Mxy, 1.0 / k_)   # guter GPS-Fit -> Veto fuer Loesungen (unabhaengiger Lagebeleg)
    print("Grobsuche (Anteil nahe LoD2-Wand, Massstab, Drehung, Verschiebung): " + "; ".join(f"{b[0]:.2f} s={b[1]:.3f} {math.degrees(b[2]):.0f} Grad" for b in top[:4]))

    # 3. Fein: 7 Parameter, Punkt-zu-Flaeche, getrimmt; Startwerte aus den besten Grobloesungen
    Tall = np.vstack([T, G]); Nall = np.vstack([Tn, Gn]); baum = cKDTree(Tall)
    # Nachbarsuche auf der GPU (gpu_knn, Nutzerregel); ohne GPU Rueckfall auf cKDTree
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import naechster as _gnn
        def nn(M, bound=None):
            d, j = _gnn(np.asarray(M, np.float64), Tall)
            if bound is not None: bad = d > bound; d = np.where(bad, np.inf, d); j = np.where(bad, 0, j)
            return d, j
        print("Nachbarsuche: GPU (gpu_knn)", flush=True)
    except Exception as e:
        print("Nachbarsuche: CPU (cKDTree), GPU nicht verfuegbar:", type(e).__name__, flush=True)
        def nn(M, bound=None):
            d, j = baum.query(M, distance_upper_bound=bound) if bound is not None else baum.query(M)
            return d, j

    def zu_modell(p, X):                                                                      # X im lotrechten Netzsystem -> Modell
        s = math.exp(p[0]); return Rot.from_rotvec(p[1:4]).apply(X) / s + p[4:7]

    def fein(p0, X, schwellen=(3.0, 1.5, 0.8), band=0.35):
        p = np.array(p0, float); ls0 = p[0]
        for sw in schwellen:
            for _ in range(3):
                M = zu_modell(p, X); d, j = nn(M, sw * 2)
                ok = np.isfinite(d); jj = j[ok]; Xo = X[ok]
                if len(Xo) > a.fein_punkte:  # Feinfit mit fester Zufallsauswahl (7 Parameter brauchen keine Millionen Punkte; spart CPU je Schritt)
                    sel = np.random.default_rng(7).choice(len(Xo), a.fein_punkte, replace=False); Xo = Xo[sel]; jj = jj[sel]
                if ok.sum() < 30: return p, 0.0, np.inf, ok
                wk = a.kamera_gewicht * math.sqrt(len(Xo) / len(Cq))
                def r(q):
                    rp = np.einsum("ij,ij->i", zu_modell(q, Xo) - Tall[jj], Nall[jj]) * math.exp(q[0])  # Residuum in SfM-Einheiten (massstabsneutral, kein Kollaps)
                    rk = (zu_modell(q, Cq)[:, 2] - a.kamerahoehe[0]) / a.kamerahoehe[1] * math.exp(ls0) * wk   # ANNAHME Strassenfotos: Kamerahoehe h0 +- sigma (robust: Turm-/Fensterfotos sind Ausreisser)
                    return np.r_[rp, rk]
                if GPU_FFT:  # Residuum auf der GPU (torch): gleiche Formeln wie oben, Rodrigues-Rotation
                    Xo_t = torch.as_tensor(Xo, dtype=torch.float64, device="cuda"); Tj_t = torch.as_tensor(Tall[jj], dtype=torch.float64, device="cuda")
                    Nj_t = torch.as_tensor(Nall[jj], dtype=torch.float64, device="cuda"); Cq_t = torch.as_tensor(Cq, dtype=torch.float64, device="cuda")
                    def r(q, _Xo=Xo_t, _Tj=Tj_t, _Nj=Nj_t, _wk=wk, _ls0=ls0):
                        qt = torch.as_tensor(np.asarray(q, np.float64), device="cuda")
                        th = torch.linalg.norm(qt[1:4]) + 1e-18; k = qt[1:4] / th
                        Kx = torch.stack([torch.zeros((), dtype=torch.float64, device="cuda"), -k[2], k[1], k[2], torch.zeros((), dtype=torch.float64, device="cuda"), -k[0], -k[1], k[0], torch.zeros((), dtype=torch.float64, device="cuda")]).reshape(3, 3)
                        Rm = torch.eye(3, dtype=torch.float64, device="cuda") + torch.sin(th) * Kx + (1 - torch.cos(th)) * (Kx @ Kx)
                        s_ = torch.exp(qt[0])
                        Y = (_Xo @ Rm.T) / s_ + qt[4:7]
                        rp = ((Y - _Tj) * _Nj).sum(1) * s_
                        Yc = (Cq_t @ Rm.T) / s_ + qt[4:7]
                        rk = (Yc[:, 2] - a.kamerahoehe[0]) / a.kamerahoehe[1] * math.exp(_ls0) * _wk
                        return torch.cat([rp, rk]).cpu().numpy()
                lo = np.full(7, -np.inf); hi = np.full(7, np.inf); lo[0], hi[0] = ls0 - band, ls0 + band   # Massstab begrenzt (+-40 % um den Start): sonst Kollaps aller Punkte auf eine Flaeche
                p = least_squares(r, np.clip(p, lo + 1e-9, hi - 1e-9), loss="huber", f_scale=sw / 3 * math.exp(ls0), max_nfev=200, bounds=(lo, hi)).x
        M = zu_modell(p, X); d, _ = nn(M); ok = d * math.exp(p[0]) < schwellen[-1] * s0      # Inlier-Schwelle in SfM-Einheiten (massstabsneutral)
        return p, ok.mean(), float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else np.inf, ok

    def abdeckung(p, X):
        """Anteil der zur Kamera gewandten Objektwand-Flaeche (unter der Traufe) mit einem Netzpunkt im Umkreis 0,6 m: ein geschrumpftes Netz deckt nur einen Fleck."""
        M = zu_modell(p, X); Cm_ = zu_modell(p, Cq); cz = Cm_.mean(0)
        sicht = ((cz - Wo) * Wn).sum(1) > 0
        if sicht.sum() < 20: return 0.0
        d, _ = cKDTree(M).query(Wo[sicht]); return float((d < 0.6).mean())

    loes = []; _s_gps_best = None
    for sc, s, th, dx, dy in top:
        p0 = [math.log(s), 0, 0, th, dx, dy, 0.0]
        if GPS_PRUEF is not None and (abs(p0[0] - math.log(GPS_PRUEF[2])) > 0.6 or float(np.median(np.linalg.norm(zu_modell(p0, Cq[GPS_PRUEF[0]])[:, :2] - GPS_PRUEF[1], axis=1))) > 30):
            continue                                                                          # kann das GPS-Veto nie bestehen (Massstab > Band + Veto oder Kameras > 30 m neben GPS) -> Rechenzeit sparen
        zc = np.median(Cq[:, 2]) / s; p0[6] = 1.6 - zc                                         # Hoehenstart: Kameras ~1,6 m ueber Boden (nur Start, ANNAHME)
        if sc == -1.0 and _s_gps_best is None:                                              # 15.11.: MASSSTABS-RASTER statt freiem Massstab. Der Feinfit lief IMMER an die Bandgrenze
            _kand = []                                                                      # (schwab_auto 0,0737 = untere, schwab_v3 0,0968 = obere Grenze; wahr 0,0732). Jetzt: Massstab je
            for _f in np.linspace(-0.27, 0.27, 19):                                         # Rasterwert festhalten (+-0,5 %), nur Drehung/Lage anpassen; es gewinnt Inlier x Wandabdeckung.
                _p0 = list(p0); _p0[0] = p0[0] + float(_f); _p, _fr, _rm, _ok = fein(_p0, Q, band=0.005); _ab = abdeckung(_p, Q); _kand.append((_fr * _ab, _rm, _p, _ok, _fr, _ab))
            _kand.sort(key=lambda l: -l[0]); _s_gps_best = _kand[0][2][0]; loes += _kand[:3]
            print(f"   GPS-Massstabsraster: bester Massstab {math.exp(_s_gps_best):.4f} (Guete {100 * _kand[0][0]:.0f} %, Inlier {100 * _kand[0][4]:.0f} %, Abdeckung {100 * _kand[0][5]:.0f} %); zweitbester {math.exp(_kand[1][2][0]):.4f} ({100 * _kand[1][0]:.0f} %)", flush=True)
            continue
        if sc == -1.0: p0[0] = _s_gps_best
        p, frac, rms, ok = fein(p0, Q, band=0.005 if sc == -1.0 else 0.35); ab = abdeckung(p, Q); loes.append((frac * ab, rms, p, ok, frac, ab))
        print(f"   Start {math.degrees(th):5.0f} Grad s={s:.3f}: Inlier {100 * frac:.0f} %, Objektwand-Abdeckung {100 * ab:.0f} %, RMS {rms:.2f} m, Massstab {math.exp(p[0]):.4f}")
    if GPS_PRUEF is not None:                                                                 # 15.11.: GPS-Veto (v2: Loesung mit 2,5-fach zu grossem Modell gewann mit Guete 4 %)
        _gi, _gm, _gs = GPS_PRUEF
        def _gps_rest(p_): return float(np.median(np.linalg.norm(zu_modell(p_, Cq[_gi])[:, :2] - _gm, axis=1)))
        _kons = [l for l in loes if _gps_rest(l[2]) < 12 and abs(l[2][0] - math.log(_gs)) < 0.25]
        print(f"GPS-Veto: {len(_kons)} von {len(loes)} Loesungen passen zum Foto-GPS (Kamerarest < 12 m, Massstab +-28 %); beste verworfene Guete {100 * max([l[0] for l in loes if not any(l is k for k in _kons)], default=0):.0f} %")
        if _kons: loes = _kons
        else: print("WARNUNG GPS-Veto: KEINE Loesung passt zum Foto-GPS - Ergebnis nicht glauben (Tore entscheiden)")
    loes.sort(key=lambda l: -l[0])
    _verschieden = []
    for l in loes:                                                                              # unterscheidbare Lagen (Korrekturkreislauf: Loesung K probieren, Tore entscheiden)
        if all(np.degrees((Rot.from_rotvec(l[2][1:4]).inv() * Rot.from_rotvec(v[2][1:4])).magnitude()) > 10 or np.linalg.norm(np.asarray(l[2][4:7]) - np.asarray(v[2][4:7])) > 3 for v in _verschieden):
            _verschieden.append(l)
    i_loes, rc_ende = loesung_index(a.loesung, len(_verschieden), a.schreiben)
    if rc_ende == 5 and i_loes is not None:                                                     # liegt schon Loesung 0 auf der Platte (es gab nur eine), nichts neu schreiben
        try: _nr_alt = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG{('-' + a.name) if a.name else ''}.json")))["transformation"].get("loesung_nr", 0)
        except Exception: _nr_alt = None
        if _nr_alt == 0: i_loes = None
    if rc_ende == 5:
        print(f"KEINE_LOESUNG {a.loesung}: nur {len(_verschieden)} unterscheidbare Loesungen" + (" - schreibe Loesung 0 (beste Guete) ZURUECK, damit nicht die zuletzt probierte, durchgefallene liegen bleibt" if i_loes is not None else ""), flush=True)
        if i_loes is None: sys.exit(5)
    elif a.loesung: print(f"Korrekturkreislauf: nehme unterscheidbare Loesung {a.loesung} von {len(_verschieden)} (Guete {100 * _verschieden[a.loesung][0]:.1f} % statt {100 * loes[0][0]:.1f} %)")
    guete, rms, p, ok, frac, ab = _verschieden[i_loes]
    # Bootstrap: Massstab-/Lage-Streuung aus Teilstichproben
    rng = np.random.default_rng(1); bs = []
    for _ in range(8):
        sub = rng.choice(len(Q), len(Q) // 2, replace=False); pb, *_ = fein(p, Q[sub], schwellen=(1.5, 0.8)); bs.append(pb)
    bs = np.array(bs); s_sig = 100 * np.std(np.exp(bs[:, 0])) / math.exp(p[0]); t_sig = np.std(bs[:, 4:7], 0)
    zweit = loes[1][0] if len(loes) > 1 else 0; frac = guete                                   # Guete = Inlier x Abdeckung
    _anders = [l for l in loes[1:] if np.degrees((Rot.from_rotvec(l[2][1:4]).inv() * Rot.from_rotvec(p[1:4])).magnitude()) > 10
               or np.linalg.norm(np.asarray(l[2][4:7]) - np.asarray(p[4:7])) > 3]              # nur wirklich andere Lagen, nicht Duplikate derselben
    mehrdeutig = bool(_anders) and bool(_anders[0][0] > 0.85 * guete)                                   # Schwabentor 2026-11-14: 0,222 vs 0,194 (87 %) -> Fluegel auf der Strasse
    if mehrdeutig:
        print(f"\nWARNUNG MEHRDEUTIG: andere Lage (>10 Grad oder >3 m) erreicht {100 * _anders[0][0]:.1f} % gegen {100 * guete:.1f} % "
              f"({100 * _anders[0][0] / guete:.0f} %) - danach tools/wolke_grundriss_pruefen.py + tools/kamera_abdeckung.py, Lage am Foto belegen")
    # Gesamt: X_modell = Rz(X_sfm - cm) B0^T / s + t  ->  X_sfm = s * R @ X_modell + t
    s = math.exp(p[0]); Rl = Rot.from_rotvec(p[1:4]).as_matrix(); Rm = Rl @ B0                  # X_m = Rm (X_s - cm)/s + tm
    tm = p[4:7]; R_s = Rm.T; t_s = cm - s * R_s @ tm
    print(f"\nMassstab SfM-Einheiten/m = {s:.5f} +- {s_sig:.1f} %   Lage-Sigma {t_sig.round(2).tolist()} m   Guete (Inlier x Abdeckung) {100 * frac:.0f} % (zweitbeste {100 * zweit:.0f} %), RMS {rms:.2f} m")
    Pm = ((P - cm) @ Rm.T) / s + tm; Cm = ((C - cm) @ Rm.T) / s + tm
    hz = Cm[:, 2]; print(f"Kamerahoehen (robuste Bedingung, ANNAHME h0 {a.kamerahoehe[0]} +- {a.kamerahoehe[1]} m; Rest = Ausreisser): Median {np.median(hz):.2f} m, {np.sum((hz > -1) & (hz < 6))} von {len(hz)} zwischen -1 und 6 m (Strassenfotos ~1,5-2)")
    dg = baum.query(Pm[gut])[0]; print(f"Wolke im Modellsystem: z p1 {np.percentile(Pm[:, 2], 1):.1f} .. p99 {np.percentile(Pm[:, 2], 99):.1f} m; Abstand zu LoD2/DGM: Median {np.median(dg):.2f} m")
    if a.schreiben:
        sfx = ("-" + a.name) if a.name else ""; usfx = ("_" + a.name) if a.name else ""
        kam = {}
        for im, c in zip(ims, Cm):
            nr = os.path.splitext(im.name)[0]; cw = im.cam_from_world(); Rc = cw.rotation.matrix() @ R_s; tc = (cw.rotation.matrix() @ t_s + np.array(cw.translation)) / s
            cam = CAMS[im.camera_id]; pr = list(cam.params)
            kam[nr] = dict(standort=c.round(2).tolist(), f_px_original=float(pr[0]), fak=1.0, off=[0.0, 0.0], R=Rc.tolist(), t=tc.tolist(), cx=float(pr[2] if cam.model.name in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[1]), cy=float(pr[3] if cam.model.name in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[2]),
                           k=[float(v) for v in pr[3:]] if cam.model.name in ("SIMPLE_RADIAL", "RADIAL") else [], bild_b=cam.width, bild_h=cam.height, hinweis="f/cx/cy in SfM-Bildpixeln (fak nicht bestimmt)")
        out = dict(verfahren="sfm_lod2_ausrichten.py (ohne Picks: Kameraebene -> Lot, LoD2-Wandlinien -> Grob, Punkt-zu-Flaeche LoD2+DGM1 -> Fein)", sparse=a.sparse, fotos_sfm=sorted(kam), fotos_mit_picks=[],
                   transformation=dict(beschreibung="X_sfm = s * R @ X_modell + t ; Modellsystem = objekt.json rahmen (anker3d.json)", s=s, s_sigma_prozent=float(s_sig), rvec=Rot.from_matrix(R_s).as_rotvec().tolist(),
                                       t=t_s.tolist(), t_sigma_m=t_sig.tolist(), inlier_anteil=float(frac), rms_m=float(rms), zweitbeste_inlier=float(zweit), mehrdeutig=mehrdeutig, loesung_nr=i_loes, loesungen_unterscheidbar=len(_verschieden)),
                   ziel=dict(lod2_gebaeude=nb, radius_m=a.radius, boden=gq), kameras=kam,
                   kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)),
                   wolke=dict(n=len(Pm), z_p1=float(np.percentile(Pm[:, 2], 1)), z_p999=float(np.percentile(Pm[:, 2], 99.9))), annahmen=dict(kamerahoehe=dict(h0=a.kamerahoehe[0], sigma=a.kamerahoehe[1], gewicht=a.kamera_gewicht, hinweis="ANNAHME Strassenfotos, robuste Bedingung (Huber)")))
        pth = ergebnis_schreiben(od, sfx, usfx, out, Pm, FARBEN); print("geschrieben:", pth, "+ sfm/punkte_modell, punkte_farben (ein Stand, atomar)")
        try:
            sim = pycolmap.Sim3d(1.0 / s, pycolmap.Rotation3d(Rm), tm - Rm @ cm / s); rec.transform(sim); ziel = os.path.join(od, "sfm", f"sparse_modell{usfx}"); os.makedirs(ziel, exist_ok=True); rec.write(ziel)
            print("geschrieben:", ziel, "(COLMAP-Modell im Modellsystem, Meter)")
        except Exception as e: print("sparse_modell nicht geschrieben:", type(e).__name__, e)
    if rc_ende: sys.exit(rc_ende)


if __name__ == "__main__":
    main()
