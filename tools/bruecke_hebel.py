#!/usr/bin/env python3
"""bruecke_hebel.py - SOFTWARE-HEBEL FUER DUENNE BRUECKEN zwischen starren Teilmodellen (22.11.2026, Nutzer: "vollautomatisiert so robust, dass sie auch mit duennen
Bruecken umgehen kann ... und an Stellen, wo es schwach wird, mit Software nochmal mehr rausholt als Nachmatchen"). Bausteine fuer tools/seiten_eck_koppeln.py;
gemessen im Selbsttest tools/versuche/bruecke2_selbsttest.py (bekannte Wahrheit) und an schwabentor-1122.

A  LOT: lot_modell (Fluchtpunkt-Lot je Teil, seiten_gps_vereinen.lot_ausrichtung - dieselbe Funktion wie die Ausrichtung), umeyama_lot (Aehnlichkeit mit R u = v:
   5 Freiheitsgrade), lot_kante (Kante A-B ueber ein Zwischenmodell E: die Lotrichtung in E ist unbekannt (2 Freiheitsgrade), beide Kopplungen E->A, E->B muessen sie
   auf das jeweilige Teil-Lot abbilden -> 12 statt 14 Freiheitsgrade; Ergebnis bildet Lot B exakt auf Lot A ab). Pruefgroesse: winkel_frei = Winkel zwischen den Loten
   nach der FREIEN Kopplung.
B  GEFUEHRTES NACHMESSEN: kandidaten_paare (Bildpaare A x B, die sich laut Naeherungslage sehen muessten: Punkte von a in b sichtbar und umgekehrt, Blickachsen < MAX_WINKEL),
   lg_paare (ALIKED+LightGlue nur fuer diese Paare, tools/lg_match.py --paare, GPU-Deckel), paare_pruefen (je Paar Essentialmatrix-RANSAC + EPIPOLARBAND aus der
   Naeherung: ein verwechseltes Paar verletzt die Naeherungs-Epipolargeometrie), direkte Spuren A<->B ueber die 3D-Punkte der Teilmodelle (Tiefe aus den Spuren der Umgebung, punkte_aus_tiefe, neben
   einer beobachteten Spur), direkt_koppeln (robuste Sim3 B->A aus diesen Spuren, dieselben Annahmeregeln wie seiten_eck_koppeln.kopplung_pruefen).
C  GEMEINSAMER AUSGLEICH: ausgleich (B als starrer Koerper 7 bzw. mit Lot 5 Parameter, gleichzeitig E->A; Quellen: Zwischenmodell-Spuren E-A, E-B + direkte Spuren A-B,
   alles BILDZUORDNUNGEN ueber die Naht; Teil A fest). HALBSTARR: zusaetzlich Verformung von B mit 2 Parametern (Massstabsverlauf a je Teillaenge, Biegung b um
   die Lotachse je Teillaenge, ueber die Hauptachse von B) - die starke Bindung ist das Modell selbst (2 statt 6 x Kameras Freiheitsgrade); angenommen nur, wenn
   signifikant (> SIG_VERFORMUNG sigma). Ausgabe a, b +- sigma = Messwert "Teil in sich verformt".
D  URTEIL: urteil_kante (stark / duenn / zu duenn) aus Hebel, Wiederholbarkeit, unabhaengigen Spuren, Kreisschluss; Schwellen siehe dort.
Datenstruktur: Modell (aus pycolmap.Reconstruction, eigene Arrays: Posen, Merkmale, Punkte) - transformierbar/verformbar ohne pycolmap-Schreibzugriff."""
import os, sys, json, subprocess, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from sim3_robust import umeyama, matrix, anwenden
import seiten_eck_koppeln as EK

MAX_WINKEL = 60.0        # Blickachsen eines Kandidatenpaars hoechstens 60 Grad auseinander (Auftrag; SIFT/ALIKED tragen bis ~60 Grad)
MIN_UEBERLAPP = 0.2      # ANNAHME: >= 20 % der Punkte von a liegen im Bild b (und umgekehrt), Tiefe 0,25-4 x der Bildtiefe von b
JE_BILD = 4              # ANNAHME: je Bild die 4 besten Partner (Kosten begrenzen); MAX_PAARE gesamt
MAX_PAARE = 400
MIN_PAAR = 15            # Zuordnungen je bestaetigtem Paar (wie bruecke_nachmatchen --min-matches)
BAND_ANTEIL = 0.5        # ANNAHME: >= 50 % der RANSAC-Inlier liegen im Naeherungs-Epipolarband, sonst ist das Paar mit der Naeherung unvertraeglich (Verwechslung)
BAND_MIN_PX = 4.0
BAND_SIGMA = 3.0         # Bandbreite = 3 x Kopplungsunsicherheit (Winkel) x Brennweite
TIEFE_RADIUS_PX = 15.0   # ANNAHME: Tiefe eines Merkmals aus den Spuren im Umkreis 15 px (Ebene 1/z linear im Bild), Rest <= 1 %
TIEFE_REST = 0.01
SIG_VERFORMUNG = 3.0
VERFORMUNG_MAX = 0.15    # Gueltigkeits-Guard: |a| <= 15 %, |b| <= 0,15 rad (8,6 Grad) - mehr ist keine Mapper-Verformung, sondern ein falsches Teil


# ---------------------------------------------------------------- Modell
class Modell:
    """Posen (cam_from_world R, t), Kamera (pycolmap.Camera), Merkmale xy + 3D-Punkt-Index je Bild, Punkte P (n x 3). Einheiten des Modells."""
    def __init__(self, rec=None):
        self.namen, self.R, self.t, self.cam, self.xy, self.pid = [], [], [], [], [], []; self.P = np.zeros((0, 3))
        if rec is None: return
        ids = sorted(rec.points3D.keys()); ix = {p: i for i, p in enumerate(ids)}; self.P = np.array([rec.points3D[p].xyz for p in ids]).reshape(-1, 3)
        for im in sorted((i for i in rec.images.values() if i.has_pose), key=lambda i: i.name):
            cw = im.cam_from_world(); p2 = im.points2D
            self.namen.append(im.name); self.R.append(np.asarray(cw.rotation.matrix(), float)); self.t.append(np.asarray(cw.translation, float)); self.cam.append(rec.cameras[im.camera_id])
            self.xy.append(np.array([q.xy for q in p2]).reshape(-1, 2)); self.pid.append(np.array([ix.get(q.point3D_id, -1) if q.has_point3D() else -1 for q in p2], int))
        self.idx = {n: i for i, n in enumerate(self.namen)}

    def C(self, i): return -self.R[i].T @ self.t[i]

    def kopie(self):
        m = Modell(); m.namen, m.cam, m.xy, m.pid, m.idx = self.namen, self.cam, self.xy, self.pid, self.idx
        m.R = [r.copy() for r in self.R]; m.t = [t.copy() for t in self.t]; m.P = self.P.copy(); return m

    def transformiert(self, M):
        """X' = M X (Sim3). Kamera: R' = R Rm^T, t' = s t - R Rm^T tm (Projektion massstabsfrei)."""
        s, Rm, tm = EK.zerlegen(M); m = self.kopie(); m.P = anwenden(M, self.P)
        m.R = [R @ Rm.T for R in self.R]; m.t = [s * t - R @ Rm.T @ tm for R, t in zip(self.R, self.t)]; return m

    def verformt(self, feld):
        """feld: Funktion X (n x 3) -> (X', Rloc (n x 3 x 3) lokale Drehung). Punkte und Kamerazentren werden verschoben, Blickrichtungen mitgedreht."""
        m = self.kopie(); m.P = feld(self.P)[0]; C = np.array([self.C(i) for i in range(len(self.namen))]).reshape(-1, 3); C2, Rl = feld(C)
        m.R = [R @ Rl[i].T for i, R in enumerate(self.R)]; m.t = [-m.R[i] @ C2[i] for i in range(len(self.namen))]; return m

    def ausdehnung(self): return EK.ausdehnung(self.P)


def punkte(E, Z):
    """Wie seiten_eck_koppeln.punkte, fuer Modell: gemeinsame Bilder, gleicher Merkmalsindex, in beiden trianguliert -> (X_E, X_Z, Tiefe in E, gemeinsame Namen)."""
    pe, pz, td, ges = [], [], [], set(); ns = sorted(set(E.namen) & set(Z.namen))
    for n in ns:
        i, j = E.idx[n], Z.idx[n]; a, b = E.pid[i], Z.pid[j]; k = min(len(a), len(b)); w = np.flatnonzero((a[:k] >= 0) & (b[:k] >= 0)); c = E.C(i)
        for x in w:
            key = (a[x], b[x])
            if key in ges: continue
            ges.add(key); pe.append(a[x]); pz.append(b[x]); td.append(float(np.linalg.norm(E.P[a[x]] - c)))   # Tiefe = Abstand zur Kamera des ersten gemeinsamen Bilds (wie EK.punkte)
    if not pe: return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), ns
    return E.P[pe], Z.P[pz], np.array(td), ns


# ---------------------------------------------------------------- A: Lot
def lot_modell(rec, fotos, n_max=150, cache=None):
    """Fluchtpunkt-Lot eines Teilmodells (Bild-x-Rueckfall wie die Ausrichtung). -> dict(oben, quelle, getragen, sigma_grad, hinweis)."""
    import seiten_gps_vereinen as SG
    ims = [im for im in rec.images.values() if im.has_pose]
    l = SG.lot_ausrichtung([im.cam_from_world().rotation.matrix() for im in ims], SG.kameras_fuer_lot(ims, rec.cameras), fotos, n_max, cache)
    fl = l.get("fluchtpunkte") or {}
    return dict(oben=np.asarray(l["oben"], float).tolist(), quelle=l.get("quelle"), getragen=int(fl.get("getragen", 0) or 0), sigma_grad=fl.get("sigma_mittel_grad"),
                streuung_median_grad=fl.get("streuung_median_grad"), hinweis=l.get("hinweis"))


def drehung_auf(u, v):
    """Kleinste Drehung, die u auf v abbildet."""
    u = np.asarray(u, float) / np.linalg.norm(u); v = np.asarray(v, float) / np.linalg.norm(v); w = np.cross(u, v); s = np.linalg.norm(w); c = float(u @ v)
    if s < 1e-12: return np.eye(3) if c > 0 else -np.eye(3) + 2 * np.outer(*(2 * [np.linalg.svd(u[None])[2][1]]))
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]]) / s; a = np.arctan2(s, c); return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def basis(v):
    v = np.asarray(v, float) / np.linalg.norm(v); e1 = np.cross(v, [1.0, 0, 0] if abs(v[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); return np.c_[e1, np.cross(v, e1), v]


def umeyama_lot(X, Y, u, v):
    """Aehnlichkeit Y = s R X + t mit R u = v (u: Lot im X-Rahmen, v: Lot im Y-Rahmen): Drehung nur um v. -> (s, R, t)."""
    X = np.asarray(X, float); Y = np.asarray(Y, float); R0 = drehung_auf(u, v); B = basis(v); mx, my = X.mean(0), Y.mean(0)
    a = (X - mx) @ R0.T @ B; b = (Y - my) @ B
    th = np.arctan2(np.sum(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]), np.sum(a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1])); c, s_ = np.cos(th), np.sin(th)
    Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1.0]]); R = B @ Rz @ B.T @ R0; s = float(np.sum(b * (a @ Rz.T)) / max(np.sum(a * a), 1e-18))
    return s, R, my - s * R @ mx


def _rest(M, X, Y, td):
    s = float(np.cbrt(np.linalg.det(M[:3, :3]))); return np.linalg.norm(anwenden(M, X) - Y, axis=1) / (s * np.maximum(td, 1e-12))


def lot_kante(XA, YA, tA, XB, YB, tB, obenA, obenB, MA, MB, ausdE, ausdA, ausdB):
    """Kante A-B ueber E mit Lot-Zwang. XA/YA: E- und A-Koordinaten der Spuren E-A (tA Tiefe in E), XB/YB fuer E-B; MA, MB: freie Kopplungen E->A, E->B.
    -> dict(winkel_frei_grad, u (Lot in E), MA, MB, pruefung_a, pruefung_b, ok_a, ok_b, grund_a, grund_b)."""
    from scipy.optimize import minimize
    oa = np.asarray(obenA, float) / np.linalg.norm(obenA); ob = np.asarray(obenB, float) / np.linalg.norm(obenB)
    uA = EK.zerlegen(MA)[1].T @ oa; uB = EK.zerlegen(MB)[1].T @ ob
    if uA @ uB < 0: ob = -ob; uB = -uB                                               # Vorzeichen der Teil-Lote aus der freien Kopplung (nur das Vorzeichen)
    wf = float(np.degrees(np.arccos(np.clip(uA @ uB, -1, 1)))); u0 = (uA + uB) / np.linalg.norm(uA + uB); Bs = basis(u0)
    iA = _rest(MA, XA, YA, tA) <= EK.SCHWELLE_REL; iB = _rest(MB, XB, YB, tB) <= EK.SCHWELLE_REL
    def u_von(p): u = Bs @ np.array([p[0], p[1], 1.0]); return u / np.linalg.norm(u)
    def kosten(p):
        u = u_von(p); c = 0.0
        for X, Y, td, inl, o in ((XA, YA, tA, iA, oa), (XB, YB, tB, iB, ob)):
            if inl.sum() < 3: return 1e9
            M = matrix(*umeyama_lot(X[inl], Y[inl], u, o)); c += float(np.sum(np.minimum(_rest(M, X, Y, td), EK.SCHWELLE_REL) ** 2))
        return c
    r = minimize(kosten, [0.0, 0.0], method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-12, maxiter=400)); u = u_von(r.x)
    out = dict(winkel_frei_grad=round(wf, 3), u=u.tolist(), verschiebung_lot_e_grad=round(float(np.degrees(np.arccos(np.clip(u @ u0, -1, 1)))), 3))
    for k, X, Y, td, o, au, az in (("a", XA, YA, tA, oa, ausdE, ausdA), ("b", XB, YB, tB, ob, ausdE, ausdB)):
        M, pr, ok, g = EK.kopplung_pruefen(X, Y, au, az, tiefe=td, fitter=lambda X_, Y_, o=o: umeyama_lot(X_, Y_, u, o))
        out.update({f"M{k}": M, f"pruefung_{k}": pr, f"ok_{k}": ok, f"grund_{k}": g})
    return out


# ---------------------------------------------------------------- B: gefuehrtes Nachmessen
def _fcc(cam):
    p = np.asarray(cam.params, float); m = getattr(cam.model, "name", str(cam.model))
    return (p[0], p[0], p[1], p[2]) if m in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE", "RADIAL_FISHEYE") else (p[0], p[1], p[2], p[3])


def _proj(R, t, cam, X):
    fx, fy, cx, cy = _fcc(cam); Xc = X @ R.T + t; z = Xc[:, 2]; ok = z > 1e-9; uv = np.full((len(X), 2), -1e9)
    uv[ok] = np.c_[fx * Xc[ok, 0] / z[ok] + cx, fy * Xc[ok, 1] / z[ok] + cy]; return uv, z


def _sicht(Mq, i, Mz, j, n_max=300, rng=None):
    """Anteil der von Bild i (Modell Mq) beobachteten Punkte, die im Bild j (Modell Mz, gleicher Rahmen) liegen, Tiefe 0,25-4 x der eigenen Bildtiefe von j."""
    p = Mq.pid[i]; p = p[p >= 0]
    if len(p) == 0: return 0.0
    if len(p) > n_max: p = (rng or np.random.default_rng(0)).choice(p, n_max, replace=False)
    uv, z = _proj(Mz.R[j], Mz.t[j], Mz.cam[j], Mq.P[p]); c = Mz.cam[j]; pj = Mz.pid[j]; pj = pj[pj >= 0]
    if len(pj) == 0: return 0.0
    zj = np.median((Mz.P[pj[:n_max]] @ Mz.R[j].T + Mz.t[j])[:, 2])
    ok = (uv[:, 0] >= 0) & (uv[:, 0] < c.width) & (uv[:, 1] >= 0) & (uv[:, 1] < c.height) & (z > 0.25 * zj) & (z < 4 * zj); return float(ok.mean())


def kandidaten_paare(A, B_in_A, max_winkel=MAX_WINKEL, min_ueberlapp=MIN_UEBERLAPP, je_bild=JE_BILD, max_paare=MAX_PAARE, ausschluss=(), start=()):
    """A, B_in_A: Modelle im selben Rahmen (B mit der Naeherung transformiert). -> [(a_name, b_name, guete)] absteigend (guete = min der beiden Sichtanteile)."""
    rng = np.random.default_rng(0); ach = lambda M, i: M.R[i][2]; ex = set(ausschluss); kand = []
    for i in range(len(A.namen)):
        if A.namen[i] in ex: continue
        for j in range(len(B_in_A.namen)):
            if B_in_A.namen[j] in ex or B_in_A.namen[j] == A.namen[i]: continue
            if np.degrees(np.arccos(np.clip(ach(A, i) @ ach(B_in_A, j), -1, 1))) > max_winkel: continue
            f1 = _sicht(A, i, B_in_A, j, rng=rng)
            if f1 < min_ueberlapp: continue
            f2 = _sicht(B_in_A, j, A, i, rng=rng)
            if f2 >= min_ueberlapp: kand.append((A.namen[i], B_in_A.namen[j], min(f1, f2)))
    st = set(start); kand.sort(key=lambda x: (not (x[0] in st or x[1] in st), -x[2])); na, nb, aus = {}, {}, []   # Radar-Startbilder zuerst
    for a, b, g in kand:
        if na.get(a, 0) >= je_bild and nb.get(b, 0) >= je_bild: continue
        na[a] = na.get(a, 0) + 1; nb[b] = nb.get(b, 0) + 1; aus.append((a, b, round(g, 3)))
        if len(aus) >= max_paare: break
    return aus


def lg_paare(paare, fotos, aus, vram_mb=2500, resize=1600, max_kp=4096, log=None):
    """ALIKED+LightGlue nur fuer die Paare (tools/lg_match.py --paare, venv-seg). -> Pfad der npz oder None."""
    os.makedirs(aus, exist_ok=True); pf = os.path.join(aus, "paare.tsv"); open(pf, "w").write("".join(f"{a}\t{b}\n" for a, b, *_ in paare)); npz = os.path.join(aus, "lg.npz")
    env = dict(os.environ, RCPARK_LG_VRAM_MB=str(max(500, vram_mb - 600)), PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    with open(log or os.path.join(aus, "lg_match.log"), "w") as lg:
        rc = subprocess.call(["/media/oem/scan/venv-seg/bin/python", "-I", os.path.join(T, "lg_match.py"), fotos, npz, "--paare", pf, "--resize", str(resize), "--max-kp", str(max_kp),
                              "--min-matches", str(MIN_PAAR)], stdout=lg, stderr=subprocess.STDOUT, env=env)
    return npz if rc == 0 and os.path.isfile(npz) else None


def _ess(Ra, ta, Rb, tb):
    R = Rb @ Ra.T; t = tb - R @ ta; tx = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]]); return tx @ R


def _epi_px(E, na, nb, f):
    """Abstand von nb zur Epipolarlinie E na (normierte Koordinaten) in Pixeln (x f)."""
    ha = np.c_[na, np.ones(len(na))]; hb = np.c_[nb, np.ones(len(nb))]; l = ha @ E.T; return np.abs(np.sum(l * hb, 1)) / np.maximum(np.linalg.norm(l[:, :2], axis=1), 1e-12) * f


def punkte_aus_tiefe(M, i, q, radius=TIEFE_RADIUS_PX, kmin=4, rest_max=TIEFE_REST):
    """3D-Punkt (Rahmen von M) fuer Bildpunkte q im Bild i aus den beobachteten Spuren der Umgebung: 1/z = a x + b y + c (Ebene im Bild, exakt fuer ebene Flaechen)
    ueber die >= kmin Spuren im Umkreis 'radius' px, nur wenn alle auf 'rest_max' (relativ) zur Ebene passen (Tiefenkanten fallen heraus). Sonst NaN.
    22.11.2026: die erste Fassung (Merkmal <= 3 px neben einer Spur) behielt am Martinstor 231 von 69469 bestaetigten Zuordnungen."""
    from scipy.spatial import cKDTree
    out = np.full((len(q), 3), np.nan); w = np.flatnonzero(M.pid[i] >= 0)
    if len(w) < kmin or len(q) == 0: return out
    Xc = M.P[M.pid[i][w]] @ M.R[i].T + M.t[i]; z = Xc[:, 2]; ok = z > 1e-9; w, Xc, z = w[ok], Xc[ok], z[ok]
    if len(w) < kmin: return out
    n = M.cam[i].cam_from_img(M.xy[i][w].astype(float)); nq = M.cam[i].cam_from_img(np.asarray(q, float)); tr = cKDTree(M.xy[i][w])
    for k, nb in enumerate(tr.query_ball_point(np.asarray(q, float), radius)):
        if len(nb) < kmin: continue
        G = np.c_[n[nb], np.ones(len(nb))]; iz = 1.0 / z[nb]; c, *_ = np.linalg.lstsq(G, iz, rcond=None)
        if np.max(np.abs(G @ c - iz) * z[nb]) > rest_max: continue
        zq = 1.0 / float(np.r_[nq[k], 1.0] @ c)
        if not np.isfinite(zq) or zq <= 0: continue
        out[k] = M.R[i].T @ (zq * np.r_[nq[k], 1.0] - M.t[i])
    return out


def paare_pruefen(npz, A, B, M_A_B, sigma_rad, band_min_px=BAND_MIN_PX):
    """Gematchte Paare gegen die Naeherung pruefen und direkte Spuren A<->B bilden. B im eigenen Rahmen, M_A_B = Naeherung B -> A.
    -> (stat, spuren = Liste (X_A, X_B, tiefe_B, bild_b)); 3D je Seite aus punkte_aus_tiefe."""
    import cv2
    D = np.load(npz, allow_pickle=True); meta = json.loads(str(D["meta"])); gr = meta.get("groesse", {}); BA = B.transformiert(M_A_B)
    stat = dict(paare_gematcht=0, paare_bestaetigt=0, paare_verworfen_band=0, paare_zu_wenig=0, paare_groesse_falsch=0, zuordnungen=0, band_px_median=None); spuren = {}; bander = []
    for k in D.files:
        if not k.startswith("m_"): continue
        a, b = k[2:].split("|", 1)
        if a not in A.idx or b not in B.idx:
            if b in A.idx and a in B.idx: a, b = b, a; m = D[k][:, ::-1]
            else: continue
        else: m = D[k]
        stat["paare_gematcht"] += 1; i, j = A.idx[a], B.idx[b]; ca, cb = A.cam[i], B.cam[j]
        if any(tuple(gr.get(n, (c.width, c.height))) != (c.width, c.height) for n, c in ((a, ca), (b, cb))): stat["paare_groesse_falsch"] += 1; continue
        ka = D["kp_" + a][m[:, 0]].astype(float); kb = D["kp_" + b][m[:, 1]].astype(float); na = ca.cam_from_img(ka); nb = cb.cam_from_img(kb)
        fb = _fcc(cb)[0]; band = max(band_min_px, BAND_SIGMA * sigma_rad * fb); bander.append(band)
        Ea = _ess(A.R[i], A.t[i], BA.R[j], BA.t[j]); d = _epi_px(Ea, na, nb, fb)
        if len(na) < 8: stat["paare_zu_wenig"] += 1; continue
        E, msk = cv2.findEssentialMat(na, nb, np.eye(3), method=cv2.RANSAC, prob=0.999, threshold=1.5 / fb)
        if E is None or msk is None: stat["paare_zu_wenig"] += 1; continue
        inl = msk.ravel() > 0; keep = inl & (d <= band)
        if inl.sum() < MIN_PAAR: stat["paare_zu_wenig"] += 1; continue
        if keep.sum() < MIN_PAAR or keep.sum() < BAND_ANTEIL * inl.sum(): stat["paare_verworfen_band"] += 1; continue
        stat["paare_bestaetigt"] += 1; stat["zuordnungen"] += int(keep.sum())
        XA_ = punkte_aus_tiefe(A, i, ka[keep]); XB_ = punkte_aus_tiefe(B, j, kb[keep]); w_ = np.flatnonzero(np.isfinite(XA_[:, 0]) & np.isfinite(XB_[:, 0])); cb_ = B.C(j)
        ia_ = np.flatnonzero(keep)
        for x in w_: spuren.setdefault((a, int(m[ia_[x], 0])), (XA_[x], XB_[x], float(np.linalg.norm(XB_[x] - cb_)), b))   # je Merkmal in a eine Spur
    stat["band_px_median"] = round(float(np.median(bander)), 1) if bander else None
    stat["spuren"] = len(spuren); return stat, list(spuren.values())


def direkt_koppeln(A, B, spuren):
    """Robuste Sim3 B -> A aus direkten Spuren (Annahmeregeln wie seiten_eck_koppeln). -> (M, pruefung, ok, grund, X_B, X_A, tiefe)."""
    if not spuren: return None, dict(punkte=0), False, "keine direkten Spuren", None, None, None
    X = np.array([s[1] for s in spuren]); Y = np.array([s[0] for s in spuren]); td = np.array([s[2] for s in spuren])
    M, pr, ok, g = EK.kopplung_pruefen(X, Y, B.ausdehnung(), A.ausdehnung(), tiefe=td)
    if M is not None:
        inl = _rest(M, X, Y, td) <= EK.SCHWELLE_REL; pr["hebel_b"] = round(EK.ausdehnung(X[inl]) / max(B.ausdehnung(), 1e-12), 3)
        pr["bilder_b"] = len({s[3] for s, w in zip(spuren, inl) if w})
    return M, pr, ok, g, X, Y, td


def bestaetigt(M_direkt, M_naeherung, PB, sigma_rad):
    """Liegt die direkte Kopplung im Unsicherheitsband der Naeherung? Drehung, Massstab und mittlere Verschiebung der B-Punkte (relativ zur Ausdehnung von B im
    Zielrahmen) <= BAND_SIGMA x sigma (mind. 0,5 Grad / 1 %). Eine falsche Naeherung ausserhalb ihres eigenen Bands wird so NICHT bestaetigt (Selbsttest:
    3 m Versatz -> direkte Kopplung findet die Wahrheit, weicht ab, abgelehnt). -> (ok, dict)."""
    s, R, _ = EK.zerlegen(np.linalg.inv(M_naeherung) @ M_direkt); dg = EK.winkel(R); sn = float(np.cbrt(np.linalg.det(M_naeherung[:3, :3])))
    vr = float(np.median(np.linalg.norm(anwenden(M_direkt, PB) - anwenden(M_naeherung, PB), axis=1))) / max(sn * EK.ausdehnung(PB), 1e-12)
    g = max(BAND_SIGMA * sigma_rad, np.radians(0.5)); gr = max(BAND_SIGMA * sigma_rad, 0.01)
    return bool(np.radians(dg) <= g and vr <= gr and abs(s - 1) <= gr), dict(drehung_grad=round(dg, 3), versatz_rel=round(vr, 4), massstab_rel=round(abs(s - 1), 4),
                                                                             grenze_grad=round(float(np.degrees(g)), 3), grenze_rel=round(gr, 4))


# ---------------------------------------------------------------- C: gemeinsamer Ausgleich
def _rot(v):
    th = np.linalg.norm(v)
    if th < 1e-15: return np.eye(3)
    k = v / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def feld_parameter(P, hoch=None):
    """Achse, Mitte, Laenge, Hochachse fuer das Verformungsfeld eines Teils (wie eck_rest_eichung.verformen)."""
    c = np.median(P, 0); _, _, Vt = np.linalg.svd(P - c, full_matrices=False); ach = Vt[0]; L = np.percentile((P - c) @ ach, 95) - np.percentile((P - c) @ ach, 5)
    h = Vt[2] if hoch is None else np.asarray(hoch, float) / np.linalg.norm(hoch)
    if hoch is not None: ach = ach - (ach @ h) * h; ach /= np.linalg.norm(ach)                 # Laengsachse waagerecht zum Lot
    return dict(c=c, ach=ach, L=float(L), hoch=h)


def feld(fp, a, b, drehungen=False):
    """Verformung: Massstab 1 + a u, Drehung um die Hochachse b u (rad), u = Lage entlang der Achse / Laenge. -> Funktion X -> (X', Rloc oder None; Rloc nur mit drehungen=True, fuer Kameras)."""
    def f(X):
        X = np.asarray(X, float); u = ((X - fp["c"]) @ fp["ach"]) / fp["L"]; v = X - fp["c"]; h = fp["hoch"]; ang = b * u
        k = np.cross(h, v); v2 = v * np.cos(ang)[:, None] + k * np.sin(ang)[:, None] + np.outer(v @ h, h) * (1 - np.cos(ang))[:, None]
        Rl = (np.array([_rot(h * x) for x in ang]) if len(X) else np.zeros((0, 3, 3))) if drehungen else None; return fp["c"] + v2 * (1 + a * u)[:, None], Rl
    return f


def ausgleich(quellen, M_AB0, M_AE0=None, lot=None, fp=None, verformung=False, f_scale=0.003):
    """Gemeinsamer Ausgleich, Teil A fest. quellen: dict mit 'direkt' (X_B, X_A, tiefe_B), 'ea' (X_E, Y_A, tiefe_E), 'eb' (X_E, Y_B, tiefe_E) - jede optional.
    Unbekannte: T_AB (7; mit lot=(oben_A, oben_B): 5 = Drehung um oben_A), T_AE (7, nur wenn ea/eb), bei verformung zusaetzlich (a, b) des Feldes fp fuer B.
    Robust (Cauchy, f_scale relativ zur Tiefe). -> dict(M_AB, M_AE, a, b, sigma_a, sigma_b, rest_median, n)."""
    from scipy.optimize import least_squares
    hat_e = M_AE0 is not None and any(k in quellen for k in ("ea", "eb"))
    sAB, RAB, tAB = EK.zerlegen(M_AB0)
    if lot is not None:
        oa, ob = (np.asarray(x, float) / np.linalg.norm(x) for x in lot); R0 = drehung_auf(ob, oa); Bs = basis(oa)
        R1 = Bs.T @ RAB @ R0.T @ Bs; th0 = float(np.arctan2(R1[1, 0], R1[0, 0]))                 # Drehung um oa, die der Naeherung am naechsten kommt
    def zerl(p):
        k = 0
        if lot is None: R = _rot(p[0:3]) @ RAB; k = 3
        else: c, s_ = np.cos(th0 + p[0]), np.sin(th0 + p[0]); R = Bs @ np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1.0]]) @ Bs.T @ R0; k = 1
        s = sAB * np.exp(p[k]); t = tAB + p[k + 1:k + 4] * max(sAB, 1e-12); k += 4; MAB = matrix(s, R, t); MAE = None
        if hat_e:
            sE, RE, tE = EK.zerlegen(M_AE0); MAE = matrix(sE * np.exp(p[k + 3]), _rot(p[k:k + 3]) @ RE, tE + p[k + 4:k + 7] * max(sE, 1e-12)); k += 7
        a, b = (p[k], p[k + 1]) if verformung else (0.0, 0.0); return MAB, MAE, a, b
    n0 = (3 if lot is None else 1) + 4 + (7 if hat_e else 0) + (2 if verformung else 0)
    def res(p):
        MAB, MAE, a, b = zerl(p); f = feld(fp, a, b) if verformung else (lambda X: (X, None)); r = []
        if "direkt" in quellen:
            X, Y, td = quellen["direkt"]; s = np.cbrt(np.linalg.det(MAB[:3, :3])); r.append(((anwenden(MAB, f(X)[0]) - Y) / (s * td[:, None])).ravel())
        if hat_e and "ea" in quellen:
            X, Y, td = quellen["ea"]; s = np.cbrt(np.linalg.det(MAE[:3, :3])); r.append(((anwenden(MAE, X) - Y) / (s * td[:, None])).ravel())
        if hat_e and "eb" in quellen:
            X, Y, td = quellen["eb"]; s = np.cbrt(np.linalg.det(MAE[:3, :3])); r.append(((anwenden(MAE, X) - anwenden(MAB, f(Y)[0])) / (s * td[:, None])).ravel())
        return np.concatenate(r)
    sol = least_squares(res, np.zeros(n0), loss="cauchy", f_scale=f_scale, x_scale=1e-3, max_nfev=400)
    MAB, MAE, a, b = zerl(sol.x); rr = np.linalg.norm(sol.fun.reshape(-1, 3), axis=1); out = dict(M_AB=MAB, M_AE=MAE, a=float(a), b=float(b), n=int(len(rr)), rest_median=float(np.median(rr)))
    if verformung:
        J = sol.jac; w = 1.0 / (1 + (sol.fun / f_scale) ** 2)                                   # Cauchy-Gewichte -> Kovarianz der Parameter
        try:
            H = (J * w[:, None]).T @ J; s2 = float(np.sum(w * sol.fun ** 2) / max(len(sol.fun) - n0, 1)); C = np.linalg.inv(H) * s2
            out.update(sigma_a=float(np.sqrt(C[-2, -2])), sigma_b=float(np.sqrt(C[-1, -1])))
        except np.linalg.LinAlgError: out.update(sigma_a=float("inf"), sigma_b=float("inf"))
    return out


def verformung_urteil(erg):
    """Halbstarr angenommen? signifikant (> SIG_VERFORMUNG sigma) und plausibel (<= VERFORMUNG_MAX). -> (an, grund)."""
    za = abs(erg["a"]) / max(erg.get("sigma_a", np.inf), 1e-12); zb = abs(erg["b"]) / max(erg.get("sigma_b", np.inf), 1e-12)
    if abs(erg["a"]) > VERFORMUNG_MAX or abs(erg["b"]) > VERFORMUNG_MAX: return False, f"Verformung unplausibel (a {erg['a']:+.3f}, b {erg['b']:+.3f}) - Teil falsch, nicht verbiegen"
    if za < SIG_VERFORMUNG and zb < SIG_VERFORMUNG: return False, f"nicht signifikant (a {za:.1f} sigma, b {zb:.1f} sigma)"
    return True, f"Verformung signifikant (a {erg['a']:+.4f} = {za:.1f} sigma, b {np.degrees(erg['b']):+.2f} Grad = {zb:.1f} sigma)"


# ---------------------------------------------------------------- D: Urteil je Kante
def urteil_kante(hebel, wdh_drehung_grad=None, spuren=0, kreis_ok=None):
    """stark / duenn / zu duenn. Schwellen aus den Selbsttests (bruecke2_selbsttest.py, Doku/projekt/lage-seiten.md 22.11.):
    HEBEL (kleinerer der beiden Seiten): Martinstor 0,16 -> 0,7-0,8 Grad Kopplungsfehler, Kaufhaus 0,38-0,5 -> 0,1-0,3 Grad, 1122 Teil 0 0,06.
    -> stark: Hebel >= HEBEL_STARK und Wiederholbarkeit <= WDH_STARK_GRAD; zu duenn: Hebel < HEBEL_MIN und keine direkten Spuren; sonst duenn."""
    if kreis_ok is False: return "zu duenn", "Kreisschluss widerspricht"
    if hebel is None: return "zu duenn", "keine Kopplung"
    if hebel >= HEBEL_STARK and (wdh_drehung_grad is None or wdh_drehung_grad <= WDH_STARK_GRAD) and spuren >= MIN_SPUREN_STARK:
        return "stark", f"Hebel {hebel:.2f} >= {HEBEL_STARK}"
    if hebel < HEBEL_MIN and spuren < MIN_SPUREN_STARK: return "zu duenn", f"Hebel {hebel:.2f} < {HEBEL_MIN}, {spuren} unabhaengige Spuren"
    return "duenn", f"Hebel {hebel:.2f}" + (f", Wiederholbarkeit {wdh_drehung_grad:.2f} Grad" if wdh_drehung_grad is not None else "")


HEBEL_STARK = 0.35       # Kaufhaus (0,38-0,5): Fehler <= 0,3 Grad / 4 cm; Martinstor (0,16): 0,7 Grad -> dazwischen
WDH_STARK_GRAD = 0.5     # Wiederholbarkeit Kaufhaus k3 0,48, k5 0,08; Martinstor k10 0,67 -> 0,5
HEBEL_MIN = 0.1          # 1122 Teil 0: 0,06 (SIFT) -> Kopplung nur ueber einen Fassadenstreifen; Martinstor 0,16 koppelt noch (0,7 Grad)
MIN_SPUREN_STARK = 100   # = MIN_PUNKTE der Kopplung


def radar_urteil(radar, i, j, namen):
    """URTEIL AUS DEM SCHWACHSTELLEN-RADAR (tools/verbund_schwachstellen.py, Format 'verbund_schwachstellen/1', Agent ae06; keine eigene Erkennung schwacher Stellen):
    radar = geladenes JSON; i, j = Teilnummern der Kante; namen = Bildnamen von A, B und Zwischenmodell. Gilt die Schwachstelle, deren 'teile' i und j enthalten,
    sonst die mit gemeinsamen 'bilder'/'seite_klein'; Reihenfolge nach 'ausloeser' (schlimmste zuerst). -> (urteil 'stark'|'duenn'|'zu duenn' oder None, grund, startbilder)."""
    if not radar or radar.get("urteil") in (None, "kein_graph"): return None, "kein Radar", []
    sw = {x.get("id"): x for x in radar.get("schwachstellen") or []}; rang = {k: n for n, k in enumerate(radar.get("ausloeser") or [])}; nm = set(namen)
    def passt(x):
        t = {str(v) for v in (x.get("teile") or [])}
        return (str(i) in t and str(j) in t) if t else bool(nm & (set(x.get("bilder") or []) | set(x.get("seite_klein") or [])))
    tr = sorted((x for x in sw.values() if passt(x)), key=lambda x: rang.get(x.get("id"), 10 ** 6))
    if not tr: return "stark", "Radar: keine Schwachstelle an dieser Naht", []
    x = tr[0]; st = x.get("staerke") or {}; uw = str(x.get("urteil") or "")
    if uw: u = {"stark": "stark", "duenn": "duenn", "zu_duenn": "zu duenn"}.get(uw, "duenn")
    elif x.get("id") not in rang: u = "stark"
    else: u = "zu duenn" if ((st.get("knoten_disjunkt") or 0) <= 1 or (st.get("spuren_quer") or 0) < 30) else "duenn"   # Radar-Grenzen (verbund_schwachstellen/1)
    st = x.get("staerke") or {}
    return u, f"Radar {x.get('id')} ({x.get('art')}): Spuren quer {st.get('spuren_quer')}, Wege {st.get('knoten_disjunkt')}", [b for b in (x.get("bilder") or []) if b in nm]


# ---------------------------------------------------------------- Eskalationsleiter (seiten_eck_koppeln)
AUSGLEICH = os.environ.get("RCPARK_ECK_AUSGLEICH", "1") != "0"     # Stufe C starr (Standard an, Beleg siehe leiter)
FUEHREN = os.environ.get("RCPARK_ECK_FUEHREN", "1") != "0"         # Stufe B bei Urteil 'duenn' (GPU, Minuten)
LOT_ZWANG = os.environ.get("RCPARK_ECK_LOT_ZWANG", "0") == "1"     # Stufe A als Zwang (Standard AUS: Lot ist Pruefung, Beleg siehe leiter)
FUEHREN_VRAM_MB = int(os.environ.get("RCPARK_ECK_FUEHREN_VRAM_MB", "2500"))
FUEHREN_RESIZE = int(os.environ.get("RCPARK_ECK_FUEHREN_RESIZE", "1024"))
LOT_TOR_GRAD = 3.0       # vorlaeufig, Beleg siehe Doku (relativer Lotfehler der Teile im Selbsttest)


def leiter(E, A, B, MA, MB, pa, pb, fotos, aus, lot=None, wdh_grad=None, radar=None, teile=(None, None)):
    """ESKALATIONSLEITER fuer EINE Kante A-B ueber das Zwischenmodell E (Modelle als bruecke_hebel.Modell, MA/MB = stimmige Kopplungen E->A, E->B aus
    seiten_eck_koppeln, pa/pb deren Pruefungen). Stufen: (1) Zwischenmodell-Kopplung (SIFT/Nachmatchen, schon gerechnet) -> (2) gemeinsamer Ausgleich starr
    (tiefengewichtet, Cauchy) -> Urteil -> bei nicht 'stark': (3) gefuehrtes Nachmessen, direkte Spuren A<->B, (4) gemeinsamer Ausgleich mit den direkten Spuren.
    Lot (lot = (oben_A, oben_B) aus lot_modell) ist PRUEFUNG (Winkel der Lote nach der Kopplung), nur mit RCPARK_ECK_LOT_ZWANG=1 Zwang.
    -> dict(M (B -> A), stufe, urteil, stufen [...], lot_pruefung, fotoauftrag)."""
    M0 = MA @ np.linalg.inv(MB); sig = float(np.sqrt(sum(p["rest_rel"] ** 2 + p["massstab_haelften_rel"] ** 2 for p in (pa, pb)))); out = dict(stufen=[], sigma=round(sig, 5))
    XA, YA, tA, _ = punkte(E, A); XB, YB, tB, _ = punkte(E, B); q = {}
    for k, M, X, Y, td in (("ea", MA, XA, YA, tA), ("eb", MB, XB, YB, tB)):
        w = np.flatnonzero(_rest(M, X, Y, td) <= EK.SCHWELLE_REL)
        if len(w) > 4000: w = np.random.default_rng(0).choice(w, 4000, replace=False)
        q[k] = (X[w], Y[w], td[w])
    M = M0; stufe = "zwischenmodell"; out["stufen"].append(dict(stufe=stufe, hebel=[pa.get("hebel"), pb.get("hebel")]))
    lotarg = tuple(lot) if (lot is not None and LOT_ZWANG) else None
    if AUSGLEICH:
        g = ausgleich(q, M0, MA, lot=lotarg); d = bestaetigt(g["M_AB"], M0, B.P, sig)[1]
        out["stufen"].append(dict(stufe="ausgleich_starr", rest_median=round(g["rest_median"], 5), unterschied=d)); M = g["M_AB"]; stufe = "ausgleich_starr"
    hs = [x for x in (pa.get("hebel"), pb.get("hebel")) if x is not None]; heb = min(hs) if hs else None
    u, grund, start = radar_urteil(radar, teile[0], teile[1], set(A.namen) | set(B.namen) | set(E.namen)) if radar else (None, "", [])
    if u is None: u, grund = urteil_kante(heb, wdh_grad, 0); grund = "ohne Radar: " + grund      # Rueckfall nur ohne Radar-Datei
    out.update(urteil=u, urteil_grund=grund, radar_startbilder=start)
    if u != "stark" and FUEHREN:
        try:
            kp = kandidaten_paare(A, B.transformiert(M), start=start); info = dict(stufe="fuehren", kandidatenpaare=len(kp))
            npz = lg_paare(kp, fotos, os.path.join(aus, "fuehren"), vram_mb=FUEHREN_VRAM_MB, resize=FUEHREN_RESIZE) if kp else None
            if npz:
                st, sp = paare_pruefen(npz, A, B, M, sig); info.update(st); Md, prd, okd, gd, X, Y, td = direkt_koppeln(A, B, sp); info["direkt"] = dict(ok=okd, grund=gd, **prd)
                if Md is not None: b_, dd = bestaetigt(Md, M, B.P, sig); info.update(bestaetigt=b_, unterschied=dd)
                out["stufen"].append(info)
                if okd and info.get("bestaetigt"):
                    # QUELLEN NICHT MITTELN (Selbsttest Martinstor k3: direkt allein 0,19 Grad / 1,0 cm; gemeinsam mit den Zwischenmodell-Spuren 0,48 Grad / 4,7 cm,
                    # die 8000 E-Spuren ueberstimmen die 231 direkten): die direkte Kopplung TRAEGT, die Zwischenmodell-Kopplung ist Gegenprobe ('unterschied').
                    # Danach Ausgleich NUR ueber die direkten Spuren (tiefengewichtet, Cauchy): Martinstor k3 0,10 -> 0,035 Grad, 0,9 -> 0,3 cm (Sim3-Inlier ungewichtet).
                    w = np.flatnonzero(_rest(Md, X, Y, td) <= EK.SCHWELLE_REL); g = ausgleich(dict(direkt=(X[w], Y[w], td[w])), Md, lot=lotarg); M = g["M_AB"]; stufe = "direkt"
                    out["stufen"].append(dict(stufe="direkt", spuren=len(w), rest_median=round(g["rest_median"], 5), gegenprobe_zwischenmodell=info.get("unterschied")))
                    hb = min(prd.get("hebel") or 0, prd.get("hebel_b") or 0); u, grund = urteil_kante(max(heb or 0, hb), wdh_grad, len(w)); out.update(urteil=u, urteil_grund=grund + " (nach Nachmessen)")
            else: info["grund"] = "keine Kandidatenpaare / LightGlue gescheitert"; out["stufen"].append(info)
        except Exception as ex: out["stufen"].append(dict(stufe="fuehren", fehler=str(ex)[:300]))
    if lot is not None:
        oa, ob = (np.asarray(x, float) / np.linalg.norm(x) for x in lot); R = EK.zerlegen(M)[1]; w = float(np.degrees(np.arccos(np.clip(abs((R @ ob) @ oa), -1, 1))))
        out["lot_pruefung"] = dict(winkel_grad=round(w, 3), grenze_grad=LOT_TOR_GRAD, ok=bool(w <= LOT_TOR_GRAD))
    if out["urteil"] == "zu duenn": out["fotoauftrag"] = "Naht zu duenn: Fotos, die beide Teile gemeinsam zeigen (Uebergang um die Ecke, Schritte <= 30 Grad, auch Fernfotos ueber die ganze Naht)"
    out.update(M=M, stufe=stufe); return out
