#!/usr/bin/env python3
"""wolke_umgebung.py - UMGEBUNGSMASKE und RAUSCHMESSUNG fuer die Elementschleife (generator_elemente_schleife.py). Nichts Objektspezifisches.

  /media/oem/scan/venv-seg/bin/python -I tools/wolke_umgebung.py <objekt.json> <stand.stl> <aus_dir> [--wolke GLOB] [--massstab 87]
  (schreibt <aus_dir>/umgebung.json und umgebung.jpg: Vorder-/Seiten-/Draufsicht, behalten = grau, entfernt = rot)

UMGEBUNGSMASKE (alles aus den Daten, Reihenfolge)
 1 BODEN      robuste Bodenebene (RANSAC) auf den Punkten in 1,5 m ueber dem tiefsten Punkt des Modells (nur fast waagerechte Ebenen, deren Hoehe an der Modellmitte um <= 0,5 m der Modell-Fusshoehe entspricht; sonst keine Bodenentfernung - der Schnitt Boden+0,5 m der Cluster bleibt); Punkte <= K_RAUSCH*sigma von der Ebene
              (und alles unter der Ebene) werden entfernt. sigma = gemessene lokale Wolkenstreuung (rauschen_messen).
 2 AUSREISSER Punkte, deren Abstand zum k-ten Nachbarn ueber Median + K_AUSREISSER (8, ANNAHME; 3 entfernte 13 % = legitime duenne Dachpunkte) robuste Sigma der k-NN-Abstaende liegt (Himmel, einzelne Streupunkte).
 3 FENSTER    signierter Abstand r zur Modellhuelle im Fassadenbereich [-3 m, +3 m] (ANNAHME = BAND der Clusterung). Ein Dichteprofil-Knie in Wandnormalenrichtung wurde erprobt (Test) und
              VERWORFEN: es liegt bei der Wandstaerke und schneidet duenne vorspringende Erker ab; es wird nur berichtet (profil_knie_*). Seitliche Nachbarn ausserhalb 3 m der Huelle fallen weg.
 4 ZUSAMMENHANG dichte Voxel (vox m, >= vox_min Punkte) im Fenster; nur Komponenten, die die Huelle beruehren (mind. ein Voxel mit Punkten |r| <= K_RAUSCH*sigma) bleiben
              (schwebende Reste = Baeume/Geruest fallen weg).
K_RAUSCH = 3 (Gauss: 0,3 % Ueberschreitung -> 3-Sigma-Kriterium), K_KNIE = 3 (Dichte mindestens das Dreifache des Hintergrunds) - beide ANNAHME, benannt und im Protokoll.

RAUSCHMESSUNG (Wolkenstreuung senkrecht zu gut belegten ebenen Wandstuecken, nicht aus Sollwerten)
 Die am besten belegte senkrechte Flaechenrichtung des Modells (Punkte mit |r| < 0,5 m, Normalenrichtung in 5-Grad-Klassen) liefert die Wandpunkte. Je Kachelgroesse s (0,5 / 1 / 2 m, entlang der
 Wand und in der Hoehe) wird in jeder Kachel mit >= 200 Punkten eine Ebene angepasst (PCA); robuste Streuung sigma_s = 1,4826*MAD der Abstaende, und mittlerer Betrag E|d| (dieselbe Statistik wie
 die Flaechigkeit im Tor). Median ueber die Kacheln. s = 0,5 m = reines Rauschen (Relief und Gerueste weitgehend rausgemittelt), s = 2 m = Elementgroesse (enthaelt Relief und Posenversatz zwischen den
 Aufnahmestapeln) = OBERE Schranke. Zusaetzlich sigma_wand = MAD ueber die ganze Wand (Relief + Versatz + Rauschen).
 ABGELEITET (Festlegung im Aufrufer): schwelle = K_SCHWELLE * sigma_0,5 ; dc_max (Flaechigkeit) = Median E|d| bei Elementgroesse (2 m): eine Elementplatte kann nicht flacher sein als die gemessene Wand.
"""
import sys, os, json, glob, argparse, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

K_RAUSCH = 3.0
K_KNIE = 3.0
K_SCHWELLE = 3.0
K_AUSREISSER = 8.0
PROFIL_BIN = 0.25
GPU = True          # kNN auf GPU (gpu_knn / knn_points); main(--cpu) schaltet auf cKDTree zurueck (Originalverhalten)


def _pca_ebene(Q):
    c = Q.mean(0); w, V = np.linalg.eigh(np.cov((Q - c).T)); return c, V[:, 0], V


def rauschen_messen(P, mesh, r, zmin, kd_proben=600000, massstab_kacheln=(0.5, 1.0, 2.0)):
    """-> dict. P (N,3) Wolke, mesh trimesh in m, r signierter Abstand (NaN fern), zmin = Bodenhoehe."""
    import trimesh
    Sm, fi = trimesh.sample.sample_surface(mesh, kd_proben, seed=1)
    sel = np.where((np.abs(np.nan_to_num(r, nan=9)) < 0.5) & (P[:, 2] > zmin + 0.5))[0]
    if GPU:
        from gpu_knn import naechster; _, i = naechster(P[sel], Sm)
    else:
        from scipy.spatial import cKDTree; _, i = cKDTree(Sm).query(P[sel])
    nrm = mesh.face_normals[fi[i]]; vert = np.abs(nrm[:, 2]) < 0.3
    key = np.round(np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) / 5).astype(int)
    zaehl = {int(k): int(((key == k) & vert).sum()) for k in np.unique(key[vert])}
    k = max(zaehl, key=zaehl.get); Qa = P[sel[(key == k) & vert]]
    c, nv, V = _pca_ebene(Qa); d = (Qa - c) @ nv; med = np.median(d); sigma_wand = 1.4826 * float(np.median(np.abs(d - med)))
    t1 = V[:, 2]; u = (Qa - c) @ t1; z = Qa[:, 2]; erg = dict(wand_richtung_grad=k * 5.0, wand_punkte=int(len(Qa)), klassen=zaehl, sigma_wand=round(sigma_wand, 4),
                                                                 mittel_betrag_wand=round(float(np.abs(d - med).mean()), 4), kacheln={})
    for s in massstab_kacheln:
        sg, ma, n = [], [], []
        iu = np.floor((u - u.min()) / s).astype(int); iz = np.floor((z - z.min()) / s).astype(int); key2 = iu * 100000 + iz
        o = np.argsort(key2); ks = key2[o]; grenzen = np.r_[0, np.where(np.diff(ks) != 0)[0] + 1, len(ks)]
        for a, b in zip(grenzen[:-1], grenzen[1:]):
            if b - a < 200: continue
            X = Qa[o[a:b]]; cc, nn, _ = _pca_ebene(X); dd = (X - cc) @ nn
            sg.append(1.4826 * float(np.median(np.abs(dd - np.median(dd))))); ma.append(float(np.abs(dd).mean())); n.append(b - a)
        if sg:
            erg["kacheln"][str(s)] = dict(n_kacheln=len(sg), sigma_median=round(float(np.median(sg)), 4), sigma_p90=round(float(np.percentile(sg, 90)), 4),
                                          mittel_betrag_median=round(float(np.median(ma)), 4), mittel_betrag_p90=round(float(np.percentile(ma, 90)), 4))
    return erg


def _profil_grenze(r, rmax=10.0, vorz=+1):
    """Knie des Dichteprofils. r signiert; vorz +1 aussen / -1 innen. -> (grenze_m, info)."""
    a = vorz * r[~np.isnan(r)]; a = a[(a >= 0) & (a < rmax)]
    h, e = np.histogram(a, bins=np.arange(0, rmax + 1e-9, PROFIL_BIN)); b = float(np.median(h[len(h) // 2:]))
    pk = int(np.argmax(h)); g = pk
    while g + 1 < len(h) and h[g + 1] > K_KNIE * max(b, 1.0): g += 1
    return float((g + 1) * PROFIL_BIN), dict(hintergrund_je_schicht=b, dichtemaximum_bei=float(e[pk]), schichten=[int(x) for x in h[:int(4 / PROFIL_BIN)]])


def boden_ebene(P, zmin, sigma, z_toleranz=0.5, mitte_xy=None):
    """RANSAC auf Punkten bis zmin+1.5 m, nur fast waagerechte Ebenen -> (n, d) mit n.x = d oder None."""
    Q = P[P[:, 2] < zmin + 1.5]
    if len(Q) < 500: return None
    rng = np.random.default_rng(1); best = (0, None); Qs = Q[rng.choice(len(Q), min(len(Q), 60000), replace=False)]
    for _ in range(300):
        T = Qs[rng.choice(len(Qs), 3, replace=False)]; n = np.cross(T[1] - T[0], T[2] - T[0]); nn = np.linalg.norm(n)
        if nn < 1e-9: continue
        n /= nn
        if n[2] < 0: n = -n
        if n[2] < 0.9: continue
        cnt = int((np.abs((Qs - T[0]) @ n) <= K_RAUSCH * sigma).sum())
        if cnt > best[0]: best = (cnt, (n, float(n @ T[0])))
    if best[1] is None: return None
    n, d = best[1]
    if mitte_xy is not None and abs((d - n[0] * mitte_xy[0] - n[1] * mitte_xy[1]) / n[2] - zmin) > z_toleranz: return None      # Ebene liegt nicht auf Gelaendehoehe des Modells (z.B. Wandring-Schicht)
    inl = np.abs(Q @ n - d) <= K_RAUSCH * sigma; c, nv, _ = _pca_ebene(Q[inl]); nv = nv if nv[2] > 0 else -nv
    return nv, float(nv @ c), int(inl.sum())


def umgebungsmaske(P, mesh, r, zmin, sigma, vox=0.4, vox_min=3, k_nn=10, fenster=3.0):
    """-> keep (bool, N), info. r = signierter Abstand (aussen +, NaN fern) der Wolke zum Modell."""
    from scipy.spatial import cKDTree
    from scipy import ndimage as ndi
    N = len(P); keep = np.ones(N, bool); info = dict(n_start=int(N), k_rausch=K_RAUSCH, k_knie=K_KNIE, sigma=sigma)
    eb = boden_ebene(P, zmin, sigma, mitte_xy=mesh.bounds.mean(0)[:2])
    if eb is not None:
        n, d, ninl = eb; dist = P @ n - d; boden = dist <= K_RAUSCH * sigma; boden_nah = np.abs(dist) <= K_RAUSCH * sigma
        keep &= ~boden; info["boden"] = dict(normale=[round(float(x), 4) for x in n], d=round(d, 3), inlier=ninl, entfernt=int(boden.sum()), neigung_grad=round(math.degrees(math.acos(min(1, n[2]))), 2))
    else: info["boden"] = "keine Ebene gefunden"
    if GPU:
        import torch; sys.path.insert(0, "/media/oem/scan/p3d_site"); from pytorch3d.ops import knn_points
        Pk = P[keep]; Xg = torch.as_tensor(np.asarray(Pk - Pk.mean(0), np.float32), device="cuda")[None]; dk = np.empty(len(Pk))
        for i0 in range(0, len(Pk), 500000): dk[i0:i0 + 500000] = knn_points(Xg[:, i0:i0 + 500000], Xg, K=k_nn + 1).dists[0, :, -1].clamp_min(0).sqrt().double().cpu().numpy()
    else:
        kdt = cKDTree(P[keep]); dk = kdt.query(P[keep], k=k_nn + 1)[0][:, -1]
    m = np.median(dk); sg = 1.4826 * np.median(np.abs(dk - m)); lim = m + K_AUSREISSER * sg
    aus = np.zeros(N, bool); aus[np.where(keep)[0][dk > lim]] = True; keep &= ~aus
    info["ausreisser"] = dict(k=k_nn, median_abstand=round(float(m), 4), grenze=round(float(lim), 4), entfernt=int(aus.sum()))
    rr = r.copy(); rr[~keep] = np.nan
    pa, ia = _profil_grenze(rr, vorz=+1); pi, ii = _profil_grenze(rr, vorz=-1); ra = ri = float(fenster)
    info["fenster"] = dict(aussen_m=ra, innen_m=ri, herkunft="ANNAHME 3 m = BAND der Clusterung (ein Dichteprofil-Knie wurde ERPROBT und verworfen: es liegt bei der Wandstaerke und schneidet vorspringende Erker ab; im Test 0,25 m, Erkervorderseite zu 77 % verloren)",
                           profil_knie_aussen_m=pa, profil_knie_innen_m=pi, profil_aussen=ia, profil_innen=ii)
    fen = ~np.isnan(rr) & (rr <= ra) & (rr >= -ri); entf_f = keep & ~fen; keep &= fen; info["fenster"]["entfernt"] = int(entf_f.sum())
    idx = np.where(keep)[0]; Q = P[idx]; lo = Q.min(0); g = np.floor((Q - lo) / vox).astype(int); shp = g.max(0) + 1
    cnt = np.zeros(shp, int); np.add.at(cnt, tuple(g.T), 1); lab, nl = ndi.label(cnt >= vox_min, structure=np.ones((3, 3, 3))); l = lab[tuple(g.T)]
    nah = np.abs(rr[idx]) <= K_RAUSCH * sigma; saat = set(np.unique(l[nah & (l > 0)]).tolist()); gut = np.isin(l, list(saat)) & (l > 0)
    entf_z = idx[~gut]; keep[entf_z] = False; info["zusammenhang"] = dict(komponenten=int(nl), mit_huelle=len(saat), entfernt=int(len(entf_z)))
    info["n_behalten"] = int(keep.sum()); info["anteil_behalten"] = round(float(keep.mean()), 4)
    return keep, info


def bild(P, keep, mesh, pfad, titel=""):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(24, 8)); E = mesh.edges_unique; V = mesh.vertices; sub = np.arange(0, len(P), max(1, len(P) // 120000))
    for a, (i, j, t) in zip(ax, ((0, 2, "Vorderansicht x-z"), (1, 2, "Seite y-z"), (0, 1, "Draufsicht x-y"))):
        k = sub[keep[sub]]; e = sub[~keep[sub]]
        a.scatter(P[e, i], P[e, j], s=0.4, c="red", alpha=0.35); a.scatter(P[k, i], P[k, j], s=0.4, c="0.35", alpha=0.5)
        for ed in E: a.plot(V[ed, i], V[ed, j], "b-", lw=0.5)
        a.set_aspect("equal"); a.set_title(f"{t} {titel}")
    plt.tight_layout(); plt.savefig(pfad, dpi=55); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("stl"); ap.add_argument("aus"); ap.add_argument("--wolke"); ap.add_argument("--massstab", type=float); ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args(argv); global GPU; GPU = not a.cpu
    if GPU: os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")          # generator_elemente_schleife blendet sonst per setdefault die GPU aus
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import generator_elemente_schleife as G
    obj = json.load(open(a.objekt)); ms = a.massstab or float(obj.get("stl_massstab", 87))
    spec = a.wolke or next(b["wolke"] for b in obj["bauteile"] if b.get("typ") == "rumpf_wolke"); P = G.wolke_laden(spec)
    mesh = G.stl_laden(a.stl, ms); mod = G.Modell(mesh); r = mod.res(P, band=30); zmin = float(mesh.bounds[0, 2]); os.makedirs(a.aus, exist_ok=True)
    rau = rauschen_messen(P, mesh, r, zmin); s05 = rau["kacheln"]["0.5"]["sigma_median"]
    keep, inf = umgebungsmaske(P, mesh, r, zmin, s05); json.dump(dict(rauschen=rau, umgebung=inf), open(os.path.join(a.aus, "umgebung.json"), "w"), indent=1, default=float)
    bild(P, keep, mesh, os.path.join(a.aus, "umgebung.jpg"), f"behalten {inf['n_behalten']}/{inf['n_start']}"); print(json.dumps(dict(rauschen=rau, umgebung={k: v for k, v in inf.items() if k != 'fenster'}, fenster={k: v for k, v in inf['fenster'].items() if not k.startswith('profil')}), indent=1, default=float))


if __name__ == "__main__":
    main()
