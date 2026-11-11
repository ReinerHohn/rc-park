#!/usr/bin/env python3
"""flaechen_mass.py - FLAECHENMASS (Spec modelle/SPEC_FLAECHENMASS.md, Nutzerentscheid 11.11.): Formvergleich ueber FLAECHEN statt Kanten.

Warum: der Foto-F1 (teil_fotoform.py) zaehlt Kanten und ist blind fuer Formfamilien (Treppe gegen Saegezahn -0,002, Rechteck gegen Bogen).
Hier: je Foto und Teil zerlegt SAM (facebook/sam-vit-large, Apache-2.0, transformers mask-generation) den Teilausschnitt in Flaechen; das Modell
(render_kern, gleiche Kamera/Rahmen/Verdeckung wie teil_fotoform) wird in Flaechen zerlegt:
  - Flaechen des Zielteils = zusammenhaengende Bereiche gleicher Normalenklasse (sichtbar, nicht verdeckt),
  - "Rest" (= Loch/Hintergrund/Himmel) = Bereich in der Huelle des Teils (Vereinigung aller Varianten + Rand), in dem das Teil NICHT ist und
    weder Modell noch Fotowolke davorliegen: dort sieht man durch/hinter das Teil.
Mass: je Modellflaeche die beste SAM-Maske (IoU im Bewertungsbereich ROI), flaechengewichtet gemittelt = iou_flaechen.
iou_silhouette = bester IoU der GANZEN sichtbaren Teilmaske gegen eine einzelne SAM-Maske (Umriss gegen Himmel/Hintergrund).
Verdeckte Pixel (anderes Teil des Modells oder Fotowolke davor) zaehlen nirgends.

Aufruf (venv-seg, GPU ~3,5 GB, ueber job_start mit JOB_GPU_MB=4000):
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/flaechen_mass.py <objekt> --teile_dir DIR --nur TEIL --fotos A,B|auto:6 --aus out.json
        [--bereich_von DIR2 (gleicher ROI wie Gegenvariante, Pflicht fuer Vorher/Nachher-Vergleich)] [--bilder] [--bilder_dir D] [--ohne_cache]
SAM-Masken liegen im Cache /media/oem/scan/rc-park_tmp/flaechen_cache/ (unabhaengig vom Modell; Schluessel Fotodatei + Ausschnitt + Parameter).
Kein Objektname im Code: alles aus modelle/<objekt>/objekt.json.
"""
import sys, os, json, glob, argparse, hashlib, time, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK, foto_diff as FD

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRIK = "f1_sam_large_roi"
CACHE = "/media/oem/scan/rc-park_tmp/flaechen_cache"
SAMP = {}
SAM_PAR = dict(points_per_batch=32, pred_iou_thresh=0.88, stability_score_thresh=0.92)   # wie editor_modell.sam_flaechen
ARBEIT = 1024   # Langseite des SAM-Eingangs (SAM skaliert intern ohnehin auf 1024)


def sam_masken(crop_bgr, schluessel, ohne_cache=False):
    """-> (masken bool (n,h,w), scores) fuer das BGR-Bild (h,w) <= ARBEIT; Cache nach Schluessel."""
    os.makedirs(CACHE, exist_ok=True)
    cp = os.path.join(CACHE, hashlib.sha256(schluessel.encode()).hexdigest()[:24] + ".npz")
    if not ohne_cache and os.path.exists(cp):
        z = np.load(cp); h, w = z["shape"]; return np.unpackbits(z["bits"], axis=1)[:, :h * w].reshape(-1, h, w).astype(bool), z["scores"], True
    os.environ.setdefault("HF_HOME", "/media/oem/scan/tools_src/hf_cache")
    import torch
    from PIL import Image
    if "g" not in SAMP:
        from transformers import pipeline
        SAMP["g"] = pipeline("mask-generation", model="facebook/sam-vit-large", device=0)
    r = SAMP["g"](Image.fromarray(crop_bgr[:, :, ::-1]), **SAM_PAR)
    h, w = crop_bgr.shape[:2]
    M = np.stack([np.asarray(m.cpu() if hasattr(m, "cpu") else m).astype(bool) for m in r["masks"]]) if len(r["masks"]) else np.zeros((0, h, w), bool)
    sc = np.asarray([float(s) for s in r["scores"]], np.float32)
    if not ohne_cache:
        np.savez_compressed(cp, bits=np.packbits(M.reshape(len(M), -1), axis=1), scores=sc, shape=np.array([h, w]))
    torch.cuda.empty_cache()
    return M, sc, False


def lade_teile(td, nur, obj):
    """Alle Teile eines Verzeichnisses (Meter, Modellrahmen vor Verschiebung): -> (Zielteil trimesh|None, Rest als EIN trimesh|None)."""
    sc = obj.get("stl_massstab", 87) / 1000.0; ziel = None; rest = []
    for p in sorted(glob.glob(os.path.join(td, "*.stl"))):
        m = trimesh.load(p, force="mesh")
        if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0: continue
        m.apply_scale(sc)
        if os.path.basename(p)[:-4] == nur: ziel = m
        else: rest.append(m)
    return ziel, (trimesh.util.concatenate(rest) if rest else None)


def normalklassen(m, fid):
    """Normalenklasse je Pixel: Normale auf 0,15 gerundet (~8 Grad), -1 = kein Teil. fid = Dreiecksnummer je Pixel."""
    n = np.round(np.asarray(m.face_normals) / 0.15).astype(np.int32)
    key = n[:, 0] * 10007 + n[:, 1] * 101 + n[:, 2]
    _, kl = np.unique(key, return_inverse=True)
    out = np.full(fid.shape, -1, np.int32); ok = fid >= 0; out[ok] = kl[fid[ok]]
    return out


def geometrie(nr, a, obj, objp, R0_, VERD, rahmen_fn, TMc):
    """Rendert Zielteil (+ Gegenvariante fuer ROI) und Verdecker fuer ein Foto. -> dict oder None."""
    kp = FF.k_datei(objp, obj, R0_, nr)
    if not kp or not os.path.exists(kp): return None
    K = json.load(open(kp)); kk = K.get("kamera")
    if not kk: return None
    bild = glob.glob(os.path.join(R0_, obj["fotos_dir"], nr + "_*"))
    if not bild: return None
    im = cv2.imread(bild[0]); im, K = FD.foto_skalieren(im, K); kk = K["kamera"]
    im, _ = FF.foto_entzerren(im, kk); H, W = im.shape[:2]
    R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0_, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
    tr = rahmen_fn(kk)
    def rend(m):
        m = m.copy(); m.apply_translation(tr); return RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H)
    ziel, rest = TMc["haupt"]
    if ziel is None: return None
    dz, fz, _ = rend(ziel)
    dr = rend(rest)[0] if rest is not None else np.full((H, W), np.inf, np.float32)
    # Gegenvariante nur fuer ROI und gemeinsamen Ausschnitt
    z2 = TMc.get("gegen"); fin2 = None
    if z2 is not None:
        d2, f2, _ = rend(z2); fin2 = np.isfinite(d2)
    fin = np.isfinite(dz); vis2 = None
    if fin2 is not None: vis2 = fin2 & (d2 <= dr * 1.003 + 0.03)
    vis = fin & (dz <= dr * 1.003 + 0.03)                          # Verdeckung durch das uebrige Modell (wie teil_fotoform)
    verd_w = np.zeros((H, W), bool)
    if VERD is not None and "rahmen_verschiebung" in kk:
        ZL = max(2, int(round(12 * float(os.environ.get("RCPARK_FOTO_SKALA") or 1.0)))); zc = VERD.zkarte(R, t, f, cx, cy, W, H, zelle=ZL)
        verd_w = VERD.verdeckt(zc, np.where(fin, dz, np.nan), ZL, 0.5, 0.05, 10)
        # Rest-Pixel (Teil fehlt): Fotowolke vor der Szene dort -> Tiefe der Wolke-Lage unbekannt; Zelle gilt als verdeckt, wenn die Wolke nahe vor dem Teilrand liegt
    return dict(im=im, W=W, H=H, dz=dz, fz=fz, fin=fin, fin2=fin2, vis2=vis2, vis=vis & ~verd_w, dr=dr, verd_w=verd_w)


def flaechen_foto(nr, G, zielm, a, bd, ohne_cache=False):
    """Bewertung eines Fotos aus dem Geometriepaket G. -> Ergebniszeile oder Text (Grund)."""
    im, W, H = G["im"], G["W"], G["H"]
    uni = G["vis"] | (G["vis2"] if G["vis2"] is not None else False)   # Ausschnitt/ROI um die SICHTBAREN Teilpixel (aller Varianten)
    ys, xs = np.where(uni)
    if len(ys) < 400: return "Teil nicht im Bild"
    sicht = int(G["vis"].sum())
    if sicht < a.min_px: return f"zu wenig sichtbare Teilpixel ({sicht})"
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    bh, bw = y1 - y0, x1 - x0
    # ROI = Huelle der Teilsilhouette (alle Varianten) + Rand
    r_ = int(max(12, 0.10 * max(bh, bw)))
    huell = cv2.morphologyEx(uni.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_ + 1, 2 * r_ + 1)))
    roi = cv2.dilate(huell, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_ + 1, 2 * r_ + 1))) > 0
    # Ausschnitt +30 % Rand
    my, mx = int(0.3 * bh), int(0.3 * bw)
    cy0, cy1, cx0, cx1 = max(0, y0 - my - r_), min(H, y1 + my + r_), max(0, x0 - mx - r_), min(W, x1 + mx + r_)
    s = min(1.0, ARBEIT / max(cy1 - cy0, cx1 - cx0))
    crop = im[cy0:cy1, cx0:cx1]
    cw, ch = max(1, int(round(crop.shape[1] * s))), max(1, int(round(crop.shape[0] * s)))
    cs = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_AREA) if s < 1 else crop
    def klein(m, nearest=True):
        c = m[cy0:cy1, cx0:cx1]; return cv2.resize(c.astype(np.uint8), (cw, ch), interpolation=cv2.INTER_NEAREST) if s < 1 else c.astype(np.uint8)
    bf = glob.glob(os.path.join(R0, a.obj["fotos_dir"], nr + "_*"))[0]
    schl = json.dumps([os.path.basename(bf), os.path.getsize(bf), os.environ.get("RCPARK_FOTO_SKALA", "1"), [int(cy0), int(cy1), int(cx0), int(cx1)], ARBEIT, SAM_PAR, "sam-vit-large", METRIK[:2]], sort_keys=True)
    t0 = time.time(); M, sc, aus_cache = sam_masken(cs, schl, ohne_cache); t_sam = time.time() - t0
    # Modellflaechen im Arbeitsmassstab
    roi_k = klein(roi).astype(bool)
    vis_k = klein(G["vis"]).astype(bool) & roi_k
    verd_k = klein(G["verd_w"]).astype(bool)
    # uebriges Modell vor dem Zielteil-Bereich: dort ist die Sicht verstellt -> ungueltig. Verdeckung = Rest-Modell endlich (irgendwo im ROI) UND (Teil dort vorhanden aber dahinter ODER Teil fehlt)
    # Rest-Pixel (Teil fehlt): gueltig nur, wo auch das uebrige Modell nichts zeigt (sonst ist es kein Durchblick, sondern anderes Modell)
    rest_modell = klein(np.isfinite(G["dr"])).astype(bool)
    fin_k = klein(G["fin"]).astype(bool)
    verdeckt_ziel = fin_k & ~klein(G["vis"] | G["verd_w"]).astype(bool)          # Zielteil da, aber Modell davor
    kl = normalklassen(zielm, G["fz"]) if G["fz"] is not None else np.full((H, W), -1, np.int32)
    kl_k = cv2.resize(kl[cy0:cy1, cx0:cx1].astype(np.int32), (cw, ch), interpolation=cv2.INTER_NEAREST) if s < 1 else kl[cy0:cy1, cx0:cx1]
    # Randband: +-d um die Teilsilhouette (Ziel UND Gegenvariante). Grund: Rest-/Himmelsflaechen dominieren den Gesamt-IoU, der Formunterschied
    # (Treppe gegen Saegezahn, Bogen gegen Rechteck) liegt aber nur am Rand -> Hauptmass = Band, "voll" = ganze Huelle als Gegenprobe.
    vy, vx = np.where(G['vis'] | (G['vis2'] if G['vis2'] is not None else False)); vb = max(vy.max() - vy.min(), vx.max() - vx.min()) + 1
    d = max(3, int(round(0.05 * vb * s))); ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1)); band = np.zeros((ch, cw), np.uint8)
    for fm in (G["vis"], G["vis2"]):      # Band um die SICHTBARE Teilsilhouette (nicht um verdeckte Teile der Platte)
        if fm is None: continue
        fk_ = klein(fm); band |= (cv2.dilate(fk_, ke) - cv2.erode(fk_, ke)).astype(np.uint8)
    band = band > 0
    gueltig_voll = roi_k & ~verd_k & ~verdeckt_ziel
    Mv = M & gueltig_voll[None]
    def bewerten(gueltig):
        """-> (zeilen, iou_fl, iou_sil, Mk, gut, flaechen)"""
        flaechen = []; minpx = max(30, int(0.002 * gueltig.sum())); vis_g = vis_k & gueltig
        for c in np.unique(kl_k[vis_g & (kl_k >= 0)]):
            n, lab, st, _ = cv2.connectedComponentsWithStats((vis_g & (kl_k == c)).astype(np.uint8), 8)
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] >= minpx: flaechen.append((f"fl{len(flaechen)}", lab == i))
        # Rest = Teil fehlt hier (Loch/Hintergrund/Himmel; auch uebriges Modell dahinter): bewertet wird die Sicht DURCH das Teil, nicht das Modell dahinter
        rest = gueltig & ~fin_k
        if rest.sum() >= minpx:
            n, lab, st, _ = cv2.connectedComponentsWithStats(rest.astype(np.uint8), 8)
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] >= minpx: flaechen.append((f"rest{i}", lab == i))
        Mk = M & gueltig[None]; areaS = Mk.reshape(len(Mk), -1).sum(1) if len(Mk) else np.zeros(0, int)
        gut = np.where(areaS >= max(20, 0.005 * max(int(gueltig.sum()), 1)))[0]
        zeilen = []; tot = wsum = 0.0
        for nm, mk in flaechen:
            am = int(mk.sum()); best, bj = 0.0, -1
            for j in gut:
                inter = int((mk & Mk[j]).sum())
                if inter == 0: continue
                iou = inter / float(am + int(Mk[j].sum()) - inter)
                if iou > best: best, bj = iou, int(j)
            zeilen.append(dict(name=nm, px=am, iou=round(best, 3), sam=bj)); tot += best * am; wsum += am
        gm = vis_g; ag = max(int(gm.sum()), 1); bs = 0.0
        for j in gut:
            inter = int((gm & Mk[j]).sum())
            if inter: bs = max(bs, inter / float(ag + int(Mk[j].sum()) - inter))
        return zeilen, (tot / wsum if wsum else 0.0), bs, Mk, gut, flaechen, wsum
    gueltig = gueltig_voll & band
    zeilen, ifl, isil, Mk, gut, flaechen, wsum = bewerten(gueltig)
    if not zeilen: return "keine Modellflaechen"
    zv, iflv, isilv, _, gutv, _, wsv = bewerten(gueltig_voll)
    e = dict(iou_flaechen=round(ifl, 4), iou_silhouette=round(isil, 4), iou_flaechen_voll=round(iflv, 4), iou_silhouette_voll=round(isilv, 4),
             n_flaechen_modell=len(zeilen), n_flaechen_foto=int(len(gut)), px=int(round(wsum / (s * s))), px_arbeit=int(wsum), px_voll=int(round(wsv / (s * s))),
             sam_aus_cache=bool(aus_cache), sam_s=round(t_sam, 1), flaechen=zeilen, band_px_arbeit=int(d), crop=[int(cy0), int(cy1), int(cx0), int(cx1)])
    areaS = Mk.reshape(len(Mk), -1).sum(1) if len(Mk) else np.zeros(0, int)
    if a.bilder:
        os.makedirs(bd, exist_ok=True)
        rng = np.random.RandomState(7); pal = rng.randint(40, 255, (max(len(M), 1) + 1, 3)).astype(np.uint8)
        # SAM-Partition: kleinste Maske zuletzt malen
        sam_img = cs.copy() // 2
        for j in np.argsort(-areaS)[:200]:
            if areaS[j] < 20: continue
            sam_img[Mk[j]] = (0.4 * cs[Mk[j]] + 0.6 * pal[j]).astype(np.uint8)
        sam_img[~gueltig] = (sam_img[~gueltig] * 0.35).astype(np.uint8)
        mod_img = np.zeros_like(cs); mod_img[:] = (30, 30, 30)
        pm = np.array([(0, 160, 255), (60, 200, 60), (255, 120, 40), (200, 60, 200), (60, 220, 220), (160, 160, 255)], np.uint8)
        zu_img = cs.copy() // 3
        for k, (nm, mk) in enumerate(flaechen):
            col = pm[k % len(pm)]; mk = mk & gueltig
            mod_img[mk] = col
            z = next((z for z in zeilen if z["name"] == nm), None)
            if z and z["sam"] >= 0:
                sj = Mk[z["sam"]]; zu_img[sj & mk] = (0, 255, 0); zu_img[mk & ~sj] = (0, 0, 255); zu_img[sj & ~mk & gueltig] = (0, 200, 255)
        kop = lambda im_, tx: (cv2.putText(im_, tx, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2), im_)[1]
        sheet = np.hstack([kop(sam_img.copy(), f"SAM {len(gut)} Masken"), kop(mod_img, f"Modell {len(zeilen)} Flaechen"),
                           kop(zu_img, f"iou_fl {e['iou_flaechen']:.3f} sil {e['iou_silhouette']:.3f} (gruen=gleich rot=nur Modell gelb=nur SAM)")])
        fn = os.path.join(bd, f"{a.nur}_{nr}{('_' + a.etikett) if a.etikett else ''}.jpg"); cv2.imwrite(fn, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88]); e["bild"] = fn
    return e


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True); ap.add_argument("--nur", required=True)
    ap.add_argument("--fotos", required=True, help="Liste A,B,C oder auto:N (N Fotos mit den meisten sichtbaren Teilpixeln)")
    ap.add_argument("--aus"); ap.add_argument("--bilder", action="store_true"); ap.add_argument("--bilder_dir"); ap.add_argument("--etikett", default="")
    ap.add_argument("--bereich_von", help="Teile-Verzeichnis der GEGENVARIANTE: ROI/Ausschnitt gemeinsam (Pflicht fuer Vorher/Nachher-Vergleich); Verdecker = uebrige Teile aus --teile_dir")
    ap.add_argument("--min_px", type=int, default=300); ap.add_argument("--ohne_cache", action="store_true", help="SAM neu rechnen, Cache nicht lesen/schreiben (Determinismustest)")
    ap.add_argument("--wolke_verdeckung", choices=["an", "aus"], default=os.environ.get("RCPARK_WOLKE_VERDECKUNG", "an")); ap.add_argument("--wolke")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); a.obj = obj
    stl = os.path.join(R0, obj["stl"])
    bd = a.bilder_dir or "/media/oem/scan/rc-park_tmp/flaechen_bilder"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import teil_fotoform as TF
    ziel, rest = lade_teile(a.teile_dir, a.nur, obj)
    if ziel is None: print("Teil fehlt in", a.teile_dir); return {"fehler": "teil fehlt"}
    gegen = None
    if a.bereich_von:
        gl = [lade_teile(d_, a.nur, obj)[0] for d_ in a.bereich_von.split(",")]; gl = [g_ for g_ in gl if g_ is not None]
        gegen = trimesh.util.concatenate(gl) if gl else None      # mehrere Gegenvarianten (Komma): ROI/Band = Vereinigung aller Silhouetten
    VERD = None
    if a.wolke_verdeckung == "an":
        import wolke_verdeckung as WV
        wp = a.wolke or obj.get("kreis", {}).get("wolke") or "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy"
        if os.path.exists(wp): VERD = WV.Verdecker(np.load(wp, mmap_mode="r"))
    cache_rahmen = {}
    def rahmen_fn(kk):
        k = json.dumps(kk.get("rahmen_verschiebung"))
        if k not in cache_rahmen: cache_rahmen[k] = TF.rahmen(stl, obj, kk)
        return cache_rahmen[k]
    TMc = {"haupt": (ziel, rest), "gegen": gegen}
    if a.fotos.startswith("auto:"):
        n = int(a.fotos[5:]); alle = sorted(os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json")))
        sc_ = []
        for nr in alle:
            try:
                G = geometrie(nr, a, obj, objp, R0, VERD, rahmen_fn, TMc)
            except Exception as ex:
                print("auto", nr, "Fehler", str(ex)[:80]); continue
            if G is not None: sc_.append((int(G["vis"].sum()), nr)); print("auto", nr, sc_[-1][0], flush=True)
            del G
        sc_.sort(reverse=True); fotos = [nr for _, nr in sc_[:n]]; print("gewaehlt:", fotos, flush=True)
    else: fotos = a.fotos.split(",")
    erg = {"objekt": a.objekt, "teil": a.nur, "teile_dir": a.teile_dir, "bereich_von": a.bereich_von, "metrik": METRIK, "fotos": {}, "sam": "facebook/sam-vit-large"}
    import torch
    for nr in fotos:
        t0 = time.time()
        for versuch in range(40):      # GPU parallel zum Kreis: bei vollem Speicher warten und wiederholen (Nutzer/Koordinator 11.11.)
            try:
                G = geometrie(nr, a, obj, objp, R0, VERD, rahmen_fn, TMc)
                if G is None: e = "keine Kamera/Bild/Teil"; break
                e = flaechen_foto(nr, G, ziel, a, bd, a.ohne_cache); break
            except (torch.OutOfMemoryError, RuntimeError) as ex:
                if "out of memory" not in str(ex).lower(): raise
                e = "GPU-Speicher dauerhaft voll"; G = None; torch.cuda.empty_cache(); print(f"Foto {nr}: GPU voll, Versuch {versuch + 1}, warte 30 s", flush=True); time.sleep(30)
        if isinstance(e, dict): e["laufzeit_s"] = round(time.time() - t0, 1); e["vram_max_mib"] = int(torch.cuda.max_memory_allocated() / 2**20)
        erg["fotos"][nr] = e
        print(f"Foto {nr}: " + (f"iou_fl {e['iou_flaechen']:.3f} sil {e['iou_silhouette']:.3f} Fl {e['n_flaechen_modell']}/{e['n_flaechen_foto']} px {e['px']} t {e['laufzeit_s']}s" if isinstance(e, dict) else e), flush=True)
    je = [v for v in erg["fotos"].values() if isinstance(v, dict)]
    if je:
        w = sum(v["px"] for v in je)
        erg["_gesamt"] = {"iou_flaechen": round(sum(v["iou_flaechen"] * v["px"] for v in je) / w, 4), "iou_silhouette": round(sum(v["iou_silhouette"] * v["px"] for v in je) / w, 4),
                          "iou_flaechen_voll": round(sum(v["iou_flaechen_voll"] * v["px_voll"] for v in je) / sum(v["px_voll"] for v in je), 4),
                          "px": w, "fotos": len(je), "vram_max_mib": max(v["vram_max_mib"] for v in je)}
        print("GESAMT", erg["_gesamt"], flush=True)
    if a.aus: json.dump(erg, open(a.aus, "w"), ensure_ascii=False, indent=1)
    return erg


if __name__ == "__main__":
    main()
