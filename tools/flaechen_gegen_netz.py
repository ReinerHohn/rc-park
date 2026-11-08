#!/usr/bin/env python3
"""flaechen_gegen_netz.py - "Geraffel"-Melder (Nutzeridee 2026-11-07): Im FOTO sind Fenster-/Wandflaechen einfarbig, im 3D-Netz sind dort Beulen.
Ablauf je Foto (K-Kamera wie foto_diff.main): Foto entzerren + verkleinern -> Netz exakt rastern (Tiefe, Flaechen-ID, Weltposition) ->
Foto in farbgleiche Flaechen zerlegen (Felzenszwalb auf geglaettetem Lab, Flaeche >= A_MIN px, Farbstreuung <= SIGMA_MAX) ->
je Flaeche die Netzpunkte darunter mit einer robusten Ebene ausgleichen; ein Netzpixel ist 'rau', wenn sein Abstand zur Ebene > RAU_FAKTOR x Pixelfussabdruck
(mindestens RAU_MIN_M) oder die Flaechennormale mehr als ANG_MAX von der Ebenennormalen abweicht. Ueber alle Fotos stimmt jedes Dreieck ab
(rau&einfarbig gegen glatt&einfarbig, nur Dreiecke mit >= N_MIN Fotos). --abbauen legt freie Knoten markierter Flaechen auf die Ausgleichsebene und glaettet (Taubin).
Beweis zuerst synthetisch (test_flaechen_gegen_netz.py), Wirkung nur ueber foto_diff (modell_wettbewerb.py): uebernehmen nur wenn kosten_lr besser und kein Foto schlechter.
  venv-seg/bin/python -I tools/flaechen_gegen_netz.py modelle/<obj>/objekt.json --stl NETZ.stl --aus DIR [--liste 000,004,...|--alle] [--abbauen]
ANNAHME grob_m/eben_min: nur Flaechen, bei denen >= 60 % der Netzpunkte innerhalb 0,3 m der Ausgleichsebene liegen, zaehlen (dunkle Arkadenoeffnungen sind einfarbig, aber tief).
ANNAHMEN (alle als Parameter, Standardwerte aus Sichtpruefung Kaufhaus, nicht aus Sollwerten): Arbeitsbreite 1600 px; einfarbig = Lab-Streuung <= 6 (nach Gauss 1.5 px);
Mindestflaeche 600 px; Rauheitsschwelle 1,0 Pixelfussabdruck, mind. 3 cm; Normalenabweichung 20 Grad; Dreieck markiert wenn >= 3 Fotos und >= 60 % rau.
Blind: Verdecker (Baeume, Fahrzeuge) vor einer einfarbigen Wand werden durch die Mehrfoto-Abstimmung nur gedaempft; gekruemmte glatte Flaechen (Kuppel) koennen als rau erscheinen."""
import sys, os, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STANDARD = dict(breite=1600, a_min=600, sigma_max=6.0, felz_scale=300, rau_faktor=1.0, rau_min_m=0.03, ang_max=20.0, rand_px=3, glaettung_px=1.5, median_px=5, rausch_px=150,
                min_px_flaeche=2, n_min=3, anteil_rau=0.6, abdeckung=0.8, cos_min=0.15, ausdehnung_min_m=0.3, grob_m=0.3, eben_min=0.6, a_min_m2=1.0, wolke_dmax=0.4, wolke_de=10.0, wolke_nb=75.0)


def segmentiere(bgr, p):
    """Rueckgabe (labels, behalten[bool je Label], bnd, streuung, area). Einfarbig = ROBUSTE Farbstreuung (1,48 x MAD je Lab-Kanal, Wurzel der Summe der Quadrate) <= sigma_max, Flaeche >= a_min.
    Rauschaufnahme (Nutzer 7.11.): (a) Medianfilter median_px auf dem Bild, (b) Felzenszwalb min_size = rausch_px, (c) kleine NICHT behaltene Zusammenhangsgebiete (< rausch_px Pixel, z.B.
    schwarze Einzelpunkte/Loecher mitten in einer Scheibe/Wand) gehen an das naechste behaltene Label, (d) die Streuung ist MAD-robust. Echte dunkle Strukturen (Fensterkreuz, Fugen > rausch_px) bleiben eigene Flaechen."""
    from skimage.segmentation import felzenszwalb, find_boundaries
    from scipy import ndimage as ndi
    b8 = bgr if bgr.dtype == np.uint8 else np.clip(bgr, 0, 255).astype(np.uint8)
    if p["median_px"] >= 3: b8 = cv2.medianBlur(b8, int(p["median_px"]) | 1)
    lab = cv2.cvtColor(b8.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab); lab_s = cv2.GaussianBlur(lab, (0, 0), p["glaettung_px"])
    labels = felzenszwalb(lab_s, scale=p["felz_scale"], sigma=0.0, min_size=max(20, int(p["rausch_px"])))
    n = labels.max() + 1; fl = labels.ravel(); area = np.bincount(fl, minlength=n).astype(float)

    def streu(lbl):
        n_ = lbl.max() + 1; a_ = np.bincount(lbl.ravel(), minlength=n_).astype(float); v = np.zeros(n_)
        for c in range(3):
            x = lab_s[..., c].ravel(); o = np.argsort(lbl.ravel(), kind="stable"); st = np.concatenate([[0], np.cumsum(a_.astype(int))])
            xs = x[o]
            for l in np.nonzero(a_ > 0)[0]:
                seg = xs[st[l]:st[l + 1]]; md = np.median(seg); v[l] += (1.4826 * np.median(np.abs(seg - md))) ** 2
        return np.sqrt(v), a_
    sg, area = streu(labels); keep = (area >= p["a_min"]) & (sg <= p["sigma_max"])
    nk = ~keep[labels]; cc, ncc = ndi.label(nk)                                                      # (c) kleine Nicht-Flaechen in behaltene Flaechen aufloesen
    if ncc:
        ca = np.bincount(cc.ravel(), minlength=ncc + 1); klein = (ca[cc] < p["rausch_px"]) & nk
        if klein.any() and (~nk).any():
            _, (iy, ix) = ndi.distance_transform_edt(~(~nk), return_indices=True); labels = np.where(klein, labels[iy, ix], labels)
            sg, area = streu(labels); keep = (area >= p["a_min"]) & (sg <= p["sigma_max"])
    bnd = find_boundaries(labels, mode="inner"); bnd = cv2.dilate(bnd.astype(np.uint8), np.ones((2 * p["rand_px"] + 1,) * 2, np.uint8)) > 0
    return labels, keep, bnd, sg, area


def ebene_robust(P, tol0):
    """Robuste Ebene (Schwerpunkt, Normale) durch Mehrfach-Trimmen: Punkte mit |Abstand| > max(2 x robustes Sigma, tol0/2) fallen weg. Rueckgabe (c, n, abstand_aller, innen)."""
    inn = np.ones(len(P), bool)
    for _ in range(4):
        c = P[inn].mean(0); u, s, vt = np.linalg.svd(P[inn] - c, full_matrices=False); n = vt[2]
        d = (P - c) @ n; r = d[inn]; sg = 1.4826 * np.median(np.abs(r - np.median(r))); inn = np.abs(d) <= max(2 * sg, tol0 / 2)
        if inn.sum() < 20: break
    return c, n, (P - c) @ n, inn, s


def foto_auswerten(m, kam, bgr, p, ausgabe=None):
    """m: trimesh im Kamerarahmen (Meter). kam: dict(R,t,f,cx,cy) fuer das ORIGINAL; bgr: entzerrtes Foto in Originalgroesse ODER schon verkleinert (kam dann passend).
    Rueckgabe dict: npx[F], nrau[F], sumN[F,3], sumD[F] (nur rau), info, Bild (BGR Ueberlagerung) oder None."""
    import render_kern as RK, torch
    H0, W0 = bgr.shape[:2]; s = min(1.0, p["breite"] / max(H0, W0))
    if s < 1.0: bgr = cv2.resize(bgr, (int(round(W0 * s)), int(round(H0 * s))), interpolation=cv2.INTER_AREA)
    H, W = bgr.shape[:2]; f = kam["f"] * s; cx = kam["cx"] * s; cy = kam["cy"] * s
    depth, fid_t, pos_t = RK.dreiecke_rastern(m, kam["R"], kam["t"], f, cx, cy, W, H, als_torch=True)
    fid = fid_t.cpu().numpy(); pos = pos_t.cpu().numpy().astype(np.float64); del fid_t, pos_t; torch.cuda.empty_cache()
    F = len(m.faces); fn = np.asarray(m.face_normals, np.float64)
    labels, keep, bnd, streuung, area = segmentiere(bgr, p)
    ok = (fid >= 0) & np.isfinite(depth)
    dg = np.zeros((H, W), bool); dd = np.where(ok, depth, np.nan)                                       # Tiefensprung (Kanten, Verdeckung) ausblenden
    for ax in (0, 1):
        j = np.abs(np.diff(dd, axis=ax)); j = np.nan_to_num(j, nan=0.0); lim = np.maximum(0.25, 0.05 * np.nan_to_num(dd[:-1] if ax == 0 else dd[:, :-1], nan=0.0))
        sp = j > lim
        if ax == 0: dg[:-1] |= sp; dg[1:] |= sp
        else: dg[:, :-1] |= sp; dg[:, 1:] |= sp
    dg = cv2.dilate(dg.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    ray = np.stack([(np.arange(W)[None] - cx) / f * np.ones((H, 1)), (np.arange(H)[:, None] - cy) / f * np.ones((1, W)), np.ones((H, W))], -1)
    Rw = np.asarray(kam["R"], float); rayw = ray @ Rw; rayw /= np.linalg.norm(rayw, axis=-1, keepdims=True)  # Blickrichtung in Welt (Zeile @ R = R^T v)
    fidc = np.clip(fid, 0, F - 1); cosb = np.abs((fn[fidc] * rayw).sum(-1))
    gut = ok & ~dg & (cosb >= p["cos_min"]) & ~bnd
    L_fi, L_r, L_nn, L_dd = [], [], [], []                                                              # je Flaeche sammeln, einmal bincount (Netze bis 2 M Dreiecke)
    rauk = np.zeros((H, W), np.float32); rauflag = np.zeros((H, W), np.uint8)                             # rauk: Abstand/Schwelle; rauflag: 1 glatt, 2 rau
    nseg = nrau_seg = 0
    ids = np.nonzero(keep)[0]; lf = labels.ravel(); order = np.argsort(lf, kind="stable"); cnt = np.bincount(lf, minlength=labels.max() + 1); start = np.concatenate([[0], np.cumsum(cnt)])
    gutr = gut.ravel(); fidr = fid.ravel(); okr = ok.ravel()
    for l in ids:
        px = order[start[l]:start[l + 1]]
        if okr[px].mean() < p["abdeckung"]: continue
        px = px[gutr[px]]
        if len(px) < p["a_min"] // 3: continue
        P = pos[np.unravel_index(px, (H, W))]; mpp = float(np.median(depth.ravel()[px])) / f; tol = max(p["rau_faktor"] * mpp, p["rau_min_m"])
        c, n, d, inn, sv = ebene_robust(P, tol)
        if inn.sum() < 20: continue
        ext = np.sqrt(np.maximum(sv[:2] ** 2 / max(inn.sum(), 1), 0)) * np.sqrt(12)
        if ext[1] < p["ausdehnung_min_m"]: continue
        if (np.abs(d) <= p["grob_m"]).mean() < p["eben_min"]: continue                                       # Flaeche im Netz GROSSRAEUMIG nicht eben (Arkade, Loggia, Relief): einfarbig sagt dort nichts ueber Ebenheit
        fi = fidr[px]; ang = np.degrees(np.arccos(np.clip(np.abs(fn[fi] @ n), 0, 1)))
        rau = (np.abs(d) > tol) | (ang > p["ang_max"])
        nseg += 1; nrau_seg += int(rau.mean() > 0.3)
        nn = np.where((fn[fi] @ n)[:, None] >= 0, n[None], -n[None])                                    # Ebene nn.x + d = 0, zur Flaechennormale ausgerichtet
        dd_ = np.where((fn[fi] @ n) >= 0, -(c @ n), (c @ n)) * np.ones(len(fi))
        L_fi.append(fi); L_r.append(rau); L_nn.append(nn.astype(np.float32)); L_dd.append(dd_.astype(np.float32))
        yy, xx = np.unravel_index(px, (H, W)); rauk[yy, xx] = np.abs(d) / tol; rauflag[yy, xx] = np.where(rau, 2, 1)
    if L_fi:
        fi = np.concatenate(L_fi); ra = np.concatenate(L_r); nn = np.concatenate(L_nn); dd_ = np.concatenate(L_dd)
        npx = np.bincount(fi, minlength=F).astype(np.float32); nrau = np.bincount(fi[ra], minlength=F).astype(np.float32)
        sumN = np.stack([np.bincount(fi[ra], nn[ra, k], minlength=F) for k in range(3)], 1).astype(np.float32); sumD = np.bincount(fi[ra], dd_[ra], minlength=F).astype(np.float32)
    else: npx = np.zeros(F, np.float32); nrau = npx.copy(); sumN = np.zeros((F, 3), np.float32); sumD = npx.copy()
    info = dict(w=W, h=H, segmente_einfarbig=int(keep.sum()), segmente_ausgewertet=nseg, segmente_rau=nrau_seg, anteil_ausgewertet_px=float((rauflag > 0).mean()),
                anteil_rau_px=float((rauflag == 2).mean()), median_mpp_cm=round(float(np.median(depth[ok])) / f * 100, 2) if ok.any() else None)
    bild = None
    if ausgabe is not None:
        b = bgr.copy(); ov = b.copy(); ov[rauflag == 1] = (0, 170, 0); ov[rauflag == 2] = (0, 0, 255); b = cv2.addWeighted(b, 0.55, ov, 0.45, 0)
        # Segmentgrenzen der behaltenen Flaechen weiss andeuten
        kb = keep[labels]; edge = cv2.morphologyEx(kb.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0; b[edge] = (255, 255, 255)
        hz = np.clip(rauk / 3.0, 0, 1); heat = cv2.applyColorMap((hz * 255).astype(np.uint8), cv2.COLORMAP_JET); heat[rauflag == 0] = (bgr[rauflag == 0] * 0.3).astype(np.uint8)
        dn = np.where(ok, depth, np.nan); lo, hi = np.nanpercentile(dn, 2) if ok.any() else 0, np.nanpercentile(dn, 98) if ok.any() else 1
        dimg = np.nan_to_num((np.clip((dn - lo) / max(hi - lo, 1e-6), 0, 1) * 255)).astype(np.uint8); dimg = cv2.cvtColor(dimg, cv2.COLOR_GRAY2BGR)
        bild = np.hstack([b, heat, dimg]); bild = cv2.resize(bild, (2100, int(bild.shape[0] * 2100 / bild.shape[1])))
        cv2.putText(bild, "gruen=einfarbig+glatt  rot=einfarbig+RAU  weiss=Flaechenrand | Mitte: Abstand/Schwelle (rot>=3) | rechts: Netztiefe", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return dict(npx=npx, nrau=nrau, sumN=sumN, sumD=sumD, info=info, bild=bild, fid=fid.astype(np.int32), bgr=bgr)


def abstimmen(erg_liste, p, F):
    """Rueckgabe dict: nfoto[F], nrau[F], markiert[F] bool, Ebene (n,d) je markiertem Dreieck (Mittel ueber rau-Pixel)."""
    nf = np.zeros(F, int); nr = np.zeros(F, int); sN = np.zeros((F, 3)); sD = np.zeros(F); sw = np.zeros(F)
    for e in erg_liste:
        v = e["npx"] >= p["min_px_flaeche"]; r = v & (e["nrau"] / np.maximum(e["npx"], 1) >= 0.5)
        nf += v; nr += r; sN += e["sumN"]; sD += e["sumD"]; sw += e["nrau"]
    mark = (nf >= p["n_min"]) & (nr / np.maximum(nf, 1) >= p["anteil_rau"])
    n = sN / np.maximum(sw, 1)[:, None]; nl = np.linalg.norm(n, axis=1); n = n / np.maximum(nl, 1e-9)[:, None]; d = sD / np.maximum(sw, 1)
    return dict(nfoto=nf, nrau=nr, markiert=mark, n=n, d=d, nlaenge=nl)


def abbauen(m, ab, iterationen=10, lam=0.5, mu=-0.53, ebene=True, winkel_max=20.0, max_m=0.3):
    """m: trimesh (beliebiger Rahmen, Ebene (n,d) muss in DEMSELBEN Rahmen sein). Freie Knoten = alle anliegenden Dreiecke markiert.
    Schritt 1 (ebene): Knoten auf mittlere Ausgleichsebene der anliegenden markierten Dreiecke, wenn deren Normalen < winkel_max auseinander (sonst Kante: bleibt).
    Schritt 2: Taubin-Glaettung (lam/mu) nur der freien Knoten, Rand fest. Rueckgabe (V_neu, frei)."""
    import scipy.sparse as sp
    F = m.faces; V = np.asarray(m.vertices, np.float64).copy(); mk = ab["markiert"]
    nv = len(V); anz = np.bincount(F.ravel(), minlength=nv); mark_anz = np.bincount(F[mk].ravel(), minlength=nv); frei = (anz > 0) & (mark_anz == anz)
    if ebene:
        sN = np.zeros((nv, 3)); sD = np.zeros(nv); cn = np.zeros(nv); minc = np.ones(nv)
        for k in range(3):
            np.add.at(sN, F[mk, k], ab["n"][mk]); np.add.at(sD, F[mk, k], ab["d"][mk]); np.add.at(cn, F[mk, k], 1.0)
        nm = sN / np.maximum(cn, 1)[:, None]; nlen = np.linalg.norm(nm, axis=1); nm /= np.maximum(nlen, 1e-9)[:, None]; dm = sD / np.maximum(cn, 1)
        for k in range(3):                                                                              # groesster Winkel eines anliegenden Dreiecks zur Mittelnormalen
            cs = (ab["n"][mk] * nm[F[mk, k]]).sum(1); np.minimum.at(minc, F[mk, k], cs)
        ok = frei & (minc >= np.cos(np.radians(winkel_max))) & (nlen > 0.5)
        dist = (V[ok] * nm[ok]).sum(1) + dm[ok]; gut = np.abs(dist) <= max_m                                # ANNAHME: Beulen < 0,3 m; groessere Spruenge sind Struktur/falsche Ebene -> Knoten bleibt
        idx = np.nonzero(ok)[0][gut]; V[idx] -= nm[idx] * dist[gut][:, None]
    E = m.edges_unique; A = sp.coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(nv, nv)); A = (A + A.T).tocsr(); deg = np.asarray(A.sum(1)).ravel()
    Dinv = sp.diags(1.0 / np.maximum(deg, 1)); L = Dinv @ A
    for _ in range(iterationen):
        for fk in (lam, mu):
            dV = L @ V - V; V[frei] += fk * dV[frei]
    return V, frei


# ---------------------------------------------------------------- Objekt-Ebene (CLI)
def lade_netz(pfad, obj, kk):
    """wie foto_diff._netz_raster, aber mit Rueckgabe der Transformation (Massstab, Verschiebung) fuer die Rueckrechnung beim Schreiben."""
    m = trimesh.load(pfad); sk = obj.get("stl_massstab", 87) / 1000.0; m.apply_scale(sk)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    tr = np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float); m.apply_translation(tr); return m, sk, tr


def wolke_regionen(m, Pw, Cw, p):
    """3D-Variante (Nutzer 7.11.): Vertexfarben aus der Wolke (naechste Nachbarn, Median, nur Punkte <= wolke_dmax), Dreiecksfarbe = Mittel der Ecken, dann zweimal ueber die
    Nachbardreiecke geglaettet (Rauschaufnahme: einzelne dunkle Punkte gehen in die Flaeche auf). Region-Growing = Zusammenhangskomponenten der Dreiecksnachbarschaft, Kante
    verbindet wenn Lab-Abstand <= wolke_de UND Normalenwinkel <= wolke_nb (locker, Beulen duerfen drin liegen). Je Region >= a_min_m2 Flaeche, robuste Farbstreuung <= sigma_max:
    robuste Ebene (Schwerpunkte), rau = Abstand > rau_min_m oder Normalenwinkel > ang_max; Region nur wenn >= eben_min der Schwerpunkte innerhalb grob_m der Ebene.
    Cw: (N,3) uint8 in der Reihenfolge RGB (ANNAHME, am Foto geprueft). Rueckgabe wie abstimmen(): markiert, n, d, nfoto (=1 beurteilt), nrau, region."""
    from scipy.spatial import cKDTree
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components
    F = len(m.faces); V = np.asarray(m.vertices); fn = np.asarray(m.face_normals); cen = V[m.faces].mean(1); fa = m.area_faces
    dist, ix = cKDTree(Pw).query(V, k=5, distance_upper_bound=p["wolke_dmax"]); okk = np.isfinite(dist); ix = np.where(okk, ix, 0)
    lab_pts = cv2.cvtColor((Cw.astype(np.float32) / 255.0).reshape(-1, 1, 3), cv2.COLOR_RGB2Lab).reshape(-1, 3)
    cv_ = lab_pts[ix]; cv_[~okk] = np.nan; vc = np.nanmedian(cv_, axis=1); vok = okk.any(1); vc[~vok] = 0
    fc = vc[m.faces].mean(1); fok = vok[m.faces].all(1)
    adj = m.face_adjacency; A = sp.coo_matrix((np.ones(len(adj)), (adj[:, 0], adj[:, 1])), shape=(F, F)); A = (A + A.T).tocsr() + sp.eye(F, format="csr")
    w = fok.astype(float)
    n_it = int(p.get("wolke_glatt_iter") or max(2, round(2 * np.sqrt(F / 165000.0))))              # Glaettungsradius in METERN konstant halten: Netzfeinheit 0,2-2 M Dreiecke
    for _ in range(n_it):
        num = A @ (fc * w[:, None]); den = A @ w; fc = np.where(den[:, None] > 0, num / np.maximum(den, 1e-9)[:, None], fc)
    de = np.linalg.norm(fc[adj[:, 0]] - fc[adj[:, 1]], axis=1); cosn = (fn[adj[:, 0]] * fn[adj[:, 1]]).sum(1)
    ok0 = fok[adj[:, 0]] & fok[adj[:, 1]] & (cosn >= np.cos(np.radians(p["wolke_nb"])))
    mark = np.zeros(F, bool); nfoto = np.zeros(F, int); nrau = np.zeros(F, int); N_ = np.zeros((F, 3)); D_ = np.zeros(F); regs = 0; rreg = 0
    todo = fok.copy()
    for stufe, fak in enumerate((1.0, 0.6, 0.35)):                                                   # Ketteneffekt (Farbverlauf A->B->C): zu streuende Komponenten mit engerer Schwelle neu zerlegen
        ok_e = ok0 & todo[adj[:, 0]] & todo[adj[:, 1]] & (de <= p["wolke_de"] * fak)
        G = sp.coo_matrix((np.ones(ok_e.sum()), (adj[ok_e, 0], adj[ok_e, 1])), shape=(F, F)); nc, lab = connected_components(G, directed=False)
        o = np.argsort(lab, kind="stable"); st = np.concatenate([[0], np.cumsum(np.bincount(lab, minlength=nc))]); neu_todo = np.zeros(F, bool)
        for l in range(nc):
            fi = o[st[l]:st[l + 1]]; fi = fi[todo[fi]]
            if len(fi) < 20 or fa[fi].sum() < p["a_min_m2"]: continue
            sg = np.sqrt(sum((1.4826 * np.median(np.abs(fc[fi, c] - np.median(fc[fi, c])))) ** 2 for c in range(3)))
            if sg > p["sigma_max"]: neu_todo[fi] = True; continue
            P = cen[fi]; c, n, d, inn, sv = ebene_robust(P, p["rau_min_m"])
            if inn.sum() < 20 or (np.abs(d) <= p["grob_m"]).mean() < p["eben_min"]: continue
            ext = np.sqrt(sv[:2] ** 2 / max(inn.sum(), 1)) * np.sqrt(12)
            if ext[1] < p["ausdehnung_min_m"]: continue
            ang = np.degrees(np.arccos(np.clip(np.abs(fn[fi] @ n), 0, 1))); rau = (np.abs(d) > p["rau_min_m"]) | (ang > p["ang_max"]); regs += 1; rreg += int(rau.mean() > 0.3)
            nfoto[fi] = 1; nrau[fi] = rau.astype(int); sgn = np.where((fn[fi] @ n) >= 0, 1.0, -1.0); N_[fi] = n[None] * sgn[:, None]; D_[fi] = -(c @ n) * sgn; mark[fi] = rau
        todo = neu_todo
    nl = nfoto.astype(float)
    return dict(nfoto=nfoto, nrau=nrau, markiert=mark, n=N_, d=D_, nlaenge=nl, regionen=int(regs), regionen_rau=int(rreg), anteil_farbe_vorhanden=float(fok.mean()))


def ausgabe_variante(m, ab, tag, p, a, sk, tr, res_extra=None):
    """PLY + abgebaut-STL + Kennzahlen je Variante."""
    F = len(m.faces); flaeche = m.area_faces; mk = ab["markiert"]; bel = ab["nfoto"] >= p["n_min"] if tag == "foto" else ab["nfoto"] >= 1
    out = dict(dreiecke=int(F), dreiecke_beurteilt=int(bel.sum()), dreiecke_markiert=int(mk.sum()), anteil_markiert_flaeche=float(flaeche[mk].sum() / flaeche.sum()),
               anteil_beurteilt_flaeche=float(flaeche[bel].sum() / flaeche.sum()), anteil_markiert_an_beurteilt=float(flaeche[mk].sum() / max(flaeche[bel].sum(), 1e-9)))
    col = np.tile(np.array([[150, 150, 150, 255]], np.uint8), (F, 1)); col[bel & ~mk] = (0, 170, 0, 255); col[mk] = (230, 30, 30, 255)
    mm = m.copy(); mm.visual.face_colors = col; mm.export(os.path.join(a.aus, f"rauheit_{tag}.ply"))
    if a.abbauen:
        V, frei = abbauen(m, ab, a.iter, ebene=not a.keine_ebene, max_m=a.max_m)
        o = trimesh.load(a.stl); V0 = np.asarray(o.vertices, np.float64); Vm = (V - tr) / sk; chg = np.nonzero(frei)[0]; Vn = V0.copy(); Vn[chg] = Vm[chg]
        o.vertices = Vn; so = os.path.join(a.aus, f"abgebaut_{tag}.stl"); o.export(so)
        d = np.linalg.norm(V[chg] - np.asarray(m.vertices)[chg], axis=1)
        out["abbau"] = dict(stl=so, freie_knoten=int(frei.sum()), knoten_gesamt=int(len(V)), verschiebung_m_mittel=float(d.mean()) if len(d) else 0.0, verschiebung_m_max=float(d.max()) if len(d) else 0.0,
                            ebene=not a.keine_ebene, iterationen=a.iter, max_m=a.max_m)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--liste"); ap.add_argument("--alle", action="store_true"); ap.add_argument("--abbauen", action="store_true")
    ap.add_argument("--variante", default="foto", choices=["foto", "wolke", "beide"]); ap.add_argument("--wolke-punkte"); ap.add_argument("--wolke-farben")
    ap.add_argument("--iter", type=int, default=10); ap.add_argument("--keine-ebene", action="store_true"); ap.add_argument("--bilder", default="ja"); ap.add_argument("--max-m", type=float, default=0.3)
    for k, v in STANDARD.items(): ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args(argv); p = {k: getattr(a, k) for k in STANDARD}
    import fehlteile_finden as FF
    od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(od)); os.makedirs(a.aus, exist_ok=True)
    nrs = a.liste.split(",") if a.liste else sorted(os.path.basename(k)[2:-5] for k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")))
    erg_l = []; per = {}; m0 = None; res = dict(stl=a.stl, parameter=p)
    for nr in nrs:
        kp = FF.k_datei(a.objekt, obj, root, nr)
        if not os.path.exists(kp): continue
        K = json.load(open(kp))
        if "kamera" not in K: continue
        fs = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
        if not fs: continue
        kk = K["kamera"]
        if m0 is None: m0 = lade_netz(a.stl, obj, kk)
        if a.variante == "wolke": break
        im = cv2.imread(fs[0]); H, W = im.shape[:2]
        s0 = min(1.0, 3200.0 / max(H, W))                                                               # erst grob verkleinern (11000-px-Fotos), dann entzerren mit skalierter Matrix
        im, k1 = FF.foto_entzerren(im if s0 == 1 else cv2.resize(im, (int(W * s0), int(H * s0)), interpolation=cv2.INTER_AREA), dict(kk, f_px=kk["f_px"] * s0, cx=kk.get("cx", W / 2) * s0, cy=kk.get("cy", H / 2) * s0) if "f_px" in kk else kk)
        R, t, f, quelle, _ = FF.kamera_laden(K, obj, nr, root, W, H)
        m = lade_netz(a.stl, obj, kk)[0]
        kam = dict(R=R, t=t, f=f * s0, cx=float(kk.get("cx", W / 2)) * s0, cy=float(kk.get("cy", H / 2)) * s0)
        e = foto_auswerten(m, kam, im, p, ausgabe=True if a.bilder == "ja" else None); erg_l.append(e); per[nr] = e["info"]
        if e["bild"] is not None: cv2.imwrite(os.path.join(a.aus, f"flaechen_{nr}.jpg"), e["bild"], [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(nr, e["info"], flush=True)
    m, sk, tr = m0; F = len(m.faces); abs_ = {}
    if a.variante in ("foto", "beide"):
        abs_["foto"] = abstimmen(erg_l, p, F)
        res["foto"] = ausgabe_variante(m, abs_["foto"], "foto", p, a, sk, tr); res["foto"]["fotos"] = list(per.keys()); res["foto"]["je_foto"] = per
        res["foto"]["fotos_mit_beitrag"] = int(sum(1 for e in erg_l if (e["nrau"] > 0).any()))
    if a.variante in ("wolke", "beide"):
        Pw = np.load(a.wolke_punkte or os.path.join(od, "sfm", "dicht_alle_modell.npy")).astype(np.float64); Cw = np.load(a.wolke_farben or os.path.join(od, "sfm", "dicht_alle_farben.npy"))
        abw = wolke_regionen(m, Pw, Cw, p); abs_["wolke"] = abw
        res["wolke"] = ausgabe_variante(m, abw, "wolke", p, a, sk, tr); res["wolke"].update(regionen=abw["regionen"], regionen_rau=abw["regionen_rau"], anteil_farbe_vorhanden=abw["anteil_farbe_vorhanden"])
    if len(abs_) == 2:
        fl = m.area_faces; A_, B_ = abs_["foto"]["markiert"], abs_["wolke"]["markiert"]; bF = abs_["foto"]["nfoto"] >= p["n_min"]; bW = abs_["wolke"]["nfoto"] >= 1; beide = bF & bW
        res["vergleich"] = dict(flaeche_beide_beurteilt_m2=float(fl[beide].sum()), markiert_foto_m2=float(fl[A_ & beide].sum()), markiert_wolke_m2=float(fl[B_ & beide].sum()),
                                markiert_beide_m2=float(fl[A_ & B_ & beide].sum()), iou_flaeche=float(fl[A_ & B_ & beide].sum() / max(fl[(A_ | B_) & beide].sum(), 1e-9)))
    if a.bilder == "ja" and erg_l:                                                                      # Abstimmungskarte je Foto und Variante: rot = markiert, gruen = beurteilt und glatt
        for tag, ab in abs_.items():
            mk = ab["markiert"]; bel = (ab["nfoto"] >= p["n_min"]) if tag == "foto" else (ab["nfoto"] >= 1)
            for nr, e in zip(per.keys(), erg_l):
                b = e["bgr"].copy(); fi = e["fid"]; v = fi >= 0; fc = np.clip(fi, 0, F - 1); ov = b.copy(); ov[v & bel[fc] & ~mk[fc]] = (0, 170, 0); ov[v & mk[fc]] = (0, 0, 255)
                cv2.imwrite(os.path.join(a.aus, f"karte_{tag}_{nr}.jpg"), cv2.addWeighted(b, 0.5, ov, 0.5, 0), [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(res, open(os.path.join(a.aus, "flaechen_gegen_netz.json"), "w"), indent=1)
    print(json.dumps({k: ({kk: vv for kk, vv in v.items() if kk != "je_foto"} if isinstance(v, dict) and k != "parameter" else v) for k, v in res.items() if k != "parameter"}, indent=1)); return res


if __name__ == "__main__":
    main()
