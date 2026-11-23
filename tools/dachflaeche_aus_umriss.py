#!/usr/bin/env python3
"""dachflaeche_aus_umriss.py - FORM DER HAUPTDACHFLAECHE (gerade / geschweift / gewoelbt) und FUSSPUNKT DES AUFSATZES aus den Foto-Silhouetten, 21.11.2026.

Anlass (Koordinator, Kontrollbild IMG_20261106_113056 Schwabentor): im Foto ist das Zeltdach eine GERADE Pyramide mit geraden Graten von der Traufkante bis
zum kleinen Aufsatz; das Kettenmodell (Wolkenscheiben + DOM1-Veto) ist glockig/konkav mit 0,5-m-Stufen und einem breiten Absatz unter dem Aufsatz.
KERNMETHODE: Form aus Fotos, Wolke/DOM1 nur Veto. Vorbild tools/vordach_profil.py (Profilfamilie g(s, c)) und tools/spitze_aus_umriss.py (Himmelskante an der Achse).

 1. Achse aus dach_profil.json (spitze_foto.achse bzw. o + achse_uv). Traufe z_t = Aussenkante aus 'traufe_foto' (Median der gueltigen Seiten), sonst z0.
 2. Je kalibriertem Foto mit Himmelsmaske (Cache audit/himmel_cache, keine neue Segmentierung) in mind. ABSTAND_MIN m: an jeder Hoehe z die Zeile durch den
    Achsenpunkt quer zur Blickrichtung nach links und rechts bis zum Himmel (beide Seiten, sonst Nachbar/Bildrand) -> sichtbare Halbbreite h(z) in m an der Achse.
 3. FUSS DES AUFSATZES je Foto: unterste Hoehe ueber z_t + 2 m, ab der h(z) ueber 0,4 m nicht mehr mit der Dachneigung abnimmt (Steigung < KNICK x Dachsteigung):
    dort endet die Dachflaeche, darueber steht der Aufsatz. Median ueber die Fotos.
 4. FORM je Foto zwischen z_t und Fuss: h(s) = h_t - (h_t - h_f) * g^-1(s; c), s = (z - z_t)/(z_f - z_t), g wie vordach_profil (c = 0 gerade, c > 0 geschweift =
    flach an der Traufe/steil oben = glockig, c < 0 gewoelbt). h_t, h_f je c per Ausgleich, c = kleinster Fehler. Familie gilt, wenn >= MIN_FOTOS Fotos sie
    waehlen und sie die Mehrheit hat (Formfamilie aus >= 3 Fotos).
 5. Fussquerschnitt: spitze_aus_umriss.querschnitt aus h_f je Blickrichtung (eckig/rund, Lage, Halbseite).
 6. DOM1-VETO (23.11.2026, war bis dahin nur angekuendigt): Laser-Isolinien je 0,1 m Hoehe (Regeln wie dach_profil_wolke.dom1_veto, Klippe an der Traufe) in den
    Block 'dom1_veto'; bauteile.flaeche_aus_foto setzt jede Ringseite, die > 0,3 m ausserhalb steht, auf die Isolinie (Traufring bleibt). Schwabentor-1122p ohne Veto:
    HOEHEN-TOR +1,73 m (Foto-Ebene ab der Ueberstand-Aussenkante 6,77 m statt Aufschiebling + 56-Grad-Flaeche wie im Laser).
Ausgabe: Block 'flaeche_foto' in audit/dach_profil.json {gueltig, familie, c, z_traufe, z_fuss, fuss {form, theta, halb}, fotos, stimmen, je_foto, grund}
-> bauteile.dach_aus_profil baut bei 'gerade' die Dachflaeche als Ebenen von der Foto-Traufe bis zum Fuss (statt Wolkenscheiben), darueber Aufsatz aus spitze_foto.
Bild audit/dachflaeche_umriss.jpg. Aufruf: dachflaeche_aus_umriss.py <objekt.json> [--profil P] [--aus A] [--bild B] [--max-fotos 300] [--nur-messen] [--root R]
rc 0 gueltig, rc 3 kein Profil, rc 4 keine Formfamilie.
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

ABSTAND_MIN = 20.0     # Silhouette an der Achse ~ Querschnitt nur aus der Ferne (nah verzerrt die Perspektive die Grate; 20 m = Dachbreite x 1,5)
MAX_HALB_M = 10.0      # groesser als jede Traufe am Turm (Schwabentor 6,5 m + Blick uebers Eck x 1,41)
SCHRITT = 0.1
KNICK = 0.35           # Aufsatz beginnt, wo die Breite weniger als 35 % so schnell abnimmt wie auf der Dachflaeche (Laterne/Aufsatz: fast senkrecht)
KNICK_LAENGE = 0.4     # ... ueber mind. 0,4 m (Maskenrauschen an Ziegeln/Firstziegeln ist kuerzer)
MIN_FOTOS = 3          # Formfamilie aus >= 3 Fotos
MIN_DECKUNG = 0.6      # Foto zaehlt fuer die Form, wenn es 60 % der Hoehen zwischen Traufe und Fuss misst
C_GITTER = np.round(np.arange(-3.0, 6.01, 0.25), 2)
FAMILIE_SCHWELLE = 0.75   # wie vordach_profil.familie
GUT_DECKUNG = 0.45     # gutes Foto: sieht mind. 45 % der Hoehen Traufe..Fuss (von unten verdeckt die Traufe den unteren Teil)
GUT_FEHLER = 0.30      # ... und die beste Hypothese trifft die Himmelskante auf 30 cm (Median)
C_GROB = np.round(np.arange(-2.0, 4.01, 0.5), 2)   # Gitter im Werkzeuglauf (13 c x 9 Fusshoehen je Foto; Familienbreite 0,75 > Schritt)
KONSENS = 0.6          # 60 % der guten Fotos innerhalb der Familienbreite um den Median


def g_profil(s, c):
    s = np.asarray(s, float); return s if abs(c) < 1e-6 else (np.exp(c * s) - 1.0) / (np.exp(c) - 1.0)


def g_inv(s, c):
    s = np.clip(np.asarray(s, float), 0.0, 1.0); return s if abs(c) < 1e-6 else np.log1p(s * (np.exp(c) - 1.0)) / c


def familie(c): return "gerade" if abs(c) < FAMILIE_SCHWELLE else ("geschweift" if c > 0 else "gewoelbt")


def breite_messen(maske, proj, A, zs, C):
    """Sichtbare Halbbreite je Hoehe (dict z -> h) an der Achse A; maske True = Himmel. Beide Seiten muessen Himmel erreichen."""
    H, W = maske.shape; X = np.c_[np.tile(A, (len(zs), 1)), zs]; p, zc = proj(X)
    if (zc <= 0.5).any(): return {}
    b = np.array([A[0] - C[0], A[1] - C[1], 0.0]); b /= max(np.linalg.norm(b), 1e-9); q = np.array([-b[1], b[0], 0.0])
    p1, _ = proj(X + q); ppm = np.linalg.norm(p1 - p, axis=1); e = (p1 - p) / np.maximum(ppm[:, None], 1e-9); out = {}
    for i, z in enumerate(zs):
        if not (2 <= p[i, 0] < W - 2 and 2 <= p[i, 1] < H - 2) or maske[int(p[i, 1]), int(p[i, 0])]: continue
        nmax = int(MAX_HALB_M * ppm[i]); k_ = np.arange(nmax + 1); seiten = []
        for sg in (-1, 1):
            x = np.round(p[i, 0] + sg * k_ * e[i, 0]).astype(int); y = np.round(p[i, 1] + sg * k_ * e[i, 1]).astype(int)
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            if not ok.all(): seiten.append(None); break          # Bildrand vor dem Himmel
            hi = np.nonzero(maske[y, x])[0]; seiten.append(int(hi[0]) if hi.size else None)
        if len(seiten) == 2 and None not in seiten: out[round(float(z), 2)] = (seiten[0] + seiten[1]) / 2 / ppm[i]
    return out


def fuss_finden(zs, h):
    """Fuss des Aufsatzes in einem Foto: laengster Lauf, in dem die Breite mit Dachneigung abnimmt (Steigung < -0,4, unten verdeckt die Traufe die Dachflaeche
    bei Fotos von unten - dort ist die Breite konstant/steigend), danach die erste Hoehe, ab der sie KNICK_LAENGE lang nicht mehr so abnimmt. -> (z_fuss, s0, z_lauf0) | None"""
    ok = np.isfinite(h); m = int(round(0.3 / SCHRITT)); sl = np.full(len(zs), np.nan)
    for i in range(m, len(zs) - m):
        if ok[i - m] and ok[i + m]: sl[i] = (h[i + m] - h[i - m]) / (2 * m * SCHRITT)
    steil = np.isfinite(sl) & (sl < -0.4); best = (0, 0); i = 0
    while i < len(zs):
        if steil[i]:
            j = i
            while j + 1 < len(zs) and steil[j + 1]: j += 1
            if j - i > best[1] - best[0]: best = (i, j)
            i = j + 1
        else: i += 1
    if (best[1] - best[0]) * SCHRITT < 1.5: return None                          # mind. 1,5 m Dachflaeche gesehen
    s0 = float(np.median(sl[best[0]:best[1] + 1])); n_ = int(round(KNICK_LAENGE / SCHRITT))
    for i in range(best[0], len(zs) - n_):
        w = sl[i:i + n_]
        if np.isfinite(w).all() and (w > KNICK * s0).all(): return float(zs[i]), s0, float(zs[best[0]])
    return None


def ringe(eave, fuss, z_t, z_f, c, n=10):
    """Ringe der Dachflaeche (Liste von (4, 3)-Punkten) von der Traufe (Rechteck eave = (o, d, n, u_lo, u_hi, v_lo, v_hi)) zum Fussquadrat (Mitte A, halb a, theta)
    mit Profil g(t; c): t = Anteil des Weges nach innen, z = z_t + (z_f - z_t) g(t)."""
    o, d, n_, ul, uh, vl, vh = eave; A, a, th = fuss
    E = np.array([o + u * d + v * n_ for u, v in ((ul, vl), (uh, vl), (uh, vh), (ul, vh))])
    if th is None: F = np.array([A + a * (sx * d + sy * n_) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])   # nicht gemessen: parallel zur Traufe
    else: tr = math.radians(th); F = np.array([A + a * np.array([sx * math.cos(tr) - sy * math.sin(tr), sx * math.sin(tr) + sy * math.cos(tr)]) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    # Ecken zuordnen: Fussecke mit gleicher Richtung wie die Traufecke
    F = np.array([F[int(np.argmax([(f - A) @ (e - A) for f in F]))] for e in E])
    return [np.c_[E + t * (F - E), np.full(4, z_t + (z_f - z_t) * float(g_profil(t, c)))] for t in np.linspace(0, 1, n + 1)]


VETO_TOL = 0.3      # wie dach_profil_wolke --dom1_tol: Fotoflaeche darf hoechstens 0,3 m weiter hinaus stehen als die Laser-Isolinie ihrer Hoehe
VETO_RASTER = 0.1   # Hoehenraster der gespeicherten Isolinien (m)


def laser_isolinien(D, hoehe, zs):
    """DOM1-Isolinien je Hoehe im Dachrahmen (o, d, n aus dach_profil.json): {z: [l_-d, l_+d, l_-n, l_+n]} = groesster Abstand nach aussen, an dem der Laser
    noch >= z misst; None = Laser blind (Laterne, Spitze, Sektor ohne Flaeche) -> dort kein Veto. Gleiche Regeln wie dach_profil_wolke.dom1_veto (Klippe an der Traufe)."""
    from dach_profil_wolke import dom1_veto
    P = [[float(z), -99.0, 99.0, -99.0, 99.0] for z in zs]
    ein = dom1_veto(P, D["o"], D["d"], D["n"], hoehe, tol=0.0); iso = {round(float(z), 2): [None] * 4 for z in zs}
    for e in ein: iso[round(float(e["z"]), 2)][("-d", "+d", "-n", "+n").index(e["seite"])] = float(e["laser_m"])
    # Glaetten: 1-m-Laserraster + bilinear gibt je 0,1 m zackige Isolinien (Schwabentor 1122p: Seite -d 3,00 -> 3,08 m bei 0,9 m mehr Hoehe). Gleitender Median
    # ueber +-0,5 m, dann nach oben nicht breiter werdend (eine Dachflaeche wird mit der Hoehe schmaler; Laterne ist blind = None und bleibt aussen vor).
    zk = sorted(iso); k_ = int(round(0.5 / max(float(np.median(np.diff(zk))) if len(zk) > 1 else 0.1, 1e-3)))
    for j in range(4):
        w = np.array([np.nan if iso[z][j] is None else iso[z][j] for z in zk], float); g = w.copy()
        for i in range(len(w)):
            s_ = w[max(0, i - k_):i + k_ + 1]
            if np.isfinite(w[i]) and np.isfinite(s_).any(): g[i] = float(np.nanmedian(s_))
        lauf = np.inf
        for i, z in enumerate(zk):
            if not np.isfinite(g[i]): lauf = np.inf; continue                              # blinde Hoehe trennt die Laeufe
            lauf = min(lauf, g[i]); iso[z][j] = round(float(lauf), 3)
    return iso


def ringe_dom1_veto(rs, o, d, n, iso, tol=VETO_TOL):
    """DOM1-VETO DER FOTO-DACHFLAECHE (23.11.2026, Schwabentor-1122p: HOEHEN-TOR +1,73 m / k 0,958 - die Foto-Ebene Traufkante 6,77 m -> Fuss 0,8 m lag auf
    r 2-5 m je Seite 1,2-1,3 m weiter draussen als die Laser-Dachflaeche (56 Grad), weil die Familie g(t; c) zwischen der Ueberstand-Aussenkante und dem Fuss keinen
    Knick (Aufschiebling) kennt; die Stufe ersetzte die schon DOM1-geprueften Wolkenscheiben ohne eigenes Veto). Wie dach_profil_wolke.dom1_veto: steht eine Ringseite
    mehr als tol weiter hinaus als die Laser-Isolinie ihrer Hoehe, kommt sie auf die Isolinie (nicht + tol). Ring 0 (Traufkante aus Fotos) bleibt. iso: {z: [4 Werte|None]}.
    -> (Ringe, Eingriffe [dict(ring, z, seite, foto_m, laser_m)])."""
    o, d, n = (np.asarray(x, float) for x in (o, d, n)); zi = np.array(sorted(iso)); out = [rs[0]]; ein = []
    for k, r in enumerate(rs[1:], 1):
        z = float(r[0, 2]); L = iso[float(zi[int(np.argmin(np.abs(zi - z)))])] if len(zi) else [None] * 4
        if len(zi) and abs(float(zi[int(np.argmin(np.abs(zi - z)))]) - z) > 0.3: L = [None] * 4     # ausserhalb der gemessenen Hoehen: kein Urteil
        u = (r[:, :2] - o) @ d; v = (r[:, :2] - o) @ n
        for j, (nm, w, sg) in enumerate((("-d", u, -1), ("+d", u, 1), ("-n", v, -1), ("+n", v, 1))):
            if L[j] is None: continue
            zu = sg * w > L[j] + tol
            if zu.any(): ein.append(dict(ring=k, z=round(z, 2), seite=nm, foto_m=round(float((sg * w).max()), 2), laser_m=round(L[j], 2))); w[zu] = sg * L[j]
        out.append(np.c_[o + u[:, None] * d + v[:, None] * n, r[:, 2]])
    return out, ein


def hypothese_maske(shape, proj, rs, unterbau):
    """Himmelsmaske (True = Himmel) einer Hypothese: konvexe Huellen zwischen aufeinanderfolgenden Ringen + Unterbau-Koerper (Liste von Punktwolken)."""
    import cv2
    m = np.zeros(shape, np.uint8)
    for P in [np.vstack([a, b]) for a, b in zip(rs[:-1], rs[1:])] + list(unterbau):
        q, zc = proj(P)
        if (zc <= 0.3).any(): continue
        cv2.fillConvexPoly(m, cv2.convexHull(np.round(q).astype(np.int32)), 255)
    return m == 0


def aufsatz(A, a, z_f, hoehe=1.5):
    """Aufsatz-Koerper der Hypothese (nur fuer die Silhouette): Quader halb a ueber dem Fuss."""
    return np.array([[A[0] + sx * a, A[1] + sy * a, z] for sx in (-1, 1) for sy in (-1, 1) for z in (z_f, z_f + hoehe)])


def foto_form(maske, proj, A, zs, C, eave, fuss, z_t, z_fs, unterbau, cs=None, hz=None):
    """Analyse durch Synthese: gemessene Halbbreiten h(z) gegen die der gerenderten Hypothese (Dachflaeche g(t; c) Traufe -> Fuss bei z_f, darauf der Aufsatz)
    je (z_f, c). Vergleich ueber z_t + 0,3 .. max(z_fs) + 0,8 (der Fuss selbst steckt im Bild hoeher als in 3D, weil die hintere Dachflaeche von unten
    ueber ihn ragt - deshalb nicht am Knick der Breite ablesen, sondern mitrendern). -> (c, z_f, {(z_f, c): fehler}, n_hoehen) oder None."""
    z_fs = np.atleast_1d(z_fs); hz = hz if hz is not None else breite_messen(maske, proj, A, zs, C); zz = [z for z in hz if z_t + 0.3 <= z <= max(z_fs) + 0.8]
    if len(zz) < 15: return None
    zz = np.array(zz); fe = {}
    for z_f in z_fs:
        for c in (C_GITTER if cs is None else cs):
            hs = breite_messen(hypothese_maske(maske.shape, proj, ringe(eave, fuss, z_t, float(z_f), c), list(unterbau) + [aufsatz(fuss[0], fuss[1], float(z_f))]), proj, A, zz, C)
            d_ = [abs(hz[round(float(z), 2)] - hs[round(float(z), 2)]) for z in zz if round(float(z), 2) in hs]
            if len(d_) >= 0.7 * len(zz): fe[(round(float(z_f), 2), float(c))] = float(np.mean(np.minimum(d_, 1.5)))   # Ausreisser (Nachbar/Kabel) gedeckelt
    if not fe: return None
    k = min(fe, key=fe.get); return k[1], k[0], fe, len(zz)


def auswerten(je, n_hoehen_max):
    """je: Liste dict(foto, c, fehler, fehler_gerade, hoehen). Nur GUTE Fotos zaehlen (mind. GUT_DECKUNG der Hoehen Traufe..Fuss gesehen, Restfehler <= GUT_FEHLER m:
    sonst verdeckt ein Nachbar/Bildrand die Grate oder die Kamera ist ungenau). c = Median der guten Fotos, Familie = familie(c); gueltig, wenn >= MIN_FOTOS gute Fotos
    und >= KONSENS davon innerhalb +-FAMILIE_SCHWELLE um c liegen (Formfamilie aus >= 3 Fotos, nicht ein Einzelfoto)."""
    erg = dict(gueltig=False, fotos=len(je)); gut = [j for j in je if j["hoehen"] >= GUT_DECKUNG * n_hoehen_max and j["fehler"] <= GUT_FEHLER]
    st = {}
    for j in je: j["familie"] = familie(j["c"]); j["gut"] = j in gut
    for j in gut: st[j["familie"]] = st.get(j["familie"], 0) + 1
    erg.update(stimmen_gut=st, fotos_gut=len(gut))
    if len(gut) < MIN_FOTOS: erg["grund"] = f"nur {len(gut)} gute Fotos (verlangt {MIN_FOTOS})"; return erg
    c = float(np.median([j["c"] for j in gut])); k = sum(abs(j["c"] - c) <= FAMILIE_SCHWELLE for j in gut)
    if all("z_fuss" in j for j in gut): zf_ = [j["z_fuss"] for j in gut]; erg.update(z_fuss=round(float(np.median(zf_)), 2), z_fuss_streuung=round(float(np.median(np.abs(np.array(zf_) - np.median(zf_)))), 2))
    erg.update(c=round(c, 2), familie=familie(c), konsens=round(k / len(gut), 2), fehler_median=round(float(np.median([j["fehler"] for j in gut])), 3),
               fehler_gerade_median=round(float(np.median([j["fehler_gerade"] for j in gut])), 3))
    if k < MIN_FOTOS or k < KONSENS * len(gut): erg["grund"] = f"Fotos uneins: nur {k} von {len(gut)} bei c {c:+.2f} +-{FAMILIE_SCHWELLE}"; return erg
    erg.update(gueltig=True, grund=None); return erg


def main(argv=None):
    import cv2, flaeche_ortho as FO, dach_aus_fotos as DA
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--profil"); ap.add_argument("--aus"); ap.add_argument("--bild"); ap.add_argument("--max-fotos", type=int, default=300)
    ap.add_argument("--nur-messen", action="store_true"); ap.add_argument("--root"); ap.add_argument("--cache")
    ap.add_argument("--ohne_dom1", action="store_true", help="kein DOM1-Veto der Fotoflaeche (nur Test)")
    a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); pp = a.profil or os.path.join(Au, "dach_profil.json")
    try: D = json.load(open(pp))
    except Exception: print("kein Dachprofil", pp); return 3
    if a.root: FO.ROOT = a.root
    SF = D.get("spitze_foto") or {}; TF = D.get("traufe_foto") or {}
    A = np.array(SF["achse"], float) if SF.get("achse") else np.array(D["o"], float) + D["achse_uv"][0] * np.array(D["d"]) + D["achse_uv"][1] * np.array(D["n"])
    zo = [E["z_oben"] for E in (TF.get("seiten") or {}).values() if E.get("gueltig")]; z_t = float(np.median(zo)) if zo and TF.get("gueltig") else float(D["z0"])
    z_hi = float(SF.get("spitze_z") or (D["scheiben"][-1][0] + 2)); zs = np.round(np.arange(z_t, z_hi + 1e-9, SCHRITT), 2)
    obj, cams = FO.kameras_laden(a.objekt); cache = a.cache or os.path.join(Au, "himmel_cache"); mess = []; bilder = []
    print(f"Achse {A.round(2)}, Traufe z {z_t:.2f} ({'traufe_foto' if zo else 'z0'}), Suche bis z {z_hi:.2f}; {len(cams)} Kameras")
    for nr, (c, pf) in sorted(cams.items()):
        if len(mess) >= a.max_fotos: break
        _, _, C = FO.projektion(np.array([[A[0], A[1], z_t]]), c)
        if math.hypot(C[0] - A[0], C[1] - A[1]) < ABSTAND_MIN: continue
        wh = c.get("bild"); W0, H0 = (int(wh[0]), int(wh[1])) if wh else (int(round(c["cx"] * 2)), int(round(c["cy"] * 2)))
        M_, s = DA.himmel_laden(dict(name=nr, W0=W0, H0=H0, foto=pf), cache, nur_cache=True)
        if M_ is None: continue
        def proj(X, c=c, s=s): q, zc, _ = FO.projektion(np.atleast_2d(X), c); return q * s, zc
        hz = breite_messen(M_, proj, A, zs, C)
        if len(hz) >= 20: mess.append((nr, math.degrees(math.atan2(C[1] - A[1], C[0] - A[0])), hz)); bilder.append((nr, pf, c, s, hz))
    if os.environ.get("DACHFLAECHE_DIAG"):
        for nm, az, hz in mess:
            zz = sorted(hz); print(f"  {nm[-24:]:24s} az {az:6.0f} z {zz[0]:.1f}..{zz[-1]:.1f} n {len(zz):3d} | " + " ".join(f"{z:.0f}:{hz[z]:.2f}" for z in zz[::10]))
    E = dict(z_traufe=round(z_t, 2), fotos_gemessen=len(mess), achse=[round(float(A[0]), 3), round(float(A[1]), 3)],
             quelle="tools/dachflaeche_aus_umriss.py: Himmelskante der kalibrierten Fotos an der Dachachse gegen gerenderte Profil-Hypothesen (Analyse durch Synthese)")
    fu = []
    for nm, az, hz in mess:
        h = np.array([hz.get(round(float(z), 2), np.nan) for z in zs]); f = fuss_finden(zs, h)
        if f: fu.append((nm, f))
    E["fotos_mit_fuss"] = len(fu)
    if len(fu) < MIN_FOTOS:
        E.update(gueltig=False, grund=f"Fuss des Aufsatzes nur in {len(fu)} Fotos")
    else:
        z_f = float(np.median([f[1][0] for f in fu])); E.update(z_fuss=round(z_f, 2), z_fuss_streuung=round(float(np.median([abs(f[1][0] - z_f) for f in fu])), 2))
        pr = [p for p in (SF.get("profil") or []) if len(p) > 6]; pf_ = min(pr, key=lambda p: abs(p[0] - z_f)) if pr else None
        if pf_ is not None and abs(pf_[0] - z_f) <= 0.3: fuss = (A, float(pf_[6]), float(pf_[5]) if pf_[4] == "eckig" else None); fq = f"spitze_foto-Profil z {pf_[0]} ({pf_[4]}" + (")" if pf_[4] == "eckig" else ", ANNAHME Quadrat parallel zur Traufe)")
        else: fuss = (A, float(np.median([hz.get(round(z_f, 2), np.nan) for _, _, hz in mess if round(z_f, 2) in hz])) / 1.2, None); fq = "Median der sichtbaren Halbbreite / 1,2 (ANNAHME Quadrat parallel zur Traufe)"
        z_fs = np.round(np.arange(z_f - 1.5, z_f + 0.51, 0.25), 2); E["z_fuss_knick"] = E.pop("z_fuss"); E["z_fuss_knick_streuung"] = E.pop("z_fuss_streuung")
        import bauteile as BT
        P2, _, _ = BT.traufe_einbauen([list(p) for p in D["scheiben"]], D); rg = next((p for p in P2 if len(p) > 6 and p[6] == "traufe_foto"), None) or P2[0]
        o_, d_, n_ = np.array(D["o"], float), np.array(D["d"], float), np.array(D["n"], float); eave = (o_, d_, n_, rg[1], rg[2], rg[3], rg[4]); wh = D["wand_halb"]
        zu = min([E_.get("z_wand_bau", E_["z_wand"]) for E_ in (TF.get("seiten") or {}).values() if E_.get("gueltig")] or [z_t - 0.9])
        Rk = lambda ul, uh, vl, vh, z0_, z1_: np.array([[*(o_ + u * d_ + v * n_), z] for u in (ul, uh) for v in (vl, vh) for z in (z0_, z1_)])
        unterbau = [Rk(rg[1], rg[2], rg[3], rg[4], zu, z_t), Rk(-wh[0], wh[0], -wh[1], wh[1], 0.0, zu)]
        E.update(fuss=dict(halb=round(fuss[1], 3), theta=fuss[2], quelle=fq), traufring=[round(float(x), 3) for x in rg[:5]])
        je = []
        for nm, pf, c, s, hz in bilder:
            r_ = foto_form(None if False else DA.himmel_laden(dict(name=nm, W0=int(c["bild"][0]) if c.get("bild") else int(round(c["cx"] * 2)), H0=int(c["bild"][1]) if c.get("bild") else int(round(c["cy"] * 2)), foto=pf), cache, nur_cache=True)[0],
                           lambda X, c=c, s=s: (FO.projektion(np.atleast_2d(X), c)[0] * s, FO.projektion(np.atleast_2d(X), c)[1]), A, zs, FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2], eave, fuss, z_t, z_fs, unterbau, cs=C_GROB, hz=hz)
            if r_ is None: continue
            cb, zb, fe, nz = r_; je.append(dict(foto=nm, c=cb, z_fuss=zb, fehler=round(fe[(zb, cb)], 3), fehler_gerade=round(min([v for (z_, c_), v in fe.items() if c_ == 0.0] or [float("nan")]), 3), hoehen=nz))
        E.update(auswerten(je, int(round((max(z_fs) + 0.8 - z_t - 0.3) / SCHRITT)) + 1)); E["je_foto"] = je
        if E.get("gueltig") and not a.ohne_dom1: E.update(veto_block(D, obj, eave, fuss, z_t, E))
    print(f"{len(mess)} Fotos mit Silhouette; Fuss in {E.get('fotos_mit_fuss')} (z {E.get('z_fuss')}, Streuung {E.get('z_fuss_streuung')}, {E.get('fuss')}); "
          + (f"FAMILIE {E['familie']} (c {E['c']}, Konsens {E['konsens']}, Restfehler {E['fehler_median']} m, gerade waere {E['fehler_gerade_median']} m), gute Fotos {E['fotos_gut']} {E['stimmen_gut']}" if E.get("gueltig") else f"UNGUELTIG: {E.get('grund')} {E.get('stimmen_gut', '')}"))
    for j in E.get("je_foto", [])[:80] if os.environ.get("DACHFLAECHE_DIAG") else []: print(f"   {j['foto'][-24:]:24s} c {j['c']:+.2f} zf {j['z_fuss']} Fehler {j['fehler']:.2f} (gerade {j['fehler_gerade']:.2f}) n {j['hoehen']}")
    try: bild(a.bild or os.path.join(Au, "dachflaeche_umriss.jpg"), bilder, A, E)
    except Exception as ex: print("Bild fehlgeschlagen:", ex)
    if not a.nur_messen: D["flaeche_foto"] = E; json.dump(D, open(a.aus or pp, "w"), indent=1); print("->", a.aus or pp, "(Block flaeche_foto)")
    return 0 if E.get("gueltig") else 4


def veto_block(D, obj, eave, fuss, z_t, E, hoehe=None):
    """DOM1-Isolinien zwischen Traufe und Fuss (+0,5 m) fuer bauteile.flaeche_aus_foto + Bericht, wie weit die gebaute Fotoflaeche draussen steht.
    -> dict(dom1_veto=...) bzw. {} ohne Rahmen/Laser."""
    if hoehe is None:
        from dach_profil_wolke import laser_im_rahmen
        hoehe = laser_im_rahmen(obj, klippe=3.0)
    if hoehe is None: return dict(dom1_veto=dict(aktiv=False, grund="kein Rahmen/Laser"))
    z_f = float(E["z_fuss"]); zs = np.round(np.arange(z_t, z_f + 0.5 + 1e-9, VETO_RASTER), 2)
    try: iso = laser_isolinien(D, hoehe, zs)
    except Exception as ex: return dict(dom1_veto=dict(aktiv=False, grund=f"Laser nicht lesbar: {ex}"))
    c_ = 0.0 if E.get("familie") == "gerade" else float(E.get("c", 0.0))
    rs = ringe(eave, fuss, z_t, z_f, c_, n=max(12, int(math.ceil((z_f - z_t) / 0.3))))
    _, ein = ringe_dom1_veto(rs, D["o"], D["d"], D["n"], iso)
    ueber = [e["foto_m"] - e["laser_m"] for e in ein]
    V = dict(aktiv=True, tol_m=VETO_TOL, isolinien=[[z] + iso[z] for z in sorted(iso)], eingriffe=len(ein),
             groesster_ueberstand_m=round(max(ueber), 2) if ueber else 0.0, median_ueberstand_m=round(float(np.median(ueber)), 2) if ueber else 0.0,
             quelle="dach_profil_wolke.dom1_veto-Regeln (Klippe 3 m) auf die Ringe der gebauten Fotoflaeche; bauteile.flaeche_aus_foto setzt die Seiten auf die Isolinie")
    print(f"DOM1-VETO Fotoflaeche: {len(ein)} Ringseiten mehr als {VETO_TOL} m ausserhalb der Laser-Isolinie (Median {V['median_ueberstand_m']} m, groesster {V['groesster_ueberstand_m']} m)"
          + (" -> Seiten auf die Isolinie (Knick/Aufschiebling statt gerader Ebene ab der Ueberstand-Aussenkante)" if ein else " -> Fotoflaeche passt zum Laser"))
    return dict(dom1_veto=V)


def bild(aus, bilder, A, E):
    """Pruefbild: bis 6 Fotos (Ausschnitt), gruen gemessene Halbbreiten, rot Traufe, blau Fuss des Aufsatzes, gelb gerade Verbindung Traufe->Fuss dieses Fotos."""
    import cv2, flaeche_ortho as FO
    je = {j["foto"]: j for j in E.get("je_foto", [])}; pick = [b for b in bilder if b[0] in je] or bilder
    pick = [pick[int(i)] for i in np.linspace(0, len(pick) - 1, min(6, len(pick)))] if pick else []; kach = []
    for nr, pf, c, s, hz in pick:
        im = cv2.imread(pf)
        if im is None: continue
        sb = im.shape[1] / (c["bild"][0] if c.get("bild") else c["cx"] * 2); P_ = lambda X: FO.projektion(np.atleast_2d(np.asarray(X, float)), c)[0][0] * sb
        C = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]; b = np.array([A[0] - C[0], A[1] - C[1], 0.0]); b /= np.linalg.norm(b); q = np.array([-b[1], b[0], 0.0])
        pts = []
        for z, h in list(hz.items())[::3]:
            for sg in (-1, 1): p = P_(np.array([A[0], A[1], z]) + sg * h * q); pts.append(p); cv2.circle(im, (int(p[0]), int(p[1])), max(2, im.shape[1] // 700), (0, 220, 0), -1)
        j = je.get(nr)
        for zz, col in ((E.get("z_traufe"), (0, 0, 255)), (E.get("z_fuss"), (255, 0, 0))):
            if zz is None: continue
            hh = hz.get(min(hz, key=lambda z_: abs(z_ - zz)), 3.0)
            l_ = P_(np.array([A[0], A[1], zz]) - hh * q); r_ = P_(np.array([A[0], A[1], zz]) + hh * q); cv2.line(im, tuple(int(v) for v in l_), tuple(int(v) for v in r_), col, max(2, im.shape[1] // 600))
        if not pts: continue
        P = np.array(pts); r = int(0.15 * np.ptp(P[:, 1]) + 40); x0, y0 = np.maximum(P.min(0) - r, 0).astype(int); x1, y1 = (P.max(0) + r).astype(int); k = im[y0:y1, x0:x1]
        if k.size == 0: continue
        k = cv2.resize(k, (max(1, int(k.shape[1] * 420 / k.shape[0])), 420)); cv2.putText(k, f"{nr[-16:]} {j['familie'] + ' c' + str(j['c']) + ' f' + str(j['fehler']) if j else ''}", (4, 16), 0, 0.45, (255, 0, 255), 1); kach.append(k)
    if kach: cv2.imwrite(aus, np.hstack(kach), [cv2.IMWRITE_JPEG_QUALITY, 85]); print("Bild:", aus)


if __name__ == "__main__": sys.exit(main())
