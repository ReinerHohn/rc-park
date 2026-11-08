#!/usr/bin/env python3
"""wolke_carving.py - Koerper NUR aus der Buendelwolke per Sichtbarkeits-Carving (Nutzerentscheid 5.11. 20:10; Koordination 21:45: "Punktwolke ist die EINZIGE Basis").

Optional --objekt objekt.json: LoD2 ergaenzt NUR unbeobachtete/bestaetigte Dach-/Wandflaechen (Widerspruch zur Wolke -> Wolke gilt), nie in carving-leeren Zellen.
Eingabe: dichte Wolke (fused.ply + fused.ply.vis), Ausrichtung (SFM-AUSRICHTUNG), Kamerazentren (kameras_unverzerrt.json), Zuschnittquader (Objektparameter), KEIN Generator-STL, KEIN LoD2/DOM1.
Verfahren (volumetrisch, Voxel --voxel, Standard 0,10 m):
 1 leer     Zellen, durch die ein Kamerastrahl Kamera -> Punkt (Ende --rand m vor dem Punkt) laeuft, werden gezaehlt (je Strahlblock einmal); >= --carve-min Bloecke = LEER (Space Carving mit .vis)
 2 Material Zellen mit >= --min-punkte Punkten + bis --hinter m hinter den Punkten (Richtung: von der ersten sehenden Kamera weg)
 3 Hulle    unbeobachtete Zellen: Material nur, wenn sie von aussen nicht erreichbar sind (6er-Fuellung ab Quaderrand durch leer/unbekannt, nach Schliessen kleiner Luecken des Materials); eingeschlossene Reste mit
            gesehenem Leerraum bleiben leer (Raeume, Hallen). Boden = Platzniveau aus Punkten mit aufwaerts gerichteter Normale (Quantil), darunter Material, Bodenplatte ausserhalb des Gebaeudes entfernt.
 4 Flaechen RANSAC-Lote (senkrechte Ebenen aus der Wolke) rasten Netzknoten ein, die innerhalb --snap m liegen; sonst bleibt die Punktlage.
 5 Netz      geglaetteter Besetzungsgrad -> Marching Cubes -> groesster Koerper -> wasserdicht (stl_dicht aus wolke_solid) -> STL 1:massstab (mm).
Herkunft je Zelle (Zahlen im JSON): beobachtet Material / geschlossene Huelle (unbeobachtet, innen) / leer durch Carving / leer (aussen unbekannt).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_carving.py --dicht D --ausrichtung A --box x0 x1 y0 y1 z1 --aus DIR
"""
import os, sys, json, time, argparse
import numpy as np, cv2, trimesh
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import freiraum_pruefen as FP


def wolke_laden(dicht, ausr, min_kam=3, ohne_bilder=()):
    """Punkte (Modellrahmen), Normalen (Rahmen), Beobachtungen (Punkt, Kamera), Kamerazentren; Punkte mit < min_kam Kameras entfallen. ohne_bilder: Bildnamen, deren Beobachtungen gestrichen werden."""
    tr = json.load(open(ausr))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float); zu = lambda X: ((X - ta) @ Ra) / s
    X = zu(FP.ply_lesen(os.path.join(dicht, "fused.ply")))
    with open(os.path.join(dicht, "fused.ply"), "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    N = np.c_[arr["nx"], arr["ny"], arr["nz"]].astype(float) @ Ra
    pi, ii = FP.vis_lesen(os.path.join(dicht, "fused.ply.vis")); K = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); ids = FP.vis_ids(dicht, K)
    Rc = np.array([K[i]["R"] for i in ids]); tc = np.array([K[i]["t"] for i in ids]); Cc = zu(np.einsum("kji,kj->ki", Rc, -tc))
    if ohne_bilder:
        drop = np.isin(ii, [ids.index(b) for b in ohne_bilder]); pi, ii = pi[~drop], ii[~drop]
    nk = np.bincount(pi, minlength=len(X)); keep = nk >= min_kam; new = np.cumsum(keep) - 1; ok = keep[pi]
    return X[keep], N[keep], new[pi[ok]], ii[ok], Cc


def carven(X, N, pi, ii, Cc, lo, hi, vox=0.10, rand=0.3, hinter=0.3, min_punkte=2, carve_min=2, n_beob=1500000, schritt=0.1, bloecke=15, seed=1, log=print):
    lo = np.asarray(lo, float); hi = np.asarray(hi, float); dim = np.ceil((hi - lo) / vox).astype(int); NV = int(dim.prod()); rng = np.random.default_rng(seed)
    idx3 = lambda P: np.floor((P - lo) / vox).astype(np.int64)
    lin = lambda I: (I[:, 0] * dim[1] + I[:, 1]) * dim[2] + I[:, 2]
    inb = lambda I: np.all((I >= 0) & (I < dim), axis=1)
    inbox = np.all((X >= lo) & (X < hi), axis=1)
    # 2 Material: Punktdichte
    t0 = time.time(); cntp = np.zeros(NV, np.int32); I = idx3(X[inbox]); cntp += np.bincount(lin(I[inb(I)]), minlength=NV).astype(np.int32)
    first = np.full(len(X), -1, np.int64); o = np.argsort(pi, kind="stable"); u, st = np.unique(pi[o], return_index=True); first[u] = ii[o][st]
    cam0 = Cc[np.maximum(first, 0)]; away = X - cam0; away /= np.maximum(np.linalg.norm(away, axis=1), 1e-9)[:, None]
    occ = cntp >= min_punkte; ext = np.zeros(NV, bool)
    for tt in np.arange(vox, hinter + 1e-9, vox):
        J = idx3(X[inbox] + away[inbox] * tt); k = inb(J); ext[lin(J[k])] = True
    surf = occ | (ext & (cntp >= 1)); log(f"Material-Zellen {int(surf.sum())} ({time.time() - t0:.0f} s)")
    # 1 Carving
    sel = np.where(np.all((X[pi] >= lo - 15) & (X[pi] < hi + 15), axis=1))[0]; sel = rng.choice(sel, min(n_beob, len(sel)), replace=False); rng.shuffle(sel)
    cnt = np.zeros(NV, np.uint8); P0 = X[pi[sel]]; C0 = Cc[ii[sel]]; D = P0 - C0; L = np.linalg.norm(D, axis=1); D /= L[:, None]; Lend = L - rand
    for b in range(bloecke):
        sl = slice(b * len(sel) // bloecke, (b + 1) * len(sel) // bloecke); hit = np.zeros(NV, bool); c, d, le = C0[sl], D[sl], Lend[sl]
        # Strahl gegen Quader schneiden (Slab-Methode) -> nur den Teil im Quader abtasten
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (lo - c) / d; t2 = (hi - c) / d
        tmin = np.nanmax(np.minimum(t1, t2), axis=1); tmax = np.nanmin(np.maximum(t1, t2), axis=1); tmin = np.maximum(tmin, 0.0); tmax = np.minimum(tmax, le)
        gut = tmax > tmin; c, d, tmin, tmax = c[gut], d[gut], tmin[gut], tmax[gut]
        if not len(c): continue
        nst = int(np.ceil((tmax - tmin).max() / schritt)) + 1
        for k in range(nst):
            t = tmin + k * schritt; m = t <= tmax
            if not m.any(): break
            Q = c[m] + d[m] * t[m][:, None]; J = idx3(Q); kk = inb(J); hit[lin(J[kk])] = True
        cnt += hit.astype(np.uint8)
        log(f"  Carving-Block {b + 1}/{bloecke} ({time.time() - t0:.0f} s)")
    leer = (cnt >= carve_min) & ~surf
    return dict(dim=dim, lo=lo, vox=vox, surf=surf.reshape(dim), leer=leer.reshape(dim), cntp=cntp.reshape(dim), beob=int(len(sel)))


def huelle(R, X, N, zg_q=5.0, schliessen=2, fuss_rand=0.2, hoch_m=2.5, schluss_m=1.5, sliver_m=0.4, sockel_m=0.2, platte_m=0.3, grund_hoch_m=2.0, lod2=None, lod2_klassen=None, grund=None, cam=None, puffer_m=0.5, ueberstand_m=1.5, log=print):
    """Unbeobachtetes: Material nur eingeschlossen; Boden/Bodenplatte."""
    surf, leer, dim, lo, vox = R["surf"], R["leer"], R["dim"], R["lo"], R["vox"]
    inb = np.all((X >= lo) & (X < lo + dim * vox), axis=1); up = inb & (N[:, 2] > 0.8)
    if up.sum() > 100:   # Platzniveau = tiefste grosse Horizontalebene (Histogramm der aufwaerts gerichteten Punkte, Stufe 0,2 m, >= 15 % des Maximums)
        hz, ed = np.histogram(X[up, 2], bins=np.arange(X[up, 2].min(), X[up, 2].max() + 0.2, 0.2)); k = int(np.argmax(hz >= 0.15 * hz.max())); zg = float(np.median(X[up, 2][(X[up, 2] >= ed[k]) & (X[up, 2] < ed[k] + 0.4)]))
    else: zg = float(np.percentile(X[inb, 2], 1))
    iz_g = int(np.floor((zg - lo[2]) / vox)); mat = surf.copy(); mat[:, :, :max(iz_g, 0)] = True
    cl = ndi.binary_closing(mat, structure=ndi.generate_binary_structure(3, 1), iterations=schliessen)
    frei = ~cl; lab, n = ndi.label(frei)
    rand = np.zeros(dim, bool); rand[0], rand[-1], rand[:, 0], rand[:, -1], rand[:, :, -1] = True, True, True, True, True; aussen = np.unique(lab[rand & frei]); aussen = aussen[aussen > 0]
    comp_leer = np.zeros(n + 1, bool); comp_leer[np.unique(lab[leer & frei])] = True
    ist_aussen = np.zeros(n + 1, bool); ist_aussen[aussen] = True
    innen = frei & ~ist_aussen[lab] & ~comp_leer[lab]               # eingeschlossen, kein gesehener Leerraum -> Huelle = Material
    material = (cl | innen) & ~(leer & ~mat)
    # Gebaeude = groesste zusammenhaengende Materialmasse > hoch_m ueber Boden (generisch, kein Objektbezug); Umgebung (Strasse, Nachbarn, Rauschen) faellt weg
    iz_h = min(dim[2] - 1, iz_g + int(round(hoch_m / vox))); hoch0 = material[:, :, iz_h:].copy()
    hoch = ndi.binary_dilation(hoch0, structure=ndi.generate_binary_structure(3, 1), iterations=int(round(0.5 / vox))); lab2, n2 = ndi.label(hoch, structure=np.ones((3, 3, 3)))
    if n2:
        gr = np.bincount(lab2[hoch0], minlength=n2 + 1)[1:]; gb = lab2 == (1 + int(gr.argmax())); fp = gb.any(axis=2); fp = ndi.binary_fill_holes(ndi.binary_dilation(fp, iterations=int(round(0.5 / vox))))
        material &= fp[:, :, None]; log(f"Gebaeude: groesste Masse {int(gr.max())} von {n2} Zellkomponenten ueber {hoch_m} m, Grundriss {int(fp.sum()) * vox * vox:.0f} m2")
    # Hohlraumfuellung: je Grundrisszelle Material von unten bis zur oberen Huelle (Dach aus Wolke, Luecken per Grau-Schliessen), AUSSER Zellen mit gesehenem Leerraum (Carving: Arkaden, Hallen, Durchgaenge)
    if n2:
        zi = np.arange(dim[2])[None, None, :]; top = np.where(surf.any(2), dim[2] - 1 - np.argmax(surf[:, :, ::-1], 2), -1); top = np.where(fp, top, -1)
        k = int(round(schluss_m / vox)) | 1; top = ndi.grey_closing(top, size=(k, k)); top = np.where(ndi.binary_fill_holes(fp & (top >= iz_h)), top, -1)
        spalte = (zi <= top[:, :, None]) & (top[:, :, None] >= 0); fuell = spalte & ~leer & ~material; fuell = ndi.binary_opening(fuell, structure=ndi.generate_binary_structure(3, 1), iterations=int(round(sliver_m / vox))); log(f"Hohlraumfuellung (unbeobachtet, innen): {int(fuell.sum())} Zellen")
        material |= fuell; innen = innen | fuell
    # LoD2-Ergaenzung (nur unbeobachtet/bestaetigt, nie widerspruch, nie carving-leer)
    n_lod2 = (0, 0)
    if lod2 and lod2_klassen:
        material, nn, nl = lod2_ergaenzen(material, leer, lod2, lod2_klassen, lo, vox, iz_g, log=log); n_lod2 = (nn, nl)
    # Objekttrennung: eigener LoD2-Grundriss + puffer_m; ausserhalb faellt Material weg, ausser vorn (Kamerarichtung, cos >= 0,6) bis ueberstand_m (Erker/Balkon, von der Wolke beobachtet)
    uebst = None
    if grund:
        from matplotlib.path import Path
        gx = lo[0] + (np.arange(dim[0]) + 0.5) * vox; gy = lo[1] + (np.arange(dim[1]) + 0.5) * vox; XX, YY = np.meshgrid(gx, gy, indexing="ij"); pts = np.c_[XX.ravel(), YY.ravel()]
        fpr = np.zeros(XX.shape, bool)
        for P in grund: fpr |= Path(P[:, :2]).contains_points(pts).reshape(XX.shape)
        d, (ia, ib) = ndi.distance_transform_edt(~fpr, return_indices=True); d = d * vox
        vx = XX - XX[ia, ib]; vy = YY - YY[ia, ib]; cg = np.array([XX[fpr].mean(), YY[fpr].mean()]); dc = cam[:2] - cg; dc /= max(np.linalg.norm(dc), 1e-9)
        cosc = (vx * dc[0] + vy * dc[1]) / np.maximum(d, 1e-9); erlaubt = (d <= puffer_m) | ((d <= ueberstand_m) & (cosc >= 0.6))
        z_er = iz_g + int(round(2.5 / vox)); rest = np.zeros(dim, bool); rest[:, :, :z_er] = d[:, :, None] <= puffer_m; rest[:, :, z_er:] = erlaubt[:, :, None]
        weg = material & ~rest; material &= rest; log(f"Objekttrennung: {int(weg.sum())} Zellen ausserhalb Grundriss+{puffer_m} m entfernt")
        mp = material.any(2); out = mp & ~fpr; ue = {}
        for nm, (sx, sy) in dict(plus_x=(1, 0), minus_x=(-1, 0), plus_y=(0, 1), minus_y=(0, -1)).items():
            sel = out & ((vx * sx + vy * sy) >= 0.7 * np.maximum(d, 1e-9)); ue[nm] = round(float(d[sel].max()), 2) if sel.any() else 0.0
        uebst = ue; log(f"Grundriss-Ueberstand je Seite (m): {ue}")
    # Platzplatte: Grundriss = Projektion des Materials > grund_hoch_m ueber Platz, morphologisch geschlossen; ausserhalb davon faellt Material < Platz + platte_m weg; innerhalb ebener Sockel auf Platzniveau
    ob = material[:, :, min(dim[2] - 1, iz_g + int(round(grund_hoch_m / vox))):].any(axis=2); kk = int(round(1.0 / vox)); ob = ndi.binary_closing(np.pad(ob, kk), structure=ndi.generate_binary_structure(2, 1), iterations=kk)[kk:-kk, kk:-kk]
    ob = ndi.binary_dilation(ob, iterations=int(round(fuss_rand / vox)) + 1); material[:, :, :max(iz_g, 0) + int(round(platte_m / vox))] &= ob[:, :, None]
    i_s = max(iz_g - int(round(sockel_m / vox)), 0); material[:, :, i_s:max(iz_g, 0)] |= ob[:, :, None]
    material[:, :, :i_s] = False        # Sockel: Koerper endet kurz unter dem Platzniveau (kein Erdblock)
    log(f"Boden z {zg:.2f} m; Material {int(material.sum())} Zellen; Huelle (unbeobachtet innen) {int((innen & ~cl).sum())}; leer durch Carving {int(leer.sum())}")
    return material, dict(boden_z=zg, zellen_material=int(material.sum()), zellen_huelle=int((innen & ~cl).sum()), zellen_beobachtet=int(surf.sum()), zellen_leer_carving=int(leer.sum()), zellen_gesamt=int(np.prod(dim)), grundriss_ueberstand_m=uebst, zellen_lod2_neu=n_lod2[0], zellen_lod2_carving_leer_ausgenommen=n_lod2[1])


def lod2_laden(objekt_json):
    """LoD2-Flaechen des Objekts (RoofSurface/WallSurface) im Modellrahmen aus objekt.json (lod2.gml/id, rahmen). Rueckgabe Liste (typ, P[n,3] m). Nur Daten aus objekt.json, kein Objektbezug im Code."""
    import lod2_gebaeude as LG
    o = json.load(open(objekt_json)); R = o["rahmen"]; c0 = np.array(R["mitte_utm"], float); xh = np.array(R["xhat_utm"], float); yh = np.array(R["yhat_utm"], float); g = float(R["gelaende"]); out = []
    for meta, polys in LG.extract(o["lod2"]["gml"], center=tuple(c0), radius=40):
        if meta["id"] != o["lod2"]["id"]: continue
        for t, P in polys:
            if t not in ("RoofSurface", "WallSurface", "GroundSurface"): continue
            d = P[:, :2] - c0; out.append((t, np.c_[d @ xh, d @ yh, P[:, 2] - g]))
    return out


def lod2_klassifizieren(flaechen, X, such_m=1.0, med_m=0.3, deck_min=0.2, raster=0.5, lat_m=0.4, log=print):
    """Je LoD2-Flaeche: bestaetigt (Median |Abstand| <= med_m bei Abdeckung >= deck_min), widerspruch (Median > med_m bei Abdeckung >= deck_min), unbeobachtet_lod2 (Abdeckung < deck_min).
    Abdeckung = Anteil der Rasterpunkte (raster m) in der Flaeche mit >= 1 Wolkenpunkt lateral <= lat_m und Abstand <= such_m. Kein Mitteln: Wolke gilt bei Widerspruch."""
    from scipy.spatial import cKDTree
    from matplotlib.path import Path
    kd = cKDTree(X); erg = []
    for i, (t, P) in enumerate(flaechen):
        c = P.mean(0); u, sv, vt = np.linalg.svd(P - c); n = vt[2]
        if n[2] < 0 and t == "RoofSurface": n = -n
        e1 = vt[0]; e2 = np.cross(n, e1); q = np.c_[(P - c) @ e1, (P - c) @ e2]; pa = Path(q)
        g = np.mgrid[q[:, 0].min():q[:, 0].max():raster, q[:, 1].min():q[:, 1].max():raster].reshape(2, -1).T; g = g[pa.contains_points(g)]
        flaeche = abs(0.5 * np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]))
        if len(g) < 1: erg.append(dict(i=i, typ=t, klasse="unbeobachtet_lod2", flaeche_m2=round(float(flaeche), 2), abdeckung=0.0, median_abstand_m=None)); continue
        if len(g) > 4000: g = g[np.random.default_rng(1).choice(len(g), 4000, replace=False)]
        S = c + g[:, :1] * e1 + g[:, 1:] * e2; nb = kd.query_ball_point(S, such_m + lat_m, workers=-1); cov = 0; ds = []
        for k, ix in enumerate(nb):
            if not ix: continue
            V = X[ix] - S[k]; dn = V @ n; lat = np.linalg.norm(V - dn[:, None] * n, axis=1); m = (lat <= lat_m) & (np.abs(dn) <= such_m)
            if m.any(): cov += 1; ds.extend(np.abs(dn[m]).tolist())
        ab = cov / len(g); med = float(np.median(ds)) if ds else None
        kl = "unbeobachtet_lod2" if ab < deck_min else ("bestaetigt" if med <= med_m else "widerspruch")
        erg.append(dict(i=i, typ=t, klasse=kl, flaeche_m2=round(float(flaeche), 2), abdeckung=round(float(ab), 3), median_abstand_m=None if med is None else round(med, 3), normale_z=round(float(abs(n[2])), 2)))
    z = {k: sum(1 for e in erg if e["klasse"] == k) for k in ("bestaetigt", "widerspruch", "unbeobachtet_lod2")}; log(f"LoD2-Flaechen {len(erg)}: {z}")
    return erg


def lod2_ergaenzen(material, leer, flaechen, klassen, lo, vox, iz_g, wand_dick=0.5, log=print):
    """LoD2-Volumen ergaenzen: unter Dachflaechen (klasse bestaetigt/unbeobachtet_lod2; NIE widerspruch) je Zellsaeule von Platzniveau bis Dachhoehe, unbeobachtete Wandflaechen als Platte wand_dick nach innen;
    NIE in Zellen, die Carving als leer bewiesen hat (Kamerastrahl durch)."""
    from matplotlib.path import Path
    dim = material.shape; ix = lo[0] + (np.arange(dim[0]) + 0.5) * vox; iy = lo[1] + (np.arange(dim[1]) + 0.5) * vox; zc = lo[2] + (np.arange(dim[2]) + 0.5) * vox
    XX, YY = np.meshgrid(ix, iy, indexing="ij"); add = np.zeros(dim, bool); n_dach = n_wand = 0
    for e, (t, P) in zip(klassen, flaechen):
        if e["klasse"] == "widerspruch": continue
        if t == "RoofSurface" and e["klasse"] in ("bestaetigt", "unbeobachtet_lod2"):
            c = P.mean(0); n = np.cross(P[1] - P[0], P[-1] - P[0]) if len(P) < 4 else np.linalg.svd(P - c)[2][2]
            if abs(n[2]) < 0.2: continue
            x0, x1 = P[:, 0].min(), P[:, 0].max(); y0, y1 = P[:, 1].min(), P[:, 1].max(); a0, a1 = np.searchsorted(ix, x0), np.searchsorted(ix, x1); b0, b1 = np.searchsorted(iy, y0), np.searchsorted(iy, y1)
            if a1 <= a0 or b1 <= b0: continue
            sub = np.c_[XX[a0:a1, b0:b1].ravel(), YY[a0:a1, b0:b1].ravel()]; ins = Path(P[:, :2]).contains_points(sub).reshape(a1 - a0, b1 - b0)
            zr = c[2] - (n[0] * (XX[a0:a1, b0:b1] - c[0]) + n[1] * (YY[a0:a1, b0:b1] - c[1])) / n[2]
            k = (zc[None, None, :] <= zr[:, :, None]) & ins[:, :, None] & (np.arange(dim[2])[None, None, :] >= iz_g); add[a0:a1, b0:b1] |= k; n_dach += 1
        elif t == "WallSurface" and e["klasse"] == "unbeobachtet_lod2":
            c = P.mean(0); n = np.linalg.svd(P - c)[2][2]; d = np.array([-n[1], n[0]])
            if abs(n[2]) > 0.3 or np.linalg.norm(d) < 1e-6: continue
            n2 = n[:2] / np.linalg.norm(n[:2]); u = (np.c_[XX.ravel(), YY.ravel()] - c[:2]) @ d / np.linalg.norm(d); w = (np.c_[XX.ravel(), YY.ravel()] - c[:2]) @ n2
            uu = (P[:, :2] - c[:2]) @ d / np.linalg.norm(d); sel = ((u >= uu.min()) & (u <= uu.max()) & (np.abs(w) <= wand_dick)).reshape(XX.shape)
            # Wandumriss in (u, z): nur Zellen INNERHALB des Wandpolygons (Giebel/Traufkante), kein Rechteck bis zur Maximalhoehe
            pw = Path(np.c_[uu, P[:, 2]]); zi0 = max(iz_g, 0); Zg = np.broadcast_to(zc[None, None, zi0:], (dim[0], dim[1], dim[2] - zi0)); Ug = np.broadcast_to(u.reshape(XX.shape)[:, :, None], Zg.shape)
            inn = np.zeros(dim, bool); ss = np.broadcast_to(sel[:, :, None], Zg.shape); idx = np.where(ss)
            if len(idx[0]): inn[:, :, zi0:][idx] = pw.contains_points(np.c_[Ug[idx], Zg[idx]])
            add |= inn; n_wand += 1
    neu = add & ~leer & ~material; log(f"LoD2-Ergaenzung: {n_dach} Dach-, {n_wand} Wandflaechen, {int(neu.sum())} neue Zellen (Carving-leer {int((add & leer).sum())} ausgenommen)")
    return material | neu, int(neu.sum()), int((add & leer).sum())


def lote_ransac(X, N, lo, hi, tol=0.10, min_pts=4000, n_max=20, iters=800, seed=1):
    """Senkrechte Ebenen (Lote in xy) der Wolke: sequentielles RANSAC auf Punkten mit |nz| < 0.3. Rueckgabe Liste (n2, off, Indizes)."""
    ink = np.all((X >= lo) & (X < hi), axis=1) & (np.abs(N[:, 2]) < 0.3); idx = np.where(ink)[0]; rng = np.random.default_rng(seed); out = []
    for _ in range(n_max):
        if len(idx) < min_pts: break
        Q = X[idx, :2]; best = (0, None)
        for _ in range(iters):
            a, b = Q[rng.choice(len(Q), 2, replace=False)]; t = b - a; ln = np.linalg.norm(t)
            if ln < 1.0: continue
            nn = np.array([t[1], -t[0]]) / ln; c = int((np.abs((Q - a) @ nn) < tol).sum())
            if c > best[0]: best = (c, (nn, a))
        if best[1] is None or best[0] < min_pts: break
        nn, a = best[1]; I = idx[np.abs((Q - a) @ nn) < tol]; off = float(np.median((X[I, :2] - a) @ nn)) + float(a @ nn); out.append((nn, off, I)); idx = np.setdiff1d(idx, I)
    return out


def einrasten(m, planes, X, snap=0.12, min_len=3.0):
    """Netzknoten innerhalb snap vor einer Wolken-Lotebene (und im Bereich ihrer Inlier) auf die Ebene ziehen; sonst unveraendert."""
    V = m.vertices.copy(); n_ges = 0
    for nn, off, I in planes:
        P = X[I, :2]; d = np.array([-nn[1], nn[0]]); u = P @ d; u0, u1 = np.percentile(u, [1, 99])
        if u1 - u0 < min_len: continue
        z0, z1 = np.percentile(X[I, 2], [1, 99]); dist = V[:, :2] @ nn - off; uu = V[:, :2] @ d
        k = (np.abs(dist) < snap) & (uu >= u0) & (uu <= u1) & (V[:, 2] >= z0 - 0.3) & (V[:, 2] <= z1 + 0.3)
        V[k, :2] -= dist[k, None] * nn[None]; n_ges += int(k.sum())
    return trimesh.Trimesh(V, m.faces, process=False), n_ges


def netz(material, lo, vox, sigma=1.0):
    """Vorzeichenbehaftetes Abstandsfeld (Voxel-Distanz innen/aussen, geglaettet sigma Voxel) -> Marching Cubes bei 0: bricht die 10-cm-Treppen der binaeren Belegung."""
    from skimage.measure import marching_cubes
    mp = np.pad(material, 2, constant_values=False); f = (ndi.distance_transform_edt(~mp) - ndi.distance_transform_edt(mp)).astype(np.float32); f = ndi.gaussian_filter(f, sigma)
    v, fc, nrm, _ = marching_cubes(f, 0.0, spacing=(vox, vox, vox)); v = v + lo - 2 * vox; m = trimesh.Trimesh(v, fc, process=True); parts = m.split(only_watertight=False); return max(parts, key=lambda c: abs(c.volume)) if len(parts) > 1 else m


def haut_anlegen(m, haut_pfad, X, boden_z, max_d=0.5, min_pkt=5, rad=0.15, cos_min=0.5, glaetten=3, n_samp=800000, einwaerts_max=0.05):
    """Carving-Oberflaeche an eine Fremdhaut (z. B. OpenMVS-Netz aus denselben Fotos, Meter, Modellrahmen) legen: Knoten, deren naechster Hautpunkt <= max_d liegt, von >= min_pkt Wolkenpunkten (je >= 3 Kameras)
    innerhalb rad gestuetzt ist, gleiche Aussenrichtung hat (cos >= cos_min) und > boden_z + 0,3 m liegt, wandern entlang ihrer Normale zur Haut (Versatz geglaettet). Sonst bleibt die Carving-Lage.
    Rueckgabe (Netz, Zahlen). Herkunft je Knoten: haut / carving."""
    from scipy.spatial import cKDTree
    from scipy import sparse
    h = trimesh.load(haut_pfad, force="mesh"); P, fi = trimesh.sample.sample_surface(h, n_samp, seed=1); Nh = h.face_normals[fi]; from gpu_knn import naechster, ball_anzahl   # GPU (Nutzerregel)
    V = m.vertices; Nv = m.vertex_normals; d, j = naechster(V, P); p = P[j]; nh = Nh[j]
    cosw = (nh * Nv).sum(1); sgn = np.where(cosw < 0, -1.0, 1.0); cosw = np.abs(cosw)       # Hautnormalen sind nicht orientiert
    stuetz = ball_anzahl(p, X, rad, kmax=max(min_pkt, 8)) if len(p) < 3000000 else np.zeros(len(p))   # gedeckelt bei kmax: nur Schwelle >= min_pkt zaehlt
    ok = (d <= max_d) & (stuetz >= min_pkt) & (cosw >= cos_min) & (p[:, 2] > boden_z + 0.3)
    dn = np.maximum(((p - V) * Nv).sum(1), -einwaerts_max); D = np.where(ok, dn, 0.0)[:, None] * Nv
    E = m.edges_unique; n = len(V); A = sparse.coo_matrix((np.ones(len(E) * 2), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr(); deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    w = ok.astype(float)
    for _ in range(glaetten):
        Dn = (A @ (D * w[:, None])) / np.maximum(np.asarray(A @ w).ravel(), 1e-9)[:, None]; D = np.where(ok[:, None], 0.5 * D + 0.5 * Dn, D)
    m2 = trimesh.Trimesh(V + D, m.faces, process=False); mv = np.linalg.norm(D, axis=1)[ok]
    return m2, dict(knoten=int(n), haut=int(ok.sum()), carving=int(n - ok.sum()), anteil_haut=round(float(ok.mean()), 3), versatz_median_m=round(float(np.median(mv)), 3) if len(mv) else None, versatz_p95_m=round(float(np.percentile(mv, 95)), 3) if len(mv) else None,
                    verworfen_zu_weit=int((d > max_d).sum()), verworfen_ungestuetzt=int(((d <= max_d) & (stuetz < min_pkt)).sum()), verworfen_richtung=int(((d <= max_d) & (cosw < cos_min)).sum()))


def lauf(dicht, ausr, lo, hi, aus, massstab=87.0, ohne_bilder=(), vox=0.10, stl_name=None, haut=None, lod2=None, puffer_m=0.5, ueberstand_m=1.5, sigma=0.75, **kw):
    t0 = time.time(); os.makedirs(aus, exist_ok=True); X, N, pi, ii, Cc = wolke_laden(dicht, ausr, 3, ohne_bilder); log = lambda s: print(s, flush=True)
    log(f"{len(X)} Punkte, {len(pi)} Beobachtungen, {len(Cc)} Kameras ({time.time() - t0:.0f} s)")
    cp = os.path.join(aus, "carving_cache.npz")
    if os.path.exists(cp) and os.environ.get("CARVING_CACHE") == "1":
        z = np.load(cp); R = dict(dim=z["dim"], lo=z["lo"], vox=float(z["vox"]), surf=z["surf"], leer=z["leer"], beob=int(z["beob"])); log("Carving aus Zwischenspeicher (CARVING_CACHE=1)")
    else:
        R = carven(X, N, pi, ii, Cc, lo, hi, vox=vox, log=log, **kw); np.savez_compressed(cp, dim=R["dim"], lo=R["lo"], vox=R["vox"], surf=R["surf"], leer=R["leer"], beob=R["beob"])
    grund = [P for t, P in (lod2 or []) if t == "GroundSurface"]; lod2 = [(t, P) for t, P in (lod2 or []) if t != "GroundSurface"] or None
    kl = lod2_klassifizieren(lod2, X, log=log) if lod2 else None
    material, zahl = huelle(R, X, N, lod2=lod2, lod2_klassen=kl, grund=grund, cam=Cc.mean(0), puffer_m=puffer_m, ueberstand_m=ueberstand_m, log=log)
    m = netz(material, R["lo"], vox, sigma); pl = lote_ransac(X, N, np.asarray(lo), np.asarray(hi)); m, nsn = einrasten(m, pl, X)
    hz = None
    if haut:
        m, hz = haut_anlegen(m, haut, X, zahl["boden_z"]); log(f"Haut: {json.dumps(hz)}")
    import wolke_solid as WS
    pfad = stl_name or os.path.join(aus, f"wolke_carving_1-{int(massstab)}.stl"); m2, gr, okl, dv = WS.stl_dicht(m, massstab, pfad)
    erg = dict(dicht=dicht, ausrichtung=ausr, box=[list(map(float, lo)), list(map(float, hi))], voxel_m=vox, massstab=massstab, zellen=zahl, beobachtungen_carving=R["beob"], lote=len(pl), lod2_flaechen=kl, lod2_verwendet=bool(lod2), knoten_eingerastet=nsn, haut=hz, haut_datei=haut,
               stl=pfad, stl_raster_m=gr, stl_wasserdicht_nach_laden=bool(okl), kennzahlen=WS.kennzahlen(m2, massstab), sekunden=round(time.time() - t0, 1), ohne_bilder=list(ohne_bilder),
               keine_stl_gelesen="Eingabeparameter: nur Wolke/Ausrichtung/Kameras/Zuschnittquader; kein --stl; LoD2 nur wenn lod2_verwendet (Klassen je Flaeche), nie gegen die Wolke; kein DOM1")
    json.dump(erg, open(os.path.join(aus, "wolke_carving.json"), "w"), indent=1); np.savez_compressed(os.path.join(aus, "material.npz"), material=material, lo=R["lo"], vox=vox)
    log(json.dumps(erg["kennzahlen"])); log(f"-> {pfad} ({erg['sekunden']} s)"); return erg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--dicht", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--box", nargs=5, type=float, required=True, metavar=("X0", "X1", "Y0", "Y1", "Z1"), help="Zuschnittquader im Modellrahmen (m); z von --zmin"); ap.add_argument("--zmin", type=float, default=-3.0)
    ap.add_argument("--aus", required=True); ap.add_argument("--voxel", type=float, default=0.10); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--ohne-bilder", nargs="*", default=[])
    ap.add_argument("--n-beob", type=int, default=1500000); ap.add_argument("--stl-aus"); ap.add_argument("--objekt", help="objekt.json: LoD2-Flaechen (lod2.gml/id, rahmen) fuer die Dach-/Wand-Ergaenzung"); ap.add_argument("--ohne-lod2", action="store_true"); ap.add_argument("--sigma", type=float, default=0.75, help="Glaettung des Abstandsfelds (Voxel)"); ap.add_argument("--puffer", type=float, default=0.5); ap.add_argument("--ueberstand", type=float, default=1.5); ap.add_argument("--haut", help="optionale Fremdhaut (PLY, Meter, Modellrahmen) aus denselben Fotos")
    a = ap.parse_args(argv); lo = [a.box[0], a.box[2], a.zmin]; hi = [a.box[1], a.box[3], a.box[4]]
    lauf(a.dicht, a.ausrichtung, lo, hi, a.aus, a.massstab, tuple(a.ohne_bilder), a.voxel, a.stl_aus, haut=a.haut, puffer_m=a.puffer, sigma=a.sigma, ueberstand_m=a.ueberstand, lod2=(None if a.ohne_lod2 or not a.objekt else lod2_laden(a.objekt)), n_beob=a.n_beob)


if __name__ == "__main__":
    main()
