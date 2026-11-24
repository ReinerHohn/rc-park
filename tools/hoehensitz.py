#!/usr/bin/env python3
"""hoehensitz.py <objekt.json> [--fotosatz F] [--wolke P] [--stl P] [--json J] [--bild PNG] [--probe] [--rot] [--n-wolke N] [--n-modell N]
HOEHENSENSITIVES FORMMASS je Seite (Auftrag 24.11.2026, zweites Mass neben tools/formsitz.py). Befund: der Formsitz (Tiefen-IoU je Foto) trennt senkrecht zur
Wand stark, ist aber fast HOEHENBLIND (Modell +-0,3 m in z -> Abfall <= 0,005; +-2 m -> 0,01-0,06): eine Flaeche, die 0,5 m hoeher sitzt, hat aus fast jeder
Kamera dieselbe Tiefe. Bekannte Hoehenfehler am Schwabentor (Register 21.11.: Uhr +0,7 m, Sohlbank +0,45..0,53 m) fielen so nicht auf.

WAHL (begruendet, gegen den Vorschlag "Tiefensprung je Foto-Render"):
  Gemessen wird nicht im Bild, sondern im 3D-RAHMEN JE SEITE: Seitennormale n (Achse aus objekt.json seiten_konvention), Querkoordinate t, Hoehe z.
  Je Wandstreifen (STREIF_M 1 m breit in t) und Hoehenzelle (DZ_M 5 cm) die AUSSENLAGE r(t, z) = Quantil Q_AUSSEN der Normalkoordinate aller Punkte auf
  dieser Haelfte - getrennt fuer Modell (STL flaechengewichtet abgetastet) und dichte Wolke (sfm/punkte_modell_*.npy, derselbe Kamerarahmen).
  HORIZONTALE STRUKTURLINIEN = Spruenge von r in z (Traufe, Gesims Unter-/Oberkante, Dachfuss mit Ueberstand, Sohlbank/Sturz einer Nische, Uhr-Ober-/
  Unterkante, Bogenscheitel = Ende der Durchfahrt). Sprung je z: d(z) = r(z + H_M) - r(z - H_M) minus Median von d in +-UMGEB_M (eine gleichmaessig
  geneigte Dachflaeche ist kein Sprung); Linie = lokales Maximum |d| >= SPRUNG_M (Abstand >= NMS_M), Vorzeichen = springt nach aussen/innen.
  Warum nicht je Foto: (1) Ein ausladendes Gesims/Traufe liegt vor der Wandebene und wird aus einer tiefer stehenden Kamera um Ausladung*tan(Blickhoehe)
  falsch in z gelesen (Register/Rezept: 1,4 m vor der Ebene, Kamera 10 m tiefer = +0,8 m) - im Bild waere ein Hoehenfehler von einem Tiefenfehler nicht
  zu trennen; im 3D-Rahmen ist z direkt die Hoehe. (2) Kein Render, keine Verdeckung, keine Himmelsmaske -> < 1 min CPU. (3) Die Wolke ist dieselbe
  Mehrfoto-Triangulation wie beim Formsitz (KERNMETHODE: Wolke = Gegenprobe), ihre Hoehen sind die der SfM-Kameras.
  Nur ZELLEN, die Modell UND Wolke belegen (>= MIN_MODELL / MIN_WOLKE Punkte), liefern Linien - ungesehene Wand erzeugt weder Treffer noch Fehler.
VERGLEICH je Seite: jede Modell-Linie sucht im selben Streifen die naechste Wolken-Linie GLEICHEN Vorzeichens (<= SUCH_M) -> dz = z_wolke - z_modell.
  a10 / a25 = Anteil der Modell-Linien mit |dz| < 10 / 25 cm (ohne Partner = verfehlt), med_dz = Median |dz| der gepaarten,
  recall25 = Anteil Wolken-Linien mit Modell-Linie < 25 cm, HOEHENSITZ = F1(a25, recall25) (bestraft falsche Hoehe, fehlendes UND erfundenes Gesims).
  hoeher/tiefer: Median des vorzeichenbehafteten dz der Linien 0,1..SUCH_M ("Modell zu hoch" = dz < 0).
NULLPROBE (Pflicht, je Lauf): Modell um NULL_M 1,3 / 2,1 m in +-z -> hoehensitz_null (Median) = Zufallsniveau (dicht liegende Fugen/Fenster koennen zufaellig
  passen); guete = (s - null) / (1 - null).
TRENNSCHAERFE (wie formsitz): zwei zufaellige Wolkenhaelften A gegen B (decke) minus A um NULL_M in z (decke_null) = wie weit ein perfektes Modell hier
  ueber Zufall laege; trennt, wenn >= TRENN_MIN und >= N_LINIEN_MIN Wolken-Linien.
--probe: Abfall fuer Modell +-0,3/1/2 m in z (Pflicht: deutlich schlechter).
--rot:   ROT-PROBE je Seite: die staerkste richtig sitzende waagerechte Linie dieser Seite (z0, in den meisten Streifen) wird im Modell um ROT_M 0,5 m
         angehoben (Verformung nur der Punkte dieser Seitenhaelfte, |z - z0| < 0,3 m starr, Uebergang 0,5 m) -> ERKANNT, wenn die Fehlerliste die Linie bei
         z0 + 0,5 mit dz ~ -0,5 ('Modell zu hoch') in mindestens der Haelfte ihrer Streifen nennt und der Abfall dieser Seite groesser ist als jeder andere
         (der Seitenwert faellt am Bestand nur 0,02-0,07, weil eine Linie unter 80-390 ist; synthetisch >= ROT_MARGE). Dasselbe mit Wolkenhaelfte A als
         'perfektem Modell' (rot_decke) - zeigt die Probe unabhaengig vom Modellstand. --probe misst ebenso die Decke (A +-0,3/1/2 m in z gegen B).
Ausgabe: JSON (Standard <audit>/hoehensitz.json) {seiten: {achse: dict(name, hoehensitz, hoehensitz_null, guete, trennschaerfe, trennt, status, a10, a25,
  med_dz, recall25, n_modell, n_wolke, hoeher, fehler: [{t, z, dz, art}])}, probe?, rot?}; --bild: je Seite Aufriss t x z (grau = Wolken-Aussenlage,
  weiss = Wolken-Linie, gruen/gelb/rot = Modell-Linie < 10 / < 25 cm / falsch, violett = Modell-Linie ohne Partner).
Exit 0 = gerechnet, 1 = Aufruf/Daten falsch, 3 = keine Seite mit Linien.
Umgebung: /media/oem/scan/venv-seg/bin/python -I tools/hoehensitz.py ... (numpy, cv2; KEINE GPU). RAM ~0,6 GB (6 M Wolke + 4 M Modellpunkte).
"""
import sys, os, json, time, argparse
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
DZ_M = 0.05; STREIF_M = 1.0; Q_AUSSEN = 0.9; MIN_MODELL = 6; MIN_WOLKE = 6; H_M = 0.15; UMGEB_M = 1.0; SPRUNG_M = 0.12; NMS_M = 0.25
SUCH_M = 1.0; TOL = (0.10, 0.25); NULL_M = (1.3, 2.1); TRENN_MIN = 0.25; N_LINIEN_MIN = 8; RAND_M = 2.0; BODEN_M = 0.3
N_WOLKE = 6_000_000; N_MODELL = 4_000_000; PROBE_M = (0.3, 1.0, 2.0); ROT_M = 0.5; ROT_HALB = 0.3; ROT_RAMPE = 0.5; ROT_MARGE = 0.05
STUETZ_STREIFEN = 1; W_MAX = 0.0; K_AUSSEN = 5; BAND_AUSSEN = 0.15
TRENNT_NICHT = "nicht trennbar (Zufallsniveau)"
ACHSEN = {"+x": (0, 1.0), "-x": (0, -1.0), "+y": (1, 1.0), "-y": (1, -1.0)}


# ---------------------------------------------------------------- Profile + Linien
def seiten_rahmen(ax, lo, hi):
    """Achse -> (i_normal, vorzeichen, i_quer, mitte_normal)."""
    i, sg = ACHSEN[ax]; return i, sg, 1 - i, 0.5 * (lo[i] + hi[i])


def profil(P, ax, geo, min_pkt):
    """Aussenlage r (nt, nz) float32 (nan = zu wenig Punkte) je Streifen x Hoehenzelle fuer die Punkte der Seitenhaelfte."""
    i, sg, j, mitte = seiten_rahmen(ax, geo["lo"], geo["hi"]); t0, nt, z0, nz = geo["t0"][j], geo["nt"][j], geo["z0"], geo["nz"]
    o = (P[:, i] - mitte) * sg; sel = o > 0
    it = np.floor((P[sel, j] - t0) / STREIF_M).astype(np.int64); iz = np.floor((P[sel, 2] - z0) / DZ_M).astype(np.int64); o = o[sel]
    ok = (it >= 0) & (it < nt) & (iz >= 0) & (iz < nz); c = it[ok] * nz + iz[ok]; o = o[ok]
    r = np.full(nt * nz, np.nan, np.float32)
    if not len(c): return r.reshape(nt, nz)
    ordn = np.lexsort((-o, c)); c, o = c[ordn], o[ordn]                                   # je Zelle von aussen nach innen
    if K_AUSSEN <= 1:
        cnt = np.bincount(c, minlength=nt * nz); start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
        gut = cnt >= min_pkt; idx = start[gut] + ((1 - Q_AUSSEN) * (cnt[gut] - 1)).astype(np.int64); r[np.nonzero(gut)[0]] = o[idx]
        return r.reshape(nt, nz)
    # AEUSSERSTE GESTUETZTE SCHICHT: erster Punkt (von aussen), hinter dem innerhalb BAND_AUSSEN noch K_AUSSEN-1 Punkte derselben Zelle liegen (Geisterpunkte
    # vor der Wand zaehlen nicht). Ein Quantil kippte an Eckstreifen je nach Anteil der Seitenwand (Probe 24.11.: Scheinlinien +-0,7 m im Eckstreifen).
    k = K_AUSSEN; cnt = np.bincount(c, minlength=nt * nz)
    if len(c) >= k:
        span_ok = np.zeros(len(c), bool); span_ok[:len(c) - k + 1] = (c[:len(c) - k + 1] == c[k - 1:]) & (o[:len(c) - k + 1] - o[k - 1:] <= BAND_AUSSEN)
        p = np.nonzero(span_ok)[0]; cz, erst = np.unique(c[p], return_index=True); p = p[erst]
        gut = cnt[cz] >= min_pkt; r[cz[gut]] = 0.5 * (o[p[gut]] + o[p[gut] + k - 1])
    return r.reshape(nt, nz)


def linien(r, gemeinsam):
    """Waagerechte Strukturlinien je Streifen aus der Aussenlage (nur gemeinsam belegte Zellen) -> Liste (streifen, z_index (float), vorzeichen, staerke)."""
    from scipy.ndimage import median_filter
    h = int(round(H_M / DZ_M)); u = int(round(UMGEB_M / DZ_M)); nms = int(round(NMS_M / DZ_M)); out = []
    R = np.where(gemeinsam, r, np.nan)
    for s in range(R.shape[0]):
        x = R[s]
        if np.isfinite(x).sum() < 4 * h + 2: continue
        xm = x.copy(); f = np.isfinite(xm)
        # kleine Luecken (<= 2 Zellen) innerhalb belegter Bereiche schliessen, sonst entstehen Spruenge an Datenrandern
        xm = median_filter(np.where(f, xm, np.nanmedian(xm)), size=3, mode="nearest"); xm[~f] = np.nan
        d = np.full(len(x), np.nan, np.float32); d[h:-h] = xm[2 * h:] - xm[:-2 * h]
        fin = np.isfinite(d)
        if fin.sum() < 3: continue
        # Umgebungs-Median von d (Dachneigung abziehen): gleitendes Fenster +-UMGEB_M, nur endliche Werte (>= 3)
        from numpy.lib.stride_tricks import sliding_window_view
        fen = sliding_window_view(np.pad(d, u, constant_values=np.nan), 2 * u + 1)
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning); bg = np.nanmedian(fen, axis=1)
        bg[(np.isfinite(fen).sum(1) < 3) | ~fin] = np.nan
        e = np.where(np.isfinite(bg), d - bg, np.nan); ae = np.where(np.isfinite(e), np.abs(e), 0.0)
        kand = np.nonzero(ae >= SPRUNG_M)[0]; belegt = np.zeros(len(ae), bool); eig = []
        for k_ in kand[np.argsort(-ae[kand], kind="stable")]:
            if belegt[k_]: continue
            # Ein Sprung erscheint in d als Plateau der Breite 2h (Differenz ueber +-h): Lage = Schwerpunkt der zusammenhaengenden Zellen gleichen
            # Vorzeichens mit |e| >= halbe Spitze (sonst sitzt die Linie bis +-h daneben und ein Sprung gibt zwei Linien).
            sg = np.sign(e[k_]); thr = 0.5 * ae[k_]; a = k_
            while a - 1 >= 0 and ae[a - 1] >= thr and np.sign(e[a - 1]) == sg: a -= 1
            b = k_
            while b + 1 < len(ae) and ae[b + 1] >= thr and np.sign(e[b + 1]) == sg: b += 1
            idx = np.arange(a, b + 1); z = float(np.average(idx, weights=ae[idx]))   # Plateau [k-h, k+h-1] um die Grenze k -> Mitte k-1/2 (z_m: +1/2)
            belegt[max(0, a - nms):min(len(ae), b + nms + 1)] = True
            eig.append((s, z, int(sg), float(ae[k_])))
        out += eig
    if STUETZ_STREIFEN > 1 and out:
        from collections import defaultdict
        nach = defaultdict(list)
        for q in out: nach[(q[0], q[2])].append(q[1])
        nach = {k: np.asarray(v) for k, v in nach.items()}

        def gestuetzt(q):
            for ds in (-1, 1):
                v = nach.get((q[0] + ds, q[2]))
                if v is not None and np.any(np.abs(v - q[1]) <= nms): return True
            return False
        out = [q for q in out if gestuetzt(q)]
    return out


def paaren(Lm, Lw, such=SUCH_M):
    """Modell-Linien gegen Wolken-Linien (gleicher Streifen, gleiches Vorzeichen) -> dz je Modell-Linie (Meter, None = ohne Partner), dz je Wolken-Linie."""
    from collections import defaultdict
    W = defaultdict(list); M = defaultdict(list)
    for s, z, sg, _ in Lw: W[(s, sg)].append(z)
    for s, z, sg, _ in Lm: M[(s, sg)].append(z)
    W = {k: np.asarray(v) for k, v in W.items()}; M = {k: np.asarray(v) for k, v in M.items()}

    def naechst(z, arr):
        if arr is None or not len(arr): return None
        d = (arr - z) * DZ_M; i = int(np.argmin(np.abs(d))); return float(d[i]) if abs(d[i]) <= such else None
    dm = [naechst(z, W.get((s, sg))) for s, z, sg, _ in Lm]
    dw = [naechst(z, M.get((s, sg))) for s, z, sg, _ in Lw]
    return dm, dw


def bewerten(Lm, Lw):
    dm, dw = paaren(Lm, Lw); nm, nw = len(Lm), len(Lw)
    e = dict(n_modell=nm, n_wolke=nw)
    if not nm or not nw: return dict(e, hoehensitz=0.0 if (nm or nw) else None, a10=None, a25=None, recall25=None, med_dz=None, hoeher=None, dz=dm)
    wm = np.minimum([q[3] for q in Lm], W_MAX) if W_MAX else np.ones(nm); ww = np.minimum([q[3] for q in Lw], W_MAX) if W_MAX else np.ones(nw)
    a = lambda d, t, w: float(np.average([x is not None and abs(x) < t for x in d], weights=w))
    p, r = a(dm, TOL[1], wm), a(dw, TOL[1], ww); gp = [abs(x) for x in dm if x is not None]; vz = [x for x in dm if x is not None and abs(x) >= TOL[0]]
    return dict(e, hoehensitz=(2 * p * r / (p + r)) if p + r > 0 else 0.0, a10=a(dm, TOL[0], wm), a25=p, recall25=r, med_dz=float(np.median(gp)) if gp else None,
                hoeher=float(np.median(vz)) if len(vz) >= 3 else None, dz=dm)


def guete(s, s0):
    if s is None or s0 is None: return None
    return (s - s0) / max(1e-6, 1.0 - s0)


def null_varianten(weiten=NULL_M):
    return [(0.0, 0.0, sg * w) for w in weiten for sg in (1, -1)]


def verschoben(P, d):
    return P + np.asarray(d, np.float32)


def gemeinsam_maske(rm, rw):
    return np.isfinite(rm) & np.isfinite(rw)


def seite_messen(PM, PW, ax, geo, rw=None, min_m=None, min_w=None):
    """Modell-Profil gegen Wolken-Profil einer Seite -> (bewertung, Lm, Lw, rm, rw). Fuer die Decke ist das 'Modell' eine Wolkenhaelfte (min_m kleiner)."""
    rm = profil(PM, ax, geo, min_m or MIN_MODELL)
    if rw is None: rw = profil(PW, ax, geo, min_w or MIN_WOLKE)
    g = gemeinsam_maske(rm, rw); Lm, Lw = linien(rm, g), linien(rw, g)
    return bewerten(Lm, Lw), Lm, Lw, rm, rw


def gesims_heben(P, ax, geo, z0, weite=ROT_M, halb=ROT_HALB, rampe=ROT_RAMPE):
    """ROT-PROBE: Punkte der Seitenhaelfte ax (ohne 1 m an den Ecken) um z0 verformen: |z - z0| < halb starr um weite nach oben, Uebergang ueber rampe.
    Monoton in z (unten gedehnt, oben gestaucht) - die Linie bei z0 sitzt danach bei z0 + weite, Linien > halb + rampe entfernt bleiben."""
    i, sg, j, mitte = seiten_rahmen(ax, geo["lo"], geo["hi"]); Q = P.copy()
    sel = ((P[:, i] - mitte) * sg > 0) & (P[:, j] > geo["lo"][j] + 1.0) & (P[:, j] < geo["hi"][j] - 1.0)
    z = P[sel, 2]; a = np.abs(z - z0); w = np.clip(1.0 - np.maximum(0.0, a - halb) / rampe, 0.0, 1.0)
    Q[sel, 2] = z + weite * w; return Q, int(sel.sum())


# ---------------------------------------------------------------- Ablauf
def geo_aus(lo, hi):
    lo = np.asarray(lo, float); hi = np.asarray(hi, float); t0 = lo[:2] - RAND_M
    nt = np.ceil((hi[:2] - lo[:2] + 2 * RAND_M) / STREIF_M).astype(int); z0 = lo[2] - 0.5; nz = int(np.ceil((hi[2] - z0 + 3.0) / DZ_M))
    return dict(lo=lo, hi=hi, t0=t0, nt=nt, z0=z0, nz=nz)


def z_m(geo, zi):
    return geo["z0"] + (zi + 0.5) * DZ_M


def fehlerliste(Lm, bew, geo, ax, n=8):
    i, sg, j, _ = seiten_rahmen(ax, geo["lo"], geo["hi"]); out = []
    for (s, zi, vz, st), d in zip(Lm, bew["dz"]):
        if d is not None and abs(d) < TOL[1]: continue
        out.append(dict(t=round(float(geo["t0"][j] + (s + 0.5) * STREIF_M), 2), z=round(float(z_m(geo, zi)), 2), dz=None if d is None else round(d, 3),
                        art="ohne Partner" if d is None else ("Modell zu hoch" if d < 0 else "Modell zu tief"), staerke=round(st, 3), vorzeichen=vz))
    out.sort(key=lambda q: (-(q["staerke"]) if q["dz"] is not None else 0, ))
    gep = [q for q in out if q["dz"] is not None]; ohne = [q for q in out if q["dz"] is None]
    return (sorted(gep, key=lambda q: -abs(q["dz"])) + sorted(ohne, key=lambda q: -q["staerke"]))[:n]


def rot_hoehe(Lm, bew, geo):
    """Hoehe (m) der waagerechten Linie, die in den meisten Streifen RICHTIG (< 10 cm) sitzt - Kandidat fuer die Rot-Probe (ein Gesims)."""
    from collections import Counter
    z = [round(z_m(geo, zi) / 0.2) * 0.2 for (s, zi, vz, st), d in zip(Lm, bew["dz"]) if d is not None and abs(d) < TOL[0]]
    if not z: return None
    zz, k = Counter(z).most_common(1)[0]
    near = [z_m(geo, zi) for (s, zi, vz, st), d in zip(Lm, bew["dz"]) if d is not None and abs(d) < TOL[0] and abs(z_m(geo, zi) - zz) <= 0.15]
    return float(np.median(near)), k


def kontrollbild(pfad, felder, geo):
    import cv2
    px = 12; bilder = []
    for ax, name, rw, Lm, Lw, bew in felder:
        i, sg, j, _ = seiten_rahmen(ax, geo["lo"], geo["hi"]); nt, nz = rw.shape; W, H = nt * px, int(nz * DZ_M * px) + 1
        img = np.full((H, W, 3), 245, np.uint8)
        f = np.isfinite(rw)
        if f.any():
            v = rw.copy(); lo_, hi_ = np.nanpercentile(v[f], 5), np.nanpercentile(v[f], 98); g = np.clip((v - lo_) / max(1e-6, hi_ - lo_), 0, 1)
            for s in range(nt):
                for k_ in np.nonzero(f[s])[0]:
                    y = H - 1 - int((k_ + 1) * DZ_M * px); c = int(60 + 170 * g[s, k_]); img[max(0, y):y + max(1, int(DZ_M * px)) + 1, s * px:(s + 1) * px] = (c, c, c)
        zy = lambda zi: H - 1 - int((zi + 0.5) * DZ_M * px)
        for s, zi, vz, st in Lw: cv2.line(img, (s * px, zy(zi)), ((s + 1) * px - 1, zy(zi)), (255, 255, 255), 1)
        for (s, zi, vz, st), d in zip(Lm, bew["dz"]):
            col = (150, 50, 150) if d is None else ((70, 170, 40) if abs(d) < TOL[0] else ((40, 200, 230) if abs(d) < TOL[1] else (40, 40, 220)))
            cv2.line(img, (s * px + 2, zy(zi) + 1), ((s + 1) * px - 3, zy(zi) + 1), col, 2)
        for zm in range(0, int(nz * DZ_M), 5):
            y = H - 1 - int((zm - geo["z0"]) * px); cv2.line(img, (0, y), (4, y), (0, 0, 0), 1); cv2.putText(img, f"{zm}", (5, y + 4), 0, 0.3, (0, 0, 0), 1)
        kopf = np.full((34, max(W, 240), 3), 255, np.uint8); f_ = lambda x, n=2: "-" if x is None else f"{x:.{n}f}"
        cv2.putText(kopf, f"{name} ({ax}) hs {f_(bew.get('hoehensitz'))} Zufall {f_(bew.get('hoehensitz_null'))}", (3, 13), 0, 0.38, (20, 20, 20), 1, cv2.LINE_AA)
        cv2.putText(kopf, f"a10 {f_(bew.get('a10'))} a25 {f_(bew.get('a25'))} med {f_(bew.get('med_dz'))} m", (3, 28), 0, 0.38, (20, 20, 20), 1, cv2.LINE_AA)
        if W < kopf.shape[1]: img = np.hstack([img, np.full((H, kopf.shape[1] - W, 3), 255, np.uint8)])
        bilder.append(np.vstack([kopf, img]))
    if not bilder: return
    hm = max(b.shape[0] for b in bilder); bilder = [np.vstack([b, np.full((hm - b.shape[0], b.shape[1], 3), 255, np.uint8)]) for b in bilder]
    B = np.hstack([np.hstack([b, np.full((hm, 8, 3), 255, np.uint8)]) for b in bilder]); leg = np.full((20, B.shape[1], 3), 255, np.uint8)
    cv2.putText(leg, "grau Wolken-Aussenlage | weiss Wolken-Linie | Modell-Linie gruen <10 cm, gelb <25 cm, rot falsch, violett ohne Partner | z in m", (4, 14), 0, 0.36, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, np.vstack([B, leg]))


def seiten_namen(obj, achsen):
    sk = obj.get("seiten_konvention") or {}
    return {ax: sk.get(ax, ax) for ax in achsen}


def laden(a):
    """Gemeinsamer Lader (auch tools/hoehen_angleich.py): a mit objekt, fotosatz, wolke, stl, n_wolke, n_modell ->
    dict(obj, od, root, audit, achsen, namen, sp, stl, PM, PW, info, lo, hi, rahmen) oder str (Fehlermeldung). rahmen = Verschiebung STL-Meter -> Kamerarahmen."""
    import formsitz as FS, konvergenz_wolke as KW
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    audit = os.path.join(root, obj.get("audit") or os.path.relpath(os.path.join(od, "audit"), root))
    if not obj.get("seiten_konvention"): print("HINWEIS: objekt.json ohne seiten_konvention - Seiten heissen nach Achsen (+x/-x/+y/-y)")
    S, sp = FS.fotosatz_laden(a, obj, od, root)
    sk = obj.get("seiten_konvention") or {}
    achsen = [ax for ax in ACHSEN if ax in sk] or [ax for ax in S.get("seiten", {}) if ax in ACHSEN] or list(ACHSEN); namen = seiten_namen(obj, achsen)
    stl = a.stl or os.path.join(root, obj.get("stl") or "-")
    if not os.path.exists(stl): return f"FEHLER: STL fehlt ({stl})"
    wp = KW.wolke_pfad(obj, od, a.wolke)
    if not wp or not os.path.exists(wp): return f"FEHLER: keine dichte Wolke ({wp})"
    kk = None
    for nr in sorted({nr for s in S["seiten"].values() for nr in s["fotos"]}):
        try: kk = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json"))).get("kamera") or {}; break
        except Exception: pass
    if kk is None: return "FEHLER: keine K-Datei des Fotosatzes lesbar (Rahmenverschiebung)"
    T0 = FS.stl_dreiecke(stl); T = FS.modell_kamerarahmen(T0, obj, kk)
    sk_ = np.float32(obj.get("stl_massstab", 87) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0)
    rahmen = (T.reshape(-1, 3)[0] - T0.reshape(-1, 3)[0] * sk_).astype(float); del T0
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    PM, _ = FS.abtasten(T, a.n_modell); del T
    box_lo, box_hi = lo.astype(float) - RAND_M, hi.astype(float) + RAND_M; box_lo[2] = lo[2] + BODEN_M
    PW, info = KW.wolke_laden(wp, (box_lo, box_hi), a.n_wolke, boden_m=0.0)
    if len(PW) < 1000: return f"FEHLER: Wolke im Modellbereich fast leer ({info})"
    return dict(obj=obj, od=od, root=root, audit=audit, achsen=achsen, namen=namen, sp=sp, stl=stl, PM=PM, PW=PW, info=info, lo=lo, hi=hi, rahmen=rahmen)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotosatz"); ap.add_argument("--wolke"); ap.add_argument("--stl"); ap.add_argument("--json")
    ap.add_argument("--bild"); ap.add_argument("--probe", action="store_true"); ap.add_argument("--rot", action="store_true")
    ap.add_argument("--n-wolke", type=int, default=N_WOLKE); ap.add_argument("--n-modell", type=int, default=N_MODELL); a = ap.parse_args(argv)
    t_start = time.time()
    L = laden(a)
    if isinstance(L, str): print(L); return 1
    audit, achsen, namen, sp, stl, PM, PW, info, lo, hi = (L[k] for k in ("audit", "achsen", "namen", "sp", "stl", "PM", "PW", "info", "lo", "hi"))
    geo = geo_aus(lo, hi); halb = np.random.default_rng(1).random(len(PW)) < 0.5; PA, PB = PW[halb], PW[~halb]
    print(f"HOEHENSITZ: Modell {len(PM)} Punkte, Wolke {info['n_box']} im Bereich -> {len(PW)} genutzt ({time.time() - t_start:.0f} s geladen)", flush=True)
    nullv = null_varianten(); seiten, probe, rot, felder = {}, {}, {}, []
    rw_je, basis, rb_je, decke_basis, mh = {}, {}, {}, {}, max(2, MIN_WOLKE // 2)
    for ax in achsen:
        bew, Lm, Lw, rm, rw = seite_messen(PM, PW, ax, geo); rw_je[ax] = rw; basis[ax] = (bew, Lm)
        nul = [seite_messen(verschoben(PM, d), PW, ax, geo, rw)[0]["hoehensitz"] for d in nullv]; nul = [x for x in nul if x is not None]
        s0 = float(np.median(nul)) if nul else None
        rb = profil(PB, ax, geo, mh); rb_je[ax] = rb
        dk, LA, _, _, _ = seite_messen(PA, None, ax, geo, rb, min_m=mh); decke_basis[ax] = (dk, LA)
        dn = [seite_messen(verschoben(PA, d), None, ax, geo, rb, min_m=mh)[0]["hoehensitz"] for d in nullv]; dn = [q for q in dn if q is not None]
        decke, decke_null = dk["hoehensitz"], (float(np.median(dn)) if dn else None)
        ts = (decke - decke_null) if decke is not None and decke_null is not None else None
        e = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in bew.items() if k != "dz"}
        e.update(name=namen[ax], hoehensitz_null=None if s0 is None else round(s0, 4), guete=None if guete(bew["hoehensitz"], s0) is None else round(guete(bew["hoehensitz"], s0), 4),
                 decke=None if decke is None else round(decke, 4), decke_null=None if decke_null is None else round(decke_null, 4), trennschaerfe=None if ts is None else round(ts, 4),
                 fehler=fehlerliste(Lm, bew, geo, ax))
        e["trennt"] = bool(ts is not None and ts >= TRENN_MIN and bew["n_wolke"] >= N_LINIEN_MIN)
        e["status"] = "trennt" if e["trennt"] else (TRENNT_NICHT if bew["n_wolke"] >= N_LINIEN_MIN else "zu wenig Linien")
        seiten[ax] = e; felder.append((ax, namen[ax], rw, Lm, Lw, dict(bew, hoehensitz_null=s0)))
        if a.probe:
            pr = {}
            for d in PROBE_M:
                for sg in (1, -1):
                    q = seite_messen(verschoben(PM, (0, 0, sg * d)), PW, ax, geo, rw)[0]["hoehensitz"]
                    pr[f"{'+' if sg > 0 else '-'}z {d:g} m"] = None if q is None or bew["hoehensitz"] is None else round(bew["hoehensitz"] - q, 4)
                    # dieselbe Nullprobe mit dem 'perfekten Modell' Wolkenhaelfte A gegen B: zeigt die Hoehenschaerfe des Masses unabhaengig vom Modellstand
                    q = seite_messen(verschoben(PA, (0, 0, sg * d)), None, ax, geo, rb, min_m=mh)[0]["hoehensitz"]
                    pr[f"decke {'+' if sg > 0 else '-'}z {d:g} m"] = None if q is None or decke is None else round(decke - q, 4)
            probe[ax] = pr
        print(f"  {namen[ax]} ({ax}): hoehensitz {e['hoehensitz']} Zufall {e['hoehensitz_null']} | Decke {e['decke']} Zufall {e['decke_null']} Trennschaerfe {e['trennschaerfe']}"
              f" | a10 {e['a10']} a25 {e['a25']} med|dz| {e['med_dz']} Linien M {e['n_modell']} W {e['n_wolke']} -> {e['status']} ({time.time() - t_start:.0f} s)", flush=True)
    def rot_probe(P0, bas, ref, mm, wer):
        """Rot-Probe: die staerkste richtig sitzende Linie der Seite im 'Modell' P0 (Modell oder Wolkenhaelfte A) um ROT_M heben -> je Seite Abfall + Meldung."""
        out = {}
        for ax in achsen:
            bew0, Lm0 = bas[ax]; zr = rot_hoehe(Lm0, bew0, geo)
            if zr is None: out[ax] = dict(erkannt=False, grund="keine richtig sitzende Linie"); continue
            z0, k = zr; Q, n = gesims_heben(P0, ax, geo, z0); abf = {}; fl = []
            for ax2 in achsen:
                q = seite_messen(Q, None, ax2, geo, ref[ax2], min_m=mm)
                abf[ax2] = None if q[0]["hoehensitz"] is None else round(bas[ax2][0]["hoehensitz"] - q[0]["hoehensitz"], 4)
                if ax2 == ax: fl = fehlerliste(q[1], q[0], geo, ax, n=None)
            treffer = [f for f in fl if f["dz"] is not None and abs(f["z"] - (z0 + ROT_M)) <= 0.2 and -ROT_M - 0.15 <= f["dz"] <= -ROT_M + 0.15]
            andere = [v for k2, v in abf.items() if k2 != ax and v is not None]
            out[ax] = dict(z0=round(z0, 2), streifen=k, punkte=n, abfall_je_seite=abf, eigene=abf.get(ax), andere_max=max(andere) if andere else None,
                           linien_gemeldet=len(treffer), erkannt=bool(len(treffer) >= max(1, k // 2) and (abf.get(ax) or 0) > 0 and (not andere or max(andere) < abf[ax])))
            print(f"      ROT ({wer}) {namen[ax]}: Linie z0 {z0:.2f} m ({k} Streifen) um {ROT_M} m gehoben -> Abfall {abf.get(ax)} (andere {andere}), {len(treffer)} Linien "
                  f"'zu hoch ~{ROT_M}' gemeldet -> {'erkannt' if out[ax]['erkannt'] else 'NICHT erkannt'}", flush=True)
        return out
    rot_decke = {}
    if a.rot:
        rot = rot_probe(PM, basis, rw_je, None, "Modell")
        rot_decke = rot_probe(PA, decke_basis, rb_je, mh, "Wolkenhaelfte A gegen B")
    erg = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), fotosatz=sp and os.path.abspath(sp), stl=os.path.abspath(stl), wolke=info, sek=round(time.time() - t_start, 1),
               schwellen=dict(dz_m=DZ_M, streif_m=STREIF_M, q_aussen=Q_AUSSEN, h_m=H_M, umgeb_m=UMGEB_M, sprung_m=SPRUNG_M, such_m=SUCH_M, tol=list(TOL), null_m=list(NULL_M),
                              trenn_min=TRENN_MIN, n_linien_min=N_LINIEN_MIN), seiten=seiten)
    if probe: erg["probe"] = probe
    if rot: erg["rot"] = rot
    if rot_decke: erg["rot_decke"] = rot_decke
    jp = a.json or os.path.join(audit, "hoehensitz.json"); os.makedirs(os.path.dirname(os.path.abspath(jp)), exist_ok=True)
    json.dump(erg, open(jp + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(jp + ".tmp", jp)
    if a.bild:
        try: kontrollbild(a.bild, felder, geo)
        except Exception as ex: print(f"HINWEIS: Kontrollbild nicht geschrieben ({type(ex).__name__}: {ex})")
    print(f"HOEHENSITZ je Seite (waagerechte Strukturlinien Modell gegen dichte Wolke; Zufall = Modell {'/'.join(f'{m:g}' for m in NULL_M)} m in z):")
    for ax, e in seiten.items():
        print(f"  {e['name']}: hoehensitz {e['hoehensitz']} Zufall {e['hoehensitz_null']} guete {e['guete']} Trennschaerfe {e['trennschaerfe']} a10 {e['a10']} a25 {e['a25']}"
              f" med|dz| {e['med_dz']} m -> {e['status']}")
        for f in e["fehler"][:3]: print(f"      Linie t {f['t']} z {f['z']} m: {f['art']}" + (f" (dz {f['dz']:+.2f} m)" if f["dz"] is not None else ""))
        if ax in probe: print("      Probe Abfall: " + ", ".join(f"{k_} {v_}" for k_, v_ in probe[ax].items()))
    print(f"Bericht: {jp} ({erg['sek']} s)")
    return 0 if any(e.get("n_wolke") for e in seiten.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
