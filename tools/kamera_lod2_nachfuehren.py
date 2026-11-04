#!/usr/bin/env python3
"""kamera_lod2_nachfuehren.py - GENERISCH fuer jedes Objekt mit LoD2 (2026-11-04): Kamera (K-<foto>.json 'kamera') an den AMTLICHEN LoD2-Kanten
nachfuehren und pruefen. Ersetzt Handpicks und Sichtpruefung fuer neue Objekte.

Warum: Buendelkameras (Kaufhaus, Netzfehler 1 px) legten die LoD2-Ecken Meter neben die echten Ecken; auch die handgepickten Martinstor-Kameras
(RMS bis 73 px) liegen einige Prozent daneben (kamera_tor: verschobene Silhouette traf besser). Ein kleiner Netzfehler beweist nichts.

Verfahren (nur amtliche Geometrie, NICHT das Generatormodell -> kein Zirkelschluss beim spaeteren Modell-Foto-Vergleich):
  1. LoD2 aller Gebaeude im Radius (objekt_rahmen.ergaenzen -> Kachel/Rahmen), Polygone im Werkzeugrahmen (Rahmen + T_ der K-Kamera).
  2. Kanten: Polygonraender; Kanten zwischen zwei gleich orientierten Polygonen (Wand in Stuecken) entfallen. Abtastung alle --schritt m.
  3. Sichtbarkeit je Kamera: Tiefenbild der LoD2-Flaechen (Punktrender, Loecher geschlossen), Kantenpunkt sichtbar, wenn nicht deutlich dahinter.
  4. Fotokanten: Canny nach Glaettung -> Abstandsfeld (gekappt bei --kappe Anteil der langen Seite).
  5. Ausgleich (Cauchy-Verlust, f_scale 0,5, eine feine Nachstufe - synthetischer Beweis test_kamera_lod2.py): Drehung (3), Lage (3), log f; Residuum = Abstand Kantenpunkt-Projektion zur naechsten Fotokante (bilinear, gekappt), weiche Priors
     um die Startkamera (--sigma-dreh Grad, --sigma-lage m, --sigma-f relativ). Grob-fein: erst stark geglaettete Kanten, dann feine. Sichtbarkeit
     wird nach jedem Durchgang neu bestimmt.
  6. Tor: Treffer (Anteil Kantenpunkte <= --tol der langen Seite) und KONTRAST gegen dieselben Kanten um +-4 % verschoben. Bestanden nur, wenn
     Treffer >= --min-treffer und Kontrast >= --min-kontrast.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/kamera_lod2_nachfuehren.py modelle/<objekt>/objekt.json [--fotos 018,043] [--schreiben]
Ausgabe: audit/kamera_lod2.json, audit/kamera_lod2/<foto>.jpg (rot = vorher, gruen = nachher); --schreiben: K['kamera'] = nachgefuehrte Kamera
(nur bei bestandenem Tor), alte Kamera in K['kamera_vor_lod2'], Ergebnis in K['kamera']['lod2_tor']; durchgefallene Kameras bekommen
K['kamera']['lod2_tor'].ok = false (Werkzeuge muessen das beachten).
GRENZEN: LoD2 kennt keine Aufbauten/Erker/Tuerme ueber dem Dach (Martinstor-Helm) - nur Wand-/Dachkanten; Verdecker (Baeume, Autos) erzeugen
Fehlkanten (Kappung + Kontrast fangen das ab, aber nicht beliebig). k1 der Kamera wird beruecksichtigt, nicht ausgeglichen.
"""
import sys, os, json, glob, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def lod2_szene(obj, od, radius, T_):
    import lod2_gebaeude as LG, objekt_rahmen as OR
    obj = OR.ergaenzen(dict(obj), od)
    if not obj.get("lod2") or not obj.get("rahmen"): raise SystemExit("keine LoD2-Kachel/kein Rahmen (objekt_rahmen.py)")
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"]); polys = []
    for meta, ps in LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=radius):
        for typ, P in ps:
            Q = np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - R["gelaende"]] + T_
            if len(Q) >= 3: polys.append((typ, Q, meta.get("id") == obj["lod2"].get("id")))
    return polys


def kanten(polys, schritt):
    def nrm(Q):
        n = np.zeros(3)
        for i in range(len(Q)): a, b = Q[i], Q[(i + 1) % len(Q)]; n += np.cross(a, b)
        return n / max(np.linalg.norm(n), 1e-12)
    E = {}
    for typ, Q, eigen in polys:
        if typ == "GroundSurface": continue
        n = nrm(Q)
        for i in range(len(Q)):
            a, b = Q[i], Q[(i + 1) % len(Q)]
            if np.linalg.norm(b - a) < 0.05: continue
            k = tuple(sorted([tuple(np.round(a, 2)), tuple(np.round(b, 2))])); E.setdefault(k, []).append(n)
    P = []
    for (a, b), ns in E.items():
        if len(ns) >= 2 and abs(float(np.dot(ns[0], ns[1]))) > 0.985: continue          # Naht zwischen gleich orientierten Flaechen
        a, b = np.array(a), np.array(b); m = max(2, int(np.linalg.norm(b - a) / schritt) + 1); d = (b - a) / np.linalg.norm(b - a)
        P.append(np.c_[a + np.linspace(0, 1, m)[:, None] * (b - a), np.repeat(d[None], m, 0)])
    return np.vstack(P)                                                                             # (N, 6): Punkt + Kantenrichtung


def flaechen_netz(polys):
    import trimesh
    V, F = [], []
    for typ, Q, _ in polys:
        b = sum(len(v) for v in V); V.append(Q); F += [[b, b + i, b + i + 1] for i in range(1, len(Q) - 1)]
    return trimesh.Trimesh(np.vstack(V), np.array(F), process=False)


def projiziere(X, rv, t, f, k1, cx, cy):
    R, _ = cv2.Rodrigues(np.asarray(rv, float)); Xc = X @ R.T + t; z = Xc[:, 2]; zz = np.where(z > 1e-3, z, 1e-3)
    xn, yn = Xc[:, 0] / zz, Xc[:, 1] / zz; d = 1 + k1 * (xn ** 2 + yn ** 2); return np.c_[f * d * xn + cx, f * d * yn + cy], z


def bilin(img, uv):
    H, W = img.shape; u = np.clip(uv[:, 0], 0, W - 1.001); v = np.clip(uv[:, 1], 0, H - 1.001); x0 = u.astype(int); y0 = v.astype(int); fx = u - x0; fy = v - y0
    return img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy


def sichtbar(Pk, mesh, rv, t, f, k1, cx, cy, W, H):
    """Strahltest Kamera -> Kantenpunkt gegen das LoD2-Netz: sichtbar, wenn kein Treffer deutlich (> 0,25 m + 1 %) vor dem Punkt."""
    R, _ = cv2.Rodrigues(np.asarray(rv, float)); C = -R.T @ np.asarray(t, float)
    uv, z = projiziere(Pk[:, :3], rv, t, f, k1, cx, cy); ins = (z > 1) & (uv[:, 0] >= 2) & (uv[:, 0] < W - 2) & (uv[:, 1] >= 2) & (uv[:, 1] < H - 2)
    ok = np.zeros(len(Pk), bool); i = np.nonzero(ins)[0]
    if not len(i): return ok
    d = Pk[i, :3] - C; L = np.linalg.norm(d, axis=1); d /= L[:, None]
    loc, ri, _ = mesh.ray.intersects_location(np.repeat(C[None], len(i), 0), d, multiple_hits=False)
    vor = np.zeros(len(i), bool)
    if len(ri): vor[ri] = np.linalg.norm(loc - C, axis=1) < L[ri] - (0.25 + 0.01 * L[ri])
    ok[i] = ~vor; return ok


def nachfuehren(K, im, Pk, Pf, a):
    from scipy.optimize import least_squares
    H0, W0 = im.shape[:2]; s = min(1.0, a.px / max(W0, H0)); W, H = int(W0 * s), int(H0 * s); img = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    rv0 = np.array(K["rvec"], float); t0 = np.array(K["t"], float); f0 = K["f_px"] * s; cx = K.get("cx", W0 / 2) * s; cy = K.get("cy", H0 / 2) * s; k1 = float(K.get("k1", 0.0))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); L = max(W, H); kap = a.kappe * L
    NB = 8
    def feld(glatt):
        """Orientierte Abstandsfelder: Canny-Kanten nach Gradientenrichtung in NB Faechern (0..180 Grad, je +-1 Fach), je Fach ein Abstandsfeld."""
        g = cv2.GaussianBlur(gray, (0, 0), glatt); e = cv2.Canny(g, 20, 60) > 0
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); ang = (np.degrees(np.arctan2(gy, gx)) % 180.0); b = (ang / (180.0 / NB)).astype(int) % NB
        out = np.empty((NB, H, W), np.float32)
        for k in range(NB):
            ek = e & ((b == k) | (b == (k + 1) % NB) | (b == (k - 1) % NB))
            out[k] = np.minimum(cv2.distanceTransform((~ek).astype(np.uint8), cv2.DIST_L2, 3), kap)
        return out
    def abstand(D, X, rv, t, f, dxy=(0.0, 0.0)):
        uv, z = projiziere(X[:, :3], rv, t, f, k1, cx, cy); uv2, _ = projiziere(X[:, :3] + 0.2 * X[:, 3:6], rv, t, f, k1, cx, cy)
        dd = uv2 - uv; nang = (np.degrees(np.arctan2(dd[:, 1], dd[:, 0])) + 90.0) % 180.0; b = (nang / (180.0 / NB)).astype(int) % NB   # Gradient steht senkrecht zur Kante
        uv = uv + np.asarray(dxy); r = np.empty(len(X), np.float32)
        for k in range(NB):
            j = b == k
            if j.any(): r[j] = bilin(D[k], uv[j])
        aus = (z <= 1) | (uv[:, 0] < 0) | (uv[:, 0] > W - 1) | (uv[:, 1] < 0) | (uv[:, 1] > H - 1)    # ausserhalb = gekappt (vorher Randwert per bilin-Klemmung: Optimierer floh aus dem Bild, Test 2026-11-04 24 Grad)
        r[aus] = kap; return r, uv
    def bewerten(rv, t, f, sel, D):
        X = Pk[sel]; tr = lambda dx, dy: float((abstand(D, X, rv, t, f, (dx, dy))[0] <= a.tol * L).mean())
        t_ = tr(0, 0); zf = max(tr(0.04 * W, 0), tr(-0.04 * W, 0), tr(0, 0.04 * H), tr(0, -0.04 * H)); return t_, zf, abstand(D, X, rv, t, f)[1]
    D_fein = feld(max(1.0, W / 900)); sel0 = sichtbar(Pk, Pf, rv0, t0, f0, k1, cx, cy, W, H)
    if sel0.sum() < 200: return dict(ok=False, grund=f"nur {int(sel0.sum())} LoD2-Kantenpunkte sichtbar"), None, None
    tr0, zf0, uv0 = bewerten(rv0, t0, f0, sel0, D_fein)
    q = np.r_[rv0, t0, np.log(f0)]; sd = np.r_[[np.radians(a.sigma_dreh)] * 3, [a.sigma_lage] * 3, a.sigma_f]; sel = sel0
    stufen = [W / 150, W / 400, max(1.0, W / 900)] + [max(1.0, W / 900)] * int(getattr(a, "nach", 1))
    for glatt in stufen:                                                                                     # grob -> fein
        D = feld(glatt); X = Pk[sel]
        def res(p):
            r = abstand(D, X, p[:3], p[3:6], np.exp(p[6]))[0] / (a.tol * L); return np.r_[r / np.sqrt(len(X)) * 10, (p - np.r_[rv0, t0, np.log(f0)]) / sd]
        q = least_squares(res, q, loss=getattr(a, "loss", "cauchy"), f_scale=float(getattr(a, "f_scale", 0.5)), x_scale=sd, max_nfev=(200 if glatt <= max(1.0, W / 900) else 60), diff_step=1e-4).x
        sel = sichtbar(Pk, Pf, q[:3], q[3:6], np.exp(q[6]), k1, cx, cy, W, H)
    tr1, zf1, uv1 = bewerten(q[:3], q[3:6], np.exp(q[6]), sel, D_fein)
    ok = tr1 >= a.min_treffer and tr1 - zf1 >= a.min_kontrast
    Rn, _ = cv2.Rodrigues(q[:3]); R0, _ = cv2.Rodrigues(rv0); dreh = float(np.degrees(np.arccos(np.clip((np.trace(Rn @ R0.T) - 1) / 2, -1, 1))))
    C0 = -R0.T @ t0; C1 = -Rn.T @ q[3:6]
    vis = (img * 0.5).astype(np.uint8)
    for uv, col in ((uv0, (0, 0, 255)), (uv1, (0, 230, 0))):
        for x, y in uv[::2].astype(int): cv2.circle(vis, (int(x), int(y)), 1, col, -1)
    cv2.putText(vis, f"vorher {tr0:.2f}/{zf0:.2f}  nachher {tr1:.2f}/{zf1:.2f}  {'OK' if ok else 'DURCHGEFALLEN'}", (10, 32), 0, 0.9, (255, 255, 255), 2)
    r = dict(ok=bool(ok), treffer_vorher=round(tr0, 3), zufall_vorher=round(zf0, 3), treffer=round(tr1, 3), zufall=round(zf1, 3), kontrast=round(tr1 - zf1, 3),
             kantenpunkte=int(sel.sum()), dreh_grad=round(dreh, 2), lage_m=round(float(np.linalg.norm(C1 - C0)), 2), f_faktor=round(float(np.exp(q[6]) / f0), 4))
    neu = dict(K, rvec=q[:3].tolist(), t=q[3:6].tolist(), f_px=float(np.exp(q[6]) / s), standort_xyz=[round(float(x), 3) for x in C1])
    return r, neu, vis


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos"); ap.add_argument("--stl"); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--radius", type=float, default=70.0); ap.add_argument("--schritt", type=float, default=0.1); ap.add_argument("--px", type=int, default=1400)
    ap.add_argument("--tol", type=float, default=0.005); ap.add_argument("--kappe", type=float, default=0.03)
    ap.add_argument("--sigma-dreh", type=float, default=3.0); ap.add_argument("--sigma-lage", type=float, default=2.0); ap.add_argument("--sigma-f", type=float, default=0.15)
    ap.add_argument("--loss", default="cauchy", help="Verlust im Ausgleich (Beweis 2026-11-04: soft_l1/1.0 blieb 6 px daneben, cauchy/0.5 + 1 Nachstufe 0,5 px)"); ap.add_argument("--f-scale", type=float, default=0.5); ap.add_argument("--nach", type=int, default=1, help="zusaetzliche feine Durchgaenge")
    ap.add_argument("--min-treffer", type=float, default=0.4); ap.add_argument("--min-kontrast", type=float, default=0.15); a = ap.parse_args()
    import trimesh
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    aus = os.path.join(od, "audit", "kamera_lod2"); os.makedirs(aus, exist_ok=True); wahl = set(a.fotos.split(",")) if a.fotos else None
    m = trimesh.load(a.stl or os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3); T_std = np.array([-c[0], -c[1], -m.bounds[0, 2]])
    cache = {}; erg = {}
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]; KK = json.load(open(kp)); K = KK.get("kamera_vor_lod2") or KK.get("kamera")
        if not K or (wahl and nr not in wahl): continue
        fp = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
        if not fp: continue
        T_ = np.array(K.get("rahmen_verschiebung", T_std), float); key = tuple(np.round(T_, 3))
        if key not in cache: polys = lod2_szene(obj, od, a.radius, T_); cache[key] = (kanten(polys, a.schritt), flaechen_netz(polys)); print(f"LoD2: {len(polys)} Flaechen, {len(cache[key][0])} Kantenpunkte (Rahmen T_ {list(key)})", flush=True)
        Pk, Pf = cache[key]; r, neu, vis = nachfuehren(K, cv2.imread(fp[0]), Pk, Pf, a); erg[nr] = r; print(f"  {nr}: {'OK  ' if r['ok'] else 'NEIN'} {r}", flush=True)
        if vis is not None: cv2.imwrite(os.path.join(aus, nr + ".jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if a.schreiben:
            KK.setdefault("kamera_vor_lod2", K); tor = dict(r, werkzeug="kamera_lod2_nachfuehren.py", annahmen={k: v for k, v in vars(a).items() if k not in ("objekt", "fotos", "schreiben", "stl")})
            KK["kamera"] = dict(neu, lod2_tor=tor) if r["ok"] else dict(K, lod2_tor=tor); json.dump(KK, open(kp, "w"), indent=1, ensure_ascii=False)
    n_ok = sum(1 for r in erg.values() if r["ok"])
    json.dump(dict(bestanden=n_ok, geprueft=len(erg), kameras=erg, annahmen={k: v for k, v in vars(a).items()}), open(os.path.join(od, "audit", "kamera_lod2.json"), "w"), indent=1)
    print(f"LoD2-Nachfuehrung: {n_ok} von {len(erg)} Kameras bestanden -> audit/kamera_lod2.json, audit/kamera_lod2/<foto>.jpg")


if __name__ == "__main__":
    main()
