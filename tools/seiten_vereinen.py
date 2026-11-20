#!/usr/bin/env python3
"""seiten_vereinen.py <modell_A> <modell_B> <db.db> --aus <ordner> [--min-paare 60] [--rel 0.02]

Zwei GETRENNT gerechnete Seitenmodelle eines Baus (tools/seiten_erkennen.py --streng: Vorder- und Rueckseite ohne echte gemeinsame Punkte) zueinander legen.
Anlass Martinstor 19.11.2026. Gedanke: die Verwechslung ist selbst eine Messung.
  1. GEKLAPPTE LAGE: die Bildpaare zwischen A und B in der URSPRUNGS-Datenbank (auch die fuer den Mapper geloeschten) verbinden 3D-Punkte beider Modelle. Sie zeigen
     aehnliche, aber verschiedene Waende; die beste Aehnlichkeitsabbildung (Sim3, RANSAC, Lot erhalten) legt die B-Wand AUF die A-Wand, Kameras auf derselben Seite.
     Daraus kommen Massstab und Lot von B.
  2. ACHSE AUS DEM BAU: bei einem oben drehsymmetrischen Bau entsteht die geklappte Lage aus der wahren durch eine halbe Drehung um die senkrechte Mittelachse.
     Die Achse ist die Stelle der HOECHSTEN schlanken Bauteile (Helmstange) in der DICHTEN Wolke (oberstes Band, Funktion stange); Dachende/alle hohen Punkte liegen zur Kameraseite verschoben.
     Achse = Mittel der beiden Modelle; ihr Abstand voneinander ist die eingebaute Probe ('achse_einigkeit'; Martinstor 0,2 m = 0,4 % der Bauhoehe).
     NICHT die Mitte des Kataster-Grundrisses nehmen: die LoD2-Ausrichtung lag laengs der Strasse 0,9 m daneben, die Dachflaechen kreuzten sich (Nutzerbild 19.11.).
  3. DREHEN: B_wahr = geklappte Lage, waagerecht an der Achse gespiegelt-gedreht (x -> 2a - x).
  4. PRUEFUNGEN (jede einzeln im Ergebnis, 'ok' nur wenn alle bestehen):
     - achse_einigkeit <= 1,5 % der Bauhoehe
     - blick: Kameras von B blicken nach dem Drehen > 120 Grad gegen die von A (vorher < 60 Grad)
     - flanke: unsymmetrische Nachbarbauten (Punkte seitlich neben der Wand) liegen in A und im gedrehten B auf DERSELBEN Flanke; im geklappten B auf der anderen.
       Ohne einseitigen Nachbarn ist die Probe 'nicht bewertbar' (kein Fehler).
     - dach: die oberen Flaechen beider Seiten laufen an der Achse zusammen, statt sich darunter zu kreuzen (Hoehe, in der jede Flaeche die Achse erreicht, gegen die Bauhoehe).
Ausgabe <aus>/vereinen.json: Abbildung B -> A-System (s, R, t fuer die geklappte Lage; 'achse_punkt', 'lot' fuer die Drehung; fertige 4x4-Matrix 'B_nach_A'), Pruefwerte, urteil.
rc 0 = vereint und geprueft, rc 3 = Pruefung nicht bestanden (nichts uebernehmen, Seiten einzeln ausrichten), rc 2 = zu wenige Verbindungen.
GRENZEN: setzt oben Drehsymmetrie voraus (sonst gaebe es die Verwechslung meist nicht); Genauigkeit quer zur Wand = Genauigkeit der Achse; Lage laengs der Wand aus den
Wandpaaren (Martinstor Rest 13 cm). Alle Laengen in Einheiten des Modells A (Meter erst nach der Ausrichtung von A)."""
import sys, os, json, sqlite3, collections, argparse
import numpy as np

MAXID = 2147483647


def umeyama(P, Q):
    mp, mq = P.mean(0), Q.mean(0); H = (Q - mq).T @ (P - mp) / len(P); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / max(1e-12, ((P - mp) ** 2).sum(1).mean()); return s, R, mq - s * R @ mp


def lot_aus_kameras(RA):
    """Lot = die Richtung, auf der die Bild-x-Achsen der Kameras senkrecht stehen (Fotos werden waagerecht gehalten); Vorzeichen: Bild-y zeigt nach unten."""
    up = np.linalg.svd(np.array([r[0] for r in RA]))[2][-1]; return up * -np.sign(np.median(np.array([r[1] for r in RA]) @ up))


def lot_aus_waenden(X, up0, n_max=400000, saat=0):
    """Lot nachschaerfen aus den Normalen ebener, fast senkrechter Flaechen der DICHTEN Wolke (Waende stehen senkrecht): Richtung, auf der alle Wandnormalen senkrecht stehen.
    Anlass Martinstor 19.11.: Kameralot 2,3 Grad verkippt (Turm- und Hauswandnormalen einig auf 0,3-0,8 Grad mit der LoD2-Ausrichtung); bei 60 m Drehhoehe = Meter Versatz am Boden.
    Rueckgabe (lot, Zahl tragender Normalen) oder (up0, 0), wenn zu wenig Waende."""
    from scipy.spatial import cKDTree
    X = np.asarray(X, float); X = X[np.random.default_rng(saat).choice(len(X), min(n_max, len(X)), replace=False)]
    if len(X) < 1000: return up0, 0
    _, I = cKDTree(X).query(X, 16); Nb = X[I] - X[I].mean(1, keepdims=True); w, U = np.linalg.eigh(np.einsum('nki,nkj->nij', Nb, Nb))
    n = U[:, :, 0]; N = n[(w[:, 0] / (w[:, 1] + 1e-30) < 0.02) & (np.abs(n @ up0) < 0.25)]; u = up0
    for grenze in (0.25, 0.1, 0.1, 0.1):
        k = np.abs(N @ u) < grenze
        if k.sum() < 300: return up0, 0
        u = np.linalg.eigh(N[k].T @ N[k])[1][:, 0]; u = u * np.sign(u @ up0)
    return u, int(k.sum())


def geklappt(P, Q, up, rel=0.02, runden=20000, saat=0):
    """Beste Sim3 P -> Q, die das Lot erhaelt (< 20 Grad). Rueckgabe (s, R, t, inlier-Maske) oder None."""
    if len(P) < 12: return None
    thr = rel * np.percentile(np.linalg.norm(Q - np.median(Q, 0), axis=1), 50); rng = np.random.default_rng(saat); best = (0, None)
    for _ in range(runden):
        ix = rng.choice(len(P), 3, replace=False); s, R, t = umeyama(P[ix], Q[ix])
        if not np.isfinite(s) or s <= 0 or (R @ up) @ up < 0.94: continue
        inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr
        if inl.sum() > best[0]: best = (int(inl.sum()), inl)
    if best[1] is None: return None
    inl = best[1]
    for _ in range(3): s, R, t = umeyama(P[inl], Q[inl]); inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr
    return s, R, t, inl


def spitze(X, mitte, H, boden, anteil=0.92):
    """Waagerechte Lage der hoechsten Bauteile: Punkte im Umkreis 0,35 H um die Wandmitte, oberhalb von `anteil` der Hoehe des hoechsten dichten Bereichs. (Lage xy, Zahl, Hoehe)."""
    nah = X[np.linalg.norm(X[:, :2] - mitte, axis=1) < 0.35 * H]
    if len(nah) < 50: return None
    oben = np.percentile(nah[:, 2], 99.7); k = nah[:, 2] > boden + anteil * (oben - boden)
    return (np.median(nah[k, :2], 0), int(k.sum()), float(oben - boden)) if k.sum() >= 20 else None


def stange(X, wm, H, boden, band=0.025, quantil=99.9):
    """Achse aus der HELMSTANGE / dem hoechsten schlanken Bauteil der DICHTEN Wolke: Punkte im Umkreis 0,35 H um die Wandmitte, oberstes Band (2,5 % H unter dem
    99,9-%-Hoechstwert). Anlass Martinstor 19.11.: Dachende und 'alle hohen Punkte' lagen 0,7-2,3 m zur Kameraseite verschoben (die abgewandte Dachhaelfte fehlt in jeder
    Seitenwolke); das oberste Band traf die von Hand gemessene Stange auf 0,1 m. Rueckgabe (Achse xy, Hoehe ueber Boden, Zahl, Streuung xy) oder None."""
    nah = X[np.linalg.norm(X[:, :2] - wm, axis=1) < 0.35 * H]
    if len(nah) < 200: return None
    z9 = np.percentile(nah[:, 2], quantil); k = nah[:, 2] > z9 - band * H
    if k.sum() < 30: return None
    xy = nah[k, :2]; m = np.median(xy, 0); return m, float(z9 - boden), int(k.sum()), float(np.median(np.linalg.norm(xy - m, axis=1)))


def achse_aus_dach(X, wm, v, H, boden, schichten=40):
    """Achse aus der DACHFLAECHE statt aus Einzelpunkten der Spitze (die sind in der duennen Wolke laengs der Sehstrahlen verschmiert: Martinstor 2,4 m daneben, und beide
    Modelle irren in der geklappten Lage GLEICH - 'Einigkeit' 0,17 m war wertlos). Je Hoehenschicht ueber der Wandoberkante die dichteste Lage u laengs der Blickrichtung;
    die geneigte Flaeche ist eine Gerade u(z). Sie endet am First/an der Spitze: oberste Schicht, die noch auf der Geraden liegt. Dort liegt die Achse.
    Rueckgabe (Achse xy, Endhoehe ueber Boden, Zahl der Schichten auf der Geraden) oder None (kein geneigtes Dach erkennbar)."""
    q = np.array([-v[1], v[0]]); d = X[:, :2] - wm; z = X[:, 2] - boden; oben = np.percentile(z[(np.linalg.norm(d, axis=1) < 0.35 * H)], 99.7) if len(X) else 0
    if oben < 1.1 * H: return None
    m0 = (np.abs(d @ q) < 0.08 * H) & (np.abs(d @ v) < 0.6 * H) & (z > 1.02 * H); u = (d @ v)[m0]; zz = z[m0]; qq = (d @ q)[m0]; dz = (oben - 1.02 * H) / schichten; L = []
    for i in range(schichten):
        k = (zz >= 1.02 * H + i * dz) & (zz < 1.02 * H + (i + 1) * dz)
        if k.sum() < 15: L.append((1.02 * H + (i + 0.5) * dz, np.nan, 0)); continue
        h, e = np.histogram(u[k], bins=np.linspace(-0.6 * H, 0.6 * H, 241)); L.append((1.02 * H + (i + 0.5) * dz, e[np.argmax(h)] + 0.0025 * H, int(k.sum())))
    L = np.array(L); g = np.isfinite(L[:, 1])
    if g.sum() < 6: return None
    best = (0, None)                                                               # Gerade durch zwei Schichten, die meisten Schichten innerhalb 1 % H
    ix = np.where(g)[0]
    for i in ix:
        for j in ix:
            if j <= i + 2: continue
            b_ = (L[j, 1] - L[i, 1]) / (L[j, 0] - L[i, 0]); a_ = L[i, 1] - b_ * L[i, 0]; inl = g & (np.abs(a_ + b_ * L[:, 0] - L[:, 1]) < 0.01 * H)
            if inl.sum() > best[0] and abs(b_) > 0.05: best = (int(inl.sum()), (a_, b_, inl))
    if best[1] is None or best[0] < 6: return None
    a_, b_, inl = best[1]; b_, a_ = np.polyfit(L[inl, 0], L[inl, 1], 1); ende = L[inl, 0].max() + 0.5 * dz
    return wm + (a_ + b_ * ende) * v + np.median(qq[zz > ende - 4 * dz]) * q if (zz > ende - 4 * dz).any() else wm + (a_ + b_ * ende) * v, float(ende), best[0]


def dachprobe(X, achse, v, H, boden, oben):
    """Hoehe (ueber Boden), in der die geneigte obere Flaeche die Achse erreicht: je Hoehenschicht die dichteste Lage laengs der Blickrichtung v, Gerade durch die Schichten
    zwischen Wandoberkante und Spitze, Schnitt mit der Achse. None, wenn keine geneigte Flaeche erkennbar ist (Flachdach)."""
    q = np.array([-v[1], v[0]]); d = X[:, :2] - achse; k = (np.abs(d @ q) < 0.06 * H) & (np.abs(d @ v) < 0.5 * H); X = X[k]; u = (X[:, :2] - achse) @ v; z = X[:, 2] - boden
    zz, uu = [], []
    for z0 in np.linspace(1.0 * H, 0.97 * oben, 12)[:-1]:
        m = (z >= z0) & (z < z0 + (0.97 * oben - H) / 11)
        if m.sum() < 30: continue
        h, e = np.histogram(u[m], bins=np.linspace(-0.5 * H, 0.5 * H, 201)); zz.append(z0); uu.append(e[np.argmax(h)])
    if len(zz) < 4: return None
    zz, uu = np.array(zz), np.array(uu); b, a = np.polyfit(zz, uu, 1)
    return float(-a / b) if abs(b) > 0.03 else None


def flanke(X, achse, v, H, boden):
    """Punkte seitlich neben dem Bau (0,2-0,5 H quer zur Blickrichtung, bis 0,5 H hoch, nahe der Wandtiefe): (Zahl links, Zahl rechts) bezogen auf den festen Quervektor."""
    q = np.array([-v[1], v[0]]); d = X[:, :2] - achse; z = X[:, 2] - boden; k = (z > 0.1 * H) & (z < 0.5 * H) & (np.abs(d @ v) < 0.25 * H)
    return int((k & (d @ q > 0.2 * H) & (d @ q < 0.5 * H)).sum()), int((k & (d @ q < -0.2 * H) & (d @ q > -0.5 * H)).sum())


def vereinen(XA, CA, VA, XB, CB, VB, P, Q, up, rel=0.02, DA=None, DB=None):
    """XA/XB Punkte, CA/CB Kamerazentren, VA/VB Blickrichtungen (je Modell im eigenen System), P/Q gemeinsame Punktpaare (B, A), up = Lot von A. -> Ergebnis-dict."""
    g = geklappt(P, Q, up, rel)
    if g is None: return dict(urteil="keine geklappte Lage (zu wenige/uneinige Punktpaare)", ok=False)
    s, R, t, inl = g; e1 = np.cross(up, [1.0, 0, 0]); e1 /= np.linalg.norm(e1); E = np.array([e1, np.cross(up, e1), up]); lok = lambda X: np.asarray(X) @ E.T
    a_ = lok(XA); b_ = lok(s * np.asarray(XB) @ R.T + t); ca = lok(CA); cb = lok(s * np.asarray(CB) @ R.T + t); q = lok(Q[inl]); boden = float(np.percentile(ca[:, 2], 20))
    wm = np.median(q[:, :2], 0); H = float(np.percentile(q[:, 2], 98) - boden); sa, sb = spitze(a_, wm, H, boden), spitze(b_, wm, H, boden)
    erg = dict(paare=int(len(P)), inlier=int(inl.sum()), rest=float(np.median(np.linalg.norm(s * P[inl] @ R.T + t - Q[inl], axis=1))), massstab=float(s), wandhoehe=H, s=float(s), R=R.tolist(), t=t.tolist(), lot=up.tolist())
    if sa is None or sb is None: erg.update(urteil="keine hoechsten Bauteile in beiden Modellen gefunden - Achse unbestimmt", ok=False); return erg
    v = wm - np.median(ca[:, :2], 0); v /= np.linalg.norm(v); hoch = max(sa[2], sb[2])
    if DA is not None: a_d, b_d = lok(DA), lok(s * np.asarray(DB) @ R.T + t)      # dichte Wolken (genauer) fuer Achse, Dach und Flanke
    else: a_d, b_d = a_, b_
    st = [stange(X, wm, H, boden) for X in (a_d, b_d)] if DA is not None else [None, None]
    da_, db_ = (None, None) if all(st) else (achse_aus_dach(a_d, wm, v, H, boden), achse_aus_dach(b_d, wm, v, H, boden))
    if all(st):                                                                    # beide Seiten: oberstes Band; sieht eine Seite die Spitze deutlich hoeher, zaehlt sie doppelt
        w = np.array([2.0 if st[0][1] > st[1][1] + 0.05 * H else 1.0, 2.0 if st[1][1] > st[0][1] + 0.05 * H else 1.0])
        achse = (w[0] * st[0][0] + w[1] * st[1][0]) / w.sum(); einig = float(np.linalg.norm(st[0][0] - st[1][0])); erg["achse_aus"] = "helmstange_dicht"
        erg["stange"] = dict(a=dict(hoehe=st[0][1], n=st[0][2], streuung=st[0][3]), b=dict(hoehe=st[1][1], n=st[1][2], streuung=st[1][3]))
    elif da_ is not None and db_ is not None: achse = (da_[0] + db_[0]) / 2; einig = float(np.linalg.norm(da_[0] - db_[0])); erg["achse_aus"] = "dachflaeche" + ("_dicht" if DA is not None else "_duenn") + " (unsicher: Dachende liegt zur Kameraseite verschoben)"
    else: achse = (sa[0] + sb[0]) / 2; einig = float(np.linalg.norm(sa[0] - sb[0])); erg["achse_aus"] = "hoechste_punkte (unsicher: laengs der Sehstrahlen verschmiert)"
    a_, b_ = a_d, b_d
    dreh = lambda X: np.c_[2 * achse - X[:, :2], X[:, 2]]
    b2 = dreh(b_)
    wA = lok(np.asarray(VA) @ np.eye(3))[:, :2]; wB = (np.asarray(VB) @ R.T) @ E.T; wB = wB[:, :2]; mA = np.median(wA, 0); mB = np.median(wB, 0); cosw = float(mA @ mB / max(1e-9, np.linalg.norm(mA) * np.linalg.norm(mB)))
    blick_vor = float(np.degrees(np.arccos(np.clip(cosw, -1, 1)))); blick_nach = 180.0 - blick_vor
    fa, fbd, fbg = flanke(a_, achse, v, H, boden), flanke(b2, achse, v, H, boden), flanke(b_, achse, v, H, boden)
    seite = lambda f: 0 if max(f) < 200 or max(f) < 2.5 * max(1, min(f)) else (1 if f[0] > f[1] else -1)
    fl = "nicht bewertbar" if seite(fa) == 0 or seite(fbd) == 0 else ("gleich" if seite(fa) == seite(fbd) else "verschieden")
    da, db = dachprobe(a_, achse, v, H, boden, sa[2]), dachprobe(b2, achse, -v, H, boden, sb[2])
    dach = None if da is None or db is None else dict(a=da / hoch, b=db / hoch)
    pr = dict(achse_einigkeit=einig / hoch, blick_vorher=blick_vor, blick_nachher=blick_nach, flanke=fl, flanke_punkte=dict(a=fa, b_gedreht=fbd, b_geklappt=fbg), dach=dach, tiefe=float(2 * abs((achse - wm) @ v)) / hoch)
    gruende = []
    if pr["achse_einigkeit"] > 0.015: gruende.append(f"die Modelle sind sich ueber die Achse nicht einig ({100 * pr['achse_einigkeit']:.1f} % der Bauhoehe, Grenze 1,5 %)")
    if blick_vor > 60: gruende.append(f"die geklappte Lage ist keine Klappung (Kameras {blick_vor:.0f} Grad auseinander statt < 60)")
    if fl == "verschieden": gruende.append("Nachbarbau liegt in beiden Seitenmodellen auf verschiedenen Flanken")
    if dach and min(dach["a"], dach["b"]) < 0.80: gruende.append(f"Dachflaechen erreichen die Achse schon bei {100 * min(dach['a'], dach['b']):.0f} % der Bauhoehe (sie kreuzen sich, Achse liegt falsch)")
    # fertige Abbildung B -> A: X_A = E^T [ D (E (s R X_B + t)) ]  mit D = Drehung 180 Grad um die Achse (waagerecht x -> 2a - x)
    D4 = np.eye(4); D4[0, 0] = D4[1, 1] = -1; D4[:2, 3] = 2 * achse; E4 = np.eye(4); E4[:3, :3] = E; S4 = np.eye(4); S4[:3, :3] = s * R; S4[:3, 3] = t
    M = np.linalg.inv(E4) @ D4 @ E4 @ S4; ap = E.T @ np.array([achse[0], achse[1], boden])
    erg.update(achse_punkt=ap.tolist(), bauhoehe=hoch, pruefung=pr, B_nach_A=M.tolist(), ok=not gruende, urteil="vereint" if not gruende else "; ".join(gruende)); return erg


def lies(p):
    import pycolmap
    r = pycolmap.Reconstruction(p); ims = [im for im in r.images.values() if im.has_pose]
    return ({im.name: np.array([q.point3D_id if q.has_point3D() else -1 for q in im.points2D], dtype=np.int64) for im in ims}, {i: q.xyz for i, q in r.points3D.items()},
            np.array([im.projection_center() for im in ims]), [im.cam_from_world().rotation.matrix() for im in ims])


def ply_punkte(p, max_n=3000000):
    """xyz einer COLMAP-fused.ply (binaer, 27 Byte je Punkt), hoechstens max_n (feste Zufallsauswahl)."""
    f = open(p, "rb"); n = 0
    while True:
        l = f.readline().decode(errors="replace").strip()
        if l.startswith("element vertex"): n = int(l.split()[-1])
        if l == "end_header" or not l: break
    d = np.frombuffer(f.read(n * 27), dtype=np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)]))["p"].astype(np.float64)
    return d[np.random.default_rng(0).permutation(len(d))[:max_n]] if len(d) > max_n else d


def punktpaare(db, PA, PB, min_inlier=15):
    """Gemeinsame 3D-Punkte zweier Modelle ueber die bestaetigten Bildpaare der Datenbank: Liste (Punkt-ID B, Punkt-ID A), je B-Punkt der haeufigste A-Punkt."""
    d = sqlite3.connect(f"file:{db}?mode=ro", uri=True); nm = dict(d.execute("select image_id, name from images")); kor = {}; n = 0
    for pid, data in d.execute("select pair_id, data from two_view_geometries where rows >= ?", (min_inlier,)):
        x, y = nm[pid // MAXID], nm[pid % MAXID]; m = np.frombuffer(data, np.uint32).reshape(-1, 2)
        if x in PB and y in PA and x not in PA: x, y, m = y, x, m[:, ::-1]
        if not (x in PA and y in PB) or y in PA or x in PB: continue
        m = m[(m[:, 0] < len(PA[x])) & (m[:, 1] < len(PB[y]))]          # 20.11.: Modelle aus gekuerzter Merkmals-DB (FlexGlue, 6000 je Bild) - Nummern gleich, Rest fehlt
        qa, qb = PA[x][m[:, 0]], PB[y][m[:, 1]]; ok = (qa >= 0) & (qb >= 0); n += 1
        for u, w in zip(qb[ok], qa[ok]): kor.setdefault(int(u), collections.Counter())[int(w)] += 1
    return [(u, c.most_common(1)[0][0]) for u, c in kor.items()], n


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("db"); ap.add_argument("--aus", required=True); ap.add_argument("--min-paare", type=int, default=60); ap.add_argument("--rel", type=float, default=0.02)
    ap.add_argument("--dicht-a", help="dichte Wolke von A (fused.ply im System von Modell A): Achse, Dach- und Flankenprobe daraus (genauer als die duenne Wolke)"); ap.add_argument("--dicht-b", help="dichte Wolke von B (im System von Modell B)")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True); PA, XA, CA, RA = lies(a.a); PB, XB, CB, RB = lies(a.b); kor, n = punktpaare(a.db, PA, PB)
    print(f"A {len(PA)} Bilder, {len(XA)} Punkte | B {len(PB)} Bilder, {len(XB)} Punkte | Bildpaare A-B {n}, gemeinsame Punkte {len(kor)}", flush=True)
    if len(kor) < a.min_paare:
        json.dump(dict(ok=False, urteil=f"nur {len(kor)} gemeinsame Punkte (unter {a.min_paare}) - Seiten einzeln ausrichten"), open(os.path.join(a.aus, "vereinen.json"), "w"), indent=1); print("WARNUNG: zu wenige Verbindungen zwischen den Seitenmodellen"); return 2
    P = np.array([XB[u] for u, _ in kor]); Q = np.array([XA[w] for _, w in kor]); up = lot_aus_kameras(RA)
    DA = ply_punkte(a.dicht_a) if a.dicht_a and a.dicht_b else None; DB = ply_punkte(a.dicht_b) if DA is not None else None; lot_info = dict(aus="kameras")
    if DA is not None:
        u2, nw = lot_aus_waenden(DA, up)
        if nw: lot_info = dict(aus="waende_dicht", normalen=nw, korrektur_grad=float(np.degrees(np.arccos(np.clip(u2 @ up, -1, 1))))); up = u2
        print(f"Lot aus {lot_info['aus']}" + (f": {nw} Wandnormalen, {lot_info['korrektur_grad']:.2f} Grad neben dem Kameralot" if nw else " (zu wenig Waende in der dichten Wolke)"), flush=True)
    erg = vereinen(np.array(list(XA.values())), CA, np.array([r[2] for r in RA]), np.array(list(XB.values())), CB, np.array([r[2] for r in RB]), P, Q, up, a.rel, DA, DB)
    erg.update(modell_a=os.path.abspath(a.a), modell_b=os.path.abspath(a.b), lot_herkunft=lot_info); json.dump(erg, open(os.path.join(a.aus, "vereinen.json"), "w"), indent=1); pr = erg.get("pruefung") or {}
    if "inlier" in erg: print(f"geklappte Lage: {erg['inlier']} von {erg['paare']} Punktpaaren, Rest {erg['rest']:.4f}, Massstab B->A {erg['massstab']:.3f}")
    if pr: print(f"Achse aus {erg.get('achse_aus')}: Einigkeit der Modelle {100 * pr['achse_einigkeit']:.2f} % der Bauhoehe | Blick vorher {pr['blick_vorher']:.0f} Grad, nachher {pr['blick_nachher']:.0f} | Flanke {pr['flanke']} {pr['flanke_punkte']} | Dach {pr['dach']} | Tiefe {pr['tiefe']:.2f} der Bauhoehe")
    print(("SEITEN VEREINT: " if erg["ok"] else "WARNUNG SEITEN NICHT VEREINT: ") + erg["urteil"]); return 0 if erg["ok"] else 3


if __name__ == "__main__": sys.exit(main())
