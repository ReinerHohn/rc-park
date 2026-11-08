#!/usr/bin/env python3
"""bildwert.py - Bildwert messen: nur Bilder/Frames verwenden, die LUECKEN schliessen (SPEC_S7_BILDWERT, Plan Stufe 4c; 2026-11-06).

Ersetzt abdeckung.py (Faustwerte; alte Datei bleibt) und die Aehnlichkeitsklassen aus bilder_schleife.py durch eine Messung je Zelle:
  1. --bedarf       Bedarfskarte je Flaeche (Wand/Vorbau/Dach) aus der S3-Fehlerkarte (n_fotos, rot, gelb) und der Zahl n_kam der BESTEHENDEN Kameras,
                    die die Zelle gueltig sehen (Embree gegen den Stand). Tabelle Bedarf je Seite (Nord/Ost/Sued/West/Dach) = "wo fehlen Bilder".
                    bedarf = w_abdeckung*max(0,3-n_kam)/3 + w_fehler*(gelb+rot)*[n_fotos>=3]   (m2-gewichtet; Dach: nur der Fehleranteil, Spec 1)
  2. --poses-mapillary MANIFEST   grobe Pose aus GPS+Peilung (Hoehe 1,6 m ANNAHME, Nick 0, Bildwinkel ANNAHME), Panoramen als Ausschnitte
     --poses-frames ORDNER        Pose von Videoframes/Handyfotos ohne GPS: SIFT gegen Referenzfotos je Seite (CPU-Ersatz fuer LightGlue wenn die GPU-Sperre/Platztor blockiert)
                                  + PnP gegen 3D-Punkte (Modelloberflaeche per Strahl durch die Referenzkamera, ANNAHME statt Netzpunkte); < min_inlier Inlier = Wert 0 "nicht verortbar"
  3. --bewerten KAND.json   Wert je Kandidat (vorher), gierige Auswahl mit Aktualisierung von n_kam, Abbruch min_wert/max_bilder, Bildblatt der wertvollsten (ANSEHEN)
  4. --nachher AUSWAHL.json NEUE_KAMERAS.json   tatsaechlich neue Zellen je gewaehltem Bild gegen die Vorhersage, Kalibrierfaktor, "ohne Gewinn"-Liste
Schwellen sind Argumente; jede ohne Quelle heisst ANNAHME (siehe --help). Kein Generator-/foto_diff-Zugriff; schreibt nur unter --aus.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/bildwert.py modelle/kaufhaus_null5/objekt.json --bedarf --aus DIR
"""
import os, sys, json, glob, argparse, time, math
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
SEITEN = ("Nord", "Ost", "Sued", "West", "Dach")
FARBE = {"Nord": (255, 160, 60), "Ost": (60, 200, 60), "Sued": (60, 60, 255), "West": (0, 200, 255), "Dach": (200, 60, 200)}


# ------------------------------------------------------------------ Parameter (alle Schwellen hier, alle ANNAHME ausser wo Quelle genannt)
def standard_parameter():
    return dict(
        w_abdeckung=1.0,            # Spec 1 (Plan-Schluessel)
        w_fehler=0.0,               # ANNAHME: AUS (gemessen 2026-11-06: schon 0,1 gibt Frontdubletten 27 m2 Wert, T1 faellt durch; Fehlercluster 352 m2), weil gelb durch Textur saturiert (STAND_2026-11-06 S3 Phase A: Mittel 0,30-0,46); Spec-Standard 1 waere ein Fehlerbedarf von ~100 m2 allein
        fehler_nur_cluster=True,    # ANNAHME: Fehlerbedarf nur in Zellen innerhalb eines S3-Fehlerclusters (stimmen >= 0.5), nicht flaechig
        n_ziel=3,                   # Spec 1: Zelle gilt mit >= 3 Kameras als abgedeckt
        min_fotos=3,                # S3-Plan konvergenz.min_fotos: Fehlerterm nur wo >= 3 Fotos die Zelle sahen
        einfall_max_deg=70.0,       # Spec 2
        gsd_ziel_m=0.05,            # Spec 2 (ANNAHME 0,05 m/px)
        basis_min_deg=10.0, basis_max_deg=30.0,   # Spec 2
        dublette_faktor=0.5,        # Spec 2: "sonst nur halber Wert"
        min_wert_m2=0.25,           # Spec 3: ANNAHME = Druckaufloesung x 2
        max_bilder=40,              # ANNAHME: Obergrenze je Lauf
        sicht_schritt=4,            # ANNAHME: Sichtbarkeit auf Raster 0,4 m (4 x 0,10 m); Embree-Kosten, Verdeckung aendert sich langsam
        sicht_tol_m=0.15,           # S3-Plan sicht_toleranz_m
        min_modell_anteil=0.5,      # ANNAHME: Grobzelle zaehlt als Flaeche, wenn >= 50 % der Feinzellen Modelloberflaeche haben
        augenhoehe_m=1.6,           # Spec 2 (ANNAHME)
        hfov_deg=65.0,              # ANNAHME: Handy-/Mapillary-Weitwinkel ohne EXIF-Brennweite
        pano_ausschnitt_deg=90.0,   # ANNAHME: Panorama -> 4 Ausschnitte (Peilung + 0/90/180/270), je 90 Grad
        min_inlier=30,              # Spec 2
    )


# ------------------------------------------------------------------ Kameras
def kamera_aus_K(K, nr):
    k = K["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); W, H = (k.get("bild") or [None, None])
    return dict(name=nr, R=R, t=np.array(k["t"], float), f=float(k["f_px"]), cx=float(k.get("cx", W / 2)), cy=float(k.get("cy", H / 2)), W=int(W), H=int(H), quelle="K")


def kameras_laden(objp, obj, sfm_json=None):
    """Bestehende Kameras im Modellrahmen: K-<nr>.json (amtliche Anker, wie foto_diff) hat Vorrang; sonst kameras_unverzerrt.json (SfM-Rahmen) um den
    mittleren z-Versatz K-minus-SfM verschoben (Kaufhaus: 0,431 m = Gelaendeverschiebung 'rahmen_verschiebung')."""
    od = os.path.dirname(os.path.abspath(objp)); out = {}
    for p in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        try: K = json.load(open(p))
        except Exception: continue
        nr = os.path.basename(p)[2:-5]
        if "kamera" in K and K["kamera"].get("bild"): out[nr] = kamera_aus_K(K, nr)
    info = dict(n_K=len(out), n_sfm=0, dz=0.0)
    sj = sfm_json
    if sj is None:
        for c in glob.glob(os.path.join(od, "sfm", "dicht_*", "kameras_unverzerrt.json")): sj = c; break
    if sj and os.path.exists(sj):
        S = json.load(open(sj)); dz = []
        for nr, k in S.items():
            if nr in out:
                R = np.array(k["R"], float); dz.append((-out[nr]["R"].T @ out[nr]["t"] - (-R.T @ np.array(k["t"], float)))[2])
        dzm = float(np.median(dz)) if dz else 0.0; info["dz"] = round(dzm, 4)
        for nr, k in S.items():
            if nr in out: continue
            R = np.array(k["R"], float); C = -R.T @ np.array(k["t"], float); C[2] += dzm
            out[nr] = dict(name=nr, R=R, t=-R @ C, f=float(k["fx"]), cx=float(k["cx"]), cy=float(k["cy"]), W=int(k["W"]), H=int(k["H"]), quelle="sfm"); info["n_sfm"] += 1
    return out, info


def zentrum(c): return -c["R"].T @ c["t"]


def blickrichtung(c): return c["R"][2]


# ------------------------------------------------------------------ Szene: Zellen aller Flaechen
def seite_aus_normale(n):
    if n[2] > 0.3: return "Dach"
    a = math.degrees(math.atan2(n[1], n[0])) % 360
    return "Ost" if (a < 45 or a >= 315) else "Nord" if a < 135 else "West" if a < 225 else "Sued"


def block(A, s, fn):
    nz, nu = A.shape; Z, U = -(-nz // s), -(-nu // s); B = np.full((Z * s, U * s), np.nan, A.dtype if A.dtype.kind == "f" else float); B[:nz, :nu] = A
    return fn(B.reshape(Z, s, U, s).transpose(0, 2, 1, 3).reshape(Z, U, s * s), axis=2)


class Szene:
    """Grobe Zellen (Rastermass = zelle * sicht_schritt) aller Flaechen, global durchnummeriert. Felder je Zelle: P (Modelloberflaeche), n, A (Abdeckungsflaeche m2),
    Ferr (Fehlerflaeche m2), fid, seite."""
    def __init__(self, fl):
        self.P = np.concatenate([f["P"] for f in fl]); self.n = np.concatenate([np.tile(f["n"], (len(f["P"]), 1)) for f in fl])
        self.A = np.concatenate([f["A"] for f in fl]); self.Ferr = np.concatenate([f["Ferr"] for f in fl]); self.fidx = np.concatenate([np.full(len(f["P"]), i) for i, f in enumerate(fl)])
        self.fl = fl; self.N = len(self.P); self.seite = np.array([f["seite"] for f in fl])[self.fidx]; self.dach = np.array([f["seite"] == "Dach" for f in fl])[self.fidx]
        self.sl = []; o = 0
        for f in fl: self.sl.append(slice(o, o + len(f["P"]))); o += len(f["P"])


def szene_aus_restfeld(restfeld_dir, fk_dir, par, log=print):
    """Flaechen = restfeld.json (n, o, dd, e) + restfeld_<fid>.npz (Modelltiefe); Fehler = fehlerkarte_k0/<fid>.npz (n_fotos, rot, gelb) und cluster.json (Zellen im Cluster)."""
    R = json.load(open(os.path.join(restfeld_dir, "restfeld.json"))); s = par["sicht_schritt"]; fl = []
    cj = None
    if fk_dir and os.path.exists(os.path.join(fk_dir, "cluster.json")): cj = json.load(open(os.path.join(fk_dir, "cluster.json")))
    for fid, F in R["fassaden"].items():
        p = os.path.join(restfeld_dir, f"restfeld_{fid}.npz")
        if not os.path.exists(p): continue
        z = np.load(p); modell = z["modell"]; u0, z1, zelle = float(z["u0"]), float(z["z1"]), float(z["zelle"]); nz, nu = modell.shape
        n, o, dd, e = (np.array(F[k], float) for k in ("n", "o", "dd", "e")); dach = fid.startswith("d")
        gueltig = np.isfinite(modell); anteil = block(gueltig.astype(float), s, np.mean)
        zc = zelle * s; Z, U = anteil.shape; gu, gz = np.meshgrid(u0 + (np.arange(U) + 0.5) * zc, z1 - (np.arange(Z) + 0.5) * zc)
        mo = block(np.where(gueltig, modell, np.nan), s, np.nanmean); oz = o[2] if e[2] > 0.999 else 0.0
        Pm = o[None] + gu.reshape(-1, 1) * dd[None] + (gz.reshape(-1, 1) - oz) * e[None] + n[None] * np.nan_to_num(mo.reshape(-1, 1), nan=0.0)
        ok = (anteil >= par["min_modell_anteil"]).ravel()
        nf = np.zeros((nz, nu)); gel = np.zeros((nz, nu)); rot = np.zeros((nz, nu)); fp = os.path.join(fk_dir, f"{fid}.npz") if fk_dir else None
        if fp and os.path.exists(fp):
            k = np.load(fp); nf, gel, rot = k["n_fotos"].astype(float), k["gelb"].astype(float), k["rot"].astype(float)
        err = (gel + rot) * (nf >= par["min_fotos"]) * gueltig
        if par["fehler_nur_cluster"]:
            inc = np.zeros((nz, nu), bool)
            for c in (cj or {}).get("cluster", []):
                if c["fid"] != fid: continue
                j0, j1 = int((c["u0"] - u0) / zelle), int(math.ceil((c["u1"] - u0) / zelle)); i0, i1 = int((z1 - c["z1"]) / zelle), int(math.ceil((z1 - c["z0"]) / zelle)); inc[max(i0, 0):i1, max(j0, 0):j1] = True
            err = err * inc
        Ferr = block(err * zelle * zelle, s, np.nansum).ravel()
        A = (anteil * zc * zc).ravel() * (0.0 if dach else 1.0)                                          # Dach: kein Abdeckungsbedarf (Spec 1)
        fl.append(dict(fid=fid, n=n, P=Pm[ok], A=A[ok], Ferr=Ferr[ok], seite=seite_aus_normale(n), dach=dach, shape=(Z, U), ok=ok, u0=u0, z1=z1, zc=zc, gu=gu, gz=gz))
    return Szene(fl)


def szene_aus_stl(stl, massstab, par, abstand=0.4):
    """Ohne Fehlerkarte/Restfeld (z. B. Martinstor): Oberflaechenproben der STL (Gitter ~abstand, flaechenproportional) mit Flaechennormale; kein Fehlerterm."""
    import trimesh
    m = trimesh.load(stl); m.apply_scale(float(massstab) / 1000.0); n = max(2000, int(m.area / abstand ** 2)); P, fi = trimesh.sample.sample_surface(m, n, seed=0); N = m.face_normals[fi]
    seite = np.array([seite_aus_normale(x) for x in N]); fl = []
    for sname in SEITEN:
        i = np.flatnonzero(seite == sname)
        if len(i): fl.append(dict(fid=sname.lower(), n=np.array([0, 0, 1.0]), P=P[i], A=np.full(len(i), m.area / n) * (0.0 if sname == "Dach" else 1.0), Ferr=np.zeros(len(i)), seite=sname, dach=sname == "Dach", normalen=N[i]))
    S = Szene(fl); S.n = np.concatenate([f["normalen"] for f in fl]); return S


# ------------------------------------------------------------------ Sicht
class Verdecker:
    def __init__(self, stl, massstab, obj=None):
        import trimesh; from trimesh.ray.ray_pyembree import RayMeshIntersector
        m = trimesh.load(stl); m.apply_scale(float(massstab) / 1000.0); self.mesh = m; self.n_nachbarn = 0; sicht_m = m
        try:                                                                                          # LoD2-Nachbarn als Verdecker (wie fassade_ortho.nachbarn_netz)
            import fassade_ortho as FO; nb, n = FO.nachbarn_netz(obj); sicht_m = trimesh.util.concatenate([m, nb]); self.n_nachbarn = n
        except Exception as ex: self.nachbar_fehler = f"{type(ex).__name__}: {ex}"
        self.rmi = RayMeshIntersector(sicht_m)

    def verdeckt(self, C, P, tol):
        d = P - C[None]; dist = np.linalg.norm(d, axis=1); loc, ri, _ = self.rmi.intersects_location(np.repeat(C[None], len(P), 0), d / dist[:, None], multiple_hits=False)
        th = np.full(len(P), np.inf); th[ri] = np.linalg.norm(loc - C[None], axis=1); return th < dist - tol


def sicht(cam, S, V, par, idx=None):
    """Bool-Maske (S.N): Zelle im Bild, vor der Kamera, Einfallswinkel < max, Bodenaufloesung < Ziel, nicht vom Modell verdeckt."""
    out = np.zeros(S.N, bool); idx = np.arange(S.N) if idx is None else idx; P = S.P[idx]
    pc = P @ cam["R"].T + cam["t"]; z = pc[:, 2]; ok = z > 0.5; zz = np.where(ok, z, 1.0)
    u = cam["f"] * pc[:, 0] / zz + cam["cx"]; v = cam["f"] * pc[:, 1] / zz + cam["cy"]; ok &= (u >= 0) & (u < cam["W"]) & (v >= 0) & (v < cam["H"])
    C = zentrum(cam); dv = P - C[None]; dist = np.linalg.norm(dv, axis=1); cosw = -(dv * S.n[idx]).sum(1) / np.maximum(dist, 1e-9)
    ok &= cosw > math.cos(math.radians(par["einfall_max_deg"])); ok &= (z / (cam["f"] * np.maximum(cosw, 1e-3))) < par["gsd_ziel_m"]
    j = np.flatnonzero(ok)
    if len(j) and V is not None: ok[j] = ~V.verdeckt(C, P[j], par["sicht_tol_m"])
    out[idx] = ok; return out


def bedarf_zellen(S, nk, par, idx=None):
    idx = np.arange(S.N) if idx is None else idx
    return par["w_abdeckung"] * S.A[idx] * np.maximum(0, par["n_ziel"] - nk[idx]) / par["n_ziel"] + par["w_fehler"] * S.Ferr[idx]


def basisfaktor(cam, S, idx, nk, Vis, cams_C, par):
    """Je Zelle 1, wenn es keine bestehende Kamera gibt oder eine mit Basiswinkel 10-30 Grad; sonst dublette_faktor (Spec 2)."""
    f = np.ones(len(idx)); mit = nk[idx] > 0
    if not mit.any() or len(cams_C) == 0: return f
    P = S.P[idx[mit]]; d0 = cam_C_dir = zentrum(cam)[None] - P; d0 /= np.linalg.norm(d0, axis=1, keepdims=True)
    d1 = cams_C[None, :, :] - P[:, None, :]; d1 /= np.linalg.norm(d1, axis=2, keepdims=True); ang = np.degrees(np.arccos(np.clip((d0[:, None, :] * d1).sum(2), -1, 1)))
    ok = ((ang >= par["basis_min_deg"]) & (ang <= par["basis_max_deg"]) & Vis[:, idx[mit]].T).any(1); f[mit] = np.where(ok, 1.0, par["dublette_faktor"]); return f


def n_kam_berechnen(S, cams, V, par, log=print):
    """Rueckgabe nk (S.N), Vis (ncam x N bool), namen."""
    namen = sorted(cams); Vis = np.zeros((len(namen), S.N), bool); t0 = time.time()
    for i, nr in enumerate(namen): Vis[i] = sicht(cams[nr], S, V, par)
    log(f"Sicht {len(namen)} Kameras x {S.N} Zellen: {time.time() - t0:.0f} s"); return Vis.sum(0).astype(int), Vis, namen


# ------------------------------------------------------------------ Ausgabe Bedarf
def bedarf_tabelle(S, nk, par):
    """Je Seite: Flaeche, Flaeche mit n_kam < 3, Abdeckungsbedarf, Fehlerbedarf, Summe (alles m2)."""
    b_ab = par["w_abdeckung"] * S.A * np.maximum(0, par["n_ziel"] - nk) / par["n_ziel"]; b_fe = par["w_fehler"] * S.Ferr; T = {}
    for s in SEITEN:
        m = S.seite == s
        T[s] = dict(
                    zellen=int(m.sum()), zellen_nk0=int((m & (nk == 0)).sum()), zellen_nk_lt3=int((m & (nk < par["n_ziel"])).sum()),
                    anteil_nk_ge3=round(float((nk[m] >= par["n_ziel"]).mean()), 4) if m.any() else None, nk_median=float(np.median(nk[m])) if m.any() else None,
                    bedarf_abdeckung_m2=round(float(b_ab[m].sum()), 3), bedarf_fehler_m2=round(float(b_fe[m].sum()), 3), bedarf_m2=round(float((b_ab + b_fe)[m].sum()), 3))
        T[s]["flaeche_m2"] = round(float(S.A[m].sum()), 2) if s != "Dach" else None
    return T


def bedarf_bilder(S, nk, par, aus, log=print):
    os.makedirs(aus, exist_ok=True); b = bedarf_zellen(S, nk, par); alle = {}
    for i, f in enumerate(S.fl):
        sl = S.sl[i]; Z, U = f["shape"] if "shape" in f else (None, None)
        if Z is None: continue
        def vol(x, fill=np.nan):
            M = np.full(Z * U, fill, float); M[f["ok"]] = x; return M.reshape(Z, U)
        Mn, Mb, Mf = vol(nk[sl].astype(float)), vol(b[sl]), vol(S.Ferr[sl])
        np.savez_compressed(os.path.join(aus, f"bedarf_{f['fid']}.npz"), n_kam=Mn, bedarf=Mb, fehler=Mf, u0=f["u0"], z1=f["z1"], zelle=f["zc"], seite=f["seite"])
        sk = max(2, min(int(round(260 / Z)), int(round(420 / U)))); T = []
        for A, lo, hi, tit, cm in ((Mn, 0, 6, "n_kam (0..6)", cv2.COLORMAP_VIRIDIS), (Mb, 0, max(float(np.nanmax(Mb)) if np.isfinite(Mb).any() else 1e-6, 1e-6), "bedarf m2 je Zelle", cv2.COLORMAP_INFERNO)):
            im = cv2.applyColorMap(np.clip((np.nan_to_num(A) - lo) / max(hi - lo, 1e-9) * 255, 0, 255).astype(np.uint8), cm); im[~np.isfinite(A)] = 40
            im = cv2.resize(im, (U * sk, Z * sk), interpolation=cv2.INTER_NEAREST); cv2.rectangle(im, (0, 0), (im.shape[1], 18), (0, 0, 0), -1); cv2.putText(im, tit, (3, 13), 0, 0.4, (255, 255, 255), 1); T.append(im)
        kopf = np.zeros((22, T[0].shape[1] * 2, 3), np.uint8)
        cv2.putText(kopf, f"{f['fid']} ({f['seite']}): Bedarf {float(np.nansum(Mb)):.2f} m2, Zellen n_kam<3: {int((np.isfinite(Mn) & (Mn < 3)).sum())}/{int(np.isfinite(Mn).sum())}", (3, 15), 0, 0.45, (255, 255, 255), 1)
        im = cv2.vconcat([kopf, cv2.hconcat(T)]); cv2.imwrite(os.path.join(aus, f"bedarf_{f['fid']}.png"), im); alle[f["fid"]] = im
    # Uebersicht je Seite: Bedarfstafeln eines Seitentyps nebeneinander
    for s in SEITEN:
        ims = [alle[f["fid"]] for f in S.fl if f["seite"] == s and f["fid"] in alle]
        if not ims: continue
        Wm = max(i.shape[1] for i in ims); zeilen = [cv2.copyMakeBorder(i, 0, 4, 0, Wm - i.shape[1], cv2.BORDER_CONSTANT) for i in ims]
        cv2.imwrite(os.path.join(aus, f"bedarf_seite_{s}.jpg"), cv2.vconcat(zeilen), [cv2.IMWRITE_JPEG_QUALITY, 85])


# ------------------------------------------------------------------ Kandidaten: Posen
def pose_blick(C, d, f, W, H, nick_deg=0.0):
    """Welt->Kamera aus Zentrum C und horizontaler Blickrichtung d (x,y), Nick nach oben positiv; Kamera: x rechts, y unten, z vorn."""
    d = np.array([d[0], d[1], 0.0]); d /= np.linalg.norm(d); fw = d * math.cos(math.radians(nick_deg)) + np.array([0, 0, math.sin(math.radians(nick_deg))])
    x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x); R = np.vstack([x, y, fw]); return dict(R=R, t=-R @ C, f=f, cx=W / 2, cy=H / 2, W=W, H=H)


def poses_mapillary(objp, obj, manifest, par, ausdir=None):
    """Mapillary-Seitenbilder (G6): GPS (UTM) + Peilung -> grobe Pose im Modellrahmen. Panoramen: 4 Ausschnitte (Ausschnittsbilder werden unter ausdir geschrieben)."""
    rr = obj["rahmen"]; m0 = np.array(rr["mitte_utm"], float); xh = np.array(rr["xhat_utm"], float); yh = np.array(rr["yhat_utm"], float); out = []
    for e in json.load(open(manifest)):
        E, N = e["utm"]; C = np.array([(E - m0[0]) * xh[0] + (N - m0[1]) * xh[1], (E - m0[0]) * yh[0] + (N - m0[1]) * yh[1], par["augenhoehe_m"]])
        peil = e.get("computed_compass_angle"); q = "computed_compass_angle"
        if peil is None or not (0 <= peil <= 360): peil, q = e.get("compass_angle"), "compass_angle"
        if peil is None or not (0 <= peil <= 360): out.append(dict(id=e["id"], quelle="mapillary", seite_hint=e["seite"], wert=0.0, grund="keine gueltige Peilung")); continue
        a = math.radians(peil); dU = np.array([math.sin(a), math.cos(a)]); d = np.array([dU @ xh, dU @ yh])
        if not os.path.exists(e["datei"]): out.append(dict(id=e["id"], quelle="mapillary", seite_hint=e["seite"], wert=0.0, grund="Datei fehlt")); continue
        im = cv2.imread(e["datei"]); H, W = im.shape[:2]
        if e.get("is_pano") or e.get("camera_type") == "spherical":
            hf = par["pano_ausschnitt_deg"]; f = 0.5 * 1440 / math.tan(math.radians(hf / 2))
            for k in range(4):
                th = a + math.radians(90 * k); dU = np.array([math.sin(th), math.cos(th)]); d = np.array([dU @ xh, dU @ yh]); pz = pose_blick(C, d, f, 1440, 1080)
                bild = None
                if ausdir:
                    bild = os.path.join(ausdir, f"pano_{e['id']}_{k}.jpg"); os.makedirs(ausdir, exist_ok=True)
                    if not os.path.exists(bild): cv2.imwrite(bild, pano_ausschnitt(im, 90 * k, hf, 1440, 1080), [cv2.IMWRITE_JPEG_QUALITY, 88])
                out.append(dict(id=f"{e['id']}_p{k}", quelle="mapillary_pano", seite_hint=e["seite"], pose=pz, bild=bild, pose_guete=f"grob: GPS +-3 m, Peilung +-10 Grad ({q}); Pano-Ausschnitt {90 * k} Grad zur Peilung (Peilung = Bildmitte, ANNAHME), Hoehe/Nick ANNAHME"))
        else:
            f = 0.5 * W / math.tan(math.radians(par["hfov_deg"] / 2)); out.append(dict(id=e["id"], quelle="mapillary", seite_hint=e["seite"], pose=pose_blick(C, d, f, W, H), bild=e["datei"],
                                                                                         pose_guete=f"grob: GPS +-3 m, Peilung +-10 Grad ({q}); Hoehe {par['augenhoehe_m']} m, Nick 0, hfov {par['hfov_deg']} Grad = ANNAHME"))
    return out


def pano_ausschnitt(im, dyaw_deg, hfov, W, H):
    """Gleichwinkel-Panorama -> Ausschnitt (Nick 0). Bildmitte des Panoramas = Peilung."""
    Hp, Wp = im.shape[:2]; f = 0.5 * W / math.tan(math.radians(hfov / 2)); xs, ys = np.meshgrid(np.arange(W) - W / 2, np.arange(H) - H / 2)
    lon = np.arctan2(xs, f) + math.radians(dyaw_deg); lat = np.arctan2(-ys, np.hypot(xs, f)); mapx = ((lon / (2 * math.pi)) % 1.0 * Wp).astype(np.float32); mapy = ((0.5 - lat / math.pi) * Hp).astype(np.float32)
    return cv2.remap(im, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def frames_extrahieren(video, aus, fenster=None, abstand_s=0.3, max_n=40, laplace_min=60.0, breite=1280):
    """Kandidaten-Frames: im Fenster (s) scharfe Frames (Varianz des Laplace >= laplace_min, ANNAHME) mit Mindestabstand abstand_s (Spec 3); bei mehr als max_n gleichmaessig ausgeduennt.
    Schreibt <aus>/<sekunde>.jpg (Breite `breite`). Rueckgabe Liste der Pfade."""
    os.makedirs(aus, exist_ok=True); cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; dauer = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    ts = []
    for lo, hi in (fenster or [[0, dauer]]):
        t = float(lo)
        while t <= min(float(hi), dauer): ts.append(t); t += abstand_s
    if len(ts) > max_n * 4: ts = ts[::int(math.ceil(len(ts) / (max_n * 4)))]
    out = []
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, im = cap.read()
        if not ok: continue
        if cv2.Laplacian(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var() < laplace_min: continue
        if im.shape[1] > breite: im = cv2.resize(im, (breite, int(im.shape[0] * breite / im.shape[1])), interpolation=cv2.INTER_AREA)
        out.append((t, im))
    if len(out) > max_n: out = [out[i] for i in np.linspace(0, len(out) - 1, max_n).astype(int)]
    pf = []
    for t, im in out: p = os.path.join(aus, f"{t:08.2f}.jpg"); cv2.imwrite(p, im, [cv2.IMWRITE_JPEG_QUALITY, 90]); pf.append(p)
    cap.release(); return pf


def seite_der_kamera(C):
    return seite_aus_normale(np.array([C[0], C[1], 0.0]))


class Referenzen:
    """Bis zu `je_seite` Referenzfotos je Seite (aus den Kamerastandorten), SIFT auf dem Foto und je Merkmal ein 3D-Punkt (Strahl durch die Referenzkamera auf das Modell)."""
    def __init__(self, cams, bilddir, verd, je_seite=20, kante=1000, log=print):
        self.sift = cv2.SIFT_create(4000); self.R = []; per = {}
        for nr, c in sorted(cams.items()):
            if c["quelle"] != "sfm" and c["quelle"] != "K": continue
            per.setdefault(seite_der_kamera(zentrum(c)), []).append(nr)
        for s, L in per.items():
            step = max(1, len(L) // je_seite)
            for nr in L[::step][:je_seite]:
                p = next((q for q in (os.path.join(bilddir, f"{nr}.jpg"),) if os.path.exists(q)), None)
                if not p: continue
                im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                if im is None: continue
                c = cams[nr]; sx = c["W"] / im.shape[1]; sy = c["H"] / im.shape[0]
                f = kante / max(im.shape); im2 = cv2.resize(im, None, fx=min(1, f), fy=min(1, f), interpolation=cv2.INTER_AREA); k, d = self.sift.detectAndCompute(im2, None)
                if d is None or len(k) < 50: continue
                xy = np.float32([q.pt for q in k]) / min(1, f)                                               # Pixel des gespeicherten Bildes
                Pw = self.punkte3d(c, xy[:, 0] * sx, xy[:, 1] * sy, verd)
                ok = np.isfinite(Pw[:, 0]); self.R.append(dict(nr=nr, seite=s, xy=xy[ok], d=d[ok], P=Pw[ok]))
        log(f"Referenzen: {len(self.R)} Fotos ({', '.join(f'{s} {sum(1 for r in self.R if r['seite'] == s)}' for s in per)})")

    @staticmethod
    def punkte3d(c, u, v, verd):
        d = np.stack([(u - c["cx"]) / c["f"], (v - c["cy"]) / c["f"], np.ones_like(u)], 1); dw = d @ c["R"]; dw /= np.linalg.norm(dw, axis=1, keepdims=True); C = zentrum(c)
        loc, ri, _ = verd.rmi.intersects_location(np.repeat(C[None], len(u), 0), dw, multiple_hits=False); P = np.full((len(u), 3), np.nan); P[ri] = loc; return P


def pose_aus_bild(bild, refs, par, kante=1000, f_faktoren=(0.7, 1.0, 1.4)):
    """SIFT (OpenCV) gegen alle Referenzen (Lowe 0,75 + Fundamentalmatrix-RANSAC), PnP-RANSAC ueber alle Treffer. Rueckgabe dict(pose, inlier, refs) oder dict(grund)."""
    g = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY) if bild.ndim == 3 else bild; Hb, Wb = g.shape; f0 = kante / max(g.shape); g2 = cv2.resize(g, None, fx=min(1, f0), fy=min(1, f0), interpolation=cv2.INTER_AREA)
    k, d = refs.sift.detectAndCompute(g2, None)
    if d is None or len(k) < 50: return dict(grund="zu wenige Merkmale")
    xy = np.float32([q.pt for q in k]) / min(1, f0); bf = cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=64)); A, B3, Z = [], [], []; treff = []
    for r in refs.R:
        mm = bf.knnMatch(d, r["d"], k=2); g_ = [m for m, n in (x for x in mm if len(x) == 2) if m.distance < 0.75 * n.distance]
        if len(g_) < 20: continue
        a = xy[[m.queryIdx for m in g_]]; b = r["xy"][[m.trainIdx for m in g_]]; F, msk = cv2.findFundamentalMat(a, b, cv2.FM_RANSAC, 3.0, 0.999)
        if msk is None: continue
        msk = msk.ravel().astype(bool)
        if msk.sum() < 15: continue
        treff.append((r["nr"], int(msk.sum()))); A.append(a[msk]); B3.append(r["P"][[m.trainIdx for m in g_]][msk])
    if not A: return dict(grund="kein Referenzfoto mit >= 15 Inlier (Fundamentalmatrix) - Objekt nicht im Bild oder Ansicht zu fern")
    A = np.concatenate(A).astype(np.float64); P3 = np.concatenate(B3).astype(np.float64); best = None
    for ff in f_faktoren:
        f = ff * 0.5 * Wb / math.tan(math.radians(par["hfov_deg"] / 2)); K = np.array([[f, 0, Wb / 2], [0, f, Hb / 2], [0, 0, 1.0]])
        ok, rv, tv, inl = cv2.solvePnPRansac(P3, A, K, None, iterationsCount=2000, reprojectionError=8.0, confidence=0.999, flags=cv2.SOLVEPNP_EPNP)
        if ok and inl is not None and (best is None or len(inl) > best[0]): best = (len(inl), f, rv, tv, inl)
    if best is None or best[0] < par["min_inlier"]: return dict(grund=f"nicht verortbar: PnP {0 if best is None else best[0]} Inlier < {par['min_inlier']} (ANNAHME Spec 2)", refs=sorted(treff, key=lambda x: -x[1])[:5])
    n_i, f, rv, tv, inl = best; K = np.array([[f, 0, Wb / 2], [0, f, Hb / 2], [0, 0, 1.0]])
    rv, tv = cv2.solvePnPRefineLM(P3[inl[:, 0]], A[inl[:, 0]], K, None, rv, tv); R, _ = cv2.Rodrigues(rv)
    return dict(pose=dict(R=R, t=tv.ravel(), f=float(f), cx=Wb / 2, cy=Hb / 2, W=Wb, H=Hb), inlier=int(n_i), refs=sorted(treff, key=lambda x: -x[1])[:5], punkte=int(len(P3)))


# ------------------------------------------------------------------ Kandidaten bewerten und auswaehlen
def kand_pose(k):
    p = k["pose"]; return dict(R=np.array(p["R"], float), t=np.array(p["t"], float), f=float(p["f"]), cx=float(p["cx"]), cy=float(p["cy"]), W=int(p["W"]), H=int(p["H"]))


def pose_json(p): return dict(R=np.asarray(p["R"]).tolist(), t=np.asarray(p["t"]).tolist(), f=p["f"], cx=p["cx"], cy=p["cy"], W=p["W"], H=p["H"])


def bewerten(S, cams, V, kands, par, log=print):
    """Rueckgabe (kandidaten mit wert/neu_m2/seite/grund, auswahl). Kandidaten ohne Pose (grund) bekommen Wert 0. Gierig mit Aktualisierung (lazy), Abbruch min_wert/max_bilder."""
    nk, Vis, namen = n_kam_berechnen(S, cams, V, par, log); nk0 = nk.copy(); Cs = np.array([zentrum(cams[n]) for n in namen]); t0 = time.time()
    for k in kands:
        if k.get("pose") is None: k.setdefault("wert", 0.0); k["neu_m2"] = 0.0; k["seite"] = k.get("seite_hint"); continue
        cam = kand_pose(k); s = sicht(cam, S, V, par); k["_idx"] = np.flatnonzero(s); k["_C"] = zentrum(cam); k["_cam"] = cam
    log(f"Sicht {len(kands)} Kandidaten: {time.time() - t0:.0f} s")

    def wert(k, nkc, Viscur, Ccur):
        idx = k["_idx"]
        if len(idx) == 0: return 0.0, 0.0, {}
        b = bedarf_zellen(S, nkc, par, idx); bf = basisfaktor(k["_cam"], S, idx, nkc, Viscur, Ccur, par); w = b * bf; neu = float(S.A[idx][nkc[idx] < par["n_ziel"]].sum())
        je = {s_: float(w[S.seite[idx] == s_].sum()) for s_ in SEITEN}; return float(w.sum()), neu, je
    for k in kands:
        if "_idx" in k: k["wert"], k["neu_m2"], je = wert(k, nk, Vis, Cs); k["wert_je_seite"] = {a: round(b, 3) for a, b in je.items()}; k["seite"] = max(je, key=je.get) if je and k["wert"] > 0 else k.get("seite_hint")
        k["wert_vorher"] = k["wert"]
        if k["wert"] <= 0 and "grund" not in k:
            k["grund"] = ("sieht keine Flaeche gueltig (im Bild/Einfallswinkel/Aufloesung/verdeckt)" if len(k.get("_idx", [])) == 0 else "sieht nur Zellen ohne Bedarf (n_kam >= 3, kein Fehlercluster)")
    gewaehlt = []; rest = [k for k in kands if "_idx" in k and k["wert"] > 0]; Visc = Vis.copy(); Cc = Cs.copy(); nkc = nk.copy(); heap_wert = {k["id"]: k["wert"] for k in rest}
    while rest and len(gewaehlt) < par["max_bilder"]:
        rest.sort(key=lambda k: -heap_wert[k["id"]]); top = rest[0]; w, neu, je = wert(top, nkc, Visc, Cc)
        if w < heap_wert[top["id"]] - 1e-12: heap_wert[top["id"]] = w; continue                              # veraltet: neu einsortieren (lazy greedy)
        if w < par["min_wert_m2"]: break
        top["wert_bei_auswahl"] = round(w, 3); top["neu_m2_bei_auswahl"] = round(neu, 3); gewaehlt.append(top["id"]); rest.pop(0)
        nkc[top["_idx"]] += 1; Visc = np.vstack([Visc, np.isin(np.arange(S.N), top["_idx"])[None]]); Cc = np.vstack([Cc, top["_C"][None]])
    for k in kands:
        if k["id"] in gewaehlt: k["status"] = "gewaehlt"
        else:
            k["status"] = "verworfen"
            if "grund" not in k: k["grund"] = f"Restwert {heap_wert.get(k['id'], 0):.3f} m2 < min_wert {par['min_wert_m2']} bzw. Bedarf von frueher gewaehlten Bildern gedeckt" if k.get("wert", 0) > 0 else "Wert 0"
    return kands, gewaehlt, nk0, nkc


def bildblatt(S, kands, pfad, par, n=16, spalten=4, breite=420):
    """Die n wertvollsten Kandidaten: Bild (Pano-Ausschnitt/Frame) mit projizierten Bedarfszellen (Farbe = Seite), Kopf mit Wert."""
    top = sorted([k for k in kands if k.get("wert", 0) > 0 and k.get("bild") and os.path.exists(k["bild"])], key=lambda k: -k["wert"])[:n]; tafeln = []
    for k in top:
        im = cv2.imread(k["bild"]); cam = k["_cam"]; sc = breite / im.shape[1]; im = cv2.resize(im, None, fx=sc, fy=sc)
        if (cam["W"], cam["H"]) != (im.shape[1] / sc, im.shape[0] / sc) and abs(cam["W"] / im.shape[1] * sc - 1) > 0.02: pass
        idx = k["_idx"]; P = S.P[idx]; pc = P @ cam["R"].T + cam["t"]; u = (cam["f"] * pc[:, 0] / pc[:, 2] + cam["cx"]) * im.shape[1] / cam["W"]; v = (cam["f"] * pc[:, 1] / pc[:, 2] + cam["cy"]) * im.shape[0] / cam["H"]
        b = bedarf_zellen(S, k["_nk_eval"], par, idx) if "_nk_eval" in k else None
        for j in range(len(idx)):
            col = FARBE[S.seite[idx[j]]]; cv2.circle(im, (int(u[j]), int(v[j])), 1, col, -1)
        cv2.rectangle(im, (0, 0), (im.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(im, f"{k['id'][:22]} {k['quelle']}", (3, 12), 0, 0.38, (255, 255, 255), 1); cv2.putText(im, f"wert {k['wert']:.2f} m2 neu {k['neu_m2']:.1f} m2 {k.get('seite')} [{k.get('status', '')}]", (3, 25), 0, 0.38, (0, 255, 255), 1)
        tafeln.append(cv2.resize(im, (breite, int(breite * 0.75))) if im.shape[0] != int(breite * 0.75) else im)
    if not tafeln: return None
    h = max(t.shape[0] for t in tafeln); tafeln = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tafeln]
    while len(tafeln) % spalten: tafeln.append(np.zeros_like(tafeln[0]))
    bl = cv2.vconcat([cv2.hconcat(tafeln[i:i + spalten]) for i in range(0, len(tafeln), spalten)]); cv2.imwrite(pfad, bl, [cv2.IMWRITE_JPEG_QUALITY, 85]); return pfad


def nachher(S, V, cams_vorher, auswahl, neue, par, log=print):
    """Tatsaechlich neue Zellen je gewaehltem Bild: Zellen mit n_kam vorher < 3, die mit den registrierten Posen der gewaehlten Bilder nachher >= 3 erreichen.
    Je Bild der eigene Beitrag (Zellen, die es sieht und die ohne es unter 3 blieben, gezaehlt je Reihenfolge der Auswahl). Rueckgabe Tabelle + Faktor."""
    nk, Vis, namen = n_kam_berechnen(S, cams_vorher, V, par, log); nk_v = nk.copy(); cur = nk.copy(); res = []; Pv = 0.0; Ta = 0.0
    for e in auswahl["gewaehlt"]:
        if e["id"] not in neue: res.append(dict(id=e["id"], vorhergesagt_m2=e.get("neu_m2_bei_auswahl"), tatsaechlich_m2=None, grund="nicht registriert (keine Pose im Nachher)")); continue
        s = sicht(kand_pose(dict(pose=neue[e["id"]])), S, V, par); neu_z = s & (cur < par["n_ziel"]) & (cur + 1 >= par["n_ziel"]); cur[s] += 1
        tat = float(S.A[neu_z].sum()); res.append(dict(id=e["id"], vorhergesagt_m2=e.get("neu_m2_bei_auswahl"), tatsaechlich_m2=round(tat, 3), ohne_gewinn=tat <= 0)); Pv += e.get("neu_m2_bei_auswahl") or 0; Ta += tat
    je = {}
    for s_ in SEITEN:
        m = S.seite == s_
        if m.any(): je[s_] = dict(vorher=round(float((nk_v[m] >= par["n_ziel"]).mean()), 4), nachher=round(float((cur[m] >= par["n_ziel"]).mean()), 4))
    return dict(je_bild=res, summe_vorhergesagt_m2=round(Pv, 3), summe_tatsaechlich_m2=round(Ta, 3), kalibrierfaktor=round(Ta / Pv, 3) if Pv > 0 else None, anteil_nk_ge3_je_seite=je,
                ohne_gewinn=[r["id"] for r in res if r.get("ohne_gewinn")]), cur


# ------------------------------------------------------------------ Einbau-Funktion fuer nullstart / Video-Stufe
def frames_auswaehlen(objp, kandidaten_json, aus, par=None, restfeld=None, fk=None, stl=None, log=print):
    """Aufrufstelle fuer nullstart (Schritt `bilder` vor `netz`, Video-Stufe `--videos`): liest eine Kandidatenliste (poses_*-Ausgabe) und gibt die ids der gewaehlten Bilder zurueck;
    SfM bekommt NUR diese. (Noch nicht in nullstart.py eingebaut - siehe Register CQ.)"""
    par = dict(standard_parameter(), **(par or {})); obj = json.load(open(objp)); cams, _ = kameras_laden(objp, obj)
    S = szene_aus_restfeld(restfeld, fk, par); V = Verdecker(stl, obj["stl_massstab"], obj); kands = json.load(open(kandidaten_json))
    for k in kands:
        if k.get("pose"): k["pose"] = {a: (np.array(b) if a in ("R", "t") else b) for a, b in k["pose"].items()}
    kands, gew, _, _ = bewerten(S, cams, V, kands, par, log); os.makedirs(aus, exist_ok=True)
    json.dump(dict(gewaehlt=[dict(id=k["id"], wert=k.get("wert_bei_auswahl"), neu_m2_bei_auswahl=k.get("neu_m2_bei_auswahl"), seite=k.get("seite")) for k in kands if k["id"] in gew]), open(os.path.join(aus, "auswahl.json"), "w"), indent=1)
    return gew


# ------------------------------------------------------------------ Hauptprogramm
def _arg_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("objekt")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bedarf", action="store_true"); g.add_argument("--poses-mapillary"); g.add_argument("--poses-frames"); g.add_argument("--bewerten"); g.add_argument("--nachher", nargs=2, metavar=("AUSWAHL", "NEUE_POSEN"))
    ap.add_argument("--aus", required=True); ap.add_argument("--restfeld", default="/media/oem/scan/rc-park_null/s3_phase_a/restfeld_v1"); ap.add_argument("--fehlerkarte", default="/media/oem/scan/rc-park_null/s3_phase_a/lauf_d/fehlerkarte_k0")
    ap.add_argument("--stl", help="Standard: restfeld.json parameter.stl, sonst objekt.json stl"); ap.add_argument("--kameras", help="kameras_unverzerrt.json (Standard: sfm/dicht_*/ des Objekts)"); ap.add_argument("--ohne-fehlerkarte", action="store_true", help="Flaechen aus STL-Oberflaechenproben (kein Restfeld/Fehlerterm), z. B. Martinstor")
    ap.add_argument("--bilder-dir", help="Bilder der Referenzkameras (poses-frames; Standard sfm/dicht_*/images)"); ap.add_argument("--je-seite", type=int, default=20)
    ap.add_argument("--max-frames", type=int, default=60); ap.add_argument("--frame-abstand-s", type=float, default=0.3)
    for k, v in standard_parameter().items():
        if isinstance(v, bool): ap.add_argument("--" + k.replace("_", "-"), type=lambda s: s.lower() in ("1", "true", "ja"), default=v)
        else: ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v, help="ANNAHME-Schwelle (Standard %s)" % v)
    return ap


def main(argv=None):
    a = _arg_parser().parse_args(argv); par = {k: getattr(a, k) for k in standard_parameter()}; objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); os.makedirs(a.aus, exist_ok=True)
    stl = a.stl
    if not stl:
        rp = os.path.join(a.restfeld, "restfeld.json")
        stl = json.load(open(rp))["parameter"]["stl"] if (os.path.exists(rp) and not a.ohne_fehlerkarte) else os.path.join(ROOT, obj["stl"])
    cams, info = kameras_laden(objp, obj, a.kameras); print(f"Kameras: {len(cams)} ({info})")
    if a.poses_mapillary:
        k = poses_mapillary(objp, obj, a.poses_mapillary, par, os.path.join(a.aus, "pano")); [x.update(pose=pose_json(x["pose"])) for x in k if x.get("pose")]
        json.dump(k, open(os.path.join(a.aus, "kandidaten_mapillary.json"), "w"), indent=1); print(len(k), "Kandidaten ->", os.path.join(a.aus, "kandidaten_mapillary.json")); return
    V = Verdecker(stl, obj["stl_massstab"], obj); print('Nachbarn als Verdecker:', V.n_nachbarn, getattr(V, 'nachbar_fehler', ''))
    if a.poses_frames:
        bd = a.bilder_dir or next(iter(glob.glob(os.path.join(os.path.dirname(objp), "sfm", "dicht_*", "images"))))
        refs = Referenzen(cams, bd, V, a.je_seite); out = []
        for p in sorted(glob.glob(os.path.join(a.poses_frames, "**", "*.jpg"), recursive=True))[:a.max_frames]:
            im = cv2.imread(p); r = pose_aus_bild(im, refs, par) if im is not None else dict(grund="Bild nicht lesbar"); e = dict(id=os.path.relpath(p, a.poses_frames).replace(os.sep, "/"), quelle="frame", bild=p)
            if "pose" in r: e.update(pose=pose_json(r["pose"]), inlier=r["inlier"], refs=r["refs"], pose_guete=f"PnP {r['inlier']} Inlier (Modelloberflaeche als 3D, ANNAHME)")
            else: e.update(wert=0.0, grund=r["grund"], refs=r.get("refs"))
            out.append(e); print(e["id"], e.get("inlier"), e.get("grund", ""), flush=True)
        json.dump(out, open(os.path.join(a.aus, "kandidaten_frames.json"), "w"), indent=1); return
    if a.ohne_fehlerkarte or not os.path.exists(os.path.join(a.restfeld, "restfeld.json")): S = szene_aus_stl(stl, obj["stl_massstab"], par)
    else: S = szene_aus_restfeld(a.restfeld, a.fehlerkarte, par)
    print(f"Szene: {S.N} Grobzellen, {len(S.fl)} Flaechen, Abdeckungsflaeche {S.A.sum():.1f} m2, Fehlerflaeche {S.Ferr.sum():.2f} m2")
    if a.bedarf:
        nk, Vis, namen = n_kam_berechnen(S, cams, V, par); T = bedarf_tabelle(S, nk, par); bedarf_bilder(S, nk, par, a.aus)
        json.dump(dict(parameter=par, kameras=info, n_kameras=len(cams), tabelle=T, namen=namen, restfeld=a.restfeld, stl=stl), open(os.path.join(a.aus, "bedarf.json"), "w"), indent=1, ensure_ascii=False)
        np.savez_compressed(os.path.join(a.aus, "n_kam.npz"), n_kam=nk, vis=Vis, namen=np.array(namen)); print(f"{'Seite':6s} {'Flaeche':>8s} {'n_kam>=3':>9s} {'Bedarf Abd':>11s} {'Bedarf Fehl':>12s} {'Bedarf':>8s}")
        for s in SEITEN: t = T[s]; print(f"{s:6s} {str(t['flaeche_m2']):>8s} {str(t['anteil_nk_ge3']):>9s} {t['bedarf_abdeckung_m2']:11.2f} {t['bedarf_fehler_m2']:12.2f} {t['bedarf_m2']:8.2f}")
        print("groesster Bedarf:", max(SEITEN, key=lambda s: T[s]["bedarf_m2"])); return
    if a.bewerten:
        k = json.load(open(a.bewerten))
        for x in k:
            if x.get("pose"): x["pose"] = {u: (np.array(v) if u in ("R", "t") else v) for u, v in x["pose"].items()}
        k, gew, nk0, nk1 = bewerten(S, cams, V, k, par); k.sort(key=lambda x: -x.get("wert", 0))
        pj = [{u: v for u, v in x.items() if not u.startswith("_") and u != "pose"} | ({"pose": pose_json(x["pose"])} if x.get("pose") else {}) for x in k]
        json.dump(dict(parameter=par, gewaehlt=[dict(id=x["id"], wert=x.get("wert_bei_auswahl"), neu_m2_bei_auswahl=x.get("neu_m2_bei_auswahl"), seite=x.get("seite")) for x in k if x["id"] in gew], kandidaten=pj,
                       anteil_nk_ge3_vorher={s: round(float((nk0[S.seite == s] >= par["n_ziel"]).mean()), 4) for s in SEITEN if (S.seite == s).any()},
                       anteil_nk_ge3_nach_auswahl={s: round(float((nk1[S.seite == s] >= par["n_ziel"]).mean()), 4) for s in SEITEN if (S.seite == s).any()}), open(os.path.join(a.aus, "auswahl.json"), "w"), indent=1, ensure_ascii=False)
        bl = bildblatt(S, k, os.path.join(a.aus, "bildblatt_top16.jpg"), par); print("gewaehlt:", len(gew), "von", len(k), "Bildblatt:", bl)
        for x in k[:16]: print(f"{x['id'][:30]:30s} {x['quelle']:14s} wert {x.get('wert', 0):7.2f} neu {x.get('neu_m2', 0):6.1f} m2 {str(x.get('seite')):5s} {x['status']:10s} {x.get('grund', '')}")
        return
    if a.nachher:
        aw = json.load(open(a.nachher[0])); nz = {k: {u: (np.array(v) if u in ("R", "t") else v) for u, v in p.items()} for k, p in json.load(open(a.nachher[1])).items()}
        R, _ = nachher(S, V, cams, aw, nz, par); json.dump(R, open(os.path.join(a.aus, "nachher.json"), "w"), indent=1); print(json.dumps({k: v for k, v in R.items() if k != "je_bild"}, indent=1))


if __name__ == "__main__":
    main()
