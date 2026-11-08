#!/usr/bin/env python3
"""dicht_handy.py - dichte Wolke (COLMAP PatchMatch Stereo, GPU) aus den Handybildern des Zusatz-Registrierlaufs (Register DL, 2026-11-06).

Warum eigenes Werkzeug: sfm_dicht.py rechnet ein ganzes Seitennetz (Rekonstruktion = Quelle der Wahrheit, alle Bilder); hier gibt es
  (1) Handybilder, die per PnP gegen ein Referenznetz registriert sind (Posen im Modellrahmen von sparse_alle, geprueft: Referenzposen identisch),
  (2) Masken (255 = benutzen) und (3) Posenguete je Bild. Wiederverwendet: Transformation Modellrahmen, PatchMatch-/Fusionsaufrufe, Sparse-Beschnitt-Idee.
Stufen (jede schreibt JSON nach --aus):
  auswahl   Posenguete -> Klasse je Bild.  Kriterium AUS DATEN (keine Handschwelle): Median des Rotationsfehlers (Essentialmatrix-Test, pose_vertrauen_gruppen_*.json,
            Feld paare[].rot_fehler_grad) ueber alle Paare des Bildes; Schwelle = Bruchstelle der besten 1-D-2-Means-Teilung (Jenks) im Log-Raum ueber ALLE Bilder
            beider Laeufe (wie handy_zoom_verdacht). Unter der Schwelle = 'sicher', darueber 'unsicher' (eigene Wolke, nicht weggeworfen). Bilder mit < 3 Paaren: 'unsicher'.
            Die Schwelle ist RELATIV (trennt zwei Gruppen), kein Beweis absoluter Posengenauigkeit.
  rechnen   je Klasse+Lauf Stapel (Groesse aus freiem Platz; Platztor 10 GB), je Stapel: entzerren (inkl. Masken), PatchMatch (GPU, geom. Konsistenz,
            Quellbilder NUR aus dem Stapel = gleiche Klasse; Auswahl nach Sichtbarkeit gemeinsamer Punkte, Gewicht sin(Triangulationswinkel)), Masken auf Tiefenkarten
            (Maske 0 -> Tiefe 0), Fusion (CPU, parallel zum naechsten GPU-Stapel), Modellrahmen, Beschnitt auf Kasten der Sparse-Punkte (Perzentile), Arbeitsordner auslagern.
  vergleich Abstand zur Referenzwolke (NN, cv2.flann) im Ueberlappungsbereich + Sichtblatt.
Aufruf (alle Stufen): /media/oem/scan/venv-colmap/bin/python -I tools/dicht_handy.py <stufe> --aus ORDNER [...]
Lizenz: nur pycolmap/COLMAP (BSD), OpenCV (Apache-2.0), numpy.
"""
import sys, os, json, glob, argparse, subprocess, shutil, time, threading, collections, resource
import numpy as np
import cv2

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
BASIS = "/media/oem/scan/rc-park_null/kaufhaus_handy3"
MASKEN = "/media/oem/scan/rc-park_null/kaufhaus_handy_masken_v2"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_GB = 10.0                                                   # Platztor (tools/platz_pruefen.py)


def frei_gb(pfad="/media/oem/scan"):
    return shutil.disk_usage(pfad).free / 1e9


def lauf_ordner(l):
    return os.path.join(BASIS, l)


# ---------------------------------------------------------------- Stufe auswahl
def jenks_schwelle(werte):
    """Beste 2-Teilung (kleinste Summe der Quadratabweichungen) im Log-Raum; Rueckgabe Schwelle (geometrische Mitte der Bruchstelle)."""
    x = np.sort(np.log(np.asarray(werte, float))); best = None
    for i in range(3, len(x) - 3):
        a, b = x[:i], x[i:]; c = ((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()
        if best is None or c < best[0]: best = (c, i)
    return float(np.exp((x[best[1] - 1] + x[best[1]]) / 2)), best[1]


def stufe_auswahl(a):
    zeilen = []
    for pv, l in zip(a.pv, a.lauf):
        J = json.load(open(pv)); per = collections.defaultdict(list)
        for p in J["laeufe"][l]["paare"]:
            per[p["a"]].append(p["rot_fehler_grad"]); per[p["b"]].append(p["rot_fehler_grad"])
        for n, info in J["bilder"][l].items():
            v = per.get(n, [])
            zeilen.append(dict(lauf=l, bild=n, serie=n.split("_")[1], gruppe=info["gruppe"], n_paare=len(v), rot_median_grad=(float(np.median(v)) if v else None),
                               loo_rot_grad=info.get("loo_rot_grad"), loo_zentrum_m=info.get("loo_zentrum_m")))
    bew = [z["rot_median_grad"] for z in zeilen if z["n_paare"] >= 3]
    thr, n_unten = jenks_schwelle(bew)
    for z in zeilen:
        z["klasse"] = "sicher" if (z["n_paare"] >= 3 and z["rot_median_grad"] <= thr) else "unsicher"
    ser = collections.defaultdict(lambda: collections.Counter())
    for z in zeilen: ser[z["serie"]][z["klasse"]] += 1
    out = dict(kriterium="Median rot_fehler_grad (E-Test) je Bild, Schwelle = Jenks-2-Means im Log-Raum ueber alle Bilder; < 3 Paare = unsicher",
               schwelle_grad=thr, n_bewertet=len(bew), n_sicher_bewertet=n_unten, quantile_rot_median=dict(zip(["q10", "q25", "q50", "q75", "q90"], np.percentile(bew, [10, 25, 50, 75, 90]).tolist())),
               je_serie={s: dict(c) for s, c in sorted(ser.items())}, n_sicher=sum(z["klasse"] == "sicher" for z in zeilen), n_unsicher=sum(z["klasse"] == "unsicher" for z in zeilen), bilder=zeilen)
    os.makedirs(a.aus, exist_ok=True); json.dump(out, open(os.path.join(a.aus, "auswahl.json"), "w"), indent=1)
    print(f"Schwelle {thr:.2f} Grad; sicher {out['n_sicher']}, unsicher {out['n_unsicher']}; je Serie {out['je_serie']}")


# ---------------------------------------------------------------- Stufe rechnen: Arbeiter (Unterprozesse, spawn)
def quellen_waehlen(rec, namen, max_quellen=20):
    """Quellbilder je Bild NUR aus 'namen': Score = Summe sin(Triangulationswinkel) ueber gemeinsam gesehene 3D-Punkte (ANNAHME: sin = glatte Gewichtung ohne Schwelle;
    COLMAP-auto waehlt aehnlich nach Winkel/Ueberlappung, darf aber auf nicht entzerrte Bilder zeigen)."""
    ids = {im.name: im.image_id for im in rec.images.values() if im.name in set(namen)}; inv = {v: k for k, v in ids.items()}
    ctr = {i: rec.images[i].projection_center() for i in ids.values()}; score = collections.defaultdict(float)
    for p3 in rec.points3D.values():
        obs = sorted({e.image_id for e in p3.track.elements if e.image_id in inv})
        if len(obs) < 2: continue
        X = p3.xyz
        for i in range(len(obs)):
            for j in range(i + 1, len(obs)):
                u = ctr[obs[i]] - X; v = ctr[obs[j]] - X
                c = float(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12)); s = float(np.sqrt(max(0.0, 1 - c * c)))
                score[(obs[i], obs[j])] += s; score[(obs[j], obs[i])] += s
    res = {}
    for n in namen:
        if n not in ids: continue
        cand = sorted(((s, inv[b]) for (a_, b), s in score.items() if a_ == ids[n]), reverse=True)[:max_quellen]
        res[n] = [m for s, m in cand]
    return res


def lese_mat(pfad):
    with open(pfad, "rb") as f:
        raw = f.read()
    k = 0; teile = []
    for i, ch in enumerate(raw):
        if ch == 38:                                              # '&'
            teile.append(int(raw[k:i])); k = i + 1
            if len(teile) == 3: break
    w, h, c = teile
    return w, h, c, raw[:k], np.frombuffer(raw[k:], dtype="<f4").reshape(c, h, w) if c > 1 else np.frombuffer(raw[k:], dtype="<f4").reshape(h, w)


def vorbereiten(auftrag):
    """Entzerren (Bilder + Masken), Quellen-Konfiguration. CPU. auftrag: dict(tag, lauf, namen, max_size, aus)."""
    import pycolmap
    t0 = time.time(); W = os.path.join(auftrag["aus"], "arbeit", auftrag["tag"]); lo = lauf_ordner(auftrag["lauf"]); namen = auftrag["namen"]
    if os.path.isdir(W): shutil.rmtree(W)
    os.makedirs(W)
    uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = auftrag["max_size"]
    sparse = os.path.join(lo, "sparse_handy", "0")
    pycolmap.undistort_images(W, sparse, os.path.join(lo, "bilder"), image_names=namen, output_type="COLMAP", undistort_options=uo)
    # Masken: 255 = benutzen -> gleiche Entzerrung; als JPEG (0/255) ablegen, danach >127
    mtmp = os.path.join(W, "masken_roh"); os.makedirs(mtmp)
    fehlt = []
    for n in namen:
        mp = os.path.join(MASKEN, n.split("_")[1], n.replace(".jpg", ".png"))
        m = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if m is None: fehlt.append(n); m = np.full(cv2.imread(os.path.join(lo, "bilder", n)).shape[:2], 255, np.uint8)
        cv2.imwrite(os.path.join(mtmp, n), cv2.merge([m, m, m]), [cv2.IMWRITE_JPEG_QUALITY, 100])
    Wm = os.path.join(W, "masken_ud")
    pycolmap.undistort_images(Wm, sparse, mtmp, image_names=namen, output_type="COLMAP", undistort_options=uo)
    rec = pycolmap.Reconstruction(sparse); q = quellen_waehlen(rec, namen)
    ohne = [n for n in namen if not q.get(n)]
    cfg = os.path.join(W, "stereo", "patch-match.cfg")
    with open(cfg, "w") as f:
        for n in namen:
            if n in ohne: continue
            f.write(f"{n}\n{', '.join(q[n])}\n")
    with open(os.path.join(W, "stereo", "fusion.cfg"), "w") as f:                  # Bilder ohne Partner haben keine Tiefenkarte
        for n in namen:
            if n not in ohne: f.write(n + "\n")
    json.dump(dict(tag=auftrag["tag"], namen=namen, quellen=q, ohne_partner=ohne, masken_fehlen=fehlt), open(os.path.join(W, "vorbereitet.json"), "w"), indent=1)
    shutil.rmtree(mtmp)
    return dict(tag=auftrag["tag"], dauer_s=time.time() - t0, ohne_partner=ohne, masken_fehlen=fehlt, W=W)


def fusionieren(auftrag):
    """Masken auf Tiefenkarten, Fusion, Modellrahmen, Beschnitt, npy. CPU, ein Faden (reproduzierbar, Register CA). Danach Arbeitsordner auslagern."""
    import pycolmap, struct
    t0 = time.time(); W = os.path.join(auftrag["aus"], "arbeit", auftrag["tag"]); V = json.load(open(os.path.join(W, "vorbereitet.json")))
    stat = {}
    for n in V["namen"]:
        if n in V["ohne_partner"]: continue
        mk = cv2.imread(os.path.join(W, "masken_ud", "images", n), cv2.IMREAD_GRAYSCALE)
        for art in ("geometric", "photometric"):
            fp = os.path.join(W, "stereo", "depth_maps", f"{n}.{art}.bin")
            if not os.path.exists(fp): continue
            w, h, c, kopf, d = lese_mat(fp)
            if mk is None or mk.shape != (h, w): raise SystemExit(f"Maske {n} passt nicht zur Tiefenkarte: {None if mk is None else mk.shape} vs {(h, w)}")
            gut0 = int((d > 0).sum()); d = d.copy(); d[mk <= 127] = 0
            with open(fp, "wb") as f: f.write(kopf); f.write(d.astype("<f4").tobytes())
            if art == "geometric": stat[n] = dict(px=w * h, gueltig_vor_maske=gut0, gueltig_nach_maske=int((d > 0).sum()), maskiert_anteil=float((mk <= 127).mean()))
    ply = os.path.join(W, "fused.ply"); fo = pycolmap.StereoFusionOptions(); fo.num_threads = 1
    pycolmap.stereo_fusion(ply, W, options=fo, output_type="ply")
    with open(ply, "rb") as f:
        header = []
        while True:
            line = f.readline().decode("ascii").strip(); header.append(line)
            if line == "end_header": break
        n = int([h for h in header if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in header if h.startswith("property")]
        dt = np.dtype([(p[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[p[0]]) for p in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    X = np.c_[arr["x"], arr["y"], arr["z"]].astype(np.float64); C = np.c_[arr["red"], arr["green"], arr["blue"]].astype(np.uint8)
    tr = auftrag["transformation"]; s = float(tr["s"]); R = cv2.Rodrigues(np.array(tr["rvec"]))[0]; t = np.array(tr["t"])
    Xm = ((X - t) @ R) / s                                                    # R^T (X - t) / s, wie sfm_dicht.py
    lo, hi = np.array(auftrag["kasten"][0]), np.array(auftrag["kasten"][1]); k = ((Xm >= lo) & (Xm <= hi)).all(1)
    bd = os.path.join(auftrag["aus"], "stapel"); os.makedirs(bd, exist_ok=True)
    np.save(os.path.join(bd, f"{auftrag['tag']}_modell.npy"), Xm[k].astype(np.float32)); np.save(os.path.join(bd, f"{auftrag['tag']}_farben.npy"), C[k])
    rs = dict(tag=auftrag["tag"], n_fusion=int(len(Xm)), n_im_kasten=int(k.sum()), dauer_fusion_s=time.time() - t0, bilder=stat)
    json.dump(rs, open(os.path.join(bd, f"{auftrag['tag']}_bericht.json"), "w"), indent=1)
    os.makedirs(os.path.join(auftrag["aus"], "arbeit_ausgelagert"), exist_ok=True)
    r = subprocess.run(["bash", os.path.join(REPO, "tools", "auslagern.sh"), W], capture_output=True, text=True)
    rs["auslagern"] = (r.stdout.strip().splitlines() or [""])[-3:]; return rs


class GpuSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.w = []; self.stop = False

    def run(self):
        while not self.stop:
            try:
                o = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.split(",")
                self.w.append((float(o[0]), float(o[1])))
            except Exception: pass
            time.sleep(2)


def stufe_rechnen(a):
    import pycolmap
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    A = json.load(open(os.path.join(a.aus, "auswahl.json"))); S = json.load(open(a.ausrichtung))["transformation"]
    # Kasten aus den Sparse-Punkten (1..99 Perzentil, gespreizt um die Spannweite: aus Daten, kein Festwert)
    rec = pycolmap.Reconstruction(os.path.join(lauf_ordner(a.lauf[0]), "sparse_handy", "0")); P = np.array([p.xyz for p in rec.points3D.values()])
    R = cv2.Rodrigues(np.array(S["rvec"]))[0]; Pm = ((P - np.array(S["t"])) @ R) / float(S["s"]); lo, hi = np.percentile(Pm, 1, 0), np.percentile(Pm, 99, 0); sp = hi - lo
    kasten = ((lo - 0.5 * sp).tolist(), (hi + 0.5 * sp).tolist()); print("Kasten Modellrahmen", kasten, flush=True); del rec
    # Stapel
    ms = a.max_size; px_bild = ms * ms * 0.64                                  # ANNAHME: Hochformat 2000x2533 -> lange Seite ms, kurze 0,79 ms
    bytes_bild = px_bild * 32 + 3e6                                            # Tiefe+Normale (16 B/px) x (photometrisch + geometrisch)
    stapel = []
    for kl in ("sicher", "unsicher"):
        for l in a.lauf:
            ns = sorted(z["bild"] for z in A["bilder"] if z["lauf"] == l and z["klasse"] == kl)
            if not ns: continue
            ns = sorted(ns, key=lambda n: (n.split("_")[1], n))
            if a.probe: ns = ns[:a.probe]
            frei = frei_gb() - GATE_GB; cap = max(8, int(a.stapel_gb * 1e9 / bytes_bild)) if a.stapel_gb else max(8, int(max(frei, 1.0) * 0.5e9 / bytes_bild))
            nb = int(np.ceil(len(ns) / cap)); gs = int(np.ceil(len(ns) / nb))
            for i in range(nb): stapel.append(dict(tag=f"{kl}_{l}_{i:02d}", klasse=kl, lauf=l, namen=ns[i * gs:(i + 1) * gs], max_size=ms, aus=a.aus, transformation=S, kasten=kasten))
    print(f"{len(stapel)} Stapel: " + ", ".join(f"{s['tag']}({len(s['namen'])})" for s in stapel), flush=True)
    bericht_p = os.path.join(a.aus, "bericht_rechnen.json"); bericht = dict(max_size=ms, stapel=[], gpu=[])
    tcache = None
    if getattr(a, "tiefen_cache", None):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import dicht_handy_cache as DC; tcache = DC.cache_pfad(a.tiefen_cache)
        print("Tiefen-Cache:", tcache, flush=True)
    ctx = mp.get_context("spawn"); pool = ProcessPoolExecutor(max_workers=a.fusion_parallel + 1, mp_context=ctx)
    fus = []; vor = pool.submit(vorbereiten, stapel[0]) if stapel else None
    for i, st in enumerate(stapel):
        if frei_gb() < GATE_GB + 0.5:
            for f in fus: f.result()                                           # Auslagern fertig abwarten
            if frei_gb() < GATE_GB + 0.5: print("PLATZTOR: zu wenig Platz, Abbruch vor", st["tag"]); break
        v = vor.result(); print(f"[{i + 1}/{len(stapel)}] {st['tag']} vorbereitet in {v['dauer_s']:.0f} s, ohne Partner {len(v['ohne_partner'])}, Masken fehlen {len(v['masken_fehlen'])}; frei {frei_gb():.1f} GB", flush=True)
        if i + 1 < len(stapel) and frei_gb() > GATE_GB + 3: vor = pool.submit(vorbereiten, stapel[i + 1])
        else: vor = None
        t0 = time.time(); smp = GpuSampler(); smp.start()
        opt = pycolmap.PatchMatchOptions(); opt.max_image_size = ms; opt.geom_consistency = True; opt.gpu_index = "0"
        W = v["W"]; cfg_pm = os.path.join(W, "stereo", "patch-match.cfg"); vc = None
        if tcache:                                                              # opt-in: unveraenderte Tiefenkarten aus frueheren Laeufen einsetzen (dicht_handy_cache.py)
            import dicht_handy_cache as DC
            vc = DC.vor_patchmatch(W, opt, tcache); cfg_pm = vc["cfg"]
            print(f"    Tiefen-Cache: {len(vc['treffer'])} Treffer, {len(vc['fehlend'])} neu zu rechnen", flush=True)
        if cfg_pm: pycolmap.patch_match_stereo(W, options=opt, config_path=cfg_pm)
        if vc: DC.nach_patchmatch(W, tcache, vc, st["tag"])
        smp.stop = True; smp.join(timeout=3)
        u = [x[0] for x in smp.w]; g = dict(tag=st["tag"], dauer_s=time.time() - t0, gpu_util_mittel=float(np.mean(u)) if u else None, gpu_util_max=max(u) if u else None, vram_max_mib=max(x[1] for x in smp.w) if smp.w else None)
        bericht["gpu"].append(g); print(f"    PatchMatch {g['dauer_s']:.0f} s, GPU-Last mittel {g['gpu_util_mittel']} %, max {g['gpu_util_max']} %, VRAM {g['vram_max_mib']} MiB", flush=True)
        fus.append(pool.submit(fusionieren, st))
        if vor is None and i + 1 < len(stapel):                                 # kein Platz fuer Vorlauf -> auf Fusion/Auslagern warten, dann vorbereiten
            for f in fus: f.result()
            vor = pool.submit(vorbereiten, stapel[i + 1])
        json.dump(bericht, open(bericht_p, "w"), indent=1)
    for f in fus:
        r = f.result(); bericht["stapel"].append(r); print("    fertig", r["tag"], r["n_fusion"], "Punkte,", r["n_im_kasten"], "im Kasten", r["auslagern"], flush=True)
    pool.shutdown(); json.dump(bericht, open(bericht_p, "w"), indent=1)


# ---------------------------------------------------------------- Stufe vergleich
def nn_abstand(ref, pts, checks=256, k=8, flann=None):
    """Rueckgabe (d_nn, d_ebene): NN-Abstand und Abstand zur lokalen Ebene durch die k naechsten Referenzpunkte (nimmt den Abtastboden der Referenz heraus)."""
    idx = flann or cv2.flann_Index(ref, dict(algorithm=1, trees=4)); dn = np.empty(len(pts), np.float32); de = np.empty(len(pts), np.float32)
    for i in range(0, len(pts), 100000):
        q = np.ascontiguousarray(pts[i:i + 100000], dtype=np.float32); ii, dd = idx.knnSearch(q, k, params=dict(checks=checks)); dn[i:i + 100000] = np.sqrt(dd[:, 0])
        N = ref[ii]; m = N.mean(1, keepdims=True); C = np.einsum("nki,nkj->nij", N - m, N - m); w, v = np.linalg.eigh(C); nrm = v[:, :, 0]
        de[i:i + 100000] = np.abs(np.einsum("ni,ni->n", q - m[:, 0], nrm))
    return dn, de


def qs(d):
    return dict(n=int(len(d)), median=float(np.median(d)) if len(d) else None, q75=float(np.quantile(d, .75)) if len(d) else None, q90=float(np.quantile(d, .9)) if len(d) else None, q99=float(np.quantile(d, .99)) if len(d) else None)


def sichtblatt(ref, gruppen, pfad, kasten):
    """Draufsicht (x,y), Seite (x,z), Seite (y,z): Referenz grau, neue Wolken farbig (Fotofarbe) bzw. nach Klasse."""
    lo, hi = np.array(kasten[0]), np.array(kasten[1]); Z = 520
    def ebene(pts, cols, ax, bx, flip):
        sx = Z / (hi[ax] - lo[ax]); sy = Z / (hi[bx] - lo[bx]); sc = min(sx, sy)
        img = np.full((Z, Z, 3), 255, np.uint8); u = ((pts[:, ax] - lo[ax]) * sc).astype(int); v = ((pts[:, bx] - lo[bx]) * sc).astype(int)
        if flip: v = Z - 1 - v
        k = (u >= 0) & (u < Z) & (v >= 0) & (v < Z); img[v[k], u[k]] = cols[k]; return img
    tafeln = []
    for ax, bx, flip, name in ((0, 1, True, "Draufsicht x-y"), (0, 2, True, "Seite x-z"), (1, 2, True, "Seite y-z")):
        zeile = []
        gr = np.full((len(ref), 3), 170, np.uint8); zeile.append(ebene(ref, gr, ax, bx, flip))
        pts = np.concatenate([g["pts"] for g in gruppen]); col = np.concatenate([g["klassenfarbe"] for g in gruppen]); o = ebene(ref, gr, ax, bx, flip)
        kl_ = ebene(pts, col, ax, bx, flip); zeile.append(np.where((kl_ < 255).any(2, keepdims=True), kl_, o))
        zeile.append(ebene(pts, np.concatenate([g["farben"] for g in gruppen])[:, ::-1], ax, bx, flip))    # Fotofarbe RGB -> BGR
        for im, t in zip(zeile, ("Referenz dicht_alle", "neu nach Klasse (gruen sicher, rot unsicher) ueber Referenz", "neu, Fotofarbe")): cv2.putText(im, f"{name}: {t}", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        tafeln.append(np.hstack(zeile))
    cv2.imwrite(pfad, np.vstack(tafeln), [cv2.IMWRITE_JPEG_QUALITY, 90])


def stufe_vergleich(a):
    ref = np.ascontiguousarray(np.load(a.ref).astype(np.float32)); bd = os.path.join(a.aus, "stapel"); R = json.load(open(os.path.join(a.aus, "bericht_rechnen.json")))
    sub = np.ascontiguousarray(ref[::max(1, len(ref) // 20000)][:20000])                                  # Punktabstand der Referenz: 2. Nachbar (1. = Punkt selbst)
    FL = cv2.flann_Index(ref, dict(algorithm=1, trees=4)); idx = FL; _, dd = idx.knnSearch(sub, 2, params=dict(checks=256)); s_ref = float(np.median(np.sqrt(dd[:, 1])))
    voxel = a.ueberlappung_m if a.ueberlappung_m else 10 * s_ref
    belegt = set(map(tuple, np.floor(ref / voxel).astype(int)))
    out = dict(ref=a.ref, n_ref=int(len(ref)), ref_abstand_median_m=s_ref, ueberlappung_voxel_m=voxel, klassen={}, stapel={})
    gruppen = []
    for kl in ("sicher", "unsicher"):
        P = []; C = []
        for z in sorted(glob.glob(os.path.join(bd, f"{kl}_*_modell.npy"))):
            p = np.load(z); c = np.load(z.replace("_modell", "_farben")); tag = os.path.basename(z)[:-len("_modell.npy")]
            if len(p) == 0: out["stapel"][tag] = dict(n=0); continue
            d, de = nn_abstand(ref, p, flann=FL); ov = np.array([tuple(v) in belegt for v in np.floor(p / voxel).astype(int)])
            out["stapel"][tag] = dict(nn_alle=qs(d), nn_ueberlappung=qs(d[ov]), ebene_ueberlappung=qs(de[ov]), anteil_ueberlappung=float(ov.mean())); P.append(p); C.append(c)
        if not P: continue
        p = np.concatenate(P); c = np.concatenate(C); d, de = nn_abstand(ref, p, flann=FL); ov = np.array([tuple(v) in belegt for v in np.floor(p / voxel).astype(int)])
        d_ov = d[ov]; schw = [0.05, 0.1, 0.25, 0.5, 1.0]
        out["klassen"][kl] = dict(n=int(len(p)), anteil_ueberlappung=float(ov.mean()), n_neu_ausserhalb=int((~ov).sum()), nn_ueberlappung=qs(d_ov), ebene_ueberlappung=qs(de[ov]), nn_alle=qs(d), ebene_alle=qs(de),
                                  anteil_ueber_m={str(s): float((d_ov > s).mean()) for s in schw}, farbe_mittel_neu_rgb=c[~ov].mean(0).tolist() if (~ov).any() else None,
                                  neu_ausserhalb_z_quantile_m=(np.percentile(p[~ov][:, 2], [5, 25, 50, 75, 95]).tolist() if (~ov).any() else None), neu_ausserhalb_xy_min_max=((p[~ov][:, :2].min(0).tolist(), p[~ov][:, :2].max(0).tolist()) if (~ov).any() else None))
        gruppen.append(dict(pts=p, farben=c, klassenfarbe=np.tile(np.array([[60, 160, 60] if kl == "sicher" else [40, 40, 230]], np.uint8), (len(p), 1))))
        np.save(os.path.join(a.aus, f"dicht_neu_{kl}_modell.npy"), p.astype(np.float32)); np.save(os.path.join(a.aus, f"dicht_neu_{kl}_farben.npy"), c)
    if gruppen:
        allp = np.concatenate([ref] + [g["pts"] for g in gruppen]); lo_ = np.percentile(allp, 0.5, 0); hi_ = np.percentile(allp, 99.5, 0)
        sichtblatt(ref, gruppen, os.path.join(a.aus, "sichtblatt.jpg"), (lo_, hi_))
    out["gpu"] = R.get("gpu"); json.dump(out, open(os.path.join(a.aus, "bericht.json"), "w"), indent=1); print(json.dumps(out["klassen"], indent=1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stufe", choices=["auswahl", "rechnen", "vergleich"]); ap.add_argument("--aus", required=True)
    ap.add_argument("--pv", nargs="+", default=[os.path.join(BASIS, "pose_vertrauen_gruppen_v2_a_m.json"), os.path.join(BASIS, "pose_vertrauen_gruppen_v2_npq.json")])
    ap.add_argument("--lauf", nargs="+", default=["a_m_v2", "npq_v2"]); ap.add_argument("--max-size", type=int, default=1600); ap.add_argument("--stapel-gb", type=float, default=None)
    ap.add_argument("--tiefen-cache", default=None, help="Objektname: Tiefenkarten-Cache unter /media/oem/scan/rc-park_daten/<objekt>/ (unveraenderte Bilder nicht neu rechnen)")
    ap.add_argument("--probe", type=int, default=None, help="Test: nur die ersten N Bilder je Klasse+Lauf, nur 1 Stapel je Klasse+Lauf"); ap.add_argument("--fusion-parallel", type=int, default=3); ap.add_argument("--ausrichtung", default=os.path.join(REPO, "modelle/kaufhaus_null4/messprotokoll/SFM-AUSRICHTUNG-alle.json"))
    ap.add_argument("--ref", default=os.path.join(REPO, "modelle/kaufhaus_null4/sfm/dicht_alle_modell.npy")); ap.add_argument("--ueberlappung-m", type=float, default=None)
    a = ap.parse_args()
    {"auswahl": stufe_auswahl, "rechnen": stufe_rechnen, "vergleich": stufe_vergleich}[a.stufe](a)


if __name__ == "__main__":
    main()
