#!/usr/bin/env python3
"""wolke_solid.py - "Wolke zuerst" (Spec modelle/SPEC_S3b_WOLKE_ZUERST.md, Nutzer 5.11. 19:45): Buendelwolke -> druckbarer Solid, das Modell nur als Fueller.

Kette (nur Bausteine der vorhandenen Werkzeuge, nichts nachgebaut):
  1 Flaechen   fassaden.json (fassade_ortho)                      - Tiefenfeld je Flaeche: restfeld_fassade.main (Daten q 0,8, >= 3 Kameras, Band -4..+2 m, Modell per Strahl)
  2 Plausibel  |Daten - Modell| <= 2,0 m, sonst Zelle "unplausibel" (nicht uebernommen, gezaehlt); Modell NaN = "ohne Modell" (nicht angefasst)
  3 Fuellen    Zellen ohne Daten / unplausibel = Modelltiefe; TV-Glaettung (Chambolle) auf dem gefuellten Feld, Uebernahme nur gewichtet (Punktzahl, 0,3 m weicher Uebergang),
               Quantisierung auf Druckaufloesung = Duese x Massstab (0,4 mm x 87 = 3,5 cm)
  4 Durchblicke freiraum_pruefen + freiraum_fassaden (>= 6 Kameras): Zellen mit gesehenem Freiraum hinter Modellmaterial und Daten > 1 m hinter dem Modell (oder ohne Daten) werden
               Oeffnungen (Rechteckhuelle je Zusammenhangskomponente >= 0,5 m breit; bei Fuellgrad < 0,6 zellgenau)
  5 Dach       NICHT aus der Wolke: DOM1-Zellwert (eigener LoD2-Grundriss, nicht steil, > 3 m) als stetiges Hoehenfeld; Stadtmesh nur als Pruefung (Widerspruch > 0,5 m = Beobachtung)
  6 Solid      manifold3d: (Modell - Schnitte) + Auftraege - Oeffnungen, groesster Koerper, Splitter < 1e-3 m3 weg; wasserdicht, Mindestbreite (Strahltest 200 Stichproben)
  7 Ausgabe    STL (mm, 1:87), audit/wolke_solid/ (Bild je Flaeche Daten | Modell | Ergebnis | Herkunft, wolke_solid.json)
Herkunft je Zelle: 0 Modell (keine Daten) | 1 Daten bestaetigen Modell (|d| < Druckschritt) | 2 Daten veraendern (Auftrag/Schnitt) | 3 unplausibel | 4 ohne Modell | 5 Oeffnung.
ANNAHME: Duese 0,4 mm (Objektparameter), Gewicht der Zelle = Punktzahl/10 (min 0,3), Roh-DOM1 = Zellmitte-Hoehe (Zellmaximum-Lesung der Spec; Widerspruch Strahl/Zellmax steht offen, Register CM).

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_solid.py modelle/kaufhaus_null5/objekt.json --stl M.stl --fassaden F.json --aus DIR [--nur f02] [--ohne-fotos 001 024 ..]
"""
import os, sys, json, time, argparse, shutil, struct
import numpy as np, cv2, trimesh
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import freiraum_pruefen as FP, freiraum_fassaden as FFa, restfeld_fassade as RF, beweis_ansatz as BA
import manifold3d as MF

P = dict(duese_mm=0.4, massstab=87.0, zelle=0.10, plausibel=2.0, tv=0.06, gewicht_punkte=10.0, uebergang=0.3, min_punkte=3, min_kameras=3,
         oeff_min_kameras=6, oeff_tiefe=0.5, oeff_daten=1.0, oeff_breite=0.5, oeff_fuell=0.6, dach_min_h=3.0, dach_steil=2.5, dach_tol=0.035, dach_pad=0.3, splitter_m3=1e-3,
         lod2_tol_m=0.3, min_breite_relief=1.5, schnitt_aussen=0.3, ueberlapp=1.5e-3, auftrag_innen=0.15)


def schritt_m(): return P["duese_mm"] * P["massstab"] / 1000.0


# ---------------------------------------------------------------- Wolke ohne Fotos (Leck schliessen)
def wolke_filtern(dicht, aus, fotos, modus="alle"):
    """Kopie der dichten Wolke ohne Beobachtungen/Punkte der zurueckgehaltenen Fotos. modus alle: Punkte, die IRGENDEIN Foto der Liste sah, entfernen (streng);
    nur: nur Punkte entfernen, die AUSSCHLIESSLICH von den Fotos gesehen wurden, bei den uebrigen die Beobachtungen streichen (Spec-Variante)."""
    os.makedirs(aus, exist_ok=True); K = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); ids = FP.vis_ids(dicht, K)
    idx = np.array([ids.index(f) for f in fotos]); pi, ii = FP.vis_lesen(os.path.join(dicht, "fused.ply.vis")); n = int(pi.max()) + 1
    hold = np.isin(ii, idx)
    if modus == "alle": gone = np.zeros(n, bool); gone[pi[hold]] = True; keep_obs = ~gone[pi]
    else:
        rest = np.bincount(pi[~hold], minlength=n); gone = rest == 0; keep_obs = ~hold & ~gone[pi]
    keep = ~gone; new_id = np.cumsum(keep) - 1; po, io = new_id[pi[keep_obs]], ii[keep_obs]
    with open(os.path.join(dicht, "fused.ply"), "rb") as f:
        hd = []
        while True:
            l = f.readline(); hd.append(l)
            if l.strip() == b"end_header": break
        nn = int([h for h in hd if h.startswith(b"element vertex")][0].split()[-1]); props = [h.decode().split()[1:] for h in hd if h.startswith(b"property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); arr = np.frombuffer(f.read(nn * dt.itemsize), dtype=dt)
    with open(os.path.join(aus, "fused.ply"), "wb") as f:
        for h in hd: f.write(h if not h.startswith(b"element vertex") else f"element vertex {int(keep.sum())}\n".encode())
        f.write(arr[keep].tobytes())
    cnt = np.bincount(po, minlength=int(keep.sum())); out = [np.array([int(keep.sum()) & 0xffffffff, int(keep.sum()) >> 32], "<u4")]
    order = np.argsort(po, kind="stable"); io_s = io[order]; st = np.r_[0, np.cumsum(cnt)]
    parts = []
    for k in range(int(keep.sum())): parts.append(np.r_[cnt[k], io_s[st[k]:st[k + 1]]].astype("<u4"))
    with open(os.path.join(aus, "fused.ply.vis"), "wb") as f:
        f.write(out[0].tobytes()); f.write(np.concatenate(parts).tobytes())
    shutil.copy(os.path.join(dicht, "kameras_unverzerrt.json"), os.path.join(aus, "kameras_unverzerrt.json"))
    os.makedirs(os.path.join(aus, "sparse"), exist_ok=True); shutil.copy(os.path.join(dicht, "sparse", "images.bin"), os.path.join(aus, "sparse", "images.bin"))   # vis-Index-Raum unveraendert (Register CW)
    return dict(modus=modus, fotos=list(fotos), punkte_vorher=int(n), punkte_nachher=int(keep.sum()), beobachtungen_vorher=int(len(pi)), beobachtungen_nachher=int(keep_obs.sum()))


# ---------------------------------------------------------------- Felder je Flaeche
def poly_maske(F, nz, nu, zelle, rand=0.3):
    """Zellen innerhalb der Wandpolygone (u,z) der Fassade (+ Rand), aus fassaden.json polys_uz; ohne polys: alles."""
    r = F["raster"]; M = np.zeros((nz, nu), np.uint8)
    for pl in F.get("polys_uz") or []:
        q = np.array(pl, float); px = (q[:, 0] - r["u0"]) / zelle; py = (r["z1"] - q[:, 1]) / zelle
        cv2.fillPoly(M, [np.round(np.c_[px, py] * 16).astype(np.int32)], 1, shift=4)
    if not M.any(): return np.ones((nz, nu), bool)
    k = int(round(rand / zelle)) * 2 + 1
    return cv2.dilate(M, np.ones((k, k), np.uint8)) > 0


def feld_loesen(daten, modell, anzahl, wand):
    """Tiefenfeld je Flaeche: Plausibilitaet, Fuellen, TV, Gewicht, Quantisierung. Rueckgabe dict mit D (Endtiefe), dq (Aenderung gegen Modell), herkunft, Zahlen."""
    q = schritt_m(); hat_d = np.isfinite(daten) & wand; hat_m = np.isfinite(modell) & wand; versatz = 0.0
    if P.get("offset_median") and (hat_d & hat_m).any():                  # VARIANTE: systematischer Tiefenversatz der Wolke gegen das Modell (Median der Differenz je Flaeche) abziehen
        dd_ = (daten - np.where(hat_m, modell, np.nan))[hat_d & hat_m]; dd_ = dd_[np.abs(dd_) <= P["plausibel"]]
        versatz = float(np.median(dd_)) if len(dd_) else 0.0; daten = daten - versatz
    plaus = hat_d & hat_m & (np.abs(daten - np.where(hat_m, modell, 0)) <= P["plausibel"]); unpl = hat_d & hat_m & ~plaus
    nur_daten_ohne_modell = hat_d & ~hat_m
    Mf = np.where(hat_m, modell, np.nan); fill = np.where(plaus, daten, np.where(hat_m, modell, 0.0))
    tv = fill.copy()
    if plaus.sum() > 20:
        from skimage.restoration import denoise_tv_chambolle
        tv = denoise_tv_chambolle(fill.astype(np.float64), weight=P["tv"], max_num_iter=50)
    w = np.clip(anzahl / P["gewicht_punkte"], 0.3, 1.0) * plaus
    s = max(P["uebergang"] / P["zelle"] / 2.0, 0.5); wsoft = np.clip(ndi.gaussian_filter(w.astype(np.float64), s) * 1.0, 0, 1); wsoft = np.where(hat_m, wsoft, 0.0)
    # Weichuebergang laesst Modellzellen neben Daten ebenfalls leicht wandern (0,3 m): nur dort, wo ein Modell existiert; gewuenscht (Spec 3)
    dn = np.where(hat_m, wsoft * (tv - np.where(hat_m, modell, 0.0)), 0.0)
    dq = np.round(dn / q) * q
    D = np.where(hat_m, modell + dq, np.nan)
    herk = np.zeros(daten.shape, np.uint8); herk[plaus & (dq == 0)] = 1; herk[plaus & (dq != 0)] = 2; herk[(dq != 0) & ~plaus] = 2; herk[unpl] = 3; herk[(~hat_m) & wand] = 4
    n_wand = int(wand.sum())
    zahl = dict(versatz_abgezogen_m=round(versatz, 3), zellen_wand=n_wand, daten_zellen=int(hat_d.sum()), datenanteil=round(float(hat_d.sum() / max(n_wand, 1)), 3), plausibel=int(plaus.sum()), unplausibel=int(unpl.sum()),
                unplausibel_anteil_daten=round(float(unpl.sum() / max(hat_d.sum(), 1)), 3), ohne_modell=int(((~hat_m) & wand).sum()), daten_ohne_modell=int(nur_daten_ohne_modell.sum()),
                auftrag_zellen=int((dq > 0).sum()), schnitt_zellen=int((dq < 0).sum()), aenderung_anteil=round(float((dq != 0).sum() / max(n_wand, 1)), 3),
                aenderung_mittel_abs_cm=round(float(np.abs(dq[dq != 0]).mean() * 100), 1) if (dq != 0).any() else 0.0,
                rest_vorher_cm=round(float(np.abs(daten - modell)[plaus].mean() * 100), 1) if plaus.any() else None,
                rest_nachher_cm=round(float(np.abs(daten - D)[plaus].mean() * 100), 1) if plaus.any() else None)
    return dict(D=D, dq=dq, herkunft=herk, plaus=plaus, hat_m=hat_m, hat_d=hat_d, zahl=zahl)


def wand_status(daten, wand, tol=None, min_anteil=0.20):
    """Nutzerregel 5.11. 20:15: LoD2-Ebene gegen Wolkenpunkte (>= 3 Kameras) im Band: Median |Tiefe| <= lod2_tol UND >= 20 % der Wandzellen mit Daten -> bestaetigt;
    Median > tol -> widerspruch (Ebene aus der Wolke); < 20 % Daten -> unbestaetigt (LoD2 nur zum Schliessen)."""
    tol = P["lod2_tol_m"] if tol is None else tol; hat = np.isfinite(daten) & wand; anteil = float(hat.sum() / max(wand.sum(), 1))
    med = float(np.median(np.abs(daten[hat]))) if hat.any() else None
    if anteil < min_anteil: st = "unbestaetigt"
    elif med is not None and med > tol: st = "widerspruch"
    else: st = "bestaetigt"
    return dict(status=st, median_abs_m=None if med is None else round(med, 3), datenanteil=round(anteil, 3), tol_m=tol)


def ebene_aus_wolke(X, F, band=1.5):
    """RANSAC (Lot in xy) der senkrechten Wandebene aus den Wolkenpunkten im Band um die LoD2-Ebene (nur bei Widerspruch). Rueckgabe neues F oder None."""
    n = np.array(F["n"], float); d = np.array(F["d"], float); o = np.array(F["o"], float); rel = X[:, :2] - o; w = rel @ n; u = rel @ d
    k = (np.abs(w) < band) & (u >= F["u"][0]) & (u <= F["u"][1]) & (X[:, 2] >= F["z"][0]) & (X[:, 2] <= F["z"][1])
    Q = X[k, :2]
    if len(Q) < 500: return None
    rng = np.random.default_rng(1); best = (0, None)
    for _ in range(400):
        a, b = Q[rng.choice(len(Q), 2, replace=False)]; t = b - a
        if np.linalg.norm(t) < 1.0: continue
        nn = np.array([t[1], -t[0]]) / np.linalg.norm(t); nn = nn if nn @ n > 0 else -nn; c = ((Q - a) @ nn); inl = int((np.abs(c) < 0.15).sum())
        if inl > best[0]: best = (inl, (nn, a))
    if best[1] is None: return None
    nn, a = best[1]; G = dict(F); G["n"] = nn.tolist(); G["d"] = [-nn[1], nn[0]]; off = np.median(((Q - a) @ nn)[np.abs((Q - a) @ nn) < 0.15]); G["o"] = (a + nn * off).tolist()
    uu = (Q - np.array(G["o"])) @ np.array(G["d"]); du = np.array(G["d"]) @ d
    G["u"] = [float(np.percentile(uu, 1)), float(np.percentile(uu, 99))]; r = F["raster"]; zc = F["raster"]["zelle"]
    G["raster"] = dict(u0=G["u"][0] - 0.5, z1=r["z1"], nu=int(np.ceil((G["u"][1] - G["u"][0] + 1.0) / zc)), nz=r["nz"], zelle=zc); G["polys_uz"] = None
    return G


def freiraum_raster(F, fr, nz, nu, zelle):
    """freiraum_fassaden-Karte (0,25 m, z aufsteigend ab z0) auf das (u0, z1)-Raster der Flaeche (z absteigend) bringen -> (Tiefe m, Kameras)."""
    out = np.zeros((nz, nu)); kam = np.zeros((nz, nu), int)
    if fr is None: return out, kam
    M = np.array(fr["raster"]); K = np.array(fr["kameras"]); z0f = fr["z"][0]; u0f = fr["u"][0]; zf = fr["zelle"]; r = F["raster"]
    gu = r["u0"] + (np.arange(nu) + 0.5) * zelle; gz = r["z1"] - (np.arange(nz) + 0.5) * zelle
    iu = np.floor((gu - u0f) / zf).astype(int); iz = np.floor((gz - z0f) / zf).astype(int)
    okc = (iu >= 0) & (iu < M.shape[1]); okr = (iz >= 0) & (iz < M.shape[0])
    sub = np.zeros((nz, nu)); subk = np.zeros((nz, nu), int)
    sub[np.ix_(okr, okc)] = M[np.ix_(iz[okr], iu[okc])]; subk[np.ix_(okr, okc)] = K[np.ix_(iz[okr], iu[okc])]
    return sub, subk


def oeffnungen(F, res, frei, nz, nu, wand):
    """Zellen: gesehener Freiraum hinter Modellmaterial (>= oeff_tiefe) UND (keine Daten ODER Daten > oeff_daten hinter dem Modell) -> Komponenten >= oeff_breite."""
    zelle = P["zelle"]; modell = np.where(res["hat_m"], res["D"], np.nan)
    d = res["_daten"]; hinter = np.isfinite(d) & (d < res["_modell"] - P["oeff_daten"]); ohne = ~np.isfinite(d)
    # Nutzer 5.11. 20:50: Durchblick = gesehener Freiraum (>= 6 Kameras) ODER Daten > 1 m hinter der Ebene -> OEFFNUNG, nicht Relief (vorher UND mit "keine Daten": griff an der Front nie)
    # Fassung 20:50 (Koordination: Freiraum ODER Daten > 1 m hinter der Ebene) lieferte am Kaufhaus Arkade = 3 und schnitt den Giebelbereich (Komponente 18,5 x 6,8 m, Tiefe 1,5 m) weg
    # -> verworfen (Befund in OR_regel/): Durchblick = gesehener Freiraum (>= 6 Kameras) UND (keine Daten ODER Daten > 1 m hinter dem Modell)
    tiefer = np.isfinite(d) & (d < -P["oeff_daten"])
    cand = (frei >= P["oeff_tiefe"]) & res["hat_m"] & wand & (hinter | ohne)
    cand = ndi.binary_closing(cand, np.ones((3, 3))) & res["hat_m"]
    tiefen = np.maximum(frei, np.where(tiefer, -np.nan_to_num(d), 0.0))
    lab, nl = ndi.label(cand); out = []
    for j in range(1, nl + 1):
        ys, xs = np.where(lab == j); h, w = (ys.max() - ys.min() + 1) * zelle, (xs.max() - xs.min() + 1) * zelle
        if min(h, w) < P["oeff_breite"]: continue
        fuell = len(ys) / ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)); tiefe = float(np.clip(np.percentile(tiefen[lab == j], 75), P["oeff_tiefe"], 4.0))
        out.append(dict(komponente=j, zellen=int(len(ys)), breite_m=round(w, 2), hoehe_m=round(h, 2), fuellgrad=round(float(fuell), 2), tiefe_m=round(tiefe, 2),
                        huelle=bool(fuell >= P["oeff_fuell"]), iu=[int(xs.min()), int(xs.max())], iz=[int(ys.min()), int(ys.max())], maske=(lab == j)))
    return out


# ---------------------------------------------------------------- Koerper
def _cube_uvw(F3, u_c, w_lo, w_hi, z_c, du, dz):
    """Quader in Flaechenkoordinaten: u Mitte/Breite, w von lo bis hi (entlang n), z Mitte/Hoehe -> Manifold im Modellrahmen."""
    n, dd, e, o = F3
    c = MF.Manifold.cube([du + 2 * P["ueberlapp"], max(w_hi - w_lo, 1e-4), dz + 2 * P["ueberlapp"]], True)   # Ueberlappung statt Kantenkontakt (sonst Kanten mit 4 Flaechen im STL)
    mid = o + dd * u_c + e * z_c + n * 0.5 * (w_lo + w_hi)
    T = np.array([[dd[0], n[0], e[0], mid[0]], [dd[1], n[1], e[1], mid[1]], [dd[2], n[2], e[2], mid[2]]], float)
    return c.transform(T)


def _runs(lo, hi, mask):
    """Zeilenweise Laeufe gleicher (lo, hi) -> Liste (iz, iu0, iu1, lo, hi)."""
    out = []; nz, nu = mask.shape
    for iz in range(nz):
        row = np.where(mask[iz])[0]
        if not len(row): continue
        st = row[0]; prev = row[0]
        for iu in list(row[1:]) + [None]:
            if iu is not None and iu == prev + 1 and abs(lo[iz, iu] - lo[iz, st]) < 1e-9 and abs(hi[iz, iu] - hi[iz, st]) < 1e-9: prev = iu; continue
            out.append((iz, st, prev, float(lo[iz, st]), float(hi[iz, st])))
            if iu is not None: st = iu; prev = iu
    return out


def flaechen_koerper(F, res, offen):
    """Auftraege (Daten weiter aussen) und Schnitte (Daten tiefer) als Quader je Zelllauf + Oeffnungsquader. Rueckgabe (auftraege, schnitte, oeffnungen, Zahl)."""
    zelle = P["zelle"]; r = F["raster"]; nz, nu = res["D"].shape
    n = np.r_[F["n"][:2], 0.0]; dd = np.r_[F["d"][:2], 0.0]; e = np.array([0, 0, 1.0]); o = np.r_[F["o"][:2], 0.0]; F3 = (n, dd, e, o)
    Mod = np.where(res["hat_m"], res["_modell"], 0.0); D = np.where(res["hat_m"], res["D"], 0.0); dq = res["dq"]
    auf = dq > 0; sch = dq < 0
    A = [_cube_uvw(F3, r["u0"] + (b + a + 1) * 0.5 * zelle, hi_lo, hi_hi, r["z1"] - (iz + 0.5) * zelle, (b - a + 1) * zelle, zelle) for (iz, a, b, hi_lo, hi_hi) in
         _runs(Mod - P["auftrag_innen"], D, auf)]
    S = [_cube_uvw(F3, r["u0"] + (b + a + 1) * 0.5 * zelle, lo, hi, r["z1"] - (iz + 0.5) * zelle, (b - a + 1) * zelle, zelle) for (iz, a, b, lo, hi) in _runs(D, Mod + P["schnitt_aussen"], sch)]
    O = []
    for c in offen:
        w_hi = float(np.nanmax(Mod[c["maske"]])) + P["schnitt_aussen"]; w_lo = float(np.nanmax(Mod[c["maske"]])) - c["tiefe_m"]
        if c["huelle"]:
            (a, b), (z0, z1) = c["iu"], c["iz"]
            O.append(_cube_uvw(F3, r["u0"] + (b + a + 1) * 0.5 * zelle, w_lo, w_hi, r["z1"] - (z0 + z1 + 1) * 0.5 * zelle, (b - a + 1) * zelle, (z1 - z0 + 1) * zelle))
        else:
            lo = np.where(c["maske"], w_lo, 0.0); hi = np.where(c["maske"], w_hi, 0.0)
            O += [_cube_uvw(F3, r["u0"] + (b + a + 1) * 0.5 * zelle, l_, h_, r["z1"] - (iz + 0.5) * zelle, (b - a + 1) * zelle, zelle) for (iz, a, b, l_, h_) in _runs(lo, hi, c["maske"])]
    return A, S, O


def feldkoerper(X, Y, top, bot, mask):
    """Geschlossene Koerper aus Hoehenfeld: Knotenraster (ny, nx) mit X,Y,top,bot, Zellmaske (ny-1, nx-1); je 4er-Komponente ein Koerper (Manifold-Liste)."""
    lab, nl = ndi.label(mask); out = []; ny, nx = top.shape
    for j in range(1, nl + 1):
        cm = lab == j; V = []; vid = {}; Fc = []
        def vi(i, k, kind):
            key = (i, k, kind)
            if key not in vid: vid[key] = len(V); V.append([X[i, k], Y[i, k], top[i, k] if kind == 0 else min(bot[i, k], top[i, k] - 1e-3)])
            return vid[key]
        for i, k in zip(*np.where(cm)):
            a, b, c, d = (i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k)
            t = [vi(*q, 0) for q in (a, b, c, d)]; s = [vi(*q, 1) for q in (a, b, c, d)]
            Fc += [(t[0], t[1], t[2]), (t[0], t[2], t[3]), (s[0], s[2], s[1]), (s[0], s[3], s[2])]
            for (qa, qb, ni, nk) in ((a, b, i - 1, k), (b, c, i, k + 1), (c, d, i + 1, k), (d, a, i, k - 1)):
                nb = cm[ni, nk] if (0 <= ni < cm.shape[0] and 0 <= nk < cm.shape[1]) else False
                if nb: continue
                ta, tb, sa, sb = vi(*qa, 0), vi(*qb, 0), vi(*qa, 1), vi(*qb, 1)
                Fc += [(ta, sa, sb), (ta, sb, tb)]
        m = trimesh.Trimesh(np.array(V, float), np.array(Fc), process=False)
        if m.volume < 0: m.invert()
        mm = MF.Manifold(MF.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
        if mm.status() != MF.Error.NoError or mm.volume() <= 0:
            m.fix_normals(); mm = MF.Manifold(MF.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
        if mm.status() == MF.Error.NoError and mm.volume() > 0: out.append(mm)
    return out


def _dach_geometrie(Cm, lx, ly, Z, zellen, HS=None, art="", quelle=""):
    """Hoehenfeld Z (Knotenraster lx, ly; zellen = gueltige Knoten) gegen die Oberkante des Modells (Strahl von oben): Auftrag wo Z hoeher, Schnitt wo tiefer."""
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    ny, nx = Z.shape; zi, zj = np.where(zellen)
    org = np.c_[lx[zi, zj], ly[zi, zj], np.full(len(zi), float(Cm.bounds[1][2]) + 10)]
    loc, ri, _ = RayMeshIntersector(Cm).intersects_location(org, np.tile([0, 0, -1.0], (len(org), 1)), multiple_hits=True)
    HC = np.full((ny, nx), np.nan); top = {}
    for q, l in zip(ri, loc): top[q] = max(top.get(q, -np.inf), l[2])
    for q, v in top.items(): HC[zi[q], zj[q]] = v
    HS = np.full((ny, nx), np.nan) if HS is None else HS
    ok = zellen & np.isfinite(HC); dZ = np.where(ok, Z - HC, np.nan)
    cell = lambda A: np.stack([A[:-1, :-1], A[:-1, 1:], A[1:, 1:], A[1:, :-1]], 0)
    cok = np.all(cell(ok), 0); cd = np.nanmean(cell(np.where(ok, dZ, np.nan)), 0) if cok.any() else np.zeros((ny - 1, nx - 1))
    amask = cok & (cd > P["dach_tol"]); smask = cok & (cd < -P["dach_tol"])
    # Diagonalkontakt vermeiden (Kantenkontakt = Kante mit 4 Flaechen): Masken um 1 Zelle in 4er-Nachbarschaft schliessen
    st4 = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
    amask = ndi.binary_closing(amask, np.ones((2, 2), bool)) & cok if amask.any() else amask; smask = ndi.binary_closing(smask, np.ones((2, 2), bool)) & cok if smask.any() else smask
    pad = P["dach_pad"]
    auf = feldkoerper(lx, ly, np.where(ok, Z, 0.0), np.where(ok, np.minimum(Z, HC) - pad, 0.0), amask)
    sch = feldkoerper(lx, ly, np.where(ok, np.maximum(Z, HC) + pad, 0.0), np.where(ok, Z, 0.0), smask & ~amask)
    stat = dict(art=art, quelle=quelle, zellen_dach=int(zellen.sum()), mit_modell=int(ok.sum()), auftrag_zellen=int(amask.sum()), schnitt_zellen=int(smask.sum()),
                dz_median_m=round(float(np.nanmedian(dZ)), 3) if ok.any() else None, dz_mittel_abs_m=round(float(np.nanmean(np.abs(dZ))), 3) if ok.any() else None,
                auftrag_koerper=len(auf), schnitt_koerper=len(sch))
    return auf, sch, stat, HC


def dach_koerper(k, Cm, stadtmesh=None):
    """VARIANTE mit_lod2/DOM1 (Spec S3b alt): DOM1-Zellwert als Hoehenfeld im eigenen LoD2-Grundriss. Nicht Hauptpfad."""
    D = BA.dom1_laden(k); eigen, art = BA.eigener_grundriss(k, D); Z = D["Z"]
    gy, gx = np.gradient(np.where(np.isfinite(Z), Z, 0.0)); steil = np.hypot(gx, gy) > P["dach_steil"]
    zellen = eigen & (Z > P["dach_min_h"]) & ~steil & np.isfinite(Z)
    auf, sch, stat, HC = _dach_geometrie(Cm, D["lx"], D["ly"], Z, zellen, None, art, D["quelle"])
    return auf, sch, stat, dict(Z=Z, HC=HC, HS=np.full(Z.shape, np.nan), zellen=zellen, lx=D["lx"], ly=D["ly"], dom=D)


def ebenen_ransac(Q, Nq, tol=0.15, min_pts=600, n_max=6, iters=1500, seed=1):
    """Sequentieller RANSAC geneigter Dachebenen (Normale nach oben, nz > 0.35) in der Wolke. Rueckgabe Liste (n, d, Indizes)."""
    rng = np.random.default_rng(seed); idx = np.arange(len(Q)); out = []
    for _ in range(n_max):
        if len(idx) < min_pts: break
        T = rng.choice(len(idx), (iters, 3)); A, B, C_ = Q[idx[T[:, 0]]], Q[idx[T[:, 1]]], Q[idx[T[:, 2]]]; nn = np.cross(B - A, C_ - A); ln = np.linalg.norm(nn, axis=1); nn /= np.maximum(ln, 1e-12)[:, None]
        nn *= np.where(nn[:, 2] < 0, -1.0, 1.0)[:, None]; gut = (ln > 1e-6) & (nn[:, 2] > 0.35)
        best, bi = 0, None
        for j in np.where(gut)[0][:iters]:
            d_ = np.abs((Q[idx] - A[j]) @ nn[j]); inl = (d_ < tol) & (np.abs(Nq[idx] @ nn[j]) > 0.8); c = int(inl.sum())
            if c > best: best, bi, bn, ba = c, inl, nn[j], A[j]
        if bi is None or best < min_pts: break
        I = idx[bi]; c0 = Q[I].mean(0); _, _, Vt = np.linalg.svd(Q[I] - c0, full_matrices=False); n2 = Vt[2] * (1 if Vt[2][2] > 0 else -1)
        d_ = np.abs((Q[idx] - c0) @ n2); I = idx[(d_ < tol) & (np.abs(Nq[idx] @ n2) > 0.8)]
        out.append((n2, c0, I)); idx = np.setdiff1d(idx, I)
    return out


def dach_aus_wolke(Cm, X, N, gs=0.5, min_pts_zelle=3, max_ext=6.0):
    """HAUPTPFAD Dach (Nutzerentscheid 5.11. 20:10): nur Wolkenpunkte (>= 3 Kameras). Hoehenfeld je Zelle = Median der aufwaerts gerichteten Punkte (Normale nz > 0.35, z > 4 m) im Grundriss des Modells
    (Rahmen/Grundriss: Modellkoerper); Zellen ohne Punkte: Dachebene aus den Wolkenpunkten (RANSAC) verlaengert, wenn eine Ebene <= max_ext m entfernt ist und im Modellband +-3 m liegt (ANNAHME), sonst bleibt das Modell
    (unbestaetigt). Keine Nord/Sued-Spiegelung. Rueckgabe wie dach_koerper plus Zellen-Herkunft."""
    from scipy.spatial import cKDTree
    b = Cm.bounds; xs = np.arange(b[0][0] - 1, b[1][0] + 1, gs) + gs / 2; ys = np.arange(b[0][1] - 1, b[1][1] + 1, gs) + gs / 2; lx, ly = np.meshgrid(xs, ys)
    ny, nx = lx.shape
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    org = np.c_[lx.ravel(), ly.ravel(), np.full(lx.size, float(b[1][2]) + 10)]; loc, ri, _ = RayMeshIntersector(Cm).intersects_location(org, np.tile([0, 0, -1.0], (len(org), 1)), multiple_hits=True)
    HC = np.full(lx.size, np.nan)
    for q, l in zip(ri, loc): HC[q] = l[2] if np.isnan(HC[q]) else max(HC[q], l[2])
    HC = HC.reshape(ny, nx); fp = np.isfinite(HC) & (HC > 4.0)
    sel = (N[:, 2] > 0.35) & (X[:, 2] > 4.0) & (X[:, 0] > b[0][0] - 1) & (X[:, 0] < b[1][0] + 1) & (X[:, 1] > b[0][1] - 1) & (X[:, 1] < b[1][1] + 1)
    Q, Nq = X[sel], N[sel]; ix = ((Q[:, 0] - xs[0]) / gs + 0.5).astype(int); iy = ((Q[:, 1] - ys[0]) / gs + 0.5).astype(int); okc = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    ix, iy, Qz = ix[okc], iy[okc], Q[okc, 2]; Hd = np.full((ny, nx), np.nan); cnt = np.zeros((ny, nx), int)
    key = iy * nx + ix; o = np.argsort(key); ks, zs = key[o], Qz[o]; u, st = np.unique(ks, return_index=True); en = np.r_[st[1:], len(ks)]
    for kk, a_, b_ in zip(u, st, en):
        if b_ - a_ >= min_pts_zelle:
            Hd[kk // nx, kk % nx] = np.median(zs[a_:b_]); cnt[kk // nx, kk % nx] = b_ - a_
    # Punkte nur im Modellgrundriss (4-Nachbarschaft um fp erweitert) und nicht weit ueber/unter dem Modell (Baeume, Nachbarn): |Hd - HC| <= 3 m
    nahe = ndi.binary_dilation(fp, iterations=1); datenz = np.isfinite(Hd) & nahe & (np.abs(Hd - np.where(np.isfinite(HC), HC, Hd)) <= 3.0)
    Z = np.where(datenz, Hd, np.nan); herk = np.zeros((ny, nx), np.uint8); herk[datenz] = 1   # 1 Wolke
    qx = np.clip(((Q[:, 0] - xs[0]) / gs + 0.5).astype(int), 0, nx - 1); qy = np.clip(((Q[:, 1] - ys[0]) / gs + 0.5).astype(int), 0, ny - 1); qn = nahe[qy, qx]
    pl = ebenen_ransac(Q[qn], Nq[qn]) if datenz.any() else []
    fehlt = fp & ~datenz
    if pl and fehlt.any():
        best = np.full((ny, nx), np.inf); zbest = np.full((ny, nx), np.nan)
        for (n2, c0, I) in pl:
            sup = np.zeros((ny, nx), bool); sx = np.clip(((Q[I, 0] - xs[0]) / gs + 0.5).astype(int), 0, nx - 1); sy = np.clip(((Q[I, 1] - ys[0]) / gs + 0.5).astype(int), 0, ny - 1); sup[sy, sx] = True
            dist = ndi.distance_transform_edt(~sup) * gs; zp = c0[2] - ((lx - c0[0]) * n2[0] + (ly - c0[1]) * n2[1]) / n2[2]
            gut = (dist <= max_ext) & (np.abs(zp - np.where(np.isfinite(HC), HC, zp)) <= 3.0) & (dist < best); best = np.where(gut, dist, best); zbest = np.where(gut, zp, zbest)
        ext = fehlt & np.isfinite(zbest); Z = np.where(ext, zbest, Z); herk[ext] = 2   # 2 Ebene verlaengert
    if P.get("offset_median") and datenz.any():
        dz0 = float(np.nanmedian((Z - HC)[datenz & np.isfinite(HC)])); Z = Z - dz0; erg_dz = dz0
    zellen = np.isfinite(Z)
    # Glaetten der Datenzellen: Median 3x3 ueber vorhandene Zellen
    Zs = Z.copy(); 
    for i in range(1, ny - 1):
        for j in range(1, nx - 1):
            if herk[i, j] == 1:
                w = Z[i - 1:i + 2, j - 1:j + 2]; w = w[np.isfinite(w)]; Zs[i, j] = np.median(w)
    auf, sch, stat, HC2 = _dach_geometrie(Cm, lx, ly, Zs, zellen, None, "Wolke (nz>0.35, z>4 m, Median je 0,5-m-Zelle) + RANSAC-Ebenenverlaengerung", "fused.ply")
    stat.update(modell_footprint_zellen=int(fp.sum()), zellen_wolke=int((herk == 1).sum()), zellen_ebene=int((herk == 2).sum()), zellen_unbestaetigt=int((fp & (herk == 0)).sum()),
                datenanteil=round(float((herk == 1).sum() / max(fp.sum(), 1)), 3), ebenen=[dict(n=[round(float(x), 3) for x in n2], punkte=int(len(I))) for n2, c0, I in pl])
    return auf, sch, stat, dict(Z=Zs, HC=HC2, HS=np.full(Zs.shape, np.nan), zellen=zellen, lx=lx, ly=ly, herk=herk)


def manifold_aus_trimesh(m):
    mm = MF.Manifold(MF.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if mm.status() != MF.Error.NoError:
        m = m.copy(); m.merge_vertices(); trimesh.repair.fix_normals(m); mm = MF.Manifold(MF.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if mm.status() != MF.Error.NoError: raise RuntimeError(f"Modell nicht manifold: {mm.status()}")
    return mm


def zu_trimesh(mf):
    """Manifold -> trimesh MIT den Merge-Vektoren von manifold3d (to_mesh liefert Knoten je Eigenschaft doppelt; ohne Zusammenfuehren zerfaellt der Koerper beim split, Befund T1 5.11.)."""
    me = mf.to_mesh(); V = np.asarray(me.vert_properties)[:, :3].astype(float); F = np.asarray(me.tri_verts).astype(np.int64)
    mfv = np.asarray(getattr(me, "merge_from_vert", [])); mtv = np.asarray(getattr(me, "merge_to_vert", []))
    if len(mfv): idx = np.arange(len(V)); idx[mfv] = mtv; F = idx[F]
    t = trimesh.Trimesh(V, F, process=False); t.remove_unreferenced_vertices(); return t


def pinch_beheben(R, n_iter=5, kante=0.004):
    """Kanten, an denen sich Teile nur beruehren (nach Knotenverschweissung 4 statt 2 Flaechen an einer Kante), bekommen einen kleinen Quader (4 mm im Modell = 0,05 mm im Druck) als Vereinigung:
    aus Kantenkontakt wird Volumenkontakt. Rueckgabe (Manifold, Anzahl schlechter Kanten je Runde)."""
    hist = []
    for _ in range(n_iter):
        t = zu_trimesh(R); tm = trimesh.Trimesh(t.vertices.copy(), t.faces.copy(), process=True); e = tm.edges_sorted; u, c = np.unique(e, axis=0, return_counts=True); bad = u[c != 2]; hist.append(int(len(bad)))
        if not len(bad): break
        mid = 0.5 * (tm.vertices[bad[:, 0]] + tm.vertices[bad[:, 1]]); cubes = [MF.Manifold.cube([kante] * 3, True).translate(list(q)) for q in mid]
        R = R + MF.Manifold.batch_boolean(cubes, MF.OpType.Add)
    return R, hist


def wand_test(m_m, massstab, n=200):
    """Strahltest wie beweis_ansatz.geometrie_druck (Stichproben, erster Treffer nach innen), Ergebnis in mm im Druckmassstab; Anteil unter 0,85 x Duese."""
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    mm = m_m.copy(); mm.apply_scale(1000.0 / massstab); Pp, fi = trimesh.sample.sample_surface(mm, n, seed=1); Pp = np.asarray(Pp); nn = mm.face_normals[fi]
    o = Pp - nn * 1e-3; loc, ri, _ = RayMeshIntersector(mm).intersects_location(o, -nn, multiple_hits=False); d = np.full(len(Pp), np.nan); d[ri] = np.linalg.norm(loc - o[ri], axis=1)
    g = d[np.isfinite(d)]; lim = 0.85 * P["duese_mm"]
    return dict(n=int(len(g)), min_mm=round(float(g.min()), 2), p5_mm=round(float(np.percentile(g, 5)), 2), anteil_unter_grenze=round(float(np.mean(g < lim)), 3), grenze_mm=round(lim, 3))


def stl_dicht(m_m, massstab, pfad):
    """STL-Rundlauf-fest machen: manifold3d liefert float32-Splitter (Befund 5.11.: 27512 entartete Dreiecke, nach dem STL-Laden 4971 offene Kanten). Knoten auf 0,1-mm-Raster (Modell), Entartete weg,
    pymeshfix (groesster Koerper), dann STL schreiben, neu laden, Wasserdichtheit/Koerperzahl/Volumenabweichung pruefen. Rueckgabe (mesh_m, Raster_m, ok, Volumenabweichung)."""
    import pymeshfix
    v0 = abs(float(m_m.volume)); res = None; first = None
    for g, fix in ((0.0, False), (1e-4, False), (1e-4, True), (2e-4, True), (5e-4, True)):
        mm = trimesh.Trimesh(np.asarray(m_m.vertices, float).copy(), m_m.faces.copy(), process=False)
        if g:
            mm.vertices = np.round(mm.vertices / g) * g; mm.merge_vertices(); mm.update_faces(mm.nondegenerate_faces()); mm.remove_unreferenced_vertices()
        r = mm
        if fix:
            mf = pymeshfix.MeshFix(mm.vertices.copy(), mm.faces.copy()); mf.repair(); r = trimesh.Trimesh(mf.points, mf.faces.reshape(-1, 3), process=False)
        parts = r.split(only_watertight=False); r = max(parts, key=lambda c: abs(c.volume)) if len(parts) > 1 else r
        out = trimesh.Trimesh(r.vertices * 1000.0 / massstab, r.faces, process=False); out.export(pfad); chk = trimesh.load(pfad, force="mesh"); dv = abs(abs(float(r.volume)) - v0) / v0
        res = (r, g if not fix else -g, bool(chk.is_watertight and len(chk.split(only_watertight=False)) == 1 and dv < 0.02), dv)   # Raster negativ = mit pymeshfix
        if res[2]: return res
        if first is None: first = res
    # kein Versuch hat Wasserdichtheit nach dem STL-Rundlauf erreicht: unveraendertes Ergebnis (groesster Koerper) schreiben, Flag False (Kantenkontakt der Quader, Befund T1/Martinstor)
    out = trimesh.Trimesh(first[0].vertices * 1000.0 / massstab, first[0].faces, process=False); out.export(pfad); return first


def kennzahlen(m_m, massstab):
    parts = m_m.split(only_watertight=False)
    return dict(koerper=len(parts), wasserdicht=bool(m_m.is_watertight), volumen_cm3_1_87=round(abs(float(m_m.volume)) * 1e6 / massstab ** 3, 1), volumen_m3=round(abs(float(m_m.volume)), 2),
                dreiecke=int(len(m_m.faces)), wand=wand_test(m_m, massstab))


# ---------------------------------------------------------------- Bilder
def flaechenbild(fid, res, zahl, pfad):
    D, M = res["D"], res["_modell"]; dat = res["_daten"]; tief, vor = 4.0, 2.0
    cm = lambda A, lo, hi: cv2.applyColorMap(np.clip((np.nan_to_num(A, nan=lo) - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
    bd = cm(dat, -tief, vor); bd[~np.isfinite(dat)] = 40; bm = cm(M, -tief, vor); bm[~np.isfinite(M)] = 40; be = cm(D, -tief, vor); be[~np.isfinite(D)] = 40
    pal = {0: (90, 90, 90), 1: (80, 200, 80), 2: (0, 200, 255), 3: (60, 60, 230), 4: (0, 0, 0), 5: (255, 140, 0)}; bh = np.zeros(D.shape + (3,), np.uint8)
    for kk, c in pal.items(): bh[res["herkunft"] == kk] = c
    nz, nu = D.shape; sk = max(1, int(round(360 / max(nz, 1)))); tiles = []
    for im, t in ((bd, "Daten (Wolke q0,8)"), (bm, "Modell C"), (be, "Ergebnis C'"), (bh, "Herkunft")):
        im = cv2.resize(im, (nu * sk, nz * sk), interpolation=cv2.INTER_NEAREST); cv2.putText(im, t, (6, 18), 0, 0.55, (255, 255, 255), 1, cv2.LINE_AA); tiles.append(im)
    bild = cv2.hconcat(tiles)
    leg = f"{fid} [{zahl.get('wandstatus', '')}]: grau Modell | gruen Daten=Modell | gelb Daten veraendern | rot unplausibel | schwarz ohne Modell | orange Oeffnung   Daten {zahl['datenanteil']:.0%} unplausibel {zahl['unplausibel']} Auftrag {zahl['auftrag_zellen']} Schnitt {zahl['schnitt_zellen']}"
    pad = np.full((24, bild.shape[1], 3), 30, np.uint8); cv2.putText(pad, leg, (6, 17), 0, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, cv2.vconcat([pad, bild]), [cv2.IMWRITE_JPEG_QUALITY, 88])


# ---------------------------------------------------------------- Hauptablauf
def lauf(objp, stl, fassaden, aus, dicht=None, ausr=None, nur=None, ohne_fotos=None, foto_modus="alle", stadtmesh=None, dach="wolke", gebe_stl=None, min_flaeche=7.0, unterordner="rest", wiederverwenden=False, freiraum=True):
    t0 = time.time(); os.makedirs(aus, exist_ok=True); obj = json.load(open(objp)); od = os.path.dirname(os.path.abspath(objp))
    k = BA.konfig(objp, aus); dicht = dicht or k["dicht"]; ausr = ausr or k["ausr"]; P["massstab"] = float(obj.get("stl_massstab", 87))
    erg = dict(objekt=k["name"], stl=os.path.abspath(stl), fassaden=os.path.abspath(fassaden), dicht=dicht, ausrichtung=ausr, parameter=dict(P), flaechen={}, zeiten={})
    if ohne_fotos:
        t = time.time(); erg["leck"] = wolke_filtern(dicht, os.path.join(aus, "wolke_ohne_fotos"), ohne_fotos, foto_modus); dicht = os.path.join(aus, "wolke_ohne_fotos"); erg["zeiten"]["filtern"] = round(time.time() - t, 1)
        print("Wolke gefiltert:", erg["leck"], flush=True)
    Fs = json.load(open(fassaden))["fassaden"]; Fs = [F for F in Fs if F["flaeche_m2"] >= min_flaeche and (not nur or F["id"] in nur)]
    fj = os.path.join(aus, "fassaden_auswahl.json"); json.dump(dict(fassaden=Fs), open(fj, "w"))
    t = time.time(); rdir = os.path.join(aus, unterordner)
    RF.main(["--stl", stl, "--dicht", dicht, "--ausrichtung", ausr, "--fassaden", fj, "--aus", rdir, "--zelle", str(P["zelle"]), "--min-kameras", str(P["min_kameras"]), "--min-punkte", str(P["min_punkte"]), "--massstab", str(P["massstab"])])
    Xw, Nw, _ = BA.wolke_modellrahmen(dicht, ausr, P["min_kameras"])
    erg["wandstatus"] = {}; ersetzt = []
    for F in Fs:
        npz = os.path.join(rdir, f"restfeld_{F['id']}.npz")
        if not os.path.exists(npz): continue
        Z_ = np.load(npz); st = wand_status(Z_["daten"], poly_maske(F, *Z_["daten"].shape, P["zelle"])); erg["wandstatus"][F["id"]] = st
        if st["status"] == "widerspruch":
            G = ebene_aus_wolke(Xw, F)
            if G is not None: ersetzt.append((F["id"], G)); st["ebene_aus_wolke"] = True
            else: st["ebene_aus_wolke"] = False
    if ersetzt:
        Fs = [dict(next((G for i, G in ersetzt if i == F["id"]), F)) for F in Fs]; json.dump(dict(fassaden=Fs), open(fj, "w"))
        RF.main(["--stl", stl, "--dicht", dicht, "--ausrichtung", ausr, "--fassaden", fj, "--aus", rdir, "--zelle", str(P["zelle"]), "--min-kameras", str(P["min_kameras"]), "--min-punkte", str(P["min_punkte"]), "--massstab", str(P["massstab"]), "--nur"] + [i for i, _ in ersetzt])
    print("Wandstatus:", {i: (v["status"], v["median_abs_m"], v["datenanteil"]) for i, v in erg["wandstatus"].items()}, flush=True)
    erg["zeiten"]["restfeld"] = round(time.time() - t, 1)
    t = time.time(); fdir = os.path.join(aus, "freiraum"); FR = {}
    if freiraum:
        if not (wiederverwenden and os.path.exists(os.path.join(fdir, "strahlen.npz"))): FP.main([objp, "--stl", stl, "--dicht", dicht, "--ausrichtung", ausr, "--aus", fdir, "--min-kameras", str(P["oeff_min_kameras"]), "--massstab", str(P["massstab"])])
        FFa.main([os.path.join(fdir, "strahlen.npz"), fj, fdir, "--min-kameras", str(P["oeff_min_kameras"]), "--stl", stl, "--massstab", str(P["massstab"])])
        FR = json.load(open(os.path.join(fdir, "freiraum_fassaden.json")))["fassaden"]; erg["zeiten"]["freiraum"] = round(time.time() - t, 1)
    Cm = trimesh.load(stl); Cm.apply_scale(P["massstab"] / 1000.0); Cmf = manifold_aus_trimesh(Cm)
    A_all, S_all, O_all = [], [], []; os.makedirs(os.path.join(aus, "flaechen"), exist_ok=True)
    for F in Fs:
        fid = F["id"]; npz = os.path.join(rdir, f"restfeld_{fid}.npz")
        if not os.path.exists(npz): continue
        Z = np.load(npz); daten, modell, anz = Z["daten"], Z["modell"], Z["anzahl"]; nz, nu = daten.shape
        wand = poly_maske(F, nz, nu, P["zelle"]); stt0 = erg["wandstatus"].get(fid, {}).get("status", "?"); breite = float(F["u"][1] - F["u"][0])
        if stt0 == "unbestaetigt" or breite < P["min_breite_relief"]: daten = np.full_like(daten, np.nan)   # unbestaetigt: LoD2 nur zum Schliessen; schmale Flaechen: Zellen mischen Nachbarflaechen (Befund f12: Pfeiler weggeschnitten)
        res = feld_loesen(daten, modell, anz, wand); res["_daten"] = daten; res["_modell"] = modell; res["zahl"]["relief_ausgesetzt"] = bool(stt0 == "unbestaetigt" or breite < P["min_breite_relief"])
        frei, kam = freiraum_raster(F, FR.get(fid), nz, nu, 0.25); frei = frei if FR.get(fid) else np.zeros((nz, nu)); offen = oeffnungen(F, res, frei, nz, nu, wand)
        for c in offen: res["herkunft"][c["maske"]] = 5
        A, S, O = flaechen_koerper(F, res, offen); A_all += A; S_all += S; O_all += O
        res["zahl"].update(oeffnungen=len(offen), oeffnungen_liste=[{a: b for a, b in c.items() if a != "maske"} for c in offen], quadern=dict(auftrag=len(A), schnitt=len(S), oeffnung=len(O)),
                           freiraum_zellen=int(((frei >= P["oeff_tiefe"]) & wand).sum()))
        stt = erg["wandstatus"].get(fid, {}).get("status", "?"); fuel = {"bestaetigt": "lod2_bestaetigt", "unbestaetigt": "lod2_unbestaetigt", "widerspruch": "wolke_ebene"}.get(stt, stt)
        nw = max(int(wand.sum()), 1); res["zahl"]["wandstatus"] = stt; res["zahl"]["herkunft_anteile"] = {"wolke": round(float(res["plaus"].sum() / nw), 3), fuel: round(float((wand & ~res["plaus"]).sum() / nw), 3)}
        erg["flaechen"][fid] = dict(flaeche_m2=F["flaeche_m2"], **res["zahl"]); flaechenbild(fid, res, res["zahl"], os.path.join(aus, "flaechen", f"{fid}.jpg"))
        np.savez_compressed(os.path.join(aus, "flaechen", f"{fid}.npz"), D=res["D"], dq=res["dq"], herkunft=res["herkunft"])
        print(f"{fid}: Daten {res['zahl']['datenanteil']:.0%} unpl {res['zahl']['unplausibel']} Auftrag {res['zahl']['auftrag_zellen']} Schnitt {res['zahl']['schnitt_zellen']} Oeffnungen {len(offen)}  ({time.time() - t0:.0f} s)", flush=True)
    dst = None
    if dach:
        t = time.time(); dA, dS, erg["dach"], dr = (dach_koerper(k, Cm, stadtmesh) if dach == "dom1" else dach_aus_wolke(Cm, Xw, Nw)); erg["zeiten"]["dach"] = round(time.time() - t, 1); np.savez_compressed(os.path.join(aus, "dach.npz"), Z=dr["Z"], HC=dr["HC"], HS=dr["HS"], lx=dr["lx"], ly=dr["ly"])
        print("Dach:", {a: b for a, b in erg["dach"].items()}, flush=True)
    else: dA, dS = [], []
    t = time.time()
    def vereinigen(L): return MF.Manifold.batch_boolean(L, MF.OpType.Add) if L else None
    cut = vereinigen(S_all + dS); add = vereinigen(A_all + dA); opn = vereinigen(O_all)
    R = Cmf; erg["volumen_schritte_m3"] = dict(C=round(R.volume(), 2))
    if cut is not None: R = R - cut; erg["volumen_schritte_m3"]["nach_schnitt"] = round(R.volume(), 2)
    if add is not None: R = R + add; erg["volumen_schritte_m3"]["nach_auftrag"] = round(R.volume(), 2)
    if opn is not None: R = R - opn; erg["volumen_schritte_m3"]["nach_oeffnung"] = round(R.volume(), 2)
    erg["manifold_status"] = str(R.status()); m = zu_trimesh(R); erg["watertight_roh"] = bool(m.is_watertight); parts = sorted(m.split(only_watertight=False), key=lambda c: -abs(c.volume))
    erg["splitter"] = dict(koerper_roh=len(parts), verworfen=[round(abs(float(c.volume)), 5) for c in parts[1:6]], verworfen_anzahl=len(parts) - 1)
    m = parts[0]; erg["zeiten"]["solid"] = round(time.time() - t, 1)
    erg["modell_C"] = kennzahlen(Cm, P["massstab"])
    stl_out = gebe_stl or os.path.join(aus, f"{k['name']}_wolke_solid_1-{int(P['massstab'])}.stl"); os.makedirs(os.path.dirname(stl_out), exist_ok=True)
    m, gr, okl, dvol = stl_dicht(m, P["massstab"], stl_out); erg["stl_raster_m"] = gr; erg["stl_reparatur_volumenabweichung"] = round(float(dvol), 4); erg["stl_wasserdicht_nach_laden"] = bool(okl); erg["solid"] = kennzahlen(m, P["massstab"])
    erg["stl_ausgabe"] = stl_out; erg["zeiten"]["gesamt"] = round(time.time() - t0, 1)
    # Belege: Zellenanteile je Herkunft (Quelle Wolke/DOM1/Stadtmesh/Modell)
    h = {}
    for fid, z in erg["flaechen"].items(): h[fid] = dict(quelle="Wolke (fused.ply >= 3 Kameras, q 0,8) fuer Zellen mit Daten, sonst Modell " + os.path.basename(stl), datenanteil=z["datenanteil"], aenderung_anteil=z["aenderung_anteil"])
    h["dach"] = dict(quelle="Wolke (Hauptpfad)" if dach == "wolke" else "DOM1 (Variante mit_lod2)", **{a: b for a, b in (erg.get("dach") or {}).items() if a in ("zellen_dach", "auftrag_zellen", "schnitt_zellen")})
    erg["belege"] = h; json.dump(erg, open(os.path.join(aus, "wolke_solid.json"), "w"), indent=1)
    print("Solid:", json.dumps(erg["solid"]), "\nModell C:", json.dumps(erg["modell_C"]), f"\n-> {stl_out} ({erg['zeiten']['gesamt']} s)", flush=True)
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--fassaden", required=True)
    ap.add_argument("--aus", required=True); ap.add_argument("--dicht"); ap.add_argument("--ausrichtung"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--ohne-fotos", nargs="*"); ap.add_argument("--foto-modus", default="alle", choices=["alle", "nur"])
    ap.add_argument("--wiederverwenden", action="store_true"); ap.add_argument("--offset-median", action="store_true", help="VARIANTE: Median-Tiefenversatz der Wolke je Flaeche / am Dach abziehen"); ap.add_argument("--stadtmesh"); ap.add_argument("--kein-dach", action="store_true"); ap.add_argument("--dach", default="wolke", choices=["wolke", "dom1"], help="wolke = Hauptpfad nur Wolke; dom1 = Variante mit_lod2/DOM1"); ap.add_argument("--stl-aus"); ap.add_argument("--min-flaeche", type=float, default=7.0)
    a = ap.parse_args(argv); P["offset_median"] = bool(a.offset_median)
    lauf(a.objekt, a.stl, a.fassaden, a.aus, a.dicht, a.ausrichtung, a.nur, a.ohne_fotos, a.foto_modus, a.stadtmesh, dach=(None if a.kein_dach else a.dach), gebe_stl=a.stl_aus, min_flaeche=a.min_flaeche, wiederverwenden=a.wiederverwenden)


if __name__ == "__main__":
    main()
