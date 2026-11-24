#!/usr/bin/env python3
"""relief_kantenglatt.py - FEINRAUSCHEN OHNE FOTOKANTE GLAETTEN (Kettenstufe der Fassaden-Kette, 24.11.2026, Befund 1122x f00_wand "erfunden 0,984").

BEFUND: audit/ebenen_abweichung.json zaehlte an der Ostwand f00 392 544 Modellkantenpunkte (Knick > 30 Grad, kantenstufe.modellkanten) gegen 18 975
triangulierte Fotokanten; 98 % der Modellkanten ohne Fotokante in 0,15 m. URSACHE (gemessen, tools/relief_kantenglatt.py --messen): die Relief-Hoehenbilder
(_voll 5 cm, _foto/_mono/_misch 2-3 cm) werden 1:1 als Gitter gebaut; schon 1-3 cm Netz-/Mono-Rauschen je Zelle knickt benachbarte Dreiecke um > 30 Grad ->
fast jede Gitterkante ist eine 'Modellkante'. relief_kanten_beleg / tiefe_belegt pruefen nur Koerper >= 5 cm (band) - das Feinrauschen darunter blieb ungeprueft,
die Quaderwaende (_voll oberhalb der Feinzone) liefen an gar keiner Kantenpruefung vorbei.
KRITERIUM (Kernmethode Form = Fotokanten + Triangulation; Mindestmass 0,8 mm H0):
  Struktur feiner als das Druckmass (druck_min = 0,8 mm x Massstab = 0,07 m bei 1:87) bleibt nur, wo eine triangulierte Fotokante (kanten_wand, Mehrfoto)
  in tol (0,15 m, gleiche Toleranz wie ebenen_abweichung) liegt oder das Wandbild sie belegt (Quaderraster 'stein_id' samt Rille). Sonst wird sie durch das
  gleitende Mittel ueber druck_min ersetzt (kleinstes ungerades Fenster >= druck_min/px, >= 3 Zellen) - groessere Formen (Vorsprung, Gesims, Bogen) bleiben,
  denn ein Mittel ueber 0,07 m verschiebt sie hoechstens am Rand. Kein freier Faktor: Fensterbreite = Druckmass, Abstand = Tor-Toleranz.
Aufruf:
  relief_kantenglatt.py --messen <relief.npz> <ebenen.json> [--zone u0 u1 z0 z1] [--massstab 87]   Messung vorher/nachher (nichts geschrieben)
  relief_kantenglatt.py <relief.npz> <aus.npz> <ebenen.json> [--massstab 87]                         schreibt aus.npz (+ .jpg)
Messgroessen (je Relief allein, Rand der Platte nicht gezaehlt): modellkanten (Punkte wie modellkanten: Gitterkanten <= 5 cm -> 2 Punkte), erfunden
(Anteil Modellkantenpunkte ohne Fotokante in tol, mit Fotokante < 1 m - wie ebenen_abweichung), recall (Anteil Fotokanten mit Modellkante in tol),
an_flaeche (Fotokante <= tol an der Reliefflaeche). Tiefe: Relief so verschoben, dass sein Median auf dem Median der Kantentiefe liegt (wie flaeche im Bau).
"""
import sys, os, json, argparse, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)


def gitter(H, W, px, u0, z0):
    ii, jj = np.mgrid[0:H, 0:W]
    return u0 + (jj + 0.5) * px, z0 + (H - 1 - ii + 0.5) * px


def knick_kanten(rel, px, u0, z0, winkel=30.0, gueltig=None):
    """Gitterkanten des Reliefgitters (Dreiecke wie relief_einsatz.koerper: (q00, q10, q01), (q01, q10, q11)) mit Knick > winkel, als Punkte (u, z, d):
    je Kante beide Endpunkte (Kanten <= 0,07 m -> wie kantenstufe.modellkanten mit schritt 0,05: 2 Punkte). gueltig = Zellmaske; Kanten mit ungueltiger Ecke fallen weg."""
    rel = np.asarray(rel, float); H, W = rel.shape
    if H < 3 or W < 3: return np.zeros((0, 3))
    U, Zg = gitter(H, W, px, u0, z0); P = np.stack([U, Zg, rel], -1)
    g = np.ones((H, W), bool) if gueltig is None else np.asarray(gueltig, bool)
    q00, q01, q10, q11 = P[:-1, :-1], P[:-1, 1:], P[1:, :-1], P[1:, 1:]
    def nrm(a, b, c):
        v = np.cross(b - a, c - a); return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)
    n1 = nrm(q00, q10, q01); n2 = nrm(q01, q10, q11); cg = np.cos(np.radians(winkel)); out = []
    g00, g01, g10, g11 = g[:-1, :-1], g[:-1, 1:], g[1:, :-1], g[1:, 1:]
    m = ((n1 * n2).sum(-1) < cg) & g01 & g10                                   # Diagonale q01-q10 im selben Quad
    out += [q01[m], q10[m]]
    m = ((n1[1:] * n2[:-1]).sum(-1) < cg) & g00[1:] & g01[1:]                  # waagrechte Kante q00-q01 (Zeile i): T1 von Quad (i, j) und T2 von Quad (i-1, j)
    out += [q00[1:][m], q01[1:][m]]
    m = ((n1[:, 1:] * n2[:, :-1]).sum(-1) < cg) & g00[:, 1:] & g10[:, 1:]      # senkrechte Kante q00-q10 (Spalte j): T1 von Quad (i, j) und T2 von Quad (i, j-1)
    out += [q00[:, 1:][m], q10[:, 1:][m]]
    return np.concatenate(out, 0) if out else np.zeros((0, 3))


def _zellen(K, H, W, px, u0, z0):
    ci = (H - 1 - np.floor((K[:, 1] - z0) / px)).astype(int); cj = np.floor((K[:, 0] - u0) / px).astype(int)
    return ci, cj, (ci >= 0) & (ci < H) & (cj >= 0) & (cj < W)


def messen(rel, px, u0, z0, K, gueltig=None, tol=0.15, winkel=30.0, versatz=None):
    """Erfunden/Recall des Reliefs gegen die Fotokanten K (N x 3: u, z, w). Nur Fotokanten ueber gueltigen Zellen zaehlen. versatz = Tiefenverschiebung
    (None: Median der Kanten - Median des Reliefs); fuer vorher/nachher DENSELBEN Wert nehmen (Rueckgabe 'versatz'), sonst misst man die Medianverschiebung mit."""
    from scipy.spatial import cKDTree
    rel = np.asarray(rel, float); H, W = rel.shape; g = np.ones((H, W), bool) if gueltig is None else np.asarray(gueltig, bool)
    K = np.asarray(K, float); ci, cj, ok = _zellen(K, H, W, px, u0, z0); ok[ok] = g[ci[ok], cj[ok]]; K = K[ok]
    if len(K) < 10 or g.sum() < 20: return dict(fotokanten=int(len(K)), modellkanten=0, erfunden=None, recall=None, an_flaeche=None, versatz=None)
    if versatz is None: versatz = float(np.median(K[:, 2]) - np.median(rel[g]))     # Relief auf die Kantentiefe (wie 'flaeche' im Bau): Messung unabhaengig von der Ebenenlage
    E = knick_kanten(rel + versatz, px, u0, z0, winkel, g)
    U, Zg = gitter(H, W, px, u0, z0); S = np.stack([U[g], Zg[g], rel[g] + versatz], 1)
    d_fl = cKDTree(S).query(K)[0]
    if not len(E): return dict(fotokanten=int(len(K)), modellkanten=0, erfunden=0.0, recall=0.0, an_flaeche=round(float((d_fl <= tol).mean()), 4), versatz=round(versatz, 4))
    d_kp = cKDTree(K).query(E)[0]; d_ka = cKDTree(E).query(K)[0]; belegt = d_kp < 1.0
    return dict(fotokanten=int(len(K)), modellkanten=int(len(E)), erfunden=round(float(((d_kp > tol) & belegt).sum() / max(belegt.sum(), 1)), 4),
                recall=round(float((d_ka <= tol).mean()), 4), an_flaeche=round(float((d_fl <= tol).mean()), 4), versatz=round(versatz, 4))


def fenster_zellen(px, druck_min):
    """Kleinstes ungerades Fenster (Zellen) >= druck_min/px, mindestens 3."""
    n = int(np.ceil(druck_min / px - 1e-9)); n = max(3, n + (1 - n % 2)); return n


def glaetten(rel, px, u0, z0, K, druck_min, tol=0.15, gueltig=None, behalten=None):
    """rel ausserhalb des Fotokanten-Belegs (Zellmitte > tol von jeder Fotokante, nur u/z) und ausserhalb 'behalten' durch das maskierte gleitende Mittel
    ueber druck_min ersetzen; weicher Uebergang (Mittel des Beleg-Anteils ueber dasselbe Fenster). Rueckgabe (rel_neu, info)."""
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    rel = np.asarray(rel, np.float64); H, W = rel.shape; g = np.ones((H, W), bool) if gueltig is None else np.asarray(gueltig, bool)
    n = fenster_zellen(px, druck_min); gf = g.astype(float)
    num = ndi.uniform_filter(np.where(g, rel, 0.0), n, mode="nearest"); den = ndi.uniform_filter(gf, n, mode="nearest")
    L = np.where(den > 1e-6, num / np.maximum(den, 1e-6), rel)
    U, Zg = gitter(H, W, px, u0, z0); bel = np.zeros((H, W), bool)
    K = np.zeros((0, 3)) if K is None else np.asarray(K, float)
    r_bel = tol + n * px                                                       # Modellkante in tol einer Fotokante haengt an Zellen bis tol + ein Mittelungsfenster entfernt (Recall bleibt)
    if len(K):
        d = cKDTree(K[:, :2]).query(np.stack([U.ravel(), Zg.ravel()], 1), distance_upper_bound=r_bel + 1e-9)[0].reshape(H, W); bel = np.isfinite(d) & (d <= r_bel)
    if behalten is not None: bel |= np.asarray(behalten, bool)
    wb = np.clip(ndi.uniform_filter(bel.astype(float), n, mode="nearest"), 0, 1); wb[bel] = 1.0      # Beleg = Originalrelief, Rand laeuft ueber ein Fenster aus
    neu = np.where(g, wb * rel + (1 - wb) * L, rel)
    geaendert = g & (np.abs(neu - rel) > 1e-4)
    return neu.astype(np.float32), dict(fenster_zellen=n, fenster_m=round(n * px, 3), beleg_anteil=round(float((bel & g).sum() / max(g.sum(), 1)), 4),
                                        geaendert_anteil=round(float(geaendert.sum() / max(g.sum(), 1)), 4),
                                        max_aenderung_m=round(float(np.abs(neu - rel)[g].max()) if g.any() else 0.0, 4))


def masken(Z):
    """(gueltig, behalten) eines Relief-npz: gueltig = Wandzellen ohne Oeffnung; behalten = Quaderraster (stein_id > 0) samt Rille (Wandbild-Beleg)."""
    from scipy import ndimage as ndi
    rel = np.asarray(Z["rel"]); g = np.isfinite(rel)
    if "wand" in Z: g &= np.asarray(Z["wand"], bool)
    if "oeffnung" in Z: g &= ~np.asarray(Z["oeffnung"], bool)
    beh = None
    if "stein_id" in Z:
        s = np.asarray(Z["stein_id"]) > 0; px = float(Z["px"])
        rb = 0.07
        if "quader_relief" in Z:
            try: rb = float(json.loads(str(Z["quader_relief"])).get("rille_breite_m", rb))
            except Exception: pass
        k = 2 * max(1, int(np.ceil(rb / px))) + 1; beh = ndi.binary_dilation(s, np.ones((k, k), bool)) if s.any() else s
    return g, beh


def relief_kantenglatt(f_in, f_out, K, druck_min, tol=0.15):
    """Datei-Stufe: liest f_in, schreibt f_out (alle Schluessel, rel geglaettet, + 'kantenglatt' JSON) und f_out.jpg (rot = geglaettet). Ohne Fotokanten unveraendert."""
    Z = dict(np.load(f_in, allow_pickle=False))
    if K is None or len(K) < 10: return dict(unveraendert=True, grund="keine Fotokanten der Wandebene")
    px, u0, z0 = float(Z["px"]), float(Z["u0"]), float(Z["z0"]); g, beh = masken(Z); rel = np.asarray(Z["rel"], np.float32)
    vor = messen(rel, px, u0, z0, K, g, tol); neu, info = glaetten(rel, px, u0, z0, K, druck_min, tol, g, beh); nach = messen(neu, px, u0, z0, K, g, tol, versatz=vor.get("versatz"))
    info.update(vorher=vor, nachher=nach, druck_min_m=round(druck_min, 4), tol_m=tol)
    if not info["geaendert_anteil"]: return dict(unveraendert=True, grund="nichts zu glaetten", **info)
    if vor.get("recall") is not None and nach.get("recall") is not None and nach["recall"] < vor["recall"]:      # Guard: Fotokanten-Recall darf nicht sinken
        return dict(unveraendert=True, grund=f"Recall sinkt {vor['recall']} -> {nach['recall']}", **info)
    Z["rel"] = neu; Z["kantenglatt"] = json.dumps(info); np.savez_compressed(f_out, **Z)
    try:
        import cv2
        lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); s = np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        ch = g & (np.abs(neu - rel) > 0.005); im[ch] = (0.5 * im[ch] + np.array([0, 0, 127])).astype(np.uint8)
        cv2.imwrite(f_out[:-4] + ".jpg", cv2.resize(im, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
    except Exception: pass
    return info


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dateien", nargs="+"); ap.add_argument("--messen", action="store_true"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--zone", nargs=4, type=float, help="nur Zellen u0 u1 z0 z1 werten (z.B. sichtbarer Teil eines groben Reliefs ueber der Feinzone)"); ap.add_argument("--tol", type=float, default=0.15)
    a = ap.parse_args(); from putz_wandbild import kanten_wand; dm = 0.0008 * a.massstab
    if a.messen:
        f, ej = a.dateien[:2]; Z = dict(np.load(f)); K = kanten_wand(ej, Z)
        if K is None: print("keine passende Wandebene"); return 2
        px, u0, z0 = float(Z["px"]), float(Z["u0"]), float(Z["z0"]); g, beh = masken(Z); rel = np.asarray(Z["rel"], np.float32)
        if a.zone:
            U, Zg = gitter(*rel.shape, px, u0, z0); g &= (U >= a.zone[0]) & (U <= a.zone[1]) & (Zg >= a.zone[2]) & (Zg <= a.zone[3])
        vor = messen(rel, px, u0, z0, K, g, a.tol); neu, info = glaetten(rel, px, u0, z0, K, dm, a.tol, g, beh); nach = messen(neu, px, u0, z0, K, g, a.tol, versatz=vor.get("versatz"))
        print(json.dumps(dict(datei=os.path.basename(f), flaeche_m2=round(float(g.sum()) * px * px, 1), vorher=vor, nachher=nach, **info), ensure_ascii=False)); return 0
    f, fo, ej = a.dateien[:3]; Z = dict(np.load(f)); K = kanten_wand(ej, Z); print(json.dumps(relief_kantenglatt(f, fo, K, dm, a.tol), ensure_ascii=False)); return 0


if __name__ == "__main__": sys.exit(main())
