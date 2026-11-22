#!/usr/bin/env python3
"""seiten_lod2_je_teil.py <objekt.json> <modell_a> <modell_b> --bilder <fotoordner> --gps <vereinen.json der GPS-Vereinigung> --aus <ordner> [--dicht-a fused.ply --dicht-b fused.ply]

LoD2 JE TEIL (22.11.2026, Nutzerwunsch "amtlichen Grundriss tiefer einbeziehen"; Nulllauf schwabentor-1122f: zwei Seitenteile per Foto-GPS vereint, Teil 1 nur 24 Geotags
(+-3,5 Grad, +-12 %), dann als EIN Modell gegen LoD2 gefittet -> GPS-Tor gruen, Grundriss-Tor rot; Wanddicke-Tor: Westkante teil0 -2,11 / teil1 -0,49 m, Treppentuermchen
von teil0 4,5 m neben LoD2, Massstab der gemeinsamen Ausrichtung am Kastenrand). Ein gemeinsamer Fit kann Teile nicht GEGENEINANDER verschieben; Querspuren zwischen den
Teilen sind am Schwabentor Gegenseiten-Verwechslungen (tools/seiten_querspur_binden.py lehnt sie ab). Hier wird JEDER Teil EINZELN gelegt:
  1. GPS-Rahmen je Teil: eigene Kameras (Lot aus den Bild-x-Achsen, seiten_gps_vereinen.lot_aus_bild_achsen), eigene Geotags direkt im Modellrahmen von objekt.json
     (seiten_gps_vereinen.rahmen; Boden aus der eigenen dichten Wolke). Kein LoD2 in diesem Schritt.
  2. KASTEN je Teil aus DESSEN GPS-Unsicherheit (Bootstrap von rahmen): Drehung/Massstab = K_SIGMA x Sigma, nach unten wie der GPS-Anker (sfm_lod2_ausrichten
     GPS_ANKER_DREH_MIN/MASS_MIN), nach oben die Grenzen des GPS-Tors (GPS_MAX_DREH 15 Grad / GPS_MAX_MASS 15 %). Versatz = Wurzel(Sitzungsversatz^2 + (K x Rest/Wurzel n)^2),
     hoechstens VERSATZ_MAX_M; Kippung +-KIPP_GRAD. Teil mit wenig GPS = weiter Kasten.
     ANNAHME Sitzungsversatz VERSATZ_SITZUNG_M = 3,4 m: am Kontrollobjekt schwabentor-1120 (Lage aus LoD2/Kette, Grundriss-Tor bestanden) liegt das Handy-GPS einer
     Fotositzung im MITTEL 3,1-3,4 m neben den Kamerastandorten (zwei Sitzungen 11:3x / 11:4x, 126 + 31 Fotos, gleiche Richtung), der Zufallsanteil des Mittels nur 1,0 m:
     ein gemeinsamer Versatz mittelt sich NICHT weg. Gemessen an EINEM Objekt / EINEM Handy - an weiteren Objekten pruefen.
  3. SUCHE im Kasten (2D, nur Kanten des ZIELGEBAEUDES = LoD2-Grundflaechen mit objekt.json lod2.id, samt Rundung des Treppentuermchens; Nachbarhaeuser ziehen nicht):
     Wandband (Z_BAND ueber Boden) gegen ein Naehe-Feld der Zielkanten, Drehung x Massstab als Raster, Verschiebung per FFT-Korrelation (wie sfm_lod2_ausrichten).
     EINDEUTIGKEIT: Bestwert am Kastenrand (Drehung, Massstab oder Versatz) = KEIN Urteil; zweitbeste ANDERE Lage (> ANDERS_GRAD oder > ANDERS_M) wird mit Abstand gemeldet,
     Verhaeltnis > EINDEUTIG_MAX = mehrdeutig (entlang einer langen Wand ohne Ende/Ecke/Rundung). Guete 'festlegung' = kleinster/groesster Eigenwert der Wandnormalen der
     getroffenen Punkte (0 = nur eine Wandrichtung, entlang frei). Der fast quadratische Grundriss (90-Grad-Mehrdeutigkeit) ist nur durch den Kasten ausgeschlossen.
  4. FEIN: Punkt-zu-Flaeche gegen LoD2-Flaechen des Zielgebaeudes + DGM1 (Huber), Kippung und Hoehe frei im Kasten, Drehung/Versatz/Massstab nur um den Suchbestwert.
  5. UEBERNAHME (alle drei, Quellen nicht gemittelt): (a) Wanddicke-Mass besser (tools/wand_dicke_tor.kanten_messen; Lageunterschied der Teile je Kante, die beide sehen;
     vorher = A per LoD2, B per GPS an A), (b) GPS-Veto haelt (seiten_querspur_binden.korridor um die GPS-Vereinigung), (c) Teile danach widerspruchsfrei (keine Kante
     'versetzt'/'doppelwand'). Sonst unveraendert (GPS-Lage) mit benannter Ursache.
Ausgabe <aus>/lod2_teile.json (ok, urteil, B_nach_A nur bei ok, B_nach_A_gps, teile{a,b}, wand_dicke{vorher, nachher}, korridor) + Pflichtbild <aus>/lod2_teile.jpg
  (Grundriss vorher | nachher, Teil A blau, Teil B rot, Zielgebaeude dick). rc 0 = uebernommen, 3 = nicht uebernommen (Ursache im JSON), 2 = nicht moeglich (kein LoD2, zu
  wenig GPS, keine dichte Wolke).
Aufruf aus tools/sfm_seiten_modelle.py (lod2_stufe) nur auf dem GPS-Weg mit mehreren vereinten Teilen; Martinstor (Klappung) und Einteiler (Kaufhaus) laufen nicht hindurch.
Test: tools/test_seiten_lod2_je_teil.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap, scipy, cv2)."""
import os, sys, json, math, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import sfm_lod2_ausrichten as SA

K_SIGMA = 3.0              # wie der GPS-Anker und der Querspur-Korridor
VERSATZ_SITZUNG_M = 3.4    # ANNAHME, gemessen 1120 (Kopf, Punkt 2)
VERSATZ_MAX_M = 6.0        # ANNAHME: nie weiter als 6 m vom GPS (Grenze des GPS-Startkandidaten +-4 m plus Fangbereich des Feinfits)
KIPP_GRAD = SA.GPS_ANKER_KIPP
Z_BAND = (1.0, 12.0)       # ANNAHME: Wandband ueber dem Boden fuer die Suche (Erker/Vordach meist hoeher, Sockel/Fahrzeuge darunter)
SIGMA_NAHE = 0.35          # m, Naehe-Feld (Wandrelief/Rauschen der dichten Wolke)
ZELLE = 0.1                # m, Raster der Suche
DREH_SCHRITT = 0.5         # Grad
MASS_SCHRITTE = 9
ANDERS_GRAD, ANDERS_M = 2.0, 1.0
EINDEUTIG_MAX = 0.85       # wie sfm_lod2_ausrichten 'mehrdeutig' (Schwabentor 14.11.: 87 % = Fluegel auf der Strasse)
FEST_MIN = 0.05            # ANNAHME: Festlegung entlang (Eigenwert-Verhaeltnis) darunter = nur eine Wandrichtung getroffen
MIN_BAND = 2000            # Wandpunkte im Band je Teil
N_PUNKTE = 400000          # Punkte je dichter Wolke (feste Zufallsauswahl)
N_FEIN = 40000
GIPFEL_MAX = 60            # so viele beste Gipfel der Naehe-Karte werden mit der Wandabdeckung neu gewertet


# ---------- Geometrie
def sim(s, R, t):
    M = np.eye(4); M[:3, :3] = s * np.asarray(R); M[:3, 3] = t; return M


def auf(M, X): return np.asarray(X, float) @ np.asarray(M)[:3, :3].T + np.asarray(M)[:3, 3]


def rz(grad):
    c, s = math.cos(math.radians(grad)), math.sin(math.radians(grad)); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def p_matrix(p, c):
    """Parameter p = [log s, rotvec (3), t (3)] (wie sfm_lod2_ausrichten.zu_modell, Bezug c = Kameramitte des Teils): X -> R (X - c) / s + t als 4x4."""
    from scipy.spatial.transform import Rotation as Rot
    R = Rot.from_rotvec(p[1:4]).as_matrix(); s = math.exp(p[0]); M = sim(1.0 / s, R, np.asarray(p[4:7]) - R @ np.asarray(c) / s); return M


# ---------- Eingaben
def gps_modell(obj, roh):
    """{Bild: (lat, lon)} -> {Bild: xy im Modellrahmen von objekt.json}."""
    from bilder_holen import wgs84_zu_utm
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"], float); xh, yh = np.array(R["xhat_utm"], float), np.array(R["yhat_utm"], float); G = {}
    for n, (la, lo) in roh.items():
        u = np.asarray(wgs84_zu_utm(la, lo), float)
        if np.isfinite(u).all(): G[n] = np.array([(u - c0) @ xh, (u - c0) @ yh])
    return G


def ziel_kanten(obj, radius=60.0):
    """LoD2-Grundflaechen des Zielgebaeudes (objekt.json lod2.id) im Modellrahmen -> Liste (n x 2)."""
    import wolke_grundriss_pruefen as WG
    zid = (obj.get("lod2") or {}).get("id")
    return [np.asarray(g, float) for b in WG.grundrisse(obj, radius) if b["id"] == zid for g in b["ground"]] if zid else []


def kasten(F):
    """Kasten je Teil aus seiner GPS-Unsicherheit -> dict(dreh_grad, mass_rel, versatz_m, kipp_grad, herkunft)."""
    d = min(max(K_SIGMA * F["dreh_sd_grad"], SA.GPS_ANKER_DREH_MIN), SA.GPS_MAX_DREH); m = min(max(K_SIGMA * F["mass_sd_rel"], SA.GPS_ANKER_MASS_MIN), SA.GPS_MAX_MASS)
    zuf = K_SIGMA * F["rest_median_m"] / math.sqrt(max(F["inlier"], 1)); v = min(math.hypot(VERSATZ_SITZUNG_M, zuf), VERSATZ_MAX_M)
    return dict(dreh_grad=round(d, 2), mass_rel=round(m, 4), versatz_m=round(v, 2), kipp_grad=KIPP_GRAD,
                herkunft=f"{K_SIGMA:.0f} x Bootstrap ({F['dreh_sd_grad']} Grad, {100 * F['mass_sd_rel']:.1f} %), Versatz Wurzel({VERSATZ_SITZUNG_M}^2 + ({zuf:.2f})^2) (Sitzungsversatz ANNAHME 1120)")


# ---------- Suche
def naehe_feld(kanten, H, zelle=ZELLE, sigma=SIGMA_NAHE):
    """Naehe-Feld exp(-d^2/2 sigma^2) der Zielkanten auf einem Raster [-H, H]^2 (Zeile = y, Spalte = x) + Abstandsfeld (m)."""
    from scipy.ndimage import distance_transform_edt
    n = int(round(2 * H / zelle)); W = np.zeros((n, n), bool)
    for g in kanten:
        for p0, p1 in zip(g, np.roll(g, -1, 0)):
            m = int(np.linalg.norm(p1 - p0) / (zelle / 3)) + 2; L = p0 + np.linspace(0, 1, m)[:, None] * (p1 - p0); ij = np.floor((L + H) / zelle).astype(int)
            ok = (ij >= 0).all(1) & (ij < n).all(1); W[ij[ok, 1], ij[ok, 0]] = True
    D = distance_transform_edt(~W) * zelle; return np.exp(-0.5 * (D / sigma) ** 2), D


def suche(xy, c, K, kanten, zelle=ZELLE):
    """2D-Suche im Kasten: xy = Wandband-Punkte (GPS-Lage, Modellrahmen), c = Drehpunkt (Kameramitte). -> dict(best, zweit, verhaeltnis, rand, ...).
    Lage = Rz(d) (xy - c) / s + c + tau; d in +-K.dreh, s = exp(l) mit l in [log(1-m), log(1+m)], tau in +-K.versatz (je Achse, wie gps_anker_grenzen)."""
    xy = np.asarray(xy, float); c = np.asarray(c, float)[:2]; v = K["versatz_m"]
    rad = float(np.percentile(np.linalg.norm(xy - c, axis=1), 99)) * 1.2 + v + 2.0
    H = math.ceil((max(np.abs(c).max() + rad, max(np.abs(g).max() for g in kanten) + v + 2.0)) / 5.0) * 5.0
    N, _ = naehe_feld(kanten, H, zelle); n = N.shape[0]; FN = np.fft.rfft2(N)
    dreh = np.arange(-K["dreh_grad"], K["dreh_grad"] + 1e-9, DREH_SCHRITT); dreh = np.unique(np.r_[dreh, -K["dreh_grad"], K["dreh_grad"]])
    lm = np.linspace(math.log(1 - K["mass_rel"]), math.log(1 + K["mass_rel"]), MASS_SCHRITTE)
    k = int(math.floor(v / zelle)); sh = np.arange(-k, k + 1)                                       # Verschiebungen in Zellen (Kasten je Achse)
    karten = np.zeros((len(dreh), len(lm), len(sh), len(sh)), np.float32)
    for i, d in enumerate(dreh):
        R2 = rz(d)[:2, :2]
        for j, l in enumerate(lm):
            q = (xy - c) @ R2.T / math.exp(l) + c; ij = np.floor((q + H) / zelle).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
            Dn = np.zeros((n, n)); np.add.at(Dn, (ij[ok, 1], ij[ok, 0]), 1.0)
            Kk = np.fft.irfft2(FN * np.conj(np.fft.rfft2(Dn)), s=(n, n))                          # Kk[dy, dx] = sum D(p) N(p + d)
            karten[i, j] = Kk[np.ix_(sh % n, sh % n)] / max(len(xy), 1)
    # GIPFEL statt Rasterpunkte: zweitbeste Lage = bester ANDERER Gipfel (lokales Maximum), nicht die Flanke des besten (Probe 1122: Flanke 1 m daneben = 94-99 %).
    # GUETE = Naehe x WANDABDECKUNG (wie sfm_lod2_ausrichten 'Inlier x Abdeckung'): die Naehe allein bevorzugt das GESCHRUMPFTE Modell (Probe 1122: Teil A lief bei jedem
    # Kasten an den Rand, 2,3 Grad / x1,06 bei +-2,3 Grad / 6 %, -8 Grad / x1,12 bei 8 Grad / 12 %) - geschrumpft liegen mehr Punkte an weniger Wand.
    from scipy.ndimage import maximum_filter
    from scipy.spatial import cKDTree
    gipfel = karten >= maximum_filter(karten, size=(3, 3, 2 * int(round(ANDERS_M / zelle / 2)) + 1, 2 * int(round(ANDERS_M / zelle / 2)) + 1), mode="nearest")
    kand = np.argwhere(gipfel & (karten > 0)); kand = kand[np.argsort(-karten[tuple(kand.T)])][:GIPFEL_MAX]
    wand = np.vstack([p0 + np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / 0.2)))[:, None] * (p1 - p0) for g in kanten for p0, p1 in zip(g, np.roll(g, -1, 0))])
    L_ = []
    for ix in kand:
        d_, l_, ty, tx = dreh[ix[0]], lm[ix[1]], sh[ix[2]] * zelle, sh[ix[3]] * zelle
        q = (xy - c) @ rz(d_)[:2, :2].T / math.exp(l_) + c + [tx, ty]; ab = float((cKDTree(q).query(wand, distance_upper_bound=2 * SIGMA_NAHE)[0] < 2 * SIGMA_NAHE).mean())
        L_.append((float(karten[tuple(ix)]) * ab, float(karten[tuple(ix)]), ab, tuple(ix)))
    L_.sort(key=lambda r: -r[0])
    if not L_: return dict(best=0.0, dreh_grad=0.0, massstab=1.0, versatz=[0.0, 0.0], zweit=0.0, verhaeltnis=1.0, rand=["keine Loesung"], abstand_zweit=dict(grad=0, m=0), naehe=0.0, abdeckung=0.0)
    best, naehe, abd, b = L_[0]; bd, bl, by, bx = dreh[b[0]], lm[b[1]], sh[b[2]] * zelle, sh[b[3]] * zelle
    anders = [r for r in L_[1:] if abs(dreh[r[3][0]] - bd) > ANDERS_GRAD or math.hypot(sh[r[3][3]] * zelle - bx, sh[r[3][2]] * zelle - by) > ANDERS_M]
    zweit, z = (anders[0][0], anders[0][3]) if anders else (0.0, b)
    rand = []
    if b[0] in (0, len(dreh) - 1): rand.append("Drehung")
    if b[1] in (0, len(lm) - 1): rand.append("Massstab")
    if b[2] in (0, len(sh) - 1) or b[3] in (0, len(sh) - 1): rand.append("Versatz")
    return dict(best=best, dreh_grad=float(bd), massstab=float(math.exp(bl)), versatz=[float(bx), float(by)], zweit=zweit,
                zweit_lage=dict(dreh_grad=float(dreh[z[0]]), massstab=float(math.exp(lm[z[1]])), versatz=[float(sh[z[3]] * zelle), float(sh[z[2]] * zelle)]),
                abstand_zweit=dict(grad=round(float(abs(dreh[z[0]] - bd)), 2), m=round(float(math.hypot(sh[z[3]] * zelle - bx, sh[z[2]] * zelle - by)), 2)),
                verhaeltnis=(zweit / best if best > 0 else 1.0), rand=rand, naehe=naehe, abdeckung=abd, gipfel=len(L_), raster=dict(dreh=len(dreh), massstab=len(lm), versatz=len(sh), zelle_m=zelle))


def festlegung(xy, kanten, grenze=2 * SIGMA_NAHE):
    """Wie gut legen die getroffenen Zielkanten die Lage in beiden Richtungen fest? Eigenwert-Verhaeltnis der Normalen (0 = eine Wandrichtung, 1 = rundum)."""
    segs = [(p0, p1) for g in kanten for p0, p1 in zip(g, np.roll(g, -1, 0)) if np.linalg.norm(p1 - p0) > 1e-6]
    A = np.array([s[0] for s in segs]); B = np.array([s[1] for s in segs]); e = B - A; L2 = (e ** 2).sum(1)
    S = np.zeros((2, 2)); nt = 0
    for i0 in range(0, len(xy), 20000):
        q = xy[i0:i0 + 20000]; t = np.clip(((q[:, None, :] - A[None]) * e[None]).sum(2) / L2[None], 0, 1); P = A[None] + t[..., None] * e[None]
        d = np.linalg.norm(q[:, None, :] - P, axis=2); j = d.argmin(1); ok = d[np.arange(len(q)), j] < grenze
        nn = np.c_[-e[j[ok], 1], e[j[ok], 0]] / np.sqrt(L2[j[ok]])[:, None]; S += nn.T @ nn; nt += int(ok.sum())
    if nt < 50: return 0.0, nt
    w = np.linalg.eigvalsh(S / nt); return float(w[0] / max(w[1], 1e-12)), nt


def fein(Xc, c, p0, grenzen, ziel, ziel_n):
    """Punkt-zu-Flaeche (LoD2 Zielgebaeude + DGM1) im Kasten, Huber. Xc = Punkte (GPS-Lage, Modellrahmen). -> p."""
    from scipy.optimize import least_squares
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation as Rot
    baum = cKDTree(ziel); p = np.array(p0, float); lo, hi = grenzen
    zu = lambda q, X: Rot.from_rotvec(q[1:4]).apply(X - c) / math.exp(q[0]) + q[4:7]
    for sw in (1.0, 0.5):
        for _ in range(3):
            d, j = baum.query(zu(p, Xc), distance_upper_bound=2 * sw); ok = np.isfinite(d)
            if ok.sum() < 200: return p, int(ok.sum())
            Xo, jj = Xc[ok], j[ok]
            if len(Xo) > N_FEIN: s_ = np.random.default_rng(7).choice(len(Xo), N_FEIN, replace=False); Xo, jj = Xo[s_], jj[s_]
            r = lambda q: np.einsum("ij,ij->i", zu(q, Xo) - ziel[jj], ziel_n[jj])
            p = least_squares(r, np.clip(p, lo + 1e-9, hi - 1e-9), loss="huber", f_scale=sw / 3, bounds=(lo, hi), max_nfev=200).x
    d, _ = baum.query(zu(p, Xc), distance_upper_bound=1.0); return p, int(np.isfinite(d).sum())


# ---------- je Teil
def teil_legen(name, kam, P, G, obj, kanten, ziel, ziel_n, rng=None):
    """kam = (Namen, Zentren, Lot), P = dichte Wolke (Teilsystem), G = Geotags im Modellrahmen -> dict mit 'T' (4x4 Teil -> Modellrahmen) oder 'grund'."""
    import seiten_gps_vereinen as SG
    F = SG.rahmen(*kam, G, boden=P, rng=rng or np.random.default_rng(0)); erg = dict(teil=name, gps={k: v for k, v in F.items() if k != "M"})
    g = SG.guete(F)
    if g: erg["grund"] = "GPS-Rahmen taugt nicht: " + "; ".join(g); return erg
    if np.linalg.det(F["M"][:3, :3]) <= 0: erg["grund"] = "GPS-Rahmen gespiegelt"; return erg
    K = kasten(F); erg["kasten"] = K
    X = auf(F["M"], P); C = auf(F["M"], kam[1]); c = np.median(C, 0)
    band = (X[:, 2] > Z_BAND[0]) & (X[:, 2] < Z_BAND[1])
    if band.sum() < MIN_BAND: erg["grund"] = f"nur {int(band.sum())} Wandpunkte im Band {Z_BAND} m (noetig {MIN_BAND})"; return erg
    xy = X[band, :2]
    if len(xy) > 60000: xy = xy[np.random.default_rng(3).choice(len(xy), 60000, replace=False)]
    S = suche(xy, c, K, kanten); erg["suche"] = {k: v for k, v in S.items()}
    q = (xy - c[:2]) @ rz(S["dreh_grad"])[:2, :2].T / S["massstab"] + c[:2] + S["versatz"]
    erg["festlegung"], erg["festlegung_punkte"] = festlegung(q, kanten)
    p_gps = np.r_[0.0, 0.0, 0.0, 0.0, c]; lo, hi = SA.gps_anker_grenzen(p_gps, dreh=K["dreh_grad"], mass=K["mass_rel"], versatz=K["versatz_m"], kipp=K["kipp_grad"])
    ps = np.r_[math.log(S["massstab"]), 0.0, 0.0, math.radians(S["dreh_grad"]), c[0] + S["versatz"][0], c[1] + S["versatz"][1], c[2]]
    l_schritt = (math.log(1 + K["mass_rel"]) - math.log(1 - K["mass_rel"])) / max(MASS_SCHRITTE - 1, 1)
    eng = np.array([l_schritt, np.inf, np.inf, math.radians(2 * DREH_SCHRITT), 2 * ZELLE, 2 * ZELLE, np.inf])   # Kippung (1, 2) und Hoehe (6) nur durch den Kasten begrenzt
    lo2, hi2 = np.maximum(lo, ps - eng), np.minimum(hi, ps + eng)                               # Drehung/Versatz/Massstab nur um den Suchbestwert; Kippung/Hoehe im Kasten
    Xf = X[(X[:, 2] > -2) & (np.linalg.norm(X[:, :2] - c[:2], axis=1) < 80)]
    if len(Xf) > 200000: Xf = Xf[np.random.default_rng(5).choice(len(Xf), 200000, replace=False)]
    p, n_in = fein(Xf, c, ps, (lo2, hi2), ziel, ziel_n); erg["fein"] = dict(p=np.round(p, 6).tolist(), punkte_an_lod2=n_in)
    from scipy.spatial.transform import Rotation as Rot
    rv = Rot.from_rotvec(p[1:4]); z = rv.apply([0, 0, 1.0]); erg["fein"].update(kippung_grad=round(float(np.degrees(np.arccos(np.clip(z[2], -1, 1)))), 2),
                                                                                  dreh_grad=round(float(np.degrees(p[3])), 2), massstab=round(float(math.exp(p[0])), 4), versatz_m=np.round(p[4:6] - c[:2], 2).tolist(), hoehe_m=round(float(p[6] - c[2]), 2))
    erg["T"] = p_matrix(p, c) @ F["M"]; erg["T_gps"] = F["M"]
    gr = []
    if S["rand"]: gr.append("Bestwert am Kastenrand (" + ", ".join(S["rand"]) + ") - kein Urteil")
    if S["verhaeltnis"] > EINDEUTIG_MAX: gr.append(f"mehrdeutig: andere Lage ({S['abstand_zweit']['grad']} Grad / {S['abstand_zweit']['m']} m daneben) erreicht {100 * S['verhaeltnis']:.0f} % des Bestwerts")
    if erg["festlegung"] < FEST_MIN: gr.append(f"Lage entlang der Wand nicht festgelegt (Festlegung {erg['festlegung']:.3f} < {FEST_MIN})")
    erg["eindeutig"] = not gr; erg["gruende"] = gr
    return erg


def wand_dicke(kanten, teile):
    import wand_dicke_tor as WD
    K = [k for g in kanten for k in WD.kanten_messen(g, teile)]; rc, u = WD.zusammenfassen(K)
    beide = [k for k in K if k.get("lageunterschied_m") is not None]
    return dict(rc=rc, urteil=u, kanten=K, max_lageunterschied_m=(max(k["lageunterschied_m"] for k in beide) if beide else None),
                summe_lageunterschied_m=(round(sum(k["lageunterschied_m"] for k in beide), 3) if beide else None), kanten_mit_beiden=len(beide))


def entscheiden(ta, tb, wd_vor, wd_nach, kor):
    """Uebernahme-Regeln (Kopf, Punkt 5) -> (ok, gruende)."""
    import wand_dicke_tor as WD
    gr = [f"Teil {t['teil']}: " + "; ".join(t["gruende"]) for t in (ta, tb) if not t.get("eindeutig")]
    if wd_nach["kanten_mit_beiden"] == 0: gr.append("(a) keine Kante mit Wandbeleg beider Teile - Verbesserung nicht messbar")
    elif wd_vor["kanten_mit_beiden"] and wd_nach["summe_lageunterschied_m"] >= wd_vor["summe_lageunterschied_m"] - 1e-3 and wd_nach["max_lageunterschied_m"] >= wd_vor["max_lageunterschied_m"] - 1e-3:
        gr.append(f"(a) Wanddicke-Mass nicht besser (Lageunterschied max {wd_vor['max_lageunterschied_m']} -> {wd_nach['max_lageunterschied_m']} m)")
    if kor is not None and not kor.get("im_korridor"): gr.append("(b) GPS-Veto: " + "; ".join(kor.get("gruende", [])))
    schlecht = [k for k in wd_nach["kanten"] if k["urteil"] in ("versetzt", "doppelwand")]
    if schlecht: gr.append("(c) Teile danach nicht widerspruchsfrei: " + "; ".join(f"Kante {k['von']}->{k['bis']} {k['urteil']} ({k['lageunterschied_m']} m > {WD.VERSATZ_MAX_M})" for k in schlecht))
    return not gr, gr


# ---------- Bild
def bild(pfad, kanten, vor, nach, zid_text=""):
    """Grundriss vorher | nachher (Band 1,5-9 m), Teil A blau, Teil B rot, Zielgebaeude schwarz."""
    import cv2
    alle = np.vstack(kanten); lo = alle.min(0) - 12; hi = alle.max(0) + 12; px = 18.0; w, h = int((hi[0] - lo[0]) * px), int((hi[1] - lo[1]) * px)
    tafeln = []
    for titel, teile in (("vorher (A LoD2, B GPS)", vor), ("nachher (je Teil LoD2)", nach)):
        im = np.full((h, w, 3), 255, np.uint8); u = lambda X: np.c_[(X[:, 0] - lo[0]) * px, (hi[1] - X[:, 1]) * px].astype(int)
        for k, farbe in zip(sorted(teile), ((200, 120, 30), (40, 40, 220), (40, 160, 40))):
            X = teile[k]; X = X[(X[:, 2] > 1.5) & (X[:, 2] < 9)]; q = u(X); ok = (q[:, 0] >= 0) & (q[:, 0] < w) & (q[:, 1] >= 0) & (q[:, 1] < h); im[q[ok, 1], q[ok, 0]] = farbe
        for g in kanten: cv2.polylines(im, [u(np.c_[g, np.zeros(len(g))]).reshape(-1, 1, 2)], True, (0, 0, 0), 2)
        for gx in range(int(lo[0] // 5) * 5, int(hi[0]) + 1, 5): cv2.line(im, (int((gx - lo[0]) * px), 0), (int((gx - lo[0]) * px), h), (225, 225, 225), 1)
        for gy in range(int(lo[1] // 5) * 5, int(hi[1]) + 1, 5): cv2.line(im, (0, int((hi[1] - gy) * px)), (w, int((hi[1] - gy) * px)), (225, 225, 225), 1)
        cv2.putText(im, titel + " " + zid_text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1); tafeln.append(im)
    cv2.imwrite(pfad, np.hstack([tafeln[0], np.full((h, 6, 3), 0, np.uint8), tafeln[1]]), [cv2.IMWRITE_JPEG_QUALITY, 88])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("objekt"); ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--bilder", required=True); ap.add_argument("--gps", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--dicht-a"); ap.add_argument("--dicht-b")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True); aj = os.path.join(a.aus, "lod2_teile.json"); erg = dict(werkzeug="seiten_lod2_je_teil.py")
    def ende(rc, urteil):
        erg.update(rc=rc, urteil=urteil, ok=rc == 0); json.dump(erg, open(aj, "w"), indent=1, ensure_ascii=False, default=lambda o: np.asarray(o).tolist())
        print(("LoD2 JE TEIL: " if rc == 0 else "WARNUNG LoD2 JE TEIL: ") + urteil, flush=True); return rc
    try:
        obj = json.load(open(a.objekt)); obj = __import__("objekt_rahmen").ergaenzen(obj, os.path.dirname(os.path.abspath(a.objekt))); vg = json.load(open(a.gps))
    except Exception as ex: return ende(2, f"Eingabe fehlt ({type(ex).__name__}: {ex})")
    if not (a.dicht_a and a.dicht_b and os.path.isfile(a.dicht_a) and os.path.isfile(a.dicht_b)): return ende(2, "dichte Wolke eines Teils fehlt")
    if not (obj.get("lod2") or {}).get("id") or not obj.get("rahmen"): return ende(2, "objekt.json ohne lod2.id/rahmen - Zielgebaeude unbekannt")
    kanten = ziel_kanten(obj)
    if not kanten: return ende(2, f"LoD2-Grundflaeche von {obj['lod2']['id']} nicht gefunden")
    T_, Tn, Tt, _, _, _, Te = SA.lod2_ziel(obj, 30.0); Gd, Gn, gq = SA.dgm_ziel(obj, 40.0)
    ziel = np.vstack([T_[Te], Gd]); ziel_n = np.vstack([Tn[Te], Gn]); erg["ziel"] = dict(lod2_id=obj["lod2"]["id"], flaechenpunkte=int(Te.sum()), boden=gq, grundflaechen=len(kanten))
    import seiten_gps_vereinen as SG
    from seiten_vereinen import ply_punkte
    KA, KB = SG.kameras(a.a), SG.kameras(a.b); roh = SG.gps_roh(a.bilder, KA[0] + KB[0]) if os.path.isdir(a.bilder) else {}; G = gps_modell(obj, roh)
    PA, PB = ply_punkte(a.dicht_a, N_PUNKTE), ply_punkte(a.dicht_b, N_PUNKTE)
    ta = teil_legen("a", KA, PA, G, obj, kanten, ziel, ziel_n); tb = teil_legen("b", KB, PB, G, obj, kanten, ziel, ziel_n)
    erg["teile"] = {t["teil"]: {k: (np.asarray(v).tolist() if k in ("T", "T_gps") else v) for k, v in t.items()} for t in (ta, tb)}
    for t in (ta, tb): print(f"Teil {t['teil']}: " + (t["grund"] if "grund" in t else f"Kasten {t['kasten']['dreh_grad']} Grad / {100 * t['kasten']['mass_rel']:.1f} % / {t['kasten']['versatz_m']} m; "
                                                    f"Suche Drehung {t['suche']['dreh_grad']:+.1f} Grad, Massstab {t['suche']['massstab']:.3f}, Versatz {np.round(t['suche']['versatz'], 2).tolist()} m, "
                                                    f"Guete {100 * t['suche']['best']:.1f} % (Naehe {100 * t['suche']['naehe']:.0f} % x Wandabdeckung {100 * t['suche']['abdeckung']:.0f} %), zweitbeste andere Lage {100 * t['suche']['verhaeltnis']:.0f} % ({t['suche']['abstand_zweit']}), Rand {t['suche']['rand'] or '-'}, "
                                                    f"Festlegung {t['festlegung']:.3f}; fein Kippung {t['fein']['kippung_grad']} Grad, Hoehe {t['fein']['hoehe_m']} m" + ("" if t["eindeutig"] else " | " + "; ".join(t["gruende"]))), flush=True)
    if "T" not in ta or "T" not in tb: return ende(2, "; ".join(f"Teil {t['teil']}: {t['grund']}" for t in (ta, tb) if "grund" in t))
    Mg = np.asarray(vg.get("B_nach_A"), float) if vg.get("B_nach_A") is not None else np.linalg.inv(ta["T_gps"]) @ tb["T_gps"]
    neu = np.linalg.inv(ta["T"]) @ tb["T"]; erg["B_nach_A_gps"] = Mg.tolist(); erg["B_nach_A_lod2"] = neu.tolist()
    vor = {"a": auf(ta["T"], PA), "b": auf(ta["T"] @ Mg, PB)}; nach = {"a": auf(ta["T"], PA), "b": auf(tb["T"], PB)}
    wv, wn = wand_dicke(kanten, vor), wand_dicke(kanten, nach); erg["wand_dicke"] = dict(vorher=wv, nachher=wn)
    for nm_, w_ in (("vorher", wv), ("nachher", wn)):
        print(f"Wanddicke {nm_}: " + " | ".join(f"{k['von']}->{k['bis']}: {k['urteil']}" + "".join(f" {t}:{v['lage_m']:+.2f}/{v['dicke_m']:.2f}" + (f"/{v['neigung_grad']:+.0f}Grad" if "neigung_grad" in v else "") for t, v in k["teile"].items() if "lage_m" in v) for k in w_["kanten"]), flush=True)
    kor = None
    try:
        import seiten_querspur_binden as SQ
        Gu = SQ.gps_unsicherheit(vg)
        if isinstance(Gu, dict): kor = SQ.korridor(neu, Gu, KA[2], KB[1]); erg["korridor"] = kor
        else: erg["korridor"] = dict(grund=Gu)
    except Exception as ex: erg["korridor"] = dict(grund=f"{type(ex).__name__}: {ex}")
    try: bild(os.path.join(a.aus, "lod2_teile.jpg"), kanten, vor, nach, obj["lod2"]["id"]); erg["bild"] = os.path.join(a.aus, "lod2_teile.jpg")
    except Exception as ex: erg["bild"] = f"nicht gezeichnet ({type(ex).__name__}: {ex})"
    ok, gr = entscheiden(ta, tb, wv, wn, kor)
    if kor is None: ok = False; gr.append("(b) GPS-Veto nicht pruefbar: " + str((erg.get("korridor") or {}).get("grund")))
    if not ok: return ende(3, "NICHT uebernommen - " + " | ".join(gr))
    erg["B_nach_A"] = neu.tolist()
    return ende(0, f"uebernommen: Lageunterschied der Teile max {wv['max_lageunterschied_m']} -> {wn['max_lageunterschied_m']} m, GPS-Korridor gehalten "
                   f"(Drehung {kor['dreh_lot_grad']:+.1f} Grad, Massstab {100 * kor['massstab_rel']:+.1f} %, Lage {kor['lage_m']:.1f} m)")


if __name__ == "__main__": sys.exit(main())
