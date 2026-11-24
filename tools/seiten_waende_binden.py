#!/usr/bin/env python3
"""seiten_waende_binden.py <dicht_a.ply> <dicht_b.ply> --gps <vereinen.json> --aus <ordner> [--modell-a <sparse> --modell-b <sparse> --bilder <fotos>]

GEGENSEITEN UEBER GEMEINSAME WAENDE BINDEN (24.11.2026, Kettenlauf schwabentor-1122w, Teil 1 = Suedseite, 63 Bilder).
BEFUND: Klappung gescheitert, Querspur abgelehnt, LoD2 je Teil "Bestwert am Kastenrand" -> Teil 1 nur ueber das Foto-GPS (+-1,4 Grad Bootstrap) und darum WEGGELASSEN.
GEMESSEN (dichte Wolken der Teile, B per GPS-Lage auf A):
  - Die Klappung ist fuer diesen Fall der falsche Ansatz: Teil 1 ist keine Gegenseiten-VERWECHSLUNG (Martinstor), sondern eine andere Seite, die Teil 0 nie im selben Bild
    hat. Die 19 Klapp-Inlier (von 105 Punktpaaren) legen B schon OHNE Klappen auf die richtige Seite (Kameras 173 Grad auseinander, Nachbarbau auf DERSELBEN Flanke wie in A
    - erst die Klappung bringt ihn auf die falsche). Die Turmhoehen-Probe scheitert, weil die dichte Wolke von A oben duenn ist (A 33 m p99,9, B 41 m).
  - Die GPS-Lage von B ist um 9,9 Grad GEKIPPT (Lot der B-Waende gegen das Lot der A-Waende; 3431 bzw. 20505 Wandnormalen): das Foto-GPS legt nur den Grundriss fest,
    das Lot von B kommt aus den Bild-x-Achsen von 63 Fotos. Dazu 5,7 Grad Wandrichtung (A 83,7 / B 78,0 Grad mod 90) - beides ist mit "+-1,4 Grad" nicht beschrieben.
  - Teil 0 sieht den Turm oberhalb der Nachbardaecher RUNDUM (Kasten aus vier Wandlinien z 14-40 m, Drohnen-/Fernbilder). Teil 1 sieht Suedwand + Ostflanke
    desselben Turms -> GEMEINSAME WAENDE (die Wand, die B frontal sieht, hat A schraeg von oben). Das ist eine Bindung ohne gemeinsame Bildmerkmale.
VERFAHREN (nur CPU, Sekunden):
  1. LOT VON B aus seinen EIGENEN Waenden (seiten_vereinen.lot_aus_waenden, dichte Wolke) gegen das Wand-Lot von A -> Kippung um die Mitte der B-Wolke. Unabhaengig vom GPS.
  2. WANDPUNKTE beider Teile: ebene, senkrechte Flaechenstuecke (Normale waagerecht) ueber Strassenhoehe (Z_MIN_M), im Grundriss um die B-Waende.
  3. GRUNDRISS-SUCHE im GPS-Korridor (seiten_querspur_binden.korridor, gleiche Grenzen wie die Querspur): Drehung um das Lot x Verschiebung, Wertung = mittlere Naehe der
     B-Wandpunkte zu den A-Waenden (Abstandsfeld, Kreuzkorrelation per FFT). Dann Feinausgleich Punkt-zu-Linie (Drehung + Verschiebung, Massstab bleibt GPS).
  4. HOEHE: Hoehenprofil der gemeinsam belegten Wandstuecke (Fenster, Gesimse, Traufe) von A und B kreuzkorreliert -> Versatz in z; nur bei eindeutigem Gipfel, sonst bleibt
     die GPS-Hoehe (gemeldet).
TOR (jede Probe einzeln, uebernommen nur wenn ALLE bestehen; sonst bleibt die GPS-Lage):
  - eindeutig: zweitbester Gipfel >= ABSTAND_ZWEIT_M entfernt hoechstens ZWEIT_ANTEIL des besten (eine Wand allein gleitet laengs -> mehrdeutig);
  - nicht am Kastenrand der Suche; Ergebnis im GPS-Korridor (Drehung, Massstab, Lage der B-Kameras; die KIPPUNG wird hier aus den Waenden gemessen, nicht vom GPS);
  - beide Wandrichtungen tragen (je >= MIN_RICHTUNG_ANTEIL der Treffer), Trefferanteil >= MIN_TREFFER;
  - ZWEI HOEHENBAENDER (unter/ueber dem Median der B-Wandpunkte) einzeln ausgeglichen stimmen ueberein (<= BAND_LAGE_M, <= BAND_DREH_GRAD) - zwei getrennte Bauteile;
  - Wandabstand B->A danach kleiner als in der GPS-Lage;
  - TURMSPITZE (in der Bindung nicht benutzt): sehen beide Wolken eine schlanke Spitze in gleicher Hoehe, liegt sie waagerecht uebereinander (sonst 'nicht messbar', Bericht);
  - GEOTAGS VON B (main, --bilder): B-Kameras nach der Bindung ueber den A-Rahmen in ENU - Median hoechstens GPS_MEHR_M schlechter als die GPS-Lage, >= 70 % unter 12 m.
  Der Korridor nutzt die EHRLICHE GPS-Unsicherheit (Bootstrap + Sitzungsfehler); die Lage der B-Kameras zaehlt nur waagerecht; die Kippung um die Mitte der B-Kameras
  (dort traegt das GPS die Hoehe).
1122w (24.11., Zwischendaten nur gelesen, CPU ~2 min): Kippung 10,0 Grad (um den Fusspunkt), Drehung +4,6 Grad, Verschiebung 3,6 m; Wandabstand Median 2,40 -> 0,07 m, Treffer 60 %,
  Geotags von B 5,1 -> 7,8 m (79 % < 12 m), Turmspitze nicht messbar (A-Wolke oben duenn), Hoehe am Fusspunkt nach GPS (Profil nicht eindeutig, nur Bericht). Seitenansicht: Turm, Helm und Uhr
  von A und B decken sich (vorher Helm um Meter versetzt und geneigt).
Ausgabe <aus>/waende.json (ok, urteil, B_nach_A nur bei ok, B_nach_A_gps, pruefung{...}, korridor), Kontrollbild <aus>/waende.jpg (Grundriss vorher/nachher + Hoehe).
rc 0 = gebunden, 2 = zu wenig Eingabe/Wandpunkte (nichts getan), 3 = abgelehnt. GRENZEN: Massstab bleibt der des GPS (nur gemeldet: B-Turm gegen A); braucht einen Teil A,
der die von B gesehenen Waende mitsieht (Drohne/Fernbild/Uebereck); bei einem Kastenturm mit vier gleichen Seiten verhindert der GPS-Korridor die 90-Grad-Verwechslung.
Test: tests/test_seiten_waende_binden.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap nur fuer die B-Kameras; ohne Modell: B-Wolke als Bezug)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from seiten_querspur_binden import gps_unsicherheit, korridor, zerlege, anwenden, KIPP_MAX_GRAD   # gleicher GPS-Korridor wie die Querspur-Bindung
from seiten_vereinen import lot_aus_waenden, stange

Z_MIN_M = 3.0             # ANNAHME: Wandpunkte erst ueber Strassenhoehe (Autos, Schilder, Passanten)
ZELLE_M = 0.10            # Raster des Abstandsfelds
SIGMA_M = 0.15            # Naehe-Wertung exp(-d^2 / 2 sigma^2); Wanddicke-Rauschen der dichten Wolken ~0,05-0,1 m
DREH_SCHRITT = 0.25       # Grad, Grobsuche
TREFFER_M = 0.25          # B-Wandpunkt "auf einer A-Wand"
MIN_WANDPUNKTE = 150      # ANNAHME: je Teil im Suchgebiet
MIN_TREFFER = 0.40        # ANNAHME: Anteil der B-Wandpunkte auf A-Waenden nach der Bindung
MIN_RICHTUNG_ANTEIL = 0.10  # ANNAHME: jede der zwei Wandrichtungen traegt >= 10 % der Treffer (sonst gleitet B laengs der einen Wand)
ZWEIT_ANTEIL = 0.85       # ANNAHME: zweitbester Gipfel (>= ABSTAND_ZWEIT_M entfernt) hoechstens 85 % des besten
ABSTAND_ZWEIT_M = 1.0
BAND_LAGE_M = 0.30        # ANNAHME: zwei Hoehenbaender einig auf 0,3 m ...
BAND_DREH_GRAD = 1.0      # ... und 1 Grad
KIPP_GRENZE_GRAD = 15.0   # lot_aus_waenden sucht Normalen nur bis ~14 Grad um das Start-Lot
RAND_M = 0.2              # Gipfel naeher als 0,2 m am Suchrand = Kastenrand
Z_PROFIL_M = 0.2          # Hoehenprofil-Raster
MIN_KIPP_NORMALEN = 300
SPITZE_M = 0.6            # ANNAHME: Helmstangen beider Teile waagerecht <= 0,6 m (Martinstor: oberstes Band traf die Handmessung auf 0,1 m)
SPITZE_HOEHE_ANTEIL = 0.10  # Spitze nur vergleichbar, wenn beide Wolken sie bis auf 10 % der Hoehe erreichen
SPITZE_SCHLANK_M = 1.0    # ANNAHME: ... und das oberste Band schlank ist (Streuung <= 1 m; 1122w: B 0,3 m, A 3,9 m = Spitze in A nicht getroffen)
GPS_MEHR_M = 3.0          # ANNAHME: Geotags von B duerfen nach der Bindung im Median hoechstens 3 m weiter weg liegen (~1 Sigma Sitzungsfehler 3,4 m, gps_unsicherheit)
GPS_ANTEIL_MIN = 0.70     # ANNAHME: und >= 70 % unter seiten_gps_vereinen.GRENZE_M (12 m)
DREH_SUCHE_MAX = 20.0     # ANNAHME: Suche um das Lot hoechstens +-20 Grad (weit weg von 45/90 Grad - Kastenturm-Verwechslung)
LAGE_SUCHE_MAX_M = 8.0    # ANNAHME: Verschiebung hoechstens +-8 m (Rechenaufwand; ein Turm von 8-12 m Seite wuerde sonst auf die Nachbarwand rutschen)


# ---------- Grundlagen
def drehung(achse, grad):
    a = np.asarray(achse, float); a = a / np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]); w = np.radians(grad)
    return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


def basis(lot):
    e1 = np.cross(lot, [1.0, 0, 0] if abs(lot[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); return np.array([e1, np.cross(lot, e1), lot])


def ply_lesen(p, max_n=1500000):
    """xyz einer COLMAP-fused.ply (27 Byte je Punkt), gleichmaessig ausgeduennt per memmap (die A-Wolke hat 16 Mio. Punkte / 450 MB)."""
    f = open(p, "rb"); n = 0; kopf = 0
    while True:
        l = f.readline(); kopf += len(l); s = l.decode(errors="replace").strip()
        if s.startswith("element vertex"): n = int(s.split()[-1])
        if s == "end_header" or not l: break
    m = np.memmap(p, dtype=np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)]), mode="r", offset=kopf, shape=(n,))
    return np.asarray(m["p"][::max(1, n // max_n)], np.float64)


def wandpunkte(X, k=16, flach=0.02, senk=0.15, n_max=400000, saat=0):
    """Ebene, senkrechte Flaechenstuecke (lokales System, z = Lot) -> (Punkte, Normalen)."""
    from scipy.spatial import cKDTree
    if len(X) > n_max: X = X[np.random.default_rng(saat).choice(len(X), n_max, replace=False)]
    if len(X) < k + 1: return X[:0], X[:0]
    _, I = cKDTree(X).query(X, k); Nb = X[I] - X[I].mean(1, keepdims=True); w, U = np.linalg.eigh(np.einsum('nki,nkj->nij', Nb, Nb)); n = U[:, :, 0]
    ok = (w[:, 0] / (w[:, 1] + 1e-30) < flach) & (np.abs(n[:, 2]) < senk); return X[ok], n[ok]


def r2(g):
    c, s = np.cos(np.radians(g)), np.sin(np.radians(g)); return np.array([[c, -s], [s, c]])


# ---------- Grundriss-Suche
def feld(PA2, mitte, halb):
    """Naehe-Feld exp(-d^2/2sigma^2) der A-Wandpunkte auf einem Raster um 'mitte' (+-halb m). -> (S, ursprung)."""
    from scipy.ndimage import distance_transform_edt
    n = int(np.ceil(2 * halb / ZELLE_M)) + 1; o = np.asarray(mitte) - halb; ij = np.floor((PA2 - o) / ZELLE_M).astype(int)
    ok = (ij >= 0).all(1) & (ij < n).all(1); belegt = np.ones((n, n), bool); belegt[ij[ok, 1], ij[ok, 0]] = False
    d = distance_transform_edt(belegt) * ZELLE_M; return np.exp(-d ** 2 / (2 * SIGMA_M ** 2)), o


def suche(PA2, PB2, c, grad_max, lage_max):
    """Grobsuche Drehung (um c) x Verschiebung. -> dict(dreh, schieb, wert, zweit, zweit_abstand, rand, karte)."""
    from scipy.signal import fftconvolve
    r_b = float(np.percentile(np.linalg.norm(PB2 - c, axis=1), 99)); halb = r_b + lage_max + 2.0; S, o = feld(PA2, c, halb); n = S.shape[0]
    ks = int(np.ceil(lage_max / ZELLE_M)); best = None; karte = None; schritt = DREH_SCHRITT if grad_max <= 5 else 2 * DREH_SCHRITT   # weite Suche grober, fein() gleicht nach
    for g in np.arange(-grad_max, grad_max + 1e-9, schritt):
        Q = (PB2 - c) @ r2(g).T; ij = np.round(Q / ZELLE_M).astype(int); m = int(np.abs(ij).max()) + 1
        K = np.zeros((2 * m + 1, 2 * m + 1)); np.add.at(K, (ij[:, 1] + m, ij[:, 0] + m), 1.0)
        Kk = fftconvolve(S, K[::-1, ::-1], mode="same") / len(PB2)                  # Kk[y, x] = Summe S an (Punkte + Verschiebung, Mitte = Rasterzelle y, x)
        ci = int(round((c[0] - o[0]) / ZELLE_M)); cj = int(round((c[1] - o[1]) / ZELLE_M))
        A = Kk[cj - ks:cj + ks + 1, ci - ks:ci + ks + 1]
        if karte is None: karte = A.copy()
        else: karte = np.maximum(karte, A)
        j, i = np.unravel_index(np.argmax(A), A.shape)
        if best is None or A[j, i] > best[0]: best = (float(A[j, i]), float(g), np.array([(i - ks) * ZELLE_M, (j - ks) * ZELLE_M]))
    w, g, sv = best; jj, ii = np.mgrid[-ks:ks + 1, -ks:ks + 1] * ZELLE_M; d = np.hypot(ii - sv[0], jj - sv[1])
    innen = np.hypot(ii, jj) <= lage_max; zw = karte[(d >= ABSTAND_ZWEIT_M) & innen]; z = float(zw.max()) if len(zw) else 0.0
    zi = np.unravel_index(np.argmax(np.where((d >= ABSTAND_ZWEIT_M) & innen, karte, -1)), karte.shape)
    rand = bool(np.hypot(*sv) > lage_max - RAND_M or abs(g) > grad_max - schritt / 2)
    return dict(dreh=g, schieb=sv, wert=w, zweit=z, zweit_abstand=float(np.hypot(ii[zi] - sv[0], jj[zi] - sv[1])), rand=rand)


def fein(PA2, NA2, PB2, c, g0, s0, runden=15, grenze=0.5):
    """Punkt-zu-Linie-Ausgleich (Drehung um c, Verschiebung): B-Wandpunkte auf die naechste A-Wand. -> (dreh, schieb, treffer-Maske)."""
    from scipy.spatial import cKDTree
    baum = cKDTree(PA2); g, s = float(g0), np.asarray(s0, float).copy()
    for k in range(runden):
        Q = (PB2 - c) @ r2(g).T + c + s; d, i = baum.query(Q); gr = max(TREFFER_M, grenze * (1 - k / runden))
        ok = d < gr
        if ok.sum() < 10: break
        n = NA2[i[ok]]; q = Q[ok]; p = PA2[i[ok]]; rq = q - c - s; J = np.c_[(n[:, 1] * rq[:, 0] - n[:, 0] * rq[:, 1]), n]   # d(n.(q-p))/d(dreh rad, sx, sy)
        r = np.einsum('ij,ij->i', n, q - p); x = np.linalg.lstsq(J, -r, rcond=None)[0]; g += float(np.degrees(x[0])); s += x[1:]
        if np.abs(x).max() < 1e-5: break
    Q = (PB2 - c) @ r2(g).T + c + s; d, _ = baum.query(Q); return g, s, d < TREFFER_M


def z_versatz(ZA, ZB, grenze):
    """Hoehenprofile (Dichte der Wandpunkte je Hoehe) von A und B kreuzkorreliert. -> (dz, eindeutig, guete)."""
    if len(ZA) < 50 or len(ZB) < 50: return 0.0, False, 0.0
    z0, z1 = min(ZA.min(), ZB.min()) - grenze, max(ZA.max(), ZB.max()) + grenze; b = np.arange(z0, z1 + Z_PROFIL_M, Z_PROFIL_M)
    def prof(Z):
        h = np.log1p(np.histogram(Z, b)[0].astype(float)); h = h - np.convolve(h, np.ones(15) / 15, "same"); return h / (np.linalg.norm(h) + 1e-12)
    pa, pb = prof(ZA), prof(ZB); k = int(np.ceil(grenze / Z_PROFIL_M)); L = np.arange(-k, k + 1)
    cc = np.array([np.dot(pa, np.roll(pb, l)) for l in L]); i = int(np.argmax(cc)); weit = np.abs(L - L[i]) * Z_PROFIL_M >= ABSTAND_ZWEIT_M
    zw = float(cc[weit].max()) if weit.any() else 0.0; ok = cc[i] > 0.2 and zw <= ZWEIT_ANTEIL * cc[i] and abs(L[i]) < k
    return float(L[i] * Z_PROFIL_M), bool(ok), float(cc[i])


# ---------- Kern
def binden(DA, DB, G, lot0, ref_b, bild=None):
    """DA/DB dichte Wolken (je eigenes Modellsystem), G = seiten_querspur_binden.gps_unsicherheit(...), lot0 = Start-Lot von A, ref_b = Bezugspunkte in B (Kamerazentren).
    -> Ergebnis-dict (ok, urteil, zu_wenig, B_nach_A bei ok, pruefung, korridor)."""
    mj = G["m_je_einheit"]; Mg = G["M"]; pr = {}; erg = dict(art="waende", B_nach_A_gps=Mg.tolist(), pruefung=pr)
    ua, na = lot_aus_waenden(DA, np.asarray(lot0, float)); Bg = anwenden(Mg, DB); ub, nb = lot_aus_waenden(Bg, ua)
    kipp = float(np.degrees(np.arccos(np.clip(ua @ ub, -1, 1)))); pr.update(lot_normalen_a=int(na), lot_normalen_b=int(nb), kippung_gps_grad=round(kipp, 2))
    if nb < MIN_KIPP_NORMALEN or na < MIN_KIPP_NORMALEN:
        erg.update(ok=False, zu_wenig=True, urteil=f"Lot aus den Waenden nicht messbar (Normalen A {na}, B {nb}, noetig {MIN_KIPP_NORMALEN}) - GPS-Lage bleibt"); return erg
    # KIPPUNG von B um den FUSSPUNKT seiner Wolke (waagerecht Wolkenmitte, Hoehe = Boden der B-Wolke): dort traegt die GPS-Lage die Hoehe (Boden der dichten Wolke
    # unter den nahen GPS-Kameras, seiten_gps_vereinen.rahmen). Waende legen die Hoehe nicht fest. 1122w gemessen: um die Kameramitte gekippt rutschte der Turm 8,4 m
    # waagerecht und 11,6 m nach oben (Fern-/Schlossbergkameras weit weg und hoch) - falsch; um die Wolkenmitte deckten sich Traufe, Uhr und Helm beider Teile.
    pv = np.median(Bg, 0); pv = pv - (pv @ ua - np.percentile(Bg @ ua, 2)) * ua; Rk = drehung(np.cross(ub, ua), kipp) if kipp > 1e-6 else np.eye(3)
    Mk = np.eye(4); Mk[:3, :3] = Rk; Mk[:3, 3] = pv - Rk @ pv
    E = basis(ua); L = np.eye(4); L[:3, :3] = mj * E                                   # lokales metrisches System von A (z = Lot)
    la = anwenden(L, DA); lb = anwenden(L @ Mk @ Mg, DB); boden = float(np.percentile(la[:, 2], 2))
    wa, nwa = wandpunkte(la[la[:, 2] > boden + Z_MIN_M]); wb, nwb = wandpunkte(lb[lb[:, 2] > boden + Z_MIN_M])
    c = np.median(wb[:, :2], 0) if len(wb) else np.zeros(2)
    # KORRIDOR mit der EHRLICHEN GPS-Unsicherheit (Zufall + Sitzungsfehler, gps_unsicherheit.py; Lehre 22.11.: Bootstrap allein unterschaetzt - 1122 Teil 1 Bootstrap +-1,4 Grad,
    # ehrlich +-9,3 Grad; die Waende messen 4-5 Grad). Suche hoechstens +-DREH_SUCHE_MAX (90-Grad-Verwechslung eines Kastenturms bleibt ausgeschlossen).
    G = dict(G, dreh_sd=max(G["dreh_sd"], G.get("dreh_sd_ehrlich") or 0.0), mass_sd=max(G["mass_sd"], G.get("mass_sd_ehrlich") or 0.0))
    k0 = korridor(Mg, G, ua, ref_b); gd, lg = min(k0["dreh_grenze_grad"], DREH_SUCHE_MAX), min(k0["lage_grenze_m"], LAGE_SUCHE_MAX_M); pr.update(dreh_grenze_grad=gd, lage_grenze_m=lg)
    r_b = float(np.percentile(np.linalg.norm(wb[:, :2] - c, axis=1), 99)) if len(wb) else 0.0; nah = np.linalg.norm(wa[:, :2] - c, axis=1) < r_b + lg + 2.0
    wa, nwa = wa[nah], nwa[nah]; pr.update(wandpunkte_a=int(len(wa)), wandpunkte_b=int(len(wb)))
    if len(wa) < MIN_WANDPUNKTE or len(wb) < MIN_WANDPUNKTE:
        erg.update(ok=False, zu_wenig=True, urteil=f"zu wenig Wandpunkte im Suchgebiet (A {len(wa)}, B {len(wb)}, noetig {MIN_WANDPUNKTE}) - GPS-Lage bleibt"); return erg
    A2, NA2 = wa[:, :2], nwa[:, :2] / (np.linalg.norm(nwa[:, :2], axis=1, keepdims=True) + 1e-12); B2 = wb[:, :2]
    from scipy.spatial import cKDTree
    d_vor = float(np.median(cKDTree(A2).query(B2)[0]))
    s = suche(A2, B2, c, gd, lg); pr["suche"] = dict(dreh_grad=round(s["dreh"], 2), schieb_m=[round(float(x), 2) for x in s["schieb"]], wert=round(s["wert"], 3), zweit=round(s["zweit"], 3),
                                                    zweit_abstand_m=round(s["zweit_abstand"], 2), kastenrand=s["rand"])
    g, sv, tr = fein(A2, NA2, B2, c, s["dreh"], s["schieb"])
    Q = (B2 - c) @ r2(g).T + c + sv
    di, ii = cKDTree(A2).query(Q); d_nach = float(np.median(di))
    ax = (np.degrees(np.arctan2(NA2[:, 1], NA2[:, 0])) % 90); az = float(np.degrees(np.angle(np.exp(4j * np.radians(ax)).mean())) / 4 % 90)
    u = np.array([np.cos(np.radians(az)), np.sin(np.radians(az))]); v = np.array([-u[1], u[0]])   # die zwei Wandrichtungen (Normalen) von A
    def richt(m):
        n_ = np.abs(nwb[m, :2] @ r2(g).T); return ((np.abs(n_ @ u) > 0.8).mean(), (np.abs(n_ @ v) > 0.8).mean()) if m.any() else (0.0, 0.0)
    ra, rb_ = richt(tr)
    # ZWEITE PROBE: zwei Hoehenbaender einzeln ausgeglichen. Verglichen wird die Lage nur laengs der Wandnormalen, die in BEIDEN Baendern tragen (eine Wand allein legt
    # die Lage laengs ihrer selbst nicht fest - 1122w: unteres Band sieht nur die Ostflanke und glitt 1,1 m laengs); traegt keine Richtung in beiden, keine Probe.
    zm = float(np.median(wb[:, 2])); baender = []
    for m in (wb[:, 2] < zm, wb[:, 2] >= zm):
        if m.sum() < MIN_WANDPUNKTE // 2: baender.append(None); continue
        gb_, sb_, tb_ = fein(A2, NA2, B2[m], c, g, sv); mm = np.zeros(len(B2), bool); mm[np.flatnonzero(m)[tb_]] = True
        baender.append((gb_, sb_, richt(mm), float(tb_.mean())))
    # Hoehe: Profile der B-Treffer und der A-Wandpunkte in ihrer Naehe
    ZB = wb[tr, 2]
    nah_a = cKDTree(Q[tr]).query(wa[:, :2])[0] < TREFFER_M if tr.any() else np.zeros(len(wa), bool); ZA = wa[nah_a, 2]
    dz, z_ok, z_g = z_versatz(ZA, ZB, lg)
    pr.update(dreh_grad=round(g, 3), schieb_m=[round(float(x), 3) for x in sv], treffer=round(float(tr.mean()), 3), richtungen=[round(float(ra), 3), round(float(rb_), 3)],
              wandabstand_median_m=dict(gps=round(d_vor, 3), nach=round(d_nach, 3)), hoehe=dict(dz_m=round(dz, 2), eindeutig=z_ok, guete=round(z_g, 3), n_a=int(len(ZA)), n_b=int(len(ZB))),
              baender=[None if b is None else dict(dreh_grad=round(b[0], 3), schieb_m=[round(float(x), 3) for x in b[1]], richtungen=[round(float(x), 3) for x in b[2]], treffer=round(b[3], 3)) for b in baender])
    # Gesamtmatrix B -> A: L^-1 * P * L * Mk * Mg, P = Drehung um c (Lot) + Verschiebung + dz im lokalen System
    P = np.eye(4); P[:2, :2] = r2(g); P[:2, 3] = c + sv - r2(g) @ c
    M = np.linalg.inv(L) @ P @ L @ Mk @ Mg
    # HOEHE bleibt am Fusspunkt die der GPS-Lage (s. Kippung). Das Hoehenprofil der gemeinsamen Waende (Fenster, Gesimse, Traufe) ist nur Bericht: 1122w war es nicht
    # eindeutig (-3,0 m bei Guete 0,26), die Seitenansicht zeigte dagegen Traufe/Helm deckungsgleich.
    pr["hoehe"]["nur_bericht"] = True
    k = korridor(M, G, ua, ref_b)
    # Lage der B-Kameras nur WAAGERECHT gegen das GPS (Handy-GPS traegt keine Hoehe; die Kippung aus den Waenden hebt/senkt ferne Kameras, 1122w: 17,5 m 3D bei 10 Grad)
    dX = anwenden(M, ref_b) - anwenden(Mg, ref_b); dX = dX - np.outer(dX @ ua, ua); k["lage_3d_m"] = k["lage_m"]; k["lage_m"] = round(float(np.median(np.linalg.norm(dX, axis=1))) * mj, 3)
    k["gruende"] = [x for x in k["gruende"] if not x.startswith("Lage der B-Kameras")] + ([f"Lage der B-Kameras waagerecht {k['lage_m']:.1f} m neben GPS (Grenze {k['lage_grenze_m']:.1f} m)"] if k["lage_m"] > k["lage_grenze_m"] else [])
    erg["korridor"] = k
    gr = []
    if s["rand"]: gr.append(f"Bestwert am Kastenrand der Suche (Drehung {s['dreh']:+.2f} Grad, Verschiebung {np.hypot(*s['schieb']):.2f} m, Grenzen {gd} Grad / {lg} m)")
    if s["zweit"] > ZWEIT_ANTEIL * s["wert"]: gr.append(f"mehrdeutig: zweite Lage {s['zweit_abstand']:.1f} m daneben erreicht {100 * s['zweit'] / max(s['wert'], 1e-9):.0f} % des Bestwerts")
    if kipp > KIPP_GRENZE_GRAD: gr.append(f"Kippung der GPS-Lage {kipp:.1f} Grad (Wand-Lot misst nur bis {KIPP_GRENZE_GRAD:.0f})")
    kg = [x for x in k["gruende"] if not x.startswith("Kippung")]                      # Kippung kommt hier aus den Waenden, nicht vom GPS (dessen Lot = Bild-x-Achsen)
    if kg: gr.append("ausserhalb des GPS-Korridors: " + "; ".join(kg))
    if tr.mean() < MIN_TREFFER: gr.append(f"nur {100 * tr.mean():.0f} % der B-Wandpunkte auf A-Waenden (noetig {100 * MIN_TREFFER:.0f} %)")
    if min(ra, rb_) < MIN_RICHTUNG_ANTEIL: gr.append(f"nur eine Wandrichtung traegt ({100 * ra:.0f} % / {100 * rb_:.0f} %) - Lage laengs der Wand nicht bestimmt")
    if any(b is None for b in baender): gr.append("ein Hoehenband ohne genug Wandpunkte - keine zweite Probe")
    else:
        ds = np.asarray(baender[0][1]) - baender[1][1]; dd = abs(baender[0][0] - baender[1][0]); getragen = [i for i in (0, 1) if min(baender[0][2][i], baender[1][2][i]) >= MIN_RICHTUNG_ANTEIL]
        dl = float(max([abs(ds @ (u, v)[i]) for i in getragen], default=float("nan"))); pr["baender_uneinig"] = dict(lage_m=round(dl, 3), dreh_grad=round(dd, 3), richtungen_verglichen=len(getragen))
        if not getragen: gr.append("keine Wandrichtung traegt in beiden Hoehenbaendern - keine zweite Probe")
        elif dl > BAND_LAGE_M or dd > BAND_DREH_GRAD: gr.append(f"Hoehenbaender uneinig ({dl:.2f} m / {dd:.2f} Grad, Grenzen {BAND_LAGE_M} m / {BAND_DREH_GRAD} Grad)")
    if d_nach >= d_vor: gr.append(f"Wandabstand nicht kleiner ({d_vor:.2f} -> {d_nach:.2f} m)")
    # DRITTE PROBE: TURMSPITZE (Helmstange, seiten_vereinen.stange) - in der Bindung NICHT benutzt (nur Waende). Beide Wolken muessen die Spitze bis nahe derselben Hoehe
    # haben (sonst 'nicht messbar', nur Bericht: 1122w endet die A-Wolke oben duenn); dann muss sie waagerecht auf SPITZE_M (bzw. 2 % der Hoehe) uebereinanderliegen.
    lbn = anwenden(L @ M, DB); wm = c + sv; zn = lbn[np.linalg.norm(lbn[:, :2] - wm, axis=1) < 15.0, 2]
    if len(zn) > 200:
        H = float(np.percentile(zn, 99.9) - boden); sa_, sb_ = stange(la, wm, H, boden), stange(lbn, wm, H, boden)
        if sa_ is not None and sb_ is not None:
            dxy = float(np.linalg.norm(sa_[0] - sb_[0])); dh = abs(sa_[1] - sb_[1]) / max(H, 1e-9)
            messbar = bool(dh <= SPITZE_HOEHE_ANTEIL and max(sa_[3], sb_[3]) <= SPITZE_SCHLANK_M)   # flaches Dach/Traufkante (einseitig gesehen) ist keine Spitze
            pr["spitze"] = dict(a_hoehe_m=round(sa_[1], 2), b_hoehe_m=round(sb_[1], 2), streuung_m=[round(sa_[3], 2), round(sb_[3], 2)], abstand_m=round(dxy, 2), messbar=messbar)
            if messbar and dxy > max(SPITZE_M, 0.02 * H): gr.append(f"Turmspitzen {dxy:.2f} m auseinander (Grenze {max(SPITZE_M, 0.02 * H):.2f} m)")
    if bild: kontrollbild(bild, A2, B2, Q, wa, wb, tr, 0.0, pr, gr)
    if gr: erg.update(ok=False, urteil="ABGELEHNT: " + "; ".join(gr) + " - GPS-Lage bleibt"); return erg
    erg.update(ok=True, B_nach_A=M.tolist(), urteil=f"ueber gemeinsame Waende gebunden: Kippung {kipp:.1f} Grad (Wand-Lot), Drehung {g:+.2f} Grad, Verschiebung {np.hypot(*sv):.2f} m, "
               f"Hoehe am Fusspunkt nach GPS; Wandabstand {d_vor:.2f} -> {d_nach:.2f} m, Treffer {100 * tr.mean():.0f} %; gegen GPS {k['dreh_lot_grad']:+.1f} Grad, "
               f"Lage der B-Kameras {k['lage_m']:.1f} m (Grenze {k['lage_grenze_m']} m)")
    return erg


def gps_probe(bilder, modell_a, modell_b, M_neu, M_gps):
    """GEOTAGS VON B als Gegenprobe: A-Rahmen Modell -> ENU (seiten_gps_vereinen.rahmen, A hat Hunderte Geotags), B-Kameras ueber M_neu bzw. M_gps in A und weiter nach
    ENU; waagerechter Abstand zu den eigenen Geotags von B (Median, und Anteil < GRENZE_M). -> dict oder None (zu wenig GPS)."""
    import seiten_gps_vereinen as SG
    A = SG.kameras(modell_a); B = SG.kameras(modell_b); roh = SG.gps_roh(bilder, A[0] + B[0])
    if len(roh) < 2 * SG.MIN_GPS: return None
    la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()]); G = SG.enu(roh, la0, lo0); FA = SG.rahmen(*A, G)
    if "M" not in FA: return None
    k = [i for i, n in enumerate(B[0]) if n in G and np.linalg.norm(G[n]) < SG.RADIUS_M]
    if len(k) < SG.MIN_GPS // 2: return None
    Y = np.array([G[B[0][i]] for i in k]); C = B[1][k]; aus = dict(n_gps_b=len(k))
    for name, M in (("gps", M_gps), ("neu", M_neu)):
        d = np.linalg.norm(anwenden(FA["M"] @ M, C)[:, :2] - Y, axis=1); aus[name] = dict(median_m=round(float(np.median(d)), 2), anteil_unter_grenze=round(float((d < SG.GRENZE_M).mean()), 3))
    return aus


def gps_urteil(gp):
    """Ergebnis von gps_probe -> Ablehnungsgrund (str) oder '' (bestanden). Ohne Probe (keine Geotags) = Ablehnung: dann waere die Lage nur von den Waenden getragen."""
    if not gp: return "Geotags von B nicht pruefbar (keine Gegenprobe)"
    gr = []
    if gp["neu"]["median_m"] > gp["gps"]["median_m"] + GPS_MEHR_M: gr.append(f"Geotags von B im Median {gp['gps']['median_m']} -> {gp['neu']['median_m']} m (hoechstens +{GPS_MEHR_M} m)")
    if gp["neu"]["anteil_unter_grenze"] < GPS_ANTEIL_MIN: gr.append(f"nur {100 * gp['neu']['anteil_unter_grenze']:.0f} % der Geotags von B unter 12 m (noetig {100 * GPS_ANTEIL_MIN:.0f} %)")
    return "; ".join(gr)


def kontrollbild(pfad, A2, B2, Q, wa, wb, tr, dz, pr, gr):
    """Grundriss vorher (B in GPS-Lage, nur gekippt) / nachher, Ansicht der Treffer in der Hoehe. A blau, B rot."""
    import cv2
    W = 700; c = np.median(Q, 0); r = max(8.0, float(np.percentile(np.linalg.norm(Q - c, axis=1), 98)) + 3.0); sk = W / (2 * r)
    def grund(P_b, titel):
        im = np.full((W, W, 3), 255, np.uint8)
        for P, col in ((A2, (200, 120, 0)), (P_b, (0, 0, 220))):
            x = (W / 2 + (P[:, 0] - c[0]) * sk).astype(int); y = (W / 2 - (P[:, 1] - c[1]) * sk).astype(int); ok = (x >= 0) & (x < W) & (y >= 0) & (y < W)
            for dx, dy in ((0, 0), (1, 0), (0, 1)): im[np.clip(y[ok] + dy, 0, W - 1), np.clip(x[ok] + dx, 0, W - 1)] = col
        cv2.line(im, (10, W - 15), (10 + int(5 * sk), W - 15), (0, 0, 0), 2); cv2.putText(im, "5 m", (12, W - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.putText(im, titel, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1); return im
    a = grund(B2, f"VORHER GPS-Lage (gekippt), Abstand {pr['wandabstand_median_m']['gps']:.2f} m"); b = grund(Q, f"NACHHER, Abstand {pr['wandabstand_median_m']['nach']:.2f} m, Treffer {100 * pr['treffer']:.0f} %")
    im = np.hstack([a, b]); cv2.putText(im, ("GEBUNDEN" if not gr else "ABGELEHNT: " + "; ".join(gr))[:150], (8, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160) if gr else (0, 120, 0), 1)
    cv2.imwrite(pfad, im)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("dicht_a"); ap.add_argument("dicht_b"); ap.add_argument("--gps", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--modell-a"); ap.add_argument("--modell-b"); ap.add_argument("--bilder"); a = ap.parse_args(argv)
    os.makedirs(a.aus, exist_ok=True); wj = os.path.join(a.aus, "waende.json")
    def ende(erg, rc):
        erg.update(dicht_a=os.path.abspath(a.dicht_a), dicht_b=os.path.abspath(a.dicht_b), gps=os.path.abspath(a.gps)); json.dump(erg, open(wj, "w"), indent=1, ensure_ascii=False)
        print(json.dumps(erg.get("pruefung"), ensure_ascii=False)[:1500]); print(("WAENDE GEBUNDEN: " if erg.get("ok") else "WAENDE NICHT UEBERNOMMEN: ") + erg["urteil"]); return rc
    try:
        vj = json.load(open(a.gps)); G = gps_unsicherheit(vj); p_ = vj.get("pruefung") or {}
        if isinstance(G, dict): G.update(dreh_sd_ehrlich=p_.get("dreh_sd_ehrlich_grad"), mass_sd_ehrlich=p_.get("mass_sd_ehrlich_rel"))
    except Exception as ex: G = f"GPS-Ergebnis nicht lesbar ({type(ex).__name__})"
    if isinstance(G, str): return ende(dict(art="waende", ok=False, zu_wenig=True, urteil="keine GPS-Lage als Start/Veto: " + G), 2)
    if not (os.path.isfile(a.dicht_a) and os.path.isfile(a.dicht_b)): return ende(dict(art="waende", ok=False, zu_wenig=True, urteil="dichte Wolke eines Teils fehlt"), 2)
    DA = ply_lesen(a.dicht_a); DB = ply_lesen(a.dicht_b); lot0 = None; ref_b = None
    if a.modell_a and a.modell_b:
        try:
            import pycolmap
            from seiten_gps_vereinen import lot_aus_bild_achsen
            ra_, rb_ = pycolmap.Reconstruction(a.modell_a), pycolmap.Reconstruction(a.modell_b)
            lot0 = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ra_.images.values() if im.has_pose])
            ref_b = np.array([im.projection_center() for im in rb_.images.values() if im.has_pose])
        except Exception as ex: print(f"Modelle nicht lesbar ({type(ex).__name__}: {ex}) - Lot aus dem GPS-Rahmen, Bezug B-Wolke")
    if lot0 is None:                                                                   # Rueckfall: Lot = Hauptachse kleinster Streuung der A-Wolke waere unsicher -> Wand-Lot ab z-Achse von A
        lot0 = np.array([0, 0, 1.0])
    if ref_b is None: ref_b = DB[::max(1, len(DB) // 2000)]
    erg = binden(DA, DB, G, lot0, ref_b, bild=os.path.join(a.aus, "waende.jpg")); erg["bild"] = os.path.join(a.aus, "waende.jpg")
    if erg.get("ok"):
        gp = None
        if a.bilder and a.modell_a and a.modell_b and os.path.isdir(a.bilder):
            try: gp = gps_probe(a.bilder, a.modell_a, a.modell_b, np.asarray(erg["B_nach_A"]), np.asarray(erg["B_nach_A_gps"]))
            except Exception as ex: print(f"GPS-Probe nicht moeglich ({type(ex).__name__}: {ex})")
        erg["pruefung"]["gps_probe"] = gp; gpr = gps_urteil(gp)
        if gpr: erg.update(ok=False, urteil="ABGELEHNT: " + gpr + " - GPS-Lage bleibt"); erg.pop("B_nach_A", None)
        else: erg["urteil"] += f"; Geotags von B Median {gp['gps']['median_m']} -> {gp['neu']['median_m']} m"
    return ende(erg, 0 if erg["ok"] else (2 if erg.get("zu_wenig") else 3))


if __name__ == "__main__": sys.exit(main())
