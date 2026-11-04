#!/usr/bin/env python3
"""video_masken.py - Masken fuer BEWEGTE Dinge (Personen, Fahrzeuge, Strassenbahn, Fahrraeder, Tiere) in Video-Frames, damit SfM nur auf der festen Szene rechnet (Plan M-Quelle Sued, F8y3lNgia5c).
Semantische Segmentierung (SegFormer-B4 ADE20K, wie gebaeude_segment.py; Gewichte nvidia/segformer-b4-finetuned-ade-512-512, Lizenz laut Modellkarte: pruefen vor Verkauf -> LIZENZ_WERKZEUGE),
CPU, Bild vor dem Netz auf --breite (960) verkleinert (Vollbild-Logits waeren ~5 GB), Maske danach per Nearest auf die Framegroesse; bewegte Klassen werden um --puffer px erweitert.
Ausgabe je Frame <ausgabe>/<clip>/<frame>.png (255 = benutzen, 0 = ignorieren, COLMAP-Konvention wie video_sfm.py) und <ausgabe>/<clip>/bericht.json (Anteil maskiert je Frame).
GRENZEN: Segmentierung ist nicht fehlerfrei (Strassenbahn kann als 'bus'/'van'/'building' erscheinen); Schattenwurf und Spiegelungen bleiben; Himmel wird NICHT maskiert (keine Merkmale dort).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/video_masken.py <frames_wurzel> <clip> --ausgabe DIR [--max N] [--threads 4] [--breite 960] [--puffer 25]
"""
import sys, os, glob, json, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DYN = ("person", "car", "bus", "truck", "van", "bicycle", "minibike", "animal", "boat", "airplane", "train", "tram")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wurzel"); ap.add_argument("clip"); ap.add_argument("--ausgabe", required=True); ap.add_argument("--max", type=int); ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--breite", type=int, default=960); ap.add_argument("--puffer", type=int, default=25); ap.add_argument("--modell", default="nvidia/segformer-b4-finetuned-ade-512-512"); a = ap.parse_args()
    import torch; torch.set_num_threads(a.threads); os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import gebaeude_segment as GS
    proc, model, _ = GS._load(a.modell); ids = [int(k) for k, v in model.config.id2label.items() if any(v.split(",")[0].strip() == d or v.startswith(d) for d in DYN)]
    print("maskierte Klassen:", {i: model.config.id2label[i] for i in ids}, flush=True)
    od = os.path.join(a.ausgabe, a.clip); os.makedirs(od, exist_ok=True); fs = sorted(glob.glob(os.path.join(a.wurzel, a.clip, "vf_*.jpg")))
    if a.max: fs = fs[:a.max]
    rep = {}; t0 = time.time(); k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.puffer + 1, 2 * a.puffer + 1))
    for i, f in enumerate(fs):
        im = cv2.imread(f); H, W = im.shape[:2]; s = a.breite / W; sm = cv2.resize(im, (a.breite, int(H * s)), interpolation=cv2.INTER_AREA)
        with torch.no_grad(): lg = model(**proc(images=cv2.cvtColor(sm, cv2.COLOR_BGR2RGB), return_tensors="pt")).logits
        lg = torch.nn.functional.interpolate(lg, size=sm.shape[:2], mode="bilinear", align_corners=False); seg = lg.argmax(1)[0].numpy()
        dyn = np.isin(seg, ids).astype(np.uint8); dyn = cv2.resize(dyn, (W, H), interpolation=cv2.INTER_NEAREST); dyn = cv2.dilate(dyn, k * 1)
        m = np.where(dyn > 0, 0, 255).astype(np.uint8); cv2.imwrite(os.path.join(od, os.path.basename(f) + ".png"), m); rep[os.path.basename(f)] = round(float((m == 0).mean()), 4)
        if i % 10 == 0: print(f"  {i + 1}/{len(fs)} {time.time() - t0:.0f} s, maskiert {100 * rep[os.path.basename(f)]:.1f} %", flush=True)
    json.dump(dict(klassen=ids, breite=a.breite, puffer=a.puffer, maskiert_anteil=rep, sekunden=round(time.time() - t0)), open(os.path.join(od, "bericht.json"), "w"), indent=1)
    v = np.array(list(rep.values())); print(f"{len(fs)} Frames, maskiert Mittel {100 * v.mean():.1f} %, Maximum {100 * v.max():.1f} %, {time.time() - t0:.0f} s")

if __name__ == "__main__":
    main()
