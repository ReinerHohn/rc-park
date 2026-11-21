#!/usr/bin/env python3
"""handy_masken.py - GPU-Masken fuer bewegte/nicht zum Bauwerk gehoerende Dinge in Handyfotos (Personen, Fahrzeuge, Fahrraeder, Marktstaende/Zelte, Kisten).
Wie video_masken.py (nicht geaendert), aber: CUDA fp16, Batch gleich grosser Bilder, Segmentierung bei --breite (Standard 1536, nicht 960).
Klassen werden aus id2label der Modellkarte (nvidia/segformer-b4-finetuned-ade-512-512, ADE20K-150) per Namensliste abgeleitet und im Bericht genannt:
  BEWEGT   person car bus truck van minibike bicycle boat ship animal
  MARKT    tent booth canopy box   (Zelte, Staende, Kisten)
  GRUEN    tree plant (seit 21.11.2026 Standard AN; --kein_gruen)
  NICHT ERFASST: Strassenbahn - ADE20K-150 hat keine Klasse dafuer (wird bus oder building); zweites Netz mit Schienenfahrzeug-Klasse noetig (offen, Lizenz pruefen)
  OPTIONAL awning (--markise): Markisen koennen Bauwerksteil sein -> Standard AUS
Ausgabe <ausgabe>/<serie>/<bildname>.png (255 benutzen, 0 ignorieren, COLMAP) + <ausgabe>/<serie>/bericht.json (Anteil maskiert, Klassenanteile je Bild).
Serie = Buchstabe aus h_<serie>_NN.jpg (sonst Unterordnername). GRENZEN: Segmentierung fehlerhaft (Transporter evtl. 'building', Stand als 'wall'); Schatten bleiben; Himmel nicht maskiert.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/handy_masken.py <bilder_ordner>... --ausgabe DIR [--breite 1536] [--batch 4] [--max N]
Lizenz SegFormer: siehe modelle/LIZENZ_WERKZEUGE.md (Nachtrag 2026-11-06)."""
import sys, os, glob, json, re, argparse, time
import numpy as np, cv2
BEWEGT = ("person", "car", "bus", "truck", "van", "minibike", "bicycle", "boat", "ship", "animal")
MARKT = ("tent", "booth", "canopy", "box")
GRUEN = ("tree", "plant")   # 21.11.2026 (Nutzer am Maskenbild Martinstor: "den Baum gar nicht"): Baeume/Pflanzen verdecken das Bauwerk und sehen je Jahreszeit anders aus -> Standard AN, --kein_gruen schaltet ab
MODELL = "nvidia/segformer-b4-finetuned-ade-512-512"

def klassen_ids(id2label, markise=False, gruen=True):
    """ADE20K-Labelzeilen sind 'a, b': erster Name muss GENAU passen (kein Teilstring wie 'carpet')."""
    namen = BEWEGT + MARKT + (("awning",) if markise else ()) + (GRUEN if gruen else ())
    return {int(k): v for k, v in id2label.items() if v.split(",")[0].strip() in namen}

def serie_von(name, ordner):
    m = re.match(r"h_([a-z])_\d+", name)
    return m.group(1) if m else os.path.basename(os.path.dirname(os.path.abspath(os.path.join(ordner, name)))) or "x"

def maske_aus_seg(seg, ids, puffer):
    dyn = np.isin(seg, list(ids)).astype(np.uint8)
    if puffer > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * puffer + 1, 2 * puffer + 1)); dyn = cv2.dilate(dyn, k)
    return np.where(dyn > 0, 0, 255).astype(np.uint8)

def segmentiere(model, proc_mean, proc_std, ims, breite, dev, fp16):
    """ims: Liste BGR gleicher Groesse -> Liste Segmentkarten (H,W) int, Logits auf Bildgroesse hochgerechnet (GPU)."""
    import torch
    H, W = ims[0].shape[:2]; s = breite / W; h2 = int(round(H * s / 32)) * 32; w2 = int(round(breite / 32)) * 32
    x = np.stack([cv2.resize(cv2.cvtColor(i, cv2.COLOR_BGR2RGB), (w2, h2), interpolation=cv2.INTER_AREA) for i in ims]).astype(np.float32) / 255.0
    x = torch.from_numpy((x - proc_mean) / proc_std).permute(0, 3, 1, 2).contiguous().to(dev)
    if fp16: x = x.half()
    with torch.no_grad():
        lg = model(pixel_values=x).logits
        out = []
        for j in range(lg.shape[0]):
            up = torch.nn.functional.interpolate(lg[j:j + 1], size=(H, W), mode="bilinear", align_corners=False)
            out.append(up.argmax(1)[0].cpu().numpy())
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner", nargs="+"); ap.add_argument("--ausgabe", required=True)
    ap.add_argument("--breite", type=int, default=1536); ap.add_argument("--batch", type=int, default=4); ap.add_argument("--puffer", type=int, default=30)
    ap.add_argument("--max", type=int); ap.add_argument("--markise", action="store_true"); ap.add_argument("--kein_gruen", action="store_true"); ap.add_argument("--cpu", action="store_true"); ap.add_argument("--modell", default=MODELL); ap.add_argument("--kein_fp16", action="store_true")
    a = ap.parse_args()
    import torch
    from transformers import SegformerForSemanticSegmentation
    dev = "cpu" if a.cpu or not torch.cuda.is_available() else "cuda"; fp16 = dev == "cuda" and not a.kein_fp16
    model = SegformerForSemanticSegmentation.from_pretrained(a.modell).eval().to(dev)
    if fp16: model = model.half()
    ids = klassen_ids(model.config.id2label, a.markise, not a.kein_gruen); print("maskierte Klassen (aus id2label):", ids, flush=True)
    mean = np.array([0.485, 0.456, 0.406], np.float32); std = np.array([0.229, 0.224, 0.225], np.float32)
    fs = sorted(sum((glob.glob(os.path.join(o, "*.jpg")) + glob.glob(os.path.join(o, "*.png")) for o in a.ordner), []))
    if a.max: fs = fs[:a.max]
    gruppen = {}
    for f in fs:
        im = cv2.imread(f)
        if im is None: print("[skip]", f); continue
        gruppen.setdefault(im.shape[:2], []).append(f)
    rep = {}; t0 = time.time(); n = 0
    for shp, lst in gruppen.items():
        for b in range(0, len(lst), a.batch):
            pf = lst[b:b + a.batch]; ims = [cv2.imread(f) for f in pf]
            segs = None
            for bb, bt in ((a.breite, a.batch), (a.breite, 1), (int(a.breite * 0.75), 1)):   # OOM-Leiter: Batch 1, dann kleinere Breite (im Bericht vermerkt)
                try:
                    segs = sum((segmentiere(model, mean, std, ims[i:i + bt], bb, dev, fp16) for i in range(0, len(ims), bt)), []); break
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache(); print("  OOM bei", bb, bt, flush=True); abw = True
            for f, seg in zip(pf, segs):
                nm = os.path.basename(f); ser = serie_von(nm, os.path.dirname(f)); od = os.path.join(a.ausgabe, ser); os.makedirs(od, exist_ok=True)
                m = maske_aus_seg(seg, ids, a.puffer); cv2.imwrite(os.path.join(od, os.path.splitext(nm)[0] + ".png"), m)
                kl = {v.split(",")[0]: round(float((seg == k).mean()), 4) for k, v in ids.items() if (seg == k).any()}
                rep.setdefault(ser, {})[nm] = dict(maskiert=round(float((m == 0).mean()), 4), klassen=kl)
            n += len(pf)
            if (n // a.batch) % 5 == 0: print(f"  {n}/{len(fs)} {time.time() - t0:.0f} s", flush=True)
    for ser, d in rep.items():
        json.dump(dict(modell=a.modell, klassen=ids, breite=a.breite, puffer=a.puffer, fp16=fp16, geraet=dev, maskiert_anteil={k: v["maskiert"] for k, v in d.items()}, klassenanteile={k: v["klassen"] for k, v in d.items()}),
                  open(os.path.join(a.ausgabe, ser, "bericht.json"), "w"), indent=1)
    v = np.array([x["maskiert"] for d in rep.values() for x in d.values()])
    if len(v): print(f"{len(v)} Bilder, maskiert Mittel {100 * v.mean():.1f} %, Maximum {100 * v.max():.1f} %, {time.time() - t0:.0f} s, GPU-Spitze {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB" if dev == "cuda" else f"{len(v)} Bilder {time.time() - t0:.0f} s")

if __name__ == "__main__":
    main()
