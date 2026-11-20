#!/usr/bin/env python3
"""beweis_ansatz.py - Vergleichslauf "Welcher Ansatz ist bei unserer Datenlage der beste?" (modelle/archiv/SPEC_BEWEIS_ANSATZ.md, 2026-11-06).

Verfahren je Objekt, gleiche Eingaben, gleiche Metriken, alles skriptiert (Handarbeit = 0):
  A Photogrammetrie : dichte Wolke (fused.ply + Ausrichtung -> Modellrahmen) -> Normalen schaetzen -> Poisson (Open3D, venv-mesh) -> groesste Komponente
                      -> wasserdicht (fill_holes, pymeshfix, sonst Voxel) -> STL 1:massstab im Rahmen des Objekts
  B amtlich         : Kaufhaus = Ausgangsmodell des Laeufers (qualitaetsstufen.v_ausgang, nur LoD2/DOM1/DGM1, keine Fotoparameter);
                      Martinstor / synthetisch = DOM1-Hoehenfeld (1-m-Zellen, Maxima) extrudiert (der Generator hat keinen "nur amtlich"-Modus)
  C Modell+Restfeld : bester uebernommener Laeuferstand (Kaufhaus) bzw. Objekt-STL (Martinstor); synthetisch: Generator Standardparameter + param_suche
Metriken: 1 Geometrie gegen Wahrheit (nur synthetisch) | 2 zurueckgehaltene Fotos (foto_diff --mehrstufig rot/gelb) | 3 Dach gegen DOM1 |
          4 Zaehlmerkmale (Pruefstand merkmal anzahl) | 5 Druckbarkeit | 6 Aufwand.
Kein Nachjustieren: Metriken und Kriterium stehen in der Spezifikation; Ergebnisse gehen unveraendert in <aus>/ergebnisse.json.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/beweis_ansatz.py modelle/<objekt>/objekt.json [--verfahren A|B|C|alle] [--synthetisch] [--aus DIR] [--schritte a,b,..]
Schritte: bauen (A,B,C-STL), fotos (Auswahl), foto_diff (Metrik 2), dach (3), zaehl (4), druck (5), blatt (Bildblatt)
Hilfsmodus (venv-mesh): --helfer-poisson in.npz out.ply depth maxtri
"""
import os, sys, json, time, argparse, subprocess, glob, shutil
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
PYSEG = "/media/oem/scan/venv-seg/bin/python"; PYMESH = "/media/oem/scan/venv-mesh/bin/python"
BASIS = "/media/oem/scan/rc-park_null/beweis_ansatz"
STAND_KH = "/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6/stand.json"


# ------------------------------------------------------------------ Hilfsmodus Poisson (Open3D, venv-mesh)
def helfer_poisson(a):
    import open3d as o3d
    d = np.load(a[0]); P, Nr = d["P"], d["N"]; depth = int(a[2]); maxtri = int(a[3])
    pc = o3d.geometry.PointCloud(); pc.points = o3d.utility.Vector3dVector(P)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=40))               # Normalen GESCHAETZT (Open3D); Vorzeichen nur nach COLMAP-Sichtrichtung
    n = np.asarray(pc.normals); s = np.sign((n * Nr).sum(1)); s[s == 0] = 1; pc.normals = o3d.utility.Vector3dVector(n * s[:, None])
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pc, depth=depth, scale=1.1, linear_fit=False)
    dens = np.asarray(dens); mesh.remove_vertices_by_mask(dens < np.quantile(dens, 0.02))          # Dichte-Trimmen 2 %
    cl, nt, ar = mesh.cluster_connected_triangles(); cl = np.asarray(cl); k = int(np.argmax(np.asarray(ar)))
    mesh.remove_triangles_by_mask(cl != k); mesh.remove_unreferenced_vertices()
    n0 = len(mesh.triangles)
    if n0 > maxtri: mesh = mesh.simplify_quadric_decimation(maxtri)
    o3d.io.write_triangle_mesh(a[1], mesh)
    print(json.dumps(dict(punkte=len(P), dreiecke_poisson=n0, dreiecke_nach=len(mesh.triangles), tiefe=depth, komponenten=int(len(np.asarray(nt))))))


# ------------------------------------------------------------------ Konfiguration je Objekt
def konfig(objp, aus):
    od = os.path.dirname(os.path.abspath(objp)); obj = json.load(open(objp)); name = os.path.basename(od)
    k = dict(name=name, objp=os.path.abspath(objp), obj=obj, od=od, massstab=float(obj.get("stl_massstab", 87)), fd_objp=os.path.abspath(objp), pruef_objp=os.path.abspath(objp))
    if name.startswith("kaufhaus"):
        fr = obj["freiraum"]; k["dicht"] = fr["dicht"]; k["ausr"] = os.path.join(od, fr["ausrichtung"]); st = json.load(open(STAND_KH))
        k["stl_B"] = st["stufen"][0]["stl"]; k["stl_C"] = [s["stl"] for s in st["stufen"] if s.get("stl")][-1]
        k["benutzt"] = sorted({nr for s in st["stufen"] for nr in (s.get("je_foto") or {})}); k["benutzt_quelle"] = STAND_KH + " (je_foto aller Stufen)"
        k["B_art"] = "Ausgangsmodell des Laeufers (modell_s1.stl, qualitaetsstufen.v_ausgang)"; k["C_art"] = "letzter uebernommener Laeuferstand modell_s3_v9.stl (Stufe 3)"
        k["min_kameras"] = 3
    elif name.startswith("martinstor"):
        ld = os.path.join(ROOT, "modelle", "martinstor_lod2"); k.update(
            dicht=os.path.join("/media/oem/scan/rc-park_null/martinstor_lod2/sfm/dicht_nord"), ausr=os.path.join(ld, "messprotokoll", "SFM-AUSRICHTUNG-buendel.json"),
            stl_C=os.path.join(ROOT, obj["stl"]), stl_B=None, fd_objp=os.path.join(ld, "objekt.json"), fd_od=ld, min_kameras=3, rms_max=1.5,
            B_art="DOM1-Hoehenfeld (1-m-Zellen) extrudiert; der Martinstor-Generator kennt keinen Modus 'nur amtlich' (LoD2 enthaelt nur den Torbau, nicht den Turm)",
            C_art="Objekt-STL modelle/stl/martinstor_v4_1-87.stl (Handparametrierung aus Fotos/Laser)")
        k["benutzt"], k["benutzt_quelle"] = martinstor_benutzt(od), "Foto-Nummern in modelle/martinstor/messprotokoll/*, masstabelle/masse/fassade/objekt/profile_generator/elemente.json (Regex, Heuristik)"
    return k


def martinstor_benutzt(od):
    import re
    ids = set()
    for p in glob.glob(os.path.join(od, "messprotokoll", "*.json")):
        m = re.match(r"(?:[A-Z]+|lupe)-(\d{3})", os.path.basename(p))
        if m: ids.add(m.group(1))
    for f in ("masstabelle.json", "masse.json", "fassade.json", "objekt.json", "profile_generator.json", "elemente.json"):
        t = open(os.path.join(od, f)).read()
        for m in re.finditer(r"(?:Fotos?|Foto-?|K-|M-|Z-|V-|E-)\s*(\d{3})(?:[/ ,und]+(\d{3}))*", t): ids.update(re.findall(r"\d{3}", m.group(0)))
    return sorted(ids)


def foto_auswahl(k, n=6):
    """Zurueckgehaltene Fotos: kalibriert (Kamera-Tor wie param_suche.fotos_waehlen), NICHT in k['benutzt'], keine Nachtfotos, gleichmaessig ueber die Nummern."""
    od = k["fd_od"] if k.get("fd_od") else k["od"]; nacht = set()
    sp = os.path.join(od, "sonne.json")
    if os.path.exists(sp): nacht = {a for a, v in json.load(open(sp))["fotos"].items() if v["urteil"] == "Nacht"}
    ok = []
    for p in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        kk = json.load(open(p)).get("kamera", {}); nr = os.path.basename(p)[2:-5]
        gut = kk and ((kk.get("buendel_tor") or {}).get("ok") or (kk.get("lod2_tor") or {}).get("ok") or kk.get("brennweite_quelle") not in (None, "buendel"))
        if k.get("rms_max") and kk: gut = kk.get("rms_px") is not None and kk["rms_px"] <= k["rms_max"]      # lod2-Kette (Buendel mit LoD2-Flaeche): kein buendel_tor-Feld, Qualitaet = Reprojektionsfehler
        if gut and nr not in k["benutzt"] and nr not in nacht: ok.append(nr)
    if len(ok) <= n: return ok, ok
    return [ok[int(round(i))] for i in np.linspace(0, len(ok) - 1, n)], ok


# ------------------------------------------------------------------ Verfahren
def wolke_modellrahmen(dicht, ausr, min_kameras):
    import cv2; sys.path.insert(0, HERE)
    from freiraum_pruefen import ply_lesen, vis_lesen
    tr = json.load(open(ausr))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    X = ((ply_lesen(os.path.join(dicht, "fused.ply")) - ta) @ Ra) / s
    # Normalen (COLMAP, nur fuer das Vorzeichen) lesen: Spalten nx ny nz nach x y z
    with open(os.path.join(dicht, "fused.ply"), "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    N = np.c_[arr["nx"], arr["ny"], arr["nz"]].astype(float) @ Ra
    pi, _ = vis_lesen(os.path.join(dicht, "fused.ply.vis")); nk = np.bincount(pi, minlength=len(X)); ok = nk >= min_kameras
    return X[ok], N[ok], int(len(X))


def stl_laden_m(stl, massstab):
    import trimesh
    m = trimesh.load(stl); m.apply_scale(massstab / 1000.0); return m


def mesh_schreiben_stl(m_m, massstab, pfad):
    mm = m_m.copy(); mm.apply_scale(1000.0 / massstab); mm.export(pfad)


def wasserdicht(m, voxel=0.05):
    """fill_holes -> pymeshfix -> Voxel-Neuvernetzung. Gibt (mesh, Schritt) zurueck."""
    import trimesh
    m = max(m.split(only_watertight=False), key=lambda c: len(c.faces)); m.merge_vertices(); m.remove_unreferenced_vertices()
    if m.is_watertight: return m, "von selbst"
    trimesh.repair.fill_holes(m)
    if m.is_watertight: return m, "fill_holes"
    try:
        import pymeshfix
        mf = pymeshfix.MeshFix(np.asarray(m.vertices, float), np.asarray(m.faces, np.int32)); mf.repair(); r = trimesh.Trimesh(np.asarray(mf.points), np.asarray(mf.faces).reshape(-1, 3))
        r = max(r.split(only_watertight=False), key=lambda c: len(c.faces))
        if r.is_watertight: return r, "pymeshfix"
    except Exception as e: print("  pymeshfix:", e)
    vg = m.voxelized(voxel).fill(); r = vg.marching_cubes; r.apply_transform(vg.transform)
    return r, f"Voxel {voxel} m"


def poisson_aus_punkten(P, N, lo, hi, rand, aus, massstab, tiefe=9, maxtri=300000, zusatz_z=(1.0, 3.0)):
    """Zuschnitt auf Quader [lo-rand, hi+rand] (xy) -> Open3D-Poisson (venv-mesh) -> wasserdicht -> STL 1:massstab. Gemeinsam fuer echte und synthetische Wolke."""
    import trimesh
    t0 = time.time()
    sel = (P[:, 0] > lo[0] - rand) & (P[:, 0] < hi[0] + rand) & (P[:, 1] > lo[1] - rand) & (P[:, 1] < hi[1] + rand) & (P[:, 2] > lo[2] - zusatz_z[0]) & (P[:, 2] < hi[2] + zusatz_z[1])
    np.savez_compressed(os.path.join(aus, "A_wolke_zuschnitt.npz"), P=P[sel], N=N[sel]); ply = os.path.join(aus, "A_poisson.ply")
    r_ = subprocess.run([PYMESH, "-I", os.path.abspath(__file__), "--helfer-poisson", os.path.join(aus, "A_wolke_zuschnitt.npz"), ply, str(tiefe), str(maxtri)], capture_output=True, text=True)
    if r_.returncode != 0: raise SystemExit("Poisson fehlgeschlagen: " + (r_.stderr or r_.stdout)[-800:])
    info = json.loads(r_.stdout.strip().splitlines()[-1])
    m = trimesh.load(ply); m, wd = wasserdicht(m); stl = os.path.join(aus, "A_poisson_1-%d.stl" % massstab); mesh_schreiben_stl(m, massstab, stl)
    return dict(stl=stl, sekunden=round(time.time() - t0, 1), wolke_punkte_zuschnitt=int(sel.sum()), poisson=info, wasserdicht_ueber=wd,
                zuschnitt=dict(lo=(np.asarray(lo) - rand).round(1).tolist(), hi=(np.asarray(hi) + rand).round(1).tolist(), rand_m=rand))


def verfahren_A(k, aus, tiefe=9, maxtri=300000):
    t0 = time.time(); Cm = stl_laden_m(k["stl_C"], k["massstab"]); lo, hi = Cm.bounds
    X, N, nges = wolke_modellrahmen(k["dicht"], k["ausr"], k.get("min_kameras", 3))
    r = poisson_aus_punkten(X, N, lo, hi, float(k.get("zuschnitt_rand_m", 3.0)), aus, k["massstab"], tiefe, maxtri)
    r.update(wolke_punkte_gesamt=nges, min_kameras=k.get("min_kameras", 3), sekunden=round(time.time() - t0, 1)); return r


def dom1_laden(k):
    """DOM1 (80 x 80 m um die Rahmenmitte) aus der amtlichen GeoTIFF-Kachel wie wolke_dom1_pruefen.py -> (Z ueber Gelaende, lx, ly) im Modellrahmen."""
    from PIL import Image; sys.path.insert(0, HERE)
    import objekt_rahmen as OR
    obj = OR.ergaenzen(json.loads(json.dumps(k["obj"])), k["od"]); R = obj["rahmen"]; c0 = np.array(R["mitte_utm"], float); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    ek, nk = int(c0[0] // 1000), int(c0[1] // 1000); tif = sorted(glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/dom1_32_{ek}_{nk}_1_bw_*.tif", recursive=True))
    if not tif:
        tif = sorted(glob.glob(f"/media/oem/scan/tmp/**/dom1_32_{ek}_{nk}_1_bw_*.tif", recursive=True))
    if not tif: return None
    A = np.array(Image.open(tif[0])).astype(float); A[A < -100] = np.nan; tf = [float(x) for x in open(tif[0][:-4] + ".tfw")]; xc, yc = tf[4], tf[5]
    h = 40; cc, rr = int(round(c0[0] - xc)), int(round(yc - c0[1])); W = A[rr - h:rr + h, cc - h:cc + h]; n = W.shape[0]
    yy, xx = np.mgrid[:n, :n]; E = xc + cc - h + xx; Nn = yc - (rr - h) - yy
    lx = (E - c0[0]) * xh[0] + (Nn - c0[1]) * xh[1]; ly = (E - c0[0]) * yh[0] + (Nn - c0[1]) * yh[1]
    return dict(Z=W - R["gelaende"], lx=lx, ly=ly, E=E, N=Nn, c0=c0, xh=xh, yh=yh, quelle=os.path.basename(tif[0]), obj=obj)


def eigener_grundriss(k, D):
    """Maske der DOM1-Zellen im eigenen LoD2-Grundriss (Dachflaechen des Gebaeudes); ohne LoD2-Eintrag: Radius um die DOM1-Spitze (ANNAHME 12 m)."""
    Z = D["Z"]; obj = D["obj"]; c0, xh, yh = D["c0"], D["xh"], D["yh"]
    if obj.get("lod2") and obj["lod2"].get("id"):
        import lod2_gebaeude as LG; from matplotlib.path import Path
        eigen = np.zeros_like(Z, bool)
        for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=40):
            if meta["id"] != obj["lod2"]["id"]: continue
            for t, P in polys:
                if t != "RoofSurface": continue
                q = np.c_[(P[:, 0] - c0[0]) * xh[0] + (P[:, 1] - c0[1]) * xh[1], (P[:, 0] - c0[0]) * yh[0] + (P[:, 1] - c0[1]) * yh[1]]
                eigen |= Path(q).contains_points(np.c_[D["lx"].ravel(), D["ly"].ravel()]).reshape(Z.shape)
        return eigen, "LoD2-Dachflaechen " + obj["lod2"]["id"]
    pk = np.unravel_index(np.nanargmax(Z), Z.shape); return (np.hypot(D["lx"] - D["lx"][pk], D["ly"] - D["ly"][pk]) <= 12.0), "Radius 12 m um die DOM1-Spitze (ANNAHME)"


def dach_dom1(m_m, D, eigen, steil_grenze=2.5, punkte=2000000):
    """Metrik 3 (korrigiert 2026-11-05 nach Dachbeweis a40b): Hoehe des Netzes gegen DOM1 NUR auf Zellen, die das Netz ueberdeckt; Abdeckung getrennt.
    zellmax: Zellmaximum der Oberflaechenpunkte (DOM1 = Zellmaximum der Oberflaeche -> passende Rechnung); strahl: Strahl von oben auf die Zellmitte (Embree).
    alt_null_hoehe: fruehere Rechnung (Zellen ohne Netz = Hoehe 0), nur zum Vergleich."""
    import trimesh
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    Z = D["Z"]; gy, gx = np.gradient(np.where(np.isfinite(Z), Z, 0.0)); steil = np.hypot(gx, gy) > steil_grenze
    zellen = eigen & (Z > 3) & ~steil & np.isfinite(Z); n = Z.shape[0]; c0, xh, yh = D["c0"], D["xh"], D["yh"]
    P, _ = trimesh.sample.sample_surface(m_m, punkte, seed=1); P = np.asarray(P)
    Eu = c0[0] + P[:, 0] * xh[0] + P[:, 1] * yh[0]; Nu = c0[1] + P[:, 0] * xh[1] + P[:, 1] * yh[1]
    jj = np.floor(Eu - (D["E"][0, 0] - 0.5)).astype(int); ii = np.floor((D["N"][0, 0] + 0.5) - Nu).astype(int)
    ok = (ii >= 0) & (ii < n) & (jj >= 0) & (jj < n); H = np.full(n * n, -np.inf); np.maximum.at(H, ii[ok] * n + jj[ok], P[ok, 2]); H = H.reshape(n, n)
    def stat(Hm, treffer):
        t = zellen & treffer; d = (Hm - Z)[t]
        if not len(d): return dict(zellen_dach=int(zellen.sum()), zellen_getroffen=0, abdeckung=0.0)
        return dict(zellen_dach=int(zellen.sum()), zellen_getroffen=int(t.sum()), abdeckung=round(float(t.sum() / zellen.sum()), 3), median_abs_m=round(float(np.median(np.abs(d))), 3),
                    mittel_abs_m=round(float(np.mean(np.abs(d))), 3), bias_m=round(float(np.mean(d)), 3), rmse_m=round(float(np.sqrt(np.mean(d ** 2))), 3), anteil_ueber_1m=round(float(np.mean(np.abs(d) > 1.0)), 3))
    r = dict(zellmax=stat(H, np.isfinite(H)))
    # Strahl von oben auf die Zellmitte (Zellmitte im Modellrahmen aus D)
    zi, zj = np.where(zellen); org = np.c_[D["lx"][zi, zj], D["ly"][zi, zj], np.full(len(zi), float(m_m.bounds[1][2]) + 10.0)]
    loc, ri, _ = RayMeshIntersector(m_m).intersects_location(org, np.tile([0, 0, -1.0], (len(org), 1)), multiple_hits=False)
    Hs = np.full((n, n), -np.inf); 
    if len(ri):
        top = {}; 
        for q, l in zip(ri, loc): top[q] = max(top.get(q, -np.inf), l[2])
        for q, v in top.items(): Hs[zi[q], zj[q]] = v
    r["strahl"] = stat(Hs, np.isfinite(Hs))
    H0 = np.where(np.isfinite(H), H, 0.0); d0 = (H0 - Z)[zellen]
    r["alt_null_hoehe"] = dict(mittel_abs_m=round(float(np.mean(np.abs(d0))), 3), median_abs_m=round(float(np.median(np.abs(d0))), 3), bias_m=round(float(np.mean(d0)), 3))
    r["zellen"] = int(zellen.sum()); return r, H


def verfahren_B_dom(k, D, aus, hoehe_min=3.0):
    """B ohne Generator: DOM1-Zellen (> hoehe_min ueber Gelaende, eigener Grundriss) als Saeulen bis z=0 (Zellmaxima), Union -> wasserdicht -> STL."""
    import trimesh
    t0 = time.time(); eigen, art = eigener_grundriss(k, D); Z = D["Z"]; boxen = []
    for i, j in zip(*np.where(eigen & (Z > hoehe_min) & np.isfinite(Z))):
        b = trimesh.creation.box(extents=[1.0, 1.0, float(Z[i, j])]); T = np.eye(4); T[:3, 3] = [D["lx"][i, j], D["ly"][i, j], float(Z[i, j]) / 2]
        Rz = np.eye(4); ang = np.arctan2(D["xh"][1], D["xh"][0]); Rz[:2, :2] = [[np.cos(-ang), -np.sin(-ang)], [np.sin(-ang), np.cos(-ang)]]   # DOM1-Zellen liegen achsparallel in UTM, im Modellrahmen um -ang gedreht
        b.apply_transform(T @ Rz); boxen.append(b)
    m = trimesh.util.concatenate(boxen)
    from trimesh.boolean import union
    try: u = union(boxen, engine="manifold")
    except Exception: u = m
    stl = os.path.join(aus, "B_dom1_1-%d.stl" % k["massstab"]); mesh_schreiben_stl(u, k["massstab"], stl); wd = bool(trimesh.load(stl).is_watertight)   # nach dem STL-Rundlauf (Scheitel werden beim Laden verschweisst)
    return dict(stl=stl, sekunden=round(time.time() - t0, 1), art=art, saeulen=len(boxen), wasserdicht_roh=bool(wd))


def kopieren_C(k, aus, name):
    dst = os.path.join(aus, name); shutil.copy(k["stl_C"], dst); return dst


# ------------------------------------------------------------------ Metriken
def gpu_frei(max_min=30):
    t0 = time.time()
    while True:
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
        if not r: return True
        if time.time() - t0 > max_min * 60: return False
        time.sleep(60)


_CPU_FALLBACK = [False]                                                                           # nach 30 min Wartezeit einmal CPU, danach fuer alle weiteren Laeufe dieses Prozesses


def foto_diff_lauf(k, fotos, stl, aus, cpu, bilder=None, extra=()):
    cpu = cpu or _CPU_FALLBACK[0]; env = dict(os.environ, PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    if cpu: env.update(RENDER_CPU="1", CUDA_VISIBLE_DEVICES="")
    else:
        env["FD_GPU"] = "1"
        for x in ("RENDER_CPU", "PRUEF_CPU", "CUDA_VISIBLE_DEVICES"): env.pop(x, None)
    erg = {}
    for nr in fotos:
        if not cpu and not gpu_frei(30): print("  GPU belegt > 30 min: CPU-Fassung (RENDER_CPU=1 CUDA_VISIBLE_DEVICES=)", flush=True); cpu = True; _CPU_FALLBACK[0] = True; env.update(RENDER_CPU="1", CUDA_VISIBLE_DEVICES=""); env.pop("FD_GPU", None)
        a = os.path.join(aus, nr); os.makedirs(a, exist_ok=True); t0 = time.time()
        r = subprocess.run([PYSEG, "-W", "ignore", "-I", os.path.join(HERE, "foto_diff.py"), k["fd_objp"], nr, "--stl", stl, "--aus", a, "--mehrstufig"] + (["--bild", bilder[nr]] if bilder else []) + list(extra), cwd=ROOT, env=env, capture_output=True, text=True)
        try: j = json.load(open(os.path.join(a, f"foto_diff_{nr}.json")))
        except Exception: open(os.path.join(a, "fehler.log"), "w").write(f"rc {r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-3000:]}"); erg[nr] = None; print("  foto_diff Fehler", nr, flush=True); continue
        erg[nr] = dict(rot=j.get("anteil_modellkanten_ohne_foto"), gelb=j.get("anteil_fotokanten_ohne_modell"), sekunden=round(time.time() - t0, 1), cpu=cpu, bild=os.path.join(a, f"foto_diff_{nr}.jpg"), versatz=(j.get("versatz") or {}).get("versatz_m"))
        print(f"  {os.path.basename(stl)} Foto {nr}: rot {erg[nr]['rot']:.3f} gelb {erg[nr]['gelb']:.3f} ({erg[nr]['sekunden']} s)", flush=True)
    return erg


def pruefstand_zeilen(k, stl, bericht):
    r = subprocess.run([PYSEG, "-W", "ignore", "-I", os.path.join(HERE, "pruefstand.py"), k["pruef_objp"], "--stl", stl, "--bericht", bericht], cwd=ROOT, capture_output=True, text=True)
    if not os.path.exists(bericht): return dict(fehler=(r.stdout + r.stderr)[-600:], rc=r.returncode)
    tab = json.load(open(os.path.join(ROOT, k["obj"]["masstabelle"]))); info = {p["name"]: p for p in tab["pruefungen"]}; out = []
    for p in json.load(open(bericht))["pruefungen"]:
        i = info.get(p["name"], {}); out.append(dict(name=p["name"], wert=p["wert"], soll=p["soll"], status=p["status"], quelltyp=i.get("quelltyp"), merkmal=i.get("merkmal")))
    return dict(rc=r.returncode, zeilen=out)


def geometrie_druck(stl, massstab, pruef_stichproben=200, slicer=True, aus=None, skala_fuer_bett=None):
    import trimesh
    m = trimesh.load(stl); L = max(m.bounds[1] - m.bounds[0]); koerper = len(m.split(only_watertight=False))
    res = dict(wasserdicht=bool(m.is_watertight), koerper=int(koerper), dreiecke=int(len(m.faces)), volumen_cm3=round(abs(float(m.volume)) / 1000.0, 1), groesse_mm=(m.bounds[1] - m.bounds[0]).round(0).tolist())
    # Mindestwandstaerke: Strahl von der Oberflaeche nach innen (200 Stichproben), erster Treffer = lokale Dicke in mm (Teil im Druckmassstab)
    rng = np.random.default_rng(1); P, fi = trimesh.sample.sample_surface(m, pruef_stichproben, seed=1); P = np.asarray(P); n = m.face_normals[fi]
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    rmi = RayMeshIntersector(m); o = P - n * 1e-3; loc, ri, _ = rmi.intersects_location(o, -n, multiple_hits=False); dick = np.full(len(P), np.nan)
    dick[ri] = np.linalg.norm(loc - o[ri], axis=1)
    d = dick[np.isfinite(dick)]
    res["wand_mm"] = dict(n=int(len(d)), min=round(float(d.min()), 2) if len(d) else None, p5=round(float(np.percentile(d, 5)), 2) if len(d) else None, anteil_unter_0_8=round(float(np.mean(d < 0.8)), 3) if len(d) else None, ohne_gegenseite=int(len(P) - len(d)))
    if slicer and aus:
        s = 1.0 if skala_fuer_bett is None else float(skala_fuer_bett)
        mm = m.copy(); mm.apply_scale(s); sp = os.path.join(aus, os.path.basename(stl).replace(".stl", "_slice.stl")); mm.export(sp); g = sp.replace(".stl", ".gcode.3mf"); t0 = time.time()
        try:
            r = subprocess.run([PYSEG, "-I", os.path.join(HERE, "bambu_slice.py"), g, sp, "--schicht", "0.2"], capture_output=True, text=True, timeout=1500)
            res["slicer"] = dict(rc=r.returncode, skala=s, sekunden=round(time.time() - t0, 1), ausgabe=(r.stdout.strip().splitlines() or [""])[-1][:300], fehler=(r.stderr or "")[-300:] if r.returncode else "")
        except subprocess.TimeoutExpired: res["slicer"] = dict(rc=-9, fehler="Zeitgrenze 25 min")
        for f in (sp, g):
            try: os.remove(f)
            except OSError: pass
    return res


# ------------------------------------------------------------------ Ablauf
def bildblatt(k, aus, fotos, ergf, verf, ziel):
    """A | B | C (| W) desselben Fotos nebeneinander, zugeschnitten auf den Bereich der farbigen Overlay-Pixel (Rot/Gelb/Gruen) ueber alle Verfahren."""
    import cv2
    nr = fotos[0]; ims = []; labels = []
    for v in verf:
        e = (ergf.get(v) or {}).get(nr)
        if not e or not os.path.exists(e["bild"]): continue
        ims.append(cv2.imread(e["bild"])); labels.append(f"{v}  rot {e['rot']:.3f}  gelb {e['gelb']:.3f}  Foto {nr}")
    if not ims: return None
    hsv = [cv2.cvtColor(im, cv2.COLOR_BGR2HSV) for im in ims]; col = np.zeros(ims[0].shape[:2], bool)
    for h in hsv: col |= (h[..., 1] > 120) & (h[..., 2] > 120)
    ys, xs = np.where(col)
    if len(xs) > 50:
        H, W = col.shape; x0, x1 = max(0, int(np.percentile(xs, 0.5)) - 40), min(W, int(np.percentile(xs, 99.5)) + 40); y0, y1 = max(0, int(np.percentile(ys, 0.5)) - 40), min(H, int(np.percentile(ys, 99.5)) + 40)
        ims = [im[y0:y1, x0:x1] for im in ims]
    tiles = []
    for im, lb in zip(ims, labels):
        sc = 800.0 / im.shape[1]; im = cv2.resize(im, None, fx=sc, fy=sc); cv2.putText(im, lb, (8, 26), 0, 0.7, (0, 0, 0), 4); cv2.putText(im, lb, (8, 26), 0, 0.7, (255, 255, 255), 2); tiles.append(im)
    h = min(t.shape[0] for t in tiles); tiles = [t[:h] for t in tiles]; os.makedirs(os.path.dirname(ziel), exist_ok=True); cv2.imwrite(ziel, cv2.hconcat(tiles), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return ziel


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--helfer-poisson": return helfer_poisson(sys.argv[2:])
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--verfahren", default="alle"); ap.add_argument("--synthetisch", action="store_true"); ap.add_argument("--aus")
    ap.add_argument("--schritte", default="bauen,fotos,foto_diff,dach,zaehl,druck,blatt"); ap.add_argument("--cpu", action="store_true"); ap.add_argument("--nur-fotos", help="Fotoliste statt Auswahl (Test)")
    ap.add_argument("--slicer-skala", type=float, default=0.0, help="0 = automatisch auf 240 mm Bett")
    a = ap.parse_args(); schritte = a.schritte.split(","); verf = ["A", "B", "C"] if a.verfahren == "alle" else a.verfahren.split(",")
    name = os.path.basename(os.path.dirname(os.path.abspath(a.objekt))); aus = a.aus or os.path.join(BASIS, name + ("_synth" if a.synthetisch else "")); os.makedirs(aus, exist_ok=True)
    if a.synthetisch:
        import beweis_ansatz_synth as S; return S.main(a, aus, verf, schritte)
    k = konfig(a.objekt, aus); ep = os.path.join(aus, "ergebnisse.json"); E = json.load(open(ep)) if os.path.exists(ep) else dict(objekt=name, verfahren={}, metriken={})
    t_ges = time.time()
    if not k.get("dicht") and "A" in verf: print("A nicht pruefbar: keine dichte Wolke/Ausrichtung in der Konfiguration"); E["verfahren"]["A"] = dict(nicht_pruefbar="keine dichte Wolke mit Ausrichtung")
    stls = E.setdefault("stl", {})
    if "bauen" in schritte:
        D = None
        for v in verf:
            if v == "A" and k.get("dicht"):
                print("A: Poisson ...", flush=True); r = verfahren_A(k, aus); E["verfahren"]["A"] = r; stls["A"] = r["stl"]; print("  ", {x: y for x, y in r.items() if x != "stl"}, flush=True)
            if v == "B":
                if k.get("stl_B"): shutil.copy(k["stl_B"], os.path.join(aus, "B_amtlich.stl")); stls["B"] = os.path.join(aus, "B_amtlich.stl"); E["verfahren"]["B"] = dict(stl=stls["B"], art=k["B_art"], sekunden=None)
                else:
                    D = D or dom1_laden(k)
                    if D is None: E["verfahren"]["B"] = dict(nicht_pruefbar="keine DOM1-Kachel"); continue
                    r = verfahren_B_dom(k, D, aus); E["verfahren"]["B"] = r; stls["B"] = r["stl"]; print("  B:", {x: y for x, y in r.items() if x != "stl"}, flush=True)
            if v == "C": stls["C"] = kopieren_C(k, aus, "C_modell_1-%d.stl" % k["massstab"]); E["verfahren"]["C"] = dict(stl=stls["C"], art=k.get("C_art"), quelle=k["stl_C"])
        json.dump(E, open(ep, "w"), indent=1)
    fotos, kand = (a.nur_fotos.split(","), []) if a.nur_fotos else foto_auswahl(k); E["zurueckgehaltene_fotos"] = fotos; E["kandidaten_fotos"] = kand; E["benutzte_fotos_laeufer"] = k.get("benutzt"); E["benutzte_quelle"] = k.get("benutzt_quelle")
    ergf = E["metriken"].setdefault("2_fotos", {})
    if "foto_diff" in schritte:
        for v in verf:
            if v in stls:
                print(f"Metrik 2: {v}", flush=True); t0 = time.time(); ergf[v] = foto_diff_lauf(k, fotos, stls[v], os.path.join(aus, "foto_diff_" + v), a.cpu)
                E["verfahren"].setdefault(v, {})["sekunden_foto_diff"] = round(time.time() - t0, 1); json.dump(E, open(ep, "w"), indent=1)
    if "dach" in schritte or "zaehl" in schritte:
        D = dom1_laden(k) if "dach" in schritte else None
        for v in verf:
            if v not in stls: continue
            ps = pruefstand_zeilen(k, stls[v], os.path.join(aus, f"pruefbericht_{v}.json")); E["metriken"].setdefault("pruefstand", {})[v] = ps
            if D is not None:
                m = stl_laden_m(stls[v], k["massstab"]); eigen, art = eigener_grundriss(k, D); r, H = dach_dom1(m, D, eigen); r["maske"] = art; r["dom1"] = D["quelle"]; E["metriken"].setdefault("3_dom1", {})[v] = r; print(f"  Dach {v}: {r}", flush=True)
            json.dump(E, open(ep, "w"), indent=1)
    if "druck" in schritte:
        import trimesh
        sk = a.slicer_skala or min(1.0, 240.0 / max(max(trimesh.load(s).extents) for s in stls.values()))
        for v in verf:
            if v in stls: print(f"Metrik 5: {v}", flush=True); E["metriken"].setdefault("5_druck", {})[v] = geometrie_druck(stls[v], k["massstab"], aus=aus, skala_fuer_bett=sk); json.dump(E, open(ep, "w"), indent=1)
    if "blatt" in schritte and ergf:
        E["bildblatt"] = bildblatt(k, aus, fotos, ergf, verf, os.path.join(ROOT, "modelle", name, "audit", "beweis_ansatz", f"blatt_{name}.jpg")); print("Bildblatt:", E["bildblatt"])
    E["sekunden_gesamt_dieser_aufruf"] = round(time.time() - t_ges, 1); json.dump(E, open(ep, "w"), indent=1)


if __name__ == "__main__":
    main()
