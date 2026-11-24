#!/usr/bin/env python3
"""formsitz.py <objekt.json> [--fotosatz F] [--wolke P] [--stl P] [--json J] [--bild PNG] [--probe] [--rot] [--je-seite K] [--n-wolke N] [--n-modell N]
TRENNSCHARFES FORMMASS je Seite (Auftrag 24.11.2026, Messfehler: das grobe Foto-F1 von konvergenz.py lag am Schwabentor nur 0,00-0,16 ueber Zufall -
es zaehlt Kantendichte (Quaderfugen, Rauschen), nicht ob die Form sitzt; PLATEAU-Urteile darauf waren blind).

WAHL (Kandidaten b + a, nicht c; Begruendung):
  (b) TIEFENSITZ: Modell und dichte Wolke der Kette aus DERSELBEN SfM-Kamera (fester Fotosatz audit/konvergenz_fotosatz.json) als Tiefenbild rendern und je
      Pixel vergleichen. Eine Wand, die 0,35 m zu weit aussen steht, verschiebt die Tiefe auf der GANZEN Wandflaeche um 0,35 m - das Kantenmass sah davon nur
      die Umrisslinie (in tol 0,35 m = blind). Die Wolke ist dafuer der richtige Bezug: sie ist Mehrfoto-Triangulation aus denselben Kameras (KERNMETHODE:
      Wolke = Lage-Veto/Gegenprobe), und genau die LAGE der Flaechen ist es, was das Kantenmass nicht trennt. Statt pipe/dicht/stereo/depth_maps die
      fusionierte Wolke (sfm/punkte_modell_*.npy, schon im Kamerarahmen der K-Dateien): Tiefenkarten liegen im COLMAP-Rahmen der entzerrten Dichte-Bilder
      (eigene Kameras/Namen) und sind ungefiltert; die Fusion ist der Mehrbild-konsistente Teil davon.
  (a) OBERKONTUR gegen die Himmelsmaske des FOTOS (audit/himmel_cache, nur gelesen): je Bildspalte mit Modell oberste Modellzeile gegen oberste
      Nicht-Himmel-Zeile. Unabhaengig von der Wolke (falls die Wolke selbst falsch liegt) und empfindlich fuer Hoehe und seitlichen Versatz von Dach/Turm,
      wo der Tiefensitz (frontaler Blick) wenig sieht. Unten grenzt das Bauwerk an Nachbarhaeuser, deshalb NUR die Oberkontur, keine volle Silhouetten-IoU.
  (c) gerichtete Kantenpassung NICHT: braucht wieder Fotokanten-Detektion (dieselbe Dichte-Falle), und Traufe/Gesimse liegen in (a) und (b) schon drin.

MESSUNG je Foto (CPU, kein torch): Bildgroesse so, dass ein Pixel am Modell PIX_M 8 cm misst (Mediantiefe/f; feiner als die 0,3-m-Nullprobe und tol,
  grob genug fuer >= K_STUETZ Wolkenpunkte je Pixel). Modell = End-STL flaechengewichtet abgetastet (N_MODELL Punkte, Saat 0), Wolke = Zuschnitt auf
  Modellhuelle + RAND_M, ohne Bodenschicht (BODEN_M ueber Modellfuss), Unterstichprobe N_WOLKE. Beide GLEICH gerendert: Tiefe je Pixel = vorderste Tiefe d,
  hinter der innerhalb BAND_M mindestens K_STUETZ Punkte liegen (Einzelpunkte/Geisterwolke vorn zaehlen nicht; Rueckseite faellt weg), eine 3x3-Fuellung.
  Projektion mit k1 (SIMPLE_RADIAL wie die K-Datei), damit die Himmelsmaske des unentzerrten Fotos passt.
  tiefe   = |beide da UND |dz| < TOL_M| / |Modell ODER Wolke da|   (Tiefen-IoU: bestraft falsche Lage UND Fehlendes/Erfundenes)
            + Bericht med_dz (Median |dz| wo beide da), a10/a25 (Anteil |dz| < 10/25 cm), deckung (Anteil Modellpixel mit Wolke)
  kontur  = Anteil der Modellspalten (Oberkante nicht am Bildrand), deren Oberkante innerhalb TOL_M (in Metern an der Modelltiefe) der Fotooberkante liegt
  formsitz = Mittel der vorhandenen Teile (Maske fehlt/unplausibel -> nur tiefe).
NULLPROBE (Pflicht, je Lauf): dasselbe fuer das Modell um NULL_M 1,3 / 2,1 m in +-x/+-y verschoben (wie konvergenz_wolke; > 3 x tol, zwei Weiten gegen
  Fenster-Raster) -> formsitz_null = Median; guete = (formsitz - null) / (1 - null) (Kappa-artig: 0 = Zufall, 1 = perfekt).
  TRENNT je Seite, wenn guete (Median der Fotos) >= GUETE_MIN 0,2 (Kappa-Skala: < 0,2 "kaum Uebereinstimmung"; das alte grobe F1 lag bei 0,00-0,16) und
  >= N_MIN 3 Fotos. konvergenz.py urteilt (steigt/PLATEAU/faellt) nur fuer Seiten, die trennen; sonst "nicht trennbar (Zufallsniveau)".
--probe: Empfindlichkeit je Seite fuer Verschiebung 0,3/1/2 m in +-x/+-y/+-z und Drehung +-2/5 Grad um die Hochachse (Modellmitte).
--rot:   ROT-PROBE je Seite: die Fassadenflaechen DIESER Seite (Normale innerhalb 30 Grad der Aussennormale) um ROT_M 0,35 m nach aussen (der Fehler
         "Koerperwand auf LoD2- statt Fotokanten-Ebene" 24.11.) -> formsitz dieser Seite muss um >= ROT_MARGE fallen.
Ausgabe: JSON (Standard <audit>/formsitz.json) {seiten: {achse: dict(name, formsitz, formsitz_null, guete, trennt, tiefe, kontur, med_dz, a10, a25, n,
  fotos)}, probe?, rot?}, Text, --bild: Kontrollbild je Seite (Foto | Tiefenvergleich: gruen sitzt, rot Modell davor, blau Modell dahinter,
  gelb nur Modell, grau nur Wolke; weisse Linie Fotooberkante, magenta Modelloberkante).
Exit 0 = gerechnet, 1 = Aufruf/Daten falsch, 3 = keine Seite mit Beleg.
Umgebung: /media/oem/scan/venv-seg/bin/python -I tools/formsitz.py ... (numpy, cv2; KEINE GPU noetig). RAM ~1 GB (6 M Wolke + 4 M Modellpunkte).
"""
import sys, os, json, glob, math, time, argparse
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
PIX_M = 0.08; TOL_M = 0.25; K_STUETZ = 3; BAND_M = 0.3; RAND_M = 2.0; BODEN_M = 0.3; N_WOLKE = 6_000_000; N_MODELL = 4_000_000; LANG_MAX = 1600; LANG_MIN = 160
NULL_M = (1.3, 2.1); TRENN_MIN = 0.25; N_MIN = 3; ROT_M = 0.35; ROT_MARGE = 0.05; ROT_COS = math.cos(math.radians(30))
PROBE_M = (0.3, 1.0, 2.0); PROBE_GRAD = (2.0, 5.0)
TRENNT_NICHT = "nicht trennbar (Zufallsniveau)"
ACHSEN = {"+x": (1.0, 0.0), "-x": (-1.0, 0.0), "+y": (0.0, 1.0), "-y": (0.0, -1.0)}


# ---------------------------------------------------------------- Laden
def stl_dreiecke(pfad):
    """Binaeres STL -> (F, 3, 3) float32 in STL-Einheiten (ohne trimesh, RAM); ASCII ueber trimesh."""
    import struct
    with open(pfad, "rb") as fh: kopf = fh.read(84)
    n = struct.unpack("<I", kopf[80:84])[0] if len(kopf) >= 84 else 0
    if n and os.path.getsize(pfad) == 84 + 50 * n:
        A = np.fromfile(pfad, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
        return np.ascontiguousarray(A["v"])
    import trimesh
    return np.asarray(trimesh.load(pfad, force="mesh").triangles, np.float32)


def modell_kamerarahmen(T, obj, kk):
    """Dreiecke (STL-Einheit) -> Meter im Kamerarahmen, GENAU wie foto_diff._netz_raster (Massstab, Zentrierung, rahmen_verschiebung der K-Datei)."""
    T = T * np.float32(obj.get("stl_massstab", 87) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0)
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    c = (lo + hi) / 2 if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    tr = np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in (kk or {}) else [-c[0], -c[1], -lo[2]], np.float32)
    return T + tr


def abtasten(T, n, saat=0):
    """Flaechengewichtete Oberflaechenpunkte (n, 3) float32 + Flaechennormale je Punkt (n, 3) float32."""
    a, b = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]; cr = np.cross(a, b); fl = np.linalg.norm(cr, axis=1)
    ok = fl > 1e-12
    if not ok.any(): return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    rng = np.random.default_rng(saat); p = fl / fl.sum(); fi = rng.choice(len(T), n, p=p)
    r1, r2 = rng.random(n, dtype=np.float32), rng.random(n, dtype=np.float32); s = np.sqrt(r1)
    P = (T[fi, 0] * (1 - s)[:, None] + T[fi, 1] * (s * (1 - r2))[:, None] + T[fi, 2] * (s * r2)[:, None]).astype(np.float32)
    N = (cr[fi] / np.maximum(fl[fi], 1e-12)[:, None]).astype(np.float32)
    return P, N


# ---------------------------------------------------------------- Kamera / Render
def kamera(K):
    """K-Datei -> dict(R, t, C, f, cx, cy, W, H, k1)."""
    import konvergenz as KV
    k = K.get("kamera") or K; c = KV.kamera(K); c["k1"] = float(k.get("k1") or 0.0); return c


def skaliert(cam, dmed, pix_m=PIX_M):
    """Kamera so verkleinern, dass ein Pixel an der Mediantiefe pix_m misst (lange Seite LANG_MIN..LANG_MAX)."""
    s = (dmed / pix_m) / cam["f"]; lang = max(cam["W"], cam["H"]); s = min(max(s, LANG_MIN / lang), LANG_MAX / lang)
    W, H = max(8, int(round(cam["W"] * s))), max(8, int(round(cam["H"] * s)))
    return dict(cam, f=cam["f"] * s, cx=cam["cx"] * s, cy=cam["cy"] * s, W=W, H=H, s=s)


def projizieren(cam, P):
    """Punkte -> (u, v, z) mit radialer Verzeichnung k1 (normierte Koordinaten, wie COLMAP SIMPLE_RADIAL)."""
    Xc = P @ cam["R"].T.astype(np.float32) + cam["t"].astype(np.float32); z = Xc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        x, y = Xc[:, 0] / z, Xc[:, 1] / z
        if cam.get("k1"): q = 1 + cam["k1"] * (x * x + y * y); x, y = x * q, y * q
    return cam["f"] * x + cam["cx"], cam["f"] * y + cam["cy"], z


def nach_tiefe(P, cam):
    """Punkte nach Kameratiefe sortiert. Eine VERSCHIEBUNG aendert alle Tiefen um denselben Betrag -> Reihenfolge bleibt; Null-/Probeverschiebungen
    brauchen dann kein neues Sortieren (tiefe_vorn(..., sortiert=True))."""
    z = P @ cam["R"][2].astype(np.float32) + np.float32(cam["t"][2]); return P[np.argsort(z, kind="stable")]


def tiefe_vorn(P, cam, k=K_STUETZ, band=BAND_M, sortiert=False, runden=4):
    """Robuste vorderste Tiefe je Pixel (H, W) float32, inf = leer: vorderste Tiefe d, hinter der innerhalb band mindestens k Punkte des Pixels liegen
    (sonst den vordersten Punkt verwerfen und erneut, hoechstens runden Mal; Einzelpunkte/Geisterwolke vorn zaehlen nicht); dann eine 3x3-Fuellung.
    Ohne Sortieren je Variante: P nach Tiefe sortiert (nach_tiefe), Minimum = erster Schreibzugriff in umgekehrter Reihenfolge."""
    import cv2
    if not sortiert: P = nach_tiefe(P, cam)
    W, H = int(cam["W"]), int(cam["H"]); u, v, z = projizieren(cam, P)
    ok = (z > 1.0) & (u >= -0.5) & (u < W - 0.5) & (v >= -0.5) & (v < H - 0.5)
    pix = (np.rint(v[ok]).astype(np.int64) * W + np.rint(u[ok]).astype(np.int64)); z = z[ok].astype(np.float32); del u, v, ok
    D = np.full(H * W, np.inf, np.float32); n = H * W
    for _ in range(runden):
        if not len(pix): break
        D[:] = np.inf; D[pix[::-1]] = z[::-1]                                     # sortiert -> der vorderste Punkt schreibt zuletzt
        if k <= 1: break
        cnt = np.bincount(pix, weights=(z - D[pix] < band), minlength=n); schlecht = (cnt < k) & np.isfinite(D)
        if not schlecht.any(): break
        weg = schlecht[pix] & (z <= D[pix]); pix, z = pix[~weg], z[~weg]
    else:
        if k > 1 and len(pix): D[schlecht] = np.inf
    D = D.reshape(H, W)
    leer = ~np.isfinite(D)
    if leer.any():
        Df = cv2.erode(np.where(leer, np.float32(1e9), D), np.ones((3, 3), np.uint8)); fu = leer & (Df < 1e8); D[fu] = Df[fu]
    return D


def himmel_laden(od, nr, cam):
    """Gecachte Himmelsmaske (audit/himmel_cache/umriss_<foto>.png, foto_pick.himmel_cached) -> bool (H, W) in Renderaufloesung oder None (fehlt/unplausibel)."""
    import cv2
    for p in (os.path.join(od, "audit", "himmel_cache", f"umriss_{nr}.png"), os.path.join(od, "himmelsmaske", f"{nr}.png")):
        if not os.path.exists(p): continue
        m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if m is None: continue
        sk = cv2.resize((m > 127).astype(np.float32), (int(cam["W"]), int(cam["H"])), interpolation=cv2.INTER_AREA) > 0.5
        try:
            import foto_pick as FP
            if not FP.plausibel(sk)[0]: return None
        except Exception: pass
        return sk
    return None


def oberkanten(maske):
    """Oberste True-Zeile je Spalte (H, wenn leer)."""
    H = maske.shape[0]; a = maske.argmax(0); a[~maske.any(0)] = H; return a


def im_blick(P, cam, rand=0.3):
    """Index der Punkte, die (mit rand x Bildgroesse Zugabe fuer Null-/Probeverschiebungen) im Bild und vor der Kamera liegen - einmal je Foto statt je Variante."""
    u, v, z = projizieren(cam, P); W, H = cam["W"], cam["H"]
    return np.nonzero((z > 1.0) & (u >= -rand * W) & (u < (1 + rand) * W) & (v >= -rand * H) & (v < (1 + rand) * H))[0]


def vergleich(Dm, Dw, himmel, cam, tol=TOL_M):
    """Tiefen-IoU + Kennzahlen + Oberkontur fuer ein Modell-Tiefenbild gegen Wolken-Tiefenbild/Himmelsmaske. formsitz = tiefe (Tiefen-IoU); die
    Oberkontur wird nur BERICHTET (kontur): an 3 von 4 Probefotos war die Turmspitze vom Bildrand abgeschnitten oder von Baeumen verdeckt (kontur 0,00-0,21
    fuer Modell UND verschobenes Modell) - sie verduennte das Mass, statt zu trennen (Probe 1122 24.11.)."""
    m, w = np.isfinite(Dm), np.isfinite(Dw); beide = m & w; ver = m | w
    if ver.sum() < 50 or m.sum() < 50: return None
    dz = (Dm - Dw)[beide]; ad = np.abs(dz)
    e = dict(tiefe=float((ad < tol).sum() / ver.sum()), med_dz=float(np.median(ad)) if len(ad) else None,
             a10=float((ad < 0.10).mean()) if len(ad) else None, a25=float((ad < 0.25).mean()) if len(ad) else None,
             deckung=float(beide.sum() / m.sum()), px=int(ver.sum()))
    if himmel is not None:
        tm, tf = oberkanten(m), oberkanten(~himmel); sp = np.nonzero((tm >= 2) & (tm < m.shape[0]))[0]
        if len(sp) >= 10:
            dm = Dm[tm[sp], sp]; fehl = np.abs(tf[sp] - tm[sp]) * dm / cam["f"]
            e["kontur"] = float((fehl < tol).mean()); e["kontur_med_m"] = float(np.median(fehl))
    e["formsitz"] = e["tiefe"]
    return e


def guete(s, s0):
    if s is None or s0 is None: return None
    return (s - s0) / max(1e-6, 1.0 - s0)


# ---------------------------------------------------------------- Varianten
def null_varianten(weiten=NULL_M):
    """Zufallsniveau: je Weite zwei Gegenrichtungen, die Weiten im Wechsel auf x und y (1,3 m +-x, 2,1 m +-y; > 3 x tol, zwei Weiten gegen Fenster-Raster)."""
    out = []
    for i, s in enumerate(weiten):
        d = np.zeros(3, np.float32); d[i % 2] = s; out += [tuple(d), tuple(-d)]
    return out


def verschoben(P, d):
    return P + np.asarray(d, np.float32)


def gedreht(P, grad, mitte):
    c, s = math.cos(math.radians(grad)), math.sin(math.radians(grad)); R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
    m = np.asarray(mitte, np.float32); return (P - m) @ R.T + m


def wand_raus(P, N, ax, weite=ROT_M, cos_min=ROT_COS):
    """ROT-PROBE: Punkte der nach ax weisenden Fassadenflaechen (|Normale| innerhalb 30 Grad der Aussennormale, Vorzeichen egal: STL-Orientierung) und auf
    der ax-Seite des Modells um weite nach aussen schieben."""
    n = np.array(list(ACHSEN[ax]) + [0.0], np.float32); i = 0 if n[0] else 1; sg = n[i]
    mitte = 0.5 * (P[:, i].min() + P[:, i].max()); sel = (np.abs(N @ n) >= cos_min) & ((P[:, i] - mitte) * sg > 0)
    Q = P.copy(); Q[sel] += weite * n; return Q, int(sel.sum())


# ---------------------------------------------------------------- Ablauf
def fotosatz_laden(a, obj, od, root):
    import konvergenz as KV
    sp = a.fotosatz or os.path.join(root, obj.get("audit") or os.path.relpath(os.path.join(od, "audit"), root), "konvergenz_fotosatz.json")
    if os.path.exists(sp): return json.load(open(sp)), sp
    fotos_dir = os.path.join(root, obj.get("fotos_dir", "")); W_ = KV.waende(obj, None); kand = KV.kandidaten(od, obj, W_, fotos_dir)
    S = KV.fotosatz_anlegen(kand, W_, KV.K_STD, fotos_dir, "formsitz_probe"); print(f"HINWEIS: kein Fotosatz - nach konvergenz-Regel angelegt (nicht gespeichert)")
    return S, None


def seiten_auswerten(S, je, trenn_min=TRENN_MIN, n_min=N_MIN):
    out = {}
    med = lambda v: None if not v else round(float(np.median(v)), 4)
    for ax, s in S["seiten"].items():
        fv = {nr: je[nr] for nr in s["fotos"] if nr in je and je[nr].get("formsitz") is not None}
        g = [e["guete"] for e in fv.values() if e.get("guete") is not None]
        e = dict(name=s.get("name", ax), formsitz=med([q["formsitz"] for q in fv.values()]), formsitz_null=med([q["formsitz_null"] for q in fv.values() if q.get("formsitz_null") is not None]),
                 guete=med(g), tiefe=med([q["tiefe"] for q in fv.values()]), kontur=med([q["kontur"] for q in fv.values() if q.get("kontur") is not None]),
                 med_dz=med([q["med_dz"] for q in fv.values() if q.get("med_dz") is not None]), a10=med([q["a10"] for q in fv.values() if q.get("a10") is not None]),
                 a25=med([q["a25"] for q in fv.values() if q.get("a25") is not None]), deckung=med([q["deckung"] for q in fv.values()]), n=len(g),
                 kontur_null=med([q["kontur_null"] for q in fv.values() if q.get("kontur_null") is not None]),
                 decke=med([q["decke"] for q in fv.values() if q.get("decke") is not None]), decke_null=med([q["decke_null"] for q in fv.values() if q.get("decke_null") is not None]),
                 trennschaerfe=med([q["trennschaerfe"] for q in fv.values() if q.get("trennschaerfe") is not None]),
                 relativ=med([q["relativ"] for q in fv.values() if q.get("relativ") is not None]),
                 fotos={nr: q.get("formsitz") for nr, q in fv.items()})
        e["trennt"] = bool(e["n"] >= n_min and e["trennschaerfe"] is not None and e["trennschaerfe"] >= trenn_min)
        e["status"] = "trennt" if e["trennt"] else (TRENNT_NICHT if e["n"] >= n_min else "zu wenig Fotos")
        out[ax] = e
    return out


def kontrollbild(pfad, beispiele, fotos_dir):
    """Je Seite ein Feld: Foto (verkleinert) | Tiefenvergleich."""
    import cv2, konvergenz as KV
    felder = []
    for name, nr, cam, Dm, Dw, sk, e in beispiele:
        H, W = Dm.shape; fp = KV.foto_pfad(fotos_dir, nr); im = cv2.imread(fp) if fp else None
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA) if im is not None else np.full((H, W, 3), 200, np.uint8)
        V = np.full((H, W, 3), 245, np.uint8); m, w = np.isfinite(Dm), np.isfinite(Dw); b = m & w; dz = np.where(b, Dm - Dw, 0)
        V[w & ~m] = (170, 170, 170); V[m & ~w] = (60, 210, 230); V[b & (np.abs(dz) < TOL_M)] = (70, 170, 40)
        V[b & (dz <= -TOL_M)] = (40, 40, 220); V[b & (dz >= TOL_M)] = (200, 110, 30)
        if sk is not None:
            tf = oberkanten(~sk); tm = oberkanten(m)
            for c in range(W):
                if tf[c] < H: V[tf[c], c] = (255, 255, 255); im[tf[c], c] = (255, 255, 255)
                if 0 < tm[c] < H: V[tm[c], c] = (220, 40, 220); im[tm[c], c] = (220, 40, 220)
        F = np.hstack([im, V]); s = 360.0 / H; F = cv2.resize(F, (int(F.shape[1] * s), 360), interpolation=cv2.INTER_AREA)
        txt = f"{name} {nr[:28]}: formsitz {e['formsitz']:.2f} (Zufall {e.get('formsitz_null', 0) or 0:.2f}) tiefe {e['tiefe']:.2f} kontur {e.get('kontur', float('nan')):.2f} med|dz| {e['med_dz'] or 0:.2f} m"
        F = np.vstack([np.full((24, F.shape[1], 3), 255, np.uint8), F]); cv2.putText(F, txt[:110], (6, 17), 0, 0.42, (20, 20, 20), 1, cv2.LINE_AA); felder.append(F)
    if not felder: return
    bw = max(f.shape[1] for f in felder); felder = [np.hstack([f, np.full((f.shape[0], bw - f.shape[1], 3), 255, np.uint8)]) for f in felder]
    leg = np.full((22, bw, 3), 255, np.uint8)
    cv2.putText(leg, "gruen sitzt (<25 cm) | rot Modell davor | blau Modell dahinter | gelb nur Modell | grau nur Wolke | weiss Foto-, magenta Modelloberkante", (6, 15), 0, 0.4, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, np.vstack(felder + [leg]))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotosatz"); ap.add_argument("--wolke"); ap.add_argument("--stl"); ap.add_argument("--json")
    ap.add_argument("--bild"); ap.add_argument("--probe", action="store_true"); ap.add_argument("--rot", action="store_true"); ap.add_argument("--je-seite", type=int, default=0)
    ap.add_argument("--n-wolke", type=int, default=N_WOLKE); ap.add_argument("--n-modell", type=int, default=N_MODELL); a = ap.parse_args(argv)
    import konvergenz as KV, konvergenz_wolke as KW
    t_start = time.time()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    audit = os.path.join(root, obj.get("audit") or os.path.relpath(os.path.join(od, "audit"), root)); fotos_dir = os.path.join(root, obj.get("fotos_dir", ""))
    S, sp = fotosatz_laden(a, obj, od, root)
    if a.je_seite: S = dict(S, seiten={ax: dict(s, fotos=s["fotos"][:a.je_seite]) for ax, s in S["seiten"].items()})
    fotos = sorted({nr for s in S["seiten"].values() for nr in s["fotos"]})
    if not fotos: print("FEHLER: Fotosatz leer"); return 1
    stl = a.stl or os.path.join(root, obj.get("stl") or "-")
    if not os.path.exists(stl): print(f"FEHLER: STL fehlt ({stl})"); return 1
    wp = KW.wolke_pfad(obj, od, a.wolke)
    if not wp or not os.path.exists(wp): print(f"FEHLER: keine dichte Wolke ({wp})"); return 1
    cams = {}
    for nr in fotos:
        kp = os.path.join(od, "messprotokoll", f"K-{nr}.json")
        try: K = json.load(open(kp)); cams[nr] = (kamera(K), K.get("kamera") or {})
        except Exception as ex: print(f"  {nr}: K-Datei fehlt/unlesbar ({type(ex).__name__})")
    if not cams: print("FEHLER: keine Kamera des Fotosatzes lesbar"); return 1
    kk = next(iter(cams.values()))[1]
    T = modell_kamerarahmen(stl_dreiecke(stl), obj, kk); lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    PM, NM = abtasten(T, a.n_modell); del T
    box_lo, box_hi = lo.astype(float) - RAND_M, hi.astype(float) + RAND_M; box_lo[2] = lo[2] + BODEN_M
    PW, info = KW.wolke_laden(wp, (box_lo, box_hi), a.n_wolke, boden_m=0.0); info.update(box=[np.round(box_lo, 2).tolist(), np.round(box_hi, 2).tolist()])
    if len(PW) < 1000: print(f"FEHLER: Wolke im Modellbereich fast leer ({info})"); return 1
    mitte = ((lo + hi) / 2).astype(np.float32)
    print(f"FORMSITZ: Modell {len(PM)} Punkte, Wolke {info['n_box']} im Bereich -> {len(PW)} genutzt ({time.time() - t_start:.0f} s geladen)", flush=True)
    nullv = null_varianten(); halb = np.random.default_rng(1).random(len(PW)) < 0.5
    probe_v = {}
    if a.probe:
        for d in PROBE_M:
            for i, nm in enumerate("xyz"):
                for sg in (1, -1): probe_v[f"{'+' if sg > 0 else '-'}{nm} {d:g} m"] = ("v", tuple(sg * d if j == i else 0.0 for j in range(3)))
        for g in PROBE_GRAD:
            for sg in (1, -1): probe_v[f"dreh {sg * g:+g} Grad"] = ("d", sg * g)
    rot_P = {}
    if a.rot:
        for ax in S["seiten"]: rot_P[ax] = wand_raus(PM, NM, ax)
    je, beispiele, probe_je, rot_je = {}, {}, {}, {}
    for nr, (cam0, _) in cams.items():
        t0 = time.time()
        try:
            u, v, z = projizieren(cam0, PM[::50]); im = (z > 1) & (u >= 0) & (u < cam0["W"]) & (v >= 0) & (v < cam0["H"])
            if im.sum() < 100: je[nr] = dict(fehler="Modell nicht im Bild"); continue
            cam = skaliert(cam0, float(np.median(z[im])))
            iw = im_blick(PW, cam); PWi = PW[iw]; hA, hB = nach_tiefe(PWi[halb[iw]], cam), PWi[~halb[iw]]; del iw
            im_ = im_blick(PM, cam); PMi = nach_tiefe(PM[im_], cam)
            Dw = tiefe_vorn(PWi, cam); sk = himmel_laden(od, nr, cam); Dm = tiefe_vorn(PMi, cam, sortiert=True)
            e = vergleich(Dm, Dw, sk, cam)
            if e is None: je[nr] = dict(fehler="zu wenig Pixel"); continue
            nulls = [vergleich(tiefe_vorn(verschoben(PMi, d), cam, sortiert=True), Dw, sk, cam) for d in nullv]
            s0 = [q["formsitz"] for q in nulls if q]; e["formsitz_null"] = float(np.median(s0)) if s0 else None
            k0 = [q["kontur"] for q in nulls if q and q.get("kontur") is not None]; e["kontur_null"] = float(np.median(k0)) if k0 and "kontur" in e else None
            # DECKE (Trennschaerfe der Daten, unabhaengig vom Modell): Wolkenhaelfte A als "perfektes Modell" gegen Haelfte B, und A verschoben
            DB = tiefe_vorn(hB, cam); dA = vergleich(tiefe_vorn(hA, cam, sortiert=True), DB, None, cam)
            dN = [vergleich(tiefe_vorn(verschoben(hA, d), cam, sortiert=True), DB, None, cam) for d in nullv]; dN = [q["formsitz"] for q in dN if q]
            e["decke"] = dA["formsitz"] if dA else None; e["decke_null"] = float(np.median(dN)) if dN else None
            e["trennschaerfe"] = (e["decke"] - e["decke_null"]) if e["decke"] is not None and e["decke_null"] is not None else None
            e["guete"] = guete(e["formsitz"], e["formsitz_null"]); e["bild_px"] = [int(cam["W"]), int(cam["H"])]; e["himmel"] = sk is not None
            e["relativ"] = (e["formsitz"] - e["formsitz_null"]) / e["trennschaerfe"] if e["trennschaerfe"] and e["trennschaerfe"] > 0.02 and e["formsitz_null"] is not None else None
            for k_, (art, p) in probe_v.items():
                Q = verschoben(PMi, p) if art == "v" else gedreht(PMi, p, mitte); q = vergleich(tiefe_vorn(Q, cam, sortiert=art == "v"), Dw, sk, cam)
                probe_je.setdefault(nr, {})[k_] = None if q is None else round(q["formsitz"], 4)
            for ax, (Q, _) in rot_P.items():
                q = vergleich(tiefe_vorn(Q[im_], cam), Dw, sk, cam); rot_je.setdefault(nr, {})[ax] = None if q is None else round(q["formsitz"], 4)
            e["sek"] = round(time.time() - t0, 1); je[nr] = {k_: (round(x, 4) if isinstance(x, float) else x) for k_, x in e.items()}
            ax_f = next((ax for ax, s in S["seiten"].items() if nr in s["fotos"]), None)
            if a.bild and ax_f and (ax_f not in beispiele or e["px"] > beispiele[ax_f][6]["px"]):
                beispiele[ax_f] = (S["seiten"][ax_f].get("name", ax_f), nr, cam, Dm, Dw, sk, e)
            print(f"  {nr[:44]}: formsitz {e['formsitz']:.3f} (Zufall {e['formsitz_null']:.3f}, guete {e['guete']:.2f}; Decke {e['decke'] and round(e['decke'], 3)} Zufall {e['decke_null'] and round(e['decke_null'], 3)}) kontur {e.get('kontur', float('nan')):.3f}"
                  f" med|dz| {e['med_dz']:.2f} m a25 {e['a25']:.2f} [{cam['W']}x{cam['H']}, {e['sek']} s]", flush=True)
        except Exception as ex:
            je[nr] = dict(fehler=f"{type(ex).__name__}: {str(ex)[:160]}"); print(f"  {nr}: FEHLER {je[nr]['fehler']}")
    seiten = seiten_auswerten(S, je)
    erg = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), fotosatz=sp and os.path.abspath(sp), stl=os.path.abspath(stl), wolke=info, sek=round(time.time() - t_start, 1),
               schwellen=dict(pix_m=PIX_M, tol_m=TOL_M, k_stuetz=K_STUETZ, band_m=BAND_M, null_m=list(NULL_M), trenn_min=TRENN_MIN, n_min=N_MIN), seiten=seiten, fotos=je)
    if probe_je:
        erg["probe"] = {}
        for ax, s in S["seiten"].items():
            fo = [nr for nr in s["fotos"] if nr in probe_je and je.get(nr, {}).get("formsitz") is not None]
            if not fo: continue
            erg["probe"][ax] = {k_: round(float(np.median([je[nr]["formsitz"] - probe_je[nr][k_] for nr in fo if probe_je[nr].get(k_) is not None])), 4) for k_ in probe_v}
    if rot_je:
        erg["rot"] = {}
        for ax, s in S["seiten"].items():
            fo = [nr for nr in s["fotos"] if nr in rot_je and je.get(nr, {}).get("formsitz") is not None]
            if not fo: continue
            abf = {ax2: round(float(np.median([je[nr]["formsitz"] - rot_je[nr][ax2] for nr in fo if rot_je[nr].get(ax2) is not None])), 4) for ax2 in rot_P}
            erg["rot"][ax] = dict(abfall_je_verschobener_wand=abf, eigene=abf.get(ax), erkannt=bool((abf.get(ax) or 0) >= ROT_MARGE), punkte=rot_P[ax][1])
    jp = a.json or os.path.join(audit, "formsitz.json"); os.makedirs(os.path.dirname(os.path.abspath(jp)), exist_ok=True)
    json.dump(erg, open(jp + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(jp + ".tmp", jp)
    if a.bild and beispiele:
        try: kontrollbild(a.bild, [beispiele[ax] for ax in S["seiten"] if ax in beispiele], fotos_dir)
        except Exception as ex: print(f"HINWEIS: Kontrollbild nicht geschrieben ({type(ex).__name__}: {ex})")
    print(f"FORMSITZ je Seite (Tiefen-IoU gegen dichte Wolke + Oberkontur gegen Himmelsmaske; Zufall = Modell {'/'.join(f'{m:g}' for m in NULL_M)} m verschoben):")
    for ax, e in seiten.items():
        f = lambda x, n=3: "-" if x is None else f"{x:.{n}f}"
        print(f"  {e['name']}: formsitz {f(e['formsitz'])} Zufall {f(e['formsitz_null'])} guete {f(e['guete'], 2)} | Decke (Wolke/Wolke) {f(e['decke'])} Zufall {f(e['decke_null'])}"
              f" Trennschaerfe {f(e['trennschaerfe'])} relativ {f(e['relativ'], 2)} | tiefe {f(e['tiefe'])} kontur {f(e['kontur'])} med|dz| {f(e['med_dz'], 2)} m a10 {f(e['a10'], 2)} a25 {f(e['a25'], 2)} (n {e['n']}) -> {e['status']}")
        if ax in (erg.get("rot") or {}): r = erg["rot"][ax]; print(f"      ROT-Probe Wand {ROT_M} m aussen: Abfall {r['eigene']} -> {'erkannt' if r['erkannt'] else 'NICHT erkannt'} (andere Seiten: {r['abfall_je_verschobener_wand']})")
        if ax in (erg.get("probe") or {}): print("      Probe Abfall: " + ", ".join(f"{k_} {v_:+.3f}" for k_, v_ in erg["probe"][ax].items()))
    print(f"Bericht: {jp} ({erg['sek']} s)")
    return 0 if any(e["n"] for e in seiten.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
