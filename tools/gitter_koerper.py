#!/usr/bin/env python3
"""gitter_koerper.py - erster geschlossener, druckbarer Rohkoerper AUS dem Kantengitter (Gitter -> Ebenen -> Grundriss -> Koerper).
Beweis, dass die Kette Gitter -> Druck durchgeht. Keine Objektkonstanten: alles aus SEG.json (segmente/helme/saeulen) abgeleitet;
Nicht-Belegtes steht als ANNAHME in koerper/annahmen.json.

  bauen   (venv rcpark, manifold3d):  gitter_koerper.py bauen SEG.json AUSDIR [--name rohkoerper_v7]
  pruefen (venv-seg, torch/cv2):      gitter_koerper.py pruefen AUSDIR WOLKE.npz KAM.json BILDDIR AUDITDIR [--name ...] [--foto ip_IMG_6261.jpg]

Stufen (bauen): 1 Hauptebenen (Fassaden-/Giebelebenen 1D-RANSAC auf Segment-Stuetzpunkten, Toleranz 8 cm, >= 30 m je Ebene; Dachebene aus
geneigten Segmenten; First = hoechste lange horizontale Kante; Traufe = hoechste lange horizontale Fassadenkante UND Schnitt Dachebene/Fassade),
2 Grundriss (Front/Enden aus Ebenen, Rueckseite ANNAHME: Firstspiegel), 3 Koerper (Rumpf, Satteldach, Staffelgiebel-Polygon wo Steiger belegt,
Saeulen-Zylinder, Helm-Pyramide, Arkaden-Bogenausschnitte), Export STL in m und 1:87 mm.
Stufen (pruefen): wasserdicht/Volumen, Wolke->Oberflaeche je Hoehenband (GPU knn), Render vorn/Seite/schraeg, Kanten-Overlay auf Foto."""
import sys, os, json, math
import numpy as np

TOL = 0.08          # Ebenen-Toleranz (m)
MIN_EBENE = 30.0    # Segmentlaenge je Ebene (m)
MIN_SCHWACH = 10.0  # schwach belegte Ebene (Enden)
H0 = 1000.0 / 87.0  # m -> mm bei 1:87


# ----------------------------------------------------------------------------- Hilfen
def lade(seg_json):
    d = json.load(open(seg_json)); S = d["segmente"]
    P0 = np.array([s[0] for s in S], float); P1 = np.array([s[1] for s in S], float)
    L = np.linalg.norm(P1 - P0, axis=1); ok = L > 1e-6; P0, P1, L = P0[ok], P1[ok], L[ok]
    Q = np.array([s[2] for s in S])[ok]
    return d, P0, P1, L, (P1 - P0) / L[:, None], Q


def stuetzpunkte(P0, P1, L, schritt=0.25):
    """Stuetzpunkte entlang der Segmente (alle `schritt` m), jeder mit Gewicht = vertretene Laenge."""
    pts, w = [], []
    for a, b, l in zip(P0, P1, L):
        k = max(2, int(math.ceil(l / schritt)) + 1); t = np.linspace(0, 1, k)[:, None]
        pts.append(a + (b - a) * t); w.append(np.full(k, l / k))
    return np.vstack(pts), np.concatenate(w)


def ransac_1d(x, w, tol, min_gewicht, max_ebenen=12):
    """1D-RANSAC fuer parallele Ebenen mit bekannter Normale: Offset mit maximalem Stuetzgewicht in +-tol, dann Inlier weg, wiederholen.
    Verfeinerung: gewichteter Mittelwert der Inlier (3 Runden Mean-Shift)."""
    x = x.copy(); w = w.copy(); frei = np.ones(len(x), bool); eb = []
    for _ in range(max_ebenen):
        if frei.sum() == 0: break
        xs = x[frei]; ws = w[frei]
        # Kandidaten = alle Stuetzpunkte (deterministisch statt Zufall: vollstaendige Suche in 1D)
        order = np.argsort(xs); xs_o = xs[order]; ws_o = ws[order]; cw = np.r_[0, np.cumsum(ws_o)]
        lo = np.searchsorted(xs_o, xs_o - tol, "left"); hi = np.searchsorted(xs_o, xs_o + tol, "right")
        g = cw[hi] - cw[lo]; i = int(np.argmax(g))
        if g[i] < min_gewicht: break
        c = xs_o[i]
        for _ in range(3):
            m = np.abs(xs - c) <= tol
            c = float(np.sum(xs[m] * ws[m]) / max(np.sum(ws[m]), 1e-9))
        m = np.abs(xs - c) <= tol
        idx = np.where(frei)[0][m]
        eb.append({"offset": c, "laenge": float(ws[m].sum()), "n_stuetz": int(m.sum()), "idx": idx})
        frei[idx] = False
    return eb


def hauptrichtung(dn, L, horiz):
    """Fassadenrichtung u (xy) aus dem laengengewichteten Doppelwinkel der horizontalen Segmente, Start im staerksten 5-Grad-Bin, Verfeinerung +-10 Grad."""
    a = np.arctan2(dn[:, 1], dn[:, 0]); deg = np.degrees(a) % 180
    h, e = np.histogram(deg[horiz], bins=36, range=(0, 180), weights=L[horiz]); th0 = (e[np.argmax(h)] + 2.5)
    d = ((deg - th0 + 90) % 180) - 90; m = horiz & (np.abs(d) < 10)
    th = 0.5 * math.atan2(np.sum(L[m] * np.sin(2 * a[m])), np.sum(L[m] * np.cos(2 * a[m])))
    u = np.array([math.cos(th), math.sin(th), 0.0]); n = np.array([-u[1], u[0], 0.0])
    return u, n, float(np.degrees(th) % 180)


def zcluster(z, w, tol=0.2, min_gewicht=5.0):
    return [{"z": e["offset"], "laenge": e["laenge"]} for e in ransac_1d(z, w, tol, min_gewicht)]


def cs(poly):
    """CrossSection aus 2D-Polygon, Orientierung automatisch CCW (manifold fuellt positiv)."""
    import manifold3d as m3
    P = np.asarray(poly, float); a = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return m3.CrossSection([P if a > 0 else P[::-1]])


def kreis_ransac(x, y, tol=0.10, iters=300, seed=0, zwang=None):
    """Robuster Kreisfit: 3-Punkt-RANSAC, Inlier < tol, Nachfit (Kasa) auf Inliern. Liefert (cx, cy, R, rms_inlier, anteil_inlier).
    zwang = (cx_min, cx_max, cy_min, cy_max, R_min, R_max): Hypothesen ausserhalb werden verworfen (Bogen: Mittelpunkt nahe Kaempfer/Oeffnungsmitte)."""
    rng = np.random.default_rng(seed); best = None
    for _ in range(iters):
        i = rng.choice(len(x), 3, replace=False); A = np.c_[2 * x[i], 2 * y[i], np.ones(3)]; b = x[i] ** 2 + y[i] ** 2
        try: s = np.linalg.solve(A, b)
        except np.linalg.LinAlgError: continue
        cx, cy = s[0], s[1]; R2 = s[2] + cx * cx + cy * cy
        if R2 <= 0: continue
        R = math.sqrt(R2)
        if zwang and not (zwang[0] <= cx <= zwang[1] and zwang[2] <= cy <= zwang[3] and zwang[4] <= R <= zwang[5]): continue
        m = np.abs(np.hypot(x - cx, y - cy) - R) < tol
        if best is None or m.sum() > best[0]: best = (m.sum(), m)
    if best is None: return None
    m = best[1]; cx, cy, R, rms = kreis_fit(x[m], y[m]); return cx, cy, R, rms, float(m.mean())


def kreis_fit(x, y):
    """Algebraischer Kreisfit (Kasa). Liefert (cx, cy, R, rms)."""
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]; b = x * x + y * y
    s, *_ = np.linalg.lstsq(A, b, rcond=None); cx, cy = s[0], s[1]; R = math.sqrt(max(s[2] + cx * cx + cy * cy, 1e-12))
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - R) ** 2))); return float(cx), float(cy), float(R), rms


# ----------------------------------------------------------------------------- Stufe 1+2: Ebenen und Grundriss
def analysiere(d, P0, P1, L, dn, Q, log):
    A = {}; annahmen = []
    M = (P0 + P1) / 2; horiz = np.abs(dn[:, 2]) < 0.2; vert = np.abs(dn[:, 2]) > 0.9; schr = ~horiz & ~vert
    u, n, th = hauptrichtung(dn, L, horiz); A["u"] = u.tolist(); A["n"] = n.tolist(); A["richtung_grad"] = th
    log(f"Fassadenrichtung u = {np.round(u, 4).tolist()} ({th:.2f} Grad), Normale n = {np.round(n, 4).tolist()}")
    par = horiz & (np.abs(dn @ u) > 0.95); perp = horiz & (np.abs(dn @ n) > 0.95)
    # --- Fassadenebenen (Normale n): Stuetzpunkte aus parallelen horizontalen + vertikalen Segmenten
    m = par | vert; X, w = stuetzpunkte(P0[m], P1[m], L[m]); eb = ransac_1d(X @ n, w, TOL, MIN_EBENE)
    ebenen = []
    for e in eb:
        Xi = X[e["idx"]]; ebenen.append({"typ": "fassade_parallel", "offset": e["offset"], "laenge": e["laenge"],
                                        "z_min": float(Xi[:, 2].min()), "z_max": float(Xi[:, 2].max()),
                                        "along_min": float((Xi @ u).min()), "along_max": float((Xi @ u).max())})
    ebenen.sort(key=lambda e: -e["laenge"])
    for e in ebenen: log(f"  Ebene parallel: offset {e['offset']:.2f} m, Stuetzlaenge {e['laenge']:.0f} m, z {e['z_min']:.1f}..{e['z_max']:.1f}, along {e['along_min']:.1f}..{e['along_max']:.1f}")
    if not ebenen: raise SystemExit("keine Fassadenebene >= 30 m gefunden")
    # --- First: hoechste lange horizontale Kante (parallel)
    Xp, wp = stuetzpunkte(P0[par], P1[par], L[par]); zc = zcluster(Xp[:, 2], wp, 0.2, 5.0)
    first = max(zc, key=lambda c: c["z"]); mz = np.abs(Xp[:, 2] - first["z"]) < 0.2
    off_first = float(np.sum((Xp[mz] @ n) * wp[mz]) / wp[mz].sum()); z_first = first["z"]
    log(f"First: z = {z_first:.2f} m (Kantenlaenge {first['laenge']:.0f} m), offset {off_first:.2f} m")
    # Frontebene = staerkste Fassadenebene auf der dem First abgewandten... = staerkste Ebene insgesamt; Rueckseite spaeter
    front = ebenen[0]; off_front = front["offset"]
    # Laubenrueckwand = naechste Ebene zwischen First und Front mit Stuetzpunkten im Erdgeschoss
    sgn = np.sign(off_front - off_first); mz = (X[:, 2] < 8) & ((X @ n - off_first) * sgn > 0) & ((off_front - X @ n) * sgn > 2.0)
    ebl = ransac_1d((X @ n)[mz], w[mz], TOL * 2, MIN_SCHWACH); laube = sorted(ebl, key=lambda e: -e["laenge"])
    off_laube = laube[0]["offset"] if laube else None
    if laube: ebenen.append({"typ": "laube_rueckwand", "offset": off_laube, "laenge": laube[0]["laenge"], "belegt": laube[0]["laenge"] >= MIN_EBENE}); 
    if laube and laube[0]["laenge"] < MIN_EBENE: annahmen.append({"was": "Laubenrueckwand", "annahme": f"ANNAHME: Rueckwand der Laube bei Offset {off_laube:.2f} m nur schwach belegt ({laube[0]['laenge']:.0f} m vertikale/horizontale Kanten, Toleranz 16 cm)"})
    # --- Traufe (a) hoechste lange horizontale Kante in der Frontebene
    mf = np.abs((Xp @ n) - off_front) < 0.5; zcf = zcluster(Xp[mf, 2], wp[mf], 0.2, 5.0)
    traufe_kante = max(zcf, key=lambda c: c["z"]) if zcf else None
    # --- Dachebene: geneigte Segmente oberhalb der Fassadenkante, Linie in (offset, z) per 1D-RANSAC ueber den Abstand
    Xs, ws = stuetzpunkte(P0[schr], P1[schr], L[schr]); zs0 = (traufe_kante["z"] - 1.0) if traufe_kante else 10.0
    ms = Xs[:, 2] > zs0; Xs, ws = Xs[ms], ws[ms]; o = Xs @ n; z = Xs[:, 2]
    best = None
    rng = np.random.default_rng(0)
    for _ in range(400):
        i, j = rng.choice(len(o), 2, replace=False)
        if abs(o[i] - o[j]) < 0.5: continue
        k = (z[j] - z[i]) / (o[j] - o[i]); b = z[i] - k * o[i]
        if not (0.4 < abs(k) < 4): continue
        dist = np.abs(k * o - z + b) / math.hypot(k, 1); m_in = dist < TOL; g = ws[m_in].sum()
        if best is None or g > best[0]: best = (g, k, b, m_in)
    dach = None
    if best and best[0] >= MIN_EBENE:
        g, k, b, m_in = best; k, b = np.polyfit(o[m_in], z[m_in], 1, w=np.sqrt(ws[m_in]))
        dach = {"steigung": float(k), "achsabschnitt": float(b), "neigung_grad": float(math.degrees(math.atan(abs(k)))), "laenge": float(g),
                "z_an_front": float(k * off_front + b), "z_am_first_offset": float(k * off_first + b)}
        log(f"Dachebene (Front): Neigung {dach['neigung_grad']:.1f} Grad, Stuetzlaenge {g:.0f} m, z an Frontebene {dach['z_an_front']:.2f}, z ueber First-Offset {dach['z_am_first_offset']:.2f} (First-Kante {z_first:.2f})")
    else:
        log("Dachebene: keine Ebene >= 30 m aus geneigten Segmenten")
    if traufe_kante: log(f"Traufe (Kante): hoechste lange horizontale Fassadenkante z = {traufe_kante['z']:.2f} m (Laenge {traufe_kante['laenge']:.0f} m)")
    if dach:
        # Dachflaeche: Steigung aus den geneigten Kanten, Lage durch die First-Kante (35 m belegt). Die geneigten Kanten selbst liegen
        # an den Giebelenden und damit (Staffelgiebel) UEBER der Dachflaeche - ihr Achsabschnitt ist der Giebelueberstand, nicht das Dach.
        k = dach["steigung"]; z_traufe = float(z_first - abs(k) * abs(off_front - off_first)); quelle_traufe = "First-Kante + Dachneigung aus geneigten Kanten, an der Frontebene"
        dach["giebel_ueber_dach_m"] = float(dach["z_am_first_offset"] - z_first); dach["z_traufe_firstgebunden"] = z_traufe
        log(f"Traufe (First-gebunden): z = {z_traufe:.2f} m; freie Dachlinie der geneigten Kanten liegt {dach['giebel_ueber_dach_m']:.2f} m ueber dem First -> Giebelkanten ueber Dachflaeche (Staffelgiebel)")
        if traufe_kante and abs(traufe_kante["z"] - z_traufe) > 0.5:
            log(f"  BEOBACHTUNG offen: Traufkante {traufe_kante['z']:.2f} vs First-gebundene Traufe {z_traufe:.2f} (Differenz {z_traufe - traufe_kante['z']:+.2f} m)")
        else: log(f"  Traufkante {traufe_kante['z']:.2f} und First-gebundene Traufe {z_traufe:.2f} stimmen ueberein (Differenz {z_traufe - traufe_kante['z']:+.2f} m)")
    else:
        z_traufe = traufe_kante["z"]; quelle_traufe = "hoechste lange horizontale Fassadenkante"
        neig = math.atan2(z_first - z_traufe, abs(off_front - off_first)); dach = {"steigung": (z_first - z_traufe) / (off_first - off_front), "neigung_grad": math.degrees(neig), "laenge": 0}
        annahmen.append({"was": "Dachneigung", "annahme": "ANNAHME: Dachneigung aus Traufkante und First (keine geneigten Dachsegmente)"})
    # --- Rueckseite: ANNAHME Firstspiegel
    off_back = 2 * off_first - off_front
    annahmen.append({"was": "Rueckwand", "annahme": f"ANNAHME: Rueckwand parallel zur Front, Firstspiegel (Offset {off_back:.2f} m); keine Kanten/Wolke auf der Rueckseite"})
    # --- Enden (Normale u): Stuetzpunkte aus perpendikularen horizontalen + vertikalen Segmenten
    m = perp | vert; Xe, we = stuetzpunkte(P0[m], P1[m], L[m]); ebe = ransac_1d(Xe @ u, we, TOL * 2, MIN_SCHWACH)
    ebe.sort(key=lambda e: e["offset"]); enden = []
    for e in ebe:
        Xi = Xe[e["idx"]]; enden.append({"typ": "giebel_perp", "along": e["offset"], "laenge": e["laenge"], "belegt": e["laenge"] >= MIN_EBENE,
                                        "z_min": float(Xi[:, 2].min()), "z_max": float(Xi[:, 2].max()), "off_min": float((Xi @ n).min()), "off_max": float((Xi @ n).max())})
    for e in enden: log(f"  Ebene Ende: along {e['along']:.2f} m, Stuetzlaenge {e['laenge']:.0f} m ({'belegt' if e['belegt'] else 'schwach'}), z {e['z_min']:.1f}..{e['z_max']:.1f}")
    # Enden = aeusserste Endebenen, die ueber die Fassadenhoehe reichen (z_max > Traufe-2) und innerhalb der Fassadenausdehnung +1,5 m liegen
    fa0, fa1 = front["along_min"] - 1.5, front["along_max"] + 1.5
    kand = [e for e in enden if fa0 <= e["along"] <= fa1 and e["z_max"] > z_traufe - 2]
    if len(kand) >= 2:
        along_w, along_e = kand[0]["along"], kand[-1]["along"]; q_end = "Endebenen aus perpendikularen/vertikalen Kanten"
        for e in (kand[0], kand[-1]):
            if not e["belegt"]: annahmen.append({"was": "Giebelebene", "annahme": f"ANNAHME: Endebene along {e['along']:.2f} nur schwach belegt ({e['laenge']:.0f} m < {MIN_EBENE:.0f} m)"})
    else:
        along_w, along_e = front["along_min"], front["along_max"]; q_end = "Ausdehnung der Frontkanten"
        annahmen.append({"was": "Giebelebenen", "annahme": "ANNAHME: Enden = Ausdehnung der Frontfassadenkanten (keine Endebenen gefunden)"})
    log(f"Enden: along {along_w:.2f} .. {along_e:.2f} m (Laenge {along_e - along_w:.2f} m) aus {q_end}")
    # --- Boden
    saeulen = d.get("saeulen", []); zf = [s["z_fuss"] for s in saeulen]
    z_boden = float(min(zf)) if zf else float(np.percentile(np.r_[P0[:, 2], P1[:, 2]], 1))
    annahmen.append({"was": "Boden", "annahme": f"ANNAHME: Bodenhoehe = niedrigster Saeulenfuss {z_boden:.2f} m (kein Bodenanker im Gitter)"})
    # --- Staffelgiebel: vertikale Steiger nahe der Endebene oberhalb der Traufe
    giebel = {}
    for name, al_end in (("ende_minus", along_w), ("ende_plus", along_e)):
        m = vert & (np.abs(M @ u - al_end) < 2.0) & (M[:, 2] > z_traufe) & (((M @ n) - off_first) * (off_front - off_first) > 0)
        if m.sum() == 0: giebel[name] = {"stufen": [], "form": "gerade"}; continue
        Xg, wg = stuetzpunkte(P0[m], P1[m], L[m], 0.1); zc = ransac_1d(Xg[:, 2], wg, 0.5, 0.5)
        st = []
        for c in zc:
            Xi = Xg[c["idx"]]; st.append({"off": float(np.median(Xi @ n)), "z_unten": float(Xi[:, 2].min()), "z_oben": float(Xi[:, 2].max()), "laenge": c["laenge"]})
        st.sort(key=lambda s: -abs(s["off"] - off_first))  # von der Traufe zum First
        # plausible Treppe: offsets monoton zum First hin, z monoton steigend
        tr = []
        for s in st:
            if not tr or (abs(s["off"] - off_first) < abs(tr[-1]["off"] - off_first) - 0.3 and s["z_unten"] > tr[-1]["z_oben"] - 0.3 and s["z_oben"] <= z_first + 0.5): tr.append(s)
        form = "staffel" if len(tr) >= 3 else "gerade"; giebel[name] = {"stufen": tr, "alle_steiger": st, "form": form}
        log(f"Giebel {name}: {len(st)} Steiger-Cluster, davon {len(tr)} als Treppe -> {form}")
        if form != "staffel": annahmen.append({"was": f"Giebel {name}", "annahme": f"ANNAHME: gerade Giebellinie (nur {len(tr)} Stufen-Steiger belegt, Treppe braucht >= 3)"})
        else: annahmen.append({"was": f"Giebel {name}", "annahme": "ANNAHME: Stufen-Trittflaechen horizontal zwischen den belegten Steigern; Rueckhaelfte gespiegelt; Wanddicke 0,5 m"})
    vorspruenge = []
    for e in sorted([e for e in ebenen if e["typ"] == "fassade_parallel" and (e["offset"] - off_front) * sgn >= 0.5 and e["laenge"] >= 2 * MIN_EBENE], key=lambda e: -e["laenge"]):
        if all(abs(e["offset"] - v["offset"]) > 0.3 for v in vorspruenge): vorspruenge.append(e)
    for v in vorspruenge:
        sel = np.abs(X @ n - v["offset"]) <= TOL; Xv = X[sel]; lauf = []
        for z0 in np.arange(math.floor(v["z_min"] * 2) / 2, v["z_max"], 0.5):
            mz = (Xv[:, 2] >= z0) & (Xv[:, 2] < z0 + 0.5); deck = len(np.unique(np.floor(Xv[mz] @ u))) / max(v["along_max"] - v["along_min"], 1) if mz.sum() else 0
            if deck >= 0.4: lauf.append(z0)
        if lauf: v["z_min_voll"], v["z_max_voll"] = float(lauf[0]), float(lauf[-1] + 0.5)
        else: v["z_min_voll"], v["z_max_voll"] = v["z_min"], v["z_max"]
        v["deckung_hinweis"] = f"dicht belegt (along-Deckung >= 40 % je 0,5-m-Band) z {v['z_min_voll']:.1f}..{v['z_max_voll']:.1f}; darueber bis {v['z_max']:.1f} nur abschnittsweise (Erker)"
        log(f"Vorsprung: Ebene {v['offset']:.2f} m ({abs(v['offset'] - off_front):.2f} m vor der Front), z {v['z_min']:.1f}..{v['z_max']:.1f}, along {v['along_min']:.1f}..{v['along_max']:.1f}, {v['laenge']:.0f} m")
        log(f"  {v['deckung_hinweis']}"); annahmen.append({"was": f"Vorsprung {v['offset']:.2f}", "annahme": f"ANNAHME: Vorsprung als durchgehender Kasten ueber along {v['along_min']:.1f}..{v['along_max']:.1f}, z {v['z_min_voll']:.1f}..{v['z_max_voll']:.1f} (Ebene belegt; {v['deckung_hinweis']})"})
    A.update(dict(vorspruenge=vorspruenge, ebenen=ebenen, enden=enden, first={"z": z_first, "offset": off_first, "laenge": first["laenge"]}, traufe={"z": z_traufe, "quelle": quelle_traufe, "kante": traufe_kante},
                  dach=dach, off_front=off_front, off_back=off_back, off_laube=off_laube, along_w=along_w, along_e=along_e, z_boden=z_boden, giebel=giebel))
    if off_laube is None:
        annahmen.append({"was": "Laubentiefe", "annahme": "ANNAHME: keine Laubenrueckwand-Ebene gefunden, Arkaden 4 m tief"})
    else: log(f"Laubenrueckwand: offset {off_laube:.2f} m (Tiefe {abs(off_front - off_laube):.2f} m)")
    return A, annahmen, (par, perp, vert, schr, M)


# ----------------------------------------------------------------------------- Stufe 3: Koerper
def baue(d, A, annahmen, P0, P1, L, dn, Q, masken, log):
    import manifold3d as m3
    u = np.array(A["u"]); n = np.array(A["n"]); par, perp, vert, schr, M = masken
    aw, ae, of, ob, zb, zt, zf, offi = A["along_w"], A["along_e"], A["off_front"], A["off_back"], A["z_boden"], A["traufe"]["z"], A["first"]["z"], A["first"]["offset"]
    teile = []; belege = []
    # Rumpf + Satteldach als EIN Querschnitt (Fuenfeck in (offset, z)), entlang along extrudiert - keine Boolesche Naht an der Traufe
    # (lokal: X=along, Y=offset, Z=z; Querschnittsrahmen a=offset, b=z, c=along -> Matrix mit det +1)
    zt_b = zf - (zf - zt)  # ANNAHME: Rueckseite symmetrisch zum First
    eps = 0.02 * np.sign(of - offi)
    huelle = m3.Manifold.extrude(cs([[of, zb], [of, zt], [offi, zf], [ob, zt_b], [ob, zb]]), ae - aw).transform(np.array([[0, 0, 1, aw], [1, 0, 0, 0], [0, 1, 0, 0]], float))
    teile.append(huelle); belege.append({"element": "Rumpf+Satteldach", "quelle": "Frontebene, Endebenen, First-Kante, Dachneigung aus geneigten Kanten; Rueckwand ANNAHME Firstspiegel"})
    of_i, ob_i = of - eps, ob + eps
    # Vorspruenge (Balkon-/Erkerzone) als Kaesten
    for v in A.get("vorspruenge", []):
        lo, hi = sorted([of, v["offset"]]); al0, al1 = max(v["along_min"], aw + 0.02), min(v["along_max"], ae - 0.02)
        z0v, z1v = v.get("z_min_voll", v["z_min"]), v.get("z_max_voll", v["z_max"])
        teile.append(m3.Manifold.extrude(cs([[al0, lo - 0.2], [al1, lo - 0.2], [al1, hi], [al0, hi]]), z1v - z0v).translate([0, 0, z0v]))
        belege.append({"element": f"Vorsprung {v['offset']:.2f}", "quelle": f"Parallelebene {v['laenge']:.0f} m Kanten, gebaut z {z0v:.1f}..{z1v:.1f} (dicht belegt)"})
    # Staffelgiebel-Waende
    for name, al_end, sgn in (("ende_minus", aw, 1), ("ende_plus", ae, -1)):
        g = A["giebel"].get(name, {})
        if g.get("form") != "staffel": continue
        pts = [[of_i, zt]]
        for s in g["stufen"]: pts += [[s["off"], s["z_unten"]], [s["off"], s["z_oben"]]]
        pts.append([offi, max(zf, pts[-1][1])])
        rueck = [[2 * offi - p[0], p[1]] for p in pts[::-1]]
        poly = pts + rueck[1:] + [[ob_i, zt - 0.3], [of_i, zt - 0.3]]
        try:
            wand = m3.Manifold.extrude(cs(poly), 0.52).transform(np.array([[0, 0, 1, al_end - 0.02 if sgn > 0 else al_end - 0.5], [1, 0, 0, 0], [0, 1, 0, 0]], float))
            if wand.volume() > 0: teile.append(wand); belege.append({"element": f"Staffelgiebel {name}", "quelle": f"{len(g['stufen'])} Steiger-Cluster (vertikale Kanten an der Endebene)"})
        except Exception as ex: log(f"  Staffelgiebel {name} nicht baubar: {ex}")
    # Saeulen
    saeulen = d.get("saeulen", [])
    n_saeulen = 0; A["saeulen_ausserhalb"] = []
    for s in saeulen:
        p = np.array([s["cx"], s["cy"], 0]); al, off = float(p @ u), float(p @ n)
        if not (aw - s["R"] <= al <= ae + s["R"] and min(of, ob) - s["R"] <= off <= max(of, ob) + s["R"]):
            A["saeulen_ausserhalb"].append({"along": al, "offset": off, "R": s["R"]}); log(f"  Saeule along {al:.2f} / offset {off:.2f} liegt ausserhalb des Grundrisses - nicht gebaut (sonst loses Teil)"); continue
        teile.append(m3.Manifold.cylinder(s["z_kopf"] - zb, s["R"], s["R"], 32).translate([al, off, zb])); n_saeulen += 1
    belege.append({"element": "Saeulen", "quelle": f"{n_saeulen} von {len(saeulen)} Zylindern aus 'saeulen' (Wolkenfit); ausserhalb des Grundrisses: {len(A['saeulen_ausserhalb'])}"})
    # Helme
    for h in d.get("helme", []):
        p = np.array([h["cx"], h["cy"], 0]); al, off = float(p @ u), float(p @ n); nseg = int(h.get("sektoren", 8)) if h.get("sektoren", 8) <= 16 else 8
        kegel = m3.Manifold.cylinder(h["z_spitze"] - h["z_fuss"], h["r_fuss"], 0.0, nseg).rotate([0, 0, math.degrees(h.get("phi", 0))]).translate([al, off, h["z_fuss"]])
        teile.append(kegel)
        if h["z_fuss"] > zt + 0.05:   # Tambour bis zur Traufe, damit der Helm nicht schwebt
            teile.append(m3.Manifold.cylinder(h["z_fuss"] - zt + 0.10, h["r_fuss"], h["r_fuss"], nseg).rotate([0, 0, math.degrees(h.get("phi", 0))]).translate([al, off, zt - 0.05]))
            annahmen.append({"was": "Helm-Unterbau", "annahme": f"ANNAHME: {nseg}-eckiger Schaft von Traufe {zt:.2f} bis Helmfuss {h['z_fuss']:.2f} m"})
    belege.append({"element": "Helme", "quelle": f"{len(d.get('helme', []))} Pyramiden aus 'helme' (Wolkenfit), Sektoren wie Fit"})
    # Arkaden: Saeulen auf der Hauptlinie (Offset nahe Front)
    koerper = m3.Manifold.batch_boolean(teile, m3.OpType.Add)
    haupt = []
    for s in saeulen:
        p = np.array([s["cx"], s["cy"], 0]); al, off = float(p @ u), float(p @ n)
        if abs(off - of) < 1.0 and aw - 0.5 < al < ae + 0.5: haupt.append((al, off, s))
    haupt.sort(key=lambda t: t[0]); arkaden = []; abzug = []
    of_laube = A["off_laube"] if A["off_laube"] is not None else of - 4.0 * np.sign(of - offi)
    vorn = max([abs(v["offset"] - offi) for v in A.get("vorspruenge", [])] + [abs(of - offi)]) + 0.5; of_aussen = offi + np.sign(of - offi) * vorn
    tiefe = abs(of_aussen - of_laube)
    Xs = np.array([]);
    for (a0, o0, s0), (a1, o1, s1) in zip(haupt[:-1], haupt[1:]):
        x0, x1 = a0 + s0["R"] + 0.02, a1 - s1["R"] - 0.02; spann = x1 - x0; zk = 0.5 * (s0["z_kopf"] + s1["z_kopf"])   # 2 cm Abstand zu den Zylindern (keine Tangentenkante)
        if spann < 1.0: continue
        # Bogenfit: geneigte Segmente nahe der Front, zwischen den Saeulen, z oberhalb der Kapitelle
        # Suchfenster = ganze Pfeilerhoehe (Saeulen-z_kopf aus dem Wolkenfit kann Kapitell ODER Bogenscheitel sein); der Kreis-RANSAC entscheidet
        m = schr & (np.abs((M @ n) - of) < 0.7) & (M @ u > x0 - 0.3) & (M @ u < x1 + 0.3) & (M[:, 2] > zb + 1.0) & (M[:, 2] < zk + 0.5)
        R = spann / 2; z_mitte = zk - R; quelle = f"ANNAHME: Halbkreis, R = halbe lichte Weite {R:.2f} m, Scheitel = Saeulenkopf {zk:.2f} m"
        fit = None
        if m.sum() >= 3:
            Xb, wb = stuetzpunkte(P0[m], P1[m], L[m], 0.1); kr = kreis_ransac(Xb @ u, Xb[:, 2], 0.10, zwang=((x0 + x1) / 2 - 0.6, (x0 + x1) / 2 + 0.6, zb + 1.0, zk, 0.3 * spann, 0.8 * spann))
            cx, cz, Rf, rms, anteil = kr if kr else (0, 0, 0, 9, 0)
            fit = {"n_seg": int(m.sum()), "n_stuetz": int(len(Xb)), "cx": cx, "cz": cz, "R": Rf, "rms_inlier": rms, "anteil_inlier": anteil}
            if kr and rms < 0.08 and len(Xb) * anteil >= 30 and 0.3 * spann < Rf < 0.8 * spann and abs(cx - (x0 + x1) / 2) < 0.6:
                R, z_mitte = Rf, cz; quelle = f"Kreisbogen-RANSAC an {int(m.sum())} Segmenten (R {Rf:.2f} m, {int(len(Xb) * anteil)} Inlier-Stuetzpunkte = {anteil:.0%}, rms {rms:.3f} m)" + (" - schwach (< 25 % Inlier)" if anteil < 0.25 else "")
        xm = (x0 + x1) / 2
        # Oeffnung = Rechteck + Halbkreis in (along, z), extrudiert entlang -offset von of+1 nach innen
        k = 24; ang = np.linspace(0, math.pi, k + 1)
        bogen = [[xm + R * math.cos(t), z_mitte + R * math.sin(t)] for t in ang][::-1]  # von links (xm-R)... sortieren
        if R < spann / 2 - 0.01:      # Bogen schmaler als die lichte Weite: Rechteck auf volle Weite, Bogen oben aufgesetzt
            poly = [[x0, zb - 0.5], [x1, zb - 0.5], [x1, z_mitte], [xm + R, z_mitte]] + [[xm + R * math.cos(t), z_mitte + R * math.sin(t)] for t in ang[1:-1]] + [[xm - R, z_mitte], [x0, z_mitte]]
        elif R > spann / 2 + 0.01:    # Segment-/Stichbogen: Kreis groesser als die halbe Weite, Kaempfer dort, wo der Kreis die Pfeilerkante schneidet
            z_s = z_mitte + math.sqrt(max(R * R - (spann / 2) ** 2, 0)); a0 = math.atan2(z_s - z_mitte, spann / 2); angs = np.linspace(a0, math.pi - a0, k + 1)
            poly = [[x0, zb - 0.5], [x1, zb - 0.5]] + [[xm + R * math.cos(t), z_mitte + R * math.sin(t)] for t in angs]
        else:                         # Halbkreis ueber die volle Weite
            poly = [[xm - R, zb - 0.5], [xm + R, zb - 0.5], [xm + R, z_mitte]] + [[xm + R * math.cos(t), z_mitte + R * math.sin(t)] for t in ang[1:-1]] + [[xm - R, z_mitte]]
        poly = np.array(poly)
        tunnel = m3.Manifold.extrude(cs(poly), tiefe).transform(np.array([[1, 0, 0, 0], [0, 0, -np.sign(of - offi), of_aussen], [0, 1, 0, 0]], float))
        abzug.append(tunnel); arkaden.append({"along_0": x0, "along_1": x1, "spannweite": spann, "R": R, "z_mittelpunkt": z_mitte, "z_scheitel": z_mitte + R, "z_kaempfer": z_mitte + math.sqrt(max(R * R - (spann / 2) ** 2, 0)) if R > spann / 2 else z_mitte, "quelle": quelle, "fit": fit})
        if quelle.startswith("ANNAHME"): annahmen.append({"was": f"Arkade along {xm:.1f}", "annahme": quelle + (f" (Fit verworfen: {fit})" if fit else " (keine Bogensegmente)")})
    if abzug:
        koerper = koerper - m3.Manifold.batch_boolean(abzug, m3.OpType.Add)   # Oeffnungen bis unter den Boden: Laubenboden = Druckbett (ANNAHME)
    log(f"Arkaden: {len(arkaden)} Oeffnungen, {sum(1 for a in arkaden if not a['quelle'].startswith('ANNAHME'))} mit Kreisbogen-Fit")
    belege.append({"element": "Arkaden", "quelle": "Oeffnungen zwischen Hauptlinien-Saeulen; Bogen aus Kreisfit oder ANNAHME"})
    A["arkaden"] = arkaden; A["belege"] = belege
    # In Weltkoordinaten: welt = along*u + off*n + z*ez
    Mw = np.c_[u, n, [0, 0, 1], [0, 0, 0]]
    return koerper.transform(Mw)


def exportiere(koerper, ausdir, name, log):
    import trimesh
    me = koerper.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; F = np.asarray(me.tri_verts)
    tm = trimesh.Trimesh(V, F, process=False)
    os.makedirs(ausdir, exist_ok=True); p = os.path.join(ausdir, name + ".stl"); tm.export(p)
    tmh = tm.copy(); tmh.apply_scale(H0); ph = os.path.join(ausdir, name + "_h0.stl"); tmh.export(ph)
    log(f"Export: {p} ({len(F)} Dreiecke, wasserdicht={tm.is_watertight}, Volumen {tm.volume:.1f} m^3); H0: {ph} (BBox mm {np.round(tmh.extents, 1).tolist()})")
    return tm


# ----------------------------------------------------------------------------- Stufe 4: Pruefung
def pruefen(ausdir, wolke, kam_json, bilddir, auditdir, name, foto):
    import trimesh, cv2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gpu_knn import min_abstand
    os.makedirs(auditdir, exist_ok=True); tm = trimesh.load(os.path.join(ausdir, name + ".stl"), process=True); tm.merge_vertices(); wd_roh = bool(tm.is_watertight)
    if not wd_roh: tm.merge_vertices(merge_tex=True, merge_norm=True); trimesh.repair.fix_normals(tm)
    erg = {"wasserdicht": bool(tm.is_watertight), "wasserdicht_vor_merge": wd_roh, "volumen_m3": float(tm.volume), "dreiecke": int(len(tm.faces)), "euler": int(tm.euler_number), "bbox": tm.bounds.tolist()}
    P = np.load(wolke)["P"].astype(np.float32)
    S, _ = trimesh.sample.sample_surface(tm, 3_000_000); S = np.asarray(S, np.float32)
    dP = min_abstand(P, S)       # Wolke -> Oberflaeche (Abtastung, Fehler <= halber Punktabstand ~2 cm)
    dS = min_abstand(S, P)       # Oberflaeche -> Wolke (Deckung)
    erg["wolke_naeher_20cm_gesamt"] = float((dP < 0.2).mean()); erg["wolke_median_abstand"] = float(np.median(dP))
    erg["oberflaeche_mit_wolke_50cm"] = float((dS < 0.5).mean())
    baender = []
    for z0 in np.arange(math.floor(P[:, 2].min()), math.ceil(P[:, 2].max()), 2.0):
        m = (P[:, 2] >= z0) & (P[:, 2] < z0 + 2); ms = (S[:, 2] >= z0) & (S[:, 2] < z0 + 2)
        if m.sum() < 100: continue
        baender.append({"z": [float(z0), float(z0 + 2)], "n_wolke": int(m.sum()), "anteil_lt_20cm": float((dP[m] < 0.2).mean()), "anteil_lt_50cm": float((dP[m] < 0.5).mean()),
                        "median": float(np.median(dP[m])), "deckung_oberflaeche_50cm": float((dS[ms] < 0.5).mean()) if ms.sum() else None})
    erg["hoehenbaender"] = baender
    # Kanten des Netzes (Dieder > 30 Grad) als Segmente
    tmc = tm.copy(); tmc.merge_vertices(); adj = tmc.face_adjacency; ang = tmc.face_adjacency_angles
    kant = tmc.face_adjacency_edges[ang > math.radians(30)]; seg = [[tmc.vertices[a].tolist(), tmc.vertices[b].tolist(), 1, 1.0] for a, b in kant]
    segp = os.path.join(ausdir, name + "_kanten.json"); json.dump({"segmente": seg, "quelle": "Netzkanten Dieder > 30 Grad"}, open(segp, "w"))
    erg["netzkanten"] = len(seg)
    # Overlay auf Foto via gitter_overlay.py
    ov = os.path.join(auditdir, f"overlay_{os.path.splitext(foto)[0]}.jpg")
    import subprocess
    r = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitter_overlay.py"), kam_json, os.path.join(bilddir, foto), segp, ov], capture_output=True, text=True)
    erg["overlay"] = ov if r.returncode == 0 else f"FEHLER {r.stderr[-400:]}"
    # Renders (Painter, orthografisch) vorn / Seite / schraeg, Wolke als Punkte darueber
    u = None
    try: u = np.array(json.load(open(os.path.join(ausdir, name + ".json")))["u"])
    except Exception: u = np.array([1.0, 0, 0])
    n = np.array([-u[1], u[0], 0.0]); V = tm.vertices; F = tm.faces; Cm = V.mean(0)
    def render(d, fn, W=1400, wolke=True):
        d = d / np.linalg.norm(d); up = np.array([0, 0, 1.0]); r = np.cross(up, d); r /= np.linalg.norm(r); up2 = np.cross(d, r)
        X = (V - Cm) @ np.c_[r, up2, d]; ext = max(np.abs(X[:, 0]).max(), np.abs(X[:, 1]).max()); sc = W * 0.46 / ext
        P2 = np.c_[X[:, 0] * sc + W / 2, -X[:, 1] * sc + W * 0.5]; tri = X[F]; nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nn /= (np.linalg.norm(nn, axis=1) + 1e-9)[:, None]
        lam = 0.3 + 0.7 * np.clip(np.abs(nn @ np.array([0.3, 0.5, 0.8])), 0, 1); zt = tri[:, :, 2].mean(1); im = np.full((W, W, 3), 255, np.uint8)
        for t in np.argsort(zt):
            c = int(200 * lam[t]); cv2.fillConvexPoly(im, P2[F[t]].astype(np.int32), (c, c + 20, c + 30))
        if wolke:
            Pw = (P[::20] - Cm) @ np.c_[r, up2, d]; px = (Pw[:, 0] * sc + W / 2).astype(int); py = (-Pw[:, 1] * sc + W * 0.5).astype(int)
            ok = (px >= 0) & (px < W) & (py >= 0) & (py < W); im[py[ok], px[ok]] = (0, 0, 255)
        cv2.imwrite(fn, im)
    render(n, os.path.join(auditdir, "render_vorn.jpg")); render(u, os.path.join(auditdir, "render_seite.jpg"))
    render(n + 0.8 * u + 0.6 * np.array([0, 0, 1.0]), os.path.join(auditdir, "render_schraeg.jpg")); render(n, os.path.join(auditdir, "render_vorn_ohnewolke.jpg"), wolke=False)
    render(-n + 0.8 * u + 0.5 * np.array([0, 0, 1.0]), os.path.join(auditdir, "render_hinten_schraeg.jpg"))
    # Flaechen-Overlay: Dreiecke perspektivisch ins Foto (SIMPLE_RADIAL), Painter nach Tiefe, 45 % Deckkraft
    try:
        k = json.load(open(kam_json))[foto]; im = cv2.imread(os.path.join(bilddir, foto), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); sc = im.shape[1] / k["W"]
        Rk = np.array(k["Rn"]); tk = np.array(k["tn"]); Xc = V @ Rk.T + tk; z = Xc[:, 2]; x = Xc[:, 0] / np.maximum(z, 0.1); y = Xc[:, 1] / np.maximum(z, 0.1)
        f1 = 1 + k["params"][3] * (x * x + y * y); px = (k["f"] * x * f1 + k["cx"]) * sc; py = (k["f"] * y * f1 + k["cy"]) * sc; P2 = np.c_[px, py]
        tri = V[F]; nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nn /= (np.linalg.norm(nn, axis=1) + 1e-9)[:, None]
        ov = im.copy(); zt = z[F].mean(1); ok = (z[F] > 0.5).all(1)
        for t in np.argsort(-zt):
            if not ok[t]: continue
            c = 0.35 + 0.65 * abs(float(nn[t] @ np.array([0.3, 0.5, 0.8]))); cv2.fillConvexPoly(ov, P2[F[t]].astype(np.int32), (int(255 * c), int(160 * c), int(60 * c)))
        out = cv2.addWeighted(im, 0.55, ov, 0.45, 0); fn = os.path.join(auditdir, f"overlay_flaechen_{os.path.splitext(foto)[0]}.jpg")
        cv2.imwrite(fn, cv2.resize(out, (1200, int(1200 * out.shape[0] / out.shape[1])))); erg["overlay_flaechen"] = fn
    except Exception as ex: erg["overlay_flaechen"] = f"FEHLER {ex}"
    json.dump(erg, open(os.path.join(ausdir, name + "_pruefung.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in erg.items() if k != "hoehenbaender"}, indent=1))
    for b in baender: print(f"  z {b['z'][0]:5.1f}-{b['z'][1]:5.1f}: n={b['n_wolke']:8d}  <20cm {b['anteil_lt_20cm']:.2f}  <50cm {b['anteil_lt_50cm']:.2f}  median {b['median']:.2f}  Deckung {b['deckung_oberflaeche_50cm']}")


def aufriss(seg_json, ausdir, auditdir, name):
    """Aufriss des Gitters im Frontband (+-1 m) in (along, z) mit den gebauten Saeulen und Boegen - Sichtpruefung der Arkadenform (Regel 9b)."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    d, P0, P1, L, dn, Q = lade(seg_json); A = json.load(open(os.path.join(ausdir, name + ".json"))); u = np.array(A["u"]); n = np.array(A["n"]); of = A["off_front"]
    M = (P0 + P1) / 2; m = np.abs(M @ n - of) < 1.0; fig, ax = plt.subplots(figsize=(22, 10))
    farbe = {0: "k", 8: "tab:blue", 9: "tab:green", 7: "tab:orange", 5: "tab:red", 4: "m", 6: "c"}
    for i in np.where(m)[0]: ax.plot([P0[i] @ u, P1[i] @ u], [P0[i, 2], P1[i, 2]], farbe.get(int(Q[i]), "y"), lw=1)
    for s in d.get("saeulen", []):
        al = np.array([s["cx"], s["cy"], 0]) @ u; ax.add_patch(plt.Rectangle((al - s["R"], s["z_fuss"]), 2 * s["R"], s["z_kopf"] - s["z_fuss"], fill=False, ec="r", lw=2))
    for a in A["arkaden"]:
        xm = (a["along_0"] + a["along_1"]) / 2; t = np.linspace(0, math.pi, 60); ax.plot(xm + a["R"] * np.cos(t), a["z_mittelpunkt"] + a["R"] * np.sin(t), "r--", lw=2)
    for z, lab in ((A["traufe"]["z"], "Traufe"), (A["first"]["z"], "First")): ax.axhline(z, color="g", ls=":"); ax.text(A["along_w"], z + 0.2, lab, color="g")
    ax.set_yticks(range(0, int(A["first"]["z"]) + 2)); ax.grid(True, alpha=.4); ax.set_aspect("equal")
    ax.set_title("Aufriss Gitter, Frontband +-1 m (Farbe = Quelle); rot = Saeulen (Wolkenfit) und gebaute Boegen; gruen = Traufe/First")
    os.makedirs(auditdir, exist_ok=True); fn = os.path.join(auditdir, "aufriss_gitter_front.jpg"); plt.savefig(fn, dpi=70, bbox_inches="tight"); print(fn)


# ----------------------------------------------------------------------------- main
def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("bauen", "pruefen", "aufriss"): print(__doc__); sys.exit(1)
    name = a[a.index("--name") + 1] if "--name" in a else "rohkoerper_v7"
    if a[0] == "bauen":
        seg_json, ausdir = a[1], a[2]; os.makedirs(ausdir, exist_ok=True); zeilen = []
        def log(s): print(s); zeilen.append(s)
        d, P0, P1, L, dn, Q = lade(seg_json); log(f"Gitter: {len(L)} Segmente, {L.sum():.0f} m, Helme {len(d.get('helme', []))}, Saeulen {len(d.get('saeulen', []))}")
        A, annahmen, masken = analysiere(d, P0, P1, L, dn, Q, log)
        k = baue(d, A, annahmen, P0, P1, L, dn, Q, masken, log)
        tm = exportiere(k, ausdir, name, log)
        A["wasserdicht"] = bool(tm.is_watertight); A["volumen_m3"] = float(tm.volume); A["quelle"] = seg_json; A["log"] = zeilen
        json.dump(A, open(os.path.join(ausdir, name + ".json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
        json.dump({"objekt_quelle": seg_json, "annahmen": annahmen}, open(os.path.join(ausdir, "annahmen.json"), "w"), indent=1)
        log(f"Annahmen: {len(annahmen)} -> {os.path.join(ausdir, 'annahmen.json')}")
    elif a[0] == "aufriss":
        aufriss(a[1], a[2], a[3], name)
    else:
        foto = a[a.index("--foto") + 1] if "--foto" in a else "ip_IMG_6261.jpg"
        pruefen(a[1], a[2], a[3], a[4], a[5], name, foto)


if __name__ == "__main__":
    main()
