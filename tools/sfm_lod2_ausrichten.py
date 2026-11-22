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
Weitere Argumente: --dicht <ply> (Punkte aus dichter Wolke), --kameras <json> (ohne pycolmap), --loesung K (K-te unterscheidbare Loesung,
  Korrekturkreislauf der Gesamtkette), --fotos <ordner> (GPS-Startmassstab), --kamerahoehe H0 SIGMA. Oder `tools/py tools/sfm_lod2_ausrichten.py ...`.
Exit: 0 = ausgerichtet, 5 = Loesung K gibt es nicht (alle probiert; mit --schreiben wird Loesung 0 zurueckgeschrieben).
"""
import sys, os, json, glob, math, argparse, numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gps_unsicherheit as GU
import lage_proben as LP
try:
    import pycolmap
except ImportError:  # GPU-Umgebung: Kameras kommen aus --kameras
    pycolmap = None


def lod2_ziel(obj, radius, dichte=0.35):
    """LoD2-Flaechen (alle Gebaeude im Umkreis) im Modellsystem, abgetastet: Punkte, Normalen, Typ (0 Wand, 1 Dach)."""
    import lod2_gebaeude as LG
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"]); gel = R["gelaende"]
    gml = obj["lod2"]["gml"]
    # Cache: das Einlesen des amtlichen GML ist reines Textparsen (~2 min). Schluessel: Datei (Groesse, Zeit), Mitte, Radius + CODE-STAND des Lesers (22.11.2026, tools/code_stand.py:
    # ein geaenderter lod2_gebaeude.py liest neu statt still den alten Cache zu nehmen).
    import pickle, hashlib
    from code_stand import code_stand
    st = os.stat(gml); schl = hashlib.sha1(f"{gml}|{st.st_size}|{int(st.st_mtime)}|{c0.tolist()}|{radius}|{code_stand('lod2_gebaeude.py')}".encode()).hexdigest()[:16]
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
GPS_ZEIT = {}  # Kameraindex -> EXIF-Aufnahmezeit (Sitzungen der ehrlichen GPS-Unsicherheit, tools/gps_unsicherheit.py)


def gps_massstab(ims, C, obj, od, fotos=""):
    """Massstab SfM-Einheiten je m aus Foto-GPS (EXIF): Median der Verhaeltnisse Kameraabstand SfM / GPS fuer Paare > 15 m GPS-Abstand.
    Unabhaengig von LoD2 und von weit entfernten Wolkenteilen. None bei < 15 Kameras mit GPS."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gps_ausrichtung import gps_exif; from bilder_holen import wgs84_zu_utm
    except Exception as e: print("GPS-Massstab: Hilfsmodule fehlen:", type(e).__name__); return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ds = [d for d in (fotos, obj.get("fotos_dir", "")) if d]; ds = [d if os.path.isabs(d) else os.path.join(root, d) for d in ds]
    U, X = [], []; GPS_KAM.clear(); GPS_ZEIT.clear()
    for _i, (im, c) in enumerate(zip(ims, C)):
        nm = os.path.splitext(os.path.basename(im.name))[0]; kand = [nm] + ([nm.split("__", 1)[1]] if "__" in nm else [])
        hit = [p for d in ds for n_ in kand for p in glob.glob(os.path.join(d, glob.escape(n_) + ".*")) if p.lower().endswith((".jpg", ".jpeg"))]
        g = gps_exif(hit[0]) if hit else None
        if g:
            u_ = np.asarray(wgs84_zu_utm(*g), float)
            if not np.isfinite(u_).all(): continue                                  # Kaufhaus 15.11.: einzelne EXIF-GPS ergeben NaN -> vergifteten Median/Fit (Rest 'nan', 0 Kameras)
            U.append(u_); X.append(c); GPS_KAM.append((_i, u_)); GPS_ZEIT[_i] = GU.exif_zeit(hit[0])
    if len(U) < 8: print(f"GPS-Massstab: nur {len(U)} Kameras mit GPS - Startmassstab aus Wolkenausdehnung"); return None   # 8: Kaufhaus hatte 10 (Chat-Kopien ohne EXIF)
    U = np.array(U, float); X = np.array(X, float); i, j = np.triu_indices(len(U), 1); dg = np.hypot(*(U[i] - U[j]).T); dx = np.linalg.norm(X[i] - X[j], axis=1); m = dg > 15
    if m.sum() < 15: return None
    q = dx[m] / dg[m]; q25, q50, q75 = np.percentile(q, [25, 50, 75]); streu = q75 / max(q25, 1e-12)
    print(f"GPS-Massstab: {len(U)} Kameras, {int(m.sum())} Paare > 15 m, Verhaeltnis-Streuung q75/q25 {streu:.2f}")
    if streu > 2.0:                                                            # Martinstor 15.11.: Commons-Geotags = Objektstandort statt Kamerastandort -> Massstab 10x falsch, keine Loesung
        # 18.11.2026 (Kaufhaus gk2f: Streuung 2,43 -> verworfen -> Massstab aus Wolkenausdehnung, Suche s0/4..4 s0, 4 Loesungen 73-158 Grad / Massstab 0,25-1,9 gegen GPS gedreht,
        # obwohl ein robuster GPS-Fit Rest Median 5,8 m hatte): einzelne falsche Geotags verderben JEDES Paar mit ihnen -> erst robuster Aehnlichkeits-Fit (RANSAC) versuchen
        r = gps_fit_robust(X, U)
        if r is not None:
            s_, inl, rest, ausd = r
            print(f"GPS-Massstab aus robustem Fit: {int(inl.sum())} von {len(U)} Kameras passen (Rest Median {rest:.1f} m, Ausdehnung {ausd:.0f} m) -> {s_:.4f} SfM-Einheiten/m; falsche Geotags aus dem GPS-Startkandidaten genommen")
            GPS_KAM[:] = [g_ for g_, ok_ in zip(GPS_KAM, inl) if ok_]; return float(s_)
        print("GPS-Massstab VERWORFEN: Paarverhaeltnisse streuen zu stark und kein robuster Fit (Geotags sind keine Kamerastandorte?) - Startmassstab aus Wolkenausdehnung"); GPS_KAM.clear(); return None
    return float(q50)


def gps_fit_robust(X, U, schwelle=10.0, iter_=3000, min_anteil=0.4, min_n=15, max_rest=8.0, min_ausd=20.0, seed=0):
    """Robuster Aehnlichkeits-Fit SfM-Kamerazentren X (3D, beliebig gedreht) -> GPS U (UTM 2D, Hoehe 0 = ANNAHME: Strassenfotos +-2 m) per RANSAC (3 Punkte, Umeyama),
    Nachfit auf den Inliern (Abstand < schwelle m). Angenommen nur mit >= min_anteil und >= min_n Inliern, Rest-Median <= max_rest m und raeumlicher Ausdehnung der
    Inlier-Geotags >= min_ausd m (Objektstandort-Geotags = ein Haufen -> kein Massstab). Liefert (s SfM-Einheiten/m, inlier-Maske, rest_median, ausdehnung) oder None."""
    X = np.asarray(X, float); Y = np.c_[np.asarray(U, float), np.zeros(len(U))]; n = len(X)
    if n < max(min_n, 3): return None
    def ume(A, B):
        ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb; S_ = B0.T @ A0 / len(A); Uu, D, Vt = np.linalg.svd(S_); E = np.eye(3); E[2, 2] = np.sign(np.linalg.det(Uu @ Vt))
        R = Uu @ E @ Vt; va = (A0 ** 2).sum() / len(A); k = float((D * np.diag(E)).sum() / max(va, 1e-12)); return k, R, mb - k * R @ ma      # B ~ k R A + t (k in m je SfM-Einheit)
    rng = np.random.default_rng(seed); best = None
    for _ in range(iter_):
        idx = rng.choice(n, 3, replace=False)
        if np.linalg.norm(np.cross(Y[idx[1]] - Y[idx[0]], Y[idx[2]] - Y[idx[0]])) < 25.0: continue      # fast kollinear / zu eng
        k, R, t = ume(X[idx], Y[idx])
        if not np.isfinite(k) or k <= 0: continue
        d = np.linalg.norm((k * (R @ X.T)).T + t - Y, axis=1); inl = d < schwelle
        if best is None or inl.sum() > best.sum(): best = inl
    if best is None or best.sum() < max(min_n, min_anteil * n): return None
    for _ in range(3):
        k, R, t = ume(X[best], Y[best]); d = np.linalg.norm((k * (R @ X.T)).T + t - Y, axis=1); best = d < schwelle
        if best.sum() < 3: return None
    rest = float(np.median(d[best])); ausd = float(np.ptp(Y[best, :2], axis=0).max())
    if best.sum() < max(min_n, min_anteil * n) or rest > max_rest or ausd < min_ausd: return None
    return 1.0 / k, best, rest, ausd


def gps_dreh_massstab(Xm, G, grenze=12.0):
    """Drehung (Grad, um das Lot) und Massstab der 2D-Aehnlichkeit, die die Kamerastandorte EINER Loesung (Xm, Modellsystem in m, n x 2) auf ihr Foto-GPS (G, gleiches System)
    legt - dieselbe Messgroesse wie das GPS-Tor tools/lage_gps_pruefen.py ('2 GPS-Fit: Drehung, Massstab'). Getrimmt: Nachfit auf Kameras mit Rest < max(80-%-Wert, grenze).
    Rueckgabe (drehung_grad, massstab) oder None (zu wenige Kameras)."""
    Xm = np.asarray(Xm, float); G = np.asarray(G, float); w = np.isfinite(Xm).all(1) & np.isfinite(G).all(1)
    if w.sum() < 8: return None
    def fit(A, B):
        ma, mb = A.mean(0), B.mean(0); A0, B0 = A - ma, B - mb; U, S, Vt = np.linalg.svd(B0.T @ A0); D = np.eye(2); D[1, 1] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt
        s = float((S * np.diag(D)).sum() / max((A0 ** 2).sum(), 1e-12)); return s, R, mb - s * R @ ma
    for _ in range(4):
        if w.sum() < 8: return None
        s, R, t = fit(Xm[w], G[w]); r = np.linalg.norm(s * Xm @ R.T + t - G, axis=1); w = np.isfinite(r) & (r < max(float(np.percentile(r[np.isfinite(r)], 80)), grenze))
    return math.degrees(math.atan2(R[1, 0], R[0, 0])), s


GPS_MAX_DREH, GPS_MAX_MASS = 15.0, 0.15   # wie die Grenzen des GPS-Tors (lage_gps_pruefen.py --max_dreh 15 --max_skala 0.15) - die Ausrichtung waehlt keine Lage, die das Tor sicher verwirft

# 22.11.2026 GPS-ANKER (Nulllauf schwabentor-1122d, vereinte Seiten 0+1, 507 Bilder): der GPS-Fit der Kameras war gut (148 Kameras, Rest 4,5 m, GPS-SEITEN-Tor stimmig),
# aber der LoD2-Feinfit dreht die Lage mit freier Drehung 22 Grad weg und schrumpft den Massstab auf 0,81 (Guete aller Loesungen nur 5-6 %, bester gegen zweitbesten
# Rasterwert 6 gegen 5 %: LoD2 bestimmt die Lage dieser Wolke kaum - Wolke reicht ueber dem Objekt nur bis ~19-23 m von 46 m LoD2, 2/3 der Punkte nicht an LoD2-Flaechen).
# Alle GPS-Startkandidaten erbten denselben Rastermassstab -> nur EINE unterscheidbare Loesung, sie fiel durchs GPS-Veto. Jetzt: ist das Foto-GPS als Lagebeleg stark
# (>= GPS_ANKER_MIN_KAM Kameras, Rest < 8 m), liefert der GPS-Fit die Startlage UND die Grenzen eines zusaetzlichen Feinfits (Drehung um das Lot, Massstab, Versatz, Kippung
# begrenzt, enger als das GPS-Tor); LoD2/DGM1 verfeinern nur innerhalb dieses Kastens (Hoehe bleibt frei: kommt aus DGM1/Kamerahoehe, nicht aus GPS - Quellen getrennt).
# Wenige Geotags (Martinstor 15-17, Objektstandort statt Kamerastandort) -> kein Anker, Verhalten wie bisher. Abschalten zum Vergleich: AUSR_GPS_ANKER=0.
GPS_ANKER_MIN_KAM, GPS_ANKER_MAX_REST = 40, 8.0
GPS_ANKER_DREH, GPS_ANKER_MASS, GPS_ANKER_VERSATZ, GPS_ANKER_KIPP = 8.0, 0.08, 4.0, 3.0


def gps_anker_aktiv(n_kam, rest_m, det_pos=True):
    """Traegt das Foto-GPS die Lage allein (genug Kameras im robusten Fit, kleiner Rest, nicht gespiegelt)? Abschaltbar per AUSR_GPS_ANKER=0."""
    if os.environ.get("AUSR_GPS_ANKER") == "0": return False
    return bool(det_pos) and int(n_kam) >= GPS_ANKER_MIN_KAM and math.isfinite(rest_m) and float(rest_m) < GPS_ANKER_MAX_REST


def gps_anker_grenzen(p0, dreh=GPS_ANKER_DREH, mass=GPS_ANKER_MASS, versatz=GPS_ANKER_VERSATZ, kipp=GPS_ANKER_KIPP):
    """Kasten fuer den Feinfit um die GPS-Startlage p0 = [log s, rotvec (3), t (3)] (Parameter von zu_modell): Drehung um das Lot +-dreh Grad, Kippung +-kipp Grad,
    Massstab +-mass (relativ), Lage waagerecht +-versatz m, Hoehe frei. Liefert (lo, hi) fuer least_squares."""
    p0 = np.asarray(p0, float); lo = np.full(7, -np.inf); hi = np.full(7, np.inf)
    lo[0], hi[0] = p0[0] + math.log(1 - mass), p0[0] + math.log(1 + mass)
    for i, w in ((1, kipp), (2, kipp), (3, dreh)): lo[i], hi[i] = p0[i] - math.radians(w), p0[i] + math.radians(w)
    for i in (4, 5): lo[i], hi[i] = p0[i] - versatz, p0[i] + versatz
    return lo, hi


# 22.11.2026 (Lauf kette-schwabentor-anker-1122e): der feste Kasten +-8 Grad / +-8 % wurde von LoD2 bis an den Rand gedrueckt (Ergebnis +8,0 Grad x1,089 gegen GPS),
# obwohl der GPS-Fit selbst auf +-0,4 Grad / +-1,3 % (1 Sigma, Bootstrap ueber 135 Kameras) bestimmt ist und LoD2 die Drehung kaum festlegt (Wandabdeckung 18-25 %, beste
# Naehe-Identitaet 33 % gegen 29 %). Eine Verfeinerung, die 18 Sigma vom GPS-Fit am Rand klebt, ist kein Messwert, sondern ein Mittel zweier widersprechender Quellen
# (KERNMETHODE: nicht mitteln). Jetzt: Kasten Drehung/Massstab = GPS_ANKER_K x Bootstrap-Sigma des GPS-Fits, nach unten begrenzt (ANNAHME: raeumlich korrelierte GPS-Fehler
# in Gassen, die der Bootstrap nicht sieht - 2 Grad / 3 %), nach oben die alten festen Werte. Versatz bleibt fest (+-4 m): ein gemeinsamer GPS-Versatz aller Kameras
# veraendert Drehung/Massstab nicht, steckt aber auch nicht in der Bootstrap-Streuung.
GPS_ANKER_K, GPS_ANKER_DREH_MIN, GPS_ANKER_MASS_MIN = 3.0, 2.0, 0.03


def gps_fit_streuung(Cxy, Mxy, w, n=200, seed=0):
    """Bootstrap-Streuung (1 Sigma) des 2D-GPS-Fits Mxy ~ k Rg Cxy + tg auf den Kameras w: (Sigma Drehung in Grad, Sigma Massstab relativ). None bei < 8 Kameras."""
    iw = np.flatnonzero(np.asarray(w, bool))
    if len(iw) < 8: return None
    rng = np.random.default_rng(seed); dr, ks = [], []
    for _ in range(n):
        i = rng.choice(iw, len(iw)); mc, cc = Mxy[i].mean(0), Cxy[i].mean(0)
        try: U, S, V = np.linalg.svd((Mxy[i] - mc).T @ (Cxy[i] - cc))
        except np.linalg.LinAlgError: continue
        D = np.diag([1, np.sign(np.linalg.det(U @ V))]); Rg = U @ D @ V; dr.append(math.atan2(Rg[1, 0], Rg[0, 0])); ks.append((S * np.diag(D)).sum() / max(((Cxy[i] - cc) ** 2).sum(), 1e-12))
    if len(dr) < 20: return None
    dr = np.asarray(dr); dr = (dr - dr[0] + math.pi) % (2 * math.pi) - math.pi                   # Winkel um eine Probe abwickeln
    return float(math.degrees(np.std(dr))), float(np.std(ks) / max(np.mean(ks), 1e-12))


def gps_anker_kasten(streuung):
    """Halbbreiten (Drehung Grad, Massstab relativ) des Anker-Kastens aus der Bootstrap-Streuung des GPS-Fits: K x Sigma, begrenzt auf [Minimum, alte feste Werte].
    Ohne Streuung (None) die alten festen Werte."""
    if streuung is None: return GPS_ANKER_DREH, GPS_ANKER_MASS
    sd, sm = streuung
    if not (math.isfinite(sd) and math.isfinite(sm)): return GPS_ANKER_DREH, GPS_ANKER_MASS
    return float(min(max(GPS_ANKER_K * sd, GPS_ANKER_DREH_MIN), GPS_ANKER_DREH)), float(min(max(GPS_ANKER_K * sm, GPS_ANKER_MASS_MIN), GPS_ANKER_MASS))


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
    # 1b. Lot aus dem KAMERABLICK (19.11.2026, Martinstor mit Drohnenclips: Kamerazentren nicht in einer Ebene, Ebenennormale 87 Grad neben dem Lot -> Modell lag auf der Seite,
    #     alle Lage-Tore rot, 3D-Seite 'Muell'). Fotos werden fast immer waagerecht gehalten: die Bild-x-Achse jeder Kamera liegt horizontal, egal wie steil sie blickt.
    #     Lot = Richtung, die auf moeglichst vielen x-Achsen senkrecht steht (kleinster Singulaervektor, Ausreisser wie Hochformat/gerollte Bilder iterativ raus).
    #     Gilt nur, wenn er der Kameraebene um > 15 Grad widerspricht und >= 50 % der Kameras ihn stuetzen - sonst bleibt das bisherige Lot (alte Laeufe unveraendert).
    try:
        _cwf = lambda im: im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
        _Rm = np.array([np.asarray(_cwf(im).rotation.matrix(), float) for im in ims]); _X = _Rm[:, 0, :]; _in = np.ones(len(_X), bool)
        for _ in range(5):
            up_b = np.linalg.svd(_X[_in], full_matrices=False)[2][2]; _in = np.abs(_X @ up_b) < np.sin(np.radians(15))
            if _in.sum() < 8: break
        if _in.sum() >= 8:
            if np.median(_Rm[_in, 1, :] @ up_b) > 0: up_b = -up_b                                  # Bild-y zeigt nach unten -> Lot entgegengesetzt
            _w = float(np.degrees(np.arccos(min(1.0, abs(float(up @ up_b)))))); _ant = float(_in.mean())
            print(f"Lot aus Kamerablick: {_in.sum()} von {len(_X)} Kameras waagerecht gehalten ({100 * _ant:.0f} %), Winkel zum Lot der Kameraebene {_w:.1f} Grad")
            if _w > 15 and _ant >= 0.5:
                print(f"ACHTUNG LOT: Kameraebene und Kamerablick widersprechen sich um {_w:.0f} Grad (Kameras nicht in einer Ebene: Drohne/Hoehenunterschiede?) - es gilt das Lot aus dem Kamerablick", flush=True)
                up = up_b
    except Exception as _e: print("HINWEIS Lot aus Kamerablick nicht bestimmbar:", _e)
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
    # 19.11.2026 (Martinstor: Wolke deckt ein ganzes Viertel aus Drohnen-/Strassenclips, GPS unbrauchbar -> s0 aus Wolkenausdehnung 0,375, richtig ~0,06; das Suchband s0/4..4 s0
    # enthielt den Massstab nicht, das Tor war im Modell 17 statt 60 m hoch). Unabhaengiger Massstab: Strassenkameras stehen ~1,6 m ueber dem Boden (ANNAHME --kamerahoehe).
    # Boden je Kamera = 3. Perzentil der Hoehe der 300 waagerecht naechsten Wolkenpunkte; Strassenkameras = untere Haelfte der Hoehen (Drohne/Fenster fallen weg).
    s_kam = None
    try:
        from scipy.spatial import cKDTree as _KD
        _kd = _KD(Q[:, :2]); _, _ix = _kd.query(Cq[:, :2], k=min(300, len(Q))); _bod = np.percentile(Q[_ix, 2], 3, axis=1); _hk = Cq[:, 2] - _bod; _hk = _hk[_hk > 0]
        if len(_hk) >= 20:
            _hs = float(np.median(_hk[_hk <= np.median(_hk)])); s_kam = _hs / a.kamerahoehe[0]
            print(f"Massstab aus Kamerahoehe: Strassenkameras {_hs:.3f} SfM-Einheiten ueber dem Boden -> {s_kam:.4f} SfM-Einheiten/m (ANNAHME {a.kamerahoehe[0]} m; Wolkenausdehnung {s0:.4f})")
    except Exception as _e: print("HINWEIS Massstab aus Kamerahoehe nicht bestimmbar:", _e)
    _kam_gilt = bool(s_kam) and not s_gps
    if s_kam and s_gps and not (1 / 1.6 < s_kam / s_gps < 1.6): print(f"ACHTUNG MASSSTAB: Foto-GPS ({s_gps:.4f}) und Kamerahoehe ({s_kam:.4f}) widersprechen sich um Faktor {max(s_kam / s_gps, s_gps / s_kam):.1f} - es gilt GPS, Ergebnis an der Gebaeudehoehe pruefen", flush=True)
    if _kam_gilt:
        if not (1 / 2.0 < s_kam / s0 < 2.0): print(f"ACHTUNG MASSSTAB: Wolkenausdehnung ({s0:.4f}) und Kamerahoehe ({s_kam:.4f}) widersprechen sich um Faktor {max(s_kam / s0, s0 / s_kam):.1f} (Wolke deckt mehr als das Objekt?) - es gilt die Kamerahoehe, Suche {s_kam / 2:.4f} .. {s_kam * 2:.4f}", flush=True)
        s0 = s_kam
    print(f"Startmassstab s0 = {s0:.4f} SfM-Einheiten/m ({'Foto-GPS' if s_gps else 'Kamerahoehe' if _kam_gilt else 'Wolkenausdehnung'}), Toleranz 0,75 m * s0/s (konstant in SfM-Einheiten)")
    _band = 1.5 if s_gps else (2.0 if _kam_gilt else 4.0)                                     # 15.11.: mit GPS-Massstab nur +-50 % suchen (GPS lag 6-8 % neben LoD2; Kaufhaus: ohne Grenze gewann ein 2,6-fach geschrumpftes Modell, Wolke 9 m hoch)
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
    GPS_PRUEF = None; GPS_ANKER = None; GPS_EHRLICH = None; GPS_START = None
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
            thg = math.atan2(Rg[1, 0], Rg[0, 0]); GPS_START = (1.0 / k_, thg, float(tg[0]), float(tg[1]))
            for _dx, _dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (0, 0)): top.insert(0, (-1.0, 1.0 / k_, thg, float(tg[0]) + _dx, float(tg[1]) + _dy))   # GPS-Lage +-4 m (Handy-GPS in der Gasse), Fangbereich Feinfit ~3 m
            print(f"GPS-Startkandidat: Massstab {1 / k_:.4f} SfM-Einheiten/m, Drehung {math.degrees(thg):.0f} Grad, Rest Median {np.median(res):.1f} m ({int(w_.sum())} von {len(w_)} Kameras)")
        else: print(f"GPS-Startkandidat nicht benutzt: Rest Median {np.median(res):.1f} m, {int(w_.sum())} Kameras")
        if np.linalg.det(Rg) > 0 and np.median(res) < 8 and int(w_.sum()) >= 15: GPS_PRUEF = (np.array([i for i, _ in _gk]), Mxy, 1.0 / k_)   # guter GPS-Fit -> Veto fuer Loesungen (unabhaengiger Lagebeleg)
        if GPS_PRUEF is not None:
            # 22.11.2026 EHRLICHE GPS-Unsicherheit (tools/gps_unsicherheit.py; schwabentor-1122: Nah-GPS EINER Sitzung systematisch +9,4 Grad / x0,867 verzerrt, der
            # Bootstrap-Kasten +-2 Grad / +-4,2 % sperrte die Ausrichtung in die falsche Lage). Bootstrap (Zufall) + systematischer Anteil je Sitzung x Ring (Hebel).
            # Dasselbe Mass rechnet das GPS-Tor (lage_gps_pruefen). Ist der ehrliche Kasten breiter als der alte Anker (8 Grad / 8 %), TRAEGT das GPS die Lage nicht:
            # kein Anker, nur Veto; dann entscheiden unabhaengige Proben (tools/lage_proben.py) zwischen den LoD2-Loesungen.
            _gidx = [i for i, _ in _gk]; _rob = GU.robust_fit2d(Cxy, Mxy) if np.isfinite(Cxy).all() else None   # wie das GPS-Tor (RANSAC < 10 m)
            _wr = _rob[3] if _rob is not None and _rob[3].sum() >= 15 else w_; _str0 = gps_fit_streuung(Cxy, Mxy, _wr)
            GPS_EHRLICH = GU.ehrlich(Mxy, _wr, zeiten=[GPS_ZEIT.get(i) for i in _gidx], M=Cxy, sd_dreh_zufall=(_str0[0] if _str0 else 0.0), sd_mass_zufall=(_str0[1] if _str0 else 0.0))
            if _rob is not None and _rob[3].sum() >= 15:                                       # Bezugslage der Lageproben = robuster GPS-Fit (Mxy ~ s R Cxy + t)
                GPS_START = (1.0 / _rob[0], math.atan2(_rob[1][1, 0], _rob[1][0, 0]), float(_rob[2][0]), float(_rob[2][1]))
                print(f"GPS robust (wie GPS-Tor): {int(_rob[3].sum())} von {len(_rob[3])} Kameras < 10 m, Massstab {1.0 / _rob[0]:.4f} SfM-Einheiten/m, Drehung {math.degrees(GPS_START[1]):.1f} Grad"
                      f" (getrimmter Fit: {1 / k_:.4f}, {math.degrees(math.atan2(Rg[1, 0], Rg[0, 0])):.1f} Grad)", flush=True)
            print(GPS_EHRLICH["text"], flush=True)
        if GPS_PRUEF is not None and gps_anker_aktiv(int(w_.sum()), float(np.median(res[w_])) if w_.any() else float("inf"), np.linalg.det(Rg) > 0) and (GPS_EHRLICH is None or GPS_EHRLICH["anker"] is not None or os.environ.get("AUSR_GPS_EHRLICH") == "0"):
            _str = gps_fit_streuung(Cxy, Mxy, w_); _kd, _km = gps_anker_kasten(_str)           # Kasten aus der Bootstrap-Unsicherheit des GPS-Fits (22.11.2026, 1122e)
            if GPS_EHRLICH is not None and GPS_EHRLICH["anker"] is not None and os.environ.get("AUSR_GPS_EHRLICH") != "0": _kd, _km = GPS_EHRLICH["anker"]   # ehrlicher Kasten (Zufall + Sitzung)
            GPS_ANKER = dict(s=1.0 / k_, drehung=math.atan2(Rg[1, 0], Rg[0, 0]), t=[float(tg[0]), float(tg[1])], kameras=int(w_.sum()), rest_m=float(np.median(res[w_])),
                             sigma_drehung_grad=(_str[0] if _str else None), sigma_massstab=(_str[1] if _str else None), kasten_drehung_grad=_kd, kasten_massstab=_km)
            print(f"GPS-ANKER: Foto-GPS traegt die Lage ({GPS_ANKER['kameras']} Kameras, Rest Median {GPS_ANKER['rest_m']:.1f} m"
                  + (f", Bootstrap-Sigma {_str[0]:.2f} Grad / {100 * _str[1]:.1f} %" if _str else "") + f") - zusaetzlicher LoD2-Feinfit nur im Kasten Drehung +-{_kd:.1f} Grad, "
                  f"Massstab +-{100 * _km:.1f} %, Versatz +-{GPS_ANKER_VERSATZ:.0f} m, Kippung +-{GPS_ANKER_KIPP:.0f} Grad um den GPS-Fit (Hoehe frei: DGM1/Kamerahoehe)", flush=True)
        elif GPS_PRUEF is not None and GPS_EHRLICH is not None and GPS_EHRLICH["anker"] is None and os.environ.get("AUSR_GPS_EHRLICH") != "0":
            print("GPS-ANKER nicht aktiv: das Foto-GPS legt Drehung/Massstab ehrlich gerechnet nicht fest (systematischer Fehler je Fotositzung) - nur Veto; unabhaengige Proben entscheiden", flush=True)
        elif GPS_PRUEF is not None: print(f"GPS-ANKER nicht aktiv: {int(w_.sum())} Kameras im GPS-Fit (noetig >= {GPS_ANKER_MIN_KAM}) oder Rest >= {GPS_ANKER_MAX_REST:.0f} m - bisheriges Verhalten")
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

    def fein(p0, X, schwellen=(3.0, 1.5, 0.8), band=0.35, grenzen=None):
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
                if grenzen is not None: lo, hi = np.asarray(grenzen[0], float), np.asarray(grenzen[1], float)   # GPS-Anker: Kasten um den GPS-Fit
                p = least_squares(r, np.clip(p, lo + 1e-9, hi - 1e-9), loss="huber", f_scale=sw / 3 * math.exp(ls0), max_nfev=200, bounds=(lo, hi)).x
        M = zu_modell(p, X); d, _ = nn(M); ok = d * math.exp(p[0]) < schwellen[-1] * s0      # Inlier-Schwelle in SfM-Einheiten (massstabsneutral)
        return p, ok.mean(), float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else np.inf, ok

    # 22.11.2026 ZWISCHENSTAND der Feinfits (Auftrag: --loesung K rechnete die ganze Ausrichtung je K neu, ~9 min). Jeder Aufruf von fein() ist deterministisch in
    # (Startwert, Punkte, Schwellen, Band, Grenzen); sein Ergebnis wird unter einem Schluessel aus EINGABEN (Dateigroesse/-zeit von objekt.json, Kameras, Wolke, Fotoordner,
    # alle Argumente ausser --loesung/--schreiben, AUSR_*-Umgebung) + CODE-STAND (tools/code_stand.py: dieses Werkzeug samt Hilfsmodulen) in
    # messprotokoll/.ausr_zwischen<name>.pkl abgelegt. Der naechste Lauf mit gleichem Schluessel nimmt die Werte (Treffer werden gezaehlt); jede Aenderung = neue Rechnung.
    # Abschalten: AUSR_ZWISCHEN=0.
    import pickle as _pk, hashlib as _hl
    _zw_an = os.environ.get("AUSR_ZWISCHEN") != "0"; _zw_pfad = os.path.join(od, "messprotokoll", f".ausr_zwischen{('-' + a.name) if a.name else ''}.pkl"); _zw = {}; _zw_treffer = [0, 0]
    if _zw_an:
        try:
            from code_stand import code_stand as _cs
            def _st(q):
                try: st_ = os.stat(q); return f"{q}|{st_.st_size}|{int(st_.st_mtime)}"
                except Exception: return f"{q}|fehlt"
            _fdir = a.fotos or obj.get("fotos_dir", ""); _fl = sorted(os.listdir(_fdir)) if _fdir and os.path.isdir(_fdir) else []
            _arg = {k_: v_ for k_, v_ in vars(a).items() if k_ not in ("loesung", "schreiben")}
            _zw_schl = _hl.sha1("|".join([_cs("sfm_lod2_ausrichten.py"), _st(a.objekt), _st(a.kameras or ""), _st(a.dicht or ""), _st(a.sparse or ""), _fdir, str(len(_fl)), _hl.sha1("".join(_fl).encode()).hexdigest(),
                                          json.dumps(_arg, sort_keys=True, default=str), json.dumps({k_: v_ for k_, v_ in os.environ.items() if k_.startswith("AUSR_") or k_ == "ALIGN_CPU"}, sort_keys=True)]).encode()).hexdigest()
            if os.path.exists(_zw_pfad):
                _alt = _pk.load(open(_zw_pfad, "rb"))
                if _alt.get("schluessel") == _zw_schl: _zw = _alt.get("fein", {}); print(f"ZWISCHENSTAND: {len(_zw)} Feinfits aus {_zw_pfad} (gleiche Eingaben + Code-Stand)", flush=True)
                else: print("ZWISCHENSTAND: vorhanden, aber andere Eingaben/Code-Stand - wird neu gerechnet", flush=True)
        except Exception as _e: print("HINWEIS Zwischenstand aus:", type(_e).__name__, _e); _zw_an = False
    _fein_rechnen = fein
    def fein(p0, X, schwellen=(3.0, 1.5, 0.8), band=0.35, grenzen=None):
        if not _zw_an: return _fein_rechnen(p0, X, schwellen=schwellen, band=band, grenzen=grenzen)
        X_ = np.ascontiguousarray(X); k_ = _hl.sha1(np.round(np.asarray(p0, float), 10).tobytes() + repr((X_.shape, schwellen, band)).encode() + X_[::max(1, len(X_) // 997)].tobytes()
                                                    + (b"" if grenzen is None else np.asarray(grenzen, float).tobytes())).hexdigest()
        if k_ in _zw:
            _zw_treffer[0] += 1; pz, fr_, rm_, okb = _zw[k_]; return np.array(pz), fr_, rm_, np.unpackbits(okb, count=len(X_)).astype(bool)
        _zw_treffer[1] += 1; r_ = _fein_rechnen(p0, X, schwellen=schwellen, band=band, grenzen=grenzen)
        _zw[k_] = (np.asarray(r_[0], float).tolist(), float(r_[1]), float(r_[2]), np.packbits(np.asarray(r_[3], bool))); return r_
    def _zw_sichern():
        if not _zw_an: return
        try:
            tmp_ = f"{_zw_pfad}.neu{os.getpid()}"; os.makedirs(os.path.dirname(_zw_pfad), exist_ok=True)
            with open(tmp_, "wb") as f_: _pk.dump(dict(schluessel=_zw_schl, fein=_zw), f_)
            os.replace(tmp_, _zw_pfad); print(f"ZWISCHENSTAND gesichert: {len(_zw)} Feinfits (Treffer {_zw_treffer[0]}, neu {_zw_treffer[1]}) -> {_zw_pfad}", flush=True)
        except Exception as _e: print("HINWEIS Zwischenstand nicht gesichert:", type(_e).__name__, _e)

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
        # 19.11.2026 HOEHENPROBE (Martinstor ohne brauchbares GPS: die 2D-Wandsuche bevorzugt das geschrumpfte Modell, Turm 40 statt 60 m). Unabhaengiges Mass: Hoehe der Wolke
        # ueber dem Objektgrundriss gegen die LoD2-Hoehe des Objekts. Weicht sie > 13-15 % ab, wird die Loesung abgewertet (x Verhaeltnis) und ein zweiter Feinfit mit dem
        # um das Verhaeltnis korrigierten Massstab gerechnet (Lage des Objekts bleibt, da das Modellsystem im Objekt zentriert ist). Nur ohne GPS-Massstab (dort gilt das GPS-Raster).
        if not s_gps and sc != -1.0:
            try:
                _oe = T[Te]; _Ho = float(_oe[:, 2].max()); _bx = (_oe[:, 0].min() - 1, _oe[:, 0].max() + 1, _oe[:, 1].min() - 1, _oe[:, 1].max() + 1)
                def _hq(p_):
                    M_ = zu_modell(p_, Q); m_ = (M_[:, 0] > _bx[0]) & (M_[:, 0] < _bx[1]) & (M_[:, 1] > _bx[2]) & (M_[:, 1] < _bx[3])
                    return float(np.percentile(M_[m_, 2], 99.5)) / _Ho if m_.sum() >= 200 and _Ho > 3 else None
                _q = _hq(p)
                if _q is not None and _q > 0:
                    loes[-1] = (frac * ab * min(_q, 1 / _q), rms, p, ok, frac, ab)
                    print(f"      Hoehenprobe: Wolke ueber dem Objektgrundriss {_q * _Ho:.1f} m, LoD2 {_Ho:.1f} m (Verhaeltnis {_q:.2f}) -> Guete {100 * loes[-1][0]:.0f} %")
                    if not (0.87 < _q < 1.15) and 0.3 < _q < 3.3:
                        _p1 = list(p); _p1[0] = p[0] + math.log(_q); _p1[4] = p[4] / _q; _p1[5] = p[5] / _q; _p1[6] = 1.6 - np.median(Cq[:, 2]) / math.exp(_p1[0])
                        _p2, _f2, _r2, _o2 = fein(_p1, Q, band=0.12); _a2 = abdeckung(_p2, Q); _q2 = _hq(_p2); _g2 = _f2 * _a2 * (min(_q2, 1 / _q2) if _q2 else 0.5); loes.append((_g2, _r2, _p2, _o2, _f2, _a2))
                        print(f"      Hoehenkorrektur: Massstab {math.exp(_p2[0]):.4f}: Inlier {100 * _f2:.0f} %, Abdeckung {100 * _a2:.0f} %, RMS {_r2:.2f} m, Hoehenverhaeltnis {(_q2 or 0):.2f} -> Guete {100 * _g2:.0f} %")
            except Exception as _e: print("      HINWEIS Hoehenprobe nicht moeglich:", _e)
    _anker_p = []                                                                             # GPS-Anker: Startlage = GPS-Fit, LoD2 verfeinert nur im Kasten
    if GPS_ANKER is not None:
        _pa = [math.log(GPS_ANKER["s"]), 0.0, 0.0, GPS_ANKER["drehung"], GPS_ANKER["t"][0], GPS_ANKER["t"][1], 1.6 - float(np.median(Cq[:, 2])) / GPS_ANKER["s"]]
        _gr = gps_anker_grenzen(_pa, dreh=GPS_ANKER["kasten_drehung_grad"], mass=GPS_ANKER["kasten_massstab"]); _pp, _fr, _rm, _ok = fein(_pa, Q, grenzen=_gr); _ab = abdeckung(_pp, Q); loes.append((_fr * _ab, _rm, _pp, _ok, _fr, _ab)); _anker_p.append((_pp, _gr))
        print(f"   GPS-Anker-Feinfit: Inlier {100 * _fr:.0f} %, Objektwand-Abdeckung {100 * _ab:.0f} %, RMS {_rm:.2f} m, Massstab {math.exp(_pp[0]):.4f} (GPS {GPS_ANKER['s']:.4f}), "
              f"Drehung {math.degrees(_pp[3] - _pa[3]):+.1f} Grad gegen GPS, Versatz {np.hypot(_pp[4] - _pa[4], _pp[5] - _pa[5]):.1f} m", flush=True)
        _rand = [nm_ for i_, nm_ in enumerate(("Massstab", "Kippung x", "Kippung y", "Drehung", "Versatz x", "Versatz y")) if min(_pp[i_] - _gr[0][i_], _gr[1][i_] - _pp[i_]) < 1e-4]
        if _rand: print(f"   HINWEIS GPS-Anker: LoD2 drueckt gegen den Kastenrand ({', '.join(_rand)}) - LoD2 und Foto-GPS widersprechen sich dort; Lage-Tore + Hoehe (DOM1) entscheiden, nicht mitteln", flush=True)
    if GPS_PRUEF is not None:                                                                # 15.11.: GPS-Veto (v2: Loesung mit 2,5-fach zu grossem Modell gewann mit Guete 4 %)
        _gi, _gm, _gs = GPS_PRUEF
        def _gps_rest(p_): return float(np.median(np.linalg.norm(zu_modell(p_, Cq[_gi])[:, :2] - _gm, axis=1)))
        _mband = max(0.25, math.log(1 + 2 * GPS_EHRLICH["mass_sd_rel"])) if (GPS_EHRLICH is not None and os.environ.get("AUSR_GPS_EHRLICH") != "0") else 0.25   # ehrlich: 2 Sigma
        _kons = [l for l in loes if _gps_rest(l[2]) < 12 and abs(l[2][0] - math.log(_gs)) < _mband]
        print(f"GPS-Veto: {len(_kons)} von {len(loes)} Loesungen passen zum Foto-GPS (Kamerarest < 12 m, Massstab +-28 %); beste verworfene Guete {100 * max([l[0] for l in loes if not any(l is k for k in _kons)], default=0):.0f} %")
        # 22.11.2026 (Nulllauf schwabentor-1122): der Kamerarest < 12 m laesst eine um 20 Grad gedrehte Loesung durch, wenn die Kameras nah am Objekt stehen (20 Grad bei 15 m
        # = 5 m) - gewaehlt wurde Guete 5 %, das GPS-Tor maß danach 20 Grad (90 %: 18-22) und brach ab. Jetzt zusaetzlich Drehung und Massstab des GPS-Fits je Loesung mit
        # den GRENZEN DES GPS-TORS; bleibt so keine Loesung, gilt die alte Auswahl (gemeldet) - es wird nie weniger gewaehlt als vorher.
        _dm = [(l, gps_dreh_massstab(zu_modell(l[2], Cq[_gi])[:, :2], _gm)) for l in _kons]
        if GPS_EHRLICH is not None and os.environ.get("AUSR_GPS_EHRLICH") != "0":                # gleiche Regel wie das GPS-Tor (ehrliches 90-%-Band, feste Grenzen)
            _sdd, _sdm = GPS_EHRLICH["dreh_sd_grad"], GPS_EHRLICH["mass_sd_rel"]
            _kons2 = [l for l, dm in _dm if dm is not None and not GU.widerspruch(dm[0], GU.band(dm[0], 0.0, _sdd), dm[1], GU.band(dm[1], 0.0, _sdm), GPS_MAX_DREH, GPS_MAX_MASS)]
        else: _kons2 = [l for l, dm in _dm if dm is not None and abs(dm[0]) <= GPS_MAX_DREH and abs(dm[1] - 1.0) <= GPS_MAX_MASS]
        print(f"GPS-Veto Drehung/Massstab (Grenzen des GPS-Tors {GPS_MAX_DREH:.0f} Grad / {100 * GPS_MAX_MASS:.0f} %): {len(_kons2)} von {len(_kons)} Loesungen; "
              + ", ".join(f"{dm[0]:+.0f} Grad x{dm[1]:.2f}" for _, dm in _dm[:8] if dm is not None))
        if _kons2: _kons = _kons2
        elif _kons: print("WARNUNG GPS-Veto: keine Loesung innerhalb der Drehungs-/Massstabsgrenzen des GPS-Tors - alte Auswahl (Kamerarest < 12 m), das GPS-Tor wird sie vermutlich verwerfen")
        if _kons: loes = _kons
        else: print("WARNUNG GPS-Veto: KEINE Loesung passt zum Foto-GPS - Ergebnis nicht glauben (Tore entscheiden)")
    # 22.11.2026 UNABHAENGIGE LAGEPROBEN (tools/lage_proben.py) - nur wenn das Foto-GPS vorhanden ist, die Lage aber ehrlich gerechnet NICHT festlegt (kein Anker):
    # (c) Wandfit mit den GESEHENEN Nachbargebaeuden (2D-Suche im ehrlichen GPS-Kasten um die GPS-Startlage) liefert einen zusaetzlichen Kandidaten (3D-Feinfit eng um seinen
    # Bestwert); dann je unterscheidbarer Loesung Proben a) Oberkante/DOM1, b) Kamerahoehe, c) Wandfit -> gewaehlt wird, was alle urteilsfaehigen Proben besteht
    # (lage_proben.entscheiden). Martinstor (kein GPS) und Objekte mit ankerndem GPS laufen wie bisher. Abschalten: AUSR_PROBEN=0 (oder AUSR_GPS_EHRLICH=0).
    LAGE_PROBEN = None
    _proben_an = (GPS_PRUEF is not None and GPS_EHRLICH is not None and GPS_EHRLICH["anker"] is None and GPS_START is not None
                  and os.environ.get("AUSR_GPS_EHRLICH") != "0" and os.environ.get("AUSR_PROBEN") != "0")
    if _proben_an:
        try:
            _cwf2 = lambda im: im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
            _Vq = np.array([np.asarray(_cwf2(im).rotation.matrix(), float)[2] for im in ims]) @ B0.T              # Blickrichtung im Lotsystem
            _fov = np.array([math.degrees(math.atan(CAMS[im.camera_id].width / 2.0 / max(float(list(CAMS[im.camera_id].params)[0]), 1e-6))) for im in ims])
            _sg, _thg, _tx, _ty = GPS_START; _pref = np.array([math.log(_sg), 0.0, 0.0, _thg, _tx, _ty, 1.6 - float(np.median(Cq[:, 2])) / _sg])
            _Yref = zu_modell(_pref, Q); _Cref = zu_modell(_pref, Cq); _Vref = Rot.from_rotvec(_pref[1:4]).apply(_Vq)
            _dz = LP.boden_versatz(_Yref, _Cref[_nah], obj)                                     # Hoehe der Bezugslage an DGM1 (Wandband!), Probe teil0 22.11.
            if _dz is not None: _pref[6] += _dz; _Yref[:, 2] += _dz; _Cref[:, 2] += _dz; print(f"LAGEPROBE Bezugslage: Hoehe {_dz:+.2f} m an den DGM1-Boden unter den Kameras angeglichen", flush=True)
            _polys = LP.grundrisse(obj, 60.0); _zid = obj.get("lod2", {}).get("id"); _ziel = [g for i_, g in _polys if i_ == _zid]
            _seg = LP.gesehene_kanten(_polys, _Cref[_nah], _Vref[_nah], _fov[_nah]); _cp = np.median(_Cref[_nah], 0)
            _box = dict(dreh_grad=float(np.clip(2 * GPS_EHRLICH["dreh_sd_grad"], 5, 20)), mass_rel=float(np.clip(2 * GPS_EHRLICH["mass_sd_rel"], 0.05, 0.25)), versatz_m=6.0)
            _S = LP.wandfit_bestwert(LP.wandband(_Yref, obj), _cp, _seg, _box)
            print(f"LAGEPROBE Wandfit mit Nachbarn: {len(_seg)} gesehene LoD2-Kanten, Kasten +-{_box['dreh_grad']:.0f} Grad / +-{100 * _box['mass_rel']:.0f} % / +-{_box['versatz_m']:.0f} m um die GPS-Lage"
                  + (f" -> Bestwert {(_S.get('fein') or _S['best'])['dreh_grad']:+.2f} Grad, x{1 / (_S.get('fein') or _S['best'])['massstab']:.3f}, Abdeckung {100 * (_S.get('fein') or _S['best'])['abdeckung']:.0f} %, zweiter Gipfel {100 * _S['verhaeltnis']:.0f} %, Rand {_S['rand']}"
                     if _S and _S.get("best") else " -> keine Loesung"), flush=True)
            if _S and _S.get("best") and not _S["rand"]:                                       # Kandidat aus dem Wandfit: 3D-Feinfit eng um den 2D-Bestwert
                _Rz, _m, _tau = LP.wandfit_lage(_S, _cp)
                _pw = np.r_[_pref[0] + math.log(_m), (Rot.from_matrix(_Rz) * Rot.from_rotvec(_pref[1:4])).as_rotvec(), _Rz @ (_pref[4:7] - _cp) / _m + _cp + _tau]
                _pp, _fr, _rm, _ok = fein(_pw, Q, grenzen=gps_anker_grenzen(_pw, dreh=1.0, mass=0.02, versatz=1.0, kipp=GPS_ANKER_KIPP)); _ab = abdeckung(_pp, Q)
                _vt = True
                if GPS_PRUEF is not None:
                    _dmw = gps_dreh_massstab(zu_modell(_pp, Cq[_gi])[:, :2], _gm)
                    _vt = _gps_rest(_pp) < 12 and _dmw is not None and not GU.widerspruch(_dmw[0], GU.band(_dmw[0], 0.0, GPS_EHRLICH["dreh_sd_grad"]), _dmw[1], GU.band(_dmw[1], 0.0, GPS_EHRLICH["mass_sd_rel"]), GPS_MAX_DREH, GPS_MAX_MASS)
                print(f"   Wandfit-Kandidat (3D-Feinfit): Inlier {100 * _fr:.0f} %, Abdeckung {100 * _ab:.0f} %, RMS {_rm:.2f} m, Massstab {math.exp(_pp[0]):.4f}" + ("" if _vt else " - VERWORFEN: verletzt das ehrliche GPS-Veto"), flush=True)
                if _vt: loes.append((_fr * _ab, _rm, _pp, _ok, _fr, _ab))
        except Exception as _e:
            print("HINWEIS Lageproben nicht moeglich:", type(_e).__name__, _e, flush=True); _proben_an = False
    loes.sort(key=lambda l: -l[0])
    _verschieden = []
    for l in loes:                                                                              # unterscheidbare Lagen (Korrekturkreislauf: Loesung K probieren, Tore entscheiden)
        if all(np.degrees((Rot.from_rotvec(l[2][1:4]).inv() * Rot.from_rotvec(v[2][1:4])).magnitude()) > 10 or np.linalg.norm(np.asarray(l[2][4:7]) - np.asarray(v[2][4:7])) > 3
               or (_proben_an and abs(l[2][0] - v[2][0]) > 0.05) for v in _verschieden):    # mit Proben: Massstab > 5 % = eigene Lage (1122g und 1120-Lage: 9 Grad, x1,25)
            _verschieden.append(l)
    if _proben_an:
        try:
            _kand = []
            for i_, l in enumerate(_verschieden):
                _Yk = zu_modell(l[2], Q); _Ck = zu_modell(l[2], Cq)
                _pr = [LP.probe_oberkante(_Yk, obj, _ziel), LP.probe_kamerahoehe(_Yk, _Ck[_nah]), LP.wandfit_urteil(_S, _Yref, _Yk, _cp)]
                _kand.append(dict(name=f"Loesung {i_} (Guete {100 * l[0]:.1f} %, Massstab {math.exp(l[2][0]):.4f})", guete=l[0], proben=_pr))
            _sub = np.random.default_rng(5).choice(len(Q), min(len(Q), 20000), replace=False)
            _ent = LP.entscheiden(_kand, lambda i_, j_: LP.vertraeglich_2d(zu_modell(_verschieden[i_][2], Q[_sub]), zu_modell(_verschieden[j_][2], Q[_sub]), _cp), alt=0)   # 0 = bisherige Wahl (beste Guete)
            for k_ in _kand:
                print(f"   {k_['name']}: {LP.bestanden(k_['proben'])} - " + "; ".join(f"{p_['probe']} {p_['urteil']} ({p_.get('grund', '')})" for p_ in k_["proben"]), flush=True)
            print(f"LAGEPROBEN: {_ent['ergebnis'].upper()} - {_ent['grund']}", flush=True)
            _rang = {"besteht": 0, "kein Urteil": 1, "faellt": 2}; _ord = sorted(range(len(_verschieden)), key=lambda i_: (_rang[_ent["je"][i_]], -_verschieden[i_][0]))
            if _ent["wahl"] is not None: _ord.remove(_ent["wahl"]); _ord.insert(0, _ent["wahl"])
            _verschieden = [_verschieden[i_] for i_ in _ord]
            LAGE_PROBEN = dict(ergebnis=_ent["ergebnis"], grund=_ent["grund"], je_loesung=[dict(urteil=_ent["je"][i_], name=_kand[i_]["name"], proben=_kand[i_]["proben"]) for i_ in _ord],
                               wandsuche=dict(kanten=len(_seg), kasten=_box, verhaeltnis=_S["verhaeltnis"] if _S else None, rand=_S["rand"] if _S else None,
                                              bestwert={k_: v_ for k_, v_ in ((_S.get("fein") or _S.get("best")) or {}).items() if k_ != "ix"} if _S else None),
                               hinweis="Reihenfolge der Loesungen (--loesung K) = bestehende zuerst, dann ohne Urteil, dann durchgefallene; 'keine'/'mehrdeutig' = Lage nicht belegt (gesamtkette: kein Modell)")
        except Exception as _e:
            print("HINWEIS Lageproben-Urteil nicht moeglich:", type(_e).__name__, _e, flush=True)
    _zw_sichern()
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
    _gr_wahl = next((g_ for p_, g_ in _anker_p if p_ is p), None)                               # gewaehlt wurde die GPS-verankerte Loesung -> Bootstrap im selben Kasten
    if _gr_wahl is not None: print("GEWAEHLT: GPS-verankerte Loesung (Lage aus Foto-GPS, LoD2/DGM1 nur verfeinert)")
    # Bootstrap: Massstab-/Lage-Streuung aus Teilstichproben
    rng = np.random.default_rng(1); bs = []
    for _ in range(8):
        sub = rng.choice(len(Q), len(Q) // 2, replace=False); pb, *_ = fein(p, Q[sub], schwellen=(1.5, 0.8), grenzen=_gr_wahl); bs.append(pb)
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
    _zw_sichern()
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
                                       t=t_s.tolist(), t_sigma_m=t_sig.tolist(), inlier_anteil=float(frac), rms_m=float(rms), zweitbeste_inlier=float(zweit), mehrdeutig=mehrdeutig, loesung_nr=i_loes, loesungen_unterscheidbar=len(_verschieden),
                                       lage_proben=LAGE_PROBEN, gps_ehrlich=(dict(dreh_sd_grad=GPS_EHRLICH["dreh_sd_grad"], mass_sd_rel=GPS_EHRLICH["mass_sd_rel"], anker=GPS_EHRLICH["anker"],
                                       systematik=GPS_EHRLICH["systematik"], text=GPS_EHRLICH["text"]) if GPS_EHRLICH else None),
                                       gps_anker=(dict(GPS_ANKER, gewaehlt=_gr_wahl is not None, grenzen=dict(drehung_grad=GPS_ANKER["kasten_drehung_grad"], massstab=GPS_ANKER["kasten_massstab"], versatz_m=GPS_ANKER_VERSATZ, kippung_grad=GPS_ANKER_KIPP)) if GPS_ANKER else None)),
                   ziel=dict(lod2_gebaeude=nb, radius_m=a.radius, boden=gq), kameras=kam,
                   kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)),
                   wolke=dict(n=len(Pm), z_p1=float(np.percentile(Pm[:, 2], 1)), z_p999=float(np.percentile(Pm[:, 2], 99.9))), annahmen=dict(kamerahoehe=dict(h0=a.kamerahoehe[0], sigma=a.kamerahoehe[1], gewicht=a.kamera_gewicht, hinweis="ANNAHME Strassenfotos, robuste Bedingung (Huber)")))
        pth = ergebnis_schreiben(od, sfx, usfx, out, Pm, FARBEN); print("geschrieben:", pth, "+ sfm/punkte_modell, punkte_farben (ein Stand, atomar)")
        # 22.11.2026 (1122e loesung0_zurueck: "AttributeError 'NoneType' object has no attribute 'Sim3d'"): die Kette ruft mit --kameras/--dicht in der GPU-Umgebung
        # (ohne pycolmap); dann ist auch kein COLMAP-Modell geladen (rec None) - schreiben ging in diesem Modus NIE. Die Kette braucht sfm/sparse_modell_<name> nicht
        # (gesamtkette.tore() liest pipe/sfm/sparse/0 + die Ausrichtungs-JSON); Verbraucher sind nur Handwerkzeuge (sfm_lod2_buendel, foto_auswahl, abdeckung,
        # nullstart-Verzerrung). Fuer sie: tools/sparse_modell_schreiben.py (venv-colmap) aus der geschriebenen Transformation.
        if rec is None or pycolmap is None:
            print(f"sparse_modell nicht geschrieben (Modus --kameras/--dicht bzw. ohne pycolmap: kein COLMAP-Modell geladen; die Kette braucht es nicht). Bei Bedarf: "
                  f"/media/oem/scan/venv-colmap/bin/python -I tools/sparse_modell_schreiben.py {a.objekt} {pth} <pipe/sfm/sparse/0>")
        else:
            try:
                sim = pycolmap.Sim3d(1.0 / s, pycolmap.Rotation3d(Rm), tm - Rm @ cm / s); rec.transform(sim); ziel = os.path.join(od, "sfm", f"sparse_modell{usfx}"); os.makedirs(ziel, exist_ok=True); rec.write(ziel)
                print("geschrieben:", ziel, "(COLMAP-Modell im Modellsystem, Meter)")
            except Exception as e: print("sparse_modell nicht geschrieben:", type(e).__name__, e)
    if rc_ende: sys.exit(rc_ende)


if __name__ == "__main__":
    main()
