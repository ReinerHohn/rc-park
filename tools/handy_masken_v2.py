#!/usr/bin/env python3
"""handy_masken_v2.py - Handy-Masken v2 (Register DI). v1 (handy_masken.py) bleibt unveraendert.
Aenderungen gegenueber v1, alle aus den Segmentierungsklassen (ADE20K id2label) bzw. OWLv2 abgeleitet, keine Objekt-Festwerte:
 (a) boat/ship/animal entfallen (v1: nur Fehlalarme auf Gewoelberippen). 'box' nur mit Bodenkontakt.
 (b) 'person' nur mit Bodenkontakt: Komponente (Zusammenhangsgebiet der Klasse) wird unten (Fuss-Band) auf Bodenklassen (floor road sidewalk earth path
     grass sand field) gegen Fassadenklassen (building house wall windowpane door column ceiling bannister tower) geprueft. Statuen am Gebaeude haben
     unter sich Fassade/Balkon, nie Boden -> bleiben frei. Fuesse von anderen bewegten Klassen verdeckt (kaum Nicht-Dyn-Pixel im Band) = stehend.
     'Flecken': kleine person/box-Komponente, die ringsum fast nur Boden hat (Pflasterstruktur) -> verworfen.
 (c) Zusatz OWLv2 (google/owlv2-base-patch16-ensemble, Apache-2.0, GPU fp16): Textabfragen white tarp / market stall canopy / tent / parasol, nur Boxen mit
     Score >= --owl_score; Plausibilitaet: Boden unter/in der Box. SAM2 (Segmentierung der Box) ist NICHT im HF-Cache (nur sam-vit-base, SAM1) und es wird
     aus Platzgruenden (Datenplatte ~10 GB frei) nichts nachgeladen -> Box wird mit dem Segformer-Schnitt gefuellt: Box ohne Himmel/Boden/Fassadenpixel
     (Plane vor Fassade bleibt dadurch Rest-Unsicherheit).
Mehrfachverarbeitung: GPU im Hauptprozess (Segformer + OWLv2, Batch), Komponenten-Nachbearbeitung + Maskenschreiben in einem multiprocessing-Pool (spawn).
Ausgabe <ausgabe>/<serie>/<bild>.png (255 benutzen/0 ignorieren) + bericht.json je Serie mit Komponenten (klasse, bbox, Bodenanteil, Entscheidung, Grund).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/handy_masken_v2.py <bilder_ordner>... --ausgabe DIR [--max N]
Lizenz: SegFormer s. modelle/LIZENZ_WERKZEUGE.md; OWLv2 Apache-2.0 (Eintrag 2026-11-06 DI)."""
import sys, os, glob, json, re, argparse, time
import numpy as np, cv2

IMMER = ("car", "bus", "truck", "van", "minibike", "bicycle")      # bewegt, kein Bodentest (Fahrzeuge stehen auch auf Auffahrten/Rampen)
BODENPFLICHT = ("person", "box")                                   # nur mit Bodenkontakt
MARKT = ("tent", "booth", "canopy")                                # Zelt/Stand: immer (wie v1)
BODEN = ("floor", "road", "sidewalk", "earth", "path", "grass", "sand", "field", "stairs")
FASSADE = ("building", "house", "wall", "windowpane", "door", "column", "ceiling", "bannister", "tower")
HIMMEL = ("sky",)
MODELL = "nvidia/segformer-b4-finetuned-ade-512-512"
OWL = "google/owlv2-base-patch16-ensemble"
OWL_ABFRAGEN = ["white tarp", "market stall canopy", "tent", "parasol"]
P = dict(min_flaeche=0.0003,   # Anteil Bildflaeche: kleinere Komponenten sind Rauschen (Merkmalsverlust vernachlaessigbar)
         band=0.08,            # Tiefe Fuss-Band relativ zur Komponentenhoehe (mind. 3 px)
         fuss=0.15,            # Spalten mit tiefstem Punkt im untersten Anteil der Komponentenhoehe zaehlen als Fuss
         boden_min=0.08,       # Bodenanteil im Fuss-Fenster (nur Nicht-Dyn-Pixel) fuer 'steht'; Statuen messen 0,0 (nur Wand/Fenster/Balkon), Passanten 0,13-0,5 (Segformer labelt Boden am Gebaeudesockel teils 'building')
         verdeckt=0.2,         # Anteil Nicht-Dyn-Pixel im Band, darunter: Fuesse verdeckt -> steht
         fleck_ring=0.85, fleck_flaeche=0.01,
         owl_score=0.3, owl_boden=0.5, owl_max=0.5)
ANALYSE_B = 1000               # Breite der Analyse-Segmentkarte

def namen(id2label):
    return {int(k): v.split(",")[0].strip() for k, v in id2label.items()}

def serie_von(name):
    m = re.match(r"h_([a-z])_\d+", name); return m.group(1) if m else "x"

def ids_von(nm, liste):
    return [k for k, v in nm.items() if v in liste]

def kontext(seg, comp, dyn, boden, fassade, h):
    """Fuss-Band unter der Komponente (spaltenweise nach unten), Ring ringsum. Liefert Bodenanteil/Fassadenanteil (nur Nicht-Dyn-Pixel)."""
    x, y, w, hh = h
    t = max(3, int(round(P["band"] * hh)))
    # Fuss-Fenster: Zeilen vom (tiefsten Komponentenpunkt - fuss*hoehe) bis t Zeilen darunter, Spalten bbox +- 0.5 Breite, ohne die Komponente selbst.
    # (Direkt unter den Fuessen ist Segformer oft falsch - Kleidung/Schatten als 'building' -, seitlich auf Fuss-Hoehe liegt der Boden zuverlaessiger.
    #  Statue am Obergeschoss: seitlich/unten nur Wand, Fenster, Balkon.)
    H_, W_ = comp.shape; ye = y + hh - 1
    band = np.zeros_like(comp, bool)
    band[max(0, int(ye - P["fuss"] * hh)):min(H_, ye + 1 + t), max(0, int(x - 0.5 * w)):min(W_, int(x + 1.5 * w))] = True
    band &= (comp == 0)
    r = max(3, int(round(0.25 * np.sqrt(comp.sum()))))
    ring = (cv2.dilate(comp, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0) & (comp == 0)
    def anteile(m):
        n = int(m.sum())
        if n == 0: return 0, 0.0, 0.0, 0.0
        nd = m & ~dyn; k = int(nd.sum())
        if k == 0: return n, 0.0, 0.0, 0.0
        return n, k / n, float((boden[seg][nd]).sum() / k), float((fassade[seg][nd]).sum() / k)
    return anteile(band), anteile(ring)

def komponenten(seg, nm, cls_ids):
    """seg: (h,w) uint8 Klassenkarte (Analyse-Aufloesung). Liefert Liste Dicts mit Maske, Entscheidung."""
    h, w = seg.shape
    boden_lut = np.zeros(256, bool); boden_lut[ids_von(nm, BODEN)] = True
    fass_lut = np.zeros(256, bool); fass_lut[ids_von(nm, FASSADE)] = True
    dyn_all = np.isin(seg, list(cls_ids["alle"]))
    res = []
    for c in cls_ids["alle"]:
        name = nm[c]
        if name in ("boat", "ship", "animal"): continue
        m = (seg == c).astype(np.uint8)
        if not m.any(): continue
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        for i in range(1, n):
            x, y, bw, bh, a = [int(v) for v in st[i]]
            if a < P["min_flaeche"] * h * w: continue
            comp = (lab == i).astype(np.uint8)
            rec = dict(klasse=name, bbox=[x, y, bw, bh], flaeche=round(a / (h * w), 5), behalten=True, grund="immer")
            if name in BODENPFLICHT:
                band, ring = kontext(seg, comp, dyn_all, boden_lut, fass_lut, (x, y, bw, bh))
                nb, nd_b, g_b, f_b = band; nr, nd_r, g_r, f_r = ring
                rec.update(band_boden=round(g_b, 3), band_fassade=round(f_b, 3), band_nichtdyn=round(nd_b, 3), ring_boden=round(g_r, 3), ring_fassade=round(f_r, 3))
                if a / (h * w) < P["fleck_flaeche"] and g_r >= P["fleck_ring"] and nr > 0:
                    rec.update(behalten=False, grund="fleck (ringsum Boden)")
                elif y + bh >= h - 2:
                    rec.update(behalten=True, grund="steht (Fuesse am unteren Bildrand: Objekt nahe der Kamera)")
                elif nb < 3 or nd_b < P["verdeckt"]:
                    rec.update(behalten=True, grund="steht (Fuesse von anderen bewegten Klassen verdeckt)")
                elif g_b >= P["boden_min"]:
                    rec.update(behalten=True, grund="steht (Bodenkontakt)")
                else:
                    rec.update(behalten=False, grund="kein Bodenkontakt (haengt an Bauwerk)" if name == "person" else "kein Bodenkontakt")
            res.append((rec, comp))
    return res

def owl_flaechen(seg, nm, boxen, h, w, sx):
    """OWLv2-Boxen (Vollbildkoord.) -> Analyse-Aufloesung; Segformer-Schnitt. Rueckgabe Liste (rec, maske)."""
    boden_lut = np.zeros(256, bool); boden_lut[ids_von(nm, BODEN)] = True
    schnitt = np.zeros(256, bool); schnitt[ids_von(nm, BODEN + HIMMEL)] = True   # Fassade bleibt im Schnitt: Plane liegt oft als wall/building segmentiert, Box-Rand kann Fassade streifen (Rest-Unsicherheit)
    out = []
    for (x0, y0, x1, y1, sc, q) in boxen:
        x0, y0, x1, y1 = [int(round(v * sx)) for v in (x0, y0, x1, y1)]
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, w), min(y1, h)
        if x1 - x0 < 4 or y1 - y0 < 4: continue
        fl = (x1 - x0) * (y1 - y0) / (h * w)
        rec = dict(klasse="owl:" + q, bbox=[x0, y0, x1 - x0, y1 - y0], flaeche=round(fl, 5), score=round(float(sc), 3), behalten=False)
        if fl > P["owl_max"]: rec["grund"] = "Box zu gross (> %.0f %% Bild)" % (100 * P["owl_max"]); out.append((rec, None)); continue
        reg = boden_lut[seg[y1:, x0:x1]] if y1 < h else np.zeros((0, x1 - x0), bool)
        g = float(reg.any(0).mean()) if reg.size else 0.0   # Anteil der Box-Spalten, unter denen irgendwo Boden folgt (Plane steht ueber Boden, Ware/Fahrzeug darunter erlaubt)
        rec["boden_unter"] = round(g, 3)
        if g < P["owl_boden"]: rec["grund"] = "kein Boden unter/in der Box"; out.append((rec, None)); continue
        m = np.zeros((h, w), np.uint8); m[y0:y1, x0:x1] = (~schnitt[seg[y0:y1, x0:x1]]).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        rec.update(behalten=bool(m.any()), grund="OWLv2-Box minus Himmel/Boden", gefuellt=round(float(m[y0:y1, x0:x1].mean()), 3))
        out.append((rec, m))
    return out

def nachbearbeiten(arg):
    """Worker: Komponenten bewerten, Maske voll aufloesen, PNG schreiben."""
    pfad_aus, seg, shape, boxen, nm, cls_ids, puffer = arg
    H, W = shape; h, w = seg.shape; sx = w / W
    recs = komponenten(seg, nm, cls_ids)
    recs += owl_flaechen(seg, nm, boxen, h, w, sx)
    dyn = np.zeros((h, w), np.uint8)
    for rec, m in recs:
        if rec["behalten"] and m is not None:
            if not rec["klasse"].startswith("owl:"):   # Loecher im Fahrzeug (Segformer markiert nur den Rand): ausfuellen
                cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); m = np.zeros_like(m); cv2.drawContours(m, [cv2.convexHull(np.vstack(cs))] if (rec["klasse"] in ("car", "bus", "truck", "van") and cs) else cs, -1, 1, -1)   # Fahrzeuge sind im Bild annaehernd konvex: Huelle fuellt auch Loecher am Bildrand
            dyn |= m
    dyn = cv2.resize(dyn, (W, H), interpolation=cv2.INTER_NEAREST)
    if puffer > 0: dyn = cv2.dilate(dyn, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * puffer + 1, 2 * puffer + 1)))
    mask = np.where(dyn > 0, 0, 255).astype(np.uint8)
    cv2.imwrite(pfad_aus, mask)
    return pfad_aus, round(float((mask == 0).mean()), 4), [r for r, _ in recs]

def seg_analyse(model, ims, breite, dev, fp16, mean, std, aw):
    import torch
    H, W = ims[0].shape[:2]; s = breite / W; h2 = int(round(H * s / 32)) * 32; w2 = int(round(breite / 32)) * 32
    x = np.stack([cv2.resize(cv2.cvtColor(i, cv2.COLOR_BGR2RGB), (w2, h2), interpolation=cv2.INTER_AREA) for i in ims]).astype(np.float32) / 255.0
    x = torch.from_numpy((x - mean) / std).permute(0, 3, 1, 2).contiguous().to(dev)
    if fp16: x = x.half()
    ah = int(round(H * aw / W))
    with torch.no_grad():
        lg = model(pixel_values=x).logits
        return [torch.nn.functional.interpolate(lg[j:j + 1], size=(ah, aw), mode="bilinear", align_corners=False).argmax(1)[0].to(torch.uint8).cpu().numpy() for j in range(lg.shape[0])]

def owl_laden(dev):
    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL); mod = Owlv2ForObjectDetection.from_pretrained(OWL, torch_dtype=torch.float16).eval().to(dev)
    tx = proc.tokenizer(OWL_ABFRAGEN, padding="max_length", max_length=16, return_tensors="pt")
    return mod, tx["input_ids"].to(dev), tx["attention_mask"].to(dev)

def owl_boxen(owl, ims, dev, schwelle):
    """Batch OWLv2: Bild quadratisch auffuellen (grau), 960 px, CLIP-Normierung. Rueckgabe je Bild Liste (x0,y0,x1,y1,score,abfrage) nach NMS."""
    import torch, torchvision
    mod, ids, am = owl; Q = ids.shape[0]; B = len(ims)
    mean = np.array([0.48145466, 0.4578275, 0.40821073], np.float32); std = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
    xs = []; sk = []
    for im in ims:
        H, W = im.shape[:2]; S = max(H, W); sq = np.full((S, S, 3), 0.5, np.float32); sq[:H, :W] = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        xs.append(cv2.resize(sq, (960, 960), interpolation=cv2.INTER_AREA)); sk.append(S)
    x = torch.from_numpy((np.stack(xs) - mean) / std).permute(0, 3, 1, 2).contiguous().to(dev).half()
    with torch.no_grad():
        o = mod(input_ids=ids.repeat(B, 1), attention_mask=am.repeat(B, 1), pixel_values=x)
        sc = torch.sigmoid(o.logits.float()); bx = o.pred_boxes.float()
    res = []
    for j in range(B):
        s, qi = sc[j].max(-1); k = s >= schwelle; b = bx[j][k]; ss = s[k]; qq = qi[k]
        if len(ss) == 0: res.append([]); continue
        xyxy = torch.stack([b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2], 1) * sk[j]
        keep = torchvision.ops.nms(xyxy, ss, 0.3)
        res.append([(*[float(v) for v in xyxy[i]], float(ss[i]), OWL_ABFRAGEN[int(qq[i])]) for i in keep])
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner", nargs="+"); ap.add_argument("--ausgabe", required=True)
    ap.add_argument("--breite", type=int, default=1536); ap.add_argument("--batch", type=int, default=2); ap.add_argument("--puffer", type=int, default=30)
    ap.add_argument("--max", type=int); ap.add_argument("--owl_score", type=float, default=P["owl_score"]); ap.add_argument("--kein_owl", action="store_true")
    ap.add_argument("--nur", help="Komma-Liste Bildnamen (Teilmenge)"); ap.add_argument("--prozesse", type=int, default=min(12, os.cpu_count() or 4))
    a = ap.parse_args(); P["owl_score"] = a.owl_score
    import multiprocessing as mp
    ctx = mp.get_context("spawn"); pool = ctx.Pool(a.prozesse)   # vor CUDA-Init
    import torch
    from transformers import SegformerForSemanticSegmentation
    dev = "cuda" if torch.cuda.is_available() else "cpu"; fp16 = dev == "cuda"
    model = SegformerForSemanticSegmentation.from_pretrained(MODELL).eval().to(dev)
    if fp16: model = model.half()
    nm = namen(model.config.id2label)
    cls_ids = dict(alle=sorted(ids_von(nm, IMMER + BODENPFLICHT + MARKT)))
    print("Klassen (aus id2label):", {c: nm[c] for c in cls_ids["alle"]}, "\nBoden:", {c: nm[c] for c in ids_von(nm, BODEN)}, "\nFassade:", {c: nm[c] for c in ids_von(nm, FASSADE)}, flush=True)
    owl = None if a.kein_owl else owl_laden(dev)
    mean = np.array([0.485, 0.456, 0.406], np.float32); std = np.array([0.229, 0.224, 0.225], np.float32)
    fs = sorted(sum((glob.glob(os.path.join(o, "*.jpg")) + glob.glob(os.path.join(o, "*.png")) for o in a.ordner), []))
    if a.nur: nur = set(a.nur.split(",")); fs = [f for f in fs if os.path.basename(f) in nur or os.path.splitext(os.path.basename(f))[0] in nur]
    if a.max: fs = fs[:a.max]
    gruppen = {}
    for f in fs:
        im = cv2.imread(f)
        if im is None: print("[skip]", f); continue
        gruppen.setdefault(im.shape[:2], []).append(f)
    jobs = []; t0 = time.time(); n = 0; rep = {}
    for shp, lst in gruppen.items():
        for b in range(0, len(lst), a.batch):
            pf = lst[b:b + a.batch]; ims = [cv2.imread(f) for f in pf]
            try:
                segs = seg_analyse(model, ims, a.breite, dev, fp16, mean, std, ANALYSE_B); torch.cuda.empty_cache()
                boxen = owl_boxen(owl, ims, dev, a.owl_score) if owl else [[] for _ in ims]; torch.cuda.empty_cache()
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache(); print("  OOM Batch", len(ims), "-> einzeln", flush=True)
                segs = sum((seg_analyse(model, [i], a.breite, dev, fp16, mean, std, ANALYSE_B) for i in ims), []); boxen = sum((owl_boxen(owl, [i], dev, a.owl_score) for i in ims), []) if owl else [[] for _ in ims]
            for f, seg, bx in zip(pf, segs, boxen):
                nmx = os.path.basename(f); ser = serie_von(nmx); od = os.path.join(a.ausgabe, ser); os.makedirs(od, exist_ok=True)
                jobs.append((nmx, ser, pool.apply_async(nachbearbeiten, ((os.path.join(od, os.path.splitext(nmx)[0] + ".png"), seg, shp, bx, nm, cls_ids, a.puffer),))))
            n += len(pf); print(f"  GPU {n}/{len(fs)} {time.time() - t0:.0f} s", flush=True)
    for nmx, ser, j in jobs:
        _, anteil, recs = j.get(); rep.setdefault(ser, {})[nmx] = dict(maskiert=anteil, komponenten=recs)
    pool.close(); pool.join()
    for ser, d in rep.items():
        json.dump(dict(version="v2", segformer=MODELL, owl=None if a.kein_owl else OWL, abfragen=OWL_ABFRAGEN, parameter=P, breite=a.breite, puffer=a.puffer,
                       maskiert_anteil={k: v["maskiert"] for k, v in d.items()}, komponenten={k: v["komponenten"] for k, v in d.items()}),
                  open(os.path.join(a.ausgabe, ser, "bericht.json"), "w"), indent=1)
    v = np.array([x["maskiert"] for d in rep.values() for x in d.values()])
    if len(v): print(f"{len(v)} Bilder, maskiert Mittel {100 * v.mean():.1f} %, Maximum {100 * v.max():.1f} %, {time.time() - t0:.0f} s, GPU-Spitze {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")

if __name__ == "__main__":
    main()
