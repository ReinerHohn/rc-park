#!/usr/bin/env python3
"""generator_elemente_schleife.py - AUTOMATISCHE ELEMENTSCHLEIFE fuer den Generator (Nutzerwunsch 6.11.: immer Diff bilden, Diff verkleinern,
Elemente automatisch hinzufuegen; keine Handliste von Erker/Giebel/Arkaden). Wolke = erste Wahrheit; LoD2 nur Luecken-Ersatz (im Rumpf, nicht hier).

  /media/oem/scan/venv-seg/bin/python -I tools/generator_elemente_schleife.py modelle/<obj>/objekt.json --aus DIR [--runden 3] [--kameras DIR_mit_K-*.json]
        [--fotos 6] [--ohne-fotos] [--minuten-je-cluster 5] [--uebernehmen] [--start-stl STL --ohne-generator --wolke GLOB]   (die letzten drei: synthetischer Beweis)
  Lange Laeufe: tools/job_start.sh elschleife LOG <diese Zeile>

SCHEMA JE RUNDE
 1 RESTFELD  Wolke (bauteile.rumpf_wolke.wolke, glob) minus aktuelles Modell (STL -> Meter): signierter Abstand (aussen +). Punkte mit |Abstand| > SCHWELLE
             (ANNAHME 0,25 m) und <= BAND (ANNAHME 3 m: weiter weg = Nachbarbebauung/Ausreisser) oberhalb Boden+0,5 m (ANNAHME) -> Voxel-Zusammenhang (0,4 m, >= 3 Punkte
             je Voxel, ANNAHME) -> Cluster mit >= MIN_PKT Punkten (ANNAHME 150); Cluster > 6 m Ausdehnung werden mit strengerer Voxeldichte zerlegt, sonst in 4-m-Kacheln (ANNAHME). Je Cluster: Vorsprung (Wolke aussen) / Ruecksprung (innen), Lage, Ausdehnung, Hoehenband.
 2 KANDIDATEN  ALLE passenden Formfamilien (bauteil_element_wolke.FAMILIEN: block, giebel, keil, zylinder | nische, rundnische, bogenreihe), je mit freien Parametern an die
             Cluster-Wolke eingepasst (Nelder-Mead, deterministisch: Start aus Hauptachsen/Kreisfit des Clusters, feste Punktabtastung seed 1). Rangfolge = Formtest-Guete
             (Chamfer Cluster<->Koerper + Koerper<->Wolke, gekappt 0,5 m, + 0,004 je Parameter ANNAHME). KEINE feste Obergrenze; Zeitbudget --minuten-je-cluster (ANNAHME 5).
             Abbruch frueher, sobald ein Kandidat das Tor besteht und kein weiterer (Fit-Guete >= 105 % des Bestandenen, ANNAHME) noch besser sein kann.
 3 TOR (streng; aus SPEC_S3 / generator_schleife Annahmetor) fuer Kandidat Nr. j (0-basiert) desselben Clusters, MEHRFACHTEST-KORREKTUR (ANNAHME):
             Flaechigkeit: mittlerer Abstand Cluster-Punkte -> Koerperflaeche <= 0,10 m*(1-0,05*j) (ANNAHME; Punkthaufen im Raum passen nie); Restfeld lokal (Umgebung = Cluster-Box + 0,75 m): Zahl ferner Punkte sinkt um >= 0,60 + 0,05*j (max 0,90), lokales p90 des |Abstands| steigt nicht, und die ferne
             Punktzahl in der weiteren Umgebung (Box + 3 m) sinkt netto (kein neuer Schaden); Stuetzanteil (Koerperflaeche sichtbar, <= 0,2 m an Wolke) >= 0,40 + 0,05*j;
             foto_diff (kosten_lr, kleiner = besser, feste Maske = Vereinigung beider Silhouetten, nur Fotos die den Cluster sehen): Kandidat nicht schlechter als Basis um
             Aufschlag 0,002*j in >= (2/3 + 0,05*j) der beurteilbaren Fotos, mindestens 3 beurteilbare (sonst abgelehnt: 'nicht beurteilbar', nichts wird erfunden;
             --ohne-fotos schaltet das Foto-Tor ab und vermerkt es in jeder Entscheidung). Jede Ablehnung mit Grund im Protokoll, mit j und Aufschlag.
 4 UEBERNAHME in objekt.json-KOPIE (<aus>/objekt.json, bauteile: element_wolke) mit Quelle/Cluster-ID/Tor/historie; Generator baut je Runde die STL
             (Beleg je Element in elemente_<k>.json). objekt.json bleibt unberuehrt ausser --uebernehmen.
 5 ABBRUCH  keine Uebernahme in der Runde, oder weder Restfeld-p90 noch Clusterzahl sinken, oder --runden erreicht.
AUSGABE <aus>/: protokoll.jsonl (je Runde 'runde' + je Kandidat 'kandidat'), runde_<k>/stand.stl, elemente_<k>.json, objekt.json, ergebnis.json.

ABWEICHUNGEN von 'vorhandene Parametersuche wiederverwenden': die Parameter der Elemente (7-8 freie Masse je Familie) werden an der Wolke lokal eingepasst
(param_suche/generator_schleife arbeiten mit BAUTEIL_PARAM auf BEREITS registrierten Typparametern und Fotokosten je Probe - zu teuer fuer einige tausend Proben je
Cluster). WIEDERVERWENDET: param_suche._fd_aufgabe (foto_diff im Pool, CPU) fuer das Foto-Tor, bauteile.segmentbogen_reihe fuer Bogenreihen, baukasten_gen @bauteil
(neuer Typ element_wolke) fuer den Bau. Photo-Tor misst nur, was Kanten in den Fotos zeigen (Regel 4); GPU wird nicht benutzt.
"""
import sys, os, json, glob, re, argparse, subprocess, time, copy, math, shutil, datetime
import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")          # CPU (Auftrag: GPU nicht anfassen)

P_ = dict(schwelle=0.25, band=3.0, boden_h=0.5, vox=0.4, vox_min=3, min_pkt=150, lokal_rand=0.75, umgebung_rand=3.0,
          gain0=0.60, dc_max=0.10, dc_j=0.05, gain_j=0.05, stuetz0=0.40, stuetz_j=0.05, foto_j=0.002, anteil0=2 / 3, anteil_j=0.05, min_fotos=3,
          kappe=0.5, max_ausdehnung=6.0, kachel=4.0, par_strafe=0.004, tie=1.05, abtast=0.04, max_pkt=500000, stuetz_abst=0.2)


# ------------------------------------------------------------------ Netz / Restfeld
def stl_laden(pfad, massstab):
    import trimesh
    m = trimesh.load(pfad, force="mesh"); m.apply_scale(massstab / 1000.0); return m


def stl_speichern(mesh_m, pfad, massstab, name="elemente"):
    import trimesh
    m = mesh_m.copy(); m.apply_scale(1000.0 / massstab); m.export(pfad)


def aus_manifold(mf):
    import trimesh
    me = mf.to_mesh(); return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3].astype(float), np.asarray(me.tri_verts), process=False)


def zu_manifold(tm):
    from manifold3d import Manifold, Mesh
    return Manifold(Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32)))


def vereinigen(basis, kmf, schnitt):
    """Basis (trimesh, m) +/- Koerper (manifold) -> trimesh. Nicht wasserdichte Basis wird gemeldet (ValueError)."""
    b = zu_manifold(basis)
    if b.status().name != "NoError": raise ValueError(f"Basis nicht manifold ({b.status().name})")
    return aus_manifold((b - kmf) if schnitt else (b + kmf))


class Modell:
    """Signierter Abstand zur Oberflaeche: KD-Baum auf dichter Abtastung (Abstand), Innen/Aussen per Strahlen (mesh.contains)."""
    def __init__(self, mesh):
        import trimesh
        from scipy.spatial import cKDTree
        self.mesh = mesh; n = int(min(1.5e6, max(2e4, mesh.area / P_["abtast"] ** 2)))
        S, _ = trimesh.sample.sample_surface(mesh, n, seed=1); self.kd = cKDTree(S)

    def res(self, P, band=None):
        """signiert (+ aussen); jenseits band = NaN."""
        band = band or P_["band"]; d, _ = self.kd.query(P); r = np.full(len(P), np.nan); nah = d <= band
        if nah.any():
            innen = self.mesh.contains(P[nah]); r[nah] = np.where(innen, -d[nah], d[nah])
        return r


def wolke_laden(spec, basis=ROOT):
    L = []
    for s in ([spec] if isinstance(spec, str) else spec):
        s = s if os.path.isabs(s) else os.path.join(basis, s)
        fs = sorted(glob.glob(s)) or ([s] if os.path.exists(s) else [])
        if not fs: raise FileNotFoundError(s)
        L += [np.load(f)[:, :3] for f in fs]
    P = np.vstack(L).astype(float)
    if len(P) > P_["max_pkt"]: P = P[np.linspace(0, len(P) - 1, P_["max_pkt"]).astype(int)]        # deterministisch gleichmaessig ausduennen
    return P


# ------------------------------------------------------------------ Cluster
def _komponenten(P, idx, vmin):
    from scipy import ndimage as ndi
    Q = P[idx]; lo = Q.min(0); g = np.floor((Q - lo) / P_["vox"]).astype(int); shp = g.max(0) + 1
    cnt = np.zeros(shp, int); np.add.at(cnt, tuple(g.T), 1)
    lab, n = ndi.label(cnt >= vmin, structure=np.ones((3, 3, 3))); l = lab[tuple(g.T)]
    return [idx[l == k] for k in range(1, n + 1) if (l == k).sum() >= P_["min_pkt"]]


def _zerlegen(P, idx, vmin, tiefe=0):
    """Komponenten ueber MAX_AUSDEHNUNG (ANNAHME 6 m: groesser als jedes Einzelelement, = Strasse/Nachbarbau verklebt) werden mit strengerer Voxeldichte
    (vmin x2, bis x32) neu zerlegt; bleibt eine zu gross, in Kacheln von 4 m (ANNAHME) geteilt - ein Element an einer Kachelgrenze wird dabei zerschnitten (Grenze, berichtet)."""
    out = []
    for ii in _komponenten(P, idx, vmin):
        Q = P[ii]; ext = float((Q.max(0) - Q.min(0)).max())
        if ext <= P_["max_ausdehnung"]: out.append(ii); continue
        if tiefe < 5: out += _zerlegen(P, ii, vmin * 2, tiefe + 1); continue
        g = np.floor((Q - Q.min(0)) / P_["kachel"]).astype(int); key = g[:, 0] * 10000 + g[:, 1] * 100 + g[:, 2]
        for kk in np.unique(key):
            m = ii[key == kk]
            if len(m) >= P_["min_pkt"]: out.append(m)
    return out


def cluster_finden(P, r, zmin, vorz):
    """vorz=+1 Vorspruenge (aussen), -1 Ruecksprung (innen). -> Liste dict, nach Punktzahl absteigend."""
    sel = (r * vorz > P_["schwelle"]) & (r * vorz <= P_["band"]) & (P[:, 2] > zmin + P_["boden_h"])
    idx = np.where(sel)[0]
    if len(idx) < P_["min_pkt"]: return []
    out = []
    for ii in _zerlegen(P, idx, P_["vox_min"]):
        Qk = P[ii]
        out.append(dict(idx=ii, n=int(len(ii)), art="vorsprung" if vorz > 0 else "ruecksprung", schwerpunkt=Qk.mean(0), lo=Qk.min(0), hi=Qk.max(0),
                        r_median=float(np.median(r[ii])), r_p90=float(np.percentile(np.abs(r[ii]), 90))))
    out.sort(key=lambda c: (-c["n"], tuple(np.round(c["schwerpunkt"], 2))))
    return out


# ------------------------------------------------------------------ Familien einpassen
def _wandrahmen(c, mod, P):
    """Aussennormale (horizontal), Fusspunkt auf der Wand und Tangente fuer einen Cluster."""
    import trimesh
    cp, d, tri = trimesh.proximity.closest_point(mod.mesh, c["schwerpunkt"][None]); nv = mod.mesh.face_normals[tri[0]]; cp = cp[0]
    nh = np.array([nv[0], nv[1]]); 
    if np.linalg.norm(nh) < 0.5:                                                                     # Dach/Boden-Flaeche: Richtung aus der Wolke (kleinster horizontaler Hauptwert)
        Q = P[c["idx"]][:, :2] - P[c["idx"]][:, :2].mean(0); w, V = np.linalg.eigh(Q.T @ Q); nh = V[:, 0]
        if nh @ (c["schwerpunkt"][:2] - cp[:2]) < 0: nh = -nh
    nh = nh / np.linalg.norm(nh); return math.atan2(nh[1], nh[0]), cp


def startwerte(fam, c, mod, P):
    Q = P[c["idx"]]; phi, cp = _wandrahmen(c, mod, P); n = np.array([math.cos(phi), math.sin(phi)]); t = np.array([-n[1], n[0]])
    s = (Q[:, :2] - cp[:2]) @ n; u = (Q[:, :2] - cp[:2]) @ t; z0, z1 = np.percentile(Q[:, 2], [1, 99]); u0, u1 = np.percentile(u, [1, 99]); uc = 0.5 * (u0 + u1)
    foot = cp[:2] + t * uc; w = max(0.4, u1 - u0)
    if fam in ("block", "giebel", "keil"):
        T = max(0.3, np.percentile(s, 98)); p = dict(cx=foot[0], cy=foot[1], phi=phi, w=w, tiefe=T, z0=z0, z1=z1)
        if fam == "giebel": p["gh"] = 0.3 * w
        if fam == "keil": p["kh"] = 0.3 * (z1 - z0)
        return p
    if fam == "nische":
        T = max(0.2, -np.percentile(s, 2)); return dict(cx=foot[0], cy=foot[1], phi=phi, w=w, tiefe=T, z0=z0, z1=z1)
    if fam in ("zylinder", "rundnische"):                                                           # algebraischer Kreisfit (Kasa) der Horizontalprojektion
        A = np.c_[2 * Q[:, 0], 2 * Q[:, 1], np.ones(len(Q))]; sol = np.linalg.lstsq(A, (Q[:, :2] ** 2).sum(1), rcond=None)[0]
        r = math.sqrt(max(0.04, sol[2] + sol[0] ** 2 + sol[1] ** 2)); r = min(r, 6.0)
        return dict(cx=sol[0], cy=sol[1], r=r, z0=z0, z1=z1)
    if fam == "bogenreihe":
        laeufe = _laeufe(u - uc, s)
        if len(laeufe) < 2: return None
        return dict(cx=foot[0], cy=foot[1], phi=phi, tiefe=max(0.2, -np.percentile(s, 2)), z_unten=z0, z_oben=z1, stich=0.2), laeufe
    return None


def _laeufe(u, s, bin_=0.1, minbreite=0.4):
    """Besetzte Laeufe (start, breite) der Ruecksprung-Punkte entlang der Wand; nur wenn gleichmaessig (Variationskoeff. der Breiten < 0,3)."""
    b = np.floor((u - u.min()) / bin_).astype(int); h = np.bincount(b, minlength=b.max() + 1) >= 3
    L = []; i = 0
    while i < len(h):
        if h[i]:
            j = i
            while j + 1 < len(h) and (h[j + 1] or (j + 2 < len(h) and h[j + 2])): j += 1
            if (j - i + 1) * bin_ >= minbreite: L.append([float(u.min() + i * bin_), float((j - i + 1) * bin_)])
            i = j + 1
        else: i += 1
    if len(L) < 2: return []
    w = np.array([x[1] for x in L]); return L if w.std() / w.mean() < 0.3 else []


def familien_fuer(art): return ["block", "giebel", "keil", "zylinder"] if art == "vorsprung" else ["nische", "rundnische", "bogenreihe"]


def _vec(fam, p):
    import bauteil_element_wolke as BE
    return np.array([p[k] for k in BE.FAMILIEN[fam]], float)


def _par(fam, x):
    import bauteil_element_wolke as BE
    return dict(zip(BE.FAMILIEN[fam], map(float, x)))


def kosten(fam, x, laeufe, Qkd, Q, wkd, M, C, rng_n=1200):
    """Chamfer: Cluster-Punkte -> Koerperoberflaeche  +  Koerperflaeche -> Wolke (gekappt). Rueckgabe (kosten, trimesh-Koerper, Abtastpunkte, d_zur_Wolke)."""
    import bauteil_element_wolke as BE, trimesh
    p = _par(fam, x); w = p.get("w", 1); T = p.get("tiefe", 1); r = p.get("r", 1)
    if w < 0.2 or T < 0.15 or r < 0.2 or p["z1" if "z1" in p else "z_oben"] - p["z0" if "z0" in p else "z_unten"] < 0.3:
        return 1e3, None, None, None
    try: mf, _ = BE.koerper(fam, p, M, C, laeufe)
    except Exception: return 1e3, None, None, None
    if mf.is_empty() or mf.num_tri() < 4: return 1e3, None, None, None
    tm = aus_manifold(mf); S, _ = trimesh.sample.sample_surface(tm, rng_n, seed=1)
    from scipy.spatial import cKDTree
    kd = cKDTree(S); d1, _ = kd.query(Q); d2, _ = wkd.query(S)
    k = P_["kappe"]; return float(np.minimum(d1, k).mean() + np.minimum(d2, k).mean()), tm, S, d2


def einpassen(fam, c, mod, P, M, C, budget_s):
    """-> dict(familie, p, laeufe, fit) oder None."""
    from scipy.optimize import minimize
    from scipy.spatial import cKDTree
    sw = startwerte(fam, c, mod, P)
    if sw is None: return None
    laeufe = None
    if fam == "bogenreihe": sw, laeufe = sw
    Q = P[c["idx"]]; Q = Q[np.linspace(0, len(Q) - 1, min(len(Q), 4000)).astype(int)]                 # deterministisch ausgeduennt (Rechenzeit)
    lo, hi = c["lo"] - 1.5, c["hi"] + 1.5; loc = P[np.all((P >= lo) & (P <= hi), axis=1)]; wkd = cKDTree(loc[np.linspace(0, len(loc) - 1, min(len(loc), 200000)).astype(int)]); Qkd = None
    x0 = _vec(fam, sw); schritt = np.array([0.3 if k not in ("phi", "stich") else (0.1 if k == "phi" else 0.05) for k in __import__("bauteil_element_wolke").FAMILIEN[fam]])
    t0 = time.time(); f = lambda x: kosten(fam, x, laeufe, Qkd, Q, wkd, M, C)[0]
    x = x0; best = f(x0)
    for _ in range(3):                                                                                 # Neustart des Simplex (Nelder-Mead bleibt sonst oft stehen)
        if time.time() - t0 > budget_s: break
        sim = np.vstack([x] + [x + np.eye(len(x))[i] * schritt[i] for i in range(len(x))])
        r = minimize(f, x, method="Nelder-Mead", options=dict(initial_simplex=sim, maxiter=500, xatol=2e-3, fatol=1e-5))
        if r.fun < best - 1e-6: x, best = r.x, r.fun
        else: break
    if best >= 1e3: return None
    return dict(familie=fam, p=_par(fam, x), laeufe=laeufe, fit=float(best), nparam=len(x), rang_fit=float(best + P_["par_strafe"] * len(x)))


# ------------------------------------------------------------------ Tor
def stuetzanteil(kand_tm, S, d2, mod, schnitt):
    """Anteil der SICHTBAREN Koerperoberflaeche (Anbau: ausserhalb des Basisnetzes, Ausschnitt: innerhalb) mit Wolke <= stuetz_abst."""
    innen = mod.mesh.contains(S); sicht = innen if schnitt else ~innen
    return float((d2[sicht] <= P_["stuetz_abst"]).mean()) if sicht.any() else 0.0


def kamera_laden(kdir):
    import cv2
    K = {}
    for p in sorted(glob.glob(os.path.join(kdir, "K-*.json"))):
        k = json.load(open(p)).get("kamera", {})
        if k and ((k.get("buendel_tor") or {}).get("ok") or (k.get("lod2_tor") or {}).get("ok")): K[os.path.basename(p)[2:-5]] = k
    return K


def sehende_fotos(K, c, n_max):
    """Fotos, deren Bild den Cluster (Schwerpunkt + Boxecken) enthaelt, bester Blick (Schwerpunkt nahe Bildmitte) zuerst."""
    import cv2
    ecken = np.array([[x, y, z] for x in (c["lo"][0], c["hi"][0]) for y in (c["lo"][1], c["hi"][1]) for z in (c["lo"][2], c["hi"][2])] + [c["schwerpunkt"]])
    erg = []
    for nr, k in K.items():
        R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; t = np.array(k["t"], float); X = ecken + np.array(k.get("rahmen_verschiebung", [0, 0, 0]), float)
        Xc = X @ R.T + t
        if (Xc[:, 2] <= 1.0).any() or Xc[-1, 2] > 150: continue
        u = k["f_px"] * Xc[:, 0] / Xc[:, 2] + k["cx"]; v = k["f_px"] * Xc[:, 1] / Xc[:, 2] + k["cy"]; W, H = k["bild"]
        ein = (u > 0) & (u < W) & (v > 0) & (v < H)
        if not ein[-1] or ein.mean() < 0.6: continue
        erg.append((math.hypot(u[-1] / W - 0.5, v[-1] / H - 0.5), nr))
    return [nr for _, nr in sorted(erg)[:n_max]]


class FotoTor:
    def __init__(self, objp, aus, extra):
        import multiprocessing as mp, param_suche as PS
        self.objp, self.aus, self.PS = objp, aus, PS; self.extra = extra
        self.pool = mp.get_context("spawn").Pool(max(1, min(6, PS.arbeiter_zahl(6))))
        os.environ["FD_PUNKTE_DIR"] = PS.PUNKTE_DIR

    def lauf(self, auf):
        res = []
        for (jp, fehler) in self.pool.imap(self.PS._fd_aufgabe, auf): res.append((jp, fehler))
        return res

    def kosten(self, stl_alt, stl_neu, fotos, tag):
        """kosten_lr alt/neu je Foto mit fester Maske (Vereinigung beider Silhouetten)."""
        import cv2
        wd = os.path.join(self.aus, "foto_tor", tag); os.makedirs(wd, exist_ok=True); stls = dict(alt=stl_alt, neu=stl_neu)
        auf = []
        for w, s in stls.items():
            for nr in fotos:
                a = os.path.join(wd, f"mask_{w}", nr); os.makedirs(a, exist_ok=True)
                auf.append(([self.objp, nr, "--stl", s, "--aus", a, "--maske-aus", os.path.join(a, "m.png")] + self.extra, os.path.join(a, f"foto_diff_{nr}.json")))
        self.lauf(auf); auf = []; md = os.path.join(wd, "masken"); os.makedirs(md, exist_ok=True)
        for nr in fotos:
            ms = [cv2.imread(os.path.join(wd, f"mask_{w}", nr, "m.png"), cv2.IMREAD_GRAYSCALE) for w in stls]; ms = [m for m in ms if m is not None]
            if ms: cv2.imwrite(os.path.join(md, f"{nr}.png"), np.maximum.reduce(ms))
        for w, s in stls.items():
            for nr in fotos:
                if not os.path.exists(os.path.join(md, f"{nr}.png")): continue
                a = os.path.join(wd, f"eval_{w}", nr); os.makedirs(a, exist_ok=True)
                auf.append(([self.objp, nr, "--stl", s, "--aus", a, "--bewertung-maske", os.path.join(md, f"{nr}.png")] + self.extra, os.path.join(a, f"foto_diff_{nr}.json")))
        self.lauf(auf); out = {}
        for nr in fotos:
            v = {}
            for w in stls:
                jp = os.path.join(wd, f"eval_{w}", nr, f"foto_diff_{nr}.json")
                if os.path.exists(jp): v[w] = json.load(open(jp)).get("kosten_lr")
            if v.get("alt") is not None and v.get("neu") is not None: out[nr] = v
        return out

    def schliessen(self):
        self.pool.close(); self.pool.join(); shutil.rmtree(self.PS.PUNKTE_DIR, ignore_errors=True)


def tor(kand, c, basis_mod, P, r_basis, M, C, j, fotoblock, aus, tag, log):
    """Strenges Tor. Rueckgabe (ok, grund, info)."""
    info = dict(j=j)
    if kand["tm"] is None: return False, "Koerper leer", info
    schnitt = kand["schnitt"]
    gain = min(0.9, P_["gain0"] + P_["gain_j"] * j); st_min = min(0.9, P_["stuetz0"] + P_["stuetz_j"] * j); info.update(aufschlag_restfeld=round(gain - P_["gain0"], 3), gain_soll=gain, stuetz_soll=st_min)
    try: neu = vereinigen(basis_mod.mesh, kand["mf"], schnitt)
    except Exception as e: return False, f"Vereinigung fehlgeschlagen: {e}", info
    dcm = P_["dc_max"] * (1 - P_["dc_j"] * j); info.update(dc=round(kand["dc"], 3), dc_soll=round(dcm, 3))
    if kand["dc"] > dcm: return False, f"Cluster liegt nicht auf der Koerperflaeche (mittlerer Abstand {kand['dc']:.3f} m > {dcm:.3f} m): kein Flaechenelement", info
    st = kand["stuetz"]; info["stuetz"] = round(st, 3)
    if st < st_min: return False, f"Stuetzanteil {st:.2f} < {st_min:.2f} (Koerperflaeche ohne Wolke = erfunden)", info
    nm = Modell(neu); kand["neues_mesh"] = neu
    lo, hi = c["lo"], c["hi"]; sel_l = np.all((P >= lo - P_["lokal_rand"]) & (P <= hi + P_["lokal_rand"]), axis=1); sel_u = np.all((P >= lo - P_["umgebung_rand"]) & (P <= hi + P_["umgebung_rand"]), axis=1)
    ra = nm.res(P[sel_u]); rb = r_basis[sel_u]; ml = sel_l[sel_u]
    def fern(r, m): v = r[m]; return int(((np.abs(v) > P_["schwelle"]) & ~np.isnan(v)).sum())
    def p90(r, m): v = np.abs(r[m]); v = v[~np.isnan(v)]; return float(np.percentile(v, 90)) if len(v) else 0.0
    fb, fa = fern(rb, ml), fern(ra, ml); red = 1 - fa / max(fb, 1); p90b, p90a = p90(rb, ml), p90(ra, ml); ub, ua = fern(rb, slice(None)), fern(ra, slice(None))
    info.update(fern_lokal_vorher=fb, fern_lokal_nachher=fa, reduktion=round(red, 3), p90_lokal_vorher=round(p90b, 3), p90_lokal_nachher=round(p90a, 3), fern_umgebung_vorher=ub, fern_umgebung_nachher=ua)
    if red < gain: return False, f"Restfeld lokal nur {red * 100:+.0f} % < {gain * 100:.0f} % (Fern {fb}->{fa})", info
    if p90a > p90b + 1e-6: return False, f"lokales p90 steigt {p90b:.3f}->{p90a:.3f}", info
    if ua >= ub: return False, f"Umgebung netto nicht besser (fern {ub}->{ua}): neuer Schaden", info
    info["foto"] = "nicht geprueft (--ohne-fotos oder keine Kameras)"
    if fotoblock is not None:
        ft, fotos = fotoblock
        if not fotos: return False, "kein kalibriertes Foto sieht den Cluster (Foto-Tor nicht beurteilbar)", info
        stl_neu = os.path.join(aus, "foto_tor", f"{tag}_neu.stl"); os.makedirs(os.path.dirname(stl_neu), exist_ok=True); stl_speichern(neu, stl_neu, fotoblock_massstab[0])
        k = ft.kosten(fotoblock_alt[0], stl_neu, fotos, tag); marg = P_["foto_j"] * j; anteil = min(1.0, P_["anteil0"] + P_["anteil_j"] * j)
        info.update(foto_fotos=len(fotos), foto_beurteilbar=len(k), foto_aufschlag=marg, foto_anteil_soll=round(anteil, 3), foto_kosten=k)
        if len(k) < P_["min_fotos"]: return False, f"nur {len(k)} beurteilbare Fotos < {P_['min_fotos']} (Foto-Tor nicht beurteilbar)", info
        gut = [nr for nr, v in k.items() if v["neu"] <= v["alt"] - marg]; info["foto_besser"] = len(gut); anteil_ist = len(gut) / len(k)
        if anteil_ist < anteil: return False, f"foto_diff kosten_lr in {len(gut)}/{len(k)} Fotos besser (um >= {marg}), verlangt {anteil * 100:.0f} %", info
        info["foto"] = f"{len(gut)}/{len(k)} besser"
    return True, "bestanden", info


fotoblock_massstab = [87.0]; fotoblock_alt = [None]


# ------------------------------------------------------------------ Hauptschleife
def kandidaten_fuer_cluster(c, basis_mod, P, r_basis, M, C, a, t_start, vorfit=None):
    """Alle Familien einpassen; Rangfolge nach Guete. Rueckgabe Liste dict(familie,p,laeufe,fit,rang_fit,tm,mf,stuetz,schnitt)."""
    import bauteil_element_wolke as BE
    fams = familien_fuer(c["art"]); out = []; budget = a.minuten_je_cluster * 60 / max(1, len(fams))
    for fam in fams:
        k = vorfit[fam] if vorfit is not None else einpassen(fam, c, basis_mod, P, M, C, budget)          # vorfit: parallel gerechnet (vorfitten), sonst hier seriell
        if not k: continue
        mf, schnitt = BE.koerper(fam, k["p"], M, C, k["laeufe"]); k.update(mf=mf, schnitt=schnitt, tm=aus_manifold(mf))
        import trimesh; from scipy.spatial import cKDTree
        S, _ = trimesh.sample.sample_surface(k["tm"], 8000, seed=1); lo, hi = c["lo"] - 1.5, c["hi"] + 1.5
        k["dc"] = float(np.minimum(cKDTree(S).query(P[c["idx"]][np.linspace(0, c["n"] - 1, min(c["n"], 20000)).astype(int)])[0], P_["kappe"]).mean())                  # mittlerer Abstand Cluster-Punkt -> Koerperflaeche (Flaechigkeit: Punkthaufen im Raum passen nie)
        d2, _ = cKDTree(P[np.all((P >= lo) & (P <= hi), axis=1)]).query(S); k["stuetz"] = stuetzanteil(k["tm"], S, d2, basis_mod, schnitt); out.append(k)
    out.sort(key=lambda k: (k["rang_fit"], k["familie"]))
    if a.test_rangfolge == "umgekehrt": out.reverse()                                               # NUR Beweis: spaete Raenge muessen erreichbar sein
    return out


_VF = {}


def _vf_aufgabe(t):
    """Arbeiter (fork): Einpassung (Cluster ci, Familie fam) gegen die Rundenstart-Wolke. Rueckgabe nur Daten (keine Manifold-Objekte)."""
    ci, fam = t; V = _VF
    try: return t, einpassen(fam, V["cl"][ci], V["mod"], V["P"], V["M"], V["C"], V["budget"])
    except Exception as e: return t, None


def vorfitten(cl, mod, P, M, C, a):
    """ALLE Cluster x Familien der Runde parallel einpassen (Einpassung braucht nur Cluster-Wolke + Wandrahmen, nicht das schrittweise wachsende Modell; das TOR rechnet danach
    seriell gegen das jeweils aktuelle Modell). Nutzerregel: alle Kerne. Deterministisch (feste Startwerte/Abtastung), Reihenfolge unabhaengig von der Arbeiterzahl."""
    import multiprocessing as mp, param_suche as PS
    ls = cl if a.max_cluster <= 0 else cl[:a.max_cluster]
    aufg = [(i, f) for i, c in enumerate(ls) for f in familien_fuer(c["art"])]
    _VF.update(cl=ls, mod=mod, P=P, M=M, C=C, budget=(a.fit_sekunden or a.minuten_je_cluster * 60 / 4))
    n = max(1, min(a.vorfit_arbeiter, PS.arbeiter_zahl(len(aufg), gb_je=0.8)))
    t0 = time.time()
    with mp.get_context("fork").Pool(n) as pool: res = dict(pool.imap_unordered(_vf_aufgabe, aufg, chunksize=1))
    print(f"  Vorfit {len(aufg)} Einpassungen mit {n} Arbeitern: {time.time() - t0:.0f} s", flush=True)
    return {i: {f: res.get((i, f)) for f in familien_fuer(c["art"])} for i, c in enumerate(ls)}


def metrik(P, r):
    v = np.abs(r[~np.isnan(r)]); return dict(n=int(len(v)), median=round(float(np.median(v)), 4), p90=round(float(np.percentile(v, 90)), 4),
                                              fern=int((v > P_["schwelle"]).sum()))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--runden", type=int, default=3)
    ap.add_argument("--kameras"); ap.add_argument("--fotos", type=int, default=6); ap.add_argument("--ohne-fotos", action="store_true")
    ap.add_argument("--minuten-je-cluster", type=float, default=5.0, help="ANNAHME 5 min je Cluster"); ap.add_argument("--uebernehmen", action="store_true")
    ap.add_argument("--start-stl"); ap.add_argument("--ohne-generator", action="store_true"); ap.add_argument("--wolke"); ap.add_argument("--max-cluster", type=int, default=12, help="0 = alle Cluster")
    ap.add_argument("--umgebung", action="store_true", help="Umgebungsmaske + Rausch-/Flaechigkeitsschwellen aus der Wolke messen (tools/wolke_umgebung.py)")
    ap.add_argument("--fit-sekunden", type=float, default=0.0, help="Zeitbudget je Einpassung (Vorfit), 0 = minuten-je-cluster*60/4")
    ap.add_argument("--vorfit-arbeiter", type=int, default=0, help="Einpassungen parallel (fork); 0 = seriell wie bisher")
    ap.add_argument("--test-rangfolge", default="", help="nur Beweis: 'umgekehrt'"); ap.add_argument("--fd", default="--tiefen aus")
    a = ap.parse_args(argv); t00 = time.time()
    from manifold3d import Manifold as M, CrossSection as C
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); aus = os.path.abspath(a.aus); os.makedirs(aus, exist_ok=True)
    massstab = float(obj.get("stl_massstab", 87)); fotoblock_massstab[0] = massstab
    spec = a.wolke or next((b["wolke"] for b in obj.get("bauteile", []) if b.get("typ") == "rumpf_wolke"), None)
    if spec is None: raise SystemExit("keine Wolke (--wolke oder bauteile.rumpf_wolke.wolke)")
    P = wolke_laden(spec); print(f"Wolke {len(P)} Punkte", flush=True)
    # Arbeitsobjekt: Kopie von objekt.json + Symlinks der Nachbardateien (Generator/foto_diff lesen aus dem Objektordner)
    wd = os.path.join(aus, "obj"); os.makedirs(wd, exist_ok=True)
    for f in os.listdir(od):
        if f == "objekt.json": continue
        q = os.path.join(wd, f)
        if not os.path.lexists(q): os.symlink(os.path.join(od, f), q)
    if a.kameras:
        q = os.path.join(wd, "messprotokoll")
        if os.path.lexists(q): os.remove(q)
        os.symlink(os.path.abspath(a.kameras), q)
    arb = copy.deepcopy(obj); arb.setdefault("bauteile", [])
    eb = next((b for b in arb["bauteile"] if b.get("typ") == "element_wolke"), None)
    if eb is None: eb = dict(typ="element_wolke", elemente=[], hinweis="automatisch: generator_elemente_schleife.py"); arb["bauteile"].append(eb)
    if "fotos_dir" in arb and not os.path.isabs(arb["fotos_dir"]): arb["fotos_dir"] = os.path.join(ROOT, arb["fotos_dir"])
    arbp = os.path.join(aus, "obj", "objekt.json"); json.dump(arb, open(arbp, "w"), indent=1, ensure_ascii=False)

    def bauen(k):
        json.dump(arb, open(arbp, "w"), indent=1, ensure_ascii=False); name = f"_elsch_{os.getpid()}_{k}.stl"
        env = dict(os.environ, OBJ_DIR=wd, STL_NAME=name, ELEMENTE_AUS=os.path.join(aus, f"elemente_{k}.json"), RUMPF_WOLKE_PARAMETER=os.path.join(aus, f"rumpf_wolke_parameter_{k}.json"),
                   SCALE=str(int(massstab)), MINMM="0.8")
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "baukasten_gen.py"), wd], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode != 0: raise SystemExit("Generator fehlgeschlagen: " + (r.stderr or r.stdout)[-600:])
        src = os.path.join(ROOT, "modelle", "stl", name); rd = os.path.join(aus, f"runde_{k}"); os.makedirs(rd, exist_ok=True); dst = os.path.join(rd, "stand.stl"); shutil.move(src, dst); return dst

    if a.start_stl: stl0 = os.path.abspath(a.start_stl)
    elif a.ohne_generator: raise SystemExit("--ohne-generator braucht --start-stl")
    else: stl0 = bauen(0)
    base = stl_laden(stl0, massstab); stl_aktuell = stl0
    umg_info = None
    if a.umgebung:
        import wolke_umgebung as WU
        m0_ = Modell(base); r0_ = m0_.res(P, band=30); zb_ = float(base.bounds[0, 2]); rau = WU.rauschen_messen(P, base, r0_, zb_); s05 = rau["kacheln"]["0.5"]["sigma_median"]
        keep, umg_info = WU.umgebungsmaske(P, base, r0_, zb_, s05)
        WU.bild(P, keep, base, os.path.join(aus, "umgebung.jpg"), f"behalten {umg_info['n_behalten']}/{umg_info['n_start']}")
        abg = dict(sigma_lokal_0_5=s05, schwelle=round(WU.K_SCHWELLE * s05, 4), dc_max=rau["kacheln"]["2.0"]["mittel_betrag_p90"],
                   herleitung=f"schwelle = {WU.K_SCHWELLE} x sigma(0,5-m-Kacheln, Median); dc_max = p90 des mittleren Betrags E|d| der Planfit-Kacheln 2 m (eine wirklich ebene Wand besteht das Kriterium in 90 % der Kacheln; Relief+Posenversatz enthalten = obere Schranke)",
                   vorher=dict(schwelle=P_["schwelle"], dc_max=P_["dc_max"]))
        P_["schwelle"] = abg["schwelle"]; P_["dc_max"] = abg["dc_max"]; P = P[keep]
        json.dump(dict(rauschen=rau, umgebung=umg_info, abgeleitet=abg), open(os.path.join(aus, "umgebung.json"), "w"), indent=1, ensure_ascii=False, default=float)
        print(f"Umgebungsmaske: {umg_info['n_behalten']}/{umg_info['n_start']} Punkte; sigma {s05} -> schwelle {abg['schwelle']}, dc_max {abg['dc_max']}", flush=True)
    ft = None; K = {}
    if not a.ohne_fotos and a.kameras:
        K = kamera_laden(a.kameras); print(f"{len(K)} kalibrierte Kameras", flush=True)
        ft = FotoTor(arbp, aus, a.fd.split())
    elif not a.ohne_fotos: print("WARNUNG: keine --kameras -> Foto-Tor entfaellt (in jeder Entscheidung vermerkt)", flush=True)
    prot = open(os.path.join(aus, "protokoll.jsonl"), "w")
    def schreibe(d): prot.write(json.dumps(d, ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o)) + "\n"); prot.flush()
    ergebnis = dict(umgebung=(None if umg_info is None else dict(abgeleitet=abg, umgebung={k: v for k, v in umg_info.items()}, rauschen_kacheln=rau["kacheln"], sigma_wand=rau["sigma_wand"])), start=None, runden=[], uebernommen=[], abgelehnt=0, geprueft=0, annahmen=P_, stl_start=stl0, ohne_fotos=bool(a.ohne_fotos or not a.kameras), grund_ende=None)
    nid = 0; vorher_p90 = None; vorher_cl = None
    try:
        for k in range(1, a.runden + 1):
            mod = Modell(base); r = mod.res(P); m0 = metrik(P, r); zmin = float(base.bounds[0, 2])
            cl = cluster_finden(P, r, zmin, +1) + cluster_finden(P, r, zmin, -1); cl.sort(key=lambda c: (-c["n"], c["art"]))
            if k == 1: ergebnis["start"] = dict(restfeld=m0, cluster=len(cl))
            schreibe(dict(typ="runde", runde=k, restfeld_vorher=m0, cluster=[dict(id=f"R{k}C{i}", art=c["art"], n=c["n"], lo=c["lo"], hi=c["hi"], schwerpunkt=c["schwerpunkt"], r_median=c["r_median"], r_p90=c["r_p90"]) for i, c in enumerate(cl)]))
            print(f"Runde {k}: Restfeld {m0}; {len(cl)} Cluster", flush=True)
            if k > 1 and not cl: ergebnis["grund_ende"] = "keine Cluster mehr (konvergiert)"; break
            neue = []; cl_run = cl if a.max_cluster <= 0 else cl[:a.max_cluster]
            vf = vorfitten(cl, mod, P, M, C, a) if a.vorfit_arbeiter > 0 else None
            for i, c in enumerate(cl_run):
                cid = f"R{k}C{i}"; t0 = time.time(); ranglist = kandidaten_fuer_cluster(c, mod, P, r, M, C, a, t0, None if vf is None else vf[i]); j = 0; bestanden = []
                fotoblock = None
                if ft is not None:
                    fotoblock = (ft, sehende_fotos(K, c, a.fotos)); fotoblock_alt[0] = stl_aktuell
                for rang, kand in enumerate(ranglist):
                    if bestanden and kand["rang_fit"] > bestanden[0]["rang_fit"] * P_["tie"]:
                        schreibe(dict(typ="kandidat", cluster=cid, familie=kand["familie"], rang=rang, entscheidung="nicht geprueft", grund="Abbruch: kein weiterer kann besser sein (Fit-Guete > 105 % des Bestandenen)")); continue
                    if time.time() - t0 > a.minuten_je_cluster * 60:
                        schreibe(dict(typ="kandidat", cluster=cid, familie=kand["familie"], rang=rang, entscheidung="nicht geprueft", grund=f"Zeitbudget {a.minuten_je_cluster} min je Cluster erschoepft")); continue
                    ok, grund, info = tor(kand, c, mod, P, r, M, C, j, fotoblock, aus, f"{cid}_{kand['familie']}", None)
                    ergebnis["geprueft"] += 1
                    schreibe(dict(typ="kandidat", runde=k, cluster=cid, familie=kand["familie"], rang=rang, anzahl_vorher_geprueft=j, aufschlag=info.get("aufschlag_restfeld"), p=kand["p"], laeufe=kand["laeufe"],
                                  fit=kand["fit"], rang_fit=kand["rang_fit"], tor=info, entscheidung="uebernommen" if ok else "abgelehnt", grund=grund, sekunden=round(time.time() - t0, 1)))
                    print(f"  {cid} {c['art']} n={c['n']} #{rang} {kand['familie']:<10} fit {kand['fit']:.3f}: {'JA' if ok else 'nein'} - {grund}", flush=True)
                    j += 1
                    if ok: bestanden.append(dict(kand, info=info, rang_fit=kand["rang_fit"]))
                    else: ergebnis["abgelehnt"] += 1
                if bestanden:
                    w = max(bestanden, key=lambda b: (b["info"]["reduktion"], -b["rang_fit"])); nid += 1
                    el = dict(id=f"E{nid}", familie=w["familie"], p={q: round(float(v), 4) for q, v in w["p"].items()}, laeufe=w["laeufe"], cluster=cid, runde=k, art=c["art"],
                              tor_kurz=f"Restfeld lokal -{w['info']['reduktion'] * 100:.0f} %, Stuetz {w['info']['stuetz']}, Foto {w['info']['foto']}, j={w['info']['j']}",
                              quelle=f"Wolke, Restfeld-Cluster {cid} ({c['art']}, {c['n']} Punkte)", historie=[dict(datum=datetime.date.today().isoformat(), werkzeug="generator_elemente_schleife.py", aktion="hinzugefuegt", tor=w["info"])])
                    eb["elemente"].append(el); neue.append(el); ergebnis["uebernommen"].append(dict(id=el["id"], cluster=cid, familie=el["familie"], p=el["p"]))
                    base = w["neues_mesh"]; mod = Modell(base); r = mod.res(P)                           # greedy: naechster Cluster sieht das neue Modell
                    if not a.ohne_generator: pass
                    tmp = os.path.join(aus, f"runde_{k}"); os.makedirs(tmp, exist_ok=True); stl_aktuell = os.path.join(tmp, "zwischen.stl"); stl_speichern(base, stl_aktuell, massstab)
            if not a.ohne_generator and neue:
                dst = bauen(k); gen = stl_laden(dst, massstab)
                dv = (abs(gen.volume) - abs(base.volume)) / max(abs(base.volume), 1e-9); print(f"  Generator-STL Volumen {dv * 100:+.2f} % gegen In-Process-Vereinigung", flush=True)
                base = gen; stl_aktuell = dst
            elif neue:
                rd = os.path.join(aus, f"runde_{k}"); os.makedirs(rd, exist_ok=True); stl_speichern(base, os.path.join(rd, "stand.stl"), massstab); stl_aktuell = os.path.join(rd, "stand.stl")
            mod = Modell(base); r2 = mod.res(P); m1 = metrik(P, r2); cl2 = cluster_finden(P, r2, zmin, +1) + cluster_finden(P, r2, zmin, -1)
            rr = dict(runde=k, restfeld_vorher=m0, restfeld_nachher=m1, cluster_vorher=len(cl), cluster_nachher=len(cl2), uebernommen=[e["id"] for e in neue])
            ergebnis["runden"].append(rr); schreibe(dict(typ="runde_ende", **rr)); print(f"  nach Runde {k}: {m1}, Cluster {len(cl)} -> {len(cl2)}", flush=True)
            if not neue: ergebnis["grund_ende"] = "keine Uebernahme in der Runde"; break
            if m1["p90"] >= m0["p90"] and len(cl2) >= len(cl): ergebnis["grund_ende"] = "Restfeld-p90 und Clusterzahl sinken nicht mehr"; break
        else: ergebnis["grund_ende"] = "Rundenzahl erreicht"
    finally:
        if ft is not None: ft.schliessen()
    ergebnis["ende"] = ergebnis["runden"][-1]["restfeld_nachher"] if ergebnis["runden"] else ergebnis["start"]; ergebnis["stl_ende"] = stl_aktuell; ergebnis["sekunden"] = round(time.time() - t00)
    json.dump(arb, open(arbp, "w"), indent=1, ensure_ascii=False); shutil.copy(arbp, os.path.join(aus, "objekt_mit_elementen.json"))
    json.dump(ergebnis, open(os.path.join(aus, "ergebnis.json"), "w"), indent=1, ensure_ascii=False, default=float)
    if a.uebernehmen:
        o2 = json.load(open(objp)); e2 = next((b for b in o2["bauteile"] if b.get("typ") == "element_wolke"), None)
        if e2 is None: e2 = dict(typ="element_wolke", elemente=[]); o2["bauteile"].append(e2)
        e2["elemente"] += [e for e in eb["elemente"] if e["id"] not in {x["id"] for x in e2["elemente"]}]
        json.dump(o2, open(objp, "w"), indent=1, ensure_ascii=False); print("objekt.json aktualisiert (--uebernehmen)")
    print(f"ENDE: {ergebnis['grund_ende']}; uebernommen {len(ergebnis['uebernommen'])}, geprueft {ergebnis['geprueft']}, abgelehnt {ergebnis['abgelehnt']}; Restfeld {ergebnis['start']['restfeld']} -> {ergebnis['ende']}")
    return ergebnis


if __name__ == "__main__":
    main()
